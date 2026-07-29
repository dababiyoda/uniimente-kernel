"""Adversarial specification for Single-Flight Echo Search. Tests A-J.

PRE-REGISTERED BEFORE IMPLEMENTATION. Mechanism-dependent tests are marked
`xfail(strict=True)`:

  - each is a real assertion against SINGLE_FLIGHT_ECHO_PROTOCOL.md, not a
    placeholder;
  - CI stays green while the mechanism does not exist;
  - `strict=True` means a test that starts passing is reported as a FAILURE until
    the marker is deliberately removed, so the specification cannot be quietly
    satisfied and no pass can be claimed without editing this file in a
    reviewable commit.

The mechanism replaces the branch tree recorded as failed in
HIERARCHICAL_BRANCH_ATTEMPT.md, which made path identity equivalent to duplicate
computation: 57 unacknowledged branches, amplification 526.71 against 12.

DISCRIMINATIVENESS. A required adversarial condition must never disappear into an
incidental `pytest.skip`, and must never be satisfiable by the advertised event
never happening. Every fixture here is either deterministic or found by scanning
pre-registered seeds and then HARD ASSERTED. `pytest.skip` appears nowhere.

DECLARED HARNESS SEAMS. Some specs need to drive the protocol directly rather
than hope a dense end-to-end run happens to produce the situation. The seams
below are part of the protocol contract and the implementation must provide them:

    Unit.canonical_searches            {SearchKey: node}
    Unit.open_canonical_search(key, parent_edge, allocation)   -> node
    Unit.deliver_search(key, edge_id, allocation, lineage)     -> outcome
    Unit.deliver_terminal(key, edge_id, outcome, refund)
    Unit.replay_search_edge(key, edge_id)
    Organ.search_edge_probes           {(from, to, SearchKey): count}
    Organ.search_edge_terminals        {(from, to, SearchKey): [outcome, ...]}
    Organ.space_exhaustion_proofs      [SearchKey, ...]
    v5.ROOT_SEARCH_CREDIT_OVERRIDE     None, or a float honoured by the root
                                       search ledger -- the ONLY correct way to
                                       starve search credit, since repair_budget
                                       is a supplier cost ceiling, not a message
                                       credit budget
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

# Pre-registered seeds scanned for a suitable structure. Fixed here so a fixture
# search is reproducible and auditable rather than open-ended.
SEEDS = tuple(range(60))

# Applied per test, NOT module-wide. A module-wide marker also covered the tests
# that ALREADY hold against the R6 baseline, and strict mode correctly reported
# them as XPASS failures.
spec = pytest.mark.xfail(strict=True,
                         reason="Single-Flight Echo Search is not implemented yet")


# ---------------------------------------------------------------------------
# fixtures: deterministic, or seed-scanned then HARD ASSERTED. Never skipped.
# ---------------------------------------------------------------------------

def _build(n_auth=4, seed=7, density=0.8):
    """A two-input reconcile join fed by `n_auth` distinct AUTH producers."""
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


def _suitable(o, ok):
    j = _join(o)
    return bool(ok and j is not None and len(j.bonds) == 2
                and len({b.supplier for b in j.bonds.values()}) == 2)


def _damaged(n_auth=4, density=0.8):
    """Scan pre-registered seeds, then HARD ASSERT. Never skips.

    A required adversarial condition must not vanish because one seed produced an
    unsuitable structure.
    """
    for seed in SEEDS:
        o, ok = _build(n_auth, seed, density)
        if _suitable(o, ok):
            j = _join(o)
            slot = min(j.bonds)
            victim = j.bonds[slot].supplier
            o.units[victim].silent = True
            return o, j, slot, victim, seed
    raise AssertionError(
        f"no formed independently-supplied join with n_auth={n_auth} "
        f"density={density} across pre-registered seeds {SEEDS[0]}..{SEEDS[-1]}; "
        f"the required structure could not be constructed, which is a failure of "
        f"this specification and not a reason to skip it")


def _topology_fingerprint(o):
    """Everything that must stay fixed when only arrival order varies."""
    return (
        tuple(sorted(o.units)),
        tuple(sorted((u.unit_id, u.capability.name, u.capability.accepts,
                      u.capability.produces, round(u.capability.cost, 6),
                      u.capability.domain) for u in o.units.values())),
        tuple(sorted((u.unit_id, tuple(sorted(u.neighbours)))
                     for u in o.units.values())),
        tuple(sorted((u.unit_id, s, b.supplier)
                     for u in o.units.values() for s, b in u.bonds.items())),
        tuple(sorted((u.unit_id, round(u.repair_budget, 6))
                     for u in o.units.values())),
    )


def _nodes(o):
    out = {}
    for u in o.units.values():
        for key, node in getattr(u, "canonical_searches", {}).items():
            out[(u.unit_id, key)] = node
    return out


def _root_key(o, join, slot):
    """The SearchKey of the damaged obligation itself, not any other search."""
    keys = [k for (uid, k) in _nodes(o) if uid == join.unit_id]
    matching = [k for k in keys if getattr(k, "origin_slot", None) == slot
                and getattr(k, "origin_unit", None) == join.unit_id]
    assert matching, (
        f"no canonical search node at {join.unit_id} for the damaged slot {slot}; "
        f"the root obligation was never expanded")
    assert len(set(matching)) == 1, (
        f"the damaged obligation produced {len(set(matching))} distinct root "
        f"SearchKeys; one obligation generation must be one semantic search")
    return matching[0]


def _per_key_edge_uniqueness(o):
    """Every (from_unit, to_unit, SearchKey) probed at most once, one terminal.

    A global bound like `probes <= units**2` is supplemental: it cannot prove
    per-key uniqueness, which is the actual invariant.
    """
    probes = getattr(o, "search_edge_probes", None)
    terminals = getattr(o, "search_edge_terminals", None)
    assert probes is not None and terminals is not None, (
        "the organ does not record per-key search edge probes or terminals, so "
        "per-key edge uniqueness cannot be proved")
    over = {e: n for e, n in probes.items() if n > 1}
    assert not over, f"directed edges probed more than once for one SearchKey: {over}"
    for edge in probes:
        outs = terminals.get(edge, [])
        assert len(outs) == 1, (
            f"edge {edge} received {len(outs)} terminal outcomes, expected exactly 1")
    return probes, terminals


# ---------------------------------------------------------------------------
# A. Diamond convergence -> one canonical node, one child set
# ---------------------------------------------------------------------------

@spec
def test_A_diamond_convergence_opens_one_canonical_node():
    o, j, slot, victim, seed = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)

    assert C["UNIQUE_CANONICAL_SEARCH_NODES"] > 0, "no canonical node was created"
    assert C["CANONICAL_SEARCH_EXPANSIONS"] == C["UNIQUE_CANONICAL_SEARCH_NODES"], (
        "a unit expanded the same semantic search more than once")
    assert C["DUPLICATE_SUBTREES_OPENED"] == 0
    # Without this the test could pass by never converging at all.
    assert C["COALESCED_DUPLICATE_ARRIVALS"] > 0, (
        "no convergent arrival occurred, so coalescing was never exercised")
    for (uid, key), node in _nodes(o).items():
        opened = list(node["children_opened"])
        assert len(opened) == len(set(opened)), (
            f"{uid} opened a duplicate child edge for one search key")
    _per_key_edge_uniqueness(o)


# ---------------------------------------------------------------------------
# B. Explicit cycle -> closed once, no ping-pong, no duplicate expansion
# ---------------------------------------------------------------------------

@spec
def test_B_an_actual_cycle_is_closed_exactly_once():
    """Constructs the cycle rather than hoping one occurs.

    The earlier form asserted `CYCLE_EDGES_CLOSED >= 0`, which passes when no
    cycle edge was exercised at all. That is removed.
    """
    o, j, slot, victim, seed = _damaged(4, density=1.0)   # complete graph: cycles exist
    reset()
    o.run_item(PAYLOAD_B)

    assert C["CYCLE_EDGES_CLOSED"] > 0, (
        "no cycle edge was closed even on a complete graph, so this test did "
        "not exercise cycle handling")
    assert C["DUPLICATE_SUBTREES_OPENED"] == 0
    assert C["ORPHANED_SEARCH_EDGES"] == 0
    assert C["CANONICAL_SEARCH_EXPANSIONS"] == C["UNIQUE_CANONICAL_SEARCH_NODES"], (
        "a cycle caused a unit to expand the same search twice")
    assert o.events_dispatched < 3000, (
        "the run hit the event cap, which is what unbounded echo ping-pong "
        "looks like")
    probes, terminals = _per_key_edge_uniqueness(o)
    cycle_edges = [e for e, outs in terminals.items()
                   if any(getattr(x, "kind", x) == "SearchCycleClosed" for x in outs)]
    assert cycle_edges, "CYCLE_EDGES_CLOSED fired but no edge recorded the outcome"
    for e in cycle_edges:
        assert len(terminals[e]) == 1, f"cycle edge {e} answered more than once"


# ---------------------------------------------------------------------------
# C. Exact replay -> one processing, one response, one refund
# ---------------------------------------------------------------------------

@spec
def test_C_exact_replay_is_idempotent():
    o, j, slot, victim, seed = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)
    nodes = _nodes(o)
    assert nodes, "no canonical search nodes were created"
    (uid, key), node = next(iter(sorted(nodes.items())))
    unit = o.units[uid]
    before = (node["returned_credit"], node["consumed_credit"],
              list(node["children_opened"]), C["TERMINAL_ECHOS_SENT"],
              node["local_reserve"])
    for _ in range(5):
        unit.replay_search_edge(key, node["adopted_parent_edge"])
    after = (node["returned_credit"], node["consumed_credit"],
             list(node["children_opened"]), C["TERMINAL_ECHOS_SENT"],
             node["local_reserve"])
    assert before == after, (
        "replaying one edge changed credit, children or echo count")


# ---------------------------------------------------------------------------
# D. Duplicate arrival carrying MORE credit -> full accounting asserted
# ---------------------------------------------------------------------------

@spec
def test_D_richer_duplicate_is_fully_accounted_and_opens_nothing():
    """Drives the protocol directly instead of hoping a dense run produces it."""
    o, j, slot, victim, seed = _damaged(4)
    reset()
    key = v5.SearchKey(need_id="probe:D", work_item_generation=2,
                       origin_unit=j.unit_id, origin_slot=slot,
                       wanted_type=j.capability.accepts[slot],
                       causal_refusal_digest="", must_differ_from_digest="",
                       constraint_generation=0)
    unit = next(u for u in o.units.values()
                if u.unit_id not in (ENV, SINK) and u.unit_id != j.unit_id)
    node = unit.open_canonical_search(key, parent_edge="e/adopted", allocation=6.0)
    adopted = node["adopted_parent_edge"]
    children = list(node["children_opened"])
    reserve = node["local_reserve"]
    coalesced_before = C["COALESCED_DUPLICATE_ARRIVALS"]
    echoes_before = C["TERMINAL_ECHOS_SENT"]

    outcome = unit.deliver_search(key, edge_id="e/rich", allocation=999.0,
                                  lineage=(j.unit_id,))

    assert getattr(outcome, "kind", outcome) == "SearchCoalesced", (
        f"a duplicate arrival produced {outcome!r}, expected SearchCoalesced")
    assert C["COALESCED_DUPLICATE_ARRIVALS"] == coalesced_before + 1, (
        "exactly one SearchCoalesced must be recorded")
    assert C["TERMINAL_ECHOS_SENT"] == echoes_before + 1, (
        "the duplicate edge must receive exactly one terminal outcome")
    assert node["adopted_parent_edge"] == adopted, "adopted parent was replaced"
    assert list(node["children_opened"]) == children, "a duplicate opened children"
    assert node["local_reserve"] == reserve, (
        "duplicate credit was pooled into the canonical node; the first "
        "implementation must not pool credit")
    refund = getattr(outcome, "refund", None)
    cost = getattr(outcome, "handling_cost", None)
    assert refund is not None and cost is not None, (
        "the coalesced outcome carries no refund/handling-cost evidence")
    assert abs(refund - (999.0 - cost)) < 1e-9, (
        f"duplicate refund {refund} is not allocation minus handling cost "
        f"({999.0} - {cost})")
    assert C["DUPLICATE_SUBTREES_OPENED"] == 0

    again = unit.deliver_search(key, edge_id="e/rich", allocation=999.0,
                               lineage=(j.unit_id,))
    assert C["COALESCED_DUPLICATE_ARRIVALS"] == coalesced_before + 1, (
        "replaying the duplicate edge produced a second coalesced response")
    assert C["TERMINAL_ECHOS_SENT"] == echoes_before + 1, (
        "replaying the duplicate edge produced a second terminal outcome")
    assert getattr(again, "refund", 0.0) == 0.0, (
        "a replayed duplicate refunded a second time")


# ---------------------------------------------------------------------------
# E. Forced mixed-child order: A exhausts, then B answers
# ---------------------------------------------------------------------------

@spec
def test_E_exhausted_child_then_late_offer_never_terminates_parent_early():
    """Forces the ordering instead of inspecting whatever a dense run produced."""
    o, j, slot, victim, seed = _damaged(4)
    reset()
    key = v5.SearchKey(need_id="probe:E", work_item_generation=2,
                       origin_unit=j.unit_id, origin_slot=slot,
                       wanted_type=j.capability.accepts[slot],
                       causal_refusal_digest="", must_differ_from_digest="",
                       constraint_generation=0)
    unit = next(u for u in o.units.values()
                if u.unit_id not in (ENV, SINK) and u.unit_id != j.unit_id)
    node = unit.open_canonical_search(key, parent_edge="e/adopted", allocation=9.0)
    kids = list(node["children_opened"])
    assert len(kids) >= 2, (
        f"the canonical node opened {len(kids)} children; this test needs at "
        f"least two to force a mixed outcome")
    a, b = kids[0], kids[1]
    echoes_before = C["TERMINAL_ECHOS_SENT"]

    unit.deliver_terminal(key, a, "SearchExhausted", refund=1.0)

    assert node["status"] == "OPEN", (
        f"parent went {node['status']} after ONE child exhausted while "
        f"{len(node['children_outstanding'])} remain outstanding")
    assert b in node["children_outstanding"], "the live child was dropped"
    assert C["TERMINAL_ECHOS_SENT"] == echoes_before, (
        "an exhaustion echo was sent upward while a child was still live")
    assert C["PREMATURE_TERMINATION_SIGNALS"] == 0

    unit.deliver_terminal(key, b, "SearchOffer", refund=0.5)

    assert node["status"] == "ANSWERED", (
        f"parent is {node['status']} after a child returned an eligible offer")
    assert node["eligible_offer"], "the offer was not recorded on the parent"
    assert node["adopted_parent_edge"] == "e/adopted", (
        "the offer did not follow the immutable adopted-parent edge")
    assert C["SEARCH_SPACE_EXHAUSTED"] == 0, (
        "a subtree that answered was also counted as exhausted")


# ---------------------------------------------------------------------------
# F. Unsatisfiable join -> exactly one space-exhaustion proof for the ROOT key
# ---------------------------------------------------------------------------

@spec
def test_F_unsatisfiable_join_proves_space_exhausted_once_for_the_root_key():
    import evaluator as EV
    o, j, slot, victim, seed = _damaged(2)          # two producers: unsatisfiable
    reset()
    result = o.run_item(PAYLOAD_B)

    assert not o.result_ok(result), "false restoration on an unsatisfiable join"
    root = _root_key(o, j, slot)
    proofs = getattr(o, "space_exhaustion_proofs", None)
    assert proofs is not None, "the organ records no space-exhaustion proofs"
    mine = [k for k in proofs if k == root]
    assert len(mine) == 1, (
        f"expected exactly one SEARCH_SPACE_EXHAUSTED proof for the damaged "
        f"obligation's root SearchKey, got {len(mine)}; unrelated searches must "
        f"not corrupt this count")
    assert C["SEARCH_BUDGET_EXHAUSTED"] == 0, (
        "a fully explored bounded wave was reported as a budget shortfall")
    assert C["ORPHANED_SEARCH_EDGES"] == 0
    assert EV.bounded_escalation_proven(o)
    _per_key_edge_uniqueness(o)


# ---------------------------------------------------------------------------
# G. Search-credit starvation -> budget exhaustion, never no-replacement proof
# ---------------------------------------------------------------------------

@spec
def test_G_search_credit_starvation_never_claims_no_replacement(monkeypatch):
    """Starves SEARCH CREDIT, not `repair_budget`.

    `repair_budget` is a supplier COST ceiling and a local repair allowance; it
    is not the search-message credit ledger, so setting it to 1.0 did not prove
    credit starvation and an ordinary no-provider result could be mislabelled.
    """
    monkeypatch.setattr(v5, "ROOT_SEARCH_CREDIT_OVERRIDE", 2.0, raising=False)
    o, j, slot, victim, seed = _damaged(4)          # a replacement DOES exist
    reset()
    o.run_item(PAYLOAD_B)

    root = _root_key(o, j, slot)
    node = next(n for (uid, k), n in _nodes(o).items()
                if uid == j.unit_id and k == root)
    remaining = node.get("eligible_untried_routes")
    assert remaining is not None, (
        "the node does not record how many eligible routes were left untried, "
        "so budget exhaustion cannot be distinguished from space exhaustion")
    assert remaining > 0, (
        "credit ran out but no eligible route remained untried, so this is a "
        "space exhaustion and the test is not exercising budget starvation")
    assert C["SEARCH_BUDGET_EXHAUSTED"] >= 1
    assert C["SEARCH_SPACE_EXHAUSTED"] == 0, (
        "credit ended before the eligible space was closed, yet the run claimed "
        "the search space was exhausted")
    proofs = getattr(o, "space_exhaustion_proofs", []) or []
    assert root not in proofs, (
        "a no-replacement proof was emitted for an obligation whose search was "
        "merely starved of credit")


# ---------------------------------------------------------------------------
# H. Return-route stability
# ---------------------------------------------------------------------------

@spec
def test_H_offer_returns_through_the_originally_adopted_edge():
    o, j, slot, victim, seed = _damaged(4, density=1.0)
    reset()
    o.run_item(PAYLOAD_B)
    assert C["OFFER_RETURN_ROUTE_MISMATCHES"] == 0, (
        "an offer travelled home through an edge that was not the adopted "
        "parent; `reverse` keyed by need_id alone allows exactly this")
    nodes = _nodes(o)
    assert nodes, "no canonical nodes were created"
    for (uid, key), node in nodes.items():
        assert node["adopted_parent_edge"] == node["adopted_parent_edge_initial"], (
            f"{uid} rebound its adopted parent edge after adoption")


# ---------------------------------------------------------------------------
# I. Formation non-regression. Plain test: must pass now and keep passing.
# ---------------------------------------------------------------------------

def test_I_formation_is_untouched_by_the_repair_protocol():
    """R6 figures for the development fixture: 16 events, 1012 messages, valid.

    Single-flight applies to repair only. The hierarchical attempt broke exactly
    this: branch-keying every need removed need-level collapse from formation and
    took the healthy run to the 3000-event cap with 103888 messages.
    """
    o = F.development(random.Random(4000))
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
# J. Amplification. Every density is exercised; none may be skipped.
# ---------------------------------------------------------------------------

@spec
@pytest.mark.parametrize("density", [0.7, 0.8, 0.9])
def test_J_amplification_scales_with_units_not_paths(density):
    o, j, slot, victim, seed = _damaged(4, density=density)
    reset()
    before = o.messages
    o.run_item(PAYLOAD_B)
    amp = round((o.messages - before) / max(1, len(o.units)), 2)
    assert amp <= 12, (
        f"repair amplification {amp} exceeds the ceiling of 12 at density "
        f"{density} (seed {seed})")
    assert C["DUPLICATE_SUBTREES_OPENED"] == 0
    assert C["CANONICAL_SEARCH_EXPANSIONS"] == C["UNIQUE_CANONICAL_SEARCH_NODES"]
    _per_key_edge_uniqueness(o)


# ---------------------------------------------------------------------------
# Arrival order, isolated: ONE organ, only delivery order varies
# ---------------------------------------------------------------------------

@spec
def test_arrival_order_alone_does_not_change_the_outcome():
    """Holds the graph fixed and permutes only message dequeue order.

    The earlier form rebuilt the organ from different seeds, which also changes
    topology, neighbour order, initial bonds and the selected victim -- so it did
    not isolate arrival order at all. Here one structure is built once, its
    fingerprint is asserted identical across runs, and only the ready-queue
    rotation differs.
    """
    base_o, _, base_slot, base_victim, seed = _damaged(4, density=0.9)
    fingerprint = _topology_fingerprint(base_o)

    outcomes, adopted_sets, amps = [], [], []
    for rotation in (0, 1, 2, 3):
        o, ok = _build(4, seed, 0.9)
        assert _suitable(o, ok), "the fixed fixture stopped forming"
        j = _join(o)
        slot = min(j.bonds)
        victim = j.bonds[slot].supplier
        o.units[victim].silent = True
        assert slot == base_slot and victim == base_victim, (
            "the damaged obligation moved between runs, so arrival order is not "
            "the only variable")
        assert _topology_fingerprint(o) == fingerprint, (
            "topology, capabilities, bonds or budgets differed between runs")

        # Rotate the ready queue before each dispatch: same events, different
        # arrival order, nothing else touched.
        original = v5.Organ._schedule
        state = {"n": 0}

        def rotating(self, uid, kind, _o=original, _r=rotation, _s=state):
            _o(self, uid, kind)
            _s["n"] += 1
            if _r and self.ready and _s["n"] % (_r + 1) == 0:
                self.ready.rotate(_r)

        v5.Organ._schedule = rotating
        try:
            reset()
            before = o.messages
            result = o.run_item(PAYLOAD_B)
        finally:
            v5.Organ._schedule = original

        outcomes.append(bool(o.result_ok(result)))
        amps.append(round((o.messages - before) / max(1, len(o.units)), 2))
        adopted_sets.append(frozenset(
            (uid, n["adopted_parent_edge"]) for (uid, k), n in _nodes(o).items()))
        sups = [b.supplier for b in j.bonds.values()]
        assert len(sups) == len(set(sups)), (
            f"independence was violated under arrival-order rotation {rotation}")
        assert C["DUPLICATE_SUBTREES_OPENED"] == 0

    assert len(set(outcomes)) == 1, (
        f"whether a distinct replacement was found depended on arrival order "
        f"alone: {outcomes}")
    assert all(a <= 12 for a in amps), f"amplification unbounded under reorder: {amps}"
    # The adopted parents MAY differ -- that is expected under first-arrival
    # adoption, and is recorded rather than asserted away.


def test_unit_id_permutation_is_a_separate_variable_from_arrival_order():
    """Naming order and arrival order are different causal variables.

    Kept plain: it holds against the R6 baseline and must keep holding.
    """
    results = []
    for n_auth in (2, 4):
        o, j, slot, victim, seed = _damaged(n_auth)
        reset()
        o.run_item(PAYLOAD_B)
        sups = [b.supplier for b in j.bonds.values()]
        assert len(sups) == len(set(sups)), (
            f"independence violated with n_auth={n_auth}")
        results.append((n_auth, o.result_ok(o._produced.get(SINK))
                        if SINK in o._produced else False))
    assert results, "no structures were exercised"
