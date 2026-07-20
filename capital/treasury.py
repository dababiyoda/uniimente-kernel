"""The Regenerative Treasury: capital metabolism, executable.

Doctrine (mission item 55; The Final Plan, Organ 4): every surplus
dollar flows through the waterfall, no exceptions, in policy order.
Capital strengthens the organism before it feeds expansion. Expansion
before reserves is how institutions die of their own growth.

The waterfall order is NOT defined here. It is loaded from
capital/allocation-policy.yaml — the declarative law this module
executes. Fund in order; never skip upward to fund downward.

Double-entry discipline (Layer 39): the institution cannot hide
consumption behind attractive output. Every posting balances; the trial
balance is always zero; a posting that does not balance is refused, not
adjusted.

Every material action posts to the five regenerative accounts
(Alfonso sovereignty, institutional resilience, productive capital,
participant capability, wider system health). Regenerative debt —
attention drain, relationship damage, externalized risk — blocks
autonomy promotion, budget expansion, and replication until repaid.
The accounts exist to BLOCK things; accounting that never blocks
anything is decoration.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field

import yaml

POLICY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "allocation-policy.yaml")

# The five regenerative accounts (The Final Plan, Organ 4).
REGENERATIVE_ACCOUNTS = (
    "alfonso_sovereignty",
    "institutional_resilience",
    "productive_capital",
    "participant_capability",
    "wider_system_health",
)

# Kinds of regenerative debt named by doctrine.
DEBT_KINDS = ("attention_drain", "relationship_damage", "externalized_risk",
              "depleted_capacity")

# Institutional moves an open regenerative debt blocks.
BLOCKED_WHILE_INDEBTED = ("autonomy_promotion", "budget_expansion", "replication")


class TreasuryError(ValueError):
    """Refused capital movement. The waterfall does not bend."""


def load_waterfall(policy_path: str = POLICY_FILE) -> list[str]:
    """The ordered tiers, straight from the declarative policy."""
    with open(policy_path) as f:
        policy = yaml.safe_load(f)
    waterfall = policy["priority_waterfall"]
    return [waterfall[k] for k in sorted(waterfall)]


@dataclass
class Posting:
    posting_id: str
    debit: str
    credit: str
    amount_usd: float
    memo: str


@dataclass
class RegenerativeDebt:
    debt_id: str
    kind: str
    description: str
    severity: float                      # 0..1
    repaid: bool = False
    repayment_evidence: str | None = None


class RegenerativeTreasury:
    """Executes the allocation waterfall and keeps the books honest."""

    def __init__(self, ledger, *, policy_path: str = POLICY_FILE):
        self.ledger = ledger
        self.waterfall = load_waterfall(policy_path)
        self._postings: list[Posting] = []
        self._balances: dict[str, float] = {}
        self._debts: dict[str, RegenerativeDebt] = {}

    # -- the waterfall ----------------------------------------------------
    def allocate(self, surplus_usd: float,
                 requirements: dict[str, float]) -> dict[str, float]:
        """Flow one surplus through the waterfall, in order, no exceptions.

        `requirements` states what each tier currently needs. Unknown tiers
        are refused. A tier receives nothing until every tier above it is
        FULLY funded; the final tier (owner distributions territory) takes
        only what remains after everything above it.
        """
        if surplus_usd < 0:
            raise TreasuryError("a negative surplus is a deficit; the waterfall "
                                "allocates surplus only")
        unknown = [t for t in requirements if t not in self.waterfall]
        if unknown:
            raise TreasuryError(f"unknown waterfall tiers: {unknown}; the order "
                                "is law, defined in allocation-policy.yaml")
        remaining = float(surplus_usd)
        allocation: dict[str, float] = {}
        for tier in self.waterfall:
            need = float(requirements.get(tier, 0.0))
            if need < 0:
                raise TreasuryError(f"tier {tier} requirement may not be negative")
            if need == 0:
                continue
            funded = min(need, remaining)
            if funded > 0:
                allocation[tier] = funded
                self.post(debit=tier, credit="surplus", amount_usd=funded,
                          memo=f"waterfall allocation to {tier}")
                remaining -= funded
            if funded < need:
                # This tier is underfunded: nothing below it receives a cent.
                below = [t for t in self.waterfall[self.waterfall.index(tier) + 1:]
                         if requirements.get(t, 0.0) > 0]
                if below:
                    self.ledger.append("event", {
                        "type": "treasury.waterfall_stopped",
                        "stopped_at": tier, "unfunded_below": below,
                        "shortfall_usd": need - funded})
                break
        self.ledger.append("event", {"type": "treasury.allocated",
                                     "surplus_usd": surplus_usd,
                                     "allocation": allocation,
                                     "unallocated_usd": remaining})
        return allocation

    # -- double-entry books ------------------------------------------------
    def post(self, *, debit: str, credit: str, amount_usd: float,
             memo: str) -> Posting:
        if amount_usd <= 0:
            raise TreasuryError("postings move positive amounts; sign games "
                                "are how consumption hides behind output")
        if debit == credit:
            raise TreasuryError("a posting must move value between two accounts")
        p = Posting(posting_id=str(uuid.uuid4()), debit=debit, credit=credit,
                    amount_usd=float(amount_usd), memo=memo)
        self._postings.append(p)
        self._balances[debit] = self._balances.get(debit, 0.0) + p.amount_usd
        self._balances[credit] = self._balances.get(credit, 0.0) - p.amount_usd
        self.ledger.append("event", {"type": "treasury.posted", "debit": debit,
                                     "credit": credit, "amount_usd": p.amount_usd,
                                     "memo": memo})
        return p

    def balance(self, account: str) -> float:
        return self._balances.get(account, 0.0)

    def trial_balance(self) -> float:
        """Always zero. Every debit has its credit; nothing hides."""
        return round(sum(self._balances.values()), 10)

    def post_regenerative(self, account: str, *, amount_usd: float,
                          memo: str) -> Posting:
        """Material actions post their regenerative effect explicitly."""
        if account not in REGENERATIVE_ACCOUNTS:
            raise TreasuryError(f"{account!r} is not a regenerative account; "
                                f"the five are {REGENERATIVE_ACCOUNTS}")
        return self.post(debit=account, credit="operations",
                         amount_usd=amount_usd, memo=memo)

    # -- regenerative debt: the accounts that block things ------------------
    def record_debt(self, *, kind: str, description: str,
                    severity: float) -> RegenerativeDebt:
        if kind not in DEBT_KINDS:
            raise TreasuryError(f"unknown regenerative debt kind {kind!r}; "
                                f"named kinds: {DEBT_KINDS}")
        if not 0.0 < severity <= 1.0:
            raise TreasuryError("debt severity must be in (0, 1]")
        debt = RegenerativeDebt(debt_id=str(uuid.uuid4()), kind=kind,
                                description=description, severity=severity)
        self._debts[debt.debt_id] = debt
        self.ledger.append("event", {"type": "treasury.debt_recorded",
                                     "debt_id": debt.debt_id, "kind": kind,
                                     "severity": severity,
                                     "description": description,
                                     "blocks": list(BLOCKED_WHILE_INDEBTED)})
        return debt

    def open_debts(self) -> list[RegenerativeDebt]:
        return [d for d in self._debts.values() if not d.repaid]

    def blocks(self, action: str) -> tuple[bool, str]:
        """Does the current debt position block this institutional move?"""
        if action not in BLOCKED_WHILE_INDEBTED:
            return False, f"{action!r} is not gated by regenerative debt"
        open_ = self.open_debts()
        if open_:
            kinds = sorted({d.kind for d in open_})
            return True, (f"{action} blocked: {len(open_)} unrepaid regenerative "
                          f"debt(s) ({', '.join(kinds)}); repair before expansion")
        return False, f"{action} unblocked: no open regenerative debt"

    def repay_debt(self, debt_id: str, *, evidence: str) -> RegenerativeDebt:
        """Repayment requires evidence of repair, not intention to repair."""
        if debt_id not in self._debts:
            raise TreasuryError(f"no debt {debt_id}")
        if not evidence:
            raise TreasuryError("repayment requires evidence of repair")
        debt = self._debts[debt_id]
        debt.repaid = True
        debt.repayment_evidence = evidence
        self.ledger.append("event", {"type": "treasury.debt_repaid",
                                     "debt_id": debt_id, "evidence": evidence})
        return debt
