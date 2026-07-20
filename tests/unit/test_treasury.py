"""Regenerative Treasury tests: waterfall order, double-entry honesty,
and debt that actually blocks things.

Adversarial suite: skipping upward to fund downward, negative surplus,
unknown tiers, sign games, self-postings, fake regenerative accounts,
repayment without evidence, and the decoration check (debt must block).
"""
import os

import pytest

from compiler.ucl_compiler import compile_constitution
from provenance.ledger import EvidenceLedger

from capital.treasury import (BLOCKED_WHILE_INDEBTED, REGENERATIVE_ACCOUNTS,
                              RegenerativeTreasury, TreasuryError, load_waterfall)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def treasury():
    compiled = compile_constitution(ROOT)
    ledger = EvidenceLedger(compiled.constitution_hash)
    return RegenerativeTreasury(ledger), ledger


# ---------- the waterfall is loaded law, not code opinion ----------

def test_waterfall_comes_from_policy_yaml():
    tiers = load_waterfall()
    assert len(tiers) == 11
    assert tiers[0] == "taxes_and_binding_legal_obligations"
    assert tiers[-1] == "family_education_and_long_term_stewardship"
    # public benefit sits above the final stewardship tier: a line item, not a mood
    assert tiers.index("humanitarian_and_public_benefit_deployment") == 9


def test_full_surplus_funds_in_order(treasury):
    t, ledger = treasury
    tiers = t.waterfall
    alloc = t.allocate(1000.0, {tiers[0]: 300.0, tiers[1]: 200.0, tiers[10]: 100.0})
    assert alloc == {tiers[0]: 300.0, tiers[1]: 200.0, tiers[10]: 100.0}
    assert t.trial_balance() == 0.0


def test_never_skip_upward_to_fund_downward(treasury):
    t, ledger = treasury
    tiers = t.waterfall
    # surplus covers tier 1 but only part of tier 2; tiers below get NOTHING
    alloc = t.allocate(400.0, {tiers[0]: 300.0, tiers[1]: 200.0,
                               tiers[8]: 50.0, tiers[10]: 100.0})
    assert alloc == {tiers[0]: 300.0, tiers[1]: 100.0}
    assert tiers[8] not in alloc and tiers[10] not in alloc
    stops = [r.payload for r in ledger.by_type("event")
             if r.payload.get("type") == "treasury.waterfall_stopped"]
    assert stops and stops[0]["stopped_at"] == tiers[1]
    assert tiers[8] in stops[0]["unfunded_below"]


def test_distributions_only_after_everything_above(treasury):
    t, _ = treasury
    tiers = t.waterfall
    reqs = {tier: 100.0 for tier in tiers}
    # exactly enough for the first ten tiers; stewardship gets zero
    alloc = t.allocate(1000.0, reqs)
    assert tiers[10] not in alloc
    assert sum(alloc.values()) == 1000.0


def test_negative_surplus_refused(treasury):
    t, _ = treasury
    with pytest.raises(TreasuryError, match="deficit"):
        t.allocate(-1.0, {})


def test_unknown_tier_refused(treasury):
    t, _ = treasury
    with pytest.raises(TreasuryError, match="unknown waterfall tiers"):
        t.allocate(100.0, {"vibes_budget": 100.0})


# ---------- double-entry honesty ----------

def test_every_posting_balances(treasury):
    t, _ = treasury
    t.post(debit="operating_cash", credit="revenue", amount_usd=500.0, memo="audit sold")
    t.post(debit="reinvestment_capital", credit="operating_cash",
           amount_usd=200.0, memo="reinvest")
    assert t.trial_balance() == 0.0
    assert t.balance("operating_cash") == 300.0


def test_sign_games_refused(treasury):
    t, _ = treasury
    with pytest.raises(TreasuryError, match="sign games"):
        t.post(debit="a", credit="b", amount_usd=-100.0, memo="hide it")
    with pytest.raises(TreasuryError, match="sign games"):
        t.post(debit="a", credit="b", amount_usd=0.0, memo="nothing")


def test_self_posting_refused(treasury):
    t, _ = treasury
    with pytest.raises(TreasuryError, match="two accounts"):
        t.post(debit="operating_cash", credit="operating_cash",
               amount_usd=100.0, memo="churn")


def test_regenerative_accounts_are_closed_set(treasury):
    t, _ = treasury
    t.post_regenerative("institutional_resilience", amount_usd=50.0,
                        memo="incident became a regression test")
    assert t.balance("institutional_resilience") == 50.0
    with pytest.raises(TreasuryError, match="not a regenerative account"):
        t.post_regenerative("brand_equity_feelings", amount_usd=10.0, memo="x")
    assert set(REGENERATIVE_ACCOUNTS) == {
        "alfonso_sovereignty", "institutional_resilience", "productive_capital",
        "participant_capability", "wider_system_health"}


# ---------- regenerative debt blocks things ----------

def test_open_debt_blocks_promotion_expansion_replication(treasury):
    t, ledger = treasury
    debt = t.record_debt(kind="attention_drain", severity=0.6,
                         description="founder pulled into daily manual triage")
    for action in BLOCKED_WHILE_INDEBTED:
        blocked, why = t.blocks(action)
        assert blocked and "repair before expansion" in why
    # repayment requires evidence, then unblocks
    with pytest.raises(TreasuryError, match="evidence"):
        t.repay_debt(debt.debt_id, evidence="")
    t.repay_debt(debt.debt_id,
                 evidence="triage workflow ratified and running for 14 days; "
                          "founder interventions 12 -> 0")
    for action in BLOCKED_WHILE_INDEBTED:
        blocked, _ = t.blocks(action)
        assert not blocked


def test_unknown_debt_kind_refused(treasury):
    t, _ = treasury
    with pytest.raises(TreasuryError, match="unknown regenerative debt kind"):
        t.record_debt(kind="general_badness", severity=0.5, description="x")


def test_debt_events_name_what_they_block(treasury):
    """The decoration check: a debt record that names nothing it blocks is
    decoration. Every debt event carries the blocked-move list."""
    t, ledger = treasury
    t.record_debt(kind="externalized_risk", severity=0.4,
                  description="unreconciled automation risk shifted to buyer")
    events = [r.payload for r in ledger.by_type("event")
              if r.payload.get("type") == "treasury.debt_recorded"]
    assert events and set(events[0]["blocks"]) == set(BLOCKED_WHILE_INDEBTED)


def test_non_gated_action_not_blocked(treasury):
    t, _ = treasury
    t.record_debt(kind="relationship_damage", severity=0.3, description="x")
    blocked, why = t.blocks("read_ledger")
    assert not blocked and "not gated" in why
