"""Directive section 8: the institution's own computational modalities as measurable signals."""
from __future__ import annotations

from egregore.goals import GoalSpec, PlanNode, WakeCondition
from egregore.sensorium import SOURCE, SUBJECT
from tests.unit.test_goal_gravity import (  # noqa: F401  (stack is a fixture)
    AUTH_REF, T0, T1, T2, T3, brief_move, governor, make_loop, obs, signal, stack,
)


def hygiene_goal():
    return GoalSpec.build(
        founder_intent="Keep the institution's evidence clean.", desired_state="no unresolved evidence conflicts",
        priority=2, authority={"authorized_by": "alfonso_lopez", "authorization_ref": AUTH_REF,
                               "legal_principal": "alfonso_lopez", "max_consequence_class": "internal_write"},
        time_horizon="continuous",
        plan=[PlanNode.build(node_id="H1", outcome="conflicts resolved", gate="no contradicted beliefs",
                             sbm="institution.evidence_conflicts", sbm_direction="lte", sbm_target=0,
                             interventions=(brief_move(intervention_id="audit-conflicts", payload={"topic": "conflict audit"}),))],
        relevant_entities=("institution",),
        wake_conditions=(WakeCondition.build(kind="metric", match="institution.evidence_conflicts", direction="gte",
                                             threshold=1, weight=1.0),))


def test_an_interoceptive_metric_wakes_a_goal_and_sets_its_bottleneck(stack):
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(hygiene_goal(), now=T0)
    quiet = loop.turn(trigger_id="t0", now=T1, resources=governor(), evidence_confidence=0.9)
    assert quiet.woken == () and len(quiet.derived_signal_ids) == 1
    disagree = [signal("a", source="feed://vendor-a", observations=[obs("actuator", "cost_usd", 420)]),
                signal("b", source="feed://vendor-b", observations=[obs("actuator", "cost_usd", 900)])]
    turn = loop.turn(trigger_id="t1", now=T2, signals=disagree, resources=governor(), evidence_confidence=0.9)
    assert loop.world.belief("actuator", "cost_usd").contradicted
    assert turn.woken == (goal_id,) and loop.registry.state(goal_id).wake_reason.startswith("relevant evidence")
    summary = turn.processed[0]
    assert summary["sbm"]["name"] == "institution.evidence_conflicts" and summary["sbm"]["current"] == 1.0
    assert summary["sbm"]["satisfied"] is False


def test_readings_are_emitted_only_on_change_and_anchored_to_the_ledger(stack):
    loop = make_loop(stack)
    loop.registry.authorize(hygiene_goal(), now=T0)
    first = loop.turn(trigger_id="t0", now=T1, resources=governor())
    second = loop.turn(trigger_id="t1", now=T2, resources=governor())
    assert len(first.derived_signal_ids) == 1 and second.derived_signal_ids == ()
    event = next(e for e in loop.world.experiences() if e.source == SOURCE)
    readings = {o["attribute"]: o["value"] for o in event.observations if o["subject"] == SUBJECT}
    assert readings["ledger_integrity"] == 1.0 and readings["evidence_conflicts"] == 0.0
    assert set(readings) == set(loop.sensorium.derived)
    head = [r for o in event.observations for r in o["evidence_refs"]][0]
    assert loop.ledger.find(head) is not None   # the reading cites the exact ledger state it was computed at
    belief = loop.world.belief(SUBJECT, "ledger_integrity")
    assert belief.trust_level == "attributed" and belief.confidence == 1.0


def test_external_modalities_are_declared_unobserved_with_their_missing_sensor(stack):
    loop = make_loop(stack)
    listing = {m["name"]: m for m in loop.sensorium.modalities()}
    assert listing["liquidity_stress"]["observed"] is False and "treasury" in listing["liquidity_stress"]["requires"]
    assert listing["institutional_trust"]["observed"] is False and "DALEOBANKS" in listing["institutional_trust"]["requires"]
    assert all(listing[name]["observed"] for name in loop.sensorium.derived)
    assert loop.sensorium.execution_authority == "none"


def test_interoception_can_be_switched_off(stack):
    compiled, passports, ledger, gate, actor = stack
    from capabilities.genome import GenomeRegistry
    from egregore.gravity import GoalGravityLoop
    loop = GoalGravityLoop(ledger=ledger, compiled=compiled, passports=passports, actor=actor.passport_id,
                           legal_principal="alfonso_lopez", genomes=GenomeRegistry(), interoception=False)
    turn = loop.turn(trigger_id="t0", now=T1, resources=governor())
    assert loop.sensorium is None and turn.derived_signal_ids == ()
