"""Kernel-side transport verification for organ bridge messages.

Third mirror of the DALEOBANKS/WealthMachineIntelligence bridge security
module (services/bridge_security.py and src/services/bridge_security.py at
the commits recorded in organs/*.manifest.yaml) — keep the canonical form,
header names, and verification semantics field-for-field compatible.

Kernel extension: "kernel" joins the known-identity set so the kernel can
witness and later participate in bridge traffic. The peer repositories
still list only {daleobanks, wealthmachine}; until they add "kernel",
messages SIGNED BY the kernel are not verifiable by the organs. That gap
is recorded as an unresolved field in both peer manifests — it is a
cross-repository change, not something this module may paper over.

A valid signature proves sender authenticity ONLY. It never carries
authorization: a perfectly signed payload still has no execution authority
and still routes through the consequence gate and human approval.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Dict, Optional, Tuple

SIGNING_KEY_ENV = "WEALTHMACHINE_SIGNING_KEY"
MAX_SKEW_SECONDS = 300
MIN_SCHEMA_VERSION = "1.0"

#: Explicit opt-in to the legacy unsigned path. Set to "1" to allow it.
#:
#: Added 2026-08-22 under FOUNDER-RULING-2026-08-22, which ratified asymmetric
#: workload identity and ruled on what may remain of the shared-key transport:
#: *"If legacy HMAC compatibility must temporarily survive, it must be an
#: explicit development compatibility mode, fail closed, never auto-downgrade,
#: and never be mistaken for mutually isolated identity."*
#:
#: It previously auto-downgraded. `must_sign` was derived as `bool(key)`, so an
#: unset `WEALTHMACHINE_SIGNING_KEY` did not fail — it returned SUCCESS carrying
#: the caller's *claimed* identity, unverified. Absence of configuration
#: silently disabled authentication, which is the failure mode where a forgotten
#: environment variable in a new deployment reads as a working trust boundary.
#: Now the absence of a key is refused unless a human has explicitly asked for
#: the legacy path by name.
DEV_UNSIGNED_ENV = "UNIIMENTE_BRIDGE_DEV_UNSIGNED"

H_IDENTITY = "X-Service-Identity"
H_TIMESTAMP = "X-Timestamp"
H_NONCE = "X-Nonce"
H_IDEMPOTENCY = "X-Idempotency-Key"
H_SCHEMA = "X-Schema-Version"
H_SIGNATURE = "X-Signature"
H_TRACE = "X-Trace-Id"

KNOWN_IDENTITIES = frozenset({"daleobanks", "wealthmachine", "kernel"})


class BridgeSecurityError(PermissionError):
    """Transport verification failed. The payload must not be processed."""


def signing_key() -> str:
    return os.getenv(SIGNING_KEY_ENV, "")


def _canonical(identity: str, timestamp: str, nonce: str, idempotency: str,
               schema_version: str, body: bytes) -> bytes:
    body_hash = hashlib.sha256(body or b"").hexdigest()
    return f"{identity}|{timestamp}|{nonce}|{idempotency}|{schema_version}|{body_hash}".encode()


def sign(key: str, identity: str, timestamp: str, nonce: str, idempotency: str,
         schema_version: str, body: bytes) -> str:
    return hmac.new(
        key.encode(), _canonical(identity, timestamp, nonce, idempotency,
                                 schema_version, body),
        hashlib.sha256,
    ).hexdigest()


def build_headers(
    body: bytes,
    *,
    identity: str,
    schema_version: str,
    idempotency_key: Optional[str] = None,
    trace_id: str = "",
) -> Dict[str, str]:
    """Signed transport headers for an outbound request/response. With no
    key configured, identity headers still travel (debuggability) but no
    signature is attached."""
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    idempotency = idempotency_key or secrets.token_hex(16)
    headers = {
        H_IDENTITY: identity,
        H_TIMESTAMP: timestamp,
        H_NONCE: nonce,
        H_IDEMPOTENCY: idempotency,
        H_SCHEMA: schema_version,
    }
    if trace_id:
        headers[H_TRACE] = trace_id
    key = signing_key()
    if key:
        headers[H_SIGNATURE] = sign(key, identity, timestamp, nonce,
                                    idempotency, schema_version, body)
    return headers


class NonceCache:
    """In-memory replay guard. A nonce is accepted exactly once inside the
    skew window; reuse fails closed."""

    def __init__(self, ttl_seconds: int = MAX_SKEW_SECONDS * 2) -> None:
        self.ttl = ttl_seconds
        self._seen: Dict[str, float] = {}

    def check_and_store(self, nonce: str) -> bool:
        now = time.time()
        for old, ts in list(self._seen.items()):
            if now - ts > self.ttl:
                del self._seen[old]
        if nonce in self._seen:
            return False
        self._seen[nonce] = now
        return True


def _version_tuple(version: str) -> Tuple[int, ...]:
    try:
        return tuple(int(p) for p in version.split("."))
    except ValueError:
        return (0,)


def verify_headers(
    headers: Dict[str, str],
    body: bytes,
    *,
    nonce_cache: NonceCache,
    require_signature: Optional[bool] = None,
) -> Dict[str, str]:
    """Verify inbound transport headers. Raises BridgeSecurityError on any
    failure — fail closed, never degrade. Returns the normalized header
    set for provenance recording."""
    getter = {k.lower(): v for k, v in headers.items()}

    def get(name: str) -> str:
        return getter.get(name.lower(), "")

    key = signing_key()
    must_sign = require_signature if require_signature is not None else True

    identity = get(H_IDENTITY)
    schema_version = get(H_SCHEMA) or MIN_SCHEMA_VERSION
    if _version_tuple(schema_version) < _version_tuple(MIN_SCHEMA_VERSION):
        raise BridgeSecurityError(
            f"schema version {schema_version} below minimum {MIN_SCHEMA_VERSION} — "
            "downgrade rejected"
        )

    if must_sign and not key:
        # Fail closed. The old code inferred `must_sign` from whether a key
        # happened to be configured, so this branch used to be a silent success.
        raise BridgeSecurityError(
            f"no signing key configured ({SIGNING_KEY_ENV} unset) and signature "
            f"required. Set the key, or set {DEV_UNSIGNED_ENV}=1 to opt into the "
            "legacy unsigned development path explicitly. Verification is never "
            "disabled by the absence of configuration."
        )

    if not must_sign:
        if os.getenv(DEV_UNSIGNED_ENV) != "1":
            raise BridgeSecurityError(
                f"unsigned transport requested but {DEV_UNSIGNED_ENV} is not set "
                "to 1. The legacy path is development-only and must be asked for "
                "by name."
            )
        # Marked so no downstream reader can mistake this for an authenticated
        # peer. `identity_isolated` is "false" because even the *signed* HMAC
        # path is not isolated identity — one shared secret verifies and signs,
        # so any holder can claim any known identity. Isolated identity is
        # `identity/pki/`, where a private key proves a SPIFFE ID no other
        # workload can assert.
        return {"identity": identity or "unsigned-local",
                "schema_version": schema_version,
                "signed": "false",
                "identity_isolated": "false",
                "dev_compatibility_mode": "true",
                "trace_id": get(H_TRACE)}

    if identity not in KNOWN_IDENTITIES:
        raise BridgeSecurityError(f"unknown service identity '{identity}'")

    timestamp = get(H_TIMESTAMP)
    try:
        skew = abs(time.time() - int(timestamp))
    except (TypeError, ValueError):
        raise BridgeSecurityError("missing or malformed timestamp")
    if skew > MAX_SKEW_SECONDS:
        raise BridgeSecurityError("timestamp outside the accepted window")

    nonce = get(H_NONCE)
    if not nonce or not nonce_cache.check_and_store(nonce):
        raise BridgeSecurityError("nonce missing or already used — replay rejected")

    idempotency = get(H_IDEMPOTENCY)
    signature = get(H_SIGNATURE)
    expected = sign(key, identity, timestamp, nonce, idempotency,
                    schema_version, body)
    if not signature or not hmac.compare_digest(signature, expected):
        raise BridgeSecurityError("signature verification failed")

    # `signed` and `identity_isolated` are separate facts and both travel.
    # A valid signature proves the sender held the shared secret; it does not
    # prove *which* holder sent it, because every participant needs that secret
    # to verify and can therefore also sign. Under the founder's ruling this
    # must never read as mutually isolated identity, so the record says so in
    # its own field rather than leaving a reader to infer it from `signed`.
    return {"identity": identity, "schema_version": schema_version,
            "signed": "true", "identity_isolated": "false",
            "idempotency_key": idempotency,
            "trace_id": get(H_TRACE)}


def verify_mutual_identity(mesh, client_service: str, server_service: str, *,
                           schema_version: str = MIN_SCHEMA_VERSION,
                           idempotency_key: str = "",
                           trace_id: str | None = None) -> Dict[str, str]:
    """Authenticate a peer with an isolated workload key instead of a shared one.

    Added 2026-08-23 under FOUNDER-RULING-2026-08-23 — the adoption half of
    technologies #7 and #26. `identity/pki/` was built and tested a day earlier
    and deliberately left unused; this is the call site that uses it.

    Returns the same shape `verify_headers` returns, so a caller can move
    between the two paths without reshaping its record. Two fields differ, and
    they are the whole point:

        identity_isolated : "true"   (the HMAC path can only ever say "false")
        peer_spiffe_id    : the workload identity that actually authenticated

    **Why the HMAC path can never say "true".** One shared secret both signs and
    verifies, so every participant able to check a signature is able to forge
    one. `X-Service-Identity` is a *claim* the holder makes about itself. Here
    the SPIFFE ID comes from a chain-validated certificate whose private key
    never leaves its own workload, so no peer can assert another's identity.

    **`identity` stays the organ, not the workload.** The organ is what the
    canonical packet records as `created_by` — the claim belongs to DALEOBANKS,
    not to one of its processes — while `peer_spiffe_id` keeps the narrower fact
    about which workload connected. Both travel; neither is inferred from the
    other.

    Raises `IdentityError` on any handshake failure, and does not fall back.
    A transport that downgraded to the shared secret when the handshake failed
    would make the strong path decorative.
    """
    _server_seen_by_client, client_seen_by_server = mesh.connect(
        client_service, server_service)

    if schema_version < MIN_SCHEMA_VERSION:
        raise BridgeSecurityError(
            f"schema version {schema_version} below minimum "
            f"{MIN_SCHEMA_VERSION} — downgrade rejected")

    peer = client_seen_by_server
    if peer.organ not in KNOWN_IDENTITIES:
        raise BridgeSecurityError(
            f"authenticated workload {peer.spiffe_id!r} maps to organ "
            f"{peer.organ!r}, which is not a known bridge identity. A valid "
            "certificate from the internal CA is proof of identity, never of "
            "membership in this transport's peer set.")

    return {
        "identity": peer.organ,
        "peer_spiffe_id": peer.spiffe_id,
        "peer_serial": str(peer.serial),
        "schema_version": schema_version,
        "signed": "true",
        "identity_isolated": "true",
        "idempotency_key": idempotency_key,
        "trace_id": trace_id or "",
    }


__all__ = [
    "BridgeSecurityError", "NonceCache", "build_headers", "verify_headers",
    "verify_mutual_identity",
    "sign", "signing_key", "SIGNING_KEY_ENV", "MAX_SKEW_SECONDS",
    "MIN_SCHEMA_VERSION", "KNOWN_IDENTITIES",
    "H_IDENTITY", "H_TIMESTAMP", "H_NONCE", "H_IDEMPOTENCY",
    "H_SCHEMA", "H_SIGNATURE", "H_TRACE",
]
