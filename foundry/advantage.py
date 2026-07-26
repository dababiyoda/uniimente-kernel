"""Qualified opportunity, eleven-route strategy, architecture, and Genome sealing.

The Advantage Foundry manufactures proposals and reusable competence. It
never grants authority or invents external evidence. A sealed Advantage
Genome is an immutable asset created only after economic commitment,
accepted delivery, externally verified outcome, closed reconciliation,
nonnegative contribution margin, clean authority state, and receipt lineage.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Any, Iterable

STRATEGY_ROUTES = (
    "fastest_path",
    "lowest_capital",
    "maximum_ownership",
    "maximum_reversibility",
    "maximum_regeneration",
    "strongest_partnership",
    "acquisition",
    "incumbent_compatible",
    "radical_simplification",
    "complete_removal",
    "do_nothing",
)
CONSEQUENCE_CLASSES = (
    "read_only", "internal_write", "external_contact", "financial", "irreversible",
)


class AdvantageRefused(ValueError):
    """The Foundry refuses incomplete, changed, or falsely closed work."""


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
    mandate_actor: str
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
            self.budget_owner, self.mandate_actor, self.recurring_transaction,
            self.broken_state, self.accepted_artifact, self.external_consequence,
            self.lawful_path, self.legal_operator,
        )
        if any(not value for value in required):
            raise AdvantageRefused("opportunity is missing a governing transaction field")
        if self.legal_operator == "UNIIMENTE":
            raise AdvantageRefused("UNIIMENTE is never the legal operator")
        if self.trapped_value_usd < 0:
            raise AdvantageRefused("trapped value cannot be negative")
        if not self.evidence_refs:
            raise AdvantageRefused("external evidence is required")

    @property
    def digest(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
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
            raise AdvantageRefused("capability need is incomplete")
        if self.consequence_class not in CONSEQUENCE_CLASSES:
            raise AdvantageRefused("unknown consequence class")
        if self.budget_usd < 0:
            raise AdvantageRefused("capability budget cannot be negative")


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
            raise AdvantageRefused(f"unknown strategy route: {self.route}")
        if any(not value for value in (
            self.mechanism, self.governing_assumption, self.strongest_counterargument,
            self.cheapest_falsification_test, self.kill_condition,
        )):
            raise AdvantageRefused("strategy branch is incomplete")
        if self.cost_usd < 0 or self.time_to_proof_days < 0 or self.founder_hours < 0:
            raise AdvantageRefused("strategy resource values cannot be negative")
        if not 0 <= self.reversibility <= 1 or not 0 <= self.evidence_quality <= 1:
            raise AdvantageRefused("strategy scores must be between zero and one")

    @property
    def score(self) -> float:
        denominator = 1 + self.cost_usd + 100 * self.founder_hours + 50 * self.time_to_proof_days
        return (
            max(self.expected_value_usd, 0)
            * (0.5 + self.reversibility)
            * (0.5 + self.evidence_quality)
            / denominator
        )


@dataclass(frozen=True)
class AdvantageArchitecture:
    architecture_id: str
    opportunity_digest: str
    selected_route: str
    accepted_artifact: str
    external_consequence: str
    control_surfaces: tuple[str, ...]
    capability_needs: tuple[CapabilityNeed, ...]
    success_metrics: tuple[str, ...]
    kill_conditions: tuple[str, ...]
    legal_operator: str
    selected_branch_digest: str

    @property
    def digest(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return "sha256:" + sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class ExternalOutcome:
    economic_commitment_usd: float
    accepted_delivery: bool
    externally_verified: bool
    contribution_margin_usd: float
    founder_hours: float
    reconciliation_closed: bool
    authority_incidents: int = 0
    critical_participant_harm_incidents: int = 0
    metric_results: dict[str, float] = field(default_factory=dict)
    receipt_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class SealedAdvantageGenome:
    name: str
    version: str
    architecture_hash: str
    composition_plan_id: str
    capability_versions: tuple[str, ...]
    economic_proof: tuple[str, ...]
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


class AdvantageFoundry:
    """Manufacture architectures and seal paid, evidenced capabilities."""

    def __init__(self, ledger: Any | None = None) -> None:
        self.ledger = ledger
        self._opportunity_digests: dict[str, str] = {}
        self._opportunities: dict[str, OpportunitySpec] = {}
        self._architectures: dict[str, AdvantageArchitecture] = {}
        self._genomes: dict[str, SealedAdvantageGenome] = {}
        if ledger is not None:
            self.rebuild_from_ledger()

    def _record(self, event_type: str, payload: dict) -> None:
        if self.ledger is not None:
            self.ledger.append("event", {"type": event_type, **payload})

    @staticmethod
    def _opportunity_from_data(data: dict[str, Any]) -> OpportunitySpec:
        raw = dict(data)
        for key in ("evidence_refs", "constraints", "prohibitions"):
            raw[key] = tuple(raw.get(key) or ())
        opportunity = OpportunitySpec(**raw)
        opportunity.validate()
        return opportunity

    @staticmethod
    def _architecture_from_data(data: dict[str, Any]) -> AdvantageArchitecture:
        raw = dict(data)
        raw["capability_needs"] = tuple(
            CapabilityNeed(**dict(item)) for item in raw.get("capability_needs") or ()
        )
        for key in ("control_surfaces", "success_metrics", "kill_conditions"):
            raw[key] = tuple(raw.get(key) or ())
        architecture = AdvantageArchitecture(**raw)
        for need in architecture.capability_needs:
            need.validate()
        return architecture

    def rebuild_from_ledger(self) -> None:
        self._opportunity_digests.clear()
        self._opportunities.clear()
        self._architectures.clear()
        self._genomes.clear()
        for record in self.ledger.by_type("event"):
            payload = record.payload
            event_type = payload.get("type")
            if event_type == "advantage.opportunity_intake":
                opportunity_id = payload["opportunity_id"]
                self._opportunity_digests[opportunity_id] = payload["opportunity_digest"]
                if isinstance(payload.get("opportunity"), dict):
                    opportunity = self._opportunity_from_data(payload["opportunity"])
                    if opportunity.digest != payload["opportunity_digest"]:
                        raise AdvantageRefused("ledgered opportunity digest mismatch")
                    self._opportunities[opportunity_id] = opportunity
            elif event_type == "advantage.architecture_compiled":
                if isinstance(payload.get("architecture"), dict):
                    architecture = self._architecture_from_data(payload["architecture"])
                    if architecture.digest != payload["architecture_digest"]:
                        raise AdvantageRefused("ledgered architecture digest mismatch")
                    self._architectures[architecture.architecture_id] = architecture
            elif event_type == "advantage.genome_sealed":
                raw = dict(payload["genome"])
                for key in ("capability_versions", "economic_proof", "outcome_proof", "kill_conditions"):
                    raw[key] = tuple(raw.get(key) or ())
                genome = SealedAdvantageGenome(**raw)
                self._genomes[genome.key] = genome

    def intake(self, opportunity: OpportunitySpec) -> OpportunitySpec:
        opportunity.validate()
        prior = self._opportunity_digests.get(opportunity.opportunity_id)
        if prior is not None and prior != opportunity.digest:
            self._record("advantage.opportunity_replay_refused", {
                "opportunity_id": opportunity.opportunity_id,
                "prior_digest": prior,
                "attempted_digest": opportunity.digest,
            })
            raise AdvantageRefused("changed-content replay for an existing opportunity id")
        if prior is None:
            self._opportunity_digests[opportunity.opportunity_id] = opportunity.digest
            self._opportunities[opportunity.opportunity_id] = opportunity
            self._record("advantage.opportunity_intake", {
                "opportunity_id": opportunity.opportunity_id,
                "opportunity_digest": opportunity.digest,
                "legal_operator": opportunity.legal_operator,
                "opportunity": asdict(opportunity),
            })
        return opportunity

    def complete_route_tournament(
        self, branches: Iterable[StrategyBranch]
    ) -> tuple[StrategyBranch, tuple[StrategyBranch, ...]]:
        branch_list = tuple(branches)
        for branch in branch_list:
            branch.validate()
        routes = [branch.route for branch in branch_list]
        if set(routes) != set(STRATEGY_ROUTES) or len(routes) != len(STRATEGY_ROUTES):
            raise AdvantageRefused("all eleven strategy routes must appear exactly once")
        winner = max(
            branch_list,
            key=lambda branch: (
                branch.score, -branch.cost_usd, -branch.time_to_proof_days, branch.route,
            ),
        )
        losers = tuple(branch for branch in branch_list if branch.route != winner.route)
        self._record("advantage.route_tournament_completed", {
            "winner": winner.route,
            "winner_score": winner.score,
            "winning_branch": asdict(winner),
            "rejected_branches": [asdict(branch) for branch in losers],
        })
        return winner, losers

    def compile_architecture(
        self,
        opportunity: OpportunitySpec,
        winner: StrategyBranch,
        capability_needs: Iterable[CapabilityNeed],
        *,
        control_surfaces: tuple[str, ...],
        success_metrics: tuple[str, ...],
        kill_conditions: tuple[str, ...],
    ) -> AdvantageArchitecture:
        self.intake(opportunity)
        winner.validate()
        needs = tuple(capability_needs)
        if not needs:
            raise AdvantageRefused("architecture requires capabilities")
        for need in needs:
            need.validate()
        if not control_surfaces or not success_metrics or not kill_conditions:
            raise AdvantageRefused("control surfaces, metrics, and kill conditions are required")
        branch_digest = "sha256:" + sha256(
            json.dumps(asdict(winner), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        seed = f"{opportunity.digest}|{winner.route}|{'|'.join(sorted(control_surfaces))}"
        architecture = AdvantageArchitecture(
            architecture_id="adv-" + sha256(seed.encode()).hexdigest()[:16],
            opportunity_digest=opportunity.digest,
            selected_route=winner.route,
            accepted_artifact=opportunity.accepted_artifact,
            external_consequence=opportunity.external_consequence,
            control_surfaces=tuple(sorted(set(control_surfaces))),
            capability_needs=needs,
            success_metrics=success_metrics,
            kill_conditions=kill_conditions,
            legal_operator=opportunity.legal_operator,
            selected_branch_digest=branch_digest,
        )
        existing = self._architectures.get(architecture.architecture_id)
        if existing is not None and existing.digest != architecture.digest:
            raise AdvantageRefused("architecture id collision with different content")
        self._architectures[architecture.architecture_id] = architecture
        self._record("advantage.architecture_compiled", {
            "architecture_id": architecture.architecture_id,
            "architecture_digest": architecture.digest,
            "opportunity_digest": opportunity.digest,
            "selected_route": winner.route,
            "capabilities": [need.capability for need in needs],
            "architecture": asdict(architecture),
        })
        return architecture

    @staticmethod
    def closure_state(outcome: ExternalOutcome | None) -> ClosureState:
        if outcome is None:
            return ClosureState.OPEN
        if outcome.economic_commitment_usd > 0 and not outcome.externally_verified:
            return ClosureState.FALSELY_CLOSED
        if outcome.externally_verified and outcome.economic_commitment_usd <= 0:
            return ClosureState.PARTIALLY_CLOSED
        if (
            outcome.economic_commitment_usd > 0
            and outcome.accepted_delivery
            and outcome.externally_verified
            and outcome.reconciliation_closed
            and outcome.contribution_margin_usd >= 0
            and outcome.authority_incidents == 0
            and outcome.critical_participant_harm_incidents == 0
            and outcome.receipt_refs
        ):
            return ClosureState.CLOSED
        return ClosureState.PARTIALLY_CLOSED

    def seal_advantage_genome(
        self,
        name: str,
        version: str,
        architecture: AdvantageArchitecture,
        composition_plan_id: str,
        capability_versions: tuple[str, ...],
        outcome: ExternalOutcome,
        *,
        time_to_validated_genome_days: int,
        rollback: str,
    ) -> SealedAdvantageGenome:
        stored = self._architectures.get(architecture.architecture_id)
        if stored is None or stored.digest != architecture.digest:
            raise AdvantageRefused("cannot seal an unknown or changed architecture")
        closure = self.closure_state(outcome)
        self._record("advantage.closure_evaluated", {
            "architecture_digest": architecture.digest,
            "closure_state": closure.value,
            "economic_commitment_usd": outcome.economic_commitment_usd,
            "externally_verified": outcome.externally_verified,
            "reconciliation_closed": outcome.reconciliation_closed,
            "authority_incidents": outcome.authority_incidents,
            "critical_participant_harm_incidents": outcome.critical_participant_harm_incidents,
        })
        if closure is not ClosureState.CLOSED:
            raise AdvantageRefused("only a clean closed external outcome may seal a Genome")
        if time_to_validated_genome_days < 0 or not rollback or not composition_plan_id:
            raise AdvantageRefused("valid TVG, Composition Plan, and rollback are required")
        genome = SealedAdvantageGenome(
            name=name,
            version=version,
            architecture_hash=architecture.digest,
            composition_plan_id=composition_plan_id,
            capability_versions=capability_versions,
            economic_proof=outcome.receipt_refs,
            outcome_proof=outcome.receipt_refs,
            contribution_margin_usd=outcome.contribution_margin_usd,
            time_to_validated_genome_days=time_to_validated_genome_days,
            founder_hours=outcome.founder_hours,
            legal_operator=architecture.legal_operator,
            rollback=rollback,
            kill_conditions=architecture.kill_conditions,
        )
        if genome.key in self._genomes:
            raise AdvantageRefused("Genome version already exists; publish a new immutable version")
        self._genomes[genome.key] = genome
        self._record("advantage.genome_sealed", {"genome": asdict(genome)})
        return genome

    def get_opportunity(self, opportunity_id: str) -> OpportunitySpec | None:
        return self._opportunities.get(opportunity_id)

    def get_architecture(self, architecture_id: str) -> AdvantageArchitecture | None:
        return self._architectures.get(architecture_id)

    def get_genome(self, name: str, version: str) -> SealedAdvantageGenome | None:
        return self._genomes.get(f"{name}@{version}")
