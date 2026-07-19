"""Event spine: typed, sequenced, hash-chained institutional events.

Phase 4, first piece. Organs exchange typed, governed events; they never
call each other arbitrarily. Every material occurrence — signal detected,
evidence verified, approval requested, capability issued, action committed
or refused, payment received, policy changed, agent quarantined, venture
terminated, capital reallocated — enters the institution as one immutable
event.

The spine is deliberately small: an :class:`EventSpine` builds
contract-conformant envelopes (``contracts/event.schema.json``,
CloudEvents-compatible) and persists them through the kernel
``DecisionLedger``, which supplies sequencing and the tamper-evident hash
chain. Causality is explicit: every event names its ``causal_parent``
(null only for origin events), so any outcome can be walked back to the
evidence and approvals that permitted it. That walk is what later phases
turn into causal memory.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

from uniimente_kernel.ledger import DecisionLedger

SPECVERSION = "1.0"

SENSITIVITIES = frozenset({"public", "internal", "confidential", "restricted"})

_TYPE_RE = re.compile(r"^[a-z]+\.[a-z_]+$")
_SPIFFE_RE = re.compile(r"^spiffe://uniimente\.internal/")
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# Contract property set (contracts/event.schema.json). Kept in parity by
# the schema-parity test in test_events.py.
EVENT_FIELDS = frozenset({
    "specversion", "id", "type", "source", "actor", "legal_principal",
    "time", "subject", "evidence_refs", "policy_version", "confidence",
    "sensitivity", "causal_parent", "expected_consequence", "data",
})

REQUIRED_FIELDS = frozenset({
    "specversion", "id", "type", "source", "actor",
    "legal_principal", "time", "sensitivity", "causal_parent",
})


class EventValidationError(ValueError):
    """Raised when an event envelope violates the contract."""


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def validate_event_dict(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate an event envelope against the contract. Inbound events are
    untrusted input: validated as data, never followed as instruction."""
    if not isinstance(payload, dict):
        raise EventValidationError("event must be an object")

    missing = REQUIRED_FIELDS - set(payload)
    if missing:
        raise EventValidationError(f"event missing required fields: {sorted(missing)}")

    extra = set(payload) - EVENT_FIELDS
    if extra:
        raise EventValidationError(f"event has unknown fields: {sorted(extra)}")

    if payload["specversion"] != SPECVERSION:
        raise EventValidationError(f"specversion must be {SPECVERSION}")

    if not _UUID_RE.match(str(payload["id"])):
        raise EventValidationError("id must be a uuid")

    if not _TYPE_RE.match(str(payload["type"])):
        raise EventValidationError("type must be dotted lowercase, e.g. 'signal.detected'")

    for key in ("source", "actor"):
        if not _SPIFFE_RE.match(str(payload[key])):
            raise EventValidationError(f"{key} must be a SPIFFE-style institutional identity")

    if not payload["legal_principal"]:
        # Never UNIIMENTE itself: a legal actor from
        # /authority/legal-principals.yaml is accountable for every event.
        raise EventValidationError("legal_principal is required")

    if payload["sensitivity"] not in SENSITIVITIES:
        raise EventValidationError(f"sensitivity must be one of {sorted(SENSITIVITIES)}")

    parent = payload["causal_parent"]
    if parent is not None and not _UUID_RE.match(str(parent)):
        raise EventValidationError("causal_parent must be a uuid or null")

    refs = payload.get("evidence_refs") or []
    if not isinstance(refs, list) or not all(_HASH_RE.match(str(r)) for r in refs):
        raise EventValidationError("evidence_refs must be a list of sha256:<hex> hashes")

    confidence = payload.get("confidence")
    if confidence is not None and not (0.0 <= float(confidence) <= 1.0):
        raise EventValidationError("confidence must be within [0, 1]")

    return payload


@dataclass
class Event:
    """One institutional event. Build via EventSpine.emit()."""

    type: str
    source: str
    actor: str
    legal_principal: str
    sensitivity: str
    causal_parent: Optional[str]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    specversion: str = SPECVERSION
    time: str = field(default_factory=_utcnow_iso)
    subject: Optional[str] = None
    evidence_refs: List[str] = field(default_factory=list)
    policy_version: Optional[str] = None
    confidence: Optional[float] = None
    expected_consequence: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "specversion": self.specversion,
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "actor": self.actor,
            "legal_principal": self.legal_principal,
            "time": self.time,
            "sensitivity": self.sensitivity,
            "causal_parent": self.causal_parent,
            "evidence_refs": list(self.evidence_refs),
            "data": dict(self.data),
        }
        if self.subject is not None:
            payload["subject"] = self.subject
        if self.policy_version is not None:
            payload["policy_version"] = self.policy_version
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        if self.expected_consequence is not None:
            payload["expected_consequence"] = self.expected_consequence
        return payload


class EventSpine:
    """Emit and read institutional events through a hash-chained ledger.

    The emitter carries the organ's standing identity (source, actor,
    legal_principal, policy_version) so call sites state only what varies:
    type, subject, data, causality.
    """

    def __init__(
        self,
        ledger: DecisionLedger,
        *,
        source: str,
        actor: str,
        legal_principal: str,
        policy_version: Optional[str] = None,
        default_sensitivity: str = "internal",
    ) -> None:
        if default_sensitivity not in SENSITIVITIES:
            raise EventValidationError("default_sensitivity must be a contract sensitivity")
        self.ledger = ledger
        self.source = source
        self.actor = actor
        self.legal_principal = legal_principal
        self.policy_version = policy_version
        self.default_sensitivity = default_sensitivity

    def emit(
        self,
        type: str,
        *,
        subject: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        causal_parent: Optional[str] = None,
        sensitivity: Optional[str] = None,
        evidence_refs: Optional[List[str]] = None,
        confidence: Optional[float] = None,
        expected_consequence: Optional[str] = None,
    ) -> Event:
        """Build, validate, and hash-chain one event. Returns the event."""
        event = Event(
            type=type,
            source=self.source,
            actor=self.actor,
            legal_principal=self.legal_principal,
            sensitivity=sensitivity or self.default_sensitivity,
            causal_parent=causal_parent,
            subject=subject,
            evidence_refs=list(evidence_refs or []),
            policy_version=self.policy_version,
            confidence=confidence,
            expected_consequence=expected_consequence,
            data=dict(data or {}),
        )
        validate_event_dict(event.to_dict())
        self.ledger.record(event.type, event.to_dict())
        return event

    def chain(self, type: str, parent: Event, **kwargs: Any) -> Event:
        """Emit an event caused by `parent` (causal_parent = parent.id)."""
        return self.emit(type, causal_parent=parent.id, **kwargs)

    def verify(self) -> bool:
        ok, _ = self.ledger.verify_chain()
        return ok

    def replay(self, type: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Read events back (ledger payloads), newest last; `limit` keeps
        the most recent N, matching ledger replay semantics."""
        return [entry["payload"] for entry in self.ledger.replay(event=type, limit=limit)]

    def get(self, event_id: str) -> Optional[Dict[str, Any]]:
        for entry in self.ledger.replay():
            if entry["payload"].get("id") == event_id:
                return entry["payload"]
        return None

    def causal_chain(self, event_id: str) -> List[Dict[str, Any]]:
        """Walk causal_parent links from an event back to its origin,
        origin first. Stops on missing parents (evidence gap, never
        invented)."""
        chain: List[Dict[str, Any]] = []
        current = self.get(event_id)
        while current is not None:
            chain.append(current)
            parent = current.get("causal_parent")
            current = self.get(parent) if parent else None
        chain.reverse()
        return chain


__all__ = [
    "SPECVERSION",
    "SENSITIVITIES",
    "EVENT_FIELDS",
    "REQUIRED_FIELDS",
    "Event",
    "EventSpine",
    "EventValidationError",
    "validate_event_dict",
]
