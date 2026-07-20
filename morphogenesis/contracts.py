"""Contracts for the UNIIMENTE Morphogenetic Control Layer.

The biological language is a coordination metaphor. These contracts are the
machine boundary: goals are measurable, observations require provenance,
actions remain bounded, and descendant cells can request ratification but can
never self-activate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


CONSEQUENCE_CLASSES = (
    "read_only",
    "internal_write",
    "external_contact",
    "financial",
    "irreversible",
)

REQUIRED_CLOSURE_METRICS = frozenset(
    {
        "payment_usd",
        "delivery_accepted",
        "external_outcome_verified",
        "contribution_margin_usd",
        "clean_completion_rate",
        "unresolved_obligations",
        "critical_authority_incidents",
        "participant_harm_incidents",
        "founder_hours",
        "spend_usd",
    }
)


class Direction(str, Enum):
    GTE = "gte"
    LTE = "lte"
    EQ = "eq"


class AssessmentState(str, Enum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    TARGET_NOT_REACHED = "TARGET_NOT_REACHED"
    TARGET_REACHED_NOT_AUTHORIZED = "TARGET_REACHED_NOT_AUTHORIZED"


@dataclass(frozen=True)
class MetricTarget:
    name: str
    direction: Direction
    target: float | bool
    weight: float = 1.0
    hard: bool = True
    unit: str = ""
    max_age_seconds: int | None = None

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.name:
            problems.append("metric target requires a name")
        if self.weight <= 0:
            problems.append(f"metric {self.name!r} weight must be positive")
        if self.max_age_seconds is not None and self.max_age_seconds <= 0:
            problems.append(f"metric {self.name!r} max_age_seconds must be positive")
        if isinstance(self.target, bool) and self.direction is not Direction.EQ:
            problems.append(f"boolean metric {self.name!r} must use eq")
        return problems


@dataclass(frozen=True)
class StateObservation:
    name: str
    value: float | bool
    observed_at: datetime
    source_ref: str
    confidence: float
    contradicted: bool = False
    natural_denominator: float | None = None

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.name:
            problems.append("observation requires a name")
        if self.observed_at.tzinfo is None:
            problems.append(f"observation {self.name!r} timestamp must be timezone-aware")
        if not self.source_ref:
            problems.append(f"observation {self.name!r} requires provenance source_ref")
        if not 0.0 <= self.confidence <= 1.0:
            problems.append(f"observation {self.name!r} confidence must be between 0 and 1")
        if self.natural_denominator is not None and self.natural_denominator <= 0:
            problems.append(f"observation {self.name!r} natural_denominator must be positive")
        return problems


@dataclass(frozen=True)
class AuthorityEnvelope:
    max_consequence_class: str
    budget_remaining_usd: float
    permitted_actions: tuple[str, ...] = ()
    prohibited_actions: tuple[str, ...] = ()

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.max_consequence_class not in CONSEQUENCE_CLASSES:
            problems.append(f"unknown consequence class {self.max_consequence_class!r}")
        if self.budget_remaining_usd < 0:
            problems.append("budget remaining may not be negative")
        overlap = set(self.permitted_actions) & set(self.prohibited_actions)
        if overlap:
            problems.append(f"actions cannot be both permitted and prohibited: {sorted(overlap)}")
        return problems


@dataclass(frozen=True)
class MorphogeneticSetPoint:
    setpoint_id: str
    venture_cell: str
    legal_principal: str
    buyer: str
    beneficiary: str
    accepted_artifact: str
    external_consequence: str
    metrics: tuple[MetricTarget, ...]
    budget_ceiling_usd: float
    founder_attention_ceiling_hours: float
    deadline: datetime
    prohibited_actions: tuple[str, ...]
    kill_conditions: tuple[str, ...]
    requires_human_activation: bool = True

    def validate(self) -> list[str]:
        problems: list[str] = []
        for name in (
            "setpoint_id",
            "venture_cell",
            "legal_principal",
            "buyer",
            "beneficiary",
            "accepted_artifact",
            "external_consequence",
        ):
            if not getattr(self, name):
                problems.append(f"missing {name}")
        if self.legal_principal.strip().upper() == "UNIIMENTE":
            problems.append("UNIIMENTE is never a legal principal")
        if self.budget_ceiling_usd < 0:
            problems.append("budget ceiling may not be negative")
        if self.founder_attention_ceiling_hours < 0:
            problems.append("founder attention ceiling may not be negative")
        if self.deadline.tzinfo is None:
            problems.append("deadline must be timezone-aware")
        if not self.kill_conditions:
            problems.append("set-point requires at least one kill condition")
        if not self.prohibited_actions:
            problems.append("set-point requires explicit prohibited actions")
        if not self.requires_human_activation:
            problems.append("venture activation must require a human")

        metric_names = [metric.name for metric in self.metrics]
        if len(metric_names) != len(set(metric_names)):
            problems.append("metric names must be unique")
        missing = sorted(REQUIRED_CLOSURE_METRICS - set(metric_names))
        if missing:
            problems.append(f"missing required closure metrics: {missing}")
        for metric in self.metrics:
            problems.extend(metric.validate())
        return problems


@dataclass(frozen=True)
class CandidateAction:
    action_id: str
    description: str
    consequence_class: str
    estimated_cost_usd: float
    projected_values: dict[str, float | bool]
    requires_human: bool = False
    reversible: bool = True

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.action_id:
            problems.append("candidate action requires action_id")
        if not self.description:
            problems.append(f"action {self.action_id!r} requires description")
        if self.consequence_class not in CONSEQUENCE_CLASSES:
            problems.append(f"action {self.action_id!r} has unknown consequence class")
        if self.estimated_cost_usd < 0:
            problems.append(f"action {self.action_id!r} cost may not be negative")
        if self.consequence_class in {"financial", "irreversible"} and not self.requires_human:
            problems.append(f"action {self.action_id!r} must require a human")
        return problems


@dataclass(frozen=True)
class ActionRecommendation:
    action_id: str
    score: float
    reason: str
    requires_gate: bool


@dataclass(frozen=True)
class FieldAssessment:
    state: AssessmentState
    errors: dict[str, float]
    blockers: tuple[str, ...]
    target_reached: bool
    can_request_gate: bool


@dataclass(frozen=True)
class DescendantProposal:
    proposal_id: str
    parent_venture_cell: str
    target_venture_cell: str
    legal_principal: str
    buyer: str
    market_failure: str
    accepted_artifact: str
    external_consequence: str
    required_genomes: tuple[str, ...]
    requested_budget_usd: float
    parent_validation_ref: str
    retention_evidence_ref: str
    reserve_evidence_ref: str
    activation_state: str = "PROPOSED_NOT_EXECUTED"
    requires_human_ratification: bool = True
    consequence_gate_receipt: str | None = None

    def validate(self) -> list[str]:
        problems: list[str] = []
        for name in (
            "proposal_id",
            "parent_venture_cell",
            "target_venture_cell",
            "legal_principal",
            "buyer",
            "market_failure",
            "accepted_artifact",
            "external_consequence",
            "parent_validation_ref",
            "retention_evidence_ref",
            "reserve_evidence_ref",
        ):
            if not getattr(self, name):
                problems.append(f"missing {name}")
        if self.legal_principal.strip().upper() == "UNIIMENTE":
            problems.append("UNIIMENTE is never a legal principal")
        if self.requested_budget_usd < 0:
            problems.append("requested budget may not be negative")
        if not self.required_genomes:
            problems.append("descendant proposal requires at least one Capability Genome")
        if self.activation_state != "PROPOSED_NOT_EXECUTED":
            problems.append("descendant proposal cannot represent an activated cell")
        if not self.requires_human_ratification:
            problems.append("descendant proposal must require human ratification")
        if self.consequence_gate_receipt is not None:
            problems.append("unratified descendant proposal may not contain a Gate receipt")
        return problems


@dataclass(frozen=True)
class ReplicationDecision:
    status: str
    reasons: tuple[str, ...] = field(default_factory=tuple)
    proposal: DescendantProposal | None = None
