"""Commit 5H: a command is completed by the child, or it is not completed.

PRE-REGISTERED BEFORE THE CORRESPONDING RUNTIME CHANGE. Strict xfail throughout.

THE INVARIANT.

    a control  means "the parent REQUESTED this transition"
    a child-owned completion outcome means "the receiving endpoint APPLIED the
    request, reconciled every descendant liability, and can account for the
    incoming allocation"

Authentication of a control proves who asked. It does not prove that the child
applied it, that descendants closed, that credit reconciled, or that the
incoming edge may close.

DESIGN SELECTED: PROMOTE `deliver_search_ack` INTO THE OUTCOME CHANNEL.

Six candidates were compared. The selection is not a preference; it follows
from what the runtime already contains.

  1. PROMOTE THE EXISTING ACK.  `deliver_search_ack` is ALREADY the child's
     closure evidence and already does every hard part: it authenticates the
     sender against `node["child_targets"][edge]`, is idempotent by
     `child_confirmed`, validates the raw claim through `_evidence_reconciles`
     before any normalization, and closes the allocation. It is simply not
     RECORDED as an outcome. Its own docstring states the conflation exactly --
     "A child's closure evidence. NOT a terminal. The edge's single terminal is
     the commit or cancellation command that travelled DOWN it" -- which is
     backwards under the split: the command is the control, and this is the
     outcome.  SELECTED. Smallest truthful state machine: no new message type,
     no second authentication path, no second replay rule, no new credit
     arithmetic.

  2. ONE GENERIC `SearchControlApplied` OUTCOME.  Rejected: it duplicates the
     ack's authentication, replay and reconciliation logic in a second place,
     and two mechanisms that must agree about credit is how the parent/child
     ledger disagreement arose in the first place.

  3. EXPLICIT PER-COMMAND OUTCOMES (`SearchCommitApplied`, ...).  Rejected for
     now: three kinds where one suffices, and the distinction they carry is
     already in `accepted_control`. Retained as the migration target if a
     completion ever needs to disagree with the control it answers.

  4. TREAT A CHILD'S NATURAL TERMINAL AS IMPLICIT COMPLETION.  Rejected: it
     cannot distinguish "I exhausted before you commanded" from "I applied your
     command", so a command sent to an already-closed node would read as
     completed by evidence that predates it.

  5. AUTHENTICATED INBOUND ALIASES until each control completes.  Retained as a
     COMPONENT, not an alternative: it is what a coalesced edge needs, and it
     composes with 1 rather than competing.

  6. IMMEDIATE COALESCED CLOSURE PLUS ORDINARY COMPLETION ELSEWHERE.  Retained
     as the other half of the coalesced case. Specified below.

WHAT MUST CHANGE, stated so the runtime commit is not free to wander:
`deliver_search_ack` must record an accepted OUTCOME on the edge, and
`_acknowledge_to_parent` must answer EVERY inbound liability rather than only
the adopted parent edge -- a node holding a coalesced inbound edge owes that
opener an answer on that exact edge, and today sends none.
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

completion = pytest.mark.xfail(
    strict=True,
    reason="child-owned command completion is not implemented yet")


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


def _counter(name):
    assert name in C.d, (
        f"the runtime defines no {name} counter, so the behaviour it names "
        f"cannot be measured and this specification cannot be satisfied")
    return C[name]


def _kind(x):
    return getattr(x, "kind", x)


def _lc(o, edge):
    return (getattr(o, "search_edge_lifecycle", {}) or {}).get(edge) or {}


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
        "no formed independently-supplied join across the pre-registered "
        "seeds; failing to construct the structure is a failure of this "
        "specification, not a reason to skip it")


def _nodes(o):
    return {(u.unit_id, k): n for u in o.units.values()
            for k, n in getattr(u, "canonical_searches", {}).items()}


# ---------------------------------------------------------------------------
# 1. THE METRIC: every applied control gets a child-owned completion
# ---------------------------------------------------------------------------

@completion
def test_every_applied_control_receives_a_child_owned_completion():
    """THE SINGLE BOTTLENECK METRIC, with a mandatory nonzero denominator."""
    o, j, slot, victim, seed = _damaged(4, density=1.0)
    reset()

    o.run_item(PAYLOAD_B)

    applied = _counter("PARENT_CONTROLS_APPLIED")
    assert applied > 0, (
        "no parent control was applied at all, so the ratio below has no "
        "denominator and would be vacuously satisfied")
    assert _counter("PARENT_CONTROLS_WITH_CHILD_OWNED_COMPLETION") == applied
    assert _counter("CLOSED_NODES_WITH_CHILDREN_OUTSTANDING") == 0
    assert _counter("DUPLICATE_CONTROL_APPLICATIONS") == 0
    assert _counter("PREMATURE_CONTROL_COMPLETION_OUTCOMES") == 0
    assert C["UNSUPPORTED_CHILD_CANCELLATION_CREDIT"] == 0
    assert C["UNAUTHENTICATED_TERMINAL_CONTROLS"] == 0
    assert C["MALFORMED_TERMINAL_EVIDENCE"] == 0
    assert C["UNAUTHORIZED_EXTERNAL_EFFECTS"] == 0


def test_every_commanded_edge_ends_with_an_accepted_child_outcome():
    """Stated on the EDGES, because that is where the evidence lives.

    An edge that carries an accepted control and no accepted outcome is a
    liability nobody discharged. Five such edges existed when this was written.
    """
    o, j, slot, victim, seed = _damaged(4, density=1.0)
    reset()

    o.run_item(PAYLOAD_B)

    lifecycle = getattr(o, "search_edge_lifecycle", None)
    assert lifecycle, "no canonical lifecycle records exist"
    commanded = {e: r for e, r in lifecycle.items()
                 if r["accepted_control"] is not None}
    assert commanded, "no edge carried a control, so this proves nothing"
    unanswered = {e: _kind(r["accepted_control"]) for e, r in commanded.items()
                  if r["accepted_outcome"] is None}
    assert not unanswered, (
        f"{len(unanswered)} commanded edge(s) never received a child-owned "
        f"outcome: {sorted(unanswered.items())[:6]}")
    for edge, rec in commanded.items():
        out = rec["accepted_outcome"]
        probe = o.search_edge_probes.get(edge, {})
        assert out.from_unit == probe.get("to_unit"), (
            f"{edge} was completed by {out.from_unit}, not by the receiving "
            f"endpoint {probe.get('to_unit')}")
        assert out.search_key == probe.get("search_key"), (
            f"{edge} was completed under a different SearchKey")


# ---------------------------------------------------------------------------
# 2. Completion is EARNED, not immediate
# ---------------------------------------------------------------------------

def test_no_completion_is_emitted_while_a_descendant_remains_outstanding():
    """THE CASE A NAIVE IMPLEMENTATION FAILS.

    A runtime that answers the moment a control arrives satisfies every
    "was it answered" test above and is wrong: it claims a subtree reconciled
    before that subtree reported. Measured over the whole run, no node may hold
    an accepted outcome on its adopted edge while it still owes children.
    """
    o, j, slot, victim, seed = _damaged(4, density=1.0)
    reset()

    o.run_item(PAYLOAD_B)

    premature = []
    for (uid, key), node in _nodes(o).items():
        adopted = node["adopted_parent_edge"]
        if not adopted:
            continue
        rec = _lc(o, adopted)
        if rec.get("accepted_outcome") is None:
            continue
        if node["children_outstanding"]:
            premature.append((uid, sorted(node["children_outstanding"])))
        if node["child_allocations_in_flight"] > 1e-9:
            premature.append((uid, f"{node['child_allocations_in_flight']} in flight"))
    assert not premature, (
        f"node(s) completed their incoming edge while still owed by "
        f"descendants or holding credit in flight: {premature[:4]}")
    assert _counter("PREMATURE_CONTROL_COMPLETION_OUTCOMES") == 0


def test_a_completion_reconciles_the_incoming_allocation_exactly():
    o, j, slot, victim, seed = _damaged(4, density=1.0)
    reset()

    o.run_item(PAYLOAD_B)

    checked = 0
    for (uid, key), node in _nodes(o).items():
        adopted = node["adopted_parent_edge"]
        rec = _lc(o, adopted) if adopted else {}
        out = rec.get("accepted_outcome")
        if out is None:
            continue
        incoming = node["incoming_allocation"]
        assert out.refund + out.handling_cost <= incoming + 1e-6, (
            f"{uid} returned {out.refund} and consumed {out.handling_cost} "
            f"against an incoming allocation of {incoming}")
        checked += 1
    assert checked > 0, (
        "no node completed its incoming edge, so no reconciliation was checked")


# ---------------------------------------------------------------------------
# 3. Application is exactly-once, and only by the right endpoint
# ---------------------------------------------------------------------------

def test_an_exact_control_replay_does_not_apply_it_twice():
    o, j, slot, victim, seed = _damaged(4, density=1.0)
    reset()
    o.run_item(PAYLOAD_B)
    applied = _counter("PARENT_CONTROLS_APPLIED")
    assert applied > 0, "no control was applied, so replay proves nothing"
    snapshot = {e: (_kind(r["accepted_control"]) if r["accepted_control"] else None,
                    _kind(r["accepted_outcome"]) if r["accepted_outcome"] else None)
                for e, r in o.search_edge_lifecycle.items()}

    for _ in range(2):
        for u in o.units.values():
            u.step(o._caps(u))

    assert _counter("PARENT_CONTROLS_APPLIED") == applied, (
        "re-stepping every unit applied a control a second time")
    assert _counter("DUPLICATE_CONTROL_APPLICATIONS") == 0
    assert {e: (_kind(r["accepted_control"]) if r["accepted_control"] else None,
                _kind(r["accepted_outcome"]) if r["accepted_outcome"] else None)
            for e, r in o.search_edge_lifecycle.items()} == snapshot, (
        "a replayed round changed an accepted control or outcome")


def test_a_closed_non_root_node_owes_nothing():
    o, j, slot, victim, seed = _damaged(4, density=1.0)
    reset()

    o.run_item(PAYLOAD_B)

    finished = {(uid, k): n for (uid, k), n in _nodes(o).items()
                if n["status"] in ("COMMITTED", "CLOSED", "EXHAUSTED")}
    assert finished, "no node reached a terminal status"
    stranded = {uid: sorted(n["children_outstanding"])
                for (uid, k), n in finished.items() if n["children_outstanding"]}
    assert not stranded, (
        f"closed node(s) still owed answers by their own children: {stranded}")
    assert _counter("CLOSED_NODES_WITH_CHILDREN_OUTSTANDING") == 0


# ---------------------------------------------------------------------------
# 4. A coalesced inbound edge is its own liability
# ---------------------------------------------------------------------------

@completion
def test_every_coalesced_inbound_edge_closes_on_its_own_edge():
    """Single-flight is about the NODE. Transport liabilities are not shared.

    A duplicate arrival adopts nothing, but its opener still committed an
    allocation to THAT edge and is owed an answer on it.
    """
    o, j, slot, victim, seed = _damaged(4, density=1.0)
    reset()

    o.run_item(PAYLOAD_B)

    total = _counter("COALESCED_INBOUND_EDGES")
    assert total > 0, (
        "no inbound edge coalesced on a complete graph, so this specification "
        "measured nothing")
    assert _counter("COALESCED_INBOUND_EDGES_CLOSED_SEPARATELY") == total, (
        f"{total - _counter('COALESCED_INBOUND_EDGES_CLOSED_SEPARATELY')} "
        f"coalesced inbound edge(s) were never closed on their own edge")


# ---------------------------------------------------------------------------
# 5. NEGATIVE CONTROLS -- a runtime that refuses everything must fail
# ---------------------------------------------------------------------------

def test_the_repair_still_restores_and_still_uses_single_flight_only():
    """PAIRED POSITIVE CONTROL for every requirement above.

    Every specification in this file can be satisfied by a runtime that never
    commands anything, never completes anything and repairs nothing. This is
    the one that such a runtime fails.

    DELIBERATELY PLAIN, not marked. It asserts properties that hold TODAY, so
    marking it would report a satisfied requirement as an expected failure and
    then flip to XPASS the moment anything touched it -- which is exactly what
    happened on the first run of this file. A positive control has to be able
    to go red when the runtime breaks, which means it must be green now.
    """
    o, j, slot, victim, seed = _damaged(4)
    reset()

    o.run_item(PAYLOAD_B)

    assert C["REPAIR_REOPENS"] > 0, "no repair was attempted"
    assert C["REPAIR_REOPENS_WITH_CANONICAL_ROOT"] == C["REPAIR_REOPENS"]
    assert C["ELIGIBLE_PROPOSALS_COMMITTED"] > 0, (
        "nothing was committed, so the completion path was never exercised")
    assert C["LEGACY_REPAIR_NEED_MESSAGES"] == 0, (
        "the legacy Need wave reappeared on the canonical repair path")
    assert C["DUAL_REPAIR_SEARCHES"] == 0
    assert C["UNAUTHENTICATED_SEARCH_DELIVERIES"] == 0
    assert C["HARNESS_DELIVERIES_USED"] == 0


def test_formation_is_untouched_by_command_completion():
    """PLAIN TEST. Must hold before the mechanism exists and keep holding."""
    o = F.development(random.Random(4000))
    F.prepare(o)
    reset()
    o.commission()

    assert o.result_ok(o.run_item(PAYLOAD_A)), "formation stopped working"
    assert o.events_dispatched == 16, (
        f"formation dispatched {o.events_dispatched} events, not 16")
    assert o.messages == 1012, (
        f"formation moved {o.messages} messages, not 1012")
