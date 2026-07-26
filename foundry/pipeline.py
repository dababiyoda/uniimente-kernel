"""Resumable Advantage Foundry -> OMNIMORPH -> external validation pipeline.

The pipeline coordinates bounded components. It does not generate strategy
branches, tribunal findings, ratification, Gate receipts, commercial actions,
or external outcomes. Every authority-bearing or reality-bearing transition
must be supplied as a separately verified record.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
from typing import Any, Iterable

from omnimorph import (
    GateActivationReceipt,
    OmnimorphEngine,
    RatificationRecord,
)
from .advantage import (
    AdvantageArchitecture,
    AdvantageFoundry,
    AdvantageRefused,
    CapabilityNeed,
    ClosureState,
    ExternalOutcome,
    SealedAdvantageGenome,
    StrategyBranch,
)
from .composition import CompositionPlan, CompositionRequest, FoundryComposer
from .tribunal import (
    SpiderWebTribunal,
    TribunalFinding,
    TribunalReport,
    TribunalVerdict,
)


class PipelineStatus(str, Enum):
    DESIGN_REJECTED = "DESIGN_REJECTED"
    AWAITING_RATIFICATION = "AWAITING_RATIFICATION"
    ACTIVATION_PROPOSED = "ACTIVATION_PROPOSED"
    GATE_ACTIVATED = "GATE_ACTIVATED"
    READY_TO_SEAL = "READY_TO_SEAL"
    MODIFY_REQUIRED = "MODIFY_REQUIRED"
    KILLED = "KILLED"
    RETAINED_GENOME = "RETAINED_GENOME"


@dataclass
class PipelineRun:
    run_id: str
    opportunity_id: str
    architecture_id: str
    architecture_hash: str
    selected_route: str
    tribunal_report_id: str
    tribunal_report_hash: str
    composition_plan_id: str | None
    organ_id: str | None
    manifest_hash: str | None
    simulation_passed: bool
    status: PipelineStatus
    decision: str | None = None
    outcome_hash: str | None = None
    genome_key: str | None = None


class FoundryPipeline:
    """Coordinate design, organ proposal, activation evidence, and sealing."""

    def __init__(
        self,
        *,
        foundry: AdvantageFoundry,
        composer: FoundryComposer,
        tribunal: SpiderWebTribunal,
        omnimorph: OmnimorphEngine,
        ledger: Any | None = None,
    ) -> None:
        self.foundry = foundry
        self.composer = composer
        self.tribunal = tribunal
        self.omnimorph = omnimorph
        self.ledger = ledger
        self._runs: dict[str, PipelineRun] = {}
        self._plans: dict[str, CompositionPlan] = {}
        self._reports: dict[str, TribunalReport] = {}
        self._outcomes: dict[str, ExternalOutcome] = {}
        if ledger is not None:
            self.rebuild_from_ledger()

    def _record_snapshot(self, run: PipelineRun) -> None:
        if self.ledger is not None:
            payload = asdict(run)
            payload["status"] = run.status.value
            self.ledger.append("event", {"type": "advantage.pipeline_snapshot", "run": payload})

    def rebuild_from_ledger(self) -> None:
        self._runs.clear()
        self._outcomes.clear()
        for record in self.ledger.by_type("event"):
            payload = record.payload
            if payload.get("type") == "advantage.pipeline_snapshot":
                raw = dict(payload["run"])
                raw["status"] = PipelineStatus(raw["status"])
                run = PipelineRun(**raw)
                self._runs[run.run_id] = run
            elif payload.get("type") == "advantage.external_outcome_submitted":
                raw = dict(payload["outcome"])
                raw["receipt_refs"] = tuple(raw.get("receipt_refs") or ())
                self._outcomes[payload["run_id"]] = ExternalOutcome(**raw)

    def design(
        self,
        *,
        opportunity_id: str,
        branches: Iterable[StrategyBranch],
        capability_needs: Iterable[CapabilityNeed],
        control_surfaces: tuple[str, ...],
        success_metrics: tuple[str, ...],
        kill_conditions: tuple[str, ...],
        findings: Iterable[TribunalFinding],
        composition_request: CompositionRequest,
        capability_versions: dict[str, str],
        objective: str,
        consequence_ceiling: str,
        expires_at: str,
    ) -> PipelineRun:
        opportunity = self.foundry.get_opportunity(opportunity_id)
        if opportunity is None:
            raise AdvantageRefused("accepted opportunity is not available")
        self._validate_composition_request(opportunity, composition_request)

        winner, _ = self.foundry.complete_route_tournament(branches)
        architecture = self.foundry.compile_architecture(
            opportunity,
            winner,
            capability_needs,
            control_surfaces=control_surfaces,
            success_metrics=success_metrics,
            kill_conditions=kill_conditions,
        )
        report = self.tribunal.evaluate(architecture, findings)
        self._reports[report.report_id] = report
        if report.verdict is not TribunalVerdict.PASSED:
            run = self._rejected_run(architecture, report)
            self._runs[run.run_id] = run
            self._record_snapshot(run)
            return run

        plan = self.composer.compose(composition_request)
        self._plans[plan.plan_id] = plan
        manifest = self.omnimorph.compose(
            architecture,
            plan,
            report,
            capability_versions,
            objective=objective,
            consequence_ceiling=consequence_ceiling,
            expires_at=expires_at,
        )
        simulation = self.omnimorph.simulate(manifest, plan)
        seed = f"{opportunity.digest}|{architecture.digest}|{report.digest}|{plan.plan_id}|{manifest.digest}"
        run_id = "foundry-run-" + sha256(seed.encode()).hexdigest()[:16]
        run = PipelineRun(
            run_id=run_id,
            opportunity_id=opportunity.opportunity_id,
            architecture_id=architecture.architecture_id,
            architecture_hash=architecture.digest,
            selected_route=winner.route,
            tribunal_report_id=report.report_id,
            tribunal_report_hash=report.digest,
            composition_plan_id=plan.plan_id,
            organ_id=manifest.organ_id,
            manifest_hash=manifest.digest,
            simulation_passed=simulation.passed,
            status=(
                PipelineStatus.AWAITING_RATIFICATION
                if simulation.passed else PipelineStatus.DESIGN_REJECTED
            ),
        )
        prior = self._runs.get(run_id)
        if prior is not None and asdict(prior) != asdict(run):
            raise AdvantageRefused("pipeline run id collision with different state")
        self._runs[run_id] = run
        self._record_snapshot(run)
        return run

    def propose_activation(
        self, run_id: str, ratification: RatificationRecord
    ) -> PipelineRun:
        run = self._require_run(run_id)
        if run.status is not PipelineStatus.AWAITING_RATIFICATION:
            raise AdvantageRefused("pipeline is not awaiting ratification")
        manifest = self._require_manifest(run)
        simulation = self.omnimorph.get_simulation(manifest.organ_id)
        if simulation is None:
            raise AdvantageRefused("recorded simulation is unavailable")
        self.omnimorph.propose_activation(manifest, simulation, ratification)
        run.status = PipelineStatus.ACTIVATION_PROPOSED
        self._record_snapshot(run)
        return run

    def record_gate_activation(
        self, run_id: str, receipt: GateActivationReceipt
    ) -> PipelineRun:
        run = self._require_run(run_id)
        if run.status is not PipelineStatus.ACTIVATION_PROPOSED:
            raise AdvantageRefused("activation must be proposed before a Gate receipt")
        manifest = self._require_manifest(run)
        self.omnimorph.record_gate_activation(manifest, receipt)
        run.status = PipelineStatus.GATE_ACTIVATED
        self._record_snapshot(run)
        return run

    def submit_external_outcome(
        self,
        run_id: str,
        outcome: ExternalOutcome,
        *,
        decision: str,
        actor: str,
        decision_evidence_ref: str,
        human_approval_ref: str,
    ) -> PipelineRun:
        run = self._require_run(run_id)
        if run.status is not PipelineStatus.GATE_ACTIVATED:
            raise AdvantageRefused("a recorded Gate activation is required before outcome review")
        if not actor or actor in {"UNIIMENTE", "OMNIMORPH", "foundry"}:
            raise AdvantageRefused("an accountable decision actor is required")
        _require_hash(decision_evidence_ref, "decision_evidence_ref")
        _require_hash(human_approval_ref, "human_approval_ref")
        normalized = decision.upper()
        if normalized not in {"RETAIN", "MODIFY", "KILL"}:
            raise AdvantageRefused("decision must be RETAIN, MODIFY, or KILL")
        closure = self.foundry.closure_state(outcome)
        if normalized == "RETAIN" and closure is not ClosureState.CLOSED:
            raise AdvantageRefused("RETAIN requires a clean closed external outcome")

        run.decision = normalized
        run.outcome_hash = _outcome_hash(outcome)
        self._outcomes[run_id] = outcome
        if normalized == "RETAIN":
            run.status = PipelineStatus.READY_TO_SEAL
        elif normalized == "MODIFY":
            run.status = PipelineStatus.MODIFY_REQUIRED
        else:
            run.status = PipelineStatus.KILLED
        if self.ledger is not None:
            self.ledger.append("event", {
                "type": "advantage.external_outcome_submitted",
                "run_id": run_id,
                "outcome_hash": run.outcome_hash,
                "outcome": asdict(outcome),
                "closure_state": closure.value,
                "decision": normalized,
                "actor": actor,
                "decision_evidence_ref": decision_evidence_ref,
                "human_approval_ref": human_approval_ref,
            })
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
    ) -> SealedAdvantageGenome:
        run = self._require_run(run_id)
        if run.status is not PipelineStatus.READY_TO_SEAL or run.decision != "RETAIN":
            raise AdvantageRefused("a human-approved RETAIN decision is required")
        architecture = self.foundry.get_architecture(run.architecture_id)
        if architecture is None or architecture.digest != run.architecture_hash:
            raise AdvantageRefused("pipeline architecture is unavailable or changed")
        outcome = self._outcomes.get(run_id)
        if outcome is None or _outcome_hash(outcome) != run.outcome_hash:
            raise AdvantageRefused("external outcome is unavailable or changed")
        if not run.composition_plan_id:
            raise AdvantageRefused("pipeline Composition Plan is missing")

        existing = self.foundry.get_genome(genome_name, genome_version)
        if existing is None:
            genome = self.foundry.seal_advantage_genome(
                genome_name,
                genome_version,
                architecture,
                run.composition_plan_id,
                capability_versions,
                outcome,
                time_to_validated_genome_days=time_to_validated_genome_days,
                rollback=rollback,
            )
        else:
            genome = existing
            if genome.architecture_hash != architecture.digest:
                raise AdvantageRefused("existing Genome belongs to another architecture")
        run.genome_key = genome.key
        run.status = PipelineStatus.RETAINED_GENOME
        self._record_snapshot(run)
        return genome

    def get(self, run_id: str) -> PipelineRun | None:
        return self._runs.get(run_id)

    def _rejected_run(
        self, architecture: AdvantageArchitecture, report: TribunalReport
    ) -> PipelineRun:
        seed = f"{architecture.digest}|{report.digest}|rejected"
        return PipelineRun(
            run_id="foundry-run-" + sha256(seed.encode()).hexdigest()[:16],
            opportunity_id=next(
                opportunity_id for opportunity_id, opportunity in self.foundry._opportunities.items()
                if opportunity.digest == architecture.opportunity_digest
            ),
            architecture_id=architecture.architecture_id,
            architecture_hash=architecture.digest,
            selected_route=architecture.selected_route,
            tribunal_report_id=report.report_id,
            tribunal_report_hash=report.digest,
            composition_plan_id=None,
            organ_id=None,
            manifest_hash=None,
            simulation_passed=False,
            status=PipelineStatus.DESIGN_REJECTED,
        )

    def _validate_composition_request(self, opportunity, request: CompositionRequest) -> None:
        if request.market_failure != opportunity.broken_state:
            raise AdvantageRefused("Composition Request market failure differs from the opportunity")
        if request.payer != opportunity.buyer:
            raise AdvantageRefused("Composition Request payer differs from the opportunity buyer")
        if opportunity.beneficiary not in request.beneficiaries:
            raise AdvantageRefused("Composition Request omits the opportunity beneficiary")
        if request.legal_principal != opportunity.legal_operator:
            raise AdvantageRefused("Composition Request legal principal differs from the opportunity")

    def _require_run(self, run_id: str) -> PipelineRun:
        run = self._runs.get(run_id)
        if run is None:
            raise AdvantageRefused("unknown Foundry pipeline run")
        return run

    def _require_manifest(self, run: PipelineRun):
        if not run.organ_id or not run.manifest_hash:
            raise AdvantageRefused("pipeline has no Organ Manifest")
        manifest = self.omnimorph.get_manifest(run.organ_id)
        if manifest is None or manifest.digest != run.manifest_hash:
            raise AdvantageRefused("pipeline Organ Manifest is unavailable or changed")
        return manifest


def _outcome_hash(outcome: ExternalOutcome) -> str:
    raw = json.dumps(asdict(outcome), sort_keys=True, separators=(",", ":"))
    return "sha256:" + sha256(raw.encode()).hexdigest()


def _require_hash(value: str, field_name: str) -> str:
    if not value.startswith("sha256:") or len(value) != 71:
        raise AdvantageRefused(f"{field_name} must be a canonical sha256 reference")
    return value
