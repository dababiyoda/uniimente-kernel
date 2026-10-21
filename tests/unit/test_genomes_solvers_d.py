"""Layer 3 batch D (MaxSAT, bin packing, reconciliation QP, communities, multistart L-BFGS-B) and the Layer 2 one-step
weighted crowd vote: contract, withheld registration, canonical path, Competency Compiler reachability, independent
verification, refutation of corrupted answers and forged certificates, invalid input and scoring.

Development seeds 0-9 and this lane's declared review range 9300-9399 only; held-out admission seeds are never
generated here.
"""
from __future__ import annotations

import copy
import json
import math

import pytest

from greg.cognition import catalog
from greg.cognition.genomes import crowd, library, solvers_d
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

ITEMS = {x.genome.family: x for x in solvers_d.INTELLIGENCES + crowd.INTELLIGENCES}
FAMILIES = tuple(sorted(ITEMS))
SPEC = {  # family: (layer, operation, epistemic class, evidence type, dependency)
    "maxsat_cpsat": (3, "weighted_maxsat", "constraint_feasibility", "optimality_certificate", "ortools"),
    "binpack_cpsat": (3, "bin_packing_min_bins", "optimization", "optimality_certificate", "ortools"),
    "reconcile_qp": (3, "reconcile_measurements", "estimate", "optimality_certificate", "scipy"),
    "community_louvain": (3, "detect_communities", "optimization", "heuristic_trace", "networkx"),
    "blackbox_multistart_lbfgsb": (3, "continuous_minimize", "optimization", "heuristic_trace", "scipy"),
    "crowd_weighted_vote": (2, "weighted_vote_labels", "estimate", "collective_trace", None),
}
EXACT = ("maxsat_cpsat", "binpack_cpsat", "reconcile_qp")
BUDGET = {"latency_s": 8.0, "compute": 100000}
_CACHE: dict = {}


def dev(family, seed=1):
    assert 0 <= seed < 10 or 9300 <= seed < 9400                # never a held-out seed
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


# ------------------------------------------------------------------ genome contract and registration
def test_genomes_validate_with_declared_identity():
    assert set(FAMILIES) == set(SPEC)
    for family, x in ITEMS.items():
        g = x.genome
        assert isinstance(g, IntelligenceGenome) and g.validate() is g
        layer, op, cls, evidence, dep = SPEC[family]
        assert (g.layer, g.operation, g.epistemic_class, g.evidence_type, g.dependency) == (layer, op, cls, evidence,
                                                                                            dep)
        assert g.buildability == "BUILDABLE_NOW" and g.standalone_decision and g.version == "1.0.0"
        assert g.authority_ceiling == g.consequence_limit == "read_only"
        assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
        assert g.known_failure_modes and g.counterindications and g.abstention_conditions
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
    for module in (solvers_d, crowd):
        tree = ast.parse(inspect.getsource(module))
        top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        names = {a.name.split(".")[0] for n in top for a in n.names} | {
            n.module.split(".")[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
        assert not names & {"numpy", "scipy", "networkx", "ortools", "z3"}


# ------------------------------------------------------------------ solve / verify on development seeds
@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("seed", range(10))
def test_solve_answers_compactly_and_its_answer_verifies(family, seed):
    data, truth, out = solved(family, seed)
    assert out["status"] == "ANSWER", out["missing"]
    _json_clean(out["output"])
    _json_clean(out["certificate"])
    assert len(json.dumps(out, allow_nan=False)) < 64 * 1024
    json.dumps(data, allow_nan=False)
    checks = ITEMS[family].verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    score = ITEMS[family].score(data, truth, out["output"])
    assert score["category"] == "correct"
    if family in EXACT:
        assert score["quality"] == pytest.approx(1.0 if family != "maxsat_cpsat" else 0.0, abs=1e-6)


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_path_withholds_until_attached_and_creates_no_authority(family):
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    data, truth = dev(family, 3)
    request = {"problem_id": f"batch-d-{family}", "operation": SPEC[family][1], "data": data,
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
    request = {"problem_id": f"batch-d-compile-{family}", "compile": {"geometry": {"geometry": cls}, "data": data}}
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


# ------------------------------------------------------------------ independent verification refutes forgeries
def _all(family, data, output, cert):
    return all(ITEMS[family].verify(data, output, cert).values())


def test_maxsat_verifier_refutes_a_suboptimal_but_consistent_answer_by_its_own_proof():
    data, truth, out = solved("maxsat_cpsat", 1)
    n, clauses, weights = solvers_d._maxsat(data)
    worse = list(out["output"]["assignment"])
    for v in range(n):                                    # flip a variable until the violated weight rises
        trial = list(worse)
        trial[v] ^= 1
        o = solvers_d._maxsat_output(clauses, weights, trial)
        if o["violated_weight"] > out["output"]["violated_weight"]:
            break
    cert = dict(out["certificate"], witness=solvers_d._digest(o["assignment"]))   # a forger re-signs its witness
    checks = solvers_d.maxsat_verify(data, o, cert)
    assert checks["violated_weight_recomputed"] and checks["witness_is_the_certified_assignment"]
    assert checks["no_better_assignment_by_z3"] is False
    assert ITEMS["maxsat_cpsat"].score(data, truth, o)["category"] == "wrong"


def test_maxsat_infeasible_hard_clauses_are_proved_and_a_false_infeasibility_claim_is_refuted():
    contradiction = {"num_vars": 2, "clauses": [[1], [-1], [2]], "clause_weights": [None, None, 3]}
    out = solvers_d.maxsat_solve(contradiction, BUDGET)
    assert out["status"] == "ANSWER" and out["output"]["feasible"] is False
    assert _all("maxsat_cpsat", contradiction, out["output"], out["certificate"])
    data, _, good = solved("maxsat_cpsat", 1)
    assert not _all("maxsat_cpsat", data, dict(solvers_d.INFEASIBLE), {})


def test_z3_optimize_competitor_failure_is_caught_by_the_verifier_on_dev_seed_4():
    """Dev finding: Z3 Optimize's default MaxRes engine returned a non-optimal model (1495 vs 1373) on a
    claims-and-rules instance. The candidate's verifier refutes that model as an answer."""
    data, truth = dev("maxsat_cpsat", 4)
    rival = solvers_d.maxsat_z3_optimize(data)
    assert rival["violated_weight"] > truth["optimum"]
    cert = {"witness": solvers_d._digest(rival["assignment"])}
    assert solvers_d.maxsat_verify(data, rival, cert)["no_better_assignment_by_z3"] is False


def test_binpack_verifier_refutes_overloads_lost_items_and_a_non_minimal_count():
    data, truth, out = solved("binpack_cpsat", 1)
    o = out["output"]
    merged = {"bins": o["bins"] - 1, "packing": sorted([sorted(o["packing"][0] + o["packing"][1])] + o["packing"][2:])}
    assert not solvers_d.binpack_verify(data, merged, {})["loads_within_capacity"]
    lost = {"bins": o["bins"], "packing": [o["packing"][0][1:] or o["packing"][0]] + o["packing"][1:]}
    assert not _all("binpack_cpsat", data, lost, {})
    sizes, cap = solvers_d._packing_input(data)
    split = [[i] for b in o["packing"] for i in b]       # one item per bin: valid but far from minimal
    extra = {"bins": len(split), "packing": sorted(split)}
    checks = solvers_d.binpack_verify(data, extra, {})
    assert checks["loads_within_capacity"] and checks["no_packing_in_fewer_bins"] is False


def test_binpack_lower_bound_is_valid_and_independent_of_the_planted_answer():
    for seed in list(range(10)) + list(range(9300, 9320)):
        data, truth = dev("binpack_cpsat", seed)
        sizes, cap = solvers_d._packing_input(data)
        assert solvers_d.martello_toth_l2(sizes, cap) <= truth["optimum"]


def test_reconcile_verifier_needs_a_kkt_certificate_and_refutes_a_feasible_non_optimum():
    data, truth, out = solved("reconcile_qp", 0)
    assert not _all("reconcile_qp", data, out["output"], {})                   # no multipliers: no certificate
    baseline = solvers_d.reconcile_slsqp(data)
    m, s, a, b = solvers_d._qp_input(data)
    import numpy as np
    x = np.array(out["output"]["estimates"])
    y = 0.5 * x + 0.5 * np.array(solvers_d.reconcile_projection_clip(data)["estimates"])   # feasible? maybe not
    forged = {"feasible": True, "estimates": [float(v) for v in y], "objective": solvers_d._qp_objective(y, m, s)}
    assert not _all("reconcile_qp", data, forged, out["certificate"])
    lam = np.array(out["certificate"]["balance_multipliers"])
    shifted = dict(out["certificate"], balance_multipliers=[float(v) for v in lam + 1.0])
    assert not solvers_d.reconcile_verify(data, out["output"], shifted)["stationarity"]
    assert baseline is None or ITEMS["reconcile_qp"].score(data, truth, baseline)["category"] in ("correct", "wrong")


def test_reconcile_infeasible_balances_are_reported_with_a_farkas_check():
    data = {"measured_values": [1.0, 2.0], "std_devs": [1.0, 1.0], "balance_matrix": [[1.0, 1.0]],
            "balance_rhs": [-5.0]}                                             # non-negative values cannot sum to -5
    out = solvers_d.reconcile_solve(data, BUDGET)
    assert out["status"] == "ANSWER" and out["output"]["feasible"] is False
    assert _all("reconcile_qp", data, out["output"], out["certificate"])
    good, _, real = solved("reconcile_qp", 1)
    assert not _all("reconcile_qp", good, {"feasible": False, "estimates": None, "objective": None}, {})


def test_reconcile_matches_the_exhaustive_optimum_on_review_seeds():
    for seed in range(9300, 9340):
        data, truth, out = solved("reconcile_qp", seed)
        assert out["status"] == "ANSWER" and _all("reconcile_qp", data, out["output"], out["certificate"])
        assert out["output"]["objective"] == pytest.approx(truth["optimum"], rel=1e-7, abs=1e-9)


def test_community_verifier_refutes_a_partition_with_an_improving_move():
    data, truth, out = solved("community_louvain", 2)
    comms = out["output"]["communities"]
    moved = [list(c) for c in comms]
    node = moved[0].pop()
    moved[1].append(node)                                  # a locally worse placement, honestly scored
    moved = sorted(sorted(c) for c in moved if c)
    nodes, edges = solvers_d._network(data)
    forged = {"communities": moved, "modularity": solvers_d._modularity(nodes, edges, moved)}
    checks = solvers_d.community_verify(data, forged, {})
    assert checks["modularity_recomputed"] and checks["no_improving_single_node_move"] is False
    assert not _all("community_louvain", data, {**out["output"], "modularity": out["output"]["modularity"] + 1e-6}, {})


def test_community_independent_modularity_matches_networkx():
    import networkx as nx
    data, _, out = solved("community_louvain", 5)
    g = nx.Graph()
    g.add_weighted_edges_from(data["network_edges"])
    assert out["output"]["modularity"] == pytest.approx(
        nx.community.modularity(g, [set(c) for c in out["output"]["communities"]], weight="weight"), abs=1e-12)


def test_blackbox_verifier_recomputes_the_value_box_and_budget():
    data, _, out = solved("blackbox_multistart_lbfgsb", 3)
    o, cert = out["output"], out["certificate"]
    assert solvers_d.bb_verify(data, {**o, "value": o["value"] * 0.5 - 1e-3}, cert)["value_recomputed"] is False
    assert solvers_d.bb_verify(data, o, dict(cert, evaluations_used=data["evaluations"] + 1))[
        "within_the_evaluation_budget"] is False
    outside = {"x": [data["upper"] + 1.0] + o["x"][1:], "value": o["value"]}
    assert solvers_d.bb_verify(data, outside, cert)["inside_the_box"] is False
    assert cert["evaluations_used"] <= data["evaluations"]


@pytest.mark.parametrize("arm", ["bb_single_start", "bb_differential_evolution"])
def test_blackbox_arms_never_exceed_the_shared_evaluation_budget(arm):
    data, _ = dev("blackbox_multistart_lbfgsb", 5)
    counted = []
    original = solvers_d._counted

    def spy(name, shift, budget):
        f, state = original(name, shift, budget)
        counted.append(state)
        return f, state
    try:
        solvers_d._counted = spy
        getattr(solvers_d, arm)(data)
    finally:
        solvers_d._counted = original
    assert counted and counted[0]["used"] <= data["evaluations"]


def test_crowd_verifier_recomputes_weights_and_labels():
    data, truth, out = solved("crowd_weighted_vote", 2)
    o = out["output"]
    item = sorted(o["labels"])[0]
    flipped = {**o, "labels": {**o["labels"], item: (o["labels"][item] + 1) % data["num_classes"]}}
    assert solvers_d is not None and crowd.vote_verify(data, flipped, {})["labels_recomputed"] is False
    worker = sorted(o["worker_weights"])[0]
    nudged = {**o, "worker_weights": {**o["worker_weights"], worker: o["worker_weights"][worker] + 1e-6}}
    assert crowd.vote_verify(data, nudged, {})["weights_recomputed"] is False
    missing = {**o, "worker_weights": {w: v for w, v in o["worker_weights"].items() if w != worker}}
    assert crowd.vote_verify(data, missing, {})["weights_recomputed"] is False


def test_crowd_weights_invert_a_systematic_adversary_and_ignore_a_spammer():
    votes = {}
    for i in range(60):
        truth = i % 2
        votes[f"i{i:02d}"] = {"good1": truth, "good2": truth, "good3": truth, "liar": 1 - truth,
                              "coin": (i * 7 // 3) % 2}
    out = crowd.vote_solve({"crowd_votes": votes, "num_classes": 2}, {})["output"]
    w = out["worker_weights"]
    assert w["liar"] < 0 < w["good1"] and abs(w["coin"]) < w["good1"]


# ------------------------------------------------------------------ invalid input is refused, never crashes
@pytest.mark.parametrize("family,bad", [
    ("maxsat_cpsat", {"num_vars": 2, "clauses": [[3]], "clause_weights": [1]}),
    ("maxsat_cpsat", {"num_vars": 2, "clauses": [[1, 1]], "clause_weights": [1]}),
    ("maxsat_cpsat", {"num_vars": 2, "clauses": [[1]], "clause_weights": [0]}),
    ("binpack_cpsat", {"item_sizes": [5, 11], "bin_capacity": 10}),
    ("binpack_cpsat", {"item_sizes": [], "bin_capacity": 10}),
    ("reconcile_qp", {"measured_values": [1.0], "std_devs": [0.0], "balance_matrix": [[1.0]], "balance_rhs": [1.0]}),
    ("reconcile_qp", {"measured_values": [1.0, 2.0], "std_devs": [1.0, 1.0], "balance_matrix": [[1.0]],
                      "balance_rhs": [1.0]}),
    ("community_louvain", {"network_edges": [["a", "a", 1]]}),
    ("community_louvain", {"network_edges": [["a", "b", 1], ["b", "a", 2]]}),
    ("blackbox_multistart_lbfgsb", {"objective": "import os", "dimension": 2, "lower": -1, "upper": 1,
                                    "shift": [0, 0], "evaluations": 100, "seed": 1}),
    ("crowd_weighted_vote", {"crowd_votes": {"i": {"w": 3}}, "num_classes": 2}),
    ("crowd_weighted_vote", {"crowd_votes": [], "num_classes": 2}),
])
def test_invalid_input_raises_a_genome_error(family, bad):
    with pytest.raises(GenomeError):
        ITEMS[family].solve(bad, BUDGET)


@pytest.mark.parametrize("family", FAMILIES)
def test_malformed_outputs_are_refuted_not_raised(family):
    data, _ = dev(family, 1)
    for junk in (None, 3, [], {}, {"x": None}, "answer"):
        checks = ITEMS[family].verify(data, junk, {})
        assert not all(checks.values())


def test_abstention_beyond_the_native_size():
    big = {"item_sizes": [1] * (solvers_d.BP_NATIVE_ITEMS + 1), "bin_capacity": 10}
    assert solvers_d.binpack_solve(big, BUDGET)["status"] == "ABSTAIN"
    many = {"num_vars": solvers_d.MS_NATIVE_VARS + 1, "clauses": [[1]], "clause_weights": [1]}
    assert solvers_d.maxsat_solve(many, BUDGET)["status"] == "ABSTAIN"


def test_instances_are_deterministic_by_seed():
    for family in FAMILIES:
        assert json.dumps(ITEMS[family].instance(9301)[0], sort_keys=True) == json.dumps(
            ITEMS[family].instance(9301)[0], sort_keys=True)
