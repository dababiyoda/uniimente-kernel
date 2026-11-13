"""Layer 3 intelligences, pack B: Monte Carlo expectation, BCa bootstrap intervals, small integer programs.

Three executables on GREG's one cognition path (``greg.cognition.cortex.reason`` -> isolated worker ->
independent verifier -> CognitiveReceipt). Each is an ordinary, well-understood method; the genome records
where it is natively competent, what it is compared against and what its verifier can and cannot certify.

* ``mc_expectation`` (``mc_expectation_estimate``): E[f(X)] for independent declared coordinates (normal,
  uniform, exponential) and five closed-form function families, by antithetic Monte Carlo with control
  variates (pair-averaged centred moments whose means are known exactly), their coefficients fitted on a
  pilot block and applied to the independent main block (unbiased), and an iid CLT interval. Verified by
  recomputing, in pure Python from the declared uniform stream, every inverse-CDF transform, f value and
  control with its own bound on each value's rounding; the pilot's least-squares normal equations at the
  certificate's coefficients; the main block's adjusted mean and its standard error (each to a small fraction of
  the recomputed standard error, which is never below the estimate's own rounding noise, all in units of mean |f|)
  and the interval arithmetic. The verifier cannot certify that the
  interval covers the true expectation: that coverage is asymptotic and is measured against analytic truth
  only by ``score``.
* ``bootstrap_ci`` (``bca_bootstrap_interval``): bias-corrected and accelerated bootstrap interval for the
  mean or median of an iid sample (``scipy.stats.bootstrap``'s resampling and BCa formulas, with each
  replicate's side of the estimate decided exactly and the mean's jackknife centred). Verified by regenerating
  the declared resample indices from the seed and recomputing the bootstrap distribution, the exact bias
  correction, the jackknife acceleration in exact integer arithmetic, the adjusted levels and the type-7
  percentiles with its own code. Coverage of
  the true parameter is not certifiable from one sample; it is measured over seeds by ``score``.
* ``milp_optimize`` (``milp_integer_optimize``): bounded pure-integer linear programs with integer data by
  ``scipy.optimize.milp`` (HiGHS, zero relative gap). Verified with exact integer arithmetic (integrality,
  bounds, every row, the objective). Optimality is certified only when an exact LP-relaxation dual bound
  (sign-feasible multipliers from ``linprog`` marginals, evaluated in rational arithmetic) meets the objective
  after rounding, or when the solver's own scan of a small box agrees and the verifier's own enumeration
  confirms it; otherwise the answer claims feasibility only and reports the proven gap.

Everything is read-only computation: no files, network, subprocesses or environment access, and no output
of any method here creates authority.
"""
from __future__ import annotations

from fractions import Fraction
import math
import random
import statistics
from statistics import NormalDist
import sys

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int, finite

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "greg/cognition/genomes/solvers_b.py (mc_importance, bayes_interval, dp_knapsack patterns)")
_N = NormalDist()


def _common(**kw):
    return dict(buildability="BUILDABLE_NOW", memory_model="stateless",
                learning_rule="none (competence settles per geometry through GREG outcomes)", lineage=LINEAGE, **kw)


def _abstain(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="ABSTAIN", missing=[reason])


def _unknown(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="UNKNOWN", missing=[reason])


def _mapping(data):
    """Every input is a JSON object; anything else is invalid input, never an AttributeError."""
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    return data


def _cert(certificate):
    """A verifier reads the certificate defensively: a non-object certificate binds nothing."""
    return certificate if isinstance(certificate, dict) else {}


def _real(value):
    return type(value) is float and math.isfinite(value)


# =================================================================== 1. Monte Carlo expectation
MC_DISTRIBUTIONS = ("normal", "uniform", "exponential")
MC_FUNCTIONS = ("exp_linear", "cos_product", "power_product", "call_on_sum", "indicator_sum")
MC_INPUT_DIM, MC_NATIVE_DIM = 32, 8
MC_NATIVE_EVALUATIONS = (1024, 16384)  # below: too few for a pilot fit; above: over the verifier's budget
MC_BASELINE_N = 1000                   # the baseline's fixed sample size
MC_REPLICATES = 16                     # independent scrambled Sobol sequences in the competitor's t interval
MC_MIN_HITS = 20                       # fewer indicator hits (or misses), or positive call payoffs: UNKNOWN
MC_U_FLOOR = 2.0 ** -53                # uniforms are floored so 0 never reaches an inverse CDF
# Floating-point floor on the standard error, relative to mean |f|: the pairs of an odd f cancel to rounding
# noise, so |pair mean| is no scale for it.
MC_SE_FLOOR = 1e-12
# Rounding bound on one evaluation of f, in units of 2^-53 times the magnitudes it is computed from: how far two
# faithful double-precision evaluations of the declared formula at one point can differ (BLAS or exactly rounded
# sums, scipy's ndtri or NormalDist.inv_cdf, numpy's or libm's exp and log1p). The worst case is about 29 units
# (eight summands, ndtri against inv_cdf measured to 11 units of |z|); 64 keeps a factor of two.
MC_NOISE_C = 64.0
_EPS = 2.0 ** -53
# Below the normal range a result's rounding is absolute: an exp or a sum whose result is subnormal differs between
# implementations by units of 2^-1074 whatever its size (numpy's and libm's exp: 1 unit, measured; a sum of subnormal
# products depends on where it is rounded). Every rounding bound carries MC_NOISE_C of them on top of its share of the
# magnitudes.
_MC_TINY = MC_NOISE_C * 2.0 ** -1074
_LN_MAX = math.log(sys.float_info.max)   # exp(s) overflows above this
MC_POWER_MAX = 6
# Everything after the draws is computed in units of mean |f|, so no square or sum overflows. A certificate's
# intercept and control coefficients are bounded in those units before any arithmetic: an honest pilot fit is
# many orders of magnitude inside the bound, and with it every intermediate stays far below the overflow threshold.
MC_COEF_MAX = 1e12
# Recomputation tolerances, as fractions of the recomputed standard error. A shift of 1% of a standard error changes
# the interval's coverage by under 0.1 percentage points and is still about 45 units in the last place of mean |f|
# when the floor sets the standard error; the solver and this verifier differed by at most 3.3e-4 (estimate) and
# 1.3e-7 (standard error) of a standard error over dev seeds, review seeds 3000-3999 and fuzzed inputs.
MC_EST_TOL, MC_SE_TOL = 1e-2, 1e-4
# The standard error is never below MC_NOISE_SE times the bound on the estimate's own rounding noise (the mean, over
# the main block, of the per-pair evaluation bounds): an interval cannot be narrower than the arithmetic that
# produced it, and the 1%-of-a-standard-error estimate check then covers two faithful evaluations of f with a factor
# of two. When control variates leave only rounding noise (f nearly a quadratic in the base coordinates, large
# cancelling terms in w . x) this, not MC_SE_FLOOR, sets the standard error.
MC_NOISE_SE = 2.0 / MC_EST_TOL
# Below the smallest normal double a number's rounding is a fixed 2^-1075, not a share of it. Every recomputation
# tolerance is a fraction of the standard error, so an answer needs a normal standard error (the solver keeps a factor
# of two). An estimate, a fitted coefficient or a value of f may be subnormal: the checks bound their absolute rounding.
# The rule is on the standard error, not on mean |f|: f near 1e-300 has a standard error that keeps its last places.
_MC_UNDERFLOW = ("near underflow: the standard error is below twice the smallest normal double (4.45e-308), so the "
                 "reported numbers' fixed rounding is no longer negligible against it")


def _mc(data):
    _mapping(data)
    coords = data.get("coordinates")
    if not isinstance(coords, list) or not 1 <= len(coords) <= MC_INPUT_DIM:
        raise GenomeError(f"coordinates: a list of 1-{MC_INPUT_DIM} independent coordinate distributions")
    parsed = []
    for c in coords:
        kind = c.get("distribution") if isinstance(c, dict) else None
        if kind == "normal" and set(c) == {"distribution", "mean", "sd"}:
            parsed.append(("normal", finite(c["mean"], low=-1e3, high=1e3, name="mean"),
                           finite(c["sd"], low=1e-6, high=1e3, name="sd")))
        elif kind == "uniform" and set(c) == {"distribution", "low", "high"}:
            low = finite(c["low"], low=-1e3, high=1e3, name="low")
            high = finite(c["high"], low=-1e3, high=1e3, name="high")
            if not high > low:
                raise GenomeError("uniform coordinate: high must exceed low")
            parsed.append(("uniform", low, high))
        elif kind == "exponential" and set(c) == {"distribution", "rate"}:
            parsed.append(("exponential", finite(c["rate"], low=1e-3, high=1e3, name="rate"), None))
        else:
            raise GenomeError("each coordinate is {distribution: normal (mean, sd) | uniform (low, high) | "
                              "exponential (rate)} with exactly those keys")
    d = len(parsed)
    fn = data.get("function")
    family = fn.get("family") if isinstance(fn, dict) else None

    def vector(name, bound):
        v = fn.get(name)
        if not isinstance(v, list) or len(v) != d:
            raise GenomeError(f"function.{name}: one number per coordinate")
        return [finite(x, low=-bound, high=bound, name=name) for x in v]
    if family == "exp_linear" and set(fn) == {"family", "weights"}:
        params = {"weights": vector("weights", 50.0)}
    elif family == "cos_product" and set(fn) == {"family", "frequencies", "phases"}:
        params = {"frequencies": vector("frequencies", 100.0), "phases": vector("phases", 10.0)}
    elif family == "power_product" and set(fn) == {"family", "powers"}:
        powers = fn["powers"]
        if not isinstance(powers, list) or len(powers) != d:
            raise GenomeError("function.powers: one non-negative integer per coordinate")
        powers = [bounded_int(k, low=0, high=MC_POWER_MAX, name="power") for k in powers]
        if not 1 <= sum(powers) <= 2 * MC_POWER_MAX:
            raise GenomeError(f"power_product: total degree 1-{2 * MC_POWER_MAX}")
        params = {"powers": powers}
    elif family == "call_on_sum" and set(fn) == {"family", "weights", "strike"}:
        params = {"weights": vector("weights", 50.0),
                  "strike": finite(fn["strike"], low=-1e6, high=1e6, name="strike")}
    elif family == "indicator_sum" and set(fn) == {"family", "weights", "threshold"}:
        params = {"weights": vector("weights", 50.0),
                  "threshold": finite(fn["threshold"], low=-1e6, high=1e6, name="threshold")}
    else:
        raise GenomeError(f"function: family one of {MC_FUNCTIONS} with exactly its parameters")
    evaluations = bounded_int(data.get("evaluations"), low=2, high=1_000_000, name="evaluations")
    if evaluations % 2:
        raise GenomeError("evaluations: an even count (antithetic pairs)")
    seed = bounded_int(data.get("seed"), low=0, high=2 ** 31 - 1, name="seed")
    level = finite(data.get("level", 0.95), low=0.5, high=0.999, name="level")
    return parsed, family, params, evaluations, seed, level


def _mc_heavy(coords, family, params):
    """The CLT interval needs a finite variance of f(X) and its standard error a finite fourth moment. Every
    family here has all moments under these coordinates except exp(w x) of an exponential coordinate."""
    if family != "exp_linear":
        return None
    for (kind, rate, _), w in zip(coords, params["weights"]):
        if kind == "exponential" and 4.0 * w >= rate:
            return (f"exp(w x) of an exponential(rate {rate:g}) coordinate at w = {w:g} has no finite fourth moment "
                    "(needs 4 w < rate): a CLT standard error would be unreliable")
    return None


def _mc_base_np(coords, u):
    """Per coordinate: the standardised base value (z, u - 1/2 or a unit exponential) and the coordinate value."""
    import numpy as np
    from scipy.special import ndtri
    base, x = np.empty_like(u), np.empty_like(u)
    for j, (kind, a, b) in enumerate(coords):
        if kind == "normal":
            base[:, j] = ndtri(u[:, j])
            x[:, j] = a + b * base[:, j]
        elif kind == "uniform":
            base[:, j] = u[:, j] - 0.5
            x[:, j] = a + (b - a) * u[:, j]
        else:
            base[:, j] = -np.log1p(-u[:, j])
            x[:, j] = base[:, j] / a
    return base, x


def _mc_transform_np(coords, u):
    return _mc_base_np(coords, u)[1]


def _mc_f_np(family, params, x):
    """f on every row; an overflow yields inf (the caller returns UNKNOWN), never a floating-point exception."""
    import numpy as np
    with np.errstate(over="ignore", invalid="ignore"):
        if family == "exp_linear":
            return np.exp(x @ np.array(params["weights"]))
        if family == "cos_product":
            return np.prod(np.cos(x * np.array(params["frequencies"]) + np.array(params["phases"])), axis=1)
        if family == "power_product":
            return np.prod(x ** np.array(params["powers"]), axis=1)
        s = x @ np.array(params["weights"])
        if family == "call_on_sum":
            return np.maximum(s - params["strike"], 0.0)
        return (s > params["threshold"]).astype(float)


def _mc_sum_np(params, x):
    import numpy as np
    return x @ np.array(params["weights"])


def _mc_mags_np(coords, base, x):
    """The magnitude each coordinate value is computed from: |a| + |b z| for a normal coordinate (the inverse CDF's
    own error scales with |b z|, not with a possibly cancelled |a + b z|), |x| otherwise."""
    import numpy as np
    mags = np.abs(x)
    for j, (kind, a, b) in enumerate(coords):
        if kind == "normal":
            mags[:, j] = abs(a) + abs(b) * np.abs(base[:, j])
    return mags


def _mc_rounding_np(family, params, x, mags, f):
    """Per evaluation, a bound on how far two faithful double-precision evaluations of f at that point can differ
    (absolute; MC_NOISE_C units of 2^-53 times the magnitudes f is computed from, plus _MC_TINY for a result below the
    normal range). Continuous in the point, so two independent computations of the bound agree to rounding. An
    indicator is exact (0 or 1) once its threshold decisions agree, which the reference evaluation guarantees."""
    import numpy as np
    if family == "indicator_sum":
        return np.zeros(len(f))
    return _mc_relative_rounding_np(family, params, x, mags, f) + _MC_TINY


def _mc_relative_rounding_np(family, params, x, mags, f):
    import numpy as np
    unit = MC_NOISE_C * _EPS
    with np.errstate(over="ignore", invalid="ignore"):
        if family == "cos_product":
            phases = sum(map(abs, params["phases"]))
            return unit * (mags @ np.abs(np.array(params["frequencies"])) + phases + mags.shape[1])
        if family == "power_product":
            # sum_j k_j |x_j|^(k_j - 1) mags_j prod_{l != j} |x_l|^k_l = |f| sum_j k_j mags_j / |x_j| where no x_j
            # under a positive power is zero; those few rows take the product form
            k = params["powers"]
            ax = np.abs(x)
            with np.errstate(divide="ignore"):
                ratio = np.where(np.array(k) > 0, np.array(k, dtype=float) * mags / ax, 0.0)
            total = np.abs(f) * ratio.sum(axis=1)
            for i in np.flatnonzero(~np.isfinite(total)).tolist():
                row, g = ax[i].tolist(), mags[i].tolist()
                total[i] = sum(kj * row[j] ** (kj - 1) * g[j]
                               * math.prod(row[l] ** kl for l, kl in enumerate(k) if l != j)
                               for j, kj in enumerate(k) if kj)
            return unit * (total + len(k) * np.abs(f))
        spread = mags @ np.abs(np.array(params["weights"]))
        if family == "exp_linear":
            return unit * np.abs(f) * (spread + 1.0)
        return unit * (spread + abs(params["strike"]))


def _mc_reference_f(coords, family, params, v):
    """f at one uniform vector by the declared reference arithmetic: NormalDist's inverse CDF, rounded products, an
    exactly rounded sum (math.fsum) and math.exp. It decides the points where two faithful evaluations may land on
    different sides of a discontinuity of the declared computation: an indicator's threshold, the sign of a call's
    payoff, exp's overflow."""
    x = []
    for (kind, a, b), vi in zip(coords, v):
        if kind == "normal":
            x.append(a + b * _N.inv_cdf(vi))
        elif kind == "uniform":
            x.append(a + (b - a) * vi)
        else:
            x.append(-math.log1p(-vi) / a)
    s = math.fsum(w * xi for w, xi in zip(params["weights"], x))
    if family == "indicator_sum":
        return 1.0 if s > params["threshold"] else 0.0
    if family == "call_on_sum":
        return max(s - params["strike"], 0.0)
    try:
        return math.exp(s)
    except OverflowError:
        return math.inf


def _mc_controls_np(coords, base, base_a):
    """Pair-averaged centred moments of the base coordinates, each with an exactly known mean of zero. The
    linear moment of a normal or uniform coordinate is odd under u -> 1 - u, so its pair average is constant
    and it is omitted."""
    import numpy as np
    names, cols = [], []
    for j, (kind, _, _) in enumerate(coords):
        b, ba = base[:, j], base_a[:, j]
        if kind == "normal":
            names.append(f"z{j}^2-1")
            cols.append(0.5 * (b * b + ba * ba) - 1.0)
        elif kind == "uniform":
            names.append(f"(u{j}-1/2)^2-1/12")
            cols.append(0.5 * (b * b + ba * ba) - 1.0 / 12.0)
        else:
            names += [f"e{j}-1", f"(e{j}-1)^2-1"]
            cols += [0.5 * (b + ba) - 1.0, 0.5 * ((b - 1.0) ** 2 + (ba - 1.0) ** 2) - 1.0]
    return names, np.column_stack(cols)


def _mc_pilot(m, p):
    """Pairs in the pilot block that fits the control coefficients: an eighth, and at least 8 per parameter."""
    return max(8 * (p + 1), m // 8)


def mc_solve(data, budget):
    import numpy as np
    from scipy.special import ndtri
    coords, family, params, evaluations, seed, level = _mc(data)
    d = len(coords)
    if d > MC_NATIVE_DIM:
        return _abstain(f"dimension {d} exceeds {MC_NATIVE_DIM}: the independent pure-Python recomputation is "
                        "over budget (the estimator itself is dimension-free)", dimension=d)
    lo_n, hi_n = MC_NATIVE_EVALUATIONS
    if not lo_n <= evaluations <= hi_n:
        return _abstain(f"{evaluations} evaluations is outside {lo_n}-{hi_n}: too few for a pilot fit and a CLT "
                        "interval, or more than the independent check can recompute", evaluations=evaluations)
    heavy = _mc_heavy(coords, family, params)
    if heavy:
        return _abstain(heavy)
    m = evaluations // 2
    u = np.maximum(np.random.default_rng(seed).random((m, d)), MC_U_FLOOR)
    ua = 1.0 - u
    base, x = _mc_base_np(coords, u)
    base_a, xa = _mc_base_np(coords, ua)
    fx, fa = _mc_f_np(family, params, x), _mc_f_np(family, params, xa)
    mags, mags_a = _mc_mags_np(coords, base, x), _mc_mags_np(coords, base_a, xa)
    if family in ("indicator_sum", "call_on_sum", "exp_linear"):
        # A point whose w . x lies within the rounding bound of the threshold, the strike or exp's overflow is
        # evaluated by the reference arithmetic, so no two faithful evaluations disagree on which side it falls.
        edge = {"indicator_sum": params.get("threshold"), "call_on_sum": params.get("strike")}.get(family, _LN_MAX)
        absw = np.abs(np.array(params["weights"]))
        for uu, xx, gg, ff in ((u, x, mags, fx), (ua, xa, mags_a, fa)):
            near = np.abs(_mc_sum_np(params, xx) - edge) <= MC_NOISE_C * _EPS * (gg @ absw + abs(edge)) + _MC_TINY
            for i in np.flatnonzero(near).tolist():
                ff[i] = _mc_reference_f(coords, family, params, uu[i].tolist())
    if not (np.all(np.isfinite(fx)) and np.all(np.isfinite(fa))):
        return _unknown("f overflowed double precision on the declared draws", seed=seed)
    if family == "indicator_sum":
        hits = int(fx.sum() + fa.sum())
        if min(hits, evaluations - hits) < MC_MIN_HITS:
            return _unknown(f"rare event: {hits} of {evaluations} evaluations hit; a CLT interval on so few hits is "
                            "unreliable (importance sampling is the native method)", hits=hits)
    if family == "call_on_sum":
        paying = int(np.count_nonzero(fx) + np.count_nonzero(fa))
        if paying < MC_MIN_HITS:
            return _unknown(f"rare event: {paying} of {evaluations} payoffs are positive; a CLT interval on so few is "
                            "unreliable (importance sampling is the native method)", paying=paying)
    # In units of mean |f| (halved before any sum), so no square or sum overflows double precision.
    fabs = 0.5 * np.abs(fx) + 0.5 * np.abs(fa)
    peak = float(fabs.max())
    if peak == 0.0:
        return _unknown("f is zero on every declared draw: the sample has no spread to put an interval on")
    scale = peak * float((fabs / peak).mean())
    if not scale > 0.0:
        return _unknown(_MC_UNDERFLOW, mean_abs_f=scale)
    noise = 0.5 * (_mc_rounding_np(family, params, x, mags, fx)
                   + _mc_rounding_np(family, params, xa, mags_a, fa)) / scale
    y = (0.5 * fx + 0.5 * fa) / scale
    names, controls = _mc_controls_np(coords, base, base_a)
    pilot = _mc_pilot(m, len(names))
    # Coefficients fitted on the pilot block only and applied to the independent main block: the estimate is
    # unbiased and its interval an iid CLT interval (fitting on the same draws biases it by O(1/n); on development
    # and review seeds that bias reached -0.28 standard errors on cos_product).
    coef = np.linalg.lstsq(np.column_stack([np.ones(pilot), controls[:pilot]]), y[:pilot], rcond=None)[0]
    if not np.all(np.abs(coef) <= 0.5 * MC_COEF_MAX):    # half the verifier's bound: its mean |f| is its own
        return _unknown("the pilot least-squares fit is degenerate (a coefficient beyond the certifiable bound)")
    beta = coef[1:]
    adjusted = y[pilot:] - controls[pilot:] @ beta
    main = m - pilot
    est_s, s_s = float(adjusted.mean()), float(adjusted.std(ddof=1))
    est, s = est_s * scale, s_s * scale
    floor = max(MC_SE_FLOOR, MC_NOISE_SE * float(noise.sum()) / main)
    se = math.hypot(s_s / math.sqrt(main), floor) * scale
    if se < 2.0 * sys.float_info.min:
        # every recomputation tolerance is a fraction of the standard error; below the smallest normal double the
        # reported numbers' fixed absolute rounding (2^-1075) is no longer negligible against it (the verifier refutes
        # below half this margin)
        return _unknown(_MC_UNDERFLOW, std_error=se, mean_abs_f=scale)
    z = float(ndtri(0.5 + level / 2.0))
    half = z * se
    interval = [est - half, est + half]
    alpha, beta = float(coef[0]) * scale, [float(b) * scale for b in beta]
    # twice the half-width must stay finite: the verifier's own z may round a unit higher
    reported = (est, s, se, abs(est) + 2.0 * half, *interval, alpha, *beta)
    if not (se > 0.0 and all(math.isfinite(v) for v in reported)):
        return _unknown("the estimate, its interval or the fitted coefficients exceed double precision")
    return answer({"estimate": est, "interval": interval, "std_error": se, "level": level, "evaluations": 2 * m},
                  {"method": "antithetic pairs (u, 1 - u) through inverse CDFs; control coefficients by OLS of the "
                             "pilot block's pair means on pair-averaged centred moment controls; estimate = mean of "
                             "the main block's control-adjusted pair means; standard error floored at "
                             "max(1e-12, 200 x the mean per-pair rounding bound) of mean |f|",
                   "rng": "numpy default_rng(seed).random((pairs, dimension)), floored at 2^-53",
                   "seed": seed, "pairs": m, "pilot_pairs": pilot, "controls": names,
                   "pilot_intercept": alpha, "control_coefficients": beta,
                   "main_sd": s, "z": z, "standard_error_floor": floor, "truth_certified": False,
                   "coverage": "asymptotic (CLT) at the stated level under the declared model; not a guarantee",
                   "model": "independent coordinates with the declared distributions; not established here"})


def _mc_pilot_size(m, p):
    """Verifier's own statement of the declared split: max(floor(m / 8), 8 (p + 1)) pilot pairs."""
    return max(m // 8, 8 * p + 8)


def _mc_moments_finite(coords, family, params):
    """Verifier's own precondition: E f(X)^4 = prod_i E exp(4 w_i X_i) for exp_linear (finite for normal and
    uniform; for an exponential coordinate only while 4 w_i < rate); bounded or polynomial otherwise."""
    if family != "exp_linear":
        return True
    return all(kind != "exponential" or rate - 4.0 * w > 0.0 for (kind, rate, _), w in zip(coords, params["weights"]))


def _mc_f_py(family, params, x):
    if family == "cos_product":
        return math.prod(math.cos(w * v + p) for w, p, v in zip(params["frequencies"], params["phases"], x))
    if family == "power_product":
        return math.prod(v ** k for v, k in zip(x, params["powers"]))
    s = math.fsum(w * v for w, v in zip(params["weights"], x))
    if family == "exp_linear":
        try:
            return math.exp(s)
        except OverflowError:                  # the same double-precision threshold as the solver's exp
            return math.inf
    if family == "call_on_sum":
        return max(s - params["strike"], 0.0)
    return 1.0 if s > params["threshold"] else 0.0


def _mc_rounding_py(family, params, x, mags, f):
    """Verifier's own bound on how far two faithful double-precision evaluations of f at one point can differ:
    MC_NOISE_C units of 2^-53 times the magnitudes f is computed from (mags: |a| + |b z| for a normal coordinate,
    |x| otherwise), plus _MC_TINY for a result below the normal range."""
    if family == "indicator_sum":
        return 0.0
    return _mc_relative_rounding_py(family, params, x, mags, f) + _MC_TINY


def _mc_relative_rounding_py(family, params, x, mags, f):
    unit = MC_NOISE_C * _EPS
    if family == "cos_product":
        return unit * (math.fsum(abs(w) * g + abs(p) for w, p, g in zip(params["frequencies"], params["phases"], mags))
                       + len(x))
    if family == "power_product":
        k, total = params["powers"], 0.0
        for j, kj in enumerate(k):
            if kj:
                term = kj * abs(x[j]) ** (kj - 1) * mags[j]
                for i, ki in enumerate(k):
                    if i != j:
                        term *= abs(x[i]) ** ki
                total += term
        return unit * (total + len(x) * abs(f))
    spread = math.fsum(abs(w) * g for w, g in zip(params["weights"], mags))
    if family == "exp_linear":
        return unit * abs(f) * (spread + 1.0)
    return unit * (spread + abs(params["strike"]))


def mc_verify(data, output, certificate):
    """Recompute the estimate on the declared draws with independent code. Certifies the arithmetic, the
    least-squares fit and the interval's construction; it cannot certify that the interval covers the truth."""
    import numpy as np                         # only to regenerate the declared uniform stream
    coords, family, params, evaluations, seed, level = _mc(data)
    certificate = _cert(certificate)
    if (not isinstance(output, dict) or set(output) != {"estimate", "interval", "std_error", "level", "evaluations"}
            or not _real(output["estimate"]) or not _real(output["std_error"]) or output["std_error"] <= 0
            or not isinstance(output["interval"], list) or len(output["interval"]) != 2
            or not all(_real(v) for v in output["interval"])):
        return {"output_shape": False}
    d, m = len(coords), evaluations // 2
    names = []
    for j, (kind, _, _) in enumerate(coords):
        names += ([f"z{j}^2-1"] if kind == "normal" else [f"(u{j}-1/2)^2-1/12"] if kind == "uniform"
                  else [f"e{j}-1", f"(e{j}-1)^2-1"])
    beta = certificate.get("control_coefficients")
    bound = (certificate.get("seed") == seed and certificate.get("pairs") == m and certificate.get("controls") == names
             and certificate.get("pilot_pairs") == _mc_pilot_size(m, len(names))
             and _real(certificate.get("pilot_intercept"))
             and isinstance(beta, list) and len(beta) == len(names) and all(_real(b) for b in beta))
    native = (d <= MC_NATIVE_DIM and MC_NATIVE_EVALUATIONS[0] <= evaluations <= MC_NATIVE_EVALUATIONS[1]
              and _mc_moments_finite(coords, family, params))
    checks = {"output_shape": True, "certificate_bound": bound, "clt_preconditions_hold": native,
              "level_as_requested": output["level"] == level,
              "evaluations_as_declared": type(output["evaluations"]) is int and output["evaluations"] == evaluations,
              "claims_no_truth_certificate": certificate.get("truth_certified") is False}
    if not (bound and native):
        return checks
    ctrl, fs, rounding = [], [], []
    for row in np.random.default_rng(seed).random((m, d)).tolist():
        x, xa, c, g, ga = [], [], [], [], []
        for (kind, a, b), v in zip(coords, row):
            v = v if v > MC_U_FLOOR else MC_U_FLOOR
            va = 1.0 - v
            if kind == "normal":
                z, za = _N.inv_cdf(v), _N.inv_cdf(va)
                x.append(a + b * z)
                xa.append(a + b * za)
                g.append(abs(a) + abs(b * z))
                ga.append(abs(a) + abs(b * za))
                c.append(0.5 * (z * z + za * za) - 1.0)
            elif kind == "uniform":
                x.append(a + (b - a) * v)
                xa.append(a + (b - a) * va)
                h, ha = v - 0.5, va - 0.5
                c.append(0.5 * (h * h + ha * ha) - 1.0 / 12.0)
            else:
                e, ea = -math.log1p(-v), -math.log1p(-va)
                x.append(e / a)
                xa.append(ea / a)
                c += [0.5 * (e + ea) - 1.0, 0.5 * ((e - 1.0) ** 2 + (ea - 1.0) ** 2) - 1.0]
            if kind != "normal":
                g.append(abs(x[-1]))
                ga.append(abs(xa[-1]))
        f, fa = _mc_f_py(family, params, x), _mc_f_py(family, params, xa)
        fs.append((f, fa))
        ctrl.append(c)
        if math.isfinite(f) and math.isfinite(fa):
            rounding.append(0.5 * _mc_rounding_py(family, params, x, g, f)
                            + 0.5 * _mc_rounding_py(family, params, xa, ga, fa))
    if not all(math.isfinite(f) and math.isfinite(fa) for f, fa in fs):
        return {**checks, "values_finite": False}
    # an indicator needs hits and misses, a call positive payoffs: with fewer the CLT interval is meaningless
    nonzero = sum((f != 0.0) + (fa != 0.0) for f, fa in fs)
    hits = min(nonzero, evaluations - nonzero) if family == "indicator_sum" else nonzero
    checks = {**checks, "values_finite": True,
              "event_not_rare": family not in ("indicator_sum", "call_on_sum") or hits >= MC_MIN_HITS}
    # Everything below is in units of the verifier's own mean |f| (halved before summing, so nothing overflows).
    fabs = [0.5 * abs(f) + 0.5 * abs(fa) for f, fa in fs]
    peak = max(fabs)
    if peak == 0.0:
        return {**checks, "f_not_identically_zero": False}
    scale = peak * (math.fsum(v / peak for v in fabs) / m)
    if not scale > 0.0:
        return {**checks, "std_error_above_underflow": False}
    est, se = output["estimate"], output["std_error"]
    pilot = certificate["pilot_pairs"]
    rounding = [r / scale for r in rounding]                  # per pair, in units of mean |f|
    alpha, beta = certificate["pilot_intercept"] / scale, [b / scale for b in beta]
    if not all(math.isfinite(v) and abs(v) <= MC_COEF_MAX for v in (alpha, *beta)):
        return {**checks, "coefficients_within_bound": False}
    ys = [(0.5 * f + 0.5 * fa) / scale for f, fa in fs]
    resid = [y - alpha - math.fsum(bj * cj for bj, cj in zip(beta, c)) for y, c in zip(ys[:pilot], ctrl[:pilot])]
    # Norms by math.hypot, which scales before squaring: the pilot's values can be far below mean |f|, and their
    # squares would underflow. Rounding noise scales with the evaluations, not with their (possibly cancelling) pair
    # means.
    slack = math.hypot(*resid) + 1e-7 * math.hypot(*(f / scale for pair in fs[:pilot] for f in pair)) / math.sqrt(2.0)
    # Two faithful evaluations of the pilot's f may differ by up to its rounding bound, and each reported coefficient
    # was rounded once in absolute units (below the normal range by up to 2^-1075, not a share of it): per residual,
    # what that moves it by; Cauchy-Schwarz bounds what that moves each normal equation by.
    wobble = math.hypot(*(r + math.ulp(0.0) * (1.0 + math.fsum(map(abs, c))) / scale
                          for r, c in zip(rounding[:pilot], ctrl[:pilot])))
    # least-squares normal equations on the pilot block: its residual is orthogonal to the intercept and each control
    fitted = abs(math.fsum(resid)) <= math.sqrt(pilot) * (1e-7 * slack + wobble)
    for j in range(len(names)):
        col = [c[j] for c in ctrl[:pilot]]
        fitted = fitted and abs(math.fsum(e * v for e, v in zip(resid, col))) <= (
            math.hypot(*col) * (1e-7 * slack + wobble))
    adjusted = [y - math.fsum(bj * cj for bj, cj in zip(beta, c)) for y, c in zip(ys[pilot:], ctrl[pilot:])]
    main = m - pilot
    est_v = math.fsum(adjusted) / main
    s = math.sqrt(math.fsum((w - est_v) * (w - est_v) for w in adjusted) / (main - 1))
    # the estimate's own rounding noise bounds how far an honest estimate, and its standard error, can sit from these
    noise = math.fsum(rounding) / main
    # >= the floors, so every tolerance below is real and the estimate's (1% of it) covers the rounding noise twice
    se_v = math.hypot(s / math.sqrt(main), max(MC_SE_FLOOR, MC_NOISE_SE * noise))
    if se_v * scale < sys.float_info.min:
        # a subnormal standard error: the reported numbers' absolute rounding (2^-1075) is no longer negligible against
        # the tolerances below, which are fractions of it
        return {**checks, "coefficients_within_bound": True, "std_error_above_underflow": False}
    half = _N.inv_cdf(0.5 + level / 2.0) * se
    lo, hi = output["interval"]
    # est -+ z se must be representable (the solver returns UNKNOWN otherwise); the solver's interval is it rounded
    # once: a few units in the last place, never a share of |est|, and always a finite tolerance
    elo, ehi = est - half, est + half
    representable = math.isfinite(half) and math.isfinite(elo) and math.isfinite(ehi)
    width_tol = 1e-9 * half + 4.0 * math.ulp(max(abs(est), half)) if representable else 0.0
    return {**checks, "std_error_above_underflow": True, "coefficients_within_bound": True,
            "pilot_least_squares_normal_equations_hold": fitted,
            "estimate_is_the_main_block_adjusted_mean": abs(est / scale - est_v) <= MC_EST_TOL * se_v,
            "std_error_recomputed": abs(se / scale - se_v) <= MC_SE_TOL * se_v + 2.0 * noise,
            "interval_is_estimate_plus_minus_z_std_error": representable and lo < est < hi
            and abs(lo - elo) <= width_tol and abs(hi - ehi) <= width_tol}


def _moment(coord, k):
    """Analytic E[X^k] for one coordinate."""
    kind, a, b = coord
    if kind == "normal":
        return math.fsum(math.comb(k, j) * a ** (k - j) * b ** j * math.prod(range(j - 1, 0, -2))
                         for j in range(0, k + 1, 2))
    if kind == "uniform":
        return (b ** (k + 1) - a ** (k + 1)) / ((k + 1) * (b - a))
    return math.factorial(k) / a ** k


def _mgf(coord, w):
    kind, a, b = coord
    if kind == "normal":
        return math.exp(w * a + 0.5 * w * w * b * b)
    if kind == "uniform":
        t = w * (b - a)
        return math.exp(w * a) * (math.expm1(t) / t if t else 1.0)
    return a / (a - w)


def _ecos(coord, w, phase):
    """Analytic E[cos(w X + phase)]."""
    kind, a, b = coord
    if kind == "normal":
        return math.cos(w * a + phase) * math.exp(-0.5 * w * w * b * b)
    if kind == "uniform":
        return (math.sin(w * b + phase) - math.sin(w * a + phase)) / (w * (b - a)) if w else math.cos(phase)
    return a * (a * math.cos(phase) - w * math.sin(phase)) / (a * a + w * w)


def mc_truth(data):
    """Evaluation side only: the analytic mean and standard deviation of f(X)."""
    coords, family, params, *_ = _mc(data)
    if family == "exp_linear":
        w = params["weights"]
        mean = math.prod(_mgf(c, wi) for c, wi in zip(coords, w))
        log_ratio = math.fsum(math.log(_mgf(c, 2 * wi)) - 2 * math.log(_mgf(c, wi)) for c, wi in zip(coords, w))
        var = mean * mean * math.expm1(log_ratio)
    elif family == "cos_product":
        f, p = params["frequencies"], params["phases"]
        mean = math.prod(_ecos(c, wi, pi) for c, wi, pi in zip(coords, f, p))
        var = math.prod(0.5 * (1.0 + _ecos(c, 2 * wi, 2 * pi)) for c, wi, pi in zip(coords, f, p)) - mean * mean
    elif family == "power_product":
        k = params["powers"]
        mean = math.prod(_moment(c, ki) for c, ki in zip(coords, k))
        var = math.prod(_moment(c, 2 * ki) for c, ki in zip(coords, k)) - mean * mean
    else:
        if any(c[0] != "normal" for c in coords):
            raise GenomeError("closed-form truth for a sum family needs normal coordinates")
        w = params["weights"]
        mu = math.fsum(wi * c[1] for wi, c in zip(w, coords))
        sd = math.sqrt(math.fsum((wi * c[2]) ** 2 for wi, c in zip(w, coords)))
        if family == "call_on_sum":
            g = mu - params["strike"]
            t = g / sd
            mean = g * _N.cdf(t) + sd * _N.pdf(t)
            var = (g * g + sd * sd) * _N.cdf(t) + g * sd * _N.pdf(t) - mean * mean
        else:
            mean = _N.cdf((mu - params["threshold"]) / sd)
            var = mean * (1.0 - mean)
    return {"mean": mean, "sd": math.sqrt(max(var, 0.0))}


def mc_instance(seed):
    r = random.Random(960_000 + seed)
    family = MC_FUNCTIONS[seed % len(MC_FUNCTIONS)]
    d = r.randint(1, MC_NATIVE_DIM)
    kinds = ["normal"] * d if family in ("call_on_sum", "indicator_sum") else [r.choice(MC_DISTRIBUTIONS)
                                                                               for _ in range(d)]
    coords = []
    for kind in kinds:
        if kind == "normal":
            coords.append({"distribution": "normal", "mean": round(r.uniform(-1.0, 1.0), 3),
                           "sd": round(r.uniform(0.3, 1.5), 3)})
        elif kind == "uniform":
            low = round(r.uniform(-1.5, 0.5), 3)
            coords.append({"distribution": "uniform", "low": low, "high": round(low + r.uniform(0.5, 2.5), 3)})
        else:
            coords.append({"distribution": "exponential", "rate": round(r.uniform(0.5, 3.0), 3)})
    root = math.sqrt(d)
    if family == "exp_linear":
        fn = {"weights": [round(r.uniform(-0.5, 0.2) * c["rate"] / root, 4) if c["distribution"] == "exponential"
                          else round(r.uniform(-0.6, 0.6) / root, 4) for c in coords]}
    elif family == "cos_product":
        fn = {"frequencies": [round(r.uniform(0.3, 1.5), 3) for _ in coords],
              "phases": [round(r.uniform(0.0, 3.1416), 3) for _ in coords]}
    elif family == "power_product":
        powers = [r.randint(0, 2) for _ in coords]
        while sum(powers) > MC_POWER_MAX:                  # total degree at most 6
            powers[r.choice([j for j, k in enumerate(powers) if k])] -= 1
        if not any(powers):
            powers[r.randrange(d)] = r.randint(1, 3)
        fn = {"powers": powers}
    else:
        w = [round(r.uniform(0.2, 1.0), 3) for _ in coords]
        mu = sum(wi * c["mean"] for wi, c in zip(w, coords))
        sd = math.sqrt(sum((wi * c["sd"]) ** 2 for wi, c in zip(w, coords)))
        fn = ({"weights": w, "strike": round(mu + sd * r.uniform(-1.0, 1.5), 4)} if family == "call_on_sum"
              else {"weights": w, "threshold": round(mu + sd * r.uniform(-1.5, 1.5), 4)})
    data = {"coordinates": coords, "function": {"family": family, **fn}, "evaluations": 8192,
            "seed": r.randrange(2 ** 31), "level": 0.95}
    return data, mc_truth(data)


def mc_subregion(data):
    family = data["function"]["family"]
    kind = ("smooth" if family in ("exp_linear", "cos_product", "power_product")
            else "kinked" if family == "call_on_sum" else "discontinuous")
    return f"{kind}_{'d1_3' if len(data['coordinates']) <= 3 else 'd4_8'}"


def mc_score(data, truth, output):
    """Quality: minus the absolute error in units of sd(f(X)) (capped at 1); correct iff the interval covers the
    analytic expectation."""
    if not isinstance(output, dict) or "estimate" not in output:
        return {"quality": -1.5, "category": "abstain"}
    est, iv = output.get("estimate"), output.get("interval")
    if (type(est) not in (int, float) or not math.isfinite(est) or not isinstance(iv, list) or len(iv) != 2
            or not all(type(v) in (int, float) and math.isfinite(v) for v in iv) or not iv[0] <= est <= iv[1]):
        return {"quality": -2.0, "category": "wrong"}
    scale = max(truth["sd"], 1e-12 * max(1.0, abs(truth["mean"])))
    return {"quality": -min(abs(est - truth["mean"]) / scale, 1.0),
            "category": "correct" if iv[0] <= truth["mean"] <= iv[1] else "wrong"}


def mc_plain(data):
    """Baseline: plain Monte Carlo at a fixed 1000 evaluations (no variance reduction), CLT interval."""
    import numpy as np
    from scipy.special import ndtri
    coords, family, params, evaluations, seed, level = _mc(data)
    n = min(MC_BASELINE_N, evaluations)
    u = np.maximum(np.random.default_rng([seed, 1]).random((n, len(coords))), MC_U_FLOOR)
    fx = _mc_f_np(family, params, _mc_transform_np(coords, u))
    if not np.all(np.isfinite(fx)):
        return None
    est, se = float(fx.mean()), float(fx.std(ddof=1)) / math.sqrt(n)
    half = float(ndtri(0.5 + level / 2.0)) * se
    return {"estimate": est, "interval": [est - half, est + half], "std_error": se, "level": level, "evaluations": n}


def mc_sobol(data):
    """Competitor: randomized quasi-Monte Carlo, 16 independent scrambled Sobol sequences (scipy.stats.qmc) of a
    power-of-two length at the same evaluation budget, t interval across the replicate means."""
    import numpy as np
    from scipy.stats import qmc, t
    coords, family, params, evaluations, seed, level = _mc(data)
    per = 2 ** int(math.log2(max(1, evaluations // MC_REPLICATES)))
    if per < 2:
        return None
    rng = np.random.default_rng([seed, 2])
    means = []
    for _ in range(MC_REPLICATES):
        points = np.clip(qmc.Sobol(len(coords), scramble=True, rng=rng).random(per), MC_U_FLOOR, 1.0 - MC_U_FLOOR)
        fx = _mc_f_np(family, params, _mc_transform_np(coords, points))
        if not np.all(np.isfinite(fx)):
            return None
        means.append(float(fx.mean()))
    est = math.fsum(means) / MC_REPLICATES
    se = statistics.stdev(means) / math.sqrt(MC_REPLICATES)
    half = float(t.ppf(0.5 + level / 2.0, MC_REPLICATES - 1)) * se
    return {"estimate": est, "interval": [est - half, est + half], "std_error": se, "level": level,
            "evaluations": per * MC_REPLICATES}


# =================================================================== 2. BCa bootstrap interval
BOOT_STATISTICS = ("mean", "median")
BOOT_INPUT_N, BOOT_NATIVE_MIN_N = 5000, 15
BOOT_NATIVE_MIN_RESAMPLES = 1000
BOOT_MAX_WORK = 600_000                # resamples x observations the pure-Python verifier recomputes
BOOT_MIN_DISTINCT = 5
# The sample's range must span at least 2^20 units in the last place of its largest magnitude (a relative spread of
# about 2e-10): below that double precision quantises the data, and the few units in the last place that any honest
# recomputation of an endpoint needs would be a material share of the bootstrap spread.
BOOT_RESOLUTION = 2 ** 20


def _boot(data):
    sample = _mapping(data).get("sample")
    if not isinstance(sample, list) or not 2 <= len(sample) <= BOOT_INPUT_N:
        raise GenomeError(f"sample: a list of 2-{BOOT_INPUT_N} numbers")
    x = [finite(v, low=-1e12, high=1e12, name="sample value") for v in sample]
    statistic = data.get("statistic")
    if statistic not in BOOT_STATISTICS:
        raise GenomeError(f"statistic is one of {BOOT_STATISTICS}")
    level = finite(data.get("level", 0.9), low=0.5, high=0.999, name="level")
    resamples = bounded_int(data.get("resamples", 2000), low=100, high=50_000, name="resamples")
    seed = bounded_int(data.get("seed"), low=0, high=2 ** 31 - 1, name="seed")
    independent = data.get("independent", True)
    if type(independent) is not bool:
        raise GenomeError("independent is a boolean")
    return x, statistic, level, resamples, seed, independent


def _sign(value):
    return (value > 0) - (value < 0)


def boot_solve(data, budget):
    import numpy as np
    from scipy.special import ndtr, ndtri
    x, statistic, level, resamples, seed, independent = _boot(data)
    n = len(x)
    if not independent:
        return _abstain("observations are declared dependent: the iid bootstrap is invalid (a block or model-based "
                        "bootstrap is required)")
    if n < BOOT_NATIVE_MIN_N:
        return _abstain(f"{n} observations: below {BOOT_NATIVE_MIN_N} the jackknife acceleration and the bias "
                        "correction are too unstable for a BCa interval", observations=n)
    if resamples < BOOT_NATIVE_MIN_RESAMPLES:
        return _abstain(f"{resamples} resamples: BCa tail percentiles need at least {BOOT_NATIVE_MIN_RESAMPLES}")
    if resamples * n > BOOT_MAX_WORK:
        return _abstain(f"resamples x observations above {BOOT_MAX_WORK}: over the independent check's budget")
    if len(set(x)) < BOOT_MIN_DISTINCT:
        return _abstain(f"fewer than {BOOT_MIN_DISTINCT} distinct values: a discrete sample makes the bootstrap "
                        "distribution lumpy and the bias correction unstable")
    arr = np.asarray(x, dtype=float)
    if float(arr.max() - arr.min()) < BOOT_RESOLUTION * math.ulp(float(np.abs(arr).max())):
        return _abstain(f"the sample's range is below {BOOT_RESOLUTION} units in the last place of its largest value: "
                        "double precision cannot resolve it")
    # Scale invariance: a sample of small magnitude is first multiplied by a power of two (exact) so that its largest
    # value lies in [1/2, 1), and every reported number is scaled back once at the end. Squares and cubes of the
    # jackknife deviations then never underflow (at 1e-108 they did, giving a wrong acceleration or a division by
    # zero), and a subnormal sample is computed with full relative precision.
    lift = max(0, -math.frexp(float(np.abs(arr).max()))[1])
    arr = np.ldexp(arr, lift)

    def back(v):
        return math.ldexp(float(v), -lift)
    # scipy.stats.bootstrap's resampling scheme and BCa formulas, computed here so that floating point never
    # decides them: scipy rounds every replicate at the scale of the values (a common offset of 1e9 costs it about
    # 1e-7) before comparing it with the estimate and before its jackknife subtracts nearly equal numbers.
    rows = np.random.default_rng(seed).integers(0, n, (resamples, n))
    if statistic == "mean":
        ref = float(np.sort(arr)[n // 2])     # an observation: differences from it are exact or nearly so
        cen = arr - ref
        values, centre_c = cen[rows].mean(axis=1), float(cen.mean())
        theta, offset = ref + centre_c, ref
        side = np.sign(values - centre_c)
        # a replicate within the summation error bound of the estimate is placed by exact rational sums
        mag = np.abs(cen)
        bound = 4.0 * (n + 2) * 2.0 ** -53 * (mag[rows].mean(axis=1) + float(mag.mean()))
        unsure = np.flatnonzero(np.abs(values - centre_c) <= bound)
        if unsure.size:
            total = sum(map(Fraction, arr.tolist()))
            for j in unsure.tolist():
                side[j] = _sign(sum(map(Fraction, arr[rows[j]].tolist())) - total)
        dev = cen - centre_c
        dev = dev - dev.mean()                 # x_i - mean: the jackknife deviations of the mean, centred twice
    else:
        values, theta, offset = np.median(arr[rows], axis=1), float(np.median(arr)), 0.0
        side = np.sign(values - theta)
        if n % 2 == 0:                         # equal rounded midpoints: compare the exact sums of the two middles
            k = n // 2
            middle = np.sort(arr)[k - 1:k + 1].tolist()
            for j in np.flatnonzero(values == theta).tolist():
                pair = np.partition(arr[rows[j]], (k - 1, k))[k - 1:k + 1].tolist()
                side[j] = _sign(Fraction(pair[0]) + Fraction(pair[1]) - Fraction(middle[0]) - Fraction(middle[1]))
        # the leave-one-out medians are the statistic in double precision at the sample's own scale (a subnormal
        # midpoint rounds there, exactly as the verifier computes it), then lifted
        given = np.asarray(x, dtype=float)
        loo = np.ldexp(np.array([np.median(np.delete(given, i)) for i in range(n)]), lift)
        w = loo - loo[n // 2]
        dev = -(w - w.mean())                  # (n - 1)(mean of leave-one-out medians - each), up to a positive factor
    share = (2 * np.count_nonzero(side < 0) + np.count_nonzero(side == 0)) / (2 * resamples)
    if not 0.0 < share < 1.0:
        return _unknown("the bootstrap distribution lies entirely on one side of the estimate: the bias correction "
                        "is infinite", seed=seed)
    z0 = float(ndtri(share))
    spread = float(np.abs(dev).max())
    if spread == 0.0:
        return _unknown("every leave-one-out statistic is equal: the jackknife acceleration is undefined")
    dev = dev / spread                         # the acceleration is scale-free; in these units s2 >= 1
    s2 = float(np.sum(dev * dev))
    accel = float(np.sum(dev * dev * dev)) / (6.0 * s2 ** 1.5)
    zq = float(ndtri((1.0 - level) / 2.0))
    adjusted = []
    for q in (zq, -zq):
        den = 1.0 - accel * (z0 + q)
        if den <= 0.0:
            return _unknown("the acceleration makes the BCa level transform non-monotone (1 - a (z0 + z) <= 0)")
        adjusted.append(float(ndtr(z0 + (z0 + q) / den)))
    if min(adjusted) * resamples < 1.0 or (1.0 - max(adjusted)) * resamples < 1.0:
        return _unknown("an adjusted BCa level falls beyond the resample range: more resamples are needed",
                        adjusted_levels=adjusted)
    lower, upper = (back(offset + float(v)) for v in np.quantile(values, adjusted, method="linear"))
    return answer({"lower": lower, "upper": upper, "level": level, "statistic": statistic, "estimate": back(theta),
                   "resamples": resamples, "method": "BCa"},
                  {"implementation": "scipy.stats.bootstrap's BCa (resampling scheme, bias correction, jackknife "
                                     "acceleration, adjusted type-7 percentiles), with exact side-of-estimate counts, "
                                     "the mean's replicates and jackknife centred on an observation, and a small "
                                     "sample scaled by a power of two",
                   "seed": seed, "resamples": resamples,
                   "resample_indices": "numpy default_rng(seed).integers(0, n, (resamples, n))",
                   "bias_correction_z0": z0, "acceleration": accel, "adjusted_levels": adjusted,
                   "percentiles": "linear interpolation between order statistics (Hyndman-Fan type 7)",
                   "bootstrap_standard_error": back(np.std(values, ddof=1)), "truth_certified": False,
                   "coverage": "second-order accurate as n grows, not exact; with skewed small samples it is "
                               "typically a few points below nominal",
                   "model": "independent, identically distributed observations; not established here"})


def _exact_acceleration(stats, orientation):
    """Verifier's jackknife acceleration sum(d^3) / (6 sum(d^2)^1.5) in exact integer arithmetic, d the deviations of
    the given floats from their exact mean (each float is an integer multiple of one power-of-two unit); orientation
    +1 for x_i - mean (the mean's jackknife), -1 for (n - 1)(mean - t_i) (leave-one-out statistics). None if every
    value is equal."""
    ratios = [v.as_integer_ratio() for v in stats]
    unit = max(den for _, den in ratios)
    ints = [num * (unit // den) for num, den in ratios]
    total, n = sum(ints), len(ints)
    v = [n * t - total for t in ints]          # n (t_i - mean) in that unit, exactly
    s2 = sum(w * w for w in v)
    if s2 == 0:
        return None
    s3 = sum(w * w * w for w in v)
    return orientation * math.copysign(math.sqrt(s3 * s3 / s2 ** 3) / 6.0, s3)


def _loo_medians(x):
    """Every leave-one-out median by index arithmetic on one sorted copy."""
    n = len(x)
    order = sorted(range(n), key=x.__getitem__)
    s = [x[i] for i in order]
    rank = [0] * n
    for r, i in enumerate(order):
        rank[i] = r

    def without(r):
        k = n - 1

        def at(t):
            return s[t] if t < r else s[t + 1]
        return at(k // 2) if k % 2 else (at(k // 2 - 1) + at(k // 2)) / 2
    return [without(rank[i]) for i in range(n)]


def _type7(ordered, p):
    h = (len(ordered) - 1) * p
    j = math.floor(h)
    if j + 1 >= len(ordered):
        return ordered[-1]
    return ordered[j] + (h - j) * (ordered[j + 1] - ordered[j])


def boot_verify(data, output, certificate):
    """Recompute the BCa interval from the declared resamples with independent code. It certifies that the
    interval is the BCa interval of this sample; it cannot certify that it covers the true parameter."""
    import numpy as np                         # only to regenerate the declared resample indices
    x, statistic, level, resamples, seed, independent = _boot(data)
    certificate = _cert(certificate)
    keys = {"lower", "upper", "level", "statistic", "estimate", "resamples", "method"}
    if (not isinstance(output, dict) or set(output) != keys
            or not all(_real(output[k]) for k in ("lower", "upper", "estimate"))
            or not output["lower"] <= output["upper"]):
        return {"output_shape": False}
    n = len(x)
    resolvable = max(x) - min(x) >= BOOT_RESOLUTION * math.ulp(max(abs(v) for v in x))
    native = (independent and n >= BOOT_NATIVE_MIN_N and resamples >= BOOT_NATIVE_MIN_RESAMPLES
              and len(set(x)) >= BOOT_MIN_DISTINCT and resolvable)
    checks = {"output_shape": True, "bootstrap_preconditions_hold": native,
              "independent_check_within_bounds": resamples * n <= BOOT_MAX_WORK,
              "request_echoed": output["level"] == level and output["statistic"] == statistic
              and type(output["resamples"]) is int and output["resamples"] == resamples and output["method"] == "BCa",
              "claims_no_truth_certificate": certificate.get("truth_certified") is False}
    if not (native and checks["independent_check_within_bounds"]):
        return checks
    k = n // 2
    if statistic == "mean":
        theta, negated = math.fsum(x) / n, [-v for v in x]
    else:
        ordered = sorted(x)
        theta = ordered[k] if n % 2 else (ordered[k - 1] + ordered[k]) / 2
    # Each replicate's side of the estimate is decided exactly: for the mean by the exactly rounded difference of
    # the sums (replicates are kept relative to the estimate), for the median by comparing order statistics and,
    # when two rounded midpoints coincide, the exact sums of the middle pairs.
    below = ties = 0
    values = []
    for row in np.random.default_rng(seed).integers(0, n, (resamples, n)).tolist():
        vals = [x[i] for i in row]
        if statistic == "mean":
            d = math.fsum(vals + negated)
            values.append(d / n)
        else:
            vals.sort()
            m = vals[k] if n % 2 else (vals[k - 1] + vals[k]) / 2
            d = m - theta
            if d == 0.0 and not n % 2:
                d = math.fsum((vals[k - 1], vals[k], -ordered[k - 1], -ordered[k]))
            values.append(m)
        below += d < 0.0
        ties += d == 0.0
    values.sort()
    centre = theta if statistic == "mean" else 0.0
    share = (2 * below + ties) / (2 * resamples)
    if not 0.0 < share < 1.0:
        return {**checks, "bias_correction_finite": False}
    z0 = _N.inv_cdf(share)
    accel = _exact_acceleration(x, 1.0) if statistic == "mean" else _exact_acceleration(_loo_medians(x), -1.0)
    if accel is None:
        return {**checks, "bias_correction_finite": True, "acceleration_defined": False}
    zq = _N.inv_cdf((1.0 - level) / 2.0)
    adjusted = []
    for q in (zq, -zq):
        den = 1.0 - accel * (z0 + q)
        adjusted.append(_N.cdf(z0 + (z0 + q) / den) if den > 0.0 else math.nan)
    if not all(math.isfinite(p) for p in adjusted):
        return {**checks, "bias_correction_finite": True, "acceleration_defined": True, "levels_monotone": False}
    lower, upper = centre + _type7(values, adjusted[0]), centre + _type7(values, adjusted[1])
    # Independent summation orders and the final rounding of an endpoint differ by a few units in its last place;
    # the resolution precondition keeps those far below the bootstrap spread. Never a share of |estimate|.
    tol = 1e-9 * (values[-1] - values[0]) + 8.0 * math.ulp(max(abs(lower), abs(upper), abs(theta)))
    claimed = certificate.get("adjusted_levels")
    cert_ok = (certificate.get("seed") == seed and certificate.get("resamples") == resamples
               and _real(certificate.get("bias_correction_z0")) and abs(certificate["bias_correction_z0"] - z0) <= 1e-9
               and _real(certificate.get("acceleration"))
               and abs(certificate["acceleration"] - accel) <= 1e-9 * (1.0 + abs(accel))
               and isinstance(claimed, list) and len(claimed) == 2 and all(_real(p) for p in claimed)
               and all(abs(p - q) <= 1e-9 for p, q in zip(claimed, adjusted)))
    return {**checks, "bias_correction_finite": True, "acceleration_defined": True, "levels_monotone": True,
            "estimate_recomputed": abs(output["estimate"] - theta) <= tol,
            "lower_is_the_bca_percentile": abs(output["lower"] - lower) <= tol,
            "upper_is_the_bca_percentile": abs(output["upper"] - upper) <= tol,
            "certificate_matches_recomputation": cert_ok}


BOOT_DISTRIBUTIONS = ("lognormal", "exponential", "pareto")


def boot_instance(seed):
    r = random.Random(970_000 + seed)
    dist = BOOT_DISTRIBUTIONS[seed % 3]
    statistic = BOOT_STATISTICS[(seed // 3) % 2]
    n = r.randint(15, 120)
    if dist == "lognormal":
        mu, sigma = r.uniform(-1.0, 2.0), r.uniform(0.5, 1.2)
        xs = [r.lognormvariate(mu, sigma) for _ in range(n)]
        truth = math.exp(mu + sigma * sigma / 2) if statistic == "mean" else math.exp(mu)
    elif dist == "exponential":
        rate = r.uniform(0.2, 5.0)
        xs = [r.expovariate(rate) for _ in range(n)]
        truth = 1.0 / rate if statistic == "mean" else math.log(2.0) / rate
    else:                                      # finite variance; the fourth moment is infinite below alpha = 4
        alpha, scale = r.uniform(2.2, 4.5), r.uniform(0.5, 3.0)
        xs = [scale * r.paretovariate(alpha) for _ in range(n)]
        truth = alpha * scale / (alpha - 1.0) if statistic == "mean" else scale * 2.0 ** (1.0 / alpha)
    data = {"sample": [float(f"{v:.6g}") for v in xs], "statistic": statistic, "level": 0.9, "resamples": 2000,
            "seed": r.randrange(2 ** 31)}
    return data, {"parameter": truth, "distribution": dist}


def boot_subregion(data):
    x = data["sample"]
    n = len(x)
    m = math.fsum(x) / n
    m2 = math.fsum((v - m) ** 2 for v in x) / n
    g = math.fsum((v - m) ** 3 for v in x) / n / m2 ** 1.5 if m2 > 0 else 0.0
    return f"{data['statistic']}_{'skew_below_1' if g < 1 else 'skew_1_3' if g < 3 else 'skew_above_3'}"


def boot_score(data, truth, output):
    """Minus the Gneiting-Raftery interval score relative to the true parameter (capped at 9); correct iff the
    interval covers the parameter. An abstention scores below every well-formed interval."""
    if not isinstance(output, dict) or "lower" not in output or "upper" not in output:
        return {"quality": -10.0, "category": "abstain"}
    lo, hi = output["lower"], output["upper"]
    if (type(lo) not in (int, float) or type(hi) not in (int, float) or not math.isfinite(lo)
            or not math.isfinite(hi) or lo > hi):
        return {"quality": -20.0, "category": "wrong"}
    alpha, theta = 1.0 - _boot(data)[2], truth["parameter"]
    s = (hi - lo) + (2.0 / alpha) * (max(0.0, lo - theta) + max(0.0, theta - hi))
    return {"quality": -min(s / abs(theta), 9.0), "category": "correct" if lo <= theta <= hi else "wrong"}


def boot_normal(data):
    """Baseline: the normal approximation, mean +- z s / sqrt(n); for the median, median +- z sqrt(pi/2) s / sqrt(n)
    (the normal-theory standard error of the median)."""
    x, statistic, level, *_ = _boot(data)
    n = len(x)
    z, s = _N.inv_cdf(0.5 + level / 2.0), statistics.stdev(x)
    centre, se = ((math.fsum(x) / n, s / math.sqrt(n)) if statistic == "mean"
                  else (statistics.median(x), math.sqrt(math.pi / 2.0) * s / math.sqrt(n)))
    return {"lower": centre - z * se, "upper": centre + z * se, "level": level, "statistic": statistic}


def boot_percentile(data):
    """Competitor: the percentile bootstrap on the same resamples (same seed and count)."""
    import warnings
    import numpy as np
    from scipy.stats import bootstrap
    x, statistic, level, resamples, seed, _ = _boot(data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = bootstrap((np.asarray(x, dtype=float),), np.mean if statistic == "mean" else np.median,
                        n_resamples=resamples, method="percentile", confidence_level=level,
                        rng=np.random.default_rng(seed), vectorized=True)
    lo, hi = float(res.confidence_interval.low), float(res.confidence_interval.high)
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return None
    return {"lower": lo, "upper": hi, "level": level, "statistic": statistic}


# =================================================================== 3. small mixed-integer programs
MILP_OPS = ("<=", ">=", "==")
MILP_INPUT_SIZE, MILP_NATIVE_VARS, MILP_NATIVE_ROWS = 2000, 150, 150
MILP_MAX_ABS = 10 ** 6                 # coefficients, right-hand sides and bounds (|activity| < 2^62 for 2000 vars)
MILP_ENUM_MAX = 1 << 16                # boxes up to this many integer points are enumerated by the verifier
MILP_CERTIFICATES = ("lp_dual", "enumeration", "none")
MILP_DUAL_GRID = 40                    # multipliers are snapped toward zero onto multiples of 2^-40


def _int(value, name):
    if type(value) is not int or abs(value) > MILP_MAX_ABS:
        raise GenomeError(f"{name}: integer data with |value| <= {MILP_MAX_ABS} required")
    return value


def _ip(data):
    """Parse a bounded pure-integer program: names sorted; rows as ({index: coefficient}, op, rhs)."""
    _mapping(data)
    variables, constraints, objective = data.get("variables"), data.get("constraints"), data.get("objective")
    if not isinstance(variables, dict) or not 1 <= len(variables) <= MILP_INPUT_SIZE:
        raise GenomeError(f"variables: an object of 1-{MILP_INPUT_SIZE} name -> [low, high]")
    if not all(isinstance(k, str) and k for k in variables):
        raise GenomeError("variable names are non-empty strings")
    names = sorted(variables)
    index = {name: j for j, name in enumerate(names)}
    lo, hi = [], []
    for name in names:
        b = variables[name]
        if not isinstance(b, list) or len(b) != 2:
            raise GenomeError(f"variable {name}: bounds [low, high]")
        low, high = _int(b[0], f"{name} low"), _int(b[1], f"{name} high")
        if low > high:
            raise GenomeError(f"variable {name}: low > high")
        lo.append(low)
        hi.append(high)

    def coefficients(c, what):
        if not isinstance(c, dict) or not all(k in index for k in c):
            raise GenomeError(f"{what}: coefficients over declared variables")
        parsed = {index[k]: _int(v, f"{what} coefficient") for k, v in c.items()}
        return {j: v for j, v in parsed.items() if v}
    if not isinstance(constraints, list) or len(constraints) > MILP_INPUT_SIZE:
        raise GenomeError(f"constraints: a list of at most {MILP_INPUT_SIZE} rows")
    rows = []
    for i, row in enumerate(constraints):
        if (not isinstance(row, dict) or not {"coefficients", "op", "rhs"} <= set(row)
                or not set(row) <= {"coefficients", "op", "rhs", "requirement_id"} or row["op"] not in MILP_OPS):
            raise GenomeError(f"constraint {i}: {{coefficients, op in {MILP_OPS}, rhs}}")
        coef = coefficients(row["coefficients"], f"constraint {i}")
        if not coef:
            raise GenomeError(f"constraint {i}: at least one nonzero coefficient")
        rows.append((coef, row["op"], _int(row["rhs"], f"constraint {i} rhs")))
    if (not isinstance(objective, dict) or set(objective) != {"coefficients", "sense"}
            or objective["sense"] not in ("max", "min")):
        raise GenomeError("objective: {coefficients, sense: max | min}")
    obj = [0] * len(names)
    for j, v in coefficients(objective["coefficients"], "objective").items():
        obj[j] = v
    return names, lo, hi, rows, obj, objective["sense"]


def _box(lo, hi, cap):
    """Number of integer points in the box, or cap + 1 once it exceeds cap."""
    total = 1
    for low, high in zip(lo, hi):
        total *= high - low + 1
        if total > cap:
            return cap + 1
    return total


def _rows_hold(rows, x):
    for coef, op, rhs in rows:
        act = sum(a * x[j] for j, a in coef.items())
        if (op == "<=" and act > rhs) or (op == ">=" and act < rhs) or (op == "==" and act != rhs):
            return False
    return True


def _lp_duals(rows, lo, hi, c_max):
    """LP-relaxation multipliers in max form (an upper bound on max c_max . x): y_i >= 0 on <= rows, <= 0 on >= rows,
    free on == rows; tiny wrong-signed values are clipped (any sign-feasible y gives a valid bound over a box)."""
    import numpy as np
    from scipy.optimize import linprog
    n, m = len(lo), len(rows)
    ub = [i for i, (_, op, _) in enumerate(rows) if op != "=="]
    eq = [i for i, (_, op, _) in enumerate(rows) if op == "=="]

    def matrix(idx, flip):
        a = np.zeros((len(idx), n))
        for r, i in enumerate(idx):
            sign = -1.0 if flip and rows[i][1] == ">=" else 1.0
            for j, v in rows[i][0].items():
                a[r, j] = sign * v
        return a
    res = linprog(-np.asarray(c_max, dtype=float),
                  A_ub=matrix(ub, True) if ub else None,
                  b_ub=[(-1.0 if rows[i][1] == ">=" else 1.0) * rows[i][2] for i in ub] if ub else None,
                  A_eq=matrix(eq, False) if eq else None, b_eq=[rows[i][2] for i in eq] if eq else None,
                  bounds=list(zip(lo, hi)), method="highs")
    y = [0.0] * m
    if res.status != 0:
        return y, None                          # the zero multipliers still bound the objective over the box
    for k, i in enumerate(ub):
        lam = float(res.ineqlin.marginals[k])  # d(min of -c_max x) / d b_ub <= 0
        y[i] = max(-lam, 0.0) if rows[i][1] == "<=" else min(lam, 0.0)
    for k, i in enumerate(eq):
        y[i] = -float(res.eqlin.marginals[k])
    # Snapping toward zero keeps every sign, so the bound stays valid; it loosens it by at most about 1e-6 here.
    grid = 2.0 ** MILP_DUAL_GRID
    return [math.trunc(v * grid) / grid if math.isfinite(v) else 0.0 for v in y], -float(res.fun)


def _dual_bound_floor(rows, lo, hi, c_max, y):
    """Floor of the exact weak-duality bound sum_i y_i b_i + sum_j max(r_j l_j, r_j u_j), r = c_max - A'y, for
    multipliers on the 2^-40 grid: every term is scaled to an exact Python integer."""
    scale = 1 << MILP_DUAL_GRID
    ys = [int(v * scale) for v in y]           # exact: each multiplier is a multiple of 2^-40
    reduced = [c * scale for c in c_max]
    total = 0
    for (coef, _, rhs), yi in zip(rows, ys):
        if yi:
            total += yi * rhs
            for j, a in coef.items():
                reduced[j] -= yi * a
    total += sum(max(r * low, r * high) for r, low, high in zip(reduced, lo, hi))
    return total // scale


def milp_solve(data, budget):
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    names, lo, hi, rows, obj, sense = _ip(data)
    n, m = len(names), len(rows)
    if n > MILP_NATIVE_VARS or m > MILP_NATIVE_ROWS:
        return _abstain(f"{n} variables and {m} rows exceed the small-program native size "
                        f"({MILP_NATIVE_VARS} x {MILP_NATIVE_ROWS})", variables=n, rows=m)
    a = np.zeros((m, n))
    for i, (coef, _, _) in enumerate(rows):
        for j, v in coef.items():
            a[i, j] = v
    low = [rhs if op in (">=", "==") else -np.inf for _, op, rhs in rows]
    high = [rhs if op in ("<=", "==") else np.inf for _, op, rhs in rows]
    sign = -1.0 if sense == "max" else 1.0
    limit = max(1.0, min(10.0, float(budget.get("latency_s", 5.0)) if isinstance(budget, dict) else 5.0))
    # A zero relative gap: at HiGHS's default (1e-4) branch and cut stops at an incumbent it reports as optimal. The
    # absolute gap stays at HiGHS's default 1e-6, below the unit step of an integer objective.
    res = milp(sign * np.asarray(obj, dtype=float), constraints=[LinearConstraint(a, low, high)] if m else (),
               bounds=Bounds(lo, hi), integrality=np.ones(n), options={"time_limit": limit, "mip_rel_gap": 0.0})
    if res.x is None:
        return _unknown(f"HiGHS found no integer solution ({res.message}); infeasibility is not independently "
                        "certified here", solver_status=int(res.status))
    x = [int(round(float(v))) for v in res.x]
    if any(not low_j <= v <= high_j for v, low_j, high_j in zip(x, lo, hi)) or not _rows_hold(rows, x):
        return _unknown("the rounded HiGHS solution violates the exact integer model")
    value = sum(o * v for o, v in zip(obj, x))
    c_max = obj if sense == "max" else [-o for o in obj]
    y, lp_value = _lp_duals(rows, lo, hi, c_max)
    floor = _dual_bound_floor(rows, lo, hi, c_max, y)
    dual_bound = floor if sense == "max" else -floor
    box = _box(lo, hi, MILP_ENUM_MAX)
    # HiGHS's status is never the evidence: an enumeration claim needs this solver's own scan of the box to agree.
    certified = ("lp_dual" if dual_bound == value
                 else "enumeration" if box <= MILP_ENUM_MAX and _scan_box(lo, hi, a, rows, obj, sense) == value
                 else "none")
    optimal = certified != "none"
    return answer({"values": x, "objective": value, "optimal": optimal, "certified_by": certified,
                   "dual_bound": dual_bound, "gap": 0 if optimal else abs(dual_bound - value)},
                  {"variables": names, "solver": "scipy.optimize.milp (HiGHS branch and cut)",
                   "solver_status": str(res.message), "solver_reports_optimal": res.status == 0,
                   "time_limit_s": limit, "mip_rel_gap": 0.0, "row_duals": y,
                   "dual_convention": "max form: y >= 0 on <= rows, y <= 0 on >= rows, free on == rows; bound = "
                                      "sum y b + sum_j max(r_j low_j, r_j high_j), r = c - A'y (c negated for min)",
                   "lp_relaxation_value": lp_value if sense == "max" or lp_value is None else -lp_value,
                   "box_points": box if box <= MILP_ENUM_MAX else None,
                   "optimality": "claimed only from the exact LP dual bound or from this solver's own scan of a box "
                                 "of at most 2^16 points, and re-checked by the verifier's enumeration; HiGHS's own "
                                 "optimality status is recorded but not trusted"})


def _scan_box(lo, hi, a, rows, obj, sense):
    """The solver's own exhaustive optimum over a box of at most 2^16 points (None if none is feasible), on the dense
    float64 matrix: every activity and objective value is an integer of magnitude below 150 x 10^12 < 2^53 here, so
    the arithmetic is exact."""
    import numpy as np
    free = [j for j, (low, high) in enumerate(zip(lo, hi)) if low < high]
    fixed = [j for j, (low, high) in enumerate(zip(lo, hi)) if low == high]
    grid = np.meshgrid(*(np.arange(lo[j], hi[j] + 1, dtype=float) for j in free), indexing="ij")
    points = np.stack([g.ravel() for g in grid], axis=1) if free else np.zeros((1, 0))
    constant = np.asarray([lo[j] for j in fixed], dtype=float)
    ok = np.ones(len(points), dtype=bool)
    for i, (_, op, rhs) in enumerate(rows):
        act = points @ a[i, free] + float(a[i, fixed] @ constant)
        ok &= (act <= rhs) if op == "<=" else (act >= rhs) if op == ">=" else (act == rhs)
    if not ok.any():
        return None
    c = np.asarray(obj, dtype=float)
    values = points[ok] @ c[free] + float(c[fixed] @ constant)
    return int(values.max() if sense == "max" else values.min())


def _verify_bound(rows, lo, hi, c_max, duals):
    """Verifier's own weak-duality evaluation, column by column in exact rationals."""
    y = [Fraction(v) for v in duals]
    columns = [[] for _ in lo]
    for i, (coef, _, _) in enumerate(rows):
        for j, a in coef.items():
            columns[j].append((i, a))
    bound = sum((yi * rhs for yi, (_, _, rhs) in zip(y, rows)), Fraction(0))
    for j, column in enumerate(columns):
        r = c_max[j] - sum((y[i] * a for i, a in column), Fraction(0))
        bound += r * (hi[j] if r > 0 else lo[j])
    return bound


def _enumerate(lo, hi, rows, obj, sense):
    """Exhaustive optimum over an enumerable box in exact int64 arithmetic: (value, point) or None if infeasible.
    Only free variables are enumerated (at most 16 when the box has at most 2^16 points); fixed ones are constants.
    |activity| <= 2000 x 10^6 x 10^6 < 2^62, so int64 never overflows on valid input."""
    import numpy as np
    free = [j for j, (low, high) in enumerate(zip(lo, hi)) if low < high]
    k = np.arange(math.prod(hi[j] - lo[j] + 1 for j in free), dtype=np.int64)
    points = np.empty((k.size, len(free)), dtype=np.int64)
    for col, j in enumerate(free):
        size = hi[j] - lo[j] + 1
        points[:, col] = lo[j] + k % size
        k //= size
    where = {j: col for col, j in enumerate(free)}
    feasible = np.ones(k.size, dtype=bool)
    for coef, op, rhs in rows:
        act = np.full(k.size, sum(a * lo[j] for j, a in coef.items() if j not in where), dtype=np.int64)
        for j, a in coef.items():
            if j in where:
                act += a * points[:, where[j]]
        feasible &= (act <= rhs) if op == "<=" else (act >= rhs) if op == ">=" else (act == rhs)
    if not feasible.any():
        return None
    fixed = sum(o * lo[j] for j, o in enumerate(obj) if j not in where)
    values = fixed + points[feasible] @ np.asarray([obj[j] for j in free], dtype=np.int64)
    best = int(np.argmax(values) if sense == "max" else np.argmin(values))
    point, chosen = list(lo), points[feasible][best]
    for col, j in enumerate(free):
        point[j] = int(chosen[col])
    return int(values[best]), point


def milp_verify(data, output, certificate):
    """Exact integer feasibility and objective; optimality only from an exact dual bound or enumeration."""
    names, lo, hi, rows, obj, sense = _ip(data)
    certificate = _cert(certificate)
    keys = {"values", "objective", "optimal", "certified_by", "dual_bound", "gap"}
    if not isinstance(output, dict) or set(output) != keys:
        return {"output_shape": False}
    x = output["values"]
    if (not isinstance(x, list) or len(x) != len(names) or not all(type(v) is int for v in x)
            or type(output["objective"]) is not int or type(output["optimal"]) is not bool
            or output["certified_by"] not in MILP_CERTIFICATES or type(output["dual_bound"]) is not int
            or type(output["gap"]) is not int):
        return {"output_shape": False}
    within = all(low <= v <= high for v, low, high in zip(x, lo, hi))
    feasible = within and all(
        (act <= rhs) if op == "<=" else (act >= rhs) if op == ">=" else (act == rhs)
        for act, op, rhs in ((sum(x[j] * a for j, a in coef.items()), op, rhs) for coef, op, rhs in rows))
    value = sum(v * o for v, o in zip(x, obj))
    duals = certificate.get("row_duals")
    signs = (isinstance(duals, list) and len(duals) == len(rows) and all(_real(y) for y in duals)
             and all(y >= 0.0 if op == "<=" else y <= 0.0 if op == ">=" else True
                     for y, (_, op, _) in zip(duals, rows)))
    rounded = None
    if signs:
        c_max = obj if sense == "max" else [-o for o in obj]
        top = math.floor(_verify_bound(rows, lo, hi, c_max, duals))
        rounded = top if sense == "max" else -top
    optimal, how = output["optimal"], output["certified_by"]
    consistent = feasible and value == output["objective"]
    if how == "lp_dual":
        certified = optimal and rounded is not None and rounded == value
    elif how == "enumeration":
        certified = (optimal and consistent and _box(lo, hi, MILP_ENUM_MAX) <= MILP_ENUM_MAX
                     and (_enumerate(lo, hi, rows, obj, sense) or (None,))[0] == value)
    else:
        certified = not optimal                 # an honest feasibility-only claim
    return {"output_shape": True, "integral_within_bounds": within, "every_constraint_holds": feasible,
            "objective_recomputed": value == output["objective"], "dual_multipliers_sign_feasible": signs,
            "dual_bound_recomputed": rounded is not None and rounded == output["dual_bound"],
            "bound_respected": rounded is not None and (value <= rounded if sense == "max" else value >= rounded),
            "gap_recomputed": output["gap"] == (0 if optimal else abs(output["dual_bound"] - output["objective"])),
            "optimality_claim_certified": certified}


def _knapsack_optimum(values, weights, uppers, capacity):
    best = [0] * (capacity + 1)
    for v, w, u in zip(values, weights, uppers):
        for _ in range(u):
            for c in range(capacity, w - 1, -1):
                if best[c - w] + v > best[c]:
                    best[c] = best[c - w] + v
    return best[capacity]


def _cover_optimum(sets, costs, elements):
    full = (1 << elements) - 1
    masks = [sum(1 << e for e in s) for s in sets]
    best = [math.inf] * (full + 1)
    best[0] = 0
    for mask in range(full + 1):
        b = best[mask]
        if b == math.inf:
            continue
        for bits, c in zip(masks, costs):
            new = mask | bits
            if new != mask and b + c < best[new]:
                best[new] = b + c
    return best[full]


def milp_instance(seed):
    """Knapsack-like, assignment-like and covering programs; truth by an independent exact method (capacity DP,
    Hungarian assignment, subset DP), never by the solver under test."""
    r = random.Random(980_000 + seed)
    kind = ("knapsack", "assignment", "covering")[seed % 3]
    if kind == "knapsack":
        n = r.randint(8, 28)
        upper = [r.choice((1, 1, 1, 2, 3)) for _ in range(n)]
        weight = [r.randint(5, 80) for _ in range(n)]
        value = [max(1, w + r.randint(-15, 25)) for w in weight]
        capacity = int(sum(u * w for u, w in zip(upper, weight)) * r.uniform(0.25, 0.5))
        names = [f"x{i:02d}" for i in range(n)]
        data = {"variables": {nm: [0, u] for nm, u in zip(names, upper)},
                "constraints": [{"coefficients": dict(zip(names, weight)), "op": "<=", "rhs": capacity}],
                "objective": {"coefficients": dict(zip(names, value)), "sense": "max"}}
        return data, {"optimum": _knapsack_optimum(value, weight, upper, capacity), "kind": kind}
    if kind == "assignment":
        from scipy.optimize import linear_sum_assignment
        k = r.randint(4, 9)
        perm = list(range(k))
        r.shuffle(perm)
        profit = [[r.randint(1, 99) for _ in range(k)] for _ in range(k)]
        forbidden = {(i, j) for i in range(k) for j in range(k) if j != perm[i] and r.random() < 0.15}
        name = {(i, j): f"a{i}_{j}" for i in range(k) for j in range(k)}
        data = {"variables": {name[i, j]: [0, 0 if (i, j) in forbidden else 1] for i in range(k) for j in range(k)},
                "constraints": [{"coefficients": {name[i, j]: 1 for j in range(k)}, "op": "==", "rhs": 1}
                                for i in range(k)]
                + [{"coefficients": {name[i, j]: 1 for i in range(k)}, "op": "==", "rhs": 1} for j in range(k)],
                "objective": {"coefficients": {name[i, j]: profit[i][j] for i in range(k) for j in range(k)},
                              "sense": "max"}}
        cost = [[-profit[i][j] if (i, j) not in forbidden else 10 ** 6 for j in range(k)] for i in range(k)]
        rows_, cols_ = linear_sum_assignment(cost)
        assert all((int(i), int(j)) not in forbidden for i, j in zip(rows_, cols_))
        return data, {"optimum": sum(profit[i][j] for i, j in zip(rows_, cols_)), "kind": kind}
    elements, count = r.randint(8, 13), r.randint(10, 22)
    sets = [set(r.sample(range(elements), r.randint(2, 5))) for _ in range(count)]
    for e in range(elements):
        if not any(e in s for s in sets):
            sets[r.randrange(count)].add(e)
    costs = [r.randint(1, 4) * len(s) + r.randint(0, 6) for s in sets]
    names = [f"s{j:02d}" for j in range(count)]
    data = {"variables": {nm: [0, 1] for nm in names},
            "constraints": [{"coefficients": {names[j]: 1 for j, s in enumerate(sets) if e in s}, "op": ">=", "rhs": 1}
                            for e in range(elements)],
            "objective": {"coefficients": dict(zip(names, costs)), "sense": "min"}}
    return data, {"optimum": _cover_optimum([sorted(s) for s in sets], costs, elements), "kind": kind}


def milp_subregion(data):
    ops = {row["op"] for row in data["constraints"]}
    return "assignment" if "==" in ops else "covering" if data["objective"]["sense"] == "min" else "knapsack"


def milp_score(data, truth, output):
    """Quality 1 at the optimum, falling with the relative objective gap (floor 0); an infeasible point, a false
    objective or a false optimality claim is wrong (-1); an abstention scores -0.5."""
    if not isinstance(output, dict) or not isinstance(output.get("values"), list):
        return {"quality": -0.5, "category": "abstain"}
    names, lo, hi, rows, obj, sense = _ip(data)
    x = output["values"]
    if (len(x) != len(names) or not all(type(v) is int and low <= v <= high for v, low, high in zip(x, lo, hi))
            or not _rows_hold(rows, x)):
        return {"quality": -1.0, "category": "wrong"}
    value, best = sum(o * v for o, v in zip(obj, x)), truth["optimum"]
    if output.get("objective", value) != value or (output.get("optimal") is True and value != best):
        return {"quality": -1.0, "category": "wrong"}
    return {"quality": max(0.0, 1.0 - abs(value - best) / max(1, abs(best))),
            "category": "correct" if value == best else "wrong"}


def _greedy_repair(lo, hi, rows, obj, sense, x):
    """Unit moves that most reduce total row violation (ties: better objective), then unit moves that improve the
    objective while staying feasible. None when it gets stuck infeasible."""
    n, sign = len(lo), 1 if sense == "max" else -1
    cols = [[] for _ in range(n)]
    for i, (coef, _, _) in enumerate(rows):
        for j, a in coef.items():
            cols[j].append((i, a))
    act = [sum(a * x[j] for j, a in coef.items()) for coef, _, _ in rows]

    def viol(i, v):
        _, op, rhs = rows[i]
        return max(0, v - rhs) if op == "<=" else max(0, rhs - v) if op == ">=" else abs(v - rhs)

    def delta(j, step):
        return sum(viol(i, act[i] + step * a) - viol(i, act[i]) for i, a in cols[j])

    def move(j, step):
        x[j] += step
        for i, a in cols[j]:
            act[i] += step * a
    total = sum(viol(i, v) for i, v in enumerate(act))
    span = sum(high - low for low, high in zip(lo, hi))
    for _ in range(10 * span + 100):
        if total == 0:
            break
        best = min(((dv, -sign * step * obj[j], j, step) for j in range(n) for step in (1, -1)
                    if lo[j] <= x[j] + step <= hi[j] for dv in (delta(j, step),) if dv < 0), default=None)
        if best is None:
            return None
        total += best[0]
        move(best[2], best[3])
    if total:
        return None
    for _ in range(span + 1):
        best = min(((-sign * step * obj[j], j, step) for j in range(n) for step in (1, -1)
                    if sign * step * obj[j] > 0 and lo[j] <= x[j] + step <= hi[j] and delta(j, step) == 0),
                   default=None)
        if best is None:
            break
        move(best[1], best[2])
    return x


def milp_lp_round(data):
    """Baseline: LP relaxation (HiGHS), every value rounded down, then greedy unit-move repair and improvement."""
    import numpy as np
    from scipy.optimize import linprog
    names, lo, hi, rows, obj, sense = _ip(data)
    n = len(names)
    ub = [(coef, op, rhs) for coef, op, rhs in rows if op != "=="]
    eq = [(coef, op, rhs) for coef, op, rhs in rows if op == "=="]

    def matrix(rs):
        a = np.zeros((len(rs), n))
        for r, (coef, op, _) in enumerate(rs):
            for j, v in coef.items():
                a[r, j] = -v if op == ">=" else v
        return a
    res = linprog((-1.0 if sense == "max" else 1.0) * np.asarray(obj, dtype=float),
                  A_ub=matrix(ub) if ub else None, b_ub=[-rhs if op == ">=" else rhs for _, op, rhs in ub] or None,
                  A_eq=matrix(eq) if eq else None, b_eq=[rhs for _, _, rhs in eq] or None,
                  bounds=list(zip(lo, hi)), method="highs")
    if res.status != 0:
        return None
    x = [min(high, max(low, math.floor(float(v) + 1e-9))) for v, low, high in zip(res.x, lo, hi)]
    x = _greedy_repair(lo, hi, rows, obj, sense, x)
    return None if x is None else {"values": x, "objective": sum(o * v for o, v in zip(obj, x))}


def milp_cpsat(data):
    """Competitor: OR-Tools CP-SAT on the same integer model (one worker, fixed seed, 10 s); exhaustive enumeration
    of a small box when OR-Tools is not installed."""
    names, lo, hi, rows, obj, sense = _ip(data)
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        if _box(lo, hi, MILP_ENUM_MAX) > MILP_ENUM_MAX:
            return None
        found = _enumerate(lo, hi, rows, obj, sense)
        return None if found is None else {"values": found[1], "objective": found[0]}
    model = cp_model.CpModel()
    x = [model.new_int_var(low, high, name) for low, high, name in zip(lo, hi, names)]
    for coef, op, rhs in rows:
        expr = sum(a * x[j] for j, a in coef.items())
        model.add(expr <= rhs if op == "<=" else expr >= rhs if op == ">=" else expr == rhs)
    objective = sum(o * v for o, v in zip(obj, x) if o)
    if sense == "max":
        model.maximize(objective)
    else:
        model.minimize(objective)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = 10.0
    if solver.solve(model) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    values = [int(solver.value(v)) for v in x]
    return {"values": values, "objective": sum(o * v for o, v in zip(obj, values))}


# =================================================================== genomes
INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.montecarlo.antithetic_control_variates", version="1.0.0", family="mc_expectation",
            layer=3, operation="mc_expectation_estimate", epistemic_class="estimate",
            subgeometry="expectation of a closed-form function of 1-8 independent normal, uniform or exponential "
                        "coordinates",
            source_provenance="Monte Carlo integration with antithetic variates (Hammersley and Morton 1956) and "
                              "regression control variates (Glasserman 2004, ch. 4)",
            native_representation="declared coordinate distributions, a function family with its parameters, an "
                                  "even evaluation budget, a seed and a confidence level",
            required_inputs=("coordinates", "function", "evaluations", "seed"),
            output_contract={"estimate": "float", "interval": "[float, float]", "std_error": "float",
                             "level": "float", "evaluations": "int"},
            algorithm_or_runtime="antithetic pairs (u, 1 - u) through inverse CDFs; control coefficients by OLS of "
                                 "a pilot block's pair means (max(1/8, 8 per parameter) of the pairs) on "
                                 "pair-averaged centred moment controls with known zero means; the estimate is the "
                                 "mean of the remaining pairs' control-adjusted values; iid CLT interval whose "
                                 "standard error is floored at the evaluation rounding noise; points within rounding "
                                 "of an indicator's threshold, a call's strike or exp's overflow are evaluated by the "
                                 "reference arithmetic (NormalDist, math.fsum, math.exp)",
            parameters={"native_dimension": MC_NATIVE_DIM, "native_evaluations": list(MC_NATIVE_EVALUATIONS),
                        "pilot": "max(pairs // 8, 8 (controls + 1)) pairs", "min_indicator_hits": MC_MIN_HITS,
                        "min_positive_call_payoffs": MC_MIN_HITS, "standard_error_floor": MC_SE_FLOOR,
                        "evaluation_rounding_bound_units_of_2^-53": MC_NOISE_C,
                        "evaluation_rounding_bound_units_of_2^-1074": MC_NOISE_C,
                        "min_std_error": "twice the smallest normal double (the verifier: once)",
                        "standard_error_floor_over_rounding_noise": MC_NOISE_SE,
                        "coefficient_bound_in_mean_abs_f": MC_COEF_MAX,
                        "recomputation_tolerance_in_standard_errors": {"estimate": MC_EST_TOL,
                                                                       "std_error": MC_SE_TOL}},
            composition_inputs=("distribution model", "payoff or loss function"),
            composition_outputs=("estimate", "interval"),
            evidence_type="statistical_estimate",
            verification_method="pure-Python recomputation from the declared uniform stream (regenerated from the "
                                "seed): NormalDist inverse CDFs, every f value and control and its own bound on that "
                                "value's rounding, then in units of its own mean |f| the pilot block's least-squares "
                                "normal equations at the certificate's (bounded) coefficients (to the rounding bound), "
                                "the main block's adjusted mean (to 1% of the recomputed standard error, which is "
                                "never below 200 times the estimate's rounding noise) and standard error (to 0.01% "
                                "plus twice that noise), z from its own quantile and the interval arithmetic (a "
                                "representable est -+ z se, to a few units in the last place); the moment, "
                                "rare-event and underflow (a normal standard error) preconditions",
            confidence_semantics="an asymptotic (CLT) interval at the stated level under the declared model; the "
                                 "verifier certifies the arithmetic and the fit on the declared draws, never that "
                                 "the interval covers the true expectation (about 1 - level of honest intervals "
                                 "miss it)",
            resource_profile="O(evaluations x dimension) draws and one least-squares fit with <= 16 controls",
            latency_profile="milliseconds to solve; about 0.1 s for the pure-Python verifier at 8192 evaluations",
            known_strengths=("a valid error bar in any dimension, without smoothness assumptions",
                             "antithetic pairs cancel the odd part of f exactly; the controls remove most of the "
                             "even quadratic part",
                             "every number is recomputable from the declared stream"),
            known_failure_modes=("the CLT interval undercovers for heavy-tailed f at small budgets",
                                 "scrambled Sobol points at the same budget usually reach a smaller error on this "
                                 "benchmark (review seeds 3000-3119: 23 candidate wins, 95 losses), at about two to "
                                 "seven times the candidate's solve latency, median about four on dev seeds "
                                 "(verification excluded, as the admission harness measures it)",
                                 "rare events (indicators with few hits or misses, calls with few positive payoffs) "
                                 "make the interval meaningless (it returns UNKNOWN)"),
            counterindications=("rare events (use mc_importance)", "infinite-variance functions",
                                "smooth integrands of very low dimension where quadrature or QMC is exact enough"),
            abstention_conditions=(f"dimension above {MC_NATIVE_DIM}",
                                   f"evaluations outside {MC_NATIVE_EVALUATIONS[0]}-{MC_NATIVE_EVALUATIONS[1]}",
                                   "exp(w x) of an exponential coordinate with 4 w >= rate (no finite fourth moment)",
                                   f"fewer than {MC_MIN_HITS} indicator hits or misses (UNKNOWN)",
                                   f"fewer than {MC_MIN_HITS} positive call payoffs (UNKNOWN)",
                                   "an estimate, interval or coefficient beyond double precision (UNKNOWN)",
                                   "mean |f| so small that the standard error's floor would be subnormal (UNKNOWN)"),
            benchmark_suite="exp_linear, cos_product, power_product (mixed normal/uniform/exponential coordinates), "
                            "call_on_sum and indicator_sum (normal coordinates); dimension 1-8; 8192 evaluations; "
                            "analytic truth; seeds 0-9 dev / held-out seeds frozen by the admission harness",
            baseline="plain Monte Carlo at a fixed 1000 evaluations with a CLT interval",
            competitor="randomized quasi-Monte Carlo: 16 independent scrambled Sobol sequences (scipy.stats.qmc) at "
                       "the same budget, t interval across replicates",
            dependency="scipy", **_common()),
        solve=mc_solve, verify=mc_verify, instance=mc_instance, score=mc_score, baseline=mc_plain,
        competitor=mc_sobol, subregion=mc_subregion, tolerance=1e-6,
        notes={"score": "quality = -|estimate - E f| / sd(f) capped at 1; category = interval covers E f",
               "truth": "analytic moments (mc_truth), never Monte Carlo"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.bootstrap.bca_interval", version="1.0.0", family="bootstrap_ci", layer=3,
            operation="bca_bootstrap_interval", epistemic_class="estimate",
            subgeometry=f"confidence interval for the mean or median of a skewed iid sample, {BOOT_NATIVE_MIN_N}-"
                        f"{BOOT_MAX_WORK // 2000} observations at the default 2000 resamples (resamples x "
                        f"observations <= {BOOT_MAX_WORK}: up to {BOOT_MAX_WORK // BOOT_NATIVE_MIN_RESAMPLES} at "
                        f"{BOOT_NATIVE_MIN_RESAMPLES})",
            source_provenance="Efron (1987) bias-corrected and accelerated bootstrap; Efron and Tibshirani (1993) "
                              "ch. 14; scipy.stats.bootstrap's resampling scheme and BCa formulas",
            native_representation="sample values, statistic (mean or median), level, resample count and seed",
            required_inputs=("sample", "statistic", "seed"),
            output_contract={"lower": "float", "upper": "float", "level": "float", "statistic": "str",
                             "estimate": "float", "resamples": "int", "method": "str"},
            algorithm_or_runtime="scipy.stats.bootstrap's BCa computed in numpy: resample indices from the seeded "
                                 "generator, bias correction from the share of replicates below the estimate (each "
                                 "replicate's side decided exactly: rational sums inside the rounding bound), "
                                 "jackknife acceleration (the mean's centred on an observation, both in units of the "
                                 "largest deviation), adjusted type-7 percentiles; a sample below 1/2 in magnitude is "
                                 "first scaled by a power of two, so the answer is scale-invariant down to subnormal "
                                 "samples",
            parameters={"native_min_observations": BOOT_NATIVE_MIN_N, "min_resamples": BOOT_NATIVE_MIN_RESAMPLES,
                        "verifier_work_bound": BOOT_MAX_WORK, "min_range_in_ulps_of_largest_value": BOOT_RESOLUTION},
            composition_inputs=("observed outcomes",), composition_outputs=("lower", "upper"),
            evidence_type="statistical_estimate",
            verification_method="regenerates the declared resample indices from the seed and recomputes, in pure "
                                "Python, every replicate statistic and its exact side of the estimate (exactly "
                                "rounded sums for the mean, order statistics and exact midpoint sums for the median), "
                                "the bias correction, the jackknife acceleration in exact integer arithmetic "
                                "(closed form for the mean, index arithmetic for leave-one-out medians), the "
                                "adjusted levels with its own normal quantiles and the type-7 percentiles; endpoints "
                                "agree to 1e-9 of the bootstrap spread plus 8 units in their last place",
            confidence_semantics="a BCa interval: second-order accurate, not exact; the verifier certifies that the "
                                 "interval is the BCa interval of this sample and seed, never that it covers the "
                                 "true parameter (coverage is measured over seeds against analytic truth)",
            resource_profile="resamples x observations statistic evaluations plus an n-point jackknife",
            latency_profile="milliseconds to solve; tens of milliseconds for the pure-Python verifier",
            known_strengths=("corrects the percentile interval's bias and skewness", "transformation-respecting",
                             "no normality assumption"),
            known_failure_modes=("undercovers for heavy right tails at small n (Pareto mean: 0.76 at level 0.9 on "
                                 "review seeds)",
                                 "the jackknife acceleration is a poor estimate for the median",
                                 "one realised interval misses the parameter at about the nominal miss rate or more",
                                 "for the mean its interval score is usually worse than the percentile bootstrap's "
                                 "(wider for the same coverage); its edge on review seeds was the median"),
            counterindications=("dependent observations (use a block bootstrap)", "statistics at the sample "
                                "extremes (minimum, maximum)", "infinite-variance data for the mean"),
            abstention_conditions=("independent is false", f"fewer than {BOOT_NATIVE_MIN_N} observations",
                                   f"fewer than {BOOT_NATIVE_MIN_RESAMPLES} resamples",
                                   f"fewer than {BOOT_MIN_DISTINCT} distinct values",
                                   f"resamples x observations above {BOOT_MAX_WORK}",
                                   f"a sample range below {BOOT_RESOLUTION} units in the last place of its largest "
                                   "value (double precision cannot resolve it)",
                                   "all leave-one-out statistics equal, or the bootstrap distribution on one side of "
                                   "the estimate (UNKNOWN)"),
            benchmark_suite="lognormal, exponential and Pareto (tail index 2.2-4.5) samples of 15-120, mean and "
                            "median, level 0.9, 2000 resamples; interval score against the analytic parameter; "
                            "seeds 0-9 dev / held-out seeds frozen by the admission harness",
            baseline="normal approximation: mean +- z s / sqrt(n) (median +- z sqrt(pi/2) s / sqrt(n))",
            competitor="percentile bootstrap on the same resamples (scipy.stats.bootstrap, method percentile)",
            dependency="scipy", **_common()),
        solve=boot_solve, verify=boot_verify, instance=boot_instance, score=boot_score, baseline=boot_normal,
        competitor=boot_percentile, subregion=boot_subregion, tolerance=1e-9,
        notes={"score": "quality = -(Gneiting-Raftery interval score) / |parameter|, capped at 9; correct iff covering",
               "coverage": "reported over dev and review seeds in tests/unit/test_genomes_stochastic.py, not tuned"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.milp.highs_certified", version="1.0.0", family="milp_optimize", layer=3,
            operation="milp_integer_optimize", epistemic_class="optimization",
            subgeometry="small bounded pure-integer linear programs with integer data (knapsack-like, "
                        "assignment-like, covering)",
            source_provenance="LP-based branch and cut (HiGHS via scipy.optimize.milp); weak LP duality",
            native_representation="variables with integer bounds; integer linear rows (<=, >=, ==); a linear "
                                  "objective with a sense",
            required_inputs=("variables", "constraints", "objective"),
            output_contract={"values": "[int] in sorted variable-name order", "objective": "int", "optimal": "bool",
                             "certified_by": "lp_dual | enumeration | none", "dual_bound": "int", "gap": "int"},
            algorithm_or_runtime="scipy.optimize.milp (HiGHS) with a time limit and a zero relative gap; LP "
                                 "relaxation by linprog for multipliers; the exact dual bound in rational "
                                 "arithmetic; its own float64 scan (exact on this data) of a box of at most 2^16 "
                                 "points before any enumeration claim",
            parameters={"native_variables": MILP_NATIVE_VARS, "native_rows": MILP_NATIVE_ROWS,
                        "enumeration_box": MILP_ENUM_MAX, "max_abs_data": MILP_MAX_ABS},
            composition_inputs=("compiled integer model",), composition_outputs=("values", "objective"),
            evidence_type="optimality_certificate",
            verification_method="exact integer arithmetic for integrality, bounds, every row and the objective; "
                                "sign-feasibility of the certificate's multipliers and its own column-wise rational "
                                "weak-duality bound; its own exhaustive int64 enumeration when the claim rests on it",
            confidence_semantics="feasibility and the objective are exact; optimality is certified only when the "
                                 "rounded exact LP dual bound equals the objective or the verifier enumerates the box; "
                                 "otherwise optimal is false and the gap to the proven bound is reported (HiGHS's own "
                                 "optimality status is recorded, not trusted)",
            resource_profile="one MILP and one LP of at most 150 x 150", latency_profile="milliseconds",
            known_strengths=("exact integer feasibility", "certified optimality whenever the LP relaxation is tight "
                             "(assignment-like) or the box is small",
                             "an honest proven gap otherwise"),
            known_failure_modes=("knapsack and covering relaxations are often loose: larger instances are returned "
                                 "feasible-only with a gap even when HiGHS proved optimality internally",
                                 "at HiGHS's default relative gap (1e-4) branch and cut reports suboptimal incumbents "
                                 "as optimal (87 of 300 large-coefficient 16-binary knapsacks on review seeds): the "
                                 "gap is set to zero and HiGHS's status is never the evidence",
                                 "HiGHS's branch-and-cut setup dominates small instances: CP-SAT reached the same "
                                 "optima in about a seventh to a fifteenth of the candidate's solve time on review "
                                 "seeds 3000-3119 (medians 2-3 ms against 19-32 ms)",
                                 "a time limit can stop branch and cut with a weaker incumbent",
                                 "infeasible models return UNKNOWN (infeasibility is not independently certified)"),
            counterindications=("continuous or fractional data (the model must be integer)",
                                "large industrial MILPs beyond the native size", "nonlinear objectives or rows"),
            abstention_conditions=(f"more than {MILP_NATIVE_VARS} variables or {MILP_NATIVE_ROWS} rows",
                                   "no integer solution found (UNKNOWN)"),
            benchmark_suite="bounded knapsack (8-28 items), assignment with forbidden pairs (4-9 square) and weighted "
                            "set covering (8-13 elements, 10-22 sets); optimum by capacity DP, Hungarian assignment "
                            "and subset DP; seeds 0-9 dev / held-out seeds frozen by the admission harness",
            baseline="LP relaxation rounded down, then greedy unit-move repair and improvement",
            competitor="OR-Tools CP-SAT on the same integer model (one worker, fixed seed); exhaustive enumeration "
                       "of a small box if OR-Tools is absent",
            dependency="scipy", **_common()),
        solve=milp_solve, verify=milp_verify, instance=milp_instance, score=milp_score, baseline=milp_lp_round,
        competitor=milp_cpsat, subregion=milp_subregion, tolerance=1e-9,
        notes={"score": "quality = 1 - |objective - optimum| / max(1, |optimum|), floored at 0; infeasible, a false "
                        "objective or a false optimality claim is wrong (-1)"}),
]
