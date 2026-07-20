from __future__ import annotations

from hashlib import sha256
from typing import Iterable

from .contracts import (
    AdvantageArchitecture, AdvantageGenome, CapabilityNeed, ClosureState,
    ExternalOutcome, FoundryError, OpportunitySpec, StrategyBranch, STRATEGY_ROUTES,
)

class AdvantageFoundry:
    """Manufactures proposals and reusable competence; never grants authority."""

    def __init__(self) -> None:
        self._opportunity_digests: dict[str, str] = {}
        self._genomes: dict[str, AdvantageGenome] = {}

    def intake(self, opportunity: OpportunitySpec) -> OpportunitySpec:
        opportunity.validate()
        prior = self._opportunity_digests.get(opportunity.opportunity_id)
        if prior is not None and prior != opportunity.digest:
            raise FoundryError("changed-content replay for an existing opportunity id")
        self._opportunity_digests[opportunity.opportunity_id] = opportunity.digest
        return opportunity

    def complete_route_tournament(self, branches: Iterable[StrategyBranch]) -> tuple[StrategyBranch, tuple[StrategyBranch, ...]]:
        branch_list = tuple(branches)
        for branch in branch_list:
            branch.validate()
        routes = [b.route for b in branch_list]
        if set(routes) != set(STRATEGY_ROUTES) or len(routes) != len(STRATEGY_ROUTES):
            raise FoundryError("all eleven strategy routes must appear exactly once")
        winner = max(branch_list, key=lambda b: (b.score, -b.cost_usd, -b.time_to_proof_days, b.route))
        return winner, tuple(b for b in branch_list if b.route != winner.route)

    def compile_architecture(
        self,
        opportunity: OpportunitySpec,
        winner: StrategyBranch,
        capability_needs: Iterable[CapabilityNeed],
        *,
        control_surface: str,
        success_metrics: tuple[str, ...],
        kill_conditions: tuple[str, ...],
    ) -> AdvantageArchitecture:
        self.intake(opportunity)
        winner.validate()
        needs = tuple(capability_needs)
        if not needs:
            raise FoundryError("architecture requires capabilities")
        for need in needs:
            need.validate()
        if not control_surface or not success_metrics or not kill_conditions:
            raise FoundryError("control surface, metrics, and kill conditions are required")
        seed = f"{opportunity.digest}|{winner.route}|{control_surface}"
        return AdvantageArchitecture(
            architecture_id="adv-" + sha256(seed.encode()).hexdigest()[:16],
            opportunity_digest=opportunity.digest,
            selected_route=winner.route,
            accepted_artifact=opportunity.accepted_artifact,
            external_consequence=opportunity.external_consequence,
            control_surface=control_surface,
            capability_needs=needs,
            success_metrics=success_metrics,
            kill_conditions=kill_conditions,
            legal_operator=opportunity.legal_operator,
        )

    @staticmethod
    def closure_state(outcome: ExternalOutcome | None) -> ClosureState:
        if outcome is None:
            return ClosureState.OPEN
        if outcome.payment_usd > 0 and not outcome.externally_verified:
            return ClosureState.FALSELY_CLOSED
        if outcome.externally_verified and outcome.payment_usd <= 0:
            return ClosureState.PARTIALLY_CLOSED
        if (
            outcome.payment_usd > 0 and outcome.accepted_delivery and outcome.externally_verified
            and outcome.reconciliation_closed and outcome.contribution_margin_usd >= 0
            and outcome.receipt_refs
        ):
            return ClosureState.CLOSED
        return ClosureState.PARTIALLY_CLOSED

    def seal_advantage_genome(
        self,
        name: str,
        version: str,
        architecture: AdvantageArchitecture,
        capability_versions: tuple[str, ...],
        outcome: ExternalOutcome,
        *,
        time_to_validated_genome_days: int,
        rollback: str,
    ) -> AdvantageGenome:
        if self.closure_state(outcome) is not ClosureState.CLOSED:
            raise FoundryError("only a closed paid external outcome may seal a genome")
        if time_to_validated_genome_days < 0 or not rollback:
            raise FoundryError("valid TVG and rollback are required")
        genome = AdvantageGenome(
            name=name,
            version=version,
            architecture_hash=architecture.digest,
            capability_versions=capability_versions,
            payment_proof=outcome.receipt_refs,
            outcome_proof=outcome.receipt_refs,
            contribution_margin_usd=outcome.contribution_margin_usd,
            time_to_validated_genome_days=time_to_validated_genome_days,
            founder_hours=outcome.founder_hours,
            legal_operator=architecture.legal_operator,
            rollback=rollback,
            kill_conditions=architecture.kill_conditions,
        )
        if genome.key in self._genomes:
            raise FoundryError("genome version already exists; publish a new immutable version")
        self._genomes[genome.key] = genome
        return genome

    def get_genome(self, name: str, version: str) -> AdvantageGenome | None:
        return self._genomes.get(f"{name}@{version}")
