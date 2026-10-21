"""One business case, run as a founder-signed GREG mission (developmental node N3).

The Kernel's commercial loop (business/commercial_loop.py) fixes the order a customer case
must close in: problem -> buyer -> offer -> payment -> delivery -> customer outcome ->
retention or termination. This module makes that order a durable GREG mission on the body:

* GREG drafts the offer inside the mission workspace (an internal write);
* every act that reaches a person outside the body (sending the offer, collecting payment,
  delivering, asking the buyer to confirm the outcome) is ``human.*`` work: GREG raises one
  costed ask, contacts and pays no one, and continues only when it observes the evidence;
* payment is never taken on the buyer's word or GREG's: ``business.reconcile`` matches the
  signed price, currency and case reference against a statement Alfonso exports from his
  payment account, exactly, to the cent, and refuses an ambiguous match;
* the settlement record is written only after payment, delivery and the buyer's confirmation
  are all observed (strategy preconditions), and the separate appraiser re-checks that order.

Mechanism sources (open-source harvest, DISCOVER only): exact-amount, single-posting matching
as plain-text double-entry tools (beancount, hledger) reconcile statements; implemented with
the Python standard library (csv, decimal), so no dependency is added. Vendor export formats
are not assumed: the signed mission names which columns hold amount, currency and reference.
"""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
from pathlib import Path

from greg.capabilities import MAX_READ_BYTES, CapabilityError, InvocationContext, _inside

DEFAULT_COLUMNS = {"amount": "amount", "currency": "currency", "reference": "description"}
_STRIP = str.maketrans("", "", " ,$€£¥ ")


def parse_amount(text: str, *, minor_units: bool = False) -> Decimal | None:
    """'1,234.50', '$99', '(12.00)' -> Decimal; None when it is not a number."""
    raw = str(text or "").strip()
    negative = raw.startswith("(") and raw.endswith(")")
    raw = raw.strip("()").translate(_STRIP)
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    if not value.is_finite():
        return None
    value = -value if negative else value
    return value / 100 if minor_units else value


def reconcile(params: dict, ctx: InvocationContext) -> dict:
    """Match exactly one statement row to the signed price, currency and case reference."""
    path = _inside(Path(params["path"]), ctx.read_roots + (ctx.workspace,))
    expected = parse_amount(str(params["amount"]))
    if expected is None or expected <= 0:
        raise CapabilityError("the signed amount must be a positive number")
    currency = str(params["currency"]).strip().upper()
    reference = str(params["reference"]).strip()
    if len(reference) < 6:
        raise CapabilityError("the case reference must be at least 6 characters, or unrelated rows could match")
    columns = {**DEFAULT_COLUMNS, **(params.get("columns") or {})}
    if not path.is_file():   # no statement yet is a measurement of the world, not a sensor failure
        return {"path": str(path), "exists": False, "matched": False, "matches": 0, "rows_read": 0,
                "detail": "no statement exported yet"}
    data = path.read_bytes()
    if len(data) > MAX_READ_BYTES:
        raise CapabilityError("statement exceeds read ceiling")
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig", errors="replace"))))
    missing = [c for c in columns.values() if rows and c not in rows[0]]
    if missing:
        return {"path": str(path), "exists": True, "matched": False, "matches": 0, "rows_read": len(rows),
                "sha256": hashlib.sha256(data).hexdigest(),
                "detail": f"statement lacks the signed columns {missing}; header is {sorted(rows[0])}"}
    minor = bool(params.get("minor_units"))
    hits, near = [], []
    for index, row in enumerate(rows):
        if reference not in (row.get(columns["reference"]) or ""):
            continue
        amount = parse_amount(row.get(columns["amount"]), minor_units=minor)
        same_currency = (row.get(columns["currency"]) or "").strip().upper() == currency
        if amount == expected and same_currency:
            hits.append((index, row))
        else:
            near.append({"row": index + 2, "amount": str(amount), "currency": row.get(columns["currency"])})
    result = {"path": str(path), "exists": True, "rows_read": len(rows), "matches": len(hits),
              "sha256": hashlib.sha256(data).hexdigest(), "expected": {"amount": str(expected),
                                                                     "currency": currency, "reference": reference}}
    if len(hits) == 1:
        index, row = hits[0]
        return {**result, "matched": True, "row": index + 2,
                "row_sha256": hashlib.sha256(repr(sorted(row.items())).encode()).hexdigest(),
                "detail": f"one posting of {expected} {currency} carries {reference}"}
    if hits:
        return {**result, "matched": False, "rows": [i + 2 for i, _ in hits],
                "detail": f"ambiguous: {len(hits)} postings match; GREG will not pick one or count twice"}
    return {**result, "matched": False, "near_misses": near[:5],
            "detail": ("rows carry the reference but differ in amount or currency" if near
                       else "no posting carries the case reference")}
