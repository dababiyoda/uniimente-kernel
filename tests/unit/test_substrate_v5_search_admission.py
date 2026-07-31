"""2D: the search-adoption boundary, and the last unbound control surfaces.

PRE-REGISTERED BEFORE THE CORRESPONDING RUNTIME CHANGE, as strict xfail
throughout. ALL 21 SPECIFICATIONS ARE NOW ACTIVE: each was satisfied by the
2D-runtime commit, and the markers were removed afterwards, in a separate
commit. The numbered defects below are the state of the runtime WHEN THIS FILE
WAS WRITTEN, retained deliberately -- they record what was wrong and therefore
what these tests are still holding closed. Each is annotated with its fix.

WHY THIS FILE EXISTS. 2A bound the data plane, 2B and 2C bound the control plane
and made identity fail closed. The INGRESS was still trust-by-receiver:

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
    AUTHENTICATED_SEARCH_ADOPTIONS
    TOTAL_CANONICAL_SEARCH_ADOPTIONS

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

# ACTIVATED. Every 2D search admission specification in this file was satisfied by the
# runtime and its `xfail(strict=True)` marker removed in the activation
# commit. The marker is retained, unused, so a new specification written
# against an unimplemented behaviour can be pre-registered the same way.
admission = pytest.mark.xfail(
    strict=True,
    reason="pre-registration marker for a NEW 2D search admission specification")


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
        if len(nbrs) < 2:
            continue
        target = o.units[nbrs[0]]
        # A NON-NEIGHBOUR OF THE RECEIVER, not of the origin. The receiver is
        # the unit whose adjacency gate is under test, so a unit that merely
        # fails to neighbour the ORIGIN proves nothing about it.
        strangers = sorted(u for u in o.units
                           if u not in (ENV, SINK, target.unit_id)
                           and u not in target.neighbours)
        # The bogus OPENER for `wrong_from` must itself be a real neighbour of
        # the RECEIVER. Picking a second neighbour of the ORIGIN left it
        # possibly non-adjacent to the receiver, so a runtime could reject on
        # adjacency alone and never compare the recorded opener with the
        # immediate sender -- the only fact that case exists to isolate.
        others = sorted(n for n in target.neighbours
                        if n not in (ENV, SINK, j.unit_id))
        if strangers and others and j.unit_id in target.neighbours:
            return (o, j, target, o.units[others[0]], o.units[strangers[0]],
                    ctx, key, seed)
    raise AssertionError(
        "no origin adjacent to a receiver that also has a second neighbour and "
        "a non-neighbour, across the pre-registered seeds; failing to build the "
        "structure is a failure of this specification, not a reason to skip it")


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


def _edge_evidence(o):
    """The COMPLETE probe and edge records, not merely which keys exist.

    Comparing key sets only forbids CREATING an edge. It still permits a
    receiver to mutate a sender-created record before refusing the request --
    bumping `delivered`, rewriting the allocation, the endpoints or the
    SearchKey, or flipping the parallel `search_edges` entry. Validation has to
    happen before any delivery telemetry moves.
    """
    return ({e: dict(r) for e, r in o.search_edge_probes.items()},
            {e: dict(r) for e, r in o.search_edges.items()})


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

    if attack == "not_a_neighbour":
        # EVERY other fact is valid: the stranger opened the edge itself, to
        # this receiver, under this key, with this allocation. The ONLY invalid
        # fact is that it does not neighbour the receiver.
        sender = stranger
    if attack != "no_probe":
        # `other` neighbours the RECEIVER, so `wrong_from` differs from a valid
        # arrival in exactly one fact: the recorded opener is not the unit that
        # delivered it.
        frm = sender if attack != "wrong_from" else other
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
    evidence_before = _edge_evidence(o)
    reset()
    kwargs = dict(lineage=(j.unit_id,), context=ctx)
    if attack != "no_sender":
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
    assert _edge_evidence(o) == evidence_before, (
        f"{attack}: a REFUSED arrival still mutated edge evidence -- delivered "
        f"count, allocation, endpoints, SearchKey or terminal status moved "
        f"before the request was validated")
    assert (_counter("UNAUTHENTICATED_SEARCH_DELIVERIES")
            + _counter("MALFORMED_SEARCH_DELIVERIES")) == 1, (
        f"{attack}: no attributable admission violation was recorded")


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
    # THE SINGLE BOTTLENECK METRIC, measured rather than declared.
    assert _counter("TOTAL_CANONICAL_SEARCH_ADOPTIONS") == 1
    assert _counter("AUTHENTICATED_SEARCH_ADOPTIONS") == 1
    assert _counter("HARNESS_DELIVERIES_USED") == 0, (
        "an authenticated adoption was recorded as a harness bypass")


# ---------------------------------------------------------------------------
# 2. Terminal emission must be bound to a real edge, key and destination
# ---------------------------------------------------------------------------

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
    # THE VALID DESTINATION IS THE OPENER. `nbr` is the edge's recorded target,
    # so answering goes back to `j`. Using `nbr` as the baseline gave three of
    # these four attacks an UNINTENDED wrong destination as well, so a runtime
    # that validated only the destination would have passed three different
    # security tests without implementing any of them.
    to = j.unit_id if attack != "wrong_destination" else other.unit_id
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
    # THE SEMANTIC QUESTION HERE IS "WAS THE COMMAND ACCEPTED", not "was the
    # edge closed". `SearchCancelled` is a parent control, so it lands in the
    # control channel; reading it out of an outcome field was only ever
    # possible because the two were conflated.
    assert o.search_edge_lifecycle.get("e/cmd", {}).get("accepted_control"), (
        "the edge's opener could not command the edge it created")
    assert o.search_edge_lifecycle.get("e/cmd", {}).get("accepted_outcome") is None, (
        "the opener's command was also recorded as the edge's outcome")
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


def _source_with_rival():
    """A source whose candidate can actually LOSE to a routed rival.

    `_source_node` returns the first producer holding a `local_candidate`, which
    may be FIRM -- and a firm candidate deliberately opens zero descendants,
    because eligibility is evaluated before expansion. Iterating
    `children_opened` on such a node finds nothing, so the rival case would fail
    on fixture selection against a CORRECT runtime. Scanned until every
    precondition is proved, then hard asserted.
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
            need_id="probe:rival", work_item_generation=2,
            origin_unit=j.unit_id, origin_slot=slot,
            wanted_type=j.capability.accepts[slot], context=ctx)
        for producer in o.units.values():
            if (producer.unit_id in (ENV, SINK)
                    or producer.capability.produces != key.wanted_type
                    or producer.silent or not producer.unmet()):
                continue        # NONFIRM only: a firm source opens no children
            producer.deliver_search(key, "e/src", allocation=12.0,
                                    lineage=(j.unit_id,), sender=j.unit_id,
                                    context=ctx, transport=v5.HARNESS_DELIVERY)
            node = producer.canonical_searches.get(key)
            if node is None or node.get("local_candidate") is None:
                continue
            if not node["children_opened"]:
                continue
            # Drive the rival through the CHILD'S OWN delivery path, so Q is a
            # real proposal that travelled, not one fabricated at the parent.
            for edge in node["children_opened"]:
                child = o.units.get(node["child_targets"][edge])
                if child is None or child.capability.produces != key.wanted_type:
                    continue
                if child.silent or child.unit_id == producer.unit_id:
                    continue
                child.deliver_search(key, edge, node["child_allocations"][edge],
                                     lineage=node["lineage"] + (producer.unit_id,),
                                     sender=producer.unit_id, context=ctx,
                                     transport=v5.HARNESS_DELIVERY)
                cnode = child.canonical_searches.get(key)
                if cnode is None or cnode.get("local_candidate") is None:
                    continue
                q = cnode["local_candidate"]
                producer.deliver_proposal(key, edge, q, child.unit_id)
                if node["proposal_routes"].get(q.proposal_id) != edge:
                    continue
                p_id = node["local_candidate"].proposal_id
                if p_id == q.proposal_id:
                    continue
                return o, j, producer, ctx, key, node, p_id, q, seed
    raise AssertionError(
        "no source holding an active local candidate alongside a rival "
        "registered through one of its own child edges, across the "
        "pre-registered seeds; failing to build the structure is a failure of "
        "this specification, not a reason to skip it")


def test_a_source_candidate_that_loses_to_another_proposal_is_cancelled():
    """The case a generic cancellation does not cover.

    Here the wave is NOT cancelled -- it COMMITS, around somebody else. `_seal`
    is called with an accepted id, and the source's own `local_candidate` is in
    neither `proposals_outstanding` nor `proposals_rejected`, so it is the one
    proposal the sealing pass can silently walk past while still reporting a
    fully dispositioned wave.
    """
    o, j, producer, ctx, key, node, losing, rival, seed = _source_with_rival()
    assert node.get("local_candidate") is not None
    assert node["proposal_routes"].get(rival.proposal_id) in node["children_opened"]
    reset()

    producer.deliver_terminal(key, node["adopted_parent_edge"],
                              "SearchCommitted", 0.0, rival.proposal_id,
                              sender=j.unit_id)

    assert node["status"] == "COMMITTED"
    assert node["accepted_proposal_id"] == rival.proposal_id
    assert node["proposal_disposition"].get(rival.proposal_id) == "accepted"
    assert node["proposal_disposition"].get(losing) == "cancelled", (
        f"the source's OWN candidate was left undispositioned when the wave "
        f"committed around another proposal: {node['proposal_disposition']}")
    assert node.get("local_candidate") is None
    assert not node["eligible_offer"], (
        "the source still advertises an offer that lost to another candidate")
    assert _counter("UNDISPOSITIONED_LOCAL_PROPOSALS") == 0


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
    # DELIBERATELY TOLERANT OF THE MISSING COUNTER. This is the plain smoke
    # test: it must hold BEFORE the mechanism exists, so it cannot require a
    # counter the runtime has not defined yet. The strict specification below
    # requires the counter to exist and to be non-vacuous.
    assert C.d.get("HARNESS_DELIVERIES_USED", 0) == 0, (
        "a healthy live run used the harness bypass")


def test_the_harness_bypass_is_counted_and_never_taken_by_live_delivery():
    """The plain test above cannot prove quarantine, and should not pretend to.

    It inspects inboxes and outboxes AFTER `run_item` returns, and a scheduler
    can deliver and drain a message in between, leaving no queue evidence. It
    also passes when the counter does not exist at all -- which is exactly why
    it passes today, before anything is implemented.

    This one requires the counter to exist, to move when the bypass is taken,
    and to stay at zero across a live run whose DELIVERY HISTORY is inspected
    rather than its drained queues.
    """
    o, j, nbr, other, stranger, ctx, key, seed = _pair()
    edge, alloc = "e/harness", 6.0
    reset()

    # Taking the bypass must be visible.
    nbr.deliver_search(key, edge, alloc, lineage=(j.unit_id,), sender=j.unit_id,
                       context=ctx, transport=v5.HARNESS_DELIVERY)
    assert _counter("HARNESS_DELIVERIES_USED") == 1, (
        "the explicit bypass was taken and not counted, so its use cannot be "
        "distinguished from an authenticated adoption")
    assert key in nbr.canonical_searches, "the declared bypass was refused"
    assert _counter("TOTAL_CANONICAL_SEARCH_ADOPTIONS") == 1
    assert _counter("AUTHENTICATED_SEARCH_ADOPTIONS") == 0, (
        "a harness bypass was counted as an authenticated adoption, which would "
        "hold the Single Bottleneck Metric at 1.0 while the gate was skipped")

    # A live run must never take it, measured over DELIVERY HISTORY.
    live = F.development(random.Random(4000))
    F.prepare(live)
    reset()
    seen = []
    original_step = v5.Unit.step

    # MEASURE ARRIVALS, NOT ONE SENDING ROUTINE.
    #
    # The previous instrument patched `Organ._deliver` alone. `Organ._pump` is a
    # SECOND, independent delivery path: it drains outboxes and increments
    # `messages` without ever calling `_deliver`. On this fixture all 1012
    # messages travel `_pump` and ZERO travel `_deliver`, so the instrument
    # watched a path carrying no traffic and `seen` stayed empty. Its own guard
    # caught that -- "no messages were delivered, so this proves nothing" was a
    # true statement about the instrument, not about the runtime.
    #
    # Recording each unit's inbox as it is consumed measures what ACTUALLY
    # ARRIVED, which is the delivery history this specification says it wants,
    # and it is indifferent to which routine did the sending.
    def recording_step(self, caps, _o=original_step, _s=seen):
        for src, msg in self.inbox:
            _s.append((src, self.unit_id, msg))
        return _o(self, caps)

    v5.Unit.step = recording_step
    try:
        live.commission()
        assert live.result_ok(live.run_item(PAYLOAD_A)), "formation stopped working"
    finally:
        v5.Unit.step = original_step
    # Anything delivered but never consumed still counts as delivered.
    for u in live.units.values():
        for src, msg in u.inbox:
            seen.append((src, u.unit_id, msg))

    assert seen, "no messages were delivered, so this proves nothing"
    for src, dest, msg in seen:
        parts = msg if isinstance(msg, tuple) else (msg,)
        assert v5.HARNESS_DELIVERY not in parts and dest is not v5.HARNESS_DELIVERY, (
            f"{src} delivered a message carrying the harness capability")
    assert _counter("HARNESS_DELIVERIES_USED") == 0, (
        "a healthy live run took the harness bypass")


def test_the_scheduler_ingress_path_adopts_only_authenticated_searches():
    """THE METRIC, MEASURED ON THE TRANSPORT PATH.

    An undamaged formation run is NOT evidence for this ratio. Formation
    deliberately keeps the legacy `Need` mechanism, so
    `TOTAL_CANONICAL_SEARCH_ADOPTIONS` can stay at zero there permanently -- even
    after Commit 3 -- and a `if total:` guard would make the assertion pass
    without the scheduler ever having adopted anything.

    So the search is put on the wire: the sender creates its own probe, queues an
    ordinary `__search__` message, `Organ._deliver` moves it, and `step` handles
    it. No bypass anywhere on the path.
    """
    o, j, nbr, other, stranger, ctx, key, seed = _pair()
    edge, alloc = "e/wire", 6.0
    _open_probe(o, j, nbr, key, edge, alloc)
    j.outbox.append((nbr.unit_id, ("__search__", key, edge, alloc,
                                   (j.unit_id,), ctx)))
    reset()

    o._deliver(j)
    assert any(m for _, m in nbr.inbox
               if isinstance(m, tuple) and m and m[0] == "__search__"), (
        "the transport did not carry the search to the receiver's inbox")
    nbr.step(o._caps(nbr))

    assert key in nbr.canonical_searches, (
        "a properly announced search delivered over the real transport was not "
        "adopted")
    total = _counter("TOTAL_CANONICAL_SEARCH_ADOPTIONS")
    assert total == 1, f"{total} canonical adoptions recorded, expected exactly 1"
    assert _counter("AUTHENTICATED_SEARCH_ADOPTIONS") == 1, (
        "an adoption over the authenticated scheduler path was not counted as "
        "authenticated, so the Single Bottleneck Metric cannot reach 1.0")
    assert _counter("HARNESS_DELIVERIES_USED") == 0, (
        "the scheduler path took the harness bypass")
    for _, msg in nbr.inbox:
        parts = msg if isinstance(msg, tuple) else (msg,)
        assert v5.HARNESS_DELIVERY not in parts
