"""Egregore Goal Gravity hosted on a GREG body (ADR-GOAL-GRAVITY-002): the egregore-side grafts.

Deterministic and model-free. These tests pin what changed in egregore for the GREG binding and that the
standalone lineage keeps its historical behaviour: superseded goals never wake, one goal's wake refusal
never faults the turn for the others, a body-hosted loop refuses any gate/executor/grant, its attention
store writes no founder ask or answer and refuses unsigned answers, a goal with no world evidence has
confidence 0 there, and stray goal records are quarantined on a body ledger while elsewhere they still
fail closed.
"""
from __future__ import annotations

import os

import pytest

from compiler.ucl_compiler import compile_constitution
from egregore.attention import ASK_RECORD, ANSWER_RECORD, LedgerAttentionStore, MemoryAttentionStore
from egregore.contracts import ContractError, IntegrityConflict, SignalEnvelope
from egregore.goals import GoalError, GoalRegistry, GoalSpec, InterventionSpec, PlanNode, WakeCondition, hosted_on_body
from egregore.gravity import GoalGravityLoop
from egregore.resources import ResourceGovernor
from identity.machine_passport import PassportRegistry
from provenance.ledger import EvidenceLedger

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
T0, T1, T2 = "2026-10-13T12:00:00Z", "2026-10-13T13:00:00Z", "2026-10-13T14:00:00Z"


@pytest.fixture
def parts():
    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    actor = passports.issue(kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
                            legal_principal="alfonso_lopez", declared_capabilities=["research.brief"],
                            budget_ceiling_usd=1.0, consequence_class="internal_write")
    return compiled, passports, actor


def loop_on(parts, ledger=None, **kw):
    compiled, passports, actor = parts
    ledger = ledger if ledger is not None else EvidenceLedger(compiled.constitution_hash)
    return GoalGravityLoop(ledger=ledger, compiled=compiled, passports=passports, actor=actor.passport_id,
                           legal_principal="alfonso_lopez", **kw)


def mark_body(ledger):
    """What makes a ledger a GREG body ledger: a founder enrollment event."""
    ledger.append("event", {"type": "greg.founder.enrolled", "event_id": "enrolled-1",
                            "payload": {"key_id": "ed25519:" + "a" * 32}})


def goal(intent="probe goal", *, tag="probe", supersedes=None):
    move = InterventionSpec.build(intervention_id="brief", description="compile a brief",
                                  action_class="research.compile", requested_capability="research.brief",
                                  consequence_class="internal_write", target="sandbox:briefs",
                                  expected_outcome="brief compiled", payload={"topic": intent})
    kw = {"supersedes": supersedes} if supersedes else {}
    return GoalSpec.build(
        founder_intent=intent, desired_state=f"{intent} satisfied", priority=3,
        authority={"authorized_by": "alfonso_lopez", "authorization_ref": "sha256:" + "c" * 64,
                   "legal_principal": "alfonso_lopez", "max_consequence_class": "internal_write"},
        time_horizon="days",
        plan=[PlanNode.build(node_id="n1", outcome="o", gate="g", sbm="probe.score", sbm_direction="gte",
                             sbm_target=1.0, interventions=(move,))],
        wake_conditions=(WakeCondition.build(kind="tag", match=tag),), **kw)


def signal(event_id, tag="probe", value=0.2):
    return SignalEnvelope.build(source="feed://probe", source_event_id=event_id, observed_at=T0,
                                payload={"tags": [tag], "observations": [{"subject": "probe", "attribute": "score",
                                                                          "value": value, "confidence": 0.9}]},
                                evidence_refs=(f"source:{event_id}",))


def governor():
    return ResourceGovernor(max_model_calls=2, max_estimated_cost_usd=0.01)


def test_superseded_goal_never_wakes_and_its_replacement_does(parts):
    loop = loop_on(parts)
    old = loop.registry.authorize(goal("first wording"), now=T0)
    new = loop.registry.supersede(old, goal("second wording", supersedes=old), actor="alfonso_lopez",
                                  reason="changed", now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[signal("e1")], resources=governor(), evidence_confidence=0.9)
    assert new in turn.woken and old not in turn.woken and turn.wake_refused == ()
    assert loop.registry.state(old).status == "superseded"
    verdicts = loop.router.route(signal("e2"), observations=loop.world.observations_from_signal(signal("e2")))
    assert verdicts[old].wake is False and "superseded" in verdicts[old].reason


def test_one_goals_wake_refusal_never_faults_the_turn_for_the_others(parts, monkeypatch):
    loop = loop_on(parts)
    a = loop.registry.authorize(goal("goal a"), now=T0)
    b = loop.registry.authorize(goal("goal b"), now=T0)
    real = loop.registry.wake

    def wake(goal_id, **kw):
        if goal_id == a:
            raise GoalError(f"goal {goal_id} cannot wake from status test-refusal")
        return real(goal_id, **kw)
    monkeypatch.setattr(loop.registry, "wake", wake)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[signal("e1")], resources=governor(), evidence_confidence=0.9)
    assert turn.woken == (b,)
    assert [w["goal_id"] for w in turn.wake_refused] == [a]
    refused = loop.ledger.by_type(GoalGravityLoop.WAKE_REFUSED_RECORD)
    assert len(refused) == 1 and refused[0].payload["goal_id"] == a
    assert refused[0].payload["disposition"] == "not_woken_retained"
    assert turn.to_dict()["wake_refused"][0]["goal_id"] == a


def test_turn_records_keep_their_historical_shape_when_nothing_was_refused(parts):
    loop = loop_on(parts)
    loop.registry.authorize(goal(), now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[signal("e1")], resources=governor(), evidence_confidence=0.9)
    assert "wake_refused" not in turn.to_dict()


def test_a_body_hosted_loop_refuses_any_gate_executor_or_grant(parts):
    compiled = parts[0]
    ledger = EvidenceLedger(compiled.constitution_hash)
    mark_body(ledger)
    loop = loop_on(parts, ledger)                  # no flag: the ledger decides
    assert loop.body_mode is True and hosted_on_body(ledger)
    loop.registry.authorize(goal(), now=T0)
    for kw in ({"gate": object()}, {"executor": lambda c: {}}, {"grants": {"x": {"grant_id": "g"}}}):
        with pytest.raises(ContractError, match="takes no gate, executor or grants"):
            loop.turn(trigger_id="t1", now=T1, signals=[signal("e1")], resources=governor(), **kw)
    flagged = loop_on(parts, body_mode=True)        # the constructor mode, on any ledger
    with pytest.raises(ContractError):
        flagged.turn(trigger_id="t1", now=T1, resources=governor(), grants={"x": {"grant_id": "g"}})


def test_a_standalone_loop_keeps_its_gate_path(parts):
    loop = loop_on(parts)
    assert loop.body_mode is False and isinstance(loop.attention.store, LedgerAttentionStore)


def test_a_founder_enrolled_after_construction_switches_the_loop_to_body_mode(parts):
    loop = loop_on(parts)
    assert loop.body_mode is False
    mark_body(loop.ledger)
    assert loop.body_mode is True
    assert isinstance(loop.attention.store, MemoryAttentionStore) and loop.registry.quarantine_unhydratable


def test_hosted_attention_writes_no_founder_ask_or_answer_and_refuses_unsigned_answers(parts):
    compiled = parts[0]
    ledger = EvidenceLedger(compiled.constitution_hash)
    mark_body(ledger)
    loop = loop_on(parts, ledger)
    loop.registry.authorize(goal(), now=T0)
    loop.turn(trigger_id="t1", now=T1, signals=[signal("e1")], resources=governor(), evidence_confidence=0.9)
    assert ledger.by_type(ASK_RECORD) == [] and ledger.by_type(ANSWER_RECORD) == []
    with pytest.raises(ContractError, match="signed founder commands"):
        loop.founder_answer("item:any", decision="accept", actor="alfonso_lopez", note="x", now=T2)
    assert ledger.by_type(ANSWER_RECORD) == []


def test_no_world_evidence_means_zero_confidence_on_a_body_and_the_standalone_label_is_unchanged(parts):
    compiled = parts[0]
    hosted_ledger = EvidenceLedger(compiled.constitution_hash)
    mark_body(hosted_ledger)
    hosted, standalone = loop_on(parts, hosted_ledger), loop_on(parts)
    for loop in (hosted, standalone):
        gid = loop.registry.authorize(goal(), now=T0)
        loop.registry.wake(gid, reason="review", now=T0)          # woken with nothing observed for it
        loop.turn(trigger_id="t1", now=T1, resources=governor(), evidence_confidence=1.0)
    hosted_evidence = hosted.ledger.by_type(GoalGravityLoop.TURN_RECORD)[-1].payload["turn"]["processed"][0]["evidence"]
    standalone_evidence = standalone.ledger.by_type(GoalGravityLoop.TURN_RECORD)[-1].payload["turn"]["processed"][0]["evidence"]
    assert hosted_evidence["confidence"] == 0.0 and hosted_evidence["basis"] == "no_world_evidence"
    assert standalone_evidence["confidence"] == 1.0 and standalone_evidence["basis"] == "caller_attested_only"


def _stray(ledger, registry, gid):
    state = registry.state(gid).to_dict()
    state["goal_id"] = "sha256:" + "e" * 64
    ledger.append(GoalRegistry.TRANSITION_RECORD, {"source": "test", "goal_id": state["goal_id"],
                                                   "reason": "stray", "state": state})


def test_a_stray_goal_record_is_quarantined_on_a_body_ledger_and_fails_closed_elsewhere(parts):
    compiled = parts[0]
    plain = EvidenceLedger(compiled.constitution_hash)
    registry = GoalRegistry(ledger=plain)
    gid = registry.authorize(goal(), now=T0)
    _stray(plain, registry, gid)
    with pytest.raises(IntegrityConflict):
        GoalRegistry(ledger=plain)                           # historical behaviour, unchanged

    body = EvidenceLedger(compiled.constitution_hash)
    mark_body(body)
    hosted = GoalRegistry(ledger=body)
    gid = hosted.authorize(goal(), now=T0)
    _stray(body, hosted, gid)
    again = GoalRegistry(ledger=body)
    assert again.goals() == [gid] and len(again.quarantined) == 1
    assert again.quarantined[0]["disposition"] == "quarantined_retained_not_folded"
    loop = loop_on(parts, body)                              # the loop keeps turning instead of faulting forever
    turn = loop.turn(trigger_id="t1", now=T1, signals=[signal("e1")], resources=governor())
    assert gid in turn.woken and len(body.by_type(GoalRegistry.TRANSITION_RECORD)) >= 2


def test_refresh_folds_goal_records_another_writer_appended(parts):
    compiled = parts[0]
    ledger = EvidenceLedger(compiled.constitution_hash)
    mark_body(ledger)
    reader = GoalRegistry(ledger=ledger)
    gid = GoalRegistry(ledger=ledger).authorize(goal(), now=T0)
    assert reader.goals() == []
    reader.refresh()
    assert reader.goals() == [gid] and reader.state(gid).status == "dormant"
