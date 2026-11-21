"""Read-only observation of a construction's realized outcome from a founder-placed record (``world.observe.*``).

Settlement prepares a dispute's verification task only for a capability that declares ``world.observe.<objective>``
(greg/cognition/settlement.py ``_observers``). These built-ins are the first real ones. Each reads one file, the
outcome records the founder exports from the system of record (a ledger, a time clock, a delivery log) into a read
root under the fixed name ``greg-outcome-records.csv``, and returns the realized value one row states for one answer.

The reading is evidence of what the record says, bound to the file's SHA-256; it never decides anything. Every value
is the record's claim; the founder still signs a REALIZATION naming the reading, and a dispute still needs a
resolution. They start VERIFIED, not ATTACHED: a body reads no outcome record until the founder attaches one.
"""
from __future__ import annotations

import csv
import hashlib
import io
import math
from pathlib import Path

RECORDS_NAME = "greg-outcome-records.csv"
COLUMNS = ("receipt", "objective", "realized")          # required; ``reference`` is optional
# the objectives settlement's OBJECTIVES promise (pinned by tests/unit/test_greg_outcome_records.py)
OBSERVABLE_OBJECTIVES = ("profit", "staffed", "size", "cost")


def observe(params, ctx) -> dict:
    """The realized ``objective`` the record states for ``receipt``, or the reason no value can be read: no record
    file, no row for this answer, rows that disagree, or a value that is not a finite number."""
    from greg.capabilities import CapabilityError, bounded_read
    receipt, objective = params.get("receipt"), params.get("objective")
    if not isinstance(receipt, str) or not receipt or objective not in OBSERVABLE_OBJECTIVES:
        raise CapabilityError("records.observe needs a receipt and one of the observable objectives")
    for root in ctx.read_roots:
        path = Path(root) / RECORDS_NAME
        if path.is_symlink() or not path.is_file():
            continue
        data = bounded_read(path, "outcome record exceeds read ceiling")
        digest = hashlib.sha256(data).hexdigest()
        base = {"record": str(path), "sha256": digest, "receipt": receipt, "objective": objective}
        try:
            rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
        except (UnicodeDecodeError, csv.Error) as exc:
            return {**base, "exists": True, "why": f"the record is not readable CSV: {exc}"}
        if rows and not set(COLUMNS) <= set(rows[0]):
            return {**base, "exists": True, "why": f"the record lacks the columns {list(COLUMNS)}"}
        hits = [(n, r) for n, r in enumerate(rows, start=2)
                if (r.get("receipt") or "").strip() == receipt and (r.get("objective") or "").strip() == objective]
        if not hits:
            return {**base, "exists": True, "why": "the record has no row for this answer and objective"}
        values = []
        for line, row in hits:
            try:
                value = float((row.get("realized") or "").replace(",", ""))
            except ValueError:
                value = math.nan
            if not math.isfinite(value):
                return {**base, "exists": True, "why": f"line {line} states no finite realized value"}
            values.append((line, value, (row.get("reference") or "").strip()))
        if len({v for _, v, _ in values}) > 1:
            return {**base, "exists": True, "conflicting": [{"line": l, "realized": v} for l, v, _ in values],
                    "why": "the record's rows for this answer disagree; it decides nothing"}
        line, value, reference = values[-1]
        return {**base, "exists": True, "realized": value, "line": line, "reference": reference,
                "nature": "what the record states, bound to its digest; the founder's signed report decides"}
    return {"exists": False, "receipt": receipt, "objective": objective,
            "why": f"no {RECORDS_NAME} in the body's read roots"}


def builtin_entries(manifest_type, lazy) -> dict:
    """One read-only observer per observable objective, registered with every other built-in."""
    source = {"source": "uniimente-kernel/greg/outcome_records.py",
              "mechanism_from": "greg/capabilities.py fs.read (bounded, digest-bound read inside read roots)"}
    return {f"records.observe.{objective}": (manifest_type(
        capability_id=f"records.observe.{objective}", version="1.0.0", provider="greg-builtin",
        function=f"world.observe.{objective}",
        description=f"Read the realized {objective} one answer achieved from the founder-placed {RECORDS_NAME}",
        route="internal", consequence_class="read_only", target_prefix="records:",
        inputs={"receipt": "str", "objective": "str"},
        outputs={"realized": "float", "record": "str", "sha256": "str", "line": "int", "reference": "str"},
        filesystem="read-scoped", retry_safe=True, strengthens=("proof", "settlement"),
        tests=("tests/unit/test_greg_outcome_records.py",), provenance=source),
        lazy("greg.outcome_records", "observe")) for objective in OBSERVABLE_OBJECTIVES}
