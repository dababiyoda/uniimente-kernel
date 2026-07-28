"""The Authorization Certificate — authority as a portable, verifiable artifact.

This is the central object of the Reality Aperture. It replaces the assumption
that authority is ambient state inside one engine's process.

A certificate states, in one self-contained signed object, that a specific
principal may cause one specific effect, once, before a deadline. It is
verifiable by anyone holding only a public key. Verification never requires a
call back to the Kernel, which is why the aperture stays safe under partition:
an effector that cannot reach the Kernel can still verify, and an effector that
cannot verify refuses.

Two rules give the object its force.

1. EVERY material field is inside the signature. `effect_binding_hash` covers
   all twenty binding fields. Change any one of them and the signature no longer
   verifies. There is no "unbound" field that an attacker can vary, which is the
   defect class that let a grant issued to actor A be redeemed by actor B.

2. Verification capability is not signing capability. The registry holds public
   keys only. Nothing in this module can produce a signature; that lives behind
   the SigningProvider interface in `keys.py`.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = "aperture/authorization-certificate/1.0.0"

# The twenty fields that constitute the authorized effect. Every one is inside
# the signature. This tuple is the single source of truth for what is bound;
# `effect_binding_hash` iterates it, so a field cannot be added to the dataclass
# and silently left unsigned.
BINDING_FIELDS = (
    "schema_version",
    "request_id",
    "authority_record_id",
    "actor_id",
    "organ_id",
    "workload_identity",
    "legal_principal",
    "capability_id",
    "action_class",
    "target_id",
    "payload_hash",
    "consequence_class",
    "policy_version",
    "constitution_version",
    "evidence_set_hash",
    "budget_reservation_id",
    "consequence_ceiling",
    "issued_at",
    "expires_at",
    "use_limit",
)


def canonical_json(obj: Any) -> bytes:
    """Deterministic serialization. Sorted keys, no incidental whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      default=str).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_payload(payload: Any) -> str:
    return "sha256:" + sha256_hex(canonical_json(payload))


def hash_evidence_set(evidence_refs: list[str]) -> str:
    """Order-independent hash of an evidence set.

    Sorted deliberately: the SET of evidence is what was authorized, and a
    caller reordering the list must not invalidate an otherwise valid
    certificate. Removing or substituting any member does invalidate it.
    """
    return "sha256:" + sha256_hex(canonical_json(sorted(evidence_refs)))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class CertificateError(Exception):
    """Base for every aperture refusal. Never raised to mean 'permitted'."""

    def __init__(self, message: str, *, code: str = "refused"):
        super().__init__(message)
        self.code = code


@dataclass
class AuthorizationCertificate:
    """One authorized effect, signed, self-describing, independently verifiable."""

    # --- the twenty binding fields -------------------------------------
    request_id: str
    authority_record_id: str
    actor_id: str
    organ_id: str
    workload_identity: str
    legal_principal: str
    capability_id: str
    action_class: str
    target_id: str
    payload_hash: str
    consequence_class: str
    policy_version: str
    constitution_version: str
    evidence_set_hash: str
    budget_reservation_id: str
    consequence_ceiling: float
    issued_at: str
    expires_at: str
    use_limit: int
    schema_version: str = SCHEMA_VERSION

    # --- signature envelope (NOT part of the binding hash) --------------
    algorithm: str = "ed25519"
    key_id: str = ""
    signature: str = ""

    def binding(self) -> dict:
        """The exact subset of fields covered by the signature."""
        d = asdict(self)
        return {k: d[k] for k in BINDING_FIELDS}

    def effect_binding_hash(self) -> str:
        return "sha256:" + sha256_hex(canonical_json(self.binding()))

    def signing_input(self) -> bytes:
        """Bytes the signer signs and the verifier checks.

        The algorithm and key_id are inside the signing input so that a
        certificate cannot be replayed under a different algorithm claim -
        an attacker cannot downgrade `algorithm` to something weaker and keep
        the signature meaningful.
        """
        return canonical_json({
            "effect_binding_hash": self.effect_binding_hash(),
            "algorithm": self.algorithm,
            "key_id": self.key_id,
        })

    def is_expired(self, now: datetime | None = None) -> bool:
        return (now or _now()) >= _parse(self.expires_at)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AuthorizationCertificate":
        return cls(**d)


def build_certificate(
    *,
    request_id: str,
    authority_record_id: str,
    actor_id: str,
    organ_id: str,
    workload_identity: str,
    legal_principal: str,
    capability_id: str,
    action_class: str,
    target_id: str,
    payload: Any,
    consequence_class: str,
    policy_version: str,
    constitution_version: str,
    evidence_refs: list[str],
    budget_reservation_id: str,
    consequence_ceiling: float,
    ttl_seconds: int,
    use_limit: int = 1,
) -> AuthorizationCertificate:
    """Assemble an UNSIGNED certificate. Signing is a separate, held privilege."""
    issued = _now()
    return AuthorizationCertificate(
        request_id=request_id,
        authority_record_id=authority_record_id,
        actor_id=actor_id,
        organ_id=organ_id,
        workload_identity=workload_identity,
        legal_principal=legal_principal,
        capability_id=capability_id,
        action_class=action_class,
        target_id=target_id,
        payload_hash=hash_payload(payload),
        consequence_class=consequence_class,
        policy_version=policy_version,
        constitution_version=constitution_version,
        evidence_set_hash=hash_evidence_set(evidence_refs),
        budget_reservation_id=budget_reservation_id,
        consequence_ceiling=float(consequence_ceiling),
        issued_at=rfc3339(issued),
        expires_at=rfc3339(issued.replace(microsecond=0)) if ttl_seconds == 0
        else rfc3339(issued + _timedelta(ttl_seconds)),
        use_limit=int(use_limit),
    )


def _timedelta(seconds: int):
    from datetime import timedelta
    return timedelta(seconds=seconds)
