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

from .contract_check import validate_record
from .contracts import canonical_copy, digest, require_text
from .goals import CONSEQUENCE_CLASSES, GoalRegistry, GoalSpec, GoalState, InterventionSpec, iso, parse_time
from .gps import GPSFix

from capabilities.router import RESOLUTION_ORDER as _ROUTER_ORDER  # noqa: E402  one canonical ladder

# The doctrine's resourcefulness ladder (FOUNDER_EFFECT_COMPILER) as the router on main records it, plus
# the doctrine's final rung, which the router leaves implicit.
RESOLUTION_ORDER = tuple(_ROUTER_ORDER) + ("escalate/abstain",)

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

    @staticmethod
    def epistemic_deficit(spec: GoalSpec, fix: Any, routing: Any, *, at: str) -> dict[str, Any]:
        """The typed CapabilityDeficit for a gate no registered mechanism can answer (one id per goal, gate, gap)."""
        d = routing.deficit
        return {
            "deficit_id": digest({"kind": "egregore-epistemic-deficit", "goal_id": spec.goal_id,
                                  "active_node_id": fix.active_node_id if fix else None,
                                  "missing_methods": sorted(d["missing_methods"]),
                                  "problem_class": d["problem_class"]}),
            "goal_id": spec.goal_id, "active_node_id": fix.active_node_id if fix else None,
            "missing_capabilities": [], "missing_methods": list(d["missing_methods"]),
            "problem_class": d["problem_class"], "router_deficit_id": d["router_deficit_id"],
            "routing_decision_id": routing.decision_id, "rejected": dict(d["rejected"]),
            "founder_intent": spec.founder_intent, "resolution_order": list(RESOLUTION_ORDER),
            "lifecycle": "DISCOVERED", "disposition": "goal_blocked_not_closed", "detected_at": at,
            "resume": "original_goal"}

    @staticmethod
    def capability_deficit(spec: GoalSpec, fix: GPSFix, *, at: str) -> dict[str, Any]:
        """The typed capability deficit for a gate whose required capability is missing. Recorded by the loop at the
        gate level (so a route that is already executed or open still names its deficit) and by ``classify``."""
        return {
            "deficit_id": digest({"kind": "egregore-capability-deficit", "goal_id": spec.goal_id,
                                  "active_node_id": fix.active_node_id, "missing": sorted(fix.missing_capabilities)}),
            "goal_id": spec.goal_id, "active_node_id": fix.active_node_id,
            "missing_capabilities": list(fix.missing_capabilities), "founder_intent": spec.founder_intent,
            "resolution_order": list(RESOLUTION_ORDER), "lifecycle": "DISCOVERED",
            "disposition": "goal_blocked_not_closed", "detected_at": at, "resume": "original_goal"}

    def _record_deficit(self, spec: GoalSpec, deficit: Mapping[str, Any]) -> None:
        """One typed record per open deficit (both origins), deduped by deficit id while open."""
        deficit = canonical_copy(dict(deficit))
        validate_record(deficit, "capability-deficit")
        already = any(r.payload.get("deficit", {}).get("deficit_id") == deficit["deficit_id"]
                      and r.payload["deficit"]["disposition"] == "goal_blocked_not_closed"
                      for r in self.ledger.by_type(self.DEFICIT_RECORD))
        resolved = any(r.payload.get("deficit", {}).get("deficit_id") == deficit["deficit_id"]
                       and r.payload["deficit"]["disposition"] == "resolved_resume_original_goal"
                       for r in self.ledger.by_type(self.DEFICIT_RECORD))
        if not already or resolved and not self._reopened(deficit["deficit_id"]):
            self.ledger.append(self.DEFICIT_RECORD, {"source": self.source, "deficit": deficit,
                                                     # flattened copies keep older readers working
                                                     "goal_id": spec.goal_id,
                                                     "missing_capabilities": deficit["missing_capabilities"],
                                                     "founder_intent": spec.founder_intent,
                                                     "disposition": deficit["disposition"]})

    def _reopened(self, deficit_id: str) -> bool:
        """True when the latest record for this deficit is already open (no duplicate re-open)."""
        latest = None
        for r in self.ledger.by_type(self.DEFICIT_RECORD):
            d = r.payload.get("deficit", {})
            if d.get("deficit_id") == deficit_id:
                latest = d["disposition"]
        return latest == "goal_blocked_not_closed"

    @staticmethod
    def proposal_id_for(goal_id: str, route_hash: str, *, attempt: int = 0) -> str:
        """Deterministic proposal identity: ``egregore:goal:<goal23>:<route23>`` for the first dispatch of a
        route; ``...:r<n>`` for the n-th re-dispatch after an accountable reconciliation. The Gate's dispatch
        claim is keyed on this id, so a re-dispatch is always a distinguishable record, never a replay."""
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 0:
            raise ValueError("attempt must be a non-negative integer")
        base = f"egregore:goal:{goal_id[:23]}:{route_hash[:23]}"
        return base if attempt == 0 else f"{base}:r{attempt}"

    def proposal_for(self, spec: GoalSpec, intervention: InterventionSpec, *, evidence_refs: Sequence[str],
                     evidence_confidence: float, context: Mapping[str, Any] | None = None, attempt: int = 0) -> Proposal:
        """Bind a move to real accountability for policy review (same shape as gate_adapter)."""
        return Proposal(
            actor=self.actor, legal_principal=self.legal_principal, action_class=intervention.action_class,
            objective=f"{spec.goal_id}:{intervention.intervention_id}", payload=canonical_copy(intervention.payload),
            target=intervention.target, consequence_class=intervention.consequence_class,
            evidence_confidence=float(evidence_confidence), evidence_refs=list(evidence_refs),
            estimated_cost_usd=intervention.estimated_cost_usd, requested_capability=intervention.requested_capability,
            expected_outcome=intervention.expected_outcome,
            context={**canonical_copy(dict(context or {})), "goal_id": spec.goal_id,
                     "egregore_route_hash": intervention.route_hash, "egregore_attempt": attempt,
                     "egregore_execution_authority": "none"},
            proposal_id=self.proposal_id_for(spec.goal_id, intervention.route_hash, attempt=attempt))

    def classify(self, spec: GoalSpec, state: GoalState, intervention: InterventionSpec, *, fix: GPSFix | None,
                 grant: Mapping[str, Any] | None, evidence_refs: Sequence[str], evidence_confidence: float,
                 now: datetime | str, record: bool = True, grant_view: Mapping[str, Any] | None = None,
                 selected: bool | None = None, unmet_dependencies: Sequence[str] = (),
                 routing: Any = None) -> Classification:
        """``grant_view`` is the Gate's evaluation view of the same grant (wire contract plus
        gate-managed stage metadata); when omitted the raw grant is evaluated as-is.
        ``selected`` reports whether standing deliberation (guardian/treasury evaluators) selected this
        move; ``False`` turns an otherwise executable move into prepared work. ``unmet_dependencies``
        (goals the spec depends on that are not completed) make every move WAIT. ``routing`` is the
        Competency Compiler's view of the active gate (``egregore.competency.RoutingView``); it only ever
        tightens: a deficit waits, a rejected declared mechanism or a human-only gate prepares, and an
        unproven mechanism never runs an external move."""
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
        elif self.registry.is_route_refused(spec.goal_id, intervention.route_hash, intervention.effect_hash):
            decision, reasons = "ABSTAIN", ["founder refused this exact route or its identical effect; not re-proposed unchanged"]
        elif self.registry.capability_revoked(spec.goal_id, intervention.requested_capability):
            decision, reasons = "ABSTAIN", [f"founder revoked capability {intervention.requested_capability!r} for this goal"]
        elif unmet_dependencies:
            decision = "WAIT"
            reasons = [f"dependency unmet: {d}" for d in unmet_dependencies] + ["original goal retained"]
        elif routing is not None and routing.deficit is not None:
            d = routing.deficit
            decision = "WAIT"
            reasons = [f"Competency Compiler: no registered mechanism can answer this {d['problem_class']} gate "
                       f"(missing {', '.join(d['missing_methods'])}); original goal retained"]
            if record:
                self._record_deficit(spec, self.epistemic_deficit(spec, fix, routing, at=classified_at))
        elif fix is not None and fix.missing_capabilities:
            decision = "WAIT"
            reasons = [f"capability deficit: {', '.join(fix.missing_capabilities)}; original goal retained"]
            if record:
                self._record_deficit(spec, self.capability_deficit(spec, fix, at=classified_at))
        else:
            identity_ok, why = self.passports.verify(self.actor)
            if not identity_ok:
                decision, reasons = "PREPARE_FOR_FOUNDER", [f"actor identity not valid: {why}; prepared only"]
            elif routing is not None and routing.declared_rejected:
                key, why = sorted(routing.declared_rejected.items())[0]
                decision, reasons = "PREPARE_FOR_FOUNDER", [
                    f"Competency Compiler rejected the declared mechanism {key}: {why}; prepared only"]
            elif (routing is not None and routing.human_escalation
                  and CONSEQUENCE_CLASSES.index(intervention.consequence_class) >= CONSEQUENCE_CLASSES.index("external_contact")):
                decision, reasons = "PREPARE_FOR_FOUNDER", [
                    f"this gate needs {', '.join(routing.human_escalation)}, which only a person can supply; prepared only"]
            elif spec.authority["legal_principal"] != self.legal_principal:
                decision, reasons = "PREPARE_FOR_FOUNDER", [
                    f"goal legal principal {spec.authority['legal_principal']!r} differs from the acting principal "
                    f"{self.legal_principal!r}; prepared only"]
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
                    elif selected is False:
                        decision, reasons = "PREPARE_FOR_FOUNDER", [
                            "standing deliberation (guardian/treasury evaluators) did not select this move; prepared only"]
                    elif routing is not None and routing.exploratory and (
                            self.registry.ask_before(spec.goal_id, "exploratory_mechanism")
                            or CONSEQUENCE_CLASSES.index(intervention.consequence_class) >= CONSEQUENCE_CLASSES.index("external_contact")):
                        decision, reasons = "PREPARE_FOR_FOUNDER", [
                            f"recruited mechanism(s) {', '.join(routing.selected)} have no verified track record; "
                            "margin from an uncertain boundary: prepared only"]
                    else:
                        decision, reasons = "EXECUTE_AUTONOMOUSLY", ["policy allows under a pre-existing grant"]
                        if routing is not None:
                            reasons.append(f"Competency Compiler recruited {', '.join(routing.selected) or 'no mechanism'} "
                                           f"(decision {routing.decision_id[7:19]})")
        if routing is not None and decision != "WAIT" and routing.preferred_instead:
            reasons = list(reasons) + [f"Competency Compiler would recruit {', '.join(routing.preferred_instead)} "
                                       "instead of the declared mechanism"]
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
