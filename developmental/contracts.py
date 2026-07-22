"""Frozen contracts for the UNIIMENTE developmental substrate benchmark.

These contracts describe a simulation, not biological life or production
authority. CellState v0.1, LocalRuleGenome v0.1, and IntelligenceGenome v0.1
are immutable so the benchmark cannot rewrite its rules after observing the
result.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any


class TissueType(StrEnum):
    SENSOR = "sensor"
    TRANSPORT = "transport"
    ACTUATOR = "actuator"


class CellStatus(StrEnum):
    ACTIVE = "active"
    REMOVED = "removed"


class TernarySignal(IntEnum):
    INHIBIT = -1
    NEUTRAL = 0
    ACTIVATE = 1


class DevelopmentalVerdict(StrEnum):
    MECHANICS_VALIDATED_NOT_PRODUCTION_AUTHORIZED = (
        "MECHANICS_VALIDATED_NOT_PRODUCTION_AUTHORIZED"
    )
    NO_MATERIAL_ADVANTAGE = "NO_MATERIAL_ADVANTAGE"
    INVALID_EXPERIMENT = "INVALID_EXPERIMENT"


@dataclass(frozen=True)
class CellState:
    """CellState v0.1 — one bounded local state snapshot."""

    cell_id: str
    x: int
    y: int
    tissue: TissueType
    status: CellStatus = CellStatus.ACTIVE
    potential: int | None = None
    resource_units: int = 0
    signal: TernarySignal = TernarySignal.NEUTRAL
    generation: int = 0
    schema_version: str = "0.1"

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.schema_version != "0.1":
            problems.append("CellState schema_version must be 0.1")
        if not self.cell_id:
            problems.append("cell_id is required")
        if self.x < 0 or self.y < 0:
            problems.append("cell coordinates must be nonnegative")
        if self.resource_units < 0:
            problems.append("resource units cannot be negative")
        if self.generation < 0:
            problems.append("generation cannot be negative")
        if self.status is CellStatus.REMOVED and self.signal is not TernarySignal.INHIBIT:
            problems.append("removed cells must emit INHIBIT")
        return problems


@dataclass(frozen=True)
class LocalRuleGenome:
    """LocalRuleGenome v0.1 — rules available to every cell."""

    neighbor_mode: str = "von_neumann"
    field_update: str = "asynchronous_local_relaxation"
    resource_policy: str = "move_to_strictly_lower_neighbor_potential"
    max_transfer_per_tick: int = 1
    prohibit_exact_restoration: bool = True
    removed_cells_may_reactivate: bool = False
    external_effects_allowed: bool = False
    schema_version: str = "0.1"

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.schema_version != "0.1":
            problems.append("LocalRuleGenome schema_version must be 0.1")
        if self.neighbor_mode != "von_neumann":
            problems.append("v0.1 supports only von_neumann neighborhoods")
        if self.field_update != "asynchronous_local_relaxation":
            problems.append("v0.1 field update is fixed")
        if self.resource_policy != "move_to_strictly_lower_neighbor_potential":
            problems.append("v0.1 resource policy is fixed")
        if self.max_transfer_per_tick != 1:
            problems.append("v0.1 permits exactly one hop per packet per tick")
        if not self.prohibit_exact_restoration:
            problems.append("exact restoration must be prohibited")
        if self.removed_cells_may_reactivate:
            problems.append("removed cells may not reactivate")
        if self.external_effects_allowed:
            problems.append("developmental benchmark may not create external effects")
        return problems


@dataclass(frozen=True)
class IntelligenceGenome:
    """IntelligenceGenome v0.1 — benchmark target and promotion constraints."""

    target_form: str = "TARGET_FORM_001"
    minimum_cells: int = 100
    required_tissues: tuple[TissueType, ...] = (
        TissueType.SENSOR,
        TissueType.TRANSPORT,
        TissueType.ACTUATOR,
    )
    perturbation_remove_fraction: float = 0.20
    recovery_throughput_ratio_min: float = 0.90
    max_compute_ratio_vs_adaptive_central: float = 4.0
    max_false_activations: int = 0
    maximum_recovery_ticks: int = 40
    production_authority: bool = False
    authorization_state: str = "SIMULATED_NOT_AUTHORIZED"
    schema_version: str = "0.1"

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.schema_version != "0.1":
            problems.append("IntelligenceGenome schema_version must be 0.1")
        if self.target_form != "TARGET_FORM_001":
            problems.append("v0.1 target form is TARGET_FORM_001")
        if self.minimum_cells < 100:
            problems.append("benchmark requires at least 100 cells")
        if set(self.required_tissues) != set(TissueType):
            problems.append("all three tissues are required")
        if self.perturbation_remove_fraction != 0.20:
            problems.append("benchmark perturbation is fixed at 20% cell removal")
        if not 0 < self.recovery_throughput_ratio_min <= 1:
            problems.append("recovery throughput ratio must be within (0,1]")
        if self.max_compute_ratio_vs_adaptive_central <= 0:
            problems.append("compute ratio ceiling must be positive")
        if self.max_false_activations != 0:
            problems.append("false activation ceiling is zero")
        if self.maximum_recovery_ticks <= 0:
            problems.append("maximum recovery ticks must be positive")
        if self.production_authority:
            problems.append("simulation may not carry production authority")
        if self.authorization_state != "SIMULATED_NOT_AUTHORIZED":
            problems.append("authorization state is fixed to SIMULATED_NOT_AUTHORIZED")
        return problems


@dataclass(frozen=True)
class PerturbationSpec:
    remove_fraction: float = 0.20
    block_original_route: bool = True
    prohibit_exact_restoration: bool = True
    deterministic_seed: int = 17

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.remove_fraction != 0.20:
            problems.append("TARGET_FORM_001 removes exactly 20% of cells")
        if not self.block_original_route:
            problems.append("original route must be blocked")
        if not self.prohibit_exact_restoration:
            problems.append("exact restoration must be prohibited")
        return problems


@dataclass(frozen=True)
class TransportMetrics:
    mode: str
    ticks: int
    injected: int
    delivered: int
    throughput_per_tick: float
    first_delivery_tick: int | None
    planning_operations: int
    transport_operations: int
    route: tuple[str, ...]
    central_coordinator_required: bool


@dataclass(frozen=True)
class DevelopmentalBenchmarkReport:
    benchmark_id: str
    verdict: DevelopmentalVerdict
    cell_count: int
    tissue_counts: dict[str, int]
    removed_cell_count: int
    removed_fraction: float
    original_route: tuple[str, ...]
    recovered_route: tuple[str, ...]
    original_route_blocked: bool
    exact_restoration_attempts: int
    false_activations: int
    distributed: TransportMetrics
    static_central: TransportMetrics
    adaptive_central: TransportMetrics
    recovery_throughput_ratio: float
    compute_ratio_vs_adaptive_central: float
    checks: tuple[str, ...]
    failures: tuple[str, ...]
    authorization_state: str = "SIMULATED_NOT_AUTHORIZED"
    external_effects: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
