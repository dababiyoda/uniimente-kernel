"""Resumable controller for the Foundry -> OMNIMORPH -> commercial loop.

The controller coordinates existing bounded components. It never fabricates a
strategy branch, ratifies an organ, calls the Consequence Gate, performs a
commercial action, or invents an outcome. Every authority-bearing transition
must be supplied as a separately verified record.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
from typing import Any, Iterable

from omnimorph import OmnimorphEngine, RatificationRecord

from .commercial import CommercialClosureCompiler, CommercialStage
from .contracts import (
    AdvantageGenome,
    CapabilityNeed,
    FoundryError,
    StrategyBranch,
)
from .engine import AdvantageFoundry


class PipelineStatus(str, Enum):
    AWAITING_RATIFICATION = "AWAITING_RATIFICATION"
    DESIGN_REJECTED = "DESIGN_REJECTED"
    ACTIVATION_PROPOSED = "ACTIVATION_PROPOSED"
    GATE_ACTIVATED = "GATE_ACTIVATED"
    COMMERCIAL_VALIDATION = "COMMERCIAL_VALIDATION"
    RETAINED_GENOME = "RETAINED_GENOME"


@dataclass
class PipelineRun:
    run_id: str
    opportunity_id: str
    architecture_id: str
    architecture_hash: str
    organ_id: str
    manifest_hash: str
    simulation_passed: bool
    status: PipelineStatus
    commercial_case_id: str | None = None
    genome_key: str | None = None


class FoundryPipeline:
    """Coordinates a bounded, externally evidenced Foundry lifecycle."""

    def __init__(
        self,
        *,
        foundry: AdvantageFoundry,
        omnimorph: OmnimorphEngine,
        commercial: CommercialClosureCompiler,
        ledger: Any | None = None,
    ) -> None:
        self.foundry = foundry
        self.omnimorph = omnimorph
        self.commercial = commercial
        self.ledger = ledger
        self._runs: dict[str, PipelineRun] = {}
        if ledger is not None:
            self.rebuild_from_ledger()

    def _record_snapshot(self, run: PipelineRun) -> None:
        if self.ledger is not None:
            payload = asdict(run)
            payload["status"] = run.status.value
            self.ledger.append(
                "event",
                {"type": "foundry.pipeline_snapshot", "run": payload},
            )

    def rebuild_from_ledger(self) -> None:
        self._runs.clear()
        for record in self.ledger.by_type("event"):
            payload = record.payload
            if payload.get("type") != "foundry.pipeline_snapshot":
                continue
            raw = dict(payload["run"])
            raw["status"] = PipelineStatus(raw["status"])
            run = PipelineRun(**raw)
            self._runs[run.run_id] = run

    def design(
        self,
        *,
        opportunity_id: str,
        branches: Iterable[StrategyBranch],
        capability_needs: Iterable[CapabilityNeed],
        control_surface: str,
        success_metrics: tuple[str, ...],
        kill_conditions: tuple[str, ...],
        capability_versions: dict[str, str],
        objective: str,
        consequence_ceiling: str,
        expires_at: str,
    ) -> PipelineRun:
        opportunity = self.foundry.get_opportunity(opportunity_id)
        if opportunity is None:
            raise FoundryError("accepted opportunity is not available")
        winner, _ = self.foundry.complete_route_tournament(branches)
        architecture = self.foundry.compile_architecture(
            opportunity,
            winner,
            capability_needs,
            control_surface=control_surface,
            success_metrics=success_metrics,
            kill_conditions=kill_conditions,
        )
        manifest = self.omnimorph.compose(
            architecture,
            capability_versions,
            objective=objective,
            consequence_ceiling=consequence_ceiling,
            expires_at=expires_at,
        )
        simulation = self.omnimorph.simulate(manifest)
        seed = f"{opportunity.digest}|{architecture.digest}|{manifest.digest}"
        run_id = "foundry-run-" + sha256(seed.encode()).hexdigest()[:16]
        run = PipelineRun(
            run_id=run_id,
            opportunity_id=opportunity.opportunity_id,
            architecture_id=architecture.architecture_id,
            architecture_hash=architecture.digest,
            organ_id=manifest.organ_id,
            manifest_hash=manifest.digest,
            simulation_passed=simulation.passed,
            status=(
                PipelineStatus.AWAITING_RATIFICATION
                if simulation.passed
                else PipelineStatus.DESIGN_REJECTED
            ),
        )
        prior = self._runs.get(run_id)
        if prior is not None and asdict(prior) != asdict(run):
            raise FoundryError("pipeline run id collision with different state")
        self._runs[run_id] = run
        self._record_snapshot(run)
        return run

    def propose_activation(
        self,
        run_id: str,
        ratification: RatificationRecord,
    ) -> PipelineRun:
        run = self._require_run(run_id)
        if run.status is not PipelineStatus.AWAITING_RATIFICATION:
            raise FoundryError("pipeline is not awaiting ratification")
        manifest = self._require_manifest(run)
        simulation = self.omnimorph.get_simulation(run.organ_id)
        if simulation is None:
            raise FoundryError("recorded simulation is unavailable")
        self.omnimorph.propose_activation(manifest, simulation, ratification)
        run.status = PipelineStatus.ACTIVATION_PROPOSED
        self._record_snapshot(run)
        return run

    def record_gate_activation(
        self,
        run_id: str,
        gate_receipt_hash: str,
    ) -> PipelineRun:
        run = self._require_run(run_id)
        if run.status is not PipelineStatus.ACTIVATION_PROPOSED:
            raise FoundryError("activation must be proposed before Gate receipt")
        manifest = self._require_manifest(run)
        self.omnimorph.record_gate_activation(manifest, gate_receipt_hash)
        run.status = PipelineStatus.GATE_ACTIVATED
        self._record_snapshot(run)
        return run

    def open_commercial_validation(self, run_id: str) -> PipelineRun:
        run = self._require_run(run_id)
        if run.status is not PipelineStatus.GATE_ACTIVATED:
            raise FoundryError("Gate activation is required before commercial validation")
        opportunity = self.foundry.get_opportunity(run.opportunity_id)
        architecture = self.foundry.get_architecture(run.architecture_id)
        if opportunity is None or architecture is None:
            raise FoundryError("resumable opportunity or architecture is unavailable")
        if architecture.digest != run.architecture_hash:
            raise FoundryError("pipeline architecture digest mismatch")
        case = self.commercial.open_case(opportunity, architecture)
        run.commercial_case_id = case.case_id
        run.status = PipelineStatus.COMMERCIAL_VALIDATION
        self._record_snapshot(run)
        return run

    def finalize_retained_genome(
        self,
        run_id: str,
        *,
        genome_name: str,
        genome_version: str,
        capability_versions: tuple[str, ...],
        time_to_validated_genome_days: int,
        rollback: str,
        accountable_actor: str,
        seal_record_hash: str,
    ) -> AdvantageGenome:
        run = self._require_run(run_id)
        if run.status is not PipelineStatus.COMMERCIAL_VALIDATION:
            raise FoundryError("pipeline is not in commercial validation")
        if not run.commercial_case_id:
            raise FoundryError("commercial case is missing")
        case = self.commercial.get(run.commercial_case_id)
        if case is None or case.stage is not CommercialStage.DECISION_RETAIN:
            raise FoundryError("a human-approved RETAIN decision is required")
        architecture = self.foundry.get_architecture(run.architecture_id)
        if architecture is None or architecture.digest != run.architecture_hash:
            raise FoundryError("pipeline architecture is unavailable or changed")
        outcome = self.commercial.build_external_outcome(case.case_id)
        self.omnimorph.validate_paid_outcome(outcome)

        existing = self.foundry.get_genome(genome_name, genome_version)
        if existing is None:
            genome = self.foundry.seal_advantage_genome(
                genome_name,
                genome_version,
                architecture,
                capability_versions,
                outcome,
                time_to_validated_genome_days=time_to_validated_genome_days,
                rollback=rollback,
            )
        else:
            genome = existing
            if genome.architecture_hash != architecture.digest:
                raise FoundryError("existing Genome belongs to another architecture")

        self.commercial.mark_genome_sealed(
            case.case_id,
            genome_key=genome.key,
            actor=accountable_actor,
            seal_record_hash=seal_record_hash,
        )
        run.genome_key = genome.key
        run.status = PipelineStatus.RETAINED_GENOME
        self._record_snapshot(run)
        return genome

    def get(self, run_id: str) -> PipelineRun | None:
        return self._runs.get(run_id)

    def _require_run(self, run_id: str) -> PipelineRun:
        run = self._runs.get(run_id)
        if run is None:
            raise FoundryError("unknown Foundry pipeline run")
        return run

    def _require_manifest(self, run: PipelineRun):
        manifest = self.omnimorph.get_manifest(run.organ_id)
        if manifest is None or manifest.digest != run.manifest_hash:
            raise FoundryError("pipeline Organ Manifest is unavailable or changed")
        return manifest


__all__ = ["FoundryPipeline", "PipelineRun", "PipelineStatus"]
