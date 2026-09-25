"""Founder authentication for GREG: real Ed25519 signatures, not shared secrets.

The synthetic GoalChase envelope (HMAC over a public demo key, identity pinned to
``sandbox:alfonso``) stays a sealed experiment. This module is its production
successor for the founder *authentication* seam only:

* Alfonso's private key is generated on a device he controls and never enters
  the body. The body stores only the enrolled public key.
* Every founder command is a signed envelope bound to one kind, one body, one
  issue/expiry window and one nonce. Nonces are retained in the canonical
  EvidenceLedger, so a replay is refused across process and machine restarts.
* Enrollment is trust-on-first-use by whoever controls the body's filesystem
  (the person installing GREG on hardware they own). Key rotation after that
  requires a signature from the currently enrolled key. Stronger ceremonies
  (Secure Enclave attestation, phone pairing) are future work and are not
  claimed here.

A valid signature proves possession of the enrolled key. It does not prove the
command is wise, lawful or inside the Constitution: every command is still
evaluated by the mission engine, the authority office and the Consequence Gate.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import secrets
import stat

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from egregore.contracts import canonical_json

COMMAND_KINDS = (
    "MISSION",            # register a persistent mission (its body carries the authority envelope)
    "DECISION",           # answer one pending decision request, bound to its exact scope
    "LIFECYCLE",          # pause / resume / supersede / abandon one mission
    "CRITIQUE",           # morning-tribunal critique of retained evidence
    "CAPABILITY_ATTACH",  # attach a verified capability under a stated ceiling
    "CAPABILITY_DETACH",
    "BODY_PAUSE", "BODY_RESUME", "BODY_STOP",
    "NODE_ENROLL",        # admit another compute node with its own bounded identity
    "SOP_RATIFY",         # promote an observed procedure into a reusable capability
    "ROTATE_FOUNDER_KEY",
)
MAX_TTL = timedelta(days=7)
CLOCK_SKEW = timedelta(minutes=5)


class FounderAuthError(ValueError):
    """Unauthenticated, replayed, expired or malformed founder interaction."""


def stamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise FounderAuthError("timezone-aware clock required")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise FounderAuthError("timestamp requires timezone")
    return parsed


def public_bytes(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def key_id(public_hex: str) -> str:
    raw = bytes.fromhex(public_hex)
    if len(raw) != 32:
        raise FounderAuthError("Ed25519 public key must be 32 bytes")
    return "ed25519:" + hashlib.sha256(raw).hexdigest()[:32]


def _signing_bytes(envelope: dict) -> bytes:
    unsigned = {k: v for k, v in envelope.items() if k != "signature"}
    return ("uniimente-greg-founder-command-v1\n" + canonical_json(unsigned)).encode("utf-8")


# -- key custody on the founder's own device ------------------------------------

def generate_founder_key(path: str | Path, passphrase: bytes | None) -> str:
    """Create a founder key file (PKCS8, optionally passphrase-encrypted, mode 0600).

    Returns the public key as hex. Run on a device Alfonso controls; only the
    public key is enrolled into a body. Refuses to overwrite an existing key.
    """
    path = Path(path)
    key = Ed25519PrivateKey.generate()
    encryption = (serialization.BestAvailableEncryption(passphrase) if passphrase
                  else serialization.NoEncryption())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, encryption)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(pem)
    return public_bytes(key.public_key()).hex()


def load_founder_key(path: str | Path, passphrase: bytes | None) -> Ed25519PrivateKey:
    path = Path(path)
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise FounderAuthError(f"founder key {path} is readable by others (mode {oct(mode)})")
    key = serialization.load_pem_private_key(path.read_bytes(), password=passphrase)
    if not isinstance(key, Ed25519PrivateKey):
        raise FounderAuthError("founder key is not Ed25519")
    return key


def sign_command(key: Ed25519PrivateKey, kind: str, body: dict, *, body_id: str,
                 now: datetime | None = None, ttl: timedelta = timedelta(hours=24),
                 nonce: str | None = None) -> dict:
    """Sign one founder command for exactly one body."""
    if kind not in COMMAND_KINDS:
        raise FounderAuthError(f"unknown command kind {kind!r}")
    if ttl <= timedelta(0) or ttl > MAX_TTL:
        raise FounderAuthError("command lifetime must be positive and at most 7 days")
    now = now or datetime.now(timezone.utc)
    envelope = {
        "version": 1, "kind": kind, "body_id": body_id,
        "founder_key_id": key_id(public_bytes(key.public_key()).hex()),
        "issued_at": stamp(now), "expires_at": stamp(now + ttl),
        "nonce": nonce or secrets.token_hex(16), "body": body,
    }
    envelope["signature"] = key.sign(_signing_bytes(envelope)).hex()
    return envelope


# -- verification inside the body ------------------------------------------------

class FounderVerifier:
    """Verifies signed founder commands against the body's enrolled keys.

    ``enrolled`` maps key_id -> public key hex for keys that are currently valid.
    ``seen_nonce`` is a callable answering whether a nonce was already accepted;
    the body backs it with retained ledger history.
    """

    def __init__(self, *, body_id: str, enrolled: dict[str, str], seen_nonce):
        self.body_id, self.enrolled, self.seen_nonce = body_id, dict(enrolled), seen_nonce

    def verify(self, envelope: dict, *, now: datetime | None = None,
               expected_kind: str | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        if not isinstance(envelope, dict):
            raise FounderAuthError("command must be a JSON object")
        required = {"version", "kind", "body_id", "founder_key_id", "issued_at",
                    "expires_at", "nonce", "body", "signature"}
        if set(envelope) != required:
            raise FounderAuthError("unknown or missing command field")
        if envelope["version"] != 1 or envelope["kind"] not in COMMAND_KINDS:
            raise FounderAuthError("unsupported command version or kind")
        if expected_kind and envelope["kind"] != expected_kind:
            raise FounderAuthError("wrong command kind")
        if envelope["body_id"] != self.body_id:
            raise FounderAuthError("command addressed to a different body")
        public_hex = self.enrolled.get(envelope["founder_key_id"])
        if public_hex is None:
            raise FounderAuthError("founder key not enrolled or revoked")
        if not isinstance(envelope["nonce"], str) or len(envelope["nonce"]) < 16:
            raise FounderAuthError("command nonce too short")
        issued, expires = instant(envelope["issued_at"]), instant(envelope["expires_at"])
        if expires - issued > MAX_TTL or expires <= issued:
            raise FounderAuthError("command lifetime invalid")
        if not issued - CLOCK_SKEW <= now < expires:
            raise FounderAuthError("command expired or issued in the future")
        if not isinstance(envelope["body"], dict):
            raise FounderAuthError("command body must be an object")
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex)).verify(
                bytes.fromhex(envelope["signature"]), _signing_bytes(envelope))
        except (InvalidSignature, ValueError) as exc:
            raise FounderAuthError("signature does not verify") from exc
        if self.seen_nonce(envelope["nonce"]):
            raise FounderAuthError("replayed command nonce")
        return envelope
