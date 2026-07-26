"""End-to-end tests for the bounded Foundry -> OMNIMORPH pipeline."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeRegistry
from foundry.advantage import (
    AdvantageFoundry,
    AdvantageRefused,
    CapabilityNeed,
    ExternalOutcome,
    OpportunitySpec,
    StrategyBranch,
    STRATEGY_ROUTES,
)
from foundry.arsenal import ARSENAL
from foundry.composition import CompositionRequest, FoundryComposer
from foundry.pipeline import FoundryPipeline, PipelineStatus
from foundry.tribunal import (
    CONTROL_SUPER_NODES,
    TRIBUNAL_LENSES,
    SpiderWebTribunal,
    TribunalFinding,
    TribunalJudgment,
)
from omnimorph import GateActivationReceipt, OmnimorphEngine, RatificationRecord
from provenance.ledger import EvidenceLedger

HASH = "sha256:" + "5" * 64
SIGNATURE = "sha256:" + "6" * 64
GATE_RECEIPT = "sha256:" + "7" * 64
DECISION_EVIDENCE = "sha256:" + "8" * 64
HUMAN_APPROVAL = "sha256:" + "9" * 64


def future():
    return (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()


def opportunity():
    return OpportunitySpec(
        opportunity_id="ivio-pilot-1",
        buyer="facility CFO", beneficiary="patient",
        pain_owner="case management", budget_owner="facility CFO",
        mandate_actor="compliance executive",
        recurring_transaction="patient transport discharge",
        broken_state="missing payer-grade transport proof",
        trapped_value_usd=250000.0,
        accepted_artifact="Request-Accept-Evidence packet",
        external_consequence="one accepted and reconciled transport outcome",
        lawful_path="BAA plus fair-market-value evidence service",
        evidence_refs=(HASH,), legal_operator="alfonso_lopez",
    )


def branches():
    return tuple(StrategyBranch(
        route=route,
        mechanism=f"mechanism {route}",
        governing_assumption=f"assumption {route}",
        strongest_counterargument=f"counter {route}",
        cheapest_falsification_test=f"test {route}",
        kill_condition=f"kill {route}",
        cost_usd=float(index + 1), time_to_proof_days=index + 1,
        expected_value_usd=10000.0 if route == "fastest_path" else 1000.0,
        reversibility=0.9, evidence_quality=0.8,
        founder_hours=float(index + 1), required_capabilities=("proof.audit",),
    ) for index, route in enumerate(STRATEGY_ROUTES))


def capability_need():
    return CapabilityNeed(
        capability="proof.audit", purpose="produce accepted evidence",
        inputs=("request",), outputs=("packet",),
        consequence_class="internal_write", budget_usd=10.0,
    )


def capability():
    return CapabilityGenome(
        name="proof.audit", version="1.0.0", description="accepted evidence",
        interface={"inputs": {"request": "dict"}, "outputs": {"packet": "dict"}},
        contracts=["event", "outcome"],
        authority=AuthorityEnvelope(
            max_consequence_class="internal_write", budget_ceiling_usd=100.0
        ),
        acceptance_tests=["packet validates"], failure_modes=["missing evidence"],
        recovery_path="return to intake",
    )


def composition_request():
    return CompositionRequest(
        market_failure="missing payer-grade transport proof",
        beneficiaries=("patient",), payer="facility CFO",
        control_surfaces=("proof",),
        desired_metrics=("clean_verified_outcome_count",),
        legal_principal="alfonso_lopez", max_budget_usd=100.0,
        requested_technology_ids=(5,), evidence_refs=(HASH,),
        kill_conditions=("no buyer commitment",),
    )


def findings(*, reconfigure=False):
    result = []
    for index, lens in enumerate(TRIBUNAL_LENSES):
        judgment = (
            TribunalJudgment.RECONFIGURE
            if reconfigure and index == 0 else TribunalJudgment.PASS
        )
        result.append(TribunalFinding(
            lens=lens, judgment=judgment,
            thesis=f"finding {lens}", evidence_refs=(HASH,),
            strongest_countercase=f"counter {lens}",
            required_changes=("repair model",) if judgment is TribunalJudgment.RECONFIGURE else (),
            addressed_control_nodes=(CONTROL_SUPER_NODES[index],)
            if index < len(CONTROL_SUPER_NODES) else (),
            confidence=0.9,
        ))
    return tuple(result)


def clean_outcome(**overrides):
    values = dict(
        economic_commitment_usd=500.0, accepted_delivery=True,
        externally_verified=True, contribution_margin_usd=250.0,
        founder_hours=4.0, reconciliation_closed=True,
        authority_incidents=0, critical_participant_harm_incidents=0,
        metric_results={"clean_verified_outcome_count": 1.0},
        receipt_refs=(HASH,),
    )
    values.update(overrides)
    return ExternalOutcome(**values)


def build_stack():
    ledger = EvidenceLedger("sha256:" + "a" * 64)
    registry = GenomeRegistry(ledger)
    genome = registry.register(capability())
    executable = {identifier: replace(spec, status="executable") for identifier, spec in ARSENAL.items()}
    composer = FoundryComposer(
        arsenal=executable,
        capability_genomes={"proof.audit@1.0.0": genome},
        technology_capabilities={5: ("proof.audit@1.0.0",)},
    )
    foundry = AdvantageFoundry(ledger)
    foundry.intake(opportunity())
    tribunal = SpiderWebTribunal(ledger)
    omnimorph = OmnimorphEngine(
        registry=registry, tribunal=tribunal, max_budget_usd=1000.0, ledger=ledger
    )
    pipeline = FoundryPipeline(
        foundry=foundry, composer=composer, tribunal=tribunal,
        omnimorph=omnimorph, ledger=ledger,
    )
    return ledger, foundry, tribunal, omnimorph, pipeline


def design(pipeline, *, reconfigure=False):
    return pipeline.design(
        opportunity_id="ivio-pilot-1",
        branches=branches(), capability_needs=(capability_need(),),
        control_surfaces=("proof",),
        success_metrics=("clean_verified_outcome_count",),
        kill_conditions=("no buyer commitment",),
        findings=findings(reconfigure=reconfigure),
        composition_request=composition_request(),
        capability_versions={"proof.audit": "1.0.0"},
        objective="produce one clean verified outcome",
        consequence_ceiling="internal_write", expires_at=future(),
    )


def activate(pipeline):
    run = design(pipeline)
    pipeline.propose_activation(run.run_id, RatificationRecord(
        manifest_hash=run.manifest_hash,
        ratifier="alfonso_lopez", signature_ref=SIGNATURE, expires_at=future(),
    ))
    pipeline.record_gate_activation(run.run_id, GateActivationReceipt(
        receipt_hash=GATE_RECEIPT, manifest_hash=run.manifest_hash,
        action_class="organ.activate", legal_principal="alfonso_lopez",
        state="recorded",
    ))
    return run


def test_reconfigure_tribunal_stops_before_composition():
    _, _, _, _, pipeline = build_stack()
    run = design(pipeline, reconfigure=True)
    assert run.status is PipelineStatus.DESIGN_REJECTED
    assert run.composition_plan_id is None
    assert run.organ_id is None


def test_successful_design_waits_for_human_ratification():
    _, _, _, _, pipeline = build_stack()
    run = design(pipeline)
    assert run.status is PipelineStatus.AWAITING_RATIFICATION
    assert run.simulation_passed
    assert run.manifest_hash and run.composition_plan_id


def test_gate_receipt_cannot_precede_ratification():
    _, _, _, _, pipeline = build_stack()
    run = design(pipeline)
    with pytest.raises(AdvantageRefused, match="must be proposed"):
        pipeline.record_gate_activation(run.run_id, GateActivationReceipt(
            receipt_hash=GATE_RECEIPT, manifest_hash=run.manifest_hash,
            action_class="organ.activate", legal_principal="alfonso_lopez",
            state="recorded",
        ))


def test_dirty_outcome_cannot_receive_retain_decision():
    _, _, _, _, pipeline = build_stack()
    run = activate(pipeline)
    with pytest.raises(AdvantageRefused, match="clean closed"):
        pipeline.submit_external_outcome(
            run.run_id, clean_outcome(authority_incidents=1),
            decision="RETAIN", actor="alfonso_lopez",
            decision_evidence_ref=DECISION_EVIDENCE,
            human_approval_ref=HUMAN_APPROVAL,
        )


def test_modify_preserves_result_but_cannot_seal():
    _, _, _, _, pipeline = build_stack()
    run = activate(pipeline)
    pipeline.submit_external_outcome(
        run.run_id, clean_outcome(contribution_margin_usd=-50.0),
        decision="MODIFY", actor="alfonso_lopez",
        decision_evidence_ref=DECISION_EVIDENCE,
        human_approval_ref=HUMAN_APPROVAL,
    )
    assert run.status is PipelineStatus.MODIFY_REQUIRED
    with pytest.raises(AdvantageRefused, match="RETAIN"):
        pipeline.finalize_retained_genome(
            run.run_id, genome_name="ivio-proof", genome_version="1.0.0",
            capability_versions=("proof.audit@1.0.0",),
            time_to_validated_genome_days=30,
            rollback="retire organ and reconcile",
        )


def test_clean_retain_seals_reusable_genome():
    _, foundry, _, _, pipeline = build_stack()
    run = activate(pipeline)
    pipeline.submit_external_outcome(
        run.run_id, clean_outcome(), decision="RETAIN", actor="alfonso_lopez",
        decision_evidence_ref=DECISION_EVIDENCE,
        human_approval_ref=HUMAN_APPROVAL,
    )
    genome = pipeline.finalize_retained_genome(
        run.run_id, genome_name="ivio-proof", genome_version="1.0.0",
        capability_versions=("proof.audit@1.0.0",),
        time_to_validated_genome_days=30,
        rollback="retire organ and reconcile",
    )
    assert run.status is PipelineStatus.RETAINED_GENOME
    assert genome.key == "ivio-proof@1.0.0"
    assert foundry.get_genome("ivio-proof", "1.0.0") == genome


def test_pipeline_rebuilds_outcome_and_terminal_state_from_ledger():
    ledger, foundry, tribunal, omnimorph, pipeline = build_stack()
    run = activate(pipeline)
    pipeline.submit_external_outcome(
        run.run_id, clean_outcome(), decision="RETAIN", actor="alfonso_lopez",
        decision_evidence_ref=DECISION_EVIDENCE,
        human_approval_ref=HUMAN_APPROVAL,
    )
    rebuilt = FoundryPipeline(
        foundry=foundry, composer=pipeline.composer, tribunal=tribunal,
        omnimorph=omnimorph, ledger=ledger,
    )
    assert rebuilt.get(run.run_id).status is PipelineStatus.READY_TO_SEAL
    genome = rebuilt.finalize_retained_genome(
        run.run_id, genome_name="ivio-proof", genome_version="1.0.0",
        capability_versions=("proof.audit@1.0.0",),
        time_to_validated_genome_days=30,
        rollback="retire organ and reconcile",
    )
    assert genome.key == "ivio-proof@1.0.0"
