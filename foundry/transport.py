"""Signed inter-organ transport for Foundry underwriting intake.

The wire format is compatible with the existing DALEOBANKS/WealthMachine
bridge: service identity, timestamp, nonce, idempotency key, schema version,
trace id, body hash, and HMAC-SHA256 signature. Authentication is never
interpreted as authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Mapping

from .contracts import FoundryError, OpportunitySpec
from .wire import opportunity_from_underwriting_wire

MAX_SKEW_SECONDS = 300
MIN_TRANSPORT_SCHEMA = "1.0"

H_IDENTITY = "X-Service-Identity"
H_TIMESTAMP = "X-Timestamp"
H_NONCE = "X-Nonce"
H_IDEMPOTENCY = "X-Idempotency-Key"
H_SCHEMA = "X-Schema-Version"
H_SIGNATURE = "X-Signature"
H_TRACE = "X-Trace-Id"


class TransportSecurityError(PermissionError):
    pass


@dataclass(frozen=True)
class TransportReceipt:
    identity: str
    schema_version: str
    idempotency_key: str
    trace_id: str
    body_hash: str
    duplicate: bool


@dataclass(frozen=True)
class IngestedUnderwriting:
    opportunity: OpportunitySpec
    transport: TransportReceipt


class ReplayGuard:
    """Nonce replay defense plus changed-content idempotency protection."""

    def __init__(self, ttl_seconds: int = MAX_SKEW_SECONDS * 2) -> None:
        self.ttl_seconds = ttl_seconds
        self._nonces: dict[str, float] = {}
        self._idempotency: dict[str, tuple[str, float]] = {}

    def accept(
        self,
        *,
        nonce: str,
        idempotency_key: str,
        body_hash: str,
        now: float,
    ) -> bool:
        self._purge(now)
        if not nonce or nonce in self._nonces:
            raise TransportSecurityError("nonce missing or already used")
        self._nonces[nonce] = now

        prior = self._idempotency.get(idempotency_key)
        if prior is None:
            self._idempotency[idempotency_key] = (body_hash, now)
            return False
        prior_hash, _ = prior
        if prior_hash != body_hash:
            raise TransportSecurityError("idempotency key reused with changed content")
        self._idempotency[idempotency_key] = (body_hash, now)
        return True

    def _purge(self, now: float) -> None:
        for nonce, observed in list(self._nonces.items()):
            if now - observed > self.ttl_seconds:
                del self._nonces[nonce]
        for key, (_, observed) in list(self._idempotency.items()):
            if now - observed > self.ttl_seconds:
                del self._idempotency[key]


def _body_hash(body: bytes) -> str:
    return hashlib.sha256(body or b"").hexdigest()


def _canonical(
    identity: str,
    timestamp: str,
    nonce: str,
    idempotency_key: str,
    schema_version: str,
    body: bytes,
) -> bytes:
    return (
        f"{identity}|{timestamp}|{nonce}|{idempotency_key}|"
        f"{schema_version}|{_body_hash(body)}"
    ).encode()


def _version_tuple(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.split("."))
    except (AttributeError, ValueError):
        return (0,)


def sign_transport(
    key: bytes | str,
    *,
    identity: str,
    timestamp: str,
    nonce: str,
    idempotency_key: str,
    schema_version: str,
    body: bytes,
) -> str:
    key_bytes = key.encode() if isinstance(key, str) else key
    if not key_bytes:
        raise TransportSecurityError("inter-organ signing key is required")
    return hmac.new(
        key_bytes,
        _canonical(
            identity, timestamp, nonce, idempotency_key, schema_version, body,
        ),
        hashlib.sha256,
    ).hexdigest()


def build_signed_headers(
    body: bytes,
    *,
    key: bytes | str,
    identity: str,
    schema_version: str,
    idempotency_key: str,
    trace_id: str = "",
    timestamp: str | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    timestamp = timestamp or str(int(time.time()))
    nonce = nonce or secrets.token_hex(16)
    headers = {
        H_IDENTITY: identity,
        H_TIMESTAMP: timestamp,
        H_NONCE: nonce,
        H_IDEMPOTENCY: idempotency_key,
        H_SCHEMA: schema_version,
        H_SIGNATURE: sign_transport(
            key,
            identity=identity,
            timestamp=timestamp,
            nonce=nonce,
            idempotency_key=idempotency_key,
            schema_version=schema_version,
            body=body,
        ),
    }
    if trace_id:
        headers[H_TRACE] = trace_id
    return headers


def verify_signed_headers(
    headers: Mapping[str, str],
    body: bytes,
    *,
    key: bytes | str,
    replay_guard: ReplayGuard,
    now: float | None = None,
) -> TransportReceipt:
    normalized = {str(name).lower(): str(value) for name, value in headers.items()}

    def get(name: str) -> str:
        return normalized.get(name.lower(), "")

    identity = get(H_IDENTITY)
    timestamp = get(H_TIMESTAMP)
    nonce = get(H_NONCE)
    idempotency_key = get(H_IDEMPOTENCY)
    schema_version = get(H_SCHEMA)
    signature = get(H_SIGNATURE)
    trace_id = get(H_TRACE)

    if not identity:
        raise TransportSecurityError("service identity is required")
    if not idempotency_key:
        raise TransportSecurityError("idempotency key is required")
    if _version_tuple(schema_version) < _version_tuple(MIN_TRANSPORT_SCHEMA):
        raise TransportSecurityError("transport schema downgrade rejected")
    current = time.time() if now is None else now
    try:
        skew = abs(current - int(timestamp))
    except (TypeError, ValueError) as exc:
        raise TransportSecurityError("timestamp is missing or malformed") from exc
    if skew > MAX_SKEW_SECONDS:
        raise TransportSecurityError("timestamp outside accepted window")

    expected = sign_transport(
        key,
        identity=identity,
        timestamp=timestamp,
        nonce=nonce,
        idempotency_key=idempotency_key,
        schema_version=schema_version,
        body=body,
    )
    if not signature or not hmac.compare_digest(signature, expected):
        raise TransportSecurityError("signature verification failed")

    body_hash = _body_hash(body)
    duplicate = replay_guard.accept(
        nonce=nonce,
        idempotency_key=idempotency_key,
        body_hash=body_hash,
        now=current,
    )
    return TransportReceipt(
        identity=identity,
        schema_version=schema_version,
        idempotency_key=idempotency_key,
        trace_id=trace_id,
        body_hash="sha256:" + body_hash,
        duplicate=duplicate,
    )


def ingest_signed_underwriting(
    headers: Mapping[str, str],
    body: bytes,
    *,
    key: bytes | str,
    replay_guard: ReplayGuard,
    ledger: Any | None = None,
) -> IngestedUnderwriting:
    transport = verify_signed_headers(
        headers,
        body,
        key=key,
        replay_guard=replay_guard,
    )
    if transport.identity != "wealthmachine":
        raise TransportSecurityError("only WealthMachine may submit underwriting envelopes")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise FoundryError("underwriting body is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise FoundryError("underwriting body must be a JSON object")

    opportunity = opportunity_from_underwriting_wire(payload)
    if ledger is not None:
        ledger.append("event", {
            "type": "foundry.underwriting_ingested",
            "identity": transport.identity,
            "schema_version": transport.schema_version,
            "idempotency_key": transport.idempotency_key,
            "trace_id": transport.trace_id,
            "body_hash": transport.body_hash,
            "duplicate": transport.duplicate,
            "opportunity_id": opportunity.opportunity_id,
            "opportunity_digest": opportunity.digest,
            "execution_authority": "none",
        })
    return IngestedUnderwriting(opportunity=opportunity, transport=transport)


__all__ = [
    "H_IDENTITY", "H_IDEMPOTENCY", "H_NONCE", "H_SCHEMA", "H_SIGNATURE",
    "H_TIMESTAMP", "H_TRACE", "IngestedUnderwriting", "MAX_SKEW_SECONDS",
    "MIN_TRANSPORT_SCHEMA", "ReplayGuard", "TransportReceipt",
    "TransportSecurityError", "build_signed_headers", "ingest_signed_underwriting",
    "sign_transport", "verify_signed_headers",
]
