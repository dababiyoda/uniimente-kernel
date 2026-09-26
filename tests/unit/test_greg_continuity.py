"""Continuity of the GREG body across power loss and concurrent founder reads.

Two failures the supervised body could not survive before:

1. A final ledger line torn by power loss or SIGKILL made every open refuse the
   ledger, so after an unlucky reboot the supervisor restarted a body that could
   never boot again.
2. ``greg morning`` opened a second *writer* while the supervised body held the
   single-writer lock, so the morning report failed exactly when it was needed.
"""
import json
from pathlib import Path

import pytest

from greg.body import Body, Layout, morning_projection, observe, status
from greg import cli
from provenance.ledger import WriterConflict
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

TORN = b'{"seq": 99, "record_type": "event", "payload": {"type": "greg.mission.act'


def _note_mission(home, key, body_id):
    note = workspace(home, "m:note") / "note.txt"
    spec = mission("m:note", checks=[note_check("note", note, "alive")],
                   strategies=[write_strategy("write", "note.txt", "alive", ["note"])],
                   capabilities=["fs.read", "fs.write"])
    drop(home, signed(key, body_id, "MISSION", spec))


def test_body_boots_after_a_torn_tail_and_keeps_the_bytes(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    _note_mission(home, key, body_id)
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    body.tick()
    body.close()  # no body.stopped record: an unclean end, like a power cut mid-run
    ledger = Layout(home).ledger
    with open(ledger, "ab") as fh:
        fh.write(TORN)

    body = Body(home, clock=clock).open()
    boot = body.boot()
    assert boot["ledger_recovery"]["bytes"] == len(TORN)
    sidecar = Path(boot["ledger_recovery"]["sidecar"])
    assert sidecar.read_bytes() == TORN and sidecar.parent == Layout(home).home
    assert body.journal.replay("body.recovered"), "an unclean end is reported as recovered"
    assert body.ledger.verify_chain()[0]
    clock.advance(60)  # a reboot takes time; a same-instant observation would reuse its retained receipt
    body.tick()  # the mission continues on the recovered history
    assert any(e.payload["mission_id"] == "m:note" for e in body.journal.replay("mission.achieved"))
    body.close()


def test_founder_reads_work_while_the_body_owns_the_ledger(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    _note_mission(home, key, body_id)
    body = Body(home, clock=Clock()).open()
    body.boot()
    body.tick()
    try:
        with pytest.raises(WriterConflict):   # the old `greg morning` path: a second writer
            Body(home).open()
        report = morning_projection(home)
        assert report["reality_status"] == "RETAINED_EVIDENCE_PROJECTION"
        assert report["q1_goals_worked_on"][0]["mission_id"] == "m:note"
        assert status(home)["security"]["chain_verified"] is True
        with observe(home) as journal:
            assert journal.replay("mission.registered")
    finally:
        body.close()


def test_a_line_still_being_written_does_not_break_a_reader(tmp_path, capsys):
    home, key, body_id, _ = make_body(tmp_path)
    body = Body(home, clock=Clock()).open()
    body.boot()
    ledger = Layout(home).ledger
    with open(ledger, "ab") as fh:
        fh.write(b'{"seq": 5, "ts_utc"')   # the writer's append is half done
    try:
        assert status(home)["security"]["chain_verified"] is True
        assert cli.main(["--home", str(home), "vepmc"]) == 0
        assert json.loads(capsys.readouterr().out)["VEPMC"] == 0
        assert cli.main(["--home", str(home), "morning"]) == 0
    finally:
        body.close()


def test_mark_reviewed_while_running_is_a_clear_refusal_not_a_crash(tmp_path, capsys):
    home, _, _, _ = make_body(tmp_path)
    body = Body(home, clock=Clock()).open()
    try:
        assert cli.main(["--home", str(home), "morning", "--mark-reviewed"]) == 2
        assert "owns the ledger" in capsys.readouterr().err
    finally:
        body.close()


def test_two_ineffective_strategies_wait_for_the_founder_instead_of_crash_looping(tmp_path):
    """Regression: ``Journal.record`` hashed the per-call envelope (emission time, per-boot
    passport), so re-recording a retained routing outcome raised EventError on the third
    tick, and again after every supervisor restart."""
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, "m:ineffective") / "note.txt"
    spec = mission("m:ineffective", checks=[note_check("note", note, "alive")],
                   strategies=[write_strategy("a", "note.txt", "dead", ["note"]),
                               write_strategy("b", "note.txt", "still dead", ["note"])],
                   capabilities=["fs.read", "fs.write"])
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    states = []
    for _ in range(5):
        clock.advance(60)
        states.append(body.tick()["missions"][0]["state"])
    body.close()
    assert states == ["ACTED", "ACTED", "BLOCKED", "WAITING", "WAITING"]
    body = Body(home, clock=clock).open()   # a restart replays the same facts without conflict
    body.boot()
    clock.advance(60)
    assert body.tick()["missions"][0]["state"] == "WAITING"
    outcomes = [e.payload["action_id"] for e in body.journal.replay("routing.outcome")]
    assert sorted(outcomes) == ["a", "b"]                       # each recorded exactly once
    body.close()


def test_same_identity_with_different_content_is_still_refused(tmp_path):
    from events.spine import EventError
    home, _, _, _ = make_body(tmp_path)
    with Body(home) as body:
        body.journal.record("probe.fact", {"value": 1}, key="probe")
        assert body.journal.record("probe.fact", {"value": 1}, key="probe").payload == {"value": 1}
        with pytest.raises(EventError, match="different content"):
            body.journal.record("probe.fact", {"value": 2}, key="probe")


def test_stop_arriving_mid_tick_admits_no_further_dispatch(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    for name, priority in (("m:first", 90), ("m:second", 10)):
        note = workspace(home, name) / "note.txt"
        drop(home, signed(key, body_id, "MISSION", mission(
            name, checks=[note_check("note", note, "alive")], priority=priority,
            strategies=[write_strategy("write", "note.txt", "alive", ["note"])],
            capabilities=["fs.read", "fs.write"])))
    body = Body(home, clock=Clock()).open()
    body.boot()
    body.ingest_inbox()
    original = body.engine._step

    def step_then_stop(m, now):                  # the founder's STOP lands during the first step
        result = original(m, now)
        Layout(home).stop_file.touch()
        return result

    body.engine._step = step_then_stop
    summary = body.tick()["missions"]
    body.close()
    assert summary[0]["mission_id"] == "m:first" and summary[0]["state"] == "ACTED"
    assert summary[1] == {"mission_id": "m:second", "state": "NOT_STEPPED", "why": "stop requested"}
    assert not (workspace(home, "m:second") / "note.txt").exists()
