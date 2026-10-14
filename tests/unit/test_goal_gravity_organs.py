"""Organ outputs become typed experience through canonical contracts (directive section 8, NOTHING IS DISCONNECTED).

Fixtures are the same synthetic wire payloads the phase-zero integration test uses; nothing here
reaches a live organ.
"""
from __future__ import annotations

import pytest

from adapters import daleobanks_opportunity as dop
from adapters import wealthmachine_assessment as wva
from egregore.contracts import ContractError
from egregore.goals import GoalSpec, PlanNode, WakeCondition
from egregore.organ_signals import ASSUMPTIONS, INFORMATION_ADDED, INFORMATION_LOST, assessment_signal, packet_signal, unresolved_signal
from tests.integration.test_phase_zero_connection import wire_assessment, wire_packet
from tests.unit.test_goal_gravity import AUTH_REF, T0, T1, T2, brief_move, governor, make_loop, stack  # noqa: F401

KERNEL = "spiffe://uniimente.internal/organ/constitutional-controller"
TRANSPORT = {"identity": "daleobanks", "signed": "true", "identity_isolated": "false", "body_digest": "sha256:" + "a" * 64}


def canonical_packet():
    result = dop.adapt(wire_packet(), transport_identity="daleobanks")
    assert result.unresolved == ["governing_bottleneck"]
    return dop.resolve(result, {"governing_bottleneck": "no automated input generator"}, resolved_by=KERNEL)


def score_goal(problem_class, packet_id):
    return GoalSpec.build(
        founder_intent=f"decide the parser venture ({problem_class})", desired_state="a decided parser venture", priority=2,
        authority={"authorized_by": "alfonso_lopez", "authorization_ref": AUTH_REF, "legal_principal": "alfonso_lopez",
                   "max_consequence_class": "internal_write"}, time_horizon="weeks",
        plan=[PlanNode.build(node_id="V1", outcome="score known", gate=f"{problem_class} gate",
                             sbm=f"opportunity:{packet_id}.wmi.opportunity_score", sbm_direction="gte", sbm_target=0.5,
                             interventions=(brief_move(payload={"topic": problem_class}),), problem_class=problem_class),
              PlanNode.build(node_id="V2", outcome="next", gate="next", sbm="parser.next", sbm_direction="eq", sbm_target=True,
                             interventions=(brief_move(intervention_id="n", payload={"topic": "next"}),))],
        wake_conditions=(WakeCondition.build(kind="domain", match="venture"),))


def test_mapping_is_declared_and_partial_translations_are_refused():
    assert INFORMATION_LOST and INFORMATION_ADDED and ASSUMPTIONS
    partial = dop.adapt(wire_packet(), transport_identity="daleobanks")
    with pytest.raises(ContractError):
        packet_signal(partial)
    gap = unresolved_signal(partial)
    obs = {o["attribute"]: o for o in gap.payload["observations"]}
    assert obs["unresolved.governing_bottleneck"]["value"] is True and obs["unresolved_count"]["value"] == 1
    with pytest.raises(ContractError):
        packet_signal({"packet_id": "not canonical"})


def test_a_canonical_packet_integrates_with_honest_trust_and_content_identity(stack):
    loop = make_loop(stack)
    packet = canonical_packet()
    untrusted = packet_signal(packet)
    attributed = packet_signal(packet, transport=TRANSPORT)
    assert untrusted.trust_level == "untrusted" and attributed.trust_level == "attributed"
    with pytest.raises(ContractError):
        packet_signal(packet, transport={"identity": "daleobanks"})   # not a verify_headers result
    loop.turn(trigger_id="t1", now=T1, signals=[attributed], resources=governor())
    subject = f"opportunity:{packet['packet_id']}"
    assert loop.world.belief(subject, "governing_bottleneck").value == "no automated input generator"
    assert loop.world.belief(subject, "affected_actor_count").establishes == "fact_within_model"
    assert loop.world.belief(subject, "pain_owner").establishes is None   # organ synthesis is untyped
    assert packet_signal(packet, transport=TRANSPORT).signal_id == attributed.signal_id   # redelivery is the same signal
    changed = {**packet, "governing_bottleneck": "no generator and no budget"}
    assert packet_signal(changed, transport=TRANSPORT).signal_id != attributed.signal_id   # a correction is a new signal


def test_a_wmi_score_can_clear_a_forecast_gate_but_never_a_demand_gate(stack):
    compiled, passports, ledger, gate, actor = stack
    from capabilities.genome import GenomeRegistry
    from capabilities.router import CapabilityRouter
    from egregore.gravity import GoalGravityLoop
    genomes = GenomeRegistry()
    loop = GoalGravityLoop(ledger=ledger, compiled=compiled, passports=passports, actor=actor.passport_id,
                           legal_principal="alfonso_lopez", genomes=genomes,
                           capability_router=CapabilityRouter(genomes, ledger=ledger))
    assessment = wva.adapt({**wire_assessment(), "opportunity_score": 0.8}, transport_identity="wealthmachine")
    packet_id = assessment["packet_id"]
    forecast = loop.registry.authorize(score_goal("forecast", packet_id), now=T0)
    demand = loop.registry.authorize(score_goal("market_demand", packet_id), now=T0)
    signal = assessment_signal(assessment, transport={**TRANSPORT, "identity": "wealthmachine"})
    turn = loop.turn(trigger_id="t1", now=T1, signals=[signal], resources=governor(), evidence_confidence=0.9)
    by_goal = {p["goal_id"]: p for p in turn.processed}
    assert by_goal[forecast]["active_node_id"] == "V2"   # a hypothesis-grade score answers a forecast
    assert by_goal[demand]["active_node_id"] == "V1"     # but never proves demand
    assert any("market_demand gate needs external_fact" in b for b in loop.registry.state(demand).blockers)
    belief = loop.world.belief(f"opportunity:{packet_id}", "wmi.recommended_verdict")
    assert belief.value == "go" and belief.establishes == "hypothesis"
    case = loop.world.belief(f"opportunity:{packet_id}", "wmi.case.bear")
    assert case.establishes == "objection"
    assert loop.world.belief(f"opportunity:{packet_id}", "wmi.requires_human_approval").value is True
