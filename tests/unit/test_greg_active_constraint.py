"""Acceptance A.G2: every active mission on the Body names its active constraint.

Mission A: "GREG backcasts, identifies the active constraint, performs permitted work ... and presents an
appropriate founder decision." `greg status` now carries, per mission, the first pursued check that has not
passed, the strategies held because a check they require has not passed, and the blocker with what would lift it
(authority, capability, a person's work, evidence or a strategy). It is derived only from retained facts, so a
restart reads the same constraint, and it disappears when the mission closes. A request the founder already
answered is shown as answered, lifted by the next tick, never as still waiting on the founder; and a pause in
force (the body's, the crash-loop breaker's, the mission's own) is named first, with what lifts it.

In-process Body with a test clock (SANDBOX); the founder key is a per-test key, not Alfonso's.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from greg.body import BREAKER, CRASH_LOOP_BOOTS, RESUME_LIFTS, Body, Layout, status
from greg.journal import iso
from greg.missions import CONSTRAINT_LIFTED_BY, MISSION_RESUME_LIFTS
from greg.templates import human_work
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
    with Body(home, clock=clock) as b:                     # answered, not yet acted on: nothing waits on the founder
        b.ingest_inbox()
    answered = constraint(home)["blocker"]
    assert answered["answered"] == "approve" and answered["lifted_by"] == "the next tick"
    assert status(home)["decisions_required"] == []
    with Body(home, clock=clock) as b:
        for _ in range(4):
            b.tick()
            clock.advance(1)
    assert (ws / "d.txt").read_text() == "shipped"
    assert constraint(home) is None                        # closed: nothing left to wait on


def test_a_pause_in_force_is_named_first_with_what_lifts_it(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    ws = workspace(home, "m:two")
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:two", checks=[note_check("c", ws / "c.txt", "ok")], strategies=[write_strategy("w", "c.txt", "ok", ["c"])],
        capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:c.txt"))))
    clock = Clock()
    with Body(home, clock=clock) as b:
        b.ingest_inbox()

    def apply(kind, body):
        drop(home, signed(key, body_id, kind, body))
        with Body(home, clock=clock) as b:
            b.tick()
        return constraint(home)

    mission_pause = {"by": "mission paused (signed LIFECYCLE)", "lifted_by": MISSION_RESUME_LIFTS}
    paused = apply("LIFECYCLE", {"mission_id": "m:two", "state": "PAUSED", "reason": "not now"})
    assert paused == {"paused_by": [mission_pause], "check_id": "c", "observed": "never observed",
                      "held_strategies": []} and not (ws / "c.txt").exists()
    both = apply("BODY_PAUSE", {"reason": "not anything"})
    assert both["paused_by"] == [{"by": "body paused (signed BODY_PAUSE)", "lifted_by": RESUME_LIFTS}, mission_pause]
    apply("BODY_RESUME", {"reason": "carry on"})
    for _ in range(CRASH_LOOP_BOOTS + 1):                  # then the body crash-loops and the breaker holds it
        with Body(home, clock=clock) as b:
            b.boot(main_loop=True)
        clock.advance(60)
    held = constraint(home)["paused_by"]
    assert held == [{"by": BREAKER, "why": status(home)["security"]["crash_loop_hold"], "lifted_by": RESUME_LIFTS},
                    mission_pause]
    assert apply("BODY_RESUME", {"reason": "fixed"})["paused_by"] == [mission_pause]
    assert "paused_by" not in (apply("LIFECYCLE", {"mission_id": "m:two", "state": "ACTIVE", "reason": "go"}) or {})
    assert (ws / "c.txt").read_text() == "ok"


def test_a_withdrawn_ask_whose_unblock_was_lost_is_lifted_by_the_next_tick(tmp_path):
    """Every withdraw site records decision.withdrawn, then mission.unblocked: two appends. A body that died
    between them left an APPROVAL blocker no answer could lift (a withdrawn request takes none) while status said
    nothing waits on the founder. The next tick finishes the withdrawal, and the mission asks afresh."""
    home, key, body_id, _ = make_body(tmp_path)
    ws = workspace(home, "m:two")
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:two", checks=[note_check("c", ws / "c.txt", "ok"), note_check("d", ws / "d.txt", "shipped")],
        strategies=[write_strategy("w", "c.txt", "ok", ["c"]),
                    write_strategy("w2", "d.txt", "shipped", ["d"], requires=["c"])],
        capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:c.txt"))))   # d.txt is outside the cone
    clock = Clock()
    why = ("world re-observed while preparing: every check the awaited move advances now passes without any GREG "
           "action")                                       # greg/missions.py _prepare's withdrawal
    with Body(home, clock=clock) as b:
        for _ in range(6):
            b.tick()
            clock.advance(1)
        rid = b.engine.book.missions["m:two"].blocker["request_id"]
        assert b.engine.book.requests[rid]["kind"] == "APPROVAL"
        b.journal.record("decision.withdrawn", {"request_id": rid, "mission_id": "m:two", "why": why,
                                                "evidence": [], "at": iso(clock())}, key=[rid, "withdrawn"])
    stuck = constraint(home)["blocker"]                    # the body died here, before mission.unblocked
    assert stuck["request_id"] == rid and stuck["withdrawn"] == why and stuck["lifted_by"] == "the next tick"
    assert status(home)["decisions_required"] == []
    with Body(home, clock=clock) as b:
        b.tick()
        [lifted] = [e.payload for e in b.journal.replay("mission.unblocked")
                    if (e.payload["resolved"] or {}).get("request_id") == rid]
        assert lifted["why"] == why                        # the fact the withdraw site would have recorded
        for _ in range(3):
            b.tick()
            clock.advance(1)
    now = constraint(home)["blocker"]                      # d still fails and w2 still needs authority: a new ask
    assert now["request_id"] != rid and now["kind"] == "APPROVAL" and now["lifted_by"] == "authority"
    assert "withdrawn" not in now and "answered" not in now
    assert [r["request_id"] for r in status(home)["decisions_required"]] == [now["request_id"]]


@pytest.mark.parametrize("kind", ["CAPABILITY_ATTACH", "HUMAN_WORK"])
def test_an_answer_that_is_only_a_record_keeps_the_blockers_lifter(tmp_path, kind):
    """Approve on a capability or human-work ask only records the answer (greg/asks.py ANSWER_ONLY_RECORDS):
    the mission still waits on an attach or on the person's deliverable, and its constraint keeps saying so."""
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:needs"
    if kind == "CAPABILITY_ATTACH":
        spec = mission(mid, checks=[note_check("n", workspace(home, mid) / "n.txt", "done")],
                       strategies=[{"action_id": "x", "function": "text.no_such_function_anywhere",
                                    "target": "fs:n.txt", "advances": ["n"], "rationale": "needs a capability"}],
                       capabilities=["fs.read"])
    else:
        spec = human_work(function="professional.legal_review", purpose="Have my lease reviewed before I sign it",
                          deliverable="lease-review.pdf", workspace_root=Layout(home).workspace)
        mid = spec["mission_id"]
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as b:
        for _ in range(4):
            b.tick()
            clock.advance(60)
    before = constraint(home, mid)["blocker"]
    assert before["kind"] == kind and before["lifted_by"] == CONSTRAINT_LIFTED_BY[kind]
    drop(home, signed(key, body_id, "DECISION", {"request_id": before["request_id"], "answer": "approve"}))
    with Body(home, clock=clock) as b:
        b.ingest_inbox()
        assert before["request_id"] in b.engine.book.answers
    assert constraint(home, mid)["blocker"] == before, "an answer that is only a record lifts nothing"
    with Body(home, clock=clock) as b:
        for _ in range(3):
            b.tick()
            clock.advance(60)
    assert constraint(home, mid)["blocker"] == before, "and the next tick does not lift it either"


def test_a_legacy_answer_to_an_unanswerable_ask_does_not_change_its_lifter(tmp_path):
    """Older ledgers may hold an answer to a SCOPE_RENEWAL (since refused: greg/missions.py NOT_ANSWERABLE). Such
    an answer lifts nothing: the mandate still needs a new signed MISSION, so the constraint keeps that lifter."""
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    mid = "m:short"
    spec = mission(mid, checks=[note_check("n", workspace(home, mid) / "n.txt", "x")], strategies=[],
                   capabilities=["fs.read"], ceiling="read_only")
    spec["light_cone"]["horizon"] = iso(clock.now + timedelta(hours=1))
    drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))
    with Body(home, clock=clock) as b:
        b.tick()
        clock.advance(7200)                               # the mandate expires
        b.tick()
        b.engine.book.rebuild()
        rid = b.engine.book.missions[mid].blocker["request_id"]
        assert b.engine.book.requests[rid]["kind"] == "SCOPE_RENEWAL"
        b.journal.record("decision.answered", {"request_id": rid, "mission_id": mid, "answer": "approve",
                                               "reason": "", "command_digest": "sha256:old"}, key=rid)
    renewal = constraint(home, mid)["blocker"]
    assert renewal["request_id"] == rid and renewal["kind"] == "SCOPE_RENEWAL"
    assert renewal["lifted_by"] == CONSTRAINT_LIFTED_BY["SCOPE_RENEWAL"] and "answered" not in renewal
    with Body(home, clock=clock) as b:                     # the next tick re-asks for the renewal, as before
        b.tick()
    again = constraint(home, mid)["blocker"]
    assert again["kind"] == "SCOPE_RENEWAL" and again["request_id"] != rid and again["lifted_by"] == renewal["lifted_by"]
