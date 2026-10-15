"""Acceptance A.G2: every active mission on the Body names its active constraint.

Mission A: "GREG backcasts, identifies the active constraint, performs permitted work ... and presents an
appropriate founder decision." `greg status` now carries, per mission, the first pursued check that has not
passed, the strategies held because a check they require has not passed, and the blocker with what would lift it
(authority, capability, a person's work, evidence or a strategy). It is derived only from retained facts, so a
restart reads the same constraint, and it disappears when the mission closes.

In-process Body with a test clock (SANDBOX); the founder key is a per-test key, not Alfonso's.
"""
from __future__ import annotations

from greg.body import Body, status
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy


def constraint(home, mid="m:two"):
    return next(m for m in status(home)["missions"] if m["mission_id"] == mid)["active_constraint"]


def test_the_active_constraint_names_the_failing_check_the_held_work_and_what_lifts_the_block(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    ws = workspace(home, "m:two")
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:two", checks=[note_check("c", ws / "c.txt", "ok"), note_check("d", ws / "d.txt", "shipped")],
        strategies=[write_strategy("w", "c.txt", "ok", ["c"]),
                    write_strategy("w2", "d.txt", "shipped", ["d"], requires=["c"])],
        capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:c.txt"))))   # d.txt is outside the cone
    clock = Clock()
    with Body(home, clock=clock) as b:
        b.ingest_inbox()
    first = constraint(home)
    assert first == {"check_id": "c", "observed": "never observed", "held_strategies": ["w2"]}

    with Body(home, clock=clock) as b:
        for _ in range(6):
            b.tick()
            clock.advance(1)
        [ask] = [e.payload for e in b.journal.replay("decision.requested") if e.payload.get("action_id") == "w2"]
    now = constraint(home)
    assert now["check_id"] == "d" and now["held_strategies"] == [] and (ws / "c.txt").read_text() == "ok"
    assert now["blocker"]["request_id"] == ask["request_id"] and now["blocker"]["kind"] == "APPROVAL"
    assert now["blocker"]["lifted_by"] == "authority"
    with Body(home, clock=clock) as b:                     # a restart reads the same constraint
        b.tick()
    assert constraint(home) == now

    drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"}))
    with Body(home, clock=clock) as b:
        for _ in range(4):
            b.tick()
            clock.advance(1)
    assert (ws / "d.txt").read_text() == "shipped"
    assert constraint(home) is None                        # closed: nothing left to wait on
