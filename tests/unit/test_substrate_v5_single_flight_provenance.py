"""2A: provenance, rejection continuation and distributed credit conservation.

PRE-REGISTERED BEFORE THE CORRESPONDING RUNTIME CHANGE. Every mechanism-dependent
test here is `xfail(strict=True)`, so a spec that starts passing is reported as a
FAILURE until its marker is deliberately removed in a reviewable commit.

WHY THIS FILE EXISTS. Commit 2 (`1f6a3e3`) landed the Single-Flight V2 core and
was audited. Four runtime defects and one test defect survived that commit, and
none of them is reachable by the existing specifications:

  1. MISSING CONTEXT FAILS OPEN. `deliver_search` rejects a context only when one
     is SUPPLIED and does not match. With no context at all, `_candidate_refusal`
     returns `candidate_context_absent` -- and the code then adopts, creates a
     canonical node and EXPANDS it. The result is a live search whose SearchKey
     advertises bound constraints while the node running it holds none of them.
     Absence of evidence was treated as absence of constraint.

  2. IDENTITY IS NOT PROVENANCE. The derived SHA-256 `proposal_id` binds the
     payload's own fields, so a relay cannot mutate a proposal and keep its
     identity. It cannot do anything else. `deliver_proposal` accepts an
     arbitrary `edge_id` and installs it into `proposal_routes` without checking
     that the edge is one of the node's own children, that the immediate sender
     is that edge's recorded target, or that the edge carries the same SearchKey.
     A relay can therefore mint a NEW internally consistent payload and register
     it on a fabricated route. A hash is integrity, not authentication.

  3. A REJECTED PROPOSAL STRANDS THE WAVE. Every relay that forwards a proposal
     records it in `proposals_outstanding`, and the exhaustion path explicitly
     refuses to terminate while any proposal is outstanding. When the root
     rejects, it clears only its OWN record and writes local telemetry. No
     rejection travels back down the registered route, so intermediates wait
     forever on a decision that was already made, and the source keeps
     `eligible_offer` set for a candidate that was refused. No exhaustion echo,
     no bounded escalation, and edges left open.

  4. COMMIT AND CANCELLATION DO NOT CONSERVE CREDIT. `_release_child` moves a
     child's ENTIRE allocation from in-flight to `cancelled_credit` with no
     acknowledgement from the child. The child may already have consumed credit,
     opened descendants, or transferred allocations further down; it then closes
     and accounts that same credit itself. Each node's local algebra balances
     while the distributed history is false. A parent may classify only what a
     child confirmed, plus reserve it never sent.

DECLARED SEAMS the corrected runtime must provide:

    Unit.deliver_proposal(key, edge, payload, sender)
                                         the IMMEDIATE sender, verified against
                                         node["child_targets"][edge]
    Unit.deliver_search_ack(key, edge, refund, consumed)
                                         a child's closure evidence. NOT a
                                         terminal: the edge's single terminal is
                                         the commit or cancellation command that
                                         travelled down it.
    "__proposal_rejected__" control       routed hop by hop through
                                         proposal_routes, nonterminal

New counters:

    UNOWNED_PROPOSAL_ROUTES
    CONTEXTLESS_CANONICAL_NODES
    STRANDED_REJECTED_PROPOSALS
    UNSUPPORTED_CHILD_CANCELLATION_CREDIT
    REJECTED_PROPOSALS_TOTAL
    REJECTED_PROPOSALS_RESOLVED
    UNAUTHENTICATED_PROPOSAL_DELIVERIES

Single Bottleneck Metric:

    REJECTED_PROPOSALS_RESOLVED / REJECTED_PROPOSALS_TOTAL == 1.0
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
from substrate.v5 import ENV, SINK, C, Terminal, reset

import fixtures as F

PAYLOAD_A = "  Claim-77  "
PAYLOAD_B = "  Claim-78  "
SEEDS = tuple(range(60))

# Distinct from `spec`, `live` and `inherited`, so an activation commit can
# target exactly this group.
core = pytest.mark.xfail(
    strict=True,
    reason="Single-Flight 2A provenance and conservation are not implemented yet")


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

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
        o.units[j.bonds[slot].supplier].silent = True
        return o, j, slot, j.bonds[slot].supplier, seed
    raise AssertionError(
        f"no formed independently-supplied join with n_auth={n_auth} "
        f"density={density} across seeds {SEEDS[0]}..{SEEDS[-1]}; failing to "
        f"construct the structure is a failure of this specification, not a "
        f"reason to skip it")


def _ctx(**kw):
    """THE canonical SearchContext schema, identical to the other two files."""
    base = dict(causally_refused_sources=frozenset(),
                must_differ_from_suppliers=frozenset(),
                maximum_supplier_cost=99.0,
                cooldown_excluded_suppliers=frozenset(),
                constraint_generation=0,
                policy_snapshot=())
    base.update(kw)
    return v5.SearchContext(**base)


def _key_for(unit, slot, ctx, need_id, wanted=None):
    return v5.SearchKey.build(
        need_id=need_id, work_item_generation=2, origin_unit=unit.unit_id,
        origin_slot=slot, wanted_type=wanted or unit.capability.accepts[slot],
        context=ctx)


def _kind(x):
    return getattr(x, "kind", x)


def _nodes(o):
    return {(u.unit_id, k): n for u in o.units.values()
            for k, n in getattr(u, "canonical_searches", {}).items()}


def _counter(name):
    """A missing counter is a FAILURE, not a silent zero."""
    assert name in C.d, (
        f"the runtime defines no {name} counter, so the behaviour it names "
        f"cannot be measured and this specification cannot be satisfied")
    return C[name]


def _relay(o, rounds=24):
    """Deliver ONLY Single-Flight messages, through the real handlers.

    The organ's own dispatcher would also run `attempt()` and could start
    unrelated repairs, which would make a controlled provenance test depend on
    incidental traffic. This moves the protocol's own messages and nothing else,
    honours cut links exactly as `Organ._deliver` does, and passes the true
    immediate sender -- which is the whole point of the tests below.
    """
    moved = 0
    for _ in range(rounds):
        pending = [(u, list(u.outbox)) for u in o.units.values() if u.outbox]
        if not pending:
            break
        for u, box in pending:
            u.outbox.clear()
            for dest, msg in box:
                if dest not in o.units or o.is_cut(u.unit_id, dest):
                    continue
                d = o.units[dest]
                if isinstance(msg, Terminal):
                    # The immediate sender travels with a terminal exactly as it
                    # does with a proposal. Dropping it here would leave the
                    # relay authenticating the data plane and not the control
                    # plane, which is the whole subject of the 2B specs.
                    d.deliver_terminal(msg.search_key, msg.edge_id, msg.kind,
                                       msg.refund, msg.proposal_id,
                                       sender=u.unit_id,
                                       from_unit=msg.from_unit,
                                       to_unit=msg.to_unit)
                    moved += 1
                elif isinstance(msg, tuple) and msg:
                    tag = msg[0]
                    if tag == "__search__":
                        d.deliver_search(msg[1], msg[2], msg[3], msg[4],
                                         u.unit_id,
                                         msg[5] if len(msg) > 5 else None)
                        moved += 1
                    elif tag == "__proposal__":
                        d.deliver_proposal(msg[1], msg[2], msg[3], u.unit_id)
                        moved += 1
                    elif tag == "__proposal_rejected__":
                        d.deliver_proposal_rejected(msg[1], msg[2], msg[3],
                                                    msg[4], u.unit_id)
                        moved += 1
                    elif tag == "__search_ack__":
                        d.deliver_search_ack(msg[1], msg[2], msg[3], msg[4],
                                             u.unit_id)
                        moved += 1
    return moved


def _reopen_locally(o, consumer, slot):
    """A REAL reopen through the unit's own event-driven path.

    `attempt()` pulls, observes the silenced supplier, fences contrastively and
    reopens. Nothing here fabricates an unbonded slot or an open need.
    """
    consumer.attempt(o._port(consumer))
    assert slot not in consumer.bonds, (
        f"slot {slot} at {consumer.unit_id} was never reopened, so there is no "
        f"obligation for a proposal to resolve against")
    nid = consumer.open_needs.get(slot)
    assert nid is not None, "the reopen produced no open Need generation"
    return nid


def _root_wave(o, consumer, slot, must_differ, allocation=18.0):
    """Open a canonical root for a really reopened obligation and spread it."""
    nid = _reopen_locally(o, consumer, slot)
    ctx = _ctx(causally_refused_sources=frozenset(consumer.refused),
               must_differ_from_suppliers=frozenset(must_differ),
               maximum_supplier_cost=max(1.0, consumer.repair_budget))
    root = v5.SearchKey.build(
        need_id=nid, work_item_generation=o.item_seq,
        origin_unit=consumer.unit_id, origin_slot=slot,
        wanted_type=consumer.capability.accepts[slot], context=ctx)
    node = consumer.open_canonical_search(root, f"{nid}#root", allocation,
                                          context=ctx)
    _relay(o)
    return ctx, root, node


def _multihop(density=0.8):
    """Scan seeds for a wave in which a proposal ACTUALLY traversed a relay.

    A required adversarial condition must not vanish because one seed happened to
    put every candidate one hop from the origin. Hard asserted, never skipped.
    """
    for seed in SEEDS:
        o = _build_raw(4, seed, density)
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
        reset()
        # must_differ deliberately EMPTY: the sibling then passes remote
        # eligibility and is refused at settlement, which is the "valid
        # remotely, rejected at the root" case the specification needs.
        ctx, root, node = _root_wave(o, j, slot, must_differ=())
        nodes = _nodes(o)
        for pid, edge in node["proposal_routes"].items():
            hops = [(uid, n) for (uid, k), n in nodes.items()
                    if k == root and uid != j.unit_id
                    and pid in n.get("proposal_routes", {})]
            if hops:
                return o, j, slot, victim, ctx, root, node, pid, hops, seed
    raise AssertionError(
        "no proposal traversed an intermediate relay across the pre-registered "
        "seeds, so multi-hop rejection routing could not be exercised; failing "
        "to construct the structure is a failure of this specification, not a "
        "reason to skip it")


def _nonfirm_wave():
    """Scan seeds for a wave in which a NON-FIRM candidate actually proposed.

    Firmness of the spare producers is a property of the seed, not of the
    mechanism: at seed 0 every AUTH producer that proposed was firm, so a
    non-firm rejection could not be exercised there at all and the specification
    would have passed its own precondition check vacuously. Scanned, then hard
    asserted.
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
        if len({b.supplier for b in j.bonds.values()}) != 2:
            continue
        slot = min(j.bonds)
        victim = j.bonds[slot].supplier
        o.units[victim].silent = True
        reset()
        ctx, root, node = _root_wave(o, j, slot, must_differ=())
        nonfirm = [e.payload for evs in o.search_edge_events.values() for e in evs
                   if _kind(e) == "SearchProposal" and e.payload is not None
                   and not e.payload.firm
                   and e.payload.proposal_id in node["proposal_routes"]]
        if nonfirm:
            return o, j, slot, victim, ctx, root, node, nonfirm[0], seed
    raise AssertionError(
        "no non-firm candidate proposed to the root across the pre-registered "
        "seeds, so the non-firm rejection path could not be exercised; failing "
        "to construct the structure is a failure of this specification, not a "
        "reason to skip it")


def _development_reopened():
    """The one fixture in which an eligible AND FIRM spare demonstrably exists.

    In the n_auth=4 join fixture, formation leaves the only firm AUTH producers
    bonded into the join itself, so no spare is settleable and an acceptance --
    which the credit-conservation test needs -- cannot occur there at all. At the
    VERDICT layer of the development fixture both RECON producers are firm.
    """
    o = F.development(random.Random(4000))
    F.prepare(o)
    reset()
    o.commission()
    assert o.result_ok(o.run_item(PAYLOAD_A)), "the development fixture did not form"
    consumer = next(u for u in o.units.values()
                    if u.capability.accepts == ("RECON",) and u.bonds)
    slot = 0
    victim = consumer.bonds[slot].supplier
    o.units[victim].silent = True
    reset()
    ctx, root, node = _root_wave(o, consumer, slot, must_differ=())
    return o, consumer, slot, victim, ctx, root, node


# ---------------------------------------------------------------------------
# 1. A missing context must FAIL CLOSED
# ---------------------------------------------------------------------------

@core
def test_a_search_delivered_without_its_context_creates_nothing():
    """Absence of evidence is not absence of constraint.

    The SearchKey advertises bound refusals, a must-differ set, a cost ceiling, a
    cooldown set, a constraint generation and a policy snapshot. A node that
    received none of them cannot enforce any of them, so adopting the search and
    expanding it manufactures a wave that claims constraints nobody is holding.
    """
    o, j, slot, victim, seed = _damaged(4)
    ctx = _ctx(must_differ_from_suppliers=frozenset({"someone.excluded"}),
               maximum_supplier_cost=3.0)
    unit = next(u for u in o.units.values()
                if u.unit_id not in (ENV, SINK) and u.unit_id != j.unit_id)

    # PAIRED POSITIVE CONTROL, same unit, same allocation, context PRESENT.
    reset()
    ok_key = _key_for(j, slot, ctx, "probe:context:control")
    control = unit.deliver_search(ok_key, "e/ctx/control", allocation=6.0,
                                  lineage=(j.unit_id,), sender=j.unit_id,
                                  context=ctx,
                                  transport=v5.HARNESS_DELIVERY)
    assert _kind(control) != "SearchContextRejected", (
        f"the control arrival was rejected ({_kind(control)}) even WITH its "
        f"context, so refusing the contextless arrival below would prove "
        f"nothing about the missing context")
    assert ok_key in unit.canonical_searches, (
        "the control arrival created no canonical node, so this unit does not "
        "adopt searches at all and the negative case is not attributable")

    reset()
    key = _key_for(j, slot, ctx, "probe:context:absent")
    outcome = unit.deliver_search(key, "e/ctx/absent", allocation=6.0,
                                  lineage=(j.unit_id,), sender=j.unit_id,
                                  transport=v5.HARNESS_DELIVERY)

    assert _kind(outcome) == "SearchContextRejected", (
        f"a search delivered without its SearchContext returned "
        f"{_kind(outcome)}; a node that holds none of the constraints its key "
        f"advertises must terminate the edge, not adopt the search")
    assert abs(getattr(outcome, "refund", -1.0) - 6.0) < 1e-9, (
        f"the rejected arrival refunded {getattr(outcome, 'refund', None)} of "
        f"its 6.0 allocation; a search that did no work consumes nothing")
    assert key not in unit.canonical_searches, (
        "a contextless arrival created a canonical node")
    assert C["UNIQUE_CANONICAL_SEARCH_NODES"] == 0
    assert C["CANONICAL_SEARCH_EXPANSIONS"] == 0
    assert C["DIRECTED_SEARCH_EDGES_PROBED"] == 0, (
        "a contextless arrival opened descendants")
    assert not [m for m in unit.outbox
                if isinstance(m[1], tuple) and m[1] and m[1][0] == "__proposal__"], (
        "a contextless arrival produced a proposal")
    assert _counter("CONTEXTLESS_CANONICAL_NODES") == 0


# ---------------------------------------------------------------------------
# 2. Identity is not provenance
# ---------------------------------------------------------------------------

def _proposal_for(o, node, supplier, edge, source_edge=None):
    """A payload whose SOURCE HOP is coherent.

    `source_edge_id` says where the proposal ORIGINATED. When it equals the edge
    the proposal arrives on, this delivery IS the source hop and the supplier
    must be that edge's target -- otherwise the payload claims a unit proposed
    itself over an edge it does not sit on, which a correct receiver refuses.
    Naming an arbitrary supplier while pointing `source_edge_id` at the arrival
    edge made the POSITIVE CONTROLS below unsatisfiable, so the negative results
    they exist to attribute proved nothing.
    """
    key = node["search_key"]
    ctx = node["search_context"]
    cand = o.units[supplier]
    return v5.SearchOfferPayload(
        proposal_id="label", search_key=key, context_digest=ctx.context_digest(),
        supplier=supplier, supplier_class=cand.capability.klass(),
        offered_type=key.wanted_type, cost=cand.capability.cost,
        firm=not cand.unmet(), derivation_chain=cand._derives_from(),
        source_node=supplier,
        source_edge_id=source_edge if source_edge is not None else edge)


@core
def test_a_proposal_on_an_edge_the_node_does_not_own_is_refused():
    """A relay cannot mutate a proposal and keep its id. It can mint a new one.

    Nothing stops it registering that new, internally consistent payload against
    a route the receiving node never opened. Content integrity says the evidence
    was not altered; it says nothing about who delivered it or over which edge.
    """
    o, j, slot, victim, seed = _damaged(4)
    reset()
    ctx = _ctx()
    key = _key_for(j, slot, ctx, "probe:unowned")
    node = j.open_canonical_search(key, "e/root", 12.0, context=ctx)
    kids = list(node["children_opened"])
    assert len(kids) >= 2, f"the root opened {len(kids)} children; need two"
    # The SOURCE of a source-hop proposal is the arrival edge's own target.
    origin_unit = node["child_targets"][kids[0]]

    # PAIRED POSITIVE CONTROL: the real child edge, from that edge's real target.
    good = _proposal_for(o, node, origin_unit, kids[0])
    j.deliver_proposal(key, kids[0], good, origin_unit)
    assert node["proposal_routes"].get(good.proposal_id) == kids[0], (
        "a proposal arriving on a real child edge from that edge's real target "
        "was not registered, so refusing the forged routes below proves nothing")

    routes_before = dict(node["proposal_routes"])
    forged = _proposal_for(o, node, origin_unit, "e/fabricated")
    assert forged.proposal_id != good.proposal_id, (
        "the two payloads share an id, so this test cannot distinguish them")
    reset()
    j.deliver_proposal(key, "e/fabricated", forged, node["child_targets"][kids[0]])

    assert dict(node["proposal_routes"]) == routes_before, (
        "a proposal was registered against an edge the node never opened")
    assert "e/fabricated" not in o.search_edge_terminals, (
        "a terminal was written to a fabricated edge")
    assert _counter("UNOWNED_PROPOSAL_ROUTES") == 1
    reasons = [getattr(x, "reason", None)
               for evs in o.search_edge_events.values() for x in evs]
    assert "proposal_edge_not_owned" in reasons, (
        f"no attributable proposal_edge_not_owned reason: {reasons}")
    # `_damaged` silences the victim but leaves its BOND in place, so the slot is
    # occupied throughout this test. The assertion is therefore that the existing
    # bond is untouched -- demanding an EMPTY slot asserted a state the fixture
    # never produces, and would have failed against a correct implementation.
    held = j.bonds[slot].supplier
    assert j.settle_search_offer(forged) is False, (
        "an unowned proposal was settled")
    assert j.bonds[slot].supplier == held, (
        "an unowned proposal replaced the slot's existing bond")


@core
def test_a_proposal_from_the_wrong_immediate_sender_is_refused():
    """The edge is real. The neighbour that handed it over is not its target.

    Without this, any unit that can reach the node can inject a candidate onto
    somebody else's branch, and the commit for that branch is then routed to a
    neighbour that never carried the proposal.
    """
    o, j, slot, victim, seed = _damaged(4)
    reset()
    ctx = _ctx()
    key = _key_for(j, slot, ctx, "probe:sender")
    node = j.open_canonical_search(key, "e/root", 12.0, context=ctx)
    kids = list(node["children_opened"])
    assert len(kids) >= 2, f"the root opened {len(kids)} children; need two"
    real = node["child_targets"][kids[0]]
    impostor = node["child_targets"][kids[1]]
    assert real != impostor, "the two child edges share a target"
    # A payload that is correct in every other respect, so the ONLY thing the
    # receiver can object to is who handed it over.
    pay = _proposal_for(o, node, real, kids[0])

    j.deliver_proposal(key, kids[0], pay, impostor)

    assert pay.proposal_id not in node["proposal_routes"], (
        f"{impostor} registered a proposal on {real}'s branch")
    assert _counter("UNOWNED_PROPOSAL_ROUTES") == 1
    reasons = [getattr(x, "reason", None)
               for evs in o.search_edge_events.values() for x in evs]
    assert "proposal_sender_mismatch" in reasons, (
        f"no attributable proposal_sender_mismatch reason: {reasons}")

    # PAIRED POSITIVE CONTROL: the SAME payload from the SAME edge's real target
    # must register, so the refusal above is attributable to the sender alone.
    j.deliver_proposal(key, kids[0], pay, real)
    assert node["proposal_routes"].get(pay.proposal_id) == kids[0], (
        "the identical payload was refused even from the edge's real target, so "
        "the refusal above cannot be attributed to sender identity")


# ---------------------------------------------------------------------------
# 3. A rejected proposal must not strand the wave
# ---------------------------------------------------------------------------

def _assert_wave_not_stranded(o, root, node, pid, hops):
    """Nothing may remain open BECAUSE a resolved proposal was remembered."""
    assert pid not in node["proposals_outstanding"], (
        "the root still lists the rejected proposal as outstanding")
    for uid, n in hops:
        assert pid not in n["proposals_outstanding"], (
            f"intermediate {uid} still waits on a proposal the root already "
            f"rejected, so its subtree can never report exhaustion")
    for (uid, k), n in _nodes(o).items():
        if k != root:
            continue
        if n["proposals_outstanding"]:
            assert n["proposals_outstanding"] != {pid}, (
                f"{uid} is blocked solely by the rejected proposal {pid}")
    assert _counter("STRANDED_REJECTED_PROPOSALS") == 0
    total = _counter("REJECTED_PROPOSALS_TOTAL")
    resolved = _counter("REJECTED_PROPOSALS_RESOLVED")
    assert total >= 1, "no rejection was recorded, so this test proves nothing"
    assert resolved == total, (
        f"{total - resolved} of {total} rejected proposals never resolved back "
        f"to their source")


@core
def test_a_firm_proposal_refused_at_settlement_releases_every_hop():
    """Valid remotely, refused by settlement-time policy.

    The candidate passes every constraint that travelled -- no refusal
    intersection, no must-differ entry, under the ceiling, not in cooldown -- and
    `_settle` still refuses it as a duplicate supplier, because domain and
    duplicate checks are computed from origin-local state at commit time. That is
    the designed final enforcement layer, and it is exactly the case in which a
    rejection has to travel home.
    """
    o, j, slot, victim, ctx, root, node, pid, hops, seed = _multihop()
    edge = node["proposal_routes"][pid]
    payload = next(e.payload for e in o.search_edge_events.get(edge, [])
                   if _kind(e) == "SearchProposal"
                   and e.payload is not None and e.payload.proposal_id == pid)
    bonded = {b.supplier for b in j.bonds.values()}
    if payload.supplier not in bonded or not payload.firm:
        candidates = [(p, e2) for e2, evs in o.search_edge_events.items()
                      for e3 in evs if _kind(e3) == "SearchProposal"
                      and (p := e3.payload) is not None
                      and p.supplier in bonded and p.firm
                      and p.proposal_id in node["proposal_routes"]]
        assert candidates, (
            "no firm proposal from an already-bonded supplier reached the root, "
            "so a settlement-time refusal of a remotely-valid candidate could "
            "not be exercised")
        payload = candidates[0][0]
        pid = payload.proposal_id
        hops = [(uid, n) for (uid, k), n in _nodes(o).items()
                if k == root and uid != j.unit_id and pid in n["proposal_routes"]]
        assert hops, "the chosen firm proposal did not traverse a relay"

    assert j.settle_search_offer(payload) is False, (
        f"{payload.supplier} already fills another slot on {j.unit_id}, yet "
        f"settlement accepted it")
    assert j._last_refusal == "duplicate_supplier", (
        f"the refusal was {j._last_refusal!r}; this test needs a settlement-time "
        f"policy refusal, not a transport or precondition failure")
    assert node["status"] == "OPEN", "a rejection closed the root's search"
    assert root.need_id not in j.closed_needs, "a rejection closed the Need"

    _relay(o)
    _assert_wave_not_stranded(o, root, node, pid, hops)

    source = o.units[payload.source_node]
    src_node = source.canonical_searches.get(root)
    assert src_node is not None, "the proposing unit holds no canonical node"
    assert not src_node["eligible_offer"], (
        "the source still advertises an eligible offer for a candidate the "
        "origin refused, so it will never continue or exhaust")
    assert src_node.get("local_candidate") is None

    # SCOPED TO THE REJECTED PROPOSAL'S OWN BRANCH. Requiring EVERY probed edge
    # to be terminated was wrong: the root's other branches carry candidates it
    # has not yet decided, and an undecided candidate is a live search path, not
    # a stranded one. Demanding their closure would have failed correct
    # behaviour and, worse, could be "fixed" by cancelling branches a rejection
    # has no business touching.
    #
    # ONE EDGE MAY CARRY SEVERAL PROPOSALS. A relay forwards every candidate its
    # subtree produced up its single adopted parent edge, so the rejected
    # proposal's own branch can still be live because a DIFFERENT candidate came
    # home the same way. Asserting that branch is no longer undecided was
    # therefore wrong. What the rejection must guarantee is proved above, per
    # proposal: cleared at every hop, and the source released.
    undecided = set(node["proposal_routes"][p]
                    for p in node["proposals_outstanding"]
                    if p in node["proposal_routes"])
    for eid, rec in o.search_edge_probes.items():
        if rec["search_key"] != root or eid in undecided:
            continue
        if any(eid.startswith(u + "/") for u in undecided):
            continue        # a descendant of a branch still awaiting a decision
        assert eid in o.search_edge_terminals, (
            f"edge {eid} was probed and never terminated after the rejection "
            f"resolved, and it carries no undecided candidate; the branch is "
            f"stranded")


@core
def test_a_rejected_nonfirm_proposal_lets_the_source_continue_or_exhaust():
    """The second form of the same defect.

    A non-firm candidate sets `eligible_offer` and expands. When the origin
    refuses it as `nonfirm`, nothing clears that flag, so the source's exhaustion
    path -- which will not terminate while an eligible offer is recorded -- can
    never fire.
    """
    o, j, slot, victim, ctx, root, node, payload, seed = _nonfirm_wave()
    pid = payload.proposal_id
    assert not payload.firm, "the scanned candidate is firm"

    src_node = o.units[payload.source_node].canonical_searches.get(root)
    assert src_node is not None, "the proposing unit holds no canonical node"
    assert src_node["eligible_offer"], (
        "the non-firm source never recorded an eligible offer, so clearing it "
        "below would prove nothing")

    assert j.settle_search_offer(payload) is False, "a non-firm candidate bonded"
    assert C["SEARCH_OFFER_SETTLEMENT_REJECTIONS"] >= 1
    _relay(o)

    # THE NAMED DEFECT FIRST. Everything else in this test is downstream of it.
    assert not src_node["eligible_offer"], (
        "the non-firm source still records an eligible offer after the origin "
        "refused it, so its exhaustion path -- which will not terminate while an "
        "eligible offer is recorded -- can never fire")
    assert src_node.get("local_candidate") is None
    assert (src_node["children_outstanding"]
            or src_node["status"] in ("EXHAUSTED", "CLOSED", "COMMITTED")), (
        f"the refused source is {src_node['status']} with no live children and "
        f"no terminal outcome: it neither continued nor exhausted")

    hops = [(uid, n) for (uid, k), n in _nodes(o).items()
            if k == root and uid != j.unit_id and pid in n["proposal_routes"]]
    _assert_wave_not_stranded(o, root, node, pid, hops)


# ---------------------------------------------------------------------------
# 4. Credit must be conserved across the distributed wave
# ---------------------------------------------------------------------------

@core
def test_a_parent_may_not_cancel_credit_a_child_never_confirmed():
    """Local algebra that balances can still record a false history.

    On commitment the parent moves each outstanding child's ENTIRE allocation to
    `cancelled_credit`. The child, independently, accounts the same credit as
    consumed or transferred. Both ledgers balance; together they describe two
    incompatible histories of the same credit. A parent may classify only what a
    child confirmed, plus reserve it never sent.
    """
    o, consumer, slot, victim, ctx, root, node = _development_reopened()
    routes = dict(node["proposal_routes"])
    assert routes, "no proposal reached the root, so no commit can be exercised"
    winner = None
    for pid, edge in routes.items():
        pay = next((e.payload for e in o.search_edge_events.get(edge, [])
                    if _kind(e) == "SearchProposal" and e.payload is not None
                    and e.payload.proposal_id == pid), None)
        if pay is not None and pay.firm and consumer.settle_search_offer(pay):
            winner = pay
            break
    assert winner is not None, (
        "no proposal was accepted, so the commit-time cancellation path was "
        "never exercised")
    assert consumer.bonds[slot].settled_from_search_offer

    _relay(o)                       # acknowledgements must be allowed to return

    nodes = _nodes(o)
    # THE NAMED DEFECT FIRST. A comparison of cumulative `child_allocations`
    # against `incoming_allocation` would be UNSOUND -- a refunded allocation
    # returns to reserve and is lawfully re-spent, so cumulative transfers
    # legitimately exceed the original grant. The sound statement is per edge and
    # requires evidence: a parent may close a child's allocation only against
    # what that child CONFIRMED.
    for (uid, k), n in nodes.items():
        if k != root:
            continue
        assert "child_confirmed" in n, (
            f"{uid} keeps no record of what each child confirmed about its "
            f"allocation, so every closure it performs is a unilateral "
            f"classification of credit it had already transferred")

    checked = 0
    for (uid, k), n in nodes.items():
        if k != root:
            continue
        assert n["child_allocations_in_flight"] < 1e-6, (
            f"{uid} closed with {n['child_allocations_in_flight']} still in "
            f"flight; an allocation was neither confirmed nor returned")
        for edge, per in n["child_allocations"].items():
            target = n["child_targets"].get(edge)
            child = nodes.get((target, k)) if target else None
            if child is None:
                continue        # the edge terminated before a node was adopted
            if child["adopted_parent_edge"] != edge:
                # The target already held this search from an EARLIER arrival, so
                # this edge was coalesced and its credit was settled by the
                # SearchCoalesced terminal, not by that node's ledger. Comparing
                # this allocation against the node's incoming_allocation would
                # compare two different arrivals -- a defect in the check, not in
                # the mechanism.
                continue
            checked += 1
            assert abs(child["incoming_allocation"] - per) < 1e-6, (
                f"{uid} sent {per} on {edge} but {target} recorded "
                f"{child['incoming_allocation']}")
            spent = (child["consumed_credit"] + child["cancelled_credit"]
                     + child["returned_to_parent"])
            assert abs(spent - per) < 1e-6, (
                f"{target} accounts {spent} against an allocation of {per}")
            confirmed = n["child_confirmed"].get(edge)
            assert confirmed is not None, (
                f"{uid} closed the allocation on {edge} with no acknowledgement "
                f"from {target}; transferred credit was classified unilaterally")
            refund, consumed = confirmed
            assert abs(refund - child["returned_to_parent"]) < 1e-6, (
                f"{uid} credited a refund of {refund} on {edge} while {target} "
                f"reports returning {child['returned_to_parent']}")
            assert abs(refund + consumed - per) < 1e-6, (
                f"{edge}: {refund} + {consumed} != {per}")
    assert checked >= 1, (
        "no parent/child allocation pair existed, so conservation across a hop "
        "was never checked")
    assert _counter("UNSUPPORTED_CHILD_CANCELLATION_CREDIT") == 0
