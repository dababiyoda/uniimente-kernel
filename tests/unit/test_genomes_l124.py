"""Layer 1, 2 and 4 batch B (token-bucket admission, NLMS online learner, priced task auction, graph diffusion):
contract, withheld registration, canonical path, Competency Compiler reachability, independent verification,
refutation of corrupted answers and forged certificates, invalid input and scoring.

Development seeds 0-9 and this lane's declared review range 9400-9439 only
(docs/evidence/greg-genome-l124-absent-2026-10-21/README.md); held-out admission seeds are never generated here.
"""
from __future__ import annotations

import copy
import json
import math

import pytest

from greg.cognition import catalog, worlds
from greg.cognition.genomes import basal_b, collective_b, developmental_b, library
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

MODULES = (basal_b, collective_b, developmental_b)
ITEMS = {x.genome.family: x for m in MODULES for x in m.INTELLIGENCES}
FAMILIES = tuple(sorted(ITEMS))
SPEC = {  # family: (layer, operation, epistemic class, evidence type, dependency, world)
    "basal_token_bucket": (1, "rate_limited_admission", "optimization", "control_trace", None, "simulated_world"),
    "basal_nlms": (1, "online_linear_predict", "prediction", "control_trace", None, "simulated_world"),
    "collective_auction": (2, "capacitated_task_allocation", "optimization", "optimality_certificate", None,
                           "mathematical_instance"),
    "develop_diffusion": (4, "propagate_graph_labels", "estimate", "developmental_trace", "scipy",
                          "simulated_world"),
}
REVIEW = range(9400, 9440)
BUDGET = {"latency_s": 8.0, "compute": 100000}
_CACHE: dict = {}


def dev(family, seed=1):
    assert 0 <= seed < 10 or 9400 <= seed < 9440                # never a held-out seed
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


def _all(family, data, output, cert):
    return all(ITEMS[family].verify(data, output, cert).values())


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
def test_genomes_validate_with_declared_identity_and_world():
    assert set(FAMILIES) == set(SPEC)
    for family, x in ITEMS.items():
        g = x.genome
        assert isinstance(g, IntelligenceGenome) and g.validate() is g
        layer, op, cls, evidence, dep, world = SPEC[family]
        assert (g.layer, g.operation, g.epistemic_class, g.evidence_type, g.dependency) == (layer, op, cls, evidence,
                                                                                            dep)
        assert worlds.world("genome", family) == world
        assert g.buildability == "BUILDABLE_NOW" and g.standalone_decision and g.version == "1.0.0"
        assert g.authority_ceiling == g.consequence_limit == "read_only"
        assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
        assert len(g.known_failure_modes) >= 3 and g.counterindications and g.abstention_conditions
        assert g.baseline and g.competitor and x.subregion is not None and x.competitor_deployable
        assert "seeds 0-9 dev" in g.benchmark_suite


def test_each_absent_layer_gets_a_family():
    assert {ITEMS[f].genome.layer for f in FAMILIES} == {1, 2, 4}


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
    for module in MODULES:
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
    json.dumps(data, allow_nan=False)
    checks = ITEMS[family].verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    score = ITEMS[family].score(data, truth, out["output"])
    assert score["category"] in ("correct", "wrong") and math.isfinite(score["quality"])
    if family == "collective_auction":
        assert score == {"quality": 1.0, "category": "correct"}


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_path_withholds_until_attached_and_creates_no_authority(family):
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    data, truth = dev(family, 3)
    request = {"problem_id": f"l124-{family}", "operation": SPEC[family][1], "data": data,
               "geometry": {"latency_limit": 30}}
    assert reason(request, registry=registry)["abstention_state"] == "CAPABILITY_DEFICIT"
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["abstention_state"] == "NONE" and r["proof_type"] == "genome_certificate"
    assert r["proof_artifact"]["evidence_type"] == SPEC[family][3]
    assert r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" and r["authority_created"] is False
    assert ITEMS[family].score(data, truth, r["output"])["category"] in ("correct", "wrong")


@pytest.mark.parametrize("family", FAMILIES)
def test_the_competency_compiler_reaches_the_family_by_its_inputs(family, tmp_path, monkeypatch):
    """Evaluation only: an in-memory attach (no body, journal or founder pin) and an empty evidence index."""
    from greg.cognition import compiler
    from greg.cognition.cortex import reason, registry_view
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")
    data, truth = dev(family, 1)
    cls = SPEC[family][2]
    request = {"problem_id": f"l124-compile-{family}", "compile": {"geometry": {"geometry": cls}, "data": data}}
    registry = registry_view()
    withheld = reason(request, registry=registry)
    assert withheld["state"] == "CAPABILITY_DEFICIT"
    assert withheld["withheld_best_fit"]["method"] == f"cognition.{family}"
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == f"cognition.{family}"
    assert r["methods_considered"] == [f"cognition.{family}"]
    assert r["derived_geometry"]["fits_by_inputs"] == [cls] and r["authority_created"] is False


# ------------------------------------------------------------------ token-bucket admission
def test_token_bucket_conformance_check_refutes_a_stream_that_breaks_the_contract():
    data, truth, out = solved("basal_token_bucket", 0)              # Poisson overload
    v = data["request_values"]
    everything = {"admitted": list(range(len(v))), "admitted_count": len(v),
                  "admitted_value": math.fsum(v)}
    checks = basal_b.token_bucket_verify(data, everything, out["certificate"])
    assert checks["value_recomputed"] and checks["conforms_to_the_token_bucket"] is False
    assert ITEMS["basal_token_bucket"].score(data, truth, everything)["category"] == "wrong"


def test_token_bucket_replay_refutes_a_conformant_answer_from_another_rule():
    data, truth, out = solved("basal_token_bucket", 0)
    plain = basal_b.token_bucket_plain(data)
    checks = basal_b.token_bucket_verify(data, plain, out["certificate"])
    assert checks["conforms_to_the_token_bucket"] and checks["value_recomputed"]
    assert checks["rule_replayed"] is False


def test_token_bucket_arrival_curve_agrees_with_bucket_simulation_on_review_seeds():
    """The verifier's arrival-curve test and a token-bucket simulation are two characterisations of one contract."""
    for seed in REVIEW:
        data, truth = dev("basal_token_bucket", seed)
        t, v, rate, burst = basal_b._tb_input(data)
        assert basal_b._conforms([t[i] for i in basal_b._plain_admitted(t, rate, burst)], rate, burst)
        admitted = basal_b.token_bucket_bid_price(data)["admitted"]
        assert basal_b._conforms([t[i] for i in admitted], rate, burst)
        if truth["kind"] != "underload":
            assert not basal_b._conforms(t, rate, burst)              # admitting all breaks an overloaded contract


def test_token_bucket_offline_optimum_bounds_every_online_policy_on_review_seeds():
    for seed in REVIEW:
        data, truth, out = solved("basal_token_bucket", seed)
        for o in (out["output"], basal_b.token_bucket_plain(data), basal_b.token_bucket_bid_price(data)):
            assert o["admitted_value"] <= truth["optimum"] * (1 + 1e-9)


# ------------------------------------------------------------------ NLMS
def test_nlms_replay_refutes_a_perturbed_prediction_and_a_wrong_step_claim():
    data, truth, out = solved("basal_nlms", 2)
    o = copy.deepcopy(out["output"])
    o["predictions"][100] += 1e-3
    o["prequential_mse"] = basal_b._mse(o["predictions"], data["target_stream"])   # a forger recomputes the error
    checks = basal_b.nlms_verify(data, o, out["certificate"])
    assert checks["prequential_mse_recomputed"] and checks["predictions_replayed"] is False
    assert basal_b.nlms_verify(data, out["output"], dict(out["certificate"], mu=0.4))["declared_rule"] is False


def test_nlms_verifier_refutes_the_rls_competitor_as_an_answer_of_the_declared_rule():
    data, truth, out = solved("basal_nlms", 0)
    rival = basal_b.nlms_rls(data)
    checks = basal_b.nlms_verify(data, rival, out["certificate"])
    assert checks["prequential_mse_recomputed"] and not checks["predictions_replayed"]


def test_nlms_learns_a_stationary_linear_relation():
    data, truth, out = solved("basal_nlms", 0)
    y = data["target_stream"]
    half = len(y) // 2
    late = basal_b._mse(out["output"]["predictions"][half:], y[half:])
    assert late < 4 * truth["noise_sd"] ** 2 + 0.05


# ------------------------------------------------------------------ priced task auction
def test_auction_matches_the_lp_optimum_and_proves_it_on_review_seeds():
    for seed in REVIEW:
        data, truth, out = solved("collective_auction", seed)
        assert out["output"]["total_value"] == truth["optimum"]
        assert _all("collective_auction", data, out["output"], out["certificate"])


def test_auction_dual_bound_refutes_a_feasible_suboptimal_allocation_even_with_the_real_prices():
    for seed in range(10):
        data, truth, out = solved("collective_auction", seed)
        greedy = collective_b.auction_greedy(data)
        if greedy["total_value"] < truth["optimum"]:
            checks = collective_b.auction_verify(data, greedy, out["certificate"])
            assert checks["capacities_respected"] and checks["value_recomputed"]
            assert checks["optimal_by_dual_bound"] is False
            return
    pytest.fail("no development seed separates greedy from the optimum")


def test_auction_forged_prices_do_not_prove_optimality_and_a_capacity_breach_is_caught():
    data, truth, out = solved("collective_auction", 1)
    cert = out["certificate"]
    zero = dict(cert, slot_prices=[[0.0] * len(p) for p in cert["slot_prices"]],
                null_prices=[0.0] * len(cert["null_prices"]))
    assert collective_b.auction_verify(data, out["output"], zero)["optimal_by_dual_bound"] is False
    assert collective_b.auction_verify(data, out["output"], dict(cert, dummy_persons=0))[
        "dual_bound_certificate_well_formed"] is False
    rows, caps = collective_b._input(data)
    crowded = [0] * len(rows)
    over = {"allocation": crowded, "total_value": sum(r[0] for r in rows)}
    assert collective_b.auction_verify(data, over, cert)["capacities_respected"] is (len(rows) <= caps[0])


def test_auction_dual_bound_is_an_upper_bound_for_any_prices():
    import random
    data, truth = dev("collective_auction", 2)
    rows, caps = collective_b._input(data)
    rnd = random.Random("test:auction-dual")
    for _ in range(20):
        slots = [[rnd.uniform(0, 500) for _ in range(c)] for c in caps]
        nulls = [rnd.uniform(0, 50) for _ in range(len(rows))]
        assert collective_b.dual_bound(rows, caps, slots, nulls, sum(caps)) >= truth["optimum"] - 1e-6


# ------------------------------------------------------------------ graph diffusion
def test_diffusion_scores_match_the_direct_solve_and_a_perturbation_is_refuted():
    data, truth, out = solved("develop_diffusion", 1)
    node = sorted(v for v in out["output"]["scores"] if v not in data["seed_labels"])[0]
    o = copy.deepcopy(out["output"])
    o["scores"][node][0] += 1e-4
    assert developmental_b.diffusion_verify(data, o, {})["scores_match_the_direct_harmonic_solve"] is False
    o = copy.deepcopy(out["output"])
    o["labels"][node] = (o["labels"][node] + 1) % data["num_label_classes"]
    assert developmental_b.diffusion_verify(data, o, {})["labels_are_the_harmonic_argmax"] is False


def test_diffusion_abstains_on_a_component_without_seeds_and_a_guess_there_is_refuted():
    data = {"graph_edges": [["a", "b", 1], ["b", "c", 1], ["x", "y", 1]], "seed_labels": {"a": 0, "c": 1},
            "num_label_classes": 2}
    out = developmental_b.diffusion_solve(data, BUDGET)
    o = out["output"]
    assert o["labels"]["x"] == o["labels"]["y"] == -1 and o["scores"]["b"] == pytest.approx([0.5, 0.5])
    assert _all("develop_diffusion", data, o, out["certificate"])
    guessed = copy.deepcopy(o)
    guessed["labels"]["x"] = 0
    assert developmental_b.diffusion_verify(data, guessed, {})["seedless_components_abstain"] is False


def test_diffusion_competitor_outputs_are_judged_by_accuracy_not_by_the_harmonic_check():
    data, truth, out = solved("develop_diffusion", 3)
    rival = developmental_b.diffusion_community_vote(data)
    assert ITEMS["develop_diffusion"].score(data, truth, rival)["category"] in ("correct", "wrong")
    assert developmental_b.diffusion_verify(data, rival, {})["output_shape"] is True


# ------------------------------------------------------------------ invalid input is refused, never crashes
@pytest.mark.parametrize("family,bad", [
    ("basal_token_bucket", {"request_times": [2.0, 1.0], "request_values": [1, 1], "token_rate": 1, "bucket_size": 2}),
    ("basal_token_bucket", {"request_times": [1.0], "request_values": [1], "token_rate": 0, "bucket_size": 2}),
    ("basal_token_bucket", {"request_times": [1.0], "request_values": [1], "token_rate": 1, "bucket_size": 0}),
    ("basal_nlms", {"feature_stream": [[1.0], [1.0, 2.0]], "target_stream": [1.0, 2.0]}),
    ("basal_nlms", {"feature_stream": [[1.0]], "target_stream": [1.0, 2.0]}),
    ("collective_auction", {"task_agent_values": [[1, 2]], "agent_capacities": [1]}),
    ("collective_auction", {"task_agent_values": [[1.5]], "agent_capacities": [1]}),
    ("collective_auction", {"task_agent_values": [[1]], "agent_capacities": [0]}),
    ("develop_diffusion", {"graph_edges": [["a", "a", 1]], "seed_labels": {"a": 0}, "num_label_classes": 2}),
    ("develop_diffusion", {"graph_edges": [["a", "b", 1]], "seed_labels": {"z": 0}, "num_label_classes": 2}),
    ("develop_diffusion", {"graph_edges": [["a", "b", 1]], "seed_labels": {"a": 2}, "num_label_classes": 2}),
    ("develop_diffusion", {"graph_edges": [["a", "b", 1], ["b", "a", 1]], "seed_labels": {"a": 0},
                           "num_label_classes": 2}),
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
    many = {"request_times": [float(i) for i in range(basal_b.TB_NATIVE_REQUESTS + 1)],
            "request_values": [1.0] * (basal_b.TB_NATIVE_REQUESTS + 1), "token_rate": 1.0, "bucket_size": 3}
    assert basal_b.token_bucket_solve(many, BUDGET)["status"] == "ABSTAIN"
    wide = {"feature_stream": [[0.0] * (basal_b.LMS_NATIVE_D + 1)] * 3, "target_stream": [0.0] * 3}
    assert basal_b.nlms_solve(wide, BUDGET)["status"] == "ABSTAIN"
    tasks = {"task_agent_values": [[1]] * (collective_b.AU_NATIVE_TASKS + 1), "agent_capacities": [1]}
    assert collective_b.auction_solve(tasks, BUDGET)["status"] == "ABSTAIN"


def test_instances_are_deterministic_by_seed():
    for family in FAMILIES:
        assert json.dumps(ITEMS[family].instance(9401)[0], sort_keys=True) == json.dumps(
            ITEMS[family].instance(9401)[0], sort_keys=True)
