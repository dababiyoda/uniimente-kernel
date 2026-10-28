"""#39 Double-entry accounting: every asset, obligation and capital movement recorded consistently.

Append-only, hash-chained journal of balanced entries in integer minor units. An
entry is refused unless debits equal credits, it has at least two lines, every
account is declared, and one currency is used. Nothing is edited or deleted: a
mistake is corrected by a reversal entry that names what it reverses. The
accounting equation (Assets = Liabilities + Equity + Revenue - Expenses) is
checked on every trial balance.

These are records. Posting an entry moves no money and grants no spending
authority; payments remain behind the Consequence Gate.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

TYPES = ("asset", "liability", "equity", "revenue", "expense")
DEBIT_NORMAL = ("asset", "expense")


class AccountingError(RuntimeError):
    """Unbalanced, malformed or unknown-account entry; broken journal chain."""


def _file(root: Path, name: str) -> Path:
    Path(root).mkdir(parents=True, exist_ok=True)
    return Path(root) / name


def _hash(record: dict) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()


def chart(root: Path) -> dict:
    path = _file(root, "chart.json")
    return json.loads(path.read_text()) if path.exists() else {"currency": None, "accounts": {}}


def open_account(root: Path, account: str, kind: str, currency: str) -> dict:
    if kind not in TYPES:
        raise AccountingError(f"account type must be one of {TYPES}")
    book = chart(root)
    if book["currency"] not in (None, currency):
        raise AccountingError(f"book currency is {book['currency']}; multi-currency is not supported")
    if account in book["accounts"] and book["accounts"][account] != kind:
        raise AccountingError(f"{account} already exists as {book['accounts'][account]}")
    book["currency"] = currency
    book["accounts"][account] = kind
    _file(root, "chart.json").write_text(json.dumps(book, sort_keys=True, indent=1))
    return book


def journal(root: Path) -> list[dict]:
    path = _file(root, "journal.jsonl")
    entries = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    previous = None
    for entry in entries:
        body = {k: v for k, v in entry.items() if k != "hash"}
        if entry["prev"] != previous or _hash(body) != entry["hash"]:
            raise AccountingError(f"journal chain broken at entry {entry.get('id')}")
        previous = entry["hash"]
    return entries


def post(root: Path, *, date: str, memo: str, lines: list[dict], currency: str, reverses: str | None = None) -> dict:
    book, entries = chart(root), journal(root)
    if currency != book["currency"]:
        raise AccountingError(f"entry currency {currency} differs from book currency {book['currency']}")
    if len(lines) < 2:
        raise AccountingError("an entry needs at least two lines")
    debit = credit = 0
    for line in lines:
        if line.get("account") not in book["accounts"]:
            raise AccountingError(f"unknown account {line.get('account')!r}")
        d, c = line.get("debit", 0), line.get("credit", 0)
        if not (isinstance(d, int) and isinstance(c, int)) or d < 0 or c < 0 or (d > 0) == (c > 0):
            raise AccountingError("each line is exactly one positive integer debit or credit (minor units)")
        debit, credit = debit + d, credit + c
    if debit != credit:
        raise AccountingError(f"unbalanced: debits {debit} != credits {credit}")
    if reverses is not None and reverses not in {e["id"] for e in entries}:
        raise AccountingError(f"cannot reverse unknown entry {reverses}")
    if reverses is not None and any(e.get("reverses") == reverses for e in entries):
        raise AccountingError(f"{reverses} is already reversed")
    body = {"id": f"je-{len(entries) + 1}", "date": date, "memo": memo, "currency": currency,
            "lines": [{"account": l["account"], "debit": l.get("debit", 0), "credit": l.get("credit", 0)} for l in lines],
            "reverses": reverses, "prev": entries[-1]["hash"] if entries else None}
    entry = dict(body, hash=_hash(body))
    with open(_file(root, "journal.jsonl"), "a") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def reverse(root: Path, entry_id: str, *, date: str, memo: str) -> dict:
    original = next((e for e in journal(root) if e["id"] == entry_id), None)
    if original is None:
        raise AccountingError(f"unknown entry {entry_id}")
    swapped = [{"account": l["account"], "debit": l["credit"], "credit": l["debit"]} for l in original["lines"]]
    return post(root, date=date, memo=f"reversal of {entry_id}: {memo}", lines=swapped,
                currency=original["currency"], reverses=entry_id)


def trial_balance(root: Path) -> dict:
    book = chart(root)
    balances = {a: 0 for a in book["accounts"]}
    for entry in journal(root):
        for line in entry["lines"]:
            sign = 1 if book["accounts"][line["account"]] in DEBIT_NORMAL else -1
            balances[line["account"]] += sign * (line["debit"] - line["credit"])
    totals = {t: sum(v for a, v in balances.items() if book["accounts"][a] == t) for t in TYPES}
    equation = totals["asset"] == totals["liability"] + totals["equity"] + totals["revenue"] - totals["expense"]
    return {"currency": book["currency"], "balances": balances, "totals": totals, "equation_holds": equation}


QUERY_OPS = {"trial_balance": lambda a, r: trial_balance(r),
             "journal": lambda a, r: {"entries": journal(r)}}
APPLY_OPS = {"open_account": lambda a, r: open_account(r, a["account"], a["type"], a["currency"]),
             "post": lambda a, r: post(r, date=a["date"], memo=a["memo"], lines=a["lines"], currency=a["currency"]),
             "reverse": lambda a, r: reverse(r, a["entry"], date=a["date"], memo=a["memo"])}


def exercise(root: Path) -> dict:
    for account, kind in (("cash", "asset"), ("receivable", "asset"), ("deferred_revenue", "liability"),
                          ("owner_equity", "equity"), ("service_revenue", "revenue"), ("compute_expense", "expense")):
        open_account(root, account, kind, "USD")
    post(root, date="2026-09-27", memo="founder capital", currency="USD",
         lines=[{"account": "cash", "debit": 100000}, {"account": "owner_equity", "credit": 100000}])
    post(root, date="2026-09-27", memo="compute", currency="USD",
         lines=[{"account": "compute_expense", "debit": 2500}, {"account": "cash", "credit": 2500}])
    wrong = post(root, date="2026-09-27", memo="invoice (wrong amount)", currency="USD",
                 lines=[{"account": "receivable", "debit": 9000}, {"account": "service_revenue", "credit": 9000}])
    reverse(root, wrong["id"], date="2026-09-27", memo="amount was 900.00 not 90.00")
    post(root, date="2026-09-27", memo="invoice", currency="USD",
         lines=[{"account": "receivable", "debit": 90000}, {"account": "service_revenue", "credit": 90000}])
    refusals = {}
    for label, lines, currency in (
            ("unbalanced", [{"account": "cash", "debit": 100}, {"account": "owner_equity", "credit": 99}], "USD"),
            ("unknown_account", [{"account": "crypto", "debit": 1}, {"account": "cash", "credit": 1}], "USD"),
            ("other_currency", [{"account": "cash", "debit": 1}, {"account": "owner_equity", "credit": 1}], "EUR"),
            ("float_amount", [{"account": "cash", "debit": 1.5}, {"account": "owner_equity", "credit": 1.5}], "USD")):
        try:
            post(root, date="2026-09-27", memo=label, lines=lines, currency=currency)
            refusals[label] = False
        except AccountingError:
            refusals[label] = True
    try:
        reverse(root, wrong["id"], date="2026-09-27", memo="again")
        double_reversal_refused = False
    except AccountingError:
        double_reversal_refused = True
    tb = trial_balance(root)
    tampered = (Path(root) / "journal.jsonl").read_text().replace('"debit": 2500', '"debit": 250')
    (Path(root) / "journal.jsonl").write_text(tampered)
    try:
        journal(root)
        tamper_detected = False
    except AccountingError:
        tamper_detected = True
    return {"totals": tb["totals"], "equation_holds": tb["equation_holds"], "refusals": refusals,
            "double_reversal_refused": double_reversal_refused, "tamper_detected": tamper_detected}
