"""Layer 3 evolutionary (genetic algorithm, MAP-Elites) and centrality (exact top-k betweenness) genomes: contract,
withheld registration, canonical path, Competency Compiler reachability, independent verification, refutation of
corrupted answers, references against independent methods, invalid input and evaluation budgets.

Development seeds 0-9 only; held-out admission seeds are never generated here.
"""
from __future__ import annotations

import copy
import itertools
import json
import math
import random

import pytest

from greg.cognition import catalog
from greg.cognition.genomes import centrality, evolutionary, library
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

ITEMS = {x.genome.family: x for x in evolutionary.INTELLIGENCES + centrality.INTELLIGENCES}
FAMILIES = tuple(sorted(ITEMS))
SPEC = {  # family: (layer, operation, epistemic class, evidence type, dependency)
    "evo_ga_factored": (3, "maximize_factored_binary", "optimization", "heuristic_trace", None),
    "evo_map_elites": (3, "quality_diversity_archive", "optimization", "heuristic_trace", None),
    "graph_betweenness_topk": (3, "betweenness_top_k", "optimization", "exact_calculation", "scipy"),
}
BUDGET = {"latency_s": 8.0, "compute": 100000}
_CACHE: dict = {}


def dev(family, seed=1):
    assert 0 <= seed < 10                                   # never a held-out seed
    key = (family, seed)
    if key not in _CACHE:
        _CACHE[key] = ITEMS[family].instance(seed)
    data, truth = _CACHE[key]
    return copy.deepcopy(data), truth


def solved(family, seed=1):
    key = ("solved", family, seed)
    if key not in _CACHE:
        data, _ = dev(family, seed)
        _CACHE[key] = ITEMS[family].solve(data, BUDGET)
    data, truth = dev(family, seed)
    return data, truth, copy.deepcopy(_CACHE[key])


def _ok(family, data, output, cert):
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
        assert g.baseline and g.competitor and x.subregion is not None and x.competitor_deployable
        assert "seeds 0-9 dev" in g.benchmark_suite


def test_registered_in_the_one_catalog_and_withheld():
    families = library.executables()
    for family in FAMILIES:
        assert families[family] is ITEMS[family]
        g = ITEMS[family].genome
        assert catalog.FAMILIES[family] == (g.layer, (g.operation,), (g.epistemic_class,), "genome_certificate",
                                            g.dependency)
        assert catalog.initial_state(f"cognition.{family}") == "VERIFIED"      # registered, never auto-attached


def test_modules_import_no_heavy_package_at_top_level():
    import ast
    import inspect
    for module in (evolutionary, centrality):
        tree = ast.parse(inspect.getsource(module))
        top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        names = {a.name.split(".")[0] for n in top for a in n.names} | {
            n.module.split(".")[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
        assert not names & {"numpy", "scipy", "networkx", "ortools", "z3"}


# ------------------------------------------------------------------ solve / verify on development seeds
@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("seed", range(10))
def test_solve_answers_and_its_answer_verifies(family, seed):
    data, truth, out = solved(family, seed)
    assert out["status"] == "ANSWER", out["missing"]
    assert len(json.dumps(out, allow_nan=False)) < 256 * 1024
    checks = ITEMS[family].verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    score = ITEMS[family].score(data, truth, out["output"])
    assert score["category"] == "correct"
    if family == "graph_betweenness_topk":
        assert score["quality"] == 1.0
    else:
        assert 0.0 < score["quality"] <= 1.0 + 1e-12


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_path_withholds_until_attached_and_creates_no_authority(family):
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    data, truth = dev(family, 3)
    request = {"problem_id": f"evo-bc-{family}", "operation": SPEC[family][1], "data": data,
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
    data, truth = dev(family, 1)
    cls = SPEC[family][2]
    request = {"problem_id": f"evo-bc-compile-{family}", "compile": {"geometry": {"geometry": cls}, "data": data}}
    registry = registry_view()
    withheld = reason(request, registry=registry)
    assert withheld["state"] == "CAPABILITY_DEFICIT"
    assert withheld["withheld_best_fit"]["method"] == f"cognition.{family}"
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == f"cognition.{family}"
    assert r["authority_created"] is False
    assert ITEMS[family].score(data, truth, r["result"])["category"] == "correct"


# ------------------------------------------------------------------ genetic algorithm
def test_ga_verifier_refutes_a_changed_bit_a_false_fitness_and_an_overrun_budget():
    data, _, out = solved("evo_ga_factored", 2)
    o, c = out["output"], out["certificate"]
    flipped = {**o, "bits": [1 - o["bits"][0]] + o["bits"][1:]}
    assert not _ok("evo_ga_factored", data, flipped, c)
    assert not _ok("evo_ga_factored", data, {**o, "fitness": o["fitness"] + 1}, c)
    assert not _ok("evo_ga_factored", data, {**o, "bits": o["bits"][:-1]}, c)
    assert not _ok("evo_ga_factored", data, o, {**c, "evaluations_used": data["evaluations"] + 1})
    assert not _ok("evo_ga_factored", data, {**o, "bits": [2] + o["bits"][1:]}, c)


@pytest.mark.parametrize("arm", ["solve", "baseline", "competitor"])
def test_ga_arms_answer_with_a_true_fitness_and_the_ga_spends_exactly_its_budget(arm):
    from greg.cognition.genomes.evolutionary import _factored, _fitness
    data, truth = dev("evo_ga_factored", 1)
    item = ITEMS["evo_ga_factored"]
    out = item.solve(data, BUDGET)["output"] if arm == "solve" else getattr(item, arm)(data)
    assert out is not None and item.score(data, truth, out)["category"] == "correct"
    assert _fitness(_factored(data)[1], out["bits"]) == out["fitness"]
    if arm == "solve":
        assert item.solve(data, BUDGET)["certificate"]["evaluations_used"] == data["evaluations"]


def test_adjacent_dynamic_program_matches_brute_force():
    r = random.Random("test:adjacent-dp")
    for n, k in ((7, 2), (8, 3), (9, 1)):
        factors = [((i,) + tuple((i + d) % n for d in range(1, k + 1)),
                    tuple(r.randint(0, 50) for _ in range(2 ** (k + 1)))) for i in range(n)]
        brute = max(evolutionary._fitness(factors, list(bits)) for bits in itertools.product((0, 1), repeat=n))
        assert evolutionary._adjacent_optimum(n, factors) == brute


def test_trap_optimum_is_all_ones_and_deceptive_for_hill_climbing():
    table = evolutionary._trap_table(5)
    assert table[31] == 1000 and table[0] == 800 and max(table[:31]) == 800
    data, truth = dev("evo_ga_factored", 1)                  # seed 1 is trap_tight
    assert truth["kind"] == "trap_tight"
    ones = [1] * data["num_bits"]
    n, factors, _, _ = evolutionary._factored(data)
    assert evolutionary._fitness(factors, ones) == truth["optimum"]


# ------------------------------------------------------------------ MAP-Elites
def test_qd_verifier_refutes_a_moved_cell_a_duplicate_cell_and_a_false_score():
    data, _, out = solved("evo_map_elites", 2)
    o, c = out["output"], out["certificate"]
    e0 = o["elites"][0]
    moved = copy.deepcopy(o)
    moved["elites"][0]["cell"] = [e0["cell"][0], (e0["cell"][1] + 1) % data["grid"]]
    assert not _ok("evo_map_elites", data, moved, c)
    dup = copy.deepcopy(o)
    dup["elites"].append(copy.deepcopy(e0))
    dup["qd_score"] += e0["quality"]
    assert not _ok("evo_map_elites", data, dup, c)
    assert not _ok("evo_map_elites", data, {**o, "qd_score": o["qd_score"] + 1e-6}, c)
    better = copy.deepcopy(o)
    better["elites"][0]["quality"] = min(1.0, e0["quality"] + 0.01)
    assert not _ok("evo_map_elites", data, better, c)


def test_reachable_cells_bound_every_archive_and_the_inner_hole_is_excluded():
    for seed in range(10):
        data, truth, out = solved("evo_map_elites", seed)
        assert len(out["output"]["elites"]) <= truth["reachable_cells"] <= data["grid"] ** 2
    data, truth = dev("evo_map_elites", 3)                     # seed 3: one long link, a hole at the centre
    assert truth["kind"] == "one_long" and truth["reachable_cells"] < data["grid"] ** 2


@pytest.mark.parametrize("arm", ["baseline", "competitor"])
def test_qd_arms_are_true_archives_within_the_budget(arm):
    data, truth = dev("evo_map_elites", 0)
    item = ITEMS["evo_map_elites"]
    out = getattr(item, arm)(data)
    assert item.score(data, truth, out)["category"] == "correct"
    assert len(out["elites"]) <= data["evaluations"]


# ------------------------------------------------------------------ centrality
@pytest.mark.parametrize("seed", range(4))
def test_reference_and_sparse_brandes_agree_with_networkx(seed):
    import networkx as nx
    data, truth = dev("graph_betweenness_topk", seed)
    nodes, index, pairs, k = centrality._graph(data)
    g = nx.Graph()
    g.add_nodes_from(range(len(nodes)))
    g.add_edges_from(pairs)
    expected = nx.betweenness_centrality(g, normalized=False)
    sparse = centrality._brandes_sparse(len(nodes), pairs)
    for i in range(len(nodes)):
        assert truth["betweenness"][i] == pytest.approx(expected[i], rel=1e-9, abs=1e-9)
        assert sparse[i] == pytest.approx(expected[i], rel=1e-9, abs=1e-9)


def test_bc_verifier_refutes_a_wrong_value_and_a_swapped_in_lower_node():
    data, truth, out = solved("graph_betweenness_topk", 2)
    o, c = out["output"], out["certificate"]
    assert not _ok("graph_betweenness_topk", data, {**o, "betweenness": [o["betweenness"][0] * 1.001]
                                                    + o["betweenness"][1:]}, c)
    nodes, index, pairs, k = centrality._graph(data)
    ref = truth["betweenness"]
    outside = min((v for v in nodes if v not in o["top"]), key=lambda v: ref[index[v]])
    swapped = {"top": o["top"][:-1] + [outside], "betweenness": o["betweenness"][:-1] + [ref[index[outside]]]}
    assert ref[index[outside]] < o["betweenness"][-1]
    assert not _ok("graph_betweenness_topk", data, swapped, c)
    assert not _ok("graph_betweenness_topk", data, {**o, "top": o["top"][:-1] + [o["top"][0]]}, c)


def test_degree_baseline_claims_no_values_and_is_scored_on_its_set():
    data, truth = dev("graph_betweenness_topk", 0)
    out = ITEMS["graph_betweenness_topk"].baseline(data)
    assert out["betweenness"] is None
    s = ITEMS["graph_betweenness_topk"].score(data, truth, out)
    assert s["category"] == "wrong" and 0.0 <= s["quality"] <= 1.0


# ------------------------------------------------------------------ invalid input, malformed output, determinism
@pytest.mark.parametrize("family,bad", [
    ("evo_ga_factored", {"num_bits": 3, "factors": [{"vars": [0, 0], "table": [1, 2, 3, 4]}], "evaluations": 9,
                         "seed": 1}),
    ("evo_ga_factored", {"num_bits": 3, "factors": [{"vars": [0, 5], "table": [1, 2, 3, 4]}], "evaluations": 9,
                         "seed": 1}),
    ("evo_ga_factored", {"num_bits": 3, "factors": [{"vars": [0, 1], "table": [1, 2, 3]}], "evaluations": 9,
                         "seed": 1}),
    ("evo_ga_factored", {"num_bits": 3, "factors": [{"vars": [0], "table": [1, -2]}], "evaluations": 9, "seed": 1}),
    ("evo_map_elites", {"link_lengths": [1.0], "grid": 8, "evaluations": 100, "seed": 1}),
    ("evo_map_elites", {"link_lengths": [1.0, float("nan")], "grid": 8, "evaluations": 100, "seed": 1}),
    ("evo_map_elites", {"link_lengths": [1.0, 1.0], "grid": 1, "evaluations": 100, "seed": 1}),
    ("graph_betweenness_topk", {"graph_edges": [["a", "a"]], "top_k": 1}),
    ("graph_betweenness_topk", {"graph_edges": [["a", "b"], ["b", "a"]], "top_k": 1}),
    ("graph_betweenness_topk", {"graph_edges": [["a", "b"]], "top_k": 3}),
])
def test_invalid_input_raises_a_genome_error(family, bad):
    with pytest.raises(GenomeError):
        ITEMS[family].solve(bad, BUDGET)


@pytest.mark.parametrize("family", FAMILIES)
def test_malformed_outputs_are_refuted_not_raised(family):
    data, _ = dev(family, 1)
    for junk in (None, 3, [], {}, {"x": None}, "answer"):
        assert not all(ITEMS[family].verify(data, junk, {}).values())


def test_abstention_beyond_the_native_size():
    big = {"num_bits": evolutionary.GA_NATIVE_BITS + 1, "factors": [{"vars": [0], "table": [0, 1]}],
           "evaluations": 10, "seed": 0}
    assert evolutionary.ga_solve(big, BUDGET)["status"] == "ABSTAIN"


def test_instances_and_answers_are_deterministic_by_seed():
    for family in FAMILIES:
        a, b = ITEMS[family].instance(4)[0], ITEMS[family].instance(4)[0]
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
        if family != "graph_betweenness_topk":
            assert ITEMS[family].solve(a, BUDGET)["output"] == ITEMS[family].solve(b, BUDGET)["output"]
    assert math.isfinite(solved("evo_map_elites", 4)[2]["output"]["qd_score"])
