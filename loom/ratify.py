"""Phase 4 — human ratification of machine-authored patterns.

Doctrine (SOVEREIGNTY): the machine authors; the human disposes. A
pattern is executable only after ratification by the legal operator,
and ratification binds to the pattern's content hash — editing a
ratified pattern yields a different hash, which is an unratified
pattern. Rejections are preserved forever (negative evidence).
"""
from __future__ import annotations

from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Ratifier:
    def __init__(self, ledger, *, operator: str = "alfonso_lopez"):
        self.ledger = ledger
        self.operator = operator

    def submit(self, pattern) -> str:
        problems = pattern.validate()
        if problems:
            raise ValueError(f"invalid pattern, refusing submission: {problems}")
        h = pattern.hash()
        self.ledger.append("event", {"type": "loom.pattern_submitted",
                                     "pattern_hash": h, "title": pattern.title,
                                     "authored_by": pattern.authored_by, "at": _now()})
        return h

    def decide(self, pattern_hash: str, *, ratified: bool, reason: str,
               ratifier: str | None = None) -> dict:
        ratifier = ratifier or self.operator
        record = {"type": "loom.pattern_ratified" if ratified else "loom.pattern_rejected",
                  "pattern_hash": pattern_hash, "ratifier": ratifier,
                  "reason": reason, "at": _now()}
        self.ledger.append("event", record)
        return record

    def status(self, pattern_hash: str) -> str:
        """ratified | rejected | submitted | unknown — latest decision wins."""
        status = "unknown"
        for rec in self.ledger.by_type("event"):
            p = rec.payload
            if p.get("pattern_hash") != pattern_hash:
                continue
            if p["type"] == "loom.pattern_submitted":
                status = "submitted"
            elif p["type"] == "loom.pattern_ratified":
                status = "ratified"
            elif p["type"] == "loom.pattern_rejected":
                status = "rejected"
        return status

    def is_ratified(self, pattern_hash: str) -> bool:
        return self.status(pattern_hash) == "ratified"
