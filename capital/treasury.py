"""Regenerative Treasury: policy-ordered capital metabolism.

Every surplus dollar flows through the declarative waterfall. Expansion
cannot skip obligations or reserves. Double-entry accounting remains
balanced, and regenerative debt blocks promotion, budget expansion, and
replication until evidence of repair exists.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

import yaml

POLICY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "allocation-policy.yaml")

REGENERATIVE_ACCOUNTS = (
    "alfonso_sovereignty",
    "institutional_resilience",
    "productive_capital",
    "participant_capability",
    "wider_system_health",
)

DEBT_KINDS = ("attention_drain", "relationship_damage", "externalized_risk",
              "depleted_capacity")

BLOCKED_WHILE_INDEBTED = ("autonomy_promotion", "budget_expansion", "replication")


class TreasuryError(ValueError):
    """Refused capital movement. The waterfall does not bend."""


def load_waterfall(policy_path: str = POLICY_FILE) -> list[str]:
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
    severity: float
    repaid: bool = False
    repayment_evidence: str | None = None


class RegenerativeTreasury:
    """Execute the allocation waterfall and keep the books balanced."""

    def __init__(self, ledger, *, policy_path: str = POLICY_FILE):
        self.ledger = ledger
        self.waterfall = load_waterfall(policy_path)
        self._postings: list[Posting] = []
        self._balances: dict[str, float] = {}
        self._debts: dict[str, RegenerativeDebt] = {}

    def allocate(self, surplus_usd: float,
                 requirements: dict[str, float]) -> dict[str, float]:
        if surplus_usd < 0:
            raise TreasuryError("a negative surplus is a deficit; the waterfall allocates surplus only")
        unknown = [t for t in requirements if t not in self.waterfall]
        if unknown:
            raise TreasuryError(f"unknown waterfall tiers: {unknown}; the order is law, defined in allocation-policy.yaml")
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

    def post(self, *, debit: str, credit: str, amount_usd: float,
             memo: str) -> Posting:
        if amount_usd <= 0:
            raise TreasuryError("postings move positive amounts; sign games are how consumption hides behind output")
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
        return round(sum(self._balances.values()), 10)

    def post_regenerative(self, account: str, *, amount_usd: float,
                          memo: str) -> Posting:
        if account not in REGENERATIVE_ACCOUNTS:
            raise TreasuryError(f"{account!r} is not a regenerative account; the five are {REGENERATIVE_ACCOUNTS}")
        return self.post(debit=account, credit="operations",
                         amount_usd=amount_usd, memo=memo)

    def record_debt(self, *, kind: str, description: str,
                    severity: float) -> RegenerativeDebt:
        if kind not in DEBT_KINDS:
            raise TreasuryError(f"unknown regenerative debt kind {kind!r}; named kinds: {DEBT_KINDS}")
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
        if action not in BLOCKED_WHILE_INDEBTED:
            return False, f"{action!r} is not gated by regenerative debt"
        open_ = self.open_debts()
        if open_:
            kinds = sorted({d.kind for d in open_})
            return True, (f"{action} blocked: {len(open_)} unrepaid regenerative debt(s) ({', '.join(kinds)}); repair before expansion")
        return False, f"{action} unblocked: no open regenerative debt"

    def repay_debt(self, debt_id: str, *, evidence: str) -> RegenerativeDebt:
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
