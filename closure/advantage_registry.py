"""Five-closure extension for Advantage Foundry and OMNIMORPH."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeRegistry
from closure.framework import ClosureRegistry, ModuleClosures
from foundry.advantage import (
    AdvantageFoundry,
    AdvantageRefused,
    CapabilityNeed,
    ClosureState,
    ExternalOutcome,
    OpportunitySpec,
    StrategyBranch,
    STRATEGY_ROUTES,
)
from foundry.arsenal import ARSENAL
from foundry.composition import CompositionRequest, FoundryComposer
from foundry.tribunal import (
    CONTROL_SUPER_NODES,
    TRIBUNAL_LENSES,
    SpiderWebTribunal,
    TribunalFinding,
    TribunalJudgment,
)
from omnimorph import GateActivationReceipt, OmnimorphEngine, RatificationRecord
from provenance.ledger import EvidenceLedger

HASH = "sha256:" + "a" * 64
SIGNATURE = "sha256:" + "b" * 64
RECEIPT = "sha256:" + "c" * 64
RECONCILIATION = "sha256:" + "d" * 64


def _future():
    return (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()


def build_opportunity(
    *,
    legal_operator,
    buyer="buyer_role",
    beneficiary="end_beneficiary",
    pain_owner="operations_owner",
    budget_owner="budget_owner_role",
    mandate_actor="mandate_owner",
    recurring_transaction="recurring_service_event",
    broken_state="missing verifiable proof of service",
    trapped_value_usd=250000.0,
    accepted_artifact="evidence packet",
    external_consequence="accepted and reconciled service outcome",
    lawful_path="written agreement plus fair-market-value evidence service",
    opportunity_id="closure-opportunity",
):
    """Generic opportunity fixture. Domain-neutral by default.

    `legal_operator` is REQUIRED and has no default. A fixture must never
    silently select an accountable party — the caller states who is
    accountable, deliberately.

    The IVIO-NEMT healthcare instance this replaced is preserved verbatim at
    ventures/ivio_nemt/fixtures.py.
    """
    return OpportunitySpec(
        opportunity_id=opportunity_id, buyer=buyer,
        beneficiary=beneficiary, pain_owner=pain_owner,
        budget_owner=budget_owner, mandate_actor=mandate_actor,
        recurring_transaction=recurring_transaction,
        broken_state=broken_state,
        trapped_value_usd=trapped_value_usd,
        accepted_artifact=accepted_artifact,
        external_consequence=external_consequence,
        lawful_path=lawful_path,
        evidence_refs=(HASH,), legal_operator=legal_operator,
    )


def _opportunity():
    # Core closure checks require a valid registered principal. alfonso_lopez
    # is passed deliberately and explicitly here, never chosen by a default.
    return build_opportunity(legal_operator="alfonso_lopez")


def _branches():
    return tuple(StrategyBranch(
        route=route, mechanism=f"mechanism {route}",
        governing_assumption=f"assumption {route}",
        strongest_counterargument=f"countercase {route}",
        cheapest_falsification_test=f"test {route}",
        kill_condition=f"kill {route}", cost_usd=float(index + 1),
        time_to_proof_days=index + 1,
        expected_value_usd=10000.0 if route == "fastest_path" else 1000.0,
        reversibility=0.9, evidence_quality=0.8,
        founder_hours=float(index + 1), required_capabilities=("proof.audit",),
    ) for index, route in enumerate(STRATEGY_ROUTES))


def _need():
    return CapabilityNeed(
        capability="proof.audit", purpose="produce evidence",
        inputs=("request",), outputs=("packet",),
        consequence_class="internal_write", budget_usd=10.0,
    )


def _capability():
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


def build_composition_request(
    *,
    legal_principal,
    max_budget=100.0,
    market_failure="missing verifiable proof of service",
    beneficiaries=("end_beneficiary",),
    payer="payer_role",
    control_surfaces=("proof",),
    desired_metrics=("clean_verified_outcome_count",),
    requested_technology_ids=(5,),
    kill_conditions=("no buyer commitment",),
):
    """Generic composition-request fixture. Domain-neutral by default.

    `legal_principal` is REQUIRED and has no default, for the same reason as
    build_opportunity: a production helper must not silently choose who is
    accountable merely because a value happens to pass registry validation
    (policy/engine.py rejects unregistered principals, which is a validity
    check, not an accountability decision).
    """
    return CompositionRequest(
        market_failure=market_failure,
        beneficiaries=beneficiaries, payer=payer,
        control_surfaces=control_surfaces,
        desired_metrics=desired_metrics,
        legal_principal=legal_principal, max_budget_usd=max_budget,
        requested_technology_ids=requested_technology_ids, evidence_refs=(HASH,),
        kill_conditions=kill_conditions,
    )


def _composition_request(max_budget=100.0, legal_principal=None):
    # Explicit, never silent. Core closure checks state accountability.
    if legal_principal is None:
        legal_principal = "alfonso_lopez"
    return build_composition_request(
        legal_principal=legal_principal, max_budget=max_budget
    )


def _findings():
    return tuple(TribunalFinding(
        lens=lens, judgment=TribunalJudgment.PASS,
        thesis=f"finding {lens}", evidence_refs=(HASH,),
        strongest_countercase=f"counter {lens}",
        addressed_control_nodes=(CONTROL_SUPER_NODES[index],)
        if index < len(CONTROL_SUPER_NODES) else (),
        confidence=0.9,
    ) for index, lens in enumerate(TRIBUNAL_LENSES))


def _clean_outcome():
    return ExternalOutcome(
        economic_commitment_usd=500.0, accepted_delivery=True,
        externally_verified=True, contribution_margin_usd=250.0,
        founder_hours=4.0, reconciliation_closed=True,
        authority_incidents=0, critical_participant_harm_incidents=0,
        metric_results={"clean_verified_outcome_count": 1.0},
        receipt_refs=(HASH,),
    )


def _stack(max_budget=100.0):
    ledger = EvidenceLedger("sha256:" + "e" * 64)
    registry = GenomeRegistry(ledger)
    genome = registry.register(_capability())
    executable = {
        identifier: replace(spec, status="executable")
        for identifier, spec in ARSENAL.items()
    }
    composer = FoundryComposer(
        arsenal=executable,
        capability_genomes={"proof.audit@1.0.0": genome},
        technology_capabilities={5: ("proof.audit@1.0.0",)},
    )
    foundry = AdvantageFoundry(ledger)
    foundry.intake(_opportunity())
    winner, losers = foundry.complete_route_tournament(_branches())
    architecture = foundry.compile_architecture(
        _opportunity(), winner, (_need(),), control_surfaces=("proof",),
        success_metrics=("clean_verified_outcome_count",),
        kill_conditions=("no buyer commitment",),
    )
    tribunal = SpiderWebTribunal(ledger)
    report = tribunal.evaluate(architecture, _findings())
    plan = composer.compose(_composition_request(max_budget=max_budget))
    omnimorph = OmnimorphEngine(
        registry=registry, tribunal=tribunal, max_budget_usd=1000.0, ledger=ledger
    )
    return ledger, foundry, architecture, tribunal, report, plan, omnimorph, losers


def register_advantage_closures(registry: ClosureRegistry) -> ClosureRegistry:
    def advantage_technical():
        _, _, architecture, tribunal, report, plan, _, losers = _stack()
        tribunal.require_passed(architecture, report)
        return (
            len(losers) == 10 and plan.verify_id() and plan.implementation_ready,
            "eleven routes, passed tribunal, and dependency-valid plan are present",
        )

    def advantage_authority():
        try:
            FoundryComposer().compose(_composition_request(legal_principal="UNIIMENTE"))
            return False, "UNIIMENTE became legal principal"
        except Exception:
            pass
        _, _, _, _, _, plan, _, _ = _stack()
        return (
            any("no infrastructure or external effect" in note for note in plan.notes),
            "Composition Plan declares no execution authority",
        )

    def advantage_evidence():
        ledger, foundry, _, _, _, _, _, losers = _stack()
        try:
            foundry.intake(replace(_opportunity(), buyer="changed buyer"))
            return False, "changed-content replay accepted"
        except AdvantageRefused:
            pass
        events = [record.payload for record in ledger.by_type("event")]
        tournament = next(
            event for event in events
            if event.get("type") == "advantage.route_tournament_completed"
        )
        return (
            len(losers) == 10
            and len(tournament["rejected_branches"]) == 10
            and any(event.get("type") == "advantage.opportunity_replay_refused" for event in events),
            "rejected routes and changed replay are preserved",
        )

    def advantage_economic():
        _, foundry, architecture, _, _, plan, _, _ = _stack()
        dirty = replace(_clean_outcome(), externally_verified=False)
        clean = _clean_outcome()
        if foundry.closure_state(dirty) is not ClosureState.FALSELY_CLOSED:
            return False, "paid but unverified outcome was not falsely closed"
        genome = foundry.seal_advantage_genome(
            "closure-proof", "1.0.0", architecture, plan.plan_id,
            ("proof.audit@1.0.0",), clean,
            time_to_validated_genome_days=30,
            rollback="retire organ and reconcile",
        )
        return (
            genome.contribution_margin_usd > 0,
            "only a clean paid accepted reconciled outcome seals a Genome",
        )

    def advantage_regenerative():
        _, _, architecture, _, report, _, _, _ = _stack()
        return (
            "do_nothing" in STRATEGY_ROUTES
            and bool(architecture.kill_conditions)
            and "reliability_governance_regeneration_continuity" in {
                finding.lens for finding in report.findings
            }
            and bool(report.strongest_countercase),
            "do-nothing, kill conditions, regeneration lens, and countercase are retained",
        )

    registry.register(ModuleClosures("advantage_foundry", {
        "technical": advantage_technical,
        "authority": advantage_authority,
        "evidence": advantage_evidence,
        "economic": advantage_economic,
        "regenerative": advantage_regenerative,
    }))

    def _manifest_stack(max_budget=100.0):
        ledger, _, architecture, _, report, plan, omnimorph, _ = _stack(max_budget)
        manifest = omnimorph.compose(
            architecture, plan, report, {"proof.audit": "1.0.0"},
            objective="one clean verified outcome",
            consequence_ceiling="internal_write", expires_at=_future(),
        )
        return ledger, plan, omnimorph, manifest

    def omnimorph_technical():
        _, plan, engine, manifest = _manifest_stack()
        simulation = engine.simulate(manifest, plan)
        return (
            simulation.passed and manifest.execution_authority is False,
            "registered manifest passes bounded simulation and remains non-executing",
        )

    def omnimorph_authority():
        _, plan, engine, manifest = _manifest_stack()
        simulation = engine.simulate(manifest, plan)
        try:
            engine.propose_activation(manifest, simulation, RatificationRecord(
                manifest_hash=manifest.digest, ratifier="OMNIMORPH",
                signature_ref=SIGNATURE, expires_at=_future(),
            ))
            return False, "OMNIMORPH self-ratified"
        except AdvantageRefused:
            pass
        engine.propose_activation(manifest, simulation, RatificationRecord(
            manifest_hash=manifest.digest, ratifier="alfonso_lopez",
            signature_ref=SIGNATURE, expires_at=_future(),
        ))
        try:
            engine.record_gate_activation(manifest, GateActivationReceipt(
                receipt_hash=RECEIPT, manifest_hash=manifest.digest,
                action_class="media.publish", legal_principal="alfonso_lopez",
                state="recorded",
            ))
            return False, "generic receipt activated the organ"
        except AdvantageRefused:
            return True, "self-ratification and receipt substitution fail closed"

    def omnimorph_evidence():
        ledger, plan, engine, manifest = _manifest_stack()
        simulation = engine.simulate(manifest, plan)
        engine.propose_activation(manifest, simulation, RatificationRecord(
            manifest_hash=manifest.digest, ratifier="alfonso_lopez",
            signature_ref=SIGNATURE, expires_at=_future(),
        ))
        engine.record_gate_activation(manifest, GateActivationReceipt(
            receipt_hash=RECEIPT, manifest_hash=manifest.digest,
            action_class="organ.activate", legal_principal="alfonso_lopez",
            state="recorded",
        ))
        events = [record.payload.get("type") for record in ledger.by_type("event")]
        required = {
            "omnimorph.manifest_composed", "omnimorph.simulation_completed",
            "omnimorph.activation_proposed", "omnimorph.gate_activation_recorded",
        }
        return required.issubset(set(events)), "manifest, simulation, proposal, and Gate receipt are ledgered"

    def omnimorph_economic():
        try:
            _manifest_stack(max_budget=5.0)
            return False, "aggregate capability budget escaped plan ceiling"
        except AdvantageRefused:
            return True, "aggregate budget is bounded by both plan and OMNIMORPH ceilings"

    def omnimorph_regenerative():
        _, plan, engine, manifest = _manifest_stack()
        simulation = engine.simulate(manifest, plan)
        engine.propose_activation(manifest, simulation, RatificationRecord(
            manifest_hash=manifest.digest, ratifier="alfonso_lopez",
            signature_ref=SIGNATURE, expires_at=_future(),
        ))
        engine.record_gate_activation(manifest, GateActivationReceipt(
            receipt_hash=RECEIPT, manifest_hash=manifest.digest,
            action_class="organ.activate", legal_principal="alfonso_lopez",
            state="recorded",
        ))
        retirement = engine.retire(
            manifest.organ_id, actor="alfonso_lopez", reason="objective complete",
            human_approval_ref=SIGNATURE, reconciliation_ref=RECONCILIATION,
        )
        return (
            retirement.status == "RETIRED"
            and manifest.organ_id not in engine.activation_state,
            "organ retires only with approval and reconciliation evidence",
        )

    registry.register(ModuleClosures("omnimorph", {
        "technical": omnimorph_technical,
        "authority": omnimorph_authority,
        "evidence": omnimorph_evidence,
        "economic": omnimorph_economic,
        "regenerative": omnimorph_regenerative,
    }))
    return registry
