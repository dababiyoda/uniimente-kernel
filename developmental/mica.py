"""MICA — Multiscale Intelligence Coordination Architecture v0.1.

MICA implements a bounded local target field over a 2-D cellular lattice.
Each cell reads only its immediate von Neumann neighbors. The sink publishes
potential zero; potential changes propagate as local messages. Packets move
one hop per tick to a strictly lower potential. No cell receives a global
route and no method creates an external effect.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, replace
from math import inf
from typing import Iterable

from .contracts import (
    CellState,
    CellStatus,
    LocalRuleGenome,
    TernarySignal,
    TissueType,
)


class DevelopmentalError(ValueError):
    """Invalid topology, mutation, or developmental operation."""


@dataclass
class RuntimeCell:
    cell_id: str
    x: int
    y: int
    tissue: TissueType
    status: CellStatus = CellStatus.ACTIVE
    potential: float = inf
    signal: TernarySignal = TernarySignal.NEUTRAL
    resource_units: int = 0
    generation: int = 0

    def snapshot(self) -> CellState:
        potential = None if self.potential == inf else int(self.potential)
        state = CellState(
            cell_id=self.cell_id,
            x=self.x,
            y=self.y,
            tissue=self.tissue,
            status=self.status,
            potential=potential,
            resource_units=self.resource_units,
            signal=self.signal,
            generation=self.generation,
        )
        problems = state.validate()
        if problems:
            raise DevelopmentalError(f"invalid CellState snapshot: {problems}")
        return state


class MICAField:
    """Bounded cellular field for TARGET_FORM_001."""

    def __init__(
        self,
        *,
        width: int = 12,
        height: int = 10,
        rules: LocalRuleGenome | None = None,
    ) -> None:
        self.rules = rules or LocalRuleGenome()
        problems = self.rules.validate()
        if problems:
            raise DevelopmentalError(f"invalid LocalRuleGenome: {problems}")
        if width * height < 100:
            raise DevelopmentalError("TARGET_FORM_001 requires at least 100 cells")
        if width < 6 or height < 5:
            raise DevelopmentalError("field is too small to form three tissues and alternate routes")
        self.width = width
        self.height = height
        self.cells: dict[str, RuntimeCell] = {}
        for y in range(height):
            for x in range(width):
                if x < 2:
                    tissue = TissueType.SENSOR
                elif x >= width - 2:
                    tissue = TissueType.ACTUATOR
                else:
                    tissue = TissueType.TRANSPORT
                cell_id = self.cell_id(x, y)
                self.cells[cell_id] = RuntimeCell(cell_id, x, y, tissue)
        self.source_id = self.cell_id(0, height // 2)
        self.sink_id = self.cell_id(width - 1, height // 2)
        self.blocked_edges: set[tuple[str, str]] = set()
        self.removed_cell_ids: set[str] = set()
        self.original_route_edges: set[tuple[str, str]] = set()
        self.planning_operations = 0
        self.field_messages = 0
        self.transport_operations = 0
        self.false_activations = 0
        self.exact_restoration_attempts = 0

    @staticmethod
    def cell_id(x: int, y: int) -> str:
        return f"cell-{x:02d}-{y:02d}"

    @staticmethod
    def edge_key(left: str, right: str) -> tuple[str, str]:
        return tuple(sorted((left, right)))

    def clone(self) -> "MICAField":
        clone = MICAField(width=self.width, height=self.height, rules=self.rules)
        clone.blocked_edges = set(self.blocked_edges)
        clone.original_route_edges = set(self.original_route_edges)
        clone.removed_cell_ids = set(self.removed_cell_ids)
        for cell_id, source in self.cells.items():
            target = clone.cells[cell_id]
            target.status = source.status
            target.potential = source.potential
            target.signal = source.signal
            target.resource_units = source.resource_units
            target.generation = source.generation
        clone.planning_operations = self.planning_operations
        clone.field_messages = self.field_messages
        clone.transport_operations = self.transport_operations
        clone.false_activations = self.false_activations
        clone.exact_restoration_attempts = self.exact_restoration_attempts
        return clone

    def active_ids(self) -> tuple[str, ...]:
        return tuple(sorted(
            cell_id for cell_id, cell in self.cells.items()
            if cell.status is CellStatus.ACTIVE
        ))

    def tissue_counts(self) -> dict[str, int]:
        counts = Counter(cell.tissue.value for cell in self.cells.values())
        return dict(sorted(counts.items()))

    def neighbors(self, cell_id: str) -> tuple[str, ...]:
        if cell_id not in self.cells:
            raise DevelopmentalError(f"unknown cell {cell_id}")
        cell = self.cells[cell_id]
        if cell.status is CellStatus.REMOVED:
            return ()
        candidates = (
            (cell.x - 1, cell.y),
            (cell.x + 1, cell.y),
            (cell.x, cell.y - 1),
            (cell.x, cell.y + 1),
        )
        result: list[str] = []
        for x, y in candidates:
            if not (0 <= x < self.width and 0 <= y < self.height):
                continue
            neighbor_id = self.cell_id(x, y)
            if self.cells[neighbor_id].status is CellStatus.REMOVED:
                continue
            if self.edge_key(cell_id, neighbor_id) in self.blocked_edges:
                continue
            result.append(neighbor_id)
        return tuple(sorted(result))

    def snapshots(self) -> tuple[CellState, ...]:
        return tuple(self.cells[cell_id].snapshot() for cell_id in sorted(self.cells))

    def propagate_target_field(self) -> tuple[int, int]:
        """Propagate sink potential using local asynchronous messages.

        Returns `(planning_operations, wavefront_depth)` for this propagation.
        """
        if self.cells[self.sink_id].status is CellStatus.REMOVED:
            raise DevelopmentalError("sink cell is removed")
        for cell in self.cells.values():
            if cell.status is CellStatus.REMOVED:
                cell.potential = inf
                cell.signal = TernarySignal.INHIBIT
            else:
                cell.potential = inf
                cell.signal = TernarySignal.NEUTRAL
        self.cells[self.sink_id].potential = 0
        self.cells[self.sink_id].signal = TernarySignal.ACTIVATE
        queue: deque[str] = deque([self.sink_id])
        operations = 0
        messages = 0
        depth = 0
        while queue:
            current_id = queue.popleft()
            current = self.cells[current_id]
            depth = max(depth, int(current.potential))
            for neighbor_id in self.neighbors(current_id):
                operations += 1
                messages += 1
                neighbor = self.cells[neighbor_id]
                candidate = current.potential + 1
                if candidate < neighbor.potential:
                    neighbor.potential = candidate
                    neighbor.signal = TernarySignal.ACTIVATE
                    queue.append(neighbor_id)
        self.planning_operations += operations
        self.field_messages += messages
        return operations, depth

    def local_route(self, start_id: str | None = None) -> tuple[str, ...]:
        """Follow strictly lower local potentials without a master route."""
        current_id = start_id or self.source_id
        if current_id not in self.cells or self.cells[current_id].status is CellStatus.REMOVED:
            return ()
        if self.cells[current_id].potential == inf:
            return ()
        route = [current_id]
        seen = {current_id}
        while current_id != self.sink_id:
            current = self.cells[current_id]
            lower = [
                neighbor_id for neighbor_id in self.neighbors(current_id)
                if self.cells[neighbor_id].potential < current.potential
            ]
            if not lower:
                return ()
            next_id = min(
                lower,
                key=lambda neighbor_id: (
                    self.cells[neighbor_id].potential,
                    neighbor_id,
                ),
            )
            if next_id in seen:
                raise DevelopmentalError("local potential field produced a cycle")
            route.append(next_id)
            seen.add(next_id)
            current_id = next_id
        return tuple(route)

    def global_shortest_path(self) -> tuple[tuple[str, ...], int]:
        """Centralized BFS used only by the adaptive comparison baseline."""
        if self.cells[self.source_id].status is CellStatus.REMOVED:
            return (), 0
        queue: deque[str] = deque([self.source_id])
        prior: dict[str, str | None] = {self.source_id: None}
        operations = 0
        while queue:
            current = queue.popleft()
            if current == self.sink_id:
                break
            for neighbor in self.neighbors(current):
                operations += 1
                if neighbor in prior:
                    continue
                prior[neighbor] = current
                queue.append(neighbor)
        if self.sink_id not in prior:
            return (), operations
        path: list[str] = []
        current: str | None = self.sink_id
        while current is not None:
            path.append(current)
            current = prior[current]
        path.reverse()
        return tuple(path), operations

    def block_route(self, route: Iterable[str]) -> int:
        route_tuple = tuple(route)
        if len(route_tuple) < 2:
            raise DevelopmentalError("route must contain at least two cells")
        blocked = 0
        for left, right in zip(route_tuple, route_tuple[1:]):
            edge = self.edge_key(left, right)
            self.original_route_edges.add(edge)
            if edge not in self.blocked_edges:
                self.blocked_edges.add(edge)
                blocked += 1
        return blocked

    def select_deterministic_removals(self, fraction: float = 0.20) -> tuple[str, ...]:
        if fraction != 0.20:
            raise DevelopmentalError("TARGET_FORM_001 removal fraction is fixed at 20%")
        count = round(len(self.cells) * fraction)
        protected = {
            cell_id for cell_id, cell in self.cells.items()
            if cell.y == 2 or cell.x in {0, self.width - 1}
        }
        protected.update({self.source_id, self.sink_id})
        candidates = [
            cell_id for cell_id in self.cells
            if cell_id not in protected
        ]
        candidates.sort(key=lambda cell_id: (
            (self.cells[cell_id].x * 37 + self.cells[cell_id].y * 61 + 17) % 997,
            cell_id,
        ))
        if len(candidates) < count:
            raise DevelopmentalError("not enough unprotected cells for perturbation")
        return tuple(candidates[:count])

    def remove_cells(self, cell_ids: Iterable[str]) -> tuple[str, ...]:
        removed: list[str] = []
        for cell_id in tuple(cell_ids):
            if cell_id in {self.source_id, self.sink_id}:
                raise DevelopmentalError("source and sink are protected")
            cell = self.cells.get(cell_id)
            if cell is None:
                raise DevelopmentalError(f"unknown cell {cell_id}")
            if cell.status is CellStatus.REMOVED:
                continue
            cell.status = CellStatus.REMOVED
            cell.potential = inf
            cell.signal = TernarySignal.INHIBIT
            cell.resource_units = 0
            self.removed_cell_ids.add(cell_id)
            removed.append(cell_id)
        return tuple(removed)

    def attempt_exact_restoration(self, cell_id: str) -> None:
        self.exact_restoration_attempts += 1
        cell = self.cells.get(cell_id)
        if cell is None:
            raise DevelopmentalError(f"unknown cell {cell_id}")
        if cell.status is not CellStatus.REMOVED:
            raise DevelopmentalError("exact restoration test requires a removed cell")
        raise DevelopmentalError("exact restoration is constitutionally prohibited")

    def attempt_cell_action(self, cell_id: str) -> bool:
        cell = self.cells.get(cell_id)
        if cell is None:
            raise DevelopmentalError(f"unknown cell {cell_id}")
        if cell.status is CellStatus.REMOVED:
            self.false_activations += 1
            return False
        self.transport_operations += 1
        return True

    def is_route_open(self, route: Iterable[str]) -> bool:
        route_tuple = tuple(route)
        if not route_tuple or route_tuple[0] != self.source_id or route_tuple[-1] != self.sink_id:
            return False
        for cell_id in route_tuple:
            if cell_id not in self.cells or self.cells[cell_id].status is CellStatus.REMOVED:
                return False
        return all(
            self.edge_key(left, right) not in self.blocked_edges
            for left, right in zip(route_tuple, route_tuple[1:])
        )

    def with_active_snapshots(self) -> tuple[CellState, ...]:
        return tuple(
            snapshot for snapshot in self.snapshots()
            if snapshot.status is CellStatus.ACTIVE
        )
