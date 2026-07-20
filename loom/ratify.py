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
    """Hash-bound ratification of any machine-authored artifact that
    exposes validate()/hash()/title/authored_by. `kind` names the artifact
    family in ledger events (loom.pattern, foundry.charter, business.genome)."""

    def __init__(self, ledger, *, operator: str = "alfonso_lopez",
                 kind: str = "loom.pattern"):
        self.ledger = ledger
        self.operator = operator
        self.kind = kind

    def submit(self, pattern) -> str:
        problems = pattern.validate()
        if problems:
            raise ValueError(f"invalid pattern, refusing submission: {problems}")
        h = pattern.hash()
        self.ledger.append("event", {"type": f"{self.kind}_submitted",
                                     "pattern_hash": h, "title": pattern.title,
                                     "authored_by": pattern.authored_by, "at": _now()})
        return h

    def decide(self, pattern_hash: str, *, ratified: bool, reason: str,
               ratifier: str | None = None) -> dict:
        ratifier = ratifier or self.operator
        record = {"type": f"{self.kind}_ratified" if ratified else f"{self.kind}_rejected",
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
            if p["type"] == f"{self.kind}_submitted":
                status = "submitted"
            elif p["type"] == f"{self.kind}_ratified":
                status = "ratified"
            elif p["type"] == f"{self.kind}_rejected":
                status = "rejected"
        return status

    def is_ratified(self, pattern_hash: str) -> bool:
        return self.status(pattern_hash) == "ratified"
