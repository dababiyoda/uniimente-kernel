"""Every path the Seed Genome intent record and its ledger row cite as evidence or
implementation must exist in the tree. A record that points at nothing would be a
claim without evidence (CANONICAL_EXECUTION_ORDER, evidence standard)."""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
RECORD = json.loads((ROOT / "docs/intent/INTENT-20261013-polyintelligence-seed-genome-v0.1.json").read_text(encoding="utf-8"))
LEDGER = (ROOT / "docs/FOUNDER_INTENT_LEDGER.md").read_text(encoding="utf-8")
PATHISH = re.compile(r"^[\w.\-]+(/[\w.\-*]*)+$")


def _paths(entries):
    for entry in entries:
        head = re.sub(r"\s*\([^()]*\)", "", entry)
        for token in re.split(r",\s*|;\s*|\s+and\s+", head):
            token = token.strip().rstrip(".")
            if PATHISH.match(token) and not token.startswith("http"):
                yield token


def _exists(path: str) -> bool:
    if "*" in path:
        return any(ROOT.glob(path))
    return (ROOT / path.rstrip("/")).exists()


def test_record_evidence_and_implementation_paths_exist():
    paths = list(_paths(RECORD["success_evidence"] + RECORD["implementation_refs"] + RECORD["source_refs"]))
    assert len(paths) >= 12, paths
    missing = [p for p in paths if not _exists(p)]
    assert not missing, missing


def test_ledger_row_paths_exist():
    row = LEDGER.split("| Required field | INTENT-20261013-polyintelligence-seed-genome-v0.1 |", 1)[1].split("\n\n", 1)[0]
    cited = re.findall(r"`([^`\s]+/[^`\s]*)`", row)
    assert cited, "the ledger row cites no paths"
    tests_dir = ROOT / "tests/unit"
    missing = [p for p in cited if not _exists(p)]
    bare = [t for t in re.findall(r"`(test_[\w]+\.py)`", row) if not (tests_dir / t).exists()]
    assert not missing and not bare, (missing, bare)


def test_record_has_the_fifteen_ledger_fields():
    fields = ("intent_id", "statement", "source_refs", "owner", "state", "binding_scope", "constitutional_constraints",
              "success_evidence", "failure_evidence", "dependencies", "conflicts", "next_review_trigger",
              "supersedes", "superseded_by", "implementation_refs")
    assert all(f in RECORD for f in fields)
    assert RECORD["state"] in ("active", "implemented", "deferred", "superseded", "prohibited", "exploratory")
