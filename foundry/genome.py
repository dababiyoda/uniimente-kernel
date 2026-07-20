"""Data contracts for bounded Foundry composition.

An Advantage Genome is a plan and evidence contract. It is never an execution
authority. External effects remain exclusively governed by the Consequence Gate.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

ALLOWED_CONTROL_SURFACES = frozenset({
    "agents", "authority", "capital", "community", "composition",
    "continuity", "coordination", "cost", "customer", "distribution",
    "economics", "eligibility", "incentives", "identity", "knowledge",
    "learning", "marketplace", "measurement", "media", "memory", "payment",
    "proof", "regeneration", "reputation", "resilience", "routing", "search",
    "security", "settlement", "simulation", "software", "sovereignty", "state",
    "strategy", "tools", "trust", "validation", "venture", "workflow",
})

ALLOWED_METRICS = frozenset({
    "revenue", "contribution_margin", "conversion_rate", "time_to_payment",
    "retention_rate", "reliability", "customer_acquisition_cost",
    "founder_minutes", "error_rate", "dispute_rate", "evidence_quality",
    "authorized_completion_rate", "state_continuity", "security_incidents",
})


@dataclass(frozen=True)
class AdvantageRequest:
    market_failure: str
    beneficiaries: tuple[str, ...]
    payer: str
    control_surfaces: tuple[str, ...]
    desired_metrics: tuple[str, ...]
    legal_principal: str = "alfonso_lopez"
    max_budget_usd: float = 0.0
    reversible_required: bool = True
    requested_technology_ids: tuple[int, ...] = ()
    prohibited_technology_ids: tuple[int, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    kill_conditions: tuple[str, ...] = ()

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.market_failure.strip():
            problems.append("market_failure is required")
        if not self.beneficiaries:
            problems.append("at least one beneficiary is required")
        if not self.payer.strip():
            problems.append("payer is required")
        unknown_surfaces = sorted(set(self.control_surfaces) - ALLOWED_CONTROL_SURFACES)
        if unknown_surfaces:
            problems.append(f"unknown control surfaces: {unknown_surfaces}")
        if not self.control_surfaces:
            problems.append("at least one control surface is required")
        unknown_metrics = sorted(set(self.desired_metrics) - ALLOWED_METRICS)
        if unknown_metrics:
            problems.append(f"unknown desired metrics: {unknown_metrics}")
        if not self.desired_metrics:
            problems.append("at least one desired metric is required")
        if self.legal_principal == "UNIIMENTE":
            problems.append("UNIIMENTE is never a legal principal")
        if self.max_budget_usd < 0:
            problems.append("max_budget_usd may not be negative")
        overlap = set(self.requested_technology_ids) & set(self.prohibited_technology_ids)
        if overlap:
            problems.append(f"technologies cannot be both requested and prohibited: {sorted(overlap)}")
        bad_ids = sorted(
            i for i in set(self.requested_technology_ids + self.prohibited_technology_ids)
            if not 1 <= i <= 55
        )
        if bad_ids:
            problems.append(f"technology ids must be within 1..55: {bad_ids}")
        if not self.kill_conditions:
            problems.append("at least one kill condition is required")
        return problems


@dataclass(frozen=True)
class AttachmentStep:
    order: int
    technology_id: int
    operation: str
    consequence_class: str
    requires_human: bool
    reversible: bool
    rollback: str
    acceptance_evidence: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceExperiment:
    hypothesis: str
    prediction: str
    metric: str
    baseline: float | None
    threshold: float
    direction: str
    budget_usd: float
    observation_window: str
    reversible: bool
    rollback: str
    success_next_decision: str
    failure_next_decision: str

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.metric not in ALLOWED_METRICS:
            problems.append(f"unsupported metric {self.metric!r}")
        if self.direction not in ("gte", "lte"):
            problems.append("direction must be gte or lte")
        if self.budget_usd < 0:
            problems.append("budget may not be negative")
        if not self.reversible:
            problems.append("Foundry v0 refuses irreversible experiments")
        if not all((self.hypothesis, self.prediction, self.observation_window, self.rollback)):
            problems.append("experiment fields may not be empty")
        return problems


@dataclass(frozen=True)
class AdvantageGenome:
    genome_id: str
    request_hash: str
    market_failure: str
    control_surfaces: tuple[str, ...]
    selected_technology_ids: tuple[int, ...]
    selected_capability_genomes: tuple[str, ...]
    implementation_status: dict[int, str]
    consequence_class: str
    budget_ceiling_usd: float
    requires_human: bool
    attachment_plan: tuple[AttachmentStep, ...]
    detachment_plan: tuple[AttachmentStep, ...]
    experiment: EvidenceExperiment
    kill_conditions: tuple[str, ...]
    legal_principal: str
    created_at: str
    notes: tuple[str, ...] = ()
    schema_version: str = "0.1.0"

    def canonical_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("genome_id", None)
        return payload

    def verify_id(self) -> bool:
        return self.genome_id == genome_id_for(self.canonical_payload())


def request_hash(request: AdvantageRequest) -> str:
    raw = json.dumps(asdict(request), sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def genome_id_for(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "adv:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "ALLOWED_CONTROL_SURFACES",
    "ALLOWED_METRICS",
    "AdvantageRequest",
    "AttachmentStep",
    "EvidenceExperiment",
    "AdvantageGenome",
    "request_hash",
    "genome_id_for",
    "utc_now",
]
