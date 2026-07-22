"""Independent verifier attestations and portable outcome credentials."""
from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from provenance.ledger import EvidenceLedger, sha256_json
from trustrail.models import (
    AttestationDecision,
    CredentialState,
    VerifiedOutcomeCredential,
    VerifierAttestation,
    canonical_json,
    now_utc,
    parse_time,
    rfc3339,
)


class TrustRailRefused(ValueError):
    """A requested transition failed closed before an external effect."""


class Signer(Protocol):
    signer_id: str
    algorithm: str

    def sign(self, payload: bytes) -> str: ...
    def verify(self, payload: bytes, signature: str) -> bool: ...


class HMACSigner:
    """Deterministic development signer.

    Production deployments must inject an asymmetric/KMS-backed signer. The
    built-in fallback key is structurally refused outside test/development.
    """

    algorithm = "HmacSha256Signature2026"
    _DEFAULT = b"uniimente-development-only-key"

    def __init__(self, signer_id: str, *, key: bytes | None = None,
                 environment: str = "development"):
        self.signer_id = signer_id
        env_key = os.environ.get("UNIIMENTE_TRUSTRAIL_HMAC_KEY")
        chosen = key or (env_key.encode("utf-8") if env_key else self._DEFAULT)
        if environment not in {"development", "test"} and chosen == self._DEFAULT:
            raise TrustRailRefused("production credential signing requires an injected secret/KMS signer")
        if len(chosen) < 16:
            raise TrustRailRefused("signing key is too short")
        self._key = chosen

    def sign(self, payload: bytes) -> str:
        return "hmac-sha256:" + hmac.new(self._key, payload, hashlib.sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        return hmac.compare_digest(self.sign(payload), signature)


def sign_attestation(attestation: VerifierAttestation, signer: Signer) -> VerifierAttestation:
    if signer.signer_id != attestation.verifier_id:
        raise TrustRailRefused("attestation signer does not match verifier identity")
    attestation.signature = signer.sign(canonical_json(attestation.signing_payload()))
    return attestation


@dataclass
class VerifierRegistration:
    verifier_id: str
    owner_organ: str
    signer: Signer
    action_classes: frozenset[str]
    active: bool = True


class VerifierRegistry:
    """Human-ratified verifier trust roots; no verifier self-registers."""

    def __init__(self, *, ratifiers: set[str] | None = None):
        self.ratifiers = ratifiers or {"alfonso"}
        self._entries: dict[str, VerifierRegistration] = {}

    def register(self, *, verifier_id: str, owner_organ: str, signer: Signer,
                 action_classes: set[str], ratified_by: str) -> None:
        if ratified_by not in self.ratifiers:
            raise TrustRailRefused("verifier registration lacks constitutional ratification")
        if signer.signer_id != verifier_id:
            raise TrustRailRefused("verifier signer identity mismatch")
        if not verifier_id or verifier_id == "UNIIMENTE" or not action_classes:
            raise TrustRailRefused("invalid verifier registration")
        self._entries[verifier_id] = VerifierRegistration(
            verifier_id, owner_organ, signer, frozenset(action_classes))

    def verify(self, attestation: VerifierAttestation, *, actor_id: str,
               action_class: str) -> VerifierRegistration:
        reg = self._entries.get(attestation.verifier_id)
        if reg is None or not reg.active:
            raise TrustRailRefused("unrecognized or inactive verifier")
        if attestation.verifier_id == actor_id:
            raise TrustRailRefused("actor may not independently verify its own outcome")
        if action_class not in reg.action_classes:
            raise TrustRailRefused("verifier is not ratified for this action class")
        if attestation.decision != AttestationDecision.ACCEPTED:
            raise TrustRailRefused(f"verifier decision is {attestation.decision.value}, not accepted")
        observed = parse_time(attestation.observed_at)
        expires = parse_time(attestation.expires_at)
        if observed > now_utc() + timedelta(minutes=5):
            raise TrustRailRefused("verifier observation time is in the future")
        if expires <= observed:
            raise TrustRailRefused("verifier attestation has an invalid lifetime")
        if now_utc() >= expires:
            raise TrustRailRefused("verifier attestation expired")
        if not reg.signer.verify(canonical_json(attestation.signing_payload()), attestation.signature):
            raise TrustRailRefused("verifier attestation signature invalid")
        return reg


class CredentialIssuer:
    """Issues credentials only from a reconciled ledger path plus independent proof."""

    def __init__(self, ledger: EvidenceLedger, verifiers: VerifierRegistry,
                 signer: Signer, *, credential_ttl_seconds: int = 86400,
                 status_authorities: set[str] | None = None):
        self.ledger = ledger
        self.verifiers = verifiers
        self.signer = signer
        self.credential_ttl = timedelta(seconds=credential_ttl_seconds)
        self.status_authorities = status_authorities or {
            "alfonso", "spiffe://uniimente.internal/kernel/settlement-router"
        }
        self._credentials: dict[str, VerifiedOutcomeCredential] = {}
        self._states: dict[str, CredentialState] = {}
        self._by_action: dict[str, str] = {}

    @staticmethod
    def _one(records, description: str):
        if len(records) != 1:
            raise TrustRailRefused(f"expected exactly one {description}; found {len(records)}")
        return records[0]

    def issue(self, action_id: str, attestation: VerifierAttestation) -> VerifiedOutcomeCredential:
        chain_ok, chain_detail = self.ledger.verify_chain()
        if not chain_ok:
            raise TrustRailRefused(f"evidence ledger integrity failure: {chain_detail}")
        if attestation.action_id != action_id:
            raise TrustRailRefused("attestation action binding mismatch")
        outcomes = [r for r in self.ledger.by_type("outcome")
                    if r.payload.get("action_ref") == action_id]
        outcome = self._one(outcomes, "outcome record")
        receipts = [r for r in self.ledger.by_type("receipt")
                    if r.payload.get("action_id") == action_id]
        receipt = self._one(receipts, "execution receipt")
        recorded = [r for r in self.ledger.by_type("event")
                    if r.payload.get("type") == "action.recorded"
                    and r.payload.get("action_id") == action_id]
        final_event = self._one(recorded, "reconciliation event")
        if final_event.payload.get("reconciled") is not True:
            raise TrustRailRefused("action is not reconciled")
        witness_id = receipt.payload.get("witness_id")
        witnesses = [r for r in self.ledger.by_type("witness")
                     if r.payload.get("witness_id") == witness_id]
        witness = self._one(witnesses, "commit witness")

        target = str(witness.payload.get("target", ""))
        if target.startswith("sandbox:") and attestation.reality_status.value == "LIVE":
            raise TrustRailRefused("sandbox action cannot produce live proof")

        expected_outcome_hash = sha256_json(outcome.payload)
        if attestation.outcome_hash != expected_outcome_hash:
            raise TrustRailRefused("attestation does not bind the ledgered outcome")
        if attestation.receipt_hash != receipt.hash:
            raise TrustRailRefused("attestation does not bind the execution receipt")
        if attestation.policy_version != witness.payload.get("policy_version"):
            raise TrustRailRefused("attestation policy version mismatch")
        if not attestation.evidence_refs:
            raise TrustRailRefused("independent attestation requires evidence references")
        action_class = witness.payload.get("action_class", "")
        actor_id = witness.payload.get("actor", "")
        self.verifiers.verify(attestation, actor_id=actor_id, action_class=action_class)

        prior_id = self._by_action.get(action_id)
        if prior_id:
            prior = self._credentials[prior_id]
            if prior.outcome_hash != expected_outcome_hash:
                raise TrustRailRefused("action already has a credential for a different outcome")
            return prior

        issued = now_utc()
        evidence_refs = sorted(set(
            list(witness.payload.get("evidence_refs") or [])
            + list(outcome.payload.get("evidence_refs") or [])
            + list(attestation.evidence_refs)
        ))
        credential = VerifiedOutcomeCredential(
            credential_id=str(uuid.uuid4()),
            issuer=self.signer.signer_id,
            action_id=action_id,
            actor_id=actor_id,
            legal_principal=witness.payload.get("legal_principal", ""),
            action_class=action_class,
            verifier_id=attestation.verifier_id,
            outcome_hash=expected_outcome_hash,
            receipt_hash=receipt.hash,
            witness_id=witness_id,
            evidence_refs=evidence_refs,
            policy_version=witness.payload.get("policy_version", ""),
            verification_result=attestation.decision.value,
            reality_status=attestation.reality_status,
            valid_from=rfc3339(issued),
            valid_until=rfc3339(issued + self.credential_ttl),
            signature_algorithm=self.signer.algorithm,
        )
        credential.signature = self.signer.sign(canonical_json(credential.signing_payload()))
        self._credentials[credential.credential_id] = credential
        self._states[credential.credential_id] = CredentialState.ACTIVE
        self._by_action[action_id] = credential.credential_id
        self.ledger.append("verifier_attestation", attestation.to_dict())
        self.ledger.append("outcome_credential", credential.as_verifiable_credential(CredentialState.ACTIVE))
        return credential

    def get(self, credential_id: str) -> VerifiedOutcomeCredential:
        try:
            return self._credentials[credential_id]
        except KeyError as exc:
            raise TrustRailRefused("unknown outcome credential") from exc

    def state(self, credential_id: str) -> CredentialState:
        self.get(credential_id)
        return self._states[credential_id]

    def verify(self, credential_id: str) -> VerifiedOutcomeCredential:
        credential = self.get(credential_id)
        self.verify_integrity(credential_id)
        if self.state(credential_id) != CredentialState.ACTIVE:
            raise TrustRailRefused(f"credential is {self.state(credential_id).value}")
        if now_utc() >= parse_time(credential.valid_until):
            raise TrustRailRefused("credential expired")
        return credential

    def verify_integrity(self, credential_id: str) -> VerifiedOutcomeCredential:
        credential = self.get(credential_id)
        chain_ok, chain_detail = self.ledger.verify_chain()
        if not chain_ok:
            raise TrustRailRefused(f"evidence ledger integrity failure: {chain_detail}")
        if not self.signer.verify(canonical_json(credential.signing_payload()), credential.signature):
            raise TrustRailRefused("credential signature invalid")
        return credential

    def set_state(self, credential_id: str, state: CredentialState, *,
                  authority_id: str, reason: str) -> None:
        if authority_id not in self.status_authorities:
            raise TrustRailRefused("credential status change lacks authority")
        old = self.state(credential_id)
        if old == CredentialState.REVOKED and state != CredentialState.REVOKED:
            raise TrustRailRefused("revoked credentials cannot be reactivated")
        self._states[credential_id] = state
        self.ledger.append("credential_status", {
            "type": "credential.status_changed",
            "credential_id": credential_id,
            "from": old.value,
            "to": state.value,
            "authority_id": authority_id,
            "reason": reason,
            "at": rfc3339(),
        })
