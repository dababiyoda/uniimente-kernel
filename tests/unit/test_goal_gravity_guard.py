"""Prior-attempt guard (fourth increment): a route whose latest record is an open or completed attempt is never
re-classified, re-asked or re-dispatched, and that must not starve anything the gate still owes: the typed
capability deficit, the acquisition ladder, the status view and the standing-cognition seam contract.

One regression test per confirmed finding of the fourth-increment adversarial review
(``tests/evidence/goal-gravity-20261013/review-increment-4.json``). Deterministic and model-free.
"""
from __future__ import annotations

from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeRegistry
from tests.unit.test_goal_gravity import (  # noqa: F401  (stack is a fixture)
    GOOD, T0, T1, T2, brief_move, governor, grant_for, make_loop, robotics_goal, stack,
)
from tests.unit.test_goal_gravity_absence import with_moves
from tests.unit.test_goal_gravity_seams import hardware_signal, make_cognitive_loop

CAPABILITY = "brief.compiler@1.0"


def brief_compiler_genome():
    return CapabilityGenome(
        name="brief.compiler", version="1.0", description="compiles a research brief from retained evidence",
        interface={"inputs": {"topic": "string"}, "outputs": {"brief": "document"}}, contracts=["evidence"],
        authority=AuthorityEnvelope(max_consequence_class="internal_write", budget_ceiling_usd=0.0),
        acceptance_tests=["tests/unit/test_goal_gravity.py::test_capability_deficit_path_keeps_original_goal_intact"],
        failure_modes=["empty evidence set"], recovery_path="report the brief as not compiled")


def test_a_capability_lost_after_the_route_executed_still_opens_a_typed_deficit_and_the_ladder(stack):
    """Finding: the typed capability deficit was written only inside classify()'s WAIT arm; once every move on the
    active gate was done or open, the guard skipped classify() and a capability that went missing afterwards left no
    typed record, no named blocker and nothing for acquisition.plan() to act on."""
    compiled, passports, ledger, gate, actor = stack
    present = GenomeRegistry(ledger)
    present.register(brief_compiler_genome())
    loop = make_loop(stack, genomes=present)
    spec = with_moves(robotics_goal(requires=(CAPABILITY,), second_node=False), brief_move())
    goal_id = loop.registry.authorize(spec, now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), gate=gate, executor=GOOD,
                     grants={"research.brief": grant_for(loop, gate, spec, brief_move())}, evidence_confidence=0.9)
    assert [e["goal_id"] for e in turn.executed] == [goal_id] and turn.executed[0]["receipt_hash"]
    assert ledger.by_type(loop.classifier.DEFICIT_RECORD) == [], "nothing was missing while the capability was present"
    # A restart on a body whose genome registry no longer carries the capability: the only move is already executed.
    later = make_loop(stack, genomes=GenomeRegistry())
    later.registry.wake(goal_id, reason="test", now=T2)
    again = later.turn(trigger_id="t2", now=T2, resources=governor(), evidence_confidence=0.9)
    decision = again.processed[0]["decisions"][0]
    assert decision["evidence_state"] == "executed" and "not re-proposed" in decision["disposition"]
    assert again.processed[0]["missing_capabilities"] == [CAPABILITY]
    typed = [r.payload for r in ledger.by_type(later.classifier.DEFICIT_RECORD)]
    assert len(typed) == 1 and typed[0]["missing_capabilities"] == [CAPABILITY]
    assert typed[0]["disposition"] == "goal_blocked_not_closed" and typed[0]["deficit"]["detected_at"] == T2
    state = later.registry.state(goal_id)
    assert state.status == "blocked" and f"capability deficit: {CAPABILITY}" in state.blockers
    assert later.status(goal_id, now=T2)["blockers"], "the status view names the blocker"
    plan = later.acquisition.plan(goal_id, now=T2)
    assert plan["disposition"].startswith("prepared_not_executed") and plan["plan_id"]
    # The deficit record is deduplicated across wakes while it stays open.
    later.registry.wake(goal_id, reason="test", now="2026-10-15T14:00:00Z")
    later.turn(trigger_id="t3", now="2026-10-15T14:00:00Z", resources=governor(), evidence_confidence=0.9)
    assert len(ledger.by_type(later.classifier.DEFICIT_RECORD)) == 1


def test_the_guard_keeps_the_seam_contract_under_standing_cognition(stack):
    """Finding: the guard hard-coded selected_by_deliberation=None, breaking the invariant the seam test documents
    (every decision of a cognitive turn says whether the tick selected it)."""
    compiled, passports, ledger, gate, actor = stack
    loop, runtime = make_cognitive_loop(stack)
    spec = with_moves(robotics_goal(), brief_move())      # one candidate, so the tick selects it and it executes
    goal_id = loop.registry.authorize(spec, now=T0)
    grants = {"research.brief": grant_for(loop, gate, spec, brief_move())}
    first = loop.turn(trigger_id="t1", now=T1, signals=[hardware_signal()], resources=governor(), gate=gate, executor=GOOD,
                      grants=grants, evidence_confidence=0.9)
    assert [e["goal_id"] for e in first.executed] == [goal_id]
    loop.registry.wake(goal_id, reason="test", now=T2)
    second = loop.turn(trigger_id="t2", now=T2, resources=governor(), evidence_confidence=0.9)
    decisions = second.processed[0]["decisions"]
    guarded = next(d for d in decisions if d["intervention_id"] == "compile-brief")
    assert guarded["evidence_state"] == "executed" and guarded["note"] == "already attempted; no duplicate consequential action"
    assert all(d["selected_by_deliberation"] in (True, False) for d in decisions), decisions
    assert second.executed == ()
