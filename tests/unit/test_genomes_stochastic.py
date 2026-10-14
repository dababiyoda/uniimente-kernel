"""Layer 3 pack B IntelligenceGenomes (Monte Carlo expectation, BCa bootstrap, small MILP): contract, validation,
independent verification, abstention, scoring, determinism and dev-seed runtime.

Development seeds only (0-9); held-out admission seeds are never generated here. Coverage sweeps quoted in
comments were measured on development seeds and review seeds 3000-3999 while building, never on held-out seeds.
"""
from __future__ import annotations

import copy
import json
import math
import time

import pytest

from greg.cognition.genomes import library, stochastic
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

FAMILIES = ("mc_expectation", "bootstrap_ci", "milp_optimize")
OPS = {"mc_expectation": "mc_expectation_estimate", "bootstrap_ci": "bca_bootstrap_interval",
       "milp_optimize": "milp_integer_optimize"}
CLASSES = {"mc_expectation": "estimate", "bootstrap_ci": "estimate", "milp_optimize": "optimization"}
EVIDENCE = {"mc_expectation": "statistical_estimate", "bootstrap_ci": "statistical_estimate",
            "milp_optimize": "optimality_certificate"}
BUDGET = {"latency_s": 5.0, "compute": 100000}
DEV = tuple(range(10))
_CACHE: dict = {}


def item(family):
    return {x.genome.family: x for x in stochastic.INTELLIGENCES}[family]


def dev(family, seed=1):
    assert 0 <= seed < 10                       # never a held-out seed
    key = (family, seed)
    if key not in _CACHE:
        _CACHE[key] = item(family).instance(seed)
    data, truth = _CACHE[key]
    return copy.deepcopy(data), truth


def solved(family, seed=1):
    key = ("solved", family, seed)
    if key not in _CACHE:
        data, _ = dev(family, seed)
        _CACHE[key] = item(family).solve(data, BUDGET)
    data, truth = dev(family, seed)
    return data, truth, copy.deepcopy(_CACHE[key])


def _json_clean(value):
    if isinstance(value, float):
        assert math.isfinite(value)
    elif isinstance(value, dict):
        assert all(isinstance(k, str) for k in value)
        for v in value.values():
            _json_clean(v)
    elif isinstance(value, list):
        assert len(value) <= 1000
        for v in value:
            _json_clean(v)
    else:
        assert value is None or type(value) in (str, int, bool)


# ------------------------------------------------------------------ genome contract
def test_genomes_validate_and_are_layer_three():
    assert sorted(x.genome.family for x in stochastic.INTELLIGENCES) == sorted(FAMILIES)
    for x in stochastic.INTELLIGENCES:
        g = x.genome
        assert isinstance(g, IntelligenceGenome) and g.validate() is g
        assert g.layer == 3 and g.buildability == "BUILDABLE_NOW" and g.standalone_decision
        assert g.operation == OPS[g.family] and g.epistemic_class == CLASSES[g.family]
        assert g.evidence_type == EVIDENCE[g.family] and g.dependency == "scipy"
        assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
        assert g.authority_ceiling == "read_only" and g.consequence_limit == "read_only"
        assert g.baseline and g.competitor and g.counterindications and g.abstention_conditions
        assert callable(x.subregion) and x.tolerance >= 0 and x.competitor_deployable


def test_library_registers_pack_b_withheld_and_without_collisions():
    from greg.cognition import catalog
    families = library.executables()
    for family in FAMILIES:
        assert families[family].genome.operation == OPS[family]
        expected = (3, (OPS[family],), (CLASSES[family],), library.PROOF_CLASS, "scipy")
        assert library.catalog_families()[family] == expected
        assert catalog.initial_state(f"cognition.{family}") == "VERIFIED"      # registered, never auto-attached


def test_module_top_level_imports_no_heavy_packages():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(stochastic))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top for a in n.names}
    names |= {n.module.split(".")[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"numpy", "scipy", "networkx", "ortools", "z3"}


def test_no_authority_or_side_effect_primitives_in_module():
    import inspect
    import re
    source = inspect.getsource(stochastic)
    for forbidden in (r"(?<![\w.])open\(", r"(?<![\w.])eval\(", r"(?<![\w.])exec\(", r"\bsubprocess\b",
                      r"\bos\.", r"\bsocket\b", r"\brequests\b", r"__import__", r"\bshutil\b"):
        assert not re.search(forbidden, source), forbidden


# ------------------------------------------------------------------ solve / verify round trip
@pytest.mark.parametrize("family,seed", [(f, s) for f in FAMILIES for s in DEV])
def test_solve_returns_a_compact_json_answer_that_verifies(family, seed):
    data, truth, out = solved(family, seed)
    assert set(out) == {"output", "certificate", "status", "missing"} and out["status"] == "ANSWER"
    assert out["missing"] == []
    _json_clean(out["output"])
    _json_clean(out["certificate"])
    assert len(json.dumps(out, allow_nan=False)) < 64 * 1024
    json.dumps(data, allow_nan=False)
    checks = item(family).verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    score = item(family).score(data, truth, out["output"])
    assert score["category"] in ("correct", "wrong") and math.isfinite(score["quality"])
    if family == "milp_optimize":                  # an exact method: every dev answer is the true optimum
        assert score["category"] == "correct"


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_adapter_runs_and_checks(family):
    data, _ = dev(family, 2)
    result = library.run(family, data, {"latency_limit": 10})
    assert result["status"] == "ANSWER" and result["proof"]["evidence_type"] == EVIDENCE[family]
    checks = library.check(family, data, result["output"], result["proof"])
    assert all(checks.values()), checks


@pytest.mark.parametrize("family", FAMILIES)
def test_the_canonical_path_runs_each_genome_only_once_attached_and_creates_no_authority(family):
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    data, _ = dev(family, 1)
    request = {"problem_id": f"pack-b-{family}", "operation": OPS[family], "data": data,
               "geometry": {"latency_limit": 30}}
    assert reason(request, registry=registry)["abstention_state"] == "CAPABILITY_DEFICIT"     # withheld
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["abstention_state"] == "NONE" and r["proof_type"] == "genome_certificate"
    assert r["proof_artifact"]["evidence_type"] == EVIDENCE[family]
    assert r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" and r["authority_created"] is False


def test_answers_carry_no_authority_or_truth_claims():
    for family in FAMILIES:
        _, _, out = solved(family, 0)
        text = json.dumps(out).lower()
        assert "authority" not in text and "approve" not in text
    for family in ("mc_expectation", "bootstrap_ci"):          # an interval never claims to certify the truth
        assert solved(family, 0)[2]["certificate"]["truth_certified"] is False


# ------------------------------------------------------------------ corrupted outputs are refuted
def _corrupt(family, data, out):
    o, c = copy.deepcopy(out["output"]), copy.deepcopy(out["certificate"])
    if family == "mc_expectation":             # a consistent interval around an estimate shifted by one SE
        shift = o["std_error"]
        o["estimate"] += shift
        o["interval"] = [v + shift for v in o["interval"]]
    elif family == "bootstrap_ci":             # swap in the percentile interval: a real interval, not this one
        p = stochastic.boot_percentile(data)
        o["lower"], o["upper"] = p["lower"], p["upper"]
    else:                                      # drop one unit of a used variable, recompute the objective, keep claims
        j = next(j for j, v in enumerate(o["values"]) if v > stochastic._ip(data)[1][j])
        o["values"][j] -= 1
        o["objective"] = sum(a * b for a, b in zip(stochastic._ip(data)[4], o["values"]))
    return o, c


@pytest.mark.parametrize("family,seed", [(f, s) for f in FAMILIES for s in (0, 1, 2)])
def test_verify_refutes_a_corrupted_output(family, seed):
    data, _, out = solved(family, seed)
    o, c = _corrupt(family, data, out)
    checks = item(family).verify(data, o, c)
    assert not all(checks.values()), checks


def _leaf_mutants(value, path=()):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _leaf_mutants(v, path + (k,))
    elif isinstance(value, list):
        if value and all(not isinstance(v, (dict, list)) for v in value):
            yield path, value[:-1]
        for i, v in enumerate(value[:3]):
            yield from _leaf_mutants(v, path + (i,))
    elif type(value) is bool:
        yield path, not value
    elif isinstance(value, (int, float)):
        yield path, value * 1.37 + 1 if isinstance(value, float) else value + 1
    elif isinstance(value, str):
        yield path, value + "_x"


def _set(obj, path, value):
    for k in path[:-1]:
        obj = obj[k]
    obj[path[-1]] = value


@pytest.mark.parametrize("family", FAMILIES)
def test_every_single_leaf_corruption_of_an_answer_is_refuted(family):
    x = item(family)
    for seed in (0, 1, 3):
        data, _, out = solved(family, seed)
        survivors = []
        for path, value in _leaf_mutants(out["output"]):
            if not path:
                continue
            forged = copy.deepcopy(out["output"])
            _set(forged, path, value)
            if all(x.verify(data, forged, out["certificate"]).values()):
                survivors.append(path)
        assert not survivors, (family, seed, survivors)


@pytest.mark.parametrize("family", FAMILIES)
def test_a_verifier_refutes_rather_than_raises_on_any_certificate_leaf(family):
    # review: pilot_intercept 1e308 made mc_verify's fsum raise OverflowError, control coefficients of 1e200 made a
    # squared deviation raise; the contract is to refute, never to raise
    x = item(family)
    data, _, out = solved(family, 1)
    for path, mutated in _leaf_mutants(out["certificate"]):
        values = [mutated] + ([1e308, -1e308, 1e200, 0.0] if isinstance(mutated, float) else [])
        if isinstance(mutated, list) and mutated and all(isinstance(v, float) for v in mutated):
            values += [[1e200] * (len(mutated) + 1), [-1e308] * (len(mutated) + 1)]
        for value in values:
            forged = copy.deepcopy(out["certificate"])
            _set(forged, path, value)
            checks = x.verify(data, out["output"], forged)
            assert checks and all(type(v) is bool for v in checks.values()), (family, path, value, checks)
    if family == "mc_expectation":
        k = len(out["certificate"]["control_coefficients"])
        for leaf, value in (("pilot_intercept", 1e308), ("control_coefficients", [1e200] * k),
                            ("control_coefficients", [-1e308] * k)):
            assert not all(x.verify(data, out["output"], {**out["certificate"], leaf: value}).values()), leaf


def test_mc_verify_refutes_forged_coefficients_a_wrong_level_and_a_truth_claim():
    data, _, out = solved("mc_expectation", 1)
    v = stochastic.mc_verify
    beta = list(out["certificate"]["control_coefficients"])
    beta[0] += 0.05 * (abs(beta[0]) + 1e-3)
    checks = v(data, out["output"], {**out["certificate"], "control_coefficients": beta})
    assert checks["pilot_least_squares_normal_equations_hold"] is False
    # an interval honestly built at level 0.9 but labelled with the requested 0.95
    o = copy.deepcopy(out["output"])
    half = 1.6448536 * o["std_error"]
    o["interval"] = [o["estimate"] - half, o["estimate"] + half]
    assert v(data, o, out["certificate"])["interval_is_estimate_plus_minus_z_std_error"] is False
    checks = v(data, out["output"], {**out["certificate"], "truth_certified": True})
    assert checks["claims_no_truth_certificate"] is False
    assert v(data, out["output"], {**out["certificate"], "pilot_pairs": 64})["certificate_bound"] is False


@pytest.mark.parametrize("function", [{"family": "power_product", "powers": [3, 1]},          # odd: pairs cancel
                                      {"family": "cos_product", "frequencies": [1.0, 1.0],
                                       "phases": [math.pi / 2, math.pi / 2]},                    # odd product
                                      {"family": "exp_linear", "weights": [0.0, 0.0]},           # constant f
                                      {"family": "power_product", "powers": [2, 0]}])            # exact control fit
@pytest.mark.parametrize("coordinate", [{"distribution": "normal", "mean": 0.0, "sd": 1.0},
                                        {"distribution": "uniform", "low": -1.0, "high": 1.0}])
def test_mc_degenerate_functions_verify_and_cover(function, coordinate):
    # found while building: an odd f on a symmetric coordinate makes every antithetic pair mean rounding noise
    # (about 1e-17); tolerances scaled by |pair mean| refuted the solver's correct answer. Noise scales with |f|.
    data = {"coordinates": [coordinate, coordinate], "function": function, "evaluations": 2048, "seed": 5}
    out = stochastic.mc_solve(data, BUDGET)
    assert out["status"] == "ANSWER"
    assert all(stochastic.mc_verify(data, out["output"], out["certificate"]).values())
    lo, hi = out["output"]["interval"]
    assert lo <= stochastic.mc_truth(data)["mean"] <= hi


def test_mc_verify_refutes_a_plain_monte_carlo_answer_presented_as_the_candidate():
    data, _, out = solved("mc_expectation", 4)
    plain = stochastic.mc_plain(data)
    assert not all(stochastic.mc_verify(data, {**plain, "evaluations": data["evaluations"]},
                                        out["certificate"]).values())


def test_bootstrap_verify_refutes_a_forged_certificate_and_request_echo():
    data, _, out = solved("bootstrap_ci", 3)
    v = stochastic.boot_verify
    assert v(data, out["output"], {**out["certificate"], "acceleration": out["certificate"]["acceleration"] + 0.01})[
        "certificate_matches_recomputation"] is False
    assert v(data, dict(out["output"], statistic="mean"), out["certificate"])["request_echoed"] is False
    assert v(data, dict(out["output"], method="percentile"), out["certificate"])["request_echoed"] is False
    other = dict(data, seed=data["seed"] + 1)                         # the interval of another resample stream
    assert not all(v(other, out["output"], out["certificate"]).values())


def test_milp_verify_checks_every_row_in_exact_integer_arithmetic():
    data = {"variables": {"a": [0, 5], "b": [0, 5]},
            "constraints": [{"coefficients": {"a": 2, "b": 3}, "op": "<=", "rhs": 12}],
            "objective": {"coefficients": {"a": 3, "b": 4}, "sense": "max"}}
    out = stochastic.milp_solve(data, BUDGET)
    assert out["status"] == "ANSWER" and all(stochastic.milp_verify(data, out["output"], out["certificate"]).values())
    over = {"values": [5, 1], "objective": 19, "optimal": False, "certified_by": "none",
            "dual_bound": out["output"]["dual_bound"], "gap": abs(out["output"]["dual_bound"] - 19)}
    checks = stochastic.milp_verify(data, over, out["certificate"])      # 2*5 + 3*1 = 13 > 12 by one unit
    assert checks["every_constraint_holds"] is False and checks["integral_within_bounds"] is True
    assert stochastic.milp_verify(data, dict(out["output"], values=[2.0, 2]), out["certificate"]) == {
        "output_shape": False}


def test_milp_certificate_kinds_are_exercised_and_each_is_checked_independently():
    kinds = {solved("milp_optimize", s)[2]["output"]["certified_by"] for s in DEV}
    assert kinds == {"lp_dual", "enumeration", "none"}
    # seed 3: a 1-row knapsack whose LP bound is loose and whose box is too large to enumerate
    data, truth, out = solved("milp_optimize", 3)
    o = out["output"]
    assert o["certified_by"] == "none" and o["optimal"] is False
    assert o["gap"] == o["dual_bound"] - o["objective"] > 0 and o["objective"] == truth["optimum"]
    forged = dict(o, optimal=True, certified_by="lp_dual", gap=0)
    assert stochastic.milp_verify(data, forged, out["certificate"])["optimality_claim_certified"] is False
    forged = dict(o, optimal=True, certified_by="enumeration", gap=0)       # box above the enumeration limit
    assert stochastic.milp_verify(data, forged, out["certificate"])["optimality_claim_certified"] is False
    # an enumeration claim on a suboptimal point is refuted by the verifier's own enumeration
    data, truth, out = solved("milp_optimize", 0)
    assert out["output"]["certified_by"] == "enumeration"
    worse, _ = _corrupt("milp_optimize", data, out)
    checks = stochastic.milp_verify(data, worse, out["certificate"])
    assert checks["every_constraint_holds"] and checks["optimality_claim_certified"] is False


def test_milp_dual_bound_is_valid_against_independent_truth_and_wrong_signs_are_refused():
    for seed in DEV:
        data, truth, out = solved("milp_optimize", seed)
        sense = data["objective"]["sense"]
        bound = out["output"]["dual_bound"]
        assert (bound >= truth["optimum"]) if sense == "max" else (bound <= truth["optimum"])
    data, _, out = solved("milp_optimize", 2)                               # covering: >= rows, y <= 0
    duals = list(out["certificate"]["row_duals"])
    duals[0] = abs(duals[0]) + 1.0
    checks = stochastic.milp_verify(data, out["output"], {**out["certificate"], "row_duals": duals})
    assert checks["dual_multipliers_sign_feasible"] is False and checks["dual_bound_recomputed"] is False


# ------------------------------------------------------------------ review regressions (each failed on the old code)
def _mc_shifted(out, data, shift=0.0, se_factor=1.0):
    """The answer with its estimate moved and its standard error rescaled, the interval rebuilt to match."""
    o = copy.deepcopy(out["output"])
    o["estimate"] += shift
    o["std_error"] *= se_factor
    half = stochastic._N.inv_cdf(0.5 + data.get("level", 0.95) / 2.0) * o["std_error"]
    o["interval"] = [o["estimate"] - half, o["estimate"] + half]
    return o


@pytest.mark.parametrize("data", [
    {"coordinates": [{"distribution": "uniform", "low": 0.0, "high": 1.0}],              # u^2: the control fits exactly
     "function": {"family": "power_product", "powers": [2]}, "evaluations": 8192, "seed": 11},
    {"coordinates": [{"distribution": "normal", "mean": 0.0, "sd": 1.0}] * 2,             # constant f
     "function": {"family": "exp_linear", "weights": [0.0, 0.0]}, "evaluations": 2048, "seed": 5}])
def test_mc_tolerances_are_fractions_of_the_recomputed_standard_error(data):
    # review: the estimate tolerance scaled with |estimate| (1e-9) and the standard error's with mean |f|, so with a
    # small standard error an estimate moved ~1000 standard errors, or a standard error shrunk 1000x, verified
    out = stochastic.mc_solve(data, BUDGET)
    assert out["status"] == "ANSWER" and all(stochastic.mc_verify(data, out["output"], out["certificate"]).values())
    se = out["output"]["std_error"]
    for shift in (3 * se, -3 * se):
        checks = stochastic.mc_verify(data, _mc_shifted(out, data, shift=shift), out["certificate"])
        assert checks["estimate_is_the_main_block_adjusted_mean"] is False, checks
    for factor in (1e-3, 0.5, 2.0):
        checks = stochastic.mc_verify(data, _mc_shifted(out, data, se_factor=factor), out["certificate"])
        assert checks["std_error_recomputed"] is False, (factor, checks)
    o = copy.deepcopy(out["output"])                           # one endpoint moved by a third of a standard error
    o["interval"][0] -= se / 3
    assert stochastic.mc_verify(data, o, out["certificate"])["interval_is_estimate_plus_minus_z_std_error"] is False


def test_mc_squares_beyond_double_precision_do_not_vacate_the_normal_equations():
    # review: f = exp(50 x) near 2e156 overflowed f * f in the verifier's slack, so any control coefficient satisfied
    # the pilot's normal equations; an answer built on 50x the least-squares coefficient verified
    data = {"coordinates": [{"distribution": "normal", "mean": 7.2, "sd": 1e-6}],
            "function": {"family": "exp_linear", "weights": [50.0]}, "evaluations": 2048, "seed": 1}
    out = stochastic.mc_solve(data, BUDGET)
    assert out["status"] == "ANSWER" and all(stochastic.mc_verify(data, out["output"], out["certificate"]).values())
    import numpy as np
    m, pilot = out["certificate"]["pairs"], out["certificate"]["pilot_pairs"]
    beta = 50.0 * out["certificate"]["control_coefficients"][0]
    adjusted, fabs = [], []
    for i, (v,) in enumerate(np.random.default_rng(data["seed"]).random((m, 1)).tolist()):
        v = max(v, stochastic.MC_U_FLOOR)
        z, za = stochastic._N.inv_cdf(v), stochastic._N.inv_cdf(1.0 - v)
        f, fa = math.exp(50 * (7.2 + 1e-6 * z)), math.exp(50 * (7.2 + 1e-6 * za))
        fabs.append(0.5 * (f + fa))
        if i >= pilot:
            adjusted.append(0.5 * (f + fa) - beta * (0.5 * (z * z + za * za) - 1.0))
    est = math.fsum(adjusted) / len(adjusted)
    s = math.sqrt(math.fsum((w - est) ** 2 for w in adjusted) / (len(adjusted) - 1))
    forged = {"estimate": est, "std_error": math.hypot(s / math.sqrt(len(adjusted)),
                                                     stochastic.MC_SE_FLOOR * math.fsum(fabs) / m),
              "level": 0.95, "evaluations": 2048}
    half = stochastic._N.inv_cdf(0.975) * forged["std_error"]
    forged["interval"] = [est - half, est + half]
    checks = stochastic.mc_verify(data, forged, {**out["certificate"], "control_coefficients": [beta]})
    assert checks.get("pilot_least_squares_normal_equations_hold") is False, checks


@pytest.mark.parametrize("mean", [14.1, 14.19])                # f near e^705 and e^709.5
def test_mc_answers_are_finite_and_verify_or_unknown(mean):
    # review: every f was finite but the block mean overflowed; the solver answered estimate inf, interval [nan, inf]
    data = {"coordinates": [{"distribution": "normal", "mean": mean, "sd": 1e-6}],
            "function": {"family": "exp_linear", "weights": [50.0]}, "evaluations": 8192, "seed": 1}
    out = stochastic.mc_solve(data, BUDGET)
    json.dumps(out, allow_nan=False)
    assert out["status"] in ("ANSWER", "UNKNOWN")
    if out["status"] == "ANSWER":
        _json_clean(out["output"])
        assert all(stochastic.mc_verify(data, out["output"], out["certificate"]).values())


def test_mc_call_with_too_few_positive_payoffs_is_unknown_and_refuted():
    # review: a deep out-of-the-money call paid 0 on every draw; the solver answered [0, 0] with standard error 0,
    # its own verifier refuted it and the interval excluded the positive expectation
    data = {"coordinates": [{"distribution": "normal", "mean": 0.0, "sd": 1.0}],
            "function": {"family": "call_on_sum", "weights": [1.0], "strike": 7.0}, "evaluations": 8192, "seed": 3}
    out = stochastic.mc_solve(data, BUDGET)
    assert out["status"] == "UNKNOWN" and "rare event" in out["missing"][0]
    rare = dict(data, function={"family": "call_on_sum", "weights": [1.0], "strike": 3.4})   # a handful pay
    out = stochastic.mc_solve(rare, BUDGET)
    assert out["status"] == "UNKNOWN" and 0 < out["certificate"]["paying"] < stochastic.MC_MIN_HITS
    plain = stochastic.mc_plain(rare)                         # any answer on such draws fails the precondition
    forged = {**plain, "std_error": max(plain["std_error"], 1e-6), "evaluations": 8192}
    half = 1.959963984540054 * forged["std_error"]
    forged["interval"] = [forged["estimate"] - half, forged["estimate"] + half]
    cert = {"seed": 3, "pairs": 4096, "controls": ["z0^2-1"], "pilot_pairs": 512, "pilot_intercept": 0.0,
            "control_coefficients": [0.0], "truth_certified": False}
    assert stochastic.mc_verify(rare, forged, cert).get("event_not_rare") is False


def _plain_float_bca_certificate(data):
    """z0, acceleration and adjusted levels recomputed in plain floating point, as a forger reproducing a verifier
    would; an endpoint check must not depend on which certificate accompanies the interval."""
    import numpy as np
    x, _, level, resamples, seed, _ = stochastic._boot(data)
    n = len(x)
    theta = math.fsum(x) / n
    reps = sorted(math.fsum(x[i] for i in row) / n
                  for row in np.random.default_rng(seed).integers(0, n, (resamples, n)).tolist())
    share = (sum(r < theta for r in reps) + sum(r <= theta for r in reps)) / (2 * resamples)
    z0 = stochastic._N.inv_cdf(share)
    dev = [v - theta for v in x]
    s2 = math.fsum(u * u for u in dev)
    a = math.fsum(u ** 3 for u in dev) / (6 * s2 ** 1.5)
    zq = stochastic._N.inv_cdf((1 - level) / 2)
    return {"bias_correction_z0": z0, "acceleration": a,
            "adjusted_levels": [stochastic._N.cdf(z0 + (z0 + q) / (1 - a * (z0 + q))) for q in (zq, -zq)]}


def test_bootstrap_endpoint_tolerance_is_not_a_share_of_the_estimate():
    # review: tolerance 1e-9 (spread + |theta|) allowed about 1.0 at a sample near 1e9 whose bootstrap spread is about
    # 0.2: an interval above every observation verified with a plain-float certificate
    import random
    r = random.Random(3001)
    data = {"sample": [1e9 + round(r.uniform(0.0, 1.0), 3) for _ in range(40)], "statistic": "mean", "level": 0.9,
            "resamples": 2000, "seed": 7}
    out = stochastic.boot_solve(data, BUDGET)
    assert out["status"] == "ANSWER"
    above = max(data["sample"]) - out["output"]["lower"] + 0.01
    forged = dict(out["output"], lower=out["output"]["lower"] + above, upper=out["output"]["upper"] + above)
    for certificate in (out["certificate"], {**out["certificate"], **_plain_float_bca_certificate(data)}):
        checks = stochastic.boot_verify(data, forged, certificate)
        assert checks["lower_is_the_bca_percentile"] is False and checks["upper_is_the_bca_percentile"] is False
    assert all(stochastic.boot_verify(data, out["output"], out["certificate"]).values())
    nudged = dict(out["output"], lower=out["output"]["lower"] - 1e-3)      # a fraction of a percent of the spread
    assert stochastic.boot_verify(data, nudged, out["certificate"])["lower_is_the_bca_percentile"] is False


@pytest.mark.parametrize("offset", [1e7, 1e9])
@pytest.mark.parametrize("statistic", ["mean", "median"])
def test_bootstrap_honest_answers_verify_at_a_large_common_offset(offset, statistic):
    # review: the solver's jackknife subtracted nearly equal leave-one-out means; at offsets 1e7 and 1e9 11/20 and
    # 20/20 honest mean answers were refuted (acceleration -0.0028209 against -0.0028218)
    import random
    for k in range(3):
        r = random.Random(3000 + k)
        data = {"sample": [offset + r.lognormvariate(0.0, 1.0) for _ in range(40)], "statistic": statistic,
                "level": 0.9, "resamples": 2000, "seed": 3000 + k}
        out = stochastic.boot_solve(data, BUDGET)
        assert out["status"] == "ANSWER", out
        checks = stochastic.boot_verify(data, out["output"], out["certificate"])
        assert all(checks.values()), (offset, statistic, k, checks)


def test_bootstrap_honest_answers_on_discrete_samples_verify_or_are_unknown():
    # found while fixing the offset defect: with a few distinct non-dyadic values a replicate mean often equals the
    # estimate exactly, and floating-point sums placed it on either side (34 of 39 honest mean answers refuted);
    # identical leave-one-out medians gave the solver a rounding-noise acceleration instead of UNKNOWN
    import random
    answered = 0
    for k in range(6):
        r = random.Random(3100 + k)
        values = [round(r.uniform(0, 5), 1) for _ in range(6)]
        sample = [r.choice(values) for _ in range(r.randint(15, 60))]
        for statistic in ("mean", "median"):
            data = {"sample": sample, "statistic": statistic, "level": 0.9, "resamples": 2000, "seed": 3100 + k}
            out = stochastic.boot_solve(data, BUDGET)
            assert out["status"] in ("ANSWER", "UNKNOWN") or len(set(sample)) < stochastic.BOOT_MIN_DISTINCT, out
            if out["status"] == "ANSWER":
                answered += 1
                checks = stochastic.boot_verify(data, out["output"], out["certificate"])
                assert all(checks.values()), (k, statistic, checks)
    assert answered >= 6
    flat = {"sample": [1.1] * 5 + [2.2] * 5 + [3.3] * 10 + [4.4] * 5 + [5.5] * 5, "statistic": "median",
            "level": 0.9, "resamples": 2000, "seed": 3}                     # every leave-one-out median is 3.3
    out = stochastic.boot_solve(flat, BUDGET)
    assert out["status"] == "UNKNOWN" and "leave-one-out" in out["missing"][0]


def test_bootstrap_reproduces_scipy_bca_where_floating_point_is_not_at_issue():
    import warnings
    import numpy as np
    from scipy.stats import bootstrap
    for s in DEV:
        data, _, out = solved("bootstrap_ci", s)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = bootstrap((np.asarray(data["sample"]),), np.mean if data["statistic"] == "mean" else np.median,
                            n_resamples=data["resamples"], method="BCa", confidence_level=data["level"],
                            rng=np.random.default_rng(data["seed"]), vectorized=True)
        width = out["output"]["upper"] - out["output"]["lower"]
        assert out["output"]["lower"] == pytest.approx(float(res.confidence_interval.low), abs=1e-12 * width)
        assert out["output"]["upper"] == pytest.approx(float(res.confidence_interval.high), abs=1e-12 * width)


def test_bootstrap_abstains_on_a_sample_double_precision_cannot_resolve():
    # 20 distinct values 19 units in the last place apart: a few-ulp tolerance would be a third of the spread
    ulp = math.ulp(5e11)
    data = {"sample": [5e11 + k * ulp for k in range(20)], "statistic": "mean", "level": 0.9, "resamples": 1000,
            "seed": 3}
    out = stochastic.boot_solve(data, BUDGET)
    assert out["status"] == "ABSTAIN" and "last place" in out["missing"][0]
    forged = {"lower": 5e11 + 30 * ulp, "upper": 5e11 + 40 * ulp, "level": 0.9, "statistic": "mean",
              "estimate": 5e11 + 9 * ulp, "resamples": 1000, "method": "BCa"}
    assert stochastic.boot_verify(data, forged, {})["bootstrap_preconditions_hold"] is False


def test_bootstrap_declared_size_matches_its_work_bound():
    # review: the genome declared 15-400 observations; at the default 2000 resamples every n above 300 abstains
    import random
    genome = item("bootstrap_ci").genome
    top = stochastic.BOOT_MAX_WORK // 2000
    assert f"{stochastic.BOOT_NATIVE_MIN_N}-{top} observations" in genome.subgeometry
    r = random.Random(3010)
    for n, status in ((top, "ANSWER"), (top + 1, "ABSTAIN")):
        data = {"sample": [r.lognormvariate(0, 1) for _ in range(n)], "statistic": "mean", "seed": 3}
        assert stochastic.boot_solve(data, BUDGET)["status"] == status


def _gap_knapsack(trial):
    """A 16-binary knapsack with large, nearly proportional coefficients (box 2^16, so enumeration may certify)."""
    import random
    r = random.Random(trial)
    names = [f"x{i:02d}" for i in range(16)]
    w = [r.randint(50000, 62000) for _ in range(16)]
    v = [16 * wi + r.randint(-300, 300) for wi in w]
    return {"variables": {nm: [0, 1] for nm in names},
            "constraints": [{"coefficients": dict(zip(names, w)), "op": "<=", "rhs": int(sum(w) * r.uniform(0.3, 0.7))}],
            "objective": {"coefficients": dict(zip(names, v)), "sense": "max"}}


def test_milp_never_claims_optimality_for_an_incumbent_stopped_by_the_gap():
    # review: at HiGHS's default relative gap (1e-4) trial 3001 stopped at 6299392 with status Optimal against the
    # true 6299764, and the solver claimed 'enumeration' on that status: its own verifier, and the cortex, refuted it
    for trial in (3001, 3003, 3004):
        data = _gap_knapsack(trial)
        out = stochastic.milp_solve(data, BUDGET)
        checks = stochastic.milp_verify(data, out["output"], out["certificate"])
        assert all(checks.values()), (trial, checks)
        best = stochastic._enumerate(*stochastic._ip(data)[1:6])[0]
        assert out["output"]["objective"] == best and out["output"]["certified_by"] == "enumeration"
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    registry.set_state("cognition.milp_optimize", "ATTACHED")
    r = reason({"problem_id": "pack-b-gap", "operation": "milp_integer_optimize", "data": _gap_knapsack(3001),
                "geometry": {"latency_limit": 30}}, registry=registry)
    assert r["abstention_state"] == "NONE" and r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED"


def test_mc_genome_states_the_sobol_competitor_latency_as_measured():
    # review: the genome said scrambled Sobol needs about a third of the candidate's latency; on the harness's
    # measure (solve only) it needs several times more
    entry = next(m for m in item("mc_expectation").genome.known_failure_modes if "Sobol" in m)
    assert "third" not in entry and "times the candidate's solve latency" in entry
    x = item("mc_expectation")
    ratios = []
    for s in DEV:
        data, _ = dev("mc_expectation", s)
        times = {}
        for arm, fn in (("candidate", lambda d: x.solve(d, BUDGET)), ("competitor", x.competitor)):
            best = math.inf
            for _ in range(3):
                started = time.perf_counter()
                fn(copy.deepcopy(data))
                best = min(best, time.perf_counter() - started)
            times[arm] = best
        ratios.append(times["competitor"] / times["candidate"])
    assert sorted(ratios)[len(ratios) // 2] > 1.5, ratios


# ------------------------------------------------------------------ independent helpers and truth
def test_verifier_leave_one_out_medians_and_percentiles_match_brute_force():
    import random
    import numpy as np
    r = random.Random(3001)
    for n in (15, 16, 41, 42):
        x = [round(r.lognormvariate(0, 1), 2) for _ in range(n)]          # rounding creates ties
        brute = [float(np.median(np.delete(np.array(x), i))) for i in range(n)]
        assert stochastic._loo_medians(x) == brute
        ordered = sorted(x)
        for p in (0.0, 0.013, 0.05, 0.5, 0.95, 0.999, 1.0):
            assert stochastic._type7(ordered, p) == pytest.approx(float(np.percentile(x, 100 * p)), rel=1e-12)


@pytest.mark.parametrize("coordinate", [{"distribution": "normal", "mean": 0.4, "sd": 0.8},
                                        {"distribution": "uniform", "low": -0.7, "high": 1.3},
                                        {"distribution": "exponential", "rate": 1.7}])
@pytest.mark.parametrize("function", [{"family": "exp_linear", "weights": [0.35]},
                                      {"family": "cos_product", "frequencies": [1.3], "phases": [0.7]},
                                      {"family": "power_product", "powers": [3]}])
def test_the_analytic_truth_matches_numerical_quadrature(coordinate, function):
    from scipy import integrate, stats
    data = {"coordinates": [coordinate], "function": function, "evaluations": 2048, "seed": 1}
    kind = coordinate["distribution"]
    dist = (stats.norm(coordinate["mean"], coordinate["sd"]) if kind == "normal"
            else stats.uniform(coordinate["low"], coordinate["high"] - coordinate["low"]) if kind == "uniform"
            else stats.expon(scale=1 / coordinate["rate"]))
    f = {"exp_linear": lambda v: math.exp(0.35 * v), "cos_product": lambda v: math.cos(1.3 * v + 0.7),
         "power_product": lambda v: v ** 3}[function["family"]]
    lo, hi = max(dist.support()[0], dist.ppf(1e-16)), min(dist.support()[1], dist.isf(1e-16))   # tails negligible
    m1 = integrate.quad(lambda v: f(v) * dist.pdf(v), lo, hi, limit=200)[0]
    m2 = integrate.quad(lambda v: f(v) ** 2 * dist.pdf(v), lo, hi, limit=200)[0]
    truth = stochastic.mc_truth(data)
    assert truth["mean"] == pytest.approx(m1, rel=1e-7, abs=1e-9)
    assert truth["sd"] == pytest.approx(math.sqrt(m2 - m1 * m1), rel=1e-6)


@pytest.mark.parametrize("family", ["call_on_sum", "indicator_sum"])
def test_the_analytic_truth_of_a_sum_family_matches_quadrature(family):
    from scipy import integrate, stats
    coords = [{"distribution": "normal", "mean": 0.3, "sd": 0.9}, {"distribution": "normal", "mean": -0.2, "sd": 0.5}]
    fn = {"family": family, "weights": [0.7, 0.4], ("strike" if family == "call_on_sum" else "threshold"): 0.25}
    data = {"coordinates": coords, "function": fn, "evaluations": 2048, "seed": 1}
    mu, sd = 0.7 * 0.3 + 0.4 * -0.2, math.hypot(0.7 * 0.9, 0.4 * 0.5)
    g = (lambda s: max(s - 0.25, 0.0)) if family == "call_on_sum" else (lambda s: float(s > 0.25))
    dist = stats.norm(mu, sd)
    m1 = integrate.quad(lambda s: g(s) * dist.pdf(s), -12, 12, points=[0.25], limit=200)[0]
    m2 = integrate.quad(lambda s: g(s) ** 2 * dist.pdf(s), -12, 12, points=[0.25], limit=200)[0]
    truth = stochastic.mc_truth(data)
    assert truth["mean"] == pytest.approx(m1, rel=1e-7)
    assert truth["sd"] == pytest.approx(math.sqrt(m2 - m1 * m1), rel=1e-6)


def test_milp_truth_is_independent_of_the_solver():
    import inspect
    for fn in (stochastic._knapsack_optimum, stochastic._cover_optimum, stochastic.milp_instance):
        source = inspect.getsource(fn)
        assert "milp(" not in source and "milp_solve" not in source and "linprog" not in source


# ------------------------------------------------------------------ invalid input
_MC = {"coordinates": [{"distribution": "normal", "mean": 0.0, "sd": 1.0},
                       {"distribution": "uniform", "low": 0.0, "high": 1.0}],
       "function": {"family": "exp_linear", "weights": [0.3, 0.5]}, "evaluations": 4096, "seed": 7, "level": 0.95}
_BOOT = {"sample": [0.3, 1.2, 0.8, 2.5, 0.1, 0.9, 1.7, 0.4, 3.9, 1.1, 0.6, 0.2, 1.4, 2.2, 0.7, 5.1, 0.5, 1.0],
         "statistic": "median", "level": 0.9, "resamples": 1000, "seed": 3}
_IP = {"variables": {"a": [0, 3], "b": [0, 2]},
       "constraints": [{"coefficients": {"a": 2, "b": 3}, "op": "<=", "rhs": 7}],
       "objective": {"coefficients": {"a": 3, "b": 4}, "sense": "max"}}

INVALID = {
    "mc_expectation": [
        "not an object", dict(_MC, coordinates=[]),
        dict(_MC, coordinates=[{"distribution": "cauchy", "scale": 1.0}, _MC["coordinates"][1]]),
        dict(_MC, coordinates=[_MC["coordinates"][0], {"distribution": "uniform", "low": 1.0, "high": 1.0}]),
        dict(_MC, coordinates=[{"distribution": "normal", "mean": float("nan"), "sd": 1.0}, _MC["coordinates"][1]]),
        dict(_MC, function={"family": "sinc", "weights": [1.0, 1.0]}),
        dict(_MC, function={"family": "exp_linear", "weights": [0.3]}),
        dict(_MC, function={"family": "power_product", "powers": [0, 0]}),
        dict(_MC, function={"family": "call_on_sum", "weights": [1.0, 1.0]}),
        dict(_MC, evaluations=4097), dict(_MC, level=0.2), dict(_MC, seed=-1)],
    "bootstrap_ci": [
        "not an object", dict(_BOOT, sample=[1.0]), dict(_BOOT, sample=_BOOT["sample"][:-1] + ["x"]),
        dict(_BOOT, statistic="mode"), dict(_BOOT, level=1.5), dict(_BOOT, independent="yes"),
        dict(_BOOT, resamples=10), dict(_BOOT, sample=_BOOT["sample"][:-1] + [float("inf")])],
    "milp_optimize": [
        "not an object", dict(_IP, variables=[["a", 0, 3]]), dict(_IP, variables={"a": [3, 0], "b": [0, 2]}),
        dict(_IP, constraints=[{"coefficients": {"a": 1.5, "b": 3}, "op": "<=", "rhs": 7}]),
        dict(_IP, constraints=[{"coefficients": {"a": 2, "c": 3}, "op": "<=", "rhs": 7}]),
        dict(_IP, constraints=[{"coefficients": {"a": 2, "b": 3}, "op": "<", "rhs": 7}]),
        dict(_IP, constraints=[{"coefficients": {"a": 0}, "op": "<=", "rhs": 7}]),
        dict(_IP, constraints=[{"coefficients": {"a": True, "b": 3}, "op": "<=", "rhs": 7}]),
        dict(_IP, objective={"coefficients": {"a": 3}, "sense": "maximize"}),
        dict(_IP, variables={"a": [0, 10 ** 7], "b": [0, 2]})],
}


@pytest.mark.parametrize("family", FAMILIES)
def test_invalid_input_raises_genome_error(family):
    for data in INVALID[family]:
        with pytest.raises(GenomeError):
            item(family).solve(copy.deepcopy(data), BUDGET)


@pytest.mark.parametrize("family", FAMILIES)
def test_invalid_input_raises_genome_error_in_verify_too(family):
    for data in INVALID[family]:
        with pytest.raises(GenomeError):
            item(family).verify(copy.deepcopy(data), {}, {})


@pytest.mark.parametrize("family", FAMILIES)
def test_verify_does_not_crash_on_a_malformed_output_or_certificate(family):
    data, _, out = solved(family, 1)
    for output in (None, [], {}, "x", {**out["output"], "extra": 1}):
        assert not all(item(family).verify(data, output, out["certificate"]).values())
    for certificate in (None, [], "x", {}):
        assert not all(item(family).verify(data, out["output"], certificate).values())


# ------------------------------------------------------------------ abstention
ABSTAIN = {
    "mc_expectation": [
        dict(_MC, coordinates=[{"distribution": "normal", "mean": 0.0, "sd": 1.0}] * 9,
             function={"family": "exp_linear", "weights": [0.1] * 9}),                     # over the native dimension
        dict(_MC, evaluations=512), dict(_MC, evaluations=20000),                          # outside native budgets
        dict(_MC, coordinates=[{"distribution": "exponential", "rate": 1.0}, _MC["coordinates"][1]],
             function={"family": "exp_linear", "weights": [0.3, 0.5]})],                   # 4w >= rate
    "bootstrap_ci": [dict(_BOOT, independent=False), dict(_BOOT, sample=_BOOT["sample"][:12]),
                     dict(_BOOT, resamples=500), dict(_BOOT, sample=[1.0, 2.0, 3.0, 4.0] * 5),
                     dict(_BOOT, sample=[float(v) for v in range(400)], resamples=2000)],
    "milp_optimize": [{"variables": {f"x{i:03d}": [0, 1] for i in range(151)},
                       "constraints": [{"coefficients": {"x000": 1}, "op": "<=", "rhs": 1}],
                       "objective": {"coefficients": {"x000": 1}, "sense": "max"}}],
}


@pytest.mark.parametrize("family", FAMILIES)
def test_abstains_outside_native_competence(family):
    for data in ABSTAIN[family]:
        out = item(family).solve(copy.deepcopy(data), BUDGET)
        assert out["status"] == "ABSTAIN" and out["output"] is None and out["missing"], (family, out)
        _json_clean(out["certificate"])


def test_unknown_on_rare_events_and_infeasible_models():
    rare = dict(_MC, coordinates=[{"distribution": "normal", "mean": 0.0, "sd": 1.0}],
                function={"family": "indicator_sum", "weights": [1.0], "threshold": 4.5})
    out = stochastic.mc_solve(rare, BUDGET)
    assert out["status"] == "UNKNOWN" and "rare event" in out["missing"][0]
    infeasible = dict(_IP, constraints=[{"coefficients": {"a": 2, "b": 3}, "op": ">=", "rhs": 99}])
    out = stochastic.milp_solve(infeasible, BUDGET)
    assert out["status"] == "UNKNOWN" and "not independently certified" in out["missing"][0]
    for data in (rare, infeasible):
        family = "mc_expectation" if data is rare else "milp_optimize"
        assert item(family).score(data, {"mean": 0.0, "sd": 1.0, "optimum": 0}, None)["category"] == "abstain"


# ------------------------------------------------------------------ scoring
def _wrong_output(family, data, truth, out):
    o = copy.deepcopy(out["output"])
    if family == "mc_expectation":            # an interval that excludes the truth
        o["estimate"] = truth["mean"] + 10 * truth["sd"]
        o["interval"] = [o["estimate"] - 1e-6, o["estimate"] + 1e-6]
    elif family == "bootstrap_ci":
        o["lower"], o["upper"] = 2.0 * truth["parameter"], 2.1 * truth["parameter"]
    else:                                     # a false optimality claim on a feasible, suboptimal point
        o = _corrupt(family, data, out)[0]
    return o


@pytest.mark.parametrize("family", FAMILIES)
def test_score_categories(family):
    x = item(family)
    seed = next(s for s in DEV if x.score(*dev(family, s), solved(family, s)[2]["output"])["category"] == "correct")
    data, truth, out = solved(family, seed)
    correct = x.score(data, truth, out["output"])
    abstain = x.score(data, truth, None)
    wrong = x.score(data, truth, _wrong_output(family, data, truth, out))
    assert correct["category"] == "correct" and abstain["category"] == "abstain" and wrong["category"] == "wrong"
    assert wrong["quality"] < correct["quality"] and abstain["quality"] < correct["quality"]


def test_milp_scores_infeasible_points_and_false_claims_as_wrong():
    data, truth, out = solved("milp_optimize", 1)
    o = copy.deepcopy(out["output"])
    o["values"] = [1] * len(o["values"])                               # every pair assigned: infeasible
    assert stochastic.milp_score(data, truth, o) == {"quality": -1.0, "category": "wrong"}
    assert stochastic.milp_score(data, truth, dict(out["output"], objective=out["output"]["objective"] + 1))[
        "category"] == "wrong"


def test_candidates_against_baselines_on_dev_seeds():
    """Development-seed comparison, not admission evidence. Monte Carlo: the candidate's standardised error is
    below the 1000-evaluation baseline's on most seeds. MILP: exact on every seed, the baseline is not."""
    mc = item("mc_expectation")
    better = 0
    for s in DEV:
        data, truth, out = solved("mc_expectation", s)
        better += mc.score(data, truth, out["output"])["quality"] > mc.score(data, truth, mc.baseline(data))["quality"]
    assert better >= 6
    ip = item("milp_optimize")
    for s in DEV:
        data, truth, out = solved("milp_optimize", s)
        assert ip.score(data, truth, out["output"])["quality"] >= ip.score(data, truth, ip.baseline(data))["quality"]
        assert ip.score(data, truth, ip.competitor(data))["category"] == "correct"


def test_bca_coverage_sweep_is_reported_not_tuned():
    """Coverage of the true parameter at level 0.9 (fraction of intervals covering it):

    development seeds 0-9 (10 instances): BCa 0.70, percentile 0.70, normal approximation 0.80.
    review seeds 3000-3299 (300 instances), measured while building:
        all             BCa 0.873  percentile 0.873  normal 0.910   (median relative width 0.334 / 0.327 / 0.383)
        lognormal mean  0.880 / 0.860 / 0.840     lognormal median    0.860 / 0.860 / 1.000
        exponential mean 0.900 / 0.940 / 0.940    exponential median  0.920 / 0.920 / 0.980
        Pareto mean     0.760 / 0.740 / 0.740     Pareto median       0.920 / 0.920 / 0.960
    BCa undercovers the mean of heavy right tails (Pareto, tail index 2.2-4.5) at n 15-120, as its genome
    declares. Monte Carlo candidate on review seeds 3000-3599 (600 instances, level 0.95): coverage 0.942,
    mean squared standardised error 1.00. These numbers are recorded here, not asserted as thresholds; the test
    only checks that the sweep runs, that every BCa answer verifies and that each coverage is a proportion."""
    x = item("bootstrap_ci")
    covered = {"bca": 0, "percentile": 0, "normal": 0}
    for s in DEV:
        data, truth, out = solved("bootstrap_ci", s)
        assert all(x.verify(data, out["output"], out["certificate"]).values())
        for arm, o in (("bca", out["output"]), ("percentile", x.competitor(data)), ("normal", x.baseline(data))):
            covered[arm] += x.score(data, truth, o)["category"] == "correct"
    assert all(0.0 <= k / len(DEV) <= 1.0 for k in covered.values())


# ------------------------------------------------------------------ determinism and runtime
@pytest.mark.parametrize("family", FAMILIES)
def test_instances_and_solves_are_deterministic(family):
    first, _ = item(family).instance(4)
    again, _ = item(family).instance(4)
    assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)
    data, _, out = solved(family, 4)
    assert item(family).solve(copy.deepcopy(data), BUDGET) == out


@pytest.mark.parametrize("family", FAMILIES)
def test_dev_seeds_run_within_budget(family):
    x = item(family)
    for seed in DEV:
        data, _ = dev(family, seed)
        started = time.perf_counter()
        out = x.solve(copy.deepcopy(data), BUDGET)
        assert time.perf_counter() - started < 2.0, (family, seed)
        started = time.perf_counter()
        assert all(x.verify(data, out["output"], out["certificate"]).values())
        assert time.perf_counter() - started < 3.0, (family, seed)
