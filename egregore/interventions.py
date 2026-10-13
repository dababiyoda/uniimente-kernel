"""Intervention Classifier (target E): what may GREG do with the next move?

Every candidate move is classified as one of

    EXECUTE_AUTONOMOUSLY   policy allows, a pre-existing standing grant covers
                           it, and the goal's declared authority ceiling permits
    PREPARE_FOR_FOUNDER    policy or authority does not cover it: prepare the
                           work product, never execute
    REQUEST_EVIDENCE       the evidence floor for the consequence class is unmet
    WAIT                   a required capability is missing (CapabilityDeficit)
    ESCALATE               the Kernel requires a human decision
    ABSTAIN                founder refused this route/tactic, or law forbids it

The classifier calls the canonical policy engine. It never executes and
never issues a grant. Execution, when permitted, still goes through the
Consequence Gate with the same pre-existing grant.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from policy.engine import Proposal, Verdict, evaluate

from .contracts import canonical_copy, digest, require_text
from .goals import CONSEQUENCE_CLASSES, GoalRegistry, GoalSpec, GoalState, InterventionSpec, iso, parse_time
from .gps import GPSFix

DECISIONS = ("EXECUTE_AUTONOMOUSLY", "PREPARE_FOR_FOUNDER", "REQUEST_EVIDENCE", "WAIT", "ESCALATE", "ABSTAIN")
EVIDENCE_STATES = ("planned", "attempted", "executed", "externally_verified", "failed", "unknown")


@dataclass(frozen=True)
class Classification:
    goal_id: str
    intervention_id: str
    route_hash: str
    decision: str
    reasons: tuple[str, ...]
    policy_verdict: str | None
    missing: tuple[str, ...]
    proposal_id: str
    consequence_class: str
    evidence_confidence: float
    classified_at: str
    classification_id: str

    @property
    def execution_authority(self) -> str:
        return "none"

    def to_dict(self) -> dict[str, Any]:
        return {"goal_id": self.goal_id, "intervention_id": self.intervention_id, "route_hash": self.route_hash,
                "decision": self.decision, "reasons": list(self.reasons), "policy_verdict": self.policy_verdict,
                "missing": list(self.missing), "proposal_id": self.proposal_id,
                "consequence_class": self.consequence_class, "evidence_confidence": self.evidence_confidence,
                "classified_at": self.classified_at, "classification_id": self.classification_id,
                "execution_authority": "none"}


class InterventionClassifier:
    CLASSIFICATION_RECORD = "egregore.intervention_classified"
    DEFICIT_RECORD = "egregore.capability_deficit"

    def __init__(self, *, ledger: Any, registry: GoalRegistry, compiled: Any, passports: Any, actor: str,
                 legal_principal: str, source: str = "spiffe://uniimente.internal/egregore/goal-gravity"):
        self.ledger = ledger
        self.registry = registry
        self.compiled = compiled
        self.passports = passports
        self.actor = require_text("actor", actor)
        self.legal_principal = require_text("legal_principal", legal_principal)
        if self.legal_principal.casefold() == "uniimente":
            raise ValueError("UNIIMENTE may never be the legal principal")
        self.source = require_text("source", source)

    @property
    def execution_authority(self) -> str:
        return "none"

    def proposal_for(self, spec: GoalSpec, intervention: InterventionSpec, *, evidence_refs: Sequence[str],
                     evidence_confidence: float, context: Mapping[str, Any] | None = None) -> Proposal:
        """Bind a move to real accountability for policy review (same shape as gate_adapter)."""
        return Proposal(
            actor=self.actor, legal_principal=self.legal_principal, action_class=intervention.action_class,
            objective=f"{spec.goal_id}:{intervention.intervention_id}", payload=canonical_copy(intervention.payload),
            target=intervention.target, consequence_class=intervention.consequence_class,
            evidence_confidence=float(evidence_confidence), evidence_refs=list(evidence_refs),
            estimated_cost_usd=intervention.estimated_cost_usd, requested_capability=intervention.requested_capability,
            expected_outcome=intervention.expected_outcome,
            context={**canonical_copy(dict(context or {})), "goal_id": spec.goal_id,
                     "egregore_route_hash": intervention.route_hash, "egregore_execution_authority": "none"},
            proposal_id=f"egregore:goal:{spec.goal_id[:23]}:{intervention.route_hash[:23]}")

    def classify(self, spec: GoalSpec, state: GoalState, intervention: InterventionSpec, *, fix: GPSFix | None,
                 grant: Mapping[str, Any] | None, evidence_refs: Sequence[str], evidence_confidence: float,
                 now: datetime | str, record: bool = True, grant_view: Mapping[str, Any] | None = None) -> Classification:
        """``grant_view`` is the Gate's evaluation view of the same grant (wire contract plus
        gate-managed stage metadata); when omitted the raw grant is evaluated as-is."""
        classified_at = iso(parse_time(now))
        reasons: list[str] = []
        missing: tuple[str, ...] = ()
        verdict: str | None = None
        proposal = self.proposal_for(spec, intervention, evidence_refs=evidence_refs, evidence_confidence=evidence_confidence)
        decision = None

        if state.status in ("revoked", "paused", "completed") or state.preferences.get("stop_pushing"):
            decision, reasons = "ABSTAIN", [f"goal is {state.status}; founder stopped pushing"]
        elif self.registry.tactic_forbidden(spec.goal_id, intervention.tactic):
            decision, reasons = "ABSTAIN", [f"founder said never use tactic {intervention.tactic!r}"]
        elif self.registry.is_route_refused(spec.goal_id, intervention.route_hash):
            decision, reasons = "ABSTAIN", ["founder refused this exact route; not re-proposed unchanged"]
        elif fix is not None and fix.missing_capabilities:
            decision = "WAIT"
            reasons = [f"capability deficit: {', '.join(fix.missing_capabilities)}; original goal retained"]
            if record:
                self.ledger.append(self.DEFICIT_RECORD, {
                    "source": self.source, "goal_id": spec.goal_id, "active_node_id": fix.active_node_id,
                    "missing_capabilities": list(fix.missing_capabilities), "founder_intent": spec.founder_intent,
                    "resolution_order": ["existing capability", "composition", "commodity infrastructure", "open source",
                                         "API/plugin/service", "authorized computer use", "small utility",
                                         "coding agent", "organization design", "new architecture", "escalate/abstain"],
                    "disposition": "goal_blocked_not_closed", "detected_at": classified_at})
        else:
            identity_ok, why = self.passports.verify(self.actor)
            if not identity_ok:
                decision, reasons = "PREPARE_FOR_FOUNDER", [f"actor identity not valid: {why}; prepared only"]
            else:
                view = grant_view if grant_view is not None else grant
                policy = evaluate(self.compiled, proposal, identity_ok=True, grant=dict(view) if view else None)
                verdict, missing = policy.verdict.value, tuple(policy.missing)
                if policy.verdict is Verdict.DENY:
                    if "sufficient_evidence" in policy.missing:
                        decision, reasons = "REQUEST_EVIDENCE", list(policy.reasons)
                    elif any("prohibited" in r or "rank-1" in r for r in policy.reasons):
                        decision, reasons = "ABSTAIN", list(policy.reasons)
                    else:
                        decision, reasons = "PREPARE_FOR_FOUNDER", list(policy.reasons) + ["prepared; not executed"]
                elif policy.verdict is Verdict.REQUIRE_HUMAN:
                    decision, reasons = "ESCALATE", list(policy.reasons)
                else:
                    ceiling = spec.authority["max_consequence_class"]
                    if self.registry.ask_before(spec.goal_id, intervention.consequence_class, intervention.action_class):
                        decision, reasons = "PREPARE_FOR_FOUNDER", ["founder asked to be consulted before this category"]
                    elif CONSEQUENCE_CLASSES.index(intervention.consequence_class) > CONSEQUENCE_CLASSES.index(ceiling):
                        decision, reasons = "PREPARE_FOR_FOUNDER", [
                            f"{intervention.consequence_class} exceeds goal authority ceiling {ceiling}; prepared only"]
                    elif grant is None:
                        decision, reasons = "PREPARE_FOR_FOUNDER", ["no pre-existing standing grant; prepared only"]
                    else:
                        decision, reasons = "EXECUTE_AUTONOMOUSLY", ["policy allows under a pre-existing grant"]
        result = Classification(
            goal_id=spec.goal_id, intervention_id=intervention.intervention_id, route_hash=intervention.route_hash,
            decision=decision, reasons=tuple(reasons), policy_verdict=verdict, missing=missing,
            proposal_id=proposal.proposal_id, consequence_class=intervention.consequence_class,
            evidence_confidence=float(evidence_confidence), classified_at=classified_at,
            classification_id=digest({"kind": "egregore-classification", "goal_id": spec.goal_id,
                                      "route_hash": intervention.route_hash, "decision": decision,
                                      "classified_at": classified_at}))
        if record:
            self.ledger.append(self.CLASSIFICATION_RECORD, {"source": self.source, "classification": result.to_dict(),
                                                            "disposition": "classified_only"})
        return result
