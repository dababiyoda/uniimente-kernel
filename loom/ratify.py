"""Human ratification of machine-authored artifacts.

The machine authors; the human disposes. An artifact is executable only
after ratification by the legal operator, and ratification binds to the
artifact's content hash. Rejections remain negative evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Ratifier:
    """Hash-bound ratification for any artifact exposing
    validate(), hash(), title, and authored_by. `kind` names its ledger
    event family without changing the default Loom behavior."""

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
