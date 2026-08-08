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

STATED PLAINLY, because a counter with no reachable increment is a claim rather
than a measurement. Of the Single-Flight V2 counters, these are incremented on a
path this commit can and does execute:

    UNIQUE_CANONICAL_SEARCH_NODES     CANONICAL_SEARCH_EXPANSIONS
    COALESCED_DUPLICATE_ARRIVALS      CYCLE_EDGES_CLOSED
    DIRECTED_SEARCH_EDGES_PROBED      TERMINAL_ECHOS_SENT
    SEARCH_SPACE_EXHAUSTED            SEARCH_BUDGET_EXHAUSTED
    UNIQUE_PROPOSAL_IDS_RECEIVED      UNIQUE_PROPOSAL_DECISIONS
    SEARCH_OFFER_SETTLEMENT_REJECTIONS
    REPAIR_REOPENS                    LEGACY_REPAIR_NEED_MESSAGES

These are wired at their real decision sites and CANNOT fire until the live
repair path is migrated, because nothing yet creates a canonical root during a
live run:

    REPAIR_REOPENS_WITH_CANONICAL_ROOT     DUAL_REPAIR_SEARCHES

And these are violation detectors: they are incremented only where the defect
they name would occur, so a correct run leaves them at zero by construction:

    DUPLICATE_SUBTREES_OPENED         OFFER_RETURN_ROUTE_MISMATCHES
    ORPHANED_SEARCH_EDGES             PREMATURE_TERMINATION_SIGNALS
    PREMATURE_PROPOSAL_CANCELLATIONS  LEGACY_PROJECTION_DECISION_READS

`LEGACY_PROJECTION_DECISION_READS` is driven by `Organ.read_legacy_projection`,
an instrumented name for the prohibited operation, in the same style as
`_scan_all_units` and `providers_of`. Nothing in the runtime calls it.
"""
from __future__ import annotations

import dataclasses
import hashlib
import itertools
import json
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Literal, Optional

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
    # Proposal/commit handshake (protocol V2). A proposal is EVIDENCE of a
    # candidate, never a terminal transport outcome and never proof of
    # restoration, so these are counted apart from the terminal counters above.
    "PREMATURE_PROPOSAL_CANCELLATIONS",
    "UNIQUE_PROPOSAL_IDS_RECEIVED",
    "UNIQUE_PROPOSAL_DECISIONS",
    "SEARCH_OFFER_SETTLEMENT_REJECTIONS",
    # Live repair path. REPAIR_REOPENS is grounded now, at the one site that
    # reopens an obligation. The three below describe the migration Commit 3
    # performs; they are defined and wired at their real decision sites so the
    # requirement is executable rather than aspirational.
    "REPAIR_REOPENS",
    "REPAIR_REOPENS_WITH_CANONICAL_ROOT",
    "LEGACY_REPAIR_NEED_MESSAGES",
    "DUAL_REPAIR_SEARCHES",
    "LEGACY_PROJECTION_DECISION_READS",
    # 2A: provenance, rejection continuation and distributed credit
    # conservation. A derived proposal id proves the evidence was not altered;
    # it says nothing about who delivered it or over which edge, and a ledger
    # that balances locally can still record a false distributed history.
    "UNOWNED_PROPOSAL_ROUTES",
    "CONTEXTLESS_CANONICAL_NODES",
    "STRANDED_REJECTED_PROPOSALS",
    "UNSUPPORTED_CHILD_CANCELLATION_CREDIT",
    "REJECTED_PROPOSALS_TOTAL",
    "REJECTED_PROPOSALS_RESOLVED",
    "UNAUTHENTICATED_PROPOSAL_DELIVERIES",
    # 2B: the CONTROL plane. Binding the data plane while leaving rejection,
    # acknowledgement and terminal controls unbound restores route forgery
    # through a different door -- suppression of a valid candidate, closure of
    # another child's allocation, forged wave closure.
    "UNAUTHENTICATED_REJECTION_CONTROLS",
    "UNAUTHENTICATED_SEARCH_ACKS",
    "UNAUTHENTICATED_TERMINAL_CONTROLS",
    "MALFORMED_SEARCH_ACKS",
    # 2D SEAM. Defined here and driven by 2D-runtime. A counter that exists
    # before the gate it measures lets the specification name the gate without
    # the specification itself creating one.
    "UNAUTHENTICATED_SEARCH_DELIVERIES",
    "MALFORMED_SEARCH_DELIVERIES",
    "UNKNOWN_EDGE_TERMINAL_EMISSIONS",
    "COMMIT_OF_RESOLVED_PROPOSAL",
    "UNDISPOSITIONED_LOCAL_PROPOSALS",
    "HARNESS_DELIVERIES_USED",
    "TOTAL_CANONICAL_SEARCH_ADOPTIONS",
    "AUTHENTICATED_SEARCH_ADOPTIONS",
    # 2C: fail-closed identity, semantically valid controls, sealed lifecycle.
    "MALFORMED_TERMINAL_EVIDENCE",
    "UNKNOWN_COMMIT_PROPOSALS",
    "LATE_CONTROLS_AFTER_CLOSURE",
    "UNAUTHENTICATED_TERMINAL_EMISSIONS",
    # Commit 3: the root ORIGINATOR. `CANONICAL_ROOTS_CREATED` is the numerator
    # the migration was missing; the rest are its accounting and its violation
    # detectors.
    "CANONICAL_ROOTS_CREATED",
    "DUPLICATE_CANONICAL_ROOTS",
    "ROOT_CONTEXT_REFUSALS",
    "SEARCH_CREDIT_ISSUED",
    "SEARCH_CREDIT_IN_FLIGHT",
    "PROPOSALS_RETURNED_TO_ROOT",
    "ELIGIBLE_PROPOSALS_COMMITTED",
    # Forbidden-operation detectors for origination. Incremented only where the
    # named defect would occur, so a correct run leaves them at zero. Two of
    # them -- the provider index and the supervisor restart -- name operations
    # the design forbids outright, in the same style as `_scan_all_units`.
    # `TARGET_TOPOLOGY_LEAKAGE_EVENTS` and `UNAUTHORIZED_EXTERNAL_EFFECTS` are
    # NOT redefined here: they already exist above and origination reuses them
    # rather than minting a second counter for one property.
    "GLOBAL_PROVIDER_INDEX_READS",
    "SOLUTION_LEAKAGE_EVENTS",
    "INHERITED_AUTHORITY_EVENTS",
    # Commit 5: proof-closed terminality. A child edge closed against the
    # outcome the organ already records, rather than against a message that
    # can never arrive.
    "CHILD_EDGES_RECONCILED_FROM_EVIDENCE",
    "TERMINALS_WITH_UNRECONCILED_CHILDREN",
    "SEARCH_CONTROLS_RECORDED",
    "CLOSED_CHILD_EDGES",
    "CLOSED_CHILD_EDGES_WITH_ACCEPTED_CHILD_OUTCOME",
    "CLOSED_CHILD_EDGES_WITHOUT_CHILD_EVIDENCE",
    "PARENT_CONTROLS_RECORDED_AS_CHILD_OUTCOMES",
    "OUTCOME_SLOT_OCCUPIED_BY_CONTROL",
    # 5L: a Terminal the sender-created probe cannot place in either channel.
    # Failing closed is the point -- an unplaceable message must not choose its
    # own channel by choosing a kind.
    "UNCLASSIFIABLE_TERMINAL_RECORDINGS",
    "DUPLICATE_TERMINAL_RESOLUTIONS",
    # Commit 5I: child-owned command completion.
    "PARENT_CONTROLS_APPLIED",
    "PARENT_CONTROLS_WITH_CHILD_OWNED_COMPLETION",
    "CLOSED_NODES_WITH_CHILDREN_OUTSTANDING",
    "DUPLICATE_CONTROL_APPLICATIONS",
    "PREMATURE_CONTROL_COMPLETION_OUTCOMES",
    "COALESCED_INBOUND_EDGES",
    "COALESCED_INBOUND_EDGES_CLOSED_SEPARATELY",
    # PA-3: authenticated receiver-side arrival is a distinct fact from the
    # sender having emitted a parent control into the shared lifecycle record.
    "PREARRIVAL_CONTROLS_HELD",
    "PREARRIVAL_CONTROLS_APPLIED",
    "PREARRIVAL_CONTROL_REPLAYS",
    "PREARRIVAL_CONTROL_CONFLICTS",
    # NC-3: causal need closure. A root whose obligation generation was retired
    # -- satisfied through some other path -- can never settle anything again,
    # because `settle_search_offer` refuses it with `wrong_need_generation`.
    # Until this existed the root was ABANDONED rather than closed: it kept its
    # descendants waiting on a decision that would never be made, and kept its
    # parent's committed credit permanently in flight.
    #
    # THE DENOMINATOR IS FIRST. A closure ratio whose denominator can be zero
    # proves nothing, and every counter below is read against this one.
    "ALTERNATE_SATISFIED_OPEN_ROOTS",
    "NEED_CLOSURE_CASCADES_INITIATED",
    "NEED_CLOSURE_CONTROLS_EMITTED",
    "ROOTS_CLOSED_BY_ALTERNATE_SATISFACTION",
    "DUPLICATE_NEED_CLOSURE_APPLICATIONS",
    "FALSE_NEED_CLOSURE_CLAIMS",
)

# A wave-closing command travels DOWN, from the adopted parent. A search outcome
# travels UP, from a child. `SearchNeedClosed` is legitimately either: a parent
# closing the wave, or a child reporting that its own need generation is closed.
PARENT_CONTROL_KINDS = ("SearchCommitted", "SearchCancelled", "SearchNeedClosed")
CHILD_OUTCOME_KINDS = ("SearchExhausted", "SearchBudgetExhausted",
                       "SearchCompleted",
                       "SearchCoalesced", "SearchCycleClosed",
                       "SearchContextRejected", "SearchNeedClosed")

ControlRecordResult = Literal["accepted", "replay", "conflict"]


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
    # True only when the bond was created by resolving a SearchOfferPayload
    # through the canonical Single-Flight path, so a settlement that came from
    # the legacy Need/Offer path cannot be reported as one that did not.
    settled_from_search_offer: bool = False


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


def _canon(obj: Any) -> str:
    """CANONICAL SERIALIZATION. One value, exactly one string, every process.

    Everything that carries institutional identity here -- a search context, a
    proposal -- is identified by a SHA-256 over this form. Three properties are
    load-bearing and none of them is offered by `repr()`, `str()` or `hash()`:

      * TYPE TAGGING. `1`, `1.0`, `"1"` and `True` serialize differently, so a
        relay cannot swap a field's type and keep the digest.
      * ORDER INDEPENDENCE FOR SETS ONLY. Sets sort; tuples and lists keep their
        order, because `policy_snapshot` is an ordered record and reordering it
        is a change.
      * ESCAPING. The separators are escaped inside strings, so
        `{"a;b"}` and `{"a", "b"}` cannot collide.

    Python's `hash()` is never used. It is randomized per process for str, so
    one semantic object would carry different identities between runs, and it is
    64-bit, so it is not collision-resistant against a hostile relay.
    """
    if obj is None:
        return "n:"
    if isinstance(obj, bool):                    # BEFORE int: bool IS an int
        return f"b:{int(obj)}"
    if isinstance(obj, int):
        return f"i:{obj}"
    if isinstance(obj, float):
        return f"f:{obj!r}"
    if isinstance(obj, str):
        return "s:" + obj.replace("\\", "\\\\").replace(";", "\\;").replace(
            "=", "\\=")
    if isinstance(obj, (frozenset, set)):
        return "S[" + ";".join(sorted(_canon(x) for x in obj)) + "]"
    if isinstance(obj, (tuple, list)):
        return "L[" + ";".join(_canon(x) for x in obj) + "]"
    if isinstance(obj, dict):
        return "D[" + ";".join(f"{_canon(k)}={_canon(obj[k])}"
                               for k in sorted(obj)) + "]"
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return ("O:" + type(obj).__name__ + "[" + ";".join(
            f"{f.name}={_canon(getattr(obj, f.name))}"
            for f in dataclasses.fields(obj)) + "]")
    raise TypeError(f"no canonical form for {type(obj).__name__}; add one "
                    f"rather than letting an unhashable field travel unbound")


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SearchContext:
    """Every field a REMOTE candidate needs to decide its own eligibility.

    V1 bound only the refusal and must-differ digests into `SearchKey`, while the
    context also carried a cost ceiling and a cooldown set. A relay could
    therefore alter either while keeping the same `SearchKey` -- an unenforced
    constraint wearing a valid identity. `context_digest()` covers all six
    fields, and `matches()` verifies the COMPLETE context rather than two of it.

    `origin_independence_evidence` is deliberately ABSENT. A remote candidate
    cannot evaluate domain independence or prohibited motifs more correctly than
    the origin -- `_settle` computes those from origin-local capabilities at
    commit time, which is the only place the answer is current -- and shipping
    the origin's occupied supplier domains to every reachable candidate is
    exactly the disclosure `TARGET_TOPOLOGY_LEAKAGE_EVENTS` exists to forbid.
    """
    causally_refused_sources: frozenset = frozenset()
    must_differ_from_suppliers: frozenset = frozenset()
    maximum_supplier_cost: float = float("inf")
    cooldown_excluded_suppliers: frozenset = frozenset()
    constraint_generation: int = 0
    policy_snapshot: tuple = ()

    def context_digest(self) -> str:
        return _sha256(_canon([
            "SearchContext/v2",
            frozenset(self.causally_refused_sources),
            frozenset(self.must_differ_from_suppliers),
            float(self.maximum_supplier_cost),
            frozenset(self.cooldown_excluded_suppliers),
            int(self.constraint_generation),
            tuple(self.policy_snapshot),
        ]))

    def matches(self, key: "SearchKey") -> bool:
        """The COMPLETE context, not two of its fields."""
        if not isinstance(key, SearchKey):
            return False
        return (key.context_digest == self.context_digest()
                and key.causal_refusal_digest
                == _digest(self.causally_refused_sources)
                and key.must_differ_from_digest
                == _digest(self.must_differ_from_suppliers)
                and key.constraint_generation == int(self.constraint_generation))


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
    # ONE digest over the COMPLETE SearchContext. The two digests above are
    # retained because they name the two constraints individually and existing
    # direct-seam callers construct keys from them; neither is sufficient on its
    # own, and only this field is checked by `SearchContext.matches`.
    context_digest: str = ""

    @staticmethod
    def build(*, need_id, work_item_generation, origin_unit, origin_slot,
              wanted_type, context: SearchContext) -> "SearchKey":
        """The ONLY key constructor. There is no partial form.

        A `build` that accepted a bare refusal set and a bare must-differ set
        produced keys whose identity omitted the cost ceiling, the cooldown set
        and the policy snapshot -- so a relay could change any of those and keep
        a valid-looking identity. Requiring the whole context here is what makes
        that impossible to express.
        """
        if not isinstance(context, SearchContext):
            raise TypeError(
                "SearchKey.build requires a complete SearchContext; a partial "
                "constructor would mint identities that do not bind every "
                "enforcement field")
        return SearchKey(need_id, work_item_generation, origin_unit, origin_slot,
                         wanted_type,
                         _digest(context.causally_refused_sources),
                         _digest(context.must_differ_from_suppliers),
                         int(context.constraint_generation),
                         context.context_digest())

    def __str__(self) -> str:
        return (f"{self.origin_unit}[{self.origin_slot}]:{self.wanted_type}"
                f"@{self.work_item_generation}/{self.need_id}")


PROPOSAL_ID_PREFIX = "sfp1:"

# "no immediate sender was supplied", distinguished from the empty string, which
# is a claim that the sender is nobody. A delivery without a sender cannot be
# authenticated, so it is counted rather than quietly trusted.
_UNSPECIFIED_SENDER = object()


class _HarnessDelivery:
    """An EXPLICIT capability to bypass transport authentication.

    A test that drives a control handler directly has no transport and therefore
    no immediate sender. It must still say so deliberately: an omitted argument
    is not authority, and reading absence as trust is how every one of these
    gates fails open. Production code has no reason to construct this, and every
    use is counted.
    """
    __slots__ = ()

    def __repr__(self) -> str:
        return "HARNESS_DELIVERY"


HARNESS_DELIVERY = _HarnessDelivery()


def _authenticated(sender: Any, expected: Any) -> bool:
    """True only for a present identity that matches, or the harness capability.

    Missing identity is REFUSED. `Unit.step` always supplies a sender, so this
    closes a fail-open entrypoint rather than changing live behaviour.
    """
    if sender is HARNESS_DELIVERY:
        C.incr("UNAUTHENTICATED_PROPOSAL_DELIVERIES")
        return True
    return sender is not _UNSPECIFIED_SENDER and sender == expected


def _evidence_reconciles(refund: float, consumed: float, per: float) -> bool:
    """One standard of raw closure evidence, whichever door it arrives through.

    NaN is the sharpest case: every comparison against it is false, so an
    unguarded check passes it straight through and it poisons the ledger
    silently.
    """
    try:
        if not math.isfinite(refund) or not math.isfinite(consumed):
            return False
    except TypeError:
        return False
    return refund >= 0.0 and consumed >= 0.0 and abs(refund + consumed - per) <= 1e-6


@dataclass(frozen=True)
class SearchOfferPayload:
    """A candidate's complete evidence, carried by a SearchProposal.

    PROPOSAL IDENTITY IS DERIVED, NOT DECLARED. `proposal_id` is recomputed in
    `__post_init__` as `sha256(canonical(every immutable field))`, so a relay
    cannot alter `firm`, `supplier_class`, `context_digest`, `source_node`, the
    derivation chain, the cost or the source edge and keep the same identity:
    changing any of them changes the id, and an unchanged id that no longer
    matches its own content is caught by `identity_intact()` at every hop.

    The value passed in as `proposal_id` is kept as `supplied_label` for
    provenance. It is a caller's name for the proposal; it carries no authority
    and it is NOT part of the digest, because two arrivals with identical
    evidence are the same proposal and must resolve exactly once no matter what
    a relay chooses to call them.
    """
    proposal_id: str
    search_key: SearchKey
    context_digest: str
    supplier: str
    supplier_class: str
    offered_type: str
    cost: float
    firm: bool
    derivation_chain: frozenset
    source_node: str
    source_edge_id: str
    supplied_label: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "supplied_label",
                           self.supplied_label or str(self.proposal_id))
        object.__setattr__(self, "proposal_id", self.derived_id())

    def _immutable_form(self) -> list:
        """Every field a hop is forbidden to change. `supplied_label` is not
        here: it is provenance, not evidence."""
        return ["SearchOfferPayload/v2",
                self.search_key,
                self.context_digest,
                self.supplier,
                self.supplier_class,
                self.offered_type,
                float(self.cost),
                bool(self.firm),
                frozenset(self.derivation_chain),
                self.source_node,
                self.source_edge_id]

    def derived_id(self) -> str:
        return PROPOSAL_ID_PREFIX + _sha256(_canon(self._immutable_form()))

    def identity_intact(self) -> bool:
        return self.proposal_id == self.derived_id()


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
    reason: str = ""
    proposal_id: str = ""
    # Always None on a terminal. A proposal is not a terminal outcome, so a
    # terminal never carries one; the field exists so every outcome object
    # answers `.payload` uniformly.
    payload: Optional[SearchOfferPayload] = None


@dataclass(frozen=True)
class SearchEvent:
    """A NONTERMINAL edge event: a proposal, or a control record.

    Stored in `Organ.search_edge_events`, never in `Organ.search_edge_terminals`.
    V1 treated a candidate offer as a terminal success, which made a node go
    ANSWERED and cancel its siblings on a mere proposal -- the premature
    cancellation defect. The two stores are separate so that confusion cannot be
    expressed.
    """
    kind: str
    search_key: SearchKey
    edge_id: str
    reason: str = ""
    payload: Optional[SearchOfferPayload] = None
    from_unit: str = ""
    to_unit: str = ""
    proposal_id: str = ""

    @property
    def refund(self) -> float:
        return 0.0


TERMINAL_KINDS = ("SearchCommitted", "SearchExhausted", "SearchBudgetExhausted",
                  "SearchCoalesced", "SearchCycleClosed", "SearchContextRejected",
                  "SearchNeedClosed", "SearchCancelled")

NONTERMINAL_KINDS = ("SearchProposal", "SearchProposalAccepted",
                     "SearchProposalRejected", "SearchPending")


def new_canonical_node(key: SearchKey, parent_edge: str, parent_sender: str,
                       allocation: float, context: Optional[SearchContext] = None,
                       lineage: tuple = ()) -> dict:
    """One canonical local computation per (unit, SearchKey).

    The adopted parent fields are immutable after first adoption: a later arrival
    must never redirect where a result travels home. `reverse[need_id]` allowed
    exactly that, because a second arrival overwrote the earlier return route.

    CREDIT ROLES ARE SEPARATE. The state invariant is

        incoming_allocation == local_reserve
                             + child_allocations_in_flight
                             + consumed_credit
                             + cancelled_credit
                             + returned_to_parent

    `child_refunds_received` (and its legacy alias `returned_credit`) is
    CUMULATIVE AUDIT telemetry and appears in no balance: a refunded child
    allocation is transferred INTO `local_reserve`, so adding both would count
    the same credit twice. `handling_cost` is likewise outside the balance --
    it is charged against a DUPLICATE arrival's own allocation, which belongs to
    the sender's ledger and is never pooled into this node's reserve.
    """
    return {
        "search_key": key,
        # The context this search actually travelled with. A node cannot build a
        # proposal against constraints it does not hold, and a digest alone
        # cannot be checked against anything.
        "search_context": context,
        "status": "OPEN",
        "wave_cancelled": False,
        "adopted_parent_edge": parent_edge,
        "adopted_parent_edge_initial": parent_edge,
        "adopted_parent_sender": parent_sender,
        # Accumulated path, so A -> B -> C -> A arrives back at A carrying
        # (A, B, C) and a real cycle can be proved as one. Sending only
        # `(self.unit_id,)` reset the path at every hop.
        "lineage": tuple(lineage),
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
        "child_allocations": {},        # child edge -> credit committed to it
        "child_targets": {},            # child edge -> neighbour, LOCAL routing
        "child_allocations_in_flight": 0.0,
        "child_refunds_received": 0.0,
        "returned_credit": 0.0,         # legacy alias of child_refunds_received
        "consumed_credit": 0.0,
        "cancelled_credit": 0.0,
        "returned_to_parent": 0.0,
        "eligible_offer": False,
        "local_candidate": None,
        # Expansion rounds are numbered, and child edge ids carry the number, so
        # a second widening cannot reuse /c0 and /c1 for different routes.
        "round": 0,
        "expansion_round": 0,
        "child_sequence": 0,
        "computed": False,
        # proposal_id -> child edge it arrived on. This is how a commit follows
        # the accepted path while every other branch is cancelled, and how
        # rejection feedback returns to the actual proposer.
        "proposal_routes": {},
        "proposal_digests": {},
        "proposal_payloads": {},
        "proposals_outstanding": set(),
        "proposals_rejected": set(),
        "accepted_proposal_id": None,
        "terminal_signal_sent": False,
        # NC-3. Why closure began, bound to the exact obligation generation.
        # Declared here rather than set on demand so a reader can always ask,
        # and so an abandoned root stays attributable to its cause AFTER it
        # closes -- abandonment is a fact about history, not about live state.
        "closure_reason": None,
        "closure_need_id": None,
        "closure_generation": None,
        # What each child CONFIRMED about the allocation it was given:
        # child edge -> (refund, consumed). A parent may close an allocation only
        # from this. Writing a transferred allocation off as cancelled without an
        # entry here records a second, incompatible history of the same credit.
        "child_confirmed": {},
        "ack_sent": False,
        # What became of each proposal once the wave closed: accepted, rejected,
        # cancelled or need_closed. A proposal left merely "outstanding" on a
        # closed node is an obligation nobody will ever answer.
        "proposal_disposition": {},
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
    # EXACTLY-ONCE PROPOSAL RESOLUTION, keyed by the derived proposal_id:
    # proposal_id -> the decision that was made. A replayed proposal returns the
    # stored decision and makes no second decision, no second bond, no second
    # rejection count and no second terminal.
    _proposal_decisions: dict = field(default_factory=dict)
    # Precondition refusals already reported, so a replayed unsettleable payload
    # does not grow telemetry without bound.
    _proposal_preconditions: set = field(default_factory=set)
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
        # THE one site at which an obligation is reopened for repair. Counted
        # here so the migration requirement -- every reopen creates a canonical
        # root -- has a real denominator rather than an asserted one.
        C.incr("REPAIR_REOPENS")
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

    # -- SINGLE-FLIGHT ECHO SEARCH, protocol V2 ------------------------
    #
    # One canonical local computation per (unit, SearchKey). A later arrival
    # carrying the same semantic search registers, refunds and terminates; it
    # never opens another subtree. That is the whole correction over the failed
    # hierarchical tree, which opened a fresh subtree per transport path.
    #
    # V2 adds the proposal/commit handshake. A candidate is EVIDENCE, not a
    # terminal outcome: the origin may refuse it for duplicate supplier, stale
    # derivation, cooldown, a prohibited motif, changed slot state or a race
    # with another candidate. So a proposal never terminates an edge, never
    # marks a node ANSWERED and never cancels siblings. Only an accepted
    # settlement closes the wave.

    # -- edge telemetry ------------------------------------------------
    #
    # CREATION AND DELIVERY ARE DIFFERENT FACTS. The sender counts an edge once,
    # when it creates it; the receiver counts a delivery. Counting both as
    # probes gave every live edge count == 2 and broke the per-edge uniqueness
    # invariant, while the direct-seam tests missed it because they call the
    # receiver themselves.

    def _edge_record(self, edge_id: str, frm: str, to: str, key: SearchKey,
                     allocation: Optional[float] = None):
        o = self._organ
        if o is None:
            return None
        rec = o.search_edge_probes.get(edge_id)
        if rec is None:
            rec = {"from_unit": frm, "to_unit": to, "search_key": key,
                   "count": 0, "delivered": 0, "allocation": 0.0}
            o.search_edge_probes[edge_id] = rec
        rec.setdefault("allocation", 0.0)
        o.search_edges.setdefault(edge_id, {
            "edge_id": edge_id, "parent_edge_id": "", "from_unit": frm,
            "to_unit": to, "search_key": key, "allocation": 0.0,
            "terminal_status": "open", "terminal_outcome": None,
            "refunded_credit": 0.0, "consumed_credit": 0.0})
        return rec

    def _record_probe(self, edge_id: str, frm: str, to: str, key: SearchKey,
                      allocation: Optional[float] = None) -> None:
        """CREATION. Called by the sender, exactly once per directed edge.

        The sender records the ALLOCATION it committed, so a receiver has
        something to check an arriving amount against. `allocation` is optional
        during this seam commit so existing callers keep working; 2D-runtime
        makes the check mandatory.
        """
        rec = self._edge_record(edge_id, frm, to, key, allocation)
        if rec is None:
            return
        rec["count"] += 1
        if allocation is not None:
            rec["allocation"] = allocation
            e = self._organ.search_edges.get(edge_id) if self._organ else None
            if e is not None:
                e["allocation"] = allocation
        C.incr("DIRECTED_SEARCH_EDGES_PROBED")

    def _record_delivery(self, edge_id: str, frm: str, to: str, key: SearchKey) -> None:
        """ARRIVAL. Recorded in its own field so it is never mistaken for a
        second creation of the same edge."""
        rec = self._edge_record(edge_id, frm, to, key)
        if rec is None:
            return
        rec["delivered"] += 1

    def _lifecycle_record(self, t: Terminal) -> dict:
        """ONE record per edge, with two semantically distinct channels.

        Not two registries: two registries would recreate the same ambiguity in
        a new place. One record, in which a COMMAND and an OUTCOME are separately
        addressable facts.
        """
        o = self._organ
        rec = o.search_edge_lifecycle.get(t.edge_id)
        if rec is None:
            rec = {"from_unit": t.from_unit, "to_unit": t.to_unit,
                   "search_key": t.search_key,
                   "controls": [], "accepted_control": None,
                   "prearrival_control_state": None,
                   "outcomes": [], "accepted_outcome": None,
                   "control_conflicts": [], "outcome_conflicts": []}
            o.search_edge_lifecycle[t.edge_id] = rec
        else:
            # Records created before PA-3 remain readable without a migration:
            # the absent field means no receiver-side pre-arrival delivery.
            rec.setdefault("prearrival_control_state", None)
        return rec

    def _record_control(self, t: Terminal) -> ControlRecordResult:
        """A COMMAND: what the opener REQUESTED. Never proof it happened.

        Authentication proves who asked for the transition. It says nothing
        about whether the transition completed, and the unit that asked is
        exactly the unit that must not be allowed to answer. So a control is
        recorded, is idempotent under exact replay, files a contradicting
        second command as a conflict -- and closes nothing. It does not touch
        `terminal_status`, `terminal_outcome`, `refunded_credit` or
        `consumed_credit`, and it does not discharge a child allocation.
        """
        o = self._organ
        if o is None:
            return "replay"                   # no shared store: inert
        rec = self._lifecycle_record(t)
        first = rec["accepted_control"]
        if first is not None:
            if first == t:
                return "replay"               # exact FULL replay: inert
            # One fingerprint is enough to prove the accepted command met a
            # contradiction. Further hostile variants are counted at the
            # receiver but retain no more attacker-controlled objects.
            fingerprint = _sha256(_canon(t))
            if not rec["control_conflicts"]:
                rec["control_conflicts"].append(fingerprint)
            if not any(x[0] == t.edge_id for x in
                       o.search_edge_terminal_conflicts):
                o.search_edge_terminal_conflicts.append(
                    (t.edge_id, _sha256(_canon(first)), fingerprint))
            return "conflict"
        rec["controls"].append(t)
        rec["accepted_control"] = t
        # NO PROJECTION WRITE. A command is visible through `accepted_control`
        # and nowhere else.
        #
        # The projection write existed to keep readers working that asked
        # `search_edge_terminals` "did the opener command this edge". Those
        # readers were the problem: the store's own name and its other
        # consumers say OUTCOMES, so writing commands into it made a command
        # indistinguishable from an answer to anything reading it -- including
        # three runtime decision sites, until 5G-R. Every remaining reader,
        # runtime and test alike, now asks the channel that owns what it wants.
        C.incr("SEARCH_CONTROLS_RECORDED")
        return "accepted"

    def _record_outcome(self, t: Terminal) -> bool:
        """AN OUTCOME: what the receiving endpoint OBSERVED. This closes the edge.

        Only this channel writes `terminal_status` and the edge's credit, and
        only the receiving endpoint may fill it -- which `_may_emit` has already
        established by direction before this is reached.
        """
        o = self._organ
        if o is None:
            return False
        rec = self._lifecycle_record(t)
        first = rec["accepted_outcome"]
        if first is not None:
            if first.kind != t.kind:
                rec["outcome_conflicts"].append((t.edge_id, first.kind, t.kind))
                o.search_edge_terminal_conflicts.append(
                    (t.edge_id, first.kind, t.kind))
                C.incr("DUPLICATE_TERMINAL_RESOLUTIONS")
            return False                    # exact replay: inert, no refund
        rec["outcomes"].append(t)
        rec["accepted_outcome"] = t
        # COMPATIBILITY PROJECTION, explicitly derived from the accepted OUTCOME
        # and from nothing else. `search_edge_terminals` keeps its historical
        # shape for existing readers, but it is now filled only by the child's
        # answer, which is what its own consumers always assumed it meant.
        o.search_edge_terminals[t.edge_id] = {
            "from_unit": t.from_unit, "to_unit": t.to_unit,
            "search_key": t.search_key, "outcomes": [t]}
        e = o.search_edges.get(t.edge_id)
        if e is not None:
            e["terminal_status"] = "terminal"
            e["terminal_outcome"] = t.kind
            e["refunded_credit"] = t.refund
            e["consumed_credit"] = t.handling_cost
        C.incr("TERMINAL_ECHOS_SENT")
        return True

    def _probe_channel(self, t: Terminal) -> str:
        """'control', 'outcome', or '' -- decided by the SENDER-CREATED PROBE.

        Kind cannot decide this. `SearchNeedClosed` is in PARENT_CONTROL_KINDS
        and in CHILD_OUTCOME_KINDS, so the same kind is a command when the
        opener sends it down and an answer when the receiver sends it back. A
        classifier reading kind alone files the receiver's answer as a command,
        which is the defect this replaces.

        The probe can decide it, because the probe records who opened the edge
        and who it was opened to. The unit that OPENED it commands it; the unit
        it was opened TO answers it.

        THE AUTHOR IS `t.from_unit`, NEVER THE UNIT DOING THE RECORDING. A
        parent records a child-authored Terminal when it observes the child's
        closure, so classifying by the recorder would file the child's answer
        as the parent's command -- the same defect by a different route.

        Six facts are bound together and all of them must agree: the edge id,
        the SearchKey, both probe endpoints and both message endpoints. An
        emission that satisfies some of them and not the rest is refused rather
        than placed in whichever channel it partially matches.

        An EMPTY destination is accepted, and only because the commit and
        cancellation paths legitimately close an edge whose target is no longer
        tracked -- the same allowance `_may_emit` already makes for exactly
        those paths. A NAMED destination must be the exact reversal of the
        author's end.
        """
        o = self._organ
        if o is None:
            return ""
        rec = o.search_edge_probes.get(t.edge_id)
        if rec is None:
            return ""                       # unknown edge: refused by 2D
        if rec.get("search_key") != t.search_key:
            return ""                       # right edge id, wrong search
        if rec["from_unit"] == rec["to_unit"]:
            # A degenerate self-edge cannot distinguish command from answer,
            # so it gets neither channel rather than the first one that matches.
            return ""
        if t.from_unit == rec["from_unit"]:
            return "control" if (not t.to_unit
                                 or t.to_unit == rec["to_unit"]) else ""
        if t.from_unit == rec["to_unit"]:
            return "outcome" if (not t.to_unit
                                 or t.to_unit == rec["from_unit"]) else ""
        return ""                           # authored by neither endpoint

    def _record_terminal(self, t: Terminal) -> bool:
        """COMPATIBILITY SHIM. Strict, and it fails closed.

        Every live call site now selects its channel explicitly -- `_emit_terminal`
        from this unit's own role in the probe, `deliver_terminal` and
        `_acknowledge_to_parent` by naming `_record_outcome` directly. So this
        exists for callers outside the runtime, and it classifies from the
        probe and from nothing else.

        No fallback by kind. A fallback is what makes a strict rule optional:
        anything the strict rule refuses would simply take the loose path, and
        the shared `SearchNeedClosed` kind is exactly the message that would.
        A Terminal this cannot place mutates neither channel and is counted
        once, so a refusal is visible instead of silently becoming a command.
        """
        channel = self._probe_channel(t)
        if channel == "control":
            return self._record_control(t) == "accepted"
        if channel == "outcome":
            return self._record_outcome(t)
        C.incr("UNCLASSIFIABLE_TERMINAL_RECORDINGS")
        return False

    def _may_emit(self, key: SearchKey, edge_id: str, kind: str,
                  to: str = "") -> str:
        """'' if this emission is justified; else the counter naming the defect.

        May THIS unit assert this outcome, on this edge, under this key, in this
        direction, to this destination?

        `_record_terminal` writes organ-wide evidence and flips the edge's
        `terminal_status` BEFORE delivery, so a unit emitting an unowned or
        wrong-direction terminal poisoned shared evidence even when the receiver
        correctly refused the transition. Edge closure is what a receiver
        accepted, not what a sender asserted -- so the assertion is checked at
        the point it becomes authoritative.

        FOUR FACTS, NOT ONE. The 2C rule checked direction alone, on an edge it
        assumed existed. An unknown edge was admitted outright ("nothing to
        contradict"), which let an endpoint record an authoritative terminal on
        an id it invented -- and create the edge record justifying it. Neither
        the SearchKey the edge carries nor the destination was compared at all.
        """
        o = self._organ
        if o is None:
            return ""
        rec = o.search_edge_probes.get(edge_id)
        if rec is None:
            return "UNKNOWN_EDGE_TERMINAL_EMISSIONS"
        if rec.get("search_key") != key:
            return "UNAUTHENTICATED_TERMINAL_EMISSIONS"
        if rec["to_unit"] == self.unit_id:
            if kind not in CHILD_OUTCOME_KINDS:     # I ANSWER what reached me
                return "UNAUTHENTICATED_TERMINAL_EMISSIONS"
            expected = rec["from_unit"]             # ...back to whoever opened it
        elif rec["from_unit"] == self.unit_id:
            if kind not in PARENT_CONTROL_KINDS:    # I COMMAND what I opened
                return "UNAUTHENTICATED_TERMINAL_EMISSIONS"
            expected = rec["to_unit"]               # ...down to whom I opened it
        else:
            return "UNAUTHENTICATED_TERMINAL_EMISSIONS"     # neither end
        # An EMPTY destination records the outcome without delivering it, which
        # is how the commit and cancellation paths close an edge whose target is
        # no longer tracked. A NAMED destination must be the right one.
        if to and to != expected:
            return "UNAUTHENTICATED_TERMINAL_EMISSIONS"
        return ""

    def _emit_terminal(self, kind: str, key: SearchKey, edge_id: str, to: str,
                       refund: float = 0.0, handling_cost: float = 0.0,
                       reason: str = "", proposal_id: str = "") -> Terminal:
        t = Terminal(kind, key, edge_id, refund, handling_cost, self.unit_id, to,
                     reason, proposal_id)
        violation = self._may_emit(key, edge_id, kind, to)
        if violation:
            # EXACTLY ONE counter per refused emission. Incrementing a specific
            # counter here and a general one as well would make a single defect
            # read as two violations, and every "sums to 1" assertion would then
            # be satisfiable by two different bugs.
            C.incr(violation)
            return t
        # EXPLICIT CHANNEL AT THE CALL SITE. `_may_emit` has just proved this
        # unit is one of the probe's two endpoints and that any named
        # destination is the right one; which endpoint it is decides the
        # channel, and a message that satisfies `_may_emit` but cannot be
        # placed is refused rather than defaulted.
        channel = self._probe_channel(t)
        if channel == "control":
            self._record_control(t)
        elif channel == "outcome":
            self._record_outcome(t)
        else:
            C.incr("UNCLASSIFIABLE_TERMINAL_RECORDINGS")
            return t                        # nothing recorded, nothing sent
        if to:
            self.outbox.append((to, t))
        return t

    def _record_event(self, edge_id: str, kind: str, key: SearchKey,
                      reason: str = "", payload: Optional[SearchOfferPayload] = None,
                      to: str = "") -> SearchEvent:
        """NONTERMINAL edge telemetry. Never enters `search_edge_terminals`."""
        ev = SearchEvent(kind, key, edge_id, reason, payload, self.unit_id, to,
                         payload.proposal_id if payload is not None else "")
        o = self._organ
        if o is not None:
            o.search_edge_events.setdefault(edge_id, []).append(ev)
        return ev

    # -- canonical node lifecycle ---------------------------------------

    def _count_canonical_computation(self, node: dict) -> None:
        """ONE local computation per (unit, SearchKey), counted where it happens.

        Evaluating local eligibility and opening a frontier are the two halves of
        the SAME single computation, so both are counted here and neither is
        counted again when a later widening round continues that computation.
        A second computation for one node is the hierarchical defect returning,
        so it breaks the Single Bottleneck Metric rather than being suppressed.
        """
        if node["computed"]:
            C.incr("DUPLICATE_SUBTREES_OPENED")
        node["computed"] = True
        C.incr("CANONICAL_SEARCH_EXPANSIONS")

    def open_canonical_search(self, key: SearchKey, parent_edge: str,
                              allocation: float, parent_sender: str = "",
                              context: Optional[SearchContext] = None,
                              lineage: tuple = (), expand: bool = True) -> dict:
        """First-arrival adoption. At most one node per SearchKey per unit."""
        node = self.canonical_searches.get(key)
        if node is not None:
            C.incr("DUPLICATE_SUBTREES_OPENED")   # must never fire
            return node
        node = new_canonical_node(key, parent_edge, parent_sender, allocation,
                                  context, lineage)
        if context is None:
            # A node holding no context can enforce no constraint its key
            # advertises. The live path can no longer produce one; a direct
            # harness call still can, and it is measured rather than assumed.
            C.incr("CONTEXTLESS_CANONICAL_NODES")
        self.canonical_searches[key] = node
        C.incr("UNIQUE_CANONICAL_SEARCH_NODES")
        self._count_canonical_computation(node)
        if expand:
            self._expand_canonical(node)
        return node

    def _expand_canonical(self, node: dict) -> None:
        """Open one ring of the frontier. Rounds are numbered and ids carry it.

        Not counted as a canonical computation: the first call and every later
        widening are the same local search continuing, and counting widenings
        would make CANONICAL_SEARCH_EXPANSIONS / UNIQUE_CANONICAL_SEARCH_NODES
        drift above 1.0 for correct behaviour, hiding the defect it exists to
        detect.
        """
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
        # THE EDGE-ID NAMESPACE, WHICH A ROOT DOES NOT GET FOR FREE.
        #
        # A relay names its children after the edge it was adopted on, which is
        # already unique. A ROOT has no adopted parent edge -- correctly, it
        # answers to nobody -- so `adopted` was the empty string and its
        # children came out as "/r0/c0", "/r0/c1". Two roots in one organ then
        # minted THE SAME child edge ids, the second root's `_record_probe`
        # collided with the first's record, and the 2D gate correctly refused
        # the arrival as `sender_is_not_the_recorded_opener`. The ingress was
        # right and the naming was wrong.
        #
        # `need_id` is `unit:slot:activation`, so it is unique to the unit, the
        # obligation and the reopen that created it -- locally derived, and
        # enough to separate every root in the organ.
        adopted = node["adopted_parent_edge"] or f"root:{node['search_key'].need_id}"
        rnd = node["expansion_round"]
        opened = 0
        for i, n in enumerate(ring):
            if node["local_reserve"] < per:
                break
            # GLOBALLY UNIQUE ACROSS ROUNDS. `f"{adopted}/c{i}"` restarted `i`
            # at zero on every expansion, so a second widening reused /c0 and
            # /c1 for different routes and the two rounds' edges collided.
            child = f"{adopted}/r{rnd}/c{i}"
            node["local_reserve"] -= per
            node["child_allocations"][child] = per
            node["child_allocations_in_flight"] += per
            node["child_targets"][child] = n
            node["children_opened"].append(child)
            node["children_outstanding"].add(child)
            node["children_from"].setdefault(adopted, []).append(child)
            node["neighbours_tried"].add(n)
            node["child_sequence"] += 1
            opened += 1
            self._record_probe(child, self.unit_id, n, key, allocation=per)
            self.outbox.append((n, ("__search__", key, child, per,
                                    node["lineage"] + (self.unit_id,),
                                    node["search_context"])))
        node["eligible_untried_routes"] = max(
            0, node["eligible_untried_routes"] - opened)
        node["expansion_round"] += 1
        node["round"] = node["expansion_round"]

    # -- remote eligibility ---------------------------------------------

    def _candidate_refusal(self, key: SearchKey,
                           context: Optional[SearchContext]) -> str:
        """Why THIS unit may not propose itself for `key`. '' means eligible.

        Every rule is evaluated against the SearchContext that TRAVELLED with the
        probe. A digest proves identity; it cannot enforce a constraint that
        never left the origin -- which is exactly how the excluded sibling
        supplier could receive a probe remotely and offer itself, recreating the
        duplicate-supplier defect the mechanism exists to remove.

        Domain independence and prohibited motifs are deliberately NOT here.
        They are computed at settlement from origin-local capabilities, which is
        the only place the answer is current, and shipping the origin's occupied
        domains to every reachable candidate would be a topology disclosure.
        """
        if self.dissolved:
            return "candidate_dissolved"
        if self.silent:
            return "candidate_silent"
        if self.capability.produces != key.wanted_type:
            return "candidate_type_mismatch"
        if context is None:
            # No constraints arrived, so nothing can be enforced. Refusing is the
            # only safe reading: proposing here would be an unchecked candidate.
            return "candidate_context_absent"
        if self.unit_id in context.must_differ_from_suppliers:
            return "candidate_must_differ"
        if self.capability.cost * self.cost_multiplier > context.maximum_supplier_cost:
            return "candidate_above_cost_ceiling"
        if self.unit_id in context.cooldown_excluded_suppliers:
            return "candidate_in_cooldown"
        if self._derives_from() & frozenset(context.causally_refused_sources):
            # DERIVATION intersection, not just this unit's own id. Checking only
            # the candidate's own name proves direct exclusion and says nothing
            # about whether a refused ancestor is still upstream of it.
            return "candidate_derivation_refused"
        return ""

    def _build_offer_payload(self, key: SearchKey,
                             context: Optional[SearchContext],
                             source_edge: str) -> SearchOfferPayload:
        """Everything `_settle` needs, bound to the search that asked for it.

        `Terminal` carried no supplier, class, type, cost, firm flag or
        derivation chain, so the mechanism could report "an offer exists" and
        then be unable to settle it.
        """
        return SearchOfferPayload(
            proposal_id="",                        # derived from the content
            search_key=key,
            context_digest=key.context_digest,
            supplier=self.unit_id,
            supplier_class=self.capability.klass(),
            offered_type=self.capability.produces,
            cost=self.capability.cost * self.cost_multiplier,
            firm=not self.unmet(),
            derivation_chain=self._derives_from(),
            source_node=self.unit_id,
            source_edge_id=source_edge,
            supplied_label=f"{self.unit_id}@{source_edge}")

    def _propose_upward(self, node: dict, payload: SearchOfferPayload) -> None:
        """Send the proposal home along the ADOPTED parent edge, and only that.

        `reverse[need_id]` was keyed by need alone, so a later arrival could
        overwrite the return route and a result could travel home through the
        wrong parent while duplicate suppression still looked correct.
        """
        to = node["adopted_parent_sender"]
        if not to:
            return
        self.outbox.append((to, ("__proposal__", node["search_key"],
                                 node["adopted_parent_edge"], payload)))

    # -- arrivals --------------------------------------------------------

    def _admit_prearrival_parent_control(
            self, terminal: Terminal, *, sender: Any
    ) -> ControlRecordResult | Literal["rejected"]:
        """Authenticate first; only then mark one canonical control as held.

        The sender may already have recorded ``accepted_control`` when it
        emitted the message. That is evidence of emission, not receiver
        arrival. ``prearrival_control_state`` is moved only here, after the
        immediate sender, sender-created probe, key, direction and both claimed
        endpoints all agree.
        """
        o = self._organ
        if (o is None or sender is HARNESS_DELIVERY
                or sender is _UNSPECIFIED_SENDER
                or not isinstance(sender, str) or not sender
                or sender not in self.neighbours):
            C.incr("UNAUTHENTICATED_TERMINAL_CONTROLS")
            return "rejected"
        probe = o.search_edge_probes.get(terminal.edge_id)
        if (probe is None
                or probe.get("from_unit") != sender
                or probe.get("to_unit") != self.unit_id
                or probe.get("search_key") != terminal.search_key
                or terminal.from_unit != sender
                or terminal.to_unit != self.unit_id
                or terminal.kind not in PARENT_CONTROL_KINDS
                or self._probe_channel(terminal) != "control"):
            C.incr("UNAUTHENTICATED_TERMINAL_CONTROLS")
            return "rejected"

        result = self._record_control(terminal)
        rec = o.search_edge_lifecycle[terminal.edge_id]
        state = rec.get("prearrival_control_state")
        if result == "conflict":
            C.incr("PREARRIVAL_CONTROL_CONFLICTS")
            return result
        if state is None:
            rec["prearrival_control_state"] = "held"
            C.incr("PREARRIVAL_CONTROLS_HELD")
            # The shared record normally made the full message an exact replay
            # at this point. Receiver arrival is nevertheless new.
            return "accepted"
        C.incr("PREARRIVAL_CONTROL_REPLAYS")
        return "replay"

    def _apply_recorded_parent_control(
            self, node: dict[str, Any], *, edge_id: str
    ) -> bool:
        """Apply one authenticated held control after valid node adoption."""
        o = self._organ
        if o is None:
            return False
        rec = o.search_edge_lifecycle.get(edge_id)
        if rec is None or rec.get("prearrival_control_state") != "held":
            return False
        terminal = rec.get("accepted_control")
        probe = o.search_edge_probes.get(edge_id)
        valid = (
            isinstance(terminal, Terminal)
            and probe is not None
            and terminal.edge_id == edge_id
            and terminal.search_key == node.get("search_key")
            and terminal.from_unit == node.get("adopted_parent_sender")
            and terminal.to_unit == self.unit_id
            and probe.get("from_unit") == terminal.from_unit
            and probe.get("to_unit") == self.unit_id
            and probe.get("search_key") == terminal.search_key
            and terminal.kind in PARENT_CONTROL_KINDS
            and self._probe_channel(terminal) == "control"
        )
        if not valid:
            rec["prearrival_control_state"] = "rejected"
            C.incr("UNAUTHENTICATED_TERMINAL_CONTROLS")
            return False
        if terminal.kind == "SearchCommitted":
            if not self._knows_proposal(node, terminal.proposal_id):
                rec["prearrival_control_state"] = "rejected"
                C.incr("UNKNOWN_COMMIT_PROPOSALS")
                return False
            if not self._commit_eligible(node, terminal.proposal_id):
                rec["prearrival_control_state"] = "rejected"
                C.incr("COMMIT_OF_RESOLVED_PROPOSAL")
                return False
        if node.get("wave_cancelled"):
            rec["prearrival_control_state"] = "rejected"
            C.incr("DUPLICATE_CONTROL_APPLICATIONS")
            return False
        self._close_wave_from_parent(
            node, terminal.kind, terminal.proposal_id,
        )
        rec["prearrival_control_state"] = "applied"
        C.incr("PREARRIVAL_CONTROLS_APPLIED")
        return True

    def _refuse_search(self, key: SearchKey, edge_id: str, counter: str,
                       reason: str) -> Terminal:
        """A refusal that writes NOTHING but its own counter.

        Deliberately NOT routed through `_emit_terminal`: recording a terminal
        flips `search_edges[edge].terminal_status` and writes organ-wide
        evidence, so refusing an arrival would mutate exactly the records the
        arrival failed to justify -- and on a fabricated edge it would create
        them. The caller receives an object carrying the reason; the organ
        learns only that a violation occurred, and from whom it claimed to come.
        """
        C.incr(counter)
        return Terminal("SearchAdmissionRefused", key, edge_id, 0.0, 0.0,
                        self.unit_id, "", reason, "")

    def _admit_search(self, key: SearchKey, edge_id: str, allocation: float,
                      sender: Any, transport: Any):
        """True if this arrival proved its route. Otherwise a refusal Terminal.

        SENDER-OWNED EVIDENCE. The sender creates the probe when it opens the
        edge (`_expand_canonical` -> `_record_probe`), recording the endpoints,
        the SearchKey and the allocation it committed. The receiver checks the
        arrival against that record and NEVER creates it: a receiver that
        manufactures the sender's evidence has authenticated nothing but its own
        willingness to be told.

        `transport` is an EXPLICIT declaration that no sender-created probe
        exists, for a test driving another layer directly. It is separate from
        `sender`, never replaces it, is counted every time, and is required to
        read zero across a live run.
        """
        if transport is HARNESS_DELIVERY:
            C.incr("HARNESS_DELIVERIES_USED")
            return True
        o = self._organ
        if o is None:
            return True
        # 1. IDENTITY. Absence is not the origin. `sender or key.origin_unit`
        #    read a caller with no identity at all as the unit named in the key,
        #    which is the one identity an attacker never has to earn.
        if sender is _UNSPECIFIED_SENDER or not sender or not isinstance(sender, str):
            return self._refuse_search(key, edge_id,
                                       "UNAUTHENTICATED_SEARCH_DELIVERIES",
                                       "sender_absent")
        # 2. ADJACENCY. A search may only arrive from a unit this one is
        #    actually joined to. Checked before the probe, so a stranger holding
        #    a structurally perfect edge record is still refused.
        if sender not in self.neighbours:
            return self._refuse_search(key, edge_id,
                                       "UNAUTHENTICATED_SEARCH_DELIVERIES",
                                       "sender_not_adjacent")
        rec = o.search_edge_probes.get(edge_id)
        # 3. THE PROBE MUST ALREADY EXIST.
        if rec is None:
            return self._refuse_search(key, edge_id,
                                       "MALFORMED_SEARCH_DELIVERIES",
                                       "no_sender_probe")
        # 4. THE RECORDED OPENER IS THE UNIT THAT DELIVERED IT.
        if rec.get("from_unit") != sender:
            return self._refuse_search(key, edge_id,
                                       "UNAUTHENTICATED_SEARCH_DELIVERIES",
                                       "sender_is_not_the_recorded_opener")
        # 5. THE RECORDED DESTINATION IS ME. An edge opened to somebody else
        #    does not become mine because I was handed its id.
        if rec.get("to_unit") != self.unit_id:
            return self._refuse_search(key, edge_id,
                                       "MALFORMED_SEARCH_DELIVERIES",
                                       "edge_destination_is_another_unit")
        # 6. THE EDGE CARRIES THIS SEARCHKEY.
        if rec.get("search_key") != key:
            return self._refuse_search(key, edge_id,
                                       "MALFORMED_SEARCH_DELIVERIES",
                                       "edge_carries_another_search_key")
        # 7. THE ARRIVING AMOUNT IS THE ONE THE SENDER COMMITTED. Without this
        #    a neighbour can inflate its own allocation on arrival and be
        #    refunded credit nobody ever reserved.
        committed = rec.get("allocation", 0.0)
        try:
            mismatch = not math.isfinite(allocation) or abs(
                float(allocation) - float(committed)) > 1e-9
        except (TypeError, ValueError):
            mismatch = True
        if mismatch:
            return self._refuse_search(key, edge_id,
                                       "MALFORMED_SEARCH_DELIVERIES",
                                       "allocation_is_not_the_committed_amount")
        return True

    def deliver_search(self, key: SearchKey, edge_id: str, allocation: float,
                       lineage: tuple = (), sender: str = "",
                       context: Optional[SearchContext] = None,
                       transport: Any = None):
        """One arrival on one transport edge. Returns its single outcome.

        `transport` is SEPARATE from `sender`, and never replaces it: the sender
        still names the claimed immediate unit, while `transport` carries an
        explicit `HARNESS_DELIVERY` declaration that no sender-created probe
        exists. Substituting the capability for the identity would destroy the
        return route and hide which unit is being trusted. ACCEPTED BUT NOT YET
        ENFORCED -- this commit adds the seam only, so admission behaviour is
        unchanged and the suite composition must not move.

        A first arrival that is locally eligible returns a nonterminal
        SearchProposal; the edge stays open until the origin commits or cancels
        it. Every other first arrival adopts, expands and stays open. A
        duplicate, a cycle, a closed need and a forged context each terminate
        the arriving edge exactly once.
        """
        o = self._organ
        # THE ADMISSION GATE, AND IT RUNS FIRST.
        #
        # Ordering is the whole security property here. Every branch below --
        # the terminal-edge replay, the cycle response, the closed-Need
        # response, duplicate coalescing, the context gate and the node lookup
        # -- either returns a REFUND or reveals whether this unit holds a given
        # SearchKey. An unauthenticated caller must not be able to reach even a
        # zero-value replay echo before proving its route, so nothing is
        # consulted and nothing is recorded until the arrival is admitted.
        admitted = self._admit_search(key, edge_id, allocation, sender, transport)
        if admitted is not True:
            return admitted
        _lc = (o.search_edge_lifecycle.get(edge_id) or {}) if o is not None else {}
        if _lc.get("accepted_outcome") is not None:
            # Exact replay of an edge ALREADY ANSWERED: no reprocessing, no
            # second terminal, and CRUCIALLY no second refund. Returning the
            # original terminal object would report its original refund again,
            # which reads as a second payment; the replay is reported as a
            # zero-value echo of the same outcome.
            #
            # ANSWERED, not merely commanded. This read membership in
            # `search_edge_terminals`, which the control path also wrote, so a
            # parent's command made its own edge look already-answered and this
            # branch returned an inert echo before cycle, closed-Need,
            # coalescing, context or adoption logic could run. An edge is
            # answered when its canonical lifecycle holds an accepted OUTCOME,
            # and a command is not an answer.
            first = _lc["accepted_outcome"]
            return Terminal(first.kind, first.search_key, edge_id, 0.0, 0.0,
                            self.unit_id, first.to_unit, "edge_replay",
                            first.proposal_id)
        self._record_delivery(edge_id, sender or key.origin_unit, self.unit_id, key)

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
            # A DUPLICATE ARRIVAL ADOPTS NOTHING AND STILL OWES ITS OPENER AN
            # ANSWER ON THIS EXACT EDGE. Counted at creation so the ratio below
            # has a real denominator rather than one derived from the answers.
            C.incr("COALESCED_INBOUND_EDGES")
            node["children_from"].setdefault(edge_id, [])
            node["handling_cost"] += cost
            C.incr("COALESCED_DUPLICATE_ARRIVALS")
            return self._emit_terminal("SearchCoalesced", key, edge_id, sender,
                                       refund=max(0.0, allocation - cost),
                                       handling_cost=cost)

        # THE CONTEXT GATE GUARDS ADOPTION, AND FAILS CLOSED.
        #
        # It sits exactly here, after the paths that create nothing -- an edge
        # replay, a cycle, a closed need and a duplicate arrival all refuse to
        # compute, refuse to expand and refuse to adopt, so no context of theirs
        # is ever honoured -- and immediately before the only path that does.
        #
        # A MISMATCHED context is a forgery: an unenforced constraint wearing a
        # valid identity. A MISSING one is the same defect reached by omission.
        # The key advertises bound refusals, a must-differ set, a cost ceiling, a
        # cooldown set, a constraint generation and a policy snapshot; a node
        # that received none of them can enforce none of them, and adopting the
        # search anyway -- which is what returning SearchPending and expanding
        # did -- manufactures a wave claiming constraints nobody holds. Absence
        # of evidence is not absence of constraint.
        if context is None:
            if _lc.get("prearrival_control_state") == "held":
                C.incr("MALFORMED_SEARCH_DELIVERIES")
                return Terminal("SearchContextRejected", key, edge_id,
                                0.0, 0.0, self.unit_id, sender,
                                "context_absent", "")
            return self._emit_terminal("SearchContextRejected", key, edge_id,
                                       sender, refund=max(0.0, allocation),
                                       reason="context_absent")
        if not context.matches(key):
            if _lc.get("prearrival_control_state") == "held":
                C.incr("MALFORMED_SEARCH_DELIVERIES")
                return Terminal("SearchContextRejected", key, edge_id,
                                0.0, 0.0, self.unit_id, sender,
                                "context_digest_mismatch", "")
            return self._emit_terminal("SearchContextRejected", key, edge_id,
                                       sender, refund=max(0.0, allocation),
                                       reason="context_digest_mismatch")

        # ADOPTION IS THE MEASURED EVENT, and it is certain from here: both
        # branches below open a canonical node. Counted once, and split by
        # whether the arrival PROVED its route or DECLARED a bypass -- counting
        # a harness delivery as authenticated would hold the Single Bottleneck
        # Metric at 1.0 while the gate was being skipped.
        C.incr("TOTAL_CANONICAL_SEARCH_ADOPTIONS")
        if transport is not HARNESS_DELIVERY:
            C.incr("AUTHENTICATED_SEARCH_ADOPTIONS")

        # FIRST ARRIVAL. Eligibility is evaluated BEFORE expansion: an eligible
        # supplier used to open descendants first and answer second, spending
        # credit on a search it did not need.
        reason = self._candidate_refusal(key, context)
        node = self.open_canonical_search(key, edge_id, allocation, sender,
                                          context=context, lineage=lineage,
                                          expand=False)
        if self._apply_recorded_parent_control(node, edge_id=edge_id):
            control = _lc["accepted_control"]
            return self._record_event(
                edge_id, control.kind, key,
                reason="prearrival_control_applied", to=sender,
            )
        if not reason:
            payload = self._build_offer_payload(key, context, edge_id)
            node["local_candidate"] = payload
            node["eligible_offer"] = True
            C.incr("DISTINCT_ELIGIBLE_REPLACEMENTS_DISCOVERED")
            self._propose_upward(node, payload)
            if not payload.firm:
                # A non-firm candidate is evidence, not an answer: the origin
                # cannot bond it, so the wave must continue past it.
                self._expand_canonical(node)
                # NESTED PREREQUISITE RECRUITMENT. This unit COULD serve the
                # search except that it is itself unmet, so continuing the wave
                # outward is only half the response: the other half is repairing
                # the reason it cannot answer. The legacy `Need` path did this
                # by minting a sub-need per unmet slot; the canonical form is
                # simply to ORIGINATE, because a prerequisite deficit is a
                # deficit like any other and origination is what a unit does
                # with one. Recursion falls out of the mechanism rather than
                # needing a second one.
                self._recruit_prerequisites()
            return SearchEvent("SearchProposal", key, edge_id, "", payload,
                               self.unit_id, sender, payload.proposal_id)
        self._expand_canonical(node)
        return self._record_event(edge_id, "SearchPending", key, reason=reason,
                                  to=sender)

    def _must_differ(self, key: SearchKey) -> frozenset[str]:
        """Sibling exclusions for a key I originated. Empty for keys I relay.

        Retained for local reporting only. Remote enforcement travels in
        `SearchContext.must_differ_from_suppliers`, because this function
        returns nothing at a unit that did not originate the search and so can
        never constrain a remote candidate.
        """
        if key.origin_unit != self.unit_id:
            return frozenset()
        return frozenset(b.supplier for s, b in self.bonds.items()
                         if s != key.origin_slot)

    def _knows_proposal(self, node: dict, pid: str) -> bool:
        """The three ways a proposal is legitimately known at this node.

        A relay RECEIVED it on a child edge; the origin already resolved it; the
        SOURCE minted it and holds it as `local_candidate`, so it never appears
        in that node's routes at all. A rule consulting routes alone would make
        every accepted candidate uncommittable at exactly the node that produced
        it -- the same shape of defect that made rejections unroutable.
        """
        if not pid:
            return False
        mine = node.get("local_candidate")
        return (pid in node["proposal_routes"]
                or pid in node["proposals_rejected"]
                or pid in node["proposal_disposition"]
                or (mine is not None and mine.proposal_id == pid))

    def _commit_eligible(self, node: dict, pid: str) -> bool:
        """ACQUAINTANCE IS NOT ELIGIBILITY. May this proposal still be decided?

        `_knows_proposal` answers whether this node has ever seen `pid`. That is
        the right question for routing and the wrong one for commitment: it
        counts `proposals_rejected` and `proposal_disposition` as known, so an
        authenticated parent could reject P, leave the wave open, and then
        commit P. Exactly-once resolution forbids a second, contradictory
        decision about the same candidate.

        The exact replay of an ALREADY-ACCEPTED commit stays eligible, because a
        replay is not a second decision -- it is the same decision arriving
        twice, and `_close_wave_from_parent` is idempotent against it. Ordering
        matters: the accepted id is checked FIRST, because sealing writes it
        into `proposal_disposition` and the general rule below would then refuse
        the replay of the very commit this node acted on.
        """
        if not pid:
            return False
        if pid == node.get("accepted_proposal_id"):
            return True
        if pid in node["proposals_rejected"]:
            return False
        if pid in node["proposal_disposition"]:
            return False
        return self._knows_proposal(node, pid)

    def deliver_proposal(self, key: SearchKey, edge_id: str,
                         payload: SearchOfferPayload,
                         sender: Any = _UNSPECIFIED_SENDER):
        """Register a candidate that arrived on `edge_id`. NONTERMINAL.

        PROVENANCE, NOT ONLY INTEGRITY. The derived `proposal_id` proves the
        evidence was not altered in transit. It proves nothing about who
        delivered it or over which edge: a relay that cannot mutate a proposal
        can still MINT a new, internally consistent one and register it against
        a route this node never opened, or inject a candidate onto a
        neighbour's branch so the commit for that branch is later routed to a
        unit that never carried it. A hash is integrity; the checks below are
        authentication.

        The arrival edge is the route home for a commit and for rejection
        feedback. It is NOT `payload.source_edge_id`: that says where the
        proposal ORIGINATED, possibly several hops away, and using it here would
        let this node write terminals on edges it does not own.
        """
        node = self.canonical_searches.get(key)
        if node is None:
            C.incr("ORPHANED_SEARCH_EDGES")
            return None
        if node["wave_cancelled"] or node["terminal_signal_sent"]:
            # A CLOSED WAVE ADMITS NO NEW CANDIDATE. Registering one would put a
            # fresh obligation on a node that has already reported its outcome,
            # and forwarding it would carry that obligation upward to a search
            # that is over.
            C.incr("LATE_CONTROLS_AFTER_CLOSURE")
            return self._record_event(edge_id, "SearchNeedClosed", key,
                                      reason="wave_already_closed",
                                      payload=payload)
        # 1. THE EDGE MUST BE MINE. An edge this node never opened is not a
        #    route it can commit or cancel through.
        if edge_id not in node["child_allocations"]:
            C.incr("UNOWNED_PROPOSAL_ROUTES")
            return self._record_event(edge_id, "SearchProposalRejected", key,
                                      reason="proposal_edge_not_owned",
                                      payload=payload)
        # 2. THE SENDER MUST BE THAT EDGE'S TARGET.
        target = node["child_targets"].get(edge_id)
        if not _authenticated(sender, target):
            C.incr("UNOWNED_PROPOSAL_ROUTES")
            return self._record_event(edge_id, "SearchProposalRejected", key,
                                      reason="proposal_sender_mismatch",
                                      payload=payload)
        # 3. THE EDGE MUST CARRY THIS SEARCH.
        o = self._organ
        rec = o.search_edge_probes.get(edge_id) if o is not None else None
        if rec is not None and rec["search_key"] != key:
            C.incr("UNOWNED_PROPOSAL_ROUTES")
            return self._record_event(edge_id, "SearchProposalRejected", key,
                                      reason="proposal_edge_key_mismatch",
                                      payload=payload)
        if payload.search_key != key:
            return self._record_event(edge_id, "SearchProposalRejected", key,
                                      reason="wrong_search_key", payload=payload)
        if payload.context_digest != key.context_digest:
            return self._record_event(edge_id, "SearchProposalRejected", key,
                                      reason="context_digest_mismatch",
                                      payload=payload)
        if not payload.identity_intact():
            # The id no longer matches its own content: a hop altered a field
            # and kept the identity.
            return self._record_event(edge_id, "SearchProposalRejected", key,
                                      reason="proposal_payload_mutated",
                                      payload=payload)
        # 4. AT THE SOURCE HOP the proposing unit must be the unit that is
        #    actually offering itself. Further up, the payload is relayed
        #    evidence and the sender is the relay, so this cannot apply.
        if (sender is not _UNSPECIFIED_SENDER and sender is not HARNESS_DELIVERY
                and payload.source_edge_id == edge_id
                and (payload.source_node != sender or payload.supplier != sender)):
            C.incr("UNOWNED_PROPOSAL_ROUTES")
            return self._record_event(edge_id, "SearchProposalRejected", key,
                                      reason="proposal_source_not_sender",
                                      payload=payload)
        pid = payload.proposal_id
        digest = payload.derived_id()
        known = node["proposal_digests"].get(pid)
        if known is not None and known != digest:
            return self._record_event(edge_id, "SearchProposalRejected", key,
                                      reason="proposal_payload_mutated",
                                      payload=payload)
        route = node["proposal_routes"].get(pid)
        if route is not None:
            if route != edge_id:
                # One proposal, two arrival routes. Accepting the second would
                # let a relay redirect where the commit travels.
                C.incr("OFFER_RETURN_ROUTE_MISMATCHES")
                return self._record_event(edge_id, "SearchProposalRejected", key,
                                          reason="proposal_route_conflict",
                                          payload=payload)
            return None          # exact replay: no second event, no second count
        node["proposal_routes"][pid] = edge_id
        node["proposal_digests"][pid] = digest
        node["proposal_payloads"][pid] = payload
        node["proposals_outstanding"].add(pid)
        C.incr("UNIQUE_PROPOSAL_IDS_RECEIVED")
        ev = self._record_event(edge_id, "SearchProposal", key, payload=payload)
        if key.origin_unit == self.unit_id:
            if node["status"] == "OPEN":
                node["status"] = "PROPOSAL_PENDING"
            C.incr("PROPOSALS_RETURNED_TO_ROOT")
            # REGISTERED, NOT DECIDED. Settlement is driven from `step`, not
            # from here. Deciding synchronously on arrival would mean the FIRST
            # firm proposal to be delivered wins, with no chance for a
            # competitor delivered in the same round to race -- which is what
            # `PROPOSAL_PENDING` exists to represent, and what
            # `_continue_after_child` already waits on.
        else:
            # A relay carries the evidence home unchanged. It does not settle,
            # does not answer, and does not cancel anything.
            self._propose_upward(node, payload)
        return ev

    # -- rejection feedback ----------------------------------------------

    def _reject_downward(self, node: dict, pid: str, reason: str) -> None:
        """Send a refusal back along the route the proposal actually came in on.

        Without this the origin's decision never leaves the origin. Every relay
        that forwarded the proposal keeps it in `proposals_outstanding`, and the
        exhaustion path refuses to terminate while any proposal is outstanding,
        so the subtree waits forever on a decision that was already made. That
        is not a slow search; it is a search that can never report a result.
        """
        edge = node["proposal_routes"].get(pid)
        if edge is None:
            C.incr("STRANDED_REJECTED_PROPOSALS")
            return
        to = node["child_targets"].get(edge)
        if not to:
            C.incr("STRANDED_REJECTED_PROPOSALS")
            return
        self.outbox.append((to, ("__proposal_rejected__", node["search_key"],
                                 edge, pid, reason)))

    def deliver_proposal_rejected(self, key: SearchKey, edge_id: str, pid: str,
                                  reason: str, sender: Any = _UNSPECIFIED_SENDER):
        """A refusal arriving from my parent. NONTERMINAL, routed hop by hop.

        Clears exactly the proposal named, at exactly this node, and forwards it
        one more hop through this node's OWN mapping. It closes no unrelated
        branch, never rebinds the adopted parent, and never terminates an edge:
        the branch that carried the candidate is still a legal search path and
        may continue.
        """
        node = self.canonical_searches.get(key)
        if node is None:
            C.incr("ORPHANED_SEARCH_EDGES")
            return None
        if edge_id != node["adopted_parent_edge"]:
            C.incr("UNOWNED_PROPOSAL_ROUTES")
            return self._record_event(edge_id, "SearchProposalRejected", key,
                                      reason="rejection_edge_not_adopted")
        # THE EDGE ID IS NOT A CREDENTIAL. Any neighbour can name it, so
        # authenticating on it alone hands every neighbour a denial-of-repair
        # primitive: suppress a valid candidate and the wave behaves as though
        # the origin had decided. The adopted parent is immutable after adoption
        # and is the only party entitled to answer on that edge.
        if not _authenticated(sender, node["adopted_parent_sender"]):
            C.incr("UNAUTHENTICATED_REJECTION_CONTROLS")
            return self._record_event(edge_id, "SearchProposalRejected", key,
                                      reason="rejection_sender_not_adopted_parent")
        # A proposal is KNOWN here if it was registered on one of my child edges,
        # if I already rejected it, or if it is my OWN candidate -- the source
        # minted the proposal and forwarded it, so it never appears in that
        # node's `proposal_routes`. Requiring a route would have made every
        # rejection unroutable at exactly the node that has to act on it.
        mine = node.get("local_candidate")
        if (pid not in node["proposal_routes"]
                and pid not in node["proposals_rejected"]
                and not (mine is not None and mine.proposal_id == pid)):
            C.incr("UNAUTHENTICATED_REJECTION_CONTROLS")
            return self._record_event(edge_id, "SearchProposalRejected", key,
                                      reason="rejection_of_unknown_proposal")
        if node["wave_cancelled"] or node["terminal_signal_sent"]:
            # CLOSED MEANS CAUSALLY SEALED. A decision after closure cannot
            # change what the wave already resolved, and letting it mutate
            # `proposals_rejected` or the accepted identity would reopen a
            # settled obligation from a late message.
            C.incr("LATE_CONTROLS_AFTER_CLOSURE")
            return self._record_event(edge_id, "SearchNeedClosed", key,
                                      reason="wave_already_closed")
        if pid in node["proposals_rejected"]:
            return None                          # replay: idempotent
        node["proposals_rejected"].add(pid)
        node["proposals_outstanding"].discard(pid)
        payload = node["proposal_payloads"].get(pid)
        self._record_event(edge_id, "SearchProposalRejected", key, reason=reason,
                           payload=payload)
        if node.get("local_candidate") is not None and \
                node["local_candidate"].proposal_id == pid:
            # THIS unit was the candidate. Its offer was refused, so it must stop
            # advertising one -- otherwise its own exhaustion path, which will
            # not terminate while an eligible offer is recorded, can never fire.
            node["local_candidate"] = None
            node["eligible_offer"] = False
            C.incr("REJECTED_PROPOSALS_RESOLVED")
            if (not node["children_outstanding"]
                    and not node["terminal_signal_sent"]):
                # Continue the bounded frontier if routes and credit remain;
                # otherwise report the correct exhaustion.
                if node["local_reserve"] >= 1.0:
                    self._expand_canonical(node)
                if not node["children_outstanding"]:
                    self._echo_exhaustion(node)
            return None
        self._reject_downward(node, pid, reason)
        return None

    # -- settlement -------------------------------------------------------

    def _reject_precondition(self, payload: SearchOfferPayload, reason: str) -> None:
        """A refusal to DECIDE, recorded with an attributable reason.

        These are not settlement rejections: nothing reached `_settle`, so they
        are counted apart from SEARCH_OFFER_SETTLEMENT_REJECTIONS and are not
        written into the exactly-once decision ledger.
        """
        mark = (payload.proposal_id, reason)
        if mark in self._proposal_preconditions:
            return
        self._proposal_preconditions.add(mark)
        key = payload.search_key
        node = self.canonical_searches.get(key)
        edge = None
        if node is not None:
            edge = node["proposal_routes"].get(payload.proposal_id)
        self._record_event(edge or payload.source_edge_id,
                           "SearchProposalRejected", key, reason=reason,
                           payload=payload)

    def _refuse_proposal(self, node: dict, payload: SearchOfferPayload,
                         reason: str) -> None:
        """One refused settlement: counted, recorded, and ROUTED HOME."""
        pid = payload.proposal_id
        C.incr("UNIQUE_PROPOSAL_DECISIONS")
        C.incr("SEARCH_OFFER_SETTLEMENT_REJECTIONS")
        C.incr("REJECTED_PROPOSALS_TOTAL")
        self._proposal_decisions[pid] = False
        node["proposals_outstanding"].discard(pid)
        # A rejection does NOT close the Need, does NOT cancel unrelated children
        # and does NOT end the wave. Remaining candidates and bounded
        # continuation stay available.
        node["status"] = "OPEN"
        self._record_event(node["proposal_routes"][pid], "SearchProposalRejected",
                           node["search_key"], reason=reason, payload=payload)
        self._reject_downward(node, pid, reason)

    def settle_search_offer(self, payload: SearchOfferPayload) -> bool:
        """Resolve one proposal EXACTLY ONCE. Returns the decision.

        `_settle` writes `self.bonds[slot]` with no independent slot-open check
        -- that guard lives in `_on_offer` -- so a proposal resolved directly
        against a still-bonded slot would OVERWRITE it. Every precondition is
        checked here, before any bond can be created.
        """
        key = payload.search_key
        pid = payload.proposal_id
        prior = self._proposal_decisions.get(pid)
        if prior is not None:
            return prior            # replayed decision: stored answer, no effects
        if key.origin_unit != self.unit_id:
            self._reject_precondition(payload, "not_my_search")
            return False
        if not payload.identity_intact():
            self._reject_precondition(payload, "proposal_payload_mutated")
            return False
        if payload.context_digest != key.context_digest:
            self._reject_precondition(payload, "context_digest_mismatch")
            return False
        slot = key.origin_slot
        if slot in self.bonds:
            self._reject_precondition(payload, "slot_already_bonded")
            return False
        node = self.canonical_searches.get(key)
        if node is None:
            self._reject_precondition(payload, "no_canonical_node")
            return False
        if node["proposal_routes"].get(pid) is None:
            # Settlement follows a REGISTERED arrival on a real child edge.
            # Without this an arbitrary unregistered payload could be settled.
            self._reject_precondition(payload, "proposal_not_registered")
            return False
        nid = self.open_needs.get(slot)
        if nid is None or nid != key.need_id:
            self._reject_precondition(payload, "wrong_need_generation")
            return False

        if not payload.firm:
            self._refuse_proposal(node, payload, "nonfirm")
            return False
        offer = Offer(key.need_id, payload.supplier, payload.supplier_class,
                      payload.offered_type, payload.cost, payload.firm,
                      payload.derivation_chain)
        caps = self._organ._caps(self) if self._organ is not None else {}
        self._last_refusal = ""
        ok = self._settle(slot, offer, caps)
        if not ok:
            self._refuse_proposal(node, payload,
                                  self._last_refusal or "unrecorded_refusal")
            return False
        C.incr("UNIQUE_PROPOSAL_DECISIONS")
        self._proposal_decisions[pid] = True
        node["proposals_outstanding"].discard(pid)
        b = self.bonds.get(slot)
        if b is not None:
            b.settled_from_search_offer = True
        sups = [x.supplier for x in self.bonds.values()]
        if len(sups) != len(set(sups)):
            C.incr("INDEPENDENCE_VIOLATIONS")
        if node.get("search_context") is not None or self._must_differ(key):
            C.incr("DISTINCT_ELIGIBLE_REPLACEMENTS_SETTLED")
        node["accepted_proposal_id"] = pid
        self._record_event(node["proposal_routes"][pid], "SearchProposalAccepted",
                           key, payload=payload)
        self._commit_wave(node, pid)
        return True

    # -- closure and credit ----------------------------------------------

    def _seal(self, node: dict, accepted: str, reason: str) -> None:
        """Give every outstanding proposal an explicit terminal disposition.

        INCLUDING THE SOURCE'S OWN. A source MINTS its candidate and holds it as
        `local_candidate` -- in neither `proposals_outstanding` nor
        `proposals_rejected` -- so a sealing pass over those two sets walked
        straight past the one proposal this node actually produced, and left
        `eligible_offer` set. A closed wave then still had a node advertising an
        active offer, which is the same class of defect as an unresolved
        obligation reported as resolved.
        """
        for p in list(node["proposals_outstanding"]):
            node["proposal_disposition"][p] = (
                "accepted" if p == accepted else reason)
        node["proposals_outstanding"].clear()
        for p in node["proposals_rejected"]:
            node["proposal_disposition"].setdefault(p, "rejected")
        if accepted:
            node["proposal_disposition"][accepted] = "accepted"
        mine = node.get("local_candidate")
        if mine is not None:
            node["proposal_disposition"][mine.proposal_id] = (
                "accepted" if mine.proposal_id == accepted else reason)
            node["local_candidate"] = None
        # The wave is closed: this node is no longer offering anything, whether
        # its candidate won, lost or was never decided upon.
        node["eligible_offer"] = False
        # NON-VACUOUS SELF-CHECK. Measured over all three places a proposal can
        # be known, AFTER dispositioning, so it reads zero on correct behaviour
        # and fires the moment a future change adds a fourth place and forgets
        # to seal it. A counter that can only ever be zero proves nothing.
        known = set(node["proposal_routes"]) | set(node["proposals_rejected"])
        if mine is not None:
            known.add(mine.proposal_id)
        if any(p not in node["proposal_disposition"] for p in known):
            C.incr("UNDISPOSITIONED_LOCAL_PROPOSALS")

    def _commit_wave(self, node: dict, pid: str) -> None:
        """Close the wave AFTER an accepted settlement, never on a proposal.

        The commit and the cancellations are COMMANDS. They travel down and each
        edge records its one terminal, but the credit those edges carry is not
        reclassified here: a child may already have consumed credit, opened
        descendants or transferred allocations further down, and only the child
        knows. See `deliver_search_ack`.
        """
        key = node["search_key"]
        win = node["proposal_routes"][pid]
        node["status"] = "COMMITTED"
        node["terminal_signal_sent"] = True
        node["wave_cancelled"] = True
        self._emit_terminal("SearchCommitted", key, win,
                            node["child_targets"].get(win, ""), proposal_id=pid)
        for c in list(node["children_outstanding"]):
            if c == win:
                continue
            self._emit_terminal("SearchCancelled", key, c,
                                node["child_targets"].get(c, ""),
                                reason="wave_committed", proposal_id=pid)
        # Only reserve this node never transferred may be written off here.
        node["cancelled_credit"] += node["local_reserve"]
        node["local_reserve"] = 0.0
        self._seal(node, pid, "cancelled")
        self._reconcile_closed_children(node)

    def _reconcile_closed_children(self, node: dict) -> None:
        """Close child edges whose outcome the ORGAN ALREADY RECORDS.

        THE DEFECT THIS ANSWERS. A node that closes its wave commands each
        outstanding child and then waits for that child's acknowledgement. A
        child whose own wave is ALREADY closed never sends one: the command
        arrives on an edge that is neither its adopted parent edge nor one of
        its children -- because it COALESCED that edge as a duplicate -- so it
        is refused as an unauthenticated control, correctly, and the commanding
        parent waits forever. Measured on a complete graph, three nodes
        including the ROOT finished with `children_outstanding` non-empty and
        no further message could ever arrive.

        Waiting for a message that cannot come is the failure mode the closure
        invariant exists to forbid: a terminal claim may not be inferred from
        the ABSENCE of a message. So this does not infer anything. It reads the
        edge's recorded terminal -- immutable evidence the emitting unit already
        wrote through `_record_terminal`, carrying the refund it returned -- and
        closes the allocation against THAT. An edge with no recorded outcome is
        left outstanding, because for that edge there is genuinely no proof.

        This introduces no second lifecycle registry. `search_edge_lifecycle`
        is the existing canonical record and remains the only source of truth.
        """
        o = self._organ
        if o is None:
            return
        for edge in sorted(node["children_outstanding"]):
            # THE CHILD'S ANSWER, from the channel only a child can fill.
            # Reading the legacy projection here meant reading a store the
            # PARENT also wrote, so this loop kept finding the parent's own
            # command where a child's evidence was required and rejecting it
            # below -- 810 times per suite run. The rejection was correct; the
            # store was the wrong place to ask.
            rec = o.search_edge_lifecycle.get(edge)
            if rec is None or rec.get("accepted_outcome") is None:
                continue                    # no evidence: it stays open
            if edge in node["child_confirmed"]:
                continue
            first = rec["accepted_outcome"]
            if first.from_unit == self.unit_id:
                # MY OWN COMMAND IS NOT THE CHILD'S EVIDENCE. Closing against a
                # terminal I emitted downward is precisely "a parent classifying
                # credit a child never confirmed" -- the defect an active
                # specification forbids, and which caught this function's first
                # version. The liability stays open and is counted as unproven.
                C.incr("TERMINALS_WITH_UNRECONCILED_CHILDREN")
                continue
            per = node["child_allocations"].get(edge, 0.0)
            refund = float(getattr(first, "refund", 0.0) or 0.0)
            refund = max(0.0, min(refund, per))
            node["child_confirmed"][edge] = (refund, per - refund)
            node["children_outstanding"].discard(edge)
            node["children_completed"].add(edge)
            node["child_allocations_in_flight"] = max(
                0.0, node["child_allocations_in_flight"] - per)
            node["cancelled_credit"] += refund
            node["child_refunds_received"] += refund
            C.incr("CHILD_EDGES_RECONCILED_FROM_EVIDENCE")
        # NC-3 JOIN. A closing root discharged synchronously here would
        # otherwise sit in CLOSING with nothing outstanding, waiting for a
        # `_continue_after_child` that already happened.
        self._settle_closure_if_complete(node)

    def _close_wave_from_parent(self, node: dict, kind: str, pid: str) -> None:
        """A commit or cancellation arrived from my adopted parent.

        Routed hop by hop through THIS node's own mappings. A root that wrote
        directly to a distant source edge would be using organ-global telemetry
        as a shortcut, not local routing.
        """
        key = node["search_key"]
        if node["wave_cancelled"]:
            return                              # replay: idempotent
        # THE CONTROL IS APPLIED HERE, EXACTLY ONCE. The `wave_cancelled` guard
        # above is the exactly-once rule: a replayed command returns before
        # reaching this point, so application and its counter cannot double.
        C.incr("PARENT_CONTROLS_APPLIED")
        node["terminal_signal_sent"] = True
        node["wave_cancelled"] = True
        win = node["proposal_routes"].get(pid) if pid else None
        if kind == "SearchCommitted":
            node["status"] = "COMMITTED"
            node["accepted_proposal_id"] = pid or node["accepted_proposal_id"]
        else:
            node["status"] = "CLOSED"
        if win is not None:
            self._emit_terminal(kind, key, win, node["child_targets"].get(win, ""),
                                proposal_id=pid)
        for c in list(node["children_outstanding"]):
            if c == win:
                continue
            self._emit_terminal("SearchCancelled", key, c,
                                node["child_targets"].get(c, ""),
                                reason="wave_closed", proposal_id=pid)
        node["cancelled_credit"] += node["local_reserve"]
        node["local_reserve"] = 0.0
        self._seal(node, pid if kind == "SearchCommitted" else "",
                   "need_closed" if kind == "SearchNeedClosed" else "cancelled")
        self._reconcile_closed_children(node)
        self._acknowledge_to_parent(node)

    def _acknowledge_to_parent(self, node: dict) -> None:
        """Report to my parent EXACTLY what became of the credit it sent me.

        Only sent once every child of mine has itself acknowledged, so what I
        report is evidence rather than a guess about work still in flight.
        """
        if node["ack_sent"] or node["children_outstanding"]:
            return
        to = node["adopted_parent_sender"]
        if not to:
            node["ack_sent"] = True
            return
        refund = node["local_reserve"] + node["cancelled_credit"]
        consumed = max(0.0, node["incoming_allocation"] - refund)
        node["ack_sent"] = True
        node["local_reserve"] = 0.0
        node["cancelled_credit"] = 0.0
        node["returned_to_parent"] += refund
        node["consumed_credit"] = consumed
        edge = node["adopted_parent_edge"]
        self.outbox.append((to, ("__search_ack__", node["search_key"],
                                 edge, refund, consumed)))
        # THE ACK IS THIS NODE'S CHILD-OWNED COMPLETION OUTCOME, and it is
        # recorded as one. It is emitted only here, and the guard above is what
        # earns it: `children_outstanding` must be empty, so every descendant
        # liability has already reconciled before this node claims its own
        # incoming edge is answerable. That is the difference between answering
        # a command and completing it.
        #
        # `_record_outcome` -- not `_emit_terminal` -- because the message
        # itself already travels as `__search_ack__` on the wire and is
        # authenticated at the far end by `deliver_search_ack` against
        # `child_targets`. Emitting a second Terminal would put two messages on
        # one edge for one fact.
        self._record_outcome(Terminal(
            "SearchCompleted", node["search_key"], edge, refund, consumed,
            self.unit_id, to, "control_applied", node["accepted_proposal_id"] or ""))
        C.incr("PARENT_CONTROLS_WITH_CHILD_OWNED_COMPLETION")

    def deliver_search_ack(self, key: SearchKey, edge_id: str, refund: float,
                           consumed: float, sender: Any = _UNSPECIFIED_SENDER):
        """A child's closure evidence. NOT a terminal.

        The edge's single terminal is the commit or cancellation command that
        travelled DOWN it; this is what came back. Until it arrives the parent
        may not classify that allocation at all -- writing it off as cancelled
        while the child accounts the same credit as consumed produces two
        ledgers that each balance and together describe incompatible histories.
        """
        node = self.canonical_searches.get(key)
        if node is None:
            C.incr("ORPHANED_SEARCH_EDGES")
            return None
        per = node["child_allocations"].get(edge_id)
        if per is None:
            C.incr("UNOWNED_PROPOSAL_ROUTES")
            return None
        # ONLY THE CHILD THAT HOLDS THE ALLOCATION MAY CLOSE IT. Without this, a
        # neighbour can settle somebody else's branch: complete the edge, move
        # its credit and drive the search onward. That is the proposal-route
        # forgery 2A removed, committed through accounting instead.
        if not _authenticated(sender, node["child_targets"].get(edge_id)):
            C.incr("UNAUTHENTICATED_SEARCH_ACKS")
            self._record_event(edge_id, "SearchProposalRejected", key,
                               reason="ack_sender_not_child_target")
            return None
        if edge_id in node["child_confirmed"]:
            return None                          # replay: idempotent
        # VALIDATE THE RAW CLAIM, BEFORE ANY NORMALIZATION.
        #
        # Clamping first and checking afterwards converts a detected violation
        # into a state transition: the values are forced into a lawful-looking
        # shape, the mismatch is counted, and the protocol advances anyway. NaN
        # is worse -- every comparison against it is false, so it passes each
        # guard untouched and poisons the ledger without tripping anything. A
        # violation counter is evidence; it is not authorization to mutate.
        if not _evidence_reconciles(refund, consumed, per):
            C.incr("MALFORMED_SEARCH_ACKS")
            self._record_event(edge_id, "SearchProposalRejected", key,
                               reason="ack_does_not_reconcile")
            return None
        node["child_confirmed"][edge_id] = (refund, consumed)
        node["children_outstanding"].discard(edge_id)
        node["children_completed"].add(edge_id)
        node["child_allocations_in_flight"] -= per
        node["child_refunds_received"] += refund
        node["returned_credit"] = node["child_refunds_received"]
        node["consumed_credit"] += consumed
        if node["wave_cancelled"] or node["terminal_signal_sent"]:
            node["cancelled_credit"] += refund
            # NC-3 JOIN. A closing root sets `wave_cancelled` at initiation, so
            # this branch is the one its child completions take. Returning here
            # without the join left it in CLOSING with nothing outstanding.
            self._settle_closure_if_complete(node)
            self._acknowledge_to_parent(node)
            return None
        node["local_reserve"] += refund
        self._continue_after_child(node)
        return None

    def _echo_exhaustion(self, node: dict) -> None:
        """Report the correct failure: space closed, or credit ended first."""
        if node["terminal_signal_sent"]:
            return
        key = node["search_key"]
        budget_bound = (node["eligible_untried_routes"] > 0
                        and node["local_reserve"] < 1.0)
        node["status"] = "EXHAUSTED"
        node["terminal_signal_sent"] = True
        back = node["local_reserve"]
        node["returned_to_parent"] += back
        node["local_reserve"] = 0.0
        node["ack_sent"] = True
        if budget_bound:
            C.incr("SEARCH_BUDGET_EXHAUSTED")
            if self._organ is not None:
                self._organ.budget_exhaustion_records.append(key)
            self.escalations.append(
                f"search budget exhausted for {key}: "
                f"{node['eligible_untried_routes']} eligible routes untried")
            self._emit_terminal("SearchBudgetExhausted", key,
                                node["adopted_parent_edge"],
                                node["adopted_parent_sender"], refund=back)
            return
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
                            node["adopted_parent_sender"], refund=back)

    def _close_need_satisfied_elsewhere(self, node: dict) -> None:
        """This root's obligation generation was retired. Close it causally.

        WHY A ROOT REACHES HERE. `settle_search_offer` refuses any proposal
        whose `open_needs[slot]` no longer names this root's `need_id`
        (`wrong_need_generation`). Once that happens the root can never settle
        anything again, whatever arrives on it. Before this existed
        `_settle_pending_roots` reached such a root and executed a bare
        `continue`: the root stayed OPEN, its descendants kept `eligible_offer`,
        `local_candidate` and `proposals_outstanding` forever, and its parent's
        committed credit stayed permanently in flight. Measured at
        `_damaged(3, density=0.6)` seed 5: three abandoned roots holding 18.0
        credit on a run that reached quiescence with an empty scheduler.

        THIS IS INITIATION ONLY. The descendant machinery already exists:
        `_close_wave_from_parent` applies the control exactly once, cascades to
        its own children through its own `child_targets`, seals with reason
        `need_closed`, reconciles and acknowledges upward. What was missing was
        an emitter.

        `_close_wave_from_parent` is deliberately NOT reused here. It sets
        `CLOSED` immediately, and a root that closed before its descendants
        answered would satisfy "closes only after descendant outcomes" by
        accident. The root enters CLOSING and leaves it only when the join
        completes -- which is `_settle_closure_if_complete`, driven by real
        child evidence and never by a timer or by silence.

        COMMITTED IS NOT OVERLOADED. This root accepted no proposal and must not
        claim it did.
        """
        if node.get("closure_reason") or node["wave_cancelled"] \
                or node["terminal_signal_sent"]:
            C.incr("DUPLICATE_NEED_CLOSURE_APPLICATIONS")
            return                          # idempotent: initiation happens once
        key = node["search_key"]
        # Bound to the exact obligation, not merely to the slot. A later
        # generation mints a different `need_id` and therefore a different
        # SearchKey, so this closure can never be mistaken for that one's.
        node["closure_reason"] = "need_satisfied_elsewhere"
        node["closure_need_id"] = key.need_id
        node["closure_generation"] = key.work_item_generation
        node["status"] = "CLOSING_NEED_SATISFIED_ELSEWHERE"
        node["wave_cancelled"] = True
        node["terminal_signal_sent"] = True
        C.incr("ALTERNATE_SATISFIED_OPEN_ROOTS")
        C.incr("NEED_CLOSURE_CASCADES_INITIATED")
        # A DESCENDANT LEARNS THAT THE OBLIGATION IS GONE, not that its
        # candidate lost. `_seal` records `need_closed` only when the inbound
        # kind is `SearchNeedClosed`, so initiating with `SearchCancelled` would
        # erase the one fact that separates the two.
        for child in sorted(node["children_outstanding"]):
            self._emit_terminal("SearchNeedClosed", key, child,
                                node["child_targets"].get(child, ""),
                                reason="need_satisfied_elsewhere")
            C.incr("NEED_CLOSURE_CONTROLS_EMITTED")
        # Only reserve this node never transferred may be written off here. A
        # child's allocation stays outstanding until the child's own evidence
        # returns it.
        node["cancelled_credit"] += node["local_reserve"]
        node["local_reserve"] = 0.0
        self._seal(node, "", "need_closed")
        self._reconcile_closed_children(node)
        self._settle_closure_if_complete(node)

    def _close_roots_for_retired_need(self, nid: str) -> None:
        """Close every canonical root serving a need generation just retired.

        LOCAL AND EXACT. Matches on `need_id`, which is `unit:slot:activation`
        and therefore names one obligation generation at one unit. A later
        generation has a different `need_id` and a different SearchKey, so this
        can never reach forward into a successor root.

        Called at the moment of retirement rather than on a later step, because
        a later step may never come: the unit whose need this was may have no
        further messages, and closure inferred from -- or delayed until -- an
        empty scheduler is exactly what specification 23 forbids.
        """
        for key, node in list(self.canonical_searches.items()):
            if key.origin_unit != self.unit_id or key.need_id != nid:
                continue
            if node["status"] not in ("OPEN", "PROPOSAL_PENDING"):
                continue
            self._close_need_satisfied_elsewhere(node)

    def _settle_closure_if_complete(self, node: dict) -> None:
        """The JOIN. CLOSING becomes CLOSED only on descendant evidence.

        No timer, no retry, no completion inferred from silence. A child that
        never answers leaves this root in CLOSING with its edge explicitly
        unresolved, which is a visible unfinished obligation rather than a false
        closure and a false refund.
        """
        if node["status"] != "CLOSING_NEED_SATISFIED_ELSEWHERE":
            return
        if node["children_outstanding"] or node["child_allocations_in_flight"] > 0:
            return
        node["status"] = "CLOSED"
        C.incr("ROOTS_CLOSED_BY_ALTERNATE_SATISFACTION")
        self._acknowledge_to_parent(node)

    def _continue_after_child(self, node: dict) -> None:
        """One child finished. Widen, wait, or report -- decided locally."""
        if node["status"] == "CLOSING_NEED_SATISFIED_ELSEWHERE":
            # A closing root does not widen and does not report exhaustion. The
            # only question left is whether the join is complete.
            self._settle_closure_if_complete(node)
            return
        if node["status"] not in ("OPEN", "PROPOSAL_PENDING"):
            return
        if node["terminal_signal_sent"] or node["children_outstanding"]:
            return
        if node["proposals_outstanding"] or node["eligible_offer"]:
            # A candidate is in flight toward the origin. Reporting exhaustion
            # now would claim the space is closed while an unresolved proposal
            # is still travelling.
            return
        if node["eligible_untried_routes"] > 0 and node["local_reserve"] >= 1.0:
            self._expand_canonical(node)        # widen: the round is complete
            if node["children_outstanding"]:
                return
        self._echo_exhaustion(node)

    def _release_child(self, node: dict, edge_id: str) -> None:
        """PRESERVED, UNUSED, and instrumented.

        This is what Commit 2 did at every commit and cancellation: move a
        child's entire allocation from in-flight to cancelled with no evidence
        from the child. It is kept as the instrumented name for the prohibited
        operation, in the same style as the organ's other forbidden-operation
        stubs. Nothing in the runtime calls it.
        """
        if edge_id not in node["children_outstanding"]:
            return
        per = node["child_allocations"].get(edge_id, 0.0)
        C.incr("UNSUPPORTED_CHILD_CANCELLATION_CREDIT")
        node["children_outstanding"].discard(edge_id)
        node["children_completed"].add(edge_id)
        node["child_allocations_in_flight"] -= per
        node["cancelled_credit"] += per

    def _deliver_terminal_message(self, terminal: Terminal, *,
                                  sender: Any) -> None:
        """Deliver the full wire object without discarding identity fields.

        AUTHENTICATED AND DIRECTION-BOUND. A terminal naming the adopted parent
        edge used to close the wave with no proof of who sent it, so any
        neighbour could forge closure from a structurally valid edge id. Which
        way a control may travel is part of its meaning: a wave-closing command
        comes DOWN from the adopted parent, a search outcome comes UP from a
        child, and neither is legitimate in the other direction.

        `from_unit` and `to_unit` are written by the sender. They are claims, and
        they are checked AGAINST the route the message actually took rather than
        trusted in place of it -- otherwise they are a second, forgeable
        identity channel.
        """
        key = terminal.search_key
        edge_id = terminal.edge_id
        kind = terminal.kind
        refund = terminal.refund
        proposal_id = terminal.proposal_id
        from_unit = terminal.from_unit
        to_unit = terminal.to_unit
        if kind in NONTERMINAL_KINDS:
            # A proposal reaching the terminal aggregator is the V1 defect
            # exactly: it would mark the node ANSWERED and cancel its siblings
            # on mere evidence. Counted, refused, and never accounted.
            C.incr("PREMATURE_PROPOSAL_CANCELLATIONS")
            return
        node = self.canonical_searches.get(key)
        if node is None:
            self._admit_prearrival_parent_control(terminal, sender=sender)
            return
        if sender is not HARNESS_DELIVERY:
            if from_unit and from_unit != sender:
                C.incr("UNAUTHENTICATED_TERMINAL_CONTROLS")
                return
            if to_unit and to_unit != self.unit_id:
                C.incr("UNAUTHENTICATED_TERMINAL_CONTROLS")
                return
        if edge_id == node["adopted_parent_edge"]:
            if kind not in PARENT_CONTROL_KINDS:
                C.incr("UNAUTHENTICATED_TERMINAL_CONTROLS")
                return
            if not _authenticated(sender, node["adopted_parent_sender"]):
                C.incr("UNAUTHENTICATED_TERMINAL_CONTROLS")
                return
            o = self._organ
            rec = (o.search_edge_lifecycle.get(edge_id)
                   if o is not None else None)
            if rec is not None and rec.get("accepted_control") is not None:
                result = self._record_control(terminal)
                state = rec.get("prearrival_control_state")
                if result == "conflict":
                    if state in ("held", "applied", "rejected"):
                        C.incr("PREARRIVAL_CONTROL_CONFLICTS")
                    return
                if state == "held":
                    self._apply_recorded_parent_control(node, edge_id=edge_id)
                    return
                if state in ("applied", "rejected"):
                    C.incr("PREARRIVAL_CONTROL_REPLAYS")
                    return
            if kind == "SearchCommitted":
                if not self._knows_proposal(node, proposal_id):
                    # AUTHENTICATION ANSWERS WHO, NOT WHETHER THE COMMAND MEANS
                    # ANYTHING. Committing a proposal this node never saw leaves
                    # no route to the supposed winner, so the wave would close
                    # around a candidate that never existed on this branch.
                    C.incr("UNKNOWN_COMMIT_PROPOSALS")
                    return
                if not self._commit_eligible(node, proposal_id):
                    # KNOWN, AND ALREADY DECIDED.
                    C.incr("COMMIT_OF_RESOLVED_PROPOSAL")
                    return
            self._close_wave_from_parent(node, kind, proposal_id)
            return
        if edge_id in node["child_allocations"]:
            if kind not in CHILD_OUTCOME_KINDS:
                # A child cannot command its parent to close the wave.
                C.incr("UNAUTHENTICATED_TERMINAL_CONTROLS")
                return
            if not _authenticated(sender, node["child_targets"].get(edge_id)):
                C.incr("UNAUTHENTICATED_TERMINAL_CONTROLS")
                return
        else:
            # Neither my adopted parent edge nor an edge I opened.
            C.incr("UNAUTHENTICATED_TERMINAL_CONTROLS")
            return
        if edge_id in node["children_completed"]:
            return                              # replay: idempotent, no refund
        if edge_id not in node["children_outstanding"]:
            return
        per = node["child_allocations"].get(edge_id, 0.0)
        # ONE STANDARD OF EVIDENCE, BOTH DOORS. This writes the same
        # `child_confirmed` ledger as `deliver_search_ack`, so clamping here
        # while that path fails closed let an authenticated child launder a
        # negative, oversized, NaN or infinite refund by choosing the terminal.
        if not _evidence_reconciles(refund, per - refund, per):
            C.incr("MALFORMED_TERMINAL_EVIDENCE")
            self._record_event(edge_id, "SearchProposalRejected", key,
                               reason="terminal_evidence_does_not_reconcile")
            return
        credited = refund
        # A terminal that ends a child edge IS the child's own evidence about
        # that allocation: it carries what came back and, by difference, what
        # the subtree used. Recorded in the same ledger an explicit
        # acknowledgement would fill, so both routes are auditable alike.
        node["child_confirmed"][edge_id] = (credited, per - credited)
        node["children_outstanding"].discard(edge_id)
        node["children_completed"].add(edge_id)
        node["child_allocations_in_flight"] -= per
        node["consumed_credit"] += per - credited
        node["child_refunds_received"] += credited
        node["returned_credit"] = node["child_refunds_received"]
        node["local_reserve"] += credited
        # The parent OBSERVES the child's closure, so the child's edge carries
        # its one terminal outcome even when the emitting side is a harness.
        #
        # `_record_outcome` BY NAME, not through the classifier. This Terminal
        # is authored by the child -- `from_unit` is the child target and
        # `to_unit` is this parent -- and it is child evidence whichever kind it
        # carries. Routing it through a generic dispatcher would make the
        # correctness of an observation depend on a lookup succeeding, when the
        # authentication above has already established every fact that matters:
        # the sender, the edge, the key, the destination and the evidence.
        self._record_outcome(Terminal(kind, key, edge_id, credited, 0.0,
                                      node["child_targets"].get(edge_id, ""),
                                      self.unit_id, "", proposal_id))
        if node["wave_cancelled"] or node["terminal_signal_sent"]:
            self._settle_closure_if_complete(node)      # NC-3 join, same reason
            self._acknowledge_to_parent(node)
            return
        self._continue_after_child(node)

    def deliver_terminal(self, key: SearchKey, edge_id: str, kind: str,
                         refund: float = 0.0, proposal_id: str = "",
                         sender: Any = _UNSPECIFIED_SENDER,
                         from_unit: Optional[str] = None,
                         to_unit: Optional[str] = None) -> None:
        """Compatibility seam for direct callers; live dispatch keeps Terminal.

        The public signature is intentionally unchanged. Direct callers never
        supplied ``handling_cost`` or ``reason``, so their equivalent wire
        object uses the historical defaults. ``Unit.step`` calls the internal
        full-object handler and therefore preserves every identity field.
        """
        terminal = Terminal(
            kind, key, edge_id, refund, 0.0,
            from_unit or "", to_unit or "", "", proposal_id,
        )
        self._deliver_terminal_message(terminal, sender=sender)

    def replay_search_edge(self, key: SearchKey, edge_id: str) -> None:
        """Exact replay of an already-ANSWERED edge is a no-op.

        Answered means the canonical lifecycle holds an accepted outcome. An
        edge that has only been commanded has not been answered, and replaying
        it must still reach `deliver_search`.
        """
        o = self._organ
        _lc = (o.search_edge_lifecycle.get(edge_id) or {}) if o is not None else {}
        if _lc.get("accepted_outcome") is not None:
            return
        self.deliver_search(key, edge_id, 0.0)

    def would_refuse_everything(self, producers: Iterable[str]) -> bool:
        prod = set(producers)
        return bool(prod) and prod <= self.refused

    def _repair_context(self, slot: int) -> Optional[SearchContext]:
        """Compile THIS unit's local evidence into a set of constraints.

        Every field comes from state this unit already holds for its own
        operation. Nothing is read from the organ, from a provider index, or
        from any other unit:

            causally_refused_sources   `self.refused`  -- what I refused, and why
                                       I refused it, is mine
            must_differ_from_suppliers my OTHER bonds, so a replacement cannot
                                       duplicate a supplier I already depend on
            maximum_supplier_cost      `self.repair_budget`, a supplier COST
                                       ceiling
            cooldown_excluded_suppliers`self.memory.cooldown`, my own failure
                                       memory
            constraint_generation      `self.local_activations`, my own reopen
                                       count -- monotonic and local
            policy_snapshot            the ordered record of what I am enforcing

        EVERY SET IS AN EXCLUSION SET. There is no field in which a PERMITTED
        supplier could be named, so the answer cannot travel inside the context
        even by accident. That is a structural property, not a convention: a
        candidate reading this context learns my LIMITS and never my SOLUTION.

        Domain independence and prohibited motifs are deliberately absent, for
        the reason `SearchContext` already documents -- they are computed at
        settlement from origin-local capabilities, and shipping the origin's
        occupied domains to every reachable candidate is the disclosure
        `TARGET_TOPOLOGY_LEAKAGE_EVENTS` exists to forbid.
        """
        if slot >= len(self.capability.accepts):
            C.incr("ROOT_CONTEXT_REFUSALS")
            return None
        siblings = frozenset(b.supplier for s, b in self.bonds.items()
                             if s != slot)
        cooldown = frozenset(self.memory.cooldown)
        return SearchContext(
            causally_refused_sources=frozenset(self.refused),
            must_differ_from_suppliers=siblings,
            maximum_supplier_cost=float(self.repair_budget),
            cooldown_excluded_suppliers=cooldown,
            constraint_generation=int(self.local_activations),
            policy_snapshot=("distinct_supplier", "causal_refusal",
                             "cost_ceiling", "cooldown"))

    def _open_repair_root(self, slot: int, nid: str) -> Optional[dict]:
        """Originate ONE canonical root for a deficit this unit just suffered.

        THE IDENTITY IS DERIVED, NOT ASSIGNED. `SearchKey.build` hashes the
        complete context, so the same deficit under the same constraints yields
        the same key -- and `open_canonical_search` already refuses a second
        node per key. Deduplication is therefore a property of how the
        obligation is NAMED rather than a separate mechanism, and a separate
        mechanism would have had to know about the other roots, which is
        exactly the global knowledge this design forbids.

        A root has NO adopted parent edge and NO parent sender. It is the one
        node in a wave that answers to nobody, which is also why it is the one
        node that may settle.
        """
        if self.unit_id in (ENV, SINK):
            # The boundary holds no repair authority, so it originates nothing.
            C.incr("ROOT_CONTEXT_REFUSALS")
            return None
        context = self._repair_context(slot)
        if context is None:
            return None
        key = SearchKey.build(
            need_id=nid, work_item_generation=int(self.item_seq),
            origin_unit=self.unit_id, origin_slot=slot,
            wanted_type=self.capability.accepts[slot], context=context)
        if key in self.canonical_searches:
            # The same deficit under the same constraints. Not an error and not
            # a second root: the derived identity converged, which is the point.
            C.incr("DUPLICATE_CANONICAL_ROOTS")
            return self.canonical_searches[key]
        credit = (ROOT_SEARCH_CREDIT_OVERRIDE
                  if ROOT_SEARCH_CREDIT_OVERRIDE is not None
                  else REPAIR_SEARCH_BUDGET)
        node = self.open_canonical_search(
            key, parent_edge="", allocation=float(credit), parent_sender="",
            context=context, lineage=(self.unit_id,))
        C.incr("CANONICAL_ROOTS_CREATED")
        C.incr("SEARCH_CREDIT_ISSUED")
        C.incr("REPAIR_REOPENS_WITH_CANONICAL_ROOT")
        return node

    def _settle_pending_roots(self) -> None:
        """Decide the searches I ORIGINATED, once this round's arrivals are in.

        Driven from `step`, deliberately, and not from `deliver_proposal`. A
        whole delivery round lands before anything is decided, so competitors
        delivered in the same round actually race instead of the first one
        through the door winning by arrival order -- the property
        `test_arrival_order_alone_does_not_change_the_outcome` exists to hold.

        This is a TRIGGER, not an authority. `settle_search_offer` re-checks
        every precondition itself: my ownership of the search, payload
        integrity, the context digest, the slot's state, registration on a real
        child edge, and the need generation. Nothing here can settle anything
        that function would refuse, and a proposal is examined in a stable
        order so the decision does not depend on dictionary iteration.
        """
        for key in sorted(self.canonical_searches, key=str):
            if key.origin_unit != self.unit_id:
                continue
            node = self.canonical_searches[key]
            if node["status"] not in ("OPEN", "PROPOSAL_PENDING"):
                continue
            # THE OBLIGATION GENERATION, NOT THE SLOT.
            #
            # This was `if key.origin_slot in self.bonds: continue` -- a silent
            # skip that abandoned the root. Two things were wrong with it. It
            # answered nothing: the root stayed open holding its descendants'
            # liability forever. And it asked the wrong question: measured at
            # `_damaged(3, density=0.6)`, one of the three abandoned roots had
            # NO BOND AT ALL, and the two that were bonded were already caught
            # by the generation test. The bond is provenance for WHY the
            # generation retired; it is not the condition.
            #
            # `settle_search_offer` already refuses on exactly this predicate,
            # so a root that fails it can never settle anything again and is
            # owed a closure rather than a skip.
            if self.open_needs.get(key.origin_slot) != key.need_id:
                self._close_need_satisfied_elsewhere(node)
                continue
            if key.origin_slot in self.bonds:
                # Generation still live but the slot is occupied. Preserved as a
                # distinct guard: `settle_search_offer` would refuse with
                # `slot_already_bonded`, and closing here on a bond this root's
                # own settlement may have created would close a root that won.
                continue
            for pid in sorted(node["proposals_outstanding"]):
                payload = node["proposal_payloads"].get(pid)
                if payload is None or not payload.firm:
                    continue
                if self.settle_search_offer(payload):
                    C.incr("ELIGIBLE_PROPOSALS_COMMITTED")
                    break

    def _recruit_prerequisites(self) -> None:
        """Originate a root for each of MY unmet slots. Bounded and idempotent.

        Called only by a unit that was asked to serve and found itself unmet.
        Bounded three ways, all local: a unit with no repair budget recruits
        nothing; a slot already carrying an open need is skipped, so a repeated
        arrival cannot mint a second root; and each root it does open is itself
        a bounded search with its own credit ledger.
        """
        if self.repair_budget <= 0 or self.unit_id in (ENV, SINK):
            return
        for slot in sorted(self.unmet()):
            if slot in self.open_needs:
                continue
            self._emit_need(slot)

    def _emit_need(self, slot: int) -> None:
        """LOCAL BOUNDED ROUTING, not a broadcast.

        REPAIR IS ORIGINATED AS A CANONICAL SINGLE-FLIGHT ROOT. The legacy
        `Need` wave is NOT run alongside it: two active searches for one
        obligation, each unaware the other may settle it, is the migration
        hazard `DUAL_REPAIR_SEARCHES` exists to detect, so the legacy path is
        REPLACED here rather than supplemented. Formation is untouched --
        commissioning never reaches this function, which is why
        `_send_to_frontier` remains and stays correct for the path that does
        use it.

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
        # TWO ACTIVE SEARCHES FOR ONE OBLIGATION is the migration hazard: the
        # legacy Need wave and a canonical Single-Flight root both hunting the
        # same slot, each unaware the other may settle it. Detected here, at the
        # only place a legacy repair search is opened.
        if any(k.origin_unit == self.unit_id and k.origin_slot == slot
               and n["status"] in ("OPEN", "PROPOSAL_PENDING")
               for k, n in self.canonical_searches.items()):
            C.incr("DUAL_REPAIR_SEARCHES")
        if self._open_repair_root(slot, nid) is None:
            # Origination refused -- the boundary, or a slot this unit does not
            # have. FALLING BACK TO THE LEGACY WAVE HERE WOULD BE WRONG: it
            # would run the mechanism whose refusal was just recorded, and the
            # refusal reasons are exactly the cases that hold no repair
            # authority. The obligation stays open and is reported, not routed.
            self.open_needs.pop(slot, None)
            self._search.pop(nid, None)
            self._close_roots_for_retired_need(nid)

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
            # LEGACY REPAIR TRAFFIC. `_send_to_frontier` is reached only from a
            # repair reopen or its widening -- commissioning needs create no
            # `_search` ledger, so `widen` never selects them -- which makes
            # this the exact denominator Commit 3 must drive to zero.
            C.incr("LEGACY_REPAIR_NEED_MESSAGES")
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
        # NC-3. The LEGACY wave just retired this obligation generation. Any
        # canonical root serving the same generation can no longer settle
        # anything -- `settle_search_offer` would refuse it with
        # `wrong_need_generation` -- so it is owed a closure here, at the moment
        # of retirement, rather than on some later step that may never come.
        # Measured: `reconcile.12:0:1` was retired on this path and its unit was
        # never stepped again, so a closure driven only from
        # `_settle_pending_roots` left it abandoned.
        self._close_roots_for_retired_need(nid)
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
                key, edge_id, allocation, lineage = msg[1:5]
                context = msg[5] if len(msg) > 5 else None
                self.deliver_search(key, edge_id, allocation, lineage, sender,
                                    context)
                continue
            if isinstance(msg, tuple) and msg and msg[0] == "__proposal__":
                _, key, edge_id, payload = msg
                self.deliver_proposal(key, edge_id, payload, sender)
                continue
            if isinstance(msg, tuple) and msg and msg[0] == "__proposal_rejected__":
                _, key, edge_id, pid, reason = msg
                self.deliver_proposal_rejected(key, edge_id, pid, reason, sender)
                continue
            if isinstance(msg, tuple) and msg and msg[0] == "__search_ack__":
                _, key, edge_id, refund, consumed = msg
                self.deliver_search_ack(key, edge_id, refund, consumed, sender)
                continue
            if isinstance(msg, Terminal):
                # The immediate sender travels with a terminal exactly as it
                # does with a proposal. Dropping it here left wave closure
                # authenticated by nothing but an edge id any neighbour can name.
                self._deliver_terminal_message(msg, sender=sender)
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
        self._settle_pending_roots()
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

@dataclass(frozen=True)
class ScheduledEvent:
    """One scheduling decision, with a stable identity.

    The ready queue held bare `(uid, kind)` tuples, so "the queue is empty" was
    the only available evidence about dispatch. An empty queue proves REMOVAL,
    not dispatch: a resume could drop event A, dispatch event B twice, end with
    an empty queue and hide the difference in an aggregate count. Event-level
    identity is the only way to tell those apart.
    """
    event_id: str
    unit_id: str
    kind: str


@dataclass
class PausedRun:
    """A work item stopped mid-flight, with its complete live continuation.

    Carrying only a SearchKey would make `resume` a euphemism for "start a new
    work item and look at the old one's root": `run_item` resets `_payload`,
    `_produced`, `item_seq`, `events_dispatched`, `ready`, `_queued` and
    `_unmet_state`, which changes provenance and `settled_item`, drops queued
    non-message events, and makes a restarted item look like the continuation of
    the paused wave.
    """
    payload: Any
    item_seq: int
    produced: dict
    ready: Any
    queued: set
    msg_pending: set
    unmet_state: dict
    events_dispatched: int
    root: Optional[SearchKey]


_KEEP_PAYLOAD = object()


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
        # ONE record per edge, two semantically distinct channels.
        self.search_edge_lifecycle: dict = {}
        # NONTERMINAL edge telemetry: proposals and control records. Held apart
        # from terminals so a proposal can never be stored as the outcome that
        # ended an edge.
        self.search_edge_events: dict = {}
        # Two ends disagreeing about how one edge ended. Preserved rather than
        # dropped: it is a finding.
        self.search_edge_terminal_conflicts: list = []
        self.space_exhaustion_proofs: list = []
        self.budget_exhaustion_records: list = []
        # HARNESS TELEMETRY, event_id -> {unit_id, event_kind,
        # work_item_generation, scheduled_count, dispatch_count}. It RECORDS.
        # Nothing in scheduling reads it, so it cannot influence a dispatch
        # decision; it exists so exactly-once dispatch can be proved at event
        # level instead of inferred from an aggregate count.
        self.scheduler_event_log: dict = {}
        self._event_seq = 0
        for u in self.units.values():
            u._organ = self
        # Recipients that hold undelivered work. Maintained as messages are
        # delivered, so run_item never scans the organ to find them.
        self._msg_pending: set = set()
        # Last observed readiness per unit, for edge-triggered scheduling.
        self._unmet_state: dict = {}
        self._payload: Any = None
        self._produced: dict[str, Value] = {}
        from collections import deque
        self.ready: deque = deque()
        self._queued: set = set()
        self.item_seq = 0
        self.events_dispatched = 0
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
        self._start_item(payload)
        self._drive(max_events)
        return self._produced.get(SINK)

    def _start_item(self, payload: Any) -> None:
        """Begin a NEW work item generation and seed its ready queue."""
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

    def _drive(self, max_events: int, stop: Optional[Callable[[], bool]] = None) -> bool:
        """Dispatch until the queue drains, the cap is reached, or `stop` fires.

        `stop` is a HARNESS predicate. It is evaluated after a dispatch
        completes, decides nothing about routing or settlement, and cannot
        change what any unit does; it only says where a test driver may pause.
        """
        while self.ready and self.events_dispatched < max_events:
            ev = self.ready.popleft()
            uid, kind = ev.unit_id, ev.kind
            self._queued.discard((uid, kind))
            u = self.units.get(uid)
            if u is None:
                continue
            rec = self.scheduler_event_log.get(ev.event_id)
            if rec is not None:
                rec["dispatch_count"] += 1
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
            if stop is not None and stop():
                return True
        return False

    def _schedule(self, uid: str, kind: str) -> None:
        if uid in self.units and (uid, kind) not in self._queued:
            self._queued.add((uid, kind))
            self._event_seq += 1
            gen = getattr(self, "item_seq", 0)
            eid = f"{gen}:{uid}:{kind}:{self._event_seq}"
            # Telemetry only. Deduplication still keys on (uid, kind), exactly
            # as before, so scheduling behaviour is unchanged.
            self.scheduler_event_log[eid] = {
                "event_id": eid, "unit_id": uid, "event_kind": kind,
                "work_item_generation": gen,
                "scheduled_count": 1, "dispatch_count": 0}
            self.ready.append(ScheduledEvent(eid, uid, kind))

    # -- pause / resume: a TEST DRIVER, not protocol authority -----------

    def run_until_repair_root(self, unit_id: str, slot: int,
                              max_events: int = 3000,
                              payload: Any = _KEEP_PAYLOAD) -> Optional[PausedRun]:
        """Run a work item and stop as soon as a repair root exists and is OPEN.

        Why this exists: with several producers a CORRECT implementation may
        discover and settle a replacement during the very call that creates the
        root. A test that ran the search to completion and then demanded the
        search still be open would be a temporally impossible fixture, failing
        against the finished mechanism it is meant to exercise.

        `payload` defaults to the payload already loaded, because a resume must
        continue THIS item rather than introduce a new input mid-wave.
        """
        if payload is _KEEP_PAYLOAD:
            payload = self._payload
        found: dict = {}

        def _root_open() -> bool:
            u = self.units.get(unit_id)
            if u is None:
                return False
            for k, n in u.canonical_searches.items():
                if (k.origin_unit == unit_id and k.origin_slot == slot
                        and n["status"] == "OPEN"
                        and n["accepted_proposal_id"] is None
                        and not n["terminal_signal_sent"]):
                    found["root"] = k
                    return True
            return False

        self._start_item(payload)
        if not _root_open():
            self._drive(max_events, stop=_root_open)
        if "root" not in found:
            return None
        return PausedRun(payload=self._payload, item_seq=self.item_seq,
                         produced=self._produced, ready=self.ready,
                         queued=self._queued, msg_pending=self._msg_pending,
                         unmet_state=self._unmet_state,
                         events_dispatched=self.events_dispatched,
                         root=found["root"])

    def resume_paused_item(self, paused: PausedRun,
                           max_events: int = 3000) -> Optional[Value]:
        """Continue the SAME work item. A fresh `run_item` is not continuation.

        Nothing here starts a generation, recommissions, scans the organ, or
        makes a routing or settlement decision. It reinstalls the captured
        scheduler state and keeps dispatching.
        """
        self._payload = paused.payload
        self._produced = paused.produced
        self.item_seq = paused.item_seq
        self.ready = paused.ready
        self._queued = paused.queued
        self._msg_pending = paused.msg_pending
        self._unmet_state = paused.unmet_state
        self.events_dispatched = paused.events_dispatched
        self._drive(max_events)
        return self._produced.get(SINK)

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

    def read_legacy_projection(self, unit_id: str, need_id: str):
        """Instrumented name for reading `_search` AS A DECISION INPUT.

        `_search` survives as a one-way audit projection of canonical state. It
        may be read for diagnostics; it may never route, widen, settle, close or
        alter a canonical search. Nothing in the runtime calls this, so a
        non-zero LEGACY_PROJECTION_DECISION_READS means dual control returned.
        """
        C.incr("LEGACY_PROJECTION_DECISION_READS")
        u = self.units.get(unit_id)
        return None if u is None else u._search.get(need_id)

    def providers_of(self, type_: str) -> list:
        """Global provider knowledge. EVALUATOR ONLY - never reachable from a
        developmental decision, and every read is recorded."""
        C.incr("FULL_PROVIDER_INDEX_READS")
        # THE SAME EVENT UNDER THE NAME THE ORIGINATION SPECS MEASURE. One read
        # drives both counters rather than one being an untested synonym of the
        # other: `FULL_PROVIDER_INDEX_READS` is the historical name and stays,
        # `GLOBAL_PROVIDER_INDEX_READS` is what Commit 3 asserts against.
        C.incr("GLOBAL_PROVIDER_INDEX_READS")
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
