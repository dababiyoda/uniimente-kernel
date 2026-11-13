"""Abstention-to-resolution: an abstaining cognition step names the one founder decision that would let it answer.

The producer (greg/cognition/resolution.py) reads the cortex or compile receipt; the consumer
(MissionEngine._resolution_ask) asks exactly that, once, with an unsigned prepared command, and the mission waits.
A resolution is a proposal, never authority; FORM leaves Capability Genesis unchanged.
"""
import copy
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("z3")
pytest.importorskip("ortools")

from cortex.genome import seed_registry  # noqa: E402
from greg.cognition import bridge, resolution  # noqa: E402
from greg.cognition.cortex import reason, registry_view  # noqa: E402

DECL = {"consequence_class": "internal_write", "reversibility": "reversible"}
FERMI = {"target": {"name": "weekly_hours", "unit": "h"},
         "variables": [{"name": "jobs", "unit": "1", "low": 20, "high": 30},
                       {"name": "hours_per_job", "unit": "h", "low": 1.5, "high": 2.5}],
         "expression": ["*", "jobs", "hours_per_job"], "dependencies": [], "reference_class": None, "seed": 7}


def request(payload, pid="t:resolution"):
    payload = dict(payload)
    payload.setdefault("declared", DECL)
    return {"problem_id": pid, "problem": {"question": "how many hours?", "payload": payload}}


class TestProducer:
    def test_part_table_covers_exactly_the_bridged_solver_organs(self):
        assert set(resolution.PART_OF) == set(bridge.ORGANS)
        enabled = {k for k, p in seed_registry().profiles().items() if p.enabled and p.role == "solver"}
        assert set(resolution.PART_OF) == enabled

    def test_missing_input_is_supply_inputs_naming_the_part(self):
        r = reason(request({"declared": {**DECL, "epistemic_class": "estimate"}}), registry=registry_view())
        res = r["resolution"]
        assert res["kind"] == "SUPPLY_INPUTS" and res["inputs"] == ["estimation_model"]
        assert res["verified"] is False and res["authority"] == resolution.AUTHORITY
        from greg.cognition.settlement import _valid_receipt
        assert _valid_receipt(r)                     # a typed, digest-bound receipt field
        forged = {**r, "resolution": {**res, "verified": True}}
        assert not _valid_receipt(forged)

    def test_detached_organ_is_attach_naming_its_greg_id(self):
        registry = registry_view()
        registry.set_state("cognition.cortex.estimation.fermi", "DETACHED")
        r = reason(request({"estimation_model": FERMI}), registry=registry)
        assert r["resolution"]["kind"] == "ATTACH"
        assert r["resolution"]["capabilities"] == ["cognition.cortex.estimation.fermi"]

    def test_protection_question_is_a_human_handoff(self):
        protection = {"relevant": True, "required_actions": ["immediate_protection", "escalation"],
                      "evidence_access": "need_to_know", "disclosure_controls": ["no disclosure without consent"]}
        r = reason(request({"estimation_model": FERMI, "victim_protection": protection}), registry=registry_view())
        assert r["abstention_state"] == "HUMAN_REVIEW_REQUIRED" and r["resolution"]["kind"] == "HUMAN_HANDOFF"

    def test_an_answered_receipt_carries_no_resolution(self):
        r = reason(request({"estimation_model": FERMI}), registry=registry_view())
        assert r["abstention_state"] == "NONE" and "resolution" not in r

    def test_compile_receipts(self):
        detached = {"state": "CAPABILITY_DEFICIT", "geometry": {"geometry": "estimate"},
                    "derived_geometry": {"declared": "estimate", "fits_by_inputs": ["estimate"], "agrees": True},
                    "capability_deficit": {"function": "cognition.estimate:x", "verification": {"unserviceable": [
                        {"method": "cognition.cortex.estimation.fermi", "why": "state DETACHED"}]}}}
        assert resolution.from_compile(detached) is None      # Genesis's awaiting-attach path owns it
        wrong = copy.deepcopy(detached)
        wrong["capability_deficit"]["verification"]["unserviceable"] = []
        wrong["derived_geometry"] = {"declared": "constraint_feasibility", "fits_by_inputs": ["estimate"],
                                     "agrees": False}
        assert resolution.from_compile(wrong) == {**resolution.from_compile(wrong), "kind": "CORRECT_DECLARATION",
                                                  "declare": "estimate"}
        unknown = copy.deepcopy(wrong)
        unknown["derived_geometry"] = {"declared": "optimization", "fits_by_inputs": [], "agrees": True}
        assert resolution.from_compile(unknown)["kind"] == "FORM"
        supply = {"state": "ABSTAIN", "geometry": {"geometry": "constraint_feasibility"},
                  "missing_information": [{"method": "cognition.formal", "missing_inputs": ["constraints", "variables"]}]}
        assert resolution.from_compile(supply)["inputs"][0] == "formal_model"

    def test_read_refuses_anything_that_claims_verification_or_authority(self):
        good = resolution._resolution("ATTACH", "x", capabilities=["c"])
        assert resolution.read({"resolution": good}) == good
        assert resolution.read({"resolution": {**good, "verified": True}}) is None
        assert resolution.read({"resolution": {**good, "authority": "founder"}}) is None
        assert resolution.read({"resolution": {**good, "kind": "GRANT"}}) is None
        assert resolution.read(None) is None


# ------------------------------------------------------------------ the mission engine consumes it
def _run(payload, *, detach=(), sign=True, patch=None):
    from greg.body import Body
    from tests.greg_fixtures import Clock, drop, make_body, mission, signed
    home, key, body_id, _ = make_body(Path(tempfile.mkdtemp(prefix="resolution-")))
    for i, cid in enumerate(detach):
        drop(home, signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": cid}), name=f"a{i}-detach.json")
    params = request(payload, pid="t:engine")
    spec = mission("m:resolution-engine", checks=[{
        "check_id": "answered", "description": "the question is answered",
        "sensor": {"capability": "cognition.solve", "target": "cognition:t", "params": params},
        "predicate": {"op": "equals", "field": "abstention_state", "value": "NONE"}}],
        strategies=[{"action_id": "solve", "capability": "cognition.solve", "target": "cognition:t",
                     "params": params, "advances": ["answered"], "rationale": "answer"}],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="internal_write")
    drop(home, signed(key, body_id, "MISSION", spec), name="z-mission.json")
    clock = Clock()
    with Body(home, clock=clock) as body:
        if patch:
            patch(body)
        body.boot()
        for _ in range(3):
            body.tick()
            clock.advance(31)
        asks = [e.payload for e in body.journal.replay("decision.requested")]
        out = {"asks": asks, "spec": spec}
        prepared = next((a["prepared_command"] for a in asks if a.get("prepared_command")), None)
        if sign and prepared and not prepared["founder_supplies"]:
            drop(home, signed(key, body_id, prepared["kind"], prepared["body"]), name="zz-founder.json")
            for _ in range(3):
                body.tick()
                clock.advance(31)
        out["status"] = {mid: m.status for mid, m in body.engine.book.missions.items()}
        out["genesis"] = [e.payload for e in body.journal.replay("deficit.opened")]
        return out


class TestConsumer:
    def test_one_signed_attach_closes_a_mission_its_detach_stopped(self):
        out = _run({"estimation_model": FERMI}, detach=["cognition.cortex.estimation.fermi"])
        attach = [a for a in out["asks"] if a.get("prepared_command")]
        assert [a["kind"] for a in attach] == ["CAPABILITY_ATTACH"]
        assert attach[0]["prepared_command"]["body"] == {"capability_id": "cognition.cortex.estimation.fermi"}
        assert not any(a["kind"] == "NO_STRATEGY" for a in out["asks"])
        assert out["status"]["m:resolution-engine"] == "ACHIEVED"

    def test_without_the_consumer_the_same_mission_ends_in_a_generic_ask(self):
        from greg import missions

        def ablate(body):
            body.engine._resolution_ask = lambda *a, **k: None
        out = _run({"estimation_model": FERMI}, detach=["cognition.cortex.estimation.fermi"], patch=ablate)
        assert not any(a.get("prepared_command") for a in out["asks"])
        assert out["status"]["m:resolution-engine"] != "ACHIEVED"
        assert hasattr(missions.MissionEngine, "_resolution_ask")

    def test_a_prepared_successor_never_widens_the_original(self):
        out = _run({"declared": {**DECL, "epistemic_class": "estimate"}}, sign=False)
        ask = next(a for a in out["asks"] if a.get("prepared_command"))
        assert ask["kind"] == "NO_STRATEGY"
        prepared = ask["prepared_command"]
        assert prepared["kind"] == "MISSION" and prepared["body"]["mission_id"] == "m:resolution-engine-r1"
        body = prepared["body"]
        for field in ("light_cone", "closure", "priority", "founder_expression", "intended_effect"):
            assert body[field] == out["spec"][field]
        assert [s["capability"] for s in body["strategies"]] == [s["capability"] for s in out["spec"]["strategies"]]
        # the founder supplies the one value only they hold; GREG fills nothing in
        supply = prepared["founder_supplies"]
        assert [s["from"] for s in supply] == ["estimation_model", "estimation_model"]
        for s in supply:
            node = body
            for k in s["path"][:-1]:
                node = node[k]
            assert s["path"][-1] not in node

    def test_human_handoff_waits_and_never_achieves(self):
        protection = {"relevant": True, "required_actions": ["immediate_protection", "escalation"],
                      "evidence_access": "need_to_know", "disclosure_controls": ["no disclosure without consent"]}
        out = _run({"estimation_model": FERMI, "victim_protection": protection})
        assert [a["kind"] for a in out["asks"]] == ["HUMAN_JUDGMENT"]
        assert out["status"]["m:resolution-engine"] != "ACHIEVED"
