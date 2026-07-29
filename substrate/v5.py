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
   refusing broadly.

   A unit does NOT decide whether its refusal excluded every valid
   alternative: answering that needs the provider set, which is global
   knowledge a developmental unit may never hold. Units emit refusal
   EVIDENCE (failed derivation, working-sibling derivations, distinguishing
   set, uncertainty, direct supplier, required type) and the post-hoc
   evaluator judges over-refusal using hidden fixture truth after execution.

INSTRUMENTATION
---------------

Every counter is incremented AT THE SITE of the behaviour it measures, and each
has an adversarial test that TRIGGERS that behaviour and asserts the increment:
`_scan_all_units()`, `providers_of()`, a second `commission()`, a boundary
reopen attempt, and a pull outside a unit's own bonds.

`counters_are_live()` proves counter-container arithmetic ONLY. It increments
every counter by hand, so it demonstrates that dictionary arithmetic works and
nothing more. It is never evidence that a measured behaviour drives its
counter.
"""
from __future__ import annotations

import dataclasses
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

# Propagation depth. Formation must reach the full contract chain; repair is a
# local search and is deliberately shallower. These bound message volume in a
# dense neighbourhood, where preserving a need's full budget across relays is
# what produced amplification of 52 against a ceiling of 12.
FORMATION_HOPS = 40
REPAIR_HOPS = 14
# Local bounded routing. Repair starts at an evidence-selected frontier and
# widens one ring at a time; a single large TTL over a dense neighbourhood is
# what produced amplification of 47.65 against a ceiling of 12.
FRONTIER_WIDTH = 3
REPAIR_SEARCH_BUDGET = 18.0
FORMATION_CREDITS = 400.0

COUNTER_NAMES = (
    "BOUNDARY_TRIGGERED_REPAIR_EVENTS",
    "SUPERVISOR_RESTART_EVENTS",
    "WHOLE_ORGAN_REVIEW_PASSES",
    "GLOBAL_REPAIR_SCANS",
    "UNIT_ENUMERATIONS_FOR_REPAIR",
    "FULL_PROVIDER_INDEX_READS",
    "STALE_DERIVATIONS_REJECTED",
    "STALE_DERIVATION_REUSE",
    "OVER_REFUSAL_EVENTS",
    "TARGET_TOPOLOGY_LEAKAGE_EVENTS",
    "UNAUTHORIZED_EXTERNAL_EFFECTS",
    "EVENT_DRIVEN_LOCAL_ACTIVATIONS",
    # Constraint-preserving distinct replacement search.
    "DISTINCT_ELIGIBLE_REPLACEMENTS_DISCOVERED",
    "DISTINCT_ELIGIBLE_REPLACEMENTS_SETTLED",
    "BOUNDED_DISTINCT_REPLACEMENT_EXHAUSTIONS",
    "INELIGIBLE_CANDIDATE_BRANCH_CONTINUATIONS",
    "INDEPENDENCE_VIOLATIONS",
    # Single-Flight Echo Search.
    "UNIQUE_CANONICAL_SEARCH_NODES",
    "CANONICAL_SEARCH_EXPANSIONS",
    "COALESCED_DUPLICATE_ARRIVALS",
    "CYCLE_EDGES_CLOSED",
    "DUPLICATE_SUBTREES_OPENED",
    "DIRECTED_SEARCH_EDGES_PROBED",
    "TERMINAL_ECHOS_SENT",
    "OFFER_RETURN_ROUTE_MISMATCHES",
    "ORPHANED_SEARCH_EDGES",
    "PREMATURE_TERMINATION_SIGNALS",
    "SEARCH_SPACE_EXHAUSTED",
    "SEARCH_BUDGET_EXHAUSTED",
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
    budget: float                 # what a supplier may cost
    refused: frozenset[str]
    hops: int = 24                # how far this need may travel
    credits: float = 0.0          # END-TO-END message budget; branching divides it
    fanout: int = 0               # unused; hops and credits bound propagation
    # SLOT INELIGIBILITY, held strictly apart from `refused`.
    #
    # `refused` is CAUSAL BLAME: this supplier or derivation is implicated in a
    # failure. `must_differ_from` is a STRUCTURAL COMPATIBILITY CONSTRAINT: this
    # supplier is healthy and trustworthy but already fills another slot on the
    # origin, so it cannot also fill this one without destroying the
    # independence a multi-input join exists to provide.
    #
    # Merging them would poison failure memory against a blameless supplier and
    # would make a structural fact look like evidence of fault. It is derived
    # only from the origin's OWN currently settled sibling slots -- local
    # evidence, not a provider index and not topology.
    must_differ_from: frozenset[str] = frozenset()
    # Which allocation of the origin's budget this message is spending. Refunds
    # are credited back to exactly one branch, so a duplicate or replayed
    # completion cannot refund twice.
    branch_id: str = ""

    def relay(self, through: str) -> "Need":
        """A relay SPENDS. Preserving the full budget across relays is what let
        one need saturate a dense neighbourhood; supplier cost was bounded but
        propagation was not."""
        return Need(self.need_id, self.wanted, self.origin, self.slot,
                    self.lineage + (through,), self.budget, self.refused,
                    self.hops - 1, self.credits - 1.0, self.fanout,
                    self.must_differ_from, self.branch_id)

    def sub(self, wanted: str, by: str, slot: int, share: float) -> "Need":
        # A sub-need is a DIFFERENT slot on a DIFFERENT unit, so the origin's
        # sibling exclusions do not apply to it and must not leak across.
        return Need(f"{self.need_id}/{by}:{slot}", wanted, by, slot,
                    self.lineage + (by,), share, self.refused,
                    self.hops - 1, self.credits - 1.0, self.fanout,
                    frozenset(), self.branch_id)


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
    # SETTLEMENT PROVENANCE, read by the evaluator only. Nothing in the runtime
    # branches on either field. Without them an edge can only be keyed by
    # supplier name, so two occurrences of the same supplier cannot be told
    # apart: distinct legitimate edges, a re-settlement in a later work item,
    # and duplicate instrumentation all look identical.
    settled_by: str = ""        # the need generation that closed this slot
    settled_item: int = 0       # the work item during which it settled


# The share of the origin's remaining reserve that one search round may commit.
# The origin must DEBIT what it allocates, so committing the whole reserve in
# round 0 would leave nothing to widen with.
ROUND_SHARE = 0.5

# Test-harness seam: the ONLY correct way to starve search credit. `repair_budget`
# is a supplier COST ceiling, so setting it low does not exercise the message
# credit ledger and cannot distinguish budget exhaustion from space exhaustion.
ROOT_SEARCH_CREDIT_OVERRIDE = None

# Cost a unit charges itself for answering a duplicate arrival. Small, explicit,
# and NOT pooled into the canonical node's reserve.
COALESCE_HANDLING_COST = 1.0


def _digest(items: Iterable[str]) -> str:
    """Deterministic digest of an unordered collection.

    Python's `hash()` is process-randomized for str, so using it here would make
    one semantic search produce different SearchKeys between runs. Sets are
    sorted before digesting so iteration order cannot leak into identity.
    """
    return _h("|".join(sorted(items)))


@dataclass(frozen=True)
class SearchKey:
    """SEMANTIC identity of one search. Transport properties are excluded.

    Two arrivals with the same SearchKey are requests for the same local
    computation. `edge_id`, immediate sender, lineage and arrival order identify
    transport paths, not distinct work, so none of them appear here -- that
    conflation is what made the hierarchical attempt open a fresh subtree per
    path and drove amplification to 526.71.
    """
    need_id: str
    work_item_generation: int
    origin_unit: str
    origin_slot: int
    wanted_type: str
    causal_refusal_digest: str = ""
    must_differ_from_digest: str = ""
    constraint_generation: int = 0

    @staticmethod
    def build(need_id, work_item_generation, origin_unit, origin_slot, wanted_type,
              refused=(), must_differ_from=(), constraint_generation=0) -> "SearchKey":
        return SearchKey(need_id, work_item_generation, origin_unit, origin_slot,
                         wanted_type, _digest(refused), _digest(must_differ_from),
                         constraint_generation)

    def __str__(self) -> str:
        return (f"{self.origin_unit}[{self.origin_slot}]:{self.wanted_type}"
                f"@{self.work_item_generation}/{self.need_id}")


@dataclass(frozen=True)
class Terminal:
    """Exactly one of these ends each transport edge.

    Only SearchExhausted contributes to a no-replacement proof. SearchCoalesced
    means "this path created no additional work because equivalent work is
    already active", which is not evidence about the search space.
    """
    kind: str
    search_key: SearchKey
    edge_id: str
    refund: float = 0.0
    handling_cost: float = 0.0
    from_unit: str = ""
    to_unit: str = ""


TERMINAL_KINDS = ("SearchOffer", "SearchExhausted", "SearchCoalesced",
                  "SearchCycleClosed", "SearchNeedClosed", "SearchCancelled")


def new_canonical_node(key: SearchKey, parent_edge: str, parent_sender: str,
                       allocation: float) -> dict:
    """One canonical local computation per (unit, SearchKey).

    The adopted parent fields are immutable after first adoption: a later arrival
    must never redirect where a result travels home. `reverse[need_id]` allowed
    exactly that, because a second arrival overwrote the earlier return route.
    """
    return {
        "search_key": key,
        "status": "OPEN",
        "adopted_parent_edge": parent_edge,
        "adopted_parent_edge_initial": parent_edge,
        "adopted_parent_sender": parent_sender,
        "incoming_edges": [parent_edge],
        "incoming_allocation": allocation,
        "local_reserve": allocation,
        "handling_cost": 0.0,
        "neighbours_tried": set(),
        "eligible_untried_routes": 0,
        "children_opened": [],
        "children_from": {parent_edge: []},
        "children_outstanding": set(),
        "children_completed": set(),
        "eligible_offer": False,
        "returned_credit": 0.0,
        "consumed_credit": 0.0,
        "cancelled_credit": 0.0,
        "terminal_signal_sent": False,
    }


def new_search_ledger(initial: float = REPAIR_SEARCH_BUDGET) -> dict:
    """Per-need credit ledger with first-class rounds and branches.

    The previous state kept a single `credits` number at the origin and debited
    only 1.0 per branch while handing each branch `credits/len(ring)`. With an
    18-credit budget and a ring of three that put 18 into branches while the
    origin still held 15, so the system possessed 33 credits from a budget of
    18. Calling that end-to-end conservation was wrong, and an evaluator that
    only checked `0 <= origin <= initial` could not see it.

    Invariant, checked by the evaluator over every need:

        initial_credits == reserve + in_flight + consumed + cancelled

    A branch that dies returns its unspent credit, which moves from in_flight
    back to reserve. That is a transfer, never an issue of new credit.
    """
    return {
        "initial_credits": initial,
        "reserve": initial,          # held at the origin, available to allocate
        "allocated": 0.0,            # cumulative, for audit only
        "in_flight": 0.0,            # outstanding in live branches
        "consumed": 0.0,             # spent on hops and reported back
        "returned": 0.0,             # cumulative refunds, for audit only
        "cancelled": 0.0,            # unused reserve released at closure
        "round": 0,
        "branches": {},              # branch_id -> record
        "outstanding": set(),        # opened this round, not yet completed
        "tried": set(),
        "offers": 0,
        "eligible_offers": 0,
        "ineligible_seen": 0,
        "settled": False,
        "closed": False,
        "exhaustion_recorded": False,
        "no_untried_routes": False,
        "rejected": {},
        "must_differ_from": [],
        # Retained so existing readers keep working; it mirrors `reserve`.
        "credits": initial,
    }


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
    closed_needs: set = field(default_factory=set)
    late_messages: int = 0
    # LOCAL ROUTING EVIDENCE, accumulated from this unit's own experience:
    # (required_type) -> {neighbour: [offers_seen, settlements, last_cost]}.
    # It is not a provider index: it records only neighbours THIS unit heard
    # from, and only for types it has itself required.
    routes: dict = field(default_factory=dict)
    # PER-NEED search state. A unit can have several open requirements at once;
    # a single unit-global budget let one requirement consume another's search,
    # which would corrupt simultaneous-failure and Gate G episodes.
    _search: dict = field(default_factory=dict)
    escalations: list[str] = field(default_factory=list)
    memory: Memory = field(default_factory=Memory)
    stale_rejections: int = 0
    # Why the last settlement attempt was refused. Evaluator-only diagnostics.
    _last_refusal: str = ""
    # Needs this unit has already acknowledged as a dead branch, so an
    # acknowledgement is sent at most once per unit per need.
    _exhausted_reported: set = field(default_factory=set)
    # Needs this unit has relayed onward. A later duplicate delivery of the same
    # need must NOT be acknowledged as exhausted: a live sub-branch still carries
    # it, and telling the origin otherwise would complete the branch early,
    # under-count consumed credit, and let a round widen while it is still open.
    _forwarded: set = field(default_factory=set)
    # Which work item is currently being processed. Stamped by the organ at
    # dispatch, recorded into settlement provenance, never branched on.
    item_seq: int = 0
    # SINGLE-FLIGHT: one canonical computation per SearchKey at this unit.
    canonical_searches: dict = field(default_factory=dict)
    # Set at commission. Used ONLY to record edge telemetry, never to inspect
    # other units, their bonds, or the topology.
    _organ: Any = None

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
        failures: dict[int, tuple] = {}   # slot -> (failure, detail[, chain])
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
                # A REJECTED stale derivation is not stale reuse; it is the
                # fence working. STALE_DERIVATION_REUSE means an ACCEPTED value
                # whose derivation intersects the refusal set, and it is
                # derived post hoc by the evaluator from accepted-value
                # evidence, never asserted here.
                C.incr("STALE_DERIVATIONS_REJECTED")
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
                # Fence on THIS value's derivation, not on the bond's stored
                # chain, which may describe an older accepted delivery.
                failures[slot] = (WRONG, "input fails local acceptance", v.chain)
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
        for slot, rec in sorted(failures.items()):
            failure, detail = rec[0], rec[1]
            observed = rec[2] if len(rec) > 2 else None
            self._reopen_contrastively(slot, failure, detail, working,
                                       has_sibling=bool(gathered),
                                       observed_chain=observed)
        return None

    def _reopen_contrastively(self, slot: int, failure: str, detail: str,
                              working: frozenset[str], *, has_sibling: bool,
                              observed_chain: Optional[frozenset] = None) -> None:
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
        # 6. The relationship is over: tell the former supplier so it stops
        # waking me. Without this an replaced supplier keeps scheduling its
        # ex-consumer, inflating events and polluting the stale-return test.
        self.outbox.append((b.supplier, ("__retired__", self.unit_id)))
        # 5. Blame what actually failed. b.chain can describe an older
        # accepted delivery, so an upstream that changed since would be
        # fenced on obsolete ancestry.
        failed_chain = observed_chain if observed_chain is not None else b.chain

        if has_sibling:
            # The smallest set the evidence supports: what the failing input
            # derived from that a WORKING sibling did not.
            distinguishing = set(failed_chain) - set(working) - {ENV, self.unit_id}
            if not distinguishing:
                distinguishing = {b.supplier}
            self.refused |= distinguishing
            why = f"contrastive: refused {len(distinguishing)} distinguishing source(s)"
        else:
            # No working sibling, so nothing is distinguished. Refusing the
            # chain here is exactly the Phase 3F defect. Refuse the direct
            # supplier only and carry the uncertainty forward.
            self.refused.add(b.supplier)
            self.uncertain |= (set(failed_chain) - {ENV, self.unit_id, b.supplier})
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
            "failed_derivation": sorted(failed_chain),
            "working_sibling_derivations": sorted(working),
            "distinguishing_refused": sorted(
                (set(failed_chain) - set(working) - {ENV, self.unit_id})
                if has_sibling else {b.supplier}),
            "uncertainty": sorted(self.uncertain),
            "had_working_sibling": has_sibling})
        self._emit_need(slot)

    # -- SINGLE-FLIGHT ECHO SEARCH -------------------------------------
    #
    # One canonical local computation per (unit, SearchKey). A later arrival
    # carrying the same semantic search registers, refunds and terminates; it
    # never opens another subtree. That is the whole correction over the failed
    # hierarchical tree, which opened a fresh subtree per transport path.

    def _record_probe(self, edge_id: str, frm: str, to: str, key: SearchKey) -> None:
        o = self._organ
        if o is None:
            return
        rec = o.search_edge_probes.setdefault(
            edge_id, {"from_unit": frm, "to_unit": to, "search_key": key, "count": 0})
        rec["count"] += 1
        o.search_edges.setdefault(edge_id, {
            "edge_id": edge_id, "parent_edge_id": "", "from_unit": frm,
            "to_unit": to, "search_key": key, "allocation": 0.0,
            "terminal_status": "open", "terminal_outcome": None,
            "refunded_credit": 0.0, "consumed_credit": 0.0})
        C.incr("DIRECTED_SEARCH_EDGES_PROBED")

    def _record_terminal(self, t: Terminal) -> None:
        """Exactly one terminal outcome per transport edge."""
        o = self._organ
        if o is None:
            return
        rec = o.search_edge_terminals.setdefault(
            t.edge_id, {"from_unit": t.from_unit, "to_unit": t.to_unit,
                        "search_key": t.search_key, "outcomes": []})
        rec["outcomes"].append(t)
        e = o.search_edges.get(t.edge_id)
        if e is not None:
            e["terminal_status"] = "terminal"
            e["terminal_outcome"] = t.kind
            e["refunded_credit"] = t.refund
            e["consumed_credit"] = t.handling_cost
        C.incr("TERMINAL_ECHOS_SENT")

    def _emit_terminal(self, kind: str, key: SearchKey, edge_id: str, to: str,
                       refund: float = 0.0, handling_cost: float = 0.0) -> Terminal:
        t = Terminal(kind, key, edge_id, refund, handling_cost, self.unit_id, to)
        self._record_terminal(t)
        if to:
            self.outbox.append((to, t))
        return t

    def open_canonical_search(self, key: SearchKey, parent_edge: str,
                              allocation: float, parent_sender: str = "") -> dict:
        """First-arrival adoption. At most one node per SearchKey per unit."""
        node = self.canonical_searches.get(key)
        if node is not None:
            C.incr("DUPLICATE_SUBTREES_OPENED")   # must never fire
            return node
        node = new_canonical_node(key, parent_edge, parent_sender, allocation)
        self.canonical_searches[key] = node
        C.incr("UNIQUE_CANONICAL_SEARCH_NODES")
        self._expand_canonical(node)
        return node

    def _expand_canonical(self, node: dict) -> None:
        """Evaluate local eligibility ONCE and open at most one child frontier."""
        C.incr("CANONICAL_SEARCH_EXPANSIONS")
        key = node["search_key"]
        want = key.wanted_type
        boundary = {ENV, SINK}
        ring = [n for n in self._frontier(want)
                if n not in node["neighbours_tried"] and n not in boundary]
        ring += [n for n in sorted(self.neighbours)
                 if n not in node["neighbours_tried"] and n not in self.refused
                 and n not in ring and n not in boundary]
        node["eligible_untried_routes"] = len(ring)
        ring = ring[:FRONTIER_WIDTH]
        if not ring or node["local_reserve"] <= 0:
            return
        per = (node["local_reserve"] * ROUND_SHARE) / len(ring)
        if per < 1.0:
            ring, per = ring[:1], min(node["local_reserve"], 1.0)
        adopted = node["adopted_parent_edge"]
        for i, n in enumerate(ring):
            if node["local_reserve"] < per:
                break
            child = f"{adopted}/c{i}"
            node["local_reserve"] -= per
            node["children_opened"].append(child)
            node["children_outstanding"].add(child)
            node["children_from"].setdefault(adopted, []).append(child)
            node["neighbours_tried"].add(n)
            self._record_probe(child, self.unit_id, n, key)
            self.outbox.append((n, ("__search__", key, child, per,
                                    (self.unit_id,))))
        node["eligible_untried_routes"] = max(
            0, node["eligible_untried_routes"] - len(ring))

    def deliver_search(self, key: SearchKey, edge_id: str, allocation: float,
                       lineage: tuple = (), sender: str = "") -> Terminal:
        """One arrival on one transport edge. Returns its single terminal outcome."""
        o = self._organ
        if o is not None and edge_id in o.search_edge_terminals:
            # Exact replay of an edge already answered: no reprocessing, no
            # second terminal, and CRUCIALLY no second refund. Returning the
            # original terminal object would report its original refund again,
            # which reads as a second payment; the replay is reported as a
            # zero-value echo of the same outcome.
            first = o.search_edge_terminals[edge_id]["outcomes"][0]
            return Terminal(first.kind, first.search_key, edge_id, 0.0, 0.0,
                            self.unit_id, first.to_unit)
        self._record_probe(edge_id, sender or key.origin_unit, self.unit_id, key)

        if self.unit_id in lineage:
            C.incr("CYCLE_EDGES_CLOSED")
            return self._emit_terminal("SearchCycleClosed", key, edge_id, sender,
                                       refund=max(0.0, allocation))
        if key.need_id in self.closed_needs:
            return self._emit_terminal("SearchNeedClosed", key, edge_id, sender,
                                       refund=max(0.0, allocation))
        node = self.canonical_searches.get(key)
        if node is not None:
            # DUPLICATE. No new node, no reopened frontier, no adopted-parent
            # change, and the allocation is NOT pooled into the canonical
            # reserve: only an explicit handling cost is charged.
            cost = min(COALESCE_HANDLING_COST, max(0.0, allocation))
            node["incoming_edges"].append(edge_id)
            node["children_from"].setdefault(edge_id, [])
            node["handling_cost"] += cost
            C.incr("COALESCED_DUPLICATE_ARRIVALS")
            return self._emit_terminal("SearchCoalesced", key, edge_id, sender,
                                       refund=max(0.0, allocation - cost),
                                       handling_cost=cost)
        # First arrival: adopt, and answer immediately if I can supply.
        node = self.open_canonical_search(key, edge_id, allocation, sender)
        if (self.capability.produces == key.wanted_type and not self.silent
                and self.unit_id not in self._must_differ(key)
                and not self.unmet()):
            node["eligible_offer"] = True
            node["status"] = "ANSWERED"
            C.incr("DISTINCT_ELIGIBLE_REPLACEMENTS_DISCOVERED")
            return self._emit_terminal("SearchOffer", key, edge_id, sender)
        return Terminal("SearchPending", key, edge_id, 0.0, 0.0, self.unit_id, sender)

    def _must_differ(self, key: SearchKey) -> frozenset[str]:
        """Sibling exclusions for a key I originated. Empty for keys I relay."""
        if key.origin_unit != self.unit_id:
            return frozenset()
        return frozenset(b.supplier for s, b in self.bonds.items()
                         if s != key.origin_slot)

    def deliver_terminal(self, key: SearchKey, edge_id: str, kind: str,
                         refund: float = 0.0) -> None:
        """Aggregate one child outcome. Echo upward only when ALL are terminal."""
        node = self.canonical_searches.get(key)
        if node is None:
            C.incr("ORPHANED_SEARCH_EDGES")
            return
        if edge_id in node["children_completed"]:
            return                              # replay: idempotent, no refund
        if edge_id not in node["children_outstanding"]:
            return
        node["children_outstanding"].discard(edge_id)
        node["children_completed"].add(edge_id)
        node["returned_credit"] += max(0.0, refund)
        node["local_reserve"] += max(0.0, refund)
        if node["status"] != "OPEN" or node["terminal_signal_sent"]:
            return
        if kind == "SearchOffer":
            # AN ANSWER SHORT-CIRCUITS. Waiting for the remaining children to die
            # before forwarding good news is wrong: the subtree has produced a
            # viable result, so it echoes home immediately and the rest of the
            # subtree is cancelled. Only EXHAUSTION has to wait for every child.
            node["eligible_offer"] = True
            node["status"] = "ANSWERED"
            node["terminal_signal_sent"] = True
            node["cancelled_credit"] += node["local_reserve"]
            node["local_reserve"] = 0.0
            node["children_outstanding"].clear()
            self._emit_terminal("SearchOffer", key, node["adopted_parent_edge"],
                                node["adopted_parent_sender"])
            return
        if node["children_outstanding"]:
            return                              # siblings still live
        if node["eligible_offer"]:
            node["status"] = "ANSWERED"
            node["terminal_signal_sent"] = True
            self._emit_terminal("SearchOffer", key, node["adopted_parent_edge"],
                                node["adopted_parent_sender"])
            return
        # No answer and every actual child is terminal. Is the SPACE closed, or
        # did credit run out first? These are different claims.
        if node["eligible_untried_routes"] > 0 and node["local_reserve"] < 1.0:
            node["status"] = "EXHAUSTED"
            node["terminal_signal_sent"] = True
            C.incr("SEARCH_BUDGET_EXHAUSTED")
            if self._organ is not None:
                self._organ.budget_exhaustion_records.append(key)
            self.escalations.append(
                f"search budget exhausted for {key}: "
                f"{node['eligible_untried_routes']} eligible routes untried")
            self._emit_terminal("SearchExhausted", key, node["adopted_parent_edge"],
                                node["adopted_parent_sender"],
                                refund=node["local_reserve"])
            return
        if node["eligible_untried_routes"] > 0 and node["local_reserve"] >= 1.0:
            self._expand_canonical(node)        # widen: the round is complete
            if node["children_outstanding"]:
                return
        node["status"] = "EXHAUSTED"
        node["terminal_signal_sent"] = True
        node["cancelled_credit"] += node["local_reserve"]
        node["local_reserve"] = 0.0
        C.incr("SEARCH_SPACE_EXHAUSTED")
        if self._organ is not None:
            self._organ.space_exhaustion_proofs.append(key)
        self.escalations.append(
            f"no eligible distinct supplier for slot {key.origin_slot}: "
            f"{len(node['children_completed'])} branches searched, "
            f"excluded {sorted(self._must_differ(key))}")
        self.receipts.append(Receipt("branch_exhausted", self.unit_id,
                                     key.origin_slot, None,
                                     "bounded distinct replacement exhaustion"))
        self._emit_terminal("SearchExhausted", key, node["adopted_parent_edge"],
                            node["adopted_parent_sender"])

    def replay_search_edge(self, key: SearchKey, edge_id: str) -> None:
        """Exact replay of an already-answered edge is a no-op."""
        o = self._organ
        if o is not None and edge_id in o.search_edge_terminals:
            return
        self.deliver_search(key, edge_id, 0.0)

    def would_refuse_everything(self, producers: Iterable[str]) -> bool:
        prod = set(producers)
        return bool(prod) and prod <= self.refused

    def _emit_need(self, slot: int) -> None:
        """LOCAL BOUNDED ROUTING, not a broadcast.

        Start with the neighbours this unit has itself seen deliver a settled
        offer of the required type, excluding the route that just failed. Widen
        by one ring only when the current frontier yields nothing. Every message
        and every expansion is charged against a search budget.
        """
        if slot in self.open_needs:
            return
        nid = f"{self.unit_id}:{slot}:{self.local_activations}"
        self.open_needs[slot] = nid
        self._search[nid] = new_search_ledger()
        self._send_to_frontier(slot, nid)

    def _frontier(self, want: str) -> list[str]:
        known = self.routes.get(want, {})
        good = [n for n, e in known.items()
                if e["settled"] > 0 and n not in self.refused
                and n in self.neighbours]
        if good:
            return sorted(good, key=lambda n: (-known[n]["settled"],
                                               known[n]["cost"], n))
        heard = [n for n in known if n in self.neighbours and n not in self.refused]
        return sorted(heard) if heard else []

    def _untried_routes(self, st: dict, want: str) -> list[str]:
        """Local routes for `want` this search has not yet spent a branch on."""
        boundary = {ENV, SINK}
        preferred = [n for n in self._frontier(want)
                     if n not in st["tried"] and n not in boundary]
        rest = [n for n in sorted(self.neighbours)
                if n not in st["tried"] and n not in self.refused
                and n not in preferred and n not in boundary]
        return preferred + rest

    def _send_to_frontier(self, slot: int, nid: str) -> bool:
        st = self._search.get(nid)
        if st is None or st["closed"] or st["reserve"] <= 0:
            return False
        want = self.capability.accepts[slot]
        # The boundary cannot supply an interior repair type, so spending a
        # round-0 slot on ENV or SINK wasted a third of the fan-out.
        ring = self._untried_routes(st, want)[:FRONTIER_WIDTH]
        if not ring:
            st["no_untried_routes"] = True
            return False
        # The origin DEBITS exactly what it commits. Allocating the whole reserve
        # in one round would leave nothing to widen with, so a round may commit
        # only ROUND_SHARE of what remains, and never more than it holds.
        budget = st["reserve"] * ROUND_SHARE
        per = budget / len(ring)
        if per < 1.0:                      # too little to split: spend it as one
            ring, per = ring[:1], min(st["reserve"], max(1.0, budget))
        # The suppliers already filling this consumer's OTHER slots. Derived from
        # this unit's own bonds and nothing else, so it is local evidence rather
        # than a provider index or a view of topology. Carried separately from
        # `refused`: these suppliers are not blamed, only ineligible HERE.
        excluded = frozenset(b.supplier for s, b in self.bonds.items() if s != slot)
        st["must_differ_from"] = sorted(excluded)
        rnd = st["round"]
        opened = False
        for i, n in enumerate(ring):
            if st["reserve"] < per:
                break
            bid = f"{nid}#r{rnd}b{i}"
            st["reserve"] -= per
            st["allocated"] += per
            st["in_flight"] += per
            st["credits"] = st["reserve"]
            st["branches"][bid] = {"need_id": nid, "round_id": rnd, "branch_id": bid,
                                   "route": n, "allocated_credit": per,
                                   "consumed_credit": 0.0, "refundable_credit": 0.0,
                                   "status": "open"}
            st["outstanding"].add(bid)
            st["tried"].add(n)
            opened = True
            self.outbox.append((n, Need(
                nid, want, self.unit_id, slot, (self.unit_id,),
                self.repair_budget, frozenset(self.refused),
                hops=REPAIR_HOPS, credits=per, must_differ_from=excluded,
                branch_id=bid)))
        if not opened:
            st["no_untried_routes"] = not self._untried_routes(st, want)
        return opened

    def _complete_branch(self, st: dict, bid: str, refund: float) -> None:
        """Close one branch and move its unspent credit back to reserve.

        Guarded on status, so a duplicate or replayed completion -- which happens
        whenever a relay fans one branch into several sub-branches that all die
        -- cannot refund the same allocation twice.
        """
        br = st["branches"].get(bid)
        if br is None or br["status"] != "open":
            return
        alloc = br["allocated_credit"]
        refund = max(0.0, min(refund, alloc))
        br["status"] = "completed"
        br["refundable_credit"] = refund
        br["consumed_credit"] = alloc - refund
        st["in_flight"] -= alloc
        st["consumed"] += alloc - refund
        st["reserve"] += refund
        st["returned"] += refund
        st["credits"] = st["reserve"]
        st["outstanding"].discard(bid)

    def _close_search(self, st: dict) -> None:
        """Release unused reserve explicitly rather than leaving it dangling."""
        st["cancelled"] += st["reserve"]
        st["reserve"] = 0.0
        st["credits"] = 0.0
        st["closed"] = True

    def widen(self, slot: int) -> bool:
        """Widen only when the CURRENT ROUND is fully accounted for.

        Widening on the first acknowledgement to arrive would open a new round
        while earlier branches were still in flight, so rounds would overlap and
        the round bookkeeping would mean nothing. The rule is: every branch
        opened this round has completed, nothing settled, and reserve remains.
        """
        nid = self.open_needs.get(slot)
        st = self._search.get(nid) if nid else None
        if st is None or st["settled"] or st["closed"]:
            return False
        if st["outstanding"] or st["in_flight"] > 1e-9:
            return False                      # the round is not finished
        if st["reserve"] <= 0:
            return False
        st["round"] += 1
        return self._send_to_frontier(slot, nid)

    def _prove_exhaustion(self, slot: int, nid: str) -> bool:
        """A search is exhausted when the SEARCH SPACE is, not when credit is.

        The earlier condition also required `reserve <= 0`, so a finite
        neighbourhood that had been fully searched while credit remained never
        recorded an exhaustion at all: BOUNDED_DISTINCT_REPLACEMENT_EXHAUSTIONS
        stayed at zero and a structurally unsatisfiable episode ended merely as
        "not restored" instead of as a proved bounded escalation.
        """
        st = self._search.get(nid)
        if st is None or st["settled"] or st["closed"]:
            return False
        if st["outstanding"] or st["in_flight"] > 1e-9:
            return False                      # branches still live
        want = self.capability.accepts[slot]
        if self._untried_routes(st, want):
            return False                      # an eligible local route remains
        st["no_untried_routes"] = True
        if st["exhaustion_recorded"]:
            return False
        st["exhaustion_recorded"] = True
        searched = len(st["branches"])
        self._close_search(st)
        self.closed_needs.add(nid)            # late messages suppressed from here
        self.open_needs.pop(slot, None)
        C.incr("BOUNDED_DISTINCT_REPLACEMENT_EXHAUSTIONS")
        self.escalations.append(
            f"no eligible distinct supplier for slot {slot}: "
            f"{searched} branches searched, excluded {st['must_differ_from']}, "
            f"credits consumed {st['consumed']:.1f} returned {st['returned']:.1f} "
            f"cancelled {st['cancelled']:.1f}")
        self.receipts.append(Receipt(
            "branch_exhausted", self.unit_id, slot, None,
            "bounded distinct replacement exhaustion"))
        return True

    def commission_needs(self, budget: float) -> None:
        for slot in self.unmet():
            if slot in self.open_needs:
                continue
            nid = f"{self.unit_id}:{slot}:c"
            self.open_needs[slot] = nid
            need = Need(nid, self.capability.accepts[slot], self.unit_id, slot,
                        (self.unit_id,), budget, frozenset(self.refused),
                        hops=FORMATION_HOPS, credits=FORMATION_CREDITS)
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
            if isinstance(msg, tuple) and msg and msg[0] == "__retired__":
                self.consumers.discard(msg[1])
                continue
            if isinstance(msg, tuple) and msg and msg[0] == "__search__":
                _, key, edge_id, allocation, lineage = msg
                self.deliver_search(key, edge_id, allocation, lineage, sender)
                continue
            if isinstance(msg, Terminal):
                self.deliver_terminal(msg.search_key, msg.edge_id, msg.kind,
                                      msg.refund)
                continue
            if isinstance(msg, tuple) and msg and msg[0] == "__exhausted__":
                nid = msg[1]
                bid = msg[2] if len(msg) > 2 else ""
                refund = msg[3] if len(msg) > 3 else 0.0
                if nid in self.closed_needs:
                    self.late_messages += 1
                    continue
                st = self._search.get(nid)
                if st is not None and bid in st.get("branches", {}):
                    self._complete_branch(st, bid, refund)
                else:
                    # Not mine to account for: pass it back toward the origin so
                    # the requester, not an intermediate, credits the refund.
                    back = self.reverse.get(nid)
                    if back:
                        self.outbox.append((back[0], msg))
                continue
            if isinstance(msg, Need):
                self._on_need(sender, msg)
            elif isinstance(msg, Offer):
                self._on_offer(msg, caps, sender)
        self.inbox.clear()
        # ITERATIVE WIDENING, decided locally and keyed to PROGRESS. Receiving
        # a message is not progress: an offer can be non-firm, stale, in
        # cooldown, prohibited or unsettleable. Widen unless the requirement
        # actually settled.
        for slot in sorted(self.open_needs):
            nid = self.open_needs[slot]
            st = self._search.get(nid)
            if st and not st["settled"] and not st["closed"]:
                if self.widen(slot):
                    break
                self._prove_exhaustion(slot, nid)

    def _report_exhausted(self, sender: str, need: Need) -> None:
        """Tell the immediate requester this branch is dead.

        Every early return here used to drop the need silently, so a search
        whose branches all died reported nothing at all: the origin was never
        woken again, never widened, and ended with unspent credits and no
        explanation. Deduped per unit per need so acknowledgement traffic cannot
        exceed the need traffic that caused it.
        """
        key = (need.need_id, need.branch_id)
        if key in self._exhausted_reported:
            return
        self._exhausted_reported.add(key)
        # The unspent remainder travels home with the acknowledgement so the
        # origin can return it to reserve instead of writing it off.
        self.outbox.append((sender, ("__exhausted__", need.need_id,
                                     need.branch_id, max(0.0, need.credits))))

    def _on_need(self, sender: str, need: Need) -> None:
        if (need.budget <= 0 or need.hops <= 0 or need.credits < 0
                or self.unit_id in need.lineage):
            self._report_exhausted(sender, need)
            return
        if need.need_id in self.closed_needs:
            self.late_messages += 1      # the obligation is already settled
            return
        key = f"{need.need_id}|{need.wanted}"
        if key in self.seen:
            if need.need_id not in self._forwarded:
                self._report_exhausted(sender, need)
            return
        self.seen.add(key)
        self.reverse[need.need_id] = (sender, need.wanted)

        # MATCHING BUT INELIGIBLE IS NOT AN ANSWER, AND NOT A DEAD END.
        #
        # Previously any producer of the wanted type replied and returned. When
        # the only reachable producer was the origin's own sibling supplier, it
        # returned an Offer that `_settle` was always going to refuse as a
        # duplicate, and the branch stopped there. That is the measured cause of
        # 18 of 19 unrestored development episodes: a type-compatible but
        # structurally ineligible candidate consumed the branch as though
        # discovery had succeeded.
        #
        # Such a unit now submits no usable Offer and instead keeps carrying the
        # need outward on the remaining credits, so a genuinely distinct
        # producer beyond it can still be found.
        ineligible = (self.capability.produces == need.wanted
                      and self.unit_id in need.must_differ_from)
        if ineligible:
            C.incr("INELIGIBLE_CANDIDATE_BRANCH_CONTINUATIONS")
            self.receipts.append(Receipt(
                "candidate_ineligible", self.unit_id, need.slot, None,
                "candidate_ineligible_duplicate_supplier", need.origin,
                self.capability.klass()))
        if (self.capability.produces == need.wanted and not self.silent
                and not ineligible):
            mine = self._derives_from()
            if mine & need.refused:
                self.receipts.append(Receipt("withheld", self.unit_id, None, None,
                                             "own derivation is refused"))
                return
            cost = self.capability.cost * self.cost_multiplier
            if cost > need.budget:
                return
            firm = not self.unmet()
            if firm:
                C.incr("DISTINCT_ELIGIBLE_REPLACEMENTS_DISCOVERED")
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
        # A RELAY IS ALSO ROUTED, not broadcast. Bounding only the originating
        # emission left every intermediate unit forwarding to all neighbours,
        # which is where the amplification actually came from: the frontier fix
        # alone moved it 47.65 -> 47.06.
        ring = [n for n in self._frontier(need.wanted) if n != sender]
        if not ring:
            ring = [n for n in sorted(self.neighbours) if n != sender]
        ring = ring[:FRONTIER_WIDTH]
        if not ring or need.credits <= 0:
            # BOUNDED EXHAUSTION, reported rather than silent. A branch that
            # cannot continue tells the requester so, which is what turns "no
            # eligible replacement was found" into an attributable result
            # instead of a stall with unspent credits.
            back = self.reverse.get(need.need_id)
            if back:
                self._report_exhausted(back[0], need)
            return
        # Branching DIVIDES the remaining credit. No path mints credit.
        share = need.credits / len(ring)
        self._forwarded.add(need.need_id)
        for n in ring:
            self.outbox.append((n, dataclasses.replace(
                need, lineage=need.lineage + (self.unit_id,),
                hops=need.hops - 1, credits=share - 1.0)))

    def _derives_from(self) -> frozenset[str]:
        return frozenset({self.unit_id}) | frozenset(
            itertools.chain.from_iterable(b.chain for b in self.bonds.values()))

    def _reply(self, need: Need, firm: bool, cost: float, chain: frozenset[str]) -> None:
        back = self.reverse.get(need.need_id)
        if back:
            self.outbox.append((back[0], Offer(
                need.need_id, self.unit_id, self.capability.klass(),
                self.capability.produces, cost, firm, chain)))

    def _on_offer(self, offer: Offer, caps: dict[str, Capability],
                  via: str = "") -> None:
        """`via` is the IMMEDIATE neighbour that handed me this offer.

        Recording `offer.supplier` instead was the routing defect: the ultimate
        supplier is usually not my neighbour, so `_frontier()` filtered the
        entry out and the useful route through `via` was forgotten.
        """
        if offer.need_id in self.closed_needs:
            self.late_messages += 1
            return
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
        want = self.capability.accepts[slot]
        hop = via if via in self.neighbours else offer.supplier
        ev = self.routes.setdefault(want, {}).setdefault(
            hop, {"offers": 0, "settled": 0, "cost": offer.cost,
                  "supplier": offer.supplier, "firm": 0})
        ev["offers"] += 1
        ev["cost"] = offer.cost
        ev["supplier"] = offer.supplier
        st = self._search.get(offer.need_id)
        if st is not None:
            st["offers"] += 1
        if not offer.firm:
            if st is not None:
                st["rejected"]["nonfirm"] = st["rejected"].get("nonfirm", 0) + 1
            return
        ev["firm"] += 1
        if slot in self.bonds:
            if st is not None:
                st["rejected"]["slot_already_bonded"] = (
                    st["rejected"].get("slot_already_bonded", 0) + 1)
            return
        self._last_refusal = ""
        if self._settle(slot, offer, caps):
            ev["settled"] += 1
            if st is not None:
                st["settled"] = True
            if st is not None and st.get("must_differ_from"):
                C.incr("DISTINCT_ELIGIBLE_REPLACEMENTS_SETTLED")
            # POST-CONDITION on the property the whole guard exists to protect.
            # Counted here, at the only place a bond is created, so a regression
            # cannot pass by being invisible.
            sups = [b.supplier for b in self.bonds.values()]
            if len(sups) != len(set(sups)):
                C.incr("INDEPENDENCE_VIOLATIONS")
        elif st is not None:
            why = self._last_refusal or "unrecorded_refusal"
            st["rejected"][why] = st["rejected"].get(why, 0) + 1

    def _settle(self, slot: int, offer: Offer, caps: dict[str, Capability]) -> bool:
        """Sets `_last_refusal` on every rejecting path.

        Only `nonfirm`, `stale` and `cooldown` were ever recorded, so an offer
        refused for type, duplicate supplier or prohibition showed up in the
        taxonomy as `offers=1, rejected={}` -- counted as received and then
        silently dropped, with no way to tell which of four paths took it.
        Reasons only; no control flow is changed.
        """
        if offer.offered_type != self.capability.accepts[slot]:
            self._last_refusal = "type_mismatch"
            return False
        if any(b.supplier == offer.supplier for b in self.bonds.values()):
            self._last_refusal = "duplicate_supplier"
            return False
        if offer.chain & self.refused:
            self.stale_rejections += 1
            C.incr("STALE_DERIVATIONS_REJECTED")
            self.receipts.append(Receipt("stale_rejected", self.unit_id, slot,
                                         STALE_RETURN, "offer derivation refused",
                                         offer.supplier, offer.supplier_class))
            self._last_refusal = "stale"
            return False
        if not self.memory.admits(offer.supplier):
            self.receipts.append(Receipt("cooldown", self.unit_id, slot,
                                         COOLDOWN_RETURN, "supplier cooling down",
                                         offer.supplier, offer.supplier_class))
            self._last_refusal = "cooldown"
            return False
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
                self._last_refusal = "prohibited"
                return False
        closed = self.open_needs.pop(slot, None)
        self.bonds[slot] = Bond(slot, offer.supplier, offer.supplier_class,
                                offer.offered_type, offer.cost, offer.chain,
                                settled_by=closed or "", settled_item=self.item_seq)
        if closed:
            # NEED-GENERATION CLOSURE. The obligation is satisfied; later needs
            # and offers for this generation are discarded rather than
            # circulating and reopening the same slot from another route.
            self.closed_needs.add(closed)
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
        # A SUCCESSFUL SETTLEMENT MUST SAY SO. Without this the function created
        # the bond and then fell off the end returning None, so every caller took
        # the failure branch. Consequences, all silent:
        #
        #   - st["settled"] was never set, so a search that had already succeeded
        #     kept widening and spending credit;
        #   - ev["settled"] was never incremented, so `_frontier()`'s evidence
        #     list (settled > 0) was permanently empty and route memory never
        #     learned which neighbour actually worked;
        #   - the independence post-condition at the settlement site never ran,
        #     so INDEPENDENCE_VIOLATIONS reading zero proved nothing there;
        #   - DISTINCT_ELIGIBLE_REPLACEMENTS_SETTLED could never fire;
        #   - each success was recorded as an "unrecorded_refusal", corrupting
        #     the refusal taxonomy with one bogus entry per settlement.
        return True


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
        # SINGLE-FLIGHT telemetry, keyed by EDGE ID with explicit fields. Keying
        # by (from, to, SearchKey) while nodes stored an edge identifier meant the
        # two identities were compared by tuple membership, which proved nothing.
        self.search_edges: dict = {}
        self.search_edge_probes: dict = {}
        self.search_edge_terminals: dict = {}
        self.space_exhaustion_proofs: list = []
        self.budget_exhaustion_records: list = []
        for u in self.units.values():
            u._organ = self
        # Recipients that hold undelivered work. Maintained as messages are
        # delivered, so run_item never scans the organ to find them.
        self._msg_pending: set = set()
        # Last observed readiness per unit, for edge-triggered scheduling.
        self._unmet_state: dict = {}
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
                    # Consumed. It is no longer pending, and must not seed a
                    # later work item as if it still held undelivered work.
                    self._msg_pending.discard(u.unit_id)
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
        self.item_seq = getattr(self, "item_seq", 0) + 1
        self.events_dispatched = 0
        self.ready: deque = deque()
        self._queued: set = set()
        self._unmet_state = {uid: bool(u.unmet()) for uid, u in self.units.items()}
        self.suppressed_late: int = 0
        self.suppressed_duplicates: int = 0

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
            if u is None:
                continue
            if u.dissolved:
                # This unit will never produce, so its consumers would never be
                # woken by a delivery and a single-input consumer would never
                # discover the break. The dead unit's OWN consumer registry -
                # local data it already holds, one hop - routes the failure to
                # exactly the units that depend on it. This is not a scan and
                # not a heartbeat.
                for c in sorted(u.consumers):
                    self._schedule(c, "supplier_failed")
                continue
            self.events_dispatched += 1
            u.item_seq = self.item_seq     # provenance stamp, one unit, no scan
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
            if dest not in self.units:
                continue
            if isinstance(msg, tuple) and msg and msg[0] == "__retired__":
                # Bookkeeping, not work: a retirement must land even on a
                # supplier that is gone or unreachable, or its stale consumer
                # registry keeps waking a consumer it no longer serves.
                self.units[dest].consumers.discard(msg[1])
                continue
            if (not self.units[dest].dissolved
                    and not self.is_cut(u.unit_id, dest)):
                self.units[dest].inbox.append((u.unit_id, msg))
                self.messages += 1
                self._msg_pending.add(dest)
                self._schedule(dest, "message")
        u.outbox.clear()
        # EDGE-TRIGGERED. Schedule only on the TRANSITION from unmet to
        # satisfied. Scheduling whenever a unit merely "is fully bonded and has
        # not produced" is level-triggered: a unit whose pull returns NotYet
        # returns without producing and is immediately requeued, spinning until
        # max_events. Episode 0 of the development cohort hit exactly 3000.
        if u.unit_id != ENV and u.slots():
            was_unmet = self._unmet_state.get(u.unit_id, True)
            now_unmet = bool(u.unmet())
            self._unmet_state[u.unit_id] = now_unmet
            if was_unmet and not now_unmet and u.unit_id not in self._produced:
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

    def _probe_current_result(self, payload: Any) -> Optional[Value]:
        """EVALUATOR PROBE. Can the CURRENT structure still yield a result?

        Runs a work item with every repair budget set to zero, so no unit can
        reopen: it measures what the damaged structure produces WITHOUT repair.
        Used only to prove pre-repair semantic loss. It cannot trigger repair,
        and it restores all budgets and clears the escalations it caused.
        """
        saved = {u.unit_id: u.repair_budget for u in self.units.values()}
        esc = {u.unit_id: list(u.escalations) for u in self.units.values()}
        for u in self.units.values():
            u.repair_budget = 0.0
        try:
            return self.run_item(payload)
        finally:
            for u in self.units.values():
                u.repair_budget = saved[u.unit_id]
                u.escalations[:] = esc[u.unit_id]

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
    """CONTAINER ARITHMETIC ONLY - not evidence of grounded instrumentation.

    This increments every counter by hand. It proves the container works. It
    proves nothing about whether the measured behaviour reaches the counter;
    only the behaviour-site tests do that.
    """
    before = C.snapshot()
    for name in COUNTER_NAMES:
        C.incr(name)
    after = C.snapshot()
    for name in COUNTER_NAMES:
        C.incr(name, -1)
    return {n: after[n] - before[n] for n in COUNTER_NAMES}
