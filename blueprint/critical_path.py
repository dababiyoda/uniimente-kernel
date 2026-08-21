"""The critical path: what is unblocked right now, and what is holding the rest down.

Doctrine (CRITICAL PATH): a technology may not stand above its weakest
dependency. A PROVEN capability resting on a BLUEPRINT one is not proven; it is
a claim with an unexamined floor beneath it. The ceiling for any technology is
therefore the lowest awarded rung among the technologies it depends on.

Two questions this answers, and nothing else:

    Which technologies can advance a rung today without waiting on anything?
    For everything else, exactly which dependency is holding it down?

The report ranks the frontier by leverage — how many other technologies sit
downstream of each one — because the order in which unblocked work is done
changes how much becomes unblocked next.

This module recommends. It grants nothing, activates nothing, and schedules
nothing.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from blueprint.evidence import KERNEL_ROOT
from blueprint.ladder import (
    RUNG_ORDER,
    EvidenceKind,
    Reality,
    Rung,
    missing_for,
    next_rung,
    rung_index,
)
from blueprint.registry import BindingAudit, Owner, audit, binding
from foundry.arsenal import ARSENAL


class CycleError(ValueError):
    """The arsenal dependency graph is not acyclic. Fails closed."""


def _floor() -> Rung:
    return RUNG_ORDER[0]


def dependents() -> dict[int, frozenset[int]]:
    """Reverse dependency edges: technology -> everything that depends on it."""
    out: dict[int, set[int]] = {i: set() for i in ARSENAL}
    for spec in ARSENAL.values():
        for dep in spec.dependencies:
            out[dep].add(spec.id)
    return {k: frozenset(v) for k, v in out.items()}


def topological_order() -> tuple[int, ...]:
    """Kahn's algorithm over the arsenal. Raises on any cycle."""
    indegree = {i: len(ARSENAL[i].dependencies) for i in ARSENAL}
    downstream = dependents()
    ready = sorted(i for i, d in indegree.items() if d == 0)
    order: list[int] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for child in sorted(downstream[node]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
        ready.sort()
    if len(order) != len(ARSENAL):
        stuck = sorted(set(ARSENAL) - set(order))
        raise CycleError(f"dependency cycle among technologies {stuck}")
    return tuple(order)


def transitive_dependents(root_id: int) -> frozenset[int]:
    """Everything downstream of `root_id`, however far."""
    downstream = dependents()
    seen: set[int] = set()
    stack = list(downstream[root_id])
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(downstream[node])
    return frozenset(seen)


@dataclass(frozen=True)
class TechnologyStatus:
    technology_id: int
    name: str
    category: str
    awarded_rung: Rung | None
    ceiling: Rung
    reality: Reality
    owner: Owner
    leverage: int                       # how many technologies sit downstream
    blocked_by: tuple[int, ...]         # dependencies holding the ceiling down
    gaps: tuple[str, ...]
    problems: tuple[str, ...]

    @property
    def above_foundation(self) -> bool:
        """The evidence awards more than the weakest dependency can support.

        Not a scoring error — a finding. It means a capability is being trusted
        on top of something nobody has established, and the honest reading is the
        `constrained_rung`, not the awarded one.
        """
        if self.awarded_rung is None:
            return False
        return rung_index(self.awarded_rung) > rung_index(self.ceiling)

    @property
    def constrained_rung(self) -> Rung | None:
        """The awarded rung, lowered to the ceiling its dependencies permit."""
        if self.awarded_rung is None:
            return None
        return self.ceiling if self.above_foundation else self.awarded_rung

    @property
    def can_advance(self) -> bool:
        """True when a rung is available today with no dependency in the way."""
        if self.constrained_rung is None:
            return True     # nothing proven yet; BLUEPRINT is always reachable
        if self.constrained_rung is Rung.HARDENED:
            return False
        return rung_index(self.constrained_rung) < rung_index(self.ceiling)

    @property
    def target_rung(self) -> Rung | None:
        return next_rung(self.constrained_rung)


@dataclass(frozen=True)
class UnlockLever:
    """A technology whose advance would give something downstream headroom.

    The actionable half of the stall reading. `stall_condition_fired` says the
    institution is not moving; this says exactly which technologies could move it
    and who owns each one. A technology qualifies only if it has dependents — a
    leaf can be advanced all day without raising anyone's ceiling — and only if it
    is not already at its own ceiling, since one that is cannot rise until its
    dependencies do.

    `missing` is what the *next* rung needs, so the lever is a concrete piece of
    work rather than an aspiration.
    """

    technology_id: int
    name: str
    awarded: Rung | None
    ceiling: Rung
    owner: Owner
    dependent_ids: tuple[int, ...]
    missing: tuple[EvidenceKind, ...]

    @property
    def needs_external_reality(self) -> bool:
        """No amount of building clears this one; only a reconciled consequence."""
        return EvidenceKind.EXTERNAL_OUTCOME in self.missing

    @property
    def headline(self) -> str:
        rung = self.awarded.value if self.awarded else "UNSUPPORTED"
        needs = ", ".join(k.value for k in self.missing) or "nothing"
        return (f"#{self.technology_id:<3} {self.name[:34]:<34} {rung:<11} "
                f"owner={self.owner.value:<8} unlocks {len(self.dependent_ids):<2} "
                f"needs {needs}")


@dataclass
class CriticalPathReport:
    statuses: dict[int, TechnologyStatus] = field(default_factory=dict)
    order: tuple[int, ...] = ()
    dishonest: tuple[int, ...] = ()

    @property
    def frontier(self) -> tuple[TechnologyStatus, ...]:
        """Unblocked work, highest leverage first."""
        movable = [s for s in self.statuses.values() if s.can_advance]
        return tuple(sorted(movable, key=lambda s: (-s.leverage, s.technology_id)))

    @property
    def blocked(self) -> tuple[TechnologyStatus, ...]:
        held = [s for s in self.statuses.values() if not s.can_advance and s.blocked_by]
        return tuple(sorted(held, key=lambda s: s.technology_id))

    @property
    def standing_above_foundation(self) -> tuple[TechnologyStatus, ...]:
        """Technologies whose evidence outruns what their dependencies support."""
        return tuple(sorted((s for s in self.statuses.values() if s.above_foundation),
                            key=lambda s: s.technology_id))

    def by_rung(self) -> dict[str, tuple[int, ...]]:
        out: dict[str, list[int]] = {r.value: [] for r in RUNG_ORDER}
        out["UNSUPPORTED"] = []
        for s in sorted(self.statuses.values(), key=lambda s: s.technology_id):
            key = s.awarded_rung.value if s.awarded_rung else "UNSUPPORTED"
            out[key].append(s.technology_id)
        return {k: tuple(v) for k, v in out.items()}

    def by_reality(self) -> dict[str, tuple[int, ...]]:
        out: dict[str, list[int]] = {r.value: [] for r in Reality}
        for s in sorted(self.statuses.values(), key=lambda s: s.technology_id):
            out[s.reality.value].append(s.technology_id)
        return {k: tuple(v) for k, v in out.items()}

    def unlock_levers(self) -> tuple[UnlockLever, ...]:
        """Every technology whose advance would raise someone's ceiling.

        Ordered by how many technologies sit directly downstream, because that is
        what "unlocks the most" means here.
        """
        from blueprint.evidence import resolve_all, satisfied_kinds
        from blueprint.registry import BINDINGS

        direct: dict[int, list[int]] = {}
        for technology_id, spec in ARSENAL.items():
            for dependency in spec.dependencies:
                direct.setdefault(dependency, []).append(technology_id)

        levers: list[UnlockLever] = []
        for technology_id, status in sorted(self.statuses.items()):
            downstream = direct.get(technology_id)
            if not downstream:
                continue                       # a leaf raises nobody's ceiling
            if not status.can_advance:
                continue                       # already at its own ceiling
            target = status.target_rung
            if target is None:
                continue
            binding = BINDINGS[technology_id]
            have = satisfied_kinds(resolve_all(binding.evidence))
            levers.append(UnlockLever(
                technology_id=technology_id,
                name=status.name,
                awarded=status.awarded_rung,
                ceiling=status.ceiling,
                owner=status.owner,
                dependent_ids=tuple(sorted(downstream)),
                missing=tuple(sorted(missing_for(target, have), key=lambda k: k.value)),
            ))
        return tuple(sorted(levers,
                            key=lambda l: (-len(l.dependent_ids), l.technology_id)))

    def owned_by(self, owner: Owner) -> tuple[TechnologyStatus, ...]:
        return tuple(sorted((s for s in self.statuses.values() if s.owner is owner),
                            key=lambda s: s.technology_id))


def compute(root: str = KERNEL_ROOT) -> CriticalPathReport:
    """Resolve every binding, then propagate ceilings along the dependency graph."""
    order = topological_order()
    audits: dict[int, BindingAudit] = {a.technology_id: a for a in audit(root)}
    downstream = dependents()

    report = CriticalPathReport(order=order)
    # Weakness propagates. A ceiling is computed from each dependency's
    # *constrained* rung, not its awarded one — otherwise a chain of three
    # technologies could each stand one rung above the floor beneath it and the
    # whole stack would read as sound. Topological order makes this a single pass.
    constrained: dict[int, Rung | None] = {}

    for tech_id in order:
        spec = ARSENAL[tech_id]
        a = audits[tech_id]

        deps = spec.dependencies
        if deps:
            dep_rungs = [constrained[d] for d in deps]
            if any(r is None for r in dep_rungs):
                ceiling = _floor()
            else:
                ceiling = min(dep_rungs, key=rung_index)
            blocked_by = tuple(
                d for d in deps
                if constrained[d] is None
                or rung_index(constrained[d]) <= rung_index(ceiling)
            )
        else:
            ceiling = Rung.HARDENED
            blocked_by = ()

        if a.awarded_rung is None:
            constrained[tech_id] = None
        elif rung_index(a.awarded_rung) > rung_index(ceiling):
            constrained[tech_id] = ceiling
        else:
            constrained[tech_id] = a.awarded_rung
            # Below its ceiling: nothing is holding this technology down.
            blocked_by = ()

        report.statuses[tech_id] = TechnologyStatus(
            technology_id=tech_id,
            name=spec.name,
            category=spec.category,
            awarded_rung=a.awarded_rung,
            ceiling=ceiling,
            reality=a.reality,
            owner=a.owner,
            leverage=len(transitive_dependents(tech_id)),
            blocked_by=blocked_by,
            gaps=binding(tech_id).gaps,
            problems=a.problems,
        )

    report.dishonest = tuple(
        sorted(t for t, a in audits.items() if a.problems)
    )
    return report


def unblocked_downstream_if_advanced(tech_id: int, root: str = KERNEL_ROOT) -> int:
    """How many blocked technologies would gain headroom if this one advanced one rung.

    Used to argue for an order of work, never to authorize one.
    """
    report = compute(root)
    status = report.statuses[tech_id]
    if status.awarded_rung is Rung.HARDENED:
        return 0
    return sum(1 for s in report.blocked if tech_id in s.blocked_by)
