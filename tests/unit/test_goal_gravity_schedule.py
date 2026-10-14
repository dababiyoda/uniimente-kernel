"""Wake schedule: the host-trigger view is computed from durable state, is read-only, and runs nothing."""
from __future__ import annotations

from egregore.schedule import WakeSchedule
from tests.unit.test_goal_gravity import (  # noqa: F401  (stack is a fixture)
    T0, T1, T2, governor, make_loop, robotics_goal, stack,
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
    assert plan["overdue"] == [] and plan["next_due_at"] == "2026-10-20T12:00:00Z"
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


def test_paused_revoked_completed_and_awake_goals_are_not_scheduled(stack):
    loop = make_loop(stack)
    paused = loop.registry.authorize(simple_goal(tag="p"), now=T0)
    revoked = loop.registry.authorize(simple_goal(tag="r"), now=T0)
    kept = loop.registry.authorize(simple_goal(tag="k"), now=T0)
    loop.registry.record_preference(paused, kind="stop_pushing", value=True, actor="alfonso_lopez", reason="later", now=T0)
    loop.registry.revoke(revoked, actor="alfonso_lopez", reason="no", now=T0)
    plan = loop.wake_schedule(now=T1)
    assert [e["goal_id"] for e in plan["entries"]] == [kept]
    loop.registry.wake(kept, reason="test", now=T1)
    assert loop.wake_schedule(now=T1)["entries"] == [] and loop.wake_schedule(now=T1)["next_due_at"] is None


def test_a_deferred_ask_is_scheduled_to_resurface(stack):
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(second_node=False), now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.9)
    item = (turn.routing["immediate"] + turn.routing["batched"])[0]
    answer = loop.founder_answer(item["item_id"], decision="defer", actor="alfonso_lopez", note="next week", now=T1)
    plan = loop.wake_schedule(now=T2)
    deferred = [e for e in plan["entries"] if e["kind"] == "deferred_ask"]
    assert deferred and deferred[0]["item_id"] == item["item_id"] and deferred[0]["due_at"] == answer["resurface_after"]
    assert deferred[0]["goal_id"] == goal_id and deferred[0]["overdue"] is False
    # Answering it again later (not a defer) removes it from the schedule.
    loop.registry.wake(goal_id, reason="test", now=T2)
    re_turn = loop.turn(trigger_id="t2", now="2026-10-21T13:00:00Z", signals=[hardware_signal("e9")], resources=governor(),
                        evidence_confidence=0.9)
    reopened = [i for i in re_turn.routing["immediate"] + re_turn.routing["batched"] if i["item_id"] == item["item_id"]]
    assert reopened, "the deferred ask re-surfaced after its cadence"
    loop.founder_answer(item["item_id"], decision="refuse", actor="alfonso_lopez", note="no", now="2026-10-21T14:00:00Z")
    assert [e for e in loop.wake_schedule(now="2026-10-21T15:00:00Z")["entries"] if e["kind"] == "deferred_ask"] == []
