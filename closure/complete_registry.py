"""Complete closure registry including Foundry and OMNIMORPH.

The legacy kernel registry remains untouched for historical compatibility. New
verification uses this wrapper so every newly built canonical module is held to
the same technical, authority, evidence, economic, and regenerative closures.
"""
from __future__ import annotations

from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeRegistry
from foundry import (
    AdvantageFoundry,
    CapabilityNeed,
    ClosureState,
    ExternalOutcome,
    FoundryError,
    OpportunitySpec,
    StrategyBranch,
    STRATEGY_ROUTES,
    opportunity_from_underwriting_wire,
)
from omnimorph import OmnimorphEngine, RatificationRecord
from provenance.ledger import EvidenceLedger

from .framework import ModuleClosures
from .kernel_registry import build_registry as build_legacy_registry


def _opportunity() -> OpportunitySpec:
    return OpportunitySpec(
        opportunity_id="closure-opportunity",
        buyer="Named Buyer LLC",
        beneficiary="operations team",
        pain_owner="VP Operations",
        budget_owner="CFO",
        recurring_transaction="approve and settle verified service",
        broken_state="proof is unreliable",
        trapped_value_usd=50000,
        accepted_artifact="signed verification receipt",
        external_consequence="buyer changes settlement decision",
        lawful_path="paid diagnostic under reviewed agreement",
        evidence_refs=("sha256:" + "a" * 64,),
    )


def _branches() -> tuple[StrategyBranch, ...]:
    return tuple(
        StrategyBranch(
            route=route,
            mechanism=f"mechanism-{route}",
            governing_assumption="buyer will pay for verified proof",
            strongest_counterargument="status quo may be sufficient",
            cheapest_falsification_test="ask for one paid diagnostic",
            kill_condition="no paid commitment",
            cost_usd=10 + index,
            time_to_proof_days=1 + index,
            expected_value_usd=1000 + index * 100,
            reversibility=1.0,
            evidence_quality=0.8,
            founder_hours=1.0,
            required_capabilities=("research.read", "offer.compile"),
        )
        for index, route in enumerate(STRATEGY_ROUTES)
    )


def _genome_registry() -> GenomeRegistry:
    registry = GenomeRegistry()
    for name, consequence_class, budget in (
        ("research.read", "read_only", 100),
        ("offer.compile", "internal_write", 200),
    ):
        registry.register(CapabilityGenome(
            name=name,
            version="1.0.0",
            description=name,
            interface={"inputs": {"request": "dict"}, "outputs": {"result": "dict"}},
            contracts=["event", "outcome"],
            authority=AuthorityEnvelope(
                max_consequence_class=consequence_class,
                budget_ceiling_usd=budget,
            ),
            acceptance_tests=["deterministic"],
            failure_modes=["dependency unavailable"],
            recovery_path="retry or replace",
        ))
    return registry


def _architecture(foundry: AdvantageFoundry):
    foundry.intake(_opportunity())
    winner, _ = foundry.complete_route_tournament(_branches())
    return foundry.compile_architecture(
        _opportunity(),
        winner,
        (
            CapabilityNeed(
                "research.read", "research", ("request",), ("result",),
                "read_only", 10,
            ),
            CapabilityNeed(
                "offer.compile", "compile offer", ("request",), ("result",),
                "internal_write", 20,
            ),
        ),
        control_surface="proof",
        success_metrics=("paid commitment", "verified outcome"),
        kill_conditions=("no buyer commitment",),
    )


def _foundry_technical():
    foundry = AdvantageFoundry()
    architecture = _architecture(foundry)
    ok = (
        architecture.digest.startswith("sha256:")
        and foundry.get_opportunity(_opportunity().opportunity_id) == _opportunity()
        and foundry.get_architecture(architecture.architecture_id) == architecture
    )
    return ok, "opportunity -> 11-route tournament -> typed architecture is executable"


def _foundry_authority():
    payload = {
        "schema_version": "0.1",
        "source_organ": "WealthMachineIntelligence",
        "opportunity_packet_id": "packet-1",
        "packet_digest": "sha256:" + "a" * 64,
        "assessment_id": "assessment-1",
        "assessment_digest": "sha256:" + "b" * 64,
        "human_approval_record_hash": "sha256:" + "c" * 64,
        "observed_pain": "proof is unreliable",
        "core_thesis": "verified proof may reduce disputes",
        "go_no_go": "go",
        "risk_level": "medium",
        "legal_readiness": "standard",
        "evidence_refs": ["sha256:" + "d" * 64],
        "buyer": "Named Buyer LLC",
        "beneficiary": "operations team",
        "pain_owner": "VP Operations",
        "budget_owner": "CFO",
        "recurring_transaction": "approve and settle verified service",
        "trapped_value_usd": 50000,
        "accepted_artifact": "signed verification receipt",
        "external_consequence": "buyer changes settlement decision",
        "lawful_path": "paid diagnostic under reviewed agreement",
        "legal_operator": "alfonso_lopez",
        "missing_fields": [],
        "blocking_reasons": [],
        "ready_for_foundry": True,
        "requires_human_approval": True,
        "execution_authority": "launch",
    }
    try:
        opportunity_from_underwriting_wire(payload)
    except FoundryError:
        return True, "wire intake refuses widened execution authority"
    return False, "authority-bearing underwriting envelope was accepted"


def _foundry_evidence():
    ledger = EvidenceLedger("sha256:" + "0" * 64)
    foundry = AdvantageFoundry(ledger)
    architecture = _architecture(foundry)
    restarted = AdvantageFoundry(ledger)
    ok = (
        ledger.verify_chain()[0]
        and restarted.get_opportunity(_opportunity().opportunity_id) == _opportunity()
        and restarted.get_architecture(architecture.architecture_id) == architecture
    )
    return ok, "accepted opportunity and architecture reconstruct from hash-chained evidence"


def _foundry_economic():
    false = ExternalOutcome(
        payment_usd=500,
        accepted_delivery=True,
        externally_verified=False,
        contribution_margin_usd=200,
        founder_hours=3,
        reconciliation_closed=True,
        receipt_refs=("sha256:" + "e" * 64,),
    )
    closed = ExternalOutcome(
        payment_usd=500,
        accepted_delivery=True,
        externally_verified=True,
        contribution_margin_usd=200,
        founder_hours=3,
        reconciliation_closed=True,
        receipt_refs=("sha256:" + "f" * 64,),
    )
    ok = (
        AdvantageFoundry.closure_state(false) is ClosureState.FALSELY_CLOSED
        and AdvantageFoundry.closure_state(closed) is ClosureState.CLOSED
    )
    return ok, "payment alone is false closure; paid verified margin closes economics"


def _foundry_regenerative():
    ledger = EvidenceLedger("sha256:" + "0" * 64)
    foundry = AdvantageFoundry(ledger)
    architecture = _architecture(foundry)
    outcome = ExternalOutcome(
        payment_usd=500,
        accepted_delivery=True,
        externally_verified=True,
        contribution_margin_usd=200,
        founder_hours=3,
        reconciliation_closed=True,
        receipt_refs=("sha256:" + "f" * 64,),
    )
    genome = foundry.seal_advantage_genome(
        "proof-diagnostic",
        "1.0.0",
        architecture,
        ("research.read@1.0.0", "offer.compile@1.0.0"),
        outcome,
        time_to_validated_genome_days=7,
        rollback="revoke grants and restore prior workflow",
    )
    tournaments = [
        record.payload for record in ledger.by_type("event")
        if record.payload.get("type") == "foundry.route_tournament_completed"
    ]
    ok = (
        len(tournaments) == 1
        and len(tournaments[0]["rejected_branches"]) == 10
        and bool(genome.rollback)
        and bool(genome.kill_conditions)
    )
    return ok, "rejected branches, rollback, and kill criteria remain reusable evidence"


def _omnimorph_fixture(ledger=None):
    foundry = AdvantageFoundry(ledger)
    architecture = _architecture(foundry)
    engine = OmnimorphEngine(_genome_registry(), ledger=ledger)
    manifest = engine.compose(
        architecture,
        {"research.read": "1.0.0", "offer.compile": "1.0.0"},
        objective="deliver one governed proof diagnostic",
        consequence_ceiling="internal_write",
        expires_at="2099-08-01T00:00:00Z",
    )
    return engine, manifest


def _omnimorph_technical():
    engine, manifest = _omnimorph_fixture()
    report = engine.simulate(manifest)
    ok = report.passed and engine.get_manifest(manifest.organ_id) == manifest
    return ok, "registered Capability Genomes compose into a simulated Organ Manifest"


def _omnimorph_authority():
    engine, manifest = _omnimorph_fixture()
    report = engine.simulate(manifest)
    try:
        engine.propose_activation(
            manifest,
            report,
            RatificationRecord(
                manifest.digest,
                "OMNIMORPH",
                "sha256:" + "a" * 64,
                "2099-08-01T00:00:00Z",
            ),
        )
    except FoundryError:
        return True, "self-ratification is refused and simulation cannot activate"
    return False, "OMNIMORPH self-ratification was accepted"


def _omnimorph_evidence():
    ledger = EvidenceLedger("sha256:" + "0" * 64)
    engine, manifest = _omnimorph_fixture(ledger)
    report = engine.simulate(manifest)
    restarted = OmnimorphEngine(_genome_registry(), ledger=ledger)
    ok = (
        ledger.verify_chain()[0]
        and restarted.get_manifest(manifest.organ_id) == manifest
        and restarted.get_simulation(manifest.organ_id) == report
    )
    return ok, "manifest and simulation reconstruct from the Evidence Ledger"


def _omnimorph_economic():
    foundry = AdvantageFoundry()
    foundry.intake(_opportunity())
    winner, _ = foundry.complete_route_tournament(_branches())
    architecture = foundry.compile_architecture(
        _opportunity(),
        winner,
        (
            CapabilityNeed(
                "research.read", "research", ("request",), ("result",),
                "read_only", 1000,
            ),
        ),
        control_surface="proof",
        success_metrics=("paid commitment",),
        kill_conditions=("budget exceeded",),
    )
    engine = OmnimorphEngine(_genome_registry())
    try:
        engine.compose(
            architecture,
            {"research.read": "1.0.0"},
            objective="oversized organ",
            consequence_ceiling="read_only",
            expires_at="2099-08-01T00:00:00Z",
        )
    except FoundryError:
        return True, "capability and aggregate budget ceilings fail closed"
    return False, "out-of-envelope organ budget was accepted"


def _omnimorph_regenerative():
    foundry = AdvantageFoundry()
    architecture = _architecture(foundry)
    engine = OmnimorphEngine(_genome_registry())
    versions = {"research.read": "1.0.0", "offer.compile": "1.0.0"}
    first = engine.compose(
        architecture,
        versions,
        objective="deliver one governed proof diagnostic",
        consequence_ceiling="internal_write",
        expires_at="2099-08-01T00:00:00Z",
    )
    second = engine.compose(
        architecture,
        versions,
        objective="audit one governed proof workflow",
        consequence_ceiling="internal_write",
        expires_at="2099-09-01T00:00:00Z",
    )
    ok = (
        first.organ_id != second.organ_id
        and first.state_namespace != second.state_namespace
        and first.bindings == second.bindings
        and engine.get_manifest(first.organ_id) == first
        and engine.get_manifest(second.organ_id) == second
    )
    return ok, "the same bounded competence forms distinct isolated organs without mutation"


def build_registry():
    registry = build_legacy_registry()
    registry.register(ModuleClosures("foundry", {
        "technical": _foundry_technical,
        "authority": _foundry_authority,
        "evidence": _foundry_evidence,
        "economic": _foundry_economic,
        "regenerative": _foundry_regenerative,
    }))
    registry.register(ModuleClosures("omnimorph", {
        "technical": _omnimorph_technical,
        "authority": _omnimorph_authority,
        "evidence": _omnimorph_evidence,
        "economic": _omnimorph_economic,
        "regenerative": _omnimorph_regenerative,
    }))
    return registry


__all__ = ["build_registry"]
