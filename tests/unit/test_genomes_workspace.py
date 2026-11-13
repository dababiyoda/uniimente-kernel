"""Global workspace genome (salience-gated selective broadcast among block specialists on a narrow bus): contract,
withheld registration, canonical path, independent verification, refutation of corrupted answers, bandwidth
accounting of every arm, competitor sanity, invalid input, abstention and scoring.

Development seeds 0-9 only; held-out admission seeds are never generated here.
"""
from __future__ import annotations

import copy
import itertools
import json
import math

import pytest

from greg.cognition import catalog
from greg.cognition.genomes import library
from greg.cognition.genomes import workspace as ws
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

FAMILY = "meta_global_workspace"
ITEM = {x.genome.family: x for x in ws.INTELLIGENCES}[FAMILY]
QUICK = (0, 1, 2, 3, 4, 7)
BUDGET = {"latency_s": 5.0, "compute": 100000}
ARMS = {"baseline": ws.ws_independent, "token_ring": ws.ws_token_ring, "bp_priority": ws.ws_bp_priority,
        "bp_round_robin": ws.ws_bp_round_robin, "blackboard": ws.ws_blackboard}
_CACHE: dict = {}


def dev(seed):
    assert 0 <= seed < 10                                       # never a held-out seed
    if seed not in _CACHE:
        _CACHE[seed] = ws.ws_instance(seed)
    data, truth = _CACHE[seed]
    return copy.deepcopy(data), truth


def solved(seed):
    key = ("solved", seed)
    if key not in _CACHE:
        _CACHE[key] = ws.ws_solve(dev(seed)[0], BUDGET)
    data, truth = dev(seed)
    return data, truth, copy.deepcopy(_CACHE[key])


def ok(data, output):
    return all(ws.ws_verify(data, output, {}).values())


def brute_minimum(data):
    return min(ws.energy(data, list(x)) for x in itertools.product((0, 1), repeat=data["n"]))


def tiny(owner, unary, edges, bits=200, rounds=20, bound=2.5):
    return {"n": len(owner), "owner": owner, "unary": unary, "edges": edges, "coupling_bound": bound,
            "bus": {"bits_per_round": bits, "rounds": rounds}}


# ------------------------------------------------------------------ genome contract and registration
def test_genome_validates_with_declared_identity():
    g = ITEM.genome
    assert isinstance(g, IntelligenceGenome) and g.validate() is g
    assert (g.layer, g.operation, g.epistemic_class, g.evidence_type, g.dependency) == (
        5, "global_workspace_broadcast", "optimization", "collective_trace", None)
    assert g.buildability == "BUILDABLE_NOW" and g.standalone_decision and g.version == "1.0.0"
    assert g.authority_ceiling == g.consequence_limit == "read_only"
    assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
    assert "seeds 0-9 dev" in g.benchmark_suite and "synthetic" in g.benchmark_suite
    assert ITEM.competitor is ws.ws_token_ring and ITEM.baseline is ws.ws_independent and ITEM.competitor_deployable
    assert any("priority bits are bus cost" in m for m in g.known_failure_modes)
    assert "Disclosure" in ws.__doc__ and "added after the development run" in ws.__doc__


def test_registered_in_the_one_catalog_and_withheld():
    assert library.executables()[FAMILY] is ITEM
    g = ITEM.genome
    assert catalog.FAMILIES[FAMILY] == (g.layer, (g.operation,), (g.epistemic_class,), "genome_certificate", None)
    assert catalog.initial_state(f"cognition.{FAMILY}") == "VERIFIED"           # registered, never auto-attached


def test_module_imports_no_heavy_package_at_top_level():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(ws))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top for a in n.names} | {
        n.module.split(".")[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"numpy", "scipy", "networkx", "ortools", "z3"}


def test_instances_are_deterministic_bounded_and_their_truth_is_exact():
    for seed in range(10):
        a, ta = dev(seed)
        b, tb = ws.ws_instance(seed)
        assert a == b and ta == tb
        assert 12 <= a["n"] <= ws.WS_TRUTH_MAX_N and 3 <= max(a["owner"]) + 1 <= 4
        assert 24 <= a["bus"]["bits_per_round"] <= 64 and 3 <= a["bus"]["rounds"] <= 8
        assert any(a["owner"][u] != a["owner"][w] for u, w, _ in a["edges"])
        assert len(json.dumps(a)) < 16 * 1024
    data, truth = dev(3)
    small = tiny(data["owner"][:12], data["unary"][:12], [e for e in data["edges"] if e[0] < 12 and e[1] < 12])
    assert ws.exact_minimum(small) == pytest.approx(brute_minimum(small), abs=1e-9)


# ------------------------------------------------------------------ solve / verify on development seeds
@pytest.mark.parametrize("seed", QUICK)
def test_solve_answers_compactly_within_the_bus_and_verifies(seed):
    data, truth, out = solved(seed)
    assert out["status"] == "ANSWER", out["missing"]
    o = out["output"]
    assert len(json.dumps(out, allow_nan=False)) < 32 * 1024
    checks = ws.ws_verify(data, o, out["certificate"])
    assert checks and all(checks.values()), checks
    assert ITEM.score(data, truth, o)["category"] == "correct"
    assert o["energy"] == pytest.approx(ws.energy(data, o["assignment"]))
    assert o["energy"] >= truth["min_energy"] - 1e-9
    size = ws.frame_bits("decision_priority", data["n"])
    assert all(len(r) * size <= data["bus"]["bits_per_round"] for r in o["trace"])
    assert o["bits_used"] == size * sum(len(r) for r in o["trace"]) and o["rounds_used"] <= data["bus"]["rounds"]
    assert ws.ws_solve(copy.deepcopy(data), BUDGET) == out                       # deterministic


def test_no_rounds_means_no_communication_and_the_baseline_answer():
    data, truth = dev(0)
    data["bus"]["rounds"] = 0
    out = ws.ws_solve(data, BUDGET)
    assert out["status"] == "ANSWER" and out["output"]["trace"] == [] and out["output"]["bits_used"] == 0
    assert out["output"]["assignment"] == ws.ws_independent(data)["assignment"]
    assert ok(data, out["output"])


def test_workspace_beats_no_communication_on_development_seeds():
    better = 0
    for seed in range(10):
        data, truth, out = solved(seed)
        q = ITEM.score(data, truth, out["output"])["quality"]
        better += q > ITEM.score(data, truth, ws.ws_independent(data))["quality"] + 1e-9
    assert better >= 8


@pytest.mark.parametrize("arm", sorted(ARMS))
def test_every_arm_answers_within_the_same_bus_budget(arm):
    for seed in QUICK:
        data, truth = dev(seed)
        out = ARMS[arm](data)
        assert ITEM.score(data, truth, out)["category"] == "correct"
        assert len(out["trace"]) <= data["bus"]["rounds"]
        for frames in out["trace"]:
            assert sum(ws.frame_bits(f["kind"], data["n"]) for f in frames) <= data["bus"]["bits_per_round"]
    assert ITEM.score(data, truth, None)["category"] == "abstain"


def test_canonical_path_withholds_until_attached_and_creates_no_authority():
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    data, truth = dev(0)
    request = {"problem_id": "workspace-dev-0", "operation": "global_workspace_broadcast", "data": data,
               "geometry": {"latency_limit": 30}}
    assert reason(request, registry=registry)["abstention_state"] == "CAPABILITY_DEFICIT"
    registry.set_state(f"cognition.{FAMILY}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["abstention_state"] == "NONE" and r["proof_type"] == "genome_certificate"
    assert r["proof_artifact"]["evidence_type"] == "collective_trace"
    assert r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" and r["authority_created"] is False
    assert ITEM.score(data, truth, r["output"])["category"] == "correct"


def test_the_competency_compiler_reaches_the_family_by_its_inputs(tmp_path, monkeypatch):
    """Evaluation only: an in-memory attach (no body, journal or founder pin) and an empty evidence index."""
    from greg.cognition import compiler
    from greg.cognition.cortex import reason, registry_view
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")
    data, truth = dev(0)
    request = {"problem_id": "workspace-compile-0", "compile": {"geometry": {"geometry": "optimization"},
                                                                 "data": data}}
    registry = registry_view()
    withheld = reason(request, registry=registry)
    assert withheld["state"] == "CAPABILITY_DEFICIT"
    assert withheld["withheld_best_fit"]["method"] == f"cognition.{FAMILY}"
    registry.set_state(f"cognition.{FAMILY}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == f"cognition.{FAMILY}"
    assert r["methods_considered"] == [f"cognition.{FAMILY}"] and r["authority_created"] is False
    assert ITEM.score(data, truth, r["result"])["category"] == "correct"


# ------------------------------------------------------------------ independent verification
def _corruptions(data, o):
    x, trace = o["assignment"], o["trace"]
    first = trace[0]
    out = {
        "assignment_bit_flipped": {**o, "assignment": [1 - x[0]] + x[1:],
                                   "energy": ws.energy(data, [1 - x[0]] + x[1:])},
        "energy_misreported": {**o, "energy": o["energy"] - 0.5},
        "assignment_truncated": {**o, "assignment": x[:-1]},
        "frame_value_flipped": {**o, "trace": [[{**first[0], "value": 1 - first[0]["value"]}] + first[1:]]
                                + trace[1:]},
        "priority_inflated": {**o, "trace": [[{**first[0], "priority": min(255, first[0]["priority"] + 3)
                                               if first[0]["priority"] < 252 else 0}] + first[1:]] + trace[1:]},
        "bits_misreported": {**o, "bits_used": o["bits_used"] - 1},
        "rounds_misreported": {**o, "rounds_used": o["rounds_used"] + 1},
        "quiescence_flag_flipped": {**o, "quiescent": not o["quiescent"]},
        "first_round_dropped": {**o, "trace": trace[1:], "rounds_used": len(trace) - 1,
                                "bits_used": o["bits_used"] - len(first) * ws.frame_bits("decision_priority",
                                                                                         data["n"])},
        "frame_duplicated": {**o, "trace": [first + [first[0]]] + trace[1:]},
        "empty_round_appended": {**o, "trace": trace + [[]], "rounds_used": len(trace) + 1},
        "unknown_frame_kind": {**o, "trace": [[{**first[0], "kind": "decision"}] + first[1:]] + trace[1:]},
        "baseline_assignment_claimed": {**o, "assignment": ws.ws_independent(data)["assignment"],
                                        "energy": ws.energy(data, ws.ws_independent(data)["assignment"])},
    }
    if len(first) > 1:
        out["frame_order_swapped"] = {**o, "trace": [first[::-1]] + trace[1:]}
        out["frame_dropped_below_capacity"] = {**o, "trace": [first[1:]] + trace[1:]}
    return out


@pytest.mark.parametrize("seed", QUICK)
def test_verifier_rejects_every_corruption(seed):
    data, _, out = solved(seed)
    o = out["output"]
    assert ok(data, o)
    for name, bad in _corruptions(data, o).items():
        if bad == o or (name == "baseline_assignment_claimed" and bad["assignment"] == o["assignment"]):
            continue
        if name == "frame_order_swapped" and o["trace"][0][0]["priority"] == o["trace"][0][-1]["priority"]:
            bad["trace"][0][0], bad["trace"][0][-1] = bad["trace"][0][-1], bad["trace"][0][0]   # id order
        assert not ok(data, bad), name


def test_verifier_rejects_a_trace_over_the_bus_or_round_limit():
    data, _, out = solved(1)
    o = out["output"]
    narrow = copy.deepcopy(data)
    narrow["bus"]["bits_per_round"] = ws.frame_bits("decision_priority", data["n"]) * max(len(r) for r in o["trace"]) - 1
    assert not ok(narrow, o)
    short = copy.deepcopy(data)
    short["bus"]["rounds"] = len(o["trace"]) - 1
    assert len(o["trace"]) >= 1 and not ok(short, o)


def test_competitor_and_alternative_traces_never_pass_the_workspace_verifier():
    data, _ = dev(0)
    for arm in ARMS.values():
        out = arm(data)
        forged = {"assignment": out["assignment"], "energy": ws.energy(data, out["assignment"]),
                  "trace": out["trace"], "bits_used": 0, "rounds_used": len(out["trace"]), "quiescent": True}
        assert not ok(data, forged)


@pytest.mark.parametrize("junk", [None, 3, [], {}, "answer", {"assignment": None},
                                  {"assignment": [0], "energy": 0.0, "trace": [], "bits_used": 0, "rounds_used": 0,
                                   "quiescent": True}])
def test_malformed_outputs_are_refuted_not_raised(junk):
    data, _ = dev(0)
    assert not ok(data, junk)


# ------------------------------------------------------------------ competitors: correctness of the mechanisms
def test_bp_competitors_are_exact_on_trees_with_unquantised_beliefs(monkeypatch):
    """One variable per specialist and an ample bus: min-sum BP is exact on a tree (ties aside)."""
    import random
    monkeypatch.setattr(ws, "BELIEF_LEVELS", 10 ** 9)
    for t in range(40):
        r = random.Random(f"tree:{t}")
        n = r.randint(4, 10)
        edges = [[r.randrange(v), v, round(r.uniform(-2, 2), 4)] for v in range(1, n)]
        data = tiny(list(range(n)), [round(r.gauss(0, 0.5), 4) for _ in range(n)], edges, bits=4000, rounds=40)
        m = brute_minimum(data)
        for arm in (ws.ws_bp_priority, ws.ws_bp_round_robin):
            assert ws.energy(data, arm(data)["assignment"]) == pytest.approx(m, abs=1e-6), (t, arm.__name__)


def test_on_an_ample_bus_the_token_ring_settles_and_the_synchronous_workspace_can_oscillate():
    """Recorded negative result (development seeds): with bits to spare every proposal is admitted at once, and the
    synchronous workspace flips frustrated boundaries back and forth (Jacobi oscillation) until the round limit,
    while the token ring stops at a block-coordinate local optimum. The capacity limit is what makes it work."""
    oscillated = 0
    for seed in (0, 1, 3, 5):
        data, truth = dev(seed)
        data["bus"] = {"bits_per_round": 4000, "rounds": 50}
        out = ws.ws_solve(data, {"latency_s": 5.0, "compute": 10 ** 7})["output"]
        assert ok(data, out)
        oscillated += not out["quiescent"]
        x = ws.ws_token_ring(data)["assignment"]
        e = ws.energy(data, x)
        for b in range(max(data["owner"]) + 1):
            vs = [v for v in range(data["n"]) if data["owner"][v] == b]
            for xs in itertools.product((0, 1), repeat=len(vs)):
                y = list(x)
                for v, val in zip(vs, xs):
                    y[v] = val
                assert ws.energy(data, y) >= e - 1e-9
    assert oscillated >= 1


# ------------------------------------------------------------------ scoring, abstention and input bounds
def test_score_marks_an_over_budget_answer_wrong():
    data, truth = dev(2)
    out = ws.ws_token_ring(data)
    assert ITEM.score(data, truth, out)["category"] == "correct"
    greedy = {"assignment": out["assignment"],
              "trace": [[{"kind": "decision", "var": 0, "value": 0}] * 100]}
    s = ITEM.score(data, truth, greedy)
    assert s["category"] == "wrong" and s["quality"] < ITEM.score(data, truth, None)["quality"]
    too_long = {"assignment": out["assignment"], "trace": [[]] * (data["bus"]["rounds"] + 1)}
    assert ITEM.score(data, truth, too_long)["category"] == "wrong"
    assert ITEM.score(data, truth, {"assignment": out["assignment"], "trace": [[{"kind": "telepathy"}]]})[
        "category"] == "wrong"


def test_score_is_minus_the_energy_gap_to_the_exact_minimum():
    data, truth = dev(4)
    x = ws.ws_independent(data)["assignment"]
    assert ITEM.score(data, truth, {"assignment": x, "trace": []})["quality"] == pytest.approx(
        truth["min_energy"] - ws.energy(data, x))
    small = tiny([0, 0, 1, 1, 2, 2], [0.3, -0.2, 0.1, 0.4, -0.5, 0.2],
                 [[0, 1, 1.0], [1, 2, -1.5], [2, 3, 0.7], [3, 4, -2.0], [4, 5, 1.1], [0, 5, 0.9]])
    best = min(itertools.product((0, 1), repeat=6), key=lambda y: ws.energy(small, list(y)))
    t = {"min_energy": ws.exact_minimum(small), "upper_bound": 10.0}
    assert ITEM.score(small, t, {"assignment": list(best), "trace": []})["quality"] == pytest.approx(0.0, abs=1e-9)


def test_abstains_on_a_bus_too_narrow_for_one_frame_or_a_small_compute_budget():
    data, _ = dev(0)
    data["bus"]["bits_per_round"] = ws.frame_bits("decision_priority", data["n"]) - 1
    out = ws.ws_solve(data, BUDGET)
    assert out["status"] == "ABSTAIN" and "too narrow" in out["missing"][0]
    data, _ = dev(0)
    out = ws.ws_solve(data, {"latency_s": 1.0, "compute": 10})
    assert out["status"] == "ABSTAIN" and "compute budget" in out["missing"][0]


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(n=1),
    lambda d: d.update(owner=d["owner"][:-1]),
    lambda d: d.update(owner=[0] * d["n"]),                                   # one specialist only
    lambda d: d.update(owner=[0] * 11 + [1] * (d["n"] - 11)),                # a block over 10 variables
    lambda d: d["edges"].append([0, 0, 1.0]),
    lambda d: d["edges"].append(list(d["edges"][0])),                        # duplicate edge
    lambda d: d["edges"].append([0, d["n"] - 1, 9.0]) if [0, d["n"] - 1] not in [e[:2] for e in d["edges"]]
    else d["edges"].__setitem__(0, [d["edges"][0][0], d["edges"][0][1], 9.0]),   # |J| above the bound
    lambda d: d.update(unary=[float("nan")] * d["n"]),
    lambda d: d.update(bus={"bits_per_round": 0, "rounds": 3}),
    lambda d: d.update(bus={"bits_per_round": 30, "rounds": 3, "extra": 1}),
    lambda d: d.update(coupling_bound=-1.0),
    lambda d: d.update(edges="x"),
])
def test_invalid_input_raises_a_genome_error(mutate):
    data, _ = dev(0)
    mutate(data)
    with pytest.raises(GenomeError):
        ws.ws_solve(data, BUDGET)


def test_subregion_is_computed_from_the_data_alone():
    labels = {ws.ws_subregion(dev(s)[0]) for s in range(10)}
    assert labels <= {f"{a}_bus_{b}_cross" for a in ("narrow", "wide") for b in ("strong", "weak")}
    assert len(labels) >= 2
    assert all(math.isfinite(dev(s)[1]["min_energy"]) for s in range(10))
