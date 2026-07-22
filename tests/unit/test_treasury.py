"""Tests for policy-ordered capital metabolism and regenerative debt."""
import os

import pytest

from compiler.ucl_compiler import compile_constitution
from provenance.ledger import EvidenceLedger
from capital.treasury import RegenerativeTreasury, TreasuryError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def treasury():
    constitution = compile_constitution(ROOT)
    ledger = EvidenceLedger(constitution.constitution_hash)
    return RegenerativeTreasury(ledger), ledger


def test_waterfall_funds_in_policy_order(treasury):
    t, _ = treasury
    tiers = t.waterfall
    allocation = t.allocate(600.0, {tiers[0]: 300.0, tiers[1]: 200.0, tiers[10]: 100.0})
    assert allocation == {tiers[0]: 300.0, tiers[1]: 200.0, tiers[10]: 100.0}
    assert t.trial_balance() == 0.0


def test_underfunded_tier_blocks_lower_tiers(treasury):
    t, ledger = treasury
    tiers = t.waterfall
    allocation = t.allocate(350.0, {tiers[0]: 300.0, tiers[1]: 200.0, tiers[10]: 100.0})
    assert tiers[10] not in allocation
    events = [r.payload for r in ledger.by_type("event")
              if r.payload.get("type") == "treasury.waterfall_stopped"]
    assert events and events[0]["stopped_at"] == tiers[1]


@pytest.mark.parametrize("kwargs", [
    {"debit": "a", "credit": "b", "amount_usd": 0.0, "memo": "zero"},
    {"debit": "a", "credit": "b", "amount_usd": -1.0, "memo": "sign game"},
    {"debit": "a", "credit": "a", "amount_usd": 1.0, "memo": "self posting"},
])
def test_invalid_postings_fail_closed(treasury, kwargs):
    t, _ = treasury
    with pytest.raises(TreasuryError):
        t.post(**kwargs)


def test_regenerative_debt_blocks_expansion_until_repaired(treasury):
    t, ledger = treasury
    debt = t.record_debt(kind="externalized_risk", description="risk shifted", severity=0.4)
    for action in ("autonomy_promotion", "budget_expansion", "replication"):
        assert t.blocks(action)[0]
    with pytest.raises(TreasuryError, match="evidence"):
        t.repay_debt(debt.debt_id, evidence="")
    t.repay_debt(debt.debt_id, evidence="risk reconciled and regression test added")
    for action in ("autonomy_promotion", "budget_expansion", "replication"):
        assert not t.blocks(action)[0]


def test_unknown_tier_is_refused(treasury):
    t, _ = treasury
    with pytest.raises(TreasuryError, match="unknown waterfall tiers"):
        t.allocate(100.0, {"founder_whim": 100.0})
