"""Closure integrity: regressions for the installed-body review of 2026-10-14.

Each test here was first a reviewer reproduction that passed while the defect was present
(scratch ``proof_integrity/test_pi_*.py``); it now pins the repaired behaviour. Bodies, keys and
signatures are real; the keys are test keys, never Alfonso's.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from greg import lightcone, metrics, sop
from greg.body import Body
from tests.greg_fixtures import (Clock, drop, horizon, make_body, mission, note_check, signed, workspace,
                                 write_strategy)


def tick(body, clock, n=3):
    for _ in range(n):
        body.tick()
        clock.advance(1)


def two_notes(home, mid: str, text: str = "x") -> dict:
    ws = workspace(home, mid)
    return mission(mid, checks=[note_check("n", ws / "n.txt", text), note_check("m", ws / "m.txt", text)],
                   strategies=[write_strategy("w", "n.txt", text, ["n"]), write_strategy("w2", "m.txt", text, ["m"])],
                   capabilities=["fs.read"], ceiling="read_only")


def asks(body, mid):
    return [e.payload for e in body.journal.replay("decision.requested") if e.payload["mission_id"] == mid]


def open_asks(body, mid):
    done = {e.payload["request_id"] for e in body.journal.replay("decision.")
            if e.type in ("greg.decision.answered", "greg.decision.withdrawn")}
    return [a for a in asks(body, mid) if a["request_id"] not in done]


def done_actions(body, mid):
    return [e.payload["action_id"] for e in body.journal.replay("mission.action")
            if e.payload["mission_id"] == mid and e.payload["status"] == "DONE"]


def appraisal(body, mid):
    [found] = [e.payload for e in body.journal.replay("mission.appraised") if e.payload["mission_id"] == mid]
    return found


# -- finding 1: the appraiser re-derives approval boundaries from the signed cone -------------------

def test_appraiser_refutes_an_out_of_cone_write_the_engine_never_asked_for(tmp_path, monkeypatch):
    real = lightcone.LightCone.admits

    def engine_defect(self, *, capability, target, **kw):     # the body (only) forgets the cone for one target
        return [] if target == "workspace:m.txt" else real(self, capability=capability, target=target, **kw)

    monkeypatch.setattr(lightcone.LightCone, "admits", engine_defect)
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    mid = "m:two-notes"
    with Body(home, clock=clock) as body:
        body.boot()
        drop(home, signed(key, body_id, "MISSION", two_notes(home, mid), now=clock.now))
        for _ in range(12):
            tick(body, clock, 1)
            for ask in open_asks(body, mid):
                drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"},
                                  now=clock.now))
        assert [a["action_id"] for a in asks(body, mid)] == ["w"] and sorted(done_actions(body, mid)) == ["w", "w2"]
        result = appraisal(body, mid)
        row = metrics.vepmc(body.journal)["missions"][0]
    # The appraiser runs unpatched in its own process and re-admits w2 against the signed cone.
    assert result["verdict"] == "REFUTED"
    assert result["checks"]["approval_boundaries_honored"] is False
    assert any(f.startswith("w2: executed without a prior founder approval") for f in result["findings"])
    assert row["approval_boundary"] is False and row["appraised_verified"] is False


def test_appraiser_refutes_an_approval_no_founder_command_carries(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    mid = "m:one-note"
    ws = workspace(home, mid)
    spec = mission(mid, checks=[note_check("n", ws / "n.txt", "x")], strategies=[write_strategy("w", "n.txt", "x", ["n"])],
                   capabilities=["fs.read"], ceiling="read_only")
    with Body(home, clock=clock) as body:
        body.boot()
        drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))
        for _ in range(8):
            tick(body, clock, 1)
            for ask in open_asks(body, mid):                  # an ask-path defect: no founder command at all
                body.journal.record("decision.answered", {"request_id": ask["request_id"], "mission_id": mid,
                                                          "answer": "approve", "reason": "",
                                                          "command_digest": "sha256:" + "0" * 64},
                                    key=ask["request_id"])
                body.engine.book.rebuild()
        assert [e.payload["kind"] for e in body.journal.replay("command.accepted")] == ["MISSION"]
        result = appraisal(body, mid)
    assert done_actions(body, mid) == ["w"]
    assert result["verdict"] == "REFUTED" and result["checks"]["approval_boundaries_honored"] is False


def test_appraiser_verifies_an_approval_the_founder_signed(tmp_path):
    """Positive control for the two refutations above: the honest path still verifies."""
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    mid = "m:two-notes"
    with Body(home, clock=clock) as body:
        body.boot()
        drop(home, signed(key, body_id, "MISSION", two_notes(home, mid), now=clock.now))
        for _ in range(12):
            tick(body, clock, 1)
            for ask in open_asks(body, mid):
                drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"},
                                  now=clock.now))
        result = appraisal(body, mid)
    assert sorted(a["action_id"] for a in asks(body, mid)) == ["w", "w2"]
    assert result["verdict"] == "VERIFIED", result["findings"]
    assert result["checks"]["approval_boundaries_honored"] and result["checks"]["approval_boundary_encountered"]


# -- finding 2: an SOP run pre-approves exactly the named steps -----------------------------------

def test_sop_pre_approval_admits_only_the_named_step(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    try:
        for n in range(3):                                  # three taught runs: both writes ask, both approved
            mid = f"m:two-notes-{n}"
            drop(home, signed(key, body_id, "MISSION", two_notes(home, mid, f"done {n}"), now=clock.now))
            for _ in range(6):
                tick(body, clock)
                for ask in open_asks(body, mid):
                    drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"],
                                                                 "answer": "approve"}, now=clock.now))
            assert sorted(a["action_id"] for a in asks(body, mid)) == ["w", "w2"]
        [proposal] = [e.payload for e in body.journal.replay("sop.proposed")]
        assert sorted(s["action_id"] for s in proposal["pre_approvable"]) == ["w", "w2"]
        drop(home, signed(key, body_id, "SOP_RATIFY", {"procedure_id": proposal["procedure_id"],
                                                       "pre_approve": ["w"]}, now=clock.now))
        tick(body, clock, 1)
        record = sop.ratified(body.journal)[proposal["procedure_id"]]["record"]
        spec = sop.instantiate(record, {"text": "from the sop"}, now=clock.now)
        # The cone is exactly the taught one; the pre-approval names one step, with its own target.
        assert spec["light_cone"]["capabilities"] == ["fs.read"]
        assert spec["light_cone"]["max_consequence_class"] == "read_only"
        assert spec["pre_approved_steps"] == [{"action_id": "w", "capability": "fs.write", "target": "workspace:n.txt",
                                               "consequence_class": "internal_write", "cost_usd": 0}]
        assert sop.instantiates(record, spec) == {"text": "from the sop"}
        mid = spec["mission_id"]
        drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))
        for _ in range(6):
            tick(body, clock)
            for ask in open_asks(body, mid):
                drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"},
                                  now=clock.now))
        assert [a["action_id"] for a in asks(body, mid)] == ["w2"]     # the step he did not pre-approve asked
        assert sorted(done_actions(body, mid)) == ["w", "w2"]
        result = appraisal(body, mid)
        assert result["verdict"] == "VERIFIED", result["findings"]
    finally:
        body.close()


def test_a_signed_pre_approval_must_name_its_exact_strategy(tmp_path):
    from greg.missions import MissionError, validate_mission
    import pytest
    home, *_ = make_body(tmp_path)
    spec = two_notes(home, "m:two-notes")
    spec["pre_approved_steps"] = [{"action_id": "w", "capability": "fs.write", "target": "workspace:m.txt",
                                   "consequence_class": "internal_write", "cost_usd": 0}]
    with pytest.raises(MissionError, match="exact capability and target"):
        validate_mission(spec)
    spec["pre_approved_steps"][0]["consequence_class"] = "external_contact"
    with pytest.raises(MissionError, match="mission contract"):
        validate_mission(spec)
