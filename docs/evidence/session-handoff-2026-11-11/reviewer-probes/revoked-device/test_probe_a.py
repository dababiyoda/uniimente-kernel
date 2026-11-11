"""Reviewer probes, set A: authority of a revoked device that still starts an effect after the revocation."""
import json

import pytest

from greg import revocation
from greg.body import status
from tests.greg_fixtures import drop, mission, note_check, workspace, write_strategy
from tests.unit.test_greg_revoked_device_authority import World, actions, open_asks, trail  # noqa


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def events(body, kind):
    return [e for e in body.journal.replay(kind)]


def ledger_seq(body):
    return {r.payload.get("event_id"): r.seq for r in body.ledger.by_type("event")}


def grants(body):
    return [r for r in body.ledger.by_type("event") if r.payload.get("type") == "greg.authority.grant_issued"]


RESTORE = {"capability": "fs.write", "params": {"relative_path": "note.txt", "content": "original"},
           "target": "workspace:note.txt"}


def running_with_compensation(world, body, mid="m:comp"):
    note = workspace(world.home, mid) / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("original")
    body.apply(world.sign("MISSION", mission(
        mid, checks=[note_check("c", note, "draft")],
        strategies=[write_strategy("w", "note.txt", "draft", ["c"], compensate=RESTORE)],
        capabilities=["fs.read", "fs.write"],
        closure={"kind": "infinite", "ladder": [["c"]], "cadence_seconds": 3600})))
    world.tick(body, 3)
    assert note.read_text() == "draft"
    return note


def test_A1_abandon_signed_by_a_device_then_revoked_before_the_turn_still_dispatches_the_compensation(world):
    """The device ends the mission (LIFECYCLE ABANDONED); the founder revokes the device; both reach the body before
    its next turn. Does the compensation (a new Gate dispatch, a write) start after device.revoked is on the ledger?"""
    with world.body() as body:
        phone = world.enroll(body, "phone", ("LIFECYCLE",))
        note = running_with_compensation(world, body)
        before = len(grants(body))
        drop(world.home, world.sign("LIFECYCLE", {"mission_id": "m:comp", "state": "ABANDONED", "reason": "phone"},
                                    key=phone), "a-abandon.json")
        drop(world.home, world.revoke("phone", suspected_compromise=True), "b-revoke.json")
        turn = world.tick(body)
        print("TURN commands", [(c.get("kind"), c["status"]) for c in turn["commands"]])
        world.tick(body, 3)
        seq = ledger_seq(body)
        [revoked] = events(body, "device.revoked")
        new = grants(body)[before:]
        compensated = [e.payload for e in events(body, "mission.compensated")]
        print("NOTE AFTER:", note.read_text())
        print("compensated:", [(c["action_id"], c["status"], c.get("receipt", "")[:20]) for c in compensated])
        print("revoked seq", seq[revoked.event_id], "new grants seq", [g.seq for g in new])
        print("status row", json.dumps(status(world.home)["security"]["device_revocations"], indent=1)[:1500])
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        print("review effects", [(x["effect"], x.get("state")) for x in review["effects"]])
        # the claim under test: an effect was dispatched after the revocation, resting on the revoked device's command
        assert note.read_text() == "original", "the compensation did not run"
        assert new and all(g.seq > seq[revoked.event_id] for g in new)
        # and the review, read as the revocation left the ledger, cannot list an effect that had not happened yet
        assert not any("compensation" in x["effect"] for x in review["effects"])


def test_A2_late_suspicion_review_attributes_a_founder_approved_dispatch_to_the_device(world):
    """Phone approves a standing out-of-cone write; it runs; plain revocation; the FOUNDER approves the re-ask and the
    write runs again; then the founder marks the old revocation as a suspected compromise. Does the review list the
    founder-approved dispatch as resting on the device?"""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note = workspace(world.home, "m:stand") / "n.txt"
        body.apply(world.sign("MISSION", mission(
            "m:stand", checks=[note_check("n", note, "approved")],
            strategies=[write_strategy("w", "n.txt", "approved", ["n"])],
            capabilities=["fs.read"], ceiling="read_only",
            closure={"kind": "infinite", "ladder": [["n"]], "cadence_seconds": 60})))
        world.tick(body, 2)
        [ask] = open_asks(body, "m:stand")
        body.apply(world.approve(ask["request_id"], key=phone))
        world.tick(body, 3)
        assert note.read_text() == "approved"
        first = grants(body)
        body.apply(world.revoke("phone"))                       # plain revocation: voids the standing remainder
        note.unlink()                                           # drift: the standing mission must write again
        for _ in range(3):
            world.clock.advance(61)
            world.tick(body, 2)
        [again] = open_asks(body, "m:stand")
        assert again["request_id"] != ask["request_id"]
        body.apply(world.approve(again["request_id"]))          # the FOUNDER approves
        for _ in range(3):
            world.clock.advance(61)
            world.tick(body, 2)
        assert note.read_text() == "approved"
        second = [g for g in grants(body) if g not in first and g.payload.get("founder_approved_scope")]
        assert len(second) == 1
        result = body.apply(world.revoke("phone", suspected_compromise=True))["result"]
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        print("review effects:", json.dumps([{k: x.get(k) for k in ("effect", "grant_id", "action_id", "receipt")}
                                             for x in review["effects"]], indent=1))
        wrongly = [x for x in review["effects"] if x.get("grant_id") == second[0].payload["grant_id"]]
        print("founder-approved grant listed as the device's:", wrongly)
        assert wrongly, "clean: the founder-approved dispatch is not attributed to the device"


def test_A3_a_revocation_that_arrives_during_a_turn_does_not_stop_a_dispatch_that_has_not_started(world, monkeypatch):
    """Two missions, each waiting on the phone's approval of a write. The founder's revocation file reaches the inbox
    while the first mission's write is running. Does the second mission's write, not yet started, still run in the
    same turn? (BODY_STOP is read before every mission step; DEVICE_REVOKE is not.)"""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        notes, asks_ = {}, {}
        for mid in ("m:aaa", "m:bbb"):
            notes[mid] = world.gated(body, mid)
        world.tick(body, 2)
        for mid in ("m:aaa", "m:bbb"):
            [asks_[mid]] = open_asks(body, mid)
            body.apply(world.approve(asks_[mid]["request_id"], key=phone))
        revoke = world.revoke("phone")
        real = body.registry.adapters["fs.write"] if hasattr(body.registry, "adapters") else None
        print("adapters attr:", [a for a in dir(body.registry) if "adapt" in a.lower()])
        dropped = []

        import greg.authority as authority
        original_act = authority.AuthorityOffice.act

        def act(self, **kw):
            out = original_act(self, **kw)
            if kw["manifest"].capability_id == "fs.write" and not dropped:
                drop(world.home, revoke, "z-revoke.json")      # the founder's revocation arrives now
                dropped.append(kw["mission_id"])
            return out
        monkeypatch.setattr(authority.AuthorityOffice, "act", act)
        turn = world.tick(body)
        print("turn missions:", [(m["mission_id"], m.get("state")) for m in turn["missions"]])
        print("dropped during:", dropped, "inbox still holds:", [p.name for p in (world.home / "inbox").glob("*.json")])
        ran = {mid: notes[mid].exists() for mid in notes}
        print("writes that ran in the turn the revocation arrived in:", ran)
        other = "m:bbb" if dropped == ["m:aaa"] else "m:aaa"
        assert ran[other], "clean: the second dispatch did not start after the revocation file arrived"
