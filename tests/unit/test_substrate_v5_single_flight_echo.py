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
    Organ.space_exhaustion_proofs      [SearchKey, ...]
    v5.ROOT_SEARCH_CREDIT_OVERRIDE     None, or a float honoured by the root
                                       search ledger -- the ONLY correct way to
                                       starve search credit, since repair_budget
                                       is a supplier cost ceiling, not a message
                                       credit budget

EDGE TELEMETRY IS KEYED BY EDGE ID, NOT BY A TUPLE. An earlier draft keyed
terminals by `(from_unit, to_unit, SearchKey)` while nodes stored
`adopted_parent_edge` as an edge identifier, then compared the two by tuple
membership. Those are different identities and the comparison was meaningless:

    Organ.search_edge_probes[edge_id]    -> {from_unit, to_unit, search_key, count}
    Organ.search_edge_terminals[edge_id] -> {from_unit, to_unit, search_key,
                                             outcomes: [...]}

and each canonical node records the edges that arrived at it:

    node["incoming_edges"]              -> [edge_id, ...] every arrival at this node
    node["adopted_parent_edge"]         -> edge_id, immutable after adoption
    node["adopted_parent_edge_initial"] -> edge_id captured at adoption
    node["adopted_parent_sender"]       -> unit id the adopted edge returns to
    node["children_from"]               -> {incoming edge_id: [child edge_id, ...]}
                                           proves which arrival, if any, created
                                           descendants
"""
from __future__ import annotations

import collections
import contextlib
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

def _build_raw(n_auth=4, seed=7, density=0.8):
    """Construct only. No prepare, no commission, no work item.

    Unit-ID permutation relabels here, when the only structural state is
    `unit_id` and `neighbours`, so nothing can be silently regenerated.
    """
    caps = F._spine("alpha2") + F._spine("beta2") + F._spine("gamma2")
    for i in range(n_auth):
        caps.append(F.cap(f"au{i}", ("PX", "PX"), "AUTH", F.AUTHORISE,
                          1.0 + 0.1 * i, f"d.a{i}", "authorise", F.OK_PRICE))
    caps.append(F.cap("rn0", ("AUTH", "AUTH"), "RECON", F.RECONCILE,
                      1.0, "d.p", "reconcile", F.OK_AUTH))
    caps.append(F.cap("db0", ("RECON",), "VERDICT", F.DISBURSE,
                      1.0, "d.r", "disburse", F.OK_RECON))
    return F._organ(caps, random.Random(seed), density)


def _build(n_auth=4, seed=7, density=0.8):
    """A two-input reconcile join fed by `n_auth` distinct AUTH producers."""
    o = _build_raw(n_auth, seed, density)
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


def _ctx(**kw):
    """THE canonical SearchContext schema, identical to the live-path file.

    This file previously built context-free SearchKeys and a SearchOfferPayload
    with the obsolete `edge_id` field and no proposal_id / context_digest /
    source_node / source_edge_id. Keeping that would have forced the
    implementation to retain the partial constructor and payload alias that
    commit 1A explicitly rejected.
    """
    base = dict(causally_refused_sources=frozenset(),
                must_differ_from_suppliers=frozenset(),
                maximum_supplier_cost=99.0,
                cooldown_excluded_suppliers=frozenset(),
                constraint_generation=0,
                policy_snapshot=())
    base.update(kw)
    return v5.SearchContext(**base)


def _key_for(unit, slot, ctx, need_id, wanted=None):
    """Every key is built from the COMPLETE context. No partial constructor."""
    return v5.SearchKey.build(
        need_id=need_id, work_item_generation=2, origin_unit=unit.unit_id,
        origin_slot=slot,
        wanted_type=wanted or unit.capability.accepts[slot], context=ctx)


def _payload(o, key, ctx, supplier, pid, source_edge):
    return v5.SearchOfferPayload(
        proposal_id=pid, search_key=key, context_digest=ctx.context_digest(),
        supplier=supplier,
        supplier_class=o.units[supplier].capability.klass()
        if supplier in o.units else "probe",
        offered_type=key.wanted_type,
        cost=o.units[supplier].capability.cost if supplier in o.units else 1.0,
        firm=True, derivation_chain=frozenset({supplier}),
        source_node=supplier, source_edge_id=source_edge)


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


def _edge_telemetry(o):
    """Edge records keyed by edge_id, with explicit from/to/search_key fields."""
    probes = getattr(o, "search_edge_probes", None)
    terminals = getattr(o, "search_edge_terminals", None)
    assert probes is not None and terminals is not None, (
        "the organ does not record search edge probes or terminals, so edge "
        "uniqueness cannot be proved")
    for eid, rec in probes.items():
        for f in ("from_unit", "to_unit", "search_key", "count"):
            assert f in rec, f"probe record for edge {eid} lacks {f!r}"
    for eid, rec in terminals.items():
        for f in ("from_unit", "to_unit", "search_key", "outcomes"):
            assert f in rec, f"terminal record for edge {eid} lacks {f!r}"
    return probes, terminals


def _kind(x):
    return getattr(x, "kind", x)


def _per_key_edge_uniqueness(o):
    """Each (from_unit, to_unit, SearchKey) probed at most once; one terminal each.

    A global bound like `probes <= units**2` is supplemental: it cannot prove
    per-key uniqueness, which is the actual invariant. Derived from edge-id keyed
    records rather than inferred from tuple membership.
    """
    probes, terminals = _edge_telemetry(o)
    seen = {}
    for eid, rec in probes.items():
        assert rec["count"] == 1, (
            f"edge {eid} was probed {rec['count']} times; at most once per "
            f"SearchKey is the invariant")
        triple = (rec["from_unit"], rec["to_unit"], rec["search_key"])
        seen.setdefault(triple, []).append(eid)
    repeats = {t: e for t, e in seen.items() if len(e) > 1}
    assert not repeats, (
        f"the same directed edge was probed under multiple edge ids for one "
        f"SearchKey: {repeats}")
    for eid in probes:
        outs = terminals.get(eid, {}).get("outcomes", [])
        assert len(outs) == 1, (
            f"edge {eid} received {len(outs)} terminal outcomes, expected exactly 1")
    return probes, terminals


# ---------------------------------------------------------------------------
# Proposal traffic, captured AT EMISSION
#
# `search_edge_terminals` cannot answer "where did this node send its
# proposal". Since the lifecycle/projection separation it holds ACCEPTED
# OUTCOMES only, and an outcome is a different channel from a proposal: a
# proposal is `SearchProposal`, a NONTERMINAL, and it never appears there at
# all. Reading a return route out of that projection was the defect this test
# used to contain -- it filtered for `SearchCommitted`, which is a PARENT
# CONTROL that the 2D rule forbids a child from emitting upward, so the filter
# demanded exactly the message the protocol prohibits.
#
# The canonical wire form is `("__proposal__", SearchKey, edge_id, payload)`
# appended to the emitting unit's outbox. There is no `SearchOffer` type; no
# alias is introduced here to preserve the stale wording.
# ---------------------------------------------------------------------------

class _ProposalTrace:
    """Two capture points, because either alone is unfalsifiable.

    `emitted`   the outbox entry appended by the sending unit. This is the ONLY
                record of the route the SENDER chose, and the only admissible
                source for a routing claim.
    `received`  what `deliver_proposal` was actually handed. A sender-side trace
                on its own would pass against a runtime whose messages never
                leave the outbox, and it cannot show that the unit the sender
                NAMED is the unit that got it.

    Neither point re-implements a runtime predicate, so the trace cannot agree
    with a broken runtime by mirroring it.
    """

    def __init__(self) -> None:
        self.emitted: list[dict] = []
        self.received: list[dict] = []

    def sent_index(self):
        return collections.Counter(
            (r["unit"], r["dest"], r["key"], r["edge"], r["payload"].proposal_id)
            for r in self.emitted)

    def received_index(self):
        return collections.Counter(
            (r["sender"], r["unit"], r["key"], r["edge"], r["payload"].proposal_id)
            for r in self.received)


def _adopted_chain(nodes, key, start):
    """The units on the adopted return path from `start` up toward the origin.

    Each canonical node names exactly one parent, so the path is walked rather
    than guessed. `seen` is not defensive decoration: an adopted chain that
    closed on itself would loop here forever, and returning the partial walk
    lets the caller report it as an unreachable relay instead of hanging.
    """
    chain, seen, cur = [], set(), start
    while cur and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        node = nodes.get((cur, key))
        if node is None:
            break
        cur = node["adopted_parent_sender"]
    if cur and cur not in seen:
        chain.append(cur)
    return chain


@contextlib.contextmanager
def _proposal_trace():
    """Wrap emission and arrival for the duration of one run.

    Wrapping is deliberate rather than replacing: whatever `_propose_upward` is
    bound to when this opens keeps running, so an adversarial candidate
    installed BEFORE the trace is observed exactly as it behaves.
    """
    tr = _ProposalTrace()
    orig_propose = v5.Unit._propose_upward
    orig_deliver_proposal = v5.Unit.deliver_proposal

    def propose(self, node, payload):
        before = len(self.outbox)
        # snapshot the adoption facts AS THEY STOOD AT EMISSION, so a node that
        # rebinds afterwards cannot be laundered by reading only final state
        snap = dict(node_adopted=node["adopted_parent_edge"],
                    node_adopted_initial=node["adopted_parent_edge_initial"],
                    node_sender=node["adopted_parent_sender"],
                    node_incoming=list(node["incoming_edges"]),
                    node_key=node["search_key"],
                    node_status=node["status"])
        orig_propose(self, node, payload)
        for dest, msg in self.outbox[before:]:
            if isinstance(msg, tuple) and msg and msg[0] == "__proposal__":
                tr.emitted.append(dict(unit=self.unit_id, dest=dest, key=msg[1],
                                       edge=msg[2], payload=msg[3], **snap))

    def deliver_proposal(self, key, edge_id, payload,
                         sender=v5._UNSPECIFIED_SENDER):
        tr.received.append(dict(unit=self.unit_id, sender=sender, key=key,
                                edge=edge_id, payload=payload))
        return orig_deliver_proposal(self, key, edge_id, payload, sender)

    v5.Unit._propose_upward = propose
    v5.Unit.deliver_proposal = deliver_proposal
    try:
        yield tr
    finally:
        v5.Unit._propose_upward = orig_propose
        v5.Unit.deliver_proposal = orig_deliver_proposal


def _run_traced(o, payload=PAYLOAD_B):
    """One traced work item. `reset()` inside, so counters match the trace."""
    with _proposal_trace() as tr:
        reset()
        o.run_item(payload)
    return tr


def _assert_offers_return_through_adopted_edges(o, tr, *, label):
    """THE invariant: proposal evidence travels upward through each node's
    immutable adopted parent edge, and parent controls never travel upward.

    Returns the facts it measured, so a caller can assert on the SHAPE of the
    run it obtained (relay present, contest present) instead of assuming it.
    """
    nodes = _nodes(o)
    probes, terminals = _edge_telemetry(o)
    units = o.units

    # -- the run must contain the thing being judged ------------------------
    assert tr.emitted, (
        f"[{label}] no proposal was emitted at all, so this run cannot "
        f"demonstrate that proposals return through the adopted edge")

    sent, got = tr.sent_index(), tr.received_index()
    assert sent == got, (
        f"[{label}] emitted and arrived proposals disagree. Only sent: "
        f"{sorted(sent - got)}. Only received: {sorted(got - sent)}")

    origins = {(uid, k) for (uid, k), n in nodes.items()
               if not n["adopted_parent_sender"]}
    assert origins, (
        f"[{label}] no search origin node exists, so 'an origin never proposes "
        f"upward' would be vacuous")

    by_node: dict = {}
    for r in tr.emitted:
        by_node.setdefault((r["unit"], r["key"]), []).append(r)

    relays = 0
    pre_emission_contested = 0
    for (uid, key), recs in by_node.items():
        node = nodes.get((uid, key))
        assert node is not None, (
            f"[{label}] {uid} emitted a proposal for {key} while holding no "
            f"canonical node for it")
        assert (uid, key) not in origins, (
            f"[{label}] {uid} is the origin of {key} and still proposed "
            f"upward; an origin has no parent to propose to")

        adopted = node["adopted_parent_edge"]
        assert adopted == node["adopted_parent_edge_initial"], (
            f"[{label}] {uid} rebound its adopted parent edge after adoption")
        assert adopted, f"[{label}] {uid} proposed from a node with no adopted edge"

        # PER RECORD FIRST. A group-level "all proposals used one edge" check
        # run ahead of these would short-circuit them and report every attack as
        # the same unstable-route failure, so the test would stop naming WHICH
        # route was wrong -- which is the one thing it is here to do.
        for r in recs:
            assert r["node_key"] == key == r["payload"].search_key, (
                f"[{label}] {uid} sent a proposal whose SearchKey does not "
                f"match the node it came from")
            assert r["node_adopted"] == r["node_adopted_initial"] == adopted, (
                f"[{label}] {uid} held adopted edge {r['node_adopted']} at "
                f"emission but {adopted} at the end of the run")
            assert r["edge"] == adopted, (
                f"[{label}] {uid} returned its proposal through edge "
                f"{r['edge']}, not through its immutable adopted parent edge "
                f"{adopted}")
            assert r["edge"] in r["node_incoming"], (
                f"[{label}] {uid} returned its proposal through {r['edge']}, "
                f"which never arrived at this node: {r['node_incoming']}")
            assert r["dest"] == node["adopted_parent_sender"] == r["node_sender"], (
                f"[{label}] {uid} sent its proposal to {r['dest']}, not to its "
                f"adopted parent {node['adopted_parent_sender']}")
            assert r["dest"] in units[uid].neighbours, (
                f"[{label}] {uid} sent its proposal to {r['dest']}, which is "
                f"not a neighbour; a proposal travels one hop to the adopted "
                f"parent and never jumps toward the origin")

            probe = probes.get(r["edge"])
            assert probe is not None, (
                f"[{label}] {uid} returned its proposal on {r['edge']}, an "
                f"edge the organ never probed")
            assert probe["from_unit"] == r["dest"] and probe["to_unit"] == uid, (
                f"[{label}] the return on {r['edge']} does not retrace the "
                f"arrival: probed {probe['from_unit']} -> {probe['to_unit']}, "
                f"returned {uid} -> {r['dest']}")
            assert probe["search_key"] == key, (
                f"[{label}] {uid} returned a proposal for {key} on an edge "
                f"probed for a different SearchKey")

            # PROVENANCE. `source_edge_id` names the edge the ORIGINATING node
            # was probed on, and it is NOT rewritten at each hop: a proposal
            # relayed three times still carries the edge its supplier answered
            # on. So the emitter is generally neither the source node nor the
            # unit that opened the source edge, and the only honest check is
            # the path property itself -- the emitter must actually stand on
            # the adopted return path from that source.
            p = r["payload"]
            assert p.identity_intact(), (
                f"[{label}] {uid} emitted a proposal whose derived identity "
                f"does not match its own content")
            assert p.proposal_id, f"[{label}] {uid} emitted an unidentified proposal"
            src = probes.get(p.source_edge_id)
            assert src is not None, (
                f"[{label}] {uid} emitted a proposal whose source edge "
                f"{p.source_edge_id} was never probed")
            assert src["search_key"] == key, (
                f"[{label}] the proposal's source edge belongs to another search")
            assert src["to_unit"] == p.source_node, (
                f"[{label}] the proposal claims source node {p.source_node} on "
                f"an edge probed toward {src['to_unit']}")
            chain = _adopted_chain(nodes, key, p.source_node)
            assert uid in chain, (
                f"[{label}] {uid} relayed a proposal from {p.source_node} "
                f"without standing on its adopted return path {chain}; the "
                f"source edge {p.source_edge_id} was opened by "
                f"{src['from_unit']}")
            assert src["from_unit"] in chain, (
                f"[{label}] the source edge {p.source_edge_id} was opened by "
                f"{src['from_unit']}, which is not on the adopted return path "
                f"from {p.source_node}: {chain}")

            if r["dest"] != key.origin_unit:
                relays += 1
            if len(r["node_incoming"]) > 1:
                # a competing arrival had ALREADY landed when this node
                # proposed -- the capture window `reverse[need_id]` left open
                pre_emission_contested += 1

        edges = {r["edge"] for r in recs}
        assert edges == {adopted}, (
            f"[{label}] {uid} returned proposals for one SearchKey through "
            f"{sorted(edges)}, not solely through its immutable adopted parent "
            f"edge {adopted}")

    # -- parent controls never travel upward --------------------------------
    strictly_parent = tuple(k for k in v5.PARENT_CONTROL_KINDS
                            if k not in v5.CHILD_OUTCOME_KINDS)
    assert strictly_parent, (
        "every parent control is also a child outcome, so 'controls never "
        "travel upward' has nothing left to forbid")
    inspected = 0
    for (uid, key), recs in by_node.items():
        edge, parent = recs[0]["edge"], recs[0]["dest"]
        rec = terminals.get(edge)
        if rec is None:
            continue        # this edge carries no accepted outcome in this run
        assert rec["from_unit"] == uid and rec["to_unit"] == parent, (
            f"[{label}] the outcome recorded on {edge} runs "
            f"{rec['from_unit']} -> {rec['to_unit']}, not {uid} -> {parent}")
        offending = [k for k in (_kind(x) for x in rec["outcomes"])
                     if k in strictly_parent]
        assert not offending, (
            f"[{label}] {uid} sent {offending} upward on its adopted parent "
            f"edge; {list(strictly_parent)} are parent controls and travel "
            f"only downward")
        for c in o.search_edge_lifecycle.get(edge, {}).get("controls", []):
            assert _kind(c) in v5.PARENT_CONTROL_KINDS, (
                f"[{label}] a non-control was recorded on the control channel "
                f"of {edge}")
            assert getattr(c, "from_unit", None) == parent, (
                f"[{label}] a control on {edge} came from "
                f"{getattr(c, 'from_unit', None)}, not from the parent {parent}")
        inspected += 1
    assert inspected, (
        f"[{label}] no adopted parent edge carried a recorded outcome, so the "
        f"upward channel was never actually inspected")

    # -- a competing arrival must not capture the return route --------------
    contested = []
    for (uid, key), recs in by_node.items():
        node = nodes[(uid, key)]
        incoming = list(node.get("incoming_edges", []))
        assert incoming, f"[{label}] {uid} records no incoming edges"
        for e in incoming:
            if e == node["adopted_parent_edge_initial"]:
                continue
            outs = terminals.get(e, {}).get("outcomes", [])
            if any(_kind(x) in ("SearchCoalesced", "SearchCycleClosed")
                   for x in outs):
                contested.append((uid, key, e))
    for uid, key, e in contested:
        node = nodes[(uid, key)]
        assert node["adopted_parent_edge"] == node["adopted_parent_edge_initial"], (
            f"[{label}] {uid} replaced its adopted parent after a competing "
            f"arrival on {e}")
        assert not node.get("children_from", {}).get(e), (
            f"[{label}] the competing arrival on {e} created descendants at {uid}")
        assert len(terminals[e]["outcomes"]) == 1, (
            f"[{label}] the competing arrival on {e} received "
            f"{len(terminals[e]['outcomes'])} terminal outcomes, expected 1")

    assert C["OFFER_RETURN_ROUTE_MISMATCHES"] == 0, (
        f"[{label}] a proposal travelled home through an edge that was not the "
        f"adopted parent; `reverse` keyed by need_id alone allows exactly this")

    return {"label": label, "proposals": len(tr.emitted),
            "proposing_nodes": len(by_node), "relay_proposals": relays,
            "contested_returns": len(contested),
            "pre_emission_contested": pre_emission_contested,
            "upward_edges_inspected": inspected,
            "origin_nodes": len(origins)}


# ---------------------------------------------------------------------------
# A. Diamond convergence -> one canonical node, one child set
# ---------------------------------------------------------------------------

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

    # 2D: A DUPLICATE ARRIVAL IS AN INGRESS EVENT, so it travels the
    # authenticated path rather than declaring a harness bypass. Coalescing is
    # exactly the decision an unauthenticated caller would most like to reach --
    # it returns a refund -- so this test must prove the accounting holds for an
    # arrival that proved its route, not for one that skipped the gate. A real
    # neighbour opens the edge and commits the allocation before delivering it.
    opener_id = next((n for n in sorted(unit.neighbours) if n not in (ENV, SINK)),
                     None)
    assert opener_id is not None, (
        "the receiver has no ordinary neighbour able to open the duplicate "
        "edge, so the authenticated ingress path cannot be exercised here")
    opener = o.units[opener_id]
    opener._record_probe("e/rich", opener.unit_id, unit.unit_id, key,
                         allocation=999.0)

    outcome = unit.deliver_search(key, edge_id="e/rich", allocation=999.0,
                                  lineage=(j.unit_id,), sender=opener.unit_id)

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
                               lineage=(j.unit_id,), sender=opener.unit_id)
    assert C["COALESCED_DUPLICATE_ARRIVALS"] == coalesced_before + 1, (
        "replaying the duplicate edge produced a second coalesced response")
    assert C["TERMINAL_ECHOS_SENT"] == echoes_before + 1, (
        "replaying the duplicate edge produced a second terminal outcome")
    assert getattr(again, "refund", 0.0) == 0.0, (
        "a replayed duplicate refunded a second time")


# ---------------------------------------------------------------------------
# E. Forced mixed-child order: A exhausts, then B answers
# ---------------------------------------------------------------------------
def test_E_a_child_proposal_does_not_terminate_the_parent_or_cancel_siblings():
    """PROTOCOL_SEMANTICS_CORRECTION.

    The earlier version of this test asserted that a child SearchOffer made the
    parent immediately ANSWERED. It was activated on that basis, and it
    contradicted the live-path requirement that a rejected settlement leaves the
    search open with other candidates intact. Both cannot be true.

    A candidate is a PROPOSAL. The root may reject it for duplicate supplier,
    stale derivation, cooldown, a prohibited motif, changed slot state, policy
    mismatch, or a race with another accepted candidate. So a proposal must not
    terminate the parent edge, must not mark the node ANSWERED, and must not
    cancel siblings. Only an accepted settlement closes the wave.

    No evaluation run relied on the prior interpretation: R8 has never been run
    and the activated version produced no recorded evidence.
    """
    o, j, slot, victim, seed = _damaged(4)
    reset()
    ctx = _ctx()
    key = _key_for(j, slot, ctx, "probe:E")
    unit = next(u for u in o.units.values()
                if u.unit_id not in (ENV, SINK) and u.unit_id != j.unit_id)
    node = unit.open_canonical_search(key, parent_edge="e/adopted", allocation=9.0)
    kids = list(node["children_opened"])
    assert len(kids) >= 2, (
        f"the canonical node opened {len(kids)} children; this test needs at "
        f"least two to force a mixed outcome")
    a, b = kids[0], kids[1]
    terminals_before = len(o.search_edge_terminals)

    unit.deliver_terminal(key, a, "SearchExhausted", refund=1.0,
                          sender=v5.HARNESS_DELIVERY)

    assert node["status"] == "OPEN", (
        f"parent went {node['status']} after ONE child exhausted while "
        f"{len(node['children_outstanding'])} remain outstanding")
    assert b in node["children_outstanding"], "the live child was dropped"

    # A PROPOSAL, not a terminal outcome.
    unit.deliver_proposal(key, b, _payload(o, key, ctx, "probe.supplier",
                                           "p/E", b), v5.HARNESS_DELIVERY)

    assert node["status"] in ("OPEN", "PROPOSAL_PENDING"), (
        f"a candidate proposal put the node in {node['status']}; a proposal is "
        f"not a terminal success")
    assert node["children_outstanding"] or node["children_completed"], (
        "sibling accounting was discarded on a proposal")
    assert not node.get("wave_cancelled"), (
        "the wave was cancelled by a proposal rather than by an accepted "
        "settlement")
    assert b not in o.search_edge_terminals, (
        "the proposal was recorded as the edge's terminal outcome; proposals "
        "belong in search_edge_events")
    events = o.search_edge_events.get(b, [])
    assert any(_kind(e) == "SearchProposal" for e in events), (
        "the proposal was not recorded as a nonterminal edge event")
    assert len(o.search_edge_terminals) == terminals_before + 1, (
        "a proposal added a terminal outcome; only child A's exhaustion should "
        "have produced one")
    assert C["PREMATURE_PROPOSAL_CANCELLATIONS"] == 0


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

def test_H_each_answered_node_returns_its_proposal_through_its_adopted_edge():
    """PER NODE, not globally per SearchKey.

    An earlier draft required exactly ONE offer edge per SearchKey across the
    whole organ. That is wrong for an echo protocol: evidence travelling home
    from supplier -> relay C -> relay B -> relay A -> origin legitimately leaves
    one edge PER canonical node along the adopted chain, so the same SearchKey
    appears on several return edges. The real invariant is per node.

    IT ALSO LOOKED IN THE WRONG PLACE FOR THE WRONG MESSAGE. It searched
    `search_edge_terminals` for records whose outcomes contained
    `SearchCommitted`, and called those "SearchOffer terminals". Two independent
    reasons that could never hold:

      1. `SearchCommitted` is a PARENT CONTROL. The active 2D rule forbids a
         child from emitting one upward on its adopted parent edge, so the
         filter demanded exactly the message the protocol prohibits;
      2. since the lifecycle/projection separation, `search_edge_terminals`
         holds ACCEPTED OUTCOMES only, and a proposal is a NONTERMINAL. No
         proposal can ever appear there, whatever its direction.

    The route a node chose is recorded in one place only -- the message it put
    in its own outbox -- so that is where this reads it. There is no
    `SearchOffer` type in the protocol; the canonical name is `SearchProposal`
    and no alias is added here to keep the old wording alive.

    THREE FIXTURES, because no single run contains all three required shapes
    and a missing shape makes the matching clause a claim about nothing:

      `(4, 1.0)` the pre-registered fixture. A competing arrival reaches a node
                 that answered -- but AFTER it proposed.
      `(5, 0.8)` a genuine RELAY hop: a proposing node whose adopted parent is
                 not the search origin. Without one, a candidate that handed its
                 evidence straight to the origin would be indistinguishable from
                 correct routing.
      `(3, 0.6)` a node that proposes while it ALREADY holds a second incoming
                 edge. This is the `reverse[need_id]` capture window itself, and
                 the negative control showed the first two fixtures never enter
                 it: in both, every proposing node still had exactly one arrival
                 at the moment it emitted, so "the latest arrival captured the
                 return route" was not an attack there but a no-op.
    """
    o, j, slot, victim, seed = _damaged(4, density=1.0)
    tr = _run_traced(o)
    facts = _assert_offers_return_through_adopted_edges(
        o, tr, label=f"n_auth=4 density=1.0 seed={seed}")
    assert facts["contested_returns"] >= 1, (
        "no proposing node received a later non-adopted duplicate or cross-edge "
        "arrival, so no attempt to overwrite a return route occurred at a node "
        "that actually returned a proposal")

    o2, j2, slot2, victim2, seed2 = _damaged(5, density=0.8)
    tr2 = _run_traced(o2)
    relayed = _assert_offers_return_through_adopted_edges(
        o2, tr2, label=f"n_auth=5 density=0.8 seed={seed2}")
    assert relayed["relay_proposals"] >= 1, (
        "every proposing node was a direct child of the search origin, so a "
        "candidate that jumped straight to the origin would have been "
        "indistinguishable from correct routing in this run")

    o3, j3, slot3, victim3, seed3 = _damaged(3, density=0.6)
    tr3 = _run_traced(o3)
    captured = _assert_offers_return_through_adopted_edges(
        o3, tr3, label=f"n_auth=3 density=0.6 seed={seed3}")
    assert captured["pre_emission_contested"] >= 1, (
        "no node proposed while it already held a second incoming edge, so the "
        "route-capture window this invariant exists to close was never entered "
        "and 'the latest arrival did not capture the return route' was a no-op")

    # EXACT REPLAY IS NOT A SECOND PROPOSAL. Replaying an already-answered
    # adopted edge must not re-emit evidence the parent already holds, and must
    # not move the route.
    for organ, trace in ((o, tr), (o2, tr2), (o3, tr3)):
        targets = {(r["unit"], r["key"], r["edge"]) for r in trace.emitted}
        assert targets, "nothing to replay"
        answered = [(u, k, e) for u, k, e in targets
                    if (organ.search_edge_lifecycle.get(e) or {})
                    .get("accepted_outcome") is not None]
        assert answered, (
            "no adopted parent edge that carried a proposal reached an accepted "
            "outcome, so replay idempotence was never actually exercised")
        # SORTED BY A STABLE STRING, NOT BY THE TUPLE. `SearchKey` defines no
        # ordering, so sorting `(uid, key, edge)` raises TypeError the moment
        # two entries share a `uid` and Python falls through to comparing the
        # keys. Latent until a runtime change made two edges from one unit reach
        # an accepted outcome in the same run.
        with _proposal_trace() as replay:
            for uid, key, edge in sorted(answered, key=lambda r: (r[0], r[2])):
                organ.units[uid].replay_search_edge(key, edge)
        assert not replay.emitted, (
            f"exact replay of an answered adopted edge re-emitted "
            f"{len(replay.emitted)} proposal(s): "
            f"{[(r['unit'], r['dest'], r['edge']) for r in replay.emitted]}")


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

@pytest.mark.parametrize("density", [0.7, 0.8, 0.9])
def test_J_amplification_scales_with_units_not_paths(density):
    o, j, slot, victim, seed = _damaged(4, density=density)
    reset()
    before = o.messages
    o.run_item(PAYLOAD_B)
    amp = round((o.messages - before) / max(1, len(o.units)), 2)
    # Without this the test passes on 0 == 0 while no canonical node exists at
    # all, which is exactly how it XPASSed once the counters were merely defined.
    assert C["UNIQUE_CANONICAL_SEARCH_NODES"] > 0, (
        f"no canonical search node was created at density {density}, so this "
        f"test would pass vacuously")
    assert C["DIRECTED_SEARCH_EDGES_PROBED"] > 0, "no search edge was probed"
    assert amp <= 12, (
        f"repair amplification {amp} exceeds the ceiling of 12 at density "
        f"{density} (seed {seed})")
    assert C["DUPLICATE_SUBTREES_OPENED"] == 0
    assert C["CANONICAL_SEARCH_EXPANSIONS"] == C["UNIQUE_CANONICAL_SEARCH_NODES"]
    _per_key_edge_uniqueness(o)


# ---------------------------------------------------------------------------
# Arrival order, isolated: ONE organ, only delivery order varies
# ---------------------------------------------------------------------------

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
        # Guard against a vacuous pass: the protocol must actually have run.
        assert C["UNIQUE_CANONICAL_SEARCH_NODES"] > 0, (
            f"no canonical search node under rotation {rotation}; this test "
            f"would pass without the protocol running at all")

    assert len(set(outcomes)) == 1, (
        f"whether a distinct replacement was found depended on arrival order "
        f"alone: {outcomes}")
    assert all(a <= 12 for a in amps), f"amplification unbounded under reorder: {amps}"
    # The adopted parents MAY differ -- that is expected under first-arrival
    # adoption, and is recorded rather than asserted away.
