from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from typing import Any, Iterable

from .contracts import (
    AdvantageArchitecture, AdvantageGenome, CapabilityNeed, ClosureState,
    ExternalOutcome, FoundryError, OpportunitySpec, StrategyBranch, STRATEGY_ROUTES,
)


class AdvantageFoundry:
    """Manufactures proposals and reusable competence; never grants authority."""

    def __init__(self, ledger: Any | None = None) -> None:
        self.ledger = ledger
        self._opportunity_digests: dict[str, str] = {}
        self._opportunities: dict[str, OpportunitySpec] = {}
        self._architectures: dict[str, AdvantageArchitecture] = {}
        self._genomes: dict[str, AdvantageGenome] = {}
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
        raw["success_metrics"] = tuple(raw.get("success_metrics") or ())
        raw["kill_conditions"] = tuple(raw.get("kill_conditions") or ())
        architecture = AdvantageArchitecture(**raw)
        for need in architecture.capability_needs:
            need.validate()
        return architecture

    def rebuild_from_ledger(self) -> None:
        """Reconstruct resumable Foundry state from the append-only event chain.

        Older events that recorded only hashes still restore replay protection.
        Newer events also restore the full accepted opportunity and compiled
        architecture so a process restart does not require human restatement.
        """
        self._opportunity_digests.clear()
        self._opportunities.clear()
        self._architectures.clear()
        self._genomes.clear()
        for record in self.ledger.by_type("event"):
            payload = record.payload
            event_type = payload.get("type")
            if event_type == "foundry.opportunity_intake":
                opportunity_id = payload["opportunity_id"]
                self._opportunity_digests[opportunity_id] = payload["opportunity_digest"]
                if isinstance(payload.get("opportunity"), dict):
                    opportunity = self._opportunity_from_data(payload["opportunity"])
                    if opportunity.digest != payload["opportunity_digest"]:
                        raise FoundryError("ledgered opportunity digest mismatch")
                    self._opportunities[opportunity_id] = opportunity
            elif event_type == "foundry.architecture_compiled":
                if isinstance(payload.get("architecture"), dict):
                    architecture = self._architecture_from_data(payload["architecture"])
                    if architecture.digest != payload["architecture_digest"]:
                        raise FoundryError("ledgered architecture digest mismatch")
                    self._architectures[architecture.architecture_id] = architecture
            elif event_type == "foundry.genome_sealed":
                raw = dict(payload["genome"])
                for key in (
                    "capability_versions", "payment_proof", "outcome_proof",
                    "kill_conditions",
                ):
                    raw[key] = tuple(raw.get(key) or ())
                genome = AdvantageGenome(**raw)
                self._genomes[genome.key] = genome

    def intake(self, opportunity: OpportunitySpec) -> OpportunitySpec:
        opportunity.validate()
        prior = self._opportunity_digests.get(opportunity.opportunity_id)
        if prior is not None and prior != opportunity.digest:
            self._record("foundry.opportunity_replay_refused", {
                "opportunity_id": opportunity.opportunity_id,
                "prior_digest": prior,
                "attempted_digest": opportunity.digest,
            })
            raise FoundryError("changed-content replay for an existing opportunity id")
        if prior is None:
            self._opportunity_digests[opportunity.opportunity_id] = opportunity.digest
            self._opportunities[opportunity.opportunity_id] = opportunity
            self._record("foundry.opportunity_intake", {
                "opportunity_id": opportunity.opportunity_id,
                "opportunity_digest": opportunity.digest,
                "legal_operator": opportunity.legal_operator,
                "opportunity": asdict(opportunity),
            })
        elif opportunity.opportunity_id not in self._opportunities:
            # Backward-compatible recovery for an older hash-only event. The
            # identical object may restore resumability but may not change it.
            self._opportunities[opportunity.opportunity_id] = opportunity
            self._record("foundry.opportunity_state_restored", {
                "opportunity_id": opportunity.opportunity_id,
                "opportunity_digest": opportunity.digest,
                "opportunity": asdict(opportunity),
            })
        return opportunity

    def complete_route_tournament(
        self,
        branches: Iterable[StrategyBranch],
    ) -> tuple[StrategyBranch, tuple[StrategyBranch, ...]]:
        branch_list = tuple(branches)
        for branch in branch_list:
            branch.validate()
        routes = [branch.route for branch in branch_list]
        if set(routes) != set(STRATEGY_ROUTES) or len(routes) != len(STRATEGY_ROUTES):
            raise FoundryError("all eleven strategy routes must appear exactly once")
        winner = max(
            branch_list,
            key=lambda branch: (
                branch.score,
                -branch.cost_usd,
                -branch.time_to_proof_days,
                branch.route,
            ),
        )
        losers = tuple(branch for branch in branch_list if branch.route != winner.route)
        self._record("foundry.route_tournament_completed", {
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
        architecture = AdvantageArchitecture(
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
        existing = self._architectures.get(architecture.architecture_id)
        if existing is not None and existing.digest != architecture.digest:
            raise FoundryError("architecture id collision with different content")
        self._architectures[architecture.architecture_id] = architecture
        self._record("foundry.architecture_compiled", {
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
        if outcome.payment_usd > 0 and not outcome.externally_verified:
            return ClosureState.FALSELY_CLOSED
        if outcome.externally_verified and outcome.payment_usd <= 0:
            return ClosureState.PARTIALLY_CLOSED
        if (
            outcome.payment_usd > 0
            and outcome.accepted_delivery
            and outcome.externally_verified
            and outcome.reconciliation_closed
            and outcome.contribution_margin_usd >= 0
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
        stored = self._architectures.get(architecture.architecture_id)
        if stored is not None and stored.digest != architecture.digest:
            raise FoundryError("cannot seal against a changed architecture")
        closure = self.closure_state(outcome)
        self._record("foundry.closure_evaluated", {
            "architecture_digest": architecture.digest,
            "closure_state": closure.value,
            "payment_usd": outcome.payment_usd,
            "externally_verified": outcome.externally_verified,
            "reconciliation_closed": outcome.reconciliation_closed,
        })
        if closure is not ClosureState.CLOSED:
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
        self._record("foundry.genome_sealed", {"genome": asdict(genome)})
        return genome

    def get_opportunity(self, opportunity_id: str) -> OpportunitySpec | None:
        return self._opportunities.get(opportunity_id)

    def get_architecture(self, architecture_id: str) -> AdvantageArchitecture | None:
        return self._architectures.get(architecture_id)

    def get_genome(self, name: str, version: str) -> AdvantageGenome | None:
        return self._genomes.get(f"{name}@{version}")
