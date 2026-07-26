"""CDPE — Cellular Developmental Program Executor v0.1.

CDPE runs TARGET_FORM_001 as a deterministic counterfactual benchmark. The
same damaged topology is evaluated with a local MICA field, a static central
route, and an adaptive centralized planner. The report may validate mechanics;
it never grants production authority.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from hashlib import sha256
from typing import Iterable

from .contracts import (
    DevelopmentalBenchmarkReport,
    DevelopmentalVerdict,
    IntelligenceGenome,
    LocalRuleGenome,
    PerturbationSpec,
    TransportMetrics,
)
from .mica import DevelopmentalError, MICAField


class DevelopmentalProgramExecutor:
    """Execute the frozen TARGET_FORM_001 benchmark."""

    def __init__(
        self,
        *,
        rules: LocalRuleGenome | None = None,
        intelligence: IntelligenceGenome | None = None,
        perturbation: PerturbationSpec | None = None,
        width: int = 12,
        height: int = 10,
        post_damage_ticks: int = 40,
    ) -> None:
        self.rules = rules or LocalRuleGenome()
        self.intelligence = intelligence or IntelligenceGenome()
        self.perturbation = perturbation or PerturbationSpec()
        problems = (
            self.rules.validate()
            + self.intelligence.validate()
            + self.perturbation.validate()
        )
        if problems:
            raise DevelopmentalError(f"invalid developmental program: {problems}")
        if post_damage_ticks <= 0:
            raise DevelopmentalError("post-damage ticks must be positive")
        self.width = width
        self.height = height
        self.post_damage_ticks = post_damage_ticks

    def run(self) -> DevelopmentalBenchmarkReport:
        base = MICAField(width=self.width, height=self.height, rules=self.rules)
        original_planning_ops, _ = base.propagate_target_field()
        original_route = base.local_route()
        if not original_route:
            return self._invalid_report(base, "initial target form has no route")

        removal_ids = base.select_deterministic_removals(
            self.perturbation.remove_fraction
        )
        damaged = base.clone()
        blocked_count = damaged.block_route(original_route)
        removed = damaged.remove_cells(removal_ids)

        distributed_field = damaged.clone()
        distributed_planning_ops, wavefront_depth = (
            distributed_field.propagate_target_field()
        )
        recovered_route = distributed_field.local_route()
        distributed = simulate_transport(
            distributed_field,
            recovered_route,
            ticks=self.post_damage_ticks,
            mode="distributed_local_field",
            planning_operations=distributed_planning_ops,
            central_coordinator_required=False,
        )

        static_field = damaged.clone()
        static_central = simulate_transport(
            static_field,
            original_route,
            ticks=self.post_damage_ticks,
            mode="static_central_route",
            planning_operations=original_planning_ops,
            central_coordinator_required=True,
        )

        adaptive_field = damaged.clone()
        adaptive_route, adaptive_planning_ops = adaptive_field.global_shortest_path()
        adaptive_central = simulate_transport(
            adaptive_field,
            adaptive_route,
            ticks=self.post_damage_ticks,
            mode="adaptive_central_replanner",
            planning_operations=adaptive_planning_ops,
            central_coordinator_required=True,
        )

        removed_fraction = len(removed) / len(damaged.cells)
        throughput_ratio = (
            distributed.throughput_per_tick / adaptive_central.throughput_per_tick
            if adaptive_central.throughput_per_tick > 0 else 0.0
        )
        compute_ratio = (
            distributed.planning_operations / adaptive_central.planning_operations
            if adaptive_central.planning_operations > 0 else float("inf")
        )
        original_route_blocked = not damaged.is_route_open(original_route)
        false_activations = max(
            distributed_field.false_activations,
            static_field.false_activations,
            adaptive_field.false_activations,
        )
        exact_restoration_attempts = max(
            distributed_field.exact_restoration_attempts,
            static_field.exact_restoration_attempts,
            adaptive_field.exact_restoration_attempts,
        )

        checks: list[str] = []
        failures: list[str] = []

        def require(condition: bool, success: str, failure: str) -> None:
            (checks if condition else failures).append(success if condition else failure)

        require(
            len(damaged.cells) >= self.intelligence.minimum_cells,
            "minimum_cell_count_satisfied",
            "minimum_cell_count_failed",
        )
        require(
            set(damaged.tissue_counts()) == {
                tissue.value for tissue in self.intelligence.required_tissues
            },
            "three_functional_tissues_present",
            "required_tissues_missing",
        )
        require(
            abs(removed_fraction - self.intelligence.perturbation_remove_fraction) < 1e-12,
            "exact_twenty_percent_cell_loss",
            "cell_loss_fraction_incorrect",
        )
        require(
            original_route_blocked and blocked_count == len(original_route) - 1,
            "original_route_fully_blocked",
            "original_route_not_fully_blocked",
        )
        require(
            all(
                damaged.cells[cell_id].status.value == "removed"
                for cell_id in removed
            ),
            "removed_cells_remain_removed",
            "removed_cell_reactivation_detected",
        )
        require(
            recovered_route and recovered_route != original_route,
            "novel_recovery_route_formed",
            "no_novel_recovery_route",
        )
        require(
            distributed.delivered > 0,
            "distributed_function_recovered",
            "distributed_function_did_not_recover",
        )
        require(
            static_central.delivered == 0,
            "static_central_route_failed_under_route_obstruction",
            "static_central_route_unexpectedly_survived",
        )
        require(
            adaptive_central.delivered > 0,
            "strong_adaptive_central_counterexample_recovered",
            "adaptive_central_counterexample_invalid",
        )
        require(
            throughput_ratio >= self.intelligence.recovery_throughput_ratio_min,
            "distributed_throughput_within_required_ratio_of_adaptive_central",
            "distributed_throughput_below_required_ratio",
        )
        require(
            compute_ratio <= self.intelligence.max_compute_ratio_vs_adaptive_central,
            "distributed_planning_cost_within_declared_ceiling",
            "distributed_planning_cost_exceeds_declared_ceiling",
        )
        require(
            distributed.first_delivery_tick is not None
            and distributed.first_delivery_tick <= self.intelligence.maximum_recovery_ticks,
            "recovery_within_tick_ceiling",
            "recovery_exceeded_tick_ceiling",
        )
        require(
            false_activations <= self.intelligence.max_false_activations,
            "zero_false_activation",
            "false_activation_detected",
        )
        require(
            exact_restoration_attempts == 0,
            "no_exact_restoration_attempted",
            "exact_restoration_attempt_detected",
        )
        require(
            self.intelligence.production_authority is False
            and self.intelligence.authorization_state == "SIMULATED_NOT_AUTHORIZED",
            "simulation_carries_zero_production_authority",
            "simulation_authority_boundary_failed",
        )

        verdict = (
            DevelopmentalVerdict.MECHANICS_VALIDATED_NOT_PRODUCTION_AUTHORIZED
            if not failures
            else DevelopmentalVerdict.NO_MATERIAL_ADVANTAGE
        )
        report_seed = {
            "target": self.intelligence.target_form,
            "removed": removed,
            "blocked_edges": sorted(damaged.blocked_edges),
            "distributed": asdict(distributed),
            "static": asdict(static_central),
            "adaptive": asdict(adaptive_central),
            "checks": checks,
            "failures": failures,
        }
        benchmark_id = "benchmark:" + sha256(
            json.dumps(report_seed, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:24]
        return DevelopmentalBenchmarkReport(
            benchmark_id=benchmark_id,
            verdict=verdict,
            cell_count=len(damaged.cells),
            tissue_counts=damaged.tissue_counts(),
            removed_cell_count=len(removed),
            removed_fraction=removed_fraction,
            original_route=original_route,
            recovered_route=recovered_route,
            original_route_blocked=original_route_blocked,
            exact_restoration_attempts=exact_restoration_attempts,
            false_activations=false_activations,
            distributed=distributed,
            static_central=static_central,
            adaptive_central=adaptive_central,
            recovery_throughput_ratio=throughput_ratio,
            compute_ratio_vs_adaptive_central=compute_ratio,
            checks=tuple(checks),
            failures=tuple(failures),
            authorization_state=self.intelligence.authorization_state,
            external_effects=0,
            metadata={
                "target_form": self.intelligence.target_form,
                "removed_cell_ids": list(removed),
                "blocked_original_edges": blocked_count,
                "distributed_wavefront_depth": wavefront_depth,
                "distributed_field_messages": distributed_field.field_messages,
                "static_baseline_is_deliberately_brittle": True,
                "adaptive_central_is_strong_counterexample": True,
            },
        )

    def _invalid_report(
        self, field: MICAField, failure: str
    ) -> DevelopmentalBenchmarkReport:
        empty = TransportMetrics(
            mode="invalid", ticks=0, injected=0, delivered=0,
            throughput_per_tick=0.0, first_delivery_tick=None,
            planning_operations=0, transport_operations=0,
            route=(), central_coordinator_required=False,
        )
        return DevelopmentalBenchmarkReport(
            benchmark_id="benchmark:invalid",
            verdict=DevelopmentalVerdict.INVALID_EXPERIMENT,
            cell_count=len(field.cells),
            tissue_counts=field.tissue_counts(),
            removed_cell_count=0,
            removed_fraction=0.0,
            original_route=(),
            recovered_route=(),
            original_route_blocked=False,
            exact_restoration_attempts=0,
            false_activations=0,
            distributed=empty,
            static_central=empty,
            adaptive_central=empty,
            recovery_throughput_ratio=0.0,
            compute_ratio_vs_adaptive_central=0.0,
            checks=(),
            failures=(failure,),
            authorization_state=self.intelligence.authorization_state,
            external_effects=0,
        )


def simulate_transport(
    field: MICAField,
    route: Iterable[str],
    *,
    ticks: int,
    mode: str,
    planning_operations: int,
    central_coordinator_required: bool,
) -> TransportMetrics:
    """Move one newly injected packet one hop per tick over a supplied route."""
    route_tuple = tuple(route)
    packet_positions: list[int] = []
    injected = 0
    delivered = 0
    first_delivery_tick: int | None = None
    transport_operations = 0

    for tick in range(1, ticks + 1):
        if route_tuple and route_tuple[0] == field.source_id:
            packet_positions.append(0)
            injected += 1
        next_positions: list[int] = []
        for position in packet_positions:
            current_id = route_tuple[position]
            transport_operations += 1
            if not field.attempt_cell_action(current_id):
                continue
            if position == len(route_tuple) - 1:
                delivered += 1
                first_delivery_tick = first_delivery_tick or tick
                continue
            next_id = route_tuple[position + 1]
            edge_open = (
                field.cells[next_id].status.value == "active"
                and field.edge_key(current_id, next_id) not in field.blocked_edges
            )
            if edge_open:
                next_position = position + 1
                if next_position == len(route_tuple) - 1:
                    delivered += 1
                    first_delivery_tick = first_delivery_tick or tick
                else:
                    next_positions.append(next_position)
            else:
                next_positions.append(position)
        packet_positions = next_positions

    return TransportMetrics(
        mode=mode,
        ticks=ticks,
        injected=injected,
        delivered=delivered,
        throughput_per_tick=delivered / ticks,
        first_delivery_tick=first_delivery_tick,
        planning_operations=planning_operations,
        transport_operations=transport_operations,
        route=route_tuple,
        central_coordinator_required=central_coordinator_required,
    )
