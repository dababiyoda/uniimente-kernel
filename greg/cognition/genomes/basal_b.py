"""Layer 1 basal intelligences, batch B: value-tiered token-bucket admission (rate control) and a normalised LMS
online learner (a small local learner).

The 2026-10-21 coverage record (``docs/collaboration/MIND-COVERAGE-2026-10-21.md``) lists "rate control" and
"evaluate small local learners" as ABSENT from Layer 1 (section 31 condition 1 names both). Each mechanism here is a
cheap, inspectable, bounded-memory primitive on GREG's one cognition path (``greg.cognition.cortex.reason`` ->
isolated worker -> independent verifier -> CognitiveReceipt), chosen for a behaviour GREG needs:

* ``basal_token_bucket`` (``rate_limited_admission``): admitting jobs or API calls online under a provider's
  token-bucket contract (rate r, burst b) so that nothing GREG sends is refused, while protecting tokens for valuable
  requests when load exceeds the rate. The mechanism is a token bucket whose admission threshold rises as the bucket
  empties (a quantile of the last ``TB_WINDOW`` request values). Verified by an arrival-curve conformance check
  (every admitted window of k requests spans at least (k - b) / r), a value recomputation and an independent replay
  of the declared rule. Effect, not metaphor: a "reflex" here is a fixed rule with bounded memory and nothing more.
* ``basal_nlms`` (``online_linear_predict``): one-step-ahead prediction of a numeric quantity (a job's run time or
  cost) from its features, learning online with the normalised least-mean-squares rule. Verified by an independent
  vectorised replay of the declared update, the prequential error and the final weights.

Everything is read-only computation: no files, network, subprocesses or environment access, and no output of any
method here creates authority. Development seeds 0-9 and this lane's declared review range 9400-9439 only.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right, insort
import math
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int, finite

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 4 (restore the full five-layer scope)",
           "docs/collaboration/MIND-COVERAGE-2026-10-21.md (Layer 1 ABSENT: rate control, small local learners)")


def _common(**kw):
    return dict(buildability="BUILDABLE_NOW", lineage=LINEAGE, **kw)


def _mapping(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    return data


def _num(x):
    return type(x) in (int, float) and math.isfinite(x)


# =================================================================== 1. value-tiered token-bucket admission
TB_MAX_REQUESTS, TB_NATIVE_REQUESTS = 2000, 1000
TB_WINDOW = 256                  # bounded memory: the last TB_WINDOW request values
TB_EPS = 1e-12                   # admission needs tokens >= 1 - TB_EPS
TB_CONFORM_TOL = 1e-7            # arrival-curve tolerance in tokens


def _tb_input(data):
    data = _mapping(data)
    times, values = data.get("request_times"), data.get("request_values")
    if (not isinstance(times, list) or not isinstance(values, list) or len(times) != len(values)
            or not 1 <= len(times) <= TB_MAX_REQUESTS):
        raise GenomeError(f"request_times and request_values: equal-length lists of 1-{TB_MAX_REQUESTS}")
    t = [finite(x, low=0.0, high=1e9, name="request time") for x in times]
    if any(b < a for a, b in zip(t, t[1:])):
        raise GenomeError("request_times must be non-decreasing (requests in arrival order)")
    v = [finite(x, low=0.0, high=1e9, name="request value") for x in values]
    rate = finite(data.get("token_rate"), low=1e-9, high=1e9, name="token_rate")
    if rate <= 0:
        raise GenomeError("token_rate must be positive")
    burst = bounded_int(data.get("bucket_size"), low=1, high=100_000, name="bucket_size")
    return t, v, rate, burst


def _tiered_bucket(t, v, rate, burst):
    """The mechanism: refill, then admit iff a token is available and the request's rank among the last TB_WINDOW
    values is at least 1 - fill (fill = tokens / bucket size). A full bucket admits anything; an emptying bucket
    admits only the most valuable requests."""
    tokens, prev = float(burst), t[0]
    ordered, window, admitted = [], [], []
    for i, (ti, vi) in enumerate(zip(t, v)):
        tokens = min(float(burst), tokens + rate * (ti - prev))
        prev = ti
        if ordered:
            lo, hi = bisect_left(ordered, vi), bisect_right(ordered, vi)
            rank = (lo + 0.5 * (hi - lo)) / len(ordered)
        else:
            rank = 1.0
        if tokens >= 1.0 - TB_EPS and rank >= 1.0 - tokens / burst:
            admitted.append(i)
            tokens -= 1.0
        window.append(vi)
        insort(ordered, vi)
        if len(window) > TB_WINDOW:
            old = window.pop(0)
            del ordered[bisect_left(ordered, old)]
    return admitted


def _tb_output(v, admitted):
    return {"admitted": admitted, "admitted_count": len(admitted),
            "admitted_value": float(math.fsum(v[i] for i in admitted))}


def token_bucket_solve(data, budget):
    t, v, rate, burst = _tb_input(data)
    if len(t) > TB_NATIVE_REQUESTS:
        return answer(None, {"reason": "beyond the native size"}, status="ABSTAIN",
                      missing=[f"more than {TB_NATIVE_REQUESTS} requests in one decision batch"])
    out = _tb_output(v, _tiered_bucket(t, v, rate, burst))
    return answer(out, {"rule": "value_tiered_token_bucket", "window": TB_WINDOW, "eps": TB_EPS,
                        "initial_tokens": burst, "tie_rank": "less + 0.5 * equal over the window"})


def _conforms(times_admitted, rate, burst):
    """Arrival-curve test written apart from any bucket simulation: a sequence conforms to a (b, r) token bucket that
    starts full iff every k + 1 consecutive admissions span at least (k + 1 - b) / r."""
    import numpy as np
    a = np.asarray(times_admitted, dtype=float)
    for k in range(burst, len(a)):
        if np.any(rate * (a[k:] - a[:-k]) + burst - (k + 1) < -TB_CONFORM_TOL):
            return False
    return True


def _replay_tiered(t, v, rate, burst, window):
    """Independent replay of the declared rule (plain lists and counting, no bisect structure)."""
    tokens, prev, recent, out = float(burst), t[0], [], []
    for i in range(len(t)):
        tokens = min(float(burst), tokens + rate * (t[i] - prev))
        prev = t[i]
        if recent:
            less = sum(1 for x in recent if x < v[i])
            equal = sum(1 for x in recent if x == v[i])
            rank = (less + 0.5 * equal) / len(recent)
        else:
            rank = 1.0
        if tokens >= 1.0 - TB_EPS and rank >= 1.0 - tokens / burst:
            out.append(i)
            tokens -= 1.0
        recent = (recent + [v[i]])[-window:]
    return out


def _tb_shape(output, n):
    return (isinstance(output, dict) and set(output) == {"admitted", "admitted_count", "admitted_value"}
            and isinstance(output["admitted"], list) and all(type(i) is int and 0 <= i < n for i in output["admitted"])
            and output["admitted"] == sorted(set(output["admitted"])) and type(output["admitted_count"]) is int
            and _num(output["admitted_value"]))


def token_bucket_verify(data, output, certificate):
    t, v, rate, burst = _tb_input(data)
    if not _tb_shape(output, len(t)):
        return {"output_shape": False}
    adm = output["admitted"]
    value = math.fsum(v[i] for i in adm)
    cert = certificate if isinstance(certificate, dict) else {}
    window = cert.get("window")
    return {"output_shape": True, "count_recomputed": output["admitted_count"] == len(adm),
            "value_recomputed": abs(output["admitted_value"] - value) <= 1e-9 * max(1.0, abs(value)),
            "conforms_to_the_token_bucket": _conforms([t[i] for i in adm], rate, burst),
            "declared_rule": cert.get("rule") == "value_tiered_token_bucket" and window == TB_WINDOW,
            "rule_replayed": type(window) is int and window == TB_WINDOW
            and _replay_tiered(t, v, rate, burst, window) == adm}


def _arrival_times(r, kind, n, load):
    if kind == "bursty":            # on/off modulated Poisson: bursts at 6x the mean rate
        out, now, on = [], 0.0, True
        while len(out) < n:
            lam = load * (3.0 if on else 0.4)
            now += r.expovariate(lam)
            out.append(now)
            if r.random() < 0.05:
                on = not on
        return out
    if kind == "diurnal":           # sinusoidal rate by thinning
        out, now = [], 0.0
        while len(out) < n:
            now += r.expovariate(2 * load)
            if r.random() < 0.5 * (1 + math.sin(now / 40.0)):
                out.append(now)
        return out
    out, now = [], 0.0
    for _ in range(n):
        now += r.expovariate(load)
        out.append(now)
    return out


def _request_values(r, n):
    shape = r.choice(("lognormal", "pareto", "classes"))
    if shape == "lognormal":
        return [round(r.lognormvariate(0, 1), 4) for _ in range(n)], shape
    if shape == "pareto":
        return [round(r.paretovariate(1.5), 4) for _ in range(n)], shape
    return [round(r.uniform(20, 60), 2) if r.random() < 0.15 else round(r.uniform(1, 3), 2) for _ in range(n)], shape


class _quiet_stdout:
    """Evaluation side only: route file descriptor 1 to /dev/null for the duration (the engine writes there)."""

    def __enter__(self):
        import os
        import sys
        sys.stdout.flush()
        self.saved = os.dup(1)
        self.null = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self.null, 1)
        return self

    def __exit__(self, *exc):
        import os
        os.dup2(self.saved, 1)
        os.close(self.saved)
        os.close(self.null)
        return False


def token_bucket_optimum(t, v, rate, burst):
    """Evaluation side only: the offline (hindsight) maximum admitted value by SciPy HiGHS on a 0/1 program with
    explicit token states: tau_i <= b, tau_i <= tau_{i-1} - x_{i-1} + r (t_i - t_{i-1}), x_i <= tau_i."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import lil_matrix
    n = len(t)
    c = np.concatenate([-np.asarray(v, dtype=float), np.zeros(n)])        # x_0..x_{n-1}, tau_0..tau_{n-1}
    a = lil_matrix((2 * n - 1, 2 * n))
    hi = np.zeros(2 * n - 1)
    for i in range(n):
        a[i, i], a[i, n + i] = 1.0, -1.0                                   # x_i - tau_i <= 0
    for i in range(1, n):
        row = n + i - 1
        a[row, n + i], a[row, n + i - 1], a[row, i - 1] = 1.0, -1.0, 1.0   # tau_i - tau_{i-1} + x_{i-1} <= r dt
        hi[row] = rate * (t[i] - t[i - 1])
    with _quiet_stdout():          # HiGHS's MIP heuristics print diagnostics on the C stdout
        res = milp(c, constraints=[LinearConstraint(a.tocsr(), -np.inf, hi)],
                   bounds=Bounds(np.zeros(2 * n), np.concatenate([np.ones(n), np.full(n, float(burst))])),
                   integrality=np.concatenate([np.ones(n), np.zeros(n)]), options={"mip_rel_gap": 0.0})
    if not res.success:
        raise GenomeError("offline optimum not found")
    return float(-res.fun)


def token_bucket_instance(seed):
    r = random.Random(f"genome:basal_token_bucket:{seed}")
    kind = ("poisson_overload", "bursty", "diurnal", "underload")[seed % 4]
    n = r.randint(150, 400)
    burst = r.randint(2, 20)
    load = r.uniform(0.5, 0.95) if kind == "underload" else r.uniform(1.3, 4.0)
    times = [round(x, 6) for x in _arrival_times(r, kind, n, load)]
    values, shape = _request_values(r, n)
    data = {"request_times": times, "request_values": values, "token_rate": 1.0, "bucket_size": burst}
    return data, {"optimum": token_bucket_optimum(times, values, 1.0, burst), "kind": kind, "values": shape,
                  "offered_load": load}


def token_bucket_subregion(data):
    t, v, rate, burst = _tb_input(data)
    span = max(t[-1] - t[0], 1e-9)
    load = len(t) / span / rate
    return "underload" if load <= 1.0 else ("overload" if load <= 2.5 else "heavy_overload")


def token_bucket_score(data, truth, output):
    t, v, rate, burst = _tb_input(data)
    fallback = math.fsum(v[i] for i in _plain_admitted(t, rate, burst)) / truth["optimum"]
    if output is None:
        return {"quality": fallback, "category": "abstain"}
    if not _tb_shape(output, len(t)) or not _conforms([t[i] for i in output["admitted"]], rate, burst):
        return {"quality": -1.0, "category": "wrong"}          # a refused request: the contract was broken
    value = math.fsum(v[i] for i in output["admitted"])
    if abs(output["admitted_value"] - value) > 1e-9 * max(1.0, value):
        return {"quality": -1.0, "category": "wrong"}
    return {"quality": value / truth["optimum"], "category": "correct"}


def _plain_admitted(t, rate, burst):
    tokens, prev, out = float(burst), t[0], []
    for i, ti in enumerate(t):
        tokens = min(float(burst), tokens + rate * (ti - prev))
        prev = ti
        if tokens >= 1.0 - TB_EPS:
            out.append(i)
            tokens -= 1.0
    return out


def token_bucket_plain(data):
    """Baseline: the plain token bucket (admit whenever a token is available, first come first served)."""
    t, v, rate, burst = _tb_input(data)
    return _tb_output(v, _plain_admitted(t, rate, burst))


def token_bucket_bid_price(data):
    """Competitor: online bid-price control from revenue management (fluid approximation). At each request, with the
    arrival rate and value distribution estimated from the last TB_WINDOW requests, the expected demand over the
    refill horizon H = b / r is compared with the tokens available over it (current tokens + r H); the bid price is
    the value quantile that rations demand to that supply, and a request is admitted iff a token is available and its
    value reaches the bid price."""
    t, v, rate, burst = _tb_input(data)
    tokens, prev, out = float(burst), t[0], []
    horizon = burst / rate
    for i, ti in enumerate(t):
        tokens = min(float(burst), tokens + rate * (ti - prev))
        prev = ti
        lo = max(0, i - TB_WINDOW)
        price = 0.0
        if i - lo >= 2 and ti > t[lo]:
            lam = (i - lo) / (ti - t[lo])
            demand, supply = lam * horizon, tokens + rate * horizon
            if demand > supply:
                past = sorted(v[lo:i])
                price = past[min(len(past) - 1, int((1.0 - supply / demand) * len(past)))]
        if tokens >= 1.0 - TB_EPS and v[i] >= price:
            out.append(i)
            tokens -= 1.0
    return _tb_output(v, out)


# =================================================================== 2. normalised LMS online learner
LMS_MU, LMS_EPS = 0.5, 1e-6
LMS_MAX_N, LMS_MAX_D, LMS_NATIVE_D = 20000, 50, 20
LMS_DIVERGED_NMSE = 2.0          # a prequential error above twice the target variance is a false answer
RLS_FORGET, RLS_DELTA = 0.995, 1000.0


def _lms_input(data):
    data = _mapping(data)
    xs, ys = data.get("feature_stream"), data.get("target_stream")
    if (not isinstance(xs, list) or not isinstance(ys, list) or len(xs) != len(ys)
            or not 2 <= len(xs) <= LMS_MAX_N):
        raise GenomeError(f"feature_stream and target_stream: equal-length lists of 2-{LMS_MAX_N}")
    if not isinstance(xs[0], list) or not 1 <= len(xs[0]) <= LMS_MAX_D:
        raise GenomeError(f"feature vectors of 1-{LMS_MAX_D} numbers")
    d = len(xs[0])
    x = []
    for row in xs:
        if not isinstance(row, list) or len(row) != d:
            raise GenomeError("every feature vector has the same length")
        x.append([finite(a, low=-1e6, high=1e6, name="feature") for a in row])
    y = [finite(a, low=-1e9, high=1e9, name="target") for a in ys]
    return x, y


def _nlms(x, y, mu, eps):
    """The mechanism (pure Python): predict with the current weights (bias last), then update by the normalised LMS
    rule w += mu e x / (eps + |x|^2)."""
    d = len(x[0]) + 1
    w = [0.0] * d
    preds = []
    for row, target in zip(x, y):
        xt = row + [1.0]
        p = sum(a * b for a, b in zip(w, xt))
        preds.append(p)
        g = mu * (target - p) / (eps + sum(a * a for a in xt))
        w = [a + g * b for a, b in zip(w, xt)]
    return preds, w


def _mse(preds, y):
    return math.fsum((a - b) ** 2 for a, b in zip(preds, y)) / len(y)


def _lms_output(preds, y, w):
    return {"predictions": [float(p) for p in preds], "prequential_mse": float(_mse(preds, y)),
            "final_weights": [float(a) for a in w]}


def nlms_solve(data, budget):
    x, y = _lms_input(data)
    if len(x[0]) > LMS_NATIVE_D:
        return answer(None, {"reason": "beyond the native dimension"}, status="ABSTAIN",
                      missing=[f"more than {LMS_NATIVE_D} features: use a batch or regularised method"])
    preds, w = _nlms(x, y, LMS_MU, LMS_EPS)
    if not all(math.isfinite(p) for p in preds + w):
        return answer(None, {"reason": "diverged"}, status="UNKNOWN", missing=["the online update diverged"])
    return answer(_lms_output(preds, y, w), {"rule": "nlms", "mu": LMS_MU, "eps": LMS_EPS, "initial_weights": "zeros",
                                             "bias": "last weight, constant feature 1"})


def _lms_shape(output, n, d):
    return (isinstance(output, dict) and set(output) == {"predictions", "prequential_mse", "final_weights"}
            and isinstance(output["predictions"], list) and len(output["predictions"]) == n
            and all(_num(p) for p in output["predictions"]) and _num(output["prequential_mse"])
            and isinstance(output["final_weights"], list) and len(output["final_weights"]) == d + 1
            and all(_num(a) for a in output["final_weights"]))


def _close(a, b, scale):
    import numpy as np
    return bool(np.all(np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)) <= 1e-9 * scale + 1e-12))


def nlms_verify(data, output, certificate):
    """Independent vectorised replay (NumPy, written apart from the solver) of the declared rule."""
    import numpy as np
    x, y = _lms_input(data)
    n, d = len(x), len(x[0])
    if not _lms_shape(output, n, d):
        return {"output_shape": False}
    cert = certificate if isinstance(certificate, dict) else {}
    mu, eps = cert.get("mu"), cert.get("eps")
    declared = cert.get("rule") == "nlms" and mu == LMS_MU and eps == LMS_EPS
    xa = np.hstack([np.asarray(x, dtype=float), np.ones((n, 1))])
    ya = np.asarray(y, dtype=float)
    w = np.zeros(d + 1)
    preds = np.empty(n)
    norms = eps + np.einsum("ij,ij->i", xa, xa) if declared else None
    if declared:
        for i in range(n):
            preds[i] = xa[i] @ w
            w = w + (mu * (ya[i] - preds[i]) / norms[i]) * xa[i]
    scale = max(1.0, float(np.max(np.abs(ya))))
    claimed = np.asarray(output["predictions"], dtype=float)
    mse = float(np.mean((claimed - ya) ** 2))
    return {"output_shape": True, "declared_rule": declared,
            "predictions_replayed": declared and _close(output["predictions"], preds, scale),
            "weights_replayed": declared and _close(output["final_weights"], w, scale),
            "prequential_mse_recomputed": abs(output["prequential_mse"] - mse) <= 1e-9 * max(1.0, mse)}


def nlms_instance(seed):
    r = random.Random(f"genome:basal_nlms:{seed}")
    kind = ("stationary", "drift", "switch", "heavy_tail", "correlated")[seed % 5]
    n, d = r.randint(300, 1500), r.randint(2, 10)
    w = [r.gauss(0, 2) for _ in range(d)] + [r.uniform(-5, 5)]
    noise = r.uniform(0.1, 1.0)
    xs, ys, clean = [], [], []
    prev = [r.gauss(0, 1) for _ in range(d)]
    for i in range(n):
        if kind == "correlated":
            base = r.gauss(0, 1)
            row = [0.95 * p + 0.3 * base + 0.05 * r.gauss(0, 1) for p in prev]
            prev = row
        else:
            row = [r.gauss(0, 1) for _ in range(d)]
        if kind == "drift":
            w = [a + r.gauss(0, 0.03) for a in w]
        if kind == "switch" and i == n // 2:
            w = [r.gauss(0, 2) for _ in range(d)] + [r.uniform(-5, 5)]
        f = sum(a * b for a, b in zip(w, row + [1.0]))
        e = (r.gauss(0, noise) if kind != "heavy_tail"
             else noise * r.gauss(0, 1) / math.sqrt(max(1e-9, r.gammavariate(1.0, 1.0))))
        xs.append([round(a, 6) for a in row])
        clean.append(f)
        ys.append(round(f + e, 6))
    return {"feature_stream": xs, "target_stream": ys}, {"kind": kind, "noise_sd": noise, "clean_targets": clean}


def nlms_subregion(data):
    x, y = _lms_input(data)
    return ("short" if len(x) < 800 else "long") + ("_low_dim" if len(x[0]) <= 5 else "_high_dim")


def nlms_score(data, truth, output):
    x, y = _lms_input(data)
    mean = math.fsum(y) / len(y)
    var = max(1e-12, math.fsum((a - mean) ** 2 for a in y) / len(y))
    if output is None:
        return {"quality": -_mse(_running_mean(y), y) / var, "category": "abstain"}
    if not _lms_shape(output, len(x), len(x[0])):
        return {"quality": -LMS_DIVERGED_NMSE - 1.0, "category": "wrong"}
    nmse = _mse(output["predictions"], y) / var
    if abs(output["prequential_mse"] - _mse(output["predictions"], y)) > 1e-9 * max(1.0, nmse * var) \
            or nmse > LMS_DIVERGED_NMSE:
        return {"quality": -LMS_DIVERGED_NMSE - 1.0, "category": "wrong"}
    return {"quality": -nmse, "category": "correct"}


def _running_mean(y):
    out, total = [], 0.0
    for i, a in enumerate(y):
        out.append(total / i if i else 0.0)
        total += a
    return out


def nlms_running_mean(data):
    """Baseline: predict the running mean of the targets seen so far (0 before the first)."""
    x, y = _lms_input(data)
    preds = _running_mean(y)
    return {"predictions": preds, "prequential_mse": _mse(preds, y), "final_weights": [0.0] * len(x[0]) + [
        preds[-1] if len(y) == 1 else math.fsum(y) / len(y)]}


def nlms_rls(data):
    """Competitor: exponentially weighted recursive least squares (forgetting 0.995, P0 = 1000 I), the exact
    weighted least-squares solution updated per sample (NumPy)."""
    import numpy as np
    x, y = _lms_input(data)
    n, d = len(x), len(x[0]) + 1
    xa = np.hstack([np.asarray(x, dtype=float), np.ones((n, 1))])
    w, p = np.zeros(d), np.eye(d) * RLS_DELTA
    preds = []
    for i in range(n):
        xi = xa[i]
        pred = float(xi @ w)
        preds.append(pred)
        px = p @ xi
        k = px / (RLS_FORGET + xi @ px)
        w = w + k * (y[i] - pred)
        p = (p - np.outer(k, px)) / RLS_FORGET
    if not all(math.isfinite(a) for a in preds):
        return None
    return {"predictions": preds, "prequential_mse": _mse(preds, y), "final_weights": [float(a) for a in w]}


# =================================================================== registration
INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="basal.rate.value_tiered_token_bucket", version="1.0.0", family="basal_token_bucket",
            layer=1, operation="rate_limited_admission", epistemic_class="optimization",
            subgeometry="online admission of a request stream under a token-bucket rate contract (rate r, burst b) "
                        "with per-request values: GREG's job queue or a provider's API rate limit",
            source_provenance="Turner (1986) leaky/token bucket; Cruz (1991) (sigma, rho) arrival curves; nested "
                              "protection levels from revenue management (Littlewood 1972) as a fill-dependent "
                              "threshold",
            native_representation="request arrival times (non-decreasing), request values, token rate, bucket size",
            required_inputs=("request_times", "request_values", "token_rate", "bucket_size"),
            output_contract={"admitted": "[request index] ascending", "admitted_count": "int",
                             "admitted_value": "float"},
            algorithm_or_runtime="token bucket (starts full, continuous refill); a request is admitted iff a token is "
                                 f"available and its rank among the last {TB_WINDOW} values is at least 1 - fill",
            parameters={"window": TB_WINDOW, "eps": TB_EPS, "native_requests": TB_NATIVE_REQUESTS},
            memory_model=f"bounded: the token level and the last {TB_WINDOW} request values",
            learning_rule="none beyond the sliding value window (the threshold adapts to the recent value "
                          "distribution; no parameter is fitted)",
            composition_inputs=("request stream with values", "provider rate contract"),
            composition_outputs=("admitted requests", "admitted value"),
            evidence_type="control_trace",
            verification_method="arrival-curve conformance (every k + 1 consecutive admissions span at least "
                                "(k + 1 - b) / r) checked apart from any bucket simulation; admitted count and value "
                                "recomputed; the declared rule replayed by separate code and required to give the "
                                "same decisions",
            confidence_semantics="the admitted stream provably conforms to the declared contract (no request is "
                                 "refused by a provider enforcing exactly that contract); no optimality claim",
            resource_profile=f"O(n log {TB_WINDOW}) time, O({TB_WINDOW}) memory",
            latency_profile="sub-millisecond per request; milliseconds per batch at benchmark size",
            known_strengths=("never breaks the rate contract", "admits everything when the bucket stays full "
                             "(underload)", "protects tokens for high-value requests under overload with no model"),
            known_failure_modes=("the threshold reads only the last window: a shift in the value distribution is "
                                 "followed with a lag",
                                 "it can leave tokens unused when high-value requests stop arriving after the "
                                 "bucket has emptied (it refills to full and then admits anything)",
                                 "values are the caller's: misstated priorities give a confident wrong ranking",
                                 "the contract is the declared one: a provider enforcing a different window refuses "
                                 "requests this rule admitted"),
            counterindications=("requests that can wait in a queue (a scheduler or delay-tolerant shaper does better)",
                                "known future arrivals (use the offline optimum)",
                                "sliding-window or concurrency limits that are not token buckets"),
            abstention_conditions=(f"more than {TB_NATIVE_REQUESTS} requests in one batch",),
            benchmark_suite="Poisson overload (load 1.3-4), on/off bursty, diurnal (thinned sinusoid) and underload "
                            "(load 0.5-0.95) arrivals; lognormal, Pareto(1.5) or two-class priority values; 150-400 "
                            "requests, bucket 2-20, rate 1; quality is admitted value over the offline hindsight "
                            "optimum (SciPy HiGHS 0/1 program with token states); seeds 0-9 dev, held-out seeds "
                            "fixed by the admission freeze",
            baseline="plain token bucket (admit whenever a token is available)",
            competitor="online bid-price control (fluid approximation over the refill horizon from the last 256 "
                       "requests' rate and value distribution)",
            dependency=None, **_common()),
        solve=token_bucket_solve, verify=token_bucket_verify, instance=token_bucket_instance,
        score=token_bucket_score, baseline=token_bucket_plain, competitor=token_bucket_bid_price,
        subregion=token_bucket_subregion, tolerance=1e-9),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="basal.learner.nlms", version="1.0.0", family="basal_nlms", layer=1,
            operation="online_linear_predict", epistemic_class="prediction",
            subgeometry="one-step-ahead prediction of a numeric quantity (job run time, cost) from a feature vector, "
                        "learning online from each realised value",
            source_provenance="Widrow and Hoff (1960) LMS; Nagumo and Noda (1967) normalised LMS; Haykin, Adaptive "
                              "Filter Theory (RLS competitor)",
            native_representation="feature vectors and realised targets in arrival order",
            required_inputs=("feature_stream", "target_stream"),
            output_contract={"predictions": "[float] one per sample, made before its target",
                             "prequential_mse": "float", "final_weights": "[float] (bias last)"},
            algorithm_or_runtime=f"normalised LMS, mu {LMS_MU}, eps {LMS_EPS}, zero initial weights, bias feature 1",
            parameters={"mu": LMS_MU, "eps": LMS_EPS, "native_dimension": LMS_NATIVE_D},
            memory_model="bounded: d + 1 weights",
            learning_rule="w <- w + mu e x / (eps + |x|^2) after each realised target",
            composition_inputs=("job features", "realised run times or costs"),
            composition_outputs=("next-job prediction", "prequential error"),
            evidence_type="control_trace",
            verification_method="independent vectorised NumPy replay of the declared update (predictions and final "
                                "weights to 1e-9 relative); prequential error recomputed from the claimed predictions",
            confidence_semantics="the predictions are exactly what the declared rule makes on this stream; their "
                                 "accuracy is measured, not promised",
            resource_profile="O(n d) time, O(d) memory",
            latency_profile="microseconds per sample",
            known_strengths=("constant memory and O(d) per update", "tracks slow drift without a window parameter",
                             "the step is normalised, so one outlier moves the weights by a bounded amount"),
            known_failure_modes=("slow convergence on correlated (ill-conditioned) features",
                                 "a fixed step trades tracking speed against steady-state noise; mu 0.5 is not tuned "
                                 "to the stream",
                                 "linear in the given features: a nonlinear relation is only approximated"),
            counterindications=("stationary data with correlated features (recursive least squares converges "
                                "faster)", "nonlinear targets (use a nonlinear model)",
                                "more than 20 features with few samples"),
            abstention_conditions=(f"more than {LMS_NATIVE_D} features",
                                   "UNKNOWN when the update diverges to a non-finite value"),
            benchmark_suite="linear streams with stationary, random-walk-drifting and abruptly switching weights, "
                            "heavy-tailed (Student-t, df 2) noise and strongly correlated features; 300-1500 samples, "
                            "2-10 features; quality is minus the prequential MSE over the target variance; seeds "
                            "0-9 dev, held-out seeds fixed by the admission freeze",
            baseline="running mean of the targets seen so far",
            competitor="exponentially weighted recursive least squares (forgetting 0.995, P0 = 1000 I)",
            dependency=None, **_common()),
        solve=nlms_solve, verify=nlms_verify, instance=nlms_instance, score=nlms_score,
        baseline=nlms_running_mean, competitor=nlms_rls, subregion=nlms_subregion, tolerance=1e-9),
]
