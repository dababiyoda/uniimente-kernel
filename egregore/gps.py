"""Backcast GPS adapter (target D): goal -> active node -> active gate -> SBM -> next move.

This turns ``docs/BACKCAST_GPS.md`` into an executable control loop over the
persistent goal registry and the world model. It reuses the morphogenesis
target-state contracts (``MetricTarget``/``Direction``) for the discrepancy
arithmetic instead of inventing a second metric engine. It computes; it does
not authorize. There is no second mission authority plane.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence

from morphogenesis.contracts import Direction, MetricTarget
from morphogenesis.engine import MorphogeneticEngine

from .contracts import canonical_copy, digest, require_text
from .experience import WorldModel
from .goals import GoalSpec, GoalState, PlanNode, iso, parse_time


@dataclass(frozen=True)
class GPSFix:
    goal_id: str
    fixed_at: str
    current_position: dict[str, Any]
    active_node_id: str | None
    active_gate: str | None
    sbm: dict[str, Any] | None
    exit_evidence: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    next_interventions: tuple[dict[str, Any], ...]
    nodes_cleared: tuple[str, ...]
    complete: bool
    blockers: tuple[str, ...]
    fix_hash: str

    @property
    def execution_authority(self) -> str:
        return "none"

    def to_dict(self) -> dict[str, Any]:
        return {"goal_id": self.goal_id, "fixed_at": self.fixed_at,
                "current_position": canonical_copy(self.current_position),
                "active_node_id": self.active_node_id, "active_gate": self.active_gate,
                "sbm": canonical_copy(self.sbm), "exit_evidence": list(self.exit_evidence),
                "missing_capabilities": list(self.missing_capabilities),
                "next_interventions": [canonical_copy(i) for i in self.next_interventions],
                "nodes_cleared": list(self.nodes_cleared), "complete": self.complete,
                "blockers": list(self.blockers), "fix_hash": self.fix_hash, "execution_authority": "none"}


def metric_error(direction: str, target: float | bool, value: Any) -> float | None:
    """Normalized distance to target using the morphogenesis engine arithmetic."""
    if value is None:
        return None
    try:
        metric = MetricTarget(name="sbm", direction=Direction(direction), target=target)
        return MorphogeneticEngine._error(metric, value)
    except Exception:
        return None


def capability_present(genomes: Any, capability: str) -> bool:
    if genomes is None:
        return False
    name, _, version = capability.partition("@")
    if not version:
        return False
    return genomes.get(name, version) is not None


class BackcastGPSAdapter:
    GPS_RECORD = "egregore.gps_fix"

    def __init__(self, *, ledger: Any, world: WorldModel, genomes: Any = None,
                 source: str = "spiffe://uniimente.internal/egregore/goal-gravity"):
        self.ledger = ledger
        self.world = world
        self.genomes = genomes
        self.source = require_text("source", source)

    @property
    def execution_authority(self) -> str:
        return "none"

    def _node_status(self, node: PlanNode) -> tuple[bool, dict[str, Any], list[str]]:
        belief = self.world.belief_by_key(node.sbm)
        blockers: list[str] = []
        if belief is None:
            return False, {"name": node.sbm, "current": None, "target": node.sbm_target,
                           "direction": node.sbm_direction, "gap": None, "satisfied": False,
                           "observed_at": None, "contradicted": False}, [f"no observation for {node.sbm}"]
        if belief.contradicted:
            blockers.append(f"contradicted observation for {node.sbm}")
        gap = metric_error(node.sbm_direction, node.sbm_target, belief.value)
        satisfied = gap == 0.0 and not belief.contradicted
        return satisfied, {"name": node.sbm, "current": belief.value, "target": node.sbm_target,
                           "direction": node.sbm_direction, "gap": gap, "satisfied": satisfied,
                           "observed_at": belief.observed_at, "contradicted": belief.contradicted}, blockers

    def fix(self, spec: GoalSpec, state: GoalState, *, now: datetime | str, record: bool = True) -> GPSFix:
        fixed_at = iso(parse_time(now))
        position: dict[str, Any] = {}
        cleared: list[str] = []
        active: PlanNode | None = None
        sbm: dict[str, Any] | None = None
        blockers: list[str] = []
        for node in spec.plan:
            satisfied, metric, node_blockers = self._node_status(node)
            position[node.sbm] = metric["current"]
            if satisfied:
                cleared.append(node.node_id)
                continue
            active, sbm, blockers = node, metric, node_blockers
            break
        revoked = set(state.preferences.get("revoked_capabilities", []))
        missing: tuple[str, ...] = ()
        next_moves: tuple[dict[str, Any], ...] = ()
        if active is not None:
            missing = tuple(c for c in active.requires_capabilities
                            if c in revoked or not capability_present(self.genomes, c))
            next_moves = tuple(i.to_dict() for i in active.interventions)
        fix = GPSFix(
            goal_id=spec.goal_id, fixed_at=fixed_at, current_position=position,
            active_node_id=active.node_id if active else None, active_gate=active.gate if active else None,
            sbm=sbm, exit_evidence=tuple(active.exit_evidence) if active else (),
            missing_capabilities=missing, next_interventions=next_moves, nodes_cleared=tuple(cleared),
            complete=active is None, blockers=tuple(blockers),
            fix_hash=digest({"kind": "egregore-gps-fix", "goal_id": spec.goal_id, "position": position,
                             "active_node_id": active.node_id if active else None, "missing": list(missing),
                             "blockers": blockers}))
        if record:
            self.ledger.append(self.GPS_RECORD, {"source": self.source, "fix": fix.to_dict(), "disposition": "computed_only"})
        return fix
