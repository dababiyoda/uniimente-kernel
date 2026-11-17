"""Forecasting batch B: judgmental forecast aggregation (Layer 5) and scenario forecasts (Layer 3).

Both close directive-named families recorded ABSENT in docs/collaboration/MIND-COVERAGE-2026-10-21.md ("judgmental
forecasting", "scenario forecasts"). Both run on GREG's one cognition path (``greg.cognition.cortex.reason`` ->
isolated worker -> independent verifier -> CognitiveReceipt), registered and withheld like every non-seed family.
Every benchmark here is synthetic: no real dataset is read, so the ``forecast_quantile`` M4 data (reused by P8; see
its erratum) is never touched.

* ``forecast_judgment_pool`` (``pool_judgmental_forecasts``, Layer 5): a panel of forecasters gives probabilities
  for binary events; each forecaster also has a record on resolved events. The pool is a weighted mean of the
  forecasters' log-odds, extremized by one factor ``alpha``:

      w_i = lam * max(SS_i, 0) / sum_j max(SS_j, 0) + (1 - lam) / N,   lam = T / (T + 30)
      SS_i = 1 - Brier_i / (ybar (1 - ybar))                          (skill against in-sample climatology)
      p_e = sigmoid(alpha * sum_i w_i logit(p_ie)),                    alpha = argmax history log-likelihood

  ``alpha`` is fitted on the resolved history only (one-dimensional Newton on a concave log-likelihood, clamped to
  [0.25, 4]). Extremization (alpha > 1) helps when forecasters hold different information; in a shared-information
  panel it over-counts the common evidence and hurts, and the history fit is the only guard (declared below). The
  verifier recomputes the Brier scores, the weights and every pooled probability by its own formulas and checks the
  first-order optimality condition of ``alpha`` (or the sign of the gradient at a clamp bound).

  Baseline: the simple mean of probabilities. Competitor: the per-event median probability (the brief's first-named
  competitor). The best single forecaster by past Brier score is the alternative competitor (``notes``).

* ``forecast_scenarios`` (``scenario_fan_forecast``, Layer 3): a history from a declared process family (a
  two-regime Markov-switching AR(1), or a random walk whose increments are a two-component Gaussian mixture: drift
  plus jumps) is fitted by EM; ``n_paths`` futures are simulated from a declared random stream; fast forward
  selection (Heitsch and Roemisch 2003, after Dupacova, Groewe-Kuska and Roemisch 2003) reduces them to K weighted
  scenarios. The certificate states the Kantorovich (Wasserstein-1, Euclidean path metric) distance from the reduced
  measure to the full simulated measure, and the output states the fan's coverage of the simulated paths per
  horizon. The verifier re-simulates the paths with its own vectorised recursion from the declared parameters and
  stream, recomputes the redistribution weights, recomputes the Kantorovich distance as a transport LP (SciPy
  HiGHS, a different method from nearest assignment), recomputes the coverage and the history log-likelihood (its
  own log-space forward recursion).

  Baseline: persistence with Gaussian random-walk bands as K equally weighted quantile paths. Competitor: K plain
  Monte Carlo samples (equal weights) from the same fitted model. ``forecast_quantile`` is not applicable as a
  competitor: it needs positive series of 60+ points and publishes marginal quantiles, not joint paths.

* ``forecast_recalibration`` (``recalibrate_probabilities``, Layer 3): one judge's probability judgments are
  recalibrated by isotonic regression (pool-adjacent violators) of the resolved outcomes on the judgment. Distinct
  from ``forecast_quantile`` (quantile forecasting) and from ``greg cognition calibration`` /
  ``settlement.outcome_calibration``, which measure calibration but never produce recalibrated probabilities. The
  verifier checks the map against the greatest convex minorant of the cumulative-sum diagram. Baseline: the raw
  judgments. Competitor: Platt scaling.

Everything is read-only computation; no output creates authority.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from statistics import NormalDist

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int, finite

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION",
           "MIND-COVERAGE-2026-10-21: judgmental forecasting ABSENT; scenario forecasts ABSENT")
_N = NormalDist()


def _sigmoid(x):
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


# =================================================================== judgmental forecast pooling
JP_MAX_FORECASTERS, JP_MAX_HISTORY, JP_MAX_EVENTS = 60, 2000, 2000
JP_CLIP = 1e-4                       # probabilities are clipped to [1e-4, 1 - 1e-4] before log-odds
JP_SHRINK_T0 = 30                    # lam = T / (T + 30): skill weights shrink to equal weights on a short record
JP_ALPHA_BOUNDS = (0.25, 4.0)


def _panel(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    hist, outcomes, new = data.get("history_forecasts"), data.get("history_outcomes"), data.get("forecasts")
    if not isinstance(hist, list) or not isinstance(outcomes, list) or not isinstance(new, list):
        raise GenomeError("history_forecasts [T][N], history_outcomes [T] and forecasts [M][N] required")
    if not 1 <= len(hist) <= JP_MAX_HISTORY or len(outcomes) != len(hist) or not 1 <= len(new) <= JP_MAX_EVENTS:
        raise GenomeError(f"1-{JP_MAX_HISTORY} resolved events with one outcome each and 1-{JP_MAX_EVENTS} new events")
    rows = hist + new
    if not all(isinstance(r, list) for r in rows):
        raise GenomeError("each event is a list of forecaster probabilities")
    n = len(rows[0])
    if not 2 <= n <= JP_MAX_FORECASTERS or any(len(r) != n for r in rows):
        raise GenomeError(f"2-{JP_MAX_FORECASTERS} forecasters, the same panel on every event")
    clean = [[finite(p, low=0.0, high=1.0, name="probability") for p in r] for r in rows]
    if not all(type(y) is int and y in (0, 1) for y in outcomes):
        raise GenomeError("history_outcomes are 0 or 1")
    return clean[:len(hist)], list(outcomes), clean[len(hist):], n


def _logit(p):
    p = min(max(p, JP_CLIP), 1 - JP_CLIP)
    return math.log(p / (1 - p))


def _weights(hist, outcomes, n):
    t = len(hist)
    ybar = sum(outcomes) / t
    clim = ybar * (1 - ybar)
    brier = [sum((hist[e][i] - outcomes[e]) ** 2 for e in range(t)) / t for i in range(n)]
    skill = [1 - b / clim for b in brier]
    positive = [max(s, 0.0) for s in skill]
    total = sum(positive)
    lam = t / (t + JP_SHRINK_T0) if total > 0 else 0.0
    w = [lam * (positive[i] / total if total > 0 else 0.0) + (1 - lam) / n for i in range(n)]
    return w, brier, skill, lam


def _fit_alpha(x, y):
    """Newton on the concave log-likelihood sum y log s(a x) + (1 - y) log(1 - s(a x)), clamped to the bounds."""
    lo, hi = JP_ALPHA_BOUNDS
    a = 1.0
    for _ in range(100):
        g = sum(xi * (yi - _sigmoid(a * xi)) for xi, yi in zip(x, y))
        h = sum(xi * xi * _sigmoid(a * xi) * (1 - _sigmoid(a * xi)) for xi in x)
        if h <= 1e-300:
            break
        step = g / h
        new = min(max(a + step, lo), hi)
        if abs(new - a) < 1e-13:
            a = new
            break
        a = new
    return a


def pool_solve(data, budget):
    hist, outcomes, new, n = _panel(data)
    if len(hist) < 10:
        return answer(None, {"history": len(hist)}, status="ABSTAIN",
                      missing=["at least 10 resolved events are needed to estimate skill and extremization"])
    if len(set(outcomes)) < 2:
        return answer(None, {"history": len(hist)}, status="ABSTAIN",
                      missing=["the resolved history has one outcome only: skill and extremization are unidentified"])
    w, brier, skill, lam = _weights(hist, outcomes, n)
    x_hist = [sum(w[i] * _logit(r[i]) for i in range(n)) for r in hist]
    alpha = _fit_alpha(x_hist, outcomes)
    probs = [_sigmoid(alpha * sum(w[i] * _logit(r[i]) for i in range(n))) for r in new]
    return answer({"probabilities": probs, "weights": w, "extremization": alpha},
                  {"method": "skill-weighted log-odds pool, extremized by a factor fitted on the resolved history",
                   "history_brier": brier, "skill_vs_climatology": skill, "shrinkage_lambda": lam,
                   "shrinkage_t0": JP_SHRINK_T0, "alpha_bounds": list(JP_ALPHA_BOUNDS), "clip": JP_CLIP,
                   "history_events": len(hist), "forecasters": n,
                   "regime_warning": "extremization over-counts shared information; alpha is fitted on this panel's "
                                     "own record and is only as good as that record"})


def pool_verify(data, output, certificate):
    """Independent recomputation: Brier by the p^2 - 2py + y expansion, weights from it, log-odds as
    log p - log(1 - p), each pooled probability as 1 / (1 + exp(-alpha x)), and alpha checked against the score
    equation of the history log-likelihood (zero gradient inside the bounds, outward gradient at a bound)."""
    hist, outcomes, new, n = _panel(data)
    if (not isinstance(output, dict) or set(output) != {"probabilities", "weights", "extremization"}
            or not isinstance(output["probabilities"], list) or not isinstance(output["weights"], list)):
        return {"output_shape": False}
    probs, w, a = output["probabilities"], output["weights"], output["extremization"]

    def num(v):
        return type(v) in (int, float) and math.isfinite(v)
    if len(probs) != len(new) or len(w) != n or not all(num(v) for v in probs + w) or not num(a):
        return {"output_shape": False}
    t = len(hist)
    cols = list(zip(*hist))
    ybar = sum(outcomes) / t
    expected_w = None
    if 0 < ybar < 1:
        brier = [(sum(p * p for p in col) - 2 * sum(p * y for p, y in zip(col, outcomes)) + sum(outcomes)) / t
                 for col in cols]
        pos = [max(0.0, 1 - b / (ybar - ybar * ybar)) for b in brier]
        mass = math.fsum(pos)
        lam = t / (t + JP_SHRINK_T0) if mass > 0 else 0.0
        expected_w = [(1 - lam) / n + (lam * v / mass if mass > 0 else 0.0) for v in pos]

    def lo(p):
        q = min(max(p, JP_CLIP), 1 - JP_CLIP)
        return math.log(q) - math.log1p(-q)
    checks = {"output_shape": True,
              "probabilities_valid": all(0.0 < p < 1.0 for p in probs),
              "weights_recomputed_from_history_skill": expected_w is not None and all(
                  abs(u - v) <= 1e-9 for u, v in zip(w, expected_w)),
              "weights_are_a_distribution": all(v >= 0 for v in w) and abs(math.fsum(w) - 1) <= 1e-9,
              "extremization_in_declared_bounds": JP_ALPHA_BOUNDS[0] <= a <= JP_ALPHA_BOUNDS[1]}
    if expected_w is None:
        return checks
    xs = [math.fsum(wi * lo(p) for wi, p in zip(expected_w, r)) for r in hist]
    grad = math.fsum(x * (y - 1 / (1 + math.exp(-a * x))) for x, y in zip(xs, outcomes))
    scale = math.fsum(abs(x) for x in xs) or 1.0
    if a <= JP_ALPHA_BOUNDS[0] + 1e-12:
        checks["extremization_maximises_history_likelihood"] = grad <= 1e-7 * scale
    elif a >= JP_ALPHA_BOUNDS[1] - 1e-12:
        checks["extremization_maximises_history_likelihood"] = grad >= -1e-7 * scale
    else:
        checks["extremization_maximises_history_likelihood"] = abs(grad) <= 1e-7 * scale
    pooled = [1 / (1 + math.exp(-a * math.fsum(wi * lo(p) for wi, p in zip(expected_w, r)))) for r in new]
    checks["probabilities_recomputed"] = all(abs(u - v) <= 1e-9 for u, v in zip(pooled, probs))
    return checks


JP_REGIMES = ("shared", "diverse", "clustered")


def pool_instance(seed):
    """A panel of forecasters on events Y = 1[z + eps > 0], z the sum of Gaussian information blocks, eps ~ N(0, 1).
    Each forecaster sees some blocks and forms the exact probit posterior on them, then reports it through its own
    calibration distortion (slope a_i: < 1 underconfident, > 1 overconfident; bias b_i; noise tau_i on the log-odds)
    rounded to whole percent in [1%, 99%]. Regimes (seed mod 3): shared - one block holds 70% of the signal variance
    and every forecaster sees it; diverse - 90% is split into private blocks; clustered - 80% is split among 2-3
    cluster blocks, each seen by every member of its cluster (correlated forecasters of unequal cluster size).
    Truth: the new events' outcomes and their probabilities given every block (Phi(z))."""
    r = random.Random(f"genome:forecast_judgment_pool:{seed}")
    regime = JP_REGIMES[seed % 3]
    n = r.randint(5, 12)
    t_hist = r.randint(30, 120)
    m = 150
    var = r.uniform(1.5, 4.0)
    blocks, seen = [], [set() for _ in range(n)]          # block variances; forecaster -> visible block indices
    if regime == "shared":
        blocks.append(0.7 * var)
        for i in range(n):
            seen[i].add(0)
        for i in range(n):
            blocks.append(0.3 * var / n)
            seen[i].add(len(blocks) - 1)
    elif regime == "diverse":
        blocks.append(0.1 * var)
        for i in range(n):
            seen[i].add(0)
        for i in range(n):
            blocks.append(0.9 * var / n)
            seen[i].add(len(blocks) - 1)
    else:
        k = r.randint(2, 3)
        cuts = sorted(r.sample(range(1, n), k - 1))
        groups = [list(range(a, b)) for a, b in zip([0] + cuts, cuts + [n])]
        blocks.append(0.1 * var)
        for i in range(n):
            seen[i].add(0)
        for g in groups:
            blocks.append(0.8 * var / k)
            for i in g:
                seen[i].add(len(blocks) - 1)
        for i in range(n):
            blocks.append(0.1 * var / n)
            seen[i].add(len(blocks) - 1)
    slope = [r.uniform(0.6, 1.6) for _ in range(n)]
    bias = [r.gauss(0.0, 0.25) for _ in range(n)]
    noise = [r.uniform(0.1, 0.9) for _ in range(n)]
    total = sum(blocks)

    def event():
        vals = [r.gauss(0.0, math.sqrt(v)) for v in blocks]
        z = sum(vals)
        y = 1 if z + r.gauss(0.0, 1.0) > 0 else 0
        row = []
        for i in range(n):
            s = sum(vals[b] for b in seen[i])
            hidden = total - sum(blocks[b] for b in seen[i])
            p = _N.cdf(s / math.sqrt(1.0 + hidden))
            p = min(max(p, 1e-12), 1 - 1e-12)
            lo = slope[i] * math.log(p / (1 - p)) + bias[i] + noise[i] * r.gauss(0.0, 1.0)
            row.append(min(max(round(_sigmoid(lo), 2), 0.01), 0.99))
        return row, y, _N.cdf(z)
    hist, outcomes = [], []
    for _ in range(t_hist):
        row, y, _ = event()
        hist.append(row)
        outcomes.append(y)
    new, truth_y, truth_p = [], [], []
    for _ in range(m):
        row, y, p = event()
        new.append(row)
        truth_y.append(y)
        truth_p.append(p)
    data = {"history_forecasts": hist, "history_outcomes": outcomes, "forecasts": new}
    return data, {"outcomes": truth_y, "true_probabilities": truth_p, "regime": regime}


def pool_subregion(data):
    """From the data alone: mean pairwise correlation of the forecasters' log-odds on the history (high agreement is
    the shared-information signature) and the record length."""
    hist, _, _, n = _panel(data)
    cols = [[_logit(r[i]) for r in hist] for i in range(n)]
    cors = []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = cols[i], cols[j]
            ma, mb = sum(a) / len(a), sum(b) / len(b)
            va = sum((v - ma) ** 2 for v in a)
            vb = sum((v - mb) ** 2 for v in b)
            if va > 0 and vb > 0:
                cors.append(sum((u - ma) * (v - mb) for u, v in zip(a, b)) / math.sqrt(va * vb))
    mean = sum(cors) / len(cors) if cors else 1.0
    return ("high_agreement" if mean >= 0.75 else "low_agreement") + ("_short_record" if len(hist) < 60
                                                                       else "_long_record")


def pool_score(data, truth, output):
    """Quality: minus the mean Brier score of the pooled probabilities against the new events' outcomes."""
    if not isinstance(output, dict) or not isinstance(output.get("probabilities"), list):
        return {"quality": -1.0, "category": "abstain"}
    probs = output["probabilities"]
    if len(probs) != len(truth["outcomes"]) or not all(
            type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in probs):
        return {"quality": -2.0, "category": "wrong"}
    brier = sum((p - y) ** 2 for p, y in zip(probs, truth["outcomes"])) / len(probs)
    return {"quality": -brier, "category": "correct"}


def pool_mean(data):
    """Baseline: the unweighted mean of the forecasters' probabilities per event."""
    _, _, new, n = _panel(data)
    return {"probabilities": [sum(r) / n for r in new]}


def pool_median(data):
    """Alternative competitor: the per-event median probability."""
    _, _, new, _ = _panel(data)
    out = []
    for r in new:
        s = sorted(r)
        k = len(s)
        out.append(s[k // 2] if k % 2 else (s[k // 2 - 1] + s[k // 2]) / 2)
    return {"probabilities": out}


def pool_best_single(data):
    """Competitor: the forecaster with the lowest Brier score on the resolved history (ties to the first)."""
    hist, outcomes, new, n = _panel(data)
    brier = [sum((r[i] - y) ** 2 for r, y in zip(hist, outcomes)) for i in range(n)]
    best = min(range(n), key=lambda i: (brier[i], i))
    return {"probabilities": [r[best] for r in new]}


# =================================================================== scenario forecasts
SC_MODELS = ("regime_ar", "jump_drift")
SC_MAX_HISTORY, SC_MAX_H, SC_MAX_K = 3000, 48, 20
SC_PATHS = 1000
SC_EM_ITERS = 200


def _scenario_input(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    model = data.get("model")
    if model not in SC_MODELS:
        raise GenomeError(f"model is one of {SC_MODELS}")
    y = data.get("history")
    if not isinstance(y, list) or not 50 <= len(y) <= SC_MAX_HISTORY:
        raise GenomeError(f"history of 50-{SC_MAX_HISTORY} values required")
    y = [finite(v, low=-1e9, high=1e9, name="history value") for v in y]
    h = bounded_int(data.get("horizon"), low=1, high=SC_MAX_H, name="horizon")
    k = bounded_int(data.get("scenarios"), low=2, high=SC_MAX_K, name="scenarios")
    paths = bounded_int(data.get("n_paths", SC_PATHS), low=100, high=4000, name="n_paths")
    if k >= paths:
        raise GenomeError("fewer scenarios than simulated paths required")
    return model, y, h, k, paths


def stream_seed(data) -> int:
    """The declared random stream: numpy PCG64 seeded by the first 4 bytes of sha256 of the canonical input (a
    32-bit seed, inside the receipt's numeric range)."""
    key = {k: data[k] for k in ("model", "history", "horizon", "scenarios") if k in data}
    key["n_paths"] = data.get("n_paths", SC_PATHS)
    return int.from_bytes(hashlib.sha256(json.dumps(key, sort_keys=True).encode()).digest()[:4], "big")


def _npdf(x, mu, sd):
    z = (x - mu) / sd
    return math.exp(-0.5 * z * z) / (sd * math.sqrt(2 * math.pi))


# ------------------------------------------------------------------ fits (EM)
def _fit_mixture(d):
    """Two-component Gaussian mixture of increments by EM; component 1 is the wider (jump) component."""
    n = len(d)
    med = sorted(d)[n // 2]
    mad = sorted(abs(v - med) for v in d)[n // 2] * 1.4826 or (max(d) - min(d)) / 4 or 1.0
    floor = 1e-6 * mad
    lam, m0, s0, m1, s1 = 0.05, med, mad, sum(d) / n, 3 * mad
    prev = -math.inf
    for _ in range(SC_EM_ITERS):
        r1 = []
        ll = 0.0
        for v in d:
            a, b = (1 - lam) * _npdf(v, m0, s0), lam * _npdf(v, m1, s1)
            tot = a + b
            if tot <= 0:
                r1.append(0.0 if abs(v - m0) / s0 < abs(v - m1) / s1 else 1.0)
                ll += -745.0
            else:
                r1.append(b / tot)
                ll += math.log(tot)
        n1 = sum(r1)
        n0 = n - n1
        if n1 < 1e-9 or n0 < 1e-9:
            break
        lam = min(max(n1 / n, 1e-4), 1 - 1e-4)
        m0 = sum((1 - r) * v for r, v in zip(r1, d)) / n0
        m1 = sum(r * v for r, v in zip(r1, d)) / n1
        s0 = max(math.sqrt(sum((1 - r) * (v - m0) ** 2 for r, v in zip(r1, d)) / n0), floor)
        s1 = max(math.sqrt(sum(r * (v - m1) ** 2 for r, v in zip(r1, d)) / n1), floor)
        if ll - prev < 1e-9 * max(1.0, abs(ll)):
            break
        prev = ll
    if lam > 0.5:                              # canonical labels: component 1 (the jump) is the rarer component
        lam, m0, s0, m1, s1 = 1 - lam, m1, s1, m0, s0
    return {"jump_prob": lam, "mu0": m0, "sd0": s0, "mu1": m1, "sd1": s1}


def _ar_ols(x, y, wts):
    sw = sum(wts)
    sx = sum(w * a for w, a in zip(wts, x))
    sy = sum(w * b for w, b in zip(wts, y))
    sxx = sum(w * a * a for w, a in zip(wts, x))
    sxy = sum(w * a * b for w, a, b in zip(wts, x, y))
    det = sw * sxx - sx * sx
    if sw <= 1e-9 or abs(det) <= 1e-12 * max(1.0, sw * sxx):
        return (sy / sw if sw > 0 else 0.0), 0.0
    phi = (sw * sxy - sx * sy) / det
    phi = min(max(phi, -0.995), 0.995)
    c = (sy - phi * sx) / sw
    return c, phi


def _hamilton(y, p):
    """Scaled forward filter of the two-regime AR(1); returns (log-likelihood, filtered probabilities per t)."""
    P = p["transition"]
    pr = list(p["initial"])
    ll, filt = 0.0, []
    for t in range(1, len(y)):
        # the initial distribution is the regime of the first transition (as in the EM), then the chain moves
        pred = [pr[0] * P[0][j] + pr[1] * P[1][j] for j in range(2)] if t > 1 else list(pr)
        f = [_npdf(y[t], p["c"][j] + p["phi"][j] * y[t - 1], p["sd"][j]) for j in range(2)]
        joint = [pred[j] * f[j] for j in range(2)]
        tot = joint[0] + joint[1]
        if tot <= 0:
            tot = 1e-300
            joint = [0.5e-300, 0.5e-300]
        ll += math.log(tot)
        pr = [joint[0] / tot, joint[1] / tot]
        filt.append(pr)
    return ll, filt


def _fit_regime_ar(y):
    """Baum-Welch EM for a two-regime Markov-switching AR(1); initial responsibilities split by the previous level."""
    x, z = y[:-1], y[1:]
    n = len(z)
    med = sorted(x)[len(x) // 2]
    g1 = [0.8 if v > med else 0.2 for v in x]
    resid_sd = (max(y) - min(y)) / 4 or 1.0
    floor = 1e-6 * resid_sd
    P = [[0.95, 0.05], [0.05, 0.95]]
    init = [0.5, 0.5]
    c, phi, sd = [0.0, 0.0], [0.0, 0.0], [resid_sd, resid_sd]
    for j, wts in enumerate(([1 - g for g in g1], g1)):
        c[j], phi[j] = _ar_ols(x, z, wts)
        sw = sum(wts)
        sd[j] = max(math.sqrt(sum(w * (b - c[j] - phi[j] * a) ** 2 for w, a, b in zip(wts, x, z)) / sw), floor)
    prev = -math.inf
    for _ in range(SC_EM_ITERS):
        f = [[_npdf(z[t], c[j] + phi[j] * x[t], sd[j]) + 1e-300 for j in range(2)] for t in range(n)]
        alpha, scale = [], []
        pr = init
        for t in range(n):
            pred = [pr[0] * P[0][j] + pr[1] * P[1][j] for j in range(2)] if t else list(init)
            a = [pred[j] * f[t][j] for j in range(2)]
            s = a[0] + a[1]
            scale.append(s)
            pr = [a[0] / s, a[1] / s]
            alpha.append(pr)
        ll = sum(math.log(s) for s in scale)
        beta = [[1.0, 1.0] for _ in range(n)]
        for t in range(n - 2, -1, -1):
            b = [sum(P[i][j] * f[t + 1][j] * beta[t + 1][j] for j in range(2)) for i in range(2)]
            s = scale[t + 1]
            beta[t] = [b[0] / s, b[1] / s]
        gamma = []
        for t in range(n):
            g = [alpha[t][j] * beta[t][j] for j in range(2)]
            s = g[0] + g[1]
            gamma.append([g[0] / s, g[1] / s])
        xi = [[0.0, 0.0], [0.0, 0.0]]
        for t in range(n - 1):
            m = [[alpha[t][i] * P[i][j] * f[t + 1][j] * beta[t + 1][j] for j in range(2)] for i in range(2)]
            s = sum(m[0]) + sum(m[1])
            for i in range(2):
                for j in range(2):
                    xi[i][j] += m[i][j] / s
        init = [min(max(gamma[0][j], 1e-6), 1 - 1e-6) for j in range(2)]
        init = [init[0] / sum(init), init[1] / sum(init)]
        P = []
        for i in range(2):
            row = [xi[i][j] + 1e-6 for j in range(2)]
            P.append([row[0] / sum(row), row[1] / sum(row)])
        for j in range(2):
            wts = [g[j] for g in gamma]
            c[j], phi[j] = _ar_ols(x, z, wts)
            sw = sum(wts)
            sd[j] = max(math.sqrt(sum(w * (b - c[j] - phi[j] * a) ** 2 for w, a, b in zip(wts, x, z))
                                  / max(sw, 1e-9)), floor)
        if ll - prev < 1e-9 * max(1.0, abs(ll)):
            break
        prev = ll
    if sd[0] > sd[1]:                          # canonical order: regime 0 is the calmer regime
        c, phi, sd = c[::-1], phi[::-1], sd[::-1]
        P = [[P[1][1], P[1][0]], [P[0][1], P[0][0]]]
        init = init[::-1]
    return {"c": c, "phi": phi, "sd": sd, "transition": P, "initial": init}


def _fit(model, y):
    if model == "jump_drift":
        p = _fit_mixture([b - a for a, b in zip(y[:-1], y[1:])])
        ll = sum(math.log((1 - p["jump_prob"]) * _npdf(b - a, p["mu0"], p["sd0"])
                          + p["jump_prob"] * _npdf(b - a, p["mu1"], p["sd1"]) + 1e-300)
                 for a, b in zip(y[:-1], y[1:]))
        return p, ll
    p = _fit_regime_ar(y)
    ll, filt = _hamilton(y, p)
    p = dict(p, last_regime_prob=filt[-1])
    return p, ll


# ------------------------------------------------------------------ simulation (solver: path by path)
def _streams(seed, paths, horizon):
    import numpy as np
    rng = np.random.Generator(np.random.PCG64(seed))
    u0 = rng.random(paths)
    u = rng.random((paths, horizon))
    e = rng.standard_normal((paths, horizon))
    return u0.tolist(), u.tolist(), e.tolist()


def _simulate(model, p, last, horizon, paths, seed):
    u0, u, e = _streams(seed, paths, horizon)
    out = []
    for k in range(paths):
        path, v = [], last
        if model == "jump_drift":
            for h in range(horizon):
                if u[k][h] < p["jump_prob"]:
                    v += p["mu1"] + p["sd1"] * e[k][h]
                else:
                    v += p["mu0"] + p["sd0"] * e[k][h]
                path.append(v)
        else:
            s = 0 if u0[k] < p["last_regime_prob"][0] else 1
            for h in range(horizon):
                s = 0 if u[k][h] < p["transition"][s][0] else 1
                v = p["c"][s] + p["phi"][s] * v + p["sd"][s] * e[k][h]
                path.append(v)
        out.append(path)
    return out


# ------------------------------------------------------------------ fast forward selection
def fast_forward(paths, k):
    """Heitsch-Roemisch fast forward selection on equally weighted paths (Euclidean path metric). Returns
    (selected indices in selection order, weights by nearest-selected redistribution, Kantorovich distance)."""
    import numpy as np
    x = np.asarray(paths, dtype=float)
    n = len(x)
    sq = np.einsum("ij,ij->i", x, x)
    c = np.sqrt(np.maximum(sq[:, None] + sq[None, :] - 2 * x @ x.T, 0.0))
    np.fill_diagonal(c, 0.0)
    prob = np.full(n, 1.0 / n)
    selected = []
    current = c.copy()
    remaining = np.ones(n, dtype=bool)
    for _ in range(k):
        # cost of adding u: sum over unselected i != u of p_i * min(current(i, u), ...) with current already the
        # distance to the nearest selected point (columnwise min) - candidate column u gives min(current[i], c[i,u])
        if selected:
            dmin = current[:, 0]
            cand = np.minimum(dmin[:, None], c)
        else:
            cand = c
        mask = remaining.astype(float)
        cost = (prob * mask) @ cand
        cost[~remaining] = np.inf
        u = int(np.argmin(cost))
        selected.append(u)
        remaining[u] = False
        nearest = c[:, selected].min(axis=1)
        current = nearest[:, None]
    assign = np.argmin(c[:, selected], axis=1)
    weights = np.bincount(assign, weights=prob, minlength=len(selected))
    distance = float(prob @ c[:, selected].min(axis=1))
    return selected, weights.tolist(), distance


def _coverage(paths, scenarios):
    h = len(scenarios[0])
    out = []
    for t in range(h):
        lo = min(s[t] for s in scenarios)
        hi = max(s[t] for s in scenarios)
        out.append(sum(1 for p in paths if lo <= p[t] <= hi) / len(paths))
    return out


def scenario_solve(data, budget):
    model, y, h, k, paths = _scenario_input(data)
    if int((budget or {}).get("compute", SC_PATHS)) < paths:
        return answer(None, {"n_paths": paths}, status="ABSTAIN",
                      missing=["the compute budget is below the declared number of simulated paths"])
    params, ll = _fit(model, y)
    seed = stream_seed(data)
    sims = _simulate(model, params, y[-1], h, paths, seed)
    idx, weights, distance = fast_forward(sims, k)
    scenarios = [sims[i] for i in idx]
    return answer({"scenarios": scenarios, "weights": weights, "coverage": _coverage(sims, scenarios)},
                  {"model": model, "parameters": params, "history_log_likelihood": ll, "stream_seed": seed,
                   "n_paths": paths, "selected_indices": idx, "kantorovich_distance": distance,
                   "metric": "Euclidean norm of the path difference over the horizon",
                   "reduction": "fast forward selection (Heitsch and Roemisch 2003); weights by nearest-selected "
                                "redistribution",
                   "coverage_semantics": "per horizon, the fraction of the simulated paths inside the fan's "
                                         "[min, max] envelope",
                   "fit": "EM to a relative log-likelihood change below 1e-9 or 200 iterations; a local optimum"})


# ------------------------------------------------------------------ verifier (vectorised, written apart)
def _verify_paths(model, p, last, horizon, paths, seed):
    import numpy as np
    rng = np.random.Generator(np.random.PCG64(seed))
    u0 = rng.random(paths)
    u = rng.random((paths, horizon))
    e = rng.standard_normal((paths, horizon))
    if model == "jump_drift":
        jump = u < p["jump_prob"]
        inc = np.where(jump, p["mu1"] + p["sd1"] * e, p["mu0"] + p["sd0"] * e)
        return last + np.cumsum(inc, axis=1)
    c, phi, sd = (np.asarray(p[k], dtype=float) for k in ("c", "phi", "sd"))
    stay0 = np.asarray([p["transition"][0][0], p["transition"][1][0]])
    s = (u0 >= p["last_regime_prob"][0]).astype(int)
    v = np.full(paths, float(last))
    out = np.empty((paths, horizon))
    for t in range(horizon):
        s = (u[:, t] >= stay0[s]).astype(int)
        v = c[s] + phi[s] * v + sd[s] * e[:, t]
        out[:, t] = v
    return out


def _verify_loglik(model, p, y):
    """Log-space forward recursion (log-sum-exp), not the solver's scaled filter."""
    import numpy as np
    y = np.asarray(y, dtype=float)
    if model == "jump_drift":
        d = np.diff(y)
        lp = np.stack([np.log1p(-p["jump_prob"]) - 0.5 * ((d - p["mu0"]) / p["sd0"]) ** 2 - np.log(p["sd0"]),
                       np.log(p["jump_prob"]) - 0.5 * ((d - p["mu1"]) / p["sd1"]) ** 2 - np.log(p["sd1"])])
        return float(np.sum(np.logaddexp(lp[0], lp[1])) - 0.5 * len(d) * math.log(2 * math.pi))
    logP = np.log(np.asarray(p["transition"], dtype=float))
    la = np.log(np.asarray(p["initial"], dtype=float))
    c, phi, sd = (np.asarray(p[k], dtype=float) for k in ("c", "phi", "sd"))
    total = 0.0
    for t in range(1, len(y)):
        mean = c + phi * y[t - 1]
        le = -0.5 * ((y[t] - mean) / sd) ** 2 - np.log(sd) - 0.5 * math.log(2 * math.pi)
        pred = la if t == 1 else np.logaddexp(la[0] + logP[0], la[1] + logP[1])
        joint = pred + le
        norm = float(np.logaddexp(joint[0], joint[1]))
        total += norm
        la = joint - norm
    return total, np.exp(la).tolist()


def _params_ok(model, p):
    def num(v):
        return type(v) in (int, float) and math.isfinite(v)
    if not isinstance(p, dict):
        return False
    if model == "jump_drift":
        return (set(p) == {"jump_prob", "mu0", "sd0", "mu1", "sd1"} and all(num(v) for v in p.values())
                and 0 < p["jump_prob"] < 1 and p["sd0"] > 0 and p["sd1"] > 0)
    keys = {"c", "phi", "sd", "transition", "initial", "last_regime_prob"}
    if set(p) != keys:
        return False
    try:
        flat = list(p["c"]) + list(p["phi"]) + list(p["sd"]) + list(p["initial"]) + list(p["last_regime_prob"]) + [
            v for row in p["transition"] for v in row]
    except TypeError:
        return False
    return (len(p["c"]) == len(p["phi"]) == len(p["sd"]) == len(p["initial"]) == len(p["last_regime_prob"]) == 2
            and len(p["transition"]) == 2 and all(len(r) == 2 for r in p["transition"])
            and all(num(v) for v in flat) and all(v > 0 for v in p["sd"]) and all(abs(v) < 1 for v in p["phi"])
            and all(0 < v < 1 for row in p["transition"] for v in row)
            and all(abs(sum(r) - 1) <= 1e-9 for r in [p["initial"], p["last_regime_prob"], *p["transition"]])
            and all(v > 0 for v in p["initial"]) and all(v >= 0 for v in p["last_regime_prob"]))


def _transport_distance(sims, scenarios, weights):
    """Kantorovich distance between the uniform measure on the simulated paths and the weighted scenarios, as a
    transport linear programme (SciPy HiGHS)."""
    import numpy as np
    from scipy.optimize import linprog
    from scipy.sparse import coo_matrix, vstack
    x, s = np.asarray(sims, dtype=float), np.asarray(scenarios, dtype=float)
    n, k = len(x), len(s)
    cost = np.linalg.norm(x[:, None, :] - s[None, :, :], axis=2).ravel()
    rows = np.repeat(np.arange(n), k)
    cols = np.arange(n * k)
    a_src = coo_matrix((np.ones(n * k), (rows, cols)), shape=(n, n * k))
    a_dst = coo_matrix((np.ones(n * k), (np.tile(np.arange(k), n), cols)), shape=(k, n * k))
    res = linprog(cost, A_eq=vstack([a_src, a_dst]).tocsr(),
                  b_eq=np.concatenate([np.full(n, 1.0 / n), np.asarray(weights, dtype=float)]),
                  bounds=(0, None), method="highs")
    return float(res.fun) if res.status == 0 else None


def scenario_verify(data, output, certificate):
    import numpy as np
    model, y, h, k, paths = _scenario_input(data)
    if (not isinstance(output, dict) or set(output) != {"scenarios", "weights", "coverage"}
            or not isinstance(output["scenarios"], list) or not isinstance(output["weights"], list)
            or not isinstance(output["coverage"], list)):
        return {"output_shape": False}
    sc, w, cov = output["scenarios"], output["weights"], output["coverage"]

    def num(v):
        return type(v) in (int, float) and math.isfinite(v)
    if (len(sc) != k or len(w) != k or len(cov) != h or not all(isinstance(s, list) and len(s) == h for s in sc)
            or not all(num(v) for v in w + cov + [v for s in sc for v in s])):
        return {"output_shape": False}
    cert = certificate if isinstance(certificate, dict) else {}
    checks = {"output_shape": True,
              "weights_positive_and_sum_to_one": all(v > 0 for v in w) and abs(math.fsum(w) - 1) <= 1e-9,
              "declared_model": cert.get("model") == model,
              "stream_seed_bound": cert.get("stream_seed") == stream_seed(data) and cert.get("n_paths") == paths}
    params = cert.get("parameters")
    checks["parameters_in_model_space"] = _params_ok(model, params)
    idx = cert.get("selected_indices")
    checks["indices_distinct_and_in_range"] = (isinstance(idx, list) and len(idx) == k and len(set(idx)) == k
                                               and all(type(i) is int and 0 <= i < paths for i in idx))
    if not (checks["parameters_in_model_space"] and checks["stream_seed_bound"] and checks["declared_model"]):
        return checks
    if model == "jump_drift":
        ll = _verify_loglik(model, params, y)
    else:
        ll, last_prob = _verify_loglik(model, params, y)
        checks["last_regime_probability_recomputed"] = all(
            abs(a - b) <= 1e-7 for a, b in zip(last_prob, params["last_regime_prob"]))
    claimed_ll = cert.get("history_log_likelihood")
    checks["history_log_likelihood_recomputed"] = num(claimed_ll) and abs(ll - claimed_ll) <= 1e-6 * max(
        1.0, abs(ll))
    sims = _verify_paths(model, params, y[-1], h, paths, cert["stream_seed"])
    arr = np.asarray(sc, dtype=float)
    if checks["indices_distinct_and_in_range"]:
        checks["scenarios_are_the_selected_simulated_paths"] = bool(
            np.allclose(sims[idx], arr, rtol=1e-9, atol=1e-9 * max(1.0, float(np.abs(sims).max()))))
    dist_to_sc = np.linalg.norm(sims[:, None, :] - arr[None, :, :], axis=2)
    nearest = dist_to_sc.argmin(axis=1)
    mass = np.bincount(nearest, minlength=k) / paths
    checks["weights_are_the_nearest_redistribution"] = bool(np.allclose(mass, w, rtol=0, atol=1e-9))
    # the envelope is widened by a rounding margin: a scenario on its own boundary is recomputed by a different
    # recursion (cumulative sum, vectorised regime steps) and may differ from the solver's value in the last bits
    eps = 1e-9 * max(1.0, float(np.abs(sims).max()))
    lo, hi = arr.min(axis=0) - eps, arr.max(axis=0) + eps
    inside = ((sims >= lo) & (sims <= hi)).mean(axis=0)
    checks["coverage_recomputed"] = bool(np.allclose(inside, cov, rtol=0, atol=1e-12))
    lp = _transport_distance(sims, arr, w) if checks["weights_positive_and_sum_to_one"] else None
    claimed = cert.get("kantorovich_distance")
    checks["kantorovich_distance_recomputed_by_transport_lp"] = (
        lp is not None and num(claimed) and abs(lp - claimed) <= 1e-6 * max(1.0, abs(lp)))
    return checks


# ------------------------------------------------------------------ benchmark
SC_TRUE_FUTURES = 200


def _true_step(model, p, s, v, r):
    if model == "jump_drift":
        inc = p["mu"] + p["sd"] * r.gauss(0, 1)
        if r.random() < p["jump_prob"]:
            inc += p["jump_mean"] + p["jump_sd"] * r.gauss(0, 1)
        return s, v + inc
    s = s if r.random() < p["stay"][s] else 1 - s
    return s, p["c"][s] + p["phi"][s] * v + p["sd"][s] * r.gauss(0, 1)


def scenario_instance(seed):
    """Even seeds: a two-regime Markov-switching AR(1) (calm and volatile regimes with different means). Odd seeds:
    a random walk with drift and compound-Bernoulli Gaussian jumps. History of 200-400 points; horizon 12; 5-10
    scenarios. Truth: the realised continuation and 200 independent futures from the true process and the true
    state at the forecast origin (the true conditional distribution)."""
    r = random.Random(f"genome:forecast_scenarios:{seed}")
    model = SC_MODELS[seed % 2]
    if model == "jump_drift":
        sd = r.uniform(0.5, 2.0)
        p = {"mu": r.uniform(-0.1, 0.1) * sd, "sd": sd, "jump_prob": r.uniform(0.02, 0.1),
             "jump_mean": r.choice((-1, 1)) * r.uniform(2, 5) * sd, "jump_sd": r.uniform(1, 3) * sd}
    else:
        sd0 = r.uniform(0.3, 1.0)
        mean0 = r.uniform(-5, 5)
        mean1 = mean0 + r.choice((-1, 1)) * r.uniform(1, 4) * sd0 * 3
        phi = [r.uniform(0.3, 0.9), r.uniform(0.3, 0.9)]
        p = {"phi": phi, "sd": [sd0, sd0 * r.uniform(1.5, 3.0)],
             "c": [mean0 * (1 - phi[0]), mean1 * (1 - phi[1])], "stay": [r.uniform(0.9, 0.99), r.uniform(0.9, 0.99)]}
    n = r.randint(200, 400)
    s, v = 0, (p["c"][0] / (1 - p["phi"][0]) if model == "regime_ar" else 0.0)
    for _ in range(100 if model == "regime_ar" else 0):
        s, v = _true_step(model, p, s, v, r)
    history = []
    for _ in range(n):
        s, v = _true_step(model, p, s, v, r)
        history.append(round(v, 9))
    h, k = 12, r.randint(5, 10)
    futures = []
    for _ in range(SC_TRUE_FUTURES):
        ss, vv, path = s, history[-1], []
        for _ in range(h):
            ss, vv = _true_step(model, p, ss, vv, r)
            path.append(vv)
        futures.append(path)
    data = {"model": model, "history": history, "horizon": h, "scenarios": k}
    return data, {"realised": futures[0], "futures": futures, "true_parameters": p}


def scenario_subregion(data):
    return data.get("model", "unknown")


def _energy(scenarios, weights, futures):
    import numpy as np
    x = np.asarray(scenarios, dtype=float)
    q = np.asarray(weights, dtype=float)
    f = np.asarray(futures, dtype=float)
    spread = 0.5 * float(q @ np.linalg.norm(x[:, None, :] - x[None, :, :], axis=2) @ q)
    fit = np.linalg.norm(f[:, None, :] - x[None, :, :], axis=2) @ q
    return float(fit.mean()) - spread


def scenario_score(data, truth, output):
    """Quality: minus the energy score of the weighted scenario set, averaged over the true conditional futures
    (the realised path is the first of them), in units of the history's increment standard deviation x sqrt(H)."""
    if not isinstance(output, dict) or not isinstance(output.get("scenarios"), list):
        return {"quality": -1e6, "category": "abstain"}
    sc, w = output["scenarios"], output.get("weights")
    h = data["horizon"]
    if (not isinstance(w, list) or len(w) != len(sc) or not sc
            or not all(isinstance(s, list) and len(s) == h for s in sc)
            or not all(type(v) in (int, float) and math.isfinite(v) for v in w + [v for s in sc for v in s])
            or any(v < 0 for v in w) or abs(sum(w) - 1) > 1e-6):
        return {"quality": -1e6, "category": "wrong"}
    y = data["history"]
    d = [b - a for a, b in zip(y[:-1], y[1:])]
    m = sum(d) / len(d)
    scale = math.sqrt(sum((v - m) ** 2 for v in d) / len(d) * h) or 1.0
    return {"quality": -_energy(sc, w, truth["futures"]) / scale, "category": "correct"}


def scenario_persistence(data):
    """Baseline: persistence (last value) with Gaussian random-walk bands: K paths at the (k - 0.5) / K quantiles of
    N(y_T, sigma^2 h), sigma the increment standard deviation, equally weighted."""
    model, y, h, k, _ = _scenario_input(data)
    d = [b - a for a, b in zip(y[:-1], y[1:])]
    m = sum(d) / len(d)
    sd = math.sqrt(sum((v - m) ** 2 for v in d) / (len(d) - 1))
    zs = [_N.inv_cdf((j + 0.5) / k) for j in range(k)]
    return {"scenarios": [[y[-1] + z * sd * math.sqrt(t) for t in range(1, h + 1)] for z in zs],
            "weights": [1.0 / k] * k}


def scenario_random_k(data):
    """Competitor: K plain Monte Carlo paths from the same fitted model (an independent stream), equally weighted."""
    model, y, h, k, _ = _scenario_input(data)
    params, _ = _fit(model, y)
    sims = _simulate(model, params, y[-1], h, k, stream_seed(data) ^ 0x5DEECE66D)
    return {"scenarios": sims, "weights": [1.0 / k] * k}


# =================================================================== probability recalibration (isotonic)
RC_MAX = 20000
RC_SHAPES = ("logit_linear", "s_curve", "binned_bias", "power")


def _recal_input(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    past, outcomes, new = data.get("past_judgments"), data.get("past_outcomes"), data.get("judgments")
    if not isinstance(past, list) or not isinstance(outcomes, list) or not isinstance(new, list):
        raise GenomeError("past_judgments [T], past_outcomes [T] and judgments [M] required")
    if not 1 <= len(past) <= RC_MAX or len(outcomes) != len(past) or not 1 <= len(new) <= RC_MAX:
        raise GenomeError(f"1-{RC_MAX} past judgments with one outcome each and 1-{RC_MAX} new judgments")
    past = [finite(p, low=0.0, high=1.0, name="judgment") for p in past]
    new = [finite(p, low=0.0, high=1.0, name="judgment") for p in new]
    if not all(type(y) is int and y in (0, 1) for y in outcomes):
        raise GenomeError("past_outcomes are 0 or 1")
    return past, list(outcomes), new


def _pav(xs, ys):
    """Pool-adjacent-violators on outcomes grouped by distinct judgment: (distinct x, fitted value per x)."""
    groups = {}
    for x, y in zip(xs, ys):
        s, w = groups.get(x, (0.0, 0))
        groups[x] = (s + y, w + 1)
    keys = sorted(groups)
    blocks = []                                   # [sum, weight, first index, last index]
    for i, x in enumerate(keys):
        s, w = groups[x]
        blocks.append([s, w, i, i])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] >= blocks[-1][0] / blocks[-1][1]:
            s2, w2, _, last = blocks.pop()
            blocks[-1][0] += s2
            blocks[-1][1] += w2
            blocks[-1][3] = last
    fitted = [0.0] * len(keys)
    for s, w, a, b in blocks:
        for i in range(a, b + 1):
            fitted[i] = s / w
    return keys, fitted


def _interp(keys, fitted, x):
    if x <= keys[0]:
        return fitted[0]
    if x >= keys[-1]:
        return fitted[-1]
    lo, hi = 0, len(keys) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if keys[mid] <= x:
            lo = mid
        else:
            hi = mid
    t = (x - keys[lo]) / (keys[hi] - keys[lo])
    return fitted[lo] + t * (fitted[hi] - fitted[lo])


def recal_solve(data, budget):
    past, outcomes, new = _recal_input(data)
    if len(past) < 20 or len(set(outcomes)) < 2 or len(set(past)) < 2:
        return answer(None, {"past": len(past)}, status="ABSTAIN",
                      missing=["at least 20 resolved judgments with both outcomes and two distinct judgment values"])
    keys, fitted = _pav(past, outcomes)
    probs = [_interp(keys, fitted, x) for x in new]
    return answer({"probabilities": probs, "calibration_map": {"judgments": keys, "calibrated": fitted}},
                  {"method": "isotonic regression (pool-adjacent violators) of outcomes on the judgment; linear "
                             "interpolation between distinct judgment values, constant beyond the ends",
                   "resolved_judgments": len(past), "distinct_judgments": len(keys)})


def recal_verify(data, output, certificate):
    """The calibration map is checked against the greatest convex minorant of the cumulative-sum diagram (an
    independent characterisation of the isotonic least-squares fit, computed by a monotone-chain hull), and every
    new probability is re-interpolated from it."""
    past, outcomes, new = _recal_input(data)
    if (not isinstance(output, dict) or set(output) != {"probabilities", "calibration_map"}
            or not isinstance(output["probabilities"], list) or not isinstance(output["calibration_map"], dict)):
        return {"output_shape": False}
    cmap = output["calibration_map"]
    keys, vals, probs = cmap.get("judgments"), cmap.get("calibrated"), output["probabilities"]

    def num(v):
        return type(v) in (int, float) and math.isfinite(v)
    if (not isinstance(keys, list) or not isinstance(vals, list) or len(keys) != len(vals) or not keys
            or len(probs) != len(new) or not all(num(v) for v in keys + vals + probs)):
        return {"output_shape": False}
    distinct = sorted(set(past))
    count = {x: 0 for x in distinct}
    hits = {x: 0 for x in distinct}
    for x, y in zip(past, outcomes):
        count[x] += 1
        hits[x] += y
    # cumulative-sum diagram points (W_i, S_i); the GCM slope over each step is the isotonic fit
    pts = [(0, 0)]
    for x in distinct:
        pts.append((pts[-1][0] + count[x], pts[-1][1] + hits[x]))
    hull = []
    for p in pts:
        while len(hull) >= 2 and ((hull[-1][0] - hull[-2][0]) * (p[1] - hull[-2][1])
                                  - (hull[-1][1] - hull[-2][1]) * (p[0] - hull[-2][0])) <= 0:
            hull.pop()
        hull.append(p)
    expected, h = [], 0
    for i in range(1, len(pts)):
        while hull[h + 1][0] < pts[i][0]:
            h += 1
        expected.append((hull[h + 1][1] - hull[h][1]) / (hull[h + 1][0] - hull[h][0]))
    checks = {"output_shape": True, "map_on_the_distinct_resolved_judgments": keys == distinct,
              "map_nondecreasing": all(a <= b + 1e-12 for a, b in zip(vals, vals[1:])),
              "probabilities_in_unit_interval": all(0.0 <= p <= 1.0 for p in probs + vals)}
    checks["map_is_the_isotonic_least_squares_fit"] = (keys == distinct and all(
        abs(a - b) <= 1e-9 for a, b in zip(vals, expected)))
    if keys != distinct:
        return checks
    import bisect
    re = []
    for x in new:
        j = bisect.bisect_right(distinct, x)
        if j == 0:
            re.append(expected[0])
        elif j == len(distinct):
            re.append(expected[-1])
        else:
            x0, x1 = distinct[j - 1], distinct[j]
            re.append(expected[j - 1] + (expected[j] - expected[j - 1]) * (x - x0) / (x1 - x0))
    checks["probabilities_reinterpolated"] = all(abs(a - b) <= 1e-9 for a, b in zip(re, probs))
    return checks


def _distort(shape, p, k):
    lo = math.log(p / (1 - p))
    if shape == "logit_linear":
        return _sigmoid(k["slope"] * lo + k["bias"])
    if shape == "s_curve":                      # over-extreme in the middle, under-extreme in the tails
        return _sigmoid(k["slope"] * math.tanh(lo / k["width"]) * k["width"] + k["bias"])
    if shape == "power":
        return p ** k["gamma"]
    q = _sigmoid(k["slope"] * lo + k["bias"])   # binned_bias: whole-tenth rounding of a distorted judgment
    return round(q * 10) / 10


def recal_instance(seed):
    """A judge reports a distorted version of each event's true probability (shape by seed mod 4: logit-linear
    slope/bias, an S-curve, a power curve, or a distorted judgment rounded to tenths), rounded to whole percent; the
    resolved record is 40-2000 judgments (log-uniform), the new set 400. Truth: outcomes and true probabilities."""
    r = random.Random(f"genome:forecast_recalibration:{seed}")
    shape = RC_SHAPES[seed % 4]
    k = {"slope": r.uniform(0.5, 2.0), "bias": r.gauss(0.0, 0.5), "width": r.uniform(0.7, 2.0),
         "gamma": r.uniform(0.4, 2.5)}
    a, b = r.uniform(0.5, 3), r.uniform(0.5, 3)
    t = int(round(math.exp(r.uniform(math.log(40), math.log(2000)))))

    def draw():
        p = min(max(r.betavariate(a, b), 1e-4), 1 - 1e-4)
        j = min(max(round(_distort(shape, p, k), 2), 0.0), 1.0)
        return j, (1 if r.random() < p else 0), p
    past, outcomes = [], []
    for _ in range(t):
        j, y, _ = draw()
        past.append(j)
        outcomes.append(y)
    new, ys, ps = [], [], []
    for _ in range(400):
        j, y, p = draw()
        new.append(j)
        ys.append(y)
        ps.append(p)
    return ({"past_judgments": past, "past_outcomes": outcomes, "judgments": new},
            {"outcomes": ys, "true_probabilities": ps, "shape": shape})


def recal_subregion(data):
    n = len(data.get("past_outcomes", []))
    return "short_record" if n < 200 else "long_record"


def recal_score(data, truth, output):
    """Quality: minus the mean squared error of the recalibrated probabilities against the true probabilities
    (the outcome-free part of the Brier score: E[Brier] = this + E[p(1 - p)])."""
    if not isinstance(output, dict) or not isinstance(output.get("probabilities"), list):
        return {"quality": -1.0, "category": "abstain"}
    probs = output["probabilities"]
    if len(probs) != len(truth["true_probabilities"]) or not all(
            type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in probs):
        return {"quality": -2.0, "category": "wrong"}
    return {"quality": -sum((p - q) ** 2 for p, q in zip(probs, truth["true_probabilities"])) / len(probs),
            "category": "correct"}


def recal_identity(data):
    """Baseline: the raw judgments, taken as calibrated."""
    _, _, new = _recal_input(data)
    return {"probabilities": list(new)}


def recal_platt(data):
    """Competitor: Platt scaling, logistic regression of the outcome on logit(judgment) with an intercept (Newton,
    judgments clipped to [0.005, 0.995] before the log-odds)."""
    past, outcomes, new = _recal_input(data)

    def lo(p):
        p = min(max(p, 0.005), 0.995)
        return math.log(p / (1 - p))
    x = [lo(p) for p in past]
    a, b = 1.0, 0.0
    for _ in range(100):
        g0 = g1 = h00 = h01 = h11 = 0.0
        for xi, yi in zip(x, outcomes):
            s = _sigmoid(a * xi + b)
            g0 += (yi - s) * xi
            g1 += yi - s
            v = s * (1 - s) + 1e-12
            h00 += v * xi * xi
            h01 += v * xi
            h11 += v
        det = h00 * h11 - h01 * h01
        if det <= 1e-18:
            break
        da, db = (h11 * g0 - h01 * g1) / det, (h00 * g1 - h01 * g0) / det
        a, b = a + da, b + db
        if abs(da) + abs(db) < 1e-12:
            break
    return {"probabilities": [_sigmoid(a * lo(p) + b) for p in new]}


# =================================================================== genomes
_DEV = "seeds 0-9 dev, held-out seeds fixed by the admission freeze"

INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="meta.forecast.judgment_logodds_pool", version="1.0.0", family="forecast_judgment_pool",
            layer=5, operation="pool_judgmental_forecasts", epistemic_class="prediction",
            subgeometry="probability forecasts for binary events from a panel of judges of unequal skill and "
                        "calibration, with a shared resolved record; information may be shared or diverse",
            source_provenance="Genest and Zidek (1986) logarithmic opinion pools; Satopaa et al. (2014) extremized "
                              "log-odds aggregation; Baron et al. (2014) and Ungar et al. (2012, Good Judgment "
                              "Project) on extremization; Brier (1950) score",
            buildability="BUILDABLE_NOW",
            native_representation="history_forecasts [T][N], history_outcomes [T] in {0,1}, forecasts [M][N]",
            required_inputs=("history_forecasts", "history_outcomes", "forecasts"),
            output_contract={"probabilities": "[M] pooled probability per new event",
                             "weights": "[N] forecaster weights", "extremization": "alpha"},
            algorithm_or_runtime="Brier skill vs in-sample climatology -> shrunk skill weights -> weighted mean "
                                 "log-odds -> extremization alpha by 1-D Newton maximum likelihood on the history",
            parameters={"shrinkage": "lam = T / (T + 30)", "alpha_bounds": list(JP_ALPHA_BOUNDS), "clip": JP_CLIP},
            memory_model="stateless (refits on every call)",
            learning_rule="weights and alpha re-estimated from the supplied resolved record each call",
            composition_inputs=("forecasts from judges, models or crowds", "their resolved record"),
            composition_outputs=("pooled event probabilities", "forecaster weights"),
            evidence_type="forecast_distribution",
            verification_method="independent recomputation of Brier scores (expanded form), weights, log-odds and "
                                "every pooled probability; alpha checked against the score equation of the history "
                                "log-likelihood",
            confidence_semantics="pooled probabilities; their calibration is measured by Brier score on resolved "
                                 "events, never asserted",
            resource_profile="O((T + M) N) arithmetic; pure Python", latency_profile="milliseconds",
            known_strengths=("diverse-information panels: extremization recovers the evidence the mean averages away",
                             "down-weights forecasters whose record is worse than climatology",
                             "fully recomputable from the record"),
            known_failure_modes=(
                "shared information: when forecasters hold the same evidence, extremization over-counts it and makes "
                "the pool overconfident; the history fit guards against this only if the record is long enough and "
                "from the same regime",
                "a short record makes skill weights and alpha noisy (shrinkage to equal weights is the only guard)",
                "one extremization factor for every event; no per-event or per-cluster correction for correlated "
                "forecasters", "assumes the record's forecasters are the new events' forecasters (complete panel)"),
            counterindications=("panels known to copy one another or one source", "fewer than about 30 resolved "
                                "events", "regime change between the record and the new events"),
            abstention_conditions=("fewer than 10 resolved events", "the resolved record has one outcome only"),
            benchmark_suite="simulated panels of 5-12 probit-Bayesian forecasters with distorted calibration "
                            "(slope 0.6-1.6, bias, log-odds noise, whole-percent rounding) on 30-120 resolved and 150 "
                            "new events; regimes by seed mod 3: shared information, diverse information, clustered "
                            "(correlated groups); quality minus mean Brier on the new events; " + _DEV,
            baseline="simple mean of the probabilities",
            competitor="the per-event median probability",
            lineage=LINEAGE),
        solve=pool_solve, verify=pool_verify, instance=pool_instance, score=pool_score,
        baseline=pool_mean, competitor=pool_median, subregion=pool_subregion, tolerance=1e-9,
        notes={"alternative_competitor": "pool_best_single (the forecaster with the lowest Brier score on the "
                                         "resolved record), the brief's second competitor; weaker than the median "
                                         "on development seeds; reported, not used by the rule",
               "score": "-mean Brier against the simulated outcomes; true probabilities are in the truth for "
                        "diagnostics only"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.forecast.scenario_reduction_fan", version="1.0.0", family="forecast_scenarios",
            layer=3, operation="scenario_fan_forecast", epistemic_class="prediction",
            subgeometry="joint future paths of a univariate series from a declared regime-switching AR(1) or "
                        "jump-drift random walk, reduced to K weighted scenarios",
            source_provenance="Hamilton (1989) Markov-switching filter; Dempster, Laird and Rubin (1977) EM; "
                              "Dupacova, Groewe-Kuska and Roemisch (2003) and Heitsch and Roemisch (2003) scenario "
                              "reduction by fast forward selection; Gneiting and Raftery (2007) energy score",
            buildability="BUILDABLE_NOW",
            native_representation="history [T], declared model family, horizon H, K scenarios, n_paths",
            required_inputs=("model", "history", "horizon", "scenarios"),
            output_contract={"scenarios": "[K][H] paths", "weights": "[K] summing to 1",
                             "coverage": "[H] fraction of simulated paths inside the fan envelope"},
            algorithm_or_runtime="EM fit of the declared model -> n_paths simulations from a declared PCG64 stream "
                                 "-> fast forward selection -> nearest-scenario redistribution",
            parameters={"n_paths": SC_PATHS, "em_iterations": SC_EM_ITERS, "metric": "Euclidean path norm"},
            memory_model="stateless (refits on every call)",
            learning_rule="model re-fitted from each request's history; nothing persists",
            composition_inputs=("history",), composition_outputs=("weighted scenarios for stochastic programming",),
            evidence_type="forecast_distribution",
            verification_method="vectorised re-simulation from the declared parameters and stream; nearest "
                                "redistribution weights recomputed; Kantorovich distance recomputed as a transport LP "
                                "(SciPy HiGHS); coverage and the history log-likelihood (log-space forward pass) "
                                "recomputed",
            confidence_semantics="a K-point approximation of the fitted model's predictive distribution, at the "
                                 "certified Kantorovich distance from the full simulated set; model error is not in "
                                 "that distance",
            resource_profile="EM O(T x iterations); simulation O(n_paths H); reduction O(K n_paths^2) with numpy",
            latency_profile="about a second at n_paths 1000",
            dependency="scipy",
            known_strengths=("certified reduction distance to the simulated distribution",
                             "keeps tail and regime scenarios a random K-sample can miss",
                             "weighted scenarios feed stochastic programmes directly"),
            known_failure_modes=(
                "EM finds a local optimum; a misfit model carries its error into every scenario (the certificate "
                "bounds the reduction error only)", "two regimes and one AR lag only; jumps are one Gaussian component",
                "the Kantorovich distance is to the simulated set, not to the true distribution",
                "k-means/k-medoids scenario clustering is a plausible stronger competitor that the brief did not "
                "assign and that is not measured here"),
            counterindications=("seasonal or multivariate series", "model families other than the two declared",
                                "horizons where parameter uncertainty dominates (it is not simulated)"),
            abstention_conditions=("compute budget below n_paths",),
            benchmark_suite="simulated series: even seeds two-regime Markov-switching AR(1), odd seeds drift plus "
                            "compound-Bernoulli Gaussian jumps; 200-400 history points, horizon 12, 5-10 scenarios; "
                            "quality minus the energy score averaged over 200 true conditional futures, scaled by "
                            "the increment sd x sqrt(H); " + _DEV,
            baseline="persistence with Gaussian random-walk bands as K equally weighted quantile paths",
            competitor="K plain Monte Carlo paths from the same fitted model, equally weighted",
            lineage=LINEAGE),
        solve=scenario_solve, verify=scenario_verify, instance=scenario_instance, score=scenario_score,
        baseline=scenario_persistence, competitor=scenario_random_k, subregion=scenario_subregion, tolerance=1e-9,
        notes={"forecast_quantile": "not a competitor here: it requires positive series of 60+ points and publishes "
                                    "marginal quantiles, not joint weighted paths"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.forecast.isotonic_recalibration", version="1.0.0", family="forecast_recalibration",
            layer=3, operation="recalibrate_probabilities", epistemic_class="prediction",
            subgeometry="one judge's probability judgments with a resolved record, miscalibrated by an unknown "
                        "monotone distortion",
            source_provenance="Ayer et al. (1955) and Barlow et al. (1972) pool-adjacent violators; Zadrozny and "
                              "Elkan (2002) isotonic calibration; Platt (1999) scaling",
            buildability="BUILDABLE_NOW",
            native_representation="past_judgments [T], past_outcomes [T] in {0,1}, judgments [M]",
            required_inputs=("past_judgments", "past_outcomes", "judgments"),
            output_contract={"probabilities": "[M] recalibrated probabilities",
                             "calibration_map": "{judgments: [distinct], calibrated: [nondecreasing]}"},
            algorithm_or_runtime="isotonic least squares of outcomes on the judgment (PAV over distinct judgments); "
                                 "linear interpolation between them",
            parameters={}, memory_model="stateless (refits on every call)",
            learning_rule="the map is re-fitted from the supplied record each call",
            composition_inputs=("probability judgments from a person, model or pool", "their resolved record"),
            composition_outputs=("recalibrated probabilities", "a monotone calibration map"),
            evidence_type="forecast_distribution",
            verification_method="the map is compared with the greatest convex minorant of the cumulative-sum "
                                "diagram (monotone-chain hull, an independent characterisation of the isotonic fit); "
                                "every probability is re-interpolated",
            confidence_semantics="the outcome frequency the record shows for each judgment level, made monotone; "
                                 "no interval is claimed",
            resource_profile="O(T log T)", latency_profile="milliseconds",
            known_strengths=("any monotone distortion, including S-curves and binned judgments",
                             "no parametric assumption", "certifiable by the convex-minorant characterisation"),
            known_failure_modes=("short records: step maps of few blocks overfit and can output 0 or 1 exactly",
                                 "Platt scaling wins when the distortion is logit-linear and the record is short",
                                 "a non-monotone judge (worse at the extremes than in the middle) cannot be fixed by a "
                                 "monotone map", "assumes the judge's distortion is stable from the record to the "
                                 "new judgments"),
            counterindications=("fewer than about 100 resolved judgments", "a judge whose calibration is changing"),
            abstention_conditions=("fewer than 20 resolved judgments", "one outcome only",
                                   "a single distinct judgment value"),
            benchmark_suite="simulated judges: Beta event probabilities distorted by a logit-linear, S-curve, power "
                            "or rounded-to-tenths distortion (seed mod 4), whole-percent reports; 40-2000 resolved "
                            "and 400 new judgments; quality minus mean squared error to the true probabilities; "
                            + _DEV,
            baseline="the raw judgments (identity map)", competitor="Platt scaling (logistic on logit judgment)",
            lineage=LINEAGE + ("distinct from forecast_quantile (quantile forecasting) and from settlement."
                               "outcome_calibration (which measures calibration and does not recalibrate)",)),
        solve=recal_solve, verify=recal_verify, instance=recal_instance, score=recal_score,
        baseline=recal_identity, competitor=recal_platt, subregion=recal_subregion, tolerance=1e-9,
        notes={"score": "outcome-free squared error to the simulated true probabilities; it ranks methods as the "
                        "expected Brier score does, with less noise"}),
]
