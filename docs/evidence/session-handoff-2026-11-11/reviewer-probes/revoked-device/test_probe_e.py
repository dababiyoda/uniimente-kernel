"""Reviewer probe E: exactly-once recovery of a COMPENSATION that completed at the Gate (receipt on the ledger) when
the body died before recording it, and the device that approved it is revoked before the restart.

An action has a write-ahead intent (mission.dispatching) and is settled from the Gate's record whatever the approval
state (MissionEngine._recover_dispatch). A compensation has none: it goes back through AuthorityOffice.act, which
answers OUTSIDE_SCOPE before it looks for the retained receipt once the approval is void."""
import pytest

from greg import revocation  # noqa
from tests.greg_fixtures import drop, mission, note_check, workspace, write_strategy
from tests.unit.test_greg_revoked_device_authority import World, open_asks, trail  # noqa

RESTORE = {"capability": "fs.write", "params": {"relative_path": "note.txt", "content": "original"},
           "target": "workspace:note.txt"}
MID = "m:comp"


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def compensated(body):
    return [e.payload for e in body.journal.replay("mission.compensated")]


def receipts_of_compensation(body):
    """Gate receipts of the compensating write (positive results that wrote 'original')."""
    out = []
    for r in body.ledger.by_type("receipt"):
        result = r.payload.get("result") or {}
        if result.get("observed_outcome", "").startswith("compensation of"):
            out.append((r.seq, result.get("result_class")))
    return out


def superseded_and_approved(world, body, phone):
    note = workspace(world.home, MID) / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("original")
    body.apply(world.sign("MISSION", mission(
        MID, checks=[note_check("c", note, "draft")],
        strategies=[write_strategy("w", "note.txt", "draft", ["c"], compensate=RESTORE)],
        capabilities=["fs.read", "fs.write"],
        closure={"kind": "infinite", "ladder": [["c"]], "cadence_seconds": 3600})))
    world.tick(body, 3)
    assert note.read_text() == "draft"
    body.apply(world.sign("LIFECYCLE", {"mission_id": MID, "state": "SUPERSEDED", "reason": "replaced"}))
    world.tick(body, 2)
    [ask] = open_asks(body, MID)
    assert ask.get("compensation") is True
    body.apply(world.approve(ask["request_id"], key=phone))
    return note, ask


def die_before_recording_the_compensation(world, body):
    real = body.journal.record

    def record(kind, data, **kw):
        if kind == "mission.compensated":
            raise RuntimeError("power lost after the Gate's receipt, before the mission recorded it")
        return real(kind, data, **kw)
    body.journal.record = record
    with pytest.raises(RuntimeError, match="power lost"):
        body.tick()
    body.journal.record = real


@pytest.mark.parametrize("revoked", [False, True])
def test_E1_a_compensation_completed_before_the_revocation_is_settled_from_its_receipt(world, revoked):
    body = world.body().__enter__()
    try:
        phone = world.enroll(body, "phone")
        note, ask = superseded_and_approved(world, body, phone)
        die_before_recording_the_compensation(world, body)
        assert note.read_text() == "original"                    # the compensation DID run
        assert compensated(body) == []
        done = receipts_of_compensation(body)
        assert [c for _, c in done] == ["positive"]
    finally:
        body.__exit__(None, None, None)
    if revoked:
        drop(world.home, world.revoke("phone"), "a-revoke.json")  # the founder revokes the phone while the body is down
    with world.body() as body:
        world.tick(body, 3)
        rows = compensated(body)
        asks_open = open_asks(body, MID)
        print(f"revoked={revoked}: mission.compensated={[(r['status'], r.get('receipt', '') and 'receipt') for r in rows]}"
              f" open APPROVAL asks={[(a['request_id'][-6:], a.get('compensation')) for a in asks_open]}")
        assert receipts_of_compensation(body) == done            # the Gate never dispatched it twice
        if not revoked:
            assert [r["status"] for r in rows] == ["DONE"] and asks_open == []   # receipt reused: recorded as done
            return
        # after the revocation: is the completed compensation recorded, or is the founder asked to approve an effect
        # that already happened?
        assert rows == [] and len(asks_open) == 1 and asks_open[0]["request_id"] != ask["request_id"], \
            "clean: the completed compensation was settled from its receipt"
        shown = asks_open[0]
        print("the new ask says:", shown["why_now"][:160], "|", shown["recommendation"][:120])
        print("consequence_of_no_response:", shown["consequence_of_no_response"])
        assert "already" not in (shown["why_now"] + shown["recommendation"]).lower()
        # the founder, told that "nothing is run for it" on a reject, rejects: the ledger then says DECLINED
        body.apply(world.approve(shown["request_id"], answer="reject"))
        world.tick(body, 2)
        rows = compensated(body)
        print("after the founder's reject:", [(r["status"], r["reasons"]) for r in rows], "| note:", note.read_text())
        assert [r["status"] for r in rows] == ["DECLINED"] and rows[0]["receipt"] is None
        assert note.read_text() == "original"                    # yet the effect happened and its receipt exists
