"""Canonical bridge transport v2. Consumers import this pinned implementation.

HMAC proves shared-key possession, not isolated identity, authority or founder
authentication. Version 1 transport is intentionally refused: its context and
serialization ambiguities cannot be silently preserved. Wire schemas 1.0/1.1
remain supported. No network, token issuance or effect is performed here.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import secrets
import time

SIGNING_KEY_ENV = "WEALTHMACHINE_SIGNING_KEY"
MAX_SKEW_SECONDS = 300
MIN_SCHEMA_VERSION = "1.0"
PROTOCOL_VERSION = "2"
H_IDENTITY = "X-Service-Identity"
H_TIMESTAMP = "X-Timestamp"
H_NONCE = "X-Nonce"
H_IDEMPOTENCY = "X-Idempotency-Key"
H_SCHEMA = "X-Schema-Version"
H_SIGNATURE = "X-Signature"
H_TRACE = "X-Trace-Id"
H_PROTOCOL = "X-Uniimente-Protocol"
H_RECIPIENT = "X-Recipient"
H_OPERATION = "X-Operation"
H_REQUEST = "X-Request-Digest"
H_DIRECTION = "X-Direction"
H_STATUS = "X-Response-Status"
KNOWN_IDENTITIES = frozenset({"daleobanks", "wealthmachine", "kernel"})
SCHEMA_VERSIONS = frozenset({"1.0", "1.1"})


class BridgeSecurityError(PermissionError):
    pass


def signing_key():
    return os.getenv(SIGNING_KEY_ENV, "").strip()


def body_digest(body):
    return hashlib.sha256(body).hexdigest()


def _recipient(identity):
    return "wealthmachine" if identity in ("daleobanks", "kernel") else "daleobanks"


def sign(key, identity, timestamp, nonce, idempotency, schema_version, body,
         *, recipient=None, operation="opportunity.evaluate", request_digest="",
         direction="request", status="", trace_id="", protocol=PROTOCOL_VERSION):
    # A structured domain separator, not a new cryptographic algorithm.
    context = [protocol, direction, identity, recipient or _recipient(identity),
               operation, timestamp, nonce, idempotency, schema_version,
               request_digest, str(status), trace_id, body_digest(body)]
    message = json.dumps(context, ensure_ascii=True, separators=(",", ":")).encode()
    return hmac.new(key.encode(), message, hashlib.sha256).hexdigest()


def build_headers(body, *, identity, schema_version, idempotency_key=None,
                  trace_id="", recipient=None, operation="opportunity.evaluate",
                  request_digest="", direction="request", status=""):
    key = signing_key()
    if not key:
        raise BridgeSecurityError("signing configuration required")
    if identity not in KNOWN_IDENTITIES or schema_version not in SCHEMA_VERSIONS:
        raise BridgeSecurityError("unsupported identity or schema version")
    recipient = recipient or _recipient(identity)
    if recipient not in KNOWN_IDENTITIES:
        raise BridgeSecurityError("unknown recipient")
    timestamp, nonce = str(int(time.time())), secrets.token_hex(16)
    idem = idempotency_key or secrets.token_hex(16)
    values = dict(recipient=recipient, operation=operation, request_digest=request_digest,
                  direction=direction, status=str(status), trace_id=trace_id)
    return {H_PROTOCOL: PROTOCOL_VERSION, H_IDENTITY: identity, H_RECIPIENT: recipient,
            H_TIMESTAMP: timestamp, H_NONCE: nonce, H_IDEMPOTENCY: idem,
            H_SCHEMA: schema_version, H_TRACE: trace_id, H_OPERATION: operation,
            H_REQUEST: request_digest, H_DIRECTION: direction, H_STATUS: str(status),
            H_SIGNATURE: sign(key, identity, timestamp, nonce, idem, schema_version, body, **values)}


class NonceCache:
    """Legacy in-memory fixture helper; durable consumers use BridgeState.

    Not a supported production replay store. No automatic fallback to this type.
    """
    def __init__(self, ttl_seconds=MAX_SKEW_SECONDS * 2):
        self.ttl, self._seen = ttl_seconds, {}

    def check_and_store(self, nonce):
        now = time.time()
        self._seen = {n: t for n, t in self._seen.items() if now - t <= self.ttl}
        if nonce in self._seen:
            return False
        self._seen[nonce] = now
        return True


def verify_headers(headers, body, *, nonce_cache, require_signature=None,
                   expected_recipient=None, expected_sender=None,
                   expected_operation=None, request_digest=None,
                   direction="request", status="", principal=None):
    key = signing_key()
    if not key:
        raise BridgeSecurityError("signing configuration required; unsigned admission prohibited")
    lower = {k.lower(): v for k, v in headers.items()}
    def get(name):
        return lower.get(name.lower(), "")
    if get(H_PROTOCOL) != PROTOCOL_VERSION:
        raise BridgeSecurityError("unsupported transport protocol")
    identity, recipient = get(H_IDENTITY), get(H_RECIPIENT)
    if identity not in KNOWN_IDENTITIES or recipient not in KNOWN_IDENTITIES:
        raise BridgeSecurityError("unknown sender or recipient")
    if (expected_sender is not None and identity != expected_sender or
            expected_recipient is not None and recipient != expected_recipient or
            principal is not None and principal != identity):
        raise BridgeSecurityError("principal/sender/recipient mismatch")
    version, operation = get(H_SCHEMA), get(H_OPERATION)
    if version not in SCHEMA_VERSIONS:
        raise BridgeSecurityError("unsupported schema version")
    if not operation or expected_operation is not None and operation != expected_operation:
        raise BridgeSecurityError("operation mismatch")
    if (get(H_DIRECTION) != direction or get(H_STATUS) != str(status) or
            request_digest is not None and get(H_REQUEST) != request_digest):
        raise BridgeSecurityError("request/response context mismatch")
    ts, nonce, idem = get(H_TIMESTAMP), get(H_NONCE), get(H_IDEMPOTENCY)
    try:
        valid_time = len(ts) <= 20 and ts.isdigit() and abs(time.time() - int(ts)) <= MAX_SKEW_SECONDS
    except (ValueError, OverflowError):
        valid_time = False
    if not valid_time:
        raise BridgeSecurityError("timestamp outside accepted window")
    if not nonce or not idem or len(nonce) > 256 or len(idem) > 256:
        raise BridgeSecurityError("bounded nonce and logical operation key required")
    expected = sign(key, identity, ts, nonce, idem, version, body, recipient=recipient,
                    operation=operation, request_digest=get(H_REQUEST),
                    direction=direction, status=status, trace_id=get(H_TRACE))
    signature = get(H_SIGNATURE)
    if (not isinstance(signature, str) or len(signature) != 64
            or any(c not in '0123456789abcdef' for c in signature)
            or not hmac.compare_digest(signature, expected)):
        raise BridgeSecurityError("signature verification failed")
    # Only authenticated input may consume durable freshness state.
    if not nonce_cache.check_and_store(identity + ":" + nonce):
        raise BridgeSecurityError("nonce replay refused")
    return {"identity": identity, "recipient": recipient, "schema_version": version,
            "protocol_version": PROTOCOL_VERSION, "operation": operation,
            "signed": "true", "identity_isolated": "false", "idempotency_key": idem,
            "trace_id": get(H_TRACE), "body_digest": body_digest(body)}
