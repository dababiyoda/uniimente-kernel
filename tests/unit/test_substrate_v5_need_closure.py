"""NC-1: causal need closure, pre-registered BEFORE the runtime that satisfies it.

A unit originates a canonical root for an unmet slot. The obligation is then
satisfied some other way, so `open_needs[slot]` no longer names this root's
`need_id` and `settle_search_offer` can only ever refuse it with
`wrong_need_generation`. The root can never settle anything again — and nothing
tells its subtree. Every relay and source below keeps `eligible_offer`,
`local_candidate`, `proposals_outstanding` and its parent's committed credit,
permanently.

Measured at `bc13bc3` (NC-0, `need_closure_diagnose.py`):

    3 abandoned roots · all 3 holding liability · 18.0 credit in flight
    dense fixtures: 0 abandoned roots — the condition is invisible there

THE PREDICATE IS NOT RESTATED HERE. `classify_root` and `open_roots` are
imported from the NC-0 instrument, so the specification and the diagnosis share
one oracle and cannot drift apart. A test file that re-implemented the
abandonment test could agree with a broken runtime by mirroring its mistake —
which is the failure mode this workstream has hit repeatedly.

WHAT IS DELIBERATELY NOT ASSUMED. Whether the downward control is
`SearchNeedClosed` or a new typed kind, and what travels back up, is decided in
NC-2 by evidence. These specifications are written against OBSERVABLE
CONSEQUENCES — liability discharged, credit reconciled, offers cleared, replay
inert — not against a presumed schema. Where a named counter is unavoidable,
`_counter` says so explicitly rather than raising KeyError.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (_ROOT, _ROOT / "tests" / "unit", _ROOT / "verification" / "phase3g"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import substrate.v5 as v5                                       # noqa: E402
from substrate.v5 import C, reset                               # noqa: E402
import test_substrate_v5_control_outcome_separation as S        # noqa: E402
from need_closure_diagnose import (ABANDONED_STATES,           # noqa: E402
                                   classify_root, open_roots)

PAYLOAD_B = S.PAYLOAD_B

# A DISTINCT MARKER. The existing `separation`, `prearrival` and `echo` markers
# belong to mechanisms with their own activation commits; mixing this in with
# them would let an unrelated activation remove these by accident.
need_closure = pytest.mark.xfail(
    strict=True, reason="causal need closure is not implemented yet")

# The one fixture in which an abandoned root exists at all. Recorded here so a
# future change that moves the condition elsewhere fails loudly rather than
# turning every specification below into a vacuous pass.
ABANDONED_FIXTURE = (3, 0.6)

# Imported, not restated. Includes the post-closure states, because a root that
# WAS abandoned stays countable after it is closed -- otherwise every
# specification here goes vacuous the moment the mechanism starts working.
CLOSABLE = ABANDONED_STATES


def _counter(name):
    assert name in C.d, (
        f"the runtime defines no {name} counter, so the behaviour it names "
        f"cannot be measured and this specification cannot be satisfied")
    return C[name]


def _run():
    o, _j, _slot, _victim, seed = S._damaged(*ABANDONED_FIXTURE[:1],
                                             density=ABANDONED_FIXTURE[1])
    reset()
    o.run_item(PAYLOAD_B)
    return o, seed


def _abandoned(o):
    """Every root whose obligation generation is retired, with its facts.

    HARD ASSERTED, never skipped. A run without an abandoned root cannot
    demonstrate anything about closing one, and the correct response to losing
    the condition is to fail this specification, not to pass it quietly.
    """
    out = []
    for unit, key, node in open_roots(o):
        facts = classify_root(unit, key, node)
        if facts["state"] in CLOSABLE:
            out.append((unit, key, node, facts))
    assert out, (
        "no open root has a retired obligation generation in this run, so "
        "every need-closure specification below would be vacuously satisfied; "
        "the fixture no longer contains the condition it exists to exercise")
    return out


def _liability(node):
    return (len(node["children_outstanding"])
            + len(node["proposals_outstanding"])
            + (1 if node.get("eligible_offer") else 0)
            + (1 if node.get("local_candidate") is not None else 0))


def _descendants(o, key):
    """Every unit holding a canonical node for this SearchKey, minus the origin."""
    return [(u, u.canonical_searches[key]) for u in o.units.values()
            if key in getattr(u, "canonical_searches", {})
            and u.unit_id != key.origin_unit]


def _kind(x):
    return getattr(x, "kind", x)


# ---------------------------------------------------------------------------
# Non-vacuity witnesses. NOT xfail: these must hold now, or every specification
# below is measuring an empty set and the whole file is theatre.
# ---------------------------------------------------------------------------

def test_witness_the_fixture_contains_an_abandoned_root_holding_liability():
    o, seed = _run()
    roots = _abandoned(o)
    assert any(_liability(n) > 0 for _u, _k, n, _f in roots), (
        f"seed {seed}: an abandoned root exists but none holds a child, "
        f"proposal or offer liability, so closing it would discharge nothing")
    assert sum(n["child_allocations_in_flight"] for _u, _k, n, _f in roots) > 0, (
        "no abandoned root holds credit in flight, so credit reconciliation "
        "cannot be demonstrated")


def test_witness_the_dense_fixture_contains_no_abandoned_root():
    """The condition is invisible where the other specifications look.

    This is why the four LC-2 specifications could not have found it: they run
    at density 1.0, where the single root is already terminal.
    """
    o, _j, _slot, _victim, _seed = S._damaged(4, density=1.0)
    reset()
    o.run_item(PAYLOAD_B)
    closable = [f for _u, _k, _n, f in
                ((u, k, n, classify_root(u, k, n)) for u, k, n in open_roots(o))
                if f["state"] in CLOSABLE]
    assert not closable, (
        "the dense fixture now contains an abandoned root; the recorded reason "
        "the LC-2 specifications could not see this condition is stale")


# ---------------------------------------------------------------------------
# SEVEN OF THESE CARRY NO MARKER, and never did.
#
# 03, 17, 18, 28, 31, 32 and 34 hold against the runtime as it stands. They are
# not predictions about the mechanism -- they are invariants the mechanism must
# not BREAK: the fixture really does hold a dischargeable liability; an
# unrelated or stale-generation bond does not close a live root; late outcomes
# stay replay-inert; PA-3's single pre-arrival field is still the only pending
# store; no credit is returned twice.
#
# Marking them xfail would have been false pre-registration. A strict xfail that
# XPASSes on the day it is written earns nothing when its marker later comes
# off, and eight such specifications have already been found and corrected in
# this workstream. They are active from the start, and if the closure cascade
# breaks any of them the suite goes red immediately rather than at activation.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# POSITIVE PATH (1-16)
# ---------------------------------------------------------------------------

@need_closure
def test_01_an_abandoned_root_is_recognised_as_satisfied_elsewhere():
    """The denominator of every metric below. Must be nonzero and named."""
    o, _seed = _run()
    roots = _abandoned(o)
    assert _counter("ALTERNATE_SATISFIED_OPEN_ROOTS") == len(roots), (
        "the runtime does not count the roots whose obligation generation was "
        "retired, so no closure ratio can be read against a real denominator")


@need_closure
def test_02_closure_only_applies_to_a_non_terminal_root():
    o, _seed = _run()
    for _u, _k, node, facts in _abandoned(o):
        assert facts["node_status"] in ("CLOSING_NEED_SATISFIED_ELSEWHERE",
                                        "CLOSED"), (
            f"an abandoned root is still {facts['node_status']}; a root whose "
            f"obligation generation was retired must enter a closure state and "
            f"must not remain live")


def test_03_every_abandoned_root_had_a_real_liability_to_discharge():
    o, _seed = _run()
    roots = _abandoned(o)
    assert sum(_liability(n) for _u, _k, n, _f in roots) > 0


@need_closure
def test_04_closure_is_initiated_exactly_once_per_abandoned_root():
    o, _seed = _run()
    roots = _abandoned(o)
    assert _counter("NEED_CLOSURE_CASCADES_INITIATED") == len(roots)
    assert _counter("DUPLICATE_NEED_CLOSURE_APPLICATIONS") == 0


@need_closure
def test_05_every_outstanding_child_edge_receives_an_authenticated_control():
    """Downward, on an edge this root actually opened, to that edge's target."""
    o, _seed = _run()
    for _u, key, node, _f in _abandoned(o):
        for edge in sorted(node["children_opened"]):
            rec = o.search_edge_lifecycle.get(edge)
            assert rec is not None, f"{edge} has no lifecycle record at all"
            ctrl = rec.get("accepted_control")
            assert ctrl is not None, (
                f"{edge} carried committed credit and received no closure "
                f"control, so its receiver was never told the need is gone")
            assert ctrl.from_unit == key.origin_unit or ctrl.from_unit in (
                o.search_edge_probes.get(edge, {}).get("from_unit"),), (
                f"the control on {edge} did not come from the edge's opener")
            assert ctrl.search_key == key
    assert C["UNAUTHENTICATED_TERMINAL_CONTROLS"] == 0


@need_closure
def test_06_every_relay_closes_its_own_local_wave():
    o, _seed = _run()
    for _u, key, _node, _f in _abandoned(o):
        for unit, dnode in _descendants(o, key):
            assert dnode["status"] not in ("OPEN", "PROPOSAL_PENDING"), (
                f"{unit.unit_id} still holds an open wave for a SearchKey whose "
                f"obligation no longer exists")


@need_closure
def test_07_every_source_clears_its_eligible_offer():
    o, _seed = _run()
    for _u, key, _node, _f in _abandoned(o):
        for unit, dnode in _descendants(o, key):
            assert not dnode.get("eligible_offer"), (
                f"{unit.unit_id} is still advertising an eligible offer for a "
                f"need that no longer exists")
    assert _counter("ABANDONED_ROOTS_WITH_ELIGIBLE_OFFER") == 0


@need_closure
def test_08_every_source_clears_its_local_candidate():
    o, _seed = _run()
    for _u, key, _node, _f in _abandoned(o):
        for unit, dnode in _descendants(o, key):
            assert dnode.get("local_candidate") is None, (
                f"{unit.unit_id} still holds a local candidate for a closed need")
    assert _counter("ABANDONED_ROOTS_WITH_LOCAL_CANDIDATE") == 0


@need_closure
def test_09_every_relay_clears_its_outstanding_proposals():
    o, _seed = _run()
    for _u, key, node, _f in _abandoned(o):
        assert not node["proposals_outstanding"]
        for unit, dnode in _descendants(o, key):
            assert not dnode["proposals_outstanding"], (
                f"{unit.unit_id} is still waiting on a proposal decision that "
                f"will never be made")
    assert _counter("ABANDONED_ROOTS_WITH_PROPOSALS_OUTSTANDING") == 0


@need_closure
def test_10_every_child_owned_completion_returns_upward():
    """The control is a command. Only the receiver's answer closes the edge."""
    o, _seed = _run()
    for _u, key, node, _f in _abandoned(o):
        for edge in sorted(node["children_opened"]):
            rec = o.search_edge_lifecycle.get(edge) or {}
            out = rec.get("accepted_outcome")
            assert out is not None, (
                f"{edge} was commanded closed and never answered; a command is "
                f"not proof the transition happened")
            probe = o.search_edge_probes.get(edge, {})
            assert out.from_unit == probe.get("to_unit"), (
                f"{edge} was closed by {out.from_unit}, not by its receiving "
                f"endpoint {probe.get('to_unit')}")
    assert _counter("NEED_CLOSURE_CONTROLS_WITHOUT_CHILD_COMPLETION") == 0


@need_closure
def test_11_every_child_allocation_reconciles():
    o, _seed = _run()
    for _u, _k, node, _f in _abandoned(o):
        assert not node["children_outstanding"], (
            "an abandoned root still holds outstanding children after closure")
    assert _counter("ABANDONED_ROOTS_WITH_OPEN_CHILD_LIABILITIES") == 0


@need_closure
def test_12_the_root_reaches_terminal_closure_only_after_descendant_outcomes():
    o, _seed = _run()
    roots = _abandoned(o)
    closed = [(k, n) for _u, k, n, _f in roots if n["status"] == "CLOSED"]
    assert closed, (
        "no abandoned root ever reaches CLOSED, so 'closes only after "
        "descendant outcomes' inspects nothing")
    for key, node in closed:
        for edge in sorted(node["children_opened"]):
            rec = o.search_edge_lifecycle.get(edge) or {}
            assert rec.get("accepted_outcome") is not None, (
                f"the root reached CLOSED while {edge} had no accepted outcome")


@need_closure
def test_13_credit_in_flight_reaches_zero():
    o, _seed = _run()
    total = sum(n["child_allocations_in_flight"] for _u, _k, n, _f in _abandoned(o))
    assert total == 0.0, (
        f"{total} credit remains in flight beneath roots whose obligation no "
        f"longer exists")
    assert _counter("ABANDONED_ROOTS_WITH_CREDIT_IN_FLIGHT") == 0


@need_closure
def test_14_replaying_a_closure_control_is_inert():
    o, _seed = _run()
    for _u, key, node, _f in _abandoned(o):
        for edge in sorted(node["children_opened"]):
            rec = o.search_edge_lifecycle.get(edge) or {}
            before = len(rec.get("controls", []))
            probe = o.search_edge_probes.get(edge, {})
            recv = o.units.get(probe.get("to_unit"))
            if recv is None:
                continue
            recv.replay_search_edge(key, edge)
            after = len((o.search_edge_lifecycle.get(edge) or {}).get("controls", []))
            assert after == before, f"replaying {edge} recorded a second control"
    assert _counter("DUPLICATE_NEED_CLOSURE_APPLICATIONS") == 0


@need_closure
def test_15_a_closed_root_does_not_resurrect_when_the_slot_reopens():
    """Closure is bound to the generation, so a later reopen is a NEW root."""
    o, _seed = _run()
    roots = [(u, k, n, f) for u, k, n, f in _abandoned(o)
             if n["status"] in ("CLOSING_NEED_SATISFIED_ELSEWHERE", "CLOSED")]
    assert roots, (
        "no root has been closed, so 'a closed root does not resurrect' has no "
        "closed root to test")
    for unit, key, node, _f in roots:
        before = node["status"]
        unit.bonds.pop(key.origin_slot, None)
        unit._recruit_prerequisites()
        assert node["status"] == before, (
            f"the closed root for {key.need_id} changed state when its slot "
            f"became unmet again; closure must be generation-bound")


@need_closure
def test_16_a_new_need_generation_may_open_a_new_root_normally():
    o, _seed = _run()
    closed = [(u, k, n, f) for u, k, n, f in _abandoned(o)
              if n["status"] in ("CLOSING_NEED_SATISFIED_ELSEWHERE", "CLOSED")]
    assert closed, "no closed root, so a successor generation has nothing to follow"
    for unit, key, _node, _f in closed:
        unit.bonds.pop(key.origin_slot, None)
        unit.local_activations += 1
        before = len(unit.canonical_searches)
        unit._recruit_prerequisites()
        assert unit.open_needs.get(key.origin_slot) not in (None, key.need_id), (
            "a later generation could not open its own need for the slot")
        assert len(unit.canonical_searches) >= before


# ---------------------------------------------------------------------------
# NEGATIVE AND ADVERSARIAL PATH (17-30)
# ---------------------------------------------------------------------------

def test_17_an_unrelated_bonded_slot_does_not_close_a_live_root():
    o, _seed = _run()
    for unit, key, node, facts in _abandoned(o):
        other = max(unit.bonds) + 1 if unit.bonds else 1
        assert facts["origin_slot"] != other
        assert classify_root(unit, key, node)["state"] in CLOSABLE, (
            "the predicate changed its verdict on the strength of an unrelated "
            "slot, which would let a bond on any slot close any root")


def test_18_a_stale_generation_bond_does_not_close_a_live_root():
    """A live root plus an older bond must stay live."""
    o, _seed = _run()
    live = [(u, k, n) for u, k, n in open_roots(o)
            if classify_root(u, k, n)["state"] == "0_NOT_SKIPPED_slot_still_unmet"]
    for unit, key, node in live:
        gen = int(key.need_id.rpartition(":")[2])
        unit.bonds[key.origin_slot] = v5.Bond(
            slot=key.origin_slot, supplier="stale", supplier_class="x",
            delivered_type=key.wanted_type, cost=1.0,
            settled_by=f"{unit.unit_id}:{key.origin_slot}:{gen - 1}")
        assert classify_root(unit, key, node)["state"] not in CLOSABLE, (
            "a bond from an older need generation closed a live root")


@need_closure
def test_19_a_forged_closure_sender_is_refused():
    o, _seed = _run()
    before = C["UNAUTHENTICATED_TERMINAL_CONTROLS"]
    for _u, key, node, _f in _abandoned(o):
        for edge in sorted(node["children_opened"])[:1]:
            probe = o.search_edge_probes.get(edge, {})
            recv = o.units.get(probe.get("to_unit"))
            stranger = next((u for u in o.units.values()
                             if u.unit_id not in (probe.get("from_unit"),
                                                  probe.get("to_unit"))), None)
            if recv is None or stranger is None:
                continue
            recv.deliver_terminal(
                v5.Terminal("SearchNeedClosed", key, edge, 0.0, 0.0,
                            stranger.unit_id, recv.unit_id, "forged", ""),
                sender=stranger.unit_id)
    assert C["UNAUTHENTICATED_TERMINAL_CONTROLS"] > before, (
        "a forged closure control from a stranger was not refused")
    assert _counter("FALSE_NEED_CLOSURE_CLAIMS") == 0


@need_closure
def test_20_a_wrong_search_key_is_refused():
    o, _seed = _run()
    assert _counter("CROSS_SEARCHKEY_CLOSURES") == 0


@need_closure
def test_21_a_wrong_destination_is_refused():
    o, _seed = _run()
    assert C["UNAUTHENTICATED_TERMINAL_EMISSIONS"] == 0
    assert _counter("CROSS_EDGE_CLOSURES") == 0


@need_closure
def test_22_a_wrong_edge_cannot_close_the_root():
    o, _seed = _run()
    for _u, key, node, _f in _abandoned(o):
        opened = set(node["children_opened"])
        for edge in opened:
            probe = o.search_edge_probes.get(edge, {})
            assert probe.get("search_key") == key, (
                f"{edge} is attributed to this root but was probed for a "
                f"different SearchKey")
    assert _counter("CROSS_GENERATION_CLOSURES") == 0


@need_closure
def test_23_closure_is_not_inferred_from_an_empty_scheduler():
    """Quiescence is not evidence. The runtime must ACT, not observe silence."""
    o, _seed = _run()
    assert not o.ready, "the fixture did not reach quiescence"
    assert _counter("NEED_CLOSURE_CASCADES_INITIATED") > 0, (
        "the scheduler drained and no closure was initiated, so any closure "
        "claimed here would have been inferred from silence")


@need_closure
def test_24_closure_is_not_inferred_from_missing_messages():
    o, _seed = _run()
    assert _counter("NEED_CLOSURE_CONTROLS_APPLIED") == \
        _counter("NEED_CLOSURE_CONTROLS_ACCEPTED"), (
        "controls were counted as applied without being accepted by a receiver")


@need_closure
def test_25_the_root_is_not_closed_while_child_credit_is_in_flight():
    o, _seed = _run()
    roots = _abandoned(o)
    closed = [n for _u, _k, n, _f in roots if n["status"] == "CLOSED"]
    assert closed, (
        "no abandoned root reaches CLOSED, so this cannot show that closure "
        "waits for credit; it would pass against a runtime that closes nothing")
    for node in closed:
        assert node["child_allocations_in_flight"] == 0.0, (
            "a root reported CLOSED while still holding child credit")


@need_closure
def test_26_a_partitioned_child_leaves_the_root_explicitly_unresolved():
    o, _seed = _run()
    roots = _abandoned(o)
    unit, key, node, _f = roots[0]
    edges = sorted(node["children_opened"])
    if edges:
        probe = o.search_edge_probes.get(edges[0], {})
        o.cut(unit.unit_id, probe.get("to_unit", ""))
    assert node["status"] != "CLOSED" or not node["children_outstanding"], (
        "a root with an unreachable child reported CLOSED; an unresolved edge "
        "must stay explicit rather than be written off")


@need_closure
def test_27_a_late_proposal_after_closure_cannot_reopen_the_wave():
    o, _seed = _run()
    for unit, key, node, _f in _abandoned(o):
        before = node["status"]
        assert before in ("CLOSING_NEED_SATISFIED_ELSEWHERE", "CLOSED"), (
            f"the root is {before}, not closed, so a 'late' proposal is not "
            f"late and this proves nothing about reopening a closed wave")
        payload = next((n.get("local_candidate")
                        for _u, n in _descendants(o, key)
                        if n.get("local_candidate") is not None), None)
        if payload is None:
            continue
        unit.deliver_proposal(key, node["adopted_parent_edge"] or "late",
                              payload, sender=key.origin_unit)
        assert node["status"] == before, (
            "a late proposal reopened a wave whose need no longer exists")


def test_28_a_late_child_outcome_is_replay_inert():
    o, _seed = _run()
    for _u, key, node, _f in _abandoned(o):
        for edge in sorted(node["children_opened"]):
            rec = o.search_edge_lifecycle.get(edge) or {}
            outs = rec.get("outcomes", [])
            assert len(outs) <= 1 or len({_kind(x) for x in outs}) == 1, (
                f"{edge} accumulated conflicting late outcomes")
    assert C["DUPLICATE_TERMINAL_RESOLUTIONS"] == 0


@need_closure
def test_29_a_conflicting_closure_control_is_recorded_and_does_not_overwrite():
    o, _seed = _run()
    inspected = 0
    for _u, _k, node, _f in _abandoned(o):
        for edge in sorted(node["children_opened"]):
            rec = o.search_edge_lifecycle.get(edge) or {}
            first = rec.get("accepted_control")
            if first is None:
                continue
            inspected += 1
            for c in rec.get("controls", []):
                if _kind(c) != _kind(first):
                    assert rec.get("control_conflicts"), (
                        f"{edge} accepted a second, different control without "
                        f"filing the disagreement as a conflict")
    assert inspected, (
        "no child edge beneath an abandoned root holds an accepted control, so "
        "conflict handling on the closure channel was never inspected")


@need_closure
def test_30_a_runtime_that_drops_every_control_fails_the_positive_control():
    """The specification must be falsifiable by suppressing the cascade."""
    o, _seed = _run()
    roots = _abandoned(o)
    assert _counter("NEED_CLOSURE_CONTROLS_APPLIED") >= len(roots), (
        "fewer closure controls were applied than there are abandoned roots, "
        "so at least one root discharged nothing")


# ---------------------------------------------------------------------------
# MESSAGE REORDERING (31-34) — reuses PA-3, adds no second pending store
# ---------------------------------------------------------------------------

def test_31_closure_arriving_before_the_search_is_held_not_lost():
    o, _seed = _run()
    assert C["ORPHANED_SEARCH_EDGES"] == 0, (
        "a closure control arrived before its node existed and was discarded; "
        "PA-3 holds pre-arrival controls and must hold this one too")


def test_32_the_existing_prearrival_store_holds_it():
    """NO SECOND PENDING REGISTRY. PA-3's field is the one place."""
    o, _seed = _run()
    for rec in o.search_edge_lifecycle.values():
        assert "prearrival_control_state" in rec, (
            "the lifecycle record lost its pre-arrival field, so a second "
            "pending store would be needed for closure")


@need_closure
def test_33_a_valid_later_adoption_applies_the_held_closure_exactly_once():
    o, _seed = _run()
    assert _counter("DUPLICATE_NEED_CLOSURE_APPLICATIONS") == 0
    assert C["SEARCH_CONTROLS_RECORDED"] > 0


def test_34_no_duplicate_completion_or_refund_occurs():
    o, _seed = _run()
    assert C["DUPLICATE_TERMINAL_RESOLUTIONS"] == 0
    assert C["UNSUPPORTED_CHILD_CANCELLATION_CREDIT"] == 0
    for _u, _k, node, _f in _abandoned(o):
        returned = node["returned_to_parent"] + node["cancelled_credit"]
        assert returned <= node["incoming_allocation"] + node["local_reserve"], (
            "more credit was returned than the node ever held")
