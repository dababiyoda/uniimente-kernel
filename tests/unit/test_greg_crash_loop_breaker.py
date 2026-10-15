"""Acceptance H.G5: a body whose main loop keeps dying holds itself instead of crash-looping forever.

supervisord, systemd and launchd restart a crashing body indefinitely. greg.body's breaker counts main-loop boots
in a row (no clean stop between them) that never recorded a clean stop; once CRASH_LOOP_BOOTS of them fall inside
CRASH_LOOP_WINDOW_SECONDS, the next boot records the breaker's own hold and one founder ask. The held body ticks no
mission, stays observable, reads its inbox once a tick without spinning on a due mission or measuring itself,
survives a failure in that remaining work, and only a signed BODY_RESUME (the founder key, or a device key delegated
BODY_RESUME) lifts it. The hold is never presented as the founder's pause, nor a founder pause as the hold.

In-process Body with a test clock; boots made outside the main loop (embedded hosts, tests) never count. Main-loop
runs here replace greg.body's ``time`` with FastTime, so a 30 s tick takes no wall time.
The founder key is a per-test key, not Alfonso's.
"""
from __future__ import annotations

from datetime import timedelta
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from greg import body as body_module
from greg import presence
from greg.body import (BREAKER, CRASH_LOOP_BOOTS, CRASH_LOOP_WINDOW_SECONDS, FAULT_CLEARS, FAULTED_CLEARS, HOLD_ASK,
                       Body, Layout, crash_loop_hold, status, unfinished_main_loop_boots)
from greg.founder import public_bytes, stamp
from provenance.ledger import sha256_json
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy


def crash(home, clock, n=1, step=60.0):
    """n main-loop lifetimes that end without a clean stop (the process died after booting)."""
    for _ in range(n):
        with Body(home, clock=clock) as b:
            b.boot(main_loop=True)
        clock.advance(step)


def boot(home, clock):
    with Body(home, clock=clock) as b:
        record = b.boot(main_loop=True)
        return record, b.tick()


def holds(home):
    with Body(home) as b:
        return [e.payload for e in b.journal.replay("body.paused") if e.payload.get("by") == BREAKER]


def submit(home, key, body_id, kind, body):
    drop(home, signed(key, body_id, kind, body))


class FastTime:
    """greg.body's ``time`` for one main-loop run: a sleep advances the test clock and the monotonic clock together
    and returns at once; hooks run at their test time, and at ``until`` it requests the stop a SIGTERM would."""

    def __init__(self, clock, until, hooks=()):
        self.clock, self.until, self.now, self.body = clock, until, 0.0, None
        self.hooks = sorted(hooks, key=lambda h: h[0])

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        self.clock.advance(seconds)
        while self.hooks and self.hooks[0][0] <= self.now:
            self.hooks.pop(0)[1]()
        if self.now >= self.until:
            self.body.stop_requested = True


def run_for(monkeypatch, home, clock, *, seconds, tick_seconds=30.0, hooks=(), cap=50):
    """Body.run (the canonical main loop) for ``seconds`` of test time: (turn times, heartbeat states)."""
    fast = FastTime(clock, seconds, hooks)
    monkeypatch.setattr(body_module, "time", fast)
    body = fast.body = Body(home, clock=clock)
    turns, beats = [], []
    tick, beat = body.tick, body._heartbeat

    def counted():
        turns.append(fast.now)
        if len(turns) > cap:                              # a spinning loop: stop it so the assertion can report
            body.stop_requested = True
        return tick()
    body.tick = counted
    body._heartbeat = lambda state, summary: (beats.append(state), beat(state, summary))
    assert body.run(tick_seconds=tick_seconds) == 0
    return turns, beats


def test_repeated_unfinished_main_loop_boots_hold_the_body_until_the_founder_resumes(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, "m:held") / "n.txt"
    submit(home, key, body_id, "MISSION", mission("m:held", checks=[note_check("n", note, "ok")],
                                                  strategies=[write_strategy("w", "n.txt", "ok", ["n"])],
                                                  capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:n.txt")))
    clock = Clock()
    crash(home, clock, CRASH_LOOP_BOOTS)
    record, result = boot(home, clock)
    assert record["held"] and result["paused"] is True and "held" in result
    assert not note.exists(), "a held body ticks no mission"
    [hold] = holds(home)
    assert hold["by"] == BREAKER and len(hold["unfinished_boots"]) == CRASH_LOOP_BOOTS and "command_digest" not in hold
    assert json.loads(Layout(home).heartbeat.read_text())["state"] == "HELD"
    assert status(home)["security"]["crash_loop_hold"] == hold["why"]
    with Body(home, clock=clock) as b:                  # observable and still reading its inbox while held
        assert b.tick()["paused"] is True and not note.exists()
    submit(home, key, body_id, "BODY_RESUME", {"reason": "fixed the crash"})
    with Body(home, clock=clock) as b:
        for _ in range(3):
            b.tick()
            clock.advance(1)
        assert crash_loop_hold(b.journal) is None
    assert note.read_text() == "ok", "the founder's signed resume lifts the hold"


def test_the_count_restarts_after_a_resume_and_one_hold_per_episode(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    crash(home, clock, CRASH_LOOP_BOOTS)
    boot(home, clock)
    boot(home, clock)                                     # still held: no second hold record
    assert len(holds(home)) == 1
    submit(home, key, body_id, "BODY_RESUME", {"reason": "carry on"})
    with Body(home, clock=clock) as b:
        b.tick()
    crash(home, clock, CRASH_LOOP_BOOTS - 1)
    record, _ = boot(home, clock)                         # this boot is itself left unfinished
    assert "held" not in record, "boots before the founder's resume no longer count"
    record, _ = boot(home, clock)
    assert record["held"] and len(holds(home)) == 2


def test_spread_out_crashes_clean_stops_and_non_main_loop_boots_do_not_hold(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    crash(home, clock, CRASH_LOOP_BOOTS + 1, step=CRASH_LOOP_WINDOW_SECONDS)   # one crash per window
    assert "held" not in boot(home, clock)[0]
    (tmp_path / "second").mkdir()
    home2 = make_body(tmp_path / "second")[0]
    for _ in range(CRASH_LOOP_BOOTS + 2):                # embedded and test hosts boot without the main loop
        with Body(home2, clock=clock) as b:
            b.boot()
    assert "held" not in boot(home2, clock)[0]
    (tmp_path / "third").mkdir()
    home3 = make_body(tmp_path / "third")[0]
    for _ in range(CRASH_LOOP_BOOTS + 2):                # clean main-loop lifetimes (run opens and closes)
        assert Body(home3, clock=clock).run(tick_seconds=0.01, max_ticks=1) == 0
    with Body(home3, clock=clock) as b:
        assert unfinished_main_loop_boots(b.journal, clock()) == []
    assert holds(home) == holds(home2) == holds(home3) == []


def test_a_founder_pause_is_never_shown_as_the_breakers_hold(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    submit(home, key, body_id, "BODY_PAUSE", {"reason": "my pause"})
    with Body(home) as b:
        assert b.tick()["paused"] is True and "held" not in b.tick()
        assert crash_loop_hold(b.journal) is None
    assert json.loads(Layout(home).heartbeat.read_text())["state"] == "PAUSED"
    assert status(home)["security"]["crash_loop_hold"] is None


def test_a_held_body_with_a_due_mission_waits_a_full_tick_and_measures_nothing(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, "m:due") / "n.txt"
    note.parent.mkdir(parents=True)
    note.write_text("ok")                                 # it holds at once and re-observes every 60 s
    submit(home, key, body_id, "MISSION", mission(
        "m:due", checks=[note_check("n", note, "ok")], strategies=[write_strategy("w", "n.txt", "ok", ["n"])],
        capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:n.txt"),
        closure={"kind": "infinite", "cadence_seconds": 60}))
    clock = Clock()
    with Body(home, clock=clock) as b:
        b.tick()
    crash(home, clock, CRASH_LOOP_BOOTS)                  # its next observation falls due while it crash-loops
    with Body(home, clock=clock) as b:
        assert b.next_wake(30.0) < 1, "a mission is due"
        observed = len(b.journal.replay("mission.observed"))
    turns, beats = run_for(monkeypatch, home, clock, seconds=300)
    assert len(holds(home)) == 1 and set(beats) == {"HELD", "STOPPED"}
    assert len(turns) <= 300 / 30 + 2, f"{len(turns)} turns in 300 s held: the held body spins on the due mission"
    with Body(home, clock=clock) as b:
        assert b.journal.replay("compute.telemetry") == [], "a held body records no telemetry"
        assert len(b.journal.replay("mission.observed")) == observed, "and observes nothing"
        assert b.next_wake(30.0) == 30.0, "a held body's wait is a full tick, whatever is due"


def test_a_running_body_whose_only_due_mission_is_paused_waits_a_full_tick(tmp_path, monkeypatch):
    """A LIFECYCLE-paused mission is not stepped (MissionEngine._step returns before scheduling), so its past
    next_observe_at stays past; counting it as due turned a RUNNING body every 0.05 s."""
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, "m:due") / "n.txt"
    note.parent.mkdir(parents=True)
    note.write_text("ok")
    submit(home, key, body_id, "MISSION", mission(
        "m:due", checks=[note_check("n", note, "ok")], strategies=[write_strategy("w", "n.txt", "ok", ["n"])],
        capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:n.txt"),
        closure={"kind": "infinite", "cadence_seconds": 60}))
    clock = Clock()
    with Body(home, clock=clock) as b:
        b.tick()                                          # observed, and the next observation scheduled at +60 s
    submit(home, key, body_id, "LIFECYCLE", {"mission_id": "m:due", "state": "PAUSED", "reason": "not now"})
    with Body(home, clock=clock) as b:
        b.tick()
    clock.advance(120)                                    # its observation falls due while it is paused
    with Body(home, clock=clock) as b:
        assert b.engine.book.missions["m:due"].paused and not b.paused()
        assert b.next_wake(30.0) == 30.0, "a paused mission's past observation is not due"
        observed = len(b.journal.replay("mission.observed"))
    turns, beats = run_for(monkeypatch, home, clock, seconds=300)
    assert set(beats) == {"RUNNING", "STOPPED"}
    assert len(turns) <= 300 / 30 + 2, f"{len(turns)} turns in 300 s: the body spins on a paused mission"
    with Body(home) as b:
        assert len(b.journal.replay("compute.telemetry")) == 1, "one sample per 20 active turns, not one per second"
        assert len(b.journal.replay("mission.observed")) == observed, "the paused mission observes nothing"


@pytest.mark.parametrize("where", ["note_gap", "ingest_inbox"])
def test_a_failure_in_the_work_a_held_body_still_does_is_recorded_once_and_the_body_stays_up(tmp_path, monkeypatch,
                                                                                            where):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    crash(home, clock, CRASH_LOOP_BOOTS)

    def broken(*args, **kwargs):                           # deterministic: every turn of every restart fails here
        raise OSError(f"{where} cannot write")
    monkeypatch.setattr(*((presence, "note_gap") if where == "note_gap" else (Body, "ingest_inbox")), broken)
    note = workspace(home, "m:later") / "n.txt"
    late = mission("m:later", checks=[note_check("n", note, "ok")],
                   strategies=[write_strategy("w", "n.txt", "ok", ["n"])], capabilities=["fs.read", "fs.write"],
                   targets=("fs:*", "workspace:n.txt"))
    turns, beats = run_for(monkeypatch, home, clock, seconds=150,
                           hooks=[(45.0, lambda: drop(home, signed(key, body_id, "MISSION", late), "later.json"))])
    assert set(beats) == {"HELD", "STOPPED"} and 150 / 30 <= len(turns) <= 150 / 30 + 3, "up, observable, not spinning"
    with Body(home) as b:
        [fault] = [e.payload for e in b.journal.replay("body.fault_contained")]
        assert fault["error"] == f"OSError: {where} cannot write" and fault["state"] == "HELD"
        assert crash_loop_hold(b.journal) is not None and b.journal.replay("mission.action") == []
        reads_inbox = "m:later" in b.engine.book.missions
    assert reads_inbox == (where == "note_gap") and not note.exists()
    assert (Layout(home).inbox / "later.json").exists() == (where == "ingest_inbox")
    [shown] = status(home)["security"]["contained_faults"]          # greg status names it, and how it clears
    assert shown == {"fault": "turn", "error": fault["error"], "site": fault["site"], "state": "HELD",
                     "boot_id": fault["boot_id"], "at": fault["at"], "clear_with": FAULT_CLEARS}


def test_a_running_body_whose_work_fails_still_crashes_for_the_breaker_to_count(tmp_path, monkeypatch):
    home = make_body(tmp_path)[0]

    def broken(*args, **kwargs):
        raise OSError("note_gap cannot write")
    monkeypatch.setattr(presence, "note_gap", broken)
    with pytest.raises(OSError):
        run_for(monkeypatch, home, Clock(), seconds=150)
    with Body(home) as b:
        assert b.journal.replay("body.fault_contained") == [] and b.journal.replay("body.stopped") == []


def test_a_clean_stop_ends_the_run_of_unfinished_boots(tmp_path):
    home = make_body(tmp_path)[0]
    clock = Clock()
    crash(home, clock, 3)
    assert Body(home, clock=clock).run(tick_seconds=0.01, max_ticks=1) == 0      # a clean main-loop lifetime
    crash(home, clock, CRASH_LOOP_BOOTS - 1)
    record, _ = boot(home, clock)                         # 3 + 4 unfinished boots inside the window, not in a row
    assert "held" not in record and holds(home) == []
    record, _ = boot(home, clock)                         # the 5th unfinished in a row since the clean stop
    assert record["held"] and len(holds(home)) == 1


def test_a_founder_paused_body_that_keeps_dying_stays_under_the_founders_pause(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    submit(home, key, body_id, "BODY_PAUSE", {"reason": "my pause"})
    clock = Clock()
    with Body(home, clock=clock) as b:
        b.tick()
    crash(home, clock, CRASH_LOOP_BOOTS)                  # paused, and dying under its supervisor
    record, result = boot(home, clock)
    assert "held" not in record and "held" not in result and holds(home) == []
    with Body(home) as b:
        assert crash_loop_hold(b.journal) is None
    assert json.loads(Layout(home).heartbeat.read_text())["state"] == "PAUSED"
    assert status(home)["security"]["crash_loop_hold"] is None and status(home)["decisions_required"] == []


def test_a_held_body_that_keeps_dying_records_no_second_hold(tmp_path):
    home = make_body(tmp_path)[0]
    clock = Clock()
    crash(home, clock, CRASH_LOOP_BOOTS)
    first, _ = boot(home, clock)
    crash(home, clock, CRASH_LOOP_BOOTS)                  # held, and still dying
    again, result = boot(home, clock)
    [hold] = holds(home)
    assert "held" not in again and result["held"] and hold["boot_id"] == first["boot_id"]


def test_each_hold_raises_exactly_one_ask_and_only_a_signed_resume_closes_it(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    crash(home, clock, CRASH_LOOP_BOOTS)
    boot(home, clock)
    boot(home, clock)                                     # a restart while held asks nothing new
    [ask] = status(home)["decisions_required"]
    assert ask["kind"] == HOLD_ASK and ask["answerable"] is False and "wording_withheld" not in ask
    assert ask["why_now"] == status(home)["security"]["crash_loop_hold"] and ask["mission_id"] is None
    submit(home, key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"})
    with Body(home, clock=clock) as b:                    # an answer grants nothing: refused, still held
        result = b.tick()
        assert result["held"] and [c["status"] for c in result["commands"]] == ["REJECTED"]
        assert b.journal.replay("decision.answered") == []
    assert [r["request_id"] for r in status(home)["decisions_required"]] == [ask["request_id"]]
    submit(home, key, body_id, "BODY_RESUME", {"reason": "fixed the cause"})
    with Body(home, clock=clock) as b:
        b.tick()
        assert crash_loop_hold(b.journal) is None
        [withdrawn] = [e.payload for e in b.journal.replay("decision.withdrawn")]
        assert withdrawn["request_id"] == ask["request_id"]
    assert status(home)["decisions_required"] == []
    crash(home, clock, CRASH_LOOP_BOOTS)
    boot(home, clock)                                     # a second episode asks once more, for its own hold
    with Body(home) as b:
        requested = [e.payload for e in b.journal.replay("decision.requested") if e.payload["kind"] == HOLD_ASK]
    assert len(requested) == len(holds(home)) == 2 and requested[0]["request_id"] != requested[1]["request_id"]


def test_a_resume_withdraws_only_the_holds_ask_and_never_a_missions(tmp_path):
    """BODY_RESUME is delegable, so a phone key may sign it; it must close the breaker's own ask and nothing the
    founder still has to decide: a mission's open APPROVAL, and another's NO_STRATEGY and SCOPE_RENEWAL, stay open
    across the hold and the resume."""
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    phone = Ed25519PrivateKey.generate()
    submit(home, key, body_id, "DEVICE_ENROLL", {"public_key": public_bytes(phone.public_key()).hex(),
                                                 "label": "phone", "kinds": ["BODY_RESUME"],
                                                 "expires_at": stamp(clock.now + timedelta(days=30))})
    ws = workspace(home, "m:ask")
    submit(home, key, body_id, "MISSION", mission(        # d.txt lies outside the cone: an APPROVAL ask
        "m:ask", checks=[note_check("d", ws / "d.txt", "shipped")],
        strategies=[write_strategy("w", "d.txt", "shipped", ["d"])], capabilities=["fs.read", "fs.write"],
        targets=("fs:*", "workspace:c.txt")))
    short = mission("m:short", checks=[note_check("n", workspace(home, "m:short") / "n.txt", "x")], strategies=[],
                    capabilities=["fs.read"], ceiling="read_only")
    short["light_cone"]["horizon"] = stamp(clock.now + timedelta(hours=1))   # its mandate expires: SCOPE_RENEWAL
    submit(home, key, body_id, "MISSION", short)
    with Body(home, clock=clock) as b:
        for _ in range(4):
            b.tick()
            clock.advance(1)
        clock.advance(7200)
        b.tick()
    founders = sorted((r["kind"], r["request_id"]) for r in status(home)["decisions_required"])
    assert [k for k, _ in founders] == ["APPROVAL", "NO_STRATEGY", "SCOPE_RENEWAL"]
    crash(home, clock, CRASH_LOOP_BOOTS)
    boot(home, clock)
    held = sorted((r["kind"], r["request_id"]) for r in status(home)["decisions_required"])
    assert [k for k, _ in held] == ["APPROVAL", HOLD_ASK, "NO_STRATEGY", "SCOPE_RENEWAL"]
    [hold_ask] = [rid for k, rid in held if k == HOLD_ASK]
    submit(home, phone, body_id, "BODY_RESUME", {"reason": "resumed from the phone"})
    with Body(home, clock=clock) as b:
        [result] = b.tick()["commands"]
        assert result["status"] == "APPLIED" and crash_loop_hold(b.journal) is None
        assert [e.payload["request_id"] for e in b.journal.replay("decision.withdrawn")] == [hold_ask]
    assert sorted((r["kind"], r["request_id"]) for r in status(home)["decisions_required"]) == founders


class Died(Exception):
    """The body process ending between two appends (a power loss, a SIGKILL)."""


@pytest.mark.parametrize("how", ["older_code", "crash_between"])
def test_a_hold_without_its_ask_gets_exactly_one_at_the_next_boot(tmp_path, monkeypatch, how):
    """The ask is derived from the hold record at every boot, not only at the boot that records the hold: a hold
    written by older code (which asked nothing) or a body that died between the hold and its ask still ends with
    exactly one ask, and further boots add none."""
    home = make_body(tmp_path)[0]
    clock = Clock()
    crash(home, clock, CRASH_LOOP_BOOTS)
    if how == "older_code":                               # the hold exactly as 95a104f recorded it, and no ask
        with Body(home, clock=clock) as b:
            crashed = unfinished_main_loop_boots(b.journal, clock())
            record = b.boot(main_loop=False)
            b.journal.record("body.paused", {
                "by": BREAKER, "boot_id": record["boot_id"], "unfinished_boots": crashed,
                "window_seconds": CRASH_LOOP_WINDOW_SECONDS, "at": record["at"],
                "why": f"{len(crashed)} main-loop boots ended without a clean stop within "
                       f"{CRASH_LOOP_WINDOW_SECONDS} s; no mission runs until the founder resumes",
                "lifted_by": "a founder-signed BODY_RESUME"}, key=[record["boot_id"], "crash-loop"])
    else:
        def dying(journal, ask, **kw):
            raise Died("after the hold, before its ask")
        monkeypatch.setattr(body_module.asks, "record", dying)
        with pytest.raises(Died):
            boot(home, clock)
        monkeypatch.undo()
    with Body(home) as b:
        assert crash_loop_hold(b.journal) is not None and b.journal.replay("decision.requested") == []
    for _ in range(2):
        boot(home, clock)
        [ask] = status(home)["decisions_required"]
        assert ask["kind"] == HOLD_ASK and ask["why_now"] == status(home)["security"]["crash_loop_hold"]
    assert len(holds(home)) == 1


def test_a_file_a_held_body_cannot_ingest_is_set_aside_and_never_keeps_it_from_a_signed_resume(tmp_path, monkeypatch):
    """The inbox is read in name order (greg send_signed names files by issue time, so a later resume sorts after an
    earlier file). A file whose ingestion raised (here JSON nested past the parser's recursion limit) failed every
    turn of the held body, so the founder's signed BODY_RESUME behind it was never read, and greg status showed
    nothing. A running body still exits on such a file, so the breaker counts it; a held body sets it aside under
    inbox/faulted byte for byte, records it once, reads on, and status names it with how to clear it. Setting it
    aside lifts nothing, nor does a forged resume behind it: only the signed one does."""
    home, key, body_id, _ = make_body(tmp_path)
    inbox = Layout(home).inbox
    poison = ("[" * 100_000 + "]" * 100_000).encode()
    (inbox / "0-poison.json").write_bytes(poison)
    clock = Clock()
    for _ in range(CRASH_LOOP_BOOTS):                     # a running body exits on it, and the breaker counts it
        with pytest.raises(RecursionError):
            run_for(monkeypatch, home, clock, seconds=30)
        clock.advance(60)
    assert (inbox / "0-poison.json").read_bytes() == poison
    with Body(home) as b:
        assert b.journal.replay("command.faulted") == [] and crash_loop_hold(b.journal) is None
    drop(home, signed(Ed25519PrivateKey.generate(), body_id, "BODY_RESUME", {"reason": "not yours"}), "1-forged.json")
    turns, beats = run_for(monkeypatch, home, clock, seconds=90)
    assert set(beats) == {"HELD", "STOPPED"} and len(holds(home)) == 1, "setting aside or forging lifts nothing"
    assert (inbox / "faulted" / "0-poison.json").read_bytes() == poison and not (inbox / "0-poison.json").exists()
    with Body(home) as b:
        [record] = [e.payload for e in b.journal.replay("command.faulted")]
        assert record["file"] == record["kept_as"] == "0-poison.json" and record["state"] == "HELD"
        assert record["error"].startswith("RecursionError") and record["sha256"] == sha256_json(poison.hex())
        assert [e.payload["file"] for e in b.journal.replay("command.rejected")] == ["1-forged.json"]
    [shown] = status(home)["security"]["contained_faults"]
    assert shown == {"fault": "inbox file set aside", "file": "inbox/faulted/0-poison.json", "sha256": record["sha256"],
                     "error": record["error"], "state": "HELD", "at": record["at"], "clear_with": FAULTED_CLEARS}

    (inbox / "2-poison.json").write_bytes(poison)            # and again, right in front of the founder's resume
    drop(home, signed(key, body_id, "BODY_RESUME", {"reason": "fixed the cause"}), "3-resume.json")
    turns, beats = run_for(monkeypatch, home, clock, seconds=90)
    assert beats[0] == "RUNNING" and "HELD" not in beats, "the signed resume behind it was read in the same turn"
    with Body(home) as b:
        assert crash_loop_hold(b.journal) is None
        assert [e.payload["kind"] for e in b.journal.replay("command.accepted")] == ["BODY_RESUME"]
        assert [e.payload["file"] for e in b.journal.replay("command.faulted")] == ["0-poison.json", "2-poison.json"]
    assert (inbox / "faulted" / "2-poison.json").read_bytes() == poison
    assert status(home)["decisions_required"] == []
    assert [f["file"] for f in status(home)["security"]["contained_faults"]] == ["inbox/faulted/0-poison.json",
                                                                                "inbox/faulted/2-poison.json"]
