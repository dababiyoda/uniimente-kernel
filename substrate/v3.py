"""Bidirectional developmental demand with executable function semantics.

NEW MODULE. `substrate/cell.py`, `substrate/tissue.py` and `substrate/v2.py`
are untouched, so PR #60 and PR #62 stand exactly as reported.

WHAT PHASE 3D COULD NOT DO
--------------------------

v2 recruitment was forward-only: an upstream cell differentiated and emitted
demand for its downstream roles. A cell that discovered its OWN prerequisite
missing could do nothing about it, so `diamond_reconverge` never formed. v2 also
never executed anything - `execute()` hashed carrier identities - so "restoring
the function" meant restoring a set of role names.

THE MECHANISM: RECURSIVE CONDITIONAL SETTLEMENT
-----------------------------------------------

Recombined from four primitives, each mutated (see
docs/invention/PHASE3E_MECHANISMS.md for the full cards and the 19 candidates):

  AODV on-demand route discovery   need broadcast + reverse-path state + TTL
  chemical reactant scarcity       unmet prerequisite as a local gradient
  two-phase commit                 offers that are not binding until settled
  market settlement                accumulated cost, scarcity, failed settlement

This is NOT "add a backward message", and the difference is load-bearing:

  1. A need is broadcast into an INCOMPLETELY KNOWN neighbourhood. No cell holds
     a provider index, so there is nobody to send a backward message TO.
  2. A cell that can produce the requested type but has unmet prerequisites of
     its own does NOT answer. It emits its own needs and returns a PENDING
     offer, which cannot be bonded. Satisfaction is a nested settlement, not a
     reply, and it can recurse arbitrarily deep.
  3. Offers carry ACCUMULATED cost. Each hop spends from the originator's
     resource offer, so propagation is damped by economics rather than by a
     depth constant, and an expensive deep chain simply cannot afford to answer.
  4. Settlement can FAIL. A pending offer whose sub-needs never settle expires
     and leaves a local failure receipt, which is evidence the next episode can
     use. A backward message has no failure mode of its own.
  5. Loop suppression comes from the need's LINEAGE, not from a stored DAG: a
     cell refuses to serve a need whose lineage already contains it.

INFORMATION BOUNDARY
--------------------

A cell may expose: the capability class it is missing.
A cell may never see: the target graph, the predecessor graph, the capability
pool, a ranked solution, or a construction plan. `GLOBAL_SCAN_COUNTER` records
any whole-tissue read during development and the experiment asserts it is zero.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

GLOBAL_SCAN_COUNTER = {"n": 0}


def note_global_scan() -> None:
    GLOBAL_SCAN_COUNTER["n"] += 1


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]


# ==========================================================================
# Functional semantics: real values, real transformations, real provenance
# ==========================================================================

@dataclass(frozen=True)
class TypedValue:
    """A value that actually flowed through a cell, with its derivation."""
    type: str
    value: Any
    producer: str                      # cell id
    parents: tuple[str, ...] = ()      # parent value digests

    @property
    def digest(self) -> str:
        return _h(f"{self.type}|{self.value!r}|{self.producer}|{'.'.join(self.parents)}")


@dataclass(frozen=True)
class Capability:
    """What a cell can compute. Types and a deterministic transformation.

    `accepts` is a tuple of input types WITH MULTIPLICITY: ("CHK", "CHK") is a
    genuine two-input join that must be filled by two DISTINCT suppliers.
    """
    name: str
    accepts: tuple[str, ...]
    produces: str
    transform: Callable[..., Any]
    cost: float = 1.0
    resource_domain: str = "shared"    # cells in one domain contend for it
    cls: str = ""                      # capability class, family-independent

    def klass(self) -> str:
        return self.cls or self.name


@dataclass(frozen=True)
class FunctionContract:
    """What must be true at the BOUNDARY. Never a topology.

    Says: given an input of `input_type`, produce an `output_type` satisfying
    `invariant`. It does not say which capabilities to use, in what order, or
    in what shape.
    """
    contract_id: str
    input_type: str
    output_type: str
    invariant: Callable[[TypedValue], bool]
    permitted_classes: tuple[str, ...] = ()

    def permits(self, cap: Capability) -> bool:
        return not self.permitted_classes or cap.klass() in self.permitted_classes


# ==========================================================================
# The demand protocol
# ==========================================================================

@dataclass(frozen=True)
class NeedSignal:
    need_id: str
    requested_type: str
    origin: str                        # the receptor that could not close
    lineage: tuple[str, ...]           # cells this need has passed through
    ttl: int
    resource_offer: float
    slot: int = 0                      # which input slot of the origin

    def hop(self, through: str, spend: float) -> "NeedSignal":
        return NeedSignal(self.need_id, self.requested_type, self.origin,
                          self.lineage + (through,), self.ttl - 1,
                          self.resource_offer - spend, self.slot)

    def sub_need(self, requested_type: str, by: str, slot: int,
                 spend: float) -> "NeedSignal":
        """A supplier's own unmet prerequisite. New origin, inherited budget."""
        return NeedSignal(f"{self.need_id}/{by}:{slot}", requested_type, by,
                          self.lineage + (by,), self.ttl - 1,
                          self.resource_offer - spend, slot)


OFFER_PENDING = "pending"
OFFER_FIRM = "firm"
OFFER_FAILED = "failed"


@dataclass
class SupplyOffer:
    need_id: str
    supplier: str
    offered_type: str
    accumulated_cost: float
    state: str = OFFER_PENDING
    unmet: tuple[str, ...] = ()


@dataclass(frozen=True)
class BondReceipt:
    need_id: str
    supplier: str
    consumer: str
    slot: int
    delivered_type: str
    accumulated_cost: float
    constraint_result: str


@dataclass(frozen=True)
class FailureReceipt:
    """What a settlement that did not complete leaves behind, locally."""
    need_id: str
    at_cell: str
    requested_type: str
    reason: str


# ==========================================================================
# Constraints (preserved from Phase 3D, still evaluated inside the commit)
# ==========================================================================

@dataclass(frozen=True)
class MeasuredMotif:
    """A prohibition over MEASURED relations, not over declared labels.

    Phase 3D prohibited strings the runner had inserted. Every field here is
    computed from the execution trace and the bond receipts.
    """
    capability_class: str
    shared_resource_domain_with_supplier: Optional[bool] = None
    supplier_count: Optional[int] = None
    supplier_paths_independent: Optional[bool] = None

    def matches(self, *, capability_class: str, shares_domain: bool,
                supplier_count: int, paths_independent: bool) -> bool:
        if self.capability_class != capability_class:
            return False
        if (self.shared_resource_domain_with_supplier is not None
                and self.shared_resource_domain_with_supplier != shares_domain):
            return False
        if self.supplier_count is not None and self.supplier_count != supplier_count:
            return False
        if (self.supplier_paths_independent is not None
                and self.supplier_paths_independent != paths_independent):
            return False
        return True


class ConstraintChannel:
    """Per-cell. Holds measured motifs; never touches demand."""

    __slots__ = ("motifs", "blocked", "admitted", "enabled")

    def __init__(self, enabled: bool = True):
        self.motifs: list[MeasuredMotif] = []
        self.blocked: list[str] = []
        self.admitted: list[str] = []
        self.enabled = enabled

    def receive(self, motif: MeasuredMotif) -> None:
        self.motifs.append(motif)

    def permits(self, *, capability_class: str, shares_domain: bool,
                supplier_count: int, paths_independent: bool) -> tuple[bool, str]:
        if not self.enabled:
            return True, "constraint channel disabled (control arm)"
        for m in self.motifs:
            if m.matches(capability_class=capability_class, shares_domain=shares_domain,
                         supplier_count=supplier_count,
                         paths_independent=paths_independent):
                why = (f"proposed bond for {capability_class} reproduces a measured "
                       f"prohibited relation (shares_domain={shares_domain}, "
                       f"suppliers={supplier_count}, independent={paths_independent})")
                self.blocked.append(why)
                return False, why
        self.admitted.append(capability_class)
        return True, "no prohibited measured relation"

    def would_match(self, **kw) -> bool:
        """Did a prohibited proposal actually arise? Needed for paired evidence."""
        return any(m.matches(**kw) for m in self.motifs)


# ==========================================================================
# Cells
# ==========================================================================

@dataclass
class Cell3:
    cell_id: str
    capability: Capability
    neighbours: set[str] = field(default_factory=set)
    resource: float = 1.0
    dissolved: bool = False

    inbox: list[tuple[str, Any]] = field(default_factory=list)
    outbox: list[tuple[str, Any]] = field(default_factory=list)

    reverse_path: dict[str, tuple[str, str]] = field(default_factory=dict)
    # need_id -> (sender, requested_type). The type is what stops a cell from
    # re-advertising itself for a need it merely RELAYED and cannot produce.
    seen_needs: set[str] = field(default_factory=set)
    bonds: dict[int, BondReceipt] = field(default_factory=dict)  # slot -> receipt
    offers: dict[str, list[SupplyOffer]] = field(default_factory=dict)  # need -> offers
    my_needs: dict[int, str] = field(default_factory=dict)       # slot -> need_id
    failures: list[FailureReceipt] = field(default_factory=list)
    constraints: ConstraintChannel = field(default_factory=ConstraintChannel)

    consumed: float = 0.0
    prohibited_proposals_seen: int = 0
    blocked_commits: int = 0

    def slots(self) -> tuple[int, ...]:
        return tuple(range(len(self.capability.accepts)))

    def closed(self) -> bool:
        return all(s in self.bonds for s in self.slots())

    def unmet_slots(self) -> tuple[int, ...]:
        return tuple(s for s in self.slots() if s not in self.bonds)

    # -- the one thing a cell may expose about its own incompleteness -------
    def missing_capability_classes(self) -> tuple[str, ...]:
        return tuple(self.capability.accepts[s] for s in self.unmet_slots())

    # ------------------------------------------------------------------
    # One developmental step. Everything here uses only local state.
    # ------------------------------------------------------------------
    def step(self, neighbour_caps: dict[str, Capability]) -> None:
        if self.dissolved:
            self.inbox.clear()
            return
        for sender, msg in self.inbox:
            if isinstance(msg, NeedSignal):
                self._on_need(sender, msg, neighbour_caps)
            elif isinstance(msg, SupplyOffer):
                self._on_offer(msg, neighbour_caps)
        self.inbox.clear()

    def _on_need(self, sender: str, need: NeedSignal,
                 neighbour_caps: dict[str, Capability]) -> None:
        if need.ttl <= 0 or need.resource_offer <= 0:
            return
        # Loop suppression: lineage, not a stored graph.
        if self.cell_id in need.lineage:
            return
        key = f"{need.need_id}|{need.requested_type}"
        if key in self.seen_needs:
            return
        self.seen_needs.add(key)
        self.reverse_path[need.need_id] = (sender, need.requested_type)

        if self.capability.produces == need.requested_type:
            # Economics damp the search: a chain that cannot afford itself
            # simply does not answer.
            if self.capability.cost > need.resource_offer:
                self.failures.append(FailureReceipt(
                    need.need_id, self.cell_id, need.requested_type,
                    "offer below capability cost"))
                return
            if self.closed():
                self._reply(need, OFFER_FIRM, self.capability.cost)
            else:
                # THE RECURSION. I cannot answer yet, so I acquire my own
                # prerequisites first. My offer is not binding until they settle.
                self._reply(need, OFFER_PENDING, self.capability.cost,
                            unmet=self.missing_capability_classes())
                for slot in self.unmet_slots():
                    sub = need.sub_need(self.capability.accepts[slot], self.cell_id,
                                        slot, self.capability.cost)
                    self.my_needs[slot] = sub.need_id
                    self._broadcast(sub, exclude=sender)
            return

        # Not a producer of this type: relay, keeping the reverse path.
        self._broadcast(need.hop(self.cell_id, 0.0), exclude=sender)

    def _broadcast(self, need: NeedSignal, exclude: Optional[str] = None) -> None:
        if need.ttl <= 0 or need.resource_offer <= 0:
            return
        for n in sorted(self.neighbours):
            if n != exclude:
                self.outbox.append((n, need))

    def _reply(self, need: NeedSignal, state: str, cost: float,
               unmet: tuple[str, ...] = ()) -> None:
        entry = self.reverse_path.get(need.need_id)
        offer = SupplyOffer(need.need_id, self.cell_id, self.capability.produces,
                            cost, state, unmet)
        if entry is not None:
            self.outbox.append((entry[0], offer))

    def _on_offer(self, offer: SupplyOffer, neighbour_caps: dict[str, Capability]) -> None:
        # Is this an offer for one of MY needs?
        mine = [s for s, nid in self.my_needs.items() if nid == offer.need_id]
        if not mine:
            # Forward it back along the reverse path towards the true consumer.
            entry = self.reverse_path.get(offer.need_id)
            if entry is not None and entry[0] != self.cell_id:
                self.outbox.append((entry[0], SupplyOffer(
                    offer.need_id, offer.supplier, offer.offered_type,
                    offer.accumulated_cost + self.capability.cost,
                    offer.state, offer.unmet)))
            return
        slot = mine[0]
        self.offers.setdefault(offer.need_id, []).append(offer)
        if offer.state is not OFFER_FIRM and offer.state != OFFER_FIRM:
            return                       # pending offers cannot be bonded
        if slot in self.bonds:
            return
        self._settle(slot, offer, neighbour_caps)

    def _settle(self, slot: int, offer: SupplyOffer,
                neighbour_caps: dict[str, Capability]) -> None:
        """Commit a bond. The constraint is evaluated INSIDE this transition."""
        required = self.capability.accepts[slot]
        if offer.offered_type != required:
            self.failures.append(FailureReceipt(
                offer.need_id, self.cell_id, required,
                f"type mismatch: offered {offer.offered_type}, slot needs {required}"))
            return
        if any(r.supplier == offer.supplier for r in self.bonds.values()):
            # Genuine fan-in: one supplier may not fill two slots of the same
            # join, or the "two independent checks" are one check counted twice.
            self.failures.append(FailureReceipt(
                offer.need_id, self.cell_id, required,
                "supplier already bonded to another slot of this join"))
            return
        supplier_cap = neighbour_caps.get(offer.supplier)
        shares = (supplier_cap is not None
                  and supplier_cap.resource_domain == self.capability.resource_domain)
        already = {r.supplier for r in self.bonds.values()}
        supplier_count = len(already | {offer.supplier})
        independent = len({neighbour_caps[s].resource_domain
                           for s in (already | {offer.supplier})
                           if s in neighbour_caps}) == supplier_count

        probe = dict(capability_class=self.capability.klass(), shares_domain=shares,
                     supplier_count=supplier_count, paths_independent=independent)
        if self.constraints.would_match(**probe):
            self.prohibited_proposals_seen += 1
        ok, why = self.constraints.permits(**probe)
        if not ok:
            self.blocked_commits += 1
            return                        # BOND NOT COMMITTED

        self.bonds[slot] = BondReceipt(offer.need_id, offer.supplier, self.cell_id,
                                       slot, offer.offered_type,
                                       offer.accumulated_cost, why)
        # Newly closed: my own pending offers become firm and travel back.
        if self.closed():
            for nid, (back, wanted) in list(self.reverse_path.items()):
                if nid in self.my_needs.values():
                    continue
                if wanted != self.capability.produces:
                    continue          # I relayed this need; I do not supply it
                self.outbox.append((back, SupplyOffer(
                    nid, self.cell_id, self.capability.produces,
                    self.capability.cost, OFFER_FIRM)))


# ==========================================================================
# Execution evidence
# ==========================================================================

@dataclass
class ExecutionTrace:
    """Everything the diagnostician is allowed to see. Nothing else."""
    values: dict[str, TypedValue] = field(default_factory=dict)
    bonds_used: list[BondReceipt] = field(default_factory=list)
    resource_consumed: dict[str, float] = field(default_factory=dict)
    messages_delivered: list[tuple[str, str]] = field(default_factory=list)
    messages_blocked: list[tuple[str, str]] = field(default_factory=list)
    failure_receipts: list[FailureReceipt] = field(default_factory=list)
    output: Optional[TypedValue] = None
    invariant_held: bool = False
    missing_inputs: dict[str, list[int]] = field(default_factory=dict)

    def carriers(self) -> list[str]:
        return sorted(self.values)


# ==========================================================================
# Tissue
# ==========================================================================

ENV = "@env"
SINK = "@sink"


class Tissue3:
    def __init__(self, cells: list[Cell3], contract: FunctionContract):
        self.contract = contract
        env = Cell3(cell_id=ENV, capability=Capability(
            "env", (), contract.input_type, lambda: None, cost=0.0,
            resource_domain="env", cls="env"))
        sink = Cell3(cell_id=SINK, capability=Capability(
            "sink", (contract.output_type,), "FINAL", lambda v: v, cost=0.0,
            resource_domain="sink", cls="sink"))
        self.cells: dict[str, Cell3] = {c.cell_id: c for c in [env, sink] + cells}
        self.partitioned: set[tuple[str, str]] = set()
        self.messages = 0
        self.ticks = 0
        self.delivered: list[tuple[str, str]] = []
        self.blocked_deliveries: list[tuple[str, str]] = []

    def connect(self, a: str, b: str) -> None:
        self.cells[a].neighbours.add(b)
        self.cells[b].neighbours.add(a)

    def partition(self, a: str, b: str) -> None:
        self.partitioned.add(tuple(sorted((a, b))))

    def blocked(self, a: str, b: str) -> bool:
        return tuple(sorted((a, b))) in self.partitioned

    def _visible_caps(self, c: Cell3) -> dict[str, Capability]:
        """A cell sees only its own reachable neighbours' capabilities."""
        return {n: self.cells[n].capability for n in sorted(c.neighbours)
                if n in self.cells and not self.cells[n].dissolved
                and not self.blocked(c.cell_id, n)}

    # -- development -----------------------------------------------------
    def demand(self, ttl: int = 10, budget: float = 12.0) -> None:
        """The only injection. SINK cannot close, so it asks. Everything that
        follows is cells discovering and recruiting their own prerequisites."""
        sink = self.cells[SINK]
        for slot in sink.unmet_slots():
            nid = f"root:{self.ticks}:{slot}"
            sink.my_needs[slot] = nid
            need = NeedSignal(nid, sink.capability.accepts[slot], SINK,
                              (SINK,), ttl, budget, slot)
            for n in sorted(sink.neighbours):
                sink.outbox.append((n, need))
        self._run()

    def _run(self, max_ticks: int = 60) -> None:
        for _ in range(max_ticks):
            active = [c for c in self.cells.values()
                      if (c.inbox or c.outbox) and not c.dissolved]
            if not active:
                break
            self.ticks += 1
            for c in sorted(active, key=lambda x: x.cell_id):
                if c.inbox:
                    c.step(self._visible_caps(c))
            pending = []
            for c in sorted(self.cells.values(), key=lambda x: x.cell_id):
                for dest, msg in c.outbox:
                    if dest not in self.cells or self.cells[dest].dissolved:
                        continue
                    if self.blocked(c.cell_id, dest):
                        self.blocked_deliveries.append((c.cell_id, dest))
                        continue
                    pending.append((c.cell_id, dest, msg))
                c.outbox.clear()
            for src, dest, msg in pending:
                self.cells[dest].inbox.append((src, msg))
                self.delivered.append((src, dest))
                self.messages += 1

    # -- real execution ---------------------------------------------------
    def execute(self, payload: Any, budget_per_cell: float = 3.0) -> ExecutionTrace:
        """Run an ACTUAL value through the bonded structure.

        Each cell applies its own deterministic transformation to real inputs
        and emits a real output with provenance. There is no hashing of names:
        a cell that computes the wrong value produces a wrong result, and the
        contract invariant catches it.
        """
        tr = ExecutionTrace()
        env = self.cells[ENV]
        tr.values[ENV] = TypedValue(self.contract.input_type, payload, ENV)
        for _ in range(len(self.cells) + 2):
            progressed = False
            for cid, c in sorted(self.cells.items()):
                if cid in tr.values or c.dissolved or cid == ENV:
                    continue
                if not c.closed():
                    tr.missing_inputs[cid] = list(c.unmet_slots())
                    continue
                args, ready = [], True
                for slot in c.slots():
                    b = c.bonds[slot]
                    sup = tr.values.get(b.supplier)
                    if sup is None:
                        ready = False
                        break
                    args.append(sup)
                if not ready:
                    continue
                cost = c.capability.cost
                if tr.resource_consumed.get(cid, 0.0) + cost > budget_per_cell:
                    tr.failure_receipts.append(FailureReceipt(
                        "", cid, c.capability.produces, "resource budget exhausted"))
                    continue
                tr.resource_consumed[cid] = tr.resource_consumed.get(cid, 0.0) + cost
                c.consumed = tr.resource_consumed[cid]
                out = c.capability.transform(*[a.value for a in args])
                tr.values[cid] = TypedValue(c.capability.produces, out, cid,
                                            tuple(a.digest for a in args))
                tr.bonds_used.extend(c.bonds.values())
                progressed = True
            if not progressed:
                break
        tr.messages_delivered = list(self.delivered)
        tr.messages_blocked = list(self.blocked_deliveries)
        for c in self.cells.values():
            tr.failure_receipts.extend(c.failures)
        sink = self.cells[SINK]
        if 0 in sink.bonds:
            producer = sink.bonds[0].supplier
            val = tr.values.get(producer)
            if val is not None:
                tr.output = val
                tr.invariant_held = bool(self.contract.invariant(val))
        return tr

    def damage_supplier(self, cell_id: str) -> None:
        c = self.cells.get(cell_id)
        if c is None or c.dissolved:
            return
        c.dissolved = True
        for other in self.cells.values():
            for slot, b in list(other.bonds.items()):
                if b.supplier == cell_id:
                    del other.bonds[slot]
                    other.seen_needs.clear()
                    other.failures.append(FailureReceipt(
                        b.need_id, other.cell_id, b.delivered_type,
                        "bonded supplier no longer delivering"))

    def starve(self, cell_id: str, factor: float) -> None:
        if cell_id in self.cells:
            self.cells[cell_id].resource *= factor


# ==========================================================================
# Measured causal phenotype. Every field is computed from evidence.
# ==========================================================================

def _ancestors(trace: ExecutionTrace, tissue: Tissue3, cid: str) -> set[str]:
    seen, stack = set(), [cid]
    while stack:
        cur = stack.pop()
        c = tissue.cells.get(cur)
        if c is None:
            continue
        for b in c.bonds.values():
            if b.supplier not in seen:
                seen.add(b.supplier)
                stack.append(b.supplier)
    return seen


def _reaches(tissue: Tissue3, removed: set[str]) -> bool:
    """Is SINK still derivable from ENV with `removed` gone? Post-hoc readout."""
    have, changed = {ENV} - removed, True
    while changed:
        changed = False
        for cid, c in tissue.cells.items():
            if cid in have or cid in removed or c.dissolved:
                continue
            if c.closed() and all(b.supplier in have for b in c.bonds.values()):
                have.add(cid)
                changed = True
    return SINK in have


def measure_phenotype(tissue: Tissue3, trace: ExecutionTrace) -> dict:
    """Derived from execution evidence. NOTHING here is a declared constant.

    This is the constitutional readout: it inspects the completed form AFTER
    development and influences no developmental decision.
    """
    note_global_scan()          # readout is a whole-form read, and is counted
    participating = [c for c in tissue.cells.values()
                     if not c.dissolved and c.cell_id in trace.values]
    edges = sorted({(b.supplier, b.consumer)
                    for c in participating for b in c.bonds.values()})

    domains: dict[str, list[str]] = {}
    for c in participating:
        domains.setdefault(c.capability.resource_domain, []).append(c.cell_id)
    shared = sorted(d for d, m in domains.items() if len(m) > 1)

    joins = [c for c in participating if len(c.capability.accepts) > 1]
    independence = []
    for j in joins:
        anc = [_ancestors(trace, tissue, b.supplier) | {b.supplier}
               for b in j.bonds.values()]
        disjoint = all(not (a & b) for a, b in itertools.combinations(anc, 2))
        independence.append({"cell": j.cell_id, "class": j.capability.klass(),
                             "suppliers_independent": disjoint})

    spof = sorted(cid for cid in trace.values
                  if cid not in (ENV, SINK) and not _reaches(tissue, {cid}))

    # Vertex-disjoint ENV->SINK paths, by greedy removal.
    paths, removed = 0, set()
    while _reaches(tissue, removed):
        blockers = [cid for cid in sorted(trace.values)
                    if cid not in (ENV, SINK) and cid not in removed
                    and not _reaches(tissue, removed | {cid})]
        if not blockers:
            paths += 1
            break
        removed.add(blockers[0])
        paths += 1
        if paths > 8:
            break

    return {
        "actual_dependency_edges": edges,
        "independent_input_paths": paths,
        "shared_resource_domains": shared,
        "per_cell_resource_consumption": dict(sorted(trace.resource_consumed.items())),
        "verifier_independence": independence,
        "message_path_diversity": len({d for _, d in trace.messages_delivered}),
        "state_replication": len([c for c in participating
                                  if c.capability.produces in
                                  {x.capability.produces for x in participating
                                   if x.cell_id != c.cell_id}]),
        "quorum_structure": sorted({len(c.capability.accepts) for c in participating}),
        "partition_crossings_attempted": len(trace.messages_blocked)
                                         + len(trace.messages_delivered),
        "partition_crossings_succeeded": len(trace.messages_delivered),
        "recovery_route": edges,
        "single_points_of_failure": spof,
    }


# ==========================================================================
# Topology-normalized causal form identity
# ==========================================================================

def normalized_form(tissue: Tissue3, trace: ExecutionTrace) -> str:
    """Quotient out cell ids, family labels and ordering.

    Two forms are the same iff their dependency geometry over capability
    CLASSES is isomorphic. Merkle-labelled from the sources upward, so cell
    names, family names, reserve carriers and ordering cannot make two
    causally identical forms look different.
    """
    memo: dict[str, str] = {}

    def label(cid: str) -> str:
        if cid in memo:
            return memo[cid]
        c = tissue.cells[cid]
        kids = sorted(label(b.supplier) for b in c.bonds.values())
        memo[cid] = _h(f"{c.capability.klass()}({','.join(kids)})")
        return memo[cid]

    if SINK not in trace.values and 0 not in tissue.cells[SINK].bonds:
        return "unformed"
    root = tissue.cells[SINK].bonds[0].supplier
    return label(root)


def causal_form_key(tissue: Tissue3, trace: ExecutionTrace,
                    phenotype: dict) -> str:
    """Normalized geometry PLUS the measured relations that matter causally."""
    salient = {
        "geometry": normalized_form(tissue, trace),
        "independent_input_paths": phenotype["independent_input_paths"],
        "shared_resource_domains": len(phenotype["shared_resource_domains"]),
        "verifier_independence": sorted(
            (d["class"], d["suppliers_independent"])
            for d in phenotype["verifier_independence"]),
        "quorum_structure": phenotype["quorum_structure"],
        "single_points_of_failure": len(phenotype["single_points_of_failure"]),
    }
    return _h(json.dumps(salient, sort_keys=True))


# ==========================================================================
# Blind failure diagnosis
# ==========================================================================

SUPPLIER_LOSS = "supplier_loss"
PARTITION_ISOLATION = "partition_isolation"
RESOURCE_EXHAUSTION = "resource_exhaustion"
SEMANTIC_CORRUPTION = "semantic_corruption"
CAUSAL_CLASSES = (SUPPLIER_LOSS, PARTITION_ISOLATION, RESOURCE_EXHAUSTION,
                  SEMANTIC_CORRUPTION)


@dataclass(frozen=True)
class Diagnosis:
    causal_class: str
    affected_capability_class: str
    evidence: tuple[str, ...]


def diagnose(healthy: ExecutionTrace, broken: ExecutionTrace,
             observed_classes: dict[str, str]) -> Optional[Diagnosis]:
    """Infer WHY the function stopped, from evidence alone.

    Receives: two execution traces, bond and failure receipts, resource records
    and message-delivery evidence. `observed_classes` maps cell id -> capability
    class and is derivable from the traces themselves.

    Receives NOT: the fixture's cause label, the harness-selected damaged cell,
    the expected causal class, the intended replacement, or any topology.
    """
    if broken.output is not None and broken.invariant_held:
        return None

    ev: list[str] = []

    # Values that existed before and do not now. Which one is EARLIEST in the
    # dependency order is the one to explain; later ones are consequences.
    lost = [c for c in healthy.values if c not in broken.values]
    lost_roots = [c for c in lost
                  if not (set(healthy.values[c].parents)
                          & {healthy.values[o].digest for o in lost if o != c})]
    focus = sorted(lost_roots)[0] if lost_roots else (sorted(lost)[0] if lost else None)

    # 1. Output present and well-typed but the invariant fails -> the fault is
    #    in a VALUE, not in the structure.
    if broken.output is not None and not broken.invariant_held and not lost:
        ev.append("output produced, contract invariant violated, no value missing")
        suspects = [c for c in broken.values
                    if c in healthy.values
                    and broken.values[c].value != healthy.values[c].value]
        target = sorted(suspects)[0] if suspects else (broken.output.producer)
        return Diagnosis(SEMANTIC_CORRUPTION, observed_classes.get(target, "?"),
                         tuple(ev + [f"value changed at {len(suspects)} cell(s)"]))

    if focus is None:
        return Diagnosis(SUPPLIER_LOSS, "?", ("output absent, no value diff",))

    # 2. Resource evidence: the cell was reached but could not afford to run.
    exhausted = {f.at_cell for f in broken.failure_receipts
                 if "budget" in f.reason or "cost" in f.reason}
    if focus in exhausted:
        ev.append(f"failure receipt at {focus} cites resource exhaustion")
        return Diagnosis(RESOURCE_EXHAUSTION, observed_classes.get(focus, "?"),
                         tuple(ev))

    # 3. Partition evidence: edges that carried traffic before are now blocked,
    #    and the lost cell sits on one of them.
    blocked_pairs = {tuple(sorted(p)) for p in broken.messages_blocked}
    touching = [p for p in blocked_pairs if focus in p]
    if touching:
        ev.append(f"{len(blocked_pairs)} edge(s) refused delivery; "
                  f"{len(touching)} touch the earliest lost value")
        return Diagnosis(PARTITION_ISOLATION, observed_classes.get(focus, "?"),
                         tuple(ev))

    # 4. Otherwise the producer simply stopped existing.
    ev.append(f"value from {focus} absent with no delivery refusal and no "
              f"resource receipt")
    return Diagnosis(SUPPLIER_LOSS, observed_classes.get(focus, "?"), tuple(ev))


def motif_from(diag: Diagnosis, phenotype: dict) -> MeasuredMotif:
    """Reduce a blind diagnosis to a minimal NEGATIVE constraint over MEASURED
    relations. Carries no target, no ranking, no topology."""
    if diag.causal_class == RESOURCE_EXHAUSTION:
        return MeasuredMotif(diag.affected_capability_class,
                             shared_resource_domain_with_supplier=True)
    if diag.causal_class == PARTITION_ISOLATION:
        return MeasuredMotif(diag.affected_capability_class, supplier_count=1)
    if diag.causal_class == SEMANTIC_CORRUPTION:
        return MeasuredMotif(diag.affected_capability_class,
                             supplier_paths_independent=False)
    return MeasuredMotif(diag.affected_capability_class, supplier_count=1)


# ==========================================================================
# Damage classes. The INJECTOR may read the completed execution trace; the
# developmental cells may not. That asymmetry is the pre-registered policy.
# ==========================================================================

def damage_by_cost(tissue: Tissue3, cell_id: str, multiplier: float) -> None:
    """Make a cell too expensive to run. Produces resource exhaustion at
    execution time, observable only as a failure receipt."""
    import dataclasses
    c = tissue.cells.get(cell_id)
    if c is not None:
        c.capability = dataclasses.replace(
            c.capability, cost=c.capability.cost * multiplier)


def damage_by_corruption(tissue: Tissue3, cell_id: str) -> None:
    """Leave the structure intact and the types valid, but compute a wrong
    value. Only a real execution can detect this."""
    import dataclasses
    c = tissue.cells.get(cell_id)
    if c is not None:
        old = c.capability.transform
        c.capability = dataclasses.replace(
            c.capability, transform=lambda *a, _o=old: f"corrupt:{_o(*a)}")


def partition_around(tissue: Tissue3, cell_id: str) -> int:
    """Isolate a cell from the consumers that bonded it."""
    n = 0
    for other in tissue.cells.values():
        if any(b.supplier == cell_id for b in other.bonds.values()):
            tissue.partition(cell_id, other.cell_id)
            n += 1
    for other in tissue.cells.values():
        if other.cell_id != cell_id and cell_id in other.neighbours and n < 3:
            tissue.partition(cell_id, other.cell_id)
            n += 1
    # Bonds through a now-unreachable supplier no longer deliver.
    for other in tissue.cells.values():
        for slot, b in list(other.bonds.items()):
            if b.supplier == cell_id:
                del other.bonds[slot]
                other.seen_needs.clear()
    return n
