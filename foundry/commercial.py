"""Paid-validation and commercial-closure state machine.

This module records the path from a qualified opportunity to a verified paid
Genome. It never performs outreach, payment, or delivery itself. Consequential
steps require canonical gate receipts and every stage requires evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Any, Mapping

from .contracts import AdvantageArchitecture, ExternalOutcome, FoundryError, OpportunitySpec


class CommercialStage(str, Enum):
    QUALIFIED_SIGNAL = "QUALIFIED_SIGNAL"
    BUYER_CONFIRMED = "BUYER_CONFIRMED"
    PROBLEM_EVIDENCE_CONFIRMED = "PROBLEM_EVIDENCE_CONFIRMED"
    OFFER_APPROVED = "OFFER_APPROVED"
    OUTREACH_AUTHORIZED = "OUTREACH_AUTHORIZED"
    BUYER_COMMITMENT = "BUYER_COMMITMENT"
    PAYMENT_OR_BINDING_COMMITMENT = "PAYMENT_OR_BINDING_COMMITMENT"
    DELIVERY_AUTHORIZED = "DELIVERY_AUTHORIZED"
    DELIVERY_COMPLETED = "DELIVERY_COMPLETED"
    CUSTOMER_ACCEPTANCE = "CUSTOMER_ACCEPTANCE"
    OUTCOME_OBSERVED = "OUTCOME_OBSERVED"
    ECONOMICS_RECONCILED = "ECONOMICS_RECONCILED"
    DECISION_RETAIN = "DECISION_RETAIN"
    DECISION_MODIFY = "DECISION_MODIFY"
    DECISION_KILL = "DECISION_KILL"
    CAPABILITY_GENOME_SEALED = "CAPABILITY_GENOME_SEALED"


LINEAR_STAGES = (
    CommercialStage.QUALIFIED_SIGNAL,
    CommercialStage.BUYER_CONFIRMED,
    CommercialStage.PROBLEM_EVIDENCE_CONFIRMED,
    CommercialStage.OFFER_APPROVED,
    CommercialStage.OUTREACH_AUTHORIZED,
    CommercialStage.BUYER_COMMITMENT,
    CommercialStage.PAYMENT_OR_BINDING_COMMITMENT,
    CommercialStage.DELIVERY_AUTHORIZED,
    CommercialStage.DELIVERY_COMPLETED,
    CommercialStage.CUSTOMER_ACCEPTANCE,
    CommercialStage.OUTCOME_OBSERVED,
    CommercialStage.ECONOMICS_RECONCILED,
)

REQUIRED_PAYLOAD_FIELDS = {
    CommercialStage.BUYER_CONFIRMED: ("buyer_ref",),
    CommercialStage.PROBLEM_EVIDENCE_CONFIRMED: ("problem_evidence_ref",),
    CommercialStage.OFFER_APPROVED: ("offer_ref", "human_approval_ref"),
    CommercialStage.OUTREACH_AUTHORIZED: ("human_approval_ref", "gate_receipt_hash"),
    CommercialStage.BUYER_COMMITMENT: ("commitment_ref",),
    CommercialStage.PAYMENT_OR_BINDING_COMMITMENT: ("payment_or_contract_ref", "payment_usd"),
    CommercialStage.DELIVERY_AUTHORIZED: ("human_approval_ref", "gate_receipt_hash"),
    CommercialStage.DELIVERY_COMPLETED: ("delivery_receipt_ref",),
    CommercialStage.CUSTOMER_ACCEPTANCE: ("acceptance_ref",),
    CommercialStage.OUTCOME_OBSERVED: ("outcome_ref", "externally_verified"),
    CommercialStage.ECONOMICS_RECONCILED: (
        "reconciliation_ref", "contribution_margin_usd", "founder_hours",
    ),
}


@dataclass(frozen=True)
class CommercialTransition:
    from_stage: CommercialStage
    to_stage: CommercialStage
    actor: str
    evidence_refs: tuple[str, ...]
    payload: dict[str, Any]


@dataclass
class CommercialCase:
    case_id: str
    opportunity_id: str
    opportunity_digest: str
    architecture_hash: str
    legal_operator: str
    stage: CommercialStage = CommercialStage.QUALIFIED_SIGNAL
    transitions: list[CommercialTransition] = field(default_factory=list)
    decision: str | None = None
    sealed_genome_key: str | None = None


class CommercialClosureCompiler:
    def __init__(self, ledger: Any | None = None) -> None:
        self.ledger = ledger
        self._cases: dict[str, CommercialCase] = {}
        if ledger is not None:
            self.rebuild_from_ledger()

    def _record(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.ledger is not None:
            self.ledger.append("event", {"type": event_type, **payload})

    def open_case(self, opportunity: OpportunitySpec, architecture: AdvantageArchitecture) -> CommercialCase:
        opportunity.validate()
        if architecture.opportunity_digest != opportunity.digest:
            raise FoundryError("architecture does not belong to opportunity")
        seed = f"{opportunity.opportunity_id}|{opportunity.digest}|{architecture.digest}"
        case_id = "commercial-" + sha256(seed.encode()).hexdigest()[:16]
        existing = self._cases.get(case_id)
        if existing is not None:
            return existing
        case = CommercialCase(
            case_id=case_id,
            opportunity_id=opportunity.opportunity_id,
            opportunity_digest=opportunity.digest,
            architecture_hash=architecture.digest,
            legal_operator=opportunity.legal_operator,
        )
        self._cases[case_id] = case
        self._record("commercial.case_opened", {
            "case_id": case.case_id,
            "opportunity_id": case.opportunity_id,
            "opportunity_digest": case.opportunity_digest,
            "architecture_hash": case.architecture_hash,
            "legal_operator": case.legal_operator,
            "stage": case.stage.value,
        })
        return case

    def advance(
        self,
        case_id: str,
        to_stage: CommercialStage,
        *,
        actor: str,
        evidence_refs: tuple[str, ...],
        payload: Mapping[str, Any],
    ) -> CommercialCase:
        case = self._require_case(case_id)
        if case.stage not in LINEAR_STAGES:
            raise FoundryError("terminal or decision stage cannot advance linearly")
        current_index = LINEAR_STAGES.index(case.stage)
        if current_index + 1 >= len(LINEAR_STAGES) or LINEAR_STAGES[current_index + 1] is not to_stage:
            raise FoundryError(f"cannot skip from {case.stage.value} to {to_stage.value}")
        if not actor or actor in {"UNIIMENTE", "OMNIMORPH", "foundry"}:
            raise FoundryError("an accountable actor is required")
        if not evidence_refs or any(not str(ref).strip() for ref in evidence_refs):
            raise FoundryError("every commercial transition requires evidence")
        data = dict(payload)
        for key in REQUIRED_PAYLOAD_FIELDS[to_stage]:
            if key not in data or data[key] in (None, ""):
                raise FoundryError(f"{key} is required for {to_stage.value}")
        if to_stage in {CommercialStage.OUTREACH_AUTHORIZED, CommercialStage.DELIVERY_AUTHORIZED}:
            self._require_hash(data["gate_receipt_hash"], "gate_receipt_hash")
        if to_stage is CommercialStage.PAYMENT_OR_BINDING_COMMITMENT:
            try:
                payment = float(data["payment_usd"])
            except (TypeError, ValueError) as exc:
                raise FoundryError("payment_usd must be numeric") from exc
            if payment <= 0:
                raise FoundryError("payment or binding economic commitment must be positive")
            data["payment_usd"] = payment
        if to_stage is CommercialStage.OUTCOME_OBSERVED and data["externally_verified"] is not True:
            raise FoundryError("outcome must be externally verified")
        if to_stage is CommercialStage.ECONOMICS_RECONCILED:
            for key in ("contribution_margin_usd", "founder_hours"):
                try:
                    data[key] = float(data[key])
                except (TypeError, ValueError) as exc:
                    raise FoundryError(f"{key} must be numeric") from exc
            if data["founder_hours"] < 0:
                raise FoundryError("founder_hours cannot be negative")

        transition = CommercialTransition(case.stage, to_stage, actor, tuple(evidence_refs), data)
        case.transitions.append(transition)
        case.stage = to_stage
        self._record("commercial.stage_advanced", {
            "case_id": case.case_id,
            "from_stage": transition.from_stage.value,
            "to_stage": transition.to_stage.value,
            "actor": actor,
            "evidence_refs": list(transition.evidence_refs),
            "payload": data,
        })
        return case

    def decide(
        self,
        case_id: str,
        decision: str,
        *,
        actor: str,
        evidence_ref: str,
        human_approval_ref: str,
    ) -> CommercialCase:
        case = self._require_case(case_id)
        if case.stage is not CommercialStage.ECONOMICS_RECONCILED:
            raise FoundryError("decision requires reconciled economics")
        normalized = decision.upper()
        stages = {
            "RETAIN": CommercialStage.DECISION_RETAIN,
            "MODIFY": CommercialStage.DECISION_MODIFY,
            "KILL": CommercialStage.DECISION_KILL,
        }
        if normalized not in stages:
            raise FoundryError("decision must be RETAIN, MODIFY, or KILL")
        if not actor or actor in {"UNIIMENTE", "OMNIMORPH", "foundry"}:
            raise FoundryError("an accountable decision actor is required")
        if not evidence_ref or not human_approval_ref:
            raise FoundryError("decision evidence and human approval are required")
        case.decision = normalized
        case.stage = stages[normalized]
        self._record("commercial.decision_recorded", {
            "case_id": case.case_id,
            "decision": normalized,
            "stage": case.stage.value,
            "actor": actor,
            "evidence_ref": evidence_ref,
            "human_approval_ref": human_approval_ref,
        })
        return case

    def build_external_outcome(self, case_id: str) -> ExternalOutcome:
        case = self._require_case(case_id)
        if case.stage not in {
            CommercialStage.ECONOMICS_RECONCILED,
            CommercialStage.DECISION_RETAIN,
            CommercialStage.DECISION_MODIFY,
            CommercialStage.DECISION_KILL,
            CommercialStage.CAPABILITY_GENOME_SEALED,
        }:
            raise FoundryError("commercial case has not reached reconciled economics")
        by_stage = {transition.to_stage: transition for transition in case.transitions}
        payment = by_stage[CommercialStage.PAYMENT_OR_BINDING_COMMITMENT].payload["payment_usd"]
        economics = by_stage[CommercialStage.ECONOMICS_RECONCILED].payload
        receipts = []
        for transition in case.transitions:
            receipts.extend(transition.evidence_refs)
        return ExternalOutcome(
            payment_usd=float(payment),
            accepted_delivery=CommercialStage.CUSTOMER_ACCEPTANCE in by_stage,
            externally_verified=bool(by_stage[CommercialStage.OUTCOME_OBSERVED].payload["externally_verified"]),
            contribution_margin_usd=float(economics["contribution_margin_usd"]),
            founder_hours=float(economics["founder_hours"]),
            reconciliation_closed=True,
            metric_results=dict(economics.get("metric_results") or {}),
            receipt_refs=tuple(dict.fromkeys(receipts)),
        )

    def mark_genome_sealed(
        self,
        case_id: str,
        *,
        genome_key: str,
        actor: str,
        seal_record_hash: str,
    ) -> CommercialCase:
        case = self._require_case(case_id)
        if case.stage is not CommercialStage.DECISION_RETAIN:
            raise FoundryError("only a RETAIN decision may seal a Capability Genome")
        if not genome_key or not actor:
            raise FoundryError("genome key and accountable actor are required")
        self._require_hash(seal_record_hash, "seal_record_hash")
        case.sealed_genome_key = genome_key
        case.stage = CommercialStage.CAPABILITY_GENOME_SEALED
        self._record("commercial.genome_sealed", {
            "case_id": case.case_id,
            "genome_key": genome_key,
            "actor": actor,
            "seal_record_hash": seal_record_hash,
            "stage": case.stage.value,
        })
        return case

    def get(self, case_id: str) -> CommercialCase | None:
        return self._cases.get(case_id)

    def rebuild_from_ledger(self) -> None:
        self._cases.clear()
        for record in self.ledger.by_type("event"):
            payload = record.payload
            event_type = payload.get("type")
            if event_type == "commercial.case_opened":
                self._cases[payload["case_id"]] = CommercialCase(
                    case_id=payload["case_id"],
                    opportunity_id=payload["opportunity_id"],
                    opportunity_digest=payload["opportunity_digest"],
                    architecture_hash=payload["architecture_hash"],
                    legal_operator=payload["legal_operator"],
                    stage=CommercialStage(payload["stage"]),
                )
            elif event_type == "commercial.stage_advanced" and payload.get("case_id") in self._cases:
                case = self._cases[payload["case_id"]]
                transition = CommercialTransition(
                    CommercialStage(payload["from_stage"]),
                    CommercialStage(payload["to_stage"]),
                    payload["actor"],
                    tuple(payload["evidence_refs"]),
                    dict(payload["payload"]),
                )
                case.transitions.append(transition)
                case.stage = transition.to_stage
            elif event_type == "commercial.decision_recorded" and payload.get("case_id") in self._cases:
                case = self._cases[payload["case_id"]]
                case.decision = payload["decision"]
                case.stage = CommercialStage(payload["stage"])
            elif event_type == "commercial.genome_sealed" and payload.get("case_id") in self._cases:
                case = self._cases[payload["case_id"]]
                case.sealed_genome_key = payload["genome_key"]
                case.stage = CommercialStage(payload["stage"])

    def _require_case(self, case_id: str) -> CommercialCase:
        case = self._cases.get(case_id)
        if case is None:
            raise FoundryError("unknown commercial case")
        return case

    @staticmethod
    def _require_hash(value: Any, field_name: str) -> str:
        value = str(value or "")
        if not value.startswith("sha256:") or len(value) != 71:
            raise FoundryError(f"{field_name} must be a canonical sha256 reference")
        return value


__all__ = [
    "CommercialCase",
    "CommercialClosureCompiler",
    "CommercialStage",
    "CommercialTransition",
]
