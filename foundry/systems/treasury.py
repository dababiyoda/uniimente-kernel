"""#55 Regenerative Treasury: surplus routed by a versioned policy, reconciled to the books.

The Kernel's RegenerativeTreasury (capital/treasury.py) runs the declarative
waterfall (obligations and reserves before reinvestment, productive assets,
public benefit and owner distributions). The Foundry adds what makes it an
institution's treasury rather than an allocator:

* the waterfall policy is committed as a versioned object (#3) with a reason,
  so every allocation names the policy version that governed it;
* every treasury posting is mirrored into the double-entry journal (#39) in
  integer cents, and the two books must reconcile to the cent;
* open regenerative debt blocks budget expansion until repaid with evidence.

Allocation is bookkeeping: nothing here moves money.
"""
from __future__ import annotations

from pathlib import Path

from foundry.systems import accounting, versions


def _cents(amount: float) -> int:
    return int(round(amount * 100))


def run(root: Path, surplus_usd: float, requirements: dict) -> dict:
    from capital.treasury import RegenerativeTreasury
    from provenance.ledger import EvidenceLedger
    root = Path(root)
    ledger = EvidenceLedger("sha256:" + "0" * 64)
    treasury = RegenerativeTreasury(ledger)
    try:
        policy = versions.commit(root / "policy", "treasury-waterfall", {"waterfall": treasury.waterfall},
                                 reason="waterfall in force for this allocation", evidence=["capital/allocation-policy.yaml"])
    except versions.VersionError:
        policy = versions.history(root / "policy", "treasury-waterfall")[0]
    books = root / "books"
    for account, kind in [("surplus", "asset"), ("retained_surplus", "equity")] + [(t, "asset") for t in treasury.waterfall]:
        accounting.open_account(books, account, kind, "USD")
    accounting.post(books, date="allocation", memo="surplus received", currency="USD",
                    lines=[{"account": "surplus", "debit": _cents(surplus_usd)},
                           {"account": "retained_surplus", "credit": _cents(surplus_usd)}])
    allocation = treasury.allocate(surplus_usd, requirements)
    for tier, amount in allocation.items():
        accounting.post(books, date="allocation", memo=f"waterfall {tier} under policy v{policy['n']}", currency="USD",
                        lines=[{"account": tier, "debit": _cents(amount)}, {"account": "surplus", "credit": _cents(amount)}])
    tb = accounting.trial_balance(books)
    reconciled = all(tb["balances"][tier] == _cents(treasury.balance(tier)) for tier in allocation)
    debt = treasury.record_debt(kind="attention_drain", description="founder reviewed allocations manually for 3 weeks",
                                severity=0.4)
    blocked, _ = treasury.blocks("budget_expansion")
    try:
        treasury.repay_debt(debt.debt_id, evidence="")
        evidenceless_repayment_refused = False
    except Exception:
        evidenceless_repayment_refused = True
    treasury.repay_debt(debt.debt_id, evidence="automated allocation review shipped; founder time 0.5h/week")
    unblocked_after_repair = not treasury.blocks("budget_expansion")[0]
    return {"policy_version": policy["n"], "allocation": allocation, "reconciled_to_the_cent": reconciled,
            "books_balance": tb["equation_holds"], "unallocated_cents": tb["balances"]["surplus"],
            "budget_expansion_blocked_by_debt": blocked, "evidenceless_repayment_refused": evidenceless_repayment_refused,
            "unblocked_after_evidenced_repair": unblocked_after_repair, "treasury_trial_balance": treasury.trial_balance()}


QUERY_OPS: dict = {}
APPLY_OPS = {"allocate": lambda a, r: run(r, float(a["surplus_usd"]), a["requirements"])}


def exercise(root) -> dict:
    from capital.treasury import RegenerativeTreasury, TreasuryError
    from provenance.ledger import EvidenceLedger
    tiers = RegenerativeTreasury(EvidenceLedger("sha256:" + "0" * 64)).waterfall
    requirements = {tiers[0]: 3000.0, tiers[1]: 2500.0, tiers[2]: 4000.0, tiers[-1]: 5000.0}
    result = run(root, 8000.0, requirements)
    try:
        run(Path(root) / "second", 100.0, {"skip_the_line": 10.0})
        unknown_tier_refused = False
    except TreasuryError:
        unknown_tier_refused = True
    return dict(result, waterfall=tiers, unknown_tier_refused=unknown_tier_refused,
                last_tier_starved_first=tiers[-1] not in result["allocation"])
