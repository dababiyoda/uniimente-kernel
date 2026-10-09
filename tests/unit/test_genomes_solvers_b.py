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
EVIDENCE = {"dp_knapsack": "optimality_certificate", "search_astar": "optimality_certificate",
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
