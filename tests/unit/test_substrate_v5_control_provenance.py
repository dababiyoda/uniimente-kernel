"""2B: provenance for the CONTROL plane, and fail-closed accounting.

PRE-REGISTERED BEFORE THE CORRESPONDING RUNTIME CHANGE. Strict xfail throughout,
so a spec that starts passing is reported as a FAILURE until its marker is
removed in a reviewable commit.

WHY THIS FILE EXISTS. Commit 2A (`011e238`) bound the DATA plane: a proposal must
now arrive on an edge the node opened, from that edge's recorded target, and at
the source hop must name the unit actually offering itself. The CONTROL plane
was left unbound, which restores the same class of route forgery by a different
door:

  1. REJECTION CONTROLS ARE NOT SENDER-AUTHENTICATED.
     `deliver_proposal_rejected` receives `sender` and never compares it with the
     node's immutable `adopted_parent_sender`. It checks only that the supplied
     edge id equals `adopted_parent_edge` -- a value any neighbour can name --
     and then marks the proposal rejected, drops it from
     `proposals_outstanding`, and either clears the source candidate or
     propagates the rejection downward. Any neighbour can therefore SUPPRESS a
     valid candidate.

  2. ACKNOWLEDGEMENTS ARE NOT SENDER-AUTHENTICATED.
     `deliver_search_ack` receives `sender` and never compares it with
     `child_targets[edge_id]`. A different neighbour can close another child's
     allocation: populate `child_confirmed`, complete the edge, reduce
     `child_allocations_in_flight`, classify refund and consumption, and drive
     the search onward. This is the 2A route-forgery defect committed through
     accounting instead of candidate registration.

  3. MALFORMED ACKNOWLEDGEMENTS FAIL OPEN.
     The values are CLAMPED before they are validated:

         refund   = max(0.0, min(refund, per))
         consumed = max(0.0, min(consumed, per - refund))

     If the result still does not reconcile, the code increments
     UNSUPPORTED_CHILD_CANCELLATION_CREDIT and proceeds anyway -- recording the
     acknowledgement, completing the edge, moving credit and advancing the
     protocol. A violation counter is evidence; it is not authorization to
     mutate state after validation has failed. NaN is worse than merely
     unclamped: every comparison against it is false, so it passes each guard
     untouched and poisons the ledger silently.

  4. TERMINAL CONTROLS DISCARD THE IMMEDIATE SENDER.
     `Unit.step` passes `sender` into proposal delivery, rejection and
     acknowledgement, and then calls `deliver_terminal` WITHOUT it. A terminal
     naming the adopted parent edge is accepted as a wave-closing command
     without proving the sender was the adopted parent, so a neighbour can forge
     closure using a structurally valid edge id.

DECLARED SEAMS the corrected runtime must provide:

    Unit.deliver_terminal(key, edge, kind, refund, proposal_id, sender,
                          from_unit, to_unit)
    Unit.deliver_proposal_rejected(...)  sender checked against
                                         node["adopted_parent_sender"]
    Unit.deliver_search_ack(...)         sender checked against
                                         node["child_targets"][edge]; raw values
                                         validated BEFORE any normalization

New counters, all of which a correct live run leaves at zero:

    UNAUTHENTICATED_REJECTION_CONTROLS
    UNAUTHENTICATED_SEARCH_ACKS
    UNAUTHENTICATED_TERMINAL_CONTROLS
    MALFORMED_SEARCH_ACKS

Single Bottleneck Metric:

    AUTHENTICATED_CONTROL_TRANSITIONS / TOTAL_CONTROL_TRANSITIONS == 1.0
"""
from __future__ import annotations

import math
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

# Distinct from `spec`, `live`, `inherited` and `core`.
control = pytest.mark.xfail(
    strict=True,
    reason="Single-Flight 2B control-plane provenance is not implemented yet")


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
                constraint_generation=0,
                policy_snapshot=())
    base.update(kw)
    return v5.SearchContext(**base)


def _kind(x):
    return getattr(x, "kind", x)


def _counter(name):
    assert name in C.d, (
        f"the runtime defines no {name} counter, so the behaviour it names "
        f"cannot be measured and this specification cannot be satisfied")
    return C[name]


def _relay_node():
    """A node with an immutable adopted parent AND at least two child edges.

    Seed-scanned then hard asserted: a required adversarial condition must not
    vanish because one seed produced a relay with a single neighbour.
    """
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
            need_id="probe:control", work_item_generation=2,
            origin_unit=j.unit_id, origin_slot=slot,
            wanted_type=j.capability.accepts[slot], context=ctx)
        # A unit that does NOT produce the wanted type, so it relays and opens a
        # real child frontier instead of answering locally.
        relay = next((u for u in o.units.values()
                      if u.unit_id not in (ENV, SINK) and u.unit_id != j.unit_id
                      and u.capability.produces != key.wanted_type), None)
        if relay is None:
            continue
        relay.deliver_search(key, "e/parent", allocation=18.0,
                             lineage=(j.unit_id,), sender=j.unit_id, context=ctx,
                             transport=v5.HARNESS_DELIVERY)
        node = relay.canonical_searches.get(key)
        if node is None:
            continue
        kids = list(node["children_opened"])
        if len(kids) < 2:
            continue
        if len({node["child_targets"][k] for k in kids[:2]}) < 2:
            continue
        assert node["adopted_parent_edge"] == "e/parent"
        assert node["adopted_parent_sender"] == j.unit_id
        return o, j, relay, ctx, key, node, kids, seed
    raise AssertionError(
        "no relay node with an adopted parent and two distinct child targets "
        "was constructible across the pre-registered seeds; failing to build "
        "the structure is a failure of this specification, not a reason to "
        "skip it")


def _register_proposal(o, relay, node, edge):
    """A proposal that is valid in EVERY respect, registered and outstanding."""
    target = node["child_targets"][edge]
    cand = o.units[target]
    pay = v5.SearchOfferPayload(
        proposal_id="label", search_key=node["search_key"],
        context_digest=node["search_context"].context_digest(),
        supplier=target, supplier_class=cand.capability.klass(),
        offered_type=node["search_key"].wanted_type, cost=cand.capability.cost,
        firm=not cand.unmet(), derivation_chain=cand._derives_from(),
        source_node=target, source_edge_id=edge)
    relay.deliver_proposal(node["search_key"], edge, pay, target)
    assert node["proposal_routes"].get(pay.proposal_id) == edge, (
        "the control proposal was not registered, so suppressing it below "
        "would prove nothing")
    assert pay.proposal_id in node["proposals_outstanding"]
    return pay


def _other_neighbour(o, relay, node, exclude):
    """A real unit that is NOT any of `exclude`. An impostor, not a fiction."""
    for uid in sorted(o.units):
        if uid in (ENV, SINK) or uid in exclude or uid == relay.unit_id:
            continue
        return uid
    raise AssertionError("no impostor unit available in this fixture")


def _snapshot(o, relay, node):
    """Everything an unauthenticated control must leave exactly as it found."""
    return {
        "status": node["status"],
        "outstanding": set(node["proposals_outstanding"]),
        "rejected": set(node.get("proposals_rejected", ())),
        "routes": dict(node["proposal_routes"]),
        "children_outstanding": set(node["children_outstanding"]),
        "children_completed": set(node["children_completed"]),
        "confirmed": dict(node["child_confirmed"]),
        "in_flight": node["child_allocations_in_flight"],
        "reserve": node["local_reserve"],
        "consumed": node["consumed_credit"],
        "cancelled": node["cancelled_credit"],
        "returned": node["returned_to_parent"],
        "refunds": node["child_refunds_received"],
        "eligible": node["eligible_offer"],
        "candidate": node.get("local_candidate"),
        "accepted": node["accepted_proposal_id"],
        "wave_cancelled": node["wave_cancelled"],
        "terminal_sent": node["terminal_signal_sent"],
        "ack_sent": node["ack_sent"],
        "terminals": {e: [_kind(x) for x in r["outcomes"]]
                      for e, r in o.search_edge_terminals.items()},
        "outbox": list(relay.outbox),
        "children_opened": list(node["children_opened"]),
    }


# ---------------------------------------------------------------------------
# 1. Rejection controls must be sender-authenticated
# ---------------------------------------------------------------------------

@control
def test_a_rejection_from_the_wrong_sender_cannot_suppress_a_proposal():
    """`adopted_parent_edge` is a value any neighbour can name.

    Authenticating on it alone lets any unit that knows the edge id cancel a
    valid candidate, which is a denial-of-repair primitive: the origin never
    decided, and the wave behaves as though it had.
    """
    o, j, relay, ctx, key, node, kids, seed = _relay_node()
    pay = _register_proposal(o, relay, node, kids[0])
    impostor = _other_neighbour(o, relay, node, {j.unit_id})
    assert impostor != node["adopted_parent_sender"]
    before = _snapshot(o, relay, node)
    reset()

    relay.deliver_proposal_rejected(key, node["adopted_parent_edge"],
                                    pay.proposal_id, "forged", impostor)

    assert _snapshot(o, relay, node) == before, (
        f"{impostor} suppressed a proposal by naming the adopted parent edge "
        f"without being the adopted parent")
    assert pay.proposal_id in node["proposals_outstanding"]
    assert pay.proposal_id not in node.get("proposals_rejected", set())
    assert _counter("UNAUTHENTICATED_REJECTION_CONTROLS") == 1

    # PAIRED POSITIVE CONTROL: the identical message from the real parent.
    reset()
    relay.deliver_proposal_rejected(key, node["adopted_parent_edge"],
                                    pay.proposal_id, "duplicate_supplier",
                                    node["adopted_parent_sender"])
    assert pay.proposal_id not in node["proposals_outstanding"], (
        "the identical rejection was refused even from the real adopted parent, "
        "so the refusal above cannot be attributed to sender identity")
    assert pay.proposal_id in node["proposals_rejected"]
    assert _counter("UNAUTHENTICATED_REJECTION_CONTROLS") == 0


# ---------------------------------------------------------------------------
# 2. Acknowledgements must be sender-authenticated
# ---------------------------------------------------------------------------

@control
def test_an_ack_from_another_child_cannot_close_this_childs_allocation():
    o, j, relay, ctx, key, node, kids, seed = _relay_node()
    a, b = kids[0], kids[1]
    target_a = node["child_targets"][a]
    target_b = node["child_targets"][b]
    assert target_a != target_b
    per = node["child_allocations"][a]
    before = _snapshot(o, relay, node)
    reset()

    relay.deliver_search_ack(key, a, per, 0.0, target_b)

    assert _snapshot(o, relay, node) == before, (
        f"{target_b} closed {target_a}'s allocation on edge {a}")
    assert a not in node["child_confirmed"]
    assert a in node["children_outstanding"]
    assert _counter("UNAUTHENTICATED_SEARCH_ACKS") == 1

    # PAIRED POSITIVE CONTROL: the identical acknowledgement from A's own target.
    reset()
    relay.deliver_search_ack(key, a, per, 0.0, target_a)
    assert node["child_confirmed"].get(a) is not None, (
        "the identical acknowledgement was refused even from the edge's real "
        "target, so the refusal above cannot be attributed to sender identity")
    assert a not in node["children_outstanding"]
    assert _counter("UNAUTHENTICATED_SEARCH_ACKS") == 0
    assert _counter("MALFORMED_SEARCH_ACKS") == 0


# ---------------------------------------------------------------------------
# 3. Malformed acknowledgements must fail CLOSED
# ---------------------------------------------------------------------------

def _malformed_cases(per):
    return [
        ("under", per / 4.0, per / 4.0),
        ("over", per, per),
        ("negative_refund", -per, per * 2.0),
        ("negative_consumed", per * 2.0, -per),
        ("nan_refund", float("nan"), 0.0),
        ("inf_consumed", 0.0, float("inf")),
    ]


@control
@pytest.mark.parametrize("label", [c[0] for c in _malformed_cases(4.0)])
def test_a_malformed_acknowledgement_changes_nothing(label):
    """Clamping is not validation.

    Normalizing a child's claim into something that looks lawful, and then
    proceeding when it still does not reconcile, converts a detected violation
    into a state transition. NaN is the sharpest case: every comparison against
    it is false, so it survives each guard untouched and poisons the ledger
    without tripping anything.
    """
    o, j, relay, ctx, key, node, kids, seed = _relay_node()
    a = kids[0]
    per = node["child_allocations"][a]
    target = node["child_targets"][a]
    refund, consumed = next((r, c) for lbl, r, c in _malformed_cases(per)
                            if lbl == label)
    before = _snapshot(o, relay, node)
    reset()

    relay.deliver_search_ack(key, a, refund, consumed, target)

    assert _snapshot(o, relay, node) == before, (
        f"a malformed acknowledgement ({label}: refund={refund}, "
        f"consumed={consumed}, allocation={per}) mutated node state")
    assert a not in node["child_confirmed"], "malformed evidence was recorded"
    assert a in node["children_outstanding"], "the edge was completed anyway"
    assert not math.isnan(node["child_allocations_in_flight"])
    assert not math.isnan(node["local_reserve"])
    assert not math.isnan(node["consumed_credit"])
    assert _counter("MALFORMED_SEARCH_ACKS") == 1

    # PAIRED POSITIVE CONTROL: a well-formed acknowledgement on the same edge.
    reset()
    relay.deliver_search_ack(key, a, per / 2.0, per / 2.0, target)
    assert node["child_confirmed"].get(a) is not None, (
        "a well-formed acknowledgement was refused on the same edge, so the "
        "refusal above cannot be attributed to the malformed values")
    assert _counter("MALFORMED_SEARCH_ACKS") == 0


# ---------------------------------------------------------------------------
# 4. Terminal controls must be sender- and direction-bound
# ---------------------------------------------------------------------------

@control
def test_a_forged_parent_command_cannot_close_the_wave():
    o, j, relay, ctx, key, node, kids, seed = _relay_node()
    pay = _register_proposal(o, relay, node, kids[0])
    impostor = _other_neighbour(o, relay, node, {j.unit_id})
    before = _snapshot(o, relay, node)
    reset()

    relay.deliver_terminal(key, node["adopted_parent_edge"], "SearchCommitted",
                           0.0, pay.proposal_id, sender=impostor)

    assert _snapshot(o, relay, node) == before, (
        f"{impostor} closed the wave by naming the adopted parent edge without "
        f"being the adopted parent")
    assert not node["wave_cancelled"]
    assert node["status"] == "OPEN"
    assert _counter("UNAUTHENTICATED_TERMINAL_CONTROLS") == 1

    # PAIRED POSITIVE CONTROL: the identical command from the real parent.
    reset()
    relay.deliver_terminal(key, node["adopted_parent_edge"], "SearchCommitted",
                           0.0, pay.proposal_id,
                           sender=node["adopted_parent_sender"])
    assert node["wave_cancelled"], (
        "the identical command was refused even from the real adopted parent, "
        "so the refusal above cannot be attributed to sender identity")
    assert node["status"] == "COMMITTED"
    assert _counter("UNAUTHENTICATED_TERMINAL_CONTROLS") == 0


@control
def test_a_child_terminal_from_the_wrong_sender_moves_no_credit():
    o, j, relay, ctx, key, node, kids, seed = _relay_node()
    a, b = kids[0], kids[1]
    target_a = node["child_targets"][a]
    target_b = node["child_targets"][b]
    before = _snapshot(o, relay, node)
    reset()

    relay.deliver_terminal(key, a, "SearchExhausted",
                           node["child_allocations"][a], "", sender=target_b)

    assert _snapshot(o, relay, node) == before, (
        f"{target_b} completed {target_a}'s child edge {a}")
    assert a in node["children_outstanding"]
    assert _counter("UNAUTHENTICATED_TERMINAL_CONTROLS") == 1

    reset()
    relay.deliver_terminal(key, a, "SearchExhausted",
                           node["child_allocations"][a], "", sender=target_a)
    assert a not in node["children_outstanding"], (
        "the identical terminal was refused even from the edge's real target")
    assert _counter("UNAUTHENTICATED_TERMINAL_CONTROLS") == 0


@control
def test_a_parent_command_arriving_on_a_child_edge_is_refused():
    """Direction is not decorative. A wave-closing command travels DOWN."""
    o, j, relay, ctx, key, node, kids, seed = _relay_node()
    a = kids[0]
    target_a = node["child_targets"][a]
    before = _snapshot(o, relay, node)
    reset()

    relay.deliver_terminal(key, a, "SearchCommitted", 0.0, "", sender=target_a)

    assert _snapshot(o, relay, node) == before, (
        "a child sent a wave-closing command up its own edge and it was obeyed")
    assert node["status"] == "OPEN"
    assert _counter("UNAUTHENTICATED_TERMINAL_CONTROLS") == 1


@control
def test_terminal_identity_fields_must_agree_with_the_actual_route():
    """A field inside the message is a claim, not evidence.

    `Terminal.from_unit` and `Terminal.to_unit` are written by the sender. If the
    receiver trusts them over the route the message actually took, they become a
    second, forgeable identity channel.
    """
    o, j, relay, ctx, key, node, kids, seed = _relay_node()
    a = kids[0]
    target_a = node["child_targets"][a]
    impostor = _other_neighbour(o, relay, node, {j.unit_id, target_a})
    before = _snapshot(o, relay, node)
    reset()

    relay.deliver_terminal(key, a, "SearchExhausted",
                           node["child_allocations"][a], "", sender=target_a,
                           from_unit=impostor, to_unit=relay.unit_id)
    assert _snapshot(o, relay, node) == before, (
        "a terminal whose from_unit contradicts the route it arrived on was "
        "accepted")
    assert _counter("UNAUTHENTICATED_TERMINAL_CONTROLS") == 1

    reset()
    relay.deliver_terminal(key, a, "SearchExhausted",
                           node["child_allocations"][a], "", sender=target_a,
                           from_unit=target_a, to_unit=impostor)
    assert _snapshot(o, relay, node) == before, (
        "a terminal addressed to another unit was accepted")
    assert _counter("UNAUTHENTICATED_TERMINAL_CONTROLS") == 1

    reset()
    relay.deliver_terminal(key, a, "SearchExhausted",
                           node["child_allocations"][a], "", sender=target_a,
                           from_unit=target_a, to_unit=relay.unit_id)
    assert a not in node["children_outstanding"], (
        "a terminal whose identity fields agree with its route was refused")
    assert _counter("UNAUTHENTICATED_TERMINAL_CONTROLS") == 0


# ---------------------------------------------------------------------------
# 5. Authenticated control replay is inert; unauthenticated replay stays refused
# ---------------------------------------------------------------------------

@control
def test_authenticated_control_replay_changes_nothing_further():
    o, j, relay, ctx, key, node, kids, seed = _relay_node()
    a = kids[0]
    target_a = node["child_targets"][a]
    pay = _register_proposal(o, relay, node, kids[1])
    reset()

    relay.deliver_search_ack(key, a, node["child_allocations"][a], 0.0, target_a)
    relay.deliver_proposal_rejected(key, node["adopted_parent_edge"],
                                    pay.proposal_id, "duplicate_supplier",
                                    node["adopted_parent_sender"])
    after_first = _snapshot(o, relay, node)
    counters_first = C.snapshot()

    for _ in range(4):
        relay.deliver_search_ack(key, a, node["child_allocations"][a], 0.0,
                                 target_a)
        relay.deliver_proposal_rejected(key, node["adopted_parent_edge"],
                                        pay.proposal_id, "duplicate_supplier",
                                        node["adopted_parent_sender"])
    assert _snapshot(o, relay, node) == after_first, (
        "replaying an authenticated control produced a further transition")
    assert C.snapshot() == counters_first, (
        "replaying an authenticated control moved a counter")

    # An unauthenticated replay stays refused and grows nothing but its own
    # violation evidence.
    impostor = _other_neighbour(o, relay, node, {j.unit_id, target_a})
    for _ in range(3):
        relay.deliver_search_ack(key, a, node["child_allocations"][a], 0.0,
                                 impostor)
    assert _snapshot(o, relay, node) == after_first, (
        "a replayed unauthenticated acknowledgement mutated state")
    assert _counter("UNAUTHENTICATED_SEARCH_ACKS") == 3
