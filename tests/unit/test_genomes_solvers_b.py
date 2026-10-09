"""Layer 3 batch B IntelligenceGenomes: contract shape, independent verification, abstention and scoring.

Development seeds only (0-9); the held-out admission seeds (>= 1000) are never generated here.
"""
from __future__ import annotations

import copy
import json
import math

import pytest

from greg.cognition.genomes import library, solvers_b
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

FAMILIES = ("dp_knapsack", "search_astar", "mc_importance", "queue_erlang", "bayes_interval", "game_minimax")
OPS = {"dp_knapsack": "knapsack_01_select", "search_astar": "grid_astar_route",
       "mc_importance": "tilted_tail_probability", "queue_erlang": "erlang_c_staffing",
       "bayes_interval": "jeffreys_credible_interval", "game_minimax": "zero_sum_lp_equilibrium"}
CLASSES = {"dp_knapsack": "optimization", "search_astar": "optimization", "mc_importance": "estimate",
           "queue_erlang": "prediction", "bayes_interval": "estimate", "game_minimax": "strategic"}
EVIDENCE = {"dp_knapsack": "exact_calculation", "search_astar": "exact_calculation",
            "mc_importance": "statistical_estimate", "queue_erlang": "exact_calculation",
            "bayes_interval": "posterior", "game_minimax": "optimality_certificate"}
BUDGET = {"latency_s": 5.0, "compute": 100000}
_CACHE: dict = {}


def item(family):
    return {x.genome.family: x for x in solvers_b.INTELLIGENCES}[family]


def dev(family, seed=1):
    assert 0 <= seed < 10
    key = (family, seed)
    if key not in _CACHE:
        _CACHE[key] = item(family).instance(seed)
    data, truth = _CACHE[key]
    return copy.deepcopy(data), truth


def solved(family, seed=1):
    data, truth = dev(family, seed)
    return data, truth, item(family).solve(data, BUDGET)


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
        assert value is None or isinstance(value, (str, int, bool))


# ------------------------------------------------------------------ genome contract
def test_genomes_validate_and_are_layer_three():
    assert sorted(x.genome.family for x in solvers_b.INTELLIGENCES) == sorted(FAMILIES)
    for x in solvers_b.INTELLIGENCES:
        g = x.genome
        assert isinstance(g, IntelligenceGenome) and g.validate() is g
        assert g.layer == 3 and g.buildability == "BUILDABLE_NOW" and g.standalone_decision
        assert g.version == "1.0.1"
        assert g.operation == OPS[g.family] and g.epistemic_class == CLASSES[g.family]
        assert g.evidence_type == EVIDENCE[g.family]
        assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
        assert g.authority_ceiling == "read_only" and g.consequence_limit == "read_only"
    deps = {x.genome.family: x.genome.dependency for x in solvers_b.INTELLIGENCES}
    assert deps == {"dp_knapsack": None, "search_astar": None, "mc_importance": None, "queue_erlang": None,
                    "bayes_interval": "scipy", "game_minimax": "scipy"}


def test_library_registers_batch_b_without_collisions():
    families = library.executables()
    catalog = library.catalog_families()
    for family in FAMILIES:
        assert families[family].genome.operation == OPS[family]
        assert catalog[family][:2] == (3, (OPS[family],))


def test_module_top_level_imports_no_heavy_packages():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(solvers_b))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top for a in n.names} | {n.module.split(".")[0] for n in top
                                                                      if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"numpy", "scipy", "networkx", "ortools", "z3"}


# ------------------------------------------------------------------ solve / verify
@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("seed", (0, 1, 2))
def test_solve_returns_a_compact_json_answer_that_verifies(family, seed):
    data, truth, out = solved(family, seed)
    assert set(out) == {"output", "certificate", "status", "missing"} and out["status"] == "ANSWER"
    _json_clean(out["output"])
    _json_clean(out["certificate"])
    assert len(json.dumps(out, allow_nan=False)) < 64 * 1024
    json.dumps(data, allow_nan=False)
    checks = item(family).verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    assert item(family).score(data, truth, out["output"])["category"] == "correct"


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_adapter_runs_and_checks(family):
    data, _ = dev(family, 2)
    result = library.run(family, data, {"latency_limit": 10})
    assert result["status"] == "ANSWER" and result["proof"]["evidence_type"] == EVIDENCE[family]
    checks = library.check(family, data, result["output"], result["proof"])
    assert all(checks.values()), checks


def _corrupt(family, data, out):
    o, c = copy.deepcopy(out["output"]), copy.deepcopy(out["certificate"])
    if family == "dp_knapsack":                 # drop one item, keep the claim self-consistent
        drop = o["selected"].pop()
        o["value"] -= data["values"][drop]
        o["weight"] -= data["weights"][drop]
        c["dp_optimum"] = o["value"]
    elif family == "search_astar":              # a detour that is still a valid path
        o["moves"] = o["moves"] + ("UD" if o["moves"][0] != "U" else "DU")
        o["cost"] = None
    elif family == "mc_importance":             # a tenfold over-estimate with a matching certificate
        o["probability"] = min(1.0, o["probability"] * 10.0)
        o["ci95"] = [o["probability"] * 0.9, o["probability"] * 1.1]
        c["estimate"] = o["probability"]
    elif family == "queue_erlang":              # overstaffing by one
        o["agents"] += 1
    elif family == "bayes_interval":            # shift the interval
        o["lower"] = min(o["upper"], o["lower"] + 0.03)
    elif family == "game_minimax":              # replace the equilibrium by uniform play
        o["row_strategy"] = [1.0 / len(o["row_strategy"])] * len(o["row_strategy"])
    return o, c


@pytest.mark.parametrize("family", FAMILIES)
def test_verify_refutes_a_corrupted_output(family):
    data, _, out = solved(family, 1)
    o, c = _corrupt(family, data, out)
    checks = item(family).verify(data, o, c)
    assert not all(checks.values()), checks


def test_knapsack_verify_refutes_a_consistent_but_suboptimal_selection():
    data, _ = dev("dp_knapsack", 1)
    greedy = solvers_b.knapsack_greedy(data)
    checks = solvers_b.knapsack_verify(data, greedy, {"dp_optimum": greedy["value"], "lp_upper_bound": 1e9})
    assert checks["within_capacity"] and checks["value_recomputed"]
    assert not checks["optimal_by_independent_profit_dp"]


def test_astar_verify_refutes_the_greedy_route_and_an_invalid_move():
    data, _ = dev("search_astar", 1)
    greedy = solvers_b.astar_greedy(data)
    checks = solvers_b.astar_verify(data, greedy, {})
    assert checks["path_valid"] and checks["cost_recomputed"] and not checks["optimal_by_independent_dijkstra"]
    _, _, out = solved("search_astar", 1)
    bad = dict(out["output"], moves="X" + out["output"]["moves"])
    assert not solvers_b.astar_verify(data, bad, {})["path_valid"]


def test_erlang_verify_refutes_understaffing():
    data, _, out = solved("queue_erlang", 1)
    under = dict(out["output"], agents=out["output"]["agents"] - 1)
    checks = solvers_b.erlang_verify(data, under, out["certificate"])
    assert not checks.get("meets_target", False)


def test_erlang_three_evaluations_agree():
    for seed in range(10):
        data, truth = dev("queue_erlang", seed)
        out = solvers_b.erlang_solve(data, BUDGET)
        assert out["output"]["agents"] == truth["agents"]


def test_game_value_matches_independent_lp_truth():
    for seed in range(3):
        data, truth, out = solved("game_minimax", seed)
        assert abs(out["output"]["value"] - truth["value"]) <= 1e-6


# ------------------------------------------------------------------ invalid input
INVALID = {
    "dp_knapsack": [{"values": [1, 2], "weights": [1], "capacity": 5},
                    {"values": [1], "weights": [-1], "capacity": 5},
                    {"values": [1.5], "weights": [1], "capacity": 5}],
    "search_astar": [{"grid": [[1, 1], [1]], "start": [0, 0], "goal": [1, 0]},
                     {"grid": [[1, 0], [1, 1]], "start": [0, 0], "goal": [0, 1]},
                     {"grid": [[1, 1]], "start": [0, 5], "goal": [0, 1]}],
    "mc_importance": [{"component": "cauchy", "terms": 2, "rate": 1.0, "threshold": 9.0, "samples": 1000, "seed": 1},
                      {"component": "exponential", "terms": 2, "rate": -1.0, "threshold": 9.0, "samples": 1000,
                       "seed": 1},
                      {"component": "exponential", "terms": 2, "rate": 1.0, "threshold": float("nan"),
                       "samples": 1000, "seed": 1}],
    "queue_erlang": [{"arrival_rate": float("inf"), "mean_service_time": 180.0, "target_wait": 20.0,
                      "max_wait_probability": 0.2},
                     {"arrival_rate": 1.0, "mean_service_time": 180.0, "target_wait": 20.0,
                      "max_wait_probability": 1.5},
                     {"arrival_rate": 1000.0, "mean_service_time": 1000.0, "target_wait": 20.0,
                      "max_wait_probability": 0.2}],
    "bayes_interval": [{"successes": 5, "trials": 4}, {"successes": -1, "trials": 4},
                       {"successes": 1, "trials": 4, "independent_trials": "yes"}],
    "game_minimax": [{"payoffs": [[1, 2], [3]]}, {"payoffs": [[1, float("nan")]]},
                     {"payoffs": [[1, 2]], "column_payoffs": [[1]]}],
}


@pytest.mark.parametrize("family", FAMILIES)
def test_invalid_input_raises_genome_error(family):
    for data in INVALID[family]:
        with pytest.raises(GenomeError):
            item(family).solve(data, BUDGET)


# ------------------------------------------------------------------ abstention
ABSTAIN = {
    "dp_knapsack": {"values": [1] * 61, "weights": [1] * 61, "capacity": 10},
    "search_astar": {"grid": [[1] * 61 for _ in range(61)], "start": [0, 0], "goal": [60, 60]},
    "mc_importance": {"component": "lognormal", "terms": 3, "threshold": 50.0, "samples": 1000, "seed": 3},
    "queue_erlang": {"arrival_rate": 0.5, "mean_service_time": 180.0, "target_wait": 20.0,
                     "max_wait_probability": 0.2, "abandonment_rate": 0.01},
    "bayes_interval": {"successes": 3, "trials": 20, "independent_trials": False},
    "game_minimax": {"payoffs": [[3, 0], [5, 1]], "column_payoffs": [[3, 5], [0, 1]]},
}


@pytest.mark.parametrize("family", FAMILIES)
def test_abstains_outside_native_competence(family):
    out = item(family).solve(copy.deepcopy(ABSTAIN[family]), BUDGET)
    assert out["status"] == "ABSTAIN" and out["output"] is None and out["missing"]
    _json_clean(out["certificate"])


def test_further_abstentions():
    assert solvers_b.knapsack_solve({"values": [1], "weights": [1], "capacity": 2001}, BUDGET)["status"] == "ABSTAIN"
    not_rare = {"component": "exponential", "terms": 4, "rate": 1.0, "threshold": 3.0, "samples": 1000, "seed": 1}
    assert solvers_b.mc_solve(not_rare, BUDGET)["status"] == "ABSTAIN"
    budget = {"component": "exponential", "terms": 400, "rate": 1.0, "threshold": 900.0, "samples": 10000, "seed": 1}
    assert solvers_b.mc_solve(budget, BUDGET)["status"] == "ABSTAIN"
    general = {"arrival_rate": 0.5, "mean_service_time": 180.0, "target_wait": 20.0, "max_wait_probability": 0.2,
               "service_time_cv": 2.0}
    assert solvers_b.erlang_solve(general, BUDGET)["status"] == "ABSTAIN"
    big = {"payoffs": [[(i * j) % 7 for j in range(41)] for i in range(3)]}
    assert solvers_b.game_solve(big, BUDGET)["status"] == "ABSTAIN"


def test_unreachable_goal_is_an_answer_confirmed_by_dijkstra():
    data = {"grid": [[1, 0, 1], [1, 0, 1], [1, 0, 1]], "start": [0, 0], "goal": [2, 2]}
    out = solvers_b.astar_solve(data, BUDGET)
    assert out["status"] == "ANSWER" and out["output"]["reachable"] is False
    assert all(solvers_b.astar_verify(data, out["output"], out["certificate"]).values())
    assert solvers_b.astar_score(data, {"cost": None}, out["output"])["category"] == "correct"


def test_boundary_counts_use_the_brown_cai_dasgupta_rule():
    zero = solvers_b.jeffreys_solve({"successes": 0, "trials": 12}, BUDGET)["output"]
    full = solvers_b.jeffreys_solve({"successes": 12, "trials": 12}, BUDGET)["output"]
    assert zero["lower"] == 0.0 and 0 < zero["upper"] < 0.3
    assert full["upper"] == 1.0 and 0.7 < full["lower"] < 1.0
    assert abs(zero["upper"] - (1 - full["lower"])) < 1e-12


# ------------------------------------------------------------------ scoring
@pytest.mark.parametrize("family", FAMILIES)
def test_score_categories(family):
    x = item(family)
    data, truth, out = solved(family, 1)
    assert x.score(data, truth, out["output"])["category"] == "correct"
    abstain = x.score(data, truth, None)
    assert abstain["category"] == "abstain"
    o, _ = _corrupt(family, data, out)
    if family == "search_astar":
        o["cost"] = solvers_b._walk(*solvers_b._grid(data), o["moves"])
    if family == "bayes_interval":              # an interval that misses the true p
        edge = 0.0 if truth["p"] > 0.5 else 1.0
        o = {"lower": edge, "upper": edge, "level": 0.9}
    wrong = x.score(data, truth, o)
    assert wrong["category"] == "wrong" and wrong["quality"] < x.score(data, truth, out["output"])["quality"]


def test_scores_rank_failure_severity():
    data, truth = dev("dp_knapsack", 1)
    over = {"selected": list(range(len(data["values"]))), "value": sum(data["values"])}
    assert solvers_b.knapsack_score(data, truth, over) == {"quality": -1.0, "category": "wrong"}
    data, truth = dev("queue_erlang", 1)
    best = truth["agents"]
    under = solvers_b.erlang_score(data, truth, {"agents": best - 1})
    overstaffed = solvers_b.erlang_score(data, truth, {"agents": best + 1})
    assert under["category"] == overstaffed["category"] == "wrong"
    assert under["quality"] < solvers_b.erlang_score(data, truth, None)["quality"] < overstaffed["quality"] < 0
    data, truth = dev("mc_importance", 1)
    assert solvers_b.mc_score(data, truth, {"probability": 0.0})["quality"] < solvers_b.mc_score(data, truth, None)["quality"]
    data, truth = dev("game_minimax", 1)
    assert solvers_b.game_score(data, truth, {"row_strategy": [2.0], "column_strategy": [], "value": 0.0}) == \
        {"quality": -2.0, "category": "wrong"}


def test_candidates_beat_their_baselines_on_a_dev_instance():
    for family in FAMILIES:
        x = item(family)
        data, truth, out = solved(family, 1)
        assert x.score(data, truth, out["output"])["quality"] >= x.score(data, truth, x.baseline(data))["quality"]


def test_solves_are_deterministic():
    for family in FAMILIES:
        data, _, first = solved(family, 2)
        assert item(family).solve(copy.deepcopy(data), BUDGET) == first


# ------------------------------------------------------------------ adversarial review (1.0.1)
def _forge(family, data, out, how):
    """Further corruptions per family; each must be refuted by the independent verifier."""
    o, c = copy.deepcopy(out["output"]), copy.deepcopy(out["certificate"])
    if family == "dp_knapsack" and how == "overweight":
        o["selected"] = list(range(len(data["values"])))
        o["value"], o["weight"] = sum(data["values"]), sum(data["weights"])
        c["dp_optimum"] = o["value"]
    elif family == "dp_knapsack" and how == "bound_below_optimum":
        c["lp_upper_bound"] = o["value"] - 0.5
    elif family == "search_astar" and how == "false_unreachable":
        o = {"reachable": False, "moves": None, "cost": None}
    elif family == "search_astar" and how == "understated_cost":
        o["cost"] -= 1
    elif family == "mc_importance" and how == "understated_se":
        o["std_error"] = o["std_error"] / 10.0
        o["ci95"] = [o["probability"] - 1.959964 * o["std_error"], o["probability"] + 1.959964 * o["std_error"]]
    elif family == "mc_importance" and how == "inflated_se_and_estimate":
        o["probability"] *= 10.0
        o["std_error"] = o["probability"] * 100.0
        o["ci95"] = [0.0, 1.0]
        c["estimate"] = o["probability"]
    elif family == "queue_erlang" and how == "understaffed":
        o["agents"] -= 1
    elif family == "queue_erlang" and how == "false_probability":
        o["p_wait_exceeds_target"] = o["p_wait_exceeds_target"] / 2.0
    elif family == "bayes_interval" and how == "narrowed":
        mid = 0.5 * (o["lower"] + o["upper"])
        o["lower"], o["upper"] = (o["lower"] + mid) / 2.0, (o["upper"] + mid) / 2.0
    elif family == "bayes_interval" and how == "wrong_level":
        o["level"] = 0.99
    elif family == "game_minimax" and how == "value_outside_bounds":
        o["value"] = c["upper_bound"] + 1.0
    elif family == "game_minimax" and how == "column_pure":
        o["column_strategy"] = [1.0] + [0.0] * (len(o["column_strategy"]) - 1)
    else:
        raise AssertionError((family, how))
    return o, c


FORGERIES = [("dp_knapsack", "overweight"), ("dp_knapsack", "bound_below_optimum"),
             ("search_astar", "false_unreachable"), ("search_astar", "understated_cost"),
             ("mc_importance", "understated_se"), ("mc_importance", "inflated_se_and_estimate"),
             ("queue_erlang", "understaffed"), ("queue_erlang", "false_probability"),
             ("bayes_interval", "narrowed"), ("bayes_interval", "wrong_level"),
             ("game_minimax", "value_outside_bounds"), ("game_minimax", "column_pure")]


@pytest.mark.parametrize("family,how", FORGERIES)
def test_verify_refutes_further_forgeries(family, how):
    data, _, out = solved(family, 1)
    o, c = _forge(family, data, out, how)
    checks = item(family).verify(data, o, c)
    assert not all(checks.values()), (how, checks)


def test_mc_inflated_standard_error_cannot_buy_agreement():
    """1.0.0 widened the agreement tolerance by the output's own SE, so a tenfold-wrong estimate with an inflated
    SE passed every check. The tolerance now caps the claimed SE at 2x the independent replication's."""
    data, _, out = solved("mc_importance", 1)
    o, c = _forge("mc_importance", data, out, "inflated_se_and_estimate")
    checks = solvers_b.mc_verify(data, o, c)
    assert not checks["independent_replication_agrees"]
    assert not checks["std_error_consistent_with_replication"]


def test_mc_far_tail_is_json_clean_with_a_positive_standard_error():
    """1.0.0 squared raw likelihood ratios: below ~1e-154 the ESS was NaN (invalid JSON) and the SE a false 0."""
    from scipy.stats import gamma
    data = {"component": "exponential", "terms": 400, "rate": 1.0, "threshold": 1250.0, "samples": 4000, "seed": 11}
    out = solvers_b.mc_solve(data, BUDGET)
    assert out["status"] == "ANSWER"
    json.dumps(out, allow_nan=False)
    p, se = out["output"]["probability"], out["output"]["std_error"]
    assert 0 < se < p < 1e-150 and out["certificate"]["effective_sample_size"] >= solvers_b.MC_MIN_ESS
    assert abs(p - float(gamma.sf(1250.0, 400))) <= 4 * se


def test_mc_degenerate_weights_and_underflow_are_unknown_not_answers():
    degenerate = {"component": "exponential", "terms": 1, "rate": 1.0, "threshold": 400.0, "samples": 4000, "seed": 3}
    out = solvers_b.mc_solve(degenerate, BUDGET)
    assert out["status"] == "UNKNOWN" and out["output"] is None and "effective sample size" in out["missing"][0]
    json.dumps(out, allow_nan=False)
    below_range = {"component": "exponential", "terms": 1, "rate": 1.0, "threshold": 700.0, "samples": 4000, "seed": 3}
    out = solvers_b.mc_solve(below_range, BUDGET)
    assert out["status"] == "UNKNOWN" and "double-precision" in out["missing"][0]
    json.dumps(out, allow_nan=False)


@pytest.mark.parametrize("scale", (1e-9, 1e8))
def test_game_solve_verifies_at_any_payoff_magnitude(scale):
    """1.0.0 shifted the matrix but did not rescale it: payoffs of order 1e-9 refuted the solver's own answer."""
    payoffs = [[((3 * i + 5 * j) % 7 - 3) * scale for j in range(6)] for i in range(5)]
    out = solvers_b.game_solve({"payoffs": payoffs}, BUDGET)
    assert out["status"] == "ANSWER"
    assert all(solvers_b.game_verify({"payoffs": payoffs}, out["output"], out["certificate"]).values())


def test_knapsack_verify_refuses_unbounded_work():
    import time
    data = {"values": [10_000] * 500, "weights": [1] * 500, "capacity": 3}
    started = time.perf_counter()
    checks = solvers_b.knapsack_verify(data, {"selected": [0, 1, 2], "value": 30_000, "weight": 3}, {})
    assert time.perf_counter() - started < 1.0 and not all(checks.values())


@pytest.mark.parametrize("family", FAMILIES)
def test_non_object_data_is_invalid_input(family):
    x = item(family)
    for bad in ([], "payload", None, 3):
        with pytest.raises(GenomeError):
            x.solve(bad, BUDGET)
        with pytest.raises(GenomeError):
            x.verify(bad, {}, {})


@pytest.mark.parametrize("family", FAMILIES)
def test_verify_does_not_crash_on_a_non_object_certificate(family):
    data, _, out = solved(family, 1)
    checks = item(family).verify(data, out["output"], ["not", "a", "certificate"])
    assert isinstance(checks, dict)


def test_astar_verify_requires_a_boolean_reachable():
    data = {"grid": [[1, 0, 1]], "start": [0, 0], "goal": [0, 2]}
    assert solvers_b.astar_verify(data, {"reachable": 0}, {}) == {"output_shape": False}


def test_erlang_and_jeffreys_verifiers_check_model_preconditions():
    data, _, out = solved("queue_erlang", 1)
    impatient = dict(data, abandonment_rate=0.01)
    assert not solvers_b.erlang_verify(impatient, out["output"], out["certificate"])["model_preconditions_hold"]
    data, _, out = solved("bayes_interval", 1)
    clustered = dict(data, independent_trials=False)
    assert not solvers_b.jeffreys_verify(clustered, out["output"], out["certificate"])["binomial_model_applies"]


@pytest.mark.parametrize("seed", (0, 1, 2))
def test_strengthened_competitors_are_exact_and_retained_alternatives_agree_with_truth(seed):
    data, truth = dev("dp_knapsack", seed)
    for arm in (solvers_b.knapsack_ortools, solvers_b.knapsack_cpsat):
        assert solvers_b.knapsack_score(data, truth, arm(data))["category"] == "correct"
    data, truth = dev("search_astar", seed)
    for arm in (solvers_b.astar_csgraph, solvers_b.astar_networkx):
        assert solvers_b.astar_score(data, truth, arm(data))["category"] == "correct"
    data, truth = dev("game_minimax", seed)
    result = solvers_b.game_dual_lp(data)
    assert solvers_b.game_score(data, truth, result)["category"] == "correct"
    assert abs(result["value"] - truth["value"]) <= 1e-6


def test_game_security_baseline_is_exact_only_on_saddle_games():
    for seed in range(3):
        data, truth = dev("game_minimax", seed)
        category = solvers_b.game_score(data, truth, solvers_b.game_security(data))["category"]
        assert category == ("correct" if solvers_b.game_subregion(data) == "pure_saddle" else "wrong")
