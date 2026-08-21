"""Autonomous interior re-initiation by provenance-fenced local reopening.

NEW MODULE. `substrate/cell.py`, `tissue.py`, `v2.py` and `v3.py` are untouched,
so PR #58/#59/#60/#62/#63 stand exactly as reported.

THE BOTTLENECK THIS ADDRESSES
-----------------------------

Phase 3E assembles a chain when the BOUNDARY asks for an output. It cannot
restart after an interior supplier becomes invalid: the boundary still holds a
formally intact bond, reports no missing slot, and `demand()` emits zero
messages. Measured in PR #63: 0/20 held-out regenerations.

WHY THIS IS NOT THE SEED MODEL
------------------------------

The seed proposed supplier AGREEMENTS with GENERATIONS: state on the
consumer-supplier edge, plus a counter to order repair rounds. That model is
implemented here only as a BASELINE (`GenerationFencingConsumer`), because it
has a specific blind spot:

    a generation counter fences the supplier you already suspect,
    and nothing else.

It cannot refuse a DIFFERENT supplier that silently depends on the same broken
upstream, because that supplier's generation is fresh. In an institution this
is the common case: two departments quietly share one broken source.

So validity is modelled on the VALUE, not on the relationship:

  * A cell remembers the DERIVATION CHAIN of the last input it accepted.
  * When its own execution cannot obtain a usable value, it adds that chain to a
    local REFUSAL SET.
  * Any later offer whose derivation intersects the refusal set is refused.

This subsumes stale-delivery fencing (the old supplier's chain is refused) and
additionally catches the shared-hidden-ancestor case. There is no generation
counter and no agreement object anywhere in the mechanism.

FOUR RECOMBINED PRIMITIVES, EACH MUTATED
----------------------------------------

  incremental build invalidation  a consumer discovers staleness by doing its
                                  OWN work. Mutation: pulled from evidence the
                                  consumer already has, never pushed by a
                                  coordinator that owns the graph. No polling,
                                  no timers, no clock anywhere in this module.

  Merkle / Git ancestry           identity by content and derivation.
                                  Mutation: used as a REFUSAL predicate rather
                                  than a lookup key, so it fences futures rather
                                  than deduplicating pasts.

  taint tracking                  a cell whose input is invalid marks its own
                                  output invalid instead of emitting a wrong
                                  value. Mutation: the taint is what makes the
                                  NEXT consumer reopen, so invalidation
                                  propagates by ordinary execution rather than
                                  by a notification channel.

  token bucket                    bounded repair. Mutation: the budget is
                                  DIVIDED among sub-needs rather than shared, so
                                  repair amplification is bounded structurally
                                  instead of by a rate limiter someone owns.

LOCALITY
--------

A work unit knows: its own required inputs, the derivation of what it last
accepted, its own execution evidence, its own refusal set, its direct
neighbours' offers, its remaining repair budget, its own failure history.

It never knows: the capability pool, the mission graph, which cell broke, the
correct replacement, or a ranked supplier list. The counters below are asserted
zero by the experiment.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# Locality counters. Every one must remain zero for a qualifying repair.
COUNTERS = {
    "GLOBAL_FORMATION_SCANS": 0,
    "GLOBAL_REPAIR_SCANS": 0,
    "SUPERVISOR_RESTART_EVENTS": 0,
    "BOUNDARY_RESTART_EVENTS": 0,
    "FULL_PROVIDER_INDEX_READS": 0,
    "TARGET_TOPOLOGY_LEAKAGE_EVENTS": 0,
}


def reset_counters() -> None:
    for k in COUNTERS:
        COUNTERS[k] = 0


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]


ENV = "@env"
SINK = "@sink"


# ==========================================================================
# Values carry their own derivation. That derivation is the unit of trust.
# ==========================================================================

@dataclass(frozen=True)
class Value:
    type: str
    payload: Any
    producer: str
    chain: frozenset[str] = frozenset()   # every producer that contributed
    tainted: bool = False                 # produced from a known-bad input

    @property
    def digest(self) -> str:
        return _h(f"{self.type}|{self.payload!r}|{self.producer}|"
                  f"{'.'.join(sorted(self.chain))}")

    def derive(self, type_: str, payload: Any, producer: str,
               parents: tuple["Value", ...]) -> "Value":
        chain = frozenset({producer}) | frozenset(
            itertools.chain.from_iterable(p.chain for p in parents))
        return Value(type_, payload, producer, chain,
                     tainted=any(p.tainted for p in parents))


@dataclass(frozen=True)
class Capability:
    name: str
    accepts: tuple[str, ...]
    produces: str
    transform: Callable[..., Any]
    cost: float = 1.0
    resource_domain: str = "shared"
    cls: str = ""

    def klass(self) -> str:
        return self.cls or self.name


@dataclass(frozen=True)
class Contract:
    contract_id: str
    input_type: str
    output_type: str
    invariant: Callable[[Value], bool]


# ==========================================================================
# Evidence
# ==========================================================================

SUPPLIER_GONE = "supplier_gone"
NOT_DELIVERING = "supplier_present_not_delivering"
ISOLATED = "separated_communication_path"
TOO_EXPENSIVE = "excessive_resource_cost"
SEMANTICALLY_WRONG = "wrong_semantic_output"
STALE_RETURN = "stale_supplier_return"
INTERMITTENT = "intermittent_delivery"
NO_REPLACEMENT = "no_valid_replacement"

FAILURE_CLASSES = (SUPPLIER_GONE, NOT_DELIVERING, ISOLATED, TOO_EXPENSIVE,
                   SEMANTICALLY_WRONG, STALE_RETURN, INTERMITTENT, NO_REPLACEMENT)


@dataclass(frozen=True)
class Receipt:
    """Local, durable evidence. The diagnostician sees only these and traces."""
    kind: str
    at: str
    slot: Optional[int]
    detail: str
    supplier: Optional[str] = None
    supplier_class: Optional[str] = None


@dataclass(frozen=True)
class Escalation:
    at: str
    slot: int
    required_type: str
    reason: str
    attempts: int


# ==========================================================================
# Demand
# ==========================================================================

@dataclass(frozen=True)
class Need:
    need_id: str
    wanted: str
    origin: str
    slot: int
    lineage: tuple[str, ...]
    budget: float
    refused: frozenset[str]        # derivation elements this consumer will not accept

    def relay(self, through: str) -> "Need":
        return Need(self.need_id, self.wanted, self.origin, self.slot,
                    self.lineage + (through,), self.budget, self.refused)

    def sub(self, wanted: str, by: str, slot: int, share: float) -> "Need":
        # The budget is DIVIDED, not inherited whole: this is what bounds
        # repair amplification without anybody scheduling it.
        return Need(f"{self.need_id}/{by}:{slot}", wanted, by, slot,
                    self.lineage + (by,), share, self.refused)


@dataclass
class Offer:
    need_id: str
    supplier: str
    supplier_class: str
    offered_type: str
    cost: float
    firm: bool
    chain: frozenset[str]          # what this offer's output would derive from


@dataclass
class Bond:
    slot: int
    supplier: str
    supplier_class: str
    delivered_type: str
    cost: float
    accepted_chain: frozenset[str] = frozenset()
    deliveries: int = 0


# ==========================================================================
# Failure memory: keyed by PATTERN, decaying, never a permanent blacklist
# ==========================================================================

class FailureMemory:
    """Local, bounded, forgiving.

    Keyed by (supplier_class, failure_class) rather than supplier identity, so
    the lesson generalises past the one cell that happened to fail, and a
    supplier is never permanently barred by identity alone.
    """

    __slots__ = ("counts", "cooldown", "probes")

    def __init__(self) -> None:
        self.counts: dict[tuple[str, str], int] = {}
        self.cooldown: dict[str, int] = {}        # supplier -> rounds remaining
        self.probes: dict[str, int] = {}

    def record(self, supplier: str, supplier_class: str, failure: str) -> None:
        key = (supplier_class, failure)
        self.counts[key] = self.counts.get(key, 0) + 1
        # Circuit breaker on the SUPPLIER, bounded and self-clearing.
        self.cooldown[supplier] = min(3, self.cooldown.get(supplier, 0) + 2)

    def tick(self) -> None:
        for s in list(self.cooldown):
            self.cooldown[s] -= 1
            if self.cooldown[s] <= 0:
                del self.cooldown[s]
                self.probes[s] = 1        # half-open: one probe permitted

    def admits(self, supplier: str) -> bool:
        if supplier not in self.cooldown:
            return True
        if self.probes.get(supplier, 0) > 0:      # half-open probe
            self.probes[supplier] -= 1
            return True
        return False

    def penalty(self, supplier_class: str) -> float:
        return 0.35 * sum(v for (c, _), v in self.counts.items() if c == supplier_class)


# ==========================================================================
# The work unit
# ==========================================================================

@dataclass
class Unit:
    unit_id: str
    capability: Capability
    neighbours: set[str] = field(default_factory=set)

    bonds: dict[int, Bond] = field(default_factory=dict)
    refused: set[str] = field(default_factory=set)     # derivation elements refused
    open_needs: dict[int, str] = field(default_factory=dict)
    reverse: dict[str, tuple[str, str]] = field(default_factory=dict)
    seen: set[str] = field(default_factory=set)
    offers: dict[str, list[Offer]] = field(default_factory=dict)

    inbox: list[tuple[str, Any]] = field(default_factory=list)
    outbox: list[tuple[str, Any]] = field(default_factory=list)

    repair_budget: float = 6.0
    reopens: int = 0
    receipts: list[Receipt] = field(default_factory=list)
    escalations: list[Escalation] = field(default_factory=list)
    memory: FailureMemory = field(default_factory=FailureMemory)
    stale_rejections: int = 0
    dissolved: bool = False
    quiet: bool = False              # present but no longer delivering
    cost_multiplier: float = 1.0

    # constraint channel (Gate G); disabled arm is the paired control
    prohibited: list[Any] = field(default_factory=list)
    constraint_enabled: bool = True
    prohibited_proposals: int = 0
    blocked_commits: int = 0

    def slots(self) -> tuple[int, ...]:
        return tuple(range(len(self.capability.accepts)))

    def unmet(self) -> tuple[int, ...]:
        return tuple(s for s in self.slots() if s not in self.bonds)

    def missing_classes(self) -> tuple[str, ...]:
        return tuple(self.capability.accepts[s] for s in self.unmet())

    # ------------------------------------------------------------------
    # THE MECHANISM: reopening is triggered by this unit's OWN execution
    # evidence. No timer, no poll, no notification, no supervisor.
    # ------------------------------------------------------------------
    def reopen(self, slot: int, failure: str, detail: str,
               chain: frozenset[str] = frozenset()) -> bool:
        """Refuse the current input's derivation and originate bounded demand."""
        if self.repair_budget <= 0:
            self.escalations.append(Escalation(
                self.unit_id, slot, self.capability.accepts[slot],
                "repair budget exhausted", self.reopens))
            self.receipts.append(Receipt("escalation", self.unit_id, slot,
                                         "repair budget exhausted"))
            return False
        old = self.bonds.pop(slot, None)
        if old is not None:
            # THE FENCE, sized to the evidence.
            #
            # A delivery fault (gone, isolated, silent, too costly) is evidence
            # about the DIRECT supplier only, so only that supplier is refused.
            #
            # A semantic fault is evidence that something in the derivation
            # produced a wrong value, and the consumer cannot tell which link.
            # It therefore refuses the whole upstream chain. This is where
            # provenance dominance earns its keep: a different supplier that
            # quietly shares the bad ancestry is refused too, which a
            # generation counter can never do. ENV is excluded because the
            # mission input is given, not chosen.
            if failure == SEMANTICALLY_WRONG:
                self.refused |= (set(old.accepted_chain) - {ENV, self.unit_id})
            else:
                self.refused.add(old.supplier)
            self.memory.record(old.supplier, old.supplier_class, failure)
            self.receipts.append(Receipt(
                "input_refused", self.unit_id, slot, f"{failure}: {detail}",
                old.supplier, old.supplier_class))
        else:
            self.refused |= set(chain)
            self.receipts.append(Receipt("input_refused", self.unit_id, slot,
                                         f"{failure}: {detail}"))
        self.reopens += 1
        self.repair_budget -= 1.0
        self.seen.clear()
        return True

    def restore(self, slot: int) -> None:
        """A false suspicion: the input validated after all. No replacement."""
        self.receipts.append(Receipt("suspicion_withdrawn", self.unit_id, slot,
                                     "input revalidated without replacement"))

    # -- demand protocol -------------------------------------------------
    def emit_needs(self, ttl_budget: float | None = None) -> None:
        for slot in self.unmet():
            if slot in self.open_needs:
                continue                       # coalesced: one need per slot
            nid = f"{self.unit_id}:{slot}:{self.reopens}"
            self.open_needs[slot] = nid
            need = Need(nid, self.capability.accepts[slot], self.unit_id, slot,
                        (self.unit_id,),
                        ttl_budget if ttl_budget is not None else self.repair_budget,
                        frozenset(self.refused))
            for n in sorted(self.neighbours):
                self.outbox.append((n, need))

    def step(self, neighbour_caps: dict[str, Capability]) -> None:
        if self.dissolved:
            self.inbox.clear()
            return
        for sender, msg in self.inbox:
            if isinstance(msg, Need):
                self._on_need(sender, msg)
            elif isinstance(msg, Offer):
                self._on_offer(msg, neighbour_caps)
        self.inbox.clear()

    def _on_need(self, sender: str, need: Need) -> None:
        if need.budget <= 0 or self.unit_id in need.lineage:
            return                              # loop suppression by lineage
        key = f"{need.need_id}|{need.wanted}"
        if key in self.seen:
            return                              # duplicate suppression
        self.seen.add(key)
        self.reverse[need.need_id] = (sender, need.wanted)

        if self.capability.produces == need.wanted and not self.quiet:
            # PROVENANCE FENCE, applied by the SUPPLIER as self-exclusion: if
            # anything I would derive from is refused by the consumer, I must
            # not offer. This is what stops a fresh-looking supplier that
            # quietly shares the broken ancestry.
            my_chain = self._would_derive_from()
            if my_chain & need.refused:
                self.receipts.append(Receipt(
                    "offer_withheld", self.unit_id, None,
                    "own derivation intersects the consumer's refusal set"))
                return
            cost = self.capability.cost * self.cost_multiplier
            if cost > need.budget:
                self.receipts.append(Receipt("offer_withheld", self.unit_id, None,
                                             "cost exceeds the offered budget"))
                return
            firm = not self.unmet()
            self._reply(need, firm, cost, my_chain)
            if not firm:
                share = max(0.0, (need.budget - cost) / max(1, len(self.unmet())))
                for slot in self.unmet():
                    if slot in self.open_needs:
                        continue
                    sub = need.sub(self.capability.accepts[slot], self.unit_id,
                                   slot, share)
                    self.open_needs[slot] = sub.need_id
                    for n in sorted(self.neighbours):
                        if n != sender:
                            self.outbox.append((n, sub))
            return
        for n in sorted(self.neighbours):
            if n != sender:
                self.outbox.append((n, need.relay(self.unit_id)))

    def _would_derive_from(self) -> frozenset[str]:
        return frozenset({self.unit_id}) | frozenset(
            itertools.chain.from_iterable(
                b.accepted_chain for b in self.bonds.values()))

    def _reply(self, need: Need, firm: bool, cost: float,
               chain: frozenset[str]) -> None:
        back = self.reverse.get(need.need_id)
        if back is None:
            return
        self.outbox.append((back[0], Offer(need.need_id, self.unit_id,
                                           self.capability.klass(),
                                           self.capability.produces, cost, firm,
                                           chain)))

    def _on_offer(self, offer: Offer, neighbour_caps: dict[str, Capability]) -> None:
        mine = [s for s, nid in self.open_needs.items() if nid == offer.need_id]
        if not mine:
            back = self.reverse.get(offer.need_id)
            if back is not None and back[0] != self.unit_id:
                self.outbox.append((back[0], Offer(
                    offer.need_id, offer.supplier, offer.supplier_class,
                    offer.offered_type, offer.cost + self.capability.cost,
                    offer.firm, offer.chain | {self.unit_id})))
            return
        slot = mine[0]
        self.offers.setdefault(offer.need_id, []).append(offer)
        if not offer.firm or slot in self.bonds:
            return
        self._settle(slot, offer, neighbour_caps)

    def _settle(self, slot: int, offer: Offer,
                neighbour_caps: dict[str, Capability]) -> None:
        required = self.capability.accepts[slot]
        if offer.offered_type != required:
            return
        if any(b.supplier == offer.supplier for b in self.bonds.values()):
            return                              # distinct suppliers per join
        # THE FENCE, applied by the consumer at settlement.
        if offer.chain & self.refused:
            self.stale_rejections += 1
            self.receipts.append(Receipt(
                "stale_offer_rejected", self.unit_id, slot,
                "offer derivation intersects the refusal set",
                offer.supplier, offer.supplier_class))
            return
        if not self.memory.admits(offer.supplier):
            self.receipts.append(Receipt("supplier_in_cooldown", self.unit_id, slot,
                                         "supplier is cooling down",
                                         offer.supplier, offer.supplier_class))
            return

        sup_cap = neighbour_caps.get(offer.supplier)
        shares = (sup_cap is not None
                  and sup_cap.resource_domain == self.capability.resource_domain)
        already = {b.supplier for b in self.bonds.values()}
        count = len(already | {offer.supplier})
        independent = len({neighbour_caps[s].resource_domain
                           for s in (already | {offer.supplier})
                           if s in neighbour_caps}) == count
        probe = dict(capability_class=self.capability.klass(), shares_domain=shares,
                     supplier_count=count, paths_independent=independent)
        if any(m.matches(**probe) for m in self.prohibited):
            self.prohibited_proposals += 1
            if self.constraint_enabled:
                self.blocked_commits += 1
                self.receipts.append(Receipt("commit_blocked", self.unit_id, slot,
                                             "prohibited measured relation",
                                             offer.supplier, offer.supplier_class))
                return

        self.bonds[slot] = Bond(slot, offer.supplier, offer.supplier_class,
                                offer.offered_type, offer.cost, offer.chain)
        self.open_needs.pop(slot, None)
        self.receipts.append(Receipt("bond_settled", self.unit_id, slot,
                                     "replacement settled", offer.supplier,
                                     offer.supplier_class))
        # Newly closed: the offers I made while still incomplete were PENDING
        # and could not be bonded. Now that my own prerequisites have settled,
        # they become firm. This is the recursive part of the settlement.
        if not self.unmet():
            mine = set(self.open_needs.values())
            chain = self._would_derive_from()
            for nid, (back, wanted) in list(self.reverse.items()):
                if nid in mine or wanted != self.capability.produces:
                    continue
                self.outbox.append((back, Offer(
                    nid, self.unit_id, self.capability.klass(),
                    self.capability.produces,
                    self.capability.cost * self.cost_multiplier, True, chain)))


# ==========================================================================
# The organ
# ==========================================================================

@dataclass
class Trace:
    values: dict[str, Value] = field(default_factory=dict)
    blocked: list[tuple[str, str]] = field(default_factory=list)
    delivered: list[tuple[str, str]] = field(default_factory=list)
    receipts: list[Receipt] = field(default_factory=list)
    consumed: dict[str, float] = field(default_factory=dict)
    output: Optional[Value] = None
    ok: bool = False
    unmet: dict[str, list[int]] = field(default_factory=dict)

    def carriers(self) -> list[str]:
        return sorted(k for k in self.values if k not in (ENV, SINK))


class Organ:
    """Postman and boundary. Holds no plan, no graph, no repair authority."""

    def __init__(self, units: list[Unit], contract: Contract):
        self.contract = contract
        env = Unit(unit_id=ENV, capability=Capability(
            "env", (), contract.input_type, lambda: None, 0.0, "env", "env"))
        sink = Unit(unit_id=SINK, capability=Capability(
            "sink", (contract.output_type,), "FINAL", lambda v: v, 0.0, "sink", "sink"))
        self.units: dict[str, Unit] = {u.unit_id: u for u in [env, sink] + units}
        self.cut: set[tuple[str, str]] = set()
        self.messages = 0
        self.ticks = 0
        self.boundary_demands = 0
        self.repair_rounds = 0
        self.flaky: dict[str, int] = {}          # unit -> deliver every Nth attempt
        self._attempt: dict[str, int] = {}

    def connect(self, a: str, b: str) -> None:
        self.units[a].neighbours.add(b)
        self.units[b].neighbours.add(a)

    def cut_link(self, a: str, b: str) -> None:
        self.cut.add(tuple(sorted((a, b))))

    def is_cut(self, a: str, b: str) -> bool:
        return tuple(sorted((a, b))) in self.cut

    def _caps(self, u: Unit) -> dict[str, Capability]:
        return {n: self.units[n].capability for n in sorted(u.neighbours)
                if n in self.units and not self.units[n].dissolved
                and not self.is_cut(u.unit_id, n)}

    # -- the ONLY boundary event, at mission start ------------------------
    def commission(self, budget: float = 48.0) -> None:
        """The ONLY boundary event, at mission start. Never called again.

        The budget must fund the deepest chain the contract can require: each
        hop spends its own cost and DIVIDES the remainder among its unmet
        slots, so a depth-8 structure with two joins needs real headroom.
        Under-funding it looks exactly like an unsatisfiable contract.
        """
        self.boundary_demands += 1
        self.units[SINK].emit_needs(ttl_budget=budget)
        self._pump()

    def _pump(self, max_ticks: int = 60) -> None:
        for _ in range(max_ticks):
            active = [u for u in self.units.values()
                      if (u.inbox or u.outbox) and not u.dissolved]
            if not active:
                break
            self.ticks += 1
            for u in sorted(active, key=lambda x: x.unit_id):
                if u.inbox:
                    u.step(self._caps(u))
            pending = []
            for u in sorted(self.units.values(), key=lambda x: x.unit_id):
                for dest, msg in u.outbox:
                    if dest not in self.units or self.units[dest].dissolved:
                        continue
                    if self.is_cut(u.unit_id, dest):
                        continue
                    pending.append((u.unit_id, dest, msg))
                u.outbox.clear()
            for src, dest, msg in pending:
                self.units[dest].inbox.append((src, msg))
                self.messages += 1

    # -- real execution ---------------------------------------------------
    def execute(self, payload: Any) -> Trace:
        tr = Trace()
        tr.values[ENV] = Value(self.contract.input_type, payload, ENV,
                               frozenset({ENV}))
        for _ in range(len(self.units) + 3):
            progressed = False
            for uid, u in sorted(self.units.items()):
                if uid in tr.values or u.dissolved or uid == ENV:
                    continue
                if u.unmet():
                    tr.unmet[uid] = list(u.unmet())
                    continue
                args, ready = [], True
                for slot in u.slots():
                    b = u.bonds[slot]
                    if self.is_cut(b.supplier, uid):
                        tr.blocked.append((b.supplier, uid))
                        ready = False
                        break
                    sup = self.units.get(b.supplier)
                    if sup is None or sup.dissolved or sup.quiet:
                        ready = False
                        break
                    v = tr.values.get(b.supplier)
                    if v is None:
                        ready = False
                        break
                    n = self._attempt.get(b.supplier, 0) + 1
                    self._attempt[b.supplier] = n
                    if b.supplier in self.flaky and n % self.flaky[b.supplier] != 0:
                        ready = False
                        break
                    args.append(v)
                if not ready:
                    continue
                cost = u.capability.cost * u.cost_multiplier
                tr.consumed[uid] = tr.consumed.get(uid, 0.0) + cost
                out = u.capability.transform(*[a.payload for a in args])
                base = args[0] if args else tr.values[ENV]
                tr.values[uid] = base.derive(u.capability.produces, out, uid,
                                             tuple(args))
                for slot in u.slots():
                    u.bonds[slot].deliveries += 1
                    sv = tr.values.get(u.bonds[slot].supplier)
                    if sv is not None:
                        # What this INPUT derived from - not what I produced.
                        u.bonds[slot].accepted_chain = sv.chain
                progressed = True
            if not progressed:
                break
        tr.delivered = [(a, b) for a, b in []]
        sink = self.units[SINK]
        if 0 in sink.bonds:
            v = tr.values.get(sink.bonds[0].supplier)
            if v is not None:
                tr.output = v
                tr.ok = bool(self.contract.invariant(v)) and not v.tainted
        for u in self.units.values():
            tr.receipts.extend(u.receipts)
        return tr

    # ------------------------------------------------------------------
    # AUTONOMOUS INTERIOR RE-INITIATION
    #
    # No supervisor calls this. No boundary demand is emitted. Each unit
    # inspects ONLY its own bonds and the values its own suppliers did or did
    # not deliver, and decides for itself whether to reopen one slot.
    # ------------------------------------------------------------------
    def local_review(self, tr: Trace) -> int:
        reopened = 0
        for uid in sorted(self.units):
            u = self.units[uid]
            # ENV has no inputs; SINK is the boundary and holds NO repair
            # authority - if it could reopen, this would be a boundary restart.
            if u.dissolved or uid in (ENV, SINK):
                continue
            for slot in sorted(u.bonds):
                b = u.bonds[slot]
                sup = self.units.get(b.supplier)
                failure = detail = None
                if sup is None or sup.dissolved:
                    failure, detail = SUPPLIER_GONE, "supplier no longer present"
                elif self.is_cut(uid, b.supplier):
                    failure, detail = ISOLATED, "delivery refused on the bonded link"
                elif sup.quiet:
                    failure, detail = NOT_DELIVERING, "supplier present, no delivery"
                elif sup.capability.cost * sup.cost_multiplier > u.repair_budget + 2.0:
                    failure, detail = TOO_EXPENSIVE, "supplier cost exceeds local ceiling"
                elif b.supplier not in tr.values and uid not in tr.values:
                    failure, detail = INTERMITTENT, "expected value absent this round"
                else:
                    v = tr.values.get(b.supplier)
                    if v is not None and v.tainted:
                        failure, detail = SEMANTICALLY_WRONG, "input marked invalid upstream"
                    elif (uid in tr.values and tr.values[uid].tainted):
                        failure, detail = SEMANTICALLY_WRONG, "own output invalid"
                if failure is not None:
                    if u.reopen(slot, failure, detail):
                        reopened += 1
        return reopened

    def repair_round(self) -> int:
        """One bounded round. Only units that reopened emit anything."""
        self.repair_rounds += 1
        movers = 0
        for uid in sorted(self.units):
            u = self.units[uid]
            if u.dissolved or not u.unmet() or uid == SINK:
                continue
            before = len(u.outbox)
            u.emit_needs()
            if len(u.outbox) > before:
                movers += 1
            u.memory.tick()
        if movers:
            self._pump()
        return movers

    def operate(self, payload: Any, max_rounds: int = 4) -> tuple[Trace, dict]:
        """Run the mission, repairing locally between attempts.

        The boundary is NOT asked again. `SINK.emit_needs()` is never called
        here; only interior units that found their own input unusable emit.
        """
        tr = self.execute(payload)
        stats = {"rounds": 0, "interior_reopens": 0, "interior_movers": 0,
                 "messages_start": self.messages}
        rounds = 0
        while not tr.ok and rounds < max_rounds:
            rounds += 1
            n = self.local_review(tr)
            stats["interior_reopens"] += n
            if n == 0 and not any(u.unmet() for u in self.units.values()
                                  if not u.dissolved):
                break
            stats["interior_movers"] += self.repair_round()
            tr = self.execute(payload)
        stats["rounds"] = rounds
        stats["repair_messages"] = self.messages - stats["messages_start"]
        stats["sink_reopens"] = self.units[SINK].reopens
        stats["escalations"] = sum(len(u.escalations) for u in self.units.values())
        stats["stale_rejections"] = sum(u.stale_rejections for u in self.units.values())
        return tr, stats


# ==========================================================================
# Blind diagnosis. Sees traces and receipts. Never a cause label.
# ==========================================================================

@dataclass(frozen=True)
class Diagnosis:
    failure_class: str
    affected_class: str
    evidence: tuple[str, ...]
    confidence: float


def diagnose(healthy: Trace, broken: Trace, receipts: list[Receipt]) -> Optional[Diagnosis]:
    """Infer what went wrong from local evidence only.

    Permitted inputs: execution traces, delivery attempts, blocked deliveries,
    refusal/settlement/escalation receipts, resource records, semantic
    validation results. There is no parameter through which a fixture can pass
    a cause, a victim, an expected class or a topology - asserted by test.
    """
    if broken.ok:
        return None
    refusals = [r for r in receipts if r.kind == "input_refused"]
    if not refusals:
        # No unit recorded a local refusal, yet the mission failed. All that is
        # observable is which values disappeared.
        lost = sorted(set(healthy.values) - set(broken.values))
        if not lost:
            return Diagnosis(SEMANTICALLY_WRONG, "?",
                             ("output invalid with every value still present",), 0.4)
        return Diagnosis(SUPPLIER_GONE, "?",
                         (f"{len(lost)} value(s) absent, no refusal receipt",), 0.3)

    # Each refusal names a failure class its own unit derived locally. Take the
    # modal class; disagreement lowers confidence and is itself reported.
    kinds: dict[str, int] = {}
    for r in refusals:
        cls = r.detail.split(":")[0]
        kinds[cls] = kinds.get(cls, 0) + 1
    top = max(sorted(kinds), key=lambda k: kinds[k])
    agree = kinds[top] / sum(kinds.values())
    affected = [r.supplier_class for r in refusals
                if r.detail.startswith(top) and r.supplier_class]
    return Diagnosis(top, sorted(affected)[0] if affected else "?",
                     (f"{len(refusals)} local refusal receipt(s); "
                      f"{len(kinds)} distinct class(es); modal={top}",), round(agree, 3))


# ==========================================================================
# Measured phenotype and topology-normalized causal form
# ==========================================================================

def measure(organ: Organ, tr: Trace) -> dict:
    """Constitutional readout. Runs AFTER the mission; influences nothing."""
    live = [u for u in organ.units.values() if not u.dissolved and u.unit_id in tr.values]
    edges = sorted({(b.supplier, u.unit_id) for u in live for b in u.bonds.values()})
    domains: dict[str, list[str]] = {}
    for u in live:
        domains.setdefault(u.capability.resource_domain, []).append(u.unit_id)
    joins = [u for u in live if len(u.capability.accepts) > 1]
    independence = []
    for j in joins:
        chains = [tr.values[b.supplier].chain for b in j.bonds.values()
                  if b.supplier in tr.values]
        disjoint = all(not ((a - {ENV}) & (b - {ENV}))
                       for a, b in itertools.combinations(chains, 2))
        independence.append({"class": j.capability.klass(), "independent": disjoint})
    return {
        "dependency_edges": edges,
        "shared_resource_domains": sorted(d for d, m in domains.items() if len(m) > 1),
        "per_unit_resource_consumption": dict(sorted(tr.consumed.items())),
        "verifier_independence": independence,
        "blocked_deliveries": len(tr.blocked),
        "quorum_structure": sorted({len(u.capability.accepts) for u in live}),
    }


def normalized_form(organ: Organ, tr: Trace) -> str:
    """Merkle label over capability CLASSES from the sources upward.

    Unit ids, family names, ordering and reserve carriers cannot make two
    causally identical forms look different.
    """
    memo: dict[str, str] = {}

    def label(uid: str) -> str:
        if uid in memo:
            return memo[uid]
        u = organ.units[uid]
        kids = sorted(label(b.supplier) for b in u.bonds.values())
        memo[uid] = _h(f"{u.capability.klass()}({','.join(kids)})")
        return memo[uid]

    sink = organ.units[SINK]
    if 0 not in sink.bonds:
        return "unformed"
    return label(sink.bonds[0].supplier)


def form_key(organ: Organ, tr: Trace, ph: dict) -> str:
    return _h(json.dumps({
        "geometry": normalized_form(organ, tr),
        "shared_domains": len(ph["shared_resource_domains"]),
        "independence": sorted((d["class"], d["independent"])
                               for d in ph["verifier_independence"]),
        "quorum": ph["quorum_structure"],
    }, sort_keys=True))


# ==========================================================================
# Prohibition over MEASURED relations (Gate G), preserved from Phase 3E
# ==========================================================================

@dataclass(frozen=True)
class MeasuredMotif:
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


def motif_from(diag: Diagnosis) -> MeasuredMotif:
    if diag.failure_class == TOO_EXPENSIVE:
        return MeasuredMotif(diag.affected_class,
                             shared_resource_domain_with_supplier=True)
    if diag.failure_class in (ISOLATED, SUPPLIER_GONE, NOT_DELIVERING):
        return MeasuredMotif(diag.affected_class, supplier_count=1)
    return MeasuredMotif(diag.affected_class, supplier_paths_independent=False)
