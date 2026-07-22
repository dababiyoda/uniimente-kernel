"""Adversarial tests for temporary organ composition and activation."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeRegistry
from foundry.advantage import AdvantageArchitecture, AdvantageRefused, CapabilityNeed
from foundry.arsenal import ARSENAL
from foundry.composition import CompositionRequest, FoundryComposer
from foundry.tribunal import (
    CONTROL_SUPER_NODES,
    TRIBUNAL_LENSES,
    SpiderWebTribunal,
    TribunalFinding,
    TribunalJudgment,
)
from omnimorph import (
    GateActivationReceipt,
    OmnimorphEngine,
    RatificationRecord,
)
from provenance.ledger import EvidenceLedger

HASH = "sha256:" + "f" * 64
SIGNATURE = "sha256:" + "1" * 64
RECEIPT = "sha256:" + "2" * 64
RECONCILIATION = "sha256:" + "3" * 64


def future(hours=24):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def capability():
    return CapabilityGenome(
        name="proof.audit", version="1.0.0",
        description="produce accepted evidence",
        interface={"inputs": {"request": "dict"}, "outputs": {"packet": "dict"}},
        contracts=["event", "outcome"],
        authority=AuthorityEnvelope(
            max_consequence_class="internal_write", budget_ceiling_usd=100.0
        ),
        acceptance_tests=["packet validates"],
        failure_modes=["evidence missing"],
        recovery_path="return to intake",
    )


def architecture():
    return AdvantageArchitecture(
        architecture_id="adv-test",
        opportunity_digest=HASH,
        selected_route="fastest_path",
        accepted_artifact="RAE packet",
        external_consequence="accepted outcome",
        control_surfaces=("proof",),
        capability_needs=(CapabilityNeed(
            capability="proof.audit", purpose="produce evidence",
            inputs=("request",), outputs=("packet",),
            consequence_class="internal_write", budget_usd=10.0,
        ),),
        success_metrics=("clean_verified_outcome_count",),
        kill_conditions=("no buyer commitment",),
        legal_operator="alfonso_lopez",
        selected_branch_digest=HASH,
    )


def findings():
    result = []
    for index, lens in enumerate(TRIBUNAL_LENSES):
        nodes = (CONTROL_SUPER_NODES[index],) if index < len(CONTROL_SUPER_NODES) else ()
        result.append(TribunalFinding(
            lens=lens, judgment=TribunalJudgment.PASS,
            thesis=f"pass {lens}", evidence_refs=(HASH,),
            strongest_countercase=f"counter {lens}",
            addressed_control_nodes=nodes, confidence=0.9,
        ))
    return tuple(result)


def all_executable_arsenal():
    return {identifier: replace(spec, status="executable") for identifier, spec in ARSENAL.items()}


def plan(*, executable=True, max_budget=100.0):
    composer = FoundryComposer(
        arsenal=all_executable_arsenal() if executable else ARSENAL,
        capability_genomes={"proof.audit@1.0.0": capability()},
        technology_capabilities={5: ("proof.audit@1.0.0",)},
    )
    return composer.compose(CompositionRequest(
        market_failure="missing proof", beneficiaries=("patient",),
        payer="facility CFO", control_surfaces=("proof",),
        desired_metrics=("clean_verified_outcome_count",),
        legal_principal="alfonso_lopez", max_budget_usd=max_budget,
        requested_technology_ids=(5,), evidence_refs=(HASH,),
        kill_conditions=("no buyer commitment",),
    ))


def stack(*, executable=True, register=True, max_budget=100.0):
    ledger = EvidenceLedger("sha256:" + "4" * 64)
    registry = GenomeRegistry(ledger)
    if register:
        registry.register(capability())
    tribunal = SpiderWebTribunal(ledger)
    arch = architecture()
    report = tribunal.evaluate(arch, findings())
    engine = OmnimorphEngine(
        registry=registry, tribunal=tribunal, max_budget_usd=1000.0, ledger=ledger
    )
    composition = plan(executable=executable, max_budget=max_budget)
    return ledger, engine, arch, composition, report


def compose_valid():
    ledger, engine, arch, composition, report = stack()
    manifest = engine.compose(
        arch, composition, report, {"proof.audit": "1.0.0"},
        objective="produce one clean verified outcome",
        consequence_ceiling="internal_write", expires_at=future(),
    )
    return ledger, engine, arch, composition, report, manifest


def test_unregistered_capability_refuses_composition():
    _, engine, arch, composition, report = stack(register=False)
    with pytest.raises(AdvantageRefused, match="unregistered capability"):
        engine.compose(
            arch, composition, report, {"proof.audit": "1.0.0"},
            objective="test", consequence_ceiling="internal_write", expires_at=future(),
        )


def test_aggregate_budget_cannot_escape_plan_ceiling():
    _, engine, arch, composition, report = stack(max_budget=5.0)
    with pytest.raises(AdvantageRefused, match="effective ceiling"):
        engine.compose(
            arch, composition, report, {"proof.audit": "1.0.0"},
            objective="test", consequence_ceiling="internal_write", expires_at=future(),
        )


def test_target_or_partial_technology_fails_simulation():
    _, engine, arch, composition, report = stack(executable=False)
    manifest = engine.compose(
        arch, composition, report, {"proof.audit": "1.0.0"},
        objective="test", consequence_ceiling="internal_write", expires_at=future(),
    )
    simulation = engine.simulate(manifest, composition)
    assert not simulation.passed
    assert any(reason.endswith(("_partial", "_target")) for reason in simulation.reasons)


def test_valid_manifest_simulates_but_remains_nonexecuting():
    _, engine, _, composition, _, manifest = compose_valid()
    simulation = engine.simulate(manifest, composition)
    assert simulation.passed
    assert manifest.execution_authority is False
    assert manifest.human_ratification_required is True
    assert manifest.organ_id not in engine.activation_state


@pytest.mark.parametrize("ratifier", ["UNIIMENTE", "OMNIMORPH", "foundry"])
def test_system_cannot_ratify_itself(ratifier):
    _, engine, _, composition, _, manifest = compose_valid()
    simulation = engine.simulate(manifest, composition)
    with pytest.raises(AdvantageRefused, match="cannot ratify itself"):
        engine.propose_activation(manifest, simulation, RatificationRecord(
            manifest_hash=manifest.digest, ratifier=ratifier,
            signature_ref=SIGNATURE, expires_at=future(),
        ))


def test_expired_ratification_is_refused():
    _, engine, _, composition, _, manifest = compose_valid()
    simulation = engine.simulate(manifest, composition)
    with pytest.raises(AdvantageRefused, match="must be in the future"):
        engine.propose_activation(manifest, simulation, RatificationRecord(
            manifest_hash=manifest.digest, ratifier="alfonso_lopez",
            signature_ref=SIGNATURE, expires_at=future(-1),
        ))


def activated_stack():
    _, engine, _, composition, _, manifest = compose_valid()
    simulation = engine.simulate(manifest, composition)
    engine.propose_activation(manifest, simulation, RatificationRecord(
        manifest_hash=manifest.digest, ratifier="alfonso_lopez",
        signature_ref=SIGNATURE, expires_at=future(),
    ))
    return engine, manifest


def test_generic_hash_cannot_substitute_for_exact_gate_receipt():
    engine, manifest = activated_stack()
    with pytest.raises(AdvantageRefused, match="organ.activate"):
        engine.record_gate_activation(manifest, GateActivationReceipt(
            receipt_hash=RECEIPT, manifest_hash=manifest.digest,
            action_class="media.publish", legal_principal="alfonso_lopez",
            state="recorded",
        ))


def test_gate_receipt_must_match_manifest_and_principal():
    engine, manifest = activated_stack()
    with pytest.raises(AdvantageRefused, match="not bound"):
        engine.record_gate_activation(manifest, GateActivationReceipt(
            receipt_hash=RECEIPT, manifest_hash=HASH,
            action_class="organ.activate", legal_principal="alfonso_lopez",
            state="recorded",
        ))
    with pytest.raises(AdvantageRefused, match="legal principal"):
        engine.record_gate_activation(manifest, GateActivationReceipt(
            receipt_hash=RECEIPT, manifest_hash=manifest.digest,
            action_class="organ.activate", legal_principal="different",
            state="recorded",
        ))


def test_exact_gate_receipt_records_activation_without_engine_calling_gate():
    engine, manifest = activated_stack()
    state = engine.record_gate_activation(manifest, GateActivationReceipt(
        receipt_hash=RECEIPT, manifest_hash=manifest.digest,
        action_class="organ.activate", legal_principal="alfonso_lopez",
        state="recorded",
    ))
    assert state.status == "GATE_ACTIVATED"
    assert state.gate_receipt_hash == RECEIPT


def test_retirement_requires_accountability_approval_and_reconciliation():
    engine, manifest = activated_stack()
    engine.record_gate_activation(manifest, GateActivationReceipt(
        receipt_hash=RECEIPT, manifest_hash=manifest.digest,
        action_class="organ.activate", legal_principal="alfonso_lopez",
        state="recorded",
    ))
    with pytest.raises(AdvantageRefused, match="accountable"):
        engine.retire(
            manifest.organ_id, actor="OMNIMORPH", reason="done",
            human_approval_ref=SIGNATURE, reconciliation_ref=RECONCILIATION,
        )
    record = engine.retire(
        manifest.organ_id, actor="alfonso_lopez", reason="objective complete",
        human_approval_ref=SIGNATURE, reconciliation_ref=RECONCILIATION,
    )
    assert record.status == "RETIRED"
    assert manifest.organ_id not in engine.activation_state
