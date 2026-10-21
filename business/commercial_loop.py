"""Phase 7 — the Commercial Loop, closed in order or not at all.

Recurring problem -> buyer -> offer -> payment -> delivery -> customer
outcome -> retention or termination. Payment and delivery are external
effects and must cross the Consequence Gate. A launch is not closure.

Synthetic is the default. A customer is ``observed`` only when the case is
opened with an observation from an external system of record; money is
``observed`` only when the payment's Gate receipt carries a processor
observation in live mode from a source that is not an emulator, fixture or
test mode. Everything else is labelled synthetic on the case and on its
ledger events, and a synthetic case never closes the loop externally and
never becomes external verification (foundry/outcome_bridge.py).
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
OBSERVED = "observed"
SYNTHETIC = "synthetic"
# A source naming any of these is not an external system of record.
SYNTHETIC_SOURCE_MARKERS = ("synthetic", "fixture", "emulator", "test", "stub", "sandbox", "mock", "fake",
                            "loopback", "localhost", "127.0.0.1")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CommercialLoopError(ValueError):
    """Out-of-order or unverified commercial step. Fails closed."""


def observation_problems(observation, *, money: bool) -> list[str]:
    """Why ``observation`` is not an external observation (empty when it is).

    An observation names its external system of record (``source``) and the canonical sha256 of the
    retained record (``record_ref``); a money observation must also come from the processor in live mode
    (``livemode`` True). Emulators, fixtures, test mode and stubs are synthetic, whatever they report."""
    if not isinstance(observation, dict):
        return ["no external observation"]
    problems = []
    source = str(observation.get("source") or "").strip().lower()
    if not source:
        problems.append("the observation names no external source")
    elif any(marker in source for marker in SYNTHETIC_SOURCE_MARKERS):
        problems.append(f"source {source!r} is synthetic (emulator, fixture, test mode or stub)")
    ref = str(observation.get("record_ref") or "")
    if not (ref.startswith("sha256:") and len(ref) == 71):
        problems.append("the observation cites no canonical sha256 record")
    if money and observation.get("livemode") is not True:
        problems.append("the processor did not report live mode; test-mode money is synthetic")
    return problems


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
    # Provenance labels. Synthetic unless an external observation says otherwise (see module docstring).
    customer_mode: str = SYNTHETIC
    money_mode: str = SYNTHETIC
    customer_observation: dict | None = None
    money_observation: dict | None = None

    @property
    def synthetic(self) -> bool:
        return self.customer_mode != OBSERVED or self.money_mode != OBSERVED

    def labels(self) -> dict:
        return {"synthetic": self.synthetic, "customer_mode": self.customer_mode, "money_mode": self.money_mode}


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
        entry = {"stage": to_stage, "at": _now().isoformat(), **detail, **case.labels()}
        case.history.append(entry)
        self.ledger.append("event", {"type": f"business.case_{to_stage}",
                                     "business_id": self.business.business_id,
                                     "case_id": case.case_id, **detail, **case.labels()})

    def _require_alive(self) -> None:
        if self.terminated:
            raise CommercialLoopError(
                f"business terminated ({self.termination_reason}); a dead business takes no new steps")

    def open_case(self, buyer: str, *, customer_observation: dict | None = None) -> CustomerCase:
        """Open a case. The customer is synthetic unless ``customer_observation`` comes from an external
        system of record; a supplied observation that is not one is refused rather than silently relabelled."""
        self._require_alive()
        if not buyer:
            raise CommercialLoopError("a case requires a named buyer")
        if customer_observation is not None:
            problems = observation_problems(customer_observation, money=False)
            if problems:
                raise CommercialLoopError("customer observation refused: " + "; ".join(problems))
        case = CustomerCase(case_id=str(uuid.uuid4()),
                            business_id=self.business.business_id, buyer=buyer,
                            customer_mode=OBSERVED if customer_observation is not None else SYNTHETIC,
                            customer_observation=dict(customer_observation) if customer_observation else None)
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
                     approver=None) -> CustomerCase:
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
            expected_outcome="payment settled")
        grant = self.gate.grants.issue_single_action(
            proposal=proposal, policy_version=self.gate.policy_version)
        rec = self.gate.run(proposal, executor=executor, approver=approver,
                            standing_grant=grant)
        if rec.state != "recorded":
            raise CommercialLoopError(
                f"payment did not reach recorded (state={rec.state}, reasons={rec.refusal_reasons}); an unrecorded payment did not happen")
        case.payment_action_id = rec.action_id
        case.payment_receipt_hash = rec.receipt_hash
        # The money is what the Gate's own receipt says the processor observed, never the caller's word.
        receipt = self.ledger.find(rec.receipt_hash)
        observation = ((receipt.payload.get("result") or {}).get("processor_observation")
                       if receipt is not None else None)
        why = observation_problems(observation, money=True)
        case.money_mode = SYNTHETIC if why else OBSERVED
        case.money_observation = dict(observation) if isinstance(observation, dict) else None
        self._advance(case, "payment", {"action_id": rec.action_id,
                                        "receipt_hash": rec.receipt_hash,
                                        "amount_usd": g.price_usd,
                                        **({"synthetic_money_because": why} if why else {})})
        return case

    def deliver(self, case_id: str, *, actor: str, executor,
                evidence_confidence: float, evidence_refs: list[str],
                approver=None) -> CustomerCase:
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
            expected_outcome="offer delivered")
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
        ran = [c for c in cases
               if c.payment_receipt_hash and c.delivery_receipt_hash
               and c.outcome_verified_by in ACCEPTED_VERIFICATIONS]
        # A loop run with a synthetic customer or synthetic money ran internally; it is not an external close.
        closed = [c for c in ran if not c.synthetic]
        ev = LoopEvidence(internal_ok=len(cases) > 0,
                          external_ok=len(closed) > 0,
                          detail=f"cases={len(cases)} fully_closed={len(closed)} "
                                 f"synthetic_runs={len(ran) - len(closed)}")
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
