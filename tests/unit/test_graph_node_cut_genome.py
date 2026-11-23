"""graph_node_cut_exact: the exact minimum S-T vertex cut genome and its independent Menger verifier.

Development seeds 0-9 only (the genome's own generator); no admission held-out seed is generated here.
"""
import copy
import json
from pathlib import Path

import pytest

from greg.cognition import catalog
from greg.cognition.genomes import library, node_cut as N
from greg.cognition.genomes.contract import GenomeError

FAMILY = "graph_node_cut_exact"
ROOT = Path(__file__).resolve().parents[2]

# S -> {a, b} -> {c} -> T plus S -> d -> T : the minimum cut is {c, d} (k = 2)
SMALL = {"edges": [["S", "a"], ["S", "b"], ["a", "c"], ["b", "c"], ["c", "T"], ["S", "d"], ["d", "T"],
                   ["a", "b"]], "source": "S", "target": "T"}


def _solved(data):
    out = N.node_cut_solve(data, {})
    assert out["status"] == "ANSWER"
    return out["output"], out["certificate"]


def _refuted(data, output, certificate):
    return not all(N.node_cut_verify(data, output, certificate).values())


def test_genome_registers_withheld_on_the_one_catalog():
    item = library.executables()[FAMILY]
    g = item.genome
    assert g.operation == "min_vertex_cut" and g.required_inputs == ("edges", "source", "target")
    assert catalog.FAMILIES[FAMILY] == (3, ("min_vertex_cut",), ("optimization",), "genome_certificate", "networkx")
    assert catalog.initial_state(f"cognition.{FAMILY}") == "VERIFIED"          # registered, never auto-attached
    assert g.authority_ceiling == g.consequence_limit == "read_only"
    assert "flow_maxflow" in g.competitor and "milp" in g.competitor and "betweenness" in g.baseline
    assert g.known_failure_modes and g.counterindications and g.abstention_conditions


def test_bounds_are_not_flow_maxflows_and_match_the_latency_derivation():
    from greg.cognition.genomes import flow
    assert (N.MAX_NODES, N.MAX_EDGES) != (flow.MAX_NODES, flow.MAX_EDGES)
    path = ROOT / "docs" / "evidence" / "greg-node-cut-2026-10-21" / "latency.json"
    record = json.loads(path.read_text())
    assert record["derived_bounds"] == {"max_edges": N.MAX_EDGES, "max_vertices": N.MAX_NODES}
    assert record["declared_equals_derived"] is True
    assert record["latency_target_s"] == N.LATENCY_TARGET_S
    edges = [[f"v{i}", f"v{i + 1}"] for i in range(N.MAX_EDGES + 1)]
    with pytest.raises(GenomeError):
        N.node_cut_solve({"edges": edges, "source": "v0", "target": f"v{N.MAX_EDGES + 1}"}, {})


@pytest.mark.parametrize("seed", range(10))
def test_exact_and_independently_certified_on_dev_seeds(seed):
    item = library.executables()[FAMILY]
    data, truth = item.instance(seed)
    output, certificate = _solved(data)
    assert output["k"] == truth["k"] == len(output["cut"])
    assert all(N.node_cut_verify(data, output, certificate).values())
    assert item.score(data, truth, output)["category"] == "correct"
    ilp = N.competitor_ilp(data)
    assert ilp["k"] == truth["k"]                                         # independent exact competitor agrees
    assert item.instance(seed) == (data, truth)                           # deterministic generator


def test_small_known_answer_and_edge_cases():
    output, certificate = _solved(SMALL)
    assert output == {"cut": ["c", "d"], "k": 2}
    assert len(certificate["paths"]) == 2
    direct = {"edges": [["S", "T"], ["S", "a"], ["a", "T"]], "source": "S", "target": "T"}
    assert N.node_cut_solve(direct, {})["status"] == "ABSTAIN"            # no vertex cut exists
    apart = {"edges": [["S", "a"], ["T", "b"]], "source": "S", "target": "T"}
    out = N.node_cut_solve(apart, {})
    assert out["output"] == {"cut": [], "k": 0} and all(N.node_cut_verify(apart, out["output"],
                                                                          out["certificate"]).values())
    for bad in ({"edges": [["S", "S"]], "source": "S", "target": "T"},
                {"edges": [["S", "a", 1]], "source": "S", "target": "a"},
                {"edges": [["S", "a"]], "source": "S", "target": "S"},
                {"edges": [], "source": "S", "target": "T"}):
        with pytest.raises(GenomeError):
            N.node_cut_solve(bad, {})


# ------------------------------------------------------------------ mutation tests: the verifier refutes
def test_verifier_refutes_a_cut_that_is_too_large():
    output, certificate = _solved(SMALL)
    bigger = {"cut": sorted(output["cut"] + ["a"]), "k": 3}
    assert _refuted(SMALL, bigger, certificate)                          # 2 paths cannot certify 3
    # padding the certificate with a third path cannot rescue it: it must overlap or leave the input's edges
    padded = {**certificate, "paths": certificate["paths"] + [["S", "a", "c", "T"]]}
    assert _refuted(SMALL, bigger, padded)
    forged = {**certificate, "paths": certificate["paths"] + [["S", "a", "T"]]}   # a -> T is not an edge
    assert _refuted(SMALL, bigger, forged)


def test_verifier_refutes_a_cut_that_does_not_disconnect():
    output, certificate = _solved(SMALL)
    checks = N.node_cut_verify(SMALL, {"cut": ["c"], "k": 1}, {"paths": certificate["paths"][:1]})
    assert checks["cut_separates_s_from_t"] is False
    assert not all(checks.values())


def test_verifier_refutes_a_wrong_k():
    output, certificate = _solved(SMALL)
    for k in (1, 3, 0, -1):
        assert _refuted(SMALL, {"cut": output["cut"], "k": k}, certificate)
    assert _refuted(SMALL, {"cut": output["cut"], "k": True}, certificate)
    assert _refuted(SMALL, {"cut": output["cut"], "k": 2.0}, certificate)


def test_verifier_refutes_overlapping_or_invalid_paths():
    output, certificate = _solved(SMALL)
    via_c = [p for p in certificate["paths"] if "c" in p][0]
    overlapping = {**certificate, "paths": [via_c, list(via_c)]}          # the same interior twice
    assert N.node_cut_verify(SMALL, output, overlapping)["path_interiors_pairwise_disjoint"] is False
    shared = {**certificate, "paths": [["S", "a", "c", "T"], ["S", "b", "c", "T"]]}   # share c
    assert _refuted(SMALL, output, shared)
    loop = {**certificate, "paths": [["S", "a", "b", "c", "T"], ["S", "d", "T", "d", "T"]]}
    assert N.node_cut_verify(SMALL, output, loop)["every_path_is_simple"] is False
    wrong_end = {**certificate, "paths": [["S", "a", "c"], ["S", "d", "T"]]}
    assert _refuted(SMALL, output, wrong_end)
    reversed_path = {**certificate, "paths": [["T", "c", "a", "S"], ["S", "d", "T"]]}
    assert _refuted(SMALL, output, reversed_path)
    assert _refuted(SMALL, output, {})                                    # no certificate
    assert _refuted(SMALL, output, {"paths": "S,a,c,T"})


def test_verifier_refutes_malformed_output():
    _, certificate = _solved(SMALL)
    for bad in (None, [], "c,d", {"cut": "c,d", "k": 2}, {"cut": ["c", "c"], "k": 2}, {"cut": ["c", 4], "k": 2},
                {"cut": ["c", "d"]}, {"cut": ["c", "d"], "k": 2, "extra": 1}, {"k": 2}):
        assert _refuted(SMALL, bad, certificate)
    # vertices that are not intermediate vertices of the graph
    assert _refuted(SMALL, {"cut": ["S", "c"], "k": 2}, certificate)
    assert _refuted(SMALL, {"cut": ["c", "zzz"], "k": 2}, certificate)


def test_verifier_shares_no_code_with_the_engine():
    import inspect
    source = inspect.getsource(N.node_cut_verify) + inspect.getsource(N._reaches) + inspect.getsource(N._graph)
    assert "networkx" not in source and "nx." not in source


def test_mutation_sweep_on_dev_seeds_no_corruption_survives():
    """Every single-field corruption of a valid answer on dev seeds 0-9 is refuted."""
    item = library.executables()[FAMILY]
    survived = []
    for seed in range(10):
        data, _ = item.instance(seed)
        output, certificate = _solved(data)
        mids = sorted({v for e in data["edges"] for v in e} - {data["source"], data["target"]} - set(output["cut"]))
        mutants = [{"cut": output["cut"], "k": output["k"] + 1},
                   {"cut": sorted(output["cut"] + mids[:1]), "k": output["k"] + 1},
                   {"cut": output["cut"][1:], "k": output["k"] - 1}]
        for out in mutants:
            if not _refuted(data, out, certificate):
                survived.append((seed, out))
        paths = certificate["paths"]
        cert_mutants = [{"paths": paths[1:]}, {"paths": paths + [paths[0]]},
                        {"paths": [paths[0][:-1]] + paths[1:]}, {"paths": [paths[0][::-1]] + paths[1:]}]
        for cert in cert_mutants:
            if not _refuted(data, output, cert):
                survived.append((seed, cert))
    assert survived == []


# ------------------------------------------------------------------ the canonical path and the compiler
def test_runs_through_reason_withheld_then_attached():
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    data, truth = library.executables()[FAMILY].instance(3)
    withheld = reason({"problem_id": "nc", "operation": "min_vertex_cut", "data": data}, registry=registry)
    assert withheld["abstention_state"] == "CAPABILITY_DEFICIT"
    registry.set_state(f"cognition.{FAMILY}", "ATTACHED")                 # evaluation-only, in memory
    r = reason({"problem_id": "nc", "operation": "min_vertex_cut", "data": data}, registry=registry)
    assert r["abstention_state"] == "NONE" and r["output"]["k"] == truth["k"]
    assert r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" and r["authority_created"] is False
    assert r["proof_artifact"]["evidence_type"] == "optimality_certificate"


def test_library_check_refutes_a_forged_answer():
    data, _ = library.executables()[FAMILY].instance(4)
    out = library.run(FAMILY, data, {"latency_limit": 5, "compute_limit": 1000})
    assert all(library.check(FAMILY, data, out["output"], out["proof"]).values())
    forged = copy.deepcopy(out["output"])
    forged["k"] += 1
    assert not all(library.check(FAMILY, data, forged, out["proof"]).values())


def test_compiler_routes_the_vertex_cut_geometry_to_the_genome():
    from greg.cognition.compiler import CompetencyGeometry, candidates, evidence_index
    from greg.cognition.cortex import reason, registry_view
    data, truth = library.executables()[FAMILY].instance(0)
    rows = [r for r in candidates(data, CompetencyGeometry(), evidence_index()) if not r["rejected"]]
    assert [r["method"] for r in rows] == [f"cognition.{FAMILY}"]
    registry = registry_view()
    withheld = reason({"problem_id": "nc-c", "compile": {"geometry": {"consequence_class": "read_only"},
                                                         "data": data}}, registry=registry)
    assert withheld["method_or_composition_selected"] is None                 # withheld: no answer, no attach
    registry.set_state(f"cognition.{FAMILY}", "ATTACHED")
    r = reason({"problem_id": "nc-c", "compile": {"geometry": {"consequence_class": "read_only"}, "data": data}},
               registry=registry)
    assert r["method_or_composition_selected"] == f"cognition.{FAMILY}"
    assert r["selected_receipt"]["output"]["k"] == truth["k"]


def test_baselines_and_flow_competitor_behave_as_declared():
    item = library.executables()[FAMILY]
    for seed in range(10):
        data, truth = item.instance(seed)
        for baseline in (N.betweenness_greedy, N.degree_greedy):
            cut = baseline(data)["cut"]
            assert item.score(data, truth, {"cut": cut})["category"] in ("correct", "wrong")
            assert not N._reaches(N._graph(data)[0], data["source"], data["target"], frozenset(cut))
        if item.subregion(data) == "within_flow_maxflow_bounds":
            assert N.competitor_flow_maxflow(data)["k"] == truth["k"]
        else:
            with pytest.raises(GenomeError):                              # flow_maxflow's declared bounds
                N.competitor_flow_maxflow(data)
