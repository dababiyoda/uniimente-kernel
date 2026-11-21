"""Founder intake (directive section 27): "I want X" becomes a governed draft goal, never an assumed plan.

``draft`` records the founder's statement and renders the fourteen section-27 fields, filling only
what can be derived from the statement and marking everything else ``unresolved``. It never fills
authority: ``authorize_draft`` refuses until the founder supplies the authority fields. The goal it
authorizes starts at two founder-only gates (problem class ``authorization``):

    G0  the founder confirms the desired state and the single bottleneck metric
    G1  the founder accepts a backcast plan (then ``GoalRegistry.supersede`` replaces this draft goal)

Each gate surfaces as one compressed decision; the answer is the only evidence that clears it.
GREG prepares a clarification brief inside its authority meanwhile. Deterministic: no model is
called; a local drafter can be attached as a standing-cognition proposer later and must beat this.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from .contracts import ContractError, canonical_copy, digest, require_text
from .goals import GoalSpec, InterventionSpec, PlanNode, WakeCondition, iso, parse_time

UNRESOLVED = "unresolved"
AUTHORITY_FIELDS = ("authorized_by", "authorization_ref", "legal_principal", "max_consequence_class")


class GoalIntake:
    DRAFT_RECORD = "egregore.goal_intake_draft"

    def __init__(self, loop: Any):
        self.loop = loop

    @property
    def execution_authority(self) -> str:
        return "none"

    def draft(self, statement: str, *, now: datetime | str, priority: int = 3) -> dict[str, Any]:
        statement = require_text("statement", statement)
        at = iso(parse_time(now))
        draft_id = digest({"kind": "egregore-intake-draft", "statement": statement, "priority": priority})
        short = draft_id[7:15]
        fields = {
            "desired_future_state": statement,
            "current_position": UNRESOLVED,
            "critical_assumptions": UNRESOLVED,
            "active_node": "G0",
            "active_gate": "founder confirms the desired state and the single bottleneck metric",
            "single_bottleneck_metric": f"intake.{short}.confirmed (proposed; you choose the real metric at G0)",
            "relevant_environmental_signals": UNRESOLVED,
            "available_capabilities": "preparation briefs (internal) only",
            "missing_capabilities": UNRESOLVED,
            "next_autonomous_work": "prepare a clarification brief inside standing authority",
            "next_prepared_work": "a backcast draft for your review at G1",
            "founder_required_decisions": ["confirm desired state and metric (G0)", "accept a backcast plan (G1)"],
            "evidence_state": "nothing observed yet",
            "review_trigger": "daily until G1 clears; then the authored plan's cadence",
        }
        record = {"source": self.loop.source, "draft_id": draft_id, "statement": statement, "priority": priority,
                  "fields": fields, "authority": {k: UNRESOLVED for k in AUTHORITY_FIELDS}, "drafted_at": at,
                  "disposition": "draft only: not a goal until the founder supplies authority"}
        if not any(r.payload["draft_id"] == draft_id for r in self.loop.ledger.by_type(self.DRAFT_RECORD)):
            self.loop.ledger.append(self.DRAFT_RECORD, canonical_copy(record))
        return record

    def _draft(self, draft_id: str) -> dict[str, Any]:
        for r in self.loop.ledger.by_type(self.DRAFT_RECORD):
            if r.payload["draft_id"] == draft_id:
                return r.payload
        raise ContractError("unknown intake draft")

    def authorize_draft(self, draft_id: str, *, authority: Mapping[str, Any], now: datetime | str,
                        wake_tags: Sequence[str] = (), domains: Sequence[str] = ()) -> str:
        """The founder supplies authority (declared lineage, SR001 G6); only then does a goal exist."""
        draft = self._draft(draft_id)
        missing = [k for k in AUTHORITY_FIELDS if not authority.get(k) or authority.get(k) == UNRESOLVED]
        if missing:
            raise ContractError(f"authority fields missing: {missing}; GREG never fills them in")
        short = draft_id[7:15]
        clarify = InterventionSpec.build(
            intervention_id="clarify", description="prepare a clarification brief for the desired state",
            action_class="intake.clarify", requested_capability="research.brief", consequence_class="internal_write",
            target="sandbox:intake", expected_outcome="clarification brief prepared",
            payload={"statement": draft["statement"]}, tactic="clarify")
        backcast = InterventionSpec.build(
            intervention_id="backcast", description="prepare a backcast draft for founder review",
            action_class="intake.backcast", requested_capability="research.brief", consequence_class="internal_write",
            target="sandbox:intake", expected_outcome="backcast draft prepared",
            payload={"statement": draft["statement"]}, tactic="backcast")
        spec = GoalSpec.build(
            founder_intent=draft["statement"], desired_state=draft["statement"], priority=draft["priority"],
            authority=dict(authority), time_horizon=UNRESOLVED,
            plan=[PlanNode.build(node_id="G0", outcome="desired state and metric confirmed",
                                 gate=draft["fields"]["active_gate"], sbm=f"intake.{short}.confirmed",
                                 sbm_direction="eq", sbm_target=True, interventions=(clarify,), problem_class="authorization"),
                  PlanNode.build(node_id="G1", outcome="backcast plan accepted", gate="founder accepts a backcast plan",
                                 sbm=f"intake.{short}.plan_accepted", sbm_direction="eq", sbm_target=True,
                                 interventions=(backcast,), problem_class="authorization")],
            relevant_entities=(f"intake.{short}",), domains=tuple(domains),
            wake_conditions=tuple(WakeCondition.build(kind="tag", match=t) for t in wake_tags),
            review_cadence_seconds=86400,
            assumptions=("UNRESOLVED: the founder has not stated the critical assumptions",))
        return self.loop.registry.authorize(spec, now=now)
