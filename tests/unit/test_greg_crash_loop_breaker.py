"""Acceptance H.G5: a body whose main loop keeps dying holds itself instead of crash-looping forever.

supervisord, systemd and launchd restart a crashing body indefinitely. greg.body's breaker counts main-loop boots
that never recorded a clean stop; once CRASH_LOOP_BOOTS of them fall inside CRASH_LOOP_WINDOW_SECONDS, the next
boot records the breaker's own hold. The held body ticks no mission, stays observable, reads its inbox, and only
the founder's signed BODY_RESUME lifts it. The hold is never presented as the founder's pause.

In-process Body with a test clock; boots made outside the main loop (embedded hosts, tests) never count.
The founder key is a per-test key, not Alfonso's.
"""
from __future__ import annotations

import json

from greg.body import (BREAKER, CRASH_LOOP_BOOTS, CRASH_LOOP_WINDOW_SECONDS, Body, Layout, crash_loop_hold, status,
                       unfinished_main_loop_boots)
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
