"""Layer 3 forecasting intelligence: a calibrated predictive distribution, not a point guess.

``forecast_quantile`` (operation ``forecast_distribution``): damped-trend exponential smoothing (Holt,
Gardner-McKenzie damping) with parameters chosen on in-sample one-step error, and a predictive
distribution built from rolling-origin, horizon-specific log-ratio errors of that same model (empirical
quantiles, no normality assumption). Output: point path and quantile paths for the requested levels.

Native benchmark: M4 Weekly series (Makridakis et al., independent public competition data) outside the
Micro/Industry categories, which the P6 natural composition family reserves. Truth is the real 13-week
continuation. Score: negative mean scaled pinball loss over levels and horizons (scale = mean absolute
one-step naive change in the history, the MASE scale) - it rewards calibration and sharpness together.
Baseline: naive (last value) with Gaussian random-walk quantiles. Competitor: the Theta method (SES with
half the regression drift; M3 winner, a strong M4 benchmark) with the same empirical-error quantiles.

``newsvendor_compile`` (operation ``compile_newsvendor``) is the typed translation used by the
``forecast_then_allocate`` composition: forecast scenarios + overage/underage costs + shared capacity
-> the sample-average-approximation integer model the existing CP-SAT ``optimize`` family solves.
"""
from __future__ import annotations

import gzip
import json
import math
from functools import lru_cache
from pathlib import Path

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int, finite

DATA = Path(__file__).resolve().parents[3] / "cortex" / "evaluation" / "data" / "m4_weekly.json.gz"
LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT")
LEVELS = (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95)
MIN_HISTORY = 60
# Non-constitutional method parameters: the closed space P8 protected evolution may search
# (greg/cognition/evolution.py). The genome runs DEFAULT_CONFIG; a retained evolved config is a proposal
# until a reviewed change adopts it.
DEFAULT_CONFIG = {"fit_window": 260, "origins": 104, "beta_set": [0.0, 0.05, 0.1, 0.2],
                  "phi_set": [0.8, 0.9, 0.98], "error_model": "log_ratio", "interval_scale": 1.0}
CONFIG_SPACE = {"fit_window": ("choice", [104, 156, 260, 520]), "origins": ("choice", [52, 104, 156, 208]),
                "beta_set": ("choice", [[0.0], [0.0, 0.02, 0.05], [0.0, 0.05, 0.1, 0.2]]),
                "phi_set": ("choice", [[0.8, 0.9, 0.98], [0.9, 0.98, 1.0], [0.98, 1.0]]),
                "error_model": ("choice", ["log_ratio", "additive_scaled"]),
                "interval_scale": ("float", [0.7, 1.4])}
FIT_WINDOW, ORIGINS = DEFAULT_CONFIG["fit_window"], DEFAULT_CONFIG["origins"]


def _grid(config):
    return [(a / 10, b, p) for a in range(1, 10) for b in config["beta_set"] for p in config["phi_set"]]


GRID = _grid(DEFAULT_CONFIG)
RESERVED = ("Micro", "Industry")      # P6 natural family series; never used for forecasting admission


# ------------------------------------------------------------------ model
def _series(data):
    h = data.get("history")
    if not isinstance(h, list) or not MIN_HISTORY <= len(h) <= 3000:
        raise GenomeError(f"history of {MIN_HISTORY}-3000 positive values required")
    values = [finite(v, low=1e-9, high=1e12, name="history value") for v in h]
    horizon = bounded_int(data.get("horizon", 13), low=1, high=26, name="horizon")
    levels = data.get("levels", list(LEVELS))
    if not isinstance(levels, list) or not 1 <= len(levels) <= 41:
        raise GenomeError("1-41 quantile levels required")
    levels = sorted(finite(q, low=1e-6, high=1 - 1e-6, name="level") for q in levels)
    return values, horizon, levels


def _smooth(y, alpha, beta, phi):
    """Damped-trend Holt. Returns (level, trend) after the series and one-step squared errors."""
    level, trend, sse = y[0], (y[1] - y[0]) if len(y) > 1 else 0.0, 0.0
    for v in y[1:]:
        f = level + phi * trend
        sse += (v - f) ** 2
        new_level = alpha * v + (1 - alpha) * f
        trend = beta * (new_level - level) + (1 - beta) * phi * trend
        level = new_level
    return level, trend, sse


def _path(level, trend, phi, horizon):
    out, damp = [], 0.0
    for h in range(1, horizon + 1):
        damp += phi ** h
        out.append(level + damp * trend)
    return out


def fit(y, config=DEFAULT_CONFIG):
    window = y[-config["fit_window"]:]
    best = min(_grid(config), key=lambda p: (_smooth(window, *p)[2], p))
    return best


def _holt_point(y, params, horizon, config=DEFAULT_CONFIG):
    level, trend, _ = _smooth(y[-config["fit_window"]:], *params)
    return [max(v, 1e-9) for v in _path(level, trend, params[2], horizon)]


def _theta_point(y, params_unused, horizon, config=DEFAULT_CONFIG):
    """Theta method: SES on the series plus half the OLS slope as drift (Assimakopoulos & Nikolopoulos)."""
    window = y[-config["fit_window"]:]
    n = len(window)
    tbar = (n - 1) / 2
    ybar = sum(window) / n
    slope = sum((t - tbar) * (v - ybar) for t, v in enumerate(window)) / sum((t - tbar) ** 2 for t in range(n))
    best = None
    for a in [i / 20 for i in range(1, 20)]:
        level, sse = window[0], 0.0
        for v in window[1:]:
            sse += (v - level) ** 2
            level = a * v + (1 - a) * level
        if best is None or sse < best[0]:
            best = (sse, a, level)
    _, a, level = best
    return [max(level + 0.5 * slope * (h - 1 + 1 / a), 1e-9) for h in range(1, horizon + 1)]


def _empirical_quantile(sorted_values, q):
    k = (len(sorted_values) - 1) * q
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


def _error_quantiles(y, point_fn, params, horizon, levels, config=DEFAULT_CONFIG):
    """Rolling-origin errors of the same point method, per horizon (log-ratio, or additive scaled by the
    level at the origin), widened or narrowed around the median by ``interval_scale``."""
    n = len(y)
    origins = range(max(MIN_HISTORY - 20, n - config["origins"] - horizon), n - horizon + 1)
    errors = [[] for _ in range(horizon)]
    for o in origins:
        path = point_fn(y[:o], params, horizon, config)
        for h in range(horizon):
            if config["error_model"] == "log_ratio":
                errors[h].append(math.log(y[o + h] / path[h]))
            else:
                errors[h].append((y[o + h] - path[h]) / max(y[o - 1], 1e-9))
    if min(len(e) for e in errors) < 8:
        raise GenomeError("too few rolling origins for an empirical error distribution")
    scale = config["interval_scale"]
    out = []
    for e in errors:
        raw = [_empirical_quantile(sorted(e), q) for q in levels]
        mid = _empirical_quantile(sorted(e), 0.5)
        out.append([mid + (v - mid) * scale for v in raw] if scale != 1.0 else raw)
    return out, len(errors[0])


def distribution(data, config=DEFAULT_CONFIG, point_name="holt"):
    y, horizon, levels = _series(data)
    params = fit(y, config) if point_name == "holt" else None
    point_fn = _holt_point if point_name == "holt" else _theta_point
    point = point_fn(y, params, horizon, config)
    eq, origins = _error_quantiles(y, point_fn, params, horizon, levels, config)
    if config["error_model"] == "log_ratio":
        quantiles = {f"{q:g}": [round(point[h] * math.exp(eq[h][i]), 6) for h in range(horizon)]
                     for i, q in enumerate(levels)}
    else:
        quantiles = {f"{q:g}": [round(max(point[h] + eq[h][i] * y[-1], 1e-9), 6) for h in range(horizon)]
                     for i, q in enumerate(levels)}
    return {"point": [round(v, 6) for v in point], "levels": levels, "quantiles": quantiles}, params, origins


def _distribution(data, point_name):
    return distribution(data, DEFAULT_CONFIG, point_name)


def solve_with(config, data):
    out, params, origins = distribution(data, config)
    return answer(out, {"alpha": params[0], "beta": params[1], "phi": params[2], "fit_window": config["fit_window"],
                        "rolling_origins": origins, "error_model": f"empirical {config['error_model']} quantiles "
                        "per horizon", "interval_scale": config["interval_scale"],
                        "selection": "grid minimum of in-sample one-step squared error"})


def solve(data, budget):
    return solve_with(DEFAULT_CONFIG, data)


def verify(data, output, certificate):
    y, horizon, levels = _series(data)
    p = (certificate["alpha"], certificate["beta"], certificate["phi"])
    # Independent recursion in error-correction form (algebraically equal to the smoother above).
    window = y[-int(certificate.get("fit_window", FIT_WINDOW)):]
    level, trend = window[0], window[1] - window[0]
    for v in window[1:]:
        e = v - (level + p[2] * trend)
        level, trend = level + p[2] * trend + p[0] * e, p[2] * trend + p[0] * p[1] * e
    point = [level + sum(p[2] ** j for j in range(1, h + 1)) * trend for h in range(1, horizon + 1)]
    ordered = all(output["quantiles"][f"{a:g}"][h] <= output["quantiles"][f"{b:g}"][h] + 1e-9
                  for a, b in zip(levels, levels[1:]) for h in range(horizon))
    return {"point_recomputed": all(math.isclose(max(a, 1e-9), b, rel_tol=1e-6, abs_tol=1e-6)
                                    for a, b in zip(point, output["point"])),
            "quantiles_monotone_in_level": ordered,
            "positive_and_finite": all(math.isfinite(v) and v > 0 for q in output["quantiles"].values() for v in q),
            "shape": len(output["point"]) == horizon and set(output["quantiles"]) == {f"{q:g}" for q in levels}}


# ------------------------------------------------------------------ benchmark
@lru_cache(maxsize=1)
def m4_weekly():
    with gzip.open(DATA, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def admission_series():
    return [s for s in m4_weekly()["series"] if s["category"] not in RESERVED]


def instance(seed):
    pool = admission_series()
    s = pool[(seed * 7919) % len(pool)]
    return {"history": s["train"], "horizon": 13, "levels": list(LEVELS), "series_id": s["id"]}, {"actual": s["test"]}


def score(data, truth, output):
    if not isinstance(output, dict) or "quantiles" not in output:
        return {"quality": -1e6, "category": "abstain"}
    y = data["history"]
    scale = sum(abs(a - b) for a, b in zip(y[1:], y[:-1])) / (len(y) - 1) or 1.0
    total, count = 0.0, 0
    for q in data["levels"]:
        path = output["quantiles"].get(f"{q:g}")
        if not isinstance(path, list) or len(path) != len(truth["actual"]):
            return {"quality": -1e6, "category": "wrong"}
        for f, a in zip(path, truth["actual"]):
            total += max(q * (a - f), (q - 1) * (a - f))
            count += 1
    return {"quality": -total / count / scale, "category": "correct"}


def naive_gaussian(data):
    y, horizon, levels = _series(data)
    diffs = [b - a for a, b in zip(y[:-1], y[1:])][-FIT_WINDOW:]
    sd = (sum(d * d for d in diffs) / len(diffs)) ** 0.5
    from statistics import NormalDist
    z = {q: NormalDist().inv_cdf(q) for q in levels}
    return {"point": [y[-1]] * horizon, "levels": levels,
            "quantiles": {f"{q:g}": [max(y[-1] + z[q] * sd * math.sqrt(h), 1e-9) for h in range(1, horizon + 1)]
                          for q in levels}}


def theta_empirical(data):
    return _distribution(data, "theta")[0]


# ------------------------------------------------------------------ newsvendor translation (composition stage)
def _products(data):
    products = data.get("products")
    if not isinstance(products, list) or not 1 <= len(products) <= 3:
        raise GenomeError("1-3 products per allocation (the optimisation family's 64-variable ceiling)")
    out = []
    for p in products:
        scen = p.get("scenarios")
        if not isinstance(scen, list) or not 2 <= len(scen) <= 10:
            raise GenomeError("2-10 demand scenarios per product")
        out.append({"name": str(p.get("name", "p"))[:32],
                    "scenarios": [bounded_int(int(round(finite(v, low=0, high=1e6))), low=0, high=1_000_000)
                                  for v in scen],
                    "over": bounded_int(p.get("over_cost"), low=1, high=10_000, name="over_cost"),
                    "under": bounded_int(p.get("under_cost"), low=1, high=10_000, name="under_cost")})
    capacity = bounded_int(data.get("capacity"), low=0, high=1_000_000, name="capacity")
    return out, capacity


def compile_newsvendor(data, budget):
    products, capacity = _products(data)
    variables, constraints, objective = {}, [], {}
    for i, p in enumerate(products):
        hi = max(max(p["scenarios"]), capacity)
        variables[f"q{i}"] = [0, min(hi, capacity)]
        for j, d in enumerate(p["scenarios"]):
            o, u = f"o{i}_{j}", f"u{i}_{j}"
            variables[o], variables[u] = [0, hi + d], [0, hi + d]
            constraints.append({"coefficients": {o: 1, f"q{i}": -1}, "op": ">=", "rhs": -d,
                                "requirement_id": f"over:{i}:{j}"})
            constraints.append({"coefficients": {u: 1, f"q{i}": 1}, "op": ">=", "rhs": d,
                                "requirement_id": f"under:{i}:{j}"})
            objective[o], objective[u] = p["over"], p["under"]
    constraints.append({"coefficients": {f"q{i}": 1 for i in range(len(products))}, "op": "<=", "rhs": capacity,
                        "requirement_id": "capacity"})
    if len(variables) > 64:
        return answer(None, {"variables": len(variables)}, status="ABSTAIN",
                      missing=["allocation exceeds the optimisation family's 64-variable ceiling"])
    return answer({"model": {"variables": variables, "constraints": constraints,
                             "objective": {"coefficients": objective, "sense": "min"}},
                   "decode": {f"q{i}": p["name"] for i, p in enumerate(products)}},
                  {"formulation": "sample-average approximation: min sum_s over*o + under*u, o >= q - d_s, "
                                  "u >= d_s - q, sum q <= capacity", "scenarios_per_product":
                   [len(p["scenarios"]) for p in products]})


def compile_verify(data, output, certificate):
    products, capacity = _products(data)
    model = output["model"]
    rows = {c["requirement_id"] for c in model["constraints"]}
    want = {f"{k}:{i}:{j}" for i, p in enumerate(products) for j in range(len(p["scenarios"])) for k in ("over", "under")}
    return {"one_over_and_under_row_per_scenario": want | {"capacity"} == rows,
            "capacity_row": any(c["requirement_id"] == "capacity" and c["rhs"] == capacity for c in model["constraints"]),
            "minimise": model["objective"]["sense"] == "min",
            "decode": set(output["decode"]) == {f"q{i}" for i in range(len(products))}}


def newsvendor_instance(seed):
    import random
    r = random.Random(seed)
    products = [{"name": f"p{i}", "scenarios": sorted(r.randint(50, 150) for _ in range(6)),
                 "over_cost": 2, "under_cost": r.choice((3, 6, 18))} for i in range(3)]
    data = {"products": products, "capacity": 300}
    return data, {}


def newsvendor_score(data, truth, output):
    if not isinstance(output, dict) or "model" not in output:
        return {"quality": 0.0, "category": "abstain"}
    ok = all(compile_verify(data, output, {}).values())
    return {"quality": 1.0 if ok else -1.0, "category": "correct" if ok else "wrong"}


def _genome(**kw):
    return IntelligenceGenome(source_provenance="Holt (1957); Gardner & McKenzie (1985) damped trend; empirical "
                              "rolling-origin error quantiles; Theta method (Assimakopoulos & Nikolopoulos 2000)",
                              buildability="BUILDABLE_NOW", memory_model="stateless (refits on every call)",
                              learning_rule="parameters re-selected per call; competence settles per geometry",
                              resource_profile="pure Python; ~108 grid fits of <= 260 points",
                              lineage=LINEAGE, **kw)


INTELLIGENCES = [
    Executable(
        genome=_genome(
            intelligence_id="solver.forecast.damped_trend_quantiles", version="1.0.0", family="forecast_quantile",
            layer=3, operation="forecast_distribution", epistemic_class="prediction",
            subgeometry="univariate positive time series, horizon 1-26",
            native_representation="ordered history of positive values",
            required_inputs=("history", "horizon", "levels"),
            output_contract={"point": "[h]", "levels": "[q]", "quantiles": "{q: [h]}"},
            algorithm_or_runtime="damped Holt ES, grid-selected; empirical log-ratio error quantiles per horizon",
            parameters={"grid": "alpha 0.1-0.9, beta {0,.05,.1,.2}, phi {.8,.9,.98}", "fit_window": FIT_WINDOW,
                        "rolling_origins": ORIGINS},
            composition_inputs=("history",), composition_outputs=("quantiles", "point"),
            evidence_type="forecast_distribution",
            verification_method="independent error-correction recursion of the point path; quantile monotonicity",
            confidence_semantics="empirical predictive quantiles from this model's own past errors; calibration "
                                 "is measured by pinball loss, never asserted",
            latency_profile="tens of milliseconds", known_strengths=("calibrated to the series' own error history",
                                                                     "robust damped trend"),
            known_failure_modes=("structural breaks after the history", "seasonality is not modelled",
                                 "short histories give coarse quantiles"),
            counterindications=("non-positive series", "fewer than 60 observations", "strong seasonality"),
            abstention_conditions=("too few rolling origins",),
            benchmark_suite="M4 Weekly non-Micro/Industry series; dev seeds 0-9, held-out 1000-1029",
            baseline="naive last value with Gaussian random-walk quantiles",
            competitor="Theta method with the same empirical error quantiles"),
        solve=solve, verify=verify, instance=instance, score=score, baseline=naive_gaussian,
        competitor=theta_empirical, tolerance=1e-9),
    Executable(
        genome=_genome(
            intelligence_id="solver.or.newsvendor_saa_compiler", version="1.0.0", family="newsvendor_compile",
            layer=3, operation="compile_newsvendor", epistemic_class="optimization",
            subgeometry="capacity-coupled newsvendor -> integer SAA model",
            native_representation="demand scenarios + overage/underage costs + shared capacity",
            required_inputs=("products", "capacity"),
            output_contract={"model": "optimize-family model", "decode": "{q_i: product}"},
            algorithm_or_runtime="deterministic translation (sample-average approximation)", parameters={},
            composition_inputs=("scenarios", "costs", "capacity"), composition_outputs=("model", "decode"),
            evidence_type="exact_calculation",
            verification_method="structural re-derivation of every scenario row and the capacity row",
            confidence_semantics="lossless translation of the supplied scenarios; SAA error is the forecast's",
            latency_profile="microseconds", known_strengths=("exact SAA encoding",),
            known_failure_modes=("more than 3 products x 10 scenarios exceeds the optimiser's 64 variables",),
            counterindications=("correlated multi-period inventory carry-over",),
            abstention_conditions=("> 64 model variables",),
            benchmark_suite="structural translation checks on generated scenario sets",
            baseline="none (no standalone decision)", competitor="none (no standalone decision)",
            standalone_decision=False),
        solve=compile_newsvendor, verify=compile_verify, instance=newsvendor_instance, score=newsvendor_score,
        baseline=lambda data: None, competitor=lambda data: None),
]
