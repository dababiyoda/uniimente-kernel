"""2C: fail-closed identity, valid controls, and a sealed terminal lifecycle.

PRE-REGISTERED BEFORE THE CORRESPONDING RUNTIME CHANGE. Strict xfail throughout.

WHY THIS FILE EXISTS. 2B authenticated controls that CARRY a sender. Five gaps
survive, and all of them share one shape: a check that only runs when the caller
volunteers enough information to be checked.

  1. OMITTING THE SENDER BYPASSES ALL THREE GATES. Every control handler reads

         if sender is not _UNSPECIFIED_SENDER and sender != expected: reject

     so a caller that supplies NO identity passes. `Unit.step` always supplies
     one, which is why this is not yet a live exploit -- but it is a fail-open
     protocol entrypoint, and it contradicts
     AUTHENTICATED_CONTROL_TRANSITIONS / TOTAL_CONTROL_TRANSITIONS == 1.0.
     Missing identity must be REFUSED, not read as a trusted harness.

     A harness that genuinely needs to bypass transport authentication now says
     so with an explicit capability object, `v5.HARNESS_DELIVERY`, which
     production code has no reason to construct. An omitted argument is not
     authority.

  2. MALFORMED TERMINAL REFUNDS BYPASS STRICT ACK VALIDATION. `deliver_search_ack`
     validates the raw claim and fails closed. `deliver_terminal` accepts the
     SAME closure evidence, clamps it, and writes the SAME `child_confirmed`
     ledger. An authenticated child therefore launders a negative, oversized,
     NaN or infinite refund simply by sending it as a terminal instead of an
     acknowledgement. Two doors into one ledger need one standard of evidence.

  3. AN AUTHENTICATED PARENT CAN COMMIT AN UNKNOWN PROPOSAL. A `SearchCommitted`
     from the real adopted parent is obeyed without requiring that the named
     proposal_id was ever seen here. `_close_wave_from_parent` then sets
     COMMITTED and `accepted_proposal_id` while `proposal_routes.get(pid)` is
     None, cancelling every child with no route to the supposed winner.
     Authentication answers WHO sent a command. It does not make the command
     meaningful.

  4. CLOSED WAVES ARE NOT SEALED. Commit and closure set `wave_cancelled`,
     `terminal_signal_sent` and a terminal status, but never clear
     `proposals_outstanding`, and neither proposal delivery nor rejection has a
     terminal-state gate. A late proposal can still be registered and forwarded
     after the wave has closed, and a late rejection can still mutate
     `proposals_rejected`. Closed must mean causally sealed.

  5. TERMINAL TELEMETRY IS RECORDED BEFORE THE RECEIVER AUTHENTICATES.
     `_emit_terminal` writes into the organ-wide registry and flips
     `search_edges[edge]["terminal_status"]` BEFORE the message is delivered, so
     a sender emitting an unowned or wrong-direction terminal poisons the shared
     evidence even when the receiver correctly refuses the transition. A
     sender-side claim is not authenticated edge closure.

DECLARED SEAMS:

    v5.HARNESS_DELIVERY          explicit test-only delivery capability
    Terminal-evidence validation shared with `deliver_search_ack`
    node["proposal_disposition"] {proposal_id: accepted|rejected|cancelled|
                                  need_closed} after wave closure

New counters:

    MALFORMED_TERMINAL_EVIDENCE
    UNKNOWN_COMMIT_PROPOSALS
    LATE_CONTROLS_AFTER_CLOSURE
    UNAUTHENTICATED_TERMINAL_EMISSIONS
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

# ACTIVATED. Every 2C sealed lifecycle specification in this file was satisfied by the
# runtime and its `xfail(strict=True)` marker removed in the activation
# commit. The marker is retained, unused, so a new specification written
# against an unimplemented behaviour can be pre-registered the same way.
sealing = pytest.mark.xfail(
    strict=True,
    reason="pre-registration marker for a NEW 2C sealed lifecycle specification")


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


def _counter(name):
    assert name in C.d, (
        f"the runtime defines no {name} counter, so the behaviour it names "
        f"cannot be measured and this specification cannot be satisfied")
    return C[name]


def _relay_node():
    """A relay with an immutable adopted parent and two distinct child targets."""
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
            need_id="probe:sealing", work_item_generation=2,
            origin_unit=j.unit_id, origin_slot=slot,
            wanted_type=j.capability.accepts[slot], context=ctx)
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
        if len(kids) < 2 or len({node["child_targets"][k] for k in kids[:2]}) < 2:
            continue
        return o, j, relay, ctx, key, node, kids, seed
    raise AssertionError(
        "no relay node with an adopted parent and two distinct child targets "
        "across the pre-registered seeds; failing to build the structure is a "
        "failure of this specification, not a reason to skip it")


def _proposal(o, node, edge):
    target = node["child_targets"][edge]
    cand = o.units[target]
    return v5.SearchOfferPayload(
        proposal_id="label", search_key=node["search_key"],
        context_digest=node["search_context"].context_digest(),
        supplier=target, supplier_class=cand.capability.klass(),
        offered_type=node["search_key"].wanted_type, cost=cand.capability.cost,
        firm=not cand.unmet(), derivation_chain=cand._derives_from(),
        source_node=target, source_edge_id=edge)


def _register(o, relay, node, edge):
    pay = _proposal(o, node, edge)
    relay.deliver_proposal(node["search_key"], edge, pay,
                           node["child_targets"][edge])
    assert node["proposal_routes"].get(pay.proposal_id) == edge, (
        "the control proposal was not registered, so nothing below is testing "
        "what it claims to test")
    return pay


def _snapshot(o, relay, node):
    return {
        "status": node["status"],
        "outstanding": set(node["proposals_outstanding"]),
        "rejected": set(node.get("proposals_rejected", ())),
        "routes": dict(node["proposal_routes"]),
        "children_outstanding": set(node["children_outstanding"]),
        "children_completed": set(node["children_completed"]),
        "children_opened": list(node["children_opened"]),
        "confirmed": dict(node["child_confirmed"]),
        "in_flight": node["child_allocations_in_flight"],
        "reserve": node["local_reserve"],
        "consumed": node["consumed_credit"],
        "cancelled": node["cancelled_credit"],
        "returned": node["returned_to_parent"],
        "refunds": node["child_refunds_received"],
        "eligible": node["eligible_offer"],
        "accepted": node["accepted_proposal_id"],
        "wave_cancelled": node["wave_cancelled"],
        "terminal_sent": node["terminal_signal_sent"],
        "ack_sent": node["ack_sent"],
        "terminals": {e: [_kind(x) for x in r["outcomes"]]
                      for e, r in o.search_edge_terminals.items()},
        "edge_status": {e: r.get("terminal_status")
                        for e, r in o.search_edges.items()},
        "outbox": list(relay.outbox),
    }


# ---------------------------------------------------------------------------
# 1. Missing identity must FAIL CLOSED at every control entrypoint
# ---------------------------------------------------------------------------

def test_a_control_with_no_sender_is_refused_at_every_entrypoint():
    """An omitted argument is not authority.

    `Unit.step` always supplies a sender, so this is not a live exploit today.
    It is still a fail-open entrypoint, and a protocol whose authentication is
    optional has authentication only by convention.
    """
    o, j, relay, ctx, key, node, kids, seed = _relay_node()
    a = kids[0]
    pay = _register(o, relay, node, a)
    before = _snapshot(o, relay, node)
    reset()

    relay.deliver_proposal_rejected(key, node["adopted_parent_edge"],
                                    pay.proposal_id, "forged")
    assert _snapshot(o, relay, node) == before, (
        "a rejection with no sender suppressed a proposal")
    assert _counter("UNAUTHENTICATED_REJECTION_CONTROLS") == 1

    relay.deliver_search_ack(key, a, node["child_allocations"][a], 0.0)
    assert _snapshot(o, relay, node) == before, (
        "an acknowledgement with no sender closed an allocation")
    assert _counter("UNAUTHENTICATED_SEARCH_ACKS") == 1

    relay.deliver_terminal(key, node["adopted_parent_edge"], "SearchCommitted",
                           0.0, pay.proposal_id)
    assert _snapshot(o, relay, node) == before, (
        "a terminal with no sender closed the wave")
    assert _counter("UNAUTHENTICATED_TERMINAL_CONTROLS") == 1

    # PAIRED POSITIVE CONTROL: the explicit harness capability, which a test may
    # present deliberately and production code has no reason to construct.
    reset()
    relay.deliver_search_ack(key, a, node["child_allocations"][a], 0.0,
                             v5.HARNESS_DELIVERY)
    assert node["child_confirmed"].get(a) is not None, (
        "the explicit harness capability was refused, so tests have no lawful "
        "way to drive the protocol directly")


# ---------------------------------------------------------------------------
# 2. Terminal refund evidence must meet the acknowledgement standard
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label", ["negative", "oversized", "nan", "inf",
                                   "neg_inf"])
def test_malformed_terminal_refund_evidence_fails_closed(label):
    """Two doors into one ledger need one standard of evidence.

    `deliver_search_ack` validates the raw claim and refuses. `deliver_terminal`
    clamps the same claim and writes the same `child_confirmed` entry, so an
    authenticated child launders malformed evidence by choosing the other door.
    """
    o, j, relay, ctx, key, node, kids, seed = _relay_node()
    a = kids[0]
    per = node["child_allocations"][a]
    target = node["child_targets"][a]
    refund = {"negative": -per, "oversized": per * 3.0,
              "nan": float("nan"), "inf": float("inf"),
              "neg_inf": float("-inf")}[label]
    before = _snapshot(o, relay, node)
    reset()

    relay.deliver_terminal(key, a, "SearchExhausted", refund, "", sender=target)

    assert _snapshot(o, relay, node) == before, (
        f"a terminal carrying a {label} refund ({refund}) against an allocation "
        f"of {per} mutated node state")
    assert a not in node["child_confirmed"]
    assert a in node["children_outstanding"]
    for field in ("child_allocations_in_flight", "local_reserve",
                  "consumed_credit", "cancelled_credit"):
        assert not math.isnan(node[field]), f"{field} was poisoned by {label}"
    assert _counter("MALFORMED_TERMINAL_EVIDENCE") == 1

    # PAIRED POSITIVE CONTROL: a well-formed refund on the same edge.
    reset()
    relay.deliver_terminal(key, a, "SearchExhausted", per / 4.0, "",
                           sender=target)
    assert node["child_confirmed"].get(a) == (per / 4.0, per - per / 4.0), (
        f"a well-formed terminal refund was refused or misrecorded: "
        f"{node['child_confirmed'].get(a)}")
    assert _counter("MALFORMED_TERMINAL_EVIDENCE") == 0


# ---------------------------------------------------------------------------
# 3. SearchCommitted must name a proposal this node actually knows
# ---------------------------------------------------------------------------

def test_a_commit_naming_an_unknown_proposal_is_refused():
    """Authentication answers WHO. It does not make a command meaningful.

    A commit whose proposal is unknown here leaves `proposal_routes.get(pid)` at
    None, so the node marks itself COMMITTED and cancels every child with no
    route to the supposed winner -- a wave closed around a proposal that never
    existed on this branch.
    """
    o, j, relay, ctx, key, node, kids, seed = _relay_node()
    parent = node["adopted_parent_sender"]
    before = _snapshot(o, relay, node)
    reset()

    relay.deliver_terminal(key, node["adopted_parent_edge"], "SearchCommitted",
                           0.0, "sfp1:never-seen-here", sender=parent)

    assert _snapshot(o, relay, node) == before, (
        "an authenticated parent committed a proposal this node never saw")
    assert node["status"] != "COMMITTED"
    assert node["accepted_proposal_id"] is None
    assert node["children_outstanding"], "children were cancelled anyway"
    assert _counter("UNKNOWN_COMMIT_PROPOSALS") == 1

    # POSITIVE CONTROL A: a proposal registered through a real child route.
    pay = _register(o, relay, node, kids[0])
    reset()
    relay.deliver_terminal(key, node["adopted_parent_edge"], "SearchCommitted",
                           0.0, pay.proposal_id, sender=parent)
    assert node["status"] == "COMMITTED", (
        "a commit naming a proposal registered on a real child route was "
        "refused, so the refusal above cannot be attributed to the unknown id")
    assert node["accepted_proposal_id"] == pay.proposal_id
    assert _counter("UNKNOWN_COMMIT_PROPOSALS") == 0


def test_a_source_may_be_committed_on_its_own_candidate():
    """POSITIVE CONTROL B, at the other identity the runtime must accept.

    The source MINTED its candidate and forwarded it, so the proposal never
    appears in that node's `proposal_routes`. A commit-validity rule that only
    consults routes would make every accepted candidate uncommittable at exactly
    the node that produced it -- the same shape of defect that made rejections
    unroutable in 2B.
    """
    o, j, relay, ctx, key, node, kids, seed = _relay_node()
    want = key.wanted_type
    producer = next((u for u in o.units.values()
                     if u.capability.produces == want
                     and u.unit_id not in (ENV, SINK)), None)
    assert producer is not None, "no producer of the wanted type in this fixture"
    reset()
    out = producer.deliver_search(key, "e/src", allocation=6.0,
                                  lineage=(j.unit_id,), sender=j.unit_id,
                                  context=ctx,
                                  transport=v5.HARNESS_DELIVERY)
    src = producer.canonical_searches.get(key)
    assert src is not None, "the producer adopted no canonical node"
    assert _kind(out) == "SearchProposal", (
        f"the producer returned {_kind(out)}; this control needs it to be the "
        f"SOURCE of a candidate")
    pid = src["local_candidate"].proposal_id
    assert pid not in src["proposal_routes"], (
        "the source holds its own candidate as a route, so this test is not "
        "exercising the local-candidate identity")

    producer.deliver_terminal(key, src["adopted_parent_edge"], "SearchCommitted",
                              0.0, pid, sender=j.unit_id)
    assert src["status"] == "COMMITTED", (
        "the source could not be committed on its own candidate")
    assert src["accepted_proposal_id"] == pid
    assert _counter("UNKNOWN_COMMIT_PROPOSALS") == 0


# ---------------------------------------------------------------------------
# 4. A closed wave must be causally sealed
# ---------------------------------------------------------------------------

def test_a_closed_wave_admits_no_late_proposal_or_rejection():
    o, j, relay, ctx, key, node, kids, seed = _relay_node()
    parent = node["adopted_parent_sender"]
    winner = _register(o, relay, node, kids[0])
    relay.deliver_terminal(key, node["adopted_parent_edge"], "SearchCommitted",
                           0.0, winner.proposal_id, sender=parent)
    assert node["status"] == "COMMITTED", "the wave did not close"

    # EVERY proposal must reach an explicit disposition. Leaving one merely
    # "outstanding" on a closed node is an obligation nobody will ever answer.
    assert not node["proposals_outstanding"], (
        f"{len(node['proposals_outstanding'])} proposals are still outstanding "
        f"on a COMMITTED node")
    assert "proposal_disposition" in node, (
        "the node records no terminal disposition per proposal, so a closed "
        "wave cannot say what became of each candidate")
    assert node["proposal_disposition"].get(winner.proposal_id) == "accepted"

    before = _snapshot(o, relay, node)
    reset()
    late = _proposal(o, node, kids[1])
    relay.deliver_proposal(key, kids[1], late, node["child_targets"][kids[1]])
    assert late.proposal_id not in node["proposal_routes"], (
        "a proposal was registered on a wave that had already closed")
    assert _snapshot(o, relay, node) == before, "a late proposal mutated state"
    # NOTHING NEW WAS FORWARDED. Requiring the outbox to hold no `__proposal__`
    # at all was wrong: the WINNING proposal, registered earlier in this test,
    # legitimately forwarded one before the wave closed, so the assertion failed
    # against correct behaviour. The snapshot comparison above already covers
    # the outbox, and this states the specific claim the test is making.
    forwarded = [m for m in relay.outbox
                 if isinstance(m[1], tuple) and m[1]
                 and m[1][0] == "__proposal__"
                 and m[1][3].proposal_id == late.proposal_id]
    assert not forwarded, (
        "a late proposal was forwarded upward from a closed wave")

    relay.deliver_proposal_rejected(key, node["adopted_parent_edge"],
                                    winner.proposal_id, "late", parent)
    assert _snapshot(o, relay, node) == before, (
        "a late rejection mutated a closed wave")
    assert node["accepted_proposal_id"] == winner.proposal_id, (
        "a late rejection changed the accepted proposal identity")
    assert _counter("LATE_CONTROLS_AFTER_CLOSURE") == 2


# ---------------------------------------------------------------------------
# 5. A sender-side claim is not authenticated edge closure
# ---------------------------------------------------------------------------

def test_a_sender_cannot_record_a_terminal_it_has_no_right_to_emit():
    """Driven through the SENDER's own emission path, not the receiver seam.

    `_emit_terminal` writes into the organ-wide registry and flips the edge's
    `terminal_status` BEFORE delivery, so a unit emitting an unowned or
    wrong-direction terminal poisons shared evidence even when the receiver
    correctly refuses the transition. Edge closure is what the receiver
    accepted, not what a sender asserted.
    """
    o, j, relay, ctx, key, node, kids, seed = _relay_node()
    a = kids[0]
    stranger = next(u for u in o.units.values()
                    if u.unit_id not in (ENV, SINK, relay.unit_id)
                    and u.unit_id != node["child_targets"][a])
    before = _snapshot(o, relay, node)
    reset()

    # A unit that owns neither end of edge `a` asserts its closure.
    stranger._emit_terminal("SearchExhausted", key, a, relay.unit_id,
                            refund=node["child_allocations"][a])

    # THE SEMANTIC QUESTION IS "WAS ANY FACT RECORDED AT ALL", so BOTH channels
    # are checked. A stranger owning neither end must not be able to file a
    # command or an outcome, and checking only one channel would leave the
    # other as an unguarded door.
    _lc = o.search_edge_lifecycle.get(a) or {}
    assert not _lc.get("accepted_control") and not _lc.get("accepted_outcome"), (
        f"{stranger.unit_id} recorded an authoritative terminal on edge {a}, "
        f"which it neither opened nor is the target of")
    assert o.search_edges.get(a, {}).get("terminal_status") == "open", (
        "the edge was marked terminal by a sender-side claim alone")
    assert _snapshot(o, relay, node) == before
    assert _counter("UNAUTHENTICATED_TERMINAL_EMISSIONS") == 1

    # PAIRED POSITIVE CONTROL: the edge's real target closing it lawfully.
    reset()
    target = o.units[node["child_targets"][a]]
    target._emit_terminal("SearchExhausted", key, a, relay.unit_id, refund=0.0)
    assert o.search_edge_terminals.get(a, {}).get("outcomes"), (
        "the edge's real target could not record its own terminal")
    assert _counter("UNAUTHENTICATED_TERMINAL_EMISSIONS") == 0
