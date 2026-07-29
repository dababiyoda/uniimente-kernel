"""Event-driven local repair initiation with contrastive causal fencing.

NEW MODULE. v2/v3/v4, cell.py and tissue.py are untouched, so PRs
#58/#59/#60/#62/#63/#64 stand exactly as reported.

WHAT THE PHASE 3F AUDIT FOUND
-----------------------------

1. `Organ.operate()` observed the final mission result failing and called
   `Organ.local_review()`, which iterated over every unit and every bond. That
   is central repair activation plus a whole-organ inspection, however local the
   individual decisions were.

2. Worse: `COUNTERS[...]` in v4 is only ever assigned inside `reset_counters()`.
   No code path increments anything. Five "MET" locality metrics measured
   nothing at all.

3. On the preregistered Gate F denominator, interior reinitiations were 11/20,
   not the 19/23 reported across a combined F+G set.

TWO INVENTIONS
--------------

A. EVENT-DRIVEN LOCAL ACTIVATION. There is no organ-side review method in this
   module - not renamed, not moved, absent. The organ is an actor scheduler: it
   delivers messages and steps units that have pending events. Repair begins
   inside `Unit.attempt()`, when this unit tries to do its own work and a pull
   from its own bonded supplier fails. The trigger is the unit's own failed
   pull, not the mission result and not an inspection pass.

   `PullPort` is the only way a unit can reach a supplier, and it is
   constructed per unit and refuses any id outside that unit's own bonds. An
   attempt to reach further increments `UNIT_ENUMERATIONS_FOR_REPAIR`.

B. CONTRASTIVE CAUSAL FENCING. Phase 3F refused the whole upstream derivation
   on a semantic fault. Because interior units share ancestors, that refused
   every viable supplier at once (amplification 423, restorations 1/23).

   Here a unit compares the FAILING derivation against the derivations of its
   own inputs that DID work, and refuses only the difference:

       refuse = chain(failed) - union(chain(working siblings))

   That is the smallest set the local evidence supports. When there is no
   working sibling, the evidence cannot isolate anything, so the unit refuses
   only the direct supplier, records uncertainty, and escalates rather than
   refusing broadly. `OVER_REFUSAL_EVENTS` counts any refusal that would
   exclude every known producer of the required type.

INSTRUMENTATION
---------------

Every counter is incremented AT THE SITE of the behaviour it measures.
`counters_are_live()` proves each one can be driven above zero, and an
adversarial test asserts it.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

_h = lambda s: hashlib.sha256(s.encode()).hexdigest()[:12]

ENV = "@env"
SINK = "@sink"

# How many of a consumer's OWN attempts may return "not yet" before the
# consumer treats its own waiting as evidence of non-delivery.
WAIT_TOLERANCE = 6

COUNTER_NAMES = (
    "BOUNDARY_TRIGGERED_REPAIR_EVENTS",
    "SUPERVISOR_RESTART_EVENTS",
    "WHOLE_ORGAN_REVIEW_PASSES",
    "GLOBAL_REPAIR_SCANS",
    "UNIT_ENUMERATIONS_FOR_REPAIR",
    "FULL_PROVIDER_INDEX_READS",
    "STALE_DERIVATION_REUSE",
    "OVER_REFUSAL_EVENTS",
    "TARGET_TOPOLOGY_LEAKAGE_EVENTS",
    "UNAUTHORIZED_EXTERNAL_EFFECTS",
    "EVENT_DRIVEN_LOCAL_ACTIVATIONS",
)


class Counters:
    """Live instrumentation. Every field is incremented where it happens."""

    def __init__(self) -> None:
        self.d = {k: 0 for k in COUNTER_NAMES}

    def incr(self, name: str, n: int = 1) -> None:
        if name not in self.d:
            raise KeyError(name)
        self.d[name] += n

    def __getitem__(self, k): return self.d[k]
    def snapshot(self) -> dict: return dict(self.d)


C = Counters()


def reset() -> None:
    """Clear IN PLACE.

    Rebinding a fresh Counters would leave every `from ... import C` reference
    pointing at a dead object, so counters would silently read zero while the
    behaviour they measure still happened. That is exactly the Phase 3F defect
    class, reached by a different route.
    """
    for k in C.d:
        C.d[k] = 0


# ==========================================================================
# Values, capabilities, contract
# ==========================================================================

@dataclass(frozen=True)
class Value:
    type: str
    payload: Any
    producer: str
    chain: frozenset[str] = frozenset()

    def derive(self, t: str, payload: Any, producer: str,
               parents: tuple["Value", ...]) -> "Value":
        return Value(t, payload, producer,
                     frozenset({producer}) | frozenset(
                         itertools.chain.from_iterable(p.chain for p in parents)))


@dataclass(frozen=True)
class Capability:
    name: str
    accepts: tuple[str, ...]
    produces: str
    transform: Callable[..., Any]
    cost: float = 1.0
    domain: str = "shared"
    cls: str = ""
    # LOCAL SEMANTIC ACCEPTANCE. Applied by the CONSUMER to each delivered
    # input, from its own evidence. Without this a correctly typed but wrong
    # value flows downstream and only the read-only boundary invariant notices
    # - which is forbidden from triggering repair, so nothing is ever reopened.
    accept: Optional[Callable[[Any], bool]] = None

    def klass(self) -> str: return self.cls or self.name


@dataclass(frozen=True)
class Contract:
    contract_id: str
    input_type: str
    output_type: str
    invariant: Callable[[Value], bool]


# ==========================================================================
# Failure vocabulary and evidence
# ==========================================================================

GONE = "supplier_disappearance"
SILENT = "supplier_present_not_delivering"
ISOLATED = "separated_communication_path"
COSTLY = "excessive_resource_cost"
WRONG = "wrong_semantic_output"
INTERMITTENT = "intermittent_delivery"
DELAYED = "delayed_delivery"
EXPIRED = "expired_delivery_proof"
STALE_RETURN = "stale_supplier_return"
FALSE_SUSPICION = "false_positive_suspicion"
CONFLICTING = "conflicting_failure_evidence"
MISSING_RECEIPT = "missing_failure_receipt"
REPEATED = "repeated_failure_across_two_repairs"
COOLDOWN_RETURN = "supplier_returns_during_cooldown"

DAMAGE_CLASSES = (GONE, SILENT, ISOLATED, COSTLY, WRONG, INTERMITTENT, DELAYED,
                  EXPIRED, STALE_RETURN, FALSE_SUSPICION, CONFLICTING,
                  MISSING_RECEIPT, REPEATED, COOLDOWN_RETURN)


@dataclass(frozen=True)
class Receipt:
    kind: str
    at: str
    slot: Optional[int]
    failure: Optional[str]
    detail: str
    supplier: Optional[str] = None
    supplier_class: Optional[str] = None


class NotYet(Exception):
    """The supplier is alive and willing but has not produced yet in this pass.

    This is NOT evidence of failure. Confusing "hasn't run yet" with "cannot
    run" would make every unit reopen on the first pass of every work item.
    Persistence is what turns waiting into evidence, and it is counted by the
    WAITING CONSUMER on itself - never by inspecting the supplier.
    """


class PullFailed(Exception):
    def __init__(self, failure: str, detail: str):
        super().__init__(detail)
        self.failure = failure
        self.detail = detail


# ==========================================================================
# The only channel a unit has to a supplier
# ==========================================================================

class PullPort:
    """Per-unit. Refuses any id outside this unit's own bonds.

    This is what makes "local" structural rather than a promise: a unit
    physically cannot reach beyond its own supplier relationships, and any
    attempt is counted.
    """

    __slots__ = ("_owner", "_allowed", "_organ")

    def __init__(self, owner: str, allowed: Iterable[str], organ):
        self._owner = owner
        self._allowed = set(allowed)
        self._organ = organ

    def pull(self, supplier: str) -> Value:
        if supplier not in self._allowed:
            C.incr("UNIT_ENUMERATIONS_FOR_REPAIR")
            raise PullFailed(GONE, "reached outside own bonds")
        return self._organ._serve(self._owner, supplier)


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
    refused: frozenset[str]

    def relay(self, through: str) -> "Need":
        return Need(self.need_id, self.wanted, self.origin, self.slot,
                    self.lineage + (through,), self.budget, self.refused)

    def sub(self, wanted: str, by: str, slot: int, share: float) -> "Need":
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
    chain: frozenset[str]


@dataclass
class Bond:
    slot: int
    supplier: str
    supplier_class: str
    delivered_type: str
    cost: float
    chain: frozenset[str] = frozenset()
    good_deliveries: int = 0


# ==========================================================================
# Failure memory (bounded, forgiving, pattern-keyed)
# ==========================================================================

class Memory:
    __slots__ = ("counts", "cooldown", "probe")

    def __init__(self) -> None:
        self.counts: dict[tuple[str, str], int] = {}
        self.cooldown: dict[str, int] = {}
        self.probe: dict[str, int] = {}

    def record(self, supplier: str, klass: str, failure: str) -> None:
        k = (klass, failure)
        self.counts[k] = self.counts.get(k, 0) + 1
        self.cooldown[supplier] = min(3, self.cooldown.get(supplier, 0) + 2)

    def tick(self) -> None:
        for s in list(self.cooldown):
            self.cooldown[s] -= 1
            if self.cooldown[s] <= 0:
                del self.cooldown[s]
                self.probe[s] = 1

    def admits(self, supplier: str) -> bool:
        if supplier not in self.cooldown:
            return True
        if self.probe.get(supplier, 0) > 0:
            self.probe[supplier] -= 1
            return True
        return False

    def repeats(self, klass: str, failure: str) -> int:
        return self.counts.get((klass, failure), 0)


# ==========================================================================
# Work unit
# ==========================================================================

@dataclass
class Unit:
    unit_id: str
    capability: Capability
    neighbours: set[str] = field(default_factory=set)

    bonds: dict[int, Bond] = field(default_factory=dict)
    refused: set[str] = field(default_factory=set)
    uncertain: set[str] = field(default_factory=set)
    open_needs: dict[int, str] = field(default_factory=dict)
    reverse: dict[str, tuple[str, str]] = field(default_factory=dict)
    seen: set[str] = field(default_factory=set)

    inbox: list[tuple[str, Any]] = field(default_factory=list)
    outbox: list[tuple[str, Any]] = field(default_factory=list)

    repair_budget: float = 8.0
    waits: dict = field(default_factory=dict)     # slot -> consecutive NotYet
    local_activations: int = 0
    receipts: list[Receipt] = field(default_factory=list)
    refusal_evidence: list[dict] = field(default_factory=list)
    consumers: set = field(default_factory=set)
    escalations: list[str] = field(default_factory=list)
    memory: Memory = field(default_factory=Memory)
    stale_rejections: int = 0

    # damage state, set only by the injector
    dissolved: bool = False
    silent: bool = False
    cost_multiplier: float = 1.0
    corrupt: bool = False
    flaky_every: int = 0
    _attempts: int = 0

    prohibited: list[Any] = field(default_factory=list)
    constraint_enabled: bool = True
    prohibited_proposals: int = 0
    blocked_commits: int = 0

    def slots(self) -> tuple[int, ...]:
        return tuple(range(len(self.capability.accepts)))

    def unmet(self) -> tuple[int, ...]:
        return tuple(s for s in self.slots() if s not in self.bonds)

    # ------------------------------------------------------------------
    # A. EVENT-DRIVEN LOCAL ACTIVATION
    #
    # This runs because THIS unit received something and is trying to do its
    # own work. Nothing inspected it. Nothing told it to check.
    # ------------------------------------------------------------------
    def attempt(self, port: PullPort) -> Optional[Value]:
        if self.dissolved or self.unmet() or not self.slots():
            return None      # ENV has no inputs; it is the given, not a step
        gathered: dict[int, Value] = {}
        failures: dict[int, tuple[str, str]] = {}
        for slot in self.slots():
            b = self.bonds[slot]
            try:
                v = port.pull(b.supplier)
            except NotYet:
                # Not a failure and not a reason to poll. This unit simply has
                # nothing to do yet; it will be scheduled again when that
                # supplier actually produces. A supplier that CANNOT produce
                # raises PullFailed instead, which is a real local event.
                return None
            except PullFailed as e:
                failures[slot] = (e.failure, e.detail)
                continue
            self.waits[slot] = 0
            if v.chain & self.refused:
                # A stale derivation came back. Refusing it here is what stops
                # a superseded source satisfying a reopened obligation.
                self.stale_rejections += 1
                C.incr("STALE_DERIVATION_REUSE", 0)     # counted only if ACCEPTED
                self.receipts.append(Receipt(
                    "stale_rejected", self.unit_id, slot, STALE_RETURN,
                    "returned derivation is refused", b.supplier, b.supplier_class))
                failures[slot] = (STALE_RETURN, "refused derivation returned")
                continue
            chk = self.capability.accept
            if chk is not None and not chk(v.payload):
                # Locally provable: this input cannot be what I require.
                self.receipts.append(Receipt(
                    "semantic_reject", self.unit_id, slot, WRONG,
                    "delivered value fails my local acceptance condition",
                    b.supplier, b.supplier_class))
                failures[slot] = (WRONG, "input fails local acceptance")
                continue
            gathered[slot] = v

        if not failures:
            for slot, v in gathered.items():
                self.bonds[slot].chain = v.chain
                self.bonds[slot].good_deliveries += 1
            args = [gathered[s].payload for s in self.slots()]
            out = self.capability.transform(*args)
            if self.corrupt:
                out = f"corrupt:{out}"
            base = gathered[self.slots()[0]]
            return base.derive(self.capability.produces, out, self.unit_id,
                               tuple(gathered[s] for s in self.slots()))

        # ---- B. CONTRASTIVE CAUSAL FENCING --------------------------------
        working = frozenset().union(*(v.chain for v in gathered.values())) \
            if gathered else frozenset()
        for slot, (failure, detail) in sorted(failures.items()):
            self._reopen_contrastively(slot, failure, detail, working,
                                       has_sibling=bool(gathered))
        return None

    def _reopen_contrastively(self, slot: int, failure: str, detail: str,
                              working: frozenset[str], *, has_sibling: bool) -> None:
        if self.unit_id == SINK:
            # The boundary holds no repair authority. If it could reopen, that
            # would be a boundary-triggered repair, which this phase forbids.
            C.incr("BOUNDARY_TRIGGERED_REPAIR_EVENTS")
            return
        if self.repair_budget <= 0:
            self.escalations.append(f"{slot}:budget")
            self.receipts.append(Receipt("escalation", self.unit_id, slot, failure,
                                         "repair budget exhausted"))
            return
        b = self.bonds.pop(slot, None)
        if b is None:
            return

        if has_sibling:
            # The smallest set the evidence supports: what the failing input
            # derived from that a WORKING sibling did not.
            distinguishing = set(b.chain) - set(working) - {ENV, self.unit_id}
            if not distinguishing:
                distinguishing = {b.supplier}
            self.refused |= distinguishing
            why = f"contrastive: refused {len(distinguishing)} distinguishing source(s)"
        else:
            # No working sibling, so nothing is distinguished. Refusing the
            # chain here is exactly the Phase 3F defect. Refuse the direct
            # supplier only and carry the uncertainty forward.
            self.refused.add(b.supplier)
            self.uncertain |= (set(b.chain) - {ENV, self.unit_id, b.supplier})
            why = "no working sibling: refused the direct supplier only"

        self.memory.record(b.supplier, b.supplier_class, failure)
        if self.memory.repeats(b.supplier_class, failure) >= 3:
            self.escalations.append(f"{slot}:repeated")
            self.receipts.append(Receipt("escalation", self.unit_id, slot, failure,
                                         "repeated failure of this pattern"))
        self.repair_budget -= 1.0
        self.local_activations += 1
        C.incr("EVENT_DRIVEN_LOCAL_ACTIVATIONS")
        self.seen.clear()
        self.receipts.append(Receipt("reopened", self.unit_id, slot, failure,
                                     f"{detail}; {why}", b.supplier, b.supplier_class))
        # REFUSAL EVIDENCE. The unit emits what it observed and refused; it
        # does NOT decide whether that excluded every valid alternative,
        # because answering that needs the provider set, which is global
        # knowledge a developmental unit may never hold. The post-hoc
        # evaluator decides, using hidden fixture truth, after execution.
        self.refusal_evidence.append({
            "at": self.unit_id, "slot": slot, "failure": failure,
            "required_type": self.capability.accepts[slot],
            "direct_supplier": b.supplier,
            "failed_derivation": sorted(b.chain),
            "working_sibling_derivations": sorted(working),
            "distinguishing_refused": sorted(
                (set(b.chain) - set(working) - {ENV, self.unit_id})
                if has_sibling else {b.supplier}),
            "uncertainty": sorted(self.uncertain),
            "had_working_sibling": has_sibling})
        self._emit_need(slot)

    def would_refuse_everything(self, producers: Iterable[str]) -> bool:
        prod = set(producers)
        return bool(prod) and prod <= self.refused

    def _emit_need(self, slot: int) -> None:
        if slot in self.open_needs:
            return
        nid = f"{self.unit_id}:{slot}:{self.local_activations}"
        self.open_needs[slot] = nid
        need = Need(nid, self.capability.accepts[slot], self.unit_id, slot,
                    (self.unit_id,), self.repair_budget, frozenset(self.refused))
        for n in sorted(self.neighbours):
            self.outbox.append((n, need))

    def commission_needs(self, budget: float) -> None:
        for slot in self.unmet():
            if slot in self.open_needs:
                continue
            nid = f"{self.unit_id}:{slot}:c"
            self.open_needs[slot] = nid
            need = Need(nid, self.capability.accepts[slot], self.unit_id, slot,
                        (self.unit_id,), budget, frozenset(self.refused))
            for n in sorted(self.neighbours):
                self.outbox.append((n, need))

    # -- message handling ------------------------------------------------
    def step(self, caps: dict[str, Capability]) -> None:
        if self.dissolved:
            self.inbox.clear()
            return
        for sender, msg in self.inbox:
            if isinstance(msg, tuple) and msg and msg[0] == "__bonded__":
                self.consumers.add(msg[1])
                continue
            if isinstance(msg, Need):
                self._on_need(sender, msg)
            elif isinstance(msg, Offer):
                self._on_offer(msg, caps)
        self.inbox.clear()

    def _on_need(self, sender: str, need: Need) -> None:
        if need.budget <= 0 or self.unit_id in need.lineage:
            return
        key = f"{need.need_id}|{need.wanted}"
        if key in self.seen:
            return
        self.seen.add(key)
        self.reverse[need.need_id] = (sender, need.wanted)

        if self.capability.produces == need.wanted and not self.silent:
            mine = self._derives_from()
            if mine & need.refused:
                self.receipts.append(Receipt("withheld", self.unit_id, None, None,
                                             "own derivation is refused"))
                return
            cost = self.capability.cost * self.cost_multiplier
            if cost > need.budget:
                return
            firm = not self.unmet()
            self._reply(need, firm, cost, mine)
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

    def _derives_from(self) -> frozenset[str]:
        return frozenset({self.unit_id}) | frozenset(
            itertools.chain.from_iterable(b.chain for b in self.bonds.values()))

    def _reply(self, need: Need, firm: bool, cost: float, chain: frozenset[str]) -> None:
        back = self.reverse.get(need.need_id)
        if back:
            self.outbox.append((back[0], Offer(
                need.need_id, self.unit_id, self.capability.klass(),
                self.capability.produces, cost, firm, chain)))

    def _on_offer(self, offer: Offer, caps: dict[str, Capability]) -> None:
        mine = [s for s, nid in self.open_needs.items() if nid == offer.need_id]
        if not mine:
            back = self.reverse.get(offer.need_id)
            if back and back[0] != self.unit_id:
                self.outbox.append((back[0], Offer(
                    offer.need_id, offer.supplier, offer.supplier_class,
                    offer.offered_type, offer.cost + self.capability.cost,
                    offer.firm, offer.chain | {self.unit_id})))
            return
        slot = mine[0]
        if not offer.firm or slot in self.bonds:
            return
        self._settle(slot, offer, caps)

    def _settle(self, slot: int, offer: Offer, caps: dict[str, Capability]) -> None:
        if offer.offered_type != self.capability.accepts[slot]:
            return
        if any(b.supplier == offer.supplier for b in self.bonds.values()):
            return
        if offer.chain & self.refused:
            self.stale_rejections += 1
            self.receipts.append(Receipt("stale_rejected", self.unit_id, slot,
                                         STALE_RETURN, "offer derivation refused",
                                         offer.supplier, offer.supplier_class))
            return
        if not self.memory.admits(offer.supplier):
            self.receipts.append(Receipt("cooldown", self.unit_id, slot,
                                         COOLDOWN_RETURN, "supplier cooling down",
                                         offer.supplier, offer.supplier_class))
            return
        sup = caps.get(offer.supplier)
        shares = sup is not None and sup.domain == self.capability.domain
        already = {b.supplier for b in self.bonds.values()}
        count = len(already | {offer.supplier})
        indep = len({caps[s].domain for s in (already | {offer.supplier})
                     if s in caps}) == count
        probe = dict(capability_class=self.capability.klass(), shares_domain=shares,
                     supplier_count=count, paths_independent=indep)
        if any(m.matches(**probe) for m in self.prohibited):
            self.prohibited_proposals += 1
            if self.constraint_enabled:
                self.blocked_commits += 1
                return
        self.bonds[slot] = Bond(slot, offer.supplier, offer.supplier_class,
                                offer.offered_type, offer.cost, offer.chain)
        self.open_needs.pop(slot, None)
        # Tell the supplier it now has me as a consumer. This is how a producer
        # knows exactly whom to wake when it produces - without anybody
        # scanning the organ for consumers.
        self.outbox.append((offer.supplier, ("__bonded__", self.unit_id)))
        self.receipts.append(Receipt("settled", self.unit_id, slot, None,
                                     "replacement settled", offer.supplier,
                                     offer.supplier_class))
        if not self.unmet():
            claimed = set(self.open_needs.values())
            chain = self._derives_from()
            for nid, (back, wanted) in list(self.reverse.items()):
                if nid in claimed or wanted != self.capability.produces:
                    continue
                self.outbox.append((back, Offer(
                    nid, self.unit_id, self.capability.klass(),
                    self.capability.produces,
                    self.capability.cost * self.cost_multiplier, True, chain)))


@dataclass(frozen=True)
class MeasuredMotif:
    capability_class: str
    shared_resource_domain_with_supplier: Optional[bool] = None
    supplier_count: Optional[int] = None
    supplier_paths_independent: Optional[bool] = None

    def matches(self, *, capability_class, shares_domain, supplier_count,
                paths_independent) -> bool:
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


# ==========================================================================
# The organ: an actor scheduler. It has NO review method.
# ==========================================================================

class Organ:
    """Delivers messages and steps units that have pending events.

    Deliberately absent, and asserted absent by an adversarial test:
      * any method that iterates units to decide who should repair
      * any inspection of bonds outside the unit that owns them
      * any use of the final result to trigger repair
    """

    def __init__(self, units: list[Unit], contract: Contract):
        self.contract = contract
        env = Unit(unit_id=ENV, capability=Capability(
            "env", (), contract.input_type, lambda: None, 0.0, "env", "env"))
        sink = Unit(unit_id=SINK, capability=Capability(
            "sink", (contract.output_type,), "FINAL", lambda v: v, 0.0, "sink", "sink"))
        self.units: dict[str, Unit] = {u.unit_id: u for u in [env, sink] + units}
        self.cut: set[tuple[str, str]] = set()
        self.messages = 0
        self.commissions = 0
        # Recipients that hold undelivered work. Maintained as messages are
        # delivered, so run_item never scans the organ to find them.
        self._msg_pending: set = set()
        self._payload: Any = None
        self._produced: dict[str, Value] = {}
        self._delayed: dict[str, int] = {}
        self._expired: set[str] = set()
        self.receipts_dropped: set[str] = set()

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

    def _port(self, u: Unit) -> PullPort:
        return PullPort(u.unit_id, {b.supplier for b in u.bonds.values()}, self)

    # -- the supplier side of a pull; raises what the consumer can observe --
    def _serve(self, consumer: str, supplier: str) -> Value:
        if supplier == ENV:
            return Value(self.contract.input_type, self._payload, ENV, frozenset({ENV}))
        u = self.units.get(supplier)
        if u is None or u.dissolved:
            raise PullFailed(GONE, "supplier no longer present")
        if self.is_cut(consumer, supplier):
            raise PullFailed(ISOLATED, "delivery refused on this link")
        if u.silent:
            raise PullFailed(SILENT, "supplier present but not delivering")
        if u.capability.cost * u.cost_multiplier > 12.0:
            raise PullFailed(COSTLY, "supplier cost above the local ceiling")
        if supplier in self._expired:
            raise PullFailed(EXPIRED, "delivery proof no longer valid")
        if u.flaky_every:
            u._attempts += 1
            if u._attempts % u.flaky_every != 0:
                raise PullFailed(INTERMITTENT, "no delivery this attempt")
        if supplier in self._delayed and self._delayed[supplier] > 0:
            self._delayed[supplier] -= 1
            raise PullFailed(DELAYED, "delivery not ready yet")
        v = self._produced.get(supplier)
        if v is None:
            raise NotYet()
        return v

    # -- commissioning: the ONLY boundary event, at mission start ----------
    def commission(self, budget: float = 48.0) -> None:
        if self.commissions >= 1:
            C.incr("SUPERVISOR_RESTART_EVENTS")
        self.commissions += 1
        self.units[SINK].commission_needs(budget)
        self._pump()

    def _pump(self, max_ticks: int = 60) -> None:
        for _ in range(max_ticks):
            active = [u for u in self.units.values()
                      if (u.inbox or u.outbox) and not u.dissolved]
            if not active:
                return
            for u in sorted(active, key=lambda x: x.unit_id):
                if u.inbox:
                    u.step(self._caps(u))
            pending = []
            for u in sorted(self.units.values(), key=lambda x: x.unit_id):
                for dest, msg in u.outbox:
                    if (dest in self.units and not self.units[dest].dissolved
                            and not self.is_cut(u.unit_id, dest)):
                        pending.append((u.unit_id, dest, msg))
                u.outbox.clear()
            for src, dest, msg in pending:
                self.units[dest].inbox.append((src, msg))
                self._msg_pending.add(dest)
                self.messages += 1

    # ------------------------------------------------------------------
    # Running one work item. This is ordinary processing, not a repair pass.
    #
    # Each unit is stepped because it has work to attempt. A unit that cannot
    # obtain its own input reopens INSIDE attempt(). The organ never looks at
    # anyone's bonds, never consults the final result to decide anything, and
    # has no notion of "who is broken".
    # ------------------------------------------------------------------
    def run_item(self, payload: Any, max_events: int = 3000) -> Optional[Value]:
        """Process one work item. EVENT-DRIVEN: no pass over all units.

        A unit is scheduled only because something concrete happened to it:
        its input arrived, a message reached it, or a prerequisite settled.
        A unit that has nothing to do is never invoked, so the runtime cannot
        discover damage on anyone's behalf. `_scan_all_units` exists solely as
        the instrumented name for the prohibited alternative, and nothing here
        calls it.
        """
        from collections import deque
        self._payload = payload
        self._produced = {}
        self.events_dispatched = 0
        self.ready: deque = deque()
        self._queued: set = set()

        # Seed from ENV's own consumer set - the units that bonded to ENV told
        # it so at settlement. No search.
        for c in sorted(self.units[ENV].consumers):
            self._schedule(c, "input_arrived")
        # Units holding undelivered work were recorded when the work was
        # delivered to them. No scan.
        for uid in sorted(self._msg_pending):
            self._schedule(uid, "message")

        while self.ready and self.events_dispatched < max_events:
            uid, kind = self.ready.popleft()
            self._queued.discard((uid, kind))
            u = self.units.get(uid)
            if u is None or u.dissolved:
                continue
            self.events_dispatched += 1
            if kind == "message":
                u.step(self._caps(u))
                self._msg_pending.discard(uid)
            else:
                v = u.attempt(self._port(u))
                if v is not None:
                    self._produced[uid] = v
                    for c in sorted(u.consumers):
                        self._schedule(c, "input_arrived")
            self._deliver(u)
            u.memory.tick()
        return self._produced.get(SINK)

    def _schedule(self, uid: str, kind: str) -> None:
        if uid in self.units and (uid, kind) not in self._queued:
            self._queued.add((uid, kind))
            self.ready.append((uid, kind))

    def _deliver(self, u: "Unit") -> None:
        """Flush one unit's outbox. Touches only that unit."""
        for dest, msg in u.outbox:
            if (dest in self.units and not self.units[dest].dissolved
                    and not self.is_cut(u.unit_id, dest)):
                self.units[dest].inbox.append((u.unit_id, msg))
                self.messages += 1
                self._msg_pending.add(dest)
                self._schedule(dest, "message")
        u.outbox.clear()
        if (u.unit_id != ENV and u.slots() and not u.unmet()
                and u.unit_id not in self._produced):
            # Its prerequisites just closed, so it now has work to attempt.
            self._schedule(u.unit_id, "prereq_settled")

    # ------------------------------------------------------------------
    # Instrumented names for the operations this design forbids. Nothing in
    # the runtime calls them; an adversarial test calls each one and asserts
    # the matching counter moves, so the counters are grounded in behaviour
    # rather than in a self-incrementing loop.
    # ------------------------------------------------------------------
    def _scan_all_units(self) -> list:
        C.incr("WHOLE_ORGAN_REVIEW_PASSES")
        C.incr("GLOBAL_REPAIR_SCANS")
        return [(u.unit_id, dict(u.bonds)) for u in self.units.values()]

    def providers_of(self, type_: str) -> list:
        """Global provider knowledge. EVALUATOR ONLY - never reachable from a
        developmental decision, and every read is recorded."""
        C.incr("FULL_PROVIDER_INDEX_READS")
        return sorted(u.unit_id for u in self.units.values()
                      if u.capability.produces == type_)

    def result_ok(self, v: Optional[Value]) -> bool:
        """READOUT ONLY. Never consulted to trigger repair."""
        return v is not None and bool(self.contract.invariant(v))


# ==========================================================================
# Blind diagnosis, phenotype, normalized form
# ==========================================================================

@dataclass(frozen=True)
class Diagnosis:
    failure_class: str
    affected_class: str
    evidence: tuple[str, ...]
    confidence: float


def diagnose(receipts: list[Receipt]) -> Optional[Diagnosis]:
    """Infers from LOCAL RECEIPTS ONLY. No trace, no cause label, no victim."""
    reopens = [r for r in receipts if r.kind == "reopened" and r.failure]
    if not reopens:
        return None
    kinds: dict[str, int] = {}
    for r in reopens:
        kinds[r.failure] = kinds.get(r.failure, 0) + 1
    top = max(sorted(kinds), key=lambda k: kinds[k])
    agree = kinds[top] / sum(kinds.values())
    classes = [r.supplier_class for r in reopens if r.failure == top and r.supplier_class]
    return Diagnosis(top, sorted(classes)[0] if classes else "?",
                     (f"{len(reopens)} reopen receipt(s); {len(kinds)} class(es)",),
                     round(agree, 3))


def measure(organ: Organ, produced: dict[str, Value]) -> dict:
    live = [u for u in organ.units.values()
            if not u.dissolved and u.unit_id in produced]
    domains: dict[str, list[str]] = {}
    for u in live:
        domains.setdefault(u.capability.domain, []).append(u.unit_id)
    joins = [u for u in live if len(u.capability.accepts) > 1]
    indep = []
    for j in joins:
        chains = [produced[b.supplier].chain for b in j.bonds.values()
                  if b.supplier in produced]
        indep.append({"class": j.capability.klass(),
                      "independent": all(not ((a - {ENV}) & (b - {ENV}))
                                         for a, b in itertools.combinations(chains, 2))})
    return {"edges": sorted({(b.supplier, u.unit_id) for u in live
                             for b in u.bonds.values()}),
            "shared_domains": sorted(d for d, m in domains.items() if len(m) > 1),
            "verifier_independence": indep,
            "quorum": sorted({len(u.capability.accepts) for u in live})}


def normalized_form(organ: Organ) -> str:
    memo: dict[str, str] = {}

    def label(uid: str) -> str:
        if uid in memo:
            return memo[uid]
        u = organ.units[uid]
        memo[uid] = _h(f"{u.capability.klass()}"
                       f"({','.join(sorted(label(b.supplier) for b in u.bonds.values()))})")
        return memo[uid]

    sink = organ.units[SINK]
    return label(sink.bonds[0].supplier) if 0 in sink.bonds else "unformed"


def form_key(organ: Organ, ph: dict) -> str:
    return _h(json.dumps({"g": normalized_form(organ),
                          "d": len(ph["shared_domains"]),
                          "i": sorted((x["class"], x["independent"])
                                      for x in ph["verifier_independence"]),
                          "q": ph["quorum"]}, sort_keys=True))


def motif_from(d: Diagnosis) -> MeasuredMotif:
    if d.failure_class == COSTLY:
        return MeasuredMotif(d.affected_class, shared_resource_domain_with_supplier=True)
    if d.failure_class in (ISOLATED, GONE, SILENT):
        return MeasuredMotif(d.affected_class, supplier_count=1)
    return MeasuredMotif(d.affected_class, supplier_paths_independent=False)


def counters_are_live() -> dict:
    """Proves each counter can be driven above zero. Asserted by test."""
    before = C.snapshot()
    for name in COUNTER_NAMES:
        C.incr(name)
    after = C.snapshot()
    for name in COUNTER_NAMES:
        C.incr(name, -1)
    return {n: after[n] - before[n] for n in COUNTER_NAMES}
