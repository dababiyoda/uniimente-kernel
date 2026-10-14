"""Promoted competitors: the mechanisms that superseded admitted genomes, routable as genomes of their own.

Contract shape, reuse of the superseded genome's geometry, independent verification, abstention, scoring and the
compiler route a request takes now that the superseded genome is excluded. Development seeds only (0-9); the
held-out admission seeds are never generated here, and nothing here runs or freezes an admission.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
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
        assert g.layer == 3 and g.buildability == "BUILDABLE_NOW" and g.standalone_decision and g.version == "1.0.0"
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


@pytest.mark.parametrize("scale", (1e-9, 1e8))
def test_game_solve_verifies_at_any_payoff_magnitude(scale):
    payoffs = [[((3 * i + 5 * j) % 7 - 3) * scale for j in range(6)] for i in range(5)]
    out = competitors.game_lp_dual_solve({"payoffs": payoffs}, BUDGET)
    assert out["status"] == "ANSWER"
    assert all(competitors.game_lp_dual_verify({"payoffs": payoffs}, out["output"], out["certificate"]).values())


@pytest.mark.parametrize("payoffs", ([[3.0]], [[1, 2, 3]], [[1], [2], [3]], [[5, 5], [5, 5]]))
def test_game_degenerate_shapes_verify(payoffs):
    out = competitors.game_lp_dual_solve({"payoffs": payoffs}, BUDGET)
    assert out["status"] == "ANSWER"
    assert all(competitors.game_lp_dual_verify({"payoffs": payoffs}, out["output"], out["certificate"]).values())


def test_game_falls_back_to_highs_and_reports_unknown_when_no_engine_answers(monkeypatch):
    data, truth = dev("game_lp_dual", 3)
    monkeypatch.setattr(competitors, "_gl_glop", lambda b: None)
    out = competitors.game_lp_dual_solve(data, BUDGET)
    assert out["certificate"]["engine"] == "SciPy HiGHS" and out["certificate"]["engines_failed"] == ["OR-Tools GLOP"]
    assert all(competitors.game_lp_dual_verify(data, out["output"], out["certificate"]).values())
    assert solvers_b.game_score(data, truth, out["output"])["category"] == "correct"
    monkeypatch.setattr(competitors, "_gl_highs", lambda b: None)
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


def test_operators_that_named_the_superseded_genomes_also_prefer_their_promotions():
    by_id = {op.operator_id: op for op in compiler.OPERATORS}
    plan = {"requirements": [], "prefer": [], "notes": [], "dissent": [], "evaluate": []}
    by_id["game_theory"].apply(None, {}, plan)
    by_id["feedback_loops"].apply(None, {}, plan)
    assert {"cognition.game_lp_dual", "cognition.pid_simopt"} <= set(plan["prefer"])
