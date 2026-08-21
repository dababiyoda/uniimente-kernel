"""Digital cells: bounded local competency with no view of the whole.

THE HIDDEN ASSUMPTION THIS REJECTS

My own Gate E `CandidateFormer` holds a `CapabilityPool` and enumerates role
assignments across it. That embodies the assumption:

    a candidate topology must be CONSTRUCTED by a component
    that can SEE the capabilities it is composing.

Reject it. Here, **no component ever holds a topology.** The topology is only
ever implicit in which cells have attached to which neighbours. A candidate is
not designed; it is *precipitated*, and then read out by an observer that took
no part in forming it.

THE RECIPROCAL TRANSFORMATION

Two mechanisms, each changing the other's operating meaning:

  DEPENDENCY RESOLUTION (package managers, linkers). Normally a solver holds
  the whole graph and computes a closure. MUTATION: strip the solver. Unify
  interfaces pairwise, between immediate neighbours only. No component holds
  the graph.

  REACTION-DIFFUSION / MORPHOGEN GRADIENTS. Normally continuous fields with no
  discrete admissibility. MUTATION: gate diffusion on *type* compatibility, so
  the gradient only propagates where a structural attachment is actually
  possible.

Neither alone yields the result. Dependency resolution without a solver
normally stalls; diffusion without types normally converges on garbage.
Together: **a viable dependency closure forms without any component holding the
dependency graph.** That is the capability neither mechanism had.

WHY TERNARY IS NOT DECORATION

A cell must distinguish three things about a role, and two states cannot:

    +1  this role is UNFILLED near me and I am recruiting for it
     0  this role is unresolved; I am holding, neither recruiting nor blocking
    -1  this role is FILLED near me; stop recruiting (lateral inhibition)

With binary, "not recruiting" collapses `hold` and `satisfied` together, and
the tissue over-recruits: several cells fill the same role because nobody can
say "done, stop". Lateral inhibition needs a sign distinct from silence. That
is a measurable behaviour, tested in the experiment as redundant attachments.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Iterable, Optional


class Tri(IntEnum):
    """Balanced ternary. 0 means HOLD, never 'unknown'."""
    INHIBIT = -1
    HOLD = 0
    ACTIVATE = 1


@dataclass(frozen=True)
class Signal:
    """A typed local signal. Carries a role and a sign, never a solution."""
    role: str
    sign: Tri
    intensity: float          # deficit magnitude; decays with distance
    ttl: int                  # hops remaining; bounds propagation
    origin: str               # emitting cell, for duplicate suppression
    seq: int

    def decayed(self, factor: float = 0.75) -> "Signal":
        return Signal(self.role, self.sign, self.intensity * factor,
                      self.ttl - 1, self.origin, self.seq)


@dataclass
class Interface:
    """What a cell offers and requires. Unification is PAIRWISE and local."""
    provides: str                       # role this cell can fill
    accepts: tuple[str, ...]            # upstream roles it can attach to
    emits: tuple[str, ...]              # downstream roles it can feed

    def unifies_with(self, other: "Interface") -> bool:
        """Can `self` attach downstream of `other`? Local check only."""
        return other.provides in self.accepts


class CellView:
    """EVERYTHING a cell may see. Deliberately a separate object.

    If a cell could reach the pool, the contract, or the tissue, the local
    -knowledge claim would be false. Making the view an explicit object means
    a test can assert on its attribute surface rather than trusting a comment.
    """

    __slots__ = ("own_capability", "own_interface", "neighbours", "inbox",
                 "resource", "stress", "local_attachments")

    def __init__(self, *, own_capability: str, own_interface: Interface,
                 neighbours: tuple[str, ...], inbox: tuple[Signal, ...],
                 resource: float, stress: float,
                 local_attachments: tuple[str, ...]):
        self.own_capability = own_capability
        self.own_interface = own_interface
        self.neighbours = neighbours
        self.inbox = inbox
        self.resource = resource
        self.stress = stress
        self.local_attachments = local_attachments


@dataclass
class Cell:
    """One digital cell. Knows itself and its immediate neighbourhood.

    It does not hold: the capability pool, the function contract, the target
    topology, the tissue, or any other cell's state.
    """
    cell_id: str
    capability: str
    interface: Interface
    neighbours: set[str] = field(default_factory=set)
    resource: float = 1.0
    stress: float = 0.0
    attached_to: Optional[str] = None       # upstream cell it bonded with
    differentiated_role: Optional[str] = None
    dissolved: bool = False
    inbox: list[Signal] = field(default_factory=list)
    outbox: list[tuple[str, Signal]] = field(default_factory=list)
    seen: set[tuple[str, int]] = field(default_factory=set)
    _role_field: dict[str, Tri] = field(default_factory=dict)

    # -- the only view the cell ever gets --------------------------------
    def view(self) -> CellView:
        return CellView(
            own_capability=self.capability, own_interface=self.interface,
            neighbours=tuple(sorted(self.neighbours)),
            inbox=tuple(self.inbox), resource=self.resource,
            stress=self.stress,
            local_attachments=(self.attached_to,) if self.attached_to else ())

    # -- one local step ---------------------------------------------------
    def step(self, neighbour_interfaces: dict[str, Interface],
             neighbour_roles: dict[str, Optional[str]]) -> None:
        """Consume the inbox, maybe differentiate, maybe attach, re-emit.

        `neighbour_interfaces` and `neighbour_roles` are restricted to this
        cell's OWN neighbours by the tissue. That restriction is enforced in
        `tissue.py`, and asserted by test.
        """
        if self.dissolved:
            self.inbox.clear()
            return

        for sig in self.inbox:
            key = (sig.origin, sig.seq)
            if key in self.seen or sig.ttl <= 0:
                continue                       # duplicate suppression
            self.seen.add(key)

            prev = self._role_field.get(sig.role, Tri.HOLD)
            # INHIBIT dominates ACTIVATE: once a role is filled nearby, a
            # later activation must not re-open it. Without dominance the
            # field oscillates and the tissue over-recruits.
            if sig.sign is Tri.INHIBIT or prev is Tri.INHIBIT:
                self._role_field[sig.role] = Tri.INHIBIT
            else:
                self._role_field[sig.role] = sig.sign

            self.stress = max(self.stress, sig.intensity if sig.sign is Tri.ACTIVATE else 0.0)

            # Differentiate: I can fill this role, it is being recruited for,
            # nothing nearby has filled it, and I can pay for it.
            if (self.differentiated_role is None
                    and sig.sign is Tri.ACTIVATE
                    and self._role_field.get(sig.role) is Tri.ACTIVATE
                    and self.interface.provides == sig.role
                    and self.resource >= 0.2):
                self._differentiate(sig, neighbour_interfaces, neighbour_roles)

            # Propagate what I heard, weakened, to my neighbours only.
            if sig.ttl > 1:
                d = sig.decayed()
                for n in sorted(self.neighbours):
                    if n != sig.origin:
                        self.outbox.append((n, d))

        self.inbox.clear()

    def _differentiate(self, sig: Signal,
                       neighbour_interfaces: dict[str, Interface],
                       neighbour_roles: dict[str, Optional[str]]) -> None:
        """Take the role, attach to a compatible neighbour, inhibit laterally."""
        # PAIRWISE unification. No graph, no solver, no closure computation.
        upstream = None
        for nid in sorted(self.neighbours):
            iface = neighbour_interfaces.get(nid)
            if iface is None:
                continue
            if self.interface.unifies_with(iface) and neighbour_roles.get(nid):
                upstream = nid
                break
        # A root role needs no upstream; a dependent role must find one.
        if self.interface.accepts and upstream is None:
            return                                   # cannot bond yet; hold

        self.differentiated_role = sig.role
        self.attached_to = upstream
        self.resource -= 0.2
        self._role_field[sig.role] = Tri.INHIBIT

        # LATERAL INHIBITION. This is the ternary payload: a distinct sign
        # meaning "filled, stop", which silence cannot express.
        stop = Signal(role=sig.role, sign=Tri.INHIBIT, intensity=sig.intensity,
                      ttl=2, origin=self.cell_id, seq=sig.seq)
        for n in sorted(self.neighbours):
            self.outbox.append((n, stop))

        # Recruit for what I now need downstream. I do not know who will answer.
        for nxt in self.interface.emits:
            want = Signal(role=nxt, sign=Tri.ACTIVATE,
                          intensity=sig.intensity * 0.9, ttl=sig.ttl - 1,
                          origin=self.cell_id, seq=sig.seq + 1)
            for n in sorted(self.neighbours):
                self.outbox.append((n, want))

    def dissolve(self, reason: str = "") -> None:
        """Programmed dissolution. Releases resource, keeps lineage upstream."""
        self.dissolved = True
        self.differentiated_role = None
        self.attached_to = None
        self.inbox.clear()
        self.outbox.clear()


def signature(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]
