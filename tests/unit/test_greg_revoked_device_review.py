"""Founder policy 2026-11-11, the rules an independent review of the first draft found unpinned or wrong.

"Revoking a device should immediately invalidate its unused authority to authorize future execution. Actions already
legitimately completed must remain in the evidence ledger." (docs/intent/sources/
REVOKED-DEVICE-AUTHORITY-2026-11-11-source.md)

Four groups, each on a real ``greg.body.Body`` with per-test keys:

1. compensations: what the Gate dispatched before the revocation is recorded from the Gate's own record (done,
   refused or unknown), and what it had not dispatched does not run on the revoked device's approval;
2. the review lists as resting on the key only what its own approvals authorized;
3. a mission the revoked device's own command ended stays ended, and its compensations not yet dispatched wait for
   a decision of their own;
4. safeguards whose removal no test noticed.

The helpers are those of tests/unit/test_greg_revoked_device_authority.py.
"""
import json

import pytest

from greg import revocation
from greg.body import status
from provenance.ledger import sha256_json
from tests.greg_fixtures import drop, mission, note_check, workspace, write_strategy
from tests.unit.test_greg_revoked_device_authority import (World, actions, asked, explode_once, open_asks, trail,
                                                           uncertain)

RESTORE = {"capability": "fs.write", "params": {"relative_path": "note.txt", "content": "original"},
           "target": "workspace:note.txt"}


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def compensable(world, body, mid="m:comp"):
    """A mission whose executed write has a signed compensation: write the original text back."""
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


def superseded_and_asked(world, body, mid="m:comp"):
    """The founder superseded the mission: undoing its write is asked first (a successor may rely on it)."""
    note = compensable(world, body, mid)
    body.apply(world.sign("LIFECYCLE", {"mission_id": mid, "state": "SUPERSEDED", "reason": "replaced"}))
    world.tick(body, 2)
    [ask] = open_asks(body, mid)
    assert ask["compensation"] is True
    return note, ask


def compensated(body, mid="m:comp"):
    return [e.payload for e in body.journal.replay("mission.compensated") if e.payload["mission_id"] == mid]


def grants(body):
    return [r for r in body.ledger.by_type("event") if r.payload.get("type") == "greg.authority.grant_issued"]


def gate_record(body, scope, mid="m:comp"):
    """(dispatch claims, receipts) the Gate holds for the one proposal of this mission's compensation."""
    [ran] = [a for a in actions(body, mid) if a["status"] == "DONE"]
    proposal = body.engine.office.proposal_id(scope, f"compensate:w:{ran['receipt']}")
    claims = body.ledger.select("grant_dispatch", proposal_id=proposal)
    receipts = [r for c in claims for r in body.ledger.select("receipt", grant_id=c.payload["grant_id"])]
    return claims, receipts


def killed_before_the_mission_records(body, mid="m:comp"):
    """The body stops after the Gate's receipt of the compensation and before the mission's own record of it."""
    real = body.journal.record

    def record(kind, data, **kw):
        if kind == "mission.compensated":
            raise SystemExit("killed after the Gate's receipt, before the mission's record")
        return real(kind, data, **kw)
    body.journal.record = record
    with pytest.raises(SystemExit):
        body.tick()
    assert compensated(body, mid) == []


def review_of(body):
    return [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)][-1]


# -- 1. compensations: the Gate's record decides first (review finding 1) -------------------------------------------

@pytest.mark.parametrize("revoked", [False, True])
def test_a_compensation_the_gate_completed_before_the_revocation_is_recorded_done_and_never_asked_again(world, revoked):
    """The phone approves the compensation; the Gate dispatches it and writes its receipt; the body dies before
    ``mission.compensated``; the founder revokes the phone while the body is down. The restarted body records the
    compensation DONE from the Gate's receipt. On f35b7986 it asked the founder to approve it again, said "nothing
    is run for it" about a write that had run, and recorded DECLINED with no receipt when he rejected."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = superseded_and_asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
        killed_before_the_mission_records(body)
        assert note.read_text() == "original"                       # the compensation DID run
        [claim], [receipt] = gate_record(body, ask["scope_digest"])
        assert receipt.payload["result"]["result_class"] == "positive"
    if revoked:
        drop(world.home, world.revoke("phone"), "a-revoke.json")    # while the body is down
    with world.body() as body:
        world.tick(body, 3)
        [row] = compensated(body)
        assert row["status"] == "DONE" and row["receipt"] == receipt.hash and row["scope_digest"] == ask["scope_digest"]
        assert gate_record(body, ask["scope_digest"]) == ([claim], [receipt])   # never dispatched a second time
        assert open_asks(body, "m:comp") == [] and open_asks(body, "m:comp", kind="COMPENSATION") == []
        assert note.read_text() == "original" and body.ledger.verify_chain()[0]
        if revoked:      # what the approval had not been used for is void all the same; nothing asks for it again
            [void] = trail(body, ask["request_id"])
            assert void["voids_approval"] is True
            world.tick(body, 3)
            assert open_asks(body, "m:comp") == [] and [r["status"] for r in compensated(body)] == ["DONE"]


def test_a_compensation_the_gate_refused_before_the_revocation_keeps_its_refusal(world):
    """The capability refused the compensation the phone approved (a negative receipt), the body died before its
    record, and the phone was revoked while it was down. The record after the restart is the refusal, with its
    receipt and its reason; the founder is asked about the effect, which still stands. It is not offered for
    approval as if it had never been tried, and nothing is dispatched for it again."""
    from greg.capabilities import CapabilityError
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = superseded_and_asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))

        def refuses(params, ctx):
            raise CapabilityError("the disk is read-only")
        body.registry.adapters["fs.write"] = refuses
        killed_before_the_mission_records(body)
        [claim], [receipt] = gate_record(body, ask["scope_digest"])
        assert receipt.payload["result"]["result_class"] == "negative" and note.read_text() == "draft"
    drop(world.home, world.revoke("phone"), "a-revoke.json")
    with world.body() as body:
        world.tick(body, 3)
        [row] = compensated(body)
        assert row["status"] == "REFUSED" and row["receipt"] == receipt.hash
        assert "the disk is read-only" in row["reasons"][0]
        assert open_asks(body, "m:comp") == []                      # no APPROVAL ask for what was already tried
        [question] = open_asks(body, "m:comp", kind="COMPENSATION")
        assert "the disk is read-only" in json.dumps(question["evidence"]["compensation_failed"])
        assert gate_record(body, ask["scope_digest"]) == ([claim], [receipt]) and note.read_text() == "draft"


def test_a_compensation_interrupted_inside_its_dispatch_is_recorded_as_unknown_after_the_revocation(world):
    """The body dies inside the compensation's dispatch (the Gate's claim, no receipt), and the phone that approved
    it is revoked before the restart. The outcome is unknown: recorded UNCERTAIN and put to the founder as a
    COMPENSATION decision, as without a revocation. It is never offered for approval as if nothing had run."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = superseded_and_asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
        real = body.registry.adapters["fs.write"]

        def dies(params, ctx):
            real(params, ctx)
            raise SystemExit("power lost after the write, before the Gate's receipt")
        body.registry.adapters["fs.write"] = dies
        with pytest.raises(SystemExit):
            body.tick()
        assert note.read_text() == "original" and compensated(body) == []
        [claim], receipts = gate_record(body, ask["scope_digest"])
        assert receipts == []
    drop(world.home, world.revoke("phone"), "a-revoke.json")
    with world.body() as body:
        world.tick(body, 3)
        [row] = compensated(body)
        assert row["status"] == "UNCERTAIN" and row["receipt"] is None and "outcome is unknown" in row["reasons"][0]
        assert open_asks(body, "m:comp") == []
        [question] = open_asks(body, "m:comp", kind="COMPENSATION")
        assert gate_record(body, ask["scope_digest"]) == ([claim], [])   # never dispatched again
        body.apply(world.approve(question["request_id"], answer="reject"))
        world.tick(body, 3)
        assert [r["status"] for r in compensated(body)] == ["UNCERTAIN"]   # the answer is a record; no DECLINED


def test_a_compensation_approved_by_a_device_revoked_before_its_dispatch_does_not_run(world):
    """The same rule as for an action: the phone's approval of a compensation the Gate has not dispatched is void
    from the revocation on. The effect stands until the founder (or a device still delegated) answers the new ask."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = superseded_and_asked(world, body)
        drop(world.home, world.approve(ask["request_id"], key=phone), "a-decision.json")
        drop(world.home, world.revoke("phone"), "b-revoke.json")
        world.tick(body, 4)
        assert note.read_text() == "draft" and compensated(body) == []
        assert gate_record(body, ask["scope_digest"]) == ([], [])
        [again] = open_asks(body, "m:comp")
        assert again["request_id"] != ask["request_id"] and again["compensation"] is True
        [void] = trail(body, ask["request_id"])
        assert void["voids_approval"] is True
        body.apply(world.approve(again["request_id"]))              # the founder approves: it runs, once
        world.tick(body, 3)
        assert note.read_text() == "original" and [c["status"] for c in compensated(body)] == ["DONE"]
        assert [len(x) for x in gate_record(body, ask["scope_digest"])] == [1, 1]


# -- 3. a mission the revoked device's own command ended (review finding 3) ---------------------------------------

def abandoned_by(world, body, key, mid="m:comp", *, state="ABANDONED"):
    return world.sign("LIFECYCLE", {"mission_id": mid, "state": state, "reason": "device"}, key=key)


@pytest.mark.parametrize("answer", ["approve", "reject"])
def test_a_mission_a_revoked_device_abandoned_runs_no_compensation_until_it_is_decided(world, answer):
    """The phone abandons a mission whose executed write has a signed compensation; the founder's DEVICE_REVOKE
    reaches the body in the same inbox read. On f35b7986 the compensation was dispatched on the following turn, on
    nothing but the revoked key's command. Now the mission stays abandoned, nothing is dispatched, and the founder
    is asked about this one compensation: approve runs it once, reject records that the effect stands."""
    with world.body() as body:
        phone = world.enroll(body, "phone", ("LIFECYCLE",))
        note = compensable(world, body)
        [ran] = actions(body, "m:comp")
        before = len(grants(body))
        abandon = abandoned_by(world, body, phone)
        drop(world.home, abandon, "a-abandon.json")
        drop(world.home, world.revoke("phone"), "b-revoke.json")
        turn = world.tick(body)
        assert [c["status"] for c in turn["commands"]] == ["APPLIED", "APPLIED"]
        world.tick(body, 3)
        m = body.engine.book.missions["m:comp"]
        [revoked] = body.journal.replay("device.revoked")
        assert m.status == "ABANDONED"                              # the abandon itself stands
        assert m.compensation_hold == {
            "device_key_id": world.kid("phone"), "signer": "device:phone", "revocation_event": revoked.event_id,
            "revocation_command": revoked.payload["command_digest"], "lifecycle_command": sha256_json(abandon),
            "at": revoked.payload["at"]}
        assert note.read_text() == "draft" and compensated(body) == [] and len(grants(body)) == before
        [ask] = open_asks(body, "m:comp")
        assert ask["compensation"] is True and ask["action_id"] == "w"
        assert world.kid("phone") in ask["why_now"] and "revoked" in ask["why_now"]
        assert ask["evidence"]["ended_by"] == m.compensation_hold
        assert ask["evidence"]["original_receipt"] == ran["receipt"]
        assert ask["consequence_of_no_response"] == "the executed effect stands; nothing is run for it"
        body.apply(world.approve(ask["request_id"], answer=answer))
        world.tick(body, 3)
        [row] = compensated(body)
        if answer == "approve":
            assert row["status"] == "DONE" and note.read_text() == "original" and len(grants(body)) == before + 1
            assert body.ledger.find(row["receipt"]).payload["grant_id"] == grants(body)[-1].payload["grant_id"]
        else:
            assert row["status"] == "DECLINED" and row["receipt"] is None
            assert note.read_text() == "draft" and len(grants(body)) == before
        world.tick(body, 3)
        assert compensated(body) == [row] and open_asks(body, "m:comp") == []


@pytest.mark.parametrize("restart", [False, True])
def test_the_hold_is_the_folds_and_survives_a_restart_and_a_new_delegation_of_the_key(world, restart):
    """The hold is derived from the revocation record alone: a new body folds it again, and delegating the key
    again lifts nothing (the key may be in other hands; only a decision for the compensation runs it)."""
    with world.body() as body:
        phone = world.enroll(body, "phone", ("LIFECYCLE",))
        note = compensable(world, body)
        body.apply(world.sign("BODY_PAUSE", {}))
        body.apply(abandoned_by(world, body, phone))
        body.apply(world.revoke("phone"))
        world.clock.advance(60)
        world.enroll(body, "phone", ("LIFECYCLE",))                 # the same key, delegated again
        body.apply(world.sign("BODY_RESUME", {}))
        if not restart:
            world.tick(body, 4)
            assert note.read_text() == "draft" and compensated(body) == [] and len(open_asks(body, "m:comp")) == 1
            return
    with world.body() as body:
        assert body.engine.book.missions["m:comp"].compensation_hold["device_key_id"] == world.kid("phone")
        world.tick(body, 4)
        assert note.read_text() == "draft" and compensated(body) == [] and len(open_asks(body, "m:comp")) == 1


def test_a_compensation_dispatched_before_the_revocation_of_the_device_that_ended_the_mission_stays(world):
    """What ran before the revocation is completed history. Run and recorded: nothing changes. Run and not yet
    recorded (the body died after the Gate's receipt): the restarted body records it from that receipt, although
    the mission is held by then, and asks nothing."""
    with world.body() as body:
        phone = world.enroll(body, "phone", ("LIFECYCLE",))
        note = compensable(world, body, "m:recorded")
        body.apply(abandoned_by(world, body, phone, "m:recorded"))
        world.tick(body, 3)
        [done] = compensated(body, "m:recorded")
        assert done["status"] == "DONE" and note.read_text() == "original"
        other = compensable(world, body)
        body.apply(abandoned_by(world, body, phone))
        killed_before_the_mission_records(body)
        assert other.read_text() == "original"
        issued, receipt = len(grants(body)), body.ledger.by_type("receipt")[-1]
    drop(world.home, world.revoke("phone"), "a-revoke.json")
    with world.body() as body:
        world.tick(body, 3)
        assert body.engine.book.missions["m:comp"].compensation_hold is not None
        [late] = compensated(body)
        assert late["status"] == "DONE" and late["receipt"] == receipt.hash
        assert compensated(body, "m:recorded") == [done] and len(grants(body)) == issued
        assert open_asks(body, "m:comp") == [] and open_asks(body, "m:recorded") == []


def test_only_a_mission_the_revoked_key_itself_ended_is_held(world):
    """Not held by the phone's revocation: a mission the founder ended, one another device ended, and one the phone
    only paused. A revocation record that names the founder's key holds nothing either."""
    with world.body() as body:
        phone = world.enroll(body, "phone", ("LIFECYCLE",))
        laptop = world.enroll(body, "laptop", ("LIFECYCLE",))
        notes = {mid: compensable(world, body, mid) for mid in ("m:founder", "m:laptop", "m:paused")}
        body.apply(world.sign("BODY_PAUSE", {}))
        body.apply(abandoned_by(world, body, None, "m:founder"))
        body.apply(abandoned_by(world, body, laptop, "m:laptop"))
        body.apply(abandoned_by(world, body, phone, "m:paused", state="PAUSED"))
        body.apply(world.revoke("phone"))
        [founder] = body.enrolled_keys()
        body.journal.record("device.revoked", {"device_key_id": founder, "at": "2026-11-11T00:00:00Z"},
                            key=[founder, "forged"])
        body.engine.book.rebuild()
        assert {mid: m.compensation_hold for mid, m in body.engine.book.missions.items()} == dict.fromkeys(notes)
        body.apply(world.sign("BODY_RESUME", {}))
        world.tick(body, 4)
        assert [c["status"] for mid in ("m:founder", "m:laptop") for c in compensated(body, mid)] == ["DONE", "DONE"]
        assert notes["m:founder"].read_text() == notes["m:laptop"].read_text() == "original"
        assert open_asks(body) == []


def test_the_founder_is_shown_what_a_revocation_holds_and_the_review_lists_it(world):
    """The status lists, under the revocation, the mission the key ended and each compensation that waits, with the
    ask that decides it. The review lists the abandon and the held compensation, and says of neither that it ran.
    Once the founder has decided, the status row is gone, and the review still reads as the revocation left it."""
    with world.body() as body:
        phone = world.enroll(body, "phone", ("LIFECYCLE",))
        note = compensable(world, body)
        [ran] = actions(body, "m:comp")
        body.apply(world.sign("BODY_PAUSE", {}))
        abandon = abandoned_by(world, body, phone)
        body.apply(abandon)
        body.apply(world.revoke("phone", suspected_compromise=True))
        [revoked] = body.journal.replay("device.revoked")
        review = review_of(body)
        assert [c["command_digest"] for c in review["commands"]] == [sha256_json(abandon)]
        assert [(x["effect"], x.get("mission_id"), x.get("action_id")) for x in review["effects"]] == [
            ("a mission lifecycle it set", "m:comp", None), (revocation.HELD, "m:comp", "w")]
        held = review["effects"][1]
        assert (held["capability"], held["target"], held["original_receipt"]) == (
            "fs.write", "workspace:note.txt", ran["receipt"])
        assert held["rested_on"]["command_digest"] == sha256_json(abandon)
    row = status(world.home)["security"]["device_revocations"][0]
    assert row["ended_missions_held"] == [{"mission_id": "m:comp", "state": "ABANDONED", "compensations_held": [
        {"action_id": "w", "capability": "fs.write", "target": "workspace:note.txt",
         "awaits": "asked at the body's next turn"}]}]
    with world.body() as body:
        body.apply(world.sign("BODY_RESUME", {}))
        world.tick(body, 2)
        [ask] = open_asks(body, "m:comp")
        assert note.read_text() == "draft"
    row = status(world.home)["security"]["device_revocations"][0]
    assert row["ended_missions_held"][0]["compensations_held"][0]["awaits"] == ask["request_id"]
    with world.body() as body:
        body.apply(world.approve(ask["request_id"]))
        world.tick(body, 3)
        assert note.read_text() == "original" and [c["status"] for c in compensated(body)] == ["DONE"]
        assert revocation.build_review(body.journal, revoked) == review
    assert "ended_missions_held" not in status(world.home)["security"]["device_revocations"][0]


def test_a_late_suspicion_lists_the_compensation_the_abandon_ran_and_not_the_one_the_founder_approved(world):
    """The phone abandons two missions. The first is compensated before the phone is revoked: that ran on the
    phone's command. The second is held by the revocation and runs on the founder's approval. A suspicion signed
    afterwards lists the first compensation under the phone's command and not the second."""
    with world.body() as body:
        phone = world.enroll(body, "phone", ("LIFECYCLE",))
        compensable(world, body, "m:early")
        early = abandoned_by(world, body, phone, "m:early")
        body.apply(early)
        world.tick(body, 3)
        [ran] = compensated(body, "m:early")
        assert ran["status"] == "DONE"
        compensable(world, body, "m:late")
        late = abandoned_by(world, body, phone, "m:late")
        drop(world.home, late, "a-abandon.json")
        drop(world.home, world.revoke("phone"), "b-revoke.json")
        world.tick(body, 3)
        [ask] = open_asks(body, "m:late")
        body.apply(world.approve(ask["request_id"]))                # the FOUNDER approves the held compensation
        world.tick(body, 3)
        [approved] = compensated(body, "m:late")
        assert approved["status"] == "DONE"
        body.apply(world.revoke("phone", suspected_compromise=True))
        review = review_of(body)
        assert [(x["effect"], x["mission_id"], x["rested_on"]["command_digest"]) for x in review["effects"]] == [
            ("a mission lifecycle it set", "m:early", sha256_json(early)),
            ("a compensation run after it ended the mission", "m:early", sha256_json(early)),
            ("a mission lifecycle it set", "m:late", sha256_json(late))]
        assert review["receipts"] == [ran["receipt"]] and approved["receipt"] not in json.dumps(review)
    rows = status(world.home)["security"]["device_revocations"]
    assert not [r for r in rows if "ended_missions_held" in r]      # nothing waits any more


def test_each_revocation_lists_the_missions_it_holds_itself(world):
    """Two devices each ended a mission and are revoked one after the other: the status lists each mission under
    the revocation that holds it."""
    with world.body() as body:
        phone = world.enroll(body, "phone", ("LIFECYCLE",))
        laptop = world.enroll(body, "laptop", ("LIFECYCLE",))
        compensable(world, body, "m:phone")
        compensable(world, body, "m:laptop")
        body.apply(world.sign("BODY_PAUSE", {}))
        body.apply(abandoned_by(world, body, phone, "m:phone"))
        body.apply(abandoned_by(world, body, laptop, "m:laptop"))
        body.apply(world.revoke("laptop"))
        body.apply(world.revoke("phone"))
    rows = status(world.home)["security"]["device_revocations"]
    assert [(r["device_key_id"], [m["mission_id"] for m in r["ended_missions_held"]]) for r in rows] == [
        (world.kid("laptop"), ["m:laptop"]), (world.kid("phone"), ["m:phone"])]


def test_the_review_lists_a_compensation_interrupted_after_the_device_ended_the_mission(world):
    """The compensation that followed the phone's abandon died inside its dispatch: no receipt, an unknown outcome.
    It may have changed the world, so the review lists it under the abandon like one that completed."""
    with world.body() as body:
        phone = world.enroll(body, "phone", ("LIFECYCLE",))
        compensable(world, body)
        explode_once(body)
        abandon = abandoned_by(world, body, phone)
        body.apply(abandon)
        world.tick(body, 2)
        [row] = compensated(body)
        assert row["status"] == "UNCERTAIN" and row["receipt"] is None
        body.apply(world.revoke("phone", suspected_compromise=True))
        assert [(x["effect"], x.get("status")) for x in review_of(body)["effects"]] == [
            ("a mission lifecycle it set", None), ("a compensation run after it ended the mission", "UNCERTAIN")]


# -- 2. the review attributes to the key only what its approvals authorized (review finding 2) ----------------------

def scope_grants(body, scope):
    return [r for r in grants(body) if r.payload.get("founder_approved_scope") and r.payload.get("scope_digest") == scope]


def standing(world, body, mid, *, wants="approved", writes="approved"):
    """A standing mission whose write lies outside its read-only cone; returns (note path, its open APPROVAL)."""
    note = workspace(world.home, mid) / "n.txt"
    body.apply(world.sign("MISSION", mission(
        mid, checks=[note_check("n", note, wants)], strategies=[write_strategy("w", "n.txt", writes, ["n"])],
        capabilities=["fs.read"], ceiling="read_only",
        closure={"kind": "infinite", "ladder": [["n"]], "cadence_seconds": 60})))
    world.tick(body, 2)
    [ask] = open_asks(body, mid)
    return note, ask


def cadence(world, body, times=3):
    for _ in range(times):
        world.clock.advance(61)
        world.tick(body, 2)


def test_a_late_suspicion_does_not_list_what_the_founder_approved_after_the_revocation(world):
    """The phone approves a standing write; it runs; the phone is revoked plainly; the FOUNDER approves the new ask
    and the write runs again; later the founder marks the revocation as a suspected compromise. The review lists the
    phone's run and nothing of the founder's. On f35b7986 it listed the founder's dispatch as "granted under its
    approval, not yet recorded by the mission"."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = standing(world, body, "m:stand")
        decision = world.approve(ask["request_id"], key=phone)
        body.apply(decision)
        world.tick(body, 3)
        [first] = scope_grants(body, ask["scope_digest"])
        [ran] = [a for a in actions(body, "m:stand") if a["status"] == "DONE"]
        body.apply(world.revoke("phone"))                           # voids the standing remainder
        note.unlink()                                               # drift: the standing mission must write again
        cadence(world, body)
        [again] = open_asks(body, "m:stand")
        assert again["request_id"] != ask["request_id"] and again["scope_digest"] == ask["scope_digest"]
        body.apply(world.approve(again["request_id"]))              # the FOUNDER approves
        cadence(world, body)
        assert note.read_text() == "approved"
        [_, second] = scope_grants(body, ask["scope_digest"])
        assert len([a for a in actions(body, "m:stand") if a["status"] == "DONE"]) == 2
        body.apply(world.revoke("phone", suspected_compromise=True))
        review = review_of(body)
        [effect] = review["effects"]
        assert effect["effect"] == "an action dispatched under its approval" and effect["receipt"] == ran["receipt"]
        assert effect["rested_on"]["command_digest"] == sha256_json(decision)
        assert second.payload["grant_id"] not in json.dumps(review) and review["receipts"] == [ran["receipt"]]
        assert body.ledger.find(ran["receipt"]).payload["grant_id"] == first.payload["grant_id"]


def test_a_review_does_not_list_what_ran_after_the_devices_approval_was_withdrawn(world):
    """The phone's standing approval is withdrawn by the standing-approval regression (a run under it proved
    ineffective); the FOUNDER approves the ask that follows and the write runs again; then the phone, delegated all
    along, is revoked as a suspected compromise. The founder's dispatch is not the phone's."""
    mid = "m:regress"
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = standing(world, body, mid, wants="final", writes="draft")   # the run executes and proves ineffective
        body.apply(world.approve(ask["request_id"], key=phone))
        cadence(world, body, 4)
        assert [e.payload["request_id"] for e in body.journal.replay("autonomy.regressed")] == [ask["request_id"]]
        phones = scope_grants(body, ask["scope_digest"])
        note.write_text("final")                                    # the world passes once (by hand), then drifts
        cadence(world, body, 1)
        note.unlink()
        cadence(world, body)
        [again] = [r for r in open_asks(body, mid) if r["request_id"] != ask["request_id"]]
        body.apply(world.approve(again["request_id"]))              # the FOUNDER approves
        cadence(world, body, 2)
        founders = [g for g in scope_grants(body, ask["scope_digest"]) if g not in phones]
        assert phones and founders
        body.apply(world.revoke("phone", suspected_compromise=True))
        review = review_of(body)
        assert {x["effect"] for x in review["effects"]} == {"an action dispatched under its approval"}
        listed = {body.ledger.find(x["receipt"]).payload["grant_id"] for x in review["effects"]}
        assert listed == {g.payload["grant_id"] for g in phones}
        assert not [g for g in founders if g.payload["grant_id"] in json.dumps(review)]
        [command] = review["commands"]
        assert command["standing"].startswith("WITHDRAWN_EARLIER")


def test_a_late_suspicion_lists_a_dispatch_granted_under_the_approval_and_recorded_after_the_revocation(world, monkeypatch):
    """The Gate granted and ran the phone-approved write, the body died before recording it, the phone was revoked
    plainly, and the restarted body recorded the action from the Gate's receipt. A suspicion signed later lists that
    action: it rested on the phone's approval although its record follows the revocation."""
    with world.body() as body:
        body.boot()
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        decision = world.approve(ask["request_id"], key=phone)
        body.apply(decision)
        monkeypatch.setattr(body.engine, "_record_outcome", lambda *a, **k: (_ for _ in ()).throw(SystemExit("killed")))
        with pytest.raises(SystemExit):
            world.tick(body)
        assert note.read_text() == "approved" and actions(body, "m:gated") == []
    with world.body() as body:
        body.boot()
        body.apply(world.revoke("phone"))
        world.tick(body, 4)
        [done] = actions(body, "m:gated")
        assert done["status"] == "DONE"
        body.apply(world.revoke("phone", suspected_compromise=True))
        [effect] = review_of(body)["effects"]
        assert effect["effect"] == "an action dispatched under its approval" and effect["receipt"] == done["receipt"]
        assert effect["rested_on"]["command_digest"] == sha256_json(decision)


def test_a_dispatch_the_mission_never_recorded_is_listed_once_as_the_gates_grant(world, monkeypatch):
    """The same interruption, with the suspicion signed at once: the mission has no record of the dispatch when the
    review reads the ledger, so the review lists the Gate's grant, once."""
    with world.body() as body:
        body.boot()
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
        monkeypatch.setattr(body.engine, "_record_outcome", lambda *a, **k: (_ for _ in ()).throw(SystemExit("killed")))
        with pytest.raises(SystemExit):
            world.tick(body)
        [grant] = scope_grants(body, ask["scope_digest"])
    with world.body() as body:
        body.boot()
        body.apply(world.revoke("phone", suspected_compromise=True))
        [effect] = review_of(body)["effects"]
        assert effect["effect"] == revocation.UNRECORDED and effect["grant_id"] == grant.payload["grant_id"]


def test_a_dispatch_reconciled_before_the_revocation_is_listed_once(world):
    """The phone-approved write's first dispatch is interrupted and the founder reconciles it as executed. The
    review lists the dispatch once, as the action under the phone's approval, not a second time for the record of
    the founder's reconciliation."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        explode_once(body, after_effect=True)
        body.apply(world.approve(ask["request_id"], key=phone))
        world.tick(body, 2)
        [question] = open_asks(body, "m:gated", kind="RECONCILIATION")
        body.apply(world.approve(question["request_id"], answer="reconcile_executed"))
        world.tick(body, 3)
        records = actions(body, "m:gated")
        assert [a["status"] for a in records][0] == "UNCERTAIN" and len(records) == 2
        assert records[1]["route"] == "founder_reconciliation"
        body.apply(world.revoke("phone", suspected_compromise=True))
        rows = [(x["effect"], x["status"]) for x in review_of(body)["effects"]]
        assert rows == [("an action dispatched under its approval", "UNCERTAIN")]


def test_a_record_that_names_no_grant_is_attributed_by_where_it_stands(world):
    """A dispatch found again under the earlier scope form is recorded UNCERTAIN with no grant id (greg/authority.py,
    "retained legacy dispatch"). Such a record rests on the phone's approval when it was written while the approval
    stood, and not when it was written after the revocation voided it. (The two rows are written here as that path
    writes them; the body is not turned afterwards.)"""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = standing(world, body, "m:stand")
        body.apply(world.approve(ask["request_id"], key=phone))
        world.tick(body, 3)
        [ran] = [a for a in actions(body, "m:stand") if a["status"] == "DONE"]
        legacy = {**ran, "status": "UNCERTAIN", "receipt": None, "cost_usd": 0.0,
                  "reasons": ["retained legacy dispatch; no receipt or blind retry"]}
        body.journal.record("mission.action", {**legacy, "attempt": 91}, key=["m:stand", "w", 91, "legacy"])
        body.apply(world.revoke("phone"))
        body.journal.record("mission.action", {**legacy, "attempt": 92}, key=["m:stand", "w", 92, "legacy"])
        body.apply(world.revoke("phone", suspected_compromise=True))
        assert [(x["effect"], x["status"], x["attempt"]) for x in review_of(body)["effects"]] == [
            ("an action dispatched under its approval", "DONE", ran["attempt"]),
            ("an action dispatched under its approval", "UNCERTAIN", 91)]


def test_the_review_lists_a_compensation_the_device_approved(world):
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = superseded_and_asked(world, body)
        decision = world.approve(ask["request_id"], key=phone)
        body.apply(decision)
        world.tick(body, 3)
        [row] = compensated(body)
        assert row["status"] == "DONE" and note.read_text() == "original"
        body.apply(world.revoke("phone", suspected_compromise=True))
        [effect] = review_of(body)["effects"]
        assert effect["effect"] == "a compensation dispatched under its approval"
        assert effect["receipt"] == row["receipt"] and effect["original_receipt"] == row["original_receipt"]
        assert effect["rested_on"] == {"command_digest": sha256_json(decision), "kind": "DECISION",
                                       "request_id": ask["request_id"]}
        assert compensated(body) == [row]                           # the review changed nothing


def test_a_late_suspicion_finds_a_compensation_granted_under_the_approval_and_recorded_after_the_revocation(world):
    """The Gate ran the phone-approved compensation, the body died before the mission's record, and the phone was
    revoked plainly while it was down. The record follows the revocation; the grant does not. A suspicion signed
    later lists the compensation under the phone's approval, once."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = superseded_and_asked(world, body)
        decision = world.approve(ask["request_id"], key=phone)
        body.apply(decision)
        killed_before_the_mission_records(body)
    drop(world.home, world.revoke("phone"), "a-revoke.json")
    with world.body() as body:
        world.tick(body, 3)
        [row] = compensated(body)
        body.apply(world.revoke("phone", suspected_compromise=True))
        [effect] = review_of(body)["effects"]
        assert effect["effect"] == "a compensation dispatched under its approval"
        assert effect["receipt"] == row["receipt"] and effect["rested_on"]["command_digest"] == sha256_json(decision)


def test_an_interrupted_compensation_the_device_approved_is_listed_once(world):
    """Its record names no grant (its dispatch was interrupted): the review finds the grant by the compensation's
    one proposal, so the dispatch is listed once, as the compensation, and not again as an unrecorded grant."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = superseded_and_asked(world, body)
        explode_once(body)                                          # the compensating write dies with no receipt
        body.apply(world.approve(ask["request_id"], key=phone))
        world.tick(body, 2)
        [row] = compensated(body)
        assert row["status"] == "UNCERTAIN" and row["receipt"] is None and "grant_id" not in row
        body.apply(world.revoke("phone", suspected_compromise=True))
        assert [(x["effect"], x["status"]) for x in review_of(body)["effects"]] == [
            ("a compensation dispatched under its approval", "UNCERTAIN")]


def test_a_paid_approval_stops_standing_at_the_run_that_used_it(world):
    """One paid approval funds one run. A later run of the same exact scope (a metered run that booked nothing
    leaves the scope unchanged, #157) needed a new approval, so it is not the phone's. The later grant and action
    are written here as the Gate and the engine write them; the body is not turned afterwards."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body, mid="m:paid", cost_usd=0.5)
        body.apply(world.approve(ask["request_id"], key=phone))
        world.tick(body, 3)
        [done] = actions(body, "m:paid")
        assert done["status"] == "DONE" and ask["request_id"] in body.engine.book.consumed
        body.journal.record("authority.grant_issued", {"grant_id": "grant-of-a-later-approval", "proposal_id": "p-2",
                                                       "scope_digest": ask["scope_digest"],
                                                       "founder_approved_scope": True}, key=["later-grant"])
        body.journal.record("mission.action", {**done, "attempt": done["attempt"] + 1, "receipt": None,
                                               "status": "UNCERTAIN", "grant_id": "grant-of-a-later-approval",
                                               "reasons": ["written by this test"]}, key=["m:paid", "w", "later"])
        body.apply(world.revoke("phone", suspected_compromise=True))
        review = review_of(body)
        assert [(x["effect"], x["receipt"]) for x in review["effects"]] == [
            ("an action dispatched under its approval", done["receipt"])]
        assert "grant-of-a-later-approval" not in json.dumps(review)
        [command] = review["commands"]
        assert command["standing"] == "USED: its one paid run happened"


# -- 4. safeguards the review found without a failing test ---------------------------------------------------------

def test_voiding_a_devices_reconciliation_answer_leaves_the_founders_approval_of_the_action(world):
    """The FOUNDER approved the write; its first dispatch's completion is unknown; the phone answers the
    reconciliation and is revoked before the engine records that answer. Only the phone's answer is void. A
    RECONCILIATION ask carries the action's scope digest, so a careless void would take the founder's approval."""
    mid = "m:gated"
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body, mid=mid)
        explode_once(body)
        body.apply(world.approve(ask["request_id"]))                # the founder's own approval
        world.tick(body, 2)
        [question] = open_asks(body, mid, kind="RECONCILIATION")
        assert question["scope_digest"] == ask["scope_digest"]
        drop(world.home, world.approve(question["request_id"], key=phone, answer="reconcile_not_executed"), "a.json")
        drop(world.home, world.revoke("phone"), "b.json")
        world.tick(body, 2)
        assert question["request_id"] in body.engine.book.voided
        assert body.engine.book.missions[mid].approved_scopes == {ask["scope_digest"]}
        [again] = open_asks(body, mid, kind="RECONCILIATION")
        body.apply(world.approve(again["request_id"], answer="reconcile_not_executed"))
        world.tick(body, 4)
        assert note.exists() and open_asks(body, mid) == []         # the retry ran on the founder's approval


def appraised(body):
    return body.journal.replay("mission.appraised")[-1].payload


def test_the_appraiser_refutes_nothing_for_another_devices_revocation(world):
    """The laptop approves; the PHONE is revoked before the dispatch. The laptop's approval was in force."""
    with world.body() as body:
        body.boot()
        world.enroll(body, "phone")
        laptop = world.enroll(body, "laptop")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=laptop))
        body.apply(world.revoke("phone"))
        world.tick(body, 4)
        assert note.read_text() == "approved"
        verdict = appraised(body)
        assert verdict["verdict"] == "VERIFIED" and verdict["checks"]["approval_boundaries_honored"] is True, verdict


def test_the_appraiser_accepts_a_fresh_approval_of_a_key_delegated_again(world):
    """The phone was revoked before it approved anything and delegated again; its approval under the new delegation
    is in force. Only a revocation between an answer and the dispatch voids that answer."""
    with world.body() as body:
        body.boot()
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.revoke("phone"))
        world.clock.advance(60)
        world.enroll(body, "phone")
        world.clock.advance(5)
        body.apply(world.approve(ask["request_id"], key=phone))
        world.tick(body, 4)
        assert note.read_text() == "approved"
        verdict = appraised(body)
        assert verdict["verdict"] == "VERIFIED" and verdict["checks"]["approval_boundaries_honored"] is True, verdict


def test_the_review_lists_an_exclusion_an_abandons_compensation_and_a_settled_reconciliation(world):
    with world.body() as body:
        phone = world.enroll(body, "phone", ("DECISION", "CRITIQUE", "LIFECYCLE"))
        note = compensable(world, body)                             # abandoned by the phone; the compensation runs
        abandon = abandoned_by(world, body, phone)
        body.apply(abandon)
        world.tick(body, 3)
        [undone] = compensated(body)
        assert note.read_text() == "original" and undone["status"] == "DONE"
        _, question, _ = uncertain(world, body)                     # an interrupted dispatch the phone reconciles
        reconcile = world.approve(question["request_id"], key=phone, answer="reconcile_executed")
        body.apply(reconcile)
        world.tick(body, 2)
        target = [e for e in body.journal.replay("mission.action") if e.payload["mission_id"] == "m:uncertain"][0]
        critique = world.sign("CRITIQUE", {"target_event_id": target.event_id, "verdict": "reject",
                                           "evidence_type": "founder_judgment", "text": "not this way",
                                           "exclude_strategy": True}, key=phone)
        body.apply(critique)
        body.apply(world.revoke("phone", suspected_compromise=True))
        review = review_of(body)
        assert [c["command_digest"] for c in review["commands"]] == [sha256_json(c) for c in (abandon, reconcile, critique)]
        rows = [(x["effect"], x.get("mission_id"), x.get("action_id"), x["rested_on"]["command_digest"])
                for x in review["effects"]]
        assert rows == [
            ("a mission lifecycle it set", "m:comp", None, sha256_json(abandon)),
            ("a compensation run after it ended the mission", "m:comp", "w", sha256_json(abandon)),
            ("an interrupted dispatch settled by its answer", "m:uncertain", "w", sha256_json(reconcile)),
            ("a strategy excluded by its critique", "m:uncertain", "w", sha256_json(critique))]
        assert review["effects"][1]["receipt"] == undone["receipt"]


def test_the_review_lists_a_compensation_obligation_the_devices_answer_closed(world):
    """The compensating capability is detached, so the effect is put to the founder; the phone answers "the effect
    stands"; the obligation is closed by that answer. The review lists the closure under the phone's DECISION."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note = compensable(world, body)
        body.apply(world.sign("CAPABILITY_DETACH", {"capability_id": "fs.write"}))
        world.tick(body)
        body.apply(world.sign("LIFECYCLE", {"mission_id": "m:comp", "state": "ABANDONED", "reason": "over"}))
        world.tick(body, 2)
        [question] = open_asks(body, "m:comp", kind="COMPENSATION")
        answer = world.approve(question["request_id"], key=phone, answer="reject")
        body.apply(answer)
        world.tick(body, 2)
        [closed] = compensated(body)
        assert closed["status"] == "FOUNDER_DECIDED" and closed["request_id"] == question["request_id"]
        body.apply(world.revoke("phone", suspected_compromise=True))
        [effect] = review_of(body)["effects"]
        assert effect["effect"] == "a compensation obligation closed by its answer" and effect["action_id"] == "w"
        assert effect["rested_on"]["command_digest"] == sha256_json(answer)
        assert note.read_text() == "draft"


def test_each_revocation_lists_only_what_it_voided_itself(world):
    """Two delegations of one key, each revoked while one of its approvals was unused: the status lists under each
    revocation what that revocation voided, and the review of the second says the first approval was voided
    earlier."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        _, one = asked(world, body, mid="m:one")
        body.apply(world.approve(one["request_id"], key=phone))
        body.apply(world.revoke("phone"))
        world.clock.advance(60)
        world.enroll(body, "phone")
        world.clock.advance(5)
        _, two = asked(world, body, mid="m:two")
        body.apply(world.approve(two["request_id"], key=phone))
        result = body.apply(world.revoke("phone", suspected_compromise=True))["result"]
        assert result["voided_requests"] == [two["request_id"]]
        review = review_of(body)
        standing_of = {c["request_id"]: c["standing"].split(":")[0].split(" ")[0] for c in review["commands"]}
        assert standing_of == {one["request_id"]: "VOIDED_BY_AN_EARLIER_REVOCATION",
                               two["request_id"]: "VOIDED_BY_THIS_REVOCATION"}
        assert review["voided_by_this_revocation"] == [two["request_id"]]
    rows = status(world.home)["security"]["device_revocations"]
    assert [r["voided_requests"] for r in rows] == [[one["request_id"]], [two["request_id"]]]


def test_a_listed_command_verifies_only_as_the_envelope_its_digest_names(world):
    """``signature_verifies`` says the listed digest is the digest of an envelope the delegated key signed. A row
    whose digest names something other than its envelope does not verify, whatever the envelope's own signature."""
    with world.body() as body:
        phone = world.enroll(body, "phone")
        _, ask = asked(world, body)
        decision = world.approve(ask["request_id"], key=phone)
        body.apply(decision)
        [accepted] = [e.payload for e in body.journal.replay("command.accepted") if e.payload["kind"] == "DECISION"]
        other = world.sign("DECISION", {"request_id": "req-other", "answer": "reject", "reason": "x"}, key=phone)
        body.journal.record("command.accepted", {**accepted, "digest": "sha256:" + "0" * 64, "envelope": other},
                            key=["forged-row"])
        body.apply(world.revoke("phone", suspected_compromise=True))
        assert [(c["command_digest"], c["signature_verifies"]) for c in review_of(body)["commands"]] == [
            (sha256_json(decision), True), ("sha256:" + "0" * 64, False)]


def test_the_ask_carries_the_first_rows_of_a_long_review_and_says_where_the_rest_is(world):
    with world.body() as body:
        phone = world.enroll(body, "phone", ("BODY_PAUSE", "BODY_RESUME"))
        for i in range(revocation.ASK_SHOWN // 2 + 1):
            body.apply(world.sign("BODY_PAUSE", {}, key=phone))
            body.apply(world.sign("BODY_RESUME", {}, key=phone))
        result = body.apply(world.revoke("phone", suspected_compromise=True))["result"]
        review = review_of(body)
        assert len(review["commands"]) == len(review["effects"]) == revocation.ASK_SHOWN + 2
        ask = body.engine.book.requests[result["integrity_review"]]
        evidence = ask["evidence"]
        assert len(evidence["commands"]) == len(evidence["effects"]) == revocation.ASK_SHOWN
        assert evidence["truncated"] is True and evidence["counts"]["commands"] == revocation.ASK_SHOWN + 2
        assert [c["command_digest"] for c in evidence["commands"]] == [
            c["command_digest"] for c in review["commands"][:revocation.ASK_SHOWN]]


def test_a_void_made_by_a_restore_names_the_restore(world):
    """A restore voids every device delegation by a revocation record of its own; the fold's void of the phone's
    unused approval names that restore."""
    from foundry.systems import seed
    from greg.recovery import restore_body
    with world.body() as body:
        body.boot()
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
    made = seed.make_seed(world.home, world.tmp / "seed-store")
    world.home.rename(world.home.parent / "lost-machine")
    world.clock.advance(60)
    report = restore_body(world.tmp / "seed-store", made["seed"], world.home, clock=world.clock)
    with world.body() as body:
        body.boot()
        void = body.engine.book.voided[ask["request_id"]]
        assert void["voided_by"]["restore_id"] == report["restore_id"]
        assert void["voided_by"]["device_key_id"] == world.kid("phone")


def test_delegating_a_suspected_key_again_is_said_on_the_result_and_in_the_status(world):
    """The founder's own key signs a delegation, so the body does not refuse a key he revoked as a suspected
    compromise. It says so: the delegation's result carries a warning and the key's reviews with their state, and
    the status shows the new delegation under the review. A key revoked plainly gets neither."""
    with world.body() as body:
        world.enroll(body, "phone")
        world.enroll(body, "laptop")
        review = body.apply(world.revoke("phone", suspected_compromise=True))["result"]["integrity_review"]
        body.apply(world.revoke("laptop"))
        world.clock.advance(60)
        plain = body.apply(world.sign("DEVICE_ENROLL", world.grant("laptop")))
        assert "warning" not in plain["result"] and "integrity_reviews" not in plain["result"]
        again = world.sign("DEVICE_ENROLL", world.grant("phone"))
        result = body.apply(again)["result"]
        [revoked, _] = body.journal.replay("device.revoked")
        assert result["warning"] == revocation.SUSPECTED_AGAIN
        assert result["integrity_reviews"] == [{"request_id": review, "revoked_at": revoked.payload["at"],
                                                "state": "OPEN"}]
        assert world.kid("phone") in body.device_keys()             # delegated all the same
    rows = status(world.home)["security"]["device_revocations"]
    [enrolled] = [e.payload for e in body.journal.replay("device.enrolled")
                  if e.payload["command_digest"] == sha256_json(again)]
    assert rows[0]["suspected_key_delegated_again"] == [{"at": enrolled["at"], "command_digest": sha256_json(again)}]
    assert "suspected_key_delegated_again" not in rows[1]
