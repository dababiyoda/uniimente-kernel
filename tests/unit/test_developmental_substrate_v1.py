"""Adversarial tests for MICA/CDPE TARGET_FORM_001."""
import pytest

from developmental import (
    CellStatus,
    DevelopmentalError,
    DevelopmentalProgramExecutor,
    DevelopmentalVerdict,
    IntelligenceGenome,
    LocalRuleGenome,
    MICAField,
    PerturbationSpec,
    TernarySignal,
    TissueType,
)


def test_frozen_v01_contracts_validate_and_carry_no_authority():
    rules = LocalRuleGenome()
    intelligence = IntelligenceGenome()
    perturbation = PerturbationSpec()
    assert rules.validate() == []
    assert intelligence.validate() == []
    assert perturbation.validate() == []
    assert not rules.external_effects_allowed
    assert not rules.removed_cells_may_reactivate
    assert not intelligence.production_authority
    assert intelligence.authorization_state == "SIMULATED_NOT_AUTHORIZED"


def test_target_form_has_120_cells_and_three_functional_tissues():
    field = MICAField(width=12, height=10)
    assert len(field.cells) == 120
    assert field.tissue_counts() == {
        TissueType.ACTUATOR.value: 20,
        TissueType.SENSOR.value: 20,
        TissueType.TRANSPORT.value: 80,
    }
    snapshots = field.snapshots()
    assert len(snapshots) == 120
    assert all(snapshot.validate() == [] for snapshot in snapshots)


def test_local_field_builds_initial_route_without_master_route_input():
    field = MICAField()
    operations, depth = field.propagate_target_field()
    route = field.local_route()
    assert operations > 0 and depth > 0
    assert route[0] == field.source_id and route[-1] == field.sink_id
    assert field.is_route_open(route)
    assert all(
        field.cells[right].potential < field.cells[left].potential
        for left, right in zip(route, route[1:])
    )


def test_twenty_percent_damage_blocks_original_route_and_forms_novel_route():
    field = MICAField()
    field.propagate_target_field()
    original = field.local_route()
    removals = field.select_deterministic_removals()
    assert len(removals) == 24
    field.block_route(original)
    removed = field.remove_cells(removals)
    assert len(removed) == 24
    assert not field.is_route_open(original)
    field.propagate_target_field()
    recovered = field.local_route()
    assert recovered
    assert recovered != original
    assert field.is_route_open(recovered)
    assert all(field.cells[cell_id].status is CellStatus.REMOVED for cell_id in removed)
    assert all(field.cells[cell_id].signal is TernarySignal.INHIBIT for cell_id in removed)


def test_exact_restoration_is_refused_and_removed_cell_remains_removed():
    field = MICAField()
    removed = field.remove_cells(field.select_deterministic_removals())
    target = removed[0]
    with pytest.raises(DevelopmentalError, match="constitutionally prohibited"):
        field.attempt_exact_restoration(target)
    assert field.exact_restoration_attempts == 1
    assert field.cells[target].status is CellStatus.REMOVED


def test_removed_cell_action_fails_closed_and_is_counted():
    field = MICAField()
    target = field.remove_cells(field.select_deterministic_removals())[0]
    assert field.attempt_cell_action(target) is False
    assert field.false_activations == 1


def test_target_form_benchmark_recovers_and_preserves_strong_counterexample():
    report = DevelopmentalProgramExecutor().run()
    assert report.verdict is DevelopmentalVerdict.MECHANICS_VALIDATED_NOT_PRODUCTION_AUTHORIZED
    assert report.cell_count == 120
    assert report.removed_cell_count == 24
    assert report.removed_fraction == 0.20
    assert report.original_route_blocked
    assert report.recovered_route and report.recovered_route != report.original_route
    assert report.distributed.delivered > 0
    assert report.static_central.delivered == 0
    assert report.adaptive_central.delivered > 0
    assert report.recovery_throughput_ratio >= 0.90
    assert report.compute_ratio_vs_adaptive_central <= 4.0
    assert report.false_activations == 0
    assert report.exact_restoration_attempts == 0
    assert report.external_effects == 0
    assert report.authorization_state == "SIMULATED_NOT_AUTHORIZED"
    assert report.failures == ()
    assert report.metadata["adaptive_central_is_strong_counterexample"] is True


def test_benchmark_is_deterministic_and_reconstructable():
    first = DevelopmentalProgramExecutor().run()
    second = DevelopmentalProgramExecutor().run()
    assert first.benchmark_id == second.benchmark_id
    assert first.original_route == second.original_route
    assert first.recovered_route == second.recovered_route
    assert first.distributed == second.distributed
    assert first.adaptive_central == second.adaptive_central


def test_invalid_authority_or_restoration_genomes_are_refused():
    with pytest.raises(DevelopmentalError, match="invalid developmental program"):
        DevelopmentalProgramExecutor(
            rules=LocalRuleGenome(external_effects_allowed=True)
        )
    with pytest.raises(DevelopmentalError, match="invalid developmental program"):
        DevelopmentalProgramExecutor(
            intelligence=IntelligenceGenome(production_authority=True)
        )
    with pytest.raises(DevelopmentalError, match="invalid developmental program"):
        DevelopmentalProgramExecutor(
            perturbation=PerturbationSpec(prohibit_exact_restoration=False)
        )
