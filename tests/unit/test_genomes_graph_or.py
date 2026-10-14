"""Layer 3 pack A IntelligenceGenomes (assignment, matching, critical path, min-cost flow): contract, canonical path,
independent verification, refutation of corrupted outputs, invalid input, abstention and scoring.

Development seeds (0-9) and review seeds (3000-3999) only; held-out admission seeds are never generated here.
"""
from __future__ import annotations

import copy
import json
import math
import random

import pytest

from greg.cognition import catalog
from greg.cognition.genomes import graph_or, library
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

FAMILIES = ("assignment_lsa", "graph_matching", "critical_path", "min_cost_flow")
OPS = {"assignment_lsa": "min_cost_assignment", "graph_matching": "max_weight_matching",
       "critical_path": "project_critical_path", "min_cost_flow": "min_cost_flow_plan"}
EVIDENCE = {"assignment_lsa": "optimality_certificate", "graph_matching": "exact_calculation",
            "critical_path": "exact_calculation", "min_cost_flow": "optimality_certificate"}
DEPS = {"assignment_lsa": "scipy", "graph_matching": "networkx", "critical_path": None, "min_cost_flow": "ortools"}
BUDGET = {"latency_s": 5.0, "compute": 100000}
_CACHE: dict = {}


def item(family):
    return {x.genome.family: x for x in graph_or.INTELLIGENCES}[family]


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
        assert value is None or isinstance(value, (str, int, bool))


# ------------------------------------------------------------------ genome contract
def test_genomes_validate_and_are_layer_three():
    assert sorted(x.genome.family for x in graph_or.INTELLIGENCES) == sorted(FAMILIES)
    for x in graph_or.INTELLIGENCES:
        g = x.genome
        assert isinstance(g, IntelligenceGenome) and g.validate() is g
        assert g.layer == 3 and g.buildability == "BUILDABLE_NOW" and g.standalone_decision
        assert g.version == "1.0.0" and g.operation == OPS[g.family] and g.epistemic_class == "optimization"
        assert g.evidence_type == EVIDENCE[g.family] and g.dependency == DEPS[g.family]
        assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
        assert g.authority_ceiling == "read_only" and g.consequence_limit == "read_only"
        assert x.subregion is not None and x.competitor_deployable


def test_library_and_catalog_register_pack_a_withheld():
    families = library.executables()
    for family in FAMILIES:
        g = families[family].genome
        assert g.operation == OPS[family]
        assert library.catalog_families()[family] == (3, (OPS[family],), ("optimization",), "genome_certificate",
                                                      DEPS[family])
        assert catalog.FAMILIES[family] == library.catalog_families()[family]
        assert catalog.initial_state(f"cognition.{family}") == "VERIFIED"      # registered, never auto-attached


def test_module_top_level_imports_no_heavy_packages():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(graph_or))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top for a in n.names} | {n.module.split(".")[0] for n in top
                                                                      if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"numpy", "scipy", "networkx", "ortools", "z3"}


# ------------------------------------------------------------------ solve / verify
@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("seed", range(10))
def test_solve_returns_a_compact_json_answer_that_verifies(family, seed):
    data, truth, out = solved(family, seed)
    assert set(out) == {"output", "certificate", "status", "missing"} and out["status"] == "ANSWER"
    _json_clean(out["output"])
    _json_clean(out["certificate"])
    assert len(json.dumps(out, allow_nan=False)) < 64 * 1024
    json.dumps(data, allow_nan=False)
    checks = item(family).verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    assert item(family).score(data, truth, out["output"]) == {"quality": 1.0, "category": "correct"}


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_adapter_runs_and_checks(family):
    data, _ = dev(family, 2)
    result = library.run(family, data, {"latency_limit": 10})
    assert result["status"] == "ANSWER" and result["proof"]["evidence_type"] == EVIDENCE[family]
    assert result["formal_validity"] == "VALID_CONDITIONAL_ON_MODEL"
    checks = library.check(family, data, result["output"], result["proof"])
    assert all(checks.values()), checks


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_path_withholds_until_attached_and_creates_no_authority(family):
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    data, truth = dev(family, 3)
    request = {"problem_id": f"pack-a-{family}", "operation": OPS[family], "data": data,
               "geometry": {"latency_limit": 30}}
    assert reason(request, registry=registry)["abstention_state"] == "CAPABILITY_DEFICIT"
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["abstention_state"] == "NONE" and r["proof_type"] == "genome_certificate"
    assert r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" and r["authority_created"] is False
    assert item(family).score(data, truth, r["output"])["category"] == "correct"


# ------------------------------------------------------------------ competency compiler (evaluation only)
@pytest.mark.parametrize("family", FAMILIES)
def test_the_competency_compiler_routes_a_request_by_its_inputs_once_the_family_is_attached(family, tmp_path,
                                                                                           monkeypatch):
    """Evaluation only: the attach is an in-memory registry_view state (no body, journal or founder pin), and no
    frozen admission evidence exists for pack A (an empty evidence index: every genome is UNEVALUATED)."""
    from greg.cognition import compiler
    from greg.cognition.cortex import reason, registry_view
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")
    data, truth = dev(family, 1)
    request = {"problem_id": f"pack-a-compile-{family}",
               "compile": {"geometry": {"geometry": "optimization"}, "data": data}}
    registry = registry_view()
    withheld = reason(request, registry=registry)
    assert withheld["state"] == "CAPABILITY_DEFICIT" and withheld["method_or_composition_selected"] is None
    assert withheld["withheld_best_fit"]["method"] == f"cognition.{family}"
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == f"cognition.{family}"
    assert r["methods_considered"] == [f"cognition.{family}"] and r["selection_level"] == "admission_status"
    assert r["derived_geometry"] == {"declared": "optimization", "fits_by_inputs": ["optimization"], "agrees": True}
    assert r["proof_artifacts"] == [{"type": "genome_certificate", "evidence_type": EVIDENCE[family]}]
    assert r["authority_state"] == "EXISTING_KERNEL_GATE_REQUIRED" and r["authority_created"] is False
    assert item(family).score(data, truth, r["result"]) == {"quality": 1.0, "category": "correct"}


def test_a_cost_matrix_declared_as_an_estimate_is_dissent_and_a_deficit_not_a_silent_reroute(tmp_path, monkeypatch):
    from greg.cognition import compiler
    from greg.cognition.cortex import reason, registry_view
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")
    registry = registry_view()
    registry.set_state("cognition.assignment_lsa", "ATTACHED")
    data, _ = dev("assignment_lsa", 1)
    r = reason({"problem_id": "pack-a-misdeclared", "compile": {"geometry": {"geometry": "estimate"}, "data": data}},
               registry=registry)
    assert r["state"] == "CAPABILITY_DEFICIT" and r["derived_geometry"]["agrees"] is False
    assert any("the inputs fit methods of ['optimization']" in d for d in r["dissent"])


# ------------------------------------------------------------------ corrupted outputs
def _worse_assignment(data, out):
    """Swap the columns of the first pair of rows whose exchange strictly raises the cost; keep the claim
    self-consistent."""
    c, col = data["cost_matrix"], list(out["output"]["assignment"])
    for i in range(len(col)):
        for k in range(i + 1, len(col)):
            if c[i][col[k]] + c[k][col[i]] > c[i][col[i]] + c[k][col[k]]:
                col[i], col[k] = col[k], col[i]
                return {"assignment": col, "cost": sum(c[r][col[r]] for r in range(len(col)))}
    raise AssertionError("no strictly worse exchange")


def _rerouted_flow(data, out):
    """Move one unit from a regular arc onto its parallel premium arc: still feasible, strictly costlier."""
    arcs, flow = data["arcs"], list(out["output"]["flow"])
    for k, (u, v, _, cost) in enumerate(arcs):
        if flow[k] > 0:
            for j, (x, y, cap, dearer) in enumerate(arcs):
                if (x, y) == (u, v) and dearer > cost and flow[j] < cap:
                    flow[k] -= 1
                    flow[j] += 1
                    return {"feasible": True, "flow": flow, "cost": sum(f * a[3] for f, a in zip(flow, arcs))}
    raise AssertionError("no reroutable unit")


def _corrupt(family, data, out):
    """A self-consistent, well-formed but suboptimal answer per family (the certificate is left as solved)."""
    o, c = copy.deepcopy(out["output"]), copy.deepcopy(out["certificate"])
    if family == "assignment_lsa":
        o = _worse_assignment(data, out)
    elif family == "graph_matching":              # drop the heaviest pair: still a matching, strictly lighter
        weight = {frozenset(e[:2]): e[2] for e in data["weighted_edges"]}
        o["matching"].remove(max(o["matching"], key=lambda p: weight[frozenset(p)]))
        o["weight"] = sum(weight[frozenset(p)] for p in o["matching"])
    elif family == "critical_path":               # a real source-to-sink chain that is not the longest
        chain = graph_or.cpm_greedy_chain(data)
        assert chain["makespan"] < o["makespan"]
        o.update(chain)
    else:
        o = _rerouted_flow(data, out)
    return o, c


CORRUPT_SEED = {"assignment_lsa": 1, "graph_matching": 1, "critical_path": 1, "min_cost_flow": 0}


@pytest.mark.parametrize("family", FAMILIES)
def test_verify_refutes_a_corrupted_output(family):
    data, truth, out = solved(family, CORRUPT_SEED[family])
    o, c = _corrupt(family, data, out)
    checks = item(family).verify(data, o, c)
    assert not all(checks.values()), checks
    assert item(family).score(data, truth, o)["category"] == "wrong"


def _forge(family, data, out, how):
    o, c = copy.deepcopy(out["output"]), copy.deepcopy(out["certificate"])
    if family == "assignment_lsa" and how == "duplicate_column":
        o["assignment"][1] = o["assignment"][0]
    elif family == "assignment_lsa" and how == "understated_cost":
        o["cost"] -= 1
    elif family == "assignment_lsa" and how == "potentials_not_tight":
        c["column_potentials"][o["assignment"][0]] -= 1
    elif family == "assignment_lsa" and how == "potentials_infeasible":
        c["row_potentials"][0] += 1
    elif family == "assignment_lsa" and how == "certificate_for_a_worse_assignment":
        o = _worse_assignment(data, out)
    elif family == "graph_matching" and how == "non_edge_pair":
        present = {frozenset(e[:2]) for e in data["weighted_edges"]}
        names = sorted({x for e in data["weighted_edges"] for x in e[:2]})
        free = [x for x in names if all(x not in p for p in o["matching"])]
        if len(free) < 2 or frozenset(free[:2]) in present:
            free = ["ghost_a", "ghost_b"]
        o["matching"].append(free[:2])
    elif family == "graph_matching" and how == "shared_vertex":         # a second edge at a matched vertex
        o["matching"].append(next(sorted(e[:2]) for p in o["matching"] for e in data["weighted_edges"]
                                  if p[0] in e[:2] and sorted(e[:2]) != p))
    elif family == "graph_matching" and how == "overstated_weight":
        o["weight"] += 1
    elif family == "graph_matching" and how == "certificate_counts":
        c["matched_pairs"] += 1
    elif family == "critical_path" and how == "certificate_counts":
        c["critical_activities"] -= 1
    elif family == "critical_path" and how == "understated_makespan":
        o["makespan"] -= 1
    elif family == "critical_path" and how == "reversed_path":
        o["critical_path"] = list(reversed(o["critical_path"]))
    elif family == "critical_path" and how == "float_shifted":
        name = next(a for a, f in o["total_float"].items() if f > 0)
        o["total_float"][name] -= 1
    elif family == "critical_path" and how == "path_stops_short":
        o["critical_path"] = o["critical_path"][:-1]
    elif family == "min_cost_flow" and how == "capacity_exceeded":
        o["flow"][0] = data["arcs"][0][2] + 1
    elif family == "min_cost_flow" and how == "conservation_broken":
        k = next(i for i, f in enumerate(o["flow"]) if f > 0)
        o["flow"][k] -= 1
        o["cost"] -= data["arcs"][k][3]
    elif family == "min_cost_flow" and how == "false_infeasible":
        o = {"feasible": False, "flow": None, "cost": None}
        c = {"cut": sorted(n for n, s in data["supplies"].items() if s > 0)}
    elif family == "min_cost_flow" and how == "potentials_shifted":
        k = next(i for i, f in enumerate(o["flow"]) if f < data["arcs"][i][2])        # a forward residual arc
        c["potentials"][data["arcs"][k][1]] += 10 ** 7
    elif family == "min_cost_flow" and how == "rerouted":
        o = _rerouted_flow(data, out)
    else:
        raise AssertionError((family, how))
    return o, c


FORGERIES = [("assignment_lsa", "duplicate_column"), ("assignment_lsa", "understated_cost"),
             ("assignment_lsa", "potentials_not_tight"), ("assignment_lsa", "potentials_infeasible"),
             ("assignment_lsa", "certificate_for_a_worse_assignment"),
             ("graph_matching", "non_edge_pair"), ("graph_matching", "shared_vertex"),
             ("graph_matching", "overstated_weight"), ("graph_matching", "certificate_counts"),
             ("critical_path", "certificate_counts"),
             ("critical_path", "understated_makespan"), ("critical_path", "reversed_path"),
             ("critical_path", "float_shifted"), ("critical_path", "path_stops_short"),
             ("min_cost_flow", "capacity_exceeded"), ("min_cost_flow", "conservation_broken"),
             ("min_cost_flow", "false_infeasible"), ("min_cost_flow", "potentials_shifted"),
             ("min_cost_flow", "rerouted")]


@pytest.mark.parametrize("family,how", FORGERIES)
def test_verify_refutes_further_forgeries(family, how):
    data, _, out = solved(family, CORRUPT_SEED[family])
    o, c = _forge(family, data, out, how)
    checks = item(family).verify(data, o, c)
    assert not all(checks.values()), (how, checks)


def test_the_assignment_certificate_alone_refutes_a_tampered_dual_but_the_independent_check_still_passes():
    data, _, out = solved("assignment_lsa", 1)
    o, c = _forge("assignment_lsa", data, out, "potentials_infeasible")
    checks = graph_or.assignment_verify(data, o, c)
    assert checks["certificate_potentials_dual_feasible_and_tight"] is False
    assert checks["optimal_by_independent_hungarian_dual"] is True              # the answer itself is optimal


def test_the_flow_certificate_and_the_independent_bellman_ford_judge_separately():
    data, _, out = solved("min_cost_flow", 0)
    o, c = _forge("min_cost_flow", data, out, "potentials_shifted")
    checks = graph_or.mcf_verify(data, o, c)
    assert not checks["certificate_potentials_give_nonnegative_reduced_costs"]
    assert checks["optimal_by_independent_residual_bellman_ford"]
    o = _rerouted_flow(data, out)
    checks = graph_or.mcf_verify(data, o, out["certificate"])
    assert checks["capacity_respected"] and checks["supplies_met_and_flow_conserved"] and checks["cost_recomputed"]
    assert not checks["optimal_by_independent_residual_bellman_ford"]


# ------------------------------------------------------------------ independence of the verifiers
def _boom(*args, **kwargs):
    raise AssertionError("a verifier called its solver's library")


def test_verifiers_never_call_the_solver_library(monkeypatch):
    import networkx
    import scipy.optimize
    from ortools.graph.python import max_flow, min_cost_flow
    outs = {(family, seed): solved(family, seed) for family in FAMILIES for seed in (1, 2)}
    monkeypatch.setattr(scipy.optimize, "linear_sum_assignment", _boom)
    monkeypatch.setattr(networkx, "max_weight_matching", _boom)
    monkeypatch.setattr(graph_or, "_cpm_passes", _boom)
    monkeypatch.setattr(graph_or, "_spfa_potentials", _boom)
    monkeypatch.setattr(min_cost_flow, "SimpleMinCostFlow", _boom)
    monkeypatch.setattr(max_flow, "SimpleMaxFlow", _boom)
    for (family, seed), (data, _, out) in outs.items():
        checks = item(family).verify(data, out["output"], out["certificate"])
        assert all(checks.values()), (family, seed, checks)


def test_a_corrupted_solver_engine_is_caught(monkeypatch):
    import networkx
    import numpy as np
    import scipy.optimize
    # assignment: an engine returning the identity permutation cannot be given potentials (negative exchange
    # cycle), so the solver reports UNKNOWN instead of a false certificate
    data, _ = dev("assignment_lsa", 1)
    monkeypatch.setattr(scipy.optimize, "linear_sum_assignment",
                        lambda a: (np.arange(a.shape[0]), np.arange(a.shape[0])))
    assert graph_or.assignment_solve(data, BUDGET)["status"] == "UNKNOWN"
    # matching: an engine returning the greedy matching is refuted by the independent optimum
    data, _ = dev("graph_matching", 1)
    greedy = graph_or.matching_greedy(data)["matching"]
    monkeypatch.setattr(networkx, "max_weight_matching", lambda g, **kw: {tuple(p) for p in greedy})
    out = graph_or.matching_solve(data, BUDGET)
    checks = graph_or.matching_verify(data, out["output"], out["certificate"])
    assert checks["weight_recomputed"] and checks["certificate_counts_recomputed"]
    assert checks["optimal_by_odd_set_lp_dual"] is False                 # refuted by a checked dual, not a vote
    # critical path: a backward pass that lets every activity finish one unit later is refuted by the
    # independent recomputation of the floats
    real = graph_or._cpm_passes
    monkeypatch.setattr(graph_or, "_cpm_passes", lambda ids, dur, preds: (
        lambda es, lf, mk, succ: (es, {a: lf[a] + 1 for a in lf}, mk, succ))(*real(ids, dur, preds)))
    data, _ = dev("critical_path", 1)
    out = graph_or.cpm_solve(data, BUDGET)
    checks = graph_or.cpm_verify(data, out["output"], out["certificate"])
    assert checks["makespan_is_the_longest_path"] and not checks["total_floats_recomputed"]


# ------------------------------------------------------------------ independent methods agree
def _small_graph(r, n, p, bipartite=False):
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            if (not bipartite or (i < n // 2) != (j < n // 2)) and r.random() < p:
                edges.append([f"v{i}", f"v{j}", r.randint(1, 30)])
    return edges or [["v0", "v1", 1]]


@pytest.mark.parametrize("seed", range(3000, 3012))
def test_matching_exact_methods_agree_on_review_graphs(seed):
    import networkx as nx
    r = random.Random(seed)
    for bipartite in (False, True):
        edges = graph_or._matching_graph({"weighted_edges": _small_graph(r, r.randint(4, 14), 0.4, bipartite)})
        g = nx.Graph()
        g.add_weighted_edges_from(edges)
        blossom = sum(g[u][v]["weight"] for u, v in nx.max_weight_matching(g))
        exhaustive, milp = graph_or._matching_exhaustive(edges), graph_or._matching_milp(edges)
        assert blossom == exhaustive == milp
        assert graph_or._matching_odd_set_dual(edges) in (None, exhaustive)      # certified, or no claim at all
        assert graph_or._matching_odd_set_dual(edges, lower=exhaustive) in (None, exhaustive)
        colour = graph_or._two_colouring(edges)
        assert (colour is not None) or not bipartite
        if colour is not None:
            assert graph_or._matching_bipartite_dual(edges, colour) == exhaustive


def test_general_graphs_are_certified_by_a_checked_odd_set_dual_on_every_dev_seed():
    routes = {}
    for seed in range(10):
        data, truth, out = solved("graph_matching", seed)
        edges = graph_or._matching_graph(data)
        _, routes[seed] = graph_or.matching_optimum(edges, lower=out["output"]["weight"])
        if routes[seed] == "odd_set_lp_dual":
            assert graph_or._matching_odd_set_dual(edges) == truth["optimum"]        # also closes without a hint
    assert {s for s, r in routes.items() if r == "bipartite_lp_dual"} == {2, 6}
    assert {s for s, r in routes.items() if r == "odd_set_lp_dual"} == {0, 1, 3, 4, 5, 7, 8, 9}


def test_the_odd_set_dual_refuses_an_uncovered_edge_and_a_lighter_matching_is_refuted_with_the_optimum():
    edges = [("a", "b", 5), ("b", "c", 5), ("a", "c", 5), ("c", "d", 1)]
    ends, weights = [(0, 1), (1, 2), (0, 2), (2, 3)], [5, 5, 5, 1]
    member = [[0], [0], [0], []]
    sets = [frozenset((0, 1, 2))]
    # y = 0 and z = 5 on {a, b, c} covers the triangle but not c-d: the exact check claims no bound
    assert graph_or._checked_dual_objective(ends, weights, sets, 4, [0, 0, 0, 0], [5]) is None
    # from that float dual the bound is built feasible: y_c is raised by c-d's shortfall of 1, so 5 * 1 + 1 = 6,
    # the optimum (a-b plus c-d); y_c = 1 in the float dual gives the same checked bound
    assert graph_or._exact_dual_bound(ends, weights, member, sets, 4, [0, 0, 0, 0, -5]) == 6
    assert graph_or._exact_dual_bound(ends, weights, member, sets, 4, [0, 0, -1, 0, -5]) == 6
    assert graph_or._matching_odd_set_dual(edges) == 6
    assert graph_or._matching_odd_set_dual(edges, lower=5) == 6                 # a lighter claim cannot close it


def _no_float_report(*args, **kwargs):
    raise AssertionError("optimality rested on a floating-point solver's report")


def test_when_the_cutting_planes_do_not_close_optimality_is_not_established_and_highs_is_never_consulted(
        monkeypatch):
    import scipy.optimize
    data, _, out = solved("graph_matching", 1)
    lighter, _ = _corrupt("graph_matching", data, out)
    monkeypatch.setattr(scipy.optimize, "milp", _no_float_report)
    monkeypatch.setattr(graph_or, "_matching_milp", _no_float_report)
    monkeypatch.setattr(graph_or, "MATCH_CUT_ROUNDS", 0)
    for answer in (out["output"], lighter):                 # neither certified nor refuted: not within bounds
        checks = graph_or.matching_verify(data, answer, out["certificate"])
        assert checks["independent_check_within_bounds"] is False
        assert not any(k.startswith("optimal_by_") for k in checks)
    with pytest.raises(GenomeError, match="not established"):
        graph_or.matching_instance(1)                       # a benchmark truth is never left uncertified


def _regression_graph(name):
    import pathlib
    path = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "graph_matching_highs_regressions.json"
    record = json.loads(path.read_text())[name]
    return {"weighted_edges": record["weighted_edges"]}, record


def test_a_lighter_matching_that_highs_reports_optimal_is_refuted_and_the_blossom_answer_is_certified(monkeypatch):
    """Review seed 3248 (71 vertices, 363 edges, weights 0-3 or near 10^6): HiGHS branch-and-cut reported its
    incumbent, one unit lighter than the optimum, as optimal, and the verifier that trusted that report certified
    the lighter matching and refuted the blossom answer."""
    import scipy.optimize
    data, record = _regression_graph("seed_3248_mixed")
    edges = graph_or._matching_graph(data)
    assert graph_or._two_colouring(edges) is None and len(graph_or._vertices(edges)) <= graph_or.MATCH_NATIVE_VERTICES
    lighter = {"matching": record["highs_incumbent"], "weight": record["highs_incumbent_weight"]}
    assert graph_or._matching_weight(edges, lighter["matching"]) == record["optimum"] - 1
    out = graph_or.matching_solve(data, BUDGET)
    assert out["output"]["weight"] == record["optimum"] == record["cpsat_weight"]
    monkeypatch.setattr(scipy.optimize, "milp", _no_float_report)
    right = graph_or.matching_verify(data, out["output"], out["certificate"])
    assert all(right.values()) and right["optimal_by_odd_set_lp_dual"] is True, right
    certificate = dict(out["certificate"], matched_pairs=len(lighter["matching"]))
    wrong = graph_or.matching_verify(data, lighter, certificate)
    assert wrong["certificate_counts_recomputed"] and wrong["optimal_by_odd_set_lp_dual"] is False, wrong
    assert graph_or.matching_optimum(edges) == (record["optimum"], "odd_set_lp_dual")    # closes unhinted too


def test_a_right_answer_with_weights_near_a_million_is_not_refuted():
    """Review seed 3456 (65 vertices, 398 edges, weights 999000-1000000): HiGHS's correct objective carried
    1.15e-6 of float error, an absolute 1e-6 test threw it away and the blossom answer was refuted."""
    data, record = _regression_graph("seed_3456_big")
    out = graph_or.matching_solve(data, BUDGET)
    assert out["output"]["weight"] == record["optimum"] == record["cpsat_weight"]
    checks = graph_or.matching_verify(data, out["output"], out["certificate"])
    assert all(checks.values()) and checks["optimal_by_odd_set_lp_dual"] is True, checks


def test_the_highs_cross_check_weighs_its_solution_in_integers_without_an_absolute_objective_tolerance(
        monkeypatch):
    import types

    import numpy as np
    import scipy.optimize
    data, record = _regression_graph("seed_3456_big")
    edges = graph_or._matching_graph(data)
    out = graph_or.matching_solve(data, BUDGET)
    chosen = {frozenset(p) for p in out["output"]["matching"]}
    x = np.array([1.0 if frozenset((u, v)) in chosen else 0.0 for u, v, _ in edges])
    # HiGHS's own report on this graph: status 0 and an objective 1.15e-6 away from the integer weight
    report = types.SimpleNamespace(status=0, x=x, fun=-(record["optimum"] + 1.15e-6))
    monkeypatch.setattr(scipy.optimize, "milp", lambda *args, **kwargs: report)
    assert graph_or._matching_milp(edges) == record["optimum"]
    report.x = np.ones(len(edges))                          # not a matching: no value is reported
    assert graph_or._matching_milp(edges) is None


def _review_graph(seed, weight):
    """The review's random general graph: 17-80 vertices, n to min(400, n(n-1)/2) edges, review seeds only."""
    assert 3000 <= seed < 4000
    r = random.Random(seed)
    n = r.randint(17, 80)
    m = r.randint(n, min(400, n * (n - 1) // 2))
    seen, edges = set(), []
    while len(edges) < m:
        i, j = r.sample(range(n), 2)
        if frozenset((i, j)) not in seen:
            seen.add(frozenset((i, j)))
            edges.append([f"v{i}", f"v{j}", weight(r)])
    return graph_or._matching_graph({"weighted_edges": edges})


@pytest.mark.parametrize("seed, weight", [
    (3413, lambda r: r.choice((1, 1_000_000))),            # two levels: many equally good fractional optima
    (3441, lambda r: r.randint(999_000, 1_000_000)),
    (3248, lambda r: r.choice((r.randint(0, 3), r.randint(999_990, 1_000_000)))),
    (3005, lambda r: 1)])                                   # unit weights: maximum cardinality
def test_the_checked_odd_set_dual_closes_on_degenerate_and_large_weights(seed, weight):
    import networkx as nx
    edges = _review_graph(seed, weight)
    g = nx.Graph()
    g.add_weighted_edges_from(edges)
    blossom = sum(g[u][v]["weight"] for u, v in nx.max_weight_matching(g))
    assert graph_or._two_colouring(edges) is None
    assert graph_or._matching_odd_set_dual(edges, lower=blossom) == blossom
    assert graph_or._matching_odd_set_dual(edges) == blossom
    assert graph_or._matching_odd_set_dual(edges, lower=blossom - 1) == blossom      # a lighter claim is caught


def _cut(cap, side):
    return sum(c for u in side for v, c in cap[u].items() if v not in side)


@pytest.mark.parametrize("seed", range(3400, 3440))
def test_gomory_hu_tree_and_padberg_rao_separation_match_brute_force(seed):
    import itertools
    r = random.Random(seed)
    n = r.randint(3, 9)
    cap = {i: {} for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if r.random() < 0.5:
                cap[i][j] = cap[j][i] = r.choice((0.5, 1.0, 0.25, r.random()))
    parent, value = graph_or._gomory_hu(cap, n)
    for i in range(1, n):                       # each tree edge's fundamental cut is a minimum i-parent cut
        subtree, stack = set(), [i]
        while stack:
            a = stack.pop()
            subtree.add(a)
            stack.extend(k for k in range(1, n) if parent[k] == a)
        others = [v for v in range(n) if v not in (i, parent[i])]
        best = min(_cut(cap, set(c) | {i}) for k in range(len(others) + 1) for c in itertools.combinations(others, k))
        assert math.isclose(_cut(cap, subtree), value[i], abs_tol=1e-9) and math.isclose(best, value[i], abs_tol=1e-9)
    # separation on a point of the degree polytope finds a violated odd set exactly when one exists
    n = r.randint(3, 11)
    ends = [(i, j) for i in range(n) for j in range(i + 1, n) if r.random() < 0.45] or [(0, 1)]
    x = [r.choice((0.0, 0.5, 1.0, r.random())) for _ in ends]
    degree = [0.0] * n
    for k, (i, j) in enumerate(ends):
        degree[i] += x[k]
        degree[j] += x[k]
    x = [v / max(1.0, degree[i], degree[j]) for v, (i, j) in zip(x, ends)]

    def mass(s):
        return sum(v for v, (i, j) in zip(x, ends) if i in s and j in s)
    violated = [s for k in range(3, n + 1, 2) for s in itertools.combinations(range(n), k)
                if mass(set(s)) > (k - 1) / 2 + 1e-6]
    found = graph_or._violated_odd_sets(ends, x, n)
    assert all(len(s) % 2 and mass(s) > (len(s) - 1) / 2 for s in found)
    assert bool(found) == bool(violated)


@pytest.mark.parametrize("seed", range(3100, 3110))
def test_independent_hungarian_matches_scipy_with_negative_and_rectangular_costs(seed):
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    r = random.Random(seed)
    n = r.randint(1, 12)
    m = n + r.randint(0, 6)
    c = [[r.randint(-50, 50) for _ in range(m)] for _ in range(n)]
    u, v, col, optimum = graph_or.hungarian(c)
    rows, cols = linear_sum_assignment(np.array(c))
    assert optimum == int(np.array(c)[rows, cols].sum()) == sum(u) + sum(v)
    assert graph_or._dual_feasible(c, u, v) and len(set(col)) == n
    out = graph_or.assignment_solve({"cost_matrix": c}, BUDGET)
    assert all(graph_or.assignment_verify({"cost_matrix": c}, out["output"], out["certificate"]).values())


@pytest.mark.parametrize("seed", range(10))
def test_critical_path_three_methods_agree(seed):
    data, truth, out = solved("critical_path", seed)
    assert out["output"]["makespan"] == truth["makespan"] == graph_or.cpm_networkx(data)["makespan"]
    assert graph_or.cpm_cpsat_makespan(data) == truth["makespan"]


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("seed", range(10))
def test_competitors_are_exact_on_dev_seeds(family, seed):
    data, truth = dev(family, seed)
    assert item(family).score(data, truth, item(family).competitor(data))["category"] == "correct"


def test_the_critical_path_competitor_keeps_a_zero_duration_final_milestone():
    data = {"activities": [{"id": "build", "duration": 5}, {"id": "handover", "duration": 0, "after": ["build"]}]}
    truth = {"makespan": 5, "earliest_start": {"build": 0, "handover": 5}, "total_float": {"build": 0, "handover": 0}}
    out = graph_or.cpm_networkx(data)
    assert out == {"makespan": 5, "critical_path": ["build", "handover"]}
    assert graph_or.cpm_score(data, truth, out)["category"] == "correct"
    assert graph_or.cpm_networkx({"activities": [{"id": "only", "duration": 0}]})["critical_path"] == ["only"]


def test_the_critical_path_competitor_is_exact_on_review_seeds():
    wrong = []
    for seed in range(3000, 3200):              # includes 3020, 3026, 3070 and 3124, which end in a milestone
        data, truth = item("critical_path").instance(seed)
        if item("critical_path").score(data, truth, graph_or.cpm_networkx(data))["category"] != "correct":
            wrong.append(seed)
    assert wrong == []


def test_the_matching_benchmark_suite_states_the_sizes_its_generator_produces():
    import re
    suite = item("graph_matching").genome.benchmark_suite
    most = int(re.search(r"at most (\d+) vertices", suite).group(1))
    low, high = map(int, re.search(r"\((\d+)-(\d+) vertices on development", suite).groups())
    sizes = {seed: len(graph_or._vertices(graph_or._matching_graph(item("graph_matching").instance(seed)[0])))
             for seed in (*range(10), 3750, 3209)}          # 3750: 18 vertices (bipartite); 3209: 66 (odd clusters)
    assert sizes[3750] == low == 18 and sizes[3209] == high == most == 66
    assert all(low <= v <= high for v in sizes.values())


def test_rectangular_assignment_competitor_routes_through_min_cost_flow():
    data, truth = dev("assignment_lsa", 4)
    assert graph_or.assignment_subregion(data) == "rectangular"
    assert graph_or.assignment_score(data, truth, graph_or.assignment_ortools(data))["category"] == "correct"


# ------------------------------------------------------------------ infeasible flow
def test_an_infeasible_network_is_an_answer_with_a_cut_and_is_scored_against_infeasible_truth():
    data = {"arcs": [["a", "m", 10, 1], ["m", "b", 4, 1], ["a", "c", 3, 2]],
            "supplies": {"a": 10, "b": -8, "c": -2}}
    out = graph_or.mcf_solve(data, BUDGET)
    assert out["status"] == "ANSWER" and out["output"] == {"feasible": False, "flow": None, "cost": None}
    assert out["certificate"]["supply_inside_cut"] > out["certificate"]["capacity_leaving_cut"]
    assert all(graph_or.mcf_verify(data, out["output"], out["certificate"]).values())
    assert graph_or.mcf_lp_optimum(*graph_or._network(data)) is None
    assert graph_or.mcf_score(data, {"optimum": None}, out["output"])["category"] == "correct"
    assert graph_or.mcf_networkx(data)["feasible"] is False
    forged_cut = dict(out["certificate"], cut=["b"])
    assert not graph_or.mcf_verify(data, out["output"], forged_cut)["cut_certifies_infeasibility"]
    claimed = {"feasible": True, "flow": [6, 4, 2], "cost": 16}            # does not meet b's demand
    checks = graph_or.mcf_verify(data, claimed, {})
    assert not checks["supplies_met_and_flow_conserved"]
    assert graph_or.mcf_score(data, {"optimum": None}, claimed)["category"] == "wrong"


def test_negative_cost_arcs_are_solved_exactly_and_the_greedy_baseline_abstains():
    data, truth, out = solved("min_cost_flow", 2)
    assert graph_or.mcf_subregion(data) == "rebates" and any(a[3] < 0 for a in data["arcs"])
    assert out["output"]["cost"] == truth["optimum"]
    assert graph_or.mcf_greedy(data) is None
    assert graph_or.mcf_score(data, truth, None)["category"] == "abstain"


# ------------------------------------------------------------------ invalid input
INVALID = {
    "assignment_lsa": [{"cost_matrix": [[1, 2], [3]]}, {"cost_matrix": [[1], [2]]},
                       {"cost_matrix": [[1.5, 2]]}, {"cost_matrix": [[True, 2]]},
                       {"cost_matrix": [[10 ** 7, 2]]}, {"cost_matrix": []}],
    "graph_matching": [{"weighted_edges": [["a", "a", 1]]}, {"weighted_edges": [["a", "b", 1], ["b", "a", 2]]},
                       {"weighted_edges": [["a", "b", -1]]}, {"weighted_edges": [["a", 3, 1]]},
                       {"weighted_edges": [["a", "b"]]}, {"weighted_edges": []}],
    "critical_path": [{"activities": [{"id": "a", "duration": 1, "after": ["b"]},
                                      {"id": "b", "duration": 1, "after": ["a"]}]},
                      {"activities": [{"id": "a", "duration": 1, "after": ["z"]}]},
                      {"activities": [{"id": "a", "duration": 1}, {"id": "a", "duration": 2}]},
                      {"activities": [{"id": "a", "duration": -1}]},
                      {"activities": [{"id": "a", "duration": 1, "lag": 2}]},
                      {"activities": [{"id": "a", "duration": 1, "after": ["a"]}]}],
    "min_cost_flow": [{"arcs": [["a", "b", 5, 1]], "supplies": {"a": 3, "b": -2}},
                      {"arcs": [["a", "a", 5, 1]], "supplies": {"a": 0}},
                      {"arcs": [["a", "b", -5, 1]], "supplies": {"a": 1, "b": -1}},
                      {"arcs": [["a", "b", 5, 1.5]], "supplies": {"a": 1, "b": -1}},
                      {"arcs": [["a", "b", 5, 1]], "supplies": {}},
                      {"arcs": [["a", "b", 5]], "supplies": {"a": 1, "b": -1}}],
}


@pytest.mark.parametrize("family", FAMILIES)
def test_invalid_input_raises_genome_error(family):
    for data in INVALID[family]:
        with pytest.raises(GenomeError):
            item(family).solve(data, BUDGET)
        with pytest.raises(GenomeError):
            item(family).verify(data, {}, {})


@pytest.mark.parametrize("family", FAMILIES)
def test_non_object_data_is_invalid_input(family):
    x = item(family)
    for bad in ([], "payload", None, 3):
        with pytest.raises(GenomeError):
            x.solve(bad, BUDGET)
        with pytest.raises(GenomeError):
            x.verify(bad, {}, {})


@pytest.mark.parametrize("family", FAMILIES)
def test_verify_does_not_crash_on_malformed_output_or_certificate(family):
    data, _, out = solved(family, 1)
    x = item(family)
    assert isinstance(x.verify(data, out["output"], ["not", "a", "certificate"]), dict)
    for bad in (None, [], "x", {"assignment": "x", "matching": 3, "critical_path": 3, "makespan": "9",
                                "feasible": "yes", "flow": {}}):
        checks = x.verify(data, bad, out["certificate"])
        assert isinstance(checks, dict) and not all(checks.values())


# ------------------------------------------------------------------ abstention
ABSTAIN = {
    "assignment_lsa": {"cost_matrix": [list(range(101))]},
    "graph_matching": {"weighted_edges": [[f"v{i}", f"v{i + 1}", 1] for i in range(81)]},
    "critical_path": {"activities": [{"id": f"a{i}", "duration": 1} for i in range(1001)]},
    "min_cost_flow": {"arcs": [[f"n{i}", f"n{i + 1}", 1, 1] for i in range(200)], "supplies": {"n0": 1, "n200": -1}},
}


@pytest.mark.parametrize("family", FAMILIES)
def test_abstains_outside_native_competence_and_the_verifier_refuses_unbounded_work(family):
    data = copy.deepcopy(ABSTAIN[family])
    out = item(family).solve(data, BUDGET)
    assert out["status"] == "ABSTAIN" and out["output"] is None and out["missing"]
    _json_clean(out["certificate"])
    claim = {"assignment_lsa": {"assignment": [0], "cost": 0},
             "graph_matching": {"matching": [["v0", "v1"]], "weight": 1},
             "critical_path": {"makespan": 1, "critical_path": ["a0"], "earliest_start": {}, "total_float": {}},
             "min_cost_flow": {"feasible": True, "flow": [1] * 200, "cost": 200}}[family]
    checks = item(family).verify(data, claim, {})
    assert checks.get("independent_check_within_bounds") is False and not all(checks.values())


# ------------------------------------------------------------------ scoring
@pytest.mark.parametrize("family", FAMILIES)
def test_score_categories_and_severity(family):
    x = item(family)
    data, truth, out = solved(family, CORRUPT_SEED[family])
    best = x.score(data, truth, out["output"])
    abstain = x.score(data, truth, None)
    o, _ = _corrupt(family, data, out)
    suboptimal = x.score(data, truth, o)
    false_claim, _ = _forge(family, data, out, {"assignment_lsa": "understated_cost",
                                                "graph_matching": "overstated_weight",
                                                "critical_path": "understated_makespan",
                                                "min_cost_flow": "conservation_broken"}[family])
    false = x.score(data, truth, false_claim)
    assert best == {"quality": 1.0, "category": "correct"} and abstain["category"] == "abstain"
    assert suboptimal["category"] == false["category"] == "wrong"
    assert false["quality"] < abstain["quality"] < suboptimal["quality"] < best["quality"]


def test_candidates_beat_or_match_their_baselines_on_every_dev_seed():
    for family in FAMILIES:
        x = item(family)
        for seed in range(10):
            data, truth, out = solved(family, seed)
            assert x.score(data, truth, out["output"])["quality"] >= x.score(data, truth, x.baseline(data))["quality"]


def test_baselines_are_wrong_on_most_dev_seeds():
    for family in FAMILIES:
        x = item(family)
        wrong = sum(x.score(*dev(family, seed), x.baseline(dev(family, seed)[0]))["category"] != "correct"
                    for seed in range(10))
        assert wrong >= 6, family


def test_solves_are_deterministic_and_subregions_vary():
    for family in FAMILIES:
        data, _, first = solved(family, 2)
        assert item(family).solve(copy.deepcopy(data), BUDGET) == first
        assert len({item(family).subregion(dev(family, seed)[0]) for seed in range(10)}) >= 3
