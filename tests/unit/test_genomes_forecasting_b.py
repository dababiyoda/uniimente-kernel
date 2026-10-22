"""Forecasting batch B genomes (judgmental forecast pooling, scenario fans by scenario reduction): contract, withheld
registration, canonical path, Competency Compiler reachability, independent verification, refutation of corrupted
answers and forged certificates, invalid input, abstention and scoring.

Development seeds 0-9 only; held-out admission seeds are never generated here.
"""
from __future__ import annotations

import copy
import json
import math

import pytest

from greg.cognition import catalog
from greg.cognition.genomes import forecasting_b as fb
from greg.cognition.genomes import library
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

ITEMS = {x.genome.family: x for x in fb.INTELLIGENCES}
FAMILIES = tuple(sorted(ITEMS))
SPEC = {  # family: (layer, operation, epistemic class, evidence type, dependency)
    "forecast_judgment_pool": (5, "pool_judgmental_forecasts", "prediction", "forecast_distribution", None),
    "forecast_scenarios": (3, "scenario_fan_forecast", "prediction", "forecast_distribution", "scipy"),
    "forecast_recalibration": (3, "recalibrate_probabilities", "prediction", "forecast_distribution", None),
}
QUICK = {"forecast_judgment_pool": (0, 1, 2, 3, 4, 5), "forecast_scenarios": (0, 1, 2, 3),
         "forecast_recalibration": (0, 1, 2, 3)}
BUDGET = {"latency_s": 8.0, "compute": 100000}
_CACHE: dict = {}


def dev(family, seed):
    assert 0 <= seed < 10                                      # never a held-out seed
    key = (family, seed)
    if key not in _CACHE:
        _CACHE[key] = ITEMS[family].instance(seed)
    data, truth = _CACHE[key]
    return copy.deepcopy(data), truth


def solved(family, seed):
    key = ("solved", family, seed)
    if key not in _CACHE:
        data, _ = dev(family, seed)
        _CACHE[key] = ITEMS[family].solve(data, BUDGET)
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
        for v in value:
            _json_clean(v)
    else:
        assert value is None or isinstance(value, (str, int, bool))


def _all(family, data, output, cert):
    return all(ITEMS[family].verify(data, output, cert).values())


# ------------------------------------------------------------------ genome contract and registration
def test_genomes_validate_with_declared_identity():
    assert set(FAMILIES) == set(SPEC)
    for family, x in ITEMS.items():
        g = x.genome
        assert isinstance(g, IntelligenceGenome) and g.validate() is g
        assert (g.layer, g.operation, g.epistemic_class, g.evidence_type, g.dependency) == SPEC[family]
        assert g.buildability == "BUILDABLE_NOW" and g.standalone_decision and g.version == "1.0.0"
        assert g.authority_ceiling == g.consequence_limit == "read_only"
        assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
        assert g.known_failure_modes and g.counterindications and g.abstention_conditions
        assert g.baseline and g.competitor and x.subregion is not None and x.competitor_deployable
        assert "seeds 0-9 dev" in g.benchmark_suite
    assert any("shared information" in m for m in ITEMS["forecast_judgment_pool"].genome.known_failure_modes)


def test_registered_in_the_one_catalog_and_withheld():
    families = library.executables()
    for family in FAMILIES:
        assert families[family] is ITEMS[family]
        g = ITEMS[family].genome
        assert catalog.FAMILIES[family] == (g.layer, (g.operation,), (g.epistemic_class,), "genome_certificate",
                                            g.dependency)
        assert catalog.initial_state(f"cognition.{family}") == "VERIFIED"      # registered, never auto-attached


def test_module_imports_no_heavy_package_at_top_level():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(fb))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top for a in n.names} | {
        n.module.split(".")[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"numpy", "scipy", "networkx", "ortools", "z3"}


def test_benchmarks_are_synthetic_and_never_read_the_m4_data(monkeypatch):
    from greg.cognition.genomes import forecasting

    def refuse():
        raise AssertionError("the M4 data must not be read by forecasting_b")
    monkeypatch.setattr(forecasting, "m4_weekly", refuse)
    for family in FAMILIES:
        a, _ = ITEMS[family].instance(1)
        b, _ = ITEMS[family].instance(1)
        assert a == b                                           # deterministic given the seed


# ------------------------------------------------------------------ solve / verify on development seeds
@pytest.mark.parametrize("family,seed", [(f, s) for f in FAMILIES for s in QUICK[f]])
def test_solve_answers_compactly_and_its_answer_verifies(family, seed):
    data, truth, out = solved(family, seed)
    assert out["status"] == "ANSWER", out["missing"]
    _json_clean(out["output"])
    _json_clean(out["certificate"])
    assert len(json.dumps(out, allow_nan=False)) < 64 * 1024
    json.dumps(data, allow_nan=False)
    checks = ITEMS[family].verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    assert ITEMS[family].score(data, truth, out["output"])["category"] == "correct"
    again = ITEMS[family].solve(copy.deepcopy(data), BUDGET)
    assert again == out                                         # deterministic


@pytest.mark.parametrize("family", FAMILIES)
def test_arms_answer_in_the_scored_contract(family):
    data, truth = dev(family, QUICK[family][0])
    for arm in (ITEMS[family].baseline, ITEMS[family].competitor):
        assert ITEMS[family].score(data, truth, arm(data))["category"] == "correct"
    assert ITEMS[family].score(data, truth, None)["category"] == "abstain"


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_path_withholds_until_attached_and_creates_no_authority(family):
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    data, truth = dev(family, QUICK[family][0])
    request = {"problem_id": f"forecast-b-{family}", "operation": SPEC[family][1], "data": data,
               "geometry": {"latency_limit": 30}}
    assert reason(request, registry=registry)["abstention_state"] == "CAPABILITY_DEFICIT"
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["abstention_state"] == "NONE" and r["proof_type"] == "genome_certificate"
    assert r["proof_artifact"]["evidence_type"] == SPEC[family][3]
    assert r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" and r["authority_created"] is False
    assert ITEMS[family].score(data, truth, r["output"])["category"] == "correct"


@pytest.mark.parametrize("family", FAMILIES)
def test_the_competency_compiler_reaches_the_family_by_its_inputs(family, tmp_path, monkeypatch):
    """Evaluation only: an in-memory attach (no body, journal or founder pin) and an empty evidence index."""
    from greg.cognition import compiler
    from greg.cognition.cortex import reason, registry_view
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")
    data, truth = dev(family, QUICK[family][0])
    cls = SPEC[family][2]
    request = {"problem_id": f"forecast-b-compile-{family}", "compile": {"geometry": {"geometry": cls}, "data": data}}
    registry = registry_view()
    withheld = reason(request, registry=registry)
    assert withheld["state"] == "CAPABILITY_DEFICIT"
    assert withheld["withheld_best_fit"]["method"] == f"cognition.{family}"
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == f"cognition.{family}"
    assert r["methods_considered"] == [f"cognition.{family}"]
    assert r["derived_geometry"]["fits_by_inputs"] == [cls] and r["authority_created"] is False
    assert ITEMS[family].score(data, truth, r["result"])["category"] == "correct"


# ------------------------------------------------------------------ judgment pool: independent verification
def _pool_corruptions(o, cert):
    p, w, a = o["probabilities"], o["weights"], o["extremization"]
    shifted = [min(v + 0.01, 0.999) for v in p]
    swapped_w = w[::-1] if w != w[::-1] else [w[0] + 0.01] + [v - 0.01 / (len(w) - 1) for v in w[1:]]
    return {
        "one_probability_moved": ({**o, "probabilities": [p[0] + 1e-3 * (1 if p[0] < 0.5 else -1)] + p[1:]}, cert),
        "all_probabilities_shifted": ({**o, "probabilities": shifted}, cert),
        "probability_out_of_range": ({**o, "probabilities": [1.5] + p[1:]}, cert),
        "probabilities_truncated": ({**o, "probabilities": p[:-1]}, cert),
        "weights_permuted": ({**o, "weights": swapped_w}, cert),
        "equal_weights_claimed": ({**o, "weights": [1 / len(w)] * len(w)}, cert),
        "extremization_moved": ({**o, "extremization": a * 1.1}, cert),
        "extremization_out_of_bounds": ({**o, "extremization": 5.0}, cert),
        "nan_probability": ({**o, "probabilities": [float("nan")] + p[1:]}, cert),
        "unpooled_mean_claimed": ({**o, "probabilities": [0.5] * len(p)}, cert),
    }


@pytest.mark.parametrize("seed", QUICK["forecast_judgment_pool"])
def test_pool_verifier_rejects_every_corruption(seed):
    data, truth, out = solved("forecast_judgment_pool", seed)
    o, cert = out["output"], out["certificate"]
    assert _all("forecast_judgment_pool", data, o, cert)
    for name, (bad, c) in _pool_corruptions(o, cert).items():
        assert not _all("forecast_judgment_pool", data, bad, c), name


def test_pool_alpha_is_the_history_maximum_likelihood():
    data, _, out = solved("forecast_judgment_pool", 1)
    hist, outcomes, _, n = fb._panel(data)
    w = out["output"]["weights"]
    x = [sum(w[i] * fb._logit(r[i]) for i in range(n)) for r in hist]

    def ll(a):
        return sum(y * math.log(fb._sigmoid(a * v)) + (1 - y) * math.log(1 - fb._sigmoid(a * v))
                   for v, y in zip(x, outcomes))
    a = out["output"]["extremization"]
    assert all(ll(a) >= ll(b) - 1e-9 for b in (0.25, 0.5, 1.0, a * 0.9, a * 1.1, 2.0, 4.0))


def test_pool_weights_shrink_to_equal_on_a_short_record_and_follow_skill():
    data, _, out = solved("forecast_judgment_pool", 2)
    hist, outcomes, _, n = fb._panel(data)
    w, brier, skill, lam = fb._weights(hist, outcomes, n)
    assert lam == len(hist) / (len(hist) + fb.JP_SHRINK_T0)
    assert all(v >= (1 - lam) / n - 1e-15 for v in w)
    order = sorted(range(n), key=lambda i: brier[i])
    assert w[order[0]] >= w[order[-1]]
    assert len(set(outcomes[:12])) == 2
    ws, _, _, lam_short = fb._weights(data["history_forecasts"][:12], outcomes[:12], n)
    assert lam_short == 12 / (12 + fb.JP_SHRINK_T0) < lam                 # a short record leans on equal weights
    assert all(v >= (1 - lam_short) / n - 1e-15 for v in ws)


def test_pool_extremization_is_fitted_not_fixed_across_regimes():
    alphas = {}
    for seed in range(6):
        data, truth, out = solved("forecast_judgment_pool", seed)
        alphas.setdefault(truth["regime"], []).append(out["output"]["extremization"])
    assert set(alphas) == set(fb.JP_REGIMES)
    assert min(alphas["diverse"] + alphas["clustered"]) > 1.0     # diverse information: the record asks for more
    assert len({round(a, 6) for v in alphas.values() for a in v}) == 6


def test_pool_abstains_without_an_identifiable_record():
    data, _ = dev("forecast_judgment_pool", 0)
    short = {**data, "history_forecasts": data["history_forecasts"][:5],
             "history_outcomes": data["history_outcomes"][:5]}
    assert fb.pool_solve(short, BUDGET)["status"] == "ABSTAIN"
    one = {**data, "history_outcomes": [1] * len(data["history_outcomes"])}
    assert fb.pool_solve(one, BUDGET)["status"] == "ABSTAIN"
    # a verifier facing a one-outcome record cannot confirm weights from skill
    assert not all(fb.pool_verify(one, {"probabilities": [0.5] * len(data["forecasts"]),
                                        "weights": [1 / len(data["forecasts"][0])] * len(data["forecasts"][0]),
                                        "extremization": 1.0}, {}).values())


def test_pool_competitors_and_score():
    data, truth = dev("forecast_judgment_pool", 3)
    med = fb.pool_median(data)["probabilities"]
    assert med[0] == sorted(data["forecasts"][0])[len(data["forecasts"][0]) // 2] or len(data["forecasts"][0]) % 2 == 0
    best = fb.pool_best_single(data)["probabilities"]
    assert any(best == [r[i] for r in data["forecasts"]] for i in range(len(data["forecasts"][0])))
    perfect = {"probabilities": [float(y) for y in truth["outcomes"]]}
    assert fb.pool_score(data, truth, perfect)["quality"] == 0.0
    assert fb.pool_score(data, truth, {"probabilities": [0.5]})["category"] == "wrong"


# ------------------------------------------------------------------ scenarios: independent verification
def _scenario_corruptions(o, cert):
    sc, w, cov = o["scenarios"], o["weights"], o["coverage"]
    moved = [list(s) for s in sc]
    moved[0][-1] += 0.01
    swapped = list(w)
    swapped[0], swapped[-1] = swapped[-1], swapped[0]
    if swapped == w:
        swapped = [w[0] + 1e-3, w[1] - 1e-3] + w[2:]
    p = cert["parameters"]
    bumped = {k: (v * 1.01 if isinstance(v, float) else v) for k, v in p.items()}
    if "c" in p:
        bumped = {**p, "c": [p["c"][0] + 0.01, p["c"][1]]}
    return {
        "scenario_path_moved": ({**o, "scenarios": moved}, cert),
        "weights_swapped": ({**o, "weights": swapped}, cert),
        "equal_weights_claimed": ({**o, "weights": [1 / len(w)] * len(w)}, cert),
        "weights_not_summing_to_one": ({**o, "weights": [v * 1.01 for v in w]}, cert),
        "coverage_overstated": ({**o, "coverage": [min(c + 0.05, 1.0) if c < 1 else c - 0.05 for c in cov]}, cert),
        "distance_understated": (o, {**cert, "kantorovich_distance": cert["kantorovich_distance"] * 0.9}),
        "other_simulated_path_index": (o, {**cert, "selected_indices": [
            (cert["selected_indices"][0] + 1) % cert["n_paths"]] + cert["selected_indices"][1:]}
            if (cert["selected_indices"][0] + 1) % cert["n_paths"] not in cert["selected_indices"] else
            {**cert, "selected_indices": [cert["n_paths"] - 1] + cert["selected_indices"][1:]}),
        "parameters_changed": (o, {**cert, "parameters": bumped}),
        "log_likelihood_forged": (o, {**cert, "history_log_likelihood": cert["history_log_likelihood"] + 1.0}),
        "stream_seed_forged": (o, {**cert, "stream_seed": cert["stream_seed"] + 1}),
        "scenario_dropped": ({**o, "scenarios": sc[:-1], "weights": w[:-1]}, cert),
    }


@pytest.mark.parametrize("seed", QUICK["forecast_scenarios"][:2])
def test_scenario_verifier_rejects_every_corruption(seed):
    data, truth, out = solved("forecast_scenarios", seed)
    o, cert = out["output"], out["certificate"]
    assert _all("forecast_scenarios", data, o, cert)
    for name, (bad, c) in _scenario_corruptions(o, cert).items():
        assert not _all("forecast_scenarios", data, bad, c), name


@pytest.mark.parametrize("seed", QUICK["forecast_scenarios"])
def test_transport_lp_equals_the_fast_forward_distance_and_beats_random_selection(seed):
    import numpy as np
    data, _, out = solved("forecast_scenarios", seed)
    cert = out["certificate"]
    model, y, h, k, paths = fb._scenario_input(data)
    sims = fb._verify_paths(model, cert["parameters"], y[-1], h, paths, cert["stream_seed"])
    solver_sims = np.asarray(fb._simulate(model, cert["parameters"], y[-1], h, paths, cert["stream_seed"]))
    assert np.allclose(sims, solver_sims, rtol=1e-12, atol=1e-9)      # two recursions, one declared stream
    lp = fb._transport_distance(sims, out["output"]["scenarios"], out["output"]["weights"])
    assert lp == pytest.approx(cert["kantorovich_distance"], rel=1e-6)
    # an unselected K-subset (the first K simulated paths, nearest weights) is further away on these dev seeds; greedy
    # selection is a heuristic, so this is a measured property of these seeds, not a theorem
    rand = list(range(k))
    c = np.linalg.norm(sims[:, None, :] - sims[None, rand, :], axis=2)
    assert float(c.min(axis=1).mean()) > cert["kantorovich_distance"]


def test_fast_forward_on_a_tiny_set_is_the_exhaustive_optimum_for_k_1():
    import itertools
    import numpy as np
    pts = [[0.0, 0.0], [1.0, 0.0], [0.0, 3.0], [5.0, 5.0], [1.0, 1.0]]
    idx, w, d = fb.fast_forward(pts, 1)
    x = np.asarray(pts)
    costs = [float(np.linalg.norm(x - x[j], axis=1).mean()) for j in range(len(pts))]
    assert idx == [int(np.argmin(costs))] and d == pytest.approx(min(costs)) and w == [1.0]
    idx2, w2, d2 = fb.fast_forward(pts, 2)
    best2 = min(float(np.linalg.norm(x[:, None] - x[list(s)][None], axis=2).min(axis=1).mean())
                for s in itertools.combinations(range(len(pts)), 2))
    assert d2 >= best2 - 1e-12 and sum(w2) == pytest.approx(1.0)


def test_scenario_fits_recover_the_generating_process_on_dev_seeds():
    data, truth = dev("forecast_scenarios", 0)                          # regime_ar
    p, _ = fb._fit(data["model"], data["history"])
    tp = truth["true_parameters"]
    assert p["sd"][0] < p["sd"][1] and abs(p["sd"][0] - tp["sd"][0]) < 0.2 * tp["sd"][0]
    data, truth = dev("forecast_scenarios", 9)                          # jump_drift
    p, _ = fb._fit(data["model"], data["history"])
    tp = truth["true_parameters"]
    assert p["jump_prob"] < 0.5 and abs(p["mu1"] - (tp["mu"] + tp["jump_mean"])) < 1.0


def test_scenario_abstains_below_the_compute_budget_and_refuses_bad_input():
    data, _ = dev("forecast_scenarios", 1)
    assert fb.scenario_solve(data, {"latency_s": 1, "compute": 10})["status"] == "ABSTAIN"
    for bad in ({**data, "model": "garch"}, {**data, "history": data["history"][:10]},
                {**data, "scenarios": 1}, {**data, "horizon": 0}, {**data, "history": ["x"] * 60},
                {**data, "n_paths": 100, "scenarios": 200}):
        with pytest.raises(GenomeError):
            fb.scenario_solve(bad, BUDGET)


def test_scenario_score_rewards_the_true_distribution():
    data, truth = dev("forecast_scenarios", 2)
    futures = truth["futures"]
    good = {"scenarios": futures[1:9], "weights": [1 / 8] * 8}
    flat = {"scenarios": [[data["history"][-1] + 100.0] * data["horizon"]] * 8, "weights": [1 / 8] * 8}
    assert fb.scenario_score(data, truth, good)["quality"] > fb.scenario_score(data, truth, flat)["quality"]
    assert fb.scenario_score(data, truth, {"scenarios": futures[:2], "weights": [0.7, 0.7]})["category"] == "wrong"


# ------------------------------------------------------------------ invalid input is refused, never crashes
@pytest.mark.parametrize("bad", [
    {"history_forecasts": [[0.5, 0.5]], "history_outcomes": [2], "forecasts": [[0.5, 0.5]]},
    {"history_forecasts": [[0.5]], "history_outcomes": [1], "forecasts": [[0.5]]},
    {"history_forecasts": [[0.5, 1.5]], "history_outcomes": [1], "forecasts": [[0.5, 0.5]]},
    {"history_forecasts": [[0.5, 0.5]], "history_outcomes": [1, 0], "forecasts": [[0.5, 0.5]]},
    {"history_forecasts": [[0.5, 0.5]], "history_outcomes": [1], "forecasts": [[0.5]]},
    {"history_forecasts": "x", "history_outcomes": [1], "forecasts": [[0.5, 0.5]]},
])
def test_pool_invalid_input_raises_a_genome_error(bad):
    with pytest.raises(GenomeError):
        fb.pool_solve(bad, BUDGET)


@pytest.mark.parametrize("family", FAMILIES)
def test_malformed_outputs_are_refuted_not_raised(family):
    data, _ = dev(family, QUICK[family][0])
    for junk in (None, 3, [], {}, {"x": None}, "answer", {"probabilities": "a", "weights": [], "extremization": 1},
                 {"scenarios": [[1]], "weights": [1.0], "coverage": [1.0]},
                 {"probabilities": [None], "weights": [None], "extremization": None}):
        checks = ITEMS[family].verify(data, junk, {})
        assert not all(checks.values())


# ------------------------------------------------------------------ recalibration: independent verification
def _recal_corruptions(o):
    p, m = o["probabilities"], o["calibration_map"]
    keys, vals = m["judgments"], m["calibrated"]
    bumped = list(vals)
    bumped[len(bumped) // 2] = min(bumped[len(bumped) // 2] + 0.02, 1.0)
    rev = list(vals)
    rev[0], rev[-1] = rev[-1], rev[0]
    return {
        "one_probability_moved": {**o, "probabilities": [min(p[0] + 0.01, 1.0) if p[0] < 1 else 0.99] + p[1:]},
        "raw_judgments_claimed": {**o, "probabilities": [0.5] * len(p)},
        "probability_above_one": {**o, "probabilities": [1.2] + p[1:]},
        "map_value_moved": {**o, "calibration_map": {"judgments": keys, "calibrated": bumped}},
        "map_not_monotone": {**o, "calibration_map": {"judgments": keys, "calibrated": rev}},
        "map_on_other_judgments": {**o, "calibration_map": {"judgments": [k / 2 for k in keys], "calibrated": vals}},
        "map_truncated": {**o, "calibration_map": {"judgments": keys[:-1], "calibrated": vals[:-1]}},
        "probabilities_truncated": {**o, "probabilities": p[:-1]},
    }


@pytest.mark.parametrize("seed", QUICK["forecast_recalibration"])
def test_recal_verifier_rejects_every_corruption(seed):
    data, _, out = solved("forecast_recalibration", seed)
    o = out["output"]
    assert _all("forecast_recalibration", data, o, out["certificate"])
    for name, bad in _recal_corruptions(o).items():
        assert not _all("forecast_recalibration", data, bad, {}), name


def test_isotonic_fit_matches_a_brute_force_least_squares_on_a_tiny_record():
    import itertools
    xs = [0.1, 0.2, 0.2, 0.4, 0.6, 0.7, 0.9]
    ys = [1, 0, 1, 0, 1, 0, 1]
    keys, fitted = fb._pav(xs, ys)
    grid = [i / 12 for i in range(13)]
    best = min(sum((v[keys.index(x)] - y) ** 2 for x, y in zip(xs, ys))
               for v in itertools.combinations_with_replacement(grid, len(keys)))
    sse = sum((fitted[keys.index(x)] - y) ** 2 for x, y in zip(xs, ys))
    assert sse <= best + 1e-12
    assert all(a <= b for a, b in zip(fitted, fitted[1:]))


def test_recal_abstains_and_refuses_bad_input():
    data, truth = dev("forecast_recalibration", 0)
    tiny = {**data, "past_judgments": data["past_judgments"][:10], "past_outcomes": data["past_outcomes"][:10]}
    assert fb.recal_solve(tiny, BUDGET)["status"] == "ABSTAIN"
    assert fb.recal_solve({**data, "past_outcomes": [0] * len(data["past_outcomes"])}, BUDGET)["status"] == "ABSTAIN"
    with pytest.raises(GenomeError):
        fb.recal_solve({**data, "past_outcomes": [2] * len(data["past_outcomes"])}, BUDGET)
    with pytest.raises(GenomeError):
        fb.recal_solve({**data, "judgments": [1.5]}, BUDGET)
    assert fb.recal_score(data, truth, fb.recal_platt(data))["category"] == "correct"
