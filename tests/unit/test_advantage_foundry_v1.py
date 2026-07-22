"""Adversarial tests for the Asymmetric Advantage Foundry v1."""
from dataclasses import replace

import pytest

from capabilities.genome import AuthorityEnvelope, CapabilityGenome
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
from foundry.composition import (
    CompositionRefused,
    CompositionRequest,
    FoundryComposer,
)
from foundry.tribunal import (
    CONTROL_SUPER_NODES,
    TRIBUNAL_LENSES,
    SpiderWebTribunal,
    TribunalFinding,
    TribunalJudgment,
    TribunalVerdict,
)
from provenance.ledger import EvidenceLedger

HASH = "sha256:" + "a" * 64


def opportunity(**overrides):
    values = dict(
        opportunity_id="opp-001",
        buyer="facility CFO",
        beneficiary="patient",
        pain_owner="case management",
        budget_owner="facility CFO",
        mandate_actor="compliance executive",
        recurring_transaction="patient transport discharge",
        broken_state="missing payer-grade transport proof",
        trapped_value_usd=250000.0,
        accepted_artifact="Request-Accept-Evidence packet",
        external_consequence="one accepted and reconciled transport outcome",
        lawful_path="BAA plus fair-market-value evidence service",
        evidence_refs=(HASH,),
        legal_operator="alfonso_lopez",
        constraints=("HIPAA",),
        prohibitions=("no referral payments",),
    )
    values.update(overrides)
    return OpportunitySpec(**values)


def branches():
    result = []
    for index, route in enumerate(STRATEGY_ROUTES):
        result.append(StrategyBranch(
            route=route,
            mechanism=f"mechanism for {route}",
            governing_assumption=f"assumption {route}",
            strongest_counterargument=f"countercase {route}",
            cheapest_falsification_test=f"test {route}",
            kill_condition=f"kill {route}",
            cost_usd=float(index + 1),
            time_to_proof_days=index + 1,
            expected_value_usd=10000.0 if route == "fastest_path" else 1000.0,
            reversibility=0.9,
            evidence_quality=0.8,
            founder_hours=float(index + 1),
            required_capabilities=("proof.audit",),
        ))
    return tuple(result)


def need():
    return CapabilityNeed(
        capability="proof.audit",
        purpose="produce accepted evidence",
        inputs=("request",),
        outputs=("evidence_packet",),
        consequence_class="internal_write",
        budget_usd=10.0,
    )


def composition_request(**overrides):
    values = dict(
        market_failure="missing payer-grade transport proof",
        beneficiaries=("patient",),
        payer="facility CFO",
        control_surfaces=("proof",),
        desired_metrics=("clean_verified_outcome_count",),
        legal_principal="alfonso_lopez",
        max_budget_usd=100.0,
        reversible_required=True,
        evidence_refs=(HASH,),
        kill_conditions=("no buyer commitment after ten offers",),
    )
    values.update(overrides)
    return CompositionRequest(**values)


def all_executable_arsenal():
    return {identifier: replace(spec, status="executable") for identifier, spec in ARSENAL.items()}


def capability():
    return CapabilityGenome(
        name="proof.audit",
        version="1.0.0",
        description="produce payer-grade evidence",
        interface={"inputs": {"request": "dict"}, "outputs": {"packet": "dict"}},
        contracts=["event", "outcome"],
        authority=AuthorityEnvelope(
            max_consequence_class="internal_write", budget_ceiling_usd=100.0
        ),
        acceptance_tests=["packet validates"],
        failure_modes=["source evidence missing"],
        recovery_path="return to evidence intake",
    )


def findings(*, missing_node=None, judgment=TribunalJudgment.PASS):
    result = []
    for index, lens in enumerate(TRIBUNAL_LENSES):
        nodes = ()
        if index < len(CONTROL_SUPER_NODES):
            node = CONTROL_SUPER_NODES[index]
            if node != missing_node:
                nodes = (node,)
        result.append(TribunalFinding(
            lens=lens,
            judgment=judgment if index == 0 else TribunalJudgment.PASS,
            thesis=f"finding for {lens}",
            evidence_refs=(HASH,),
            strongest_countercase=f"strongest countercase for {lens}",
            required_changes=("repair before proceeding",)
            if index == 0 and judgment is TribunalJudgment.RECONFIGURE else (),
            addressed_control_nodes=nodes,
            confidence=0.8,
        ))
    return tuple(result)


def architecture(foundry):
    foundry.intake(opportunity())
    winner, _ = foundry.complete_route_tournament(branches())
    return foundry.compile_architecture(
        opportunity(), winner, (need(),),
        control_surfaces=("proof",),
        success_metrics=("clean_verified_outcome_count",),
        kill_conditions=("no buyer commitment after ten offers",),
    )


def clean_outcome(**overrides):
    values = dict(
        economic_commitment_usd=500.0,
        accepted_delivery=True,
        externally_verified=True,
        contribution_margin_usd=250.0,
        founder_hours=4.0,
        reconciliation_closed=True,
        authority_incidents=0,
        critical_participant_harm_incidents=0,
        metric_results={"clean_verified_outcome_count": 1.0},
        receipt_refs=(HASH,),
    )
    values.update(overrides)
    return ExternalOutcome(**values)


def test_arsenal_contains_exactly_55_status_aware_entries():
    assert set(ARSENAL) == set(range(1, 56))
    assert all(not spec.validate() for spec in ARSENAL.values())
    assert {spec.status for spec in ARSENAL.values()} <= {"executable", "partial", "target"}


def test_composer_resolves_dependencies_and_reverse_detachment():
    genome = capability()
    composer = FoundryComposer(
        arsenal=all_executable_arsenal(),
        capability_genomes={"proof.audit@1.0.0": genome},
        technology_capabilities={5: ("proof.audit@1.0.0",)},
    )
    plan = composer.compose(composition_request(requested_technology_ids=(5,)))
    assert plan.verify_id()
    assert plan.selected_technology_ids.index(4) < plan.selected_technology_ids.index(5)
    assert [step.technology_id for step in plan.detachment_plan] == list(
        reversed(plan.selected_technology_ids)
    )
    assert plan.implementation_ready
    assert "plan_only" in plan.notes[0]


def test_target_architecture_remains_declared_not_executable():
    plan = FoundryComposer().compose(
        composition_request(requested_technology_ids=(10,))
    )
    assert not plan.implementation_ready
    assert any("deployment_blocker" in note for note in plan.notes)


def test_prohibited_dependency_fails_closed():
    with pytest.raises(CompositionRefused, match="prohibited"):
        FoundryComposer().compose(composition_request(
            requested_technology_ids=(5,), prohibited_technology_ids=(4,)
        ))


def test_all_eleven_routes_required_and_rejected_routes_preserved():
    ledger = EvidenceLedger("sha256:" + "b" * 64)
    foundry = AdvantageFoundry(ledger)
    with pytest.raises(AdvantageRefused, match="all eleven"):
        foundry.complete_route_tournament(branches()[:-1])
    winner, losers = foundry.complete_route_tournament(branches())
    assert winner.route == "fastest_path"
    assert len(losers) == 10
    events = [record.payload for record in ledger.by_type("event")]
    tournament = next(event for event in events if event.get("type") == "advantage.route_tournament_completed")
    assert len(tournament["rejected_branches"]) == 10


def test_changed_content_replay_is_refused_and_recorded():
    ledger = EvidenceLedger("sha256:" + "c" * 64)
    foundry = AdvantageFoundry(ledger)
    foundry.intake(opportunity())
    with pytest.raises(AdvantageRefused, match="changed-content replay"):
        foundry.intake(opportunity(buyer="different buyer"))
    assert any(
        record.payload.get("type") == "advantage.opportunity_replay_refused"
        for record in ledger.by_type("event")
    )


def test_tribunal_requires_eight_lenses_and_all_four_super_nodes():
    foundry = AdvantageFoundry()
    arch = architecture(foundry)
    tribunal = SpiderWebTribunal()
    with pytest.raises(AdvantageRefused, match="all eight"):
        tribunal.evaluate(arch, findings()[:-1])
    report = tribunal.evaluate(arch, findings(missing_node="cashflow_and_settlement"))
    assert report.verdict is TribunalVerdict.RECONFIGURE
    assert "address control super-node: cashflow_and_settlement" in report.required_changes
    with pytest.raises(AdvantageRefused, match="has not passed"):
        tribunal.require_passed(arch, report)


def test_blocking_countercase_rejects_architecture():
    foundry = AdvantageFoundry()
    arch = architecture(foundry)
    report = SpiderWebTribunal().evaluate(
        arch, findings(judgment=TribunalJudgment.BLOCK)
    )
    assert report.verdict is TribunalVerdict.REJECTED
    assert report.strongest_countercase


def test_false_and_partial_closure_are_not_genomes():
    foundry = AdvantageFoundry()
    arch = architecture(foundry)
    assert foundry.closure_state(None) is ClosureState.OPEN
    assert foundry.closure_state(clean_outcome(externally_verified=False)) is ClosureState.FALSELY_CLOSED
    assert foundry.closure_state(clean_outcome(economic_commitment_usd=0)) is ClosureState.PARTIALLY_CLOSED
    assert foundry.closure_state(clean_outcome(authority_incidents=1)) is ClosureState.PARTIALLY_CLOSED
    with pytest.raises(AdvantageRefused, match="clean closed"):
        foundry.seal_advantage_genome(
            "ivio-proof", "1.0.0", arch, "plan:abc", ("proof.audit@1.0.0",),
            clean_outcome(authority_incidents=1),
            time_to_validated_genome_days=30,
            rollback="retire organ and reconcile",
        )


def test_clean_external_outcome_seals_once_as_immutable_genome():
    foundry = AdvantageFoundry()
    arch = architecture(foundry)
    genome = foundry.seal_advantage_genome(
        "ivio-proof", "1.0.0", arch, "plan:abc", ("proof.audit@1.0.0",),
        clean_outcome(),
        time_to_validated_genome_days=30,
        rollback="retire organ and reconcile",
    )
    assert genome.key == "ivio-proof@1.0.0"
    with pytest.raises(AdvantageRefused, match="already exists"):
        foundry.seal_advantage_genome(
            "ivio-proof", "1.0.0", arch, "plan:abc", ("proof.audit@1.0.0",),
            clean_outcome(),
            time_to_validated_genome_days=30,
            rollback="retire organ and reconcile",
        )
