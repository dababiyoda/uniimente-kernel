"""Phase 7 — the Commercial Loop, closed in order or not at all.

Recurring problem -> buyer -> offer -> payment -> delivery -> customer
outcome -> retention or termination. Payment and delivery are external
effects and must cross the Consequence Gate. A launch is not closure.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from closure.whole_body import Loop, LoopEvidence, WholeBodyClosureController
from policy.engine import Proposal

STAGES = ("problem", "buyer", "offer", "payment", "delivery",
          "customer_outcome", "retention_or_termination")

ACCEPTED_VERIFICATIONS = ("deterministic_invariant", "external_outcome",
                          "external_receipt", "human_review", "independent_model")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CommercialLoopError(ValueError):
    """Out-of-order or unverified commercial step. Fails closed."""


@dataclass
class CustomerCase:
    case_id: str
    business_id: str
    buyer: str
    stage: str = "problem"
    payment_action_id: str | None = None
    payment_receipt_hash: str | None = None
    delivery_action_id: str | None = None
    delivery_receipt_hash: str | None = None
    outcome_verified_by: str | None = None
    outcome_detail: str | None = None
    resolution: str | None = None
    history: list[dict] = field(default_factory=list)


class CommercialLoop:
    """Run customer cases through a strictly ordered commercial lifecycle."""

    def __init__(self, compiled_business, *, gate, ledger):
        self.business = compiled_business
        self.gate = gate
        self.ledger = ledger
        self._cases: dict[str, CustomerCase] = {}
        self.terminated = False
        self.termination_reason: str | None = None

    def _advance(self, case: CustomerCase, to_stage: str, detail: dict) -> None:
        expected = STAGES[STAGES.index(case.stage) + 1]
        if to_stage != expected:
            raise CommercialLoopError(
                f"loop advances in order: at {case.stage!r} the next stage is {expected!r}, not {to_stage!r}")
        case.stage = to_stage
        entry = {"stage": to_stage, "at": _now().isoformat(), **detail}
        case.history.append(entry)
        self.ledger.append("event", {"type": f"business.case_{to_stage}",
                                     "business_id": self.business.business_id,
                                     "case_id": case.case_id, **detail})

    def _require_alive(self) -> None:
        if self.terminated:
            raise CommercialLoopError(
                f"business terminated ({self.termination_reason}); a dead business takes no new steps")

    def open_case(self, buyer: str) -> CustomerCase:
        self._require_alive()
        if not buyer:
            raise CommercialLoopError("a case requires a named buyer")
        case = CustomerCase(case_id=str(uuid.uuid4()),
                            business_id=self.business.business_id, buyer=buyer)
        self._cases[case.case_id] = case
        self._advance(case, "buyer", {"buyer": buyer,
                                      "problem": self.business.genome.problem})
        return case

    def present_offer(self, case_id: str) -> CustomerCase:
        self._require_alive()
        case = self._cases[case_id]
        self._advance(case, "offer", {"offer": self.business.genome.offer,
                                      "price_usd": self.business.genome.price_usd})
        return case

    def take_payment(self, case_id: str, *, actor: str, executor,
                     evidence_confidence: float, evidence_refs: list[str],
                     approver=None,
                     containment: dict | None = None) -> CustomerCase:
        self._require_alive()
        case = self._cases[case_id]
        if case.stage != "offer":
            raise CommercialLoopError(f"no payment before an offer (at {case.stage!r})")
        g = self.business.genome
        proposal = Proposal(
            actor=actor, legal_principal=g.legal_operator,
            action_class="business.charge",
            objective=f"charge {case.buyer} for {g.offer}",
            payload={"case_id": case.case_id, "amount_usd": g.price_usd,
                     "offer": g.offer},
            target=f"buyer:{case.buyer}", consequence_class="financial",
            evidence_confidence=evidence_confidence, evidence_refs=evidence_refs,
            estimated_cost_usd=g.price_usd,
            requested_capability="business.charge",
            expected_outcome="payment settled",
            # CONTRADICTION-0003 Option B. Caller-supplied for the same reason
            # as delivery: whether a payment is reversible is a fact about the
            # payment rail, which this module does not know.
            context=dict(containment or {}))
        grant = self.gate.grants.issue_single_action(
            proposal=proposal, policy_version=self.gate.policy_version)
        rec = self.gate.run(proposal, executor=executor, approver=approver,
                            standing_grant=grant)
        if rec.state != "recorded":
            raise CommercialLoopError(
                f"payment did not reach recorded (state={rec.state}, reasons={rec.refusal_reasons}); an unrecorded payment did not happen")
        case.payment_action_id = rec.action_id
        case.payment_receipt_hash = rec.receipt_hash
        self._advance(case, "payment", {"action_id": rec.action_id,
                                        "receipt_hash": rec.receipt_hash,
                                        "amount_usd": g.price_usd})
        return case

    def deliver(self, case_id: str, *, actor: str, executor,
                evidence_confidence: float, evidence_refs: list[str],
                approver=None, containment: dict | None = None) -> CustomerCase:
        self._require_alive()
        case = self._cases[case_id]
        if case.stage != "payment":
            raise CommercialLoopError(f"no delivery before payment (at {case.stage!r})")
        g = self.business.genome
        proposal = Proposal(
            actor=actor, legal_principal=g.legal_operator,
            action_class="business.deliver",
            objective=f"deliver {g.offer} to {case.buyer}",
            payload={"case_id": case.case_id, "offer": g.offer,
                     "fulfillment": g.fulfillment},
            target=f"buyer:{case.buyer}", consequence_class="external_contact",
            evidence_confidence=evidence_confidence, evidence_refs=evidence_refs,
            estimated_cost_usd=g.marginal_cost_usd,
            requested_capability="business.deliver",
            expected_outcome="offer delivered",
            # CONTRADICTION-0003 Option B. Caller-supplied: whether a delivery
            # to a real buyer is reversible or observable is a fact about the
            # fulfilment arrangement, not about this function.
            context=dict(containment or {}))
        grant = self.gate.grants.issue_single_action(
            proposal=proposal, policy_version=self.gate.policy_version)
        rec = self.gate.run(proposal, executor=executor, approver=approver,
                            standing_grant=grant)
        if rec.state != "recorded":
            raise CommercialLoopError(
                f"delivery did not reach recorded (state={rec.state}, reasons={rec.refusal_reasons}); an unrecorded delivery did not happen")
        case.delivery_action_id = rec.action_id
        case.delivery_receipt_hash = rec.receipt_hash
        self._advance(case, "delivery", {"action_id": rec.action_id,
                                         "receipt_hash": rec.receipt_hash})
        return case

    def verify_outcome(self, case_id: str, *, verified_by: str,
                       detail: str) -> CustomerCase:
        self._require_alive()
        case = self._cases[case_id]
        if case.stage != "delivery":
            raise CommercialLoopError(f"no outcome before delivery (at {case.stage!r})")
        if verified_by not in ACCEPTED_VERIFICATIONS:
            raise CommercialLoopError(
                f"{verified_by!r} cannot verify customer value; accepted: {ACCEPTED_VERIFICATIONS}")
        case.outcome_verified_by = verified_by
        case.outcome_detail = detail
        self._advance(case, "customer_outcome",
                      {"verified_by": verified_by, "detail": detail})
        return case

    def resolve(self, case_id: str, *, retained: bool, reason: str) -> CustomerCase:
        self._require_alive()
        case = self._cases[case_id]
        if case.stage != "customer_outcome":
            raise CommercialLoopError(
                f"no resolution before a verified outcome (at {case.stage!r})")
        case.resolution = "retained" if retained else "terminated"
        self._advance(case, "retention_or_termination",
                      {"resolution": case.resolution, "reason": reason})
        return case

    def evaluate(self):
        cases = list(self._cases.values())
        closed = [c for c in cases
                  if c.payment_receipt_hash and c.delivery_receipt_hash
                  and c.outcome_verified_by in ACCEPTED_VERIFICATIONS]
        ev = LoopEvidence(internal_ok=len(cases) > 0,
                          external_ok=len(closed) > 0,
                          detail=f"cases={len(cases)} fully_closed={len(closed)}")
        return WholeBodyClosureController().applicable(
            f"commercial:{self.business.genome.name}",
            {Loop.COMMERCIAL: ev}, applicable={Loop.COMMERCIAL})

    def trigger_kill(self, *, evidence: str) -> None:
        self.terminated = True
        self.termination_reason = evidence
        self.ledger.append("event", {
            "type": "business.terminated",
            "business_id": self.business.business_id,
            "genome": self.business.genome.name,
            "kill_condition": self.business.genome.kill_condition,
            "evidence": evidence,
            "learning": "termination discipline exercised; failure preserved as an appreciating asset"})
