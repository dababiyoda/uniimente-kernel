"""GREG's view of the one canonical history: EventSpine over the EvidenceLedger.

No second store. Every GREG fact is a namespaced ``greg.*`` event on the Kernel
spine with a deterministic identity, so re-emitting the same fact after a crash
is idempotent and emitting different content under the same identity is refused.
"""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

from events.spine import Event, EventSpine
from provenance.ledger import sha256_json

SOURCE = "spiffe://uniimente.internal/greg/body"
PRINCIPAL = "alfonso_lopez"
NAMESPACE = uuid.UUID("9d5c0c4e-2f1b-4a55-9c63-8f2b7a4e0b11")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class Journal:
    def __init__(self, spine: EventSpine, *, actor: str):
        self.spine, self.actor = spine, actor

    @property
    def ledger(self):
        return self.spine.ledger

    def record(self, kind: str, data: dict, *, key: object = None, causal_parent: str | None = None,
               sensitivity: str = "internal") -> Event:
        """Append one fact; ``key`` makes the fact idempotent across restarts."""
        identity = sha256_json({"kind": kind, "key": key if key is not None else data})
        event = Event(type="greg." + kind, source=SOURCE, actor=self.actor, legal_principal=PRINCIPAL,
                      event_id=str(uuid.uuid5(NAMESPACE, identity)), payload=data,
                      causal_parent=causal_parent, sensitivity=sensitivity)
        accepted = self.spine.emit(event)
        if accepted is None:  # already durable: return the retained fact
            return next(e for e in self.spine.replay("greg." + kind) if e.event_id == event.event_id)
        return accepted

    def replay(self, kind_prefix: str = "") -> list[Event]:
        return self.spine.replay("greg." + kind_prefix)

    def event_hash(self, event_id: str) -> str | None:
        for record in reversed(self.ledger.records):
            if record.record_type == "event" and record.payload.get("event_id") == event_id:
                return record.hash
        return None
