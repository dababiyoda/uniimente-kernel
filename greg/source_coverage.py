"""Validate the source-coverage ledger (directive section 10).

The ledger's own field names are the section's record:

- ``source`` and ``sha256`` — the reference
- ``date_evidence`` — the date or version, including an explicit statement that none is in the text
- ``read_status`` — inspection status: READ (inspected), PARTIAL (partially inspected), UNAVAILABLE
- ``manifest_topic`` — relevance
- ``intent_candidates`` — founder intent drawn from the source
- ``summary`` — what the source claims, including implementation claims
- ``contradictions`` — contradictions with doctrine or with itself; an empty list means the card recorded none
- ``reliability_tier`` — evidence tier
- ``gaps`` — unresolved questions

A missing field is a failed validation. An empty list is a recorded absence, not a missing field.
"""
from __future__ import annotations

import re

INSPECTION_STATUS = {
    "READ": "inspected",
    "PARTIAL": "partially_inspected",
    "UNAVAILABLE": "unavailable",
}
_SHA = re.compile(r"^[0-9a-f]{64}$")


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate(doc: dict) -> list[str]:
    """Problems in one ledger document. ``[]`` means every required field is present and typed."""
    if not isinstance(doc, dict):
        return ["ledger is not an object"]
    records = doc.get("records")
    if not isinstance(records, list) or not records:
        return ["ledger records must be a non-empty list"]
    problems = []
    for i, row in enumerate(records, 1):
        where = f"record {i}"
        if not isinstance(row, dict):
            problems.append(f"{where}: not an object")
            continue
        name = row.get("source") if _text(row.get("source")) else None
        if name:
            where = f"record {i} ({name})"
        else:
            problems.append(f"{where}: reference (source) is missing")
        sha = row.get("sha256")
        if not isinstance(sha, str) or not _SHA.match(sha):
            problems.append(f"{where}: stable reference (sha256) is missing")
        if not _text(row.get("date_evidence")):
            problems.append(f"{where}: version (date_evidence) is missing")
        status = row.get("read_status")
        if status not in INSPECTION_STATUS:
            problems.append(f"{where}: inspection status is missing "
                            f"(read_status is {', '.join(INSPECTION_STATUS)})")
        if not _text(row.get("manifest_topic")):
            problems.append(f"{where}: relevance (manifest_topic) is missing")
        intent = row.get("intent_candidates")
        if not isinstance(intent, list):
            problems.append(f"{where}: founder intent (intent_candidates) is missing")
        if not _text(row.get("summary")):
            problems.append(f"{where}: claims (summary) are missing")
        contradictions = row.get("contradictions")
        if not isinstance(contradictions, list) or any(
                not (isinstance(c, dict) or _text(c)) for c in contradictions):
            problems.append(f"{where}: contradictions are missing")
        tier = row.get("reliability_tier")
        if not (_text(tier) or isinstance(tier, dict) and tier):
            problems.append(f"{where}: evidence tier (reliability_tier) is missing")
        gaps = row.get("gaps")
        if not isinstance(gaps, list) or any(not _text(g) for g in gaps):
            problems.append(f"{where}: open questions (gaps) are missing")
    return problems
