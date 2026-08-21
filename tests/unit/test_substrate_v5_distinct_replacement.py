"""Adversarial tests for constraint-preserving distinct replacement search.

The measured cause of 18 of 19 unrestored development episodes was that a
two-input join reopened a slot, the only candidate reachable was the sibling
slot's own supplier, `_settle` refused it as a duplicate, and the branch stopped
there. The rule is correct -- one supplier filling both inputs destroys the
independence the join exists to provide -- so the search, not the rule, is what
had to change.

These tests hold the rule fixed and attack the search: an ineligible candidate
must not end a branch, the constraint must survive relays, it must never become
causal blame, budgets must stay conserved, and a genuinely unsatisfiable join
must terminate with bounded escalation rather than a silent stall.
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
from substrate.v5 import ENV, SINK, C, Need, Offer, reset

import fixtures as F

PAYLOAD = "  Claim-42  "


def _organ_with_auth_producers(n_auth, seed=7):
    """A two-input reconcile join fed by `n_auth` distinct AUTH producers.

    The development fixture has three PX spines but only TWO AUTH producers, so
    at the reconcile layer it is structurally identical to the deliberately
    unsatisfiable fixture. These builders make the producer count explicit so
    "a distinct replacement exists" and "none exists" are separate tests.
    """
    caps = F._spine("alpha2") + F._spine("beta2") + F._spine("gamma2")
    for i in range(n_auth):
        caps.append(F.cap(f"au{i}", ("PX", "PX"), "AUTH", F.AUTHORISE,
                          1.0 + 0.1 * i, f"d.a{i}", "authorise", F.OK_PRICE))
    caps.append(F.cap("rn0", ("AUTH", "AUTH"), "RECON", F.RECONCILE,
                      1.0, "d.p", "reconcile", F.OK_AUTH))
    caps.append(F.cap("db0", ("RECON",), "VERDICT", F.DISBURSE,
                      1.0, "d.r", "disburse", F.OK_RECON))
    o = F._organ(caps, random.Random(seed))
    F.prepare(o)
    reset()
    o.commission()
    healthy = o.run_item(PAYLOAD)
    return o, o.result_ok(healthy)


def _join(o, want="AUTH"):
    for u in o.units.values():
        if u.capability.accepts.count(want) == 2:
            return u
    return None


def _formed_join(n_auth):
    for seed in range(40):
        o, ok = _organ_with_auth_producers(n_auth, seed)
        j = _join(o)
        if not ok or j is None or len(j.bonds) != 2:
            continue
        sups = {b.supplier for b in j.bonds.values()}
        if len(sups) == 2:
            return o, j, seed
    pytest.skip(f"no formed two-supplier join with {n_auth} AUTH producers")


# ---------------------------------------------------------------------------
# A. Three-producer join repair
# ---------------------------------------------------------------------------

def _sweep(n_auth, seeds=range(40)):
    """Restoration and independence for a join with `n_auth` distinct producers."""
    episodes = restored = resettled = 0
    for seed in seeds:
        o, ok = _organ_with_auth_producers(n_auth, seed)
        j = _join(o)
        if not ok or j is None or len(j.bonds) != 2:
            continue
        if len({b.supplier for b in j.bonds.values()}) != 2:
            continue
        episodes += 1
        slot = min(j.bonds)
        victim = j.bonds[slot].supplier
        o.units[victim].silent = True
        reset()
        result = o.run_item(PAYLOAD)
        if o.result_ok(result):
            restored += 1
        b = j.bonds.get(slot)
        if b is not None and b.supplier != victim:
            resettled += 1
        sups = [x.supplier for x in j.bonds.values()]
        assert len(sups) == len(set(sups)), (
            f"{j.unit_id} lost supplier independence with {n_auth} producers")
        assert C["INDEPENDENCE_VIOLATIONS"] == 0
    return episodes, restored, resettled


def test_A_join_repair_discovers_a_distinct_supplier_when_one_exists():
    """The whole point: a spare independent producer must actually be found.

    Asserted as a real outcome, not as "at least it did not submit a duplicate".
    """
    episodes, restored, resettled = _sweep(4)
    assert episodes >= 10, "not enough formed joins to assert on"
    assert restored > 0, (
        "no episode restored even though a spare independent AUTH producer "
        "existed -- distinct replacement discovery is not working")
    assert resettled >= restored
    # Majority behaviour, not a single lucky seed.
    assert restored * 2 > episodes, (
        f"only {restored}/{episodes} restored with ample independent capacity")


def test_A_discovery_scales_with_independent_capacity():
    """Repair capability must track available independence, not luck.

    Two producers feeding a two-input join is unsatisfiable by construction, so
    zero restorations there is CORRECT. This is the measurement that shows the
    development fixture's reconcile layer sits at that unsatisfiable point.
    """
    two = _sweep(2)
    three = _sweep(3)
    four = _sweep(4)
    assert two[1] == 0, (
        "a join with only two producers reported a restoration; the sibling "
        "supplier must have been accepted into both slots")
    assert four[1] > three[1] > two[1], (
        f"restoration did not increase with independent capacity: "
        f"2->{two[1]}, 3->{three[1]}, 4->{four[1]}")


# ---------------------------------------------------------------------------
# B. No valid distinct replacement -> bounded escalation, never false success
# ---------------------------------------------------------------------------

def test_B_two_producer_join_escalates_and_never_reports_false_restoration():
    o, join, seed = _formed_join(2)
    producers = {u.unit_id for u in o.units.values()
                 if u.capability.produces == "AUTH"}
    assert len(producers) == 2, "this fixture must be unsatisfiable by construction"
    victim_slot = min(join.bonds)
    victim = join.bonds[victim_slot].supplier
    sibling = [b.supplier for s, b in join.bonds.items() if s != victim_slot][0]

    o.units[victim].silent = True
    reset()
    result = o.run_item(PAYLOAD)

    assert C["INDEPENDENCE_VIOLATIONS"] == 0
    assert sibling not in [b.supplier for s, b in join.bonds.items()
                           if s == victim_slot], (
        "the sibling supplier was accepted into both protected slots")
    if result is not None and o.result_ok(result):
        sups = [b.supplier for b in join.bonds.values()]
        assert len(sups) == len(set(sups)), (
            "restoration was reported while one supplier filled both slots")


# ---------------------------------------------------------------------------
# C. Constraint propagation: survives relay, never becomes causal blame
# ---------------------------------------------------------------------------

def test_C_must_differ_from_survives_every_relay():
    need = Need("n1", "AUTH", "rn.9", 1, ("rn.9",), 8.0, frozenset({"bad.1"}),
                hops=6, credits=9.0, must_differ_from=frozenset({"au.0"}))
    hop = need
    for through in ("a", "b", "c"):
        hop = hop.relay(through)
        assert hop.must_differ_from == frozenset({"au.0"}), (
            "a relay weakened the compatibility constraint")
        assert hop.refused == frozenset({"bad.1"}), "a relay altered causal blame"
    assert hop.credits < need.credits and hop.hops < need.hops


def test_C_ineligibility_never_enters_causal_failure_memory():
    o, join, seed = _formed_join(3)
    victim_slot = min(join.bonds)
    victim = join.bonds[victim_slot].supplier
    sibling = [b.supplier for s, b in join.bonds.items() if s != victim_slot][0]
    o.units[victim].silent = True
    reset()
    o.run_item(PAYLOAD)

    assert sibling not in join.refused, (
        "a healthy sibling supplier was blamed for a failure merely because it "
        "is structurally ineligible for the other slot")
    for ev in join.refusal_evidence:
        assert sibling not in ev.get("distinguishing_refused", []), (
            "slot ineligibility was recorded as causal evidence")


def test_C_sub_need_does_not_inherit_another_units_sibling_exclusions():
    need = Need("n1", "AUTH", "rn.9", 1, ("rn.9",), 8.0, frozenset(),
                hops=6, credits=9.0, must_differ_from=frozenset({"au.0"}))
    sub = need.sub("PX", "au.5", 0, 4.0)
    assert sub.must_differ_from == frozenset(), (
        "one join's sibling exclusions leaked into a different unit's slot")


# ---------------------------------------------------------------------------
# D. A matching but ineligible relay must not terminate the branch
# ---------------------------------------------------------------------------

def test_D_ineligible_producer_relays_instead_of_answering():
    o, join, seed = _formed_join(3)
    producers = [u for u in o.units.values() if u.capability.produces == "AUTH"]
    ineligible = producers[0]
    ineligible.outbox.clear()
    ineligible.seen.clear()
    ineligible._exhausted_reported.clear()
    before = C["INELIGIBLE_CANDIDATE_BRANCH_CONTINUATIONS"]

    need = Need("probe:1", "AUTH", join.unit_id, 1, (join.unit_id,), 8.0,
                frozenset(), hops=6, credits=9.0,
                must_differ_from=frozenset({ineligible.unit_id}))
    sender = next(iter(sorted(ineligible.neighbours)))
    ineligible._on_need(sender, need)

    assert C["INELIGIBLE_CANDIDATE_BRANCH_CONTINUATIONS"] == before + 1
    offers = [m for _, m in ineligible.outbox if isinstance(m, Offer)]
    assert not offers, "an ineligible candidate submitted a usable Offer"
    forwarded = [m for _, m in ineligible.outbox if isinstance(m, Need)]
    acknowledged = [m for _, m in ineligible.outbox
                    if isinstance(m, tuple) and m and m[0] == "__exhausted__"]
    assert forwarded or acknowledged, (
        "an ineligible candidate neither relayed the need nor acknowledged "
        "the branch as exhausted -- it silently consumed the branch")
    assert any(r.kind == "candidate_ineligible" for r in ineligible.receipts)


# ---------------------------------------------------------------------------
# E. Simultaneous joins keep independent constraints and budgets
# ---------------------------------------------------------------------------

def test_E_two_joins_do_not_share_exclusions_or_budgets():
    o, join, seed = _formed_join(3)
    others = [u for u in o.units.values()
              if len(u.capability.accepts) == 2 and u.unit_id != join.unit_id]
    reset()
    for u in [join] + others[:1]:
        for slot in sorted(u.bonds):
            u._reopen_contrastively(slot, v5.SILENT, "probe", frozenset(),
                                    has_sibling=False, observed_chain=None)
            break
    seen = {}
    for u in [join] + others[:1]:
        for nid, st in u._search.items():
            seen[nid] = set(st.get("must_differ_from", []))
    for nid, excl in seen.items():
        origin = nid.split(":")[0]
        for other, other_excl in seen.items():
            if other == nid:
                continue
            assert not (excl & other_excl) or origin == other.split(":")[0], (
                "one join's sibling exclusions leaked into another's search")


# ---------------------------------------------------------------------------
# F. Credit conservation
# ---------------------------------------------------------------------------

def test_F_no_branch_relay_or_acknowledgement_mints_credit():
    import evaluator as EV
    for n_auth in (2, 3):
        o, join, seed = _formed_join(n_auth)
        victim = join.bonds[min(join.bonds)].supplier
        o.units[victim].silent = True
        reset()
        o.run_item(PAYLOAD)
        assert EV.credits_conserved(o), (
            f"credit was minted or driven negative with {n_auth} AUTH producers")
        for u in o.units.values():
            for st in u._search.values():
                assert st["credits"] <= st["initial_credits"] + 1e-9
                assert st["credits"] >= -1e-9


def test_F_exhaustion_acknowledgement_is_sent_at_most_once_per_need():
    o, join, seed = _formed_join(3)
    u = next(x for x in o.units.values() if x.unit_id not in (ENV, SINK))
    u.outbox.clear()
    u._exhausted_reported.clear()
    dead = Need("probe:2", "AUTH", "rn.9", 1, ("rn.9",), 8.0, frozenset(),
                hops=0, credits=9.0)
    for _ in range(5):
        u._on_need("some.sender", dead)
    acks = [m for _, m in u.outbox
            if isinstance(m, tuple) and m and m[0] == "__exhausted__"]
    assert len(acks) == 1, f"acknowledgement traffic was amplified: {len(acks)}"


# ---------------------------------------------------------------------------
# G. Gate G preservation
# ---------------------------------------------------------------------------

def test_G_the_same_supplier_never_fills_both_protected_slots():
    for n_auth in (2, 3, 4):
        o, join, seed = _formed_join(n_auth)
        victim = join.bonds[min(join.bonds)].supplier
        o.units[victim].silent = True
        reset()
        o.run_item(PAYLOAD)
        for u in o.units.values():
            sups = [b.supplier for b in u.bonds.values()]
            assert len(sups) == len(set(sups)), (
                f"{u.unit_id} bound one supplier into two slots "
                f"({n_auth} AUTH producers)")
        assert C["INDEPENDENCE_VIOLATIONS"] == 0


def test_G_settlement_guard_remains_the_final_enforcement_layer():
    """Even if a need carried no constraint at all, `_settle` must still refuse."""
    o, join, seed = _formed_join(3)
    slot = min(join.bonds)
    sibling = [b.supplier for s, b in join.bonds.items() if s != slot][0]
    del join.bonds[slot]           # the slot is open; the sibling still holds its own
    ok = join._settle(slot, Offer("x", sibling, "authorise", "AUTH", 1.0, True,
                                  frozenset({sibling})), o._caps(join))
    assert ok is False
    assert join._last_refusal == "duplicate_supplier"


# ---------------------------------------------------------------------------
# H. Unit-ID permutation
# ---------------------------------------------------------------------------

def test_H_renaming_units_does_not_materially_change_discovery():
    outcomes = []
    for seed in (3, 11, 19, 23):
        o, ok = _organ_with_auth_producers(3, seed)
        j = _join(o)
        if not ok or j is None or len(j.bonds) != 2:
            continue
        victim = j.bonds[min(j.bonds)].supplier
        o.units[victim].silent = True
        reset()
        o.run_item(PAYLOAD)
        sups = [b.supplier for b in j.bonds.values()]
        outcomes.append((len(sups) == len(set(sups)),
                         C["INDEPENDENCE_VIOLATIONS"],
                         bool(C["INELIGIBLE_CANDIDATE_BRANCH_CONTINUATIONS"] >= 0)))
    assert outcomes, "no formed join across the permuted seeds"
    assert all(indep for indep, _, _ in outcomes), (
        "independence held for some unit namings and not others")
    assert all(v == 0 for _, v, _ in outcomes)


# ---------------------------------------------------------------------------
# Item 6: both formerly-zero counters must become nonzero at behaviour sites
# ---------------------------------------------------------------------------

def test_distinct_settlement_counter_becomes_nonzero_with_spare_capacity():
    """DISTINCT_ELIGIBLE_REPLACEMENTS_SETTLED read 0 on the whole cohort.

    It must fire when a join actually settles a distinct replacement, and the
    increment must come from the settlement site, not from an expected outcome.
    """
    fired = 0
    for seed in range(40):
        o, ok = _organ_with_auth_producers(4, seed)
        j = _join(o)
        if not ok or j is None or len(j.bonds) != 2:
            continue
        if len({b.supplier for b in j.bonds.values()}) != 2:
            continue
        slot = min(j.bonds)
        victim = j.bonds[slot].supplier
        o.units[victim].silent = True
        reset()
        o.run_item(PAYLOAD)
        if C["DISTINCT_ELIGIBLE_REPLACEMENTS_SETTLED"] > 0:
            fired += 1
            b = j.bonds.get(slot)
            # ATTRIBUTION AT THE SETTLEMENT SITE, NOT AT THE END STATE.
            #
            # This previously required the join to still hold a replacement
            # bond when the run finished. That was sound while at most one
            # repair could occur per work item. It no longer is: a candidate
            # that could serve but is itself unmet now recruits its OWN
            # prerequisite, so a run can contain several repairs, and a
            # replacement that settled can afterwards be lost to a further
            # failure. On seed 7 the counter is 1, a proposal was decided, and
            # the join's slot is open again -- all three facts are true
            # together, and the old assertion could not express that.
            #
            # What must remain true, and is still checked: the counter cannot
            # fire without a decision, and the slot must never be bonded back
            # to the supplier that failed.
            assert C["UNIQUE_PROPOSAL_DECISIONS"] > 0, (
                "the counter fired without any proposal being decided, so it "
                "is not driven by the settlement site")
            assert b is None or b.supplier != victim, (
                "the counter fired and the slot is bonded back to the victim")
    assert fired > 0, (
        "DISTINCT_ELIGIBLE_REPLACEMENTS_SETTLED never incremented even with "
        "ample spare independent capacity")


def test_bounded_exhaustion_counter_fires_with_attributable_escalation():
    """BOUNDED_DISTINCT_REPLACEMENT_EXHAUSTIONS read 0 on the whole cohort.

    The old condition also demanded `reserve <= 0`, so a fully searched finite
    neighbourhood with credit left never recorded an exhaustion. A structurally
    unsatisfiable episode must end PROVED, not merely unrestored.
    """
    import evaluator as EV
    proven = 0
    for seed in range(40):
        o, ok = _organ_with_auth_producers(2, seed)
        j = _join(o)
        if not ok or j is None or len(j.bonds) != 2:
            continue
        if len({b.supplier for b in j.bonds.values()}) != 2:
            continue
        slot = min(j.bonds)
        victim = j.bonds[slot].supplier
        o.units[victim].silent = True
        reset()
        result = o.run_item(PAYLOAD)
        if C["BOUNDED_DISTINCT_REPLACEMENT_EXHAUSTIONS"] > 0:
            proven += 1
            assert EV.bounded_escalation_proven(o), (
                "the counter fired without a receipt and an attributable reason")
            assert not o.result_ok(result), "false restoration on an unsatisfiable join"
            assert C["INDEPENDENCE_VIOLATIONS"] == 0
    assert proven > 0, (
        "no structurally unsatisfiable episode produced a proved bounded "
        "exhaustion; escalation cannot be scored as an outcome")


# ---------------------------------------------------------------------------
# Item 3: the ledger must fail under the OLD allocation pattern
# ---------------------------------------------------------------------------

def test_ledger_invariant_holds_across_a_full_repair():
    import evaluator as EV
    for n_auth in (2, 3, 4):
        o, join, seed = _formed_join(n_auth)
        victim = join.bonds[min(join.bonds)].supplier
        o.units[victim].silent = True
        reset()
        o.run_item(PAYLOAD)
        rec = EV.credit_ledger_reconciliation(o)
        assert rec["needs"] > 0, "no need ledger was produced to reconcile"
        assert rec["invariant_failures"] == 0, rec
        assert rec["budget_exceeded"] == 0, rec
        assert rec["branch_overpayments"] == 0, rec
        assert rec["worst_drift"] <= 1e-6, rec


def test_the_old_allocation_pattern_is_caught_by_the_ledger():
    """Reproduce the exact defect: debit 1.0 per branch, hand out reserve/ring.

    With an 18-credit budget and a ring of three the system held 33. The old
    evaluator checked only `0 <= origin <= initial` and passed; the ledger must
    fail.
    """
    import evaluator as EV
    o, join, seed = _formed_join(3)
    st = v5.new_search_ledger(18.0)
    ring, per = 3, 18.0 / 3
    for i in range(ring):
        st["reserve"] -= 1.0                     # the defect: debit one, not `per`
        st["allocated"] += per
        st["in_flight"] += per
        st["branches"][f"b{i}"] = {
            "need_id": "n", "round_id": 0, "branch_id": f"b{i}", "route": "x",
            "allocated_credit": per, "consumed_credit": 0.0,
            "refundable_credit": 0.0, "status": "open"}
    assert st["reserve"] + st["in_flight"] == 33.0, "defect not reproduced"
    assert 0 <= st["reserve"] <= st["initial_credits"], (
        "the OLD range check must still pass, which is why it was insufficient")
    join._search["probe"] = st
    rec = EV.credit_ledger_reconciliation(o)
    assert rec["invariant_failures"] >= 1, (
        "the ledger did not catch 33 credits existing from a budget of 18")
    assert rec["budget_exceeded"] >= 1
    assert rec["ok"] is False


def test_a_replayed_completion_cannot_refund_twice():
    o, join, seed = _formed_join(3)
    st = v5.new_search_ledger(12.0)
    per = 4.0
    st["reserve"] -= per; st["allocated"] += per; st["in_flight"] += per
    st["branches"]["b0"] = {"need_id": "n", "round_id": 0, "branch_id": "b0",
                            "route": "x", "allocated_credit": per,
                            "consumed_credit": 0.0, "refundable_credit": 0.0,
                            "status": "open"}
    st["outstanding"].add("b0")
    for _ in range(4):
        join._complete_branch(st, "b0", per)      # same completion, replayed
    assert st["reserve"] == 12.0, f"refund applied more than once: {st['reserve']}"
    assert st["in_flight"] == 0.0
    assert st["returned"] == per
    total = st["reserve"] + st["in_flight"] + st["consumed"] + st["cancelled"]
    assert abs(total - st["initial_credits"]) < 1e-9


# ---------------------------------------------------------------------------
# Item 4: a round may not widen while any of its branches is still open
# ---------------------------------------------------------------------------

def test_widening_requires_the_whole_round_to_have_completed():
    o, join, seed = _formed_join(3)
    slot = min(join.bonds)
    reset()
    join._reopen_contrastively(slot, v5.SILENT, "probe", frozenset(),
                               has_sibling=False, observed_chain=None)
    nid = join.open_needs.get(slot)
    if nid is None:
        pytest.skip("reopen did not create a need")
    st = join._search[nid]
    if not st["outstanding"]:
        pytest.skip("no branches were opened")
    opened = set(st["outstanding"])
    assert join.widen(slot) is False, (
        "widened while branches from the current round were still outstanding")
    round_before = st["round"]
    for bid in list(opened)[:-1]:
        join._complete_branch(st, bid, 0.0)
    assert join.widen(slot) is False, "widened with one branch still open"
    join._complete_branch(st, list(opened)[-1], 0.0)
    assert st["round"] == round_before
    join.widen(slot)   # may or may not open a new round, depending on routes left
    assert st["in_flight"] >= -1e-9
