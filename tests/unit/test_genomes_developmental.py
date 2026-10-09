"""Layer 4 developmental IntelligenceGenomes: contract, independent verification, abstention, scoring, determinism.

Development seeds only (0-9); the held-out admission seeds (>= 1000) are never generated here. The sealed
MICA/CDPE laboratory (``developmental/``) is only imported by the benchmark generator, never modified.
"""
from __future__ import annotations

import ast
import copy
import json
import math
from pathlib import Path
import time

import pytest

from greg.cognition.genomes import developmental, library
from greg.cognition.genomes.contract import EPISTEMIC_CLASSES, GenomeError, IntelligenceGenome

FAMILIES = ("develop_repair", "develop_constraint_release")
OPS = {"develop_repair": "target_state_repair", "develop_constraint_release": "release_recombine_pipeline"}
EVIDENCE = {"develop_repair": "developmental_trace", "develop_constraint_release": "heuristic_trace"}
RESERVED_OPS = ("setpoint calculate polynomial estimate constraints optimize shortest_path state_search beta_update "
                "treatment_effect pid value_of_information simulate minimax protection_review deterrence_model "
                "anomalies mdp interpret human_review quorum evolve_vector bind_evidence").split()
DEV_SEEDS = tuple(range(10))
BUDGET = {"latency_s": 5.0, "compute": 100000}
_CACHE: dict = {}


def item(family):
    return {x.genome.family: x for x in developmental.INTELLIGENCES}[family]


def dev(family, seed=0):
    key = (family, seed)
    if key not in _CACHE:
        _CACHE[key] = item(family).instance(seed)
    data, truth = _CACHE[key]
    return copy.deepcopy(data), truth


def solved(family, seed=0):
    key = ("solved", family, seed)
    if key not in _CACHE:
        data, truth = dev(family, seed)
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


def _refuted(family, data, output, certificate):
    checks = item(family).verify(data, output, certificate)
    return not all(bool(v) for v in checks.values())


# ------------------------------------------------------------------ genome contract
def test_genomes_validate_and_are_layer_four():
    assert sorted(x.genome.family for x in developmental.INTELLIGENCES) == sorted(FAMILIES)
    for x in developmental.INTELLIGENCES:
        g = x.genome
        assert isinstance(g, IntelligenceGenome)
        assert g.validate() is g
        assert g.layer == 4 and g.buildability == "BUILDABLE_NOW"
        assert g.operation == OPS[g.family] and g.operation not in RESERVED_OPS
        assert g.evidence_type == EVIDENCE[g.family]
        assert g.epistemic_class in EPISTEMIC_CLASSES
        assert g.authority_ceiling == g.consequence_limit == "read_only"
        assert g.dependency is None and g.standalone_decision is True
        assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
        assert g.family.startswith("develop_") and g.intelligence_id.startswith("developmental.")
        # the frontier is stated honestly in both places
        for text in ("robust unscripted organ formation", "generalized repair across domains",
                     "cross-substrate developmental compilation"):
            assert any(text in m and "NOT achieved" in m for m in g.known_failure_modes)
            assert any(text in m and "NOT achieved" in m for m in g.counterindications)
        assert x.subregion is not None
    assert item("develop_repair").genome.epistemic_class == "physical"
    assert item("develop_constraint_release").genome.epistemic_class == "optimization"


def test_genomes_make_no_biological_life_claims():
    text = json.dumps([x.genome.to_dict() for x in developmental.INTELLIGENCES]).lower()
    for claim in ("is alive", "living organism", "conscious", "general intelligence", "sentien"):
        assert claim not in text


def test_library_registers_developmental_families_without_collisions():
    executables = library.executables()
    projection = library.catalog_families()
    for family in FAMILIES:
        assert executables[family] is item(family)
        layer, ops, classes, proof, dependency = projection[family]
        assert layer == 4 and ops == (OPS[family],) and proof == "genome_certificate" and dependency is None
    assert len({x.genome.operation for x in executables.values()}) == len(executables)


def test_module_top_level_imports_are_stdlib_or_contract_and_touch_nothing():
    source = Path(developmental.__file__).read_text()
    tree = ast.parse(source)
    allowed = {"__future__", "collections", "hashlib", "json", "math", "random"}
    for node in tree.body:
        if isinstance(node, ast.Import):
            assert {a.name.split(".")[0] for a in node.names} <= allowed
        elif isinstance(node, ast.ImportFrom):
            assert (node.level == 1 and node.module == "contract") or node.module in allowed
    # the sealed laboratory is imported lazily, read-only; no files, processes, sockets or environment
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "open" not in called and "exec" not in called and "eval" not in called
    imported = {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                for a in n.names} | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not imported & {"os", "subprocess", "socket", "shutil", "pathlib", "sys"}
    assert {"developmental.mica", "developmental.contracts"} <= imported


# ------------------------------------------------------------------ solve / verify round trip
@pytest.mark.parametrize("family", FAMILIES)
def test_solve_returns_a_compact_json_answer_that_verifies(family):
    data, truth, out = solved(family)
    assert set(out) == {"output", "certificate", "status", "missing"}
    assert out["status"] == "ANSWER" and out["missing"] == []
    _json_clean(out["output"])
    _json_clean(out["certificate"])
    assert len(json.dumps(out["output"])) < 64 * 1024 and len(json.dumps(out["certificate"])) < 64 * 1024
    checks = item(family).verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    assert item(family).score(data, truth, out["output"])["category"] == "correct"


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_library_adapters_bind_and_verify(family):
    data, _ = dev(family, 0)
    result = library.run(family, data, {"latency_limit": 5})
    assert result["status"] == "ANSWER" and result["proof"]["evidence_type"] == EVIDENCE[family]
    checks = library.check(family, data, result["output"], result["proof"])
    assert all(checks.values()), checks
    tampered = copy.deepcopy(data)
    tampered["seed"] = data["seed"] + 1
    assert library.check(family, tampered, result["output"], result["proof"])["inputs_bound"] is False


# --- develop_repair: the verifier rebuilds the realized topology and follows every claimed chain
def _dead_cells(data):
    dead = {tuple(c) for c in data["removed"]}
    for ev in data["events"]:
        dead |= {tuple(c) for c in ev["fail"]}
    return dead


def test_repair_verify_refutes_a_collapsed_route_claimed_as_restored():
    data, truth, out = solved("develop_repair", 0)
    hop = out["output"]["next_hop"]
    source = out["output"]["claimed"][0]
    first = hop[source]
    hop[first] = source                          # source -> first -> source: a loop, every pointer still legal
    checks = item("develop_repair").verify(data, out["output"], out["certificate"])
    assert checks["pointers_are_lattice_edges"] and checks["no_pointer_into_removed_unit_or_blocked_link"]
    assert checks["every_claimed_source_delivers_on_realized_topology"] is False
    s = item("develop_repair").score(data, truth, out["output"])
    assert s["category"] == "wrong" and s["quality"] < item("develop_repair").score(data, truth, None)["quality"]


def test_repair_verify_refutes_a_pointer_into_a_removed_unit():
    data, _, out = solved("develop_repair", 0)
    dead = _dead_cells(data)
    hop = out["output"]["next_hop"]
    for key in sorted(hop):
        x, y = map(int, key.split(","))
        gone = [c for c in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)) if c in dead]
        if gone:
            hop[key] = f"{gone[0][0]},{gone[0][1]}"
            break
    else:                                        # pragma: no cover - the dev instance has damage next to live units
        pytest.fail("no live unit borders the damage")
    checks = item("develop_repair").verify(data, out["output"], out["certificate"])
    assert checks["no_pointer_into_removed_unit_or_blocked_link"] is False


def test_repair_verify_refutes_claiming_an_unreachable_source():
    data, truth, out = solved("develop_repair", 0)
    assert truth["unreachable_sources"], "dev seed 0 has a source cut off from every sink"
    out["output"]["claimed"] = sorted(out["output"]["claimed"] + truth["unreachable_sources"][:1])
    assert _refuted("develop_repair", data, out["output"], out["certificate"])
    assert item("develop_repair").score(data, truth, out["output"])["category"] == "wrong"


def test_repair_verify_refutes_an_understated_action_count_and_unbound_seed():
    data, _, out = solved("develop_repair", 0)
    cheap = copy.deepcopy(out)
    cheap["output"]["actions"] -= 1
    assert item("develop_repair").verify(data, cheap["output"], cheap["certificate"])["actions_match_trace"] is False
    other = copy.deepcopy(out)
    other["certificate"]["seed"] += 1
    assert item("develop_repair").verify(data, other["output"], other["certificate"])["seed_bound"] is False
    assert item("develop_repair").verify(data, ["not", "a", "dict"], {}) == {"output_shape": False}


# --- develop_constraint_release: replay the returned configuration with separate objective code
def test_constraint_release_verify_refutes_corrupted_outputs():
    data, _, out = solved("develop_constraint_release", 0)
    x = item("develop_constraint_release")
    assert out["output"]["retained"] is True        # dev seed 0 retains a recombined configuration

    swapped = copy.deepcopy(out)                    # a different configuration under the same claims
    swapped["output"]["configuration"] = ["edd"]
    assert _refuted("develop_constraint_release", data, swapped["output"], swapped["certificate"])

    inflated = copy.deepcopy(out)                   # an overstated validation gain
    inflated["output"]["validation_utility"] *= 0.5
    assert x.verify(data, inflated["output"], inflated["certificate"])["validation_claims_recomputed"] is False

    flipped = copy.deepcopy(out)                    # claims extinction while returning the recombined config
    flipped["output"]["retained"] = False
    assert x.verify(data, flipped["output"], flipped["certificate"])["retain_or_extinct_rule_obeyed"] is False

    rootless = copy.deepcopy(out)                   # lineage that does not start at the original pipeline
    rootless["output"]["lineage"] = rootless["output"]["lineage"][1:]
    assert x.verify(data, rootless["output"], rootless["certificate"])[
        "lineage_roots_at_original_and_ends_at_output"] is False

    garbage = copy.deepcopy(out)                    # malformed lineage / authority are refuted, never raised
    garbage["output"]["lineage"][-1]["parents"] = [["unhashable"]]
    garbage["output"]["authority"] = None
    checks = x.verify(data, garbage["output"], garbage["certificate"])
    assert checks["lineage_roots_at_original_and_ends_at_output"] is False and checks["no_authority_claimed"] is False

    unknown = copy.deepcopy(out)
    unknown["output"]["configuration"] = ["atc:2", "teleport:all:best"]
    assert x.verify(data, unknown["output"], unknown["certificate"]) == {"configuration_well_formed": False}


def test_constraint_release_keeps_the_original_when_nothing_beats_it():
    case = {"p": [3, 5, 2, 7], "w": [1, 2, 3, 1], "d": [10 ** 5] * 4}     # no tardiness is possible
    data = {"train": [copy.deepcopy(case) for _ in range(4)], "validation": [copy.deepcopy(case) for _ in range(4)],
            "budget": 12, "seed": 3}
    out = developmental.constraint_release_solve(data, BUDGET)
    assert out["status"] == "ANSWER"
    o = out["output"]
    assert o["retained"] is False and o["configuration"] == list(developmental.ORIGINAL_PIPELINE)
    assert len(o["lineage"]) == 1 and o["lineage"][0]["parents"] == []
    assert out["certificate"]["extinct"] == o["evaluations"] - 1 >= 1
    assert all(item("develop_constraint_release").verify(data, o, out["certificate"]).values())
    assert "none" in o["authority"]


def test_constraint_release_lineage_is_complete_at_the_budget_ceiling():
    data, _ = dev("develop_constraint_release", 0)
    data["budget"] = developmental.CR_MAX_BUDGET
    out = developmental.constraint_release_solve(data, BUDGET)
    lineage = out["output"]["lineage"]
    assert lineage[0]["config"] == list(developmental.ORIGINAL_PIPELINE)
    assert all(item("develop_constraint_release").verify(data, out["output"], out["certificate"]).values())
    assert len(json.dumps(out["output"])) < 64 * 1024


# ------------------------------------------------------------------ invalid input
def _repair_bad():
    def edit(**kw):
        def f(d):
            d.update(kw)
        return f

    def drop_events_key(d):
        d["events"] = [{"step": 30}]

    return [lambda d: d.clear() or d.update({"width": "12"}), edit(width=2), edit(width=20, height=11),
            edit(sources=[[0, 0]], sinks=[[0, 0]]), edit(blocked=[[[0, 0], [2, 0]]]), edit(message_loss=float("nan")),
            edit(message_loss="0.1"), edit(steps=0), edit(steps=401), drop_events_key, edit(seed=-1),
            edit(controller={"mode": "telepathic", "view_lag": 0, "crash_at": None}),
            edit(sources=[[99, 0]]), edit(removed=[[1, 1], [1, 1]])]


def _cr_bad():
    def edit(**kw):
        def f(d):
            d.update(kw)
        return f

    def missing_d(d):
        del d["train"][0]["d"]

    def zero_p(d):
        d["train"][0]["p"][0] = 0

    def ragged(d):
        d["validation"][0]["w"] = d["validation"][0]["w"][:-1]

    return [edit(train="cases"), missing_d, zero_p, ragged, edit(budget=0), edit(budget=10 ** 6),
            edit(pipeline=["atc:2", "teleport:all:best"]), edit(pipeline=[]), edit(seed=1.5),
            lambda d: d.update({"train": d["train"] * 5})]


@pytest.mark.parametrize("family,mutate", [("develop_repair", m) for m in _repair_bad()]
                         + [("develop_constraint_release", m) for m in _cr_bad()])
def test_invalid_input_raises_genome_error(family, mutate):
    data, _ = dev(family, 0)
    mutate(data)
    with pytest.raises(GenomeError):
        item(family).solve(data, BUDGET)


@pytest.mark.parametrize("family", FAMILIES)
def test_non_object_input_raises_genome_error(family):
    with pytest.raises(GenomeError):
        item(family).solve(["not", "an", "object"], BUDGET)


# ------------------------------------------------------------------ abstention (counterindications)
@pytest.mark.parametrize("change,reason", [
    ({"message_loss": 0.7}, "message loss"),
    ({"steps": 40, "events": []}, "settle time"),
])
def test_repair_abstains_outside_its_validated_envelope(change, reason):
    data, truth = dev("develop_repair", 0)
    data.update(change)
    out = item("develop_repair").solve(data, BUDGET)
    assert out["status"] == "ABSTAIN" and out["output"] is None and reason in out["missing"][0]
    assert item("develop_repair").score(data, truth, None)["category"] == "abstain"


def test_repair_abstains_without_a_functioning_sink_region():
    data, _ = dev("develop_repair", 0)
    data["removed"] = data["removed"] + [z for z in data["sinks"] if z not in data["removed"]]
    out = item("develop_repair").solve(data, BUDGET)
    assert out["status"] == "ABSTAIN" and "no functioning source or sink" in out["missing"][0]


@pytest.mark.parametrize("change,reason", [
    (lambda d: d.update({"train": d["train"][:3]}), "training and 4 validation"),
    (lambda d: d.update({"budget": 5}), "evaluation budget"),
    (lambda d: d["train"].append({"p": list(range(1, 14)), "w": [1] * 13, "d": [50] * 13}), "jobs per case"),
])
def test_constraint_release_abstains_outside_its_validated_envelope(change, reason):
    data, truth = dev("develop_constraint_release", 0)
    change(data)
    out = item("develop_constraint_release").solve(data, BUDGET)
    assert out["status"] == "ABSTAIN" and out["output"] is None and reason in out["missing"][0]
    assert item("develop_constraint_release").score(data, truth, None)["category"] == "abstain"


# ------------------------------------------------------------------ scoring
@pytest.mark.parametrize("family", FAMILIES)
def test_score_categories(family):
    x = item(family)
    data, truth, out = solved(family, 0)
    abstain = x.score(data, truth, None)
    correct = x.score(data, truth, out["output"])
    base = x.score(data, truth, x.baseline(copy.deepcopy(data)))
    assert abstain["category"] == "abstain" and correct["category"] == "correct" and base["category"] == "correct"
    assert correct["quality"] > base["quality"]           # the candidate beats its baseline on this dev instance
    wrong_output = copy.deepcopy(out["output"])
    if family == "develop_repair":
        wrong_output["claimed"] = sorted(wrong_output["claimed"] + truth["unreachable_sources"][:1])
    else:
        wrong_output["retained"] = not wrong_output["retained"]
    wrong = x.score(data, truth, wrong_output)
    assert wrong["category"] == "wrong" and wrong["quality"] < abstain["quality"] < correct["quality"]


def test_constraint_release_malformed_configuration_scores_wrong():
    data, truth = dev("develop_constraint_release", 0)
    s = item("develop_constraint_release").score(data, truth, {"configuration": ["teleport"]})
    assert s["category"] == "wrong" and s["quality"] < item("develop_constraint_release").score(
        data, truth, None)["quality"]


def test_repair_reliable_central_replanner_wins_and_unreliable_one_can_fail():
    """Expected and reported honestly: a reliable, fresh central replanner beats the local rules."""
    x = item("develop_repair")
    data, truth, out = solved("develop_repair", 0)
    assert x.subregion(data) == "reliable_controller"
    central = x.score(data, truth, x.competitor(copy.deepcopy(data)))
    assert central["category"] == "correct" and central["quality"] > x.score(data, truth, out["output"])["quality"]
    subregions = {x.subregion(dev("develop_repair", s)[0]) for s in DEV_SEEDS}
    assert subregions == {"reliable_controller", "unreliable_controller"}


# ------------------------------------------------------------------ determinism and dev-seed runtime
@pytest.mark.parametrize("family", FAMILIES)
def test_solve_and_instance_are_deterministic_under_a_fixed_seed(family):
    x = item(family)
    a_data, a_truth = x.instance(3)
    b_data, b_truth = x.instance(3)
    assert json.dumps([a_data, a_truth], sort_keys=True) == json.dumps([b_data, b_truth], sort_keys=True)
    first = x.solve(copy.deepcopy(a_data), BUDGET)
    second = x.solve(copy.deepcopy(a_data), BUDGET)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_repair_randomness_lives_in_the_declared_seed():
    data, _ = dev("develop_repair", 0)
    data["message_loss"] = 0.3
    one = developmental.repair_solve(copy.deepcopy(data), BUDGET)
    data["seed"] = data["seed"] + 1
    two = developmental.repair_solve(copy.deepcopy(data), BUDGET)
    assert one["certificate"]["messages_per_step"] != two["certificate"]["messages_per_step"]
    assert two["certificate"]["seed"] == data["seed"]


@pytest.mark.parametrize("family", FAMILIES)
def test_dev_seeds_run_fast_verify_and_never_make_false_claims(family):
    x = item(family)
    for seed in DEV_SEEDS:
        started = time.perf_counter()
        data, truth = x.instance(seed)
        t0 = time.perf_counter()
        out = x.solve(copy.deepcopy(data), BUDGET)
        solve_s = time.perf_counter() - t0
        x.baseline(copy.deepcopy(data))
        x.competitor(copy.deepcopy(data))
        total_s = time.perf_counter() - started
        assert solve_s < 2.0 and total_s < 5.0, (seed, solve_s, total_s)
        assert out["status"] == "ANSWER"
        assert all(x.verify(data, out["output"], out["certificate"]).values()), seed
        assert x.score(data, truth, out["output"])["category"] == "correct", seed
