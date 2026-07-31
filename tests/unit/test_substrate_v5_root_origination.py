"""Commit 3: the live repair root originator.

PRE-REGISTERED BEFORE THE CORRESPONDING RUNTIME CHANGE. Strict xfail throughout.

WHY THIS FILE EXISTS. Single-Flight has a complete RELAY, a complete RECEIVER,
a complete CONTROL plane and a complete SETTLEMENT path. It has no ORIGINATOR.
`SearchKey.build` is never called from `substrate/v5.py`, and
`settle_search_offer` is never called from `substrate/v5.py` either, so a live
repair reopen produces a legacy `Need` wave and no canonical root at all:

    REPAIR_REOPENS_WITH_CANONICAL_ROOT = 0     against REPAIR_REOPENS > 0

The existing live-path and echo specifications say what a wave must do ONCE it
exists. They do not say where it may legitimately come from, and that is the
question this file exists to answer, because origination is where the two
failure modes of a developmental substrate live: a root minted from knowledge
the unit cannot legitimately hold, and a root minted twice for one deficit.

THE MECHANISM UNDER TEST: DEFICIT-TO-IDENTITY COMPILATION.

A unit that loses a supplier compiles its OWN local evidence -- the slot it
cannot fill, the sources it has causally refused, its sibling suppliers, its
cost ceiling, its cooldown set, its constraint generation -- into a
`SearchContext`, and derives a `SearchKey` from that context. The identity is a
pure function of locally held state.

That is the whole design, and its consequence is the property worth testing:
because the key is DERIVED rather than assigned, the same deficit under the
same constraints derives the same key, and the canonical-node rule that already
exists ("at most one node per SearchKey per unit") suppresses the duplicate for
free. Convergence without coordination. A counter-based or nonce-based root id
would have needed a separate deduplication mechanism, and that mechanism would
have needed to know about the other roots.

WHAT THE ORIGINATOR MAY KNOW: its identity, the slot, the wanted type, its own
refusal set, its own bonds, its own cooldown memory, its own budget.

WHAT IT MAY NOT KNOW, and what these tests attack: the replacement topology,
the winning provider, any global provider list, the expected route, or any
fixture-held causal label.

NEGATIVE CONTROLS ARE PAIRED THROUGHOUT. A runtime that originates nothing
passes every "must not" below, so each has a positive control that fails unless
origination actually works.
"""
from __future__ import annotations

import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "verification" / "phase3g"))

import pytest

import substrate.v5 as v5
from substrate.v5 import ENV, SINK, C, reset

import fixtures as F

PAYLOAD_A = "  Claim-77  "
PAYLOAD_B = "  Claim-78  "
SEEDS = tuple(range(60))

origination = pytest.mark.xfail(
    strict=True,
    reason="the live repair root originator is not implemented yet")


def _build_raw(n_auth=4, seed=7, density=0.8):
    caps = F._spine("alpha2") + F._spine("beta2") + F._spine("gamma2")
    for i in range(n_auth):
        caps.append(F.cap(f"au{i}", ("PX", "PX"), "AUTH", F.AUTHORISE,
                          1.0 + 0.1 * i, f"d.a{i}", "authorise", F.OK_PRICE))
    caps.append(F.cap("rn0", ("AUTH", "AUTH"), "RECON", F.RECONCILE,
                      1.0, "d.p", "reconcile", F.OK_AUTH))
    caps.append(F.cap("db0", ("RECON",), "VERDICT", F.DISBURSE,
                      1.0, "d.r", "disburse", F.OK_RECON))
    return F._organ(caps, random.Random(seed), density)


def _join(o, want="AUTH"):
    for u in o.units.values():
        if u.capability.accepts.count(want) == 2:
            return u
    return None


def _damaged(n_auth=4, density=0.8):
    """Seed-scanned then HARD ASSERTED. Never skips."""
    for seed in SEEDS:
        o = _build_raw(n_auth, seed, density)
        F.prepare(o)
        reset()
        o.commission()
        if not o.result_ok(o.run_item(PAYLOAD_A)):
            continue
        j = _join(o)
        if j is None or len(j.bonds) != 2:
            continue
        if len({b.supplier for b in j.bonds.values()}) != 2:
            continue
        slot = min(j.bonds)
        victim = j.bonds[slot].supplier
        o.units[victim].silent = True
        return o, j, slot, victim, seed
    raise AssertionError(
        "no formed independently-supplied join across the pre-registered seeds; "
        "failing to construct the structure is a failure of this "
        "specification, not a reason to skip it")


def _counter(name):
    assert name in C.d, (
        f"the runtime defines no {name} counter, so the behaviour it names "
        f"cannot be measured and this specification cannot be satisfied")
    return C[name]


def _roots(o):
    """Every canonical node a unit holds for a search IT originated."""
    return {(u.unit_id, k): n for u in o.units.values()
            for k, n in getattr(u, "canonical_searches", {}).items()
            if k.origin_unit == u.unit_id}


# ---------------------------------------------------------------------------
# 1. A real deficit originates exactly one root
# ---------------------------------------------------------------------------

@origination
def test_a_real_interior_deficit_originates_exactly_one_canonical_root():
    """THE SINGLE BOTTLENECK METRIC, measured on a live run.

    Not a harness drive: the damage is real, the reopen is reached through
    ordinary execution, and the root must appear without anything in the test
    naming a key, a route or a provider.
    """
    o, j, slot, victim, seed = _damaged(4)
    reset()

    o.run_item(PAYLOAD_B)

    assert C["REPAIR_REOPENS"] > 0, (
        "the damage produced no reopen, so this measures nothing")
    assert _counter("REPAIR_REOPENS_WITH_CANONICAL_ROOT") == C["REPAIR_REOPENS"], (
        f"{C['REPAIR_REOPENS'] - _counter('REPAIR_REOPENS_WITH_CANONICAL_ROOT')} "
        f"reopen(s) created no canonical root")
    assert _counter("CANONICAL_ROOTS_CREATED") >= 1
    assert _counter("DUPLICATE_CANONICAL_ROOTS") == 0
    roots = _roots(o)
    assert roots, "no unit holds a canonical node for a search it originated"
    for (uid, key), node in roots.items():
        assert key.origin_unit == uid
        assert node["adopted_parent_edge"] == "", (
            f"{uid} originated a root that claims an adopted parent edge "
            f"{node['adopted_parent_edge']!r}; a root has no parent")
        assert node["adopted_parent_sender"] == "", (
            f"{uid} originated a root that claims a parent sender")


@origination
def test_an_undamaged_run_originates_no_root_at_all():
    """PAIRED NEGATIVE CONTROL for every positive above.

    A runtime that originated a root unconditionally would satisfy the metric
    while having nothing to do with repair.
    """
    o = F.development(random.Random(4000))
    F.prepare(o)
    reset()
    o.commission()

    assert o.result_ok(o.run_item(PAYLOAD_A)), "formation stopped working"

    assert C["REPAIR_REOPENS"] == 0, "an undamaged run reopened an obligation"
    assert _counter("CANONICAL_ROOTS_CREATED") == 0, (
        "an undamaged run originated a repair root, so origination is not "
        "caused by a deficit")
    assert not _roots(o)


# ---------------------------------------------------------------------------
# 2. The root identity is DERIVED, and therefore convergent
# ---------------------------------------------------------------------------

@origination
def test_the_root_key_is_a_pure_function_of_local_state():
    """Two identical deficits derive one identity, with no shared bookkeeping.

    This is the property that makes a separate deduplication mechanism
    unnecessary: `open_canonical_search` already refuses a second node per key,
    so a DERIVED identity converges for free while a counter-based one would
    mint a fresh root every reopen.
    """
    keys = []
    for _ in range(2):
        o, j, slot, victim, seed = _damaged(4)
        reset()
        o.run_item(PAYLOAD_B)
        mine = sorted((k for k in j.canonical_searches
                       if k.origin_unit == j.unit_id),
                      key=str)
        assert mine, "the damaged join originated no root"
        keys.append(mine[0])

    a, b = keys
    assert a == b, (
        f"two runs of the SAME deficit under the SAME constraints derived "
        f"different root identities:\n  {a}\n  {b}\n"
        f"a derived key must not depend on a counter, a nonce, arrival order "
        f"or wall-clock state")
    assert a.context_digest and a.context_digest == b.context_digest


@origination
def test_reopening_the_same_deficit_twice_creates_no_second_root():
    o, j, slot, victim, seed = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)
    first = {k for k in j.canonical_searches if k.origin_unit == j.unit_id}
    assert first, "no root was originated"
    roots_after_first = _counter("CANONICAL_ROOTS_CREATED")

    o.run_item(PAYLOAD_B)

    assert _counter("DUPLICATE_CANONICAL_ROOTS") == 0, (
        "a second reopen of the same deficit minted a duplicate root")
    again = {k for k in j.canonical_searches if k.origin_unit == j.unit_id}
    assert len(again) >= len(first)
    assert C["DUPLICATE_SUBTREES_OPENED"] == 0, (
        "the duplicate-subtree guard fired, so one deficit opened two trees")
    assert _counter("CANONICAL_ROOTS_CREATED") >= roots_after_first


# ---------------------------------------------------------------------------
# 3. The originator holds no knowledge it may not hold
# ---------------------------------------------------------------------------

@origination
def test_the_originator_reads_no_global_provider_index():
    o, j, slot, victim, seed = _damaged(4)
    reset()

    o.run_item(PAYLOAD_B)

    assert _counter("GLOBAL_PROVIDER_INDEX_READS") == 0, (
        "origination consulted a global provider index")
    assert C["LEGACY_PROJECTION_DECISION_READS"] == 0, (
        "origination read a legacy projection field to make a decision")
    assert _counter("SUPERVISOR_RESTART_EVENTS") == 0, (
        "a supervisor restart was emitted; repair must be locally originated")
    assert C["BOUNDARY_TRIGGERED_REPAIR_EVENTS"] == 0


@origination
def test_the_root_context_names_no_provider_and_no_topology():
    """The context may carry CONSTRAINTS. It may not carry the ANSWER.

    A context that named an eligible supplier, or the set of units the wave
    should reach, would be the target topology travelling under the name of a
    constraint -- and every candidate downstream would be enforcing the
    origin's solution rather than the origin's limits.
    """
    o, j, slot, victim, seed = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)
    roots = [(k, n) for k, n in j.canonical_searches.items()
             if k.origin_unit == j.unit_id]
    assert roots, "no root was originated"

    for key, node in roots:
        ctx = node["search_context"]
        assert ctx is not None, "a root was opened holding no context"
        # Every set the context carries is an EXCLUSION set. There is no field
        # in which a permitted supplier may be named, so the only way the answer
        # could travel is if the exclusions covered everything except it.
        named = (frozenset(ctx.causally_refused_sources)
                 | frozenset(ctx.must_differ_from_suppliers)
                 | frozenset(ctx.cooldown_excluded_suppliers))
        eligible = {u.unit_id for u in o.units.values()
                    if u.unit_id not in (ENV, SINK)
                    and u.capability.produces == key.wanted_type
                    and not u.silent and not u.dissolved}
        assert eligible, (
            "the fixture offers no eligible supplier of the wanted type, so "
            "this test cannot distinguish a constraint from a solution")
        survivors = eligible - named
        assert len(survivors) > 1, (
            f"the context excluded all but {sorted(survivors)} of "
            f"{len(eligible)} eligible suppliers, which is a solution wearing "
            f"the name of a constraint: a wave carrying it has nothing left to "
            f"search for")
    assert _counter("TARGET_TOPOLOGY_LEAKAGE_EVENTS") == 0
    assert _counter("SOLUTION_LEAKAGE_EVENTS") == 0


@origination
def test_origination_inherits_no_authority_and_causes_no_external_effect():
    o, j, slot, victim, seed = _damaged(4)
    reset()

    o.run_item(PAYLOAD_B)

    assert _counter("INHERITED_AUTHORITY_EVENTS") == 0
    assert _counter("UNAUTHORIZED_EXTERNAL_EFFECTS") == 0
    assert C["UNAUTHENTICATED_SEARCH_DELIVERIES"] == 0, (
        "the originated wave produced an unauthenticated arrival, so Commit 3 "
        "weakened the 2D ingress it depends on")
    assert C["MALFORMED_SEARCH_DELIVERIES"] == 0
    assert C["HARNESS_DELIVERIES_USED"] == 0, (
        "the live repair path took the harness bypass")


# ---------------------------------------------------------------------------
# 4. The originated wave is a real 2D citizen
# ---------------------------------------------------------------------------

@origination
def test_every_edge_the_root_opens_is_sender_owned_and_authenticated():
    """Commit 3 must ENTER through the 2D gate, not around it."""
    o, j, slot, victim, seed = _damaged(4)
    reset()

    o.run_item(PAYLOAD_B)

    assert _counter("CANONICAL_ROOTS_CREATED") >= 1
    probed = C["DIRECTED_SEARCH_EDGES_PROBED"]
    assert probed > 0, "the root opened no child edges, so nothing was searched"
    for edge, rec in o.search_edge_probes.items():
        assert rec["count"] == 1, (
            f"{edge} was created {rec['count']} times; a directed edge is "
            f"probed exactly once by its sender")
        assert rec["delivered"] <= rec["count"] + 1
        assert rec["from_unit"] and rec["to_unit"]
    total = _counter("TOTAL_CANONICAL_SEARCH_ADOPTIONS")
    assert total > 0, (
        "the live repair wave adopted nothing, so the Single Bottleneck Metric "
        "has no denominator on this path")
    assert _counter("AUTHENTICATED_SEARCH_ADOPTIONS") == total, (
        f"{total - _counter('AUTHENTICATED_SEARCH_ADOPTIONS')} adoption(s) on "
        f"the live repair path were not authenticated")


@origination
def test_the_originated_search_replaces_the_legacy_need_wave():
    o, j, slot, victim, seed = _damaged(4)
    reset()

    o.run_item(PAYLOAD_B)

    assert C["REPAIR_REOPENS"] > 0
    assert C["LEGACY_REPAIR_NEED_MESSAGES"] == 0, (
        "repair still emitted legacy Need messages")
    assert C["DUAL_REPAIR_SEARCHES"] == 0, (
        "the legacy Need search and Single-Flight both ran for one obligation")


def test_formation_is_untouched_by_the_originator():
    """PLAIN TEST. Formation keeps the legacy mechanism and the R6 numbers.

    Must hold BEFORE the originator exists and keep holding after, so it is
    deliberately not marked.
    """
    o = F.development(random.Random(4000))
    F.prepare(o)
    reset()
    o.commission()

    assert o.result_ok(o.run_item(PAYLOAD_A)), "formation stopped working"
    assert o.events_dispatched == 16, (
        f"formation dispatched {o.events_dispatched} events, not 16")
    assert o.messages == 1012, (
        f"formation moved {o.messages} messages, not 1012")


# ---------------------------------------------------------------------------
# 5. Credit closes, and replay is inert
# ---------------------------------------------------------------------------

@origination
def test_all_credit_the_root_issues_is_accounted():
    o, j, slot, victim, seed = _damaged(4)
    reset()

    o.run_item(PAYLOAD_B)

    roots = [n for k, n in j.canonical_searches.items()
             if k.origin_unit == j.unit_id]
    assert roots, "no root was originated"
    for node in roots:
        accounted = (node["local_reserve"] + node["child_allocations_in_flight"]
                     + node["consumed_credit"] + node["cancelled_credit"]
                     + node["returned_to_parent"])
        assert abs(accounted - node["incoming_allocation"]) < 1e-6, (
            f"{accounted} accounted against an issued allocation of "
            f"{node['incoming_allocation']}")
    assert _counter("SEARCH_CREDIT_IN_FLIGHT") == 0, (
        "credit was still in flight when the run ended")
    assert C["UNSUPPORTED_CHILD_CANCELLATION_CREDIT"] == 0


@origination
def test_replaying_the_whole_repair_run_creates_nothing_new():
    o, j, slot, victim, seed = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)
    roots_before = _counter("CANONICAL_ROOTS_CREATED")
    nodes_before = C["UNIQUE_CANONICAL_SEARCH_NODES"]
    probes_before = {e: dict(r) for e, r in o.search_edge_probes.items()}

    for _ in range(2):
        for u in o.units.values():
            u.step(o._caps(u))

    assert _counter("CANONICAL_ROOTS_CREATED") == roots_before, (
        "re-stepping every unit originated another root")
    assert C["UNIQUE_CANONICAL_SEARCH_NODES"] == nodes_before
    assert _counter("DUPLICATE_CANONICAL_ROOTS") == 0
    for edge, rec in probes_before.items():
        assert o.search_edge_probes[edge]["count"] == rec["count"], (
            f"{edge} was re-created on replay")


# ---------------------------------------------------------------------------
# 6. Origination fails closed
# ---------------------------------------------------------------------------

@origination
def test_a_unit_cannot_originate_for_another_units_slot():
    """A root names its origin. That name must be the unit that minted it."""
    o, j, slot, victim, seed = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)

    # NON-VACUITY FIRST, for the same reason as the boundary case: with no
    # originator there are no parentless nodes and the loop below never runs.
    assert _counter("CANONICAL_ROOTS_CREATED") >= 1, (
        "no root was originated, so this scans an empty set")
    parentless = [(u.unit_id, k) for u in o.units.values()
                  for k, n in getattr(u, "canonical_searches", {}).items()
                  if n["adopted_parent_edge"] == ""]
    assert parentless, "no parentless node exists, so no root was held anywhere"

    for uid, key in parentless:
        assert key.origin_unit == uid, (
            f"{uid} holds a PARENTLESS node for a search originated by "
            f"{key.origin_unit}; only the origin may hold a root, and only for "
            f"itself")


@origination
def test_the_boundary_never_originates_a_repair_root():
    o, j, slot, victim, seed = _damaged(4)
    reset()

    o.run_item(PAYLOAD_B)

    # NON-VACUITY FIRST. Without this the specification is satisfied by a
    # runtime that originates nothing at all, which is the state it was written
    # against -- it XPASSed on exactly that, and a negative control a
    # do-nothing implementation passes measures nothing.
    assert _counter("CANONICAL_ROOTS_CREATED") >= 1, (
        "no root was originated anywhere, so 'the boundary originated none' is "
        "trivially true and proves nothing about the boundary")

    for boundary in (ENV, SINK):
        u = o.units.get(boundary)
        if u is None:
            continue
        mine = [k for k in getattr(u, "canonical_searches", {})
                if k.origin_unit == boundary]
        assert not mine, f"{boundary} originated a repair root"
    assert C["BOUNDARY_TRIGGERED_REPAIR_EVENTS"] == 0
