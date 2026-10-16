"""Promoted competitors: the mechanisms that superseded admitted genomes, routable as genomes of their own.

Contract shape, reuse of the superseded genome's geometry, independent verification, abstention, scoring and the
compiler route a request takes now that the superseded genome is excluded. Development seeds only (0-9); the
held-out admission seeds are never generated here, and nothing here runs or freezes an admission.
"""
from __future__ import annotations

import copy
import itertools
import json
import math
from pathlib import Path
import random
import sys

import pytest

pytest.importorskip("ortools")
pytest.importorskip("scipy")

from greg.cognition import catalog, compiler  # noqa: E402
from greg.cognition.cortex import reason, registry_view  # noqa: E402
from greg.cognition.genomes import basal, competitors, library, solvers_b  # noqa: E402
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SUPERSEDED = {"knapsack_bnb": "dp_knapsack", "grid_dijkstra": "search_astar", "game_lp_dual": "game_minimax",
              "pid_simopt": "basal_pid"}
FAMILIES = tuple(SUPERSEDED)
OPS = {"knapsack_bnb": "knapsack_01_branch_bound", "grid_dijkstra": "grid_dijkstra_route",
       "game_lp_dual": "zero_sum_lp_dual_equilibrium", "pid_simopt": "pi_simopt_track"}
EVIDENCE = {"knapsack_bnb": "exact_calculation", "grid_dijkstra": "optimality_certificate",
            "game_lp_dual": "optimality_certificate", "pid_simopt": "control_trace"}
FROZEN = {"dp_knapsack": competitors.V1, "search_astar": competitors.V1, "game_minimax": competitors.V1,
          "basal_pid": competitors.V2}
VERSIONS = {"grid_dijkstra": "1.1.0"}           # 1.0.0 measured EXPERIMENTAL in admission v3; 1.1.0 is faster
BUDGET = {"latency_s": 5.0, "compute": 100000}
_CACHE: dict = {}


def item(family):
    return {x.genome.family: x for x in competitors.INTELLIGENCES}[family]


def old(family):
    return library.executables()[SUPERSEDED[family]]


def dev(family, seed=1):
    assert 0 <= seed < 10
    key = ("instance", family, seed)
    if key not in _CACHE:
        _CACHE[key] = item(family).instance(seed)
    data, truth = _CACHE[key]
    return copy.deepcopy(data), truth


def solved(family, seed=1):
    data, truth = dev(family, seed)
    key = ("solve", family, seed)
    if key not in _CACHE:
        _CACHE[key] = item(family).solve(copy.deepcopy(data), BUDGET)
    return data, truth, copy.deepcopy(_CACHE[key])


def _json_clean(value):
    if isinstance(value, float):
        assert math.isfinite(value)
    elif isinstance(value, dict):
        assert all(isinstance(k, str) for k in value)
        for v in value.values():
            _json_clean(v)
    elif isinstance(value, list):
        assert len(value) <= 1000                   # canonical receipt retention bound per list
        for v in value:
            _json_clean(v)
    else:
        assert value is None or isinstance(value, (str, int, bool))


# ------------------------------------------------------------------ genome contract
def test_genomes_validate_and_reuse_the_superseded_geometry():
    assert sorted(x.genome.family for x in competitors.INTELLIGENCES) == sorted(FAMILIES)
    for x in competitors.INTELLIGENCES:
        g, former = x.genome, old(x.genome.family)
        assert isinstance(g, IntelligenceGenome) and g.validate() is g
        assert g.layer == 3 and g.buildability == "BUILDABLE_NOW" and g.standalone_decision
        assert g.version == VERSIONS.get(g.family, "1.0.0")
        assert g.operation == OPS[g.family] and g.evidence_type == EVIDENCE[g.family]
        # the same requests fit it: same native geometry and input contract as the genome it replaces
        assert g.epistemic_class == former.genome.epistemic_class
        assert g.required_inputs == former.genome.required_inputs
        assert x.instance is former.instance and x.score is former.score and x.subregion is former.subregion
        assert x.tolerance == former.tolerance and x.competitor_deployable
        assert x.promotes == former.genome.family and former.competitor_deployable
        assert g.baseline.startswith(f"{former.genome.family}'s own solve")
        assert any(former.genome.family in entry for entry in g.lineage)
        assert any(entry.startswith(FROZEN[former.genome.family]) for entry in g.lineage)
        assert g.authority_ceiling == g.consequence_limit == "read_only"
        assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
    deps = {x.genome.family: x.genome.dependency for x in competitors.INTELLIGENCES}
    assert deps == {"knapsack_bnb": "ortools", "grid_dijkstra": "scipy", "game_lp_dual": "ortools", "pid_simopt": None}
    assert library.promotions() == {old: new for new, old in SUPERSEDED.items()}


def test_a_promotion_that_would_not_answer_the_promoted_familys_requests_is_refused():
    import dataclasses
    lib = dict(library.executables())
    library.check_promotions(lib)
    knap = lib["knapsack_bnb"]
    wider = dataclasses.replace(knap.genome, required_inputs=knap.genome.required_inputs + ("deadline",))
    other_class = dataclasses.replace(knap.genome, epistemic_class="estimate")
    for bad in (dataclasses.replace(knap, promotes="no_such_family"),
                dataclasses.replace(knap, promotes="knapsack_bnb"),
                dataclasses.replace(knap, genome=wider), dataclasses.replace(knap, genome=other_class),
                dataclasses.replace(knap, promotes="grid_dijkstra")):           # a chain onto another promotion
        with pytest.raises(GenomeError, match="invalid promotion"):
            library.check_promotions({**lib, "knapsack_bnb": bad})
    twice = dataclasses.replace(lib["grid_dijkstra"], promotes="dp_knapsack",
                                genome=dataclasses.replace(lib["grid_dijkstra"].genome, epistemic_class="optimization",
                                                           required_inputs=("values",)))
    with pytest.raises(GenomeError, match="invalid promotion"):
        library.check_promotions({**lib, "grid_dijkstra": twice})
    oracle = dataclasses.replace(lib["dp_knapsack"], competitor_deployable=False)
    with pytest.raises(GenomeError, match="invalid promotion"):
        library.check_promotions({**lib, "dp_knapsack": oracle})


def test_a_promotion_the_compiler_would_not_route_is_refused():
    """check_promotions accepted a composition-only promoted genome, and one reading a strict subset of the former's
    inputs without producing its decision; the compiler then rejected the promoted row ('composition stage only',
    'answers a relaxation') while the former still pointed at it, so the request ended in a bare deficit."""
    import dataclasses
    lib = dict(library.executables())
    pid = lib["pid_simopt"]
    fewer = tuple(k for k in pid.genome.required_inputs if k != "u0")
    for bad in (dataclasses.replace(pid.genome, standalone_decision=False),
                dataclasses.replace(pid.genome, required_inputs=fewer, output_contract={"gains": "dict"}),
                dataclasses.replace(pid.genome, output_contract={k: v for k, v in pid.genome.output_contract.items()
                                                                 if k != "kc"})):
        with pytest.raises(GenomeError, match="invalid promotion"):
            library.check_promotions({**lib, "pid_simopt": dataclasses.replace(pid, genome=bad)})
    # fewer inputs and every former output: the same decision from less side information, which competes
    library.check_promotions({**lib, "pid_simopt": dataclasses.replace(
        pid, genome=dataclasses.replace(pid.genome, required_inputs=fewer))})


def test_the_frozen_evidence_records_the_four_supersessions_this_module_answers():
    for family, path in FROZEN.items():
        results = json.loads((ROOT / path).read_text())["genomes"][family]
        assert results["status"] == "SUPERSEDED", family


def test_registered_on_the_one_catalog_and_withheld_until_a_founder_attach():
    families = library.executables()
    projection = library.catalog_families()
    registry = registry_view()
    for family in FAMILIES:
        g = families[family].genome
        assert projection[family] == (3, (OPS[family],), (g.epistemic_class,), "genome_certificate", g.dependency)
        assert catalog.FAMILIES[family] == projection[family]
        assert catalog.initial_state(f"cognition.{family}") == "VERIFIED"       # registered, never auto-attached
        assert f"cognition.{family}" in registry.manifests
        assert registry.state[f"cognition.{family}"] == "VERIFIED"
        assert not registry.usable(f"cognition.{family}")[0]


def test_module_top_level_imports_no_heavy_packages():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(competitors))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top for a in n.names} | {n.module.split(".")[0] for n in top
                                                                      if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"numpy", "scipy", "networkx", "ortools", "z3"}


# ------------------------------------------------------------------ solve / verify on every development seed
@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("seed", range(10))
def test_solve_answers_verifies_and_scores_correct_on_every_dev_seed(family, seed):
    data, truth, out = solved(family, seed)
    assert set(out) == {"output", "certificate", "status", "missing"} and out["status"] == "ANSWER"
    _json_clean(out["output"])
    _json_clean(out["certificate"])
    assert len(json.dumps(out, allow_nan=False)) < 64 * 1024
    checks = item(family).verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    assert item(family).score(data, truth, out["output"])["category"] == "correct"


@pytest.mark.parametrize("family", FAMILIES)
def test_baseline_is_the_superseded_genomes_own_solve(family):
    data, _ = dev(family, 2)
    former = old(family).solve(copy.deepcopy(data), BUDGET)
    assert former["status"] == "ANSWER" and item(family).baseline(data) == former["output"]


@pytest.mark.parametrize("family", FAMILIES)
def test_candidate_never_scores_below_the_superseded_genome(family):
    for seed in (0, 1, 2):
        data, truth, out = solved(family, seed)
        x = item(family)
        assert x.score(data, truth, out["output"])["quality"] >= x.score(data, truth, x.baseline(data))["quality"]


def test_pid_beats_the_simc_rule_it_replaces_on_every_dev_seed():
    for seed in range(10):
        data, truth, out = solved("pid_simopt", seed)
        new = basal.pid_score(data, truth, out["output"])["quality"]
        assert new > basal.pid_score(data, truth, basal.pid_solve(data, BUDGET)["output"])["quality"]


@pytest.mark.parametrize("family", FAMILIES)
def test_competitors_answer_in_contract(family):
    data, truth = dev(family, 3)
    result = item(family).competitor(copy.deepcopy(data))
    assert item(family).score(data, truth, result)["category"] == "correct"


@pytest.mark.parametrize("data", ({"grid": [[1, 0, 1]], "start": [0, 0], "goal": [0, 2]},
                                  {"grid": [[1, 0, 1]], "start": [0, 2], "goal": [0, 0]}))
def test_the_grid_competitor_reports_an_isolated_endpoint_unreachable(data):
    """NetworkX's bidirectional Dijkstra raised NodeNotFound for an endpoint with no passable neighbour (it had no
    edge, so it was never added), which an admission arm does not catch."""
    result = competitors.grid_networkx_bidirectional(copy.deepcopy(data))
    assert result == {"reachable": False, "moves": None, "cost": None}
    assert solvers_b.astar_score(data, {"cost": None}, result)["category"] == "correct"
    assert competitors.grid_dijkstra_solve(data, BUDGET)["output"]["reachable"] is False


def test_solves_are_deterministic():
    for family in FAMILIES:
        data, _, first = solved(family, 2)
        assert item(family).solve(copy.deepcopy(data), BUDGET) == first


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_adapter_runs_and_checks(family):
    data, _ = dev(family, 2)
    result = library.run(family, data, {"latency_limit": 10})
    assert result["status"] == "ANSWER" and result["proof"]["evidence_type"] == EVIDENCE[family]
    checks = library.check(family, data, result["output"], result["proof"])
    assert all(checks.values()), checks
    assert not all(library.check(family, data, result["output"], {**result["proof"], "inputs_digest": "x"}).values())


@pytest.mark.parametrize("family", FAMILIES)
def test_the_isolated_worker_path_answers_once_attached_for_evaluation(family):
    data, _ = dev(family, 4)
    registry = registry_view()
    request = {"problem_id": f"promoted:{family}", "operation": OPS[family], "data": data,
               "geometry": {"latency_limit": 20}}
    assert reason(request, registry=registry)["abstention_state"] == "CAPABILITY_DEFICIT"       # withheld
    registry.set_state(f"cognition.{family}", "ATTACHED")                   # evaluation-only, in memory
    r = reason(request, registry=registry)
    assert r["abstention_state"] == "NONE" and r["proof_type"] == "genome_certificate"
    assert r["proof_artifact"]["evidence_type"] == EVIDENCE[family]
    assert r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" and r["authority_created"] is False


# ------------------------------------------------------------------ the verifiers are independent of the solvers
def _blocked(monkeypatch, *packages):
    for name in list(sys.modules):
        if name.split(".")[0] in packages:
            monkeypatch.delitem(sys.modules, name)
    for name in packages:
        monkeypatch.setitem(sys.modules, name, None)        # any import of it now raises ImportError


def test_knapsack_and_game_verifiers_run_without_the_solver_libraries(monkeypatch):
    knap, game = solved("knapsack_bnb", 1), solved("game_lp_dual", 1)
    _blocked(monkeypatch, "ortools", "scipy")
    for family, (data, _, out) in (("knapsack_bnb", knap), ("game_lp_dual", game)):
        assert all(item(family).verify(data, out["output"], out["certificate"]).values())
    with pytest.raises(ImportError):
        competitors.knapsack_bnb_solve(knap[0], BUDGET)


def test_grid_verifier_runs_without_scipy_and_never_searches(monkeypatch):
    data, _, out = solved("grid_dijkstra", 1)
    _blocked(monkeypatch, "scipy", "networkx", "numpy")
    monkeypatch.setattr(solvers_b, "_dijkstra_cost", lambda *a: pytest.fail("the verifier must not search"))
    assert all(competitors.grid_dijkstra_verify(data, out["output"], out["certificate"]).values())


def test_pid_verifier_does_not_share_the_solvers_simulation(monkeypatch):
    # corrupt the solver-side simulation and stability check: the verifier's judgement of a good answer must not
    # move, and the corrupted solver's answer must be refuted
    data, _, good = solved("pid_simopt", 5)
    real_loop = basal._pid_loop

    def biased(p, ctrl):
        ys, us, rs = real_loop(p, ctrl)
        return [y + 0.05 * abs(p["gain"]) for y in ys], us, rs
    monkeypatch.setattr(basal, "_pid_loop", biased)
    monkeypatch.setattr(basal, "_pid_spectral_radius_poly", lambda p, ctrl: 0.5)
    monkeypatch.setattr(basal, "_pid_judge", lambda *a: pytest.fail("the verifier must not use the scorer's replay"))
    monkeypatch.setattr(basal, "_pid_eig_radius", lambda *a: pytest.fail("the verifier has its own stability check"))
    assert all(competitors.pid_simopt_verify(data, good["output"], good["certificate"]).values())
    bad = competitors.pid_simopt_solve(data, BUDGET)
    assert bad["status"] == "ANSWER"
    assert not all(competitors.pid_simopt_verify(data, bad["output"], bad["certificate"]).values())


def test_pid_independent_replay_and_stability_agree_with_both_existing_implementations():
    for seed in (0, 3, 6):
        data, _, out = solved("pid_simopt", seed)
        p = basal._pid_inputs(data)
        for ctrl in (basal.pid_solve(data, BUDGET)["output"], out["output"]):
            mine = competitors._px_replay(p, ctrl["kc"], ctrl["ti"], p["seed"])
            judged = basal._pid_judge(p, basal._pid_controller(ctrl))
            looped = basal._pid_metrics(p, *basal._pid_loop(p, basal._pid_controller(ctrl)))
            for key in ("cost", "iae", "effort_tv", "max_abs_error"):
                assert math.isclose(mine[key], judged[key], rel_tol=1e-9) and math.isclose(mine[key], looped[key],
                                                                                           rel_tol=1e-9)
            assert mine["longest_limit_run"] == judged["longest_limit_run"] == looped["longest_limit_run"]
            rho = competitors._px_radius(p, ctrl["kc"], ctrl["ti"])
            assert abs(rho - basal._pid_eig_radius(p, basal._pid_controller(ctrl))) <= 1e-8
            assert abs(rho - basal._pid_spectral_radius_poly(p, basal._pid_controller(ctrl))) <= 1e-6


# ------------------------------------------------------------------ forgeries are refuted
def _forge(family, data, out, how):
    o, c = copy.deepcopy(out["output"]), copy.deepcopy(out["certificate"])
    if family == "knapsack_bnb" and how == "drop_item":            # self-consistent but suboptimal
        drop = o["selected"].pop()
        o["value"] -= data["values"][drop]
        o["weight"] -= data["weights"][drop]
    elif family == "knapsack_bnb" and how == "greedy":
        o = solvers_b.knapsack_greedy(data)
    elif family == "knapsack_bnb" and how == "overweight":
        o["selected"] = list(range(len(data["values"])))
        o["value"], o["weight"] = sum(data["values"]), sum(data["weights"])
    elif family == "knapsack_bnb" and how == "unproven":
        c["solver_reports_optimal"] = False
    elif family == "grid_dijkstra" and how == "detour":              # a valid, costed route that is not shortest
        o["moves"] = o["moves"] + ("UD" if o["moves"][0] != "U" else "DU")
        o["cost"] = solvers_b._walk(*solvers_b._grid(data), o["moves"])
        o["steps"] = len(o["moves"])
    elif family == "grid_dijkstra" and how == "greedy_with_raised_goal_potential":
        o = dict(solvers_b.astar_greedy(data))
        o["steps"] = len(o["moves"])
        c["potential"][data["goal"][0]][data["goal"][1]] = o["cost"]
    elif family == "grid_dijkstra" and how == "potential_not_zero_at_start":
        c["potential"] = [[x + 1 for x in row] for row in c["potential"]]
    elif family == "grid_dijkstra" and how == "potential_float":
        c["potential"][0][0] = float(c["potential"][0][0])
    elif family == "grid_dijkstra" and how == "false_unreachable":
        o = {"reachable": False, "moves": None, "cost": None}
    elif family == "game_lp_dual" and how == "uniform_row":
        o["row_strategy"] = [1.0 / len(o["row_strategy"])] * len(o["row_strategy"])
    elif family == "game_lp_dual" and how == "value_outside_bounds":
        o["value"] = c["upper_bound"] + 1.0
    elif family == "game_lp_dual" and how == "pure_column":
        o["column_strategy"] = [1.0] + [0.0] * (len(o["column_strategy"]) - 1)
    elif family == "game_lp_dual" and how == "certificate_bounds":
        c["lower_bound"] -= 1.0
    elif family == "pid_simopt" and how == "simc_gains_with_consistent_claims":
        simc = basal.pid_solve(data, BUDGET)["output"]
        o.update(kc=simc["kc"], ti=simc["ti"])
        p = basal._pid_inputs(data)
        sim = competitors._px_replay(p, o["kc"], o["ti"], p["seed"])
        c.update({k: sim[k] for k in ("iae", "effort_tv", "cost", "max_abs_error", "longest_limit_run")},
                 closed_loop_spectral_radius=competitors._px_radius(p, o["kc"], o["ti"]))
        c["optimisation"]["objective"] = competitors._px_admissible(
            p, o["kc"], o["ti"], competitors._px_noise_seed(p["seed"]))
    elif family == "pid_simopt" and how == "understated_cost":
        c["cost"] *= 0.9
    elif family == "pid_simopt" and how == "chosen_noise":
        c["optimisation"]["noise_seed"] += 1
    elif family == "pid_simopt" and how == "derivative_term":
        o.update(td=1.0, tf=0.1)
    else:
        raise AssertionError((family, how))
    return o, c


FORGERIES = [(family, how) for family, hows in (
    ("knapsack_bnb", ("drop_item", "greedy", "overweight", "unproven")),
    ("grid_dijkstra", ("detour", "greedy_with_raised_goal_potential", "potential_not_zero_at_start", "potential_float",
                       "false_unreachable")),
    ("game_lp_dual", ("uniform_row", "value_outside_bounds", "pure_column", "certificate_bounds")),
    ("pid_simopt", ("simc_gains_with_consistent_claims", "understated_cost", "chosen_noise", "derivative_term")))
    for how in hows]


@pytest.mark.parametrize("family,how", FORGERIES)
def test_verify_refutes_forgeries(family, how):
    data, _, out = solved(family, 1)
    o, c = _forge(family, data, out, how)
    checks = item(family).verify(data, o, c)
    assert not all(checks.values()), (how, checks)


def test_a_consistent_suboptimal_knapsack_is_refuted_only_by_the_independent_optimum():
    data, _, out = solved("knapsack_bnb", 1)
    o, c = _forge("knapsack_bnb", data, out, "greedy")
    checks = competitors.knapsack_bnb_verify(data, o, c)
    assert checks["within_capacity"] and checks["value_recomputed"]
    assert not checks["optimal_by_independent_dynamic_program"]


def test_a_detour_fails_tightness_and_a_raised_goal_potential_fails_feasibility():
    data, _, out = solved("grid_dijkstra", 1)
    checks = competitors.grid_dijkstra_verify(data, *_forge("grid_dijkstra", data, out, "detour"))
    assert checks["path_valid"] and checks["cost_recomputed"] and checks["potential_feasible_on_every_edge"]
    assert not checks["route_tight_with_potential"]
    checks = competitors.grid_dijkstra_verify(data, *_forge("grid_dijkstra", data, out,
                                                            "greedy_with_raised_goal_potential"))
    assert checks["path_valid"] and checks["route_tight_with_potential"]
    assert not checks["potential_feasible_on_every_edge"]


def test_a_simc_answer_with_self_consistent_claims_is_refuted_by_local_optimality():
    data, _, out = solved("pid_simopt", 1)
    checks = competitors.pid_simopt_verify(data, *_forge("pid_simopt", data, out,
                                                         "simc_gains_with_consistent_claims"))
    failed = {k for k, v in checks.items() if not v}
    assert failed == {"locally_optimal_on_the_optimisation_noise"}, checks


def test_a_game_strategy_with_mass_off_the_best_responses_is_refuted():
    data, _, out = solved("game_lp_dual", 1)
    o = copy.deepcopy(out["output"])
    a = data["payoffs"]
    conceded = [sum(a[i][j] * o["column_strategy"][j] for j in range(len(a[0]))) for i in range(len(a))]
    worst = min(range(len(a)), key=conceded.__getitem__)
    best = max(range(len(a)), key=conceded.__getitem__)
    assert conceded[best] > conceded[worst]
    o["row_strategy"] = [(1.0 if i == worst else 0.0) * 1e-3 + p * (1 - 1e-3) for i, p in enumerate(o["row_strategy"])]
    checks = competitors.game_lp_dual_verify(data, o, out["certificate"])
    assert not checks["row_support_are_best_responses"] and not checks["equilibrium_gap_zero"]


# matching pennies at a common offset: (payoffs, exact value)
OFFSET_GAMES = {"dollars": ([[1_000_000.01, 999_999.99], [999_999.99, 1_000_000.01]], 1_000_000.0),
                "billion": ([[1e9, 1e9 - 2], [1e9 - 2, 1e9]], 1e9 - 1)}


def _offset_forgery(payoffs):
    """Both strategies scaled by 1 + 0.99e-9 (inside the accepted |sum - 1| <= 1e-9), value and bounds recomputed
    on the raw payoffs: every guarantee moves by 0.99e-9 x the common offset, not by 0.99e-9 x the range."""
    stretch, m, n = 1 + 0.99e-9, len(payoffs), len(payoffs[0])
    x, y = [stretch / m] * m, [stretch / n] * n
    lower = min(math.fsum(x[i] * payoffs[i][j] for i in range(m)) for j in range(n))
    upper = max(math.fsum(payoffs[i][j] * y[j] for j in range(n)) for i in range(m))
    return {"row_strategy": x, "column_strategy": y, "value": upper}, {"lower_bound": lower, "upper_bound": upper}


@pytest.mark.parametrize("game", sorted(OFFSET_GAMES))
def test_a_false_value_carried_by_a_common_payoff_offset_is_refuted(game):
    payoffs, value = OFFSET_GAMES[game]
    data, span = {"payoffs": payoffs}, max(map(max, payoffs)) - min(map(min, payoffs))
    forged, certificate = _offset_forgery(payoffs)
    assert abs(forged["value"] - value) >= 0.04 * span            # 4.95% (dollars), 49.5% (billion) of the range
    checks = competitors.game_lp_dual_verify(data, forged, certificate)
    assert checks["mixed_strategies"] and checks["equilibrium_gap_zero"]
    assert not checks["value_between_bounds"] and not checks["certificate_bounds"], checks
    run = library.run("game_lp_dual", data, {"latency_limit": 10})
    assert not all(library.check("game_lp_dual", data, forged, {**run["proof"], "certificate": certificate}).values())
    assert solvers_b.game_score(data, {"value": value}, forged)["category"] == "wrong"
    assert run["status"] == "ANSWER" and abs(run["output"]["value"] - value) <= 1e-7 * span
    assert all(library.check("game_lp_dual", data, run["output"], run["proof"]).values())
    assert solvers_b.game_score(data, {"value": value}, run["output"])["category"] == "correct"


# ------------------------------------------------------------------ invalid input, abstention, edge behaviour
INVALID = {
    "knapsack_bnb": [{"values": [1, 2], "weights": [1], "capacity": 5}, {"values": [1], "weights": [-1], "capacity": 5},
                     {"values": [1.5], "weights": [1], "capacity": 5}],
    "grid_dijkstra": [{"grid": [[1, 1], [1]], "start": [0, 0], "goal": [1, 0]},
                      {"grid": [[1, 0], [1, 1]], "start": [0, 0], "goal": [0, 1]},
                      {"grid": [[1, 1]], "start": [0, 5], "goal": [0, 1]}],
    "game_lp_dual": [{"payoffs": [[1, 2], [3]]}, {"payoffs": [[1, float("nan")]]},
                     {"payoffs": [[1, 2]], "column_payoffs": [[1]]}],
    "pid_simopt": [{"gain": 0.0, "tau": 1.0, "theta": 0.5, "dt": 0.1, "steps": 100, "setpoints": [[0.0, 1.0]],
                    "u_min": 0.0, "u_max": 2.0, "u0": 1.0},
                   {"gain": 1.0, "tau": 1.0, "theta": 0.5, "dt": 0.1, "steps": 100, "setpoints": [[1.0, 1.0]],
                    "u_min": 0.0, "u_max": 2.0, "u0": 1.0},
                   {"gain": 1.0, "tau": 1.0, "theta": 0.5, "dt": 0.1, "steps": 100, "setpoints": [[0.0, 1.0]],
                    "u_min": 2.0, "u_max": 1.0, "u0": 1.0}],
}


@pytest.mark.parametrize("family", FAMILIES)
def test_invalid_input_raises_genome_error(family):
    for data in INVALID[family]:
        with pytest.raises(GenomeError):
            item(family).solve(data, BUDGET)


@pytest.mark.parametrize("family", FAMILIES)
def test_non_object_data_is_invalid_input_and_a_non_object_certificate_binds_nothing(family):
    x = item(family)
    for bad in ([], "payload", None, 3):
        with pytest.raises(GenomeError):
            x.solve(bad, BUDGET)
        with pytest.raises(GenomeError):
            x.verify(bad, {}, {})
    data, _, out = solved(family, 1)
    checks = x.verify(data, out["output"], ["not", "a", "certificate"])
    assert isinstance(checks, dict) and not all(checks.values())


ABSTAIN = {
    "knapsack_bnb": {"values": [10_000] * 500, "weights": [1] * 500, "capacity": 999_999},
    "grid_dijkstra": {"grid": [[1] * 101 for _ in range(101)], "start": [0, 0], "goal": [100, 100]},
    "game_lp_dual": {"payoffs": [[3, 0], [5, 1]], "column_payoffs": [[3, 5], [0, 1]]},
}


@pytest.mark.parametrize("family", sorted(ABSTAIN))
def test_abstains_outside_native_competence(family):
    out = item(family).solve(copy.deepcopy(ABSTAIN[family]), BUDGET)
    assert out["status"] == "ABSTAIN" and out["output"] is None and out["missing"]
    _json_clean(out["certificate"])


def test_pid_abstains_on_long_horizons_and_unreachable_setpoints():
    data, _ = dev("pid_simopt", 4)
    assert competitors.pid_simopt_solve(dict(data, steps=2001), BUDGET)["status"] == "ABSTAIN"
    far = dict(data, setpoints=[[0.0, data["setpoints"][0][1]], [5.0, 100.0]])
    out = competitors.pid_simopt_solve(far, BUDGET)
    assert out["status"] == "ABSTAIN" and "unreachable" in out["missing"][0]


def _spanner(seed, n=40):
    """A review instance (seeds 3000-3999) with two item types in multiples: hard for branch and bound."""
    import random
    r = random.Random(seed)
    base = [(r.randint(1, 1000), r.randint(1, 1000)) for _ in range(2)]
    items = [base[r.randrange(2)] for _ in range(n)]
    m = [r.randint(1, 3) for _ in range(n)]
    w = [b[0] * k for b, k in zip(items, m)]
    return {"values": [min(10_000, b[1] * k) for b, k in zip(items, m)], "weights": w, "capacity": sum(w) // 2}


def test_knapsack_answers_beyond_the_former_native_range_with_bounded_solvers_only():
    former = solvers_b.knapsack_solve({"values": [1] * 61, "weights": [1] * 61, "capacity": 2001}, BUDGET)
    assert former["status"] == "ABSTAIN"
    import random
    r = random.Random(3500)
    for n in (61, 64, 65, 150):
        data = {"values": [r.randint(1, 500) for _ in range(n)], "weights": [r.randint(1, 400) for _ in range(n)],
                "capacity": 2500 + 40 * n}
        out = competitors.knapsack_bnb_solve(data, BUDGET)
        # OR-Tools' 64-item bitset solver ignores its time limit (339 s measured on a 40-item review instance)
        assert out["status"] == "ANSWER" and out["certificate"]["solver"] in (competitors.KX_BNB, competitors.KX_DP)
        assert all(competitors.knapsack_bnb_verify(data, out["output"], out["certificate"]).values())
    zero = {"values": [5, 0, 3], "weights": [2, 3, 9], "capacity": 0}
    out = competitors.knapsack_bnb_solve(zero, BUDGET)
    assert out["output"] == {"selected": [], "value": 0, "weight": 0}
    assert all(competitors.knapsack_bnb_verify(zero, out["output"], out["certificate"]).values())


def test_a_branch_and_bound_stall_is_answered_exactly_by_the_dynamic_program_within_its_bound():
    import time
    data = _spanner(3434)            # the bare branch and bound held a suboptimal incumbent here after 1 s
    started = time.perf_counter()
    out = competitors.knapsack_bnb_solve(data, BUDGET)
    assert time.perf_counter() - started < 5.0
    assert out["status"] == "ANSWER" and out["certificate"]["solver"] == competitors.KX_DP
    assert out["certificate"]["solvers_tried"] and "not proven" in out["certificate"]["solvers_tried"][0]
    assert all(competitors.knapsack_bnb_verify(data, out["output"], out["certificate"]).values())
    assert out["output"]["value"] == competitors._kx_exact_optimum(data["values"], data["weights"], data["capacity"])


def test_a_stall_beyond_the_dynamic_programs_bound_is_unknown_never_a_guess(monkeypatch):
    calls = []

    def stalled(kind, v, w, cap, limit=None):
        calls.append((kind, limit))
        return None
    monkeypatch.setattr(competitors, "_kx_ortools", stalled)
    # 50 items with values 1-50 (total <= 2500, so the check certifies it) and capacity 100 000 (DP 5e6 cells)
    wide = {"values": [1 + i for i in range(50)], "weights": [1500 + 37 * i for i in range(50)], "capacity": 100_000}
    out = competitors.knapsack_bnb_solve(wide, BUDGET)
    assert out["status"] == "UNKNOWN" and out["output"] is None and "cell bound" in out["missing"][0]
    assert calls == [(competitors.KX_BNB, competitors.KX_BNB_SLICE)]
    calls.clear()
    out = competitors.knapsack_bnb_solve(_spanner(3434), {"latency_s": 0.02})      # within bound: DP tried too
    assert out["status"] == "UNKNOWN" and [k for k, _ in calls] == [competitors.KX_BNB, competitors.KX_DP]
    assert calls[0][1] == 0.005                                                   # the slice follows the budget


def test_knapsack_verify_refuses_unbounded_work():
    import time
    data = {"values": [10_000] * 500, "weights": [1] * 500, "capacity": 999_999}
    started = time.perf_counter()
    checks = competitors.knapsack_bnb_verify(data, {"selected": [0, 1, 2], "value": 30_000, "weight": 3}, {})
    assert time.perf_counter() - started < 1.0 and checks["independent_check_within_bounds"] is False


def test_grid_unreachable_goal_is_an_answer_confirmed_by_flood_fill():
    data = {"grid": [[1, 0, 1], [1, 0, 1], [1, 0, 1]], "start": [0, 0], "goal": [2, 2]}
    out = competitors.grid_dijkstra_solve(data, BUDGET)
    assert out["status"] == "ANSWER" and out["output"]["reachable"] is False
    assert out["certificate"]["component_size"] == 3
    assert all(competitors.grid_dijkstra_verify(data, out["output"], out["certificate"]).values())
    assert solvers_b.astar_score(data, {"cost": None}, out["output"])["category"] == "correct"
    wrong = dict(out["certificate"], component_size=4)
    assert not competitors.grid_dijkstra_verify(data, out["output"], wrong)["component_size_recomputed"]


def test_grid_answers_up_to_one_hundred_cells_a_side_within_the_worker_output_bound():
    import random
    r = random.Random(3600)
    grid = [[0 if r.random() < 0.2 else r.randint(1, 1000) for _ in range(100)] for _ in range(100)]
    grid[0][0] = grid[99][99] = 5
    data = {"grid": grid, "start": [0, 0], "goal": [99, 99]}
    out = competitors.grid_dijkstra_solve(data, BUDGET)
    assert out["status"] == "ANSWER"
    assert all(competitors.grid_dijkstra_verify(data, out["output"], out["certificate"]).values())
    assert len(json.dumps(out)) < 256 * 1024                 # the isolated worker's output bound
    _json_clean(out["certificate"])


# --------------------------- grid_dijkstra 1.1.0: 1.0.0's distances and certificate (guaranteed), route (observed)
def _grid_case(r, rows, cols, blocked, high):
    """A review-seed grid (seeds 3700-3799): rows x cols, a blocked fraction, costs 1..high, passable endpoints."""
    grid = [[0 if r.random() < blocked else r.randint(1, high) for _ in range(cols)] for _ in range(rows)]
    start, goal = [r.randrange(rows), r.randrange(cols)], [r.randrange(rows), r.randrange(cols)]
    for rr, cc in (start, goal):
        grid[rr][cc] = grid[rr][cc] or 1
    return {"grid": grid, "start": start, "goal": goal}


def _grid_edge_cases():
    cases = [{"grid": [[1]], "start": [0, 0], "goal": [0, 0]},                                   # start is the goal
             {"grid": [[1, 0, 1]], "start": [0, 0], "goal": [0, 2]},                             # isolated endpoints
             {"grid": [[1, 0, 1], [1, 0, 1], [1, 0, 1]], "start": [0, 0], "goal": [2, 2]},      # a wall: unreachable
             {"grid": [[5] * 7], "start": [0, 6], "goal": [0, 0]},                               # one row, leftwards
             {"grid": [[2] for _ in range(7)], "start": [6, 0], "goal": [0, 0]},                 # one column, upwards
             {"grid": [[1000] * 100 for _ in range(100)], "start": [99, 99], "goal": [0, 0]}]    # largest, dearest
    for seed in range(3700, 3740):
        r = random.Random(seed)
        cases.append(_grid_case(r, r.randint(1, 100), r.randint(1, 100), r.choice((0.0, 0.2, 0.45, 0.6)),
                                r.choice((1, 9, 1000))))
    return cases


ROUTE = ("moves", "steps")      # which optimal route was traced: observed equal to 1.0.0's, never guaranteed


def _without_route(result):
    return {**result, "output": {k: v for k, v in result["output"].items() if k not in ROUTE}}


def _route(result):
    return {k: result["output"].get(k) for k in ROUTE}


def _assert_1_0_guarantee(new, ref, data):
    """What 1.1.0 guarantees against 1.0.0 (``grid_dijkstra_solve``'s docstring): every distance is unchanged, so the
    status, reachability, cost and the whole certificate (the potential and the settled-cell and component counts
    are functions of the distances) are equal, and the answer verifies. The route is not compared here: which optimal
    route the predecessors trace depends on SciPy's heap tie-breaking (the observation test checks it apart)."""
    assert new["status"] == ref["status"] == "ANSWER"
    assert _without_route(new) == _without_route(ref)
    assert all(competitors.grid_dijkstra_verify(data, new["output"], new["certificate"]).values())


def _tight_route(data, potential, order):
    """An optimal route traced back from the goal along tight edges of the potential, preferring moves in ``order``:
    a stand-in for the route another tie-break would trace."""
    step = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}
    grid, start, (r, c) = data["grid"], tuple(data["start"]), data["goal"]
    path = []
    while (r, c) != start:
        m = next(m for m in order if 0 <= r - step[m][0] < len(grid) and 0 <= c - step[m][1] < len(grid[0])
                 and grid[r - step[m][0]][c - step[m][1]]
                 and potential[r - step[m][0]][c - step[m][1]] + grid[r][c] == potential[r][c])
        path.append(m)
        r, c = r - step[m][0], c - step[m][1]
    return "".join(reversed(path))


@pytest.mark.parametrize("seed", range(10))
def test_grid_1_1_keeps_the_distances_cost_and_certificate_of_1_0_on_every_dev_seed(seed):
    data, truth = dev("grid_dijkstra", seed)
    new = competitors.grid_dijkstra_solve(copy.deepcopy(data), BUDGET)
    _assert_1_0_guarantee(new, competitors.grid_dijkstra_solve_v100(copy.deepcopy(data), BUDGET), data)
    assert new["output"]["cost"] == truth["cost"] == competitors.grid_networkx_bidirectional(data)["cost"]


def test_grid_1_1_matches_1_0_and_networkx_on_edge_and_review_grids_and_every_answer_verifies():
    reachable = unreachable = 0
    for data in _grid_edge_cases():
        new = competitors.grid_dijkstra_solve(copy.deepcopy(data), BUDGET)
        _assert_1_0_guarantee(new, competitors.grid_dijkstra_solve_v100(copy.deepcopy(data), BUDGET), data)
        assert new["certificate"]["method"] == competitors.GD_METHOD
        other = competitors.grid_networkx_bidirectional(copy.deepcopy(data))
        assert new["output"]["reachable"] == other["reachable"] and new["output"]["cost"] == other["cost"]
        reachable += new["output"]["reachable"]
        unreachable += not new["output"]["reachable"]
    assert reachable >= 20 and unreachable >= 5          # both branches are exercised


def test_the_grid_1_0_guarantee_holds_for_another_optimal_route_and_fails_on_another_cost_or_potential():
    """A SciPy tie-break change must not fail the guarantee tests: an answer that traces another optimal route (here
    traced along tight edges of the potential with other move preferences) still meets the 1.0 guarantee and
    verifies, while the observation test would report it; a changed cost or potential fails the guarantee."""
    data, _, new = solved("grid_dijkstra", 1)                # a uniform-cost obstacle grid: optimal routes tie
    ref = competitors.grid_dijkstra_solve_v100(copy.deepcopy(data), BUDGET)
    potential = new["certificate"]["potential"]
    others = sorted({_tight_route(data, potential, order) for order in itertools.permutations("UDLR")}
                    - {new["output"]["moves"]})
    assert others                                            # this grid has another optimal route
    other = {**new, "output": {**new["output"], "moves": others[0], "steps": len(others[0])}}
    _assert_1_0_guarantee(other, ref, data)
    assert _route(other) != _route(ref)
    broken = ({**other, "output": {**other["output"], "cost": other["output"]["cost"] + 1}},
              {**other, "certificate": {**other["certificate"], "potential": [[x + 1 for x in row]
                                                                              for row in potential]}})
    for answer in broken:
        with pytest.raises(AssertionError):
            _assert_1_0_guarantee(answer, ref, data)


def _grid_inputs_answered():
    """The inputs of the input-check test that the contract accepts (a plain grid and a list-subclass grid)."""
    out = []
    for data in GRID_INPUTS + [{"grid": [_Row([1, 2]), _Row([3, 4])], "start": [0, 0], "goal": [1, 1]}]:
        try:
            solvers_b._grid(copy.deepcopy(data))
        except GenomeError:
            continue
        out.append(data)
    return out


def test_observation_not_a_guarantee_1_1_traces_1_0s_route_on_every_grid_tested():
    """OBSERVATION, not a guarantee (``grid_dijkstra_solve``'s docstring). 1.1.0 scans neighbours in another order
    than 1.0.0's sorted CSR, so where several routes are optimal the one traced depends on SciPy's heap tie-breaking.
    On every grid tested both trace the same route. If this fails while the guarantee tests pass, SciPy's tie-breaking
    changed: the answers are still optimal and verified; correct the genome's notes that report identical routes."""
    cases = [dev("grid_dijkstra", seed)[0] for seed in range(10)] + _grid_edge_cases() + _grid_inputs_answered()
    differ = []
    for data in cases:
        new = competitors.grid_dijkstra_solve(copy.deepcopy(data), BUDGET)
        ref = competitors.grid_dijkstra_solve_v100(copy.deepcopy(data), BUDGET)
        if _route(new) != _route(ref):
            differ.append((data["start"], data["goal"], _route(new), _route(ref)))
    assert len(cases) >= 58 and not differ, (
        f"OBSERVATION changed, not a guarantee failure: 1.1.0 traced another optimal route than 1.0.0 on "
        f"{len(differ)} grid(s): {differ[:3]}")


def test_grid_1_1_certificate_is_a_feasible_tight_potential_checked_here_independently():
    """The dual certificate, checked by this test's own loop (not the genome's verifier): integer, zero at the start,
    no edge into a passable cell rises by more than that cell's cost, tight at the goal, capped at the route cost."""
    for seed in (0, 4, 8):
        data, _, out = solved("grid_dijkstra", seed)
        grid, (sr, sc), (gr, gc) = data["grid"], data["start"], data["goal"]
        pi, cost = out["certificate"]["potential"], out["output"]["cost"]
        assert all(type(x) is int and 0 <= x <= cost for row in pi for x in row)
        assert pi[sr][sc] == 0 and pi[gr][gc] == cost == out["certificate"]["potential_cap"]
        rows, cols = len(grid), len(grid[0])
        for r in range(rows):
            for c in range(cols):
                for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                    if grid[r][c] and 0 <= rr < rows and 0 <= cc < cols and grid[rr][cc]:
                        assert pi[rr][cc] <= pi[r][c] + grid[rr][cc]


GRID_INPUTS = [
    {"grid": [[1, 2], [3, 4]], "start": [0, 0], "goal": [1, 1]},                        # valid, fast path
    {"grid": [[1, True], [3, 4]], "start": [0, 0], "goal": [1, 1]},                     # bool is not an int
    {"grid": [[1, 2.0], [3, 4]], "start": [0, 0], "goal": [1, 1]},
    {"grid": [[1, "2"], [3, 4]], "start": [0, 0], "goal": [1, 1]},
    {"grid": [[1, None], [3, 4]], "start": [0, 0], "goal": [1, 1]},
    {"grid": [[1, -1], [3, 4]], "start": [0, 0], "goal": [1, 1]},
    {"grid": [[1, 1001], [3, 4]], "start": [0, 0], "goal": [1, 1]},
    {"grid": [[1, 2 ** 70], [3, 4]], "start": [0, 0], "goal": [1, 1]},                 # beyond int64
    {"grid": [[1, -(2 ** 70)], [3, 4]], "start": [0, 0], "goal": [1, 1]},
    {"grid": [[1, 2], [3]], "start": [0, 0], "goal": [1, 0]},                           # ragged
    {"grid": [[1], [3, 4]], "start": [0, 0], "goal": [1, 0]},
    {"grid": [[], []], "start": [0, 0], "goal": [1, 0]},
    {"grid": [], "start": [0, 0], "goal": [0, 0]},
    {"grid": [[[1]]], "start": [0, 0], "goal": [0, 0]},                                 # one level too deep
    {"grid": [[1, 2], 3], "start": [0, 0], "goal": [0, 1]},
    {"grid": ((1, 2), (3, 4)), "start": [0, 0], "goal": [1, 1]},                        # a tuple is not a list
    {"grid": [(1, 2), (3, 4)], "start": [0, 0], "goal": [1, 1]},
    {"grid": [[1] * 201], "start": [0, 0], "goal": [0, 1]},                             # beyond GRID_MAX columns
    {"grid": [[1] for _ in range(201)], "start": [0, 0], "goal": [1, 0]},               # beyond GRID_MAX rows
    {"grid": [[1, 2], [3, 4]], "start": [0, 2], "goal": [1, 1]},                        # start off the grid
    {"grid": [[1, 2], [3, 4]], "start": [0], "goal": [1, 1]},
    {"grid": [[1, 2], [3, 4]], "start": [0, True], "goal": [1, 1]},
    {"grid": [[1, 2], [3, 4]], "start": "0,0", "goal": [1, 1]},
    {"grid": [[1, 2], [3, 4]], "start": [0, 0]},                                         # no goal
    {"grid": [[0, 2], [3, 4]], "start": [0, 0], "goal": [1, 1]},                        # blocked start
    {"grid": [[1, 2], [3, 0]], "start": [0, 0], "goal": [1, 1]},                        # blocked goal
    {"start": [0, 0], "goal": [1, 1]},                                                   # no grid
    [], "grid", None, 3,                                                                 # not an object
]


class _Row(list):
    """A list subclass: the reference contract (isinstance) accepts it; the fast path leaves it to the reference."""


@pytest.mark.parametrize("data", GRID_INPUTS + [{"grid": [_Row([1, 2]), _Row([3, 4])], "start": [0, 0],
                                                 "goal": [1, 1]}])
def test_the_vectorised_input_check_is_solvers_b_grid_contract_with_the_same_refusals(data):
    try:
        cells, rows, cols, s, t = solvers_b._grid(copy.deepcopy(data))
    except GenomeError as exc:
        with pytest.raises(GenomeError) as raised:
            competitors._gd_grid(copy.deepcopy(data))
        assert str(raised.value) == str(exc)
        for solve in (competitors.grid_dijkstra_solve, competitors.grid_dijkstra_solve_v100):
            with pytest.raises(GenomeError) as refused:
                solve(copy.deepcopy(data), BUDGET)
            assert str(refused.value) == str(exc)
        return
    costs, rows2, cols2, s2, t2 = competitors._gd_grid(copy.deepcopy(data))
    assert (costs.ravel().tolist(), rows2, cols2, s2, t2) == (cells, rows, cols, s, t)
    assert str(costs.dtype) == "int64" and costs.shape == (rows, cols)
    new = competitors.grid_dijkstra_solve(copy.deepcopy(data), BUDGET)
    _assert_1_0_guarantee(new, competitors.grid_dijkstra_solve_v100(copy.deepcopy(data), BUDGET), data)


def test_a_plain_grid_takes_the_vectorised_check_and_never_the_per_cell_one(monkeypatch):
    data, _ = dev("grid_dijkstra", 5)
    monkeypatch.setattr(solvers_b, "_grid", lambda d: pytest.fail("a plain grid must not take the per-cell check"))
    costs, rows, cols, s, t = competitors._gd_grid(data)
    assert costs.shape == (rows, cols) and costs.ravel().tolist() == [x for row in data["grid"] for x in row]
    assert competitors.grid_dijkstra_solve(data, BUDGET)["status"] == "ANSWER"


def test_the_grid_abstention_and_refusals_are_unchanged_from_1_0():
    big = copy.deepcopy(ABSTAIN["grid_dijkstra"])
    assert competitors.grid_dijkstra_solve(big, BUDGET) == competitors.grid_dijkstra_solve_v100(big, BUDGET)
    for data in INVALID["grid_dijkstra"]:
        with pytest.raises(GenomeError) as new:
            competitors.grid_dijkstra_solve(copy.deepcopy(data), BUDGET)
        with pytest.raises(GenomeError) as old:
            competitors.grid_dijkstra_solve_v100(copy.deepcopy(data), BUDGET)
        assert str(new.value) == str(old.value)


def test_the_version_bump_keeps_the_v3_verdict_as_negative_evidence_until_a_readmission():
    """grid_dijkstra 1.0.0 was measured EXPERIMENTAL (admission v3). 1.1.0 inherits no positive verdict, and the
    negative one stays on record (labelled as measured at 1.0.0) until a held-out re-admission at 1.1.0 replaces it."""
    import importlib.util
    index = json.loads((ROOT / "docs" / "evidence" / "greg-mind-evidence-index.json").read_text())
    record = index["genomes"]["grid_dijkstra"]
    assert record["status"] == "EXPERIMENTAL" and record["version"] == "1.0.0"
    assert record["evidence"] == competitors.V3 + "#genomes.grid_dijkstra"
    genome = library.genome("grid_dijkstra")
    assert genome.version == "1.1.0" and any(entry.startswith(competitors.V3) for entry in genome.lineage)
    data = {k: 0 for k in genome.required_inputs}
    row = next(c for c in compiler.candidates(data, compiler.CompetencyGeometry(), index)
               if c["method"] == "cognition.grid_dijkstra")
    assert row["status"] == "EXPERIMENTAL" and "stale_evidence" not in row
    spec = importlib.util.spec_from_file_location("_mind_status_grid", ROOT / "scripts" / "mind_status.py")
    status = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(status)
    entry = next(e for e in status.status()["mechanisms"] if e["id"] == "cognition.grid_dijkstra")
    assert entry["label"] == "UNRESOLVED" and entry["version_current"] == "1.1.0"
    assert entry["heldout"]["version_measured"] == "1.0.0" and entry["heldout"]["current"] is False
    assert "current 1.1.0" in entry["basis"] and "persists until a re-admission" in entry["basis"]


@pytest.mark.parametrize("scale,offset", ((1e-9, 0.0), (1e8, 0.0), (1.0, 999_999_000.0), (0.01, 1e6),
                                          (1.0, -999_999_000.0)))
def test_game_solve_verifies_at_any_payoff_magnitude(scale, offset):
    payoffs = [[((3 * i + 5 * j) % 7 - 3) * scale + offset for j in range(6)] for i in range(5)]
    out = competitors.game_lp_dual_solve({"payoffs": payoffs}, BUDGET)
    assert out["status"] == "ANSWER"
    assert all(competitors.game_lp_dual_verify({"payoffs": payoffs}, out["output"], out["certificate"]).values())


def _offset_games(seed, payoff, count=60):
    r, games = random.Random(seed), []                       # review seeds (3000-3999), never admission seeds
    for _ in range(count):
        m, n = r.randint(3, 10), r.randint(3, 10)
        games.append([[payoff(r) for _ in range(n)] for _ in range(m)])
    return games


OFFSETS = {"cents_around_a_million": (3004, lambda r: 1_000_000.0 + r.randint(-1, 1) / 100),
           "integers_near_a_billion": (3001, lambda r: 999_999_000.0 + r.randint(-10, 10))}


@pytest.mark.parametrize("name", sorted(OFFSETS))
def test_game_solve_answers_exact_equilibria_under_a_large_common_payoff_offset(name):
    """The duality-gap self-check ran on the raw payoffs, whose rounding scales with the offset rather than the
    range, and answered UNKNOWN on 37-44 of 200 such games although the LP on the rescaled game was exact."""
    for payoffs in _offset_games(*OFFSETS[name]):
        data = {"payoffs": payoffs}
        out = competitors.game_lp_dual_solve(data, BUDGET)
        assert out["status"] == "ANSWER", out["missing"]
        assert all(competitors.game_lp_dual_verify(data, out["output"], out["certificate"]).values())
        assert solvers_b.game_score(data, None, out["output"])["category"] == "correct"


def test_game_solve_never_states_a_value_its_verifier_refutes_when_payoffs_agree_to_nine_figures():
    """Payoffs 1e9 - k/8: a float near 1e9 holds about 1.2e-7, more than the verifier's 1e-7 x range allows; the
    solver states only what it can carry and answers UNKNOWN, with the reason, otherwise."""
    answered = unknown = 0
    for payoffs in _offset_games(3012, lambda r: 1e9 - r.randint(0, 3) * 0.125):
        data = {"payoffs": payoffs}
        out = competitors.game_lp_dual_solve(data, BUDGET)
        if out["status"] == "ANSWER":
            answered += 1
            assert all(competitors.game_lp_dual_verify(data, out["output"], out["certificate"]).values())
        else:
            unknown += 1
            assert out["status"] == "UNKNOWN" and out["output"] is None and "offset" in out["missing"][0]
            assert out["certificate"]["stated_error_over_range"] > competitors.GL_STATED
    assert answered and unknown


SUBNORMAL_GAME = [[-3.999995e-318, -4.999994e-318, -2.999996e-318, 1e-318],
                  [-3.999995e-318, -1e-318, 1.999997e-318, 2.999996e-318],
                  [3.999995e-318, 3.999995e-318, 1.999997e-318, 2.999996e-318],
                  [4.999994e-318, -3.999995e-318, 3.999995e-318, 1e-318],
                  [2.999996e-318, -3.999995e-318, -4.999994e-318, -3.999995e-318],
                  [-4.999994e-318, 1.999997e-318, 1e-318, -1.999997e-318]]


def test_game_solve_answers_unknown_when_subnormal_rounding_exceeds_the_verification_tolerance():
    """Payoff differences of about 1e-318 are subnormal floats, which the input contract accepts. The self-check
    on the rescaled game passed, the stated-error guard measured 0 in subnormal arithmetic against a threshold
    that underflowed to 0, and the verifier, whose 1e-7 x range tolerance is about one subnormal step, refuted the
    answer (9 of 30 games at 1e-318, 7 at 1e-320). The solver now answers only while that tolerance covers the
    verifier's worst rounding drift on the game's shape twice, (m + n + 2) steps of 2^-1074, and says why
    otherwise; it keeps answering where the drift fits (every game at 1e-300-1e-314 and most at 1e-316)."""
    out = competitors.game_lp_dual_solve({"payoffs": SUBNORMAL_GAME}, BUDGET)
    assert out["status"] == "UNKNOWN" and out["output"] is None and "subnormal" in out["missing"][0]
    assert 0 < out["certificate"]["payoff_range"] < out["certificate"]["range_floor"]
    answered = {}
    for unit in (1e-300, 1e-305, 1e-308, 1e-310, 1e-312, 1e-314, 1e-316, 1e-318, 1e-320):
        r, answered[unit] = random.Random(3500), 0           # a review seed
        for _ in range(30):
            m, n = r.randint(1, 6), r.randint(1, 6)
            data = {"payoffs": [[r.randint(-5, 5) * unit for _ in range(n)] for _ in range(m)]}
            out = competitors.game_lp_dual_solve(data, BUDGET)
            if out["status"] == "ANSWER":
                answered[unit] += 1
                assert all(competitors.game_lp_dual_verify(data, out["output"], out["certificate"]).values())
                assert solvers_b.game_score(data, None, out["output"])["category"] == "correct"
            else:
                assert out["status"] == "UNKNOWN" and out["output"] is None and "subnormal" in out["missing"][0]
    assert all(answered[unit] == 30 for unit in (1e-300, 1e-305, 1e-308, 1e-310, 1e-312, 1e-314)), answered
    assert answered[1e-316] >= 20 and answered[1e-318] < 30, answered


def _near_degenerate_games():
    """k/8 payoffs plus noise of up to 3e-8 (review seeds 3000-3099), and one offset game -1e6 + k/800."""
    games = [[[-999999.99625, -999999.99875, -999999.9925, -999999.99625, -999999.99625],
              [-999999.9975, -999999.99375, -999999.99, -999999.995, -999999.99125],
              [-999999.99625, -999999.9975, -999999.99875, -999999.99625, -999999.9975]]]
    for seed in range(3000, 3100):
        r = random.Random(seed)
        for eps in (0.0, 1e-9, 1e-8, 3e-8):
            m, n = r.randint(3, 8), r.randint(3, 8)
            games.append([[r.randint(0, 8) / 8 + r.uniform(-eps, eps) for _ in range(n)] for _ in range(m)])
    return games


@pytest.mark.parametrize("glop", (True, False))
def test_game_solve_answers_near_degenerate_games_its_engines_can_solve(glop, monkeypatch):
    """The self-check demands a duality gap of at most 1e-9 of the range, but both engines ran at their default
    feasibility tolerances (GLOP 1e-8, HiGHS 1e-7): on near-degenerate games both returned the same vertex with a
    gap of 1.2-2.5e-9, and the solver answered UNKNOWN on 7 of these 401 games, where the superseded game_minimax
    answered and both verifiers accepted. Each engine's first attempt (GLOP, or HiGHS alone as the fallback) runs
    at feasibility tolerances of 1e-10 and reaches the 1e-9 precision target on all of them."""
    if not glop:
        monkeypatch.setattr(competitors, "_gl_glop", lambda b, tolerance=None: None)
    for payoffs in _near_degenerate_games():
        data = {"payoffs": payoffs}
        out = competitors.game_lp_dual_solve(data, BUDGET)
        assert out["status"] == "ANSWER", (payoffs, out["missing"])
        assert out["certificate"]["engine"] == ("OR-Tools GLOP" if glop else "SciPy HiGHS")
        assert all(competitors.game_lp_dual_verify(data, out["output"], out["certificate"]).values())
        assert solvers_b.game_score(data, None, out["output"])["category"] == "correct"


def _tiny_entry_game(r, eps, size):
    """Most payoffs within eps of 0, about one in ten uniform in [-1, 1]: near-degenerate after rescaling."""
    m, n = r.randint(*size), r.randint(*size)
    return [[(r.uniform(-1, 1) if r.random() < 0.1 else r.uniform(-eps, eps)) for _ in range(n)] for _ in range(m)]


# Review seeds only: the 11 such games on which df122d0 answered UNKNOWN (seed 3415 drawn with salt 7; the others
# with salts 0, 1 and 3 for eps 1e-9, 1e-8 and 1e-9 on 20-60 actions a side). 3415 and 3165 were answered before
# df122d0 moved both engines to tight tolerances only.
TINY_ENTRY_GAMES = [(341507, 1e-9, (2, 15))] + [
    (seed * 1000 + salt, eps, size) for seed, salt, eps, size in
    ((3025, 0, 1e-9, (2, 15)), (3053, 1, 1e-8, (2, 15)), (3074, 1, 1e-8, (2, 15)), (3096, 1, 1e-8, (2, 15)),
     (3116, 1, 1e-8, (2, 15)), (3118, 1, 1e-8, (2, 15)), (3136, 0, 1e-9, (2, 15)), (3165, 3, 1e-9, (20, 60)),
     (3242, 1, 1e-8, (2, 15)), (3308, 1, 1e-8, (2, 15)))]


@pytest.mark.parametrize("seed,eps,size", TINY_ENTRY_GAMES)
def test_game_solve_answers_every_near_degenerate_game_whose_engine_answers_the_verifier_accepts(seed, eps, size):
    """A self-check gap of 1e-9 of the range, a hundredth of the verifier's tolerance, refused these games: every
    engine left a gap of 1.0e-9 to 1e-8 (feasibility tolerances apply to the engines' scaled problems and bound
    neither the gap nor success: at 1e-10 GLOP's gap grew on 3415 and 3165 and HiGHS failed outright), while the
    superseded game_minimax, with no self-check, answered each one and every verifier accepted. The self-check is
    now the verifier's own conditions at half their tolerances, each engine is tried at tight and then at default
    tolerances, and 1e-9 is a precision target that picks among passing attempts, never a refusal threshold."""
    data = {"payoffs": _tiny_entry_game(random.Random(seed), eps, size)}
    superseded = solvers_b.game_solve(data, BUDGET)
    assert superseded["status"] == "ANSWER"
    assert all(competitors.game_lp_dual_verify(data, superseded["output"], superseded["certificate"]).values())
    out = competitors.game_lp_dual_solve(data, BUDGET)
    assert out["status"] == "ANSWER", out["missing"]
    assert all(competitors.game_lp_dual_verify(data, out["output"], out["certificate"]).values())
    assert all(solvers_b.game_verify(data, out["output"], out["certificate"]).values())
    assert solvers_b.game_score(data, None, out["output"])["category"] == "correct"
    payoffs = [p for row in data["payoffs"] for p in row]
    spread = max(payoffs) - min(payoffs)
    assert out["certificate"]["duality_gap"] <= competitors.GL_MARGIN * competitors.GL_TOL * spread


def test_game_solve_never_answers_an_attempt_whose_supported_action_the_verifier_refutes(monkeypatch):
    """The self-check covered only the duality gap. An attempt that plays a strictly worse row with probability
    2e-6 (at least the verifier's support threshold) keeps the gap at 5e-10 of the range, within the old 1e-9
    check, and was answered; the verifier refuted it (that row concedes 2.5e-4 less than the best response). The
    self-check now applies every verifier condition, so the attempt is rejected and the next engine answers."""
    data = {"payoffs": [[1.0, 0.0], [0.0, 1.0], [0.49975, 0.49975]]}
    monkeypatch.setattr(competitors, "_gl_glop",
                        lambda b, tolerance=None: ([0.5 - 1e-6, 0.5 - 1e-6, 2e-6], [0.5, 0.5]))
    out = competitors.game_lp_dual_solve(data, BUDGET)
    assert out["status"] == "ANSWER" and out["certificate"]["engine"] == "SciPy HiGHS"
    assert out["certificate"]["engines_failed"] == ["OR-Tools GLOP"]
    assert all(competitors.game_lp_dual_verify(data, out["output"], out["certificate"]).values())
    monkeypatch.setattr(competitors, "_gl_highs", lambda b, tolerance=None: None)
    out = competitors.game_lp_dual_solve(data, BUDGET)
    assert out["status"] == "UNKNOWN" and out["output"] is None
    assert "row action" in out["certificate"]["failures"]["OR-Tools GLOP"]


# The four LP attempts game_lp_dual_solve makes, in order: name -> (engine function, feasibility tolerance).
GL_ATTEMPTS = {"OR-Tools GLOP": ("_gl_glop", competitors.GL_FEASIBILITY),
               "SciPy HiGHS": ("_gl_highs", competitors.GL_FEASIBILITY),
               "OR-Tools GLOP at its default tolerances": ("_gl_glop", None),
               "SciPy HiGHS at its default tolerances": ("_gl_highs", None)}


def _attempt_alone(monkeypatch, data, name):
    """game_lp_dual_solve with only the attempt ``name`` live (every other engine call returns nothing)."""
    live = GL_ATTEMPTS[name]
    for function in ("_gl_glop", "_gl_highs"):
        engine = getattr(competitors, function)
        monkeypatch.setattr(competitors, function,
                            lambda b, tolerance, f=function, e=engine: e(b, tolerance) if (f, tolerance) == live
                            else None)
    try:
        return competitors.game_lp_dual_solve(data, BUDGET)
    finally:
        monkeypatch.undo()


@pytest.mark.parametrize("seed,eps,size", [g for g in TINY_ENTRY_GAMES if g[0] in (3025000, 3053001)])
def test_game_certificate_calls_failed_only_the_attempts_that_failed(seed, eps, size, monkeypatch):
    """The answer's certificate listed every other attempt made as failed. On review seed 3053 (the verifier's
    tinysweep tiny8) HiGHS answered with a gap of 1.11e-9 of the range and engines_failed named both GLOP attempts
    and HiGHS at its defaults, though each passes the self-check alone (gaps 4.9e-9, 4.9e-9 and 9.5e-9); on 3025
    (tiny9) it named both GLOP attempts, which pass, beside HiGHS at 1e-10, which returns nothing. Each attempt now
    leaves one record, and every certificate field is derived from those records."""
    data = {"payoffs": _tiny_entry_game(random.Random(seed), eps, size)}
    cert = competitors.game_lp_dual_solve(data, BUDGET)["certificate"]
    for name in cert["engines_failed"]:
        assert _attempt_alone(monkeypatch, data, name)["status"] == "UNKNOWN", f"{name} passes on its own"
    assert set(cert["failures"]) == set(cert["engines_failed"])
    outcomes = [r["outcome"] for r in cert["attempts"]]
    assert outcomes.count("answered") == 1 and "passed, not selected" in outcomes
    for record in cert["attempts"]:
        alone = _attempt_alone(monkeypatch, data, record["engine"])
        if record["outcome"] == "failed":
            assert alone["status"] == "UNKNOWN" and record["engine"] in cert["engines_failed"]
            assert alone["certificate"]["failures"][record["engine"]] == record["reason"]
        else:
            assert alone["status"] == "ANSWER" and alone["certificate"]["engine"] == record["engine"]
            assert alone["certificate"]["duality_gap"] == record["duality_gap"]
            assert record["duality_gap"] >= cert["duality_gap"]
            assert (record["outcome"] == "answered") == (record["engine"] == cert["engine"])
    _json_clean(cert)


def test_game_certificate_records_a_passing_attempt_that_was_not_selected(monkeypatch):
    """GLOP's attempt passes the self-check with a gap of 1e-8 of the range, above the 1e-9 precision target, so
    HiGHS is tried and answers with a smaller gap. GLOP passed: it is recorded as passed and not selected, with its
    gap, and never as failed."""
    data = {"payoffs": [[1.0, 0.0], [0.0, 1.0]]}
    monkeypatch.setattr(competitors, "_gl_glop", lambda b, tolerance: ([0.5 + 1e-8, 0.5 - 1e-8], [0.5, 0.5]))
    out = competitors.game_lp_dual_solve(data, BUDGET)
    cert = out["certificate"]
    assert out["status"] == "ANSWER" and cert["engine"] == "SciPy HiGHS"
    assert cert["engines_failed"] == [] and cert["failures"] == {}
    [glop, highs] = cert["attempts"]
    assert glop["engine"] == "OR-Tools GLOP" and glop["outcome"] == "passed, not selected"
    assert glop["duality_gap"] == pytest.approx(1e-8, rel=1e-6)
    assert highs == {"engine": "SciPy HiGHS", "outcome": "answered", "duality_gap": cert["duality_gap"]}
    assert all(competitors.game_lp_dual_verify(data, out["output"], cert).values())


@pytest.mark.parametrize("glop", (([math.inf, 0.0], [0.5, 0.5]), ([1e308, 1e308], [1e308, 1e308]),
                                  ([0.5, 0.5, math.nan], [0.5, 0.5])))
def test_game_solve_never_answers_engine_output_that_is_not_finite(glop, monkeypatch):
    """Synthetic engine output (real GLOP and HiGHS return finite values on these bounded LPs). inf became NaN
    strategies and finite entries whose sum overflows became all-zero ones: both passed the self-check (NaN
    compares False; zero strategies have zero gap) and were answered, and the verifier refuted them
    (mixed_strategies). A NaN entry was silently clipped to 0, rewriting the engine's output. Non-finite output is
    now no strategy: the attempt is recorded failed and the next engine answers, or the solver says UNKNOWN."""
    x, y = glop
    data = {"payoffs": [[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]][:len(x)]}
    monkeypatch.setattr(competitors, "_gl_glop", lambda b, tolerance: (list(x), list(y)))
    out = competitors.game_lp_dual_solve(data, BUDGET)
    assert out["status"] == "ANSWER" and out["certificate"]["engine"] == "SciPy HiGHS"
    assert "not finite" in out["certificate"]["failures"]["OR-Tools GLOP"]
    assert all(competitors.game_lp_dual_verify(data, out["output"], out["certificate"]).values())
    monkeypatch.setattr(competitors, "_gl_highs", lambda b, tolerance: (list(x), list(y)))
    out = competitors.game_lp_dual_solve(data, BUDGET)
    assert out["status"] == "UNKNOWN" and out["output"] is None
    assert out["certificate"]["engines_failed"] == list(GL_ATTEMPTS)
    assert all(r["outcome"] == "failed" for r in out["certificate"]["attempts"])


@pytest.mark.parametrize("payoffs", ([[3.0]], [[1, 2, 3]], [[1], [2], [3]], [[5, 5], [5, 5]]))
def test_game_degenerate_shapes_verify(payoffs):
    out = competitors.game_lp_dual_solve({"payoffs": payoffs}, BUDGET)
    assert out["status"] == "ANSWER"
    assert all(competitors.game_lp_dual_verify({"payoffs": payoffs}, out["output"], out["certificate"]).values())


def test_game_falls_back_to_highs_and_reports_unknown_when_no_engine_answers(monkeypatch):
    data, truth = dev("game_lp_dual", 3)
    monkeypatch.setattr(competitors, "_gl_glop", lambda b, tolerance=None: None)
    out = competitors.game_lp_dual_solve(data, BUDGET)
    assert out["certificate"]["engine"] == "SciPy HiGHS" and out["certificate"]["engines_failed"] == ["OR-Tools GLOP"]
    assert all(competitors.game_lp_dual_verify(data, out["output"], out["certificate"]).values())
    assert solvers_b.game_score(data, truth, out["output"])["category"] == "correct"
    monkeypatch.setattr(competitors, "_gl_highs", lambda b, tolerance=None: None)
    out = competitors.game_lp_dual_solve(data, BUDGET)
    assert out["status"] == "UNKNOWN" and out["output"] is None and out["missing"]


@pytest.mark.parametrize("family", FAMILIES)
def test_score_categories(family):
    x = item(family)
    data, truth, out = solved(family, 1)
    good = x.score(data, truth, out["output"])
    assert good["category"] == "correct"
    assert x.score(data, truth, None)["category"] == "abstain"
    how = {"knapsack_bnb": "drop_item", "grid_dijkstra": "detour", "game_lp_dual": "uniform_row",
           "pid_simopt": None}[family]
    if how:
        wrong = x.score(data, truth, _forge(family, data, out, how)[0])
        assert wrong["category"] == "wrong" and wrong["quality"] < good["quality"]


# ------------------------------------------------------------------ the compiler route the promotion opens
@pytest.fixture
def superseded_index(tmp_path, monkeypatch):
    """The four superseded genomes recorded SUPERSEDED at their current versions (as the frozen evidence records
    them); the promoted genomes have no admission record (UNEVALUATED)."""
    index = tmp_path / "index.json"
    lib = library.executables()
    index.write_text(json.dumps({"genomes": {
        o: {"status": "SUPERSEDED", "version": lib[o].genome.version, "evidence": f"{FROZEN[o]}#genomes.{o}"}
        for o in SUPERSEDED.values()}, "recipes": {}, "routing": {}}))
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", index)
    return index


@pytest.mark.parametrize("family", FAMILIES)
def test_a_request_only_the_superseded_genome_fitted_now_has_a_route(superseded_index, family):
    data, _ = dev(family, 1)
    geometry = {"geometry": item(family).genome.epistemic_class}
    method, former = f"cognition.{family}", f"cognition.{SUPERSEDED[family]}"
    registry = registry_view()
    registry.set_state(former, "ATTACHED")             # attaching the superseded genome cannot route the request
    withheld = reason({"problem_id": "promoted", "compile": {"geometry": geometry, "data": data}}, registry=registry)
    assert withheld["state"] == "CAPABILITY_DEFICIT"
    assert {"method": former, "why": "frozen admission status SUPERSEDED"} in withheld["methods_rejected"]
    # the promoted genome now fits the same request: the deficit names it as registered but withheld, and the
    # superseding mechanism is not proposed for Genesis acquisition (it is already a registered genome)
    unserviceable = withheld["capability_deficit"]["verification"]["unserviceable"]
    assert {"method": method, "why": "state VERIFIED"} in unserviceable and "acquisition_candidates" not in withheld
    registry.set_state(method, "ATTACHED")             # evaluation-only founder pin, in memory; no body changed
    r = reason({"problem_id": "promoted", "compile": {"geometry": geometry, "data": data}}, registry=registry)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == method
    assert r["confidence_type"] == EVIDENCE[family] and r["intermediate_receipts"]
    assert r["authority_created"] is False and "acquisition_candidates" not in r
    assert item(family).score(data, dev(family, 1)[1], r["result"])["category"] == "correct"


def test_a_withheld_promoted_genome_is_asked_for_on_the_attach_contract(superseded_index):
    from greg import asks
    data, _ = dev("knapsack_bnb", 1)
    r = reason({"problem_id": "promoted-ask", "compile": {"geometry": {"geometry": "optimization"}, "data": data,
                                                          "execute": False}}, registry=registry_view())
    assert r["state"] == "CAPABILITY_DEFICIT"
    assert r["withheld_best_fit"] == {"method": "cognition.knapsack_bnb", "state": "state VERIFIED",
                                      "status": "UNEVALUATED", "served_by": None, "promotes": "cognition.dp_knapsack"}
    ask = r["founder_attach_ask"]
    assert ask["kind"] == "CAPABILITY_ATTACH" and ask["authority_requested"]["attach"] == "cognition.knapsack_bnb"
    assert ask["authority_requested"]["consequence_class"] == "read_only" and asks.screen(ask) == []
    assert ask["evidence"]["promotes"]["superseded_method"] == "cognition.dp_knapsack"
    assert ask["evidence"]["promotes"]["supersession_evidence"] == f"{competitors.V1}#genomes.dp_knapsack"


def test_a_promoted_genome_that_cannot_answer_leaves_the_mechanism_an_acquisition_candidate(superseded_index):
    """The superseded row named its promoted genome (promoted_as) even when that row was itself rejected, which
    removed the Genesis acquisition candidate and left a bare deficit. Here the promoted genome carries a
    hypothetical frozen REJECTED status of its own."""
    index = json.loads(superseded_index.read_text())
    index["genomes"]["knapsack_bnb"] = {"status": "REJECTED", "version": library.genome("knapsack_bnb").version,
                                        "evidence": "hypothetical"}
    superseded_index.write_text(json.dumps(index))
    data, _ = dev("knapsack_bnb", 1)
    r = reason({"problem_id": "promoted-rejected", "compile": {"geometry": {"geometry": "optimization"}, "data": data,
                                                               "execute": False}}, registry=registry_view())
    rejected = {"method": "cognition.knapsack_bnb", "why": "frozen admission status REJECTED"}
    assert r["state"] == "CAPABILITY_DEFICIT" and rejected in r["methods_rejected"]
    [candidate] = [c for c in r["acquisition_candidates"] if c["supersedes"] == "cognition.dp_knapsack"]
    assert candidate["mechanism"] == library.genome("dp_knapsack").competitor
    assert candidate["promoted_genome_rejected"] == rejected
    assert candidate["authority"].startswith("none")


def test_operators_that_named_the_superseded_genomes_also_prefer_their_promotions():
    by_id = {op.operator_id: op for op in compiler.OPERATORS}
    plan = {"requirements": [], "prefer": [], "notes": [], "dissent": [], "evaluate": []}
    by_id["game_theory"].apply(None, {}, plan)
    by_id["feedback_loops"].apply(None, {}, plan)
    assert {"cognition.game_lp_dual", "cognition.pid_simopt"} <= set(plan["prefer"])
