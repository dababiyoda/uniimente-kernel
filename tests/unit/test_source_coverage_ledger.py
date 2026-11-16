"""Section 10: a source-coverage row missing its inspection status fails validation.

The 2026-10-15 ledger is a document. Nothing in that tree checked its fields, so a
row with no inspection status was still a well-formed card. ``greg.source_coverage``
is the check.
"""
from __future__ import annotations

import json
from pathlib import Path

from greg.source_coverage import validate

LEDGER = Path(__file__).resolve().parents[2] / "docs" / "opus-maximus" / "SOURCE_COVERAGE_LEDGER.json"


def _ledger() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def test_a_row_missing_inspection_status_fails_validation():
    doc = _ledger()
    row = dict(doc["records"][0])
    assert "read_status" in row
    del row["read_status"]
    doc["records"] = [row]
    problems = validate(doc)
    assert problems and any("inspection status" in p for p in problems)


def test_the_committed_ledger_records_every_required_field():
    assert validate(_ledger()) == []
