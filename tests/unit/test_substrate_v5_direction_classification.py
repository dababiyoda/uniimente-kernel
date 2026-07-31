"""Commit 5K: a message's CHANNEL follows its direction, not its name.

PRE-REGISTERED BEFORE THE CORRESPONDING RUNTIME CHANGE. Strict xfail throughout.

THE DEFECT, IN MY OWN 5B DISPATCHER.

`_record_terminal` classifies by kind alone:

    if t.kind in PARENT_CONTROL_KINDS:
        return self._record_control(t)
    return self._record_outcome(t)

and `SearchNeedClosed` is a member of BOTH tuples:

    PARENT_CONTROL_KINDS = ("SearchCommitted", "SearchCancelled",
                            "SearchNeedClosed")
    CHILD_OUTCOME_KINDS  = (..., "SearchNeedClosed")

so EVERY `SearchNeedClosed` enters the control channel -- including the
child-emitted one that `deliver_search` legitimately produces when
`key.need_id in self.closed_needs`. That outcome therefore never closes its
edge, never writes credit, and leaves the opener holding an allocation it can
never reconcile. It is the same class of defect the split was built to remove,
reintroduced by the dispatcher that was supposed to end it.

The kind is genuinely ambiguous and should stay ambiguous: an opener closing a
need downward and a receiver reporting a closed need upward are different facts
that share a name honestly. What must not be ambiguous is the CHANNEL.

THE CLASSIFICATION RULE THIS FILE REQUIRES. `_may_emit` already computes the
emitter's role from the sender-created probe -- it knows whether this unit is
the edge's recorded `to_unit` (a receiver, which may emit child outcomes) or its
recorded `from_unit` (the opener, which may emit parent controls). That role is
the classification, and it is already established before anything is recorded.
The dispatcher simply does not use it.

    role = receiver (edge's to_unit)  -> OUTCOME channel
    role = opener   (edge's from_unit) -> CONTROL channel

No kind-based tie-breaking, so an ambiguous kind cannot be routed by its name.
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
SEEDS = tuple(range(60))

direction = pytest.mark.xfail(
    strict=True,
    reason="edge-role classification is not implemented; the dispatcher still "
           "routes by kind alone")


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


def _ctx(**kw):
    base = dict(causally_refused_sources=frozenset(),
                must_differ_from_suppliers=frozenset(),
                maximum_supplier_cost=99.0,
                cooldown_excluded_suppliers=frozenset(),
                constraint_generation=0, policy_snapshot=())
    base.update(kw)
    return v5.SearchContext(**base)


def _kind(x):
    return getattr(x, "kind", x)


def _pair():
    """An origin, a real NEIGHBOUR of it, and a key. Seed-scanned, hard asserted."""
    for seed in SEEDS:
        o = _build_raw(4, seed, 0.8)
        F.prepare(o)
        reset()
        o.commission()
        if not o.result_ok(o.run_item(PAYLOAD_A)):
            continue
        j = _join(o)
        if j is None or len(j.bonds) != 2:
            continue
        slot = min(j.bonds)
        o.units[j.bonds[slot].supplier].silent = True
        reset()
        ctx = _ctx()
        key = v5.SearchKey.build(
            need_id="probe:direction", work_item_generation=2,
            origin_unit=j.unit_id, origin_slot=slot,
            wanted_type=j.capability.accepts[slot], context=ctx)
        nbrs = sorted(n for n in j.neighbours if n not in (ENV, SINK))
        if len(nbrs) < 1:
            continue
        target = o.units[nbrs[0]]
        if j.unit_id in target.neighbours:
            return o, j, target, ctx, key, seed
    raise AssertionError(
        "no adjacent origin/receiver pair across the pre-registered seeds; "
        "failing to build the structure is a failure of this specification, "
        "not a reason to skip it")


def _open(o, sender, target, key, edge, allocation=6.0):
    sender._record_probe(edge, sender.unit_id, target.unit_id, key,
                         allocation=allocation)
    return o.search_edge_probes[edge]


def _lc(o, edge):
    rec = getattr(o, "search_edge_lifecycle", None)
    assert rec is not None, "the organ exposes no canonical lifecycle record"
    r = rec.get(edge)
    assert r is not None, f"no lifecycle record for edge {edge}"
    return r


def _edge_state(o, edge):
    e = o.search_edges.get(edge, {})
    return (e.get("terminal_status", "open"), e.get("terminal_outcome"),
            e.get("refunded_credit", 0.0), e.get("consumed_credit", 0.0))


# ---------------------------------------------------------------------------
# 1. The ambiguous kind, in each direction
# ---------------------------------------------------------------------------

def test_an_opener_emitted_need_closed_is_a_control():
    """DELIBERATELY PLAIN. The downward form already lands in the control
    channel today -- by accident of kind membership rather than by rule, but it
    lands there. Marking it strict-xfail would report a satisfied requirement
    as an expected failure, and it XPASSed on the first run of this file. It is
    the paired positive control for the upward case, and a positive control has
    to be able to go red when the runtime breaks, which means it must be green
    now.
    """
    o, j, nbr, ctx, key, seed = _pair()
    edge = "e/dir/down"
    _open(o, j, nbr, key, edge)
    reset()

    j._emit_terminal("SearchNeedClosed", key, edge, nbr.unit_id)

    rec = _lc(o, edge)
    assert rec["accepted_control"] is not None, (
        "the opener's SearchNeedClosed was not recorded as a control")
    assert _kind(rec["accepted_control"]) == "SearchNeedClosed"
    assert rec["accepted_outcome"] is None, (
        "a downward SearchNeedClosed was recorded as the edge's OUTCOME")
    assert _edge_state(o, edge)[0] == "open", (
        "a parent command closed the edge")


@direction
def test_a_receiver_emitted_need_closed_is_an_outcome():
    """THE CASE THE KIND-ONLY DISPATCHER GETS WRONG.

    `deliver_search` legitimately emits this upward when the arriving key names
    a need this unit has already closed. Routed by name it lands in the control
    channel, so it never closes its edge and never writes the refund -- and the
    opener is left holding an allocation it can never reconcile.
    """
    o, j, nbr, ctx, key, seed = _pair()
    edge = "e/dir/up"
    _open(o, j, nbr, key, edge)
    reset()

    nbr._emit_terminal("SearchNeedClosed", key, edge, j.unit_id, refund=6.0)

    rec = _lc(o, edge)
    assert rec["accepted_outcome"] is not None, (
        "the receiver's SearchNeedClosed was not recorded as an outcome; "
        "routed by kind it went into the control channel")
    assert _kind(rec["accepted_outcome"]) == "SearchNeedClosed"
    assert rec["accepted_control"] is None, (
        "an upward SearchNeedClosed was recorded as a parent CONTROL")
    status, outcome, refunded, consumed = _edge_state(o, edge)
    assert status == "terminal", "the child's outcome did not close the edge"
    assert outcome == "SearchNeedClosed"
    assert refunded == 6.0, (
        "the refund the child reported was not written to the edge")


@direction
def test_the_two_forms_do_not_share_a_channel_on_one_edge():
    """Both may occur on one edge, and each lands in its own channel."""
    o, j, nbr, ctx, key, seed = _pair()
    edge = "e/dir/both"
    _open(o, j, nbr, key, edge)
    reset()

    j._emit_terminal("SearchNeedClosed", key, edge, nbr.unit_id)
    nbr._emit_terminal("SearchNeedClosed", key, edge, j.unit_id, refund=6.0)

    rec = _lc(o, edge)
    assert rec["accepted_control"] is not None and rec["accepted_outcome"] is not None, (
        "one direction displaced the other; a command and an answer sharing a "
        "kind must still occupy separate channels")
    assert rec["accepted_control"].from_unit == j.unit_id
    assert rec["accepted_outcome"].from_unit == nbr.unit_id
    assert not rec["control_conflicts"], (
        "the child's answer was filed as a conflicting COMMAND")
    assert not rec["outcome_conflicts"], (
        "the opener's command was filed as a conflicting OUTCOME")
    assert _edge_state(o, edge)[0] == "terminal"


@pytest.mark.parametrize("emitter,expected_channel", [
    pytest.param("opener", "accepted_control"),
    pytest.param("receiver", "accepted_outcome", marks=direction)])
def test_exact_replay_is_inert_in_whichever_channel_the_role_selects(
        emitter, expected_channel):
    o, j, nbr, ctx, key, seed = _pair()
    edge = f"e/dir/replay/{emitter}"
    _open(o, j, nbr, key, edge)
    reset()
    unit, to = (j, nbr.unit_id) if emitter == "opener" else (nbr, j.unit_id)

    unit._emit_terminal("SearchNeedClosed", key, edge, to, refund=0.0)
    rec = _lc(o, edge)
    assert rec[expected_channel] is not None, (
        f"the {emitter}'s emission did not reach {expected_channel}")
    before = (len(rec["controls"]), len(rec["outcomes"]), _edge_state(o, edge))

    for _ in range(3):
        unit._emit_terminal("SearchNeedClosed", key, edge, to, refund=0.0)

    rec = _lc(o, edge)
    assert (len(rec["controls"]), len(rec["outcomes"]),
            _edge_state(o, edge)) == before, (
        f"an exact {emitter} replay was not inert")
    assert not rec["control_conflicts"] and not rec["outcome_conflicts"]


# ---------------------------------------------------------------------------
# 2. The role gate is not weakened by making it role-aware
# ---------------------------------------------------------------------------

@direction
def test_a_stranger_owning_neither_end_reaches_neither_channel():
    """PAIRED with a positive control, so a runtime refusing everything fails."""
    o, j, nbr, ctx, key, seed = _pair()
    edge = "e/dir/stranger"
    _open(o, j, nbr, key, edge)
    stranger = next(u for u in o.units.values()
                    if u.unit_id not in (ENV, SINK, j.unit_id, nbr.unit_id))
    reset()

    stranger._emit_terminal("SearchNeedClosed", key, edge, j.unit_id, refund=6.0)

    lc = getattr(o, "search_edge_lifecycle", {}) or {}
    rec = lc.get(edge) or {}
    assert not rec.get("accepted_control") and not rec.get("accepted_outcome"), (
        f"{stranger.unit_id} owns neither end of {edge} and still recorded a fact")
    assert _edge_state(o, edge)[0] == "open"
    assert C["UNAUTHENTICATED_TERMINAL_EMISSIONS"] == 1

    # POSITIVE CONTROL, same edge, same kind, a legitimate endpoint.
    reset()
    nbr._emit_terminal("SearchNeedClosed", key, edge, j.unit_id, refund=6.0)
    assert _lc(o, edge)["accepted_outcome"] is not None, (
        "the legitimate receiver was also refused, so the negative case above "
        "proves nothing")


@direction
def test_classification_is_by_role_and_never_by_kind_membership():
    """THE RULE ITSELF, asserted directly.

    Every kind either endpoint may legitimately emit must land in the channel
    its ROLE selects. A dispatcher consulting `PARENT_CONTROL_KINDS` first
    cannot satisfy this for a kind in both tuples.
    """
    o, j, nbr, ctx, key, seed = _pair()
    shared = [k for k in v5.PARENT_CONTROL_KINDS
              if k in v5.CHILD_OUTCOME_KINDS]
    assert shared, (
        "no kind is ambiguous any more; if the tuples were disentangled "
        "instead, this specification should be retired deliberately rather "
        "than left passing vacuously")
    for i, kind in enumerate(shared):
        down, up = f"e/dir/role/{i}/d", f"e/dir/role/{i}/u"
        _open(o, j, nbr, key, down)
        _open(o, j, nbr, key, up)
        reset()
        j._emit_terminal(kind, key, down, nbr.unit_id)
        nbr._emit_terminal(kind, key, up, j.unit_id, refund=6.0)
        assert _lc(o, down)["accepted_control"] is not None, (
            f"{kind} from the opener did not reach the control channel")
        assert _lc(o, down)["accepted_outcome"] is None
        assert _lc(o, up)["accepted_outcome"] is not None, (
            f"{kind} from the receiver did not reach the outcome channel")
        assert _lc(o, up)["accepted_control"] is None


def test_formation_is_untouched_by_role_classification():
    """PLAIN TEST. Must hold before the mechanism exists and keep holding."""
    o = F.development(random.Random(4000))
    F.prepare(o)
    reset()
    o.commission()

    assert o.result_ok(o.run_item(PAYLOAD_A)), "formation stopped working"
    assert o.events_dispatched == 16
    assert o.messages == 1012
