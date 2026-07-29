"""Adversarial specification for Single-Flight Echo Search. Tests A-J.

PRE-REGISTERED BEFORE IMPLEMENTATION. Every test here is marked
`xfail(strict=True)`:

  - it is a real assertion against the protocol in
    SINGLE_FLIGHT_ECHO_PROTOCOL.md, not a placeholder;
  - CI stays green while the mechanism does not exist;
  - `strict=True` means a test that starts passing is reported as a FAILURE
    until the marker is deliberately removed, so the specification cannot be
    quietly satisfied, and I cannot claim it passed without editing this file
    in a reviewable commit.

The mechanism being specified replaces the branch tree recorded as failed in
HIERARCHICAL_BRANCH_ATTEMPT.md, which made path identity equivalent to duplicate
computation: 57 unacknowledged branches and amplification 526.71 against a
ceiling of 12.
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

# Applied per test, NOT module-wide. Marking the whole module xfail also marked
# the two tests that ALREADY hold against the R6 baseline -- formation
# non-regression and arrival-order stability -- and strict mode correctly
# reported them as XPASS failures. Those two are plain tests: they must pass now
# and must keep passing.
spec = pytest.mark.xfail(strict=True,
                         reason="Single-Flight Echo Search is not implemented yet")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _chain(n_auth=4, seed=7, density=0.8):
    """A two-input reconcile join with `n_auth` distinct AUTH producers."""
    caps = F._spine("alpha2") + F._spine("beta2") + F._spine("gamma2")
    for i in range(n_auth):
        caps.append(F.cap(f"au{i}", ("PX", "PX"), "AUTH", F.AUTHORISE,
                          1.0 + 0.1 * i, f"d.a{i}", "authorise", F.OK_PRICE))
    caps.append(F.cap("rn0", ("AUTH", "AUTH"), "RECON", F.RECONCILE,
                      1.0, "d.p", "reconcile", F.OK_AUTH))
    caps.append(F.cap("db0", ("RECON",), "VERDICT", F.DISBURSE,
                      1.0, "d.r", "disburse", F.OK_RECON))
    o = F._organ(caps, random.Random(seed), density)
    F.prepare(o)
    reset()
    o.commission()
    return o, o.result_ok(o.run_item(PAYLOAD_A))


def _join(o, want="AUTH"):
    for u in o.units.values():
        if u.capability.accepts.count(want) == 2:
            return u
    return None


def _damaged(n_auth=4, seed=7):
    o, ok = _chain(n_auth, seed)
    j = _join(o)
    if not ok or j is None or len(j.bonds) != 2:
        pytest.skip("no formed join")
    if len({b.supplier for b in j.bonds.values()}) != 2:
        pytest.skip("join not independently supplied")
    slot = min(j.bonds)
    victim = j.bonds[slot].supplier
    o.units[victim].silent = True
    return o, j, slot, victim


def _nodes(o):
    """Every canonical search node in the organ, keyed by (unit, SearchKey)."""
    out = {}
    for u in o.units.values():
        for key, node in getattr(u, "canonical_searches", {}).items():
            out[(u.unit_id, key)] = node
    return out


# ---------------------------------------------------------------------------
# A. Diamond convergence -> one canonical node, one child set
# ---------------------------------------------------------------------------

@spec
def test_A_diamond_convergence_opens_one_canonical_node():
    o, j, slot, victim = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)

    assert C["DUPLICATE_SUBTREES_OPENED"] == 0
    assert C["CANONICAL_SEARCH_EXPANSIONS"] == C["UNIQUE_CANONICAL_SEARCH_NODES"], (
        "a unit expanded the same semantic search more than once")
    assert C["COALESCED_DUPLICATE_ARRIVALS"] > 0, (
        "a dense graph produced no convergent arrivals at all, so this test is "
        "not exercising coalescing")
    for (uid, key), node in _nodes(o).items():
        assert len(node["children_opened"]) == len(set(node["children_opened"])), (
            f"{uid} opened a duplicate child edge for one search key")


# ---------------------------------------------------------------------------
# B. Cycle -> closed once, no ping-pong, no new subtree
# ---------------------------------------------------------------------------

@spec
def test_B_cycle_is_closed_without_ping_pong():
    o, j, slot, victim = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)

    assert C["CYCLE_EDGES_CLOSED"] >= 0
    assert C["DUPLICATE_SUBTREES_OPENED"] == 0
    assert o.events_dispatched < 3000, (
        "the run hit the event cap, which is what unbounded echo ping-pong "
        "looks like")
    assert C["ORPHANED_SEARCH_EDGES"] == 0


# ---------------------------------------------------------------------------
# C. Exact replay -> one processing, one response, one refund
# ---------------------------------------------------------------------------

@spec
def test_C_exact_replay_is_idempotent():
    o, j, slot, victim = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)
    nodes = _nodes(o)
    if not nodes:
        pytest.fail("no canonical search nodes were created")
    (uid, key), node = next(iter(nodes.items()))
    unit = o.units[uid]
    before = (node["returned_credit"], len(node["children_opened"]),
              C["TERMINAL_ECHOS_SENT"])
    for _ in range(5):
        unit.replay_search_edge(key, node["adopted_parent_edge"])
    after = (node["returned_credit"], len(node["children_opened"]),
             C["TERMINAL_ECHOS_SENT"])
    assert before == after, "replaying one edge changed credit, children or echoes"


# ---------------------------------------------------------------------------
# D. Convergent duplicate carrying MORE credit -> refunded, no new subtree
# ---------------------------------------------------------------------------

@spec
def test_D_richer_duplicate_does_not_reopen_or_pool_credit():
    o, j, slot, victim = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)
    nodes = _nodes(o)
    if not nodes:
        pytest.fail("no canonical search nodes were created")
    (uid, key), node = next(iter(nodes.items()))
    unit = o.units[uid]
    adopted = node["adopted_parent_edge"]
    children = list(node["children_opened"])
    reserve = node["local_reserve"]

    unit.deliver_duplicate_search(key, edge_id="probe/rich", allocation=999.0)

    assert node["adopted_parent_edge"] == adopted, "adopted parent was replaced"
    assert list(node["children_opened"]) == children, "a duplicate opened children"
    assert node["local_reserve"] == reserve, (
        "duplicate credit was pooled into the canonical node; the first "
        "implementation must not pool")
    assert C["COALESCED_DUPLICATE_ARRIVALS"] > 0


# ---------------------------------------------------------------------------
# E. One dead child, one live child -> no premature exhaustion
# ---------------------------------------------------------------------------

@spec
def test_E_one_exhausted_child_does_not_terminate_the_parent():
    o, j, slot, victim = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)
    assert C["PREMATURE_TERMINATION_SIGNALS"] == 0
    for (uid, key), node in _nodes(o).items():
        if node["status"] == "EXHAUSTED":
            assert not node["children_outstanding"], (
                f"{uid} reported EXHAUSTED with children still outstanding")


# ---------------------------------------------------------------------------
# F. Multi-level complete exhaustion -> proved once
# ---------------------------------------------------------------------------

@spec
def test_F_unsatisfiable_join_proves_search_space_exhausted_once():
    import evaluator as EV
    o, j, slot, victim = _damaged(2)      # two producers: unsatisfiable
    reset()
    result = o.run_item(PAYLOAD_B)

    assert not o.result_ok(result), "false restoration on an unsatisfiable join"
    assert C["SEARCH_SPACE_EXHAUSTED"] == 1, (
        f"expected exactly one proof of exhausted search space, got "
        f"{C['SEARCH_SPACE_EXHAUSTED']}")
    assert C["SEARCH_BUDGET_EXHAUSTED"] == 0, (
        "a fully explored bounded wave was reported as a budget shortfall")
    assert C["ORPHANED_SEARCH_EDGES"] == 0
    assert EV.bounded_escalation_proven(o)


# ---------------------------------------------------------------------------
# G. Budget exhaustion is NOT no-replacement proof
# ---------------------------------------------------------------------------

@spec
def test_G_budget_exhaustion_never_claims_no_replacement():
    o, j, slot, victim = _damaged(4)
    for u in o.units.values():
        u.repair_budget = 1.0             # starve the search deliberately
    reset()
    o.run_item(PAYLOAD_B)
    assert C["SEARCH_SPACE_EXHAUSTED"] == 0, (
        "credit ran out before the eligible space was closed, yet the run "
        "claimed the search space was exhausted")
    assert C["SEARCH_BUDGET_EXHAUSTED"] >= 1


# ---------------------------------------------------------------------------
# H. Return-route stability
# ---------------------------------------------------------------------------

@spec
def test_H_offer_returns_through_the_originally_adopted_edge():
    o, j, slot, victim = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)
    assert C["OFFER_RETURN_ROUTE_MISMATCHES"] == 0, (
        "an offer travelled home through an edge that was not the adopted "
        "parent; `reverse` keyed by need_id alone allows exactly this")
    for (uid, key), node in _nodes(o).items():
        assert node["adopted_parent_edge"] == node["adopted_parent_edge_initial"], (
            f"{uid} rebound its adopted parent edge after adoption")


# ---------------------------------------------------------------------------
# I. Formation non-regression
# ---------------------------------------------------------------------------

def test_I_formation_is_untouched_by_the_repair_protocol():
    """R6 figures for the development fixture: 16 events, 1012 messages, valid.

    Single-flight applies to repair only. The hierarchical attempt broke exactly
    this: branch-keying every need removed need-level collapse from formation and
    took the healthy run to the 3000-event cap with 103888 messages.
    """
    rng = random.Random(4000)
    o = F.development(rng)
    F.prepare(o)
    reset()
    o.commission()
    v = o.run_item(PAYLOAD_A)
    assert o.result_ok(v), "formation stopped producing a valid result"
    assert o.events_dispatched == 16, (
        f"formation event count moved from 16 to {o.events_dispatched}")
    assert o.messages == 1012, (
        f"formation message count moved from 1012 to {o.messages}")


# ---------------------------------------------------------------------------
# J. Amplification under convergence and cycles
# ---------------------------------------------------------------------------

@spec
@pytest.mark.parametrize("density", [0.7, 0.8, 0.9])
def test_J_amplification_scales_with_units_not_paths(density):
    o, ok = _chain(4, 11, density)
    j = _join(o)
    if not ok or j is None or len(j.bonds) != 2:
        pytest.skip("no formed join at this density")
    slot = min(j.bonds)
    o.units[j.bonds[slot].supplier].silent = True
    reset()
    before = o.messages
    o.run_item(PAYLOAD_B)
    amp = round((o.messages - before) / max(1, len(o.units)), 2)
    assert amp <= 12, f"repair amplification {amp} exceeds the ceiling of 12"
    assert C["DUPLICATE_SUBTREES_OPENED"] == 0
    assert C["DIRECTED_SEARCH_EDGES_PROBED"] <= len(o.units) ** 2, (
        "a directed edge was probed more than once for one search key")


# ---------------------------------------------------------------------------
# Arrival-order sensitivity: the known risk, measured rather than assumed
# ---------------------------------------------------------------------------

def test_arrival_order_does_not_change_whether_a_replacement_is_found():
    """First-arrival adoption makes the wave shape depend on delivery order.

    A coverage difference across orderings is a finding to report, not a
    nuisance to suppress, so this asserts the OUTCOME is stable even though the
    adopted parents may differ.
    """
    outcomes = []
    for seed in (3, 11, 19, 23, 31):
        o, ok = _chain(4, seed)
        j = _join(o)
        if not ok or j is None or len(j.bonds) != 2:
            continue
        slot = min(j.bonds)
        o.units[j.bonds[slot].supplier].silent = True
        reset()
        outcomes.append(bool(o.result_ok(o.run_item(PAYLOAD_B))))
    assert outcomes, "no formed joins across the permuted seeds"
    assert len(set(outcomes)) == 1, (
        f"whether a distinct replacement was found depended on arrival order: "
        f"{outcomes}")
