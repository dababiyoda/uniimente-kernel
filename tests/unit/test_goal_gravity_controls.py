"""Founder controls, attention effects, measurement and one-ledger agreement (directive sections 3, 9, 13, 20, 30)."""
from __future__ import annotations

from capabilities.genome import GenomeRegistry
from egregore.cognition_seam import GoalProposer
from egregore.contracts import CandidateProposal
from egregore.gravity import GoalGravityLoop
from egregore.relevance import evaluate_relevance
from egregore.runtime import StandingCognitionRuntime
from tests.unit.test_goal_gravity import (  # noqa: F401  (stack is a fixture)
    T0, T1, T2, T3, brief_move, governor, grant_for, make_loop, obs, outreach_move, robotics_goal, signal, stack,
)
from tests.unit.test_goal_gravity_seams import approving, hardware_signal


def test_a_declared_model_tactic_is_bound_by_never_use_tactic(stack):
    compiled, passports, ledger, gate, actor = stack

    def strategist(signals, context):
        if not context.get("goal_id"):
            return []
        return [CandidateProposal.build(
            proposed_by="strategist", objective="cold email the buyers", action_class="outreach.message",
            requested_capability="outreach.contact", target="mailto:buyers", consequence_class="external_contact",
            payload={"template": "cold", "tactic": "cold_outreach"}, evidence_refs=[r for s in signals for r in s.evidence_refs],
            confidence=0.6, estimated_cost_usd=0.0, expected_outcome="replies", source_signal_ids=[s.signal_id for s in signals])]

    runtime = StandingCognitionRuntime(ledger=ledger, proposers={"goal-gravity": GoalProposer(), "strategist": strategist},
                                       evaluators={"guardian": approving("guardian"), "treasury": approving("treasury")})
    loop = GoalGravityLoop(ledger=ledger, compiled=compiled, passports=passports, actor=actor.passport_id,
                           legal_principal="alfonso_lopez", genomes=GenomeRegistry(), cognition=runtime)
    goal_id = loop.registry.authorize(robotics_goal(second_node=False), now=T0)
    loop.registry.record_preference(goal_id, kind="never_use_tactic", value="cold_outreach", actor="alfonso_lopez",
                                    reason="never cold outreach", now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.9)
    model = [d for d in turn.processed[0]["decisions"] if d["intervention_id"].startswith("strategist:")]
    assert model and model[0]["decision"] == "ABSTAIN" and "cold_outreach" in model[0]["reasons"][0]


def test_untrusted_sources_are_not_counted_as_modalities(stack):
    loop = make_loop(stack)
    loop.registry.authorize(robotics_goal(), now=T0)
    from egregore.contracts import SignalEnvelope
    shady = SignalEnvelope.build(source="feed://anonymous", source_event_id="x", observed_at=T1,
                                 payload={"observations": [obs("rumor", "level", 3)]}, evidence_refs=("r",), trust_level="untrusted")
    loop.turn(trigger_id="t1", now=T1, signals=[shady, hardware_signal()], resources=governor(), evidence_confidence=0.9)
    surface = loop.world.experience_surface()
    assert surface["untrusted_sources"] == 1
    assert "feed://anonymous" not in {b.source for b in loop.world.beliefs().values() if b.trust_level != "untrusted"}


def test_wake_precision_and_recall_are_measured_against_labels(stack):
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(), now=T0)
    hit = hardware_signal("hit")
    near_miss = signal("near", domain="hardware", observations=[obs("actuator", "cost_usd", 900)])   # domain only: 0.5 < 1.0
    noise = signal("noise", domain="weather", observations=[obs("sky", "temp", 3)])
    labeled = [(hit, [goal_id]), (near_miss, [goal_id]), (noise, [])]
    m = evaluate_relevance(loop.router, labeled, label_source="synthetic")
    assert m["wake_precision"] == 1.0 and m["wake_recall"] == 0.5 and m["ground_truth"] is False
    flipped = evaluate_relevance(loop.router, [(hit, [goal_id]), (near_miss, []), (noise, [])], label_source="synthetic")
    assert flipped["wake_recall"] == 1.0 and flipped["corpus_hash"] != m["corpus_hash"]
    assert loop.world.experiences() == []   # evaluation integrates nothing


def test_pause_and_lower_priority_answers_take_effect(stack):
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(second_node=False), now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.9)
    asks = turn.routing["immediate"] + turn.routing["batched"]
    lowered = loop.founder_answer(asks[0]["item_id"], decision="lower_priority", actor="alfonso_lopez", note="later", now=T1)
    assert loop.registry.effective_priority(goal_id) == 3 and "priority lowered to 3" in lowered["effect"]
    paused = loop.founder_answer(asks[1]["item_id"], decision="pause", actor="alfonso_lopez", note="not now", now=T1)
    assert loop.registry.state(goal_id).status == "paused" and "paused" in paused["effect"]
    later = loop.turn(trigger_id="t2", now=T2, signals=[hardware_signal("e2", observed_at=T2)], resources=governor())
    assert later.woken == ()


def test_status_answers_what_controls_the_gate_what_changed_threats_and_assets(stack):
    compiled, passports, ledger, gate, actor = stack
    loop = make_loop(stack, genomes=GenomeRegistry(ledger))
    goal_id = loop.registry.authorize(robotics_goal(second_node=False), now=T0)
    loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.9)
    loop.registry.wake(goal_id, reason="test", now=T2)
    loop.turn(trigger_id="t2", now=T2, resources=governor(), gate=gate, executor=lambda p: {
        "observed_outcome": p.expected_outcome, "result_class": "positive"}, evidence_confidence=0.9,
        grants={"research.brief": grant_for(loop, gate, loop.registry.get(goal_id), brief_move())},
        signals=[signal("e2", tags=["robotics"], domain="hardware", observed_at=T2,
                        observations=[obs("robotics", "opportunity_score", 0.4)])])
    status = loop.status(goal_id, now=T2)
    controller = status["gate_controller"]
    assert controller["metric"] == "robotics.opportunity_score" and controller["evidence_needed"] == "any trusted observation"
    changed = status["changed_since_last_assessment"]
    assert changed["changes"]["robotics.opportunity_score"] == {"before": None, "after": 0.4}
    assert isinstance(status["threats"], list)
    assert status["retained_assets"] and status["retained_assets"][0]["kind"] == "evidence"


def test_a_muted_domain_is_not_monitored_at_all(stack):
    loop = make_loop(stack)
    goal_id = loop.registry.authorize(robotics_goal(), now=T0)
    loop.registry.record_preference(goal_id, kind="do_not_monitor", value="hardware", actor="alfonso_lopez",
                                    reason="privacy", now=T0)
    loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.9)
    assert loop.world.belief("actuator", "cost_usd") is None
    [record] = [r.payload for r in loop.ledger.by_type(loop.MUTED_RECORD)]
    assert record["domain"] == "hardware" and "observations" not in str(record) and "420" not in str(record)
    # A goal that does monitor the domain still senses it.
    other = make_loop(stack, ledger=type(loop.ledger)(stack[0].constitution_hash))
    other.registry.authorize(robotics_goal(), now=T0)
    other.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.9)
    assert other.world.belief("actuator", "cost_usd").value == 420


def test_founder_burden_is_measured(stack):
    loop = make_loop(stack)
    loop.registry.authorize(robotics_goal(second_node=False), now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.9)
    item = (turn.routing["immediate"] + turn.routing["batched"])[0]
    loop.founder_answer(item["item_id"], decision="defer", actor="alfonso_lopez", note="later", now=T2)
    burden = loop.measures(now=T2)["founder_burden"]
    assert burden["answers"] == 1 and burden["mean_answer_latency_seconds"] == 86400.0
    assert burden["immediate_asks"] + burden["batched_asks"] == len(turn.routing["immediate"] + turn.routing["batched"])


def test_two_loops_over_one_ledger_agree_without_rebuilding(stack):
    loop_a = make_loop(stack)
    loop_b = make_loop(stack)
    goal_id = loop_a.registry.authorize(robotics_goal(second_node=False), now=T0)
    turn = loop_a.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), evidence_confidence=0.9)
    assert goal_id in loop_b.registry.goals()
    assert loop_b.world.belief("actuator", "cost_usd").value == 420
    assert {a["item_id"] for a in loop_b.attention.open_asks()} == {a["item_id"] for a in turn.routing["immediate"] + turn.routing["batched"]}
    assert loop_b.status(goal_id, now=T1)["active_node"] == "N1"
    # Loop B answers; loop A sees the answer and the refusal it recorded.
    ask = next(a for a in loop_b.attention.open_asks() if a["route_hash"] == outreach_move().route_hash)
    loop_b.founder_answer(ask["item_id"], decision="refuse", actor="alfonso_lopez", note="no", now=T2)
    assert loop_a.registry.is_route_refused(goal_id, outreach_move().route_hash)
    assert ask["item_id"] not in {a["item_id"] for a in loop_a.attention.open_asks()}
    belief = loop_b.world.belief("actuator", "cost_usd")
    assert belief.record_hash and loop_b.ledger.find(belief.record_hash) is not None
