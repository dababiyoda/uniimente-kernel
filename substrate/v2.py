"""Bounded-local multi-branch developmental substrate.

NEW MODULE. `substrate/cell.py` and `substrate/tissue.py` are left untouched so
PR #60 remains exactly as reported.

THE FIVE DEFECTS, REPRODUCED THEN REMOVED
-----------------------------------------

A. BRANCH IDENTITY COLLISION (the real first defect, not fan-in).
   v1 keyed duplicate suppression on `(origin, seq)`, and `_differentiate`
   emitted every downstream role with the SAME `seq = sig.seq + 1`. Measured:
   a cell emitting verify_a and verify_b produced 2 distinct keys for 3
   signals, and the downstream cell deduped one branch away.

   FIX: signals carry a BRANCH LINEAGE - a tuple extended by the emitting
   cell's own local emission index. Uniqueness comes from the path, not from a
   counter anyone owns. A cell knows only its own index, so this stays
   bounded-local. Mutation of network-protocol message identity: sequence
   spaces become per-branch lineages rather than one channel counter.

B. SINGLE UPSTREAM. v1 stored `attached_to: Optional[str]` and bonded to the
   first compatible neighbour. A join role needs verify_a AND verify_b.

   FIX: a DependencyReceptor accumulates bindings per required role and the
   cell differentiates only when every requirement is locally satisfied.
   Mutation of the database keyed-join: the join is owned by the consuming
   cell and closes on locally observed evidence, with no coordinator.

C. MOTIF REFUSAL NOT ENFORCED. v1's runner evaluated a proposal, logged a
   refusal, wrote Tri.HOLD, and then ran development, where ACTIVATE could
   overwrite HOLD. 62 refusals proved 62 classifications, not 62 preventions.

   FIX: the constraint check happens INSIDE the attachment transition. A
   refused proposal cannot commit, and the counter increments only when a
   commit was actually prevented.

D. GLOBAL REDUNDANCY SCAN. v1 computed sibling redundancy by scanning every
   cell in the tissue.

   FIX: redundancy is counted over the cell's own neighbours only. A module
   -level counter records any global scan; the experiment asserts it stays 0.

E. SHARED RECEPTOR. One receptor served every cell. Each cell now owns its own.

ORDER INDEPENDENCE
------------------

A join must not depend on the order its evidence arrives in. A demand that
reaches a cell before that cell's upstreams have differentiated is RETAINED as
pending, not consumed: the cell keeps wanting the role and closes the join on
whatever tick the last binding becomes locally observable. Without this, a
demand arriving one tick early is silently swallowed by duplicate suppression,
and an asymmetric-depth join deadlocks whenever the late arm's second demand is
lost to a partition.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, Optional

from .causal import CausalMotif
from .motif_channel import ConstraintReceptor, LocalProposal

# Incremented by any code that reads whole-tissue state during FORMATION.
# The experiment asserts this stays at zero.
GLOBAL_SCAN_COUNTER = {"n": 0}


def note_global_scan() -> None:
    GLOBAL_SCAN_COUNTER["n"] += 1


class Tri(IntEnum):
    INHIBIT = -1
    HOLD = 0
    ACTIVATE = 1


@dataclass(frozen=True)
class BranchSignal:
    """A developmental request carrying its own causal lineage.

    `lineage` is the path of local emission indices from the origin of the
    deficit to here. Two branches emitted by one cell in one tick differ in
    their final element, so they can never collide - and no global counter is
    required to make that true.
    """
    role: str
    sign: Tri
    intensity: float
    ttl: int
    origin: str
    lineage: tuple[int, ...]

    @property
    def branch_id(self) -> str:
        """Identity for duplicate suppression. Distinct per branch."""
        return f"{self.origin}:{'.'.join(map(str, self.lineage))}:{self.role}"

    def child(self, role: str, index: int) -> "BranchSignal":
        return BranchSignal(role=role, sign=self.sign,
                            intensity=self.intensity * 0.9, ttl=self.ttl - 1,
                            origin=self.origin, lineage=self.lineage + (index,))

    def relay(self) -> "BranchSignal":
        """Propagate unchanged except for decay. Same branch id, so a second
        arrival by another route is correctly suppressed."""
        return BranchSignal(self.role, self.sign, self.intensity * 0.75,
                            self.ttl - 1, self.origin, self.lineage)


@dataclass
class Interface2:
    """`requires` is ALL-of. That is what makes a join expressible."""
    provides: str
    requires: tuple[str, ...] = ()
    emits: tuple[str, ...] = ()
    quorum: Optional[int] = None      # if set, any `quorum` of `requires`


class DependencyReceptor:
    """A cell's local join. Accumulates bindings; closes when satisfied.

    Monotonic: a binding once observed is never withdrawn by a duplicate or a
    reordering. That is what makes order-independence hold.
    """

    __slots__ = ("required", "quorum", "bindings", "consumed")

    def __init__(self, required: tuple[str, ...], quorum: Optional[int] = None):
        self.required = required
        self.quorum = quorum
        self.bindings: dict[str, str] = {}
        self.consumed: set[str] = set()

    def bind(self, role: str, cell_id: str) -> None:
        self.bindings.setdefault(role, cell_id)      # monotonic

    def release(self, cell_id: str) -> tuple[str, ...]:
        """Drop bindings to a cell OBSERVED to be gone.

        This is the one thing that reopens a closed join, and it is not a
        violation of monotonicity: monotonicity says a duplicate or a
        reordering never withdraws evidence. Death is neither. The cell must
        have locally observed the loss - it cannot release on hearsay.
        """
        lost = tuple(r for r, c in self.bindings.items() if c == cell_id)
        for r in lost:
            del self.bindings[r]
        return lost

    def satisfied(self) -> bool:
        if not self.required:
            return True
        if self.quorum is not None:
            return len(self.bindings) >= self.quorum
        return all(r in self.bindings for r in self.required)

    def unresolved(self) -> tuple[str, ...]:
        return tuple(r for r in self.required if r not in self.bindings)


@dataclass
class Cell2:
    cell_id: str
    capability: str
    interface: Interface2
    neighbours: set[str] = field(default_factory=set)
    resource: float = 1.0
    differentiated_role: Optional[str] = None
    dissolved: bool = False
    inbox: list[tuple[str, BranchSignal]] = field(default_factory=list)
    outbox: list[tuple[str, BranchSignal]] = field(default_factory=list)
    pending: list[BranchSignal] = field(default_factory=list)
    seen: set[str] = field(default_factory=set)
    receptor: DependencyReceptor = field(init=False)
    constraints: ConstraintReceptor = field(init=False)   # own, not shared
    blocked_attachments: int = 0
    premature_attempts: int = 0

    def __post_init__(self):
        self.receptor = DependencyReceptor(self.interface.requires,
                                           self.interface.quorum)
        self.constraints = ConstraintReceptor()

    # -- local redundancy: NEIGHBOURS ONLY, never the tissue ---------------
    def local_redundancy(self, neighbour_roles: dict[str, Optional[str]]) -> int:
        mine = self.interface.provides
        return sum(1 for r in neighbour_roles.values() if r == mine)

    def step(self, neighbour_roles: dict[str, Optional[str]],
             neighbour_provides: dict[str, str]) -> None:
        if self.dissolved:
            self.inbox.clear()
            self.pending.clear()
            return

        # Bind any locally observed upstream that fills one of my requirements.
        # Evidence, not instruction: I look at my own neighbours and see which
        # of them have become what I need. Nobody tells me to attach.
        #
        # Sorted, because `bind` is first-wins and `neighbours` is a set: over
        # unsorted iteration the chosen upstream varies with PYTHONHASHSEED and
        # the whole experiment stops being reproducible.
        for nid, prov in sorted(neighbour_provides.items()):
            if prov in self.interface.requires and neighbour_roles.get(nid):
                self.receptor.bind(prov, nid)

        for sender, sig in self.inbox:
            if sig.branch_id in self.seen or sig.ttl <= 0:
                continue                              # correct dedupe
            self.seen.add(sig.branch_id)

            if (sig.role == self.interface.provides
                    and sig.sign is Tri.ACTIVATE):
                if self.differentiated_role is None:
                    self.pending.append(sig)
                else:
                    # Already this role. A differentiated cell is not inert: it
                    # keeps inducing its downstream roles, which is what lets a
                    # SURVIVING region drive regeneration of a lost one. Without
                    # this the demand dies at the first intact cell it reaches.
                    self._emit_downstream(sig)

            if sig.ttl > 1:
                r = sig.relay()
                for n in sorted(self.neighbours):
                    if n != sender:                   # no echo to the sender
                        self.outbox.append((n, r))
        self.inbox.clear()

        # Retry every retained demand. A demand is only discarded when it is
        # satisfied, refused on causal grounds, or its TTL is spent.
        if self.differentiated_role is None:
            still: list[BranchSignal] = []
            for sig in self.pending:
                if self._try_differentiate(sig, neighbour_roles):
                    still = []                        # differentiated; done
                    break
                if sig.ttl > 1 and self.differentiated_role is None:
                    still.append(sig)
            self.pending = still
        else:
            self.pending.clear()

    def _try_differentiate(self, sig: BranchSignal,
                           neighbour_roles: dict[str, Optional[str]]) -> bool:
        """Attempt one commit. Returns True only if the cell differentiated."""
        # B: the join must be satisfied. Refusing here is what PREVENTS a
        # premature differentiation, rather than detecting one afterwards.
        if not self.receptor.satisfied():
            self.premature_attempts += 1
            return False
        if self.resource < 0.15:
            return False

        # C: constraint evaluated INSIDE the transition. A refusal here
        # prevents the commit; it does not merely get logged.
        redundancy = self.local_redundancy(neighbour_roles)
        proposal = LocalProposal(
            own_role=self.interface.provides,
            proposed_upstream_count=max(1, len(self.receptor.bindings)),
            proposed_sibling_redundancy=redundancy,
            proposed_verification_class=("single_read" if redundancy == 0
                                         else "redundant_read"),
            proposed_resource_coupling=self.resource >= 1.0)
        ok, _ = self.constraints.permits(proposal)
        if not ok:
            self.blocked_attachments += 1
            return False                              # ATTACHMENT NOT COMMITTED

        self.differentiated_role = self.interface.provides
        self.resource -= 0.15
        self._emit_downstream(sig)
        return True

    def _emit_downstream(self, sig: BranchSignal) -> None:
        """A: each downstream branch gets its OWN lineage element, so two
        branches emitted in one tick can never share an identity."""
        for idx, nxt in enumerate(self.interface.emits):
            want = sig.child(nxt, idx)
            for n in sorted(self.neighbours):
                self.outbox.append((n, want))


class Tissue2:
    """Postman and substrate. Holds no goal, no plan, no target."""

    def __init__(self, cells: list[Cell2]):
        self.cells = {c.cell_id: c for c in cells}
        self.partitioned: set[tuple[str, str]] = set()
        # Every edge a message actually crossed. A partition that is merely
        # declared proves nothing; this is what lets a test assert that the
        # blocked edge carried zero traffic.
        self.delivered_edges: list[tuple[str, str]] = []
        self.messages = 0
        self.ticks = 0

    def connect(self, a: str, b: str) -> None:
        self.cells[a].neighbours.add(b)
        self.cells[b].neighbours.add(a)

    def partition(self, a: str, b: str) -> None:
        self.partitioned.add(tuple(sorted((a, b))))

    def blocked(self, a: str, b: str) -> bool:
        return tuple(sorted((a, b))) in self.partitioned

    # Neighbour views are built in sorted order so that formation does not
    # depend on set iteration order, which varies with PYTHONHASHSEED.
    #
    # A partitioned neighbour is excluded. A cell cannot take evidence from
    # something it cannot reach: a partition that blocks messages but still
    # permits binding is a partition in name only, which is precisely the
    # defect that made PR #59's Gate F meaningless.
    def _visible(self, c: Cell2) -> list[str]:
        return [n for n in sorted(c.neighbours)
                if n in self.cells and not self.cells[n].dissolved
                and not self.blocked(c.cell_id, n)]

    def _nroles(self, c: Cell2) -> dict[str, Optional[str]]:
        return {n: self.cells[n].differentiated_role for n in self._visible(c)}

    def _nprov(self, c: Cell2) -> dict[str, str]:
        return {n: self.cells[n].interface.provides for n in self._visible(c)}

    def inject(self, cell_id: str, sig: BranchSignal) -> None:
        self.cells[cell_id].inbox.append(("field", sig))

    def develop(self, max_ticks: int = 60) -> None:
        for _ in range(max_ticks):
            active = [c for c in self.cells.values()
                      if (c.inbox or c.pending) and not c.dissolved]
            if not active:
                break
            self.ticks += 1
            for c in sorted(active, key=lambda x: x.cell_id):
                c.step(self._nroles(c), self._nprov(c))
            delivered = False
            for c in sorted(active, key=lambda x: x.cell_id):
                for dest, sig in c.outbox:
                    if (dest in self.cells and not self.blocked(c.cell_id, dest)
                            and not self.cells[dest].dissolved):
                        self.cells[dest].inbox.append((c.cell_id, sig))
                        self.delivered_edges.append((c.cell_id, dest))
                        self.messages += 1
                        delivered = True
                c.outbox.clear()
            # Quiescence: nothing new arrived and no retained demand can make
            # further progress, so stop rather than spinning out max_ticks.
            if not delivered and not any(c.inbox for c in self.cells.values()):
                if not self._pending_can_progress():
                    break

    def _pending_can_progress(self) -> bool:
        """Would another tick change anything? Retained demands only progress
        when some neighbour has since become what the waiting cell needs."""
        for c in self.cells.values():
            if c.dissolved or c.differentiated_role or not c.pending:
                continue
            nprov, nroles = self._nprov(c), self._nroles(c)
            for nid, prov in nprov.items():
                if (prov in c.interface.requires and nroles.get(nid)
                        and prov not in c.receptor.bindings):
                    return True
        return False

    # -- readout: AFTER formation, changes nothing -------------------------
    def precipitate(self) -> Optional[dict]:
        # Readout runs AFTER formation. It is a whole-tissue read, but it
        # influences no differentiation decision, so it is not counted as a
        # formation-time global scan.
        formed = [c for c in self.cells.values()
                  if c.differentiated_role and not c.dissolved]
        if not formed:
            return None
        return {"capabilities": sorted(c.capability for c in formed),
                "roles_filled": sorted({c.differentiated_role for c in formed}),
                "bindings": {c.cell_id: dict(c.receptor.bindings) for c in formed},
                "control_topology": ("fan_in" if any(
                    len(c.receptor.bindings) >= 2 for c in formed) else "pipeline"),
                "verification": ("dual_read" if any(
                    len(c.receptor.bindings) >= 2 for c in formed) else "readback"),
                "resource_allocation": "static",
                "memory_distribution": "central",
                "communication": "direct",
                "recovery_behaviour": "reassign"}

    def execute(self, payload: str, roles: tuple[str, ...]) -> Optional[str]:
        """Run an actual input through the formed tissue and return an OUTPUT.

        Counting differentiated roles is not execution, and neither is hashing
        the role NAMES - that yields a value identical before and after damage,
        which is defect F wearing a different costume. The value here is a
        function of the cells that actually carry the work, so:

          every required role filled and every join closed -> a value
          any required role unfilled, or any join broken    -> None

        and a form rebuilt through different cells returns a DIFFERENT value,
        which is what lets restoration be distinguished from mere survival.
        """
        carriers: dict[str, list[str]] = {}
        for c in sorted(self.cells.values(), key=lambda x: x.cell_id):
            if c.dissolved or not c.differentiated_role:
                continue
            if not c.receptor.satisfied():
                return None                    # a broken join carries nothing
            carriers.setdefault(c.differentiated_role, []).append(c.cell_id)
        if not set(roles) <= set(carriers):
            return None
        route = "|".join(f"{r}@{','.join(carriers[r])}" for r in sorted(carriers))
        h = hashlib.sha256((payload + "|" + route).encode()).hexdigest()[:16]
        return f"routed:{h}"

    def damage_capability(self, capability: str) -> list[str]:
        """Dissolve a capability, then let the loss propagate LOCALLY.

        A cell whose join has been broken by an observed death can no longer
        perform its function, so it reverts. The cascade is neighbour-to-
        neighbour: no cell consults the tissue, and no cell is told what to
        become next. This is what makes the later output loss an OBSERVATION.
        """
        killed = [c.cell_id for c in self.cells.values()
                  if c.capability == capability and not c.dissolved]
        for cid in killed:
            self.cells[cid].dissolved = True
            self.cells[cid].differentiated_role = None
            self.cells[cid].receptor.bindings.clear()
            self.cells[cid].pending.clear()

        frontier = list(killed)
        while frontier:
            gone = frontier.pop()
            for nid in sorted(self.cells[gone].neighbours):
                n = self.cells.get(nid)
                if n is None or n.dissolved:
                    continue
                if n.receptor.release(gone) and not n.receptor.satisfied():
                    if n.differentiated_role is not None:
                        n.differentiated_role = None
                        n.seen.clear()      # this role may be demanded again
                        frontier.append(nid)
        return killed

    def starve(self, families: tuple[str, ...], factor: float) -> None:
        for c in self.cells.values():
            if c.cell_id.rsplit(".", 1)[-1] in families:
                c.resource *= factor
