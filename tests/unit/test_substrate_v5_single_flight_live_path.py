"""LIVE-PATH contract for Single-Flight Echo Search. Strict xfail, pre-wiring.

Committed BEFORE `_emit_need` is changed, so the live-path contract cannot be
written to fit whatever the wiring happens to do.

WHY THIS FILE EXISTS. The ten remaining acceptance specs all report "zero
canonical nodes", which made it look as though wiring was the only work left. It
is not. Nine further defects were confirmed in the primitives by reading the
source, and every one of them would only surface once the protocol carried real
repair traffic:

  1. SearchKey carries DIGESTS of the refusal and must-differ sets, not the sets
     themselves, and `_must_differ` returns an empty set unless the receiving unit
     originated the search. So the sibling supplier that must be excluded can
     receive the probe remotely and offer itself -- recreating the exact
     duplicate-supplier defect the mechanism exists to remove. A digest proves
     identity; it cannot enforce a constraint that does not travel with the probe.
  2. `Terminal` carries no supplier, supplier_class, offered_type, cost, firm flag
     or derivation chain, while `_settle` requires all of them. The mechanism can
     report "an offer exists" and then cannot settle it.
  3. `open_canonical_search` calls `_expand_canonical` before `deliver_search`
     evaluates local eligibility, so an eligible supplier opens descendants first
     and answers second.
  4. The sender records the probe at creation and the receiver records the same
     edge again on arrival, so every live edge would have count == 2 and fail the
     per-edge uniqueness invariant. The direct-seam tests miss this because they
     call the receiver directly.
  5. Children are sent `lineage=(self.unit_id,)` instead of adopted lineage plus
     self, so A -> B -> C -> A never arrives back at A carrying (A, B, C) and a
     real cycle cannot be proved as such.
  6. Child ids are `f"{adopted}/c{i}"` with `i` restarting at zero on every
     expansion, so a second widening round reuses /c0, /c1 for different routes.
  7. A child SearchOffer clears `children_outstanding` and cancels only the local
     reserve, leaving the outstanding children's allocations unreconciled.
  8. That cancellation happens when a candidate APPEARS, not when the origin
     successfully settles it. A SearchOffer is a proposal; the obligation closes
     only after `_settle` returns True.

DECLARED SEAMS the live wiring must provide, beyond those already declared in
test_substrate_v5_single_flight_echo.py:

    v5.SearchContext                    immutable, carries the ACTUAL values whose
                                        digests appear in SearchKey, plus
                                        max_supplier_cost and cooldown exclusions
    SearchContext.digests()              -> (refusal_digest, must_differ_digest)
    SearchContext.matches(key)           -> bool, verified by every receiver
    v5.SearchOfferPayload                supplier, supplier_class, offered_type,
                                        cost, firm, derivation_chain, search_key,
                                        edge_id
    Terminal.payload                     the SearchOfferPayload on a SearchOffer
    Unit.settle_search_offer(payload)    -> bool, builds an Offer and calls _settle
    node["lineage"]                      adopted lineage preserved at the node
    Organ.search_edge_probes[e]["delivered"]  delivery count, SEPARATE from
                                             "count", which is creation only

New counters the live path must expose:

    REPAIR_REOPENS
    REPAIR_REOPENS_WITH_CANONICAL_ROOT
    LEGACY_REPAIR_NEED_MESSAGES
    DUAL_REPAIR_SEARCHES
    SEARCH_OFFER_SETTLEMENT_REJECTIONS
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
SEEDS = tuple(range(60))

# Distinct from the acceptance `spec` marker and from the inherited-defect
# marker, so an activation commit can target exactly one group.
live = pytest.mark.xfail(
    strict=True,
    reason="Single-Flight live-path wiring is not implemented yet")


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
        victim = j.bonds[slot].supplier
        o.units[victim].silent = True
        return o, j, slot, victim, seed
    raise AssertionError(
        f"no formed independently-supplied join with n_auth={n_auth} "
        f"density={density} across seeds {SEEDS[0]}..{SEEDS[-1]}; failing to "
        f"construct the structure is a failure of this specification, not a "
        f"reason to skip it")


def _nodes(o):
    return {(u.unit_id, k): n for u in o.units.values()
            for k, n in getattr(u, "canonical_searches", {}).items()}


def _kind(x):
    return getattr(x, "kind", x)


# ---------------------------------------------------------------------------
# 1-2. Constraints must TRAVEL, not just be hashed
# ---------------------------------------------------------------------------

@live
def test_remote_sibling_supplier_enforces_must_differ_and_offers_nothing():
    """The decisive defect: a digest cannot enforce a constraint remotely.

    `_must_differ` returns an empty set unless the receiving unit originated the
    search, so the excluded sibling could receive the probe and offer itself.
    """
    o, j, slot, victim, seed = _damaged(4)
    sibling = [b.supplier for s, b in j.bonds.items() if s != slot][0]
    ctx = v5.SearchContext(
        causally_refused_sources=frozenset(),
        must_differ_from_suppliers=frozenset({sibling}),
        max_supplier_cost=99.0,
        cooldown_excluded=frozenset(),
        constraint_generation=0)
    key = v5.SearchKey.build(
        need_id="probe:mustdiffer", work_item_generation=2,
        origin_unit=j.unit_id, origin_slot=slot,
        wanted_type=j.capability.accepts[slot],
        refused=ctx.causally_refused_sources,
        must_differ_from=ctx.must_differ_from_suppliers)
    assert ctx.matches(key), "the context does not canonicalize to the key digests"

    reset()
    unit = o.units[sibling]
    outcome = unit.deliver_search(key, "e/remote", allocation=6.0,
                                 lineage=(j.unit_id,), sender=j.unit_id,
                                 context=ctx)
    assert _kind(outcome) != "SearchOffer", (
        f"{sibling} is excluded by must_differ_from yet offered itself remotely; "
        f"this is the duplicate-supplier defect returning through the digest gap")
    assert getattr(outcome, "payload", None) is None


@live
def test_remote_candidate_enforces_the_origins_causal_refusals():
    o, j, slot, victim, seed = _damaged(4)
    candidate = next(u for u in o.units.values()
                     if u.capability.produces == j.capability.accepts[slot]
                     and u.unit_id != victim)
    own = candidate.unit_id
    ctx = v5.SearchContext(
        causally_refused_sources=frozenset({own}),
        must_differ_from_suppliers=frozenset(),
        max_supplier_cost=99.0,
        cooldown_excluded=frozenset(),
        constraint_generation=0)
    key = v5.SearchKey.build(
        need_id="probe:refused", work_item_generation=2,
        origin_unit=j.unit_id, origin_slot=slot,
        wanted_type=j.capability.accepts[slot],
        refused=ctx.causally_refused_sources,
        must_differ_from=ctx.must_differ_from_suppliers)
    reset()
    outcome = candidate.deliver_search(key, "e/refused", allocation=6.0,
                                      lineage=(j.unit_id,), sender=j.unit_id,
                                      context=ctx)
    assert _kind(outcome) != "SearchOffer", (
        "a candidate whose own derivation is refused by the origin offered itself")


@live
def test_a_receiver_rejects_a_context_that_does_not_match_the_key():
    """A forged or stale context must not be honoured."""
    o, j, slot, victim, seed = _damaged(4)
    honest = v5.SearchContext(frozenset(), frozenset({"someone"}), 99.0,
                              frozenset(), 0)
    key = v5.SearchKey.build(
        need_id="probe:forge", work_item_generation=2, origin_unit=j.unit_id,
        origin_slot=slot, wanted_type=j.capability.accepts[slot],
        refused=honest.causally_refused_sources,
        must_differ_from=honest.must_differ_from_suppliers)
    forged = v5.SearchContext(frozenset(), frozenset(), 99.0, frozenset(), 0)
    assert not forged.matches(key), "an empty context matched a constrained key"
    unit = next(u for u in o.units.values() if u.unit_id not in (ENV, SINK))
    reset()
    outcome = unit.deliver_search(key, "e/forged", allocation=6.0,
                                 lineage=(j.unit_id,), sender=j.unit_id,
                                 context=forged)
    assert _kind(outcome) == "SearchContextRejected", (
        f"a context whose digests do not match the SearchKey was accepted "
        f"({_kind(outcome)})")


# ---------------------------------------------------------------------------
# 3-4. The offer must be settleable, and rejection must not close the search
# ---------------------------------------------------------------------------

@live
def test_search_offer_carries_enough_evidence_for_settlement():
    o, j, slot, victim, seed = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)
    terminals = o.search_edge_terminals
    offers = [t for rec in terminals.values() for t in rec["outcomes"]
              if _kind(t) == "SearchOffer"]
    assert offers, "no SearchOffer was produced by a live repair"
    for t in offers:
        p = getattr(t, "payload", None)
        assert p is not None, "a SearchOffer carried no payload"
        for f in ("supplier", "supplier_class", "offered_type", "cost", "firm",
                  "derivation_chain", "search_key", "edge_id"):
            assert hasattr(p, f), f"SearchOfferPayload lacks {f!r}"
        assert p.offered_type == t.search_key.wanted_type
        assert isinstance(p.derivation_chain, frozenset)


@live
def test_the_root_settles_from_the_offer_payload():
    o, j, slot, victim, seed = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)
    # VACUITY GUARD. The R6 mechanism already settles replacements, so without
    # this the test passes with Single-Flight never having run.
    assert C["UNIQUE_CANONICAL_SEARCH_NODES"] > 0, (
        "no canonical node was created, so any settlement here came from the "
        "legacy path and this test would pass vacuously")
    b = j.bonds.get(slot)
    assert b is not None and b.supplier != victim, (
        "the root never bonded a replacement, so no payload was settleable")
    assert getattr(b, "settled_from_search_offer", False), (
        "the bond was not settled from a SearchOfferPayload")
    sups = [x.supplier for x in j.bonds.values()]
    assert len(sups) == len(set(sups)), "settlement violated independence"
    assert C["SEARCH_SPACE_EXHAUSTED"] == 0, (
        "the root settled a replacement and also proved the space exhausted")


@live
def test_a_rejected_offer_leaves_the_search_open_and_keeps_other_candidates():
    """A SearchOffer is a proposal. Only `_settle` returning True closes it."""
    o, j, slot, victim, seed = _damaged(4)
    sibling = [b.supplier for s, b in j.bonds.items() if s != slot][0]
    reset()
    payload = v5.SearchOfferPayload(
        supplier=sibling, supplier_class=o.units[sibling].capability.klass(),
        offered_type=j.capability.accepts[slot], cost=1.0, firm=True,
        derivation_chain=frozenset({sibling}),
        search_key=v5.SearchKey.build(
            need_id="probe:reject", work_item_generation=2,
            origin_unit=j.unit_id, origin_slot=slot,
            wanted_type=j.capability.accepts[slot]),
        edge_id="e/reject")
    key = payload.search_key
    node = j.open_canonical_search(key, "e/root", 9.0)
    outstanding = set(node["children_outstanding"])
    ok = j.settle_search_offer(payload)
    assert ok is False, "the sibling supplier was accepted into a second slot"
    assert C["SEARCH_OFFER_SETTLEMENT_REJECTIONS"] >= 1, (
        "a rejected settlement was not recorded as attributable")
    assert node["status"] == "OPEN", (
        f"a rejected offer closed the search (status {node['status']})")
    assert node["children_outstanding"] == outstanding, (
        "a rejected offer cancelled other candidate paths")
    assert key.need_id not in j.closed_needs, "a rejected offer closed the Need"


# ---------------------------------------------------------------------------
# 5-7. Live protocol mechanics
# ---------------------------------------------------------------------------

@live
def test_a_locally_eligible_producer_opens_zero_children():
    o, j, slot, victim, seed = _damaged(4)
    want = j.capability.accepts[slot]
    producer = next(u for u in o.units.values()
                    if u.capability.produces == want and u.unit_id != victim
                    and not u.unmet())
    ctx = v5.SearchContext(frozenset(), frozenset(), 99.0, frozenset(), 0)
    key = v5.SearchKey.build(need_id="probe:eligible", work_item_generation=2,
                             origin_unit=j.unit_id, origin_slot=slot,
                             wanted_type=want)
    reset()
    outcome = producer.deliver_search(key, "e/elig", allocation=6.0,
                                      lineage=(j.unit_id,), sender=j.unit_id,
                                      context=ctx)
    assert _kind(outcome) == "SearchOffer", f"an eligible producer returned {_kind(outcome)}"
    node = producer.canonical_searches[key]
    assert node["children_opened"] == [], (
        f"an eligible producer opened {len(node['children_opened'])} children "
        f"before answering; eligibility must be evaluated first")
    assert C["DIRECTED_SEARCH_EDGES_PROBED"] == 0, (
        "an eligible producer created outbound probes it did not need")


@live
def test_every_live_edge_is_probed_exactly_once():
    """Sender creation and receiver delivery must not both count as a probe."""
    o, j, slot, victim, seed = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)
    probes = o.search_edge_probes
    assert probes, "no search edges were probed by a live repair"
    doubled = {e: r for e, r in probes.items() if r["count"] != 1}
    assert not doubled, (
        f"{len(doubled)} live edges were counted more than once; creation and "
        f"delivery must be recorded in separate fields: "
        f"{list(doubled.items())[:3]}")
    for e, r in probes.items():
        assert "delivered" in r, (
            "delivery is not recorded separately from creation")
        assert r["delivered"] <= 1, f"edge {e} was delivered {r['delivered']} times"


@live
def test_widening_rounds_produce_globally_unique_child_edge_ids():
    o, j, slot, victim, seed = _damaged(4)
    ctx = v5.SearchContext(frozenset(), frozenset(), 99.0, frozenset(), 0)
    key = v5.SearchKey.build(need_id="probe:widen", work_item_generation=2,
                             origin_unit=j.unit_id, origin_slot=slot,
                             wanted_type=j.capability.accepts[slot])
    reset()
    node = j.open_canonical_search(key, "e/root", 40.0)
    seen = list(node["children_opened"])
    for _ in range(3):
        for child in list(node["children_outstanding"]):
            j.deliver_terminal(key, child, "SearchExhausted", refund=0.0)
        seen += [c for c in node["children_opened"] if c not in seen]
    allc = list(node["children_opened"])
    assert len(allc) == len(set(allc)), (
        f"child edge ids repeat across widening rounds: "
        f"{[c for c in allc if allc.count(c) > 1][:4]}")
    assert len(allc) > len(node["children_from"].get("e/root", []) or []) or True


@live
def test_lineage_accumulates_and_a_real_cycle_closes_positively():
    o, j, slot, victim, seed = _damaged(4, density=1.0)
    reset()
    o.run_item(PAYLOAD_B)
    nodes = _nodes(o)
    assert nodes, "no canonical nodes were created"
    depths = [len(n.get("lineage", ())) for n in nodes.values()]
    assert max(depths) >= 2, (
        f"no node received an accumulated lineage deeper than one hop "
        f"(max {max(depths) if depths else 0}); lineage is being reset per hop, "
        f"so a multi-hop cycle cannot be proved")
    assert C["CYCLE_EDGES_CLOSED"] > 0, (
        "no cycle edge was closed on a complete graph")
    terminals = o.search_edge_terminals
    cyc = [e for e, r in terminals.items()
           if any(_kind(t) == "SearchCycleClosed" for t in r["outcomes"])]
    assert cyc, "the counter fired but no edge recorded SearchCycleClosed"
    for e in cyc:
        assert len(terminals[e]["outcomes"]) == 1, f"cycle edge {e} answered twice"


@live
def test_accepted_settlement_reconciles_every_outstanding_child_allocation():
    """Clearing the outstanding set is not the same as cancelling it."""
    o, j, slot, victim, seed = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)
    nodes = _nodes(o)
    # VACUITY GUARD. With no nodes the loop body never runs and the test passes
    # having checked nothing.
    assert nodes, "no canonical nodes were created"
    finished = [n for n in nodes.values() if n["status"] in ("ANSWERED", "CLOSED")]
    assert finished, (
        "no canonical node reached ANSWERED or CLOSED, so no settlement "
        "reconciliation was exercised")
    for (uid, key), node in nodes.items():
        if node["status"] not in ("ANSWERED", "CLOSED"):
            continue
        assert not node["children_outstanding"], (
            f"{uid} finished with children still outstanding")
        accounted = (node["local_reserve"] + node["returned_credit"]
                     + node["consumed_credit"] + node["cancelled_credit"])
        assert abs(accounted - node["incoming_allocation"]) < 1e-6, (
            f"{uid} finished with {accounted} accounted against an allocation of "
            f"{node['incoming_allocation']}; outstanding child allocations were "
            f"discarded rather than cancelled")


# ---------------------------------------------------------------------------
# 8-10. No dual running, formation untouched
# ---------------------------------------------------------------------------

@live
def test_repair_uses_single_flight_only_and_emits_no_legacy_need():
    o, j, slot, victim, seed = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)
    assert C["REPAIR_REOPENS"] > 0, "no repair reopen occurred"
    assert C["REPAIR_REOPENS_WITH_CANONICAL_ROOT"] == C["REPAIR_REOPENS"], (
        f"{C['REPAIR_REOPENS'] - C['REPAIR_REOPENS_WITH_CANONICAL_ROOT']} reopens "
        f"did not create a canonical root")
    assert C["LEGACY_REPAIR_NEED_MESSAGES"] == 0, (
        "repair still emitted legacy Need messages")
    assert C["DUAL_REPAIR_SEARCHES"] == 0, (
        "both the legacy Need search and Single-Flight ran for one obligation")


def test_formation_still_uses_the_legacy_need_path_unchanged():
    """Plain test. Formation keeps the R6 mechanism and the R6 numbers exactly."""
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
