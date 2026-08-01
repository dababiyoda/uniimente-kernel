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
    Organ.run_until_repair_root(unit, slot, max_events) -> PausedRun
                                         stops as soon as the root exists and
                                         BEFORE the wave commits or exhausts
    Organ.resume_paused_item(paused, max_events)
                                         continues the SAME work item: it must
                                         not increment item_seq, reset _produced,
                                         recreate ready/_queued, recommission,
                                         start a new generation, scan the organ,
                                         or make any routing or settlement
                                         decision. It is a TEST DRIVER.
    PausedRun                            payload, item_seq, produced, ready,
                                         queued, msg_pending, unmet_state,
                                         events_dispatched, root. Its `ready`
                                         entries carry stable event identities.
    Organ.scheduler_event_log[event_id]  {unit_id, event_kind,
                                         work_item_generation, scheduled_count,
                                         dispatch_count} -- HARNESS TELEMETRY.
                                         It records; it must never influence a
                                         scheduling decision.
    node["accepted_proposal_id"]         the proposal the root actually accepted;
                                         acceptance is READ, never inferred from
                                         node status
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
                                  context=control_ctx,
                                  transport=v5.HARNESS_DELIVERY)
    assert _kind(control) == "SearchProposal", (
        f"the control candidate {sibling} did not propose under a neutral "
        f"context ({_kind(control)}), so refusing it below proves nothing about "
        f"must_differ_from enforcement")
    reset()
    outcome = unit.deliver_search(key, "e/remote", allocation=6.0,
                                 lineage=(j.unit_id,), sender=j.unit_id,
                                 context=ctx,
                                  transport=v5.HARNESS_DELIVERY)
    assert _kind(outcome) != "SearchProposal", (
        f"{sibling} is excluded by must_differ_from yet offered itself remotely; "
        f"this is the duplicate-supplier defect returning through the digest gap")
    assert getattr(outcome, "reason", None) == "candidate_must_differ", (
        f"exclusion reason was {getattr(outcome, 'reason', None)!r}, expected "
        f"'candidate_must_differ'")
    assert getattr(outcome, "payload", None) is None


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
                                      context=ctx,
                                       transport=v5.HARNESS_DELIVERY)
    assert _kind(outcome) != "SearchProposal", (
        "a candidate whose own derivation is refused by the origin proposed itself")


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
                                 context=forged,
                                  transport=v5.HARNESS_DELIVERY)
    assert _kind(outcome) == "SearchContextRejected", (
        f"a context whose digests do not match the SearchKey was accepted "
        f"({_kind(outcome)})")


# ---------------------------------------------------------------------------
# 3-4. The offer must be settleable, and rejection must not close the search
# ---------------------------------------------------------------------------

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


def test_a_rejected_proposal_leaves_the_real_root_open_with_candidates_intact():
    """Rewritten onto the real obligation.

    The earlier version built the obsolete `edge_id` payload field, invented its
    own SearchKey, opened an artificial node, and settled while `_damaged` had
    left the slot bonded -- the exact schema and bond-overwrite geometry commit
    1B claimed to have removed.
    """
    o, j, slot, victim, seed, root, node, paused = _reopened(4)
    sibling = [b.supplier for s, b in j.bonds.items() if s != slot][0]
    kids = list(node["children_opened"])
    assert len(kids) >= 2, "need a second child to prove others stay active"
    outstanding_before = set(node["children_outstanding"])

    pay = _root_payload(o, j, node, sibling, "p/rejopen", kids[0],
                        expect_eligible=False)
    assert pay.search_key is root
    assert pay.context_digest == node["search_context"].context_digest()

    j.deliver_proposal(root, kids[0], pay, v5.HARNESS_DELIVERY)
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
                                      context=ctx,
                                      transport=v5.HARNESS_DELIVERY)
    assert _kind(outcome) == "SearchProposal", (
        f"an eligible producer returned {_kind(outcome)}; a candidate is a "
        f"proposal, not a terminal answer")
    node = producer.canonical_searches[key]
    assert node["children_opened"] == [], (
        f"an eligible producer opened {len(node['children_opened'])} children "
        f"before answering; eligibility must be evaluated first")
    assert C["DIRECTED_SEARCH_EDGES_PROBED"] == 0, (
        "an eligible producer created outbound probes it did not need")


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
            j.deliver_terminal(key, child, "SearchExhausted", refund=0.0,
                               sender=v5.HARNESS_DELIVERY)
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
                                  context=forged,
                                  transport=v5.HARNESS_DELIVERY)
    assert _kind(outcome) == "SearchContextRejected", (
        f"a context with a tampered {field} was accepted ({_kind(outcome)})")


# ---------------------------------------------------------------------------
# Remote eligibility: cost ceiling, cooldown, and DERIVATION-CHAIN refusal
# ---------------------------------------------------------------------------

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
                                      sender=j.unit_id, context=control_ctx,
                                      transport=v5.HARNESS_DELIVERY)
    assert _kind(control) == "SearchProposal", (
        f"the control candidate {producer.unit_id} did not propose under a "
        f"neutral context ({_kind(control)}), so the exclusion test below "
        f"cannot attribute anything to maximum_supplier_cost")

    ctx = _ctx(maximum_supplier_cost=producer.capability.cost / 10.0)
    key = _key_for(j, slot, ctx, "probe:cost")
    reset()
    outcome = producer.deliver_search(key, "e/cost", allocation=6.0,
                                      lineage=(j.unit_id,), sender=j.unit_id,
                                      context=ctx,
                                      transport=v5.HARNESS_DELIVERY)
    assert _kind(outcome) != "SearchProposal", (
        f"{producer.unit_id} costs {producer.capability.cost} against a ceiling "
        f"of {ctx.maximum_supplier_cost} yet proposed itself")
    assert getattr(outcome, "reason", None) == "candidate_above_cost_ceiling", (
        f"exclusion reason was {getattr(outcome, 'reason', None)!r}, expected "
        f"'candidate_above_cost_ceiling'; a blanket refusal must not satisfy this")


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
                                      sender=j.unit_id, context=control_ctx,
                                      transport=v5.HARNESS_DELIVERY)
    assert _kind(control) == "SearchProposal", (
        f"the control candidate {producer.unit_id} did not propose under a "
        f"neutral context ({_kind(control)}), so the exclusion test below "
        f"cannot attribute anything to cooldown_excluded_suppliers")

    ctx = _ctx(cooldown_excluded_suppliers=frozenset({producer.unit_id}))
    key = _key_for(j, slot, ctx, "probe:cooldown")
    reset()
    outcome = producer.deliver_search(key, "e/cooldown", allocation=6.0,
                                      lineage=(j.unit_id,), sender=j.unit_id,
                                      context=ctx,
                                      transport=v5.HARNESS_DELIVERY)
    assert _kind(outcome) != "SearchProposal", (
        f"{producer.unit_id} is cooldown-excluded yet proposed itself")
    assert getattr(outcome, "reason", None) == "candidate_in_cooldown", (
        f"exclusion reason was {getattr(outcome, 'reason', None)!r}, expected "
        f"'candidate_in_cooldown'; a blanket refusal must not satisfy this test")


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
                                      sender=j.unit_id, context=control_ctx,
                                      transport=v5.HARNESS_DELIVERY)
    assert _kind(control) == "SearchProposal", (
        f"the control candidate {producer.unit_id} did not propose under a "
        f"neutral context ({_kind(control)}), so refusing it below proves "
        f"nothing about derivation-chain enforcement")

    ctx = _ctx(causally_refused_sources=frozenset({ancestor}))
    key = _key_for(j, slot, ctx, "probe:ancestor")
    reset()
    outcome = producer.deliver_search(key, "e/ancestor", allocation=6.0,
                                      lineage=(j.unit_id,), sender=j.unit_id,
                                      context=ctx,
                                      transport=v5.HARNESS_DELIVERY)
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
    paused = o.run_until_repair_root(j.unit_id, slot, max_events=3000)

    assert paused is not None, (
        f"no canonical repair root appeared for {j.unit_id}[{slot}] before the "
        f"driver stopped")
    root = paused.root
    # The continuation must carry the LIVE execution state, not just a key.
    for f in ("payload", "item_seq", "produced", "ready", "queued",
              "msg_pending", "unmet_state", "events_dispatched", "root"):
        assert hasattr(paused, f), f"PausedRun lacks {f!r}"
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
    assert "accepted_proposal_id" in node, (
        "the root does not expose accepted_proposal_id, so in a multi-proposal "
        "wave a commit cannot be correlated with the proposal that won")
    assert node["accepted_proposal_id"] is None, (
        "the paused root already records an accepted proposal")
    assert "search_context" in node, (
        "the canonical node does not expose its immutable search_context, so a "
        "proposal cannot be built against the root's actual constraints")
    assert node["search_context"].matches(root), (
        "the node's stored context does not match its own SearchKey digest")
    assert C["DUAL_REPAIR_SEARCHES"] == 0, "a legacy repair search is also active"
    return o, j, slot, victim, seed, root, node, paused


def _resume(o, paused, max_events=3000):
    """Continue the SAME work item. A fresh `run_item` is not continuation.

    `run_item` resets _payload, _produced, item_seq, events_dispatched, ready,
    _queued and _unmet_state. Calling it after a pause therefore means: pause
    generation N, discard its scheduler continuation, start generation N+1, then
    inspect generation N's root. That changes provenance and settled_item, drops
    queued non-message events, and makes a restarted item look like the
    continuation of the paused wave.
    """
    before_seq = paused.item_seq
    before_commissions = o.commissions
    before_gen = paused.root.work_item_generation
    o.resume_paused_item(paused, max_events=max_events)
    assert o.item_seq == before_seq, (
        f"resume advanced the work item from {before_seq} to {o.item_seq}; that "
        f"is a new generation, not a continuation")
    assert paused.root.work_item_generation == before_gen, (
        "the root's work-item generation changed across the resume")
    assert o.commissions == before_commissions, "resume recommissioned the organ"
    assert C["SUPERVISOR_RESTART_EVENTS"] == 0
    assert C["WHOLE_ORGAN_REVIEW_PASSES"] == 0, "resume scanned the organ"
    return paused


def _root_payload(o, j, node, supplier, pid, source_edge, expect_eligible=True):
    """A payload belonging to THE ACTUAL ROOT, carrying REAL evidence.

    Two corrections over the earlier version.

    The replay, race and rejection tests once invented keys such as
    `probe:replay` and settled them against the live root; a correct
    implementation must refuse those as `wrong_need_generation`, so those
    expectations could never pass lawfully. Every payload now carries the root's
    own SearchKey and the digest of the root's own stored context.

    And `derivation_chain=frozenset({supplier})` was a truncated fiction. The
    supplier's real derivation is itself plus all bonded ancestry, which the
    runtime already computes as `_derives_from()`. A truncated chain can make a
    stale or causally refused candidate look acceptable during direct settlement
    tests -- manufacturing eligibility the candidate does not have.
    """
    key = node["search_key"]
    ctx = node["search_context"]
    cand = o.units[supplier]
    chain = cand._derives_from()
    if expect_eligible:
        # The candidate must be genuinely eligible before it is injected;
        # otherwise a later rejection proves nothing about the rule under test.
        assert cand.capability.produces == key.wanted_type, (
            f"{supplier} does not produce {key.wanted_type}")
        assert not cand.unmet(), f"{supplier} has unmet slots and is not firm"
        assert not cand.silent, f"{supplier} is silenced"
        assert supplier not in ctx.must_differ_from_suppliers, (
            f"{supplier} is must-differ excluded under the root context")
        assert cand.capability.cost <= ctx.maximum_supplier_cost, (
            f"{supplier} costs {cand.capability.cost} over the ceiling "
            f"{ctx.maximum_supplier_cost}")
        assert supplier not in ctx.cooldown_excluded_suppliers, (
            f"{supplier} is cooldown excluded")
        assert not (chain & ctx.causally_refused_sources), (
            f"{supplier}'s derivation intersects the origin's refusals")
    return v5.SearchOfferPayload(
        proposal_id=pid, search_key=key, context_digest=ctx.context_digest(),
        supplier=supplier, supplier_class=cand.capability.klass(),
        offered_type=key.wanted_type, cost=cand.capability.cost,
        firm=not cand.unmet(), derivation_chain=chain,
        source_node=supplier, source_edge_id=source_edge)


def _payload(o, j, slot, ctx, need_id, supplier, pid, source_edge=None,
             forged_chain=None):
    """ONE evidence-construction path.

    `frozenset({supplier})` is not a derivation; the runtime computes the real
    one as `_derives_from()`. A truncated chain manufactures eligibility a
    candidate does not have. `forged_chain` exists only for a test that is
    explicitly constructing forged evidence and says so.
    """
    cand = o.units[supplier]
    return v5.SearchOfferPayload(
        proposal_id=pid,
        search_key=_key_for(j, slot, ctx, need_id),
        context_digest=ctx.context_digest(),
        supplier=supplier,
        supplier_class=cand.capability.klass(),
        offered_type=j.capability.accepts[slot],
        cost=cand.capability.cost,
        firm=not cand.unmet(),
        derivation_chain=(forged_chain if forged_chain is not None
                          else cand._derives_from()),
        source_node=supplier,
        source_edge_id=source_edge or f"e/{pid}")


def test_an_exact_proposal_replay_settles_only_once():
    o, j, slot, victim, seed, root, node, paused = _reopened(4)
    want = j.capability.accepts[slot]
    spare = next(u.unit_id for u in o.units.values()
                 if u.capability.produces == want
                 and u.unit_id not in {b.supplier for b in j.bonds.values()}
                 and u.unit_id != victim)
    kids = list(node["children_opened"])
    assert kids, "the root opened no child edge to deliver a proposal through"
    pay = _root_payload(o, j, node, spare, "p/replay", kids[0])
    assert pay.search_key is root, "the payload does not belong to the live root"

    # DELIVERY FIRST. Settling an undelivered payload would license an
    # implementation that accepts an arbitrary unregistered proposal.
    j.deliver_proposal(root, kids[0], pay, v5.HARNESS_DELIVERY)
    assert node["proposal_routes"].get(pay.proposal_id) == kids[0], (
        "the proposal was not registered against the child edge it arrived on")
    events = [e for e in o.search_edge_events.get(kids[0], [])
              if _kind(e) == "SearchProposal"]
    assert len(events) == 1, f"{len(events)} proposal events recorded, expected 1"

    first = j.settle_search_offer(pay)

    # POSITIVE ACCEPTANCE FIRST. Without these, an implementation that always
    # REJECTS passes the whole "settles only once" test: first=False,
    # accepted=None, no bond, replays stay False, nothing changes. That is
    # rejection idempotence, which the separate rejected-replay test covers.
    assert first is True, (
        "the proposal was not accepted, so this test would only be proving "
        "rejection idempotence")
    assert node["accepted_proposal_id"] == pay.proposal_id, (
        f"the root accepted {node['accepted_proposal_id']!r}, not "
        f"{pay.proposal_id!r}")
    settled_bond = j.bonds.get(slot)
    assert settled_bond is not None, "acceptance did not bond the slot"
    assert settled_bond.supplier == pay.supplier, (
        f"the slot bonded {settled_bond.supplier}, not the accepted "
        f"{pay.supplier}")
    # READ THE COMMAND WHERE COMMANDS LIVE. `SearchCommitted` is in
    # PARENT_CONTROL_KINDS and in no other set, so this assertion has always
    # been asking "did the parent command this edge" -- a control fact. It
    # asked `search_edge_terminals`, which is the legacy projection and holds
    # whatever was last written to it by either channel. The canonical answer
    # is the control channel, and reading it here means this assertion keeps
    # meaning the same thing once the projection carries accepted outcomes
    # only. Measured runtime-neutral at b6c9e0c: the identical predicate passes
    # against both the current runtime and the candidate that stops the control
    # path writing the projection (CLOSURE_TRUTH_EXACT_EXECUTION.md, section 3).
    _ac = (o.search_edge_lifecycle.get(kids[0]) or {}).get("accepted_control")
    commits = [x for x in ([_ac] if _ac is not None else [])
               if _kind(x) == "SearchCommitted"]
    assert len(commits) == 1 and getattr(commits[0], "proposal_id", None) == \
        pay.proposal_id, (
        f"the registered child edge holds {len(commits)} commits for "
        f"{pay.proposal_id!r}")
    assert C["UNIQUE_PROPOSAL_DECISIONS"] == 1, (
        f"{C['UNIQUE_PROPOSAL_DECISIONS']} decisions recorded for one proposal")

    decisions = C["UNIQUE_PROPOSAL_DECISIONS"]
    accepted = node["accepted_proposal_id"]
    routes = dict(node["proposal_routes"])
    # THE WHOLE CANONICAL RECORD, not one projection of it, and not only the
    # accepted slots. A replay is inert only if it added no second command, no
    # second outcome AND filed no conflict: a replay that arrived as a
    # contradicting command would leave both accepted slots untouched and
    # append to `control_conflicts`, so a snapshot of the accepted slots alone
    # would call that inert. Against the legacy projection none of the three
    # was visible.
    terminals = {k: [v["accepted_control"], v["accepted_outcome"],
                     list(v["control_conflicts"]), list(v["outcome_conflicts"])]
                 for k, v in o.search_edge_lifecycle.items()}

    for _ in range(4):
        j.deliver_proposal(root, kids[0], pay, v5.HARNESS_DELIVERY)  # replayed ARRIVAL
        again = j.settle_search_offer(pay)              # replayed DECISION
        assert again is first, "a replayed proposal produced a different decision"

    assert len([e for e in o.search_edge_events.get(kids[0], [])
                if _kind(e) == "SearchProposal"]) == 1, (
        "a replayed arrival recorded a second proposal event")
    assert C["UNIQUE_PROPOSAL_DECISIONS"] == decisions, (
        "a replayed proposal was decided more than once")
    assert C["UNIQUE_PROPOSAL_IDS_RECEIVED"] == 1, (
        f"one proposal id was counted {C['UNIQUE_PROPOSAL_IDS_RECEIVED']} times")
    assert node["accepted_proposal_id"] == accepted, "acceptance changed on replay"
    assert dict(node["proposal_routes"]) == routes, "replay altered a route"
    assert {k: [v["accepted_control"], v["accepted_outcome"],
                list(v["control_conflicts"]), list(v["outcome_conflicts"])]
            for k, v in o.search_edge_lifecycle.items()} == terminals, (
        "replay mutated a lifecycle channel: an accepted control, an accepted "
        "outcome, or a filed conflict changed")
    assert j.bonds.get(slot) is settled_bond, "a replayed proposal re-bonded the slot"


def test_settlement_refuses_an_unregistered_proposal():
    """A payload that never arrived on a child edge has no route and no event."""
    o, j, slot, victim, seed, root, node, paused = _reopened(4)
    want = j.capability.accepts[slot]
    spare = next(u.unit_id for u in o.units.values()
                 if u.capability.produces == want
                 and u.unit_id not in {b.supplier for b in j.bonds.values()}
                 and u.unit_id != victim)
    pay = _root_payload(o, j, node, spare, "p/unregistered", "e/never-delivered")
    assert pay.proposal_id not in node["proposal_routes"]

    assert j.settle_search_offer(pay) is False, (
        "an unregistered proposal was settled; settlement must follow a "
        "registered arrival on a real child edge")
    assert slot not in j.bonds, "an unregistered proposal bonded the slot"
    reasons = [getattr(x, "reason", None)
               for evs in o.search_edge_events.values() for x in evs]
    assert "proposal_not_registered" in reasons, (
        f"no attributable proposal_not_registered reason: {reasons}")


def test_two_competing_proposals_race_through_real_child_edges():
    """Routed through `proposal_routes`, not settled by direct call.

    The earlier version called `settle_search_offer` twice and then expected a
    terminal on `payload.source_edge_id`. That bypasses the echo topology and
    would license an implementation where the root writes directly to an
    arbitrary source edge using organ-global telemetry. `source_edge_id` says
    where a proposal ORIGINATED; it is not the root's cancellation edge.
    """
    o, j, slot, victim, seed, root, node, paused = _reopened(4)
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

    j.deliver_proposal(root, child_a, a, v5.HARNESS_DELIVERY)
    j.deliver_proposal(root, child_b, b, v5.HARNESS_DELIVERY)
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
    # SearchCommitted, SearchCancelled and SearchNeedClosed are all in
    # PARENT_CONTROL_KINDS, so every kind this race asserts about is a command
    # the root issued down a child edge -- read from the control channel that
    # owns them, not from the legacy projection.
    _wc = (o.search_edge_lifecycle.get(win_edge) or {}).get("accepted_control")
    _lc = (o.search_edge_lifecycle.get(lose_edge) or {}).get("accepted_control")
    win_outs = [_wc] if _wc is not None else []
    lose_outs = [_lc] if _lc is not None else []
    assert [_kind(x) for x in win_outs] == ["SearchCommitted"], (
        f"the winner child edge {win_edge} received "
        f"{[_kind(x) for x in win_outs]}, expected exactly SearchCommitted")
    assert lose_outs and _kind(lose_outs[0]) in ("SearchCancelled",
                                                 "SearchNeedClosed"), (
        f"the loser child edge {lose_edge} received "
        f"{[_kind(x) for x in lose_outs]}")
    # The root must NOT shortcut to an edge that is not one of its own children.
    # NON-VACUITY MATTERS MOST HERE, because this is the negative control: it
    # is satisfied trivially if it iterates nothing. It looks for edges the
    # ROOT COMMANDED, so it must read the control channel -- against the
    # projection it would go silently empty the moment commands stop being
    # written there, and a negative control that stops looking is worse than
    # none.
    _root_commanded = [eid for eid, rec in o.search_edge_lifecycle.items()
                       if (rec.get("accepted_control") is not None
                           and rec["accepted_control"].from_unit == j.unit_id)]
    assert _root_commanded, (
        "no edge carries a command authored by the root, so the loop below "
        "would inspect nothing and pass without testing anything")
    for eid, rec in o.search_edge_lifecycle.items():
        _emitted = rec.get("accepted_control")
        if _emitted is None or _emitted.from_unit != j.unit_id:
            continue
        assert eid in node["children_opened"] or eid == node["adopted_parent_edge"], (
            f"the root emitted a terminal on {eid}, which is neither one of its "
            f"own child edges nor its adopted parent edge")
    assert j.bonds.get(slot).supplier == winner.supplier, (
        "the committed bond was later replaced by the race loser")


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
    pay = _payload(o, j, slot, ctx, "probe:occupied", spare, "p/occupied",
                   source_edge="e/occupied")

    assert j.settle_search_offer(pay) is False, (
        "a proposal was settled into an occupied slot, overwriting the bond")
    assert j.bonds[slot].supplier == existing, "the existing bond was replaced"
    reasons = [getattr(x, "reason", None)
               for rec in o.search_edge_events.values() for x in rec]
    assert "slot_already_bonded" in reasons, (
        f"no attributable slot_already_bonded reason was recorded: {reasons}")


def test_a_rejected_proposal_is_recorded_once_and_replay_adds_nothing():
    o, j, slot, victim, seed, root, node, paused = _reopened(4)
    sibling = [b.supplier for s, b in j.bonds.items() if s != slot][0]
    kids = list(node["children_opened"])
    assert kids, "the root opened no child edge"
    pay = _root_payload(o, j, node, sibling, "p/rej", kids[0],
                        expect_eligible=False)
    j.deliver_proposal(root, kids[0], pay, v5.HARNESS_DELIVERY)
    assert node["proposal_routes"].get(pay.proposal_id) == kids[0], (
        "the rejected proposal was never registered against its child edge")
    # Zero initial events must FAIL. Recording the count and only requiring it to
    # stay unchanged is satisfied by 0 -> 0.
    initial = [e for e in o.search_edge_events.get(kids[0], [])
               if _kind(e) == "SearchProposal"]
    assert len(initial) == 1, (
        f"{len(initial)} SearchProposal events on the arrival edge, expected "
        f"exactly one before the first rejection")
    assert getattr(initial[0], "payload", None) is not None and \
        initial[0].payload.proposal_id == pay.proposal_id, (
        "the recorded event does not carry this proposal's identity")

    assert j.settle_search_offer(pay) is False, (
        "the sibling supplier was accepted into a second slot")
    rejections = C["SEARCH_OFFER_SETTLEMENT_REJECTIONS"]
    assert rejections == 1, f"one rejection expected, recorded {rejections}"
    assert node["accepted_proposal_id"] is None, (
        "a rejected proposal was recorded as accepted")
    assert not [x for x in o.search_edge_terminals.get(kids[0], {}).get(
        "outcomes", []) if _kind(x) == "SearchCommitted"], (
        "a rejected proposal produced a SearchCommitted")
    routes = dict(node["proposal_routes"])
    events = len([e for e in o.search_edge_events.get(kids[0], [])
                  if _kind(e) == "SearchProposal"])
    assert events == 1
    for _ in range(4):
        j.deliver_proposal(root, kids[0], pay, v5.HARNESS_DELIVERY)  # replayed ARRIVAL
        assert j.settle_search_offer(pay) is False  # replayed DECISION
    assert C["SEARCH_OFFER_SETTLEMENT_REJECTIONS"] == rejections, (
        "replaying a rejected proposal incremented the rejection count again")
    assert dict(node["proposal_routes"]) == routes, "replay altered a route"
    assert len([e for e in o.search_edge_events.get(kids[0], [])
                if _kind(e) == "SearchProposal"]) == events, (
        "a replayed arrival recorded a second proposal event")
    assert node["status"] == "OPEN", (
        f"a rejected proposal closed the search (status {node['status']})")
    assert pay.search_key.need_id not in j.closed_needs


def test_delivered_proposal_is_registered_on_the_arrival_edge():
    """LOCAL ROUTE REGISTRATION ONLY -- renamed, because it never committed.

    It was called `test_a_committed_proposal_routes_the_commit_down_the_accepted_child`
    while calling no settlement, requiring no accepted_proposal_id and requiring
    no SearchCommitted. A test name must not claim a commit it never exercises.
    Full commit propagation is covered by the multi-hop specification.
    """
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
    j.deliver_proposal(key, kids[0], pay, v5.HARNESS_DELIVERY)
    assert node["proposal_routes"].get(pay.proposal_id) == kids[0], (
        "the proposal was not correlated with the child edge it arrived on")


# ---------------------------------------------------------------------------
# Multi-hop closure: terminals must reach each proposal's source edge
# ---------------------------------------------------------------------------

@live
def test_commit_and_cancel_reach_the_proposal_source_edge_multi_hop():
    """POSITIVE. A wave that merely exhausts must not satisfy this.

    The earlier version required only that every deep child edge hold exactly one
    terminal, accepting any kind. A fully exhausted search with no proposal, no
    settlement and no commit passed it, while the test's own name claimed commit
    and cancellation reached the source edge. It now demands the live sequence.
    """
    o, j, slot, victim, seed, root, node, paused = _reopened(4, density=1.0)
    _resume(o, paused)              # continue the SAME item, not a new one

    events = o.search_edge_events
    proposals = [(eid, e) for eid, evs in events.items() for e in evs
                 if _kind(e) == "SearchProposal"]
    assert proposals, (
        "no SearchProposal occurred, so this run cannot demonstrate that a "
        "commit reaches a proposal's source edge")

    nodes = _nodes(o)

    # THE ROOT NAMES ITS WINNER. Inferring acceptance from `status == COMMITTED`
    # is unsound in a multi-proposal wave: the node can be COMMITTED because
    # proposal B won while the loop happens to select proposal A.
    pid = node["accepted_proposal_id"]
    assert pid, (
        f"the root records no accepted_proposal_id (status {node.get('status')}); "
        f"a wave that only exhausted cannot satisfy this specification")
    # PER-EDGE, NOT GLOBAL. `search_edge_events` is edge-scoped telemetry, and
    # the accepted proposal legitimately traverses source -> intermediate ->
    # root, so a correct echo records the same immutable proposal_id ONCE ON
    # EACH traversed edge. Demanding exactly one event organ-wide is the same
    # error as the earlier "one Offer edge per SearchKey globally", on the
    # proposal side.
    matching = [(eid, e) for eid, e in proposals
                if getattr(e, "payload", None)
                and e.payload.proposal_id == pid]
    assert matching, f"no proposal event carries the accepted id {pid}"
    per_edge = {}
    for eid, e in matching:
        per_edge.setdefault(eid, []).append(e)
    for eid, evs in per_edge.items():
        assert len(evs) == 1, (
            f"edge {eid} recorded {len(evs)} events for proposal {pid}; a "
            f"proposal may appear once per edge, never twice on one edge")
    payloads = {(e.payload.supplier, e.payload.offered_type, e.payload.cost,
                 e.payload.derivation_chain, e.payload.source_edge_id)
                for _, e in matching}
    assert len(payloads) == 1, (
        f"the accepted proposal's evidence mutated in transit: {payloads}")
    ev = matching[0][1]
    payload = ev.payload
    source_edge = payload.source_edge_id

    # The accepted route must pass through at least one INTERMEDIATE node.
    hops = [(uid, k, n) for (uid, k), n in nodes.items()
            if k == root and uid != j.unit_id and pid in n.get("proposal_routes", {})]
    assert hops, (
        "the accepted proposal was correlated only at the root, so multi-hop "
        "closure was never exercised")

    terminals = o.search_edge_terminals
    src_outs = terminals.get(source_edge, {}).get("outcomes", [])
    assert [_kind(x) for x in src_outs] == ["SearchCommitted"], (
        f"the proposal's source edge {source_edge} received "
        f"{[_kind(x) for x in src_outs]}, expected exactly one SearchCommitted; "
        f"closing only the root-facing child strands the deeper subtree")
    assert getattr(src_outs[0], "proposal_id", None) == pid, (
        f"the SearchCommitted on {source_edge} carries proposal id "
        f"{getattr(src_outs[0], 'proposal_id', None)!r}, not the accepted {pid!r}")
    # Every commit along the accepted route names the same proposal.
    route_edges = [node["proposal_routes"][pid]] + [
        n["proposal_routes"][pid] for _, _, n in hops]
    for e in route_edges:
        outs = terminals.get(e, {}).get("outcomes", [])
        commits = [x for x in outs if _kind(x) == "SearchCommitted"]
        assert len(commits) == 1, (
            f"accepted-route edge {e} carries {len(commits)} commits")
        assert getattr(commits[0], "proposal_id", None) == pid, (
            f"accepted-route edge {e} committed a different proposal "
            f"{getattr(commits[0], 'proposal_id', None)!r}")

    elsewhere = [eid for eid, rec in terminals.items()
                 if eid != source_edge and rec["search_key"] == root
                 and any(_kind(x) == "SearchCommitted" for x in rec["outcomes"])
                 and eid not in {n["proposal_routes"].get(pid)
                                 for _, _, n in hops} | {
                                     node["proposal_routes"].get(pid)}]
    assert not elsewhere, (
        f"SearchCommitted for {pid} also appeared on unrelated edges: {elsewhere}")

    # A non-winning branch must be cancelled through local mappings, all the way
    # down to its deepest open edge.
    losers = [c for c in node["children_opened"]
              if c != node["proposal_routes"].get(pid)]
    assert losers, "no non-winning branch existed to cancel"
    for c in losers:
        outs = terminals.get(c, {}).get("outcomes", [])
        assert len(outs) == 1 and _kind(outs[0]) in (
            "SearchCancelled", "SearchNeedClosed", "SearchExhausted",
            "SearchCoalesced", "SearchCycleClosed"), (
            f"non-winning branch {c} received {[_kind(x) for x in outs]}")
    for uid, k, n in hops:
        for child in n["children_opened"]:
            outs = terminals.get(child, {}).get("outcomes", [])
            assert len(outs) == 1, (
                f"deep edge {child} at {uid} received {len(outs)} terminals; a "
                f"subtree was stranded rather than closed")

    # Every edge on the accepted route -- source, intermediates and the
    # root-facing child -- must be represented exactly once.
    for e in set(route_edges) | {source_edge}:
        evs = [x for x in o.search_edge_events.get(e, [])
               if _kind(x) == "SearchProposal"
               and getattr(x, "payload", None)
               and x.payload.proposal_id == pid]
        assert len(evs) == 1, (
            f"accepted-route edge {e} recorded {len(evs)} proposal events for "
            f"{pid}; every route edge must carry exactly one")

    # Local routing only: no node may terminate an edge it does not own.
    for eid, rec in terminals.items():
        owner = nodes.get((rec["from_unit"], rec["search_key"]))
        if owner is None:
            continue
        allowed = set(owner["children_opened"]) | {owner["adopted_parent_edge"]}
        assert eid in allowed, (
            f"{rec['from_unit']} emitted a terminal on {eid}, which is neither "
            f"one of its own child edges nor its adopted parent edge -- a global "
            f"shortcut, not local routing")
    assert C["ORPHANED_SEARCH_EDGES"] == 0


# ---------------------------------------------------------------------------
# Pause/resume must be observationally transparent
# ---------------------------------------------------------------------------

def _normalized_value(o, v):
    """The ACTUAL result, in name-independent terms.

    `result_ok` only asks whether the contract invariant returned true, so two
    runs that consumed DIFFERENT INPUTS both satisfy it and compare equal. That
    made the pause twin blind to the one thing it most needed to control: the
    experimental organ was resuming a different work item's payload.
    """
    if v is None:
        return None
    return (v.type, v.payload,
            o.units[v.producer].capability.name
            if v.producer in o.units else v.producer,
            tuple(sorted(o.units[c].capability.name if c in o.units else c
                         for c in v.chain)))


def _normalized_run_state(o):
    """Everything a pause must not perturb, in name-independent terms."""
    return {
        "result_ok": o.result_ok(o._produced.get(SINK)),
        "result_value": _normalized_value(o, o._produced.get(SINK)),
        "bonds": sorted((u.capability.name, s,
                         o.units[b.supplier].capability.name
                         if b.supplier in o.units else b.supplier,
                         b.settled_by, b.settled_item)
                        for u in o.units.values() for s, b in u.bonds.items()),
        "terminals": sorted(
            (rec["from_unit"], rec["to_unit"], _kind(x))
            for rec in o.search_edge_terminals.values() for x in rec["outcomes"]),
        "messages": o.messages,
        "events": o.events_dispatched,
        "accepted": sorted(
            str(n.get("accepted_proposal_id")) for n in _nodes(o).values()),
        "locality": (C["WHOLE_ORGAN_REVIEW_PASSES"], C["GLOBAL_REPAIR_SCANS"],
                     C["UNIT_ENUMERATIONS_FOR_REPAIR"],
                     C["SUPERVISOR_RESTART_EVENTS"],
                     C["UNAUTHORIZED_EXTERNAL_EFFECTS"],
                     C["INDEPENDENCE_VIOLATIONS"]),
    }


def test_pausing_at_the_root_does_not_change_execution():
    """Declared continuity is not proved continuity.

    `_resume` checks item_seq, generation, commissions and two counters. A broken
    resume that reconstructs only part of the scheduler -- dropping a queued
    event, losing a pending recipient, or rebuilding `_produced` -- satisfies all
    of those and still alters execution. The only sound proof is a twin: one
    organ runs uninterrupted, the other pauses at the same root and resumes, and
    their observable state must match.
    """
    control, jc, slot_c, victim_c, seed_c = _damaged(4)
    reset()
    control.run_item(PAYLOAD_B)
    control_state = _normalized_run_state(control)

    experiment, je, slot_e, victim_e, seed_e = _damaged(4)
    assert (seed_e, slot_e, victim_e) == (seed_c, slot_c, victim_c), (
        "the twins are not identical, so any difference is not attributable to "
        "the pause")
    reset()
    # THE SAME INPUT, STATED EXPLICITLY. The harness default reuses whatever
    # payload the organ last held -- PAYLOAD_A, left by the fixture run -- so the
    # twin silently compared a PAYLOAD_B control against a PAYLOAD_A experiment.
    # Nothing in the old comparison could see that, because `result_ok` is true
    # for both inputs.
    paused = experiment.run_until_repair_root(je.unit_id, slot_e,
                                              max_events=3000,
                                              payload=PAYLOAD_B)
    assert paused is not None, "no root appeared in the experimental twin"
    assert paused.payload == PAYLOAD_B, (
        f"the paused item is carrying {paused.payload!r}, not the control's "
        f"{PAYLOAD_B!r}; the twins are not processing the same work item")
    queued_at_pause = list(paused.ready)
    assert queued_at_pause, (
        "the ready queue was empty at the pause, so nothing about event "
        "preservation is being tested")
    experiment.resume_paused_item(paused, max_events=3000)

    assert _normalized_run_state(experiment) == control_state, (
        "pausing at the repair root changed the observable execution; the "
        "resume did not restore the scheduler faithfully")

    # EXACTLY ONCE, not merely "no longer queued". An empty queue proves removal,
    # not dispatch: a resume could drop event A, dispatch event B twice, end with
    # an empty queue, and hide the difference in an aggregate count. Event-level
    # identity is the only way to tell. This telemetry records; it must never
    # influence scheduling.
    log = getattr(experiment, "scheduler_event_log", None)
    assert log is not None, (
        "the organ records no per-event scheduler telemetry, so exactly-once "
        "dispatch cannot be proved")
    for ev in queued_at_pause:
        eid = getattr(ev, "event_id", None) or (
            ev if isinstance(ev, str) else None)
        assert eid is not None, f"queued entry {ev!r} carries no event identity"
        rec = log.get(eid)
        assert rec is not None, (
            f"event {eid} was queued at the pause but never appears in the "
            f"dispatch log; the resume dropped it")
        assert rec["scheduled_count"] == 1, (
            f"event {eid} was scheduled {rec['scheduled_count']} times")
        assert rec["dispatch_count"] == 1, (
            f"event {eid} was dispatched {rec['dispatch_count']} times; the "
            f"resume duplicated it")
        assert rec["work_item_generation"] == paused.item_seq, (
            f"event {eid} was dispatched under generation "
            f"{rec['work_item_generation']}, not the paused item "
            f"{paused.item_seq}")
