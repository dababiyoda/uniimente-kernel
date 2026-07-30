"""2D: the search-adoption boundary, and the last unbound control surfaces.

PRE-REGISTERED BEFORE THE CORRESPONDING RUNTIME CHANGE. Strict xfail throughout.

WHY THIS FILE EXISTS. 2A bound the data plane, 2B and 2C bound the control plane
and made identity fail closed. The INGRESS is still trust-by-receiver:

  1. SEARCH ARRIVALS ARE NOT AUTHENTICATED. `deliver_search` records the arrival
     as `sender or key.origin_unit` -- a missing sender is silently read as the
     origin -- and `_record_delivery` reaches `_edge_record`, which CREATES the
     probe when none exists. The receiver therefore manufactures the very
     evidence the sender was supposed to have created, and nothing checks that
     the sender is a neighbour, that the edge's recorded endpoints match, that
     the edge carries this SearchKey, or that the allocation is the one the
     sender committed. Commit 3 would make this the live repair ingress.

  2. TERMINAL EMISSION BINDING IS INCOMPLETE. `_may_emit` returns True whenever
     no edge record exists, and checks neither the edge's SearchKey nor the
     destination. An endpoint can still authoritatively record a terminal on an
     unknown edge, under the wrong key, or addressed to the wrong unit. The 2C
     spec exercised only a stranger emitting on an EXISTING edge.

  3. A REJECTED PROPOSAL CAN LATER BE COMMITTED. `_knows_proposal` counts
     `proposals_rejected` and `proposal_disposition` as "known", and
     `deliver_terminal` authorizes `SearchCommitted` on that basis. An
     authenticated parent can reject P, leave the wave open, then commit P.
     Exactly-once resolution forbids it: "known" is too broad, and commit
     eligibility is a narrower question than acquaintance.

  4. SEALING OMITS THE SOURCE'S OWN LOSING CANDIDATE. `_seal` dispositions
     `proposals_outstanding` and `proposals_rejected`, but a SOURCE holds its
     proposal as `local_candidate` and in neither set. When the wave closes
     around somebody else, that candidate is never classified and
     `eligible_offer` stays set, so a closed wave still has a node advertising
     an active offer.

  5. HARNESS QUARANTINE. `HARNESS_DELIVERY` exists so a direct test drive can
     declare that it is bypassing transport authentication. It must never appear
     in a scheduler-delivered message, and a healthy live run must leave its
     counter at zero -- otherwise the bypass has become the path.

DECLARED SEAMS:

    deliver_search(..., transport=v5.HARNESS_DELIVERY)
                                 an EXPLICIT declaration that no sender-created
                                 probe exists. `sender` still carries the real
                                 identity, so return routing is unchanged.
    probe record ["allocation"]  written by the SENDER at creation

New counters:

    UNAUTHENTICATED_SEARCH_DELIVERIES
    MALFORMED_SEARCH_DELIVERIES
    UNKNOWN_EDGE_TERMINAL_EMISSIONS
    COMMIT_OF_RESOLVED_PROPOSAL
    UNDISPOSITIONED_LOCAL_PROPOSALS
    HARNESS_DELIVERIES_USED

Single Bottleneck Metric:

    AUTHENTICATED_SEARCH_ADOPTIONS / TOTAL_CANONICAL_SEARCH_ADOPTIONS == 1.0
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

admission = pytest.mark.xfail(
    strict=True,
    reason="Single-Flight 2D search admission is not implemented yet")


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
            need_id="probe:admission", work_item_generation=2,
            origin_unit=j.unit_id, origin_slot=slot,
            wanted_type=j.capability.accepts[slot], context=ctx)
        nbrs = sorted(n for n in j.neighbours if n not in (ENV, SINK))
        strangers = sorted(u for u in o.units
                           if u not in (ENV, SINK, j.unit_id)
                           and u not in j.neighbours)
        if len(nbrs) >= 2 and strangers:
            return o, j, o.units[nbrs[0]], o.units[nbrs[1]], strangers[0], ctx, key, seed
    raise AssertionError(
        "no origin with two neighbours and a non-neighbour across the "
        "pre-registered seeds; failing to build the structure is a failure of "
        "this specification, not a reason to skip it")


def _open_probe(o, sender, target, key, edge, allocation):
    """The SENDER creates the edge, exactly as `_expand_canonical` does."""
    sender._record_probe(edge, sender.unit_id, target.unit_id, key,
                         allocation=allocation)
    rec = o.search_edge_probes[edge]
    assert rec["from_unit"] == sender.unit_id and rec["to_unit"] == target.unit_id
    assert rec["allocation"] == allocation, (
        "the sender's probe does not record the allocation it committed, so a "
        "receiver cannot check the arriving amount against anything")
    return rec


def _quiet(o, unit):
    return {
        "nodes": len(unit.canonical_searches),
        "probes": {e: dict(r) for e, r in o.search_edge_probes.items()},
        "terminals": {e: [_kind(x) for x in r["outcomes"]]
                      for e, r in o.search_edge_terminals.items()},
        "events": {e: len(v) for e, v in o.search_edge_events.items()},
        "outbox": list(unit.outbox),
    }


# ---------------------------------------------------------------------------
# 1. Search arrivals must be authenticated against a SENDER-CREATED probe
# ---------------------------------------------------------------------------

@admission
@pytest.mark.parametrize("attack", [
    "no_sender", "not_a_neighbour", "no_probe", "wrong_from", "wrong_to",
    "wrong_key", "wrong_allocation"])
def test_an_unauthenticated_search_arrival_adopts_nothing(attack):
    """The receiver must not manufacture the sender's evidence.

    `_record_delivery` reaches `_edge_record`, which CREATES the probe when none
    exists, so an arrival on a fabricated edge produced its own justification.
    Combined with `sender or key.origin_unit`, a caller with no identity at all
    was recorded as the origin. This is the entrypoint Commit 3 would make the
    live repair ingress.
    """
    o, j, nbr, other, stranger, ctx, key, seed = _pair()
    edge = "e/admit"
    alloc = 6.0
    target = nbr
    sender = j
    delivered_key, delivered_alloc = key, alloc

    if attack != "no_probe":
        frm = j if attack != "wrong_from" else other
        to = target if attack != "wrong_to" else other
        pkey = key
        if attack == "wrong_key":
            pkey = v5.SearchKey.build(
                need_id="probe:other", work_item_generation=2,
                origin_unit=j.unit_id, origin_slot=key.origin_slot,
                wanted_type=key.wanted_type, context=ctx)
        _open_probe(o, frm, to, pkey, edge, alloc)
    if attack == "wrong_allocation":
        delivered_alloc = alloc * 3.0

    before = _quiet(o, target)
    reset()
    kwargs = dict(lineage=(j.unit_id,), context=ctx)
    if attack == "no_sender":
        pass
    elif attack == "not_a_neighbour":
        kwargs["sender"] = stranger
    else:
        kwargs["sender"] = sender.unit_id

    outcome = target.deliver_search(delivered_key, edge, delivered_alloc, **kwargs)

    assert delivered_key not in target.canonical_searches, (
        f"{attack}: an unauthenticated arrival adopted a canonical node")
    assert _kind(outcome) != "SearchProposal", f"{attack}: it also proposed"
    assert C["UNIQUE_CANONICAL_SEARCH_NODES"] == 0
    assert C["DIRECTED_SEARCH_EDGES_PROBED"] == 0, (
        f"{attack}: descendants were opened")
    after = _quiet(o, target)
    assert after["probes"].keys() == before["probes"].keys(), (
        f"{attack}: the RECEIVER created a probe record, manufacturing the "
        f"evidence the sender was supposed to provide")
    assert (_counter("UNAUTHENTICATED_SEARCH_DELIVERIES")
            + _counter("MALFORMED_SEARCH_DELIVERIES")) == 1, (
        f"{attack}: no attributable admission violation was recorded")


@admission
def test_a_properly_announced_search_arrival_is_admitted_once():
    """PAIRED POSITIVE CONTROL for every negative case above."""
    o, j, nbr, other, stranger, ctx, key, seed = _pair()
    edge, alloc = "e/admit/ok", 6.0
    _open_probe(o, j, nbr, key, edge, alloc)
    reset()

    nbr.deliver_search(key, edge, alloc, lineage=(j.unit_id,),
                       sender=j.unit_id, context=ctx)

    assert key in nbr.canonical_searches, (
        "a correctly announced arrival was refused, so every refusal above is "
        "unattributable")
    assert o.search_edge_probes[edge]["delivered"] == 1
    assert o.search_edge_probes[edge]["count"] == 1, (
        "delivery incremented the creation count")
    assert _counter("UNAUTHENTICATED_SEARCH_DELIVERIES") == 0
    assert _counter("MALFORMED_SEARCH_DELIVERIES") == 0
    assert C["UNIQUE_CANONICAL_SEARCH_NODES"] == 1


# ---------------------------------------------------------------------------
# 2. Terminal emission must be bound to a real edge, key and destination
# ---------------------------------------------------------------------------

@admission
@pytest.mark.parametrize("attack", ["unknown_edge", "wrong_key",
                                    "wrong_destination", "wrong_direction"])
def test_an_endpoint_cannot_record_a_terminal_it_cannot_justify(attack):
    o, j, nbr, other, stranger, ctx, key, seed = _pair()
    edge, alloc = "e/emit", 6.0
    if attack != "unknown_edge":
        _open_probe(o, j, nbr, key, edge, alloc)
    emit_key = key
    if attack == "wrong_key":
        emit_key = v5.SearchKey.build(
            need_id="probe:elsewhere", work_item_generation=2,
            origin_unit=j.unit_id, origin_slot=key.origin_slot,
            wanted_type=key.wanted_type, context=ctx)
    to = nbr.unit_id if attack != "wrong_destination" else other.unit_id
    kind = "SearchExhausted" if attack != "wrong_direction" else "SearchCommitted"
    before = _quiet(o, nbr)
    reset()

    # `nbr` is the edge's recorded TARGET, so it may answer -- and only answer,
    # on that edge, under that key, to the unit that opened it.
    nbr._emit_terminal(kind, emit_key, edge, to, refund=0.0)

    assert edge not in o.search_edge_terminals, (
        f"{attack}: an unjustified terminal was recorded as authoritative")
    assert o.search_edges.get(edge, {}).get("terminal_status", "open") == "open"
    assert not nbr.outbox, f"{attack}: it was also delivered"
    assert (_counter("UNKNOWN_EDGE_TERMINAL_EMISSIONS")
            + C["UNAUTHENTICATED_TERMINAL_EMISSIONS"]) == 1
    assert _quiet(o, nbr)["terminals"] == before["terminals"]


@admission
def test_both_endpoints_may_emit_in_their_own_direction():
    """PAIRED POSITIVE CONTROL: the target answers, the opener commands."""
    o, j, nbr, other, stranger, ctx, key, seed = _pair()
    _open_probe(o, j, nbr, key, "e/ans", 6.0)
    _open_probe(o, j, nbr, key, "e/cmd", 6.0)
    reset()

    nbr._emit_terminal("SearchExhausted", key, "e/ans", j.unit_id, refund=1.0)
    assert o.search_edge_terminals.get("e/ans", {}).get("outcomes"), (
        "the edge's recorded target could not answer its own incoming edge")

    j._emit_terminal("SearchCancelled", key, "e/cmd", nbr.unit_id)
    assert o.search_edge_terminals.get("e/cmd", {}).get("outcomes"), (
        "the edge's opener could not command the edge it created")
    assert _counter("UNKNOWN_EDGE_TERMINAL_EMISSIONS") == 0
    assert C["UNAUTHENTICATED_TERMINAL_EMISSIONS"] == 0


# ---------------------------------------------------------------------------
# 3. A resolved proposal is not commit-eligible
# ---------------------------------------------------------------------------

def _relay_with_proposal():
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
            need_id="probe:commitelig", work_item_generation=2,
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
        if node is None or len(node["children_opened"]) < 2:
            continue
        edge = node["children_opened"][0]
        target = node["child_targets"][edge]
        cand = o.units[target]
        pay = v5.SearchOfferPayload(
            proposal_id="l", search_key=key,
            context_digest=ctx.context_digest(), supplier=target,
            supplier_class=cand.capability.klass(),
            offered_type=key.wanted_type, cost=cand.capability.cost,
            firm=not cand.unmet(), derivation_chain=cand._derives_from(),
            source_node=target, source_edge_id=edge)
        relay.deliver_proposal(key, edge, pay, target)
        if node["proposal_routes"].get(pay.proposal_id) != edge:
            continue
        return o, j, relay, ctx, key, node, pay, seed
    raise AssertionError(
        "no relay carrying a registered proposal across the pre-registered "
        "seeds; failing to build the structure is a failure of this "
        "specification, not a reason to skip it")


@admission
def test_a_rejected_proposal_can_never_later_be_committed():
    """Acquaintance is not eligibility.

    `_knows_proposal` counts `proposals_rejected` and `proposal_disposition` as
    known, so an authenticated parent could reject P, leave the wave open, and
    then commit P. Exactly-once resolution forbids a second, contradictory
    decision on the same proposal.
    """
    o, j, relay, ctx, key, node, pay, seed = _relay_with_proposal()
    parent = node["adopted_parent_sender"]
    relay.deliver_proposal_rejected(key, node["adopted_parent_edge"],
                                    pay.proposal_id, "duplicate_supplier",
                                    parent)
    assert pay.proposal_id in node["proposals_rejected"]
    assert node["status"] == "OPEN", "the rejection closed the wave"
    reset()

    relay.deliver_terminal(key, node["adopted_parent_edge"], "SearchCommitted",
                           0.0, pay.proposal_id, sender=parent)

    assert node["status"] != "COMMITTED", (
        "a proposal that was already rejected was later committed")
    assert node["accepted_proposal_id"] is None
    assert pay.proposal_id in node["proposals_rejected"]
    assert node["children_outstanding"], "children were cancelled anyway"
    assert _counter("COMMIT_OF_RESOLVED_PROPOSAL") == 1


@admission
def test_an_unresolved_proposal_commits_and_its_replay_is_inert():
    """PAIRED POSITIVE CONTROL, both halves of the eligibility rule."""
    o, j, relay, ctx, key, node, pay, seed = _relay_with_proposal()
    parent = node["adopted_parent_sender"]
    reset()

    relay.deliver_terminal(key, node["adopted_parent_edge"], "SearchCommitted",
                           0.0, pay.proposal_id, sender=parent)
    assert node["status"] == "COMMITTED", (
        "an unresolved registered proposal could not be committed")
    assert node["accepted_proposal_id"] == pay.proposal_id
    assert _counter("COMMIT_OF_RESOLVED_PROPOSAL") == 0

    snapshot = (node["status"], node["accepted_proposal_id"],
                dict(node["proposal_disposition"]),
                {e: [_kind(x) for x in r["outcomes"]]
                 for e, r in o.search_edge_terminals.items()})
    for _ in range(3):
        relay.deliver_terminal(key, node["adopted_parent_edge"],
                               "SearchCommitted", 0.0, pay.proposal_id,
                               sender=parent)
    assert (node["status"], node["accepted_proposal_id"],
            dict(node["proposal_disposition"]),
            {e: [_kind(x) for x in r["outcomes"]]
             for e, r in o.search_edge_terminals.items()}) == snapshot, (
        "an exact replay of the accepted commit was not inert")
    assert _counter("COMMIT_OF_RESOLVED_PROPOSAL") == 0, (
        "an exact replay of the ACCEPTED proposal was counted as a commit of a "
        "resolved one; replay is not a second decision")


# ---------------------------------------------------------------------------
# 4. A source's own candidate must be dispositioned and deactivated
# ---------------------------------------------------------------------------

def _source_node():
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
            need_id="probe:srcseal", work_item_generation=2,
            origin_unit=j.unit_id, origin_slot=slot,
            wanted_type=j.capability.accepts[slot], context=ctx)
        producer = next((u for u in o.units.values()
                         if u.capability.produces == key.wanted_type
                         and u.unit_id not in (ENV, SINK)
                         and not u.silent), None)
        if producer is None:
            continue
        out = producer.deliver_search(key, "e/src", allocation=6.0,
                                      lineage=(j.unit_id,), sender=j.unit_id,
                                      context=ctx,
                                      transport=v5.HARNESS_DELIVERY)
        node = producer.canonical_searches.get(key)
        if node is None or node.get("local_candidate") is None:
            continue
        return o, j, producer, ctx, key, node, seed
    raise AssertionError(
        "no source node holding its own candidate across the pre-registered "
        "seeds; failing to build the structure is a failure of this "
        "specification, not a reason to skip it")


@admission
@pytest.mark.parametrize("closure,expected", [
    ("SearchCancelled", "cancelled"), ("SearchNeedClosed", "need_closed")])
def test_a_losing_source_candidate_is_dispositioned_and_deactivated(closure,
                                                                    expected):
    """A closed wave must not leave a node advertising an active offer.

    The source holds its proposal as `local_candidate` and in neither
    `proposals_outstanding` nor `proposals_rejected`, so `_seal` never saw it.
    """
    o, j, producer, ctx, key, node, seed = _source_node()
    pid = node["local_candidate"].proposal_id
    assert node["eligible_offer"], "the source is not advertising an offer"
    reset()

    producer.deliver_terminal(key, node["adopted_parent_edge"], closure, 0.0, "",
                              sender=j.unit_id)

    assert node["proposal_disposition"].get(pid) == expected, (
        f"the source's own candidate was left undispositioned after {closure}: "
        f"{node['proposal_disposition']}")
    assert node.get("local_candidate") is None, (
        "the source still holds a candidate the wave already closed around")
    assert not node["eligible_offer"], (
        "a closed wave left the source advertising an active offer")
    assert not node["proposals_outstanding"]
    assert _counter("UNDISPOSITIONED_LOCAL_PROPOSALS") == 0


@admission
def test_an_accepted_source_candidate_is_dispositioned_accepted():
    o, j, producer, ctx, key, node, seed = _source_node()
    pid = node["local_candidate"].proposal_id
    reset()

    producer.deliver_terminal(key, node["adopted_parent_edge"],
                              "SearchCommitted", 0.0, pid, sender=j.unit_id)

    assert node["status"] == "COMMITTED"
    assert node["proposal_disposition"].get(pid) == "accepted"
    assert not node["eligible_offer"], (
        "the source still advertises an offer after its candidate was accepted")
    assert node["accepted_proposal_id"] == pid


# ---------------------------------------------------------------------------
# 5. The harness capability must stay quarantined
# ---------------------------------------------------------------------------

def test_no_live_execution_ever_uses_the_harness_capability():
    """Plain test: must hold now and keep holding.

    `HARNESS_DELIVERY` exists so a direct test drive can DECLARE that it is
    bypassing transport authentication. If it ever reaches a scheduler-delivered
    message, the bypass has become the path and every gate above is decorative.
    """
    o = F.development(random.Random(4000))
    F.prepare(o)
    reset()
    o.commission()
    assert o.result_ok(o.run_item(PAYLOAD_A)), "formation stopped working"

    for u in o.units.values():
        for dest, msg in u.outbox:
            assert v5.HARNESS_DELIVERY not in (dest, msg), (
                f"{u.unit_id} queued a message carrying the harness capability")
            if isinstance(msg, tuple):
                assert v5.HARNESS_DELIVERY not in msg, (
                    f"{u.unit_id} queued a control carrying the harness "
                    f"capability: {msg[0]}")
        for src, msg in u.inbox:
            assert src is not v5.HARNESS_DELIVERY, (
                f"{u.unit_id} received a message whose sender is the harness "
                f"capability")
    assert "HARNESS_DELIVERIES_USED" not in C.d or C["HARNESS_DELIVERIES_USED"] == 0, (
        f"a healthy live run used the harness bypass "
        f"{C['HARNESS_DELIVERIES_USED']} times")
