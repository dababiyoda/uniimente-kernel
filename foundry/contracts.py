from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json

CONSEQUENCE_CLASSES = ("read_only", "internal_write", "external_contact", "financial", "irreversible")
STRATEGY_ROUTES = (
    "fastest_path", "lowest_capital", "maximum_ownership", "maximum_reversibility",
    "maximum_regeneration", "strongest_partnership", "acquisition", "incumbent_compatible",
    "radical_simplification", "complete_removal", "do_nothing",
)

class FoundryError(ValueError):
    pass

class ClosureState(str, Enum):
    OPEN = "OPEN"
    PARTIALLY_CLOSED = "PARTIALLY_CLOSED"
    FALSELY_CLOSED = "FALSELY_CLOSED"
    CLOSED = "CLOSED"

@dataclass(frozen=True)
class OpportunitySpec:
    opportunity_id: str
    buyer: str
    beneficiary: str
    pain_owner: str
    budget_owner: str
    recurring_transaction: str
    broken_state: str
    trapped_value_usd: float
    accepted_artifact: str
    external_consequence: str
    lawful_path: str
    evidence_refs: tuple[str, ...]
    legal_operator: str = "alfonso_lopez"
    constraints: tuple[str, ...] = ()
    prohibitions: tuple[str, ...] = ()

    def validate(self) -> None:
        required = (
            self.opportunity_id, self.buyer, self.beneficiary, self.pain_owner,
            self.budget_owner, self.recurring_transaction, self.broken_state,
            self.accepted_artifact, self.external_consequence, self.lawful_path,
            self.legal_operator,
        )
        if any(not value for value in required):
            raise FoundryError("opportunity is missing a governing transaction field")
        if self.legal_operator == "UNIIMENTE":
            raise FoundryError("UNIIMENTE is never the legal operator")
        if self.trapped_value_usd < 0:
            raise FoundryError("trapped value cannot be negative")
        if not self.evidence_refs:
            raise FoundryError("external evidence is required")

    @property
    def digest(self) -> str:
        payload = json.dumps(self.__dict__, sort_keys=True, default=list, separators=(",", ":"))
        return "sha256:" + sha256(payload.encode()).hexdigest()

@dataclass(frozen=True)
class CapabilityNeed:
    capability: str
    purpose: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    consequence_class: str
    budget_usd: float
    required: bool = True

    def validate(self) -> None:
        if not self.capability or not self.purpose or not self.inputs or not self.outputs:
            raise FoundryError("capability need is incomplete")
        if self.consequence_class not in CONSEQUENCE_CLASSES:
            raise FoundryError("unknown consequence class")
        if self.budget_usd < 0:
            raise FoundryError("capability budget cannot be negative")

@dataclass(frozen=True)
class StrategyBranch:
    route: str
    mechanism: str
    governing_assumption: str
    strongest_counterargument: str
    cheapest_falsification_test: str
    kill_condition: str
    cost_usd: float
    time_to_proof_days: int
    expected_value_usd: float
    reversibility: float
    evidence_quality: float
    founder_hours: float
    required_capabilities: tuple[str, ...]

    def validate(self) -> None:
        if self.route not in STRATEGY_ROUTES:
            raise FoundryError(f"unknown strategy route: {self.route}")
        if any(not x for x in (
            self.mechanism, self.governing_assumption, self.strongest_counterargument,
            self.cheapest_falsification_test, self.kill_condition,
        )):
            raise FoundryError("strategy branch is incomplete")
        if self.cost_usd < 0 or self.time_to_proof_days < 0 or self.founder_hours < 0:
            raise FoundryError("strategy branch resource values cannot be negative")
        if not 0 <= self.reversibility <= 1 or not 0 <= self.evidence_quality <= 1:
            raise FoundryError("strategy branch scores must be between zero and one")

    @property
    def score(self) -> float:
        denominator = 1 + self.cost_usd + 100 * self.founder_hours + 50 * self.time_to_proof_days
        return (max(self.expected_value_usd, 0) * (0.5 + self.reversibility) * (0.5 + self.evidence_quality)) / denominator

@dataclass(frozen=True)
class AdvantageArchitecture:
    architecture_id: str
    opportunity_digest: str
    selected_route: str
    accepted_artifact: str
    external_consequence: str
    control_surface: str
    capability_needs: tuple[CapabilityNeed, ...]
    success_metrics: tuple[str, ...]
    kill_conditions: tuple[str, ...]
    legal_operator: str

    @property
    def digest(self) -> str:
        payload = json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, separators=(",", ":"))
        return "sha256:" + sha256(payload.encode()).hexdigest()

@dataclass(frozen=True)
class ExternalOutcome:
    payment_usd: float
    accepted_delivery: bool
    externally_verified: bool
    contribution_margin_usd: float
    founder_hours: float
    reconciliation_closed: bool
    metric_results: dict[str, float] = field(default_factory=dict)
    receipt_refs: tuple[str, ...] = ()

@dataclass(frozen=True)
class AdvantageGenome:
    name: str
    version: str
    architecture_hash: str
    capability_versions: tuple[str, ...]
    payment_proof: tuple[str, ...]
    outcome_proof: tuple[str, ...]
    contribution_margin_usd: float
    time_to_validated_genome_days: int
    founder_hours: float
    legal_operator: str
    rollback: str
    kill_conditions: tuple[str, ...]

    @property
    def key(self) -> str:
        return f"{self.name}@{self.version}"
