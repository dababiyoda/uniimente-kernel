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
    missing_relationships: tuple[str, ...] = ()
    route_changed: bool = False
    later_nodes_satisfied: tuple[str, ...] = ()

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
                "blockers": list(self.blockers), "fix_hash": self.fix_hash,
                "missing_relationships": list(self.missing_relationships), "route_changed": self.route_changed,
                "later_nodes_satisfied": list(self.later_nodes_satisfied), "execution_authority": "none"}


def metric_error(direction: str, target: float | bool, value: Any) -> float | None:
    """Normalized distance to target using the morphogenesis engine arithmetic.

    A boolean target needs a boolean value and a numeric target a numeric value; Python's
    ``True == 1`` must never satisfy a gate.
    """
    if value is None or isinstance(value, bool) != isinstance(target, bool):
        return None
    if not isinstance(value, (int, float, bool)):
        return None
    try:
        metric = MetricTarget(name="sbm", direction=Direction(direction), target=target)
        return MorphogeneticEngine._error(metric, value)
    except Exception:
        return None


def admissible_methods(problem_class: str | None) -> tuple[frozenset, frozenset] | None:
    """Which methods may produce a gate's own reading, and which must also be on record about its subject.

    From the router table: the gate's reading must come from an ``any_of`` method (or the ``all_of`` methods
    when the class has no alternatives); every ``all_of`` method of a class that also has alternatives must
    have its own trusted reading about the same subject. A lone critique therefore never proves code correct,
    and a method the router never admits for a class cannot clear it by sharing a label with one it does."""
    if problem_class is None:
        return None
    from capabilities.router import PROBLEM_CLASSES
    spec = PROBLEM_CLASSES[problem_class]
    primary = frozenset(spec["any_of"]) or frozenset(spec["all_of"])
    support = frozenset(spec["all_of"]) if spec["any_of"] else frozenset()
    return primary, support


def admissible_evidence(problem_class: str | None) -> set[str] | None:
    """What the gate's own reading can count as (labels of its admissible methods); None for an untyped gate."""
    methods = admissible_methods(problem_class)
    if methods is None:
        return None
    from capabilities.router import EPISTEMIC_METHODS
    return {EPISTEMIC_METHODS[m]["establishes"] for m in methods[0]}


def human_only_class(problem_class: str | None) -> bool:
    """Only a person can answer it (every admissible method is human-only)."""
    methods = admissible_methods(problem_class)
    if methods is None:
        return False
    from capabilities.router import HUMAN_ONLY_METHODS
    return bool(methods[0]) and methods[0] <= HUMAN_ONLY_METHODS


def capability_present(genomes: Any, capability: str) -> bool:
    if genomes is None:
        return False
    name, _, version = capability.partition("@")
    if not version:
        return False
    return genomes.get(name, version) is not None


class BackcastGPSAdapter:
    GPS_RECORD = "egregore.gps_fix"

    TRUST_RANK = {"untrusted": 0, "attributed": 1, "verified": 2}

    def __init__(self, *, ledger: Any, world: WorldModel, genomes: Any = None, memory: Any = None,
                 source: str = "spiffe://uniimente.internal/egregore/goal-gravity", min_trust: str = "attributed"):
        self.ledger = ledger
        self.world = world
        self.genomes = genomes
        self.memory = memory   # memory.causal.CausalMemory: precedent weighting orders candidate moves
        self.source = require_text("source", source)
        if min_trust not in self.TRUST_RANK:
            raise ValueError(f"unknown trust level {min_trust!r}")
        self.min_trust = min_trust   # an untrusted, self-labelled signal can never clear a gate

    def _precedent(self, action_class: str) -> float | None:
        """Weighted success of this action class from ledgered outcomes (CausalMemory), if any."""
        if self.memory is None:
            return None
        try:
            weighting = self.memory.outcome_weighting(action_class)
        except Exception:
            return None
        return weighting.get("weighted_success")

    def _relationship_present(self, entity: str) -> bool:
        belief = self.world.belief(entity, "relationship")
        return bool(belief and belief.value and not belief.contradicted)

    @property
    def execution_authority(self) -> str:
        return "none"

    def _node_status(self, node: PlanNode, goal_id: str | None = None) -> tuple[bool, dict[str, Any], list[str]]:
        admissible = admissible_evidence(node.problem_class)
        methods = admissible_methods(node.problem_class)
        if human_only_class(node.problem_class):
            return self._human_gate_status(node, goal_id, admissible)
        belief = self.world.belief_by_key(node.sbm)
        blockers: list[str] = []
        if belief is None:
            return False, {"name": node.sbm, "current": None, "target": node.sbm_target,
                           "direction": node.sbm_direction, "gap": None, "satisfied": False,
                           "observed_at": None, "contradicted": False}, [f"no observation for {node.sbm}"]
        if belief.contradicted:
            blockers.append(f"contradicted observation for {node.sbm}")
        trusted = self.TRUST_RANK.get(belief.trust_level, 0) >= self.TRUST_RANK[self.min_trust]
        if not trusted:
            blockers.append(f"untrusted observation for {node.sbm} (trust {belief.trust_level}; need {self.min_trust})")
        gap = metric_error(node.sbm_direction, node.sbm_target, belief.value)
        if gap is None and belief.value is not None:
            blockers.append(f"type mismatch for {node.sbm}: target {type(node.sbm_target).__name__}, observed {type(belief.value).__name__}")
        # Typed evidence (Competency Compiler): a gate that poses a problem class clears only on a reading made by
        # a method the router admits for that class, plus a trusted reading from each method the class requires
        # alongside. A forum post never proves demand; a simulation never proves an external fact; a critique
        # alone never proves code correct.
        typed_ok = methods is None or belief.method in methods[0]
        if not typed_ok:
            blockers.append(f"evidence for {node.sbm} establishes {belief.establishes or 'nothing typed'} "
                            f"(method {belief.method or 'undeclared'}); a {node.problem_class} gate needs "
                            f"{', '.join(sorted(admissible))} (by {', '.join(sorted(methods[0]))})")
        missing_support = sorted(m for m in (methods[1] if methods else ()) if not self._supported(node.sbm, m))
        for m in missing_support:
            blockers.append(f"a {node.problem_class} gate also needs a trusted {m} reading about "
                            f"{node.sbm.split('.', 1)[0]}")
        satisfied = gap == 0.0 and not belief.contradicted and trusted and typed_ok and not missing_support
        return satisfied, {"name": node.sbm, "current": belief.value, "target": node.sbm_target,
                           "direction": node.sbm_direction, "gap": gap, "satisfied": satisfied,
                           "observed_at": belief.observed_at, "contradicted": belief.contradicted,
                           "trust_level": belief.trust_level, "establishes": belief.establishes,
                           "required_evidence": sorted(admissible) if admissible is not None else None,
                           "required_methods": sorted(methods[0]) if methods else None,
                           "required_alongside": sorted(methods[1]) if methods else None}, blockers

    def _supported(self, sbm: str, method: str) -> bool:
        subject = sbm.split(".", 1)[0]
        return any(b.subject == subject and b.method == method and not b.contradicted
                   and self.TRUST_RANK.get(b.trust_level, 0) >= self.TRUST_RANK[self.min_trust]
                   for b in self.world.beliefs().values())

    def _human_gate_status(self, node: PlanNode, goal_id: str | None,
                           admissible: set[str] | None) -> tuple[bool, dict[str, Any], list[str]]:
        """An authorization or legal gate reads the founder's decision recorded for THIS goal, never a shared belief.

        A decision is consent for one goal's gate: accepting it for one goal never clears another goal that uses
        the same metric name, and no sensor reading can stand in for it or contradict it (sensor claims of a
        human-only method are stripped at integration and retained as data)."""
        reading = self.world.human_reading(goal_id, node.sbm) if goal_id else None
        base = {"name": node.sbm, "target": node.sbm_target, "direction": node.sbm_direction,
                "required_evidence": sorted(admissible) if admissible is not None else None,
                "required_methods": sorted(admissible_methods(node.problem_class)[0]), "required_alongside": [],
                "decision_scope": "this goal only"}
        if reading is None:
            return False, {**base, "current": None, "gap": None, "satisfied": False, "observed_at": None,
                           "contradicted": False}, [f"no founder decision recorded for this goal's gate {node.sbm}"]
        blockers: list[str] = []
        trusted = self.TRUST_RANK.get(reading["trust_level"], 0) >= self.TRUST_RANK[self.min_trust]
        if not trusted:
            blockers.append(f"untrusted decision for {node.sbm} (trust {reading['trust_level']}; need {self.min_trust})")
        gap = metric_error(node.sbm_direction, node.sbm_target, reading["value"])
        if gap is None and reading["value"] is not None:
            blockers.append(f"type mismatch for {node.sbm}: target {type(node.sbm_target).__name__}, "
                            f"observed {type(reading['value']).__name__}")
        elif gap:
            blockers.append(f"the founder's recorded decision for {node.sbm} does not meet the gate")
        satisfied = gap == 0.0 and trusted
        return satisfied, {**base, "current": reading["value"], "gap": gap, "satisfied": satisfied,
                           "observed_at": reading["observed_at"], "contradicted": False,
                           "trust_level": reading["trust_level"], "establishes": reading["establishes"]}, blockers

    def fix(self, spec: GoalSpec, state: GoalState, *, now: datetime | str, record: bool = True) -> GPSFix:
        fixed_at = iso(parse_time(now))
        position: dict[str, Any] = {}
        cleared: list[str] = []
        active: PlanNode | None = None
        sbm: dict[str, Any] | None = None
        blockers: list[str] = []
        later_satisfied: list[str] = []
        for node in spec.plan:
            satisfied, metric, node_blockers = self._node_status(node, spec.goal_id)
            position[node.sbm] = metric["current"]
            if active is None:
                if satisfied:
                    cleared.append(node.node_id)
                    continue
                active, sbm, blockers = node, metric, node_blockers
            elif satisfied:
                # "Is there now a better route?": a later state is already true; the plan can be re-sequenced.
                later_satisfied.append(node.node_id)
        revoked = set(state.preferences.get("revoked_capabilities", []))
        missing: tuple[str, ...] = ()
        missing_rel: tuple[str, ...] = ()
        next_moves: tuple[dict[str, Any], ...] = ()
        if active is not None:
            missing = tuple(c for c in active.requires_capabilities
                            if c in revoked or not capability_present(self.genomes, c))
            missing_rel = tuple(r for r in active.requires_relationships if not self._relationship_present(r))
            moves = []
            for i in active.interventions:
                entry = i.to_dict()
                entry["precedent_weighted_success"] = self._precedent(i.action_class)
                moves.append(entry)
            # Evidence-ordered: moves with the strongest ledgered precedent first; declared order breaks ties.
            moves.sort(key=lambda m: (-(m["precedent_weighted_success"] if m["precedent_weighted_success"] is not None else -1.0)))
            next_moves = tuple(moves)
        fix = GPSFix(
            goal_id=spec.goal_id, fixed_at=fixed_at, current_position=position,
            active_node_id=active.node_id if active else None, active_gate=active.gate if active else None,
            sbm=sbm, exit_evidence=tuple(active.exit_evidence) if active else (),
            missing_capabilities=missing, next_interventions=next_moves, nodes_cleared=tuple(cleared),
            complete=active is None, blockers=tuple(blockers),
            fix_hash=digest({"kind": "egregore-gps-fix", "goal_id": spec.goal_id, "position": position,
                             "active_node_id": active.node_id if active else None, "missing": list(missing),
                             "missing_relationships": list(missing_rel), "blockers": blockers,
                             "later": later_satisfied}),
            missing_relationships=missing_rel, route_changed=bool(later_satisfied),
            later_nodes_satisfied=tuple(later_satisfied))
        if record:
            self.ledger.append(self.GPS_RECORD, {"source": self.source, "fix": fix.to_dict(), "disposition": "computed_only"})
        return fix
