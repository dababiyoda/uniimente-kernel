"""Canonical bridge transport v2. Consumers import this pinned implementation.

HMAC proves key possession, not authority or founder authentication. With the
shared key it proves only "a holder of the bridge key" (identity_isolated
"false"). With a per-organ key (UNIIMENTE_BRIDGE_KEY_<ORGAN>, distinct from the
shared key and from every other organ's key) it proves the sender held that
organ's key (identity_isolated "true"). Verifiers that hold per-organ keys can
still forge them: this isolates organs from each other, not from the verifier. Version 1 transport is intentionally refused: its context and
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
H_KEY_SCOPE = "X-Key-Scope"
IDENTITY_KEY_ENV_PREFIX = "UNIIMENTE_BRIDGE_KEY_"
KNOWN_IDENTITIES = frozenset({"daleobanks", "wealthmachine", "kernel"})
SCHEMA_VERSIONS = frozenset({"1.0", "1.1"})


class BridgeSecurityError(PermissionError):
    pass


def signing_key():
    return os.getenv(SIGNING_KEY_ENV, "").strip()


def identity_key(identity):
    """The per-organ key for `identity`, or "" when none is configured."""
    return os.getenv(IDENTITY_KEY_ENV_PREFIX + identity.upper(), "").strip()


def _identity_key_isolated(identity):
    """True only when the organ's key exists and collides with no other key."""
    key = identity_key(identity)
    if not key or key == signing_key():
        return False
    return all(identity_key(other) != key for other in KNOWN_IDENTITIES if other != identity)


def body_digest(body):
    return hashlib.sha256(body).hexdigest()


def _recipient(identity):
    return "wealthmachine" if identity in ("daleobanks", "kernel") else "daleobanks"


def sign(key, identity, timestamp, nonce, idempotency, schema_version, body,
         *, recipient=None, operation="opportunity.evaluate", request_digest="",
         direction="request", status="", trace_id="", protocol=PROTOCOL_VERSION,
         key_scope="shared"):
    # A structured domain separator, not a new cryptographic algorithm.
    context = [protocol, direction, identity, recipient or _recipient(identity),
               operation, timestamp, nonce, idempotency, schema_version,
               request_digest, str(status), trace_id, body_digest(body)]
    if key_scope != "shared":
        # Shared-scope context stays byte-identical to transport v2 so pinned
        # consumers interoperate; other scopes are bound into the signature so
        # a scope cannot be swapped after signing.
        context.append("key-scope:" + key_scope)
    message = json.dumps(context, ensure_ascii=True, separators=(",", ":")).encode()
    return hmac.new(key.encode(), message, hashlib.sha256).hexdigest()


def build_headers(body, *, identity, schema_version, idempotency_key=None,
                  trace_id="", recipient=None, operation="opportunity.evaluate",
                  request_digest="", direction="request", status=""):
    if identity not in KNOWN_IDENTITIES:
        raise BridgeSecurityError("unsupported identity or schema version")
    # Prefer the sender's own key; fall back to the shared key (transport v2).
    key, scope = identity_key(identity), "identity"
    if not key:
        key, scope = signing_key(), "shared"
    if not key:
        raise BridgeSecurityError("signing configuration required")
    if schema_version not in SCHEMA_VERSIONS:
        raise BridgeSecurityError("unsupported identity or schema version")
    recipient = recipient or _recipient(identity)
    if recipient not in KNOWN_IDENTITIES:
        raise BridgeSecurityError("unknown recipient")
    timestamp, nonce = str(int(time.time())), secrets.token_hex(16)
    idem = idempotency_key or secrets.token_hex(16)
    values = dict(recipient=recipient, operation=operation, request_digest=request_digest,
                  direction=direction, status=str(status), trace_id=trace_id)
    headers = {H_PROTOCOL: PROTOCOL_VERSION, H_IDENTITY: identity, H_RECIPIENT: recipient,
               H_TIMESTAMP: timestamp, H_NONCE: nonce, H_IDEMPOTENCY: idem,
               H_SCHEMA: schema_version, H_TRACE: trace_id, H_OPERATION: operation,
               H_REQUEST: request_digest, H_DIRECTION: direction, H_STATUS: str(status),
               H_SIGNATURE: sign(key, identity, timestamp, nonce, idem, schema_version, body,
                                 key_scope=scope, **values)}
    if scope != "shared":
        headers[H_KEY_SCOPE] = scope  # shared-scope headers stay identical to v2
    return headers


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
                   direction="request", status="", principal=None,
                   require_isolated_identity=False):
    lower = {k.lower(): v for k, v in headers.items()}
    def get(name):
        return lower.get(name.lower(), "")
    scope = get(H_KEY_SCOPE) or "shared"
    if scope not in ("shared", "identity"):
        raise BridgeSecurityError("unsupported key scope")
    claimed = get(H_IDENTITY)
    if scope == "identity":
        key = identity_key(claimed) if claimed in KNOWN_IDENTITIES else ""
        if not key:
            raise BridgeSecurityError("no per-organ key configured for the claimed sender")
    else:
        key = signing_key()
        if not key:
            raise BridgeSecurityError("signing configuration required; unsigned admission prohibited")
    isolated = scope == "identity" and _identity_key_isolated(claimed)
    if require_isolated_identity and not isolated:
        raise BridgeSecurityError("isolated sender identity required; shared or colliding key refused")
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
                    direction=direction, status=status, trace_id=get(H_TRACE), key_scope=scope)
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
            "signed": "true", "identity_isolated": "true" if isolated else "false",
            "key_scope": scope, "idempotency_key": idem,
            "trace_id": get(H_TRACE), "body_digest": body_digest(body)}
