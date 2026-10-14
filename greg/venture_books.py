"""Venture books: reconciled revenue through the founder's waterfall, and capability transfer (node N7).

Two measurements from the body ledger. GREG moves no money and allocates nothing; these are books.

1. **Books.** Revenue counts only from business cases that closed node N3 (founder-signed, paid to
   the cent by ``business.reconcile``, people did every outward act, appraised VERIFIED, accepted
   by Alfonso). Per venture and currency it runs through the Kernel's own allocation waterfall
   (``capital/treasury.py`` over ``capital/allocation-policy.yaml``) against the per-tier amounts
   Alfonso signed with ``TREASURY_REQUIREMENTS``. Surplus for founder-authorized reinvestment
   exists only after every tier above reinvestment is fully funded; with no signed requirements
   there is no surplus figure at all, not a zero.
2. **Transfer.** A procedure ratified from one venture's verified cases (``greg/sop.py``) and run in
   a second venture is a capability transplant. It counts when at least two of its runs there
   closed N3 and they cost fewer founder interventions, less model spend or less time per verified
   outcome than the runs that taught it, with no run failing appraisal or being rejected.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

from capital.treasury import RegenerativeTreasury, TreasuryError, load_waterfall
from greg.journal import Journal

REINVESTMENT_TIER = "high_return_reinvestment_in_validated_operations"
VENTURE = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
CURRENCY = re.compile(r"^[A-Z]{3}$")
CENT = Decimal("0.01")
MIN_TRANSFER_RUNS = 2


def reinvestable(row: dict) -> bool:
    """True only when a signed waterfall leaves a positive surplus (an amount, never a string match)."""
    value = row.get("surplus_for_reinvestment")
    return value is not None and Decimal(value) > 0


class BooksError(ValueError):
    """A treasury declaration that cannot be read as written."""


def protected_tiers() -> list[str]:
    """Obligation and reserve tiers that must be fully funded before any reinvestment."""
    tiers = load_waterfall()
    return tiers[:tiers.index(REINVESTMENT_TIER)]


def validate_requirements(body: dict) -> dict:
    """``TREASURY_REQUIREMENTS``: Alfonso's per-tier amounts for one venture and currency."""
    if set(body) != {"venture", "currency", "requirements"}:
        raise BooksError("treasury requirements name exactly venture, currency and requirements")
    if not isinstance(body["venture"], str) or not VENTURE.fullmatch(body["venture"]):
        raise BooksError("venture is a short lowercase name (letters, digits, hyphens)")
    if not isinstance(body["currency"], str) or not CURRENCY.fullmatch(body["currency"]):
        raise BooksError("currency is a three-letter code such as USD")
    tiers, requirements = load_waterfall(), body["requirements"]
    if not isinstance(requirements, dict) or not requirements:
        raise BooksError("requirements map waterfall tiers to amounts")
    unknown = sorted(set(requirements) - set(tiers))
    if unknown:
        raise BooksError(f"unknown waterfall tiers {unknown}; the order is capital/allocation-policy.yaml")
    clean = {}
    for tier, amount in requirements.items():
        try:
            value = Decimal(str(amount))
        except InvalidOperation:
            raise BooksError(f"{tier}: {amount!r} is not an amount") from None
        if not value.is_finite() or value < 0 or value != value.quantize(CENT):
            raise BooksError(f"{tier}: an amount is zero or more, to the cent")
        clean[tier] = str(value.quantize(CENT))
    return {"venture": body["venture"], "currency": body["currency"],
            "requirements": {t: clean[t] for t in tiers if t in clean}}


def declared(journal: Journal) -> dict:
    """(venture, currency) -> the latest signed requirements."""
    return {(e.payload["venture"], e.payload["currency"]): e.payload
            for e in journal.replay("treasury.requirements")}


def _closed_cases(journal: Journal) -> dict:
    """mission_id -> (venture, currency, amount) for business cases that closed N3."""
    from greg.path import business_loop_closed
    specs = {e.payload["mission_id"]: e.payload["spec"] for e in journal.replay("mission.registered")}
    out = {}
    for case in business_loop_closed(journal)["cases"]:
        spec = specs[case["mission_id"]]
        paid = next(c for c in spec["success_checks"] if c["sensor"].get("capability") == "business.reconcile")
        params = paid["sensor"]["params"]
        out[case["mission_id"]] = (spec.get("venture"), str(params["currency"]).upper(),
                                   Decimal(str(params["amount"])))
    return out


class _Sink:
    """The treasury's ledger interface, kept in memory: these are projections, not postings."""

    def __init__(self):
        self.events = []

    def append(self, kind, payload):
        self.events.append(payload)


def books(journal: Journal) -> list[dict]:
    """Per venture and currency: verified revenue, the waterfall, and any reinvestable surplus."""
    cases, signed = _closed_cases(journal), declared(journal)
    revenue = {}
    for mid, (venture, currency, amount) in cases.items():
        if venture:
            entry = revenue.setdefault((venture, currency), {"revenue": Decimal(0), "cases": []})
            entry["revenue"] += amount
            entry["cases"].append(mid)
    protected = protected_tiers()
    out = []
    for key in sorted(set(revenue) | set(signed)):
        venture, currency = key
        total = revenue.get(key, {"revenue": Decimal(0), "cases": []})
        row = {"venture": venture, "currency": currency, "verified_revenue": str(total["revenue"].quantize(CENT)),
               "cases": sorted(total["cases"])}
        if key not in signed:
            row.update(surplus_for_reinvestment=None,
                       why="no signed TREASURY_REQUIREMENTS: obligations and reserves are unknown, so no surplus "
                           "can be stated")
            out.append(row)
            continue
        requirements = {t: Decimal(v) for t, v in signed[key]["requirements"].items()}
        unprotected = [t for t in requirements if t not in protected]
        treasury = RegenerativeTreasury(_Sink())
        try:
            allocation = treasury.allocate(float(total["revenue"]),
                                           {t: float(v) for t, v in requirements.items()})
        except TreasuryError as exc:
            row.update(surplus_for_reinvestment=None, why=str(exc))
            out.append(row)
            continue
        funded = {t: Decimal(str(v)).quantize(CENT) for t, v in allocation.items()}
        short = {t: str((requirements[t] - funded.get(t, Decimal(0))).quantize(CENT))
                 for t in protected if requirements.get(t, Decimal(0)) > funded.get(t, Decimal(0))}
        held = sum((requirements.get(t, Decimal(0)) for t in protected), Decimal(0))
        # The waterfall funds protected tiers first, so any shortfall already means revenue < held.
        surplus = max(total["revenue"] - held, Decimal(0))
        row.update(requirements_signed={t: str(v) for t, v in requirements.items()},
                   funded={t: str(v) for t, v in funded.items()}, protected_shortfall=short,
                   surplus_for_reinvestment=str(surplus.quantize(CENT)),
                   requirements_below_reinvestment=unprotected)
        if short:
            row["why"] = "obligations or reserves are not fully funded; nothing is available to reinvest"
        out.append(row)
    return out


def _per_outcome(rows: list, field: str):
    values = [r[field] for r in rows if r.get(field) is not None]
    return round(sum(values) / len(values), 4) if values and len(values) == len(rows) else None


def transfers(journal: Journal) -> list[dict]:
    """Ratified procedures taught in one venture and run in another, with what the transplant cost."""
    from greg import sop
    specs = {e.payload["mission_id"]: e.payload["spec"] for e in journal.replay("mission.registered")}
    closed = _closed_cases(journal)
    out = []
    for entry in sop.trend(journal)["procedures"]:
        if entry["state"] != "RATIFIED":
            continue
        taught = entry["baseline"]["missions"]
        origin = {specs[r["mission_id"]].get("venture") for r in taught}
        if len(origin) != 1 or None in origin:
            continue
        source = origin.pop()
        by_venture = {}
        for r in entry["sop_runs"]["missions"]:
            target = specs[r["mission_id"]].get("venture")
            if target and target != source and r["mission_id"] in closed:
                by_venture.setdefault(target, []).append(r)
        for target, runs in sorted(by_venture.items()):
            measures = {}
            for field in ("interventions", "model_cost_usd", "hours_to_close"):
                before, after = _per_outcome(taught, field), _per_outcome(runs, field)
                measures[field] = {"taught_in_" + source: before, "run_in_" + target: after}
            lower = [f for f, m in measures.items() if None not in m.values()
                     and list(m.values())[1] < list(m.values())[0]]
            higher = [f for f, m in measures.items() if None not in m.values()
                      and list(m.values())[1] > list(m.values())[0] and f != "hours_to_close"]
            quality = not entry["sop_runs"]["quality_failures"]
            row = {"procedure_id": entry["procedure_id"], "from_venture": source, "to_venture": target,
                   "runs": len(runs), "missions": [r["mission_id"] for r in runs], "per_outcome": measures,
                   "lower": lower, "quality_held": quality,
                   "faster_or_cheaper": bool(lower) and not higher and quality and len(runs) >= MIN_TRANSFER_RUNS}
            if not row["faster_or_cheaper"]:
                row["why_not"] = ([f"{len(runs)} of {MIN_TRANSFER_RUNS} closed runs in {target}"]
                                  if len(runs) < MIN_TRANSFER_RUNS else []) + \
                                 (["no measure fell"] if not lower else []) + \
                                 ([f"{', '.join(higher)} rose"] if higher else []) + \
                                 (["quality not held"] if not quality else [])
            out.append(row)
    return out
