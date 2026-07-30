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

    v5.SearchContext                     ONE schema, carrying every
                                         decision-relevant field:
                                           causally_refused_sources
                                           must_differ_from_suppliers
                                           maximum_supplier_cost
                                           cooldown_excluded_suppliers
                                           constraint_generation
                                           policy_snapshot
    SearchContext.context_digest()       -> one canonical digest over ALL of them
    SearchContext.matches(key)           -> verifies the COMPLETE context
    v5.SearchKey.build(..., context=ctx) -> the only key constructor
    v5.SearchOfferPayload                proposal_id, search_key, context_digest,
                                         supplier, supplier_class, offered_type,
                                         cost, firm, derivation_chain,
                                         source_node, source_edge_id
    Unit.deliver_proposal(key, edge, payload)   nonterminal
    Unit.settle_search_offer(payload)    -> bool, builds an Offer, calls _settle
    node["proposal_routes"]              {proposal_id: child_edge_id}
    node["lineage"]                      adopted lineage preserved at the node
    Organ.search_edge_events[e]          nonterminal proposals and control events
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


def _ctx(**kw):
    """THE canonical SearchContext schema. There is no second one.

    Two schemas existed in this file -- `max_supplier_cost` / `cooldown_excluded`
    in the first tests and `maximum_supplier_cost` /
    `cooldown_excluded_suppliers` in the later ones -- and some keys were built
    from only `refused` and `must_differ_from`. Implementing aliases to satisfy
    both would have made the contradiction permanent, so all tests use this one.
    """
    base = dict(causally_refused_sources=frozenset(),
                must_differ_from_suppliers=frozenset(),
                maximum_supplier_cost=99.0,
                cooldown_excluded_suppliers=frozenset(),
                constraint_generation=0,
                policy_snapshot=())
    base.update(kw)
    return v5.SearchContext(**base)


def _key_for(j, slot, ctx, need_id):
    """Every key is built from the COMPLETE context. No partial constructor."""
    return v5.SearchKey.build(
        need_id=need_id, work_item_generation=2, origin_unit=j.unit_id,
        origin_slot=slot, wanted_type=j.capability.accepts[slot], context=ctx)


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
    ctx = _ctx(must_differ_from_suppliers=frozenset({sibling}))
    key = _key_for(j, slot, ctx, "probe:mustdiffer")
    assert ctx.matches(key), "the context does not canonicalize to the key digests"

    reset()
    unit = o.units[sibling]
    # PAIRED POSITIVE CONTROL, same producer, neutral context.
    control_ctx = _ctx()
    control_key = _key_for(j, slot, control_ctx, "probe:mustdiffer:control")
    control = unit.deliver_search(control_key, "e/remote/control", allocation=6.0,
                                  lineage=(j.unit_id,), sender=j.unit_id,
                                  context=control_ctx)
    assert _kind(control) == "SearchProposal", (
        f"the control candidate {sibling} did not propose under a neutral "
        f"context ({_kind(control)}), so refusing it below proves nothing about "
        f"must_differ_from enforcement")
    reset()
    outcome = unit.deliver_search(key, "e/remote", allocation=6.0,
                                 lineage=(j.unit_id,), sender=j.unit_id,
                                 context=ctx)
    assert _kind(outcome) != "SearchProposal", (
        f"{sibling} is excluded by must_differ_from yet offered itself remotely; "
        f"this is the duplicate-supplier defect returning through the digest gap")
    assert getattr(outcome, "reason", None) == "candidate_must_differ", (
        f"exclusion reason was {getattr(outcome, 'reason', None)!r}, expected "
        f"'candidate_must_differ'")
    assert getattr(outcome, "payload", None) is None


@live
def test_remote_candidate_enforces_the_origins_causal_refusals():
    o, j, slot, victim, seed = _damaged(4)
    candidate = next(u for u in o.units.values()
                     if u.capability.produces == j.capability.accepts[slot]
                     and u.unit_id != victim)
    own = candidate.unit_id
    ctx = _ctx(causally_refused_sources=frozenset({own}))
    key = _key_for(j, slot, ctx, "probe:refused")
    reset()
    outcome = candidate.deliver_search(key, "e/refused", allocation=6.0,
                                      lineage=(j.unit_id,), sender=j.unit_id,
                                      context=ctx)
    assert _kind(outcome) != "SearchProposal", (
        "a candidate whose own derivation is refused by the origin proposed itself")


@live
def test_a_receiver_rejects_a_context_that_does_not_match_the_key():
    """A forged or stale context must not be honoured."""
    o, j, slot, victim, seed = _damaged(4)
    honest = _ctx(must_differ_from_suppliers=frozenset({"someone"}))
    key = _key_for(j, slot, honest, "probe:forge")
    forged = _ctx()
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
    events = o.search_edge_events
    offers = [e for evs in events.values() for e in evs
              if _kind(e) == "SearchProposal"]
    assert offers, "no SearchProposal was produced by a live repair"
    for edge, rec in o.search_edge_terminals.items():
        for t in rec["outcomes"]:
            assert _kind(t) != "SearchProposal", (
                f"edge {edge} stored a proposal as its terminal outcome")
    for t in offers:
        p = getattr(t, "payload", None)
        assert p is not None, "a SearchProposal carried no payload"
        for f in ("proposal_id", "search_key", "context_digest", "supplier",
                  "supplier_class", "offered_type", "cost", "firm",
                  "derivation_chain", "source_node", "source_edge_id"):
            assert hasattr(p, f), f"SearchOfferPayload lacks {f!r}"
        assert p.proposal_id, "a proposal carried no immutable identity"
        assert p.context_digest, "a proposal carried no context binding"
        assert p.source_edge_id, "a proposal carried no source edge identity"
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
def test_a_rejected_proposal_leaves_the_real_root_open_with_candidates_intact():
    """Rewritten onto the real obligation.

    The earlier version built the obsolete `edge_id` payload field, invented its
    own SearchKey, opened an artificial node, and settled while `_damaged` had
    left the slot bonded -- the exact schema and bond-overwrite geometry commit
    1B claimed to have removed.
    """
    o, j, slot, victim, seed, root, node = _reopened(4)
    sibling = [b.supplier for s, b in j.bonds.items() if s != slot][0]
    kids = list(node["children_opened"])
    assert len(kids) >= 2, "need a second child to prove others stay active"
    outstanding_before = set(node["children_outstanding"])

    pay = _root_payload(o, j, node, sibling, "p/rejopen", kids[0])
    assert pay.search_key is root
    assert pay.context_digest == node["search_context"].context_digest()

    j.deliver_proposal(root, kids[0], pay)
    ok = j.settle_search_offer(pay)

    assert ok is False, "the sibling supplier was accepted into a second slot"
    assert C["SEARCH_OFFER_SETTLEMENT_REJECTIONS"] >= 1
    assert node["status"] == "OPEN", (
        f"a rejected proposal closed the search (status {node['status']})")
    assert slot not in j.bonds, "a rejected proposal bonded the slot anyway"
    assert root.need_id not in j.closed_needs, "a rejected proposal closed the Need"
    still = set(node["children_outstanding"])
    assert still >= (outstanding_before - {kids[0]}), (
        f"unrelated candidate paths were cancelled by a rejection: "
        f"{outstanding_before - still}")


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
    ctx = _ctx()
    key = _key_for(j, slot, ctx, "probe:eligible")
    reset()
    outcome = producer.deliver_search(key, "e/elig", allocation=6.0,
                                      lineage=(j.unit_id,), sender=j.unit_id,
                                      context=ctx)
    assert _kind(outcome) == "SearchProposal", (
        f"an eligible producer returned {_kind(outcome)}; a candidate is a "
        f"proposal, not a terminal answer")
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
    ctx = _ctx()
    key = _key_for(j, slot, ctx, "probe:widen")
    reset()
    node = j.open_canonical_search(key, "e/root", 40.0)
    first_round = list(node["children_opened"])
    seen = list(first_round)
    for _ in range(3):
        for child in list(node["children_outstanding"]):
            j.deliver_terminal(key, child, "SearchExhausted", refund=0.0)
        seen += [c for c in node["children_opened"] if c not in seen]
    allc = list(node["children_opened"])
    assert len(allc) == len(set(allc)), (
        f"child edge ids repeat across widening rounds: "
        f"{[c for c in allc if allc.count(c) > 1][:4]}")
    # The earlier version ended in `... or True`, so an implementation that
    # opened only ONE round satisfied the uniqueness assertion and the test
    # proved nothing about widening.
    assert node["round"] >= 2, (
        f"only {node['round']} expansion round(s) occurred, so uniqueness across "
        f"rounds was never exercised")
    assert len(allc) > len(first_round), (
        f"children_opened did not grow after the first round "
        f"({len(allc)} vs {len(first_round)})")
    rounds = {c.rsplit("/c", 1)[0] for c in allc}
    assert len(rounds) >= 2, (
        f"all child ids share one round prefix {rounds}; round identity does not "
        f"differ across expansions")


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
    finished = [n for n in nodes.values()
                if n["status"] in ("COMMITTED", "CLOSED", "EXHAUSTED")]
    assert finished, (
        "no canonical node reached a terminal status, so no settlement "
        "reconciliation was exercised")
    for (uid, key), node in nodes.items():
        if node["status"] not in ("COMMITTED", "CLOSED", "EXHAUSTED"):
            continue
        assert not node["children_outstanding"], (
            f"{uid} finished with children still outstanding")
        assert node["child_allocations_in_flight"] == 0, (
            f"{uid} finished with {node['child_allocations_in_flight']} still in "
            f"flight; outstanding allocations were discarded, not cancelled")
        # `child_refunds_received` is cumulative AUDIT telemetry. A refund is
        # transferred INTO local_reserve, so adding both double-counts the same
        # credit -- which is what the earlier version of this assertion did.
        accounted = (node["local_reserve"] + node["child_allocations_in_flight"]
                     + node["consumed_credit"] + node["cancelled_credit"]
                     + node["returned_to_parent"])
        assert abs(accounted - node["incoming_allocation"]) < 1e-6, (
            f"{uid}: {accounted} accounted against an allocation of "
            f"{node['incoming_allocation']}")


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


# ---------------------------------------------------------------------------
# Full context binding: every enforcement field must be inside the key digest
# ---------------------------------------------------------------------------


@live
@pytest.mark.parametrize("field,tampered", [
    ("maximum_supplier_cost", 0.01),
    ("cooldown_excluded_suppliers", frozenset({"someone.else"})),
    ("constraint_generation", 7),
    ("policy_snapshot", ("forged-policy",)),
])
def test_tampering_with_any_enforcement_field_is_rejected(field, tampered):
    """V1 bound only the refusal and must-differ digests into SearchKey.

    A relay could therefore change the cost ceiling, the cooldown set, the
    constraint generation or the policy snapshot while keeping the same
    SearchKey -- an unenforced constraint wearing a valid identity. One
    `context_digest` must cover every enforcement field.
    """
    o, j, slot, victim, seed = _damaged(4)
    honest = _ctx(must_differ_from_suppliers=frozenset({"x.1"}))
    key = _key_for(j, slot, honest, f"probe:tamper:{field}")
    assert honest.matches(key), "the honest context does not match its own key"

    forged = _ctx(must_differ_from_suppliers=frozenset({"x.1"}),
                  **{field: tampered})
    assert not forged.matches(key), (
        f"tampering with {field} left the context matching the SearchKey, so "
        f"that field is not bound by context_digest")

    unit = next(u for u in o.units.values() if u.unit_id not in (ENV, SINK))
    reset()
    outcome = unit.deliver_search(key, f"e/tamper/{field}", allocation=6.0,
                                  lineage=(j.unit_id,), sender=j.unit_id,
                                  context=forged)
    assert _kind(outcome) == "SearchContextRejected", (
        f"a context with a tampered {field} was accepted ({_kind(outcome)})")


# ---------------------------------------------------------------------------
# Remote eligibility: cost ceiling, cooldown, and DERIVATION-CHAIN refusal
# ---------------------------------------------------------------------------

@live
def test_a_candidate_above_the_cost_ceiling_proposes_nothing():
    o, j, slot, victim, seed = _damaged(4)
    want = j.capability.accepts[slot]
    producer = next(u for u in o.units.values()
                    if u.capability.produces == want and u.unit_id != victim)
    # PAIRED POSITIVE CONTROL. Without it, a candidate that is merely nonfirm,
    # unmet or silent satisfies the negative assertion and the named field is
    # never shown to be the cause.
    control_ctx = _ctx()
    control_key = _key_for(j, slot, control_ctx, "probe:cost:control")
    reset()
    control = producer.deliver_search(control_key, "e/cost/control",
                                      allocation=6.0, lineage=(j.unit_id,),
                                      sender=j.unit_id, context=control_ctx)
    assert _kind(control) == "SearchProposal", (
        f"the control candidate {producer.unit_id} did not propose under a "
        f"neutral context ({_kind(control)}), so the exclusion test below "
        f"cannot attribute anything to maximum_supplier_cost")

    ctx = _ctx(maximum_supplier_cost=producer.capability.cost / 10.0)
    key = _key_for(j, slot, ctx, "probe:cost")
    reset()
    outcome = producer.deliver_search(key, "e/cost", allocation=6.0,
                                      lineage=(j.unit_id,), sender=j.unit_id,
                                      context=ctx)
    assert _kind(outcome) != "SearchProposal", (
        f"{producer.unit_id} costs {producer.capability.cost} against a ceiling "
        f"of {ctx.maximum_supplier_cost} yet proposed itself")
    assert getattr(outcome, "reason", None) == "candidate_above_cost_ceiling", (
        f"exclusion reason was {getattr(outcome, 'reason', None)!r}, expected "
        f"'candidate_above_cost_ceiling'; a blanket refusal must not satisfy this")


@live
def test_a_cooldown_excluded_candidate_proposes_nothing():
    o, j, slot, victim, seed = _damaged(4)
    want = j.capability.accepts[slot]
    producer = next(u for u in o.units.values()
                    if u.capability.produces == want and u.unit_id != victim)
    # PAIRED POSITIVE CONTROL. Without it, a candidate that is merely nonfirm,
    # unmet or silent satisfies the negative assertion and the named field is
    # never shown to be the cause.
    control_ctx = _ctx()
    control_key = _key_for(j, slot, control_ctx, "probe:cooldown:control")
    reset()
    control = producer.deliver_search(control_key, "e/cooldown/control",
                                      allocation=6.0, lineage=(j.unit_id,),
                                      sender=j.unit_id, context=control_ctx)
    assert _kind(control) == "SearchProposal", (
        f"the control candidate {producer.unit_id} did not propose under a "
        f"neutral context ({_kind(control)}), so the exclusion test below "
        f"cannot attribute anything to cooldown_excluded_suppliers")

    ctx = _ctx(cooldown_excluded_suppliers=frozenset({producer.unit_id}))
    key = _key_for(j, slot, ctx, "probe:cooldown")
    reset()
    outcome = producer.deliver_search(key, "e/cooldown", allocation=6.0,
                                      lineage=(j.unit_id,), sender=j.unit_id,
                                      context=ctx)
    assert _kind(outcome) != "SearchProposal", (
        f"{producer.unit_id} is cooldown-excluded yet proposed itself")
    assert getattr(outcome, "reason", None) == "candidate_in_cooldown", (
        f"exclusion reason was {getattr(outcome, 'reason', None)!r}, expected "
        f"'candidate_in_cooldown'; a blanket refusal must not satisfy this test")


@live
def test_an_upstream_ancestor_in_the_refusal_set_blocks_the_proposal():
    """Proves DERIVATION intersection, not just direct candidate exclusion.

    The earlier causal-refusal test refused the candidate's OWN id, which any
    trivial identity check satisfies and which says nothing about whether the
    candidate's derivation chain was examined.
    """
    o, j, slot, victim, seed = _damaged(4)
    want = j.capability.accepts[slot]
    producer = next(u for u in o.units.values()
                    if u.capability.produces == want and u.unit_id != victim
                    and u.bonds)
    ancestors = sorted({b.supplier for b in producer.bonds.values()} - {ENV})
    assert ancestors, (
        f"{producer.unit_id} has no upstream ancestor, so derivation-chain "
        f"enforcement cannot be exercised on it")
    ancestor = ancestors[0]
    assert ancestor != producer.unit_id
    control_ctx = _ctx()
    control_key = _key_for(j, slot, control_ctx, "probe:ancestor:control")
    reset()
    control = producer.deliver_search(control_key, "e/ancestor/control",
                                      allocation=6.0, lineage=(j.unit_id,),
                                      sender=j.unit_id, context=control_ctx)
    assert _kind(control) == "SearchProposal", (
        f"the control candidate {producer.unit_id} did not propose under a "
        f"neutral context ({_kind(control)}), so refusing it below proves "
        f"nothing about derivation-chain enforcement")

    ctx = _ctx(causally_refused_sources=frozenset({ancestor}))
    key = _key_for(j, slot, ctx, "probe:ancestor")
    reset()
    outcome = producer.deliver_search(key, "e/ancestor", allocation=6.0,
                                      lineage=(j.unit_id,), sender=j.unit_id,
                                      context=ctx)
    assert _kind(outcome) != "SearchProposal", (
        f"{producer.unit_id} proposed itself although its ancestor {ancestor} is "
        f"in the origin's refusal set; the derivation chain was not checked")
    assert getattr(outcome, "reason", None) == "candidate_derivation_refused", (
        f"exclusion reason was {getattr(outcome, 'reason', None)!r}, expected "
        f"'candidate_derivation_refused'")


# ---------------------------------------------------------------------------
# Legacy projection is one-way and holds no decision authority
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Legacy projection inertness, proved with a CONTROL/EXPERIMENTAL TWIN
# ---------------------------------------------------------------------------

def _active_cone(o):
    """Units the CURRENT accepted result actually depends on.

    Walk back from SINK's accepted bond through settled bonds. A unit outside
    this cone can be silenced with no effect on the result, so damaging one
    proves nothing about repair.
    """
    seen, stack = set(), [SINK]
    while stack:
        uid = stack.pop()
        if uid in seen or uid not in o.units:
            continue
        seen.add(uid)
        for b in o.units[uid].bonds.values():
            stack.append(b.supplier)
    return seen - {ENV, SINK}


def _second_victim(o, j, first_victim):
    """A second damage target that is CAUSALLY NECESSARY to the current result.

    Choosing the first produced bonded unit in lexical order could pick a unit
    the accepted result does not depend on. Silencing it would then cause no
    repair even with a correct implementation, so the twin test would fail on
    fixture selection while appearing to prove projection inertness.
    """
    sink = o.units[SINK]
    if 0 not in sink.bonds:
        return None
    final = o._produced.get(SINK)
    chain = final.chain if final is not None else frozenset()
    cone = _active_cone(o)
    for uid in sorted(cone):
        if uid == first_victim or uid not in o._produced:
            continue
        if not o.units[uid].bonds:
            continue
        # Prefer a unit that appears in the accepted value's own derivation.
        if chain and uid not in chain:
            continue
        return uid
    return None


def _normalized_settlement(o):
    """Settlement in CAPABILITY terms, so twin comparison is name-independent."""
    return sorted((o.units[u].capability.name, s,
                   o.units[b.supplier].capability.name
                   if b.supplier in o.units else b.supplier)
                  for u in o.units for s, b in o.units[u].bonds.items())


@live
def test_legacy_projection_is_inert_across_a_SECOND_real_repair():
    """The earlier version of this test was vacuous.

    It repaired once, corrupted `_search`, then ran another work item on an
    ALREADY REPAIRED organ. With the obligation satisfied, the second run may
    initiate no canonical repair at all, so the corrupted projection is never put
    anywhere near a decision and the test proves nothing.

    Two identical organs now take the same first repair; only the experimental
    one has its projections corrupted; both then take the SAME second distinct
    damage and repair again. Inertness is proved by the second repair, not by an
    absence of activity.
    """
    control, j_c, slot_c, victim_c, seed = _damaged(4)
    reset()
    control.run_item(PAYLOAD_B)
    nodes_after_first_control = len(_nodes(control))

    experiment, j_e, slot_e, victim_e, seed_e = _damaged(4)
    assert seed_e == seed and victim_e == victim_c and slot_e == slot_c, (
        "the twins are not identical, so any difference is not attributable to "
        "the corrupted projection")
    reset()
    experiment.run_item(PAYLOAD_B)

    projections = [(u, nid, st) for u in experiment.units.values()
                   for nid, st in u._search.items()]
    assert projections, (
        "no legacy projection was produced, so this test cannot prove the "
        "projection is inert")
    for u, nid, st in projections:
        st["settled"] = not st.get("settled", False)
        st["credits"] = -999.0
        st["rejected"] = {"forged": 99}
        for f in ("reserve", "in_flight", "consumed", "cancelled"):
            if f in st:
                st[f] = -999.0

    second_c = _second_victim(control, j_c, victim_c)
    second_e = _second_victim(experiment, j_e, victim_e)
    assert second_c is not None and second_c == second_e, (
        f"no identical second damage target ({second_c} vs {second_e})")

    control.units[second_c].silent = True
    experiment.units[second_e].silent = True
    reset()
    control.run_item(PAYLOAD_B)
    control_nodes = len(_nodes(control))
    control_out = _normalized_settlement(control)
    reset()
    experiment.run_item(PAYLOAD_B)
    experiment_nodes = len(_nodes(experiment))

    assert control_nodes > nodes_after_first_control, (
        "the second damage triggered no new canonical repair in the control, so "
        "the corrupted projection was never near a live decision; if the target "
        "is outside the active dependency cone this is a fixture-selection "
        "failure rather than evidence about the projection")
    assert C["REPAIR_REOPENS"] > 0, (
        "the second damage produced no reopen, so it was not causally active")
    assert experiment_nodes == control_nodes, (
        f"canonical node counts diverged: control {control_nodes}, experiment "
        f"{experiment_nodes}")
    assert _normalized_settlement(experiment) == control_out, (
        "corrupting the legacy projection changed the second repair's "
        "settlement, so `_search` still holds decision authority")
    assert C["LEGACY_PROJECTION_DECISION_READS"] == 0, (
        "canonical routing read a legacy projection field to make a decision")
    assert C["LEGACY_REPAIR_NEED_MESSAGES"] == 0
    assert C["DUAL_REPAIR_SEARCHES"] == 0


# ---------------------------------------------------------------------------
# Exactly-once proposal resolution
# ---------------------------------------------------------------------------

def _reopened(n_auth=4, density=0.8):
    """A REAL open obligation, CAPTURED WHILE IT IS STILL OPEN.

    Two separate problems, both of which this helper must solve.

    First, `_damaged` only silences the victim; its bond is still in the slot.
    Calling `settle_search_offer` in that state exercises "overwrite a bonded
    slot" rather than proposal resolution, because `_settle` writes
    `self.bonds[slot] = Bond(...)` while the slot-open check lives in
    `_on_offer`.

    Second -- and this is why a full `run_item` will not do -- with four
    producers a CORRECT Single-Flight implementation may discover and settle a
    replacement during that very call. The helper would then find the slot
    rebonded, the Need closed and the root committed, and would fail against the
    finished mechanism it is meant to test. Running the search to completion and
    then demanding it still be open is a temporally impossible fixture.

    So the state is captured mid-flight through a declared harness seam that
    stops as soon as the root exists and before the wave commits or exhausts.
    `run_until_repair_root` is a TEST DRIVER, not protocol authority: it steps
    the existing scheduler and decides nothing about routing or settlement.
    """
    o, j, slot, victim, seed = _damaged(n_auth, density)
    reset()
    root = o.run_until_repair_root(j.unit_id, slot, max_events=3000)

    assert root is not None, (
        f"no canonical repair root appeared for {j.unit_id}[{slot}] before the "
        f"driver stopped")
    assert slot not in j.bonds, (
        f"slot {slot} is still bonded to "
        f"{j.bonds.get(slot) and j.bonds[slot].supplier}; the obligation was "
        f"never reopened, so a settlement here would be a bond OVERWRITE, not "
        f"proposal resolution")
    nid = j.open_needs.get(slot)
    assert nid is not None, (
        f"no open Need generation for slot {slot}; there is no obligation to "
        f"resolve a proposal against")
    assert nid not in j.closed_needs, "the Need generation is already closed"
    node = j.canonical_searches.get(root)
    assert node is not None, f"no canonical node at {j.unit_id} for {root}"
    assert node["status"] == "OPEN", (
        f"the root is already {node['status']}; the driver did not pause before "
        f"the wave resolved")
    assert "search_context" in node, (
        "the canonical node does not expose its immutable search_context, so a "
        "proposal cannot be built against the root's actual constraints")
    assert node["search_context"].matches(root), (
        "the node's stored context does not match its own SearchKey digest")
    assert C["DUAL_REPAIR_SEARCHES"] == 0, "a legacy repair search is also active"
    return o, j, slot, victim, seed, root, node


def _root_payload(o, j, node, supplier, pid, source_edge):
    """A payload belonging to THE ACTUAL ROOT.

    The replay, race and rejection tests previously invented keys such as
    `probe:replay` and settled them against the live root. A correct
    implementation must refuse those as `wrong_need_generation`, so those
    expectations could never pass lawfully. Every resolution payload now carries
    the root's own SearchKey and the digest of the root's own stored context.
    """
    key = node["search_key"]
    ctx = node["search_context"]
    return v5.SearchOfferPayload(
        proposal_id=pid, search_key=key, context_digest=ctx.context_digest(),
        supplier=supplier,
        supplier_class=o.units[supplier].capability.klass(),
        offered_type=key.wanted_type,
        cost=o.units[supplier].capability.cost,
        firm=True, derivation_chain=frozenset({supplier}),
        source_node=supplier, source_edge_id=source_edge)


def _payload(o, j, slot, ctx, need_id, supplier, pid):
    return v5.SearchOfferPayload(
        proposal_id=pid,
        search_key=_key_for(j, slot, ctx, need_id),
        context_digest=ctx.context_digest(),
        supplier=supplier,
        supplier_class=o.units[supplier].capability.klass(),
        offered_type=j.capability.accepts[slot],
        cost=o.units[supplier].capability.cost,
        firm=True,
        derivation_chain=frozenset({supplier}),
        source_node=supplier,
        source_edge_id=f"e/{pid}")


@live
def test_an_exact_proposal_replay_settles_only_once():
    o, j, slot, victim, seed, root, node = _reopened(4)
    want = j.capability.accepts[slot]
    spare = next(u.unit_id for u in o.units.values()
                 if u.capability.produces == want
                 and u.unit_id not in {b.supplier for b in j.bonds.values()}
                 and u.unit_id != victim)
    kids = list(node["children_opened"])
    assert kids, "the root opened no child edge to deliver a proposal through"
    pay = _root_payload(o, j, node, spare, "p/replay", kids[0])
    assert pay.search_key is root, "the payload does not belong to the live root"

    first = j.settle_search_offer(pay)
    decisions = C["UNIQUE_PROPOSAL_DECISIONS"]
    settled_bond = j.bonds.get(slot)
    for _ in range(4):
        again = j.settle_search_offer(pay)
        assert again is first, (
            "a replayed proposal produced a different decision")
    assert C["UNIQUE_PROPOSAL_DECISIONS"] == decisions, (
        "a replayed proposal was decided more than once")
    assert C["UNIQUE_PROPOSAL_IDS_RECEIVED"] == 1, (
        f"one proposal id was counted "
        f"{C['UNIQUE_PROPOSAL_IDS_RECEIVED']} times")
    assert j.bonds.get(slot) is settled_bond, (
        "a replayed proposal re-bonded the slot")


@live
def test_two_competing_proposals_race_through_real_child_edges():
    """Routed through `proposal_routes`, not settled by direct call.

    The earlier version called `settle_search_offer` twice and then expected a
    terminal on `payload.source_edge_id`. That bypasses the echo topology and
    would license an implementation where the root writes directly to an
    arbitrary source edge using organ-global telemetry. `source_edge_id` says
    where a proposal ORIGINATED; it is not the root's cancellation edge.
    """
    o, j, slot, victim, seed, root, node = _reopened(4)
    want = j.capability.accepts[slot]
    bonded = {b.supplier for b in j.bonds.values()}
    spares = [u.unit_id for u in o.units.values()
              if u.capability.produces == want and u.unit_id not in bonded
              and u.unit_id != victim]
    assert len(spares) >= 2, f"only {len(spares)} spare producers; need two"

    kids = list(node["children_opened"])
    assert len(kids) >= 2, (
        f"the root opened {len(kids)} child edges; a race needs at least two "
        f"distinct arrival paths")
    child_a, child_b = kids[0], kids[1]
    a = _root_payload(o, j, node, spares[0], "p/raceA", child_a)
    b = _root_payload(o, j, node, spares[1], "p/raceB", child_b)
    assert a.search_key is root and b.search_key is root, (
        "a racing payload does not belong to the live root generation")

    j.deliver_proposal(root, child_a, a)
    j.deliver_proposal(root, child_b, b)
    assert node["proposal_routes"].get(a.proposal_id) == child_a, (
        "proposal A was not correlated with the child edge it arrived on")
    assert node["proposal_routes"].get(b.proposal_id) == child_b, (
        "proposal B was not correlated with the child edge it arrived on")

    first = j.settle_search_offer(a)
    second = j.settle_search_offer(b)
    assert not (first and second), (
        "both competing proposals committed; a slot took two bonds")
    committed = j.bonds.get(slot)
    assert committed is not None, "neither proposal committed"
    winner, loser = ((a, b) if first else (b, a))
    assert committed.supplier == winner.supplier

    win_edge = node["proposal_routes"][winner.proposal_id]
    lose_edge = node["proposal_routes"][loser.proposal_id]
    win_outs = o.search_edge_terminals.get(win_edge, {}).get("outcomes", [])
    lose_outs = o.search_edge_terminals.get(lose_edge, {}).get("outcomes", [])
    assert [_kind(x) for x in win_outs] == ["SearchCommitted"], (
        f"the winner child edge {win_edge} received "
        f"{[_kind(x) for x in win_outs]}, expected exactly SearchCommitted")
    assert lose_outs and _kind(lose_outs[0]) in ("SearchCancelled",
                                                 "SearchNeedClosed"), (
        f"the loser child edge {lose_edge} received "
        f"{[_kind(x) for x in lose_outs]}")
    # The root must NOT shortcut to an edge that is not one of its own children.
    for eid, rec in o.search_edge_terminals.items():
        if rec["from_unit"] != j.unit_id:
            continue
        assert eid in node["children_opened"] or eid == node["adopted_parent_edge"], (
            f"the root emitted a terminal on {eid}, which is neither one of its "
            f"own child edges nor its adopted parent edge")
    assert j.bonds.get(slot).supplier == winner.supplier, (
        "the committed bond was later replaced by the race loser")


@live
def test_settlement_refuses_an_occupied_slot_with_an_attributable_reason():
    """`_settle` writes the bond without an independent slot-open check.

    The slot-open guard lives in `_on_offer`, so a proposal resolved directly
    against a still-bonded slot would OVERWRITE it.
    """
    o, j, slot, victim, seed = _damaged(4)      # silenced, but STILL BONDED
    assert slot in j.bonds, "this test requires the slot to still be occupied"
    existing = j.bonds[slot].supplier
    want = j.capability.accepts[slot]
    spare = next(u.unit_id for u in o.units.values()
                 if u.capability.produces == want
                 and u.unit_id not in {b.supplier for b in j.bonds.values()})
    ctx = _ctx()
    reset()
    key = _key_for(j, slot, ctx, "probe:occupied")
    pay = v5.SearchOfferPayload(
        proposal_id="p/occupied", search_key=key,
        context_digest=ctx.context_digest(), supplier=spare,
        supplier_class=o.units[spare].capability.klass(),
        offered_type=key.wanted_type, cost=o.units[spare].capability.cost,
        firm=True, derivation_chain=frozenset({spare}),
        source_node=spare, source_edge_id="e/occupied")

    assert j.settle_search_offer(pay) is False, (
        "a proposal was settled into an occupied slot, overwriting the bond")
    assert j.bonds[slot].supplier == existing, "the existing bond was replaced"
    reasons = [getattr(x, "reason", None)
               for rec in o.search_edge_events.values() for x in rec]
    assert "slot_already_bonded" in reasons, (
        f"no attributable slot_already_bonded reason was recorded: {reasons}")


@live
def test_a_rejected_proposal_is_recorded_once_and_replay_adds_nothing():
    o, j, slot, victim, seed, root, node = _reopened(4)
    sibling = [b.supplier for s, b in j.bonds.items() if s != slot][0]
    kids = list(node["children_opened"])
    assert kids, "the root opened no child edge"
    pay = _root_payload(o, j, node, sibling, "p/rej", kids[0])

    assert j.settle_search_offer(pay) is False, (
        "the sibling supplier was accepted into a second slot")
    rejections = C["SEARCH_OFFER_SETTLEMENT_REJECTIONS"]
    assert rejections == 1, f"one rejection expected, recorded {rejections}"
    for _ in range(4):
        assert j.settle_search_offer(pay) is False
    assert C["SEARCH_OFFER_SETTLEMENT_REJECTIONS"] == rejections, (
        "replaying a rejected proposal incremented the rejection count again")
    assert node["status"] == "OPEN", (
        f"a rejected proposal closed the search (status {node['status']})")
    assert pay.search_key.need_id not in j.closed_needs


@live
def test_a_committed_proposal_routes_the_commit_down_the_accepted_child():
    """`proposal_routes` is what makes commit/cancel addressable."""
    o, j, slot, victim, seed = _damaged(4)
    ctx = _ctx()
    reset()
    key = _key_for(j, slot, ctx, "probe:routes")
    node = j.open_canonical_search(key, "e/root", 9.0)
    assert "proposal_routes" in node, (
        "the canonical node records no proposal_id -> child_edge_id mapping, so "
        "a commit cannot follow the accepted path and rejection feedback cannot "
        "reach the actual proposer")
    kids = list(node["children_opened"])
    assert len(kids) >= 2, "need at least two children to distinguish routing"
    pay = _payload(o, j, slot, ctx, "probe:routes",
                   [b.supplier for s, b in j.bonds.items() if s != slot][0],
                   "p/routes")
    j.deliver_proposal(key, kids[0], pay)
    assert node["proposal_routes"].get(pay.proposal_id) == kids[0], (
        "the proposal was not correlated with the child edge it arrived on")


# ---------------------------------------------------------------------------
# Multi-hop closure: terminals must reach each proposal's source edge
# ---------------------------------------------------------------------------

@live
def test_commit_and_cancel_reach_the_proposal_source_edge_multi_hop():
    """A root-facing terminal alone can strand the deeper subtree.

    The routed-race spec checks the root's immediate child edges. That is
    satisfiable by an implementation that closes only the edge it can see and
    leaves every deeper edge open. Closure must travel hop by hop through each
    node's own `proposal_routes`, never by a root shortcut through organ-global
    telemetry.
    """
    o, j, slot, victim, seed, root, node = _reopened(4, density=1.0)
    reset()
    o.run_item(PAYLOAD_B)

    nodes = _nodes(o)
    deep = [(uid, k, n) for (uid, k), n in nodes.items()
            if k == root and uid != j.unit_id and n.get("children_opened")]
    assert deep, (
        "no intermediate canonical node opened children for this search, so "
        "multi-hop closure was never exercised")

    terminals = o.search_edge_terminals
    for uid, k, n in deep:
        for child in n["children_opened"]:
            outs = terminals.get(child, {}).get("outcomes", [])
            assert len(outs) == 1, (
                f"deep edge {child} at {uid} received {len(outs)} terminal "
                f"outcomes; a subtree was stranded rather than closed")

    for eid, rec in terminals.items():
        owner = nodes.get((rec["from_unit"], rec["search_key"]))
        if owner is None:
            continue
        allowed = set(owner["children_opened"]) | {owner["adopted_parent_edge"]}
        assert eid in allowed, (
            f"{rec['from_unit']} emitted a terminal on {eid}, which is neither "
            f"one of its own child edges nor its adopted parent edge -- that is "
            f"a global shortcut, not local routing")

    assert C["ORPHANED_SEARCH_EDGES"] == 0
