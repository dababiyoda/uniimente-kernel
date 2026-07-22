"""Contracts for the capital-light Venture Scout.

The Scout does not build commodity infrastructure by default. It compiles a
bounded market experiment, preserves evidence, and promotes proprietary build
work only after paid outcomes expose a repeated strategic bottleneck.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ScoutError(ValueError):
    """A Venture Scout contract or lifecycle transition failed closed."""


class ScoutStage(str, Enum):
    DRAFT = "draft"
    SIGNAL_TEST = "signal_test"
    COMMITMENT_TEST = "commitment_test"
    CONCIERGE_DELIVERY = "concierge_delivery"
    THIN_PRODUCT = "thin_product"
    REINVESTMENT_READY = "reinvestment_ready"
    KILLED = "killed"


class EvidenceKind(str, Enum):
    WAITLIST = "waitlist"
    INTERVIEW = "interview"
    LETTER_OF_INTENT = "letter_of_intent"
    DEPOSIT = "deposit"
    PAYMENT = "payment"
    ACCEPTED_OUTCOME = "accepted_outcome"
    REFUND = "refund"
    COST_RECEIPT = "cost_receipt"


class SourcingDecision(str, Enum):
    RENT = "rent"
    PARTNER = "partner"
    BUILD = "build"
    DO_NOTHING = "do_nothing"


REQUIRED_PROHIBITIONS = frozenset({
    "deception",
    "fabricated_evidence",
    "unauthorized_external_effect",
})


@dataclass(frozen=True)
class EvidenceRecord:
    kind: EvidenceKind
    ref: str
    detail: str
    amount_usd: float = 0.0
    externally_verified: bool = False

    def __post_init__(self) -> None:
        if not self.ref.startswith("sha256:") or len(self.ref) != 71:
            raise ScoutError("evidence ref must be sha256:<64 lowercase-or-uppercase hex characters>")
        try:
            int(self.ref.removeprefix("sha256:"), 16)
        except ValueError as exc:
            raise ScoutError("evidence ref contains non-hex characters") from exc
        if not self.detail.strip():
            raise ScoutError("evidence detail is required")
        if self.amount_usd < 0:
            raise ScoutError("evidence amount may not be negative")


@dataclass(frozen=True)
class VentureExperimentSpec:
    name: str
    problem: str
    beneficiary: str
    buyer_hypothesis: str
    offer: str
    success_metric: str
    baseline: float
    target: float
    max_budget_usd: float
    legal_operator: str
    kill_condition: str
    prohibited_actions: list[str]
    external_effects_allowed: bool = False

    def validate(self) -> None:
        for field_name in (
            "name", "problem", "beneficiary", "buyer_hypothesis", "offer",
            "success_metric", "legal_operator", "kill_condition",
        ):
            if not str(getattr(self, field_name)).strip():
                raise ScoutError(f"experiment missing {field_name}")
        if self.legal_operator == "UNIIMENTE":
            raise ScoutError("UNIIMENTE is never the legal operator")
        if self.max_budget_usd <= 0:
            raise ScoutError("experiment budget must be positive")
        if self.target <= self.baseline:
            raise ScoutError("target must improve on baseline")
        if self.external_effects_allowed:
            raise ScoutError("Scout experiments compile proposals only; external effects remain Gate-bound")
        missing = REQUIRED_PROHIBITIONS.difference(self.prohibited_actions)
        if missing:
            raise ScoutError(f"experiment missing permanent prohibitions: {sorted(missing)}")


@dataclass
class VentureExperiment:
    experiment_id: str
    spec: VentureExperimentSpec
    stage: ScoutStage = ScoutStage.DRAFT
    spend_usd: float = 0.0
    revenue_usd: float = 0.0
    evidence: list[EvidenceRecord] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    killed_reason: str | None = None

    @property
    def contribution_margin_usd(self) -> float:
        return round(self.revenue_usd - self.spend_usd, 2)

    @property
    def remaining_budget_usd(self) -> float:
        return round(self.spec.max_budget_usd - self.spend_usd, 2)


@dataclass(frozen=True)
class SourcingCase:
    capability_name: str
    paid_outcomes: int
    repeated_profitable_uses: int
    cross_venture_reuse_count: int
    vendor_cost_share: float
    commodity_vendor_available: bool = True
    privacy_or_regulatory_need: bool = False
    reliability_gap: bool = False
    strategic_control_point: bool = False
    switching_risk: bool = False

    def validate(self) -> None:
        if not self.capability_name.strip():
            raise ScoutError("capability name is required")
        for name in ("paid_outcomes", "repeated_profitable_uses", "cross_venture_reuse_count"):
            if getattr(self, name) < 0:
                raise ScoutError(f"{name} may not be negative")
        if not 0 <= self.vendor_cost_share <= 1:
            raise ScoutError("vendor_cost_share must be between 0 and 1")


@dataclass(frozen=True)
class SourcingVerdict:
    decision: SourcingDecision
    reasons: tuple[str, ...]
    build_score: int
