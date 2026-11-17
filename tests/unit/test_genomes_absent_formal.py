"""Property-based testing (L3), associative memory (L1) and cellular-automaton regeneration (L4): contract, withheld
registration, canonical path, Competency Compiler reachability, independent verification, refutation of corrupted
answers and forged certificates, invalid input and scoring.

Development seeds 0-9 only; held-out admission seeds are never generated here.
"""
from __future__ import annotations

import copy
import json
import math

import pytest

from greg.cognition import catalog, worlds
from greg.cognition.genomes import basal_memory, developmental_ca, formal, library
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

MODULES = (formal, basal_memory, developmental_ca)
ITEMS = {x.genome.family: x for m in MODULES for x in m.INTELLIGENCES}
FAMILIES = tuple(sorted(ITEMS))
SPEC = {  # family: (layer, operation, epistemic class, evidence type, world)
    "formal_property_search": (3, "find_property_counterexample", "deductive", "counterexample",
                               "mathematical_instance"),
    "basal_hopfield": (1, "associative_recall", "estimate", "heuristic_trace", "simulated_world"),
    "develop_ca_repair": (4, "regenerate_rule_pattern", "deductive", "developmental_trace", "simulated_world"),
}
BUDGET = {"latency_s": 8.0, "compute": 100000}
_CACHE: dict = {}


def dev(family, seed=1):
    assert 0 <= seed < 10                                       # never a held-out seed
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


def _answered(family):
    return [s for s in range(10) if solved(family, s)[2]["status"] == "ANSWER"]


# ------------------------------------------------------------------ genome contract and registration
def test_genomes_validate_with_declared_identity_and_world():
    assert set(FAMILIES) == set(SPEC)
    for family, x in ITEMS.items():
        g = x.genome
        assert isinstance(g, IntelligenceGenome) and g.validate() is g
        layer, op, cls, evidence, world = SPEC[family]
        assert (g.layer, g.operation, g.epistemic_class, g.evidence_type, g.dependency) == (layer, op, cls, evidence,
                                                                                            None)
        assert worlds.world("genome", family) == world
        assert g.buildability == "BUILDABLE_NOW" and g.standalone_decision and g.version == "1.0.0"
        assert g.authority_ceiling == g.consequence_limit == "read_only"
        assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
        assert len(g.known_failure_modes) >= 3 and g.counterindications and g.abstention_conditions
        assert g.baseline and g.competitor and x.subregion is not None and x.competitor_deployable
        assert "seeds 0-9 dev" in g.benchmark_suite


def test_each_absent_item_gets_its_layer():
    assert {ITEMS[f].genome.layer for f in FAMILIES} == {1, 3, 4}


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
def test_solve_is_compact_and_every_answer_verifies(family, seed):
    data, truth, out = solved(family, seed)
    assert out["status"] in ("ANSWER", "UNKNOWN"), out["missing"]
    _json_clean(out["certificate"])
    json.dumps(data, allow_nan=False)
    if out["status"] == "UNKNOWN":
        assert out["output"] is None and out["missing"]
        assert ITEMS[family].score(data, truth, None)["category"] == "abstain"
        return
    _json_clean(out["output"])
    checks = ITEMS[family].verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    score = ITEMS[family].score(data, truth, out["output"])
    assert score["category"] in ("correct", "abstain") and math.isfinite(score["quality"])   # never a false answer


def test_every_family_answers_on_some_development_seed():
    for family in FAMILIES:
        assert _answered(family), family


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_path_withholds_until_attached_and_creates_no_authority(family):
    from greg.cognition.cortex import reason, registry_view
    seed = _answered(family)[0]
    registry = registry_view()
    data, truth = dev(family, seed)
    request = {"problem_id": f"absent-formal-{family}", "operation": SPEC[family][1], "data": data,
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
    data, truth = dev(family, _answered(family)[0])
    cls = SPEC[family][2]
    request = {"problem_id": f"absent-formal-compile-{family}", "compile": {"geometry": {"geometry": cls},
                                                                            "data": data}}
    registry = registry_view()
    withheld = reason(request, registry=registry)
    assert withheld["state"] == "CAPABILITY_DEFICIT"
    assert withheld["withheld_best_fit"]["method"] == f"cognition.{family}"
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == f"cognition.{family}"
    assert r["methods_considered"] == [f"cognition.{family}"]
    assert r["derived_geometry"]["fits_by_inputs"] == [cls] and r["authority_created"] is False


# ------------------------------------------------------------------ property-based testing
def test_property_search_never_claims_absence_on_a_bug_free_function():
    clean = [s for s in range(10) if not dev("formal_property_search", s)[1]["buggy"]]
    assert clean
    for seed in clean:
        data, truth, out = solved("formal_property_search", seed)
        assert out["status"] == "UNKNOWN" and "not a proof" in out["missing"][0]
        proof = {"verdict": formal.PROVEN, "counterexample": None, "result": None}
        assert formal.property_search_verify(data, proof, out["certificate"]) == {"output_shape": False}


def test_property_search_counterexample_is_refuted_when_corrupted():
    seed = next(s for s in _answered("formal_property_search"))
    data, truth, out = solved("formal_property_search", seed)
    o, cert = out["output"], out["certificate"]
    name = sorted(o["counterexample"])[0]
    lie = copy.deepcopy(o)
    lie["result"] += 1
    assert formal.property_search_verify(data, lie, cert)["result_reexecuted"] is False
    outside = copy.deepcopy(o)
    outside["counterexample"][name] = data["function_under_test"]["parameters"][0]["max"] + 1
    assert formal.property_search_verify(data, outside, cert)["inputs_in_declared_domain"] is False
    assert formal.property_search_verify(data, o, dict(cert, evaluations=formal.PB_EVALUATIONS + 1))[
        "within_declared_budget"] is False
    assert ITEMS["formal_property_search"].score(data, truth, lie)["category"] == "wrong"


def test_property_search_refutes_an_input_on_which_the_property_holds():
    data, truth = dev("formal_property_search", 0)
    spec = formal._input(data)
    env = {n: lo for n, lo in zip(spec["names"], spec["lo"])}
    result = formal._mc_eval(spec["body"], env)
    held = {"verdict": formal.VERDICT, "counterexample": env, "result": result}
    if not formal._mc_eval(spec["property"], {**env, formal.RESULT: result}):
        pytest.skip("the domain's corner violates the property on this seed")
    checks = formal.property_search_verify(data, held, {"evaluations": 1})
    assert checks["result_reexecuted"] and checks["property_violated_on_reexecution"] is False


def test_property_search_planted_witnesses_reexecute_and_z3_agrees_with_construction():
    for seed in range(10):
        data, truth = dev("formal_property_search", seed)
        z = formal.property_search_z3(data)
        if truth["buggy"]:
            w = truth["witness"]
            spec = formal._input(data)
            r = formal._mc_eval(spec["body"], w)
            assert not formal._mc_eval(spec["property"], {**w, formal.RESULT: r})
            assert z["verdict"] == formal.VERDICT
            assert ITEMS["formal_property_search"].score(data, truth, z)["category"] == "correct"
        else:
            assert z["verdict"] == formal.PROVEN


def test_property_search_shrinks_toward_zero_and_stays_a_counterexample():
    for seed in _answered("formal_property_search"):
        data, truth, out = solved("formal_property_search", seed)
        spec = formal._input(data)
        x = tuple(out["output"]["counterexample"][n] for n in spec["names"])
        y, used = formal._shrink(spec, x, 200)
        assert used <= 200 and sum(map(abs, y)) <= sum(map(abs, x))
        env = dict(zip(spec["names"], y))
        r = formal._mc_eval(spec["body"], env)
        assert not formal._mc_eval(spec["property"], {**env, formal.RESULT: r})
        assert out["certificate"]["evaluations"] <= formal.PB_EVALUATIONS


def test_property_search_finds_a_literal_guard_uniform_search_misses():
    params = [{"name": "a", "min": -50000, "max": 50000}, {"name": "b", "min": -50000, "max": 50000}]
    spec = ["+", "a", "b"]
    data = {"function_under_test": {"parameters": params,
                                    "body": ["ite", ["and", ["==", "a", 31337], ["==", "b", -4242]],
                                             ["+", spec, 1], spec]},
            "property": ["==", "result", spec]}
    out = formal.property_search_solve(data, BUDGET)
    assert out["status"] == "ANSWER" and out["output"]["counterexample"] == {"a": 31337, "b": -4242}
    assert formal.property_search_uniform(data) is None


# ------------------------------------------------------------------ associative memory
def test_hopfield_replay_refutes_a_flipped_bit_a_wrong_index_and_a_forged_trace():
    seed = _answered("basal_hopfield")[0]
    data, truth, out = solved("basal_hopfield", seed)
    o, cert = out["output"], out["certificate"]
    bit = copy.deepcopy(o)
    bit["recalled"] = ("1" if o["recalled"][0] == "0" else "0") + o["recalled"][1:]
    checks = basal_memory.hopfield_verify(data, bit, cert)
    assert checks["trace_ends_at_the_recalled_state"] is False
    assert checks["memory_index_names_the_recalled_pattern"] is False
    other = dict(o, memory_index=(o["memory_index"] + 1) % len(data["stored_patterns"]))
    assert basal_memory.hopfield_verify(data, other, cert)["memory_index_names_the_recalled_pattern"] is False
    if cert["flips"]:
        forged = dict(cert, flips=cert["flips"] + [cert["flips"][-1]])
        assert basal_memory.hopfield_verify(data, o, forged)["every_flip_lowers_the_energy"] is False
    assert basal_memory.hopfield_verify(data, o, dict(cert, flips=[len(data["cue"])]))[
        "flip_trace_well_formed"] is False


def test_hopfield_refutes_the_nearest_neighbour_answer_where_the_network_cannot_reach_it():
    refuted = 0
    for seed in range(10):
        data, truth, out = solved("basal_hopfield", seed)
        nn = basal_memory.hopfield_nearest(data)
        if out["status"] != "ANSWER":
            checks = basal_memory.hopfield_verify(data, nn, {"flips": []})
            assert not all(checks.values())                     # the cue is not the stored pattern
            refuted += 1
    assert refuted


def test_hopfield_abstains_on_spurious_states_and_the_nearest_neighbour_is_never_worse():
    for seed in range(10):
        data, truth, out = solved("basal_hopfield", seed)
        nn = ITEMS["basal_hopfield"].score(data, truth, basal_memory.hopfield_nearest(data))
        mine = ITEMS["basal_hopfield"].score(data, truth, out["output"])
        assert nn["quality"] >= mine["quality"] - 1e-12
        if out["status"] == "UNKNOWN":
            assert "spurious" in out["missing"][0] or "settle" in out["missing"][0]


def test_hopfield_recalls_every_pattern_from_itself_at_low_load():
    import random
    r = random.Random("test:hopfield-fixed-points")
    patterns = ["".join(r.choice("01") for _ in range(128)) for _ in range(4)]
    for i, p in enumerate(patterns):
        out = basal_memory.hopfield_solve({"stored_patterns": patterns, "cue": p}, BUDGET)
        assert out["output"] == {"recalled": p, "memory_index": i} and out["certificate"]["flips"] == []


# ------------------------------------------------------------------ cellular-automaton regeneration
def test_ca_restores_only_true_cells_and_never_more_than_the_global_solver():
    for seed in range(10):
        data, truth, out = solved("develop_ca_repair", seed)
        z = developmental_ca.ca_global_z3(data)
        for t, row in enumerate(out["output"]["grid"]):
            for i, ch in enumerate(row):
                if ch != "?":
                    assert ch == truth["grid"][t][i]
                    assert z["grid"][t][i] == ch                   # every local restoration is globally entailed


def test_ca_replay_refutes_a_guessed_cell_a_changed_intact_cell_and_a_wrong_count():
    data, truth, out = solved("develop_ca_repair", 9)            # leaves undetermined cells on this seed
    o, cert = out["output"], out["certificate"]
    grid = o["grid"]
    t, i = next((t, i) for t, row in enumerate(grid) for i, ch in enumerate(row) if ch == "?")
    guessed = copy.deepcopy(o)
    guessed["grid"][t] = grid[t][:i] + truth["grid"][t][i] + grid[t][i + 1:]
    guessed["restored"] += 1
    guessed["undetermined"] -= 1
    forged = copy.deepcopy(cert)
    forged["rounds"].append([[t, i, int(truth["grid"][t][i])]])
    checks = developmental_ca.ca_verify(data, guessed, forged)
    assert checks["every_restored_cell_is_entailed"] is False      # a true but undetermined value is still a guess
    assert developmental_ca.ca_verify(data, guessed, cert)["output_is_the_replayed_grid"] is False
    t0, i0 = next((t, i) for t, row in enumerate(data["damaged_grid"]) for i, ch in enumerate(row) if ch != "?")
    changed = copy.deepcopy(o)
    changed["grid"][t0] = grid[t0][:i0] + ("1" if grid[t0][i0] == "0" else "0") + grid[t0][i0 + 1:]
    assert developmental_ca.ca_verify(data, changed, cert)["output_is_the_replayed_grid"] is False
    assert ITEMS["develop_ca_repair"].score(data, truth, changed)["category"] == "wrong"
    assert developmental_ca.ca_verify(data, dict(o, restored=o["restored"] + 1), cert)["counts_recomputed"] is False


def test_ca_replay_refutes_a_flipped_restoration():
    data, truth, out = solved("develop_ca_repair", 1)
    o, cert = copy.deepcopy(out["output"]), copy.deepcopy(out["certificate"])
    t, i, v = cert["rounds"][0][0]
    cert["rounds"][0][0][2] = 1 - v
    o["grid"][t] = o["grid"][t][:i] + str(1 - v) + o["grid"][t][i + 1:]
    assert developmental_ca.ca_verify(data, o, cert)["every_restored_cell_is_entailed"] is False
    assert ITEMS["develop_ca_repair"].score(data, truth, o)["category"] == "wrong"


def test_ca_refuses_intact_cells_that_contradict_the_rule():
    data, truth = dev("develop_ca_repair", 2)
    rows = list(data["damaged_grid"])
    t, i = next((t, i) for t in range(1, len(rows)) for i, ch in enumerate(rows[t]) if ch != "?"
                and "?" not in rows[t - 1][max(0, i - 1):i + 2] and 0 < i < len(rows[t]) - 1)
    rows[t] = rows[t][:i] + ("1" if rows[t][i] == "0" else "0") + rows[t][i + 1:]
    out = developmental_ca.ca_solve({"eca_rule": data["eca_rule"], "damaged_grid": rows}, BUDGET)
    assert out["status"] == "UNKNOWN" and "contradict" in out["missing"][0]


# ------------------------------------------------------------------ invalid input is refused, never crashes
@pytest.mark.parametrize("family,bad", [
    ("formal_property_search", {"function_under_test": {"parameters": [], "body": 0}, "property": True}),
    ("formal_property_search", {"function_under_test": {"parameters": [{"name": "result", "min": 0, "max": 1}],
                                                        "body": 0}, "property": True}),
    ("formal_property_search", {"function_under_test": {"parameters": [{"name": "a", "min": 0, "max": 1}],
                                                        "body": ["*", "a", "a"]}, "property": True}),
    ("formal_property_search", {"function_under_test": {"parameters": [{"name": "a", "min": 0, "max": 1}],
                                                        "body": "a"}, "property": "a"}),
    ("basal_hopfield", {"stored_patterns": ["0101010101", "01"], "cue": "0101010101"}),
    ("basal_hopfield", {"stored_patterns": ["0101010101"], "cue": "010101010x"}),
    ("basal_hopfield", {"stored_patterns": [], "cue": "0101010101"}),
    ("develop_ca_repair", {"eca_rule": 256, "damaged_grid": ["010", "1?0"]}),
    ("develop_ca_repair", {"eca_rule": 30, "damaged_grid": ["010", "1?"]}),
    ("develop_ca_repair", {"eca_rule": 30, "damaged_grid": ["010"]}),
    ("develop_ca_repair", {"eca_rule": 30, "damaged_grid": ["012", "1?0"]}),
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


def test_instances_are_deterministic_by_seed():
    for family in FAMILIES:
        assert json.dumps(ITEMS[family].instance(4)[0], sort_keys=True) == json.dumps(
            ITEMS[family].instance(4)[0], sort_keys=True)
