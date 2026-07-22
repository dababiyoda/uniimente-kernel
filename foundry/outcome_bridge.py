"""Commercial Loop -> Advantage Foundry external outcome bridge.

The existing Business Foundry owns payment, delivery, and customer-outcome
execution. This bridge does not repeat those actions. It converts a completed
CustomerCase plus explicit reconciliation evidence into an ExternalOutcome for
Foundry retain/modify/kill review.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from business.commercial_loop import ACCEPTED_VERIFICATIONS, CustomerCase
from .advantage import AdvantageRefused, ExternalOutcome


@dataclass(frozen=True)
class ReconciliationPacket:
    economic_commitment_usd: float
    fully_loaded_cost_usd: float
    founder_hours: float
    acceptance_receipt_ref: str
    outcome_receipt_ref: str
    reconciliation_ref: str
    authority_incidents: int = 0
    critical_participant_harm_incidents: int = 0
    metric_results: dict[str, float] | None = None

    def validate(self) -> None:
        if self.economic_commitment_usd <= 0:
            raise AdvantageRefused("positive economic commitment is required")
        if self.fully_loaded_cost_usd < 0 or self.founder_hours < 0:
            raise AdvantageRefused("cost and founder hours cannot be negative")
        if self.authority_incidents < 0 or self.critical_participant_harm_incidents < 0:
            raise AdvantageRefused("incident counts cannot be negative")
        for field_name in (
            "acceptance_receipt_ref", "outcome_receipt_ref", "reconciliation_ref"
        ):
            _require_hash(getattr(self, field_name), field_name)


def external_outcome_from_case(
    case: CustomerCase,
    reconciliation: ReconciliationPacket,
) -> ExternalOutcome:
    reconciliation.validate()
    if case.stage != "retention_or_termination":
        raise AdvantageRefused("commercial case must reach retention or termination")
    if not case.payment_receipt_hash:
        raise AdvantageRefused("commercial case lacks a recorded payment receipt")
    if not case.delivery_receipt_hash:
        raise AdvantageRefused("commercial case lacks a recorded delivery receipt")
    if case.outcome_verified_by not in ACCEPTED_VERIFICATIONS:
        raise AdvantageRefused("commercial outcome lacks an accepted external verifier")
    if not case.outcome_detail:
        raise AdvantageRefused("commercial outcome detail is missing")
    if case.resolution not in {"retained", "terminated"}:
        raise AdvantageRefused("commercial case lacks a valid resolution")

    receipt_refs = tuple(dict.fromkeys((
        _require_hash(case.payment_receipt_hash, "payment_receipt_hash"),
        _require_hash(case.delivery_receipt_hash, "delivery_receipt_hash"),
        reconciliation.acceptance_receipt_ref,
        reconciliation.outcome_receipt_ref,
        reconciliation.reconciliation_ref,
    )))
    return ExternalOutcome(
        economic_commitment_usd=float(reconciliation.economic_commitment_usd),
        accepted_delivery=True,
        externally_verified=True,
        contribution_margin_usd=(
            float(reconciliation.economic_commitment_usd)
            - float(reconciliation.fully_loaded_cost_usd)
        ),
        founder_hours=float(reconciliation.founder_hours),
        reconciliation_closed=True,
        authority_incidents=int(reconciliation.authority_incidents),
        critical_participant_harm_incidents=int(
            reconciliation.critical_participant_harm_incidents
        ),
        metric_results=dict(reconciliation.metric_results or {}),
        receipt_refs=receipt_refs,
    )


def _require_hash(value: Any, field_name: str) -> str:
    value = str(value or "")
    if not value.startswith("sha256:") or len(value) != 71:
        raise AdvantageRefused(f"{field_name} must be a canonical sha256 reference")
    return value
