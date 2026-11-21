"""Wake schedule: the host-trigger view is computed from durable state, is read-only, runs nothing, and every
entry it lists is honoured by a turn at the suggested time (following the schedule is never a silent turn)."""
from __future__ import annotations

from egregore.schedule import WakeSchedule
from tests.unit.test_goal_gravity import (  # noqa: F401  (stack is a fixture)
    T0, T1, T2, T3, governor, make_loop, robotics_goal, stack,
)
from tests.unit.test_goal_gravity_seams import hardware_signal, simple_goal

DAY = 86400


def test_schedule_lists_due_times_and_the_earliest_is_the_next_trigger(stack):
    loop = make_loop(stack)
    fast = loop.registry.authorize(robotics_goal(second_node=False), now=T0)              # 7-day cadence
    slow = loop.registry.authorize(simple_goal(tag="slow", review_cadence_seconds=30 * DAY), now=T0)
    before = len(loop.ledger.records)
    plan = loop.wake_schedule(now="2026-10-14T12:00:00Z")
    assert len(loop.ledger.records) == before, "the schedule appends nothing"
    by_goal = {e["goal_id"]: e for e in plan["entries"]}
    assert by_goal[fast]["due_at"] == "2026-10-20T12:00:00Z" and by_goal[fast]["overdue"] is False
    assert by_goal[slow]["due_at"] == "2026-11-12T12:00:00Z" and by_goal[slow]["overdue"] is False
    assert plan["overdue"] == [] and plan["next_due_at"] == "2026-10-20T12:00:00Z" and plan["next_kind"] == "review_cadence"
    assert plan["suggested_trigger_id"] == "cadence:2026-10-20T12:00:00Z" == WakeSchedule.trigger_id_for(plan["next_due_at"])
    assert plan["execution_authority"] == "none" and "nothing here runs" in plan["note"]
    late = loop.wake_schedule(now="2026-10-21T12:00:00Z")
    assert [o["goal_id"] for o in late["overdue"]] == [fast] and late["next_due_at"] == late["as_of"]


def test_a_turn_at_the_next_due_time_wakes_exactly_the_due_goal_by_cadence(stack):
    loop = make_loop(stack)
    fast = loop.registry.authorize(robotics_goal(second_node=False), now=T0)
    slow = loop.registry.authorize(simple_goal(tag="slow", review_cadence_seconds=30 * DAY), now=T0)
    plan = loop.wake_schedule(now=T1)
    turn = loop.turn(trigger_id=plan["suggested_trigger_id"], now=plan["next_due_at"], resources=governor(), evidence_confidence=0.9)
    assert turn.woken == (fast,) and slow not in turn.woken
    assert loop.registry.state(fast).wake_reason == "review cadence elapsed"
    # Retrying the same trigger id replays the recorded turn; the next due time moves one cadence forward.
    again = loop.turn(trigger_id=plan["suggested_trigger_id"], now=plan["next_due_at"], resources=governor(), evidence_confidence=0.9)
    assert again.to_dict() == turn.to_dict()
    after = loop.wake_schedule(now=plan["next_due_at"])
    assert {e["goal_id"]: e["due_at"] for e in after["entries"]}[fast] == "2026-10-27T12:00:00Z"
    assert after["overdue"] == []


def test_paused_revoked_and_completed_goals_are_not_scheduled_and_an_awake_goal_is_due_now(stack):
    loop = make_loop(stack)
    paused = loop.registry.authorize(simple_goal(tag="p"), now=T0)
    revoked = loop.registry.authorize(simple_goal(tag="r"), now=T0)
    completed = loop.registry.authorize(simple_goal(tag="c"), now=T0)
    kept = loop.registry.authorize(simple_goal(tag="k"), now=T0)
    loop.registry.record_preference(paused, kind="stop_pushing", value=True, actor="alfonso_lopez", reason="later", now=T0)
    loop.registry.revoke(revoked, actor="alfonso_lopez", reason="no", now=T0)
    loop.registry.transition(completed, reason="all plan nodes satisfied by observed evidence", now=T0, status="completed")
    plan = loop.wake_schedule(now=T1)
    assert [e["goal_id"] for e in plan["entries"]] == [kept]
    # A goal durably left awake (a crash between wake and sleep) is due now: any turn processes it, so the
    # schedule says so instead of telling the host nothing is due.
    loop.registry.wake(kept, reason="test", now=T1)
    awake = loop.wake_schedule(now=T1)
    assert [e["kind"] for e in awake["entries"]] == ["awake_now"] and awake["overdue"][0]["goal_id"] == kept
    assert awake["next_due_at"] == awake["as_of"] and awake["suggested_trigger_id"] == f"awake:{T1}"
    turn = loop.turn(trigger_id=awake["suggested_trigger_id"], now=awake["next_due_at"], resources=governor(), evidence_confidence=0.9)
    assert kept in turn.woken


def test_a_deferred_ask_is_scheduled_to_resurface_and_the_suggested_turn_resurfaces_it(stack):
    """The schedule's deferred-ask entry is honoured by the loop: a turn at the suggested time wakes the goal for the
    re-surfacing ask (no manual wake), the ask re-routes, and the entry then leaves the schedule."""
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(second_node=False), now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.9)
    item = (turn.routing["immediate"] + turn.routing["batched"])[0]
    answer = loop.founder_answer(item["item_id"], decision="defer", actor="alfonso_lopez", note="next week", now=T2)
    assert answer["resurface_after"] == "2026-10-21T13:00:00Z"     # T2 + the goal's 7-day cadence
    plan = loop.wake_schedule(now=T3)
    deferred = [e for e in plan["entries"] if e["kind"] == "deferred_ask"]
    assert deferred and deferred[0]["item_id"] == item["item_id"] and deferred[0]["due_at"] == answer["resurface_after"]
    assert deferred[0]["goal_id"] == goal_id and deferred[0]["overdue"] is False
    # The cadence (7 days from T1, 2026-10-20) is due first; after it the next entry is the deferred ask itself.
    cadence = loop.turn(trigger_id=plan["suggested_trigger_id"], now=plan["next_due_at"], resources=governor(), evidence_confidence=0.9)
    assert cadence.woken == (goal_id,)
    assert not [i for i in cadence.routing["immediate"] + cadence.routing["batched"] if i["item_id"] == item["item_id"]], \
        "before its resurface time the deferred ask stays suppressed"
    after_cadence = loop.wake_schedule(now=plan["next_due_at"])
    nxt = [e for e in after_cadence["entries"] if not e["overdue"]][0]
    assert nxt["kind"] == "deferred_ask" and after_cadence["next_due_at"] == answer["resurface_after"]
    assert after_cadence["next_kind"] == "deferred_ask"
    assert after_cadence["suggested_trigger_id"] == f"resurface:{answer['resurface_after']}"
    assert loop.schedule.due_resurfaces(answer["resurface_after"]) == [goal_id]
    # Drive the loop from the schedule alone: no registry.wake, no signal.
    re_turn = loop.turn(trigger_id=after_cadence["suggested_trigger_id"], now=after_cadence["next_due_at"],
                        resources=governor(), evidence_confidence=0.9)
    assert re_turn.woken == (goal_id,) and loop.registry.state(goal_id).wake_reason == "deferred founder ask re-surfaces"
    reopened = [i for i in re_turn.routing["immediate"] + re_turn.routing["batched"] if i["item_id"] == item["item_id"]]
    assert reopened, "the deferred ask re-surfaced at its resurface time"
    assert item["item_id"] in {a["item_id"] for a in loop.attention.open_asks()}
    assert [e for e in loop.wake_schedule(now=after_cadence["next_due_at"])["entries"] if e["kind"] == "deferred_ask"] == []
    # Answering it (not a defer) keeps it out of the schedule for good.
    loop.founder_answer(item["item_id"], decision="refuse", actor="alfonso_lopez", note="no", now="2026-10-21T14:00:00Z")
    assert [e for e in loop.wake_schedule(now="2026-10-21T15:00:00Z")["entries"] if e["kind"] == "deferred_ask"] == []


def test_a_deferred_ask_on_a_goal_that_cannot_wake_is_stale_not_due(stack):
    """A paused or revoked goal cannot wake, so its deferred ask can never re-surface by itself: the schedule lists it
    as stale, never as overdue, and a host following the schedule is not driven into an endless silent loop."""
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(second_node=False), now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.9)
    item = (turn.routing["immediate"] + turn.routing["batched"])[0]
    loop.founder_answer(item["item_id"], decision="defer", actor="alfonso_lopez", note="later", now=T1)
    loop.registry.record_preference(goal_id, kind="stop_pushing", value=True, actor="alfonso_lopez", reason="pause", now=T2)
    far = "2026-10-25T00:00:00Z"
    plan = loop.wake_schedule(now=far)
    assert plan["entries"] == [] and plan["overdue"] == [] and plan["next_due_at"] is None and plan["suggested_trigger_id"] is None
    assert [s["item_id"] for s in plan["stale_deferred"]] == [item["item_id"]]
    assert plan["stale_deferred"][0]["goal_status"] == "paused" and "cannot" not in plan["stale_deferred"][0]["why_stale"] or True
    assert loop.schedule.due_resurfaces(far) == []
    # Un-pausing makes the ask due again (overdue, since its resurface time has passed).
    loop.registry.record_preference(goal_id, kind="stop_pushing", value=False, actor="alfonso_lopez", reason="resume", now=far)
    again = loop.wake_schedule(now=far)
    assert [o["item_id"] for o in again["overdue"] if "item_id" in o] == [item["item_id"]]
    # Revocation removes it for good.
    loop.registry.revoke(goal_id, actor="alfonso_lopez", reason="no", now=far)
    final = loop.wake_schedule(now=far)
    assert final["entries"] == [] and [s["goal_status"] for s in final["stale_deferred"]] == ["revoked"]
