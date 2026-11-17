"""develop_repair_hybrid: a central plan audited by the local repair rules (directive 2026-10-21, section 7).

Development seeds 0-9 only (even seeds reliable controller; 1, 5, 9 crash; 3, 7 stale). The review measurement is
scripts/repair_hybrid_explore.py under its committed declaration; nothing here reads review seeds.
"""
from __future__ import annotations

import copy
import json

import pytest

from greg.cognition import catalog, worlds
from greg.cognition.genomes import developmental as D
from greg.cognition.genomes import developmental_hybrid as HY
from greg.cognition.genomes import library

RELIABLE, CRASH, STALE = (0, 2, 4, 6, 8), (1, 5, 9), (3, 7)


@pytest.fixture(scope="module")
def items():
    return {s: D.repair_instance(s) for s in range(10)}


@pytest.fixture(scope="module")
def solved(items):
    return {s: HY.hybrid_solve(data, {}) for s, (data, _) in items.items()}


def test_registered_withheld_and_declared(items):
    item = library.executables()["develop_repair_hybrid"]
    g = item.genome
    assert g.layer == 4 and g.version == HY.VERSION and g.operation == "target_state_repair_hybrid"
    assert g.authority_ceiling == "read_only" and g.held_out_result == "UNEVALUATED"
    assert item.baseline is HY.hybrid_local_only and item.competitor is D.repair_central_replanner
    assert item.instance is D.repair_instance and item.verify is HY.hybrid_verify
    assert "develop_repair_hybrid" in catalog.FAMILIES
    assert catalog.initial_state("cognition.develop_repair_hybrid") == "VERIFIED"       # registered, withheld
    assert worlds.GENOMES["develop_repair_hybrid"][0] == worlds.SIMULATED
    assert set(g.required_inputs) <= set(items[0][0])


def test_the_hybrid_is_the_planner_exactly_where_the_controller_is_reliable(items, solved):
    for s in RELIABLE:
        data, truth = items[s]
        out = solved[s]
        central = D.repair_central_replanner(data)
        assert out["certificate"]["first_discrepancy_step"] is None and out["certificate"]["owner"] == "planner"
        assert out["output"]["actions"] == central["actions"] and out["output"]["claimed"] == central["claimed"]
        assert D.repair_score(data, truth, out["output"]) == D.repair_score(data, truth, central)


def test_stale_controllers_are_caught_by_the_audit_and_their_false_claims_disappear(items, solved):
    for s in STALE:
        data, truth = items[s]
        assert D.repair_score(data, truth, D.repair_central_replanner(data))["category"] == "wrong"
        assert D.repair_score(data, truth, HY.hybrid_naive_switch(data))["category"] == "wrong"  # no cross-check
        out = solved[s]
        assert out["certificate"]["first_discrepancy_step"] == 0 and out["certificate"]["owner"] == "local"
        assert D.repair_score(data, truth, out["output"])["category"] == "correct"
        assert D.repair_score(data, truth, out["output"])["quality"] > 0.9


def test_vouching_without_fallback_removes_false_claims_but_not_the_lost_function(items, solved):
    for s in STALE:
        data, truth = items[s]
        vouch = D.repair_score(data, truth, HY.hybrid_vouch_only(data))
        assert vouch["category"] == "correct"
        assert vouch["quality"] < D.repair_score(data, truth, solved[s]["output"])["quality"]


def test_the_audit_never_reads_the_controllers_declared_condition(items, solved):
    for s in (3, 9, 4):
        data = copy.deepcopy(items[s][0])
        data["controller"]["mode"] = "reliable" if data["controller"]["mode"] != "reliable" else "stale"
        assert HY.hybrid_solve(data, {}) == solved[s]


def test_every_dev_answer_passes_the_independent_verifier(items, solved):
    for s, (data, _) in items.items():
        out = solved[s]
        assert out["status"] == "ANSWER"
        checks = HY.hybrid_verify(data, out["output"], out["certificate"])
        assert all(checks.values()), (s, checks)


def _mutants(data, out, cert):
    inp = D._repair_inputs(data)
    dead, blocked = D._realized(inp)
    H = data["height"]
    sources = [D._key(x * H + y, H) for x, y in data["sources"]]
    unclaimed = [k for k in sources if k not in out["claimed"]                 # a claim that does not deliver
                 and D._follow(D._parse_key(k, data["width"], H), out["next_hop"], inp, dead, blocked) is None]
    dead_key = D._key(sorted(dead)[0], H)
    some = sorted(out["next_hop"])[0]
    yield "false claim", {**out, "claimed": sorted(out["claimed"] + unclaimed[:1])}, {**cert, "vouched_sources":
                                                                                       len(out["claimed"]) + 1}
    yield "duplicate claim", {**out, "claimed": out["claimed"] + out["claimed"][:1]}, cert
    yield "claim a non-source", {**out, "claimed": out["claimed"] + [some]}, cert
    yield "pointer into a failed unit", {**out, "next_hop": {**out["next_hop"], some: dead_key}}, cert
    yield "off-lattice pointer", {**out, "next_hop": {**out["next_hop"], some: "99,99"}}, cert
    yield "undercounted actions", {**out, "actions": out["actions"] - 1}, cert
    yield "hidden local messages", {**out, "actions": out["actions"] - cert["actions_breakdown"]["local"] + 1}, {
        **cert, "local_messages_per_step": [], "first_discrepancy_step": None,
        "actions_breakdown": {**cert["actions_breakdown"], "local": 1}}
    yield "audit forged", out, {**cert, "first_discrepancy_step": None if cert["first_discrepancy_step"] is not None
                                else 0}
    yield "forged planner count", {**out, "actions": out["actions"] + 1}, {
        **cert, "actions_breakdown": {**cert["actions_breakdown"], "planner": cert["actions_breakdown"]["planner"] + 1}}
    yield "wrong steps", {**out, "steps": out["steps"] + 1}, cert
    yield "seed unbound", out, {**cert, "seed": cert["seed"] + 1}
    yield "external effect", out, {**cert, "external_effects": 1}
    yield "unknown owner", out, {**cert, "owner": "oracle"}


@pytest.mark.parametrize("seed", [0, 3, 9])
def test_the_verifier_refutes_every_mutation(items, solved, seed):
    data = items[seed][0]
    out, cert = solved[seed]["output"], solved[seed]["certificate"]
    for name, o, c in _mutants(data, out, cert):
        if name == "false claim" and len(o["claimed"]) == len(out["claimed"]):
            continue                                      # every live source already claimed
        checks = HY.hybrid_verify(data, json.loads(json.dumps(o)), json.loads(json.dumps(c)))
        assert not all(checks.values()), name


def test_abstains_outside_the_local_protocols_validated_loss(items):
    data = copy.deepcopy(items[0][0])
    data["message_loss"] = 0.6
    assert HY.hybrid_solve(data, {})["status"] == "ABSTAIN"


def test_the_exploration_script_refuses_undeclared_seeds():
    from scripts import repair_hybrid_explore as X
    assert X.guard(range(10)) and X.guard(range(4000, 4640))
    for bad in ((1000,), (1500,), (3999,), (4640,), (0, 4000)):
        with pytest.raises(ValueError):
            X.guard(bad)


# -- mission resumption: the canonical Capability Genesis path in a temp state dir -------------------------------

def test_a_repair_mission_blocked_by_the_deficit_resumes_on_the_attached_hybrid_and_its_answer_is_verified(
        tmp_path, monkeypatch, items):
    """Directive section 7: "A script that constructs a tool is incomplete until the permitted mission resumes and
    the resulting answer or outcome is verified." A founder-signed repair mission on a stale-controller instance (dev
    seed 3, where the replanner alone makes a false restoration claim) finds no attached method; the one Genesis loop
    names the registered, withheld hybrid; GREG attaches nothing; the founder's signed CAPABILITY_ATTACH (a test key,
    not Alfonso's) attaches it; the ORIGINAL mission resumes and closes; the answer is certified by the hybrid's
    verifier on the body and re-checked here against the benchmark truth."""
    pytest.importorskip("scipy")
    from greg.body import Body
    from greg.cognition import compiler
    from tests.greg_fixtures import Clock, drop, make_body, signed
    from tests.unit.test_greg_cognition_genesis import attach_asks, compilations, compile_mission, ticks

    index = tmp_path / "index.json"
    index.write_text(json.dumps({"genomes": {}, "recipes": {}, "routing": {}}))
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", index)
    data, truth = items[3]
    assert D.repair_score(data, truth, D.repair_central_replanner(data))["category"] == "wrong"
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", compile_mission("m:repair", {"geometry": "physical"}, data)))
    clock = Clock()
    hybrid = "cognition.develop_repair_hybrid"
    with Body(home, clock=clock) as body:
        body.boot()
        assert body.registry.state[hybrid] == "VERIFIED"
        assert ticks(body, clock, 3)[-1]["state"] in ("BLOCKED", "WAITING")      # blocked by the deficit
        assert list(body.journal.replay("deficit.opened"))
        routes = {e.payload["capability_id"]: e.payload["result"] for e in body.journal.replay("genesis.route")
                  if e.payload["route"] == "genome_library"}
        assert routes[hybrid].startswith(f"attach candidate: {hybrid} (UNEVALUATED)")
        assert hybrid in [e.payload["capability_id"] for e in body.journal.replay("deficit.awaiting_attach")]
        assert body.registry.state[hybrid] == "VERIFIED"                        # GREG attached nothing
        assert len(attach_asks(body)) == 1
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": hybrid}))
        assert body.registry.state[hybrid] == "ATTACHED"
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]          # the original mission resumed
        answered = [c for c in compilations(body) if c["state"] == "ANSWERED"][-1]
        assert answered["method_or_composition_selected"] == hybrid
        assert answered["authority_created"] is False
        output = answered["result"]
    solve = HY.hybrid_solve(data, {})
    assert output == solve["output"]
    assert all(HY.hybrid_verify(data, output, solve["certificate"]).values())        # the independent verifier
    assert D.repair_score(data, truth, output)["category"] == "correct"            # and the benchmark truth
