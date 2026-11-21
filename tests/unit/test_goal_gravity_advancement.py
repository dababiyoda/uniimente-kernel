"""Directive section 5: authorized trajectory versus observed trajectory, friction, mature report.

Deterministic and model-free. A report is information routed through the attention router;
it never acts on the founder, never escalates urgency, and is always cheap to decline.
"""
from __future__ import annotations

from egregore.goals import GoalSpec, PlanNode
from tests.unit.test_goal_gravity import (  # noqa: F401  (stack is a fixture)
    T0, brief_move, governor, make_loop, obs, outreach_move, robotics_goal, signal, stack,
)


def hw(event_id, at):
    return signal(event_id, domain="hardware", tags=["robotics"], observations=[obs("actuator", "cost_usd", 420)], observed_at=at)


DAYS = ["2026-10-13T13:00:00Z", "2026-10-14T13:00:00Z", "2026-10-15T13:00:00Z", "2026-10-16T13:00:00Z"]


def run_turns(loop, n, *, start=0):
    turns = []
    for k in range(start, start + n):
        at = DAYS[k] if k < len(DAYS) else f"2026-11-{k:02d}T13:00:00Z"
        turns.append(loop.turn(trigger_id=f"t{k}", now=at, signals=[hw(f"e{k}", at)], resources=governor(), evidence_confidence=0.9))
    return turns


def reports(turn):
    return [i for i in turn.routing["immediate"] + turn.routing["batched"] if i["category"] == "advancement"]


def test_stall_produces_one_mature_report_naming_the_main_friction(stack):
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(second_node=False), now=T0)
    t1, t2, t3 = run_turns(loop, 3)
    assert reports(t1) == reports(t2) == []
    [report] = reports(t3)
    text = report["question"]
    assert "remains one of your highest-priority goals" in text and "stalled for 3 review(s)" in text
    assert "The main friction appears to be: prepared work is waiting on your decision" in text
    assert "decision(s) still require you" in text and "Here is the evidence" in text
    assert report["kind"] == "decision" and report["urgency"] == "normal"
    labels = {o["label"]: o["cost"] for o in report["options"]}
    assert labels["pause this goal"] == "none" and labels["lower this goal's priority"] == "none"
    assert all(r.startswith("sha256:") for r in report["evidence_refs"])
    record = loop.ledger.by_type(loop.advancement.REPORT_RECORD)[-1].payload
    assert record["main_friction"] == "founder_decision" and record["stall_turns"] == 3
    assert record["disposition"].startswith("reported_to_attention_router")
    # Within the review cadence the same stall episode is not reported again.
    [t4] = run_turns(loop, 1, start=3)
    assert reports(t4) == []
    assert loop.status(goal_id, now=DAYS[3])["trajectory"]["reviews_without_progress"] == 4


def test_intensity_and_pause_are_respected(stack):
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(second_node=False), now=T0)
    loop.registry.record_preference(goal_id, kind="set_intensity", value="minimal", actor="alfonso_lopez", reason="quiet", now=T0)
    assert all(reports(t) == [] for t in run_turns(loop, 3))
    assert loop.ledger.by_type(loop.advancement.REPORT_RECORD) == []
    other = make_loop(stack, ledger=type(loop.ledger)(stack[0].constitution_hash))
    gid = other.registry.authorize(robotics_goal(second_node=False), now=T0)
    other.registry.record_preference(gid, kind="set_intensity", value="active", actor="alfonso_lopez", reason="push", now=T0)
    t1, t2 = run_turns(other, 2)
    assert reports(t1) == [] and len(reports(t2)) == 1
    paused = make_loop(stack, ledger=type(loop.ledger)(stack[0].constitution_hash))
    pid = paused.registry.authorize(robotics_goal(second_node=False), now=T0)
    run_turns(paused, 2)
    paused.registry.record_preference(pid, kind="stop_pushing", value=True, actor="alfonso_lopez", reason="not now", now=DAYS[1])
    [t3] = run_turns(paused, 1, start=2)
    assert t3.woken == () and paused.ledger.by_type(paused.advancement.REPORT_RECORD) == []


def test_missed_target_date_is_reported_on_the_first_review(stack):
    loop = make_loop(stack)
    base = robotics_goal(second_node=False)
    node = base.plan[0]
    late_node = PlanNode.build(node_id=node.node_id, outcome=node.outcome, gate=node.gate, sbm=node.sbm,
                               sbm_direction=node.sbm_direction, sbm_target=node.sbm_target,
                               exit_evidence=node.exit_evidence, interventions=node.interventions,
                               target_by="2026-10-01T00:00:00Z")
    body = {**base.to_dict(), "plan": [late_node.to_dict()]}
    body.pop("goal_id")
    spec = GoalSpec.from_dict(body)
    assert spec.goal_id != base.goal_id and "target_by" not in base.plan[0].to_dict()
    goal_id = loop.registry.authorize(spec, now=T0)
    [t1] = run_turns(loop, 1)
    [report] = reports(t1)
    assert "behind the authorized trajectory" in report["question"] and "N1 was due 2026-10-01T00:00:00Z" in report["question"]
    late = loop.status(goal_id, now=DAYS[0])["trajectory"]["behind_target"]
    assert late[0]["node_id"] == "N1" and late[0]["days_late"] > 12


def test_advancing_after_a_report_records_the_resolution_and_its_latency(stack):
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(), now=T0)
    run_turns(loop, 3)
    assert loop.ledger.by_type(loop.advancement.REPORT_RECORD)
    moved = loop.turn(trigger_id="t-advance", now=DAYS[3], resources=governor(), evidence_confidence=0.9,
                      signals=[signal("adv", domain="hardware", tags=["robotics"], observed_at=DAYS[3],
                                      observations=[obs("robotics", "opportunity_score", 0.9, confidence=0.95)])])
    assert moved.processed[0]["active_node_id"] == "N2"
    [resolution] = [r.payload for r in loop.ledger.by_type(loop.advancement.RESOLUTION_RECORD)]
    assert resolution["main_friction"] == "founder_decision" and resolution["latency_seconds"] == 86400.0
    assert loop.status(goal_id, now=DAYS[3])["trajectory"]["reviews_without_progress"] == 1
