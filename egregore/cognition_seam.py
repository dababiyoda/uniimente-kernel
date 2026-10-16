"""Seam between Goal Gravity and the canonical standing-cognition tick.

The directive says: connect the loop to the existing persistent GREG runtime
and do not add a second deliberation engine. On ``main`` that runtime is
``StandingCognitionRuntime.tick``: proposers see signals plus a context and
return ``CandidateProposal``s; required evaluators (guardian, treasury) assess;
one candidate is selected with dissent retained. This module makes goals a
*context* for that tick and makes the tick's candidates the moves the loop
classifies, so goal deliberation reuses the runtime's proposer/evaluator
discipline, resource ceilings, suspension and idempotent records.

* ``GoalProposer`` is registered by the accountable service as one proposer of
  the runtime. It emits the active node's declared moves as candidates. Any
  other proposer (a local model, an organ) sees the same goal context and may
  add candidates; every candidate is classified by the same policy engine.
* ``candidate_to_intervention`` turns any candidate into an ``InterventionSpec``.
* ``goal_context`` is what the loop hands to ``tick(context=...)``.

The seam carries no authority. A candidate selected by the tick is still only
eligible for execution; the Consequence Gate and a pre-existing grant decide.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .contracts import CandidateProposal, SignalEnvelope, canonical_copy
from .goals import GoalSpec, InterventionSpec
from .gps import GPSFix

GOAL_PROPOSER_ROLE = "goal-gravity"


def goal_context(spec: GoalSpec, fix: GPSFix, *, trigger_id: str, priority: int) -> dict[str, Any]:
    """The goal as seen by proposers: destination, active gate, SBM, declared moves, missing capabilities."""
    return canonical_copy({
        "goal_id": spec.goal_id, "trigger_id": trigger_id, "priority": priority,
        "founder_intent": spec.founder_intent, "desired_state": spec.desired_state,
        "assumptions": list(spec.assumptions), "active_node_id": fix.active_node_id,
        "active_gate": fix.active_gate, "sbm": fix.sbm, "exit_evidence": list(fix.exit_evidence),
        "missing_capabilities": list(fix.missing_capabilities),
        "missing_relationships": list(fix.missing_relationships),
        "next_interventions": list(fix.next_interventions), "route_changed": fix.route_changed,
        "execution_authority": "none",
    })


def intervention_to_candidate(spec_or_goal_id: GoalSpec | str, intervention: InterventionSpec,
                              signal_ids: Sequence[str], *, proposed_by: str = GOAL_PROPOSER_ROLE,
                              evidence_refs: Sequence[str] = (), confidence: float = 0.5) -> CandidateProposal:
    goal_id = spec_or_goal_id.goal_id if isinstance(spec_or_goal_id, GoalSpec) else spec_or_goal_id
    return CandidateProposal.build(
        proposed_by=proposed_by, objective=f"{goal_id}:{intervention.intervention_id}",
        action_class=intervention.action_class, requested_capability=intervention.requested_capability,
        target=intervention.target, consequence_class=intervention.consequence_class,
        payload={**intervention.payload, "egregore_intervention": intervention.to_dict()},
        evidence_refs=list(evidence_refs) or [f"goal:{goal_id}"], confidence=confidence,
        estimated_cost_usd=intervention.estimated_cost_usd, expected_outcome=intervention.expected_outcome,
        source_signal_ids=tuple(signal_ids))


def candidate_to_intervention(candidate: CandidateProposal) -> InterventionSpec:
    """Any candidate (declared move, model proposal, organ proposal) becomes a classifiable move."""
    declared = candidate.payload.get("egregore_intervention")
    if isinstance(declared, Mapping):
        return InterventionSpec.from_dict(declared)
    payload = {k: v for k, v in candidate.payload.items() if k != "egregore_intervention"}
    return InterventionSpec.build(
        intervention_id=f"{candidate.proposed_by}:{candidate.candidate_id[7:23]}",
        description=candidate.objective, action_class=candidate.action_class,
        requested_capability=candidate.requested_capability, consequence_class=candidate.consequence_class,
        target=candidate.target, expected_outcome=candidate.expected_outcome, payload=payload,
        estimated_cost_usd=candidate.estimated_cost_usd, tactic=f"proposer:{candidate.proposed_by}")


class GoalProposer:
    """Proposer organ for the standing runtime: emits the goal context's declared moves."""

    role = GOAL_PROPOSER_ROLE

    def __call__(self, signals: tuple[SignalEnvelope, ...], context: Mapping[str, Any]) -> list[CandidateProposal]:
        goal_id = context.get("goal_id")
        if not goal_id or not signals:
            return []
        signal_ids = tuple(s.signal_id for s in signals)
        evidence = [ref for s in signals for ref in s.evidence_refs]
        out = []
        for raw in context.get("next_interventions", ()):
            move = InterventionSpec.from_dict(raw)
            out.append(intervention_to_candidate(goal_id, move, signal_ids, evidence_refs=evidence,
                                                 confidence=0.5 if context.get("sbm") else 0.3))
        return out


def cadence_signal(goal_id: str, *, at: str, source: str) -> SignalEnvelope:
    """A review-cadence wake has no external signal; the clock tick itself is the cited evidence."""
    return SignalEnvelope.build(source=source, source_event_id=f"cadence:{goal_id}:{at}", observed_at=at,
                                payload={"observations": [], "cadence": True, "goal_id": goal_id},
                                evidence_refs=(f"cadence:{goal_id}:{at}",), trust_level="attributed")
