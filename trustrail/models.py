"""Typed, immutable-by-convention objects for proof, settlement, and dispute."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RealityStatus(str, Enum):
    LIVE = "LIVE"
    SANDBOX = "SANDBOX"
    SIMULATED = "SIMULATED"
    PROPOSED = "PROPOSED"


class AttestationDecision(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DISPUTED = "disputed"


class CredentialState(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class SettlementState(str, Enum):
    AUTHORIZED = "authorized"
    SUBMITTED = "submitted"
    RECONCILED = "reconciled"
    FAILED = "failed"
    DISPUTED = "disputed"
    REVERSED = "reversed"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def rfc3339(dt: datetime | None = None) -> str:
    return (dt or now_utc()).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def object_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def _enum_dict(value: dict) -> dict:
    return {key: (item.value if isinstance(item, Enum) else item) for key, item in value.items()}


@dataclass
class VerifierAttestation:
    verifier_id: str
    action_id: str
    outcome_hash: str
    receipt_hash: str
    decision: AttestationDecision
    evidence_refs: list[str]
    policy_version: str
    observed_at: str
    expires_at: str
    reality_status: RealityStatus
    attestation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    signature: str = ""

    def signing_payload(self) -> dict:
        data = _enum_dict(asdict(self))
        data.pop("signature", None)
        return data

    def to_dict(self) -> dict:
        return _enum_dict(asdict(self))


@dataclass
class VerifiedOutcomeCredential:
    credential_id: str
    issuer: str
    action_id: str
    actor_id: str
    legal_principal: str
    action_class: str
    verifier_id: str
    outcome_hash: str
    receipt_hash: str
    witness_id: str
    evidence_refs: list[str]
    policy_version: str
    verification_result: str
    reality_status: RealityStatus
    valid_from: str
    valid_until: str
    signature_algorithm: str
    signature: str = ""

    def signing_payload(self) -> dict:
        data = _enum_dict(asdict(self))
        data.pop("signature", None)
        return data

    def as_verifiable_credential(self, state: CredentialState) -> dict:
        return {
            "@context": [
                "https://www.w3.org/ns/credentials/v2",
                "https://schemas.uniimente.internal/trustrail/v1",
            ],
            "id": f"urn:uuid:{self.credential_id}",
            "type": ["VerifiableCredential", "VerifiedOutcomeCredential"],
            "issuer": self.issuer,
            "validFrom": self.valid_from,
            "validUntil": self.valid_until,
            "credentialSubject": {
                "actionId": self.action_id,
                "actorId": self.actor_id,
                "legalPrincipal": self.legal_principal,
                "actionClass": self.action_class,
                "verifierId": self.verifier_id,
                "outcomeHash": self.outcome_hash,
                "receiptHash": self.receipt_hash,
                "witnessId": self.witness_id,
                "evidenceRefs": list(self.evidence_refs),
                "policyVersion": self.policy_version,
                "verificationResult": self.verification_result,
                "realityStatus": self.reality_status.value,
            },
            "credentialStatus": {
                "id": f"urn:uuid:{self.credential_id}#status",
                "type": "UniimenteCredentialStatus",
                "status": state.value,
            },
            "proof": {
                "type": self.signature_algorithm,
                "created": self.valid_from,
                "verificationMethod": self.issuer,
                "proofValue": self.signature,
            },
        }


@dataclass
class SettlementAuthorization:
    authority_id: str
    legal_principal: str
    credential_id: str
    payer: str
    payee: str
    max_amount: str
    currency: str
    purpose: str
    adapter_id: str
    reality_status: RealityStatus
    issued_at: str
    expires_at: str
    authorization_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    signature: str = ""

    def signing_payload(self) -> dict:
        data = _enum_dict(asdict(self))
        data.pop("signature", None)
        return data

    def to_dict(self) -> dict:
        return _enum_dict(asdict(self))


@dataclass
class SettlementIntent:
    intent_id: str
    credential_id: str
    authorization_id: str
    requested_by: str
    legal_principal: str
    payer: str
    payee: str
    amount: str
    currency: str
    purpose: str
    adapter_id: str
    idempotency_key: str
    reality_status: RealityStatus
    created_at: str
    state: SettlementState = SettlementState.AUTHORIZED

    def to_dict(self) -> dict:
        return _enum_dict(asdict(self))


@dataclass
class SettlementReceipt:
    receipt_id: str
    intent_id: str
    adapter_id: str
    external_reference: str
    idempotency_key: str
    payer: str
    payee: str
    amount: str
    currency: str
    status: str
    reality_status: RealityStatus
    received_at: str
    raw_receipt_hash: str
    reconciled: bool = False

    def to_dict(self) -> dict:
        return _enum_dict(asdict(self))


@dataclass
class DisputeRecord:
    dispute_id: str
    credential_id: str
    intent_id: str | None
    opened_by: str
    reason: str
    opened_at: str
    state: str = "open"

    def to_dict(self) -> dict:
        return asdict(self)
