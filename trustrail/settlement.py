"""Principal-authorized, idempotent settlement with commit-time revalidation."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol

from provenance.ledger import EvidenceLedger
from trustrail.credentials import CredentialIssuer, Signer, TrustRailRefused
from trustrail.models import (
    CredentialState,
    DisputeRecord,
    RealityStatus,
    SettlementAuthorization,
    SettlementIntent,
    SettlementReceipt,
    SettlementState,
    canonical_json,
    now_utc,
    object_hash,
    parse_time,
    rfc3339,
)
from trustrail.reputation import ScopedReputationLedger


ROUTER_ID = "spiffe://uniimente.internal/kernel/settlement-router"


def _amount(value: str) -> Decimal:
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise TrustRailRefused("settlement amount is not a decimal") from exc
    if not amount.is_finite() or amount <= 0:
        raise TrustRailRefused("settlement amount must be finite and positive")
    if value != format(amount, "f"):
        raise TrustRailRefused("settlement amount must use canonical base-10 notation")
    return amount


def sign_settlement_authorization(
    authorization: SettlementAuthorization, signer: Signer
) -> SettlementAuthorization:
    if signer.signer_id != authorization.authority_id:
        raise TrustRailRefused("authorization signer does not match authority identity")
    authorization.signature = signer.sign(canonical_json(authorization.signing_payload()))
    return authorization


@dataclass
class SettlementAuthorityRegistration:
    authority_id: str
    legal_principal: str
    signer: Signer
    adapters: frozenset[str]
    currencies: frozenset[str]
    reality_statuses: frozenset[RealityStatus]
    active: bool = True


class SettlementAuthorityRegistry:
    """Human-ratified signers allowed to bind a legal principal to payment."""

    def __init__(self, *, ratifiers: set[str] | None = None,
                 maximum_ttl_seconds: int = 3600):
        self.ratifiers = ratifiers or {"alfonso"}
        self.maximum_ttl = timedelta(seconds=maximum_ttl_seconds)
        self._entries: dict[str, SettlementAuthorityRegistration] = {}

    def register(self, *, authority_id: str, legal_principal: str, signer: Signer,
                 adapters: set[str], currencies: set[str],
                 reality_statuses: set[RealityStatus], ratified_by: str) -> None:
        if ratified_by not in self.ratifiers:
            raise TrustRailRefused("settlement authority lacks constitutional ratification")
        if signer.signer_id != authority_id or not legal_principal:
            raise TrustRailRefused("settlement authority identity mismatch")
        if not adapters or not currencies or not reality_statuses:
            raise TrustRailRefused("settlement authority scope cannot be empty")
        self._entries[authority_id] = SettlementAuthorityRegistration(
            authority_id=authority_id,
            legal_principal=legal_principal,
            signer=signer,
            adapters=frozenset(adapters),
            currencies=frozenset(currencies),
            reality_statuses=frozenset(reality_statuses),
        )

    def verify(self, authorization: SettlementAuthorization) -> SettlementAuthorityRegistration:
        reg = self._entries.get(authorization.authority_id)
        if reg is None or not reg.active:
            raise TrustRailRefused("unrecognized or inactive settlement authority")
        if authorization.legal_principal != reg.legal_principal:
            raise TrustRailRefused("authorization legal principal mismatch")
        if authorization.adapter_id not in reg.adapters:
            raise TrustRailRefused("authority is not scoped for this adapter")
        if authorization.currency not in reg.currencies:
            raise TrustRailRefused("authority is not scoped for this currency")
        if authorization.reality_status not in reg.reality_statuses:
            raise TrustRailRefused("authority is not scoped for this reality status")
        issued = parse_time(authorization.issued_at)
        expires = parse_time(authorization.expires_at)
        now = now_utc()
        if issued > now + timedelta(minutes=5):
            raise TrustRailRefused("authorization issue time is in the future")
        if expires <= now:
            raise TrustRailRefused("settlement authorization expired")
        if expires <= issued or expires - issued > self.maximum_ttl:
            raise TrustRailRefused("settlement authorization lifetime exceeds policy")
        _amount(authorization.max_amount)
        if not reg.signer.verify(
            canonical_json(authorization.signing_payload()), authorization.signature
        ):
            raise TrustRailRefused("settlement authorization signature invalid")
        return reg


class SettlementAdapter(Protocol):
    adapter_id: str
    supported_reality_statuses: frozenset[RealityStatus]

    def submit(self, intent: SettlementIntent) -> SettlementReceipt: ...
    def verify_receipt(self, intent: SettlementIntent, receipt: SettlementReceipt) -> bool: ...


class SandboxSettlementAdapter:
    """No-money adapter used to prove control flow and idempotency safely."""

    adapter_id = "sandbox-ledger-v1"
    supported_reality_statuses = frozenset({RealityStatus.SANDBOX, RealityStatus.SIMULATED})

    def __init__(self):
        self.calls = 0
        self._receipts: dict[str, SettlementReceipt] = {}

    def submit(self, intent: SettlementIntent) -> SettlementReceipt:
        if intent.reality_status not in self.supported_reality_statuses:
            raise TrustRailRefused("sandbox adapter cannot create a live external effect")
        prior = self._receipts.get(intent.idempotency_key)
        if prior:
            return prior
        self.calls += 1
        raw = {
            "intent_id": intent.intent_id,
            "payer": intent.payer,
            "payee": intent.payee,
            "amount": intent.amount,
            "currency": intent.currency,
            "idempotency_key": intent.idempotency_key,
            "status": "succeeded",
            "reality_status": intent.reality_status.value,
        }
        receipt = SettlementReceipt(
            receipt_id=str(uuid.uuid4()),
            intent_id=intent.intent_id,
            adapter_id=self.adapter_id,
            external_reference="sandbox:" + object_hash(raw).split(":", 1)[1][:32],
            idempotency_key=intent.idempotency_key,
            payer=intent.payer,
            payee=intent.payee,
            amount=intent.amount,
            currency=intent.currency,
            status="succeeded",
            reality_status=intent.reality_status,
            received_at=rfc3339(),
            raw_receipt_hash=object_hash(raw),
        )
        self._receipts[intent.idempotency_key] = receipt
        return receipt

    def verify_receipt(self, intent: SettlementIntent, receipt: SettlementReceipt) -> bool:
        return self._receipts.get(intent.idempotency_key) is receipt


class SettlementRouter:
    """Revalidates identity, authority, proof, and adapter receipt at commit."""

    def __init__(self, ledger: EvidenceLedger, issuer: CredentialIssuer,
                 authorities: SettlementAuthorityRegistry,
                 adapters: list[SettlementAdapter],
                 reputation: ScopedReputationLedger | None = None,
                 *, router_id: str = ROUTER_ID,
                 dispute_resolvers: set[str] | None = None):
        self.ledger = ledger
        self.issuer = issuer
        self.authorities = authorities
        self.adapters = {adapter.adapter_id: adapter for adapter in adapters}
        self.reputation = reputation or ScopedReputationLedger(ledger)
        self.router_id = router_id
        self.dispute_resolvers = frozenset(dispute_resolvers or {"alfonso"})
        self._intents: dict[str, SettlementIntent] = {}
        self._by_key: dict[str, str] = {}
        self._authorizations: dict[str, SettlementAuthorization] = {}
        self._receipts: dict[str, SettlementReceipt] = {}
        self._disputes: dict[str, DisputeRecord] = {}
        self._intent_dispute: dict[str, str] = {}
        self.rejected_before_effect = 0
        self.unauthorized_external_effects = 0
        self.integrity_incidents = 0

    def _refuse(self, message: str) -> None:
        raise TrustRailRefused(message)

    @staticmethod
    def _key_payload(authorization: SettlementAuthorization, amount: Decimal) -> dict:
        return {
            "credential_id": authorization.credential_id,
            "authorization_id": authorization.authorization_id,
            "payer": authorization.payer,
            "payee": authorization.payee,
            "amount": str(amount),
            "currency": authorization.currency,
            "purpose": authorization.purpose,
            "adapter_id": authorization.adapter_id,
            "reality_status": authorization.reality_status.value,
        }

    def create_intent(self, authorization: SettlementAuthorization, *,
                      requested_by: str, amount: str) -> SettlementIntent:
        try:
            chain_ok, chain_detail = self.ledger.verify_chain()
            if not chain_ok:
                self._refuse(f"evidence ledger integrity failure: {chain_detail}")
            credential = self.issuer.verify(authorization.credential_id)
            self.authorities.verify(authorization)
            requested = _amount(amount)
            maximum = _amount(authorization.max_amount)
            if requested > maximum:
                self._refuse("requested amount exceeds signed authorization")
            if credential.legal_principal != authorization.legal_principal:
                self._refuse("credential and authorization principals differ")
            if requested_by not in {
                credential.actor_id, credential.legal_principal, authorization.authority_id
            }:
                self._refuse("requester is not bound to the credential or principal")
            if authorization.adapter_id not in self.adapters:
                self._refuse("settlement adapter is not installed")
            adapter = self.adapters[authorization.adapter_id]
            if authorization.reality_status not in adapter.supported_reality_statuses:
                self._refuse("adapter does not support the authorized reality status")
            if credential.reality_status != authorization.reality_status:
                self._refuse("proof and settlement reality statuses differ")
        except TrustRailRefused:
            self.rejected_before_effect += 1
            raise

        key_payload = self._key_payload(authorization, requested)
        idempotency_key = object_hash(key_payload)
        prior_id = self._by_key.get(idempotency_key)
        if prior_id:
            return self._intents[prior_id]
        intent = SettlementIntent(
            intent_id=str(uuid.uuid4()),
            credential_id=authorization.credential_id,
            authorization_id=authorization.authorization_id,
            requested_by=requested_by,
            legal_principal=authorization.legal_principal,
            payer=authorization.payer,
            payee=authorization.payee,
            amount=str(requested),
            currency=authorization.currency,
            purpose=authorization.purpose,
            adapter_id=authorization.adapter_id,
            idempotency_key=idempotency_key,
            reality_status=authorization.reality_status,
            created_at=rfc3339(),
        )
        self._intents[intent.intent_id] = intent
        self._by_key[idempotency_key] = intent.intent_id
        self._authorizations[authorization.authorization_id] = authorization
        self.ledger.append("settlement_authorization", authorization.to_dict())
        self.ledger.append("settlement_intent", intent.to_dict())
        return intent

    def commit(self, intent_id: str) -> SettlementReceipt:
        intent = self.get_intent(intent_id)
        prior = self._receipts.get(intent_id)
        if prior and intent.state == SettlementState.RECONCILED:
            return prior
        if intent_id in self._intent_dispute or intent.state == SettlementState.DISPUTED:
            self.rejected_before_effect += 1
            self._refuse("settlement intent is disputed")
        if intent.state not in {
            SettlementState.AUTHORIZED, SettlementState.SUBMITTED, SettlementState.FAILED
        }:
            self.rejected_before_effect += 1
            self._refuse(f"settlement intent cannot commit from {intent.state.value}")
        try:
            chain_ok, chain_detail = self.ledger.verify_chain()
            if not chain_ok:
                self._refuse(f"evidence ledger integrity failure: {chain_detail}")
            credential = self.issuer.verify(intent.credential_id)
            authorization = self._authorizations[intent.authorization_id]
            self.authorities.verify(authorization)
            if intent.amount != str(_amount(intent.amount)):
                self._refuse("intent amount encoding changed after authorization")
            if _amount(intent.amount) > _amount(authorization.max_amount):
                self._refuse("intent exceeds authorization at commit")
            if intent.idempotency_key != object_hash(
                self._key_payload(authorization, _amount(intent.amount))
            ):
                self._refuse("intent changed after its idempotency binding was created")
            bindings = (
                (intent.credential_id, authorization.credential_id),
                (intent.legal_principal, authorization.legal_principal),
                (intent.payer, authorization.payer),
                (intent.payee, authorization.payee),
                (intent.currency, authorization.currency),
                (intent.purpose, authorization.purpose),
                (intent.adapter_id, authorization.adapter_id),
                (intent.reality_status, authorization.reality_status),
            )
            if any(left != right for left, right in bindings):
                self._refuse("intent binding changed after authorization")
            adapter = self.adapters[intent.adapter_id]
            if intent.reality_status not in adapter.supported_reality_statuses:
                self._refuse("adapter cannot execute this reality status")
        except (KeyError, TrustRailRefused) as exc:
            self.rejected_before_effect += 1
            if isinstance(exc, KeyError):
                raise TrustRailRefused("authorization or adapter disappeared before commit") from exc
            raise

        intent.state = SettlementState.SUBMITTED
        self.ledger.append("settlement_event", {
            "type": "settlement.submitted",
            "intent_id": intent.intent_id,
            "credential_id": intent.credential_id,
            "adapter_id": intent.adapter_id,
            "at": rfc3339(),
        })
        try:
            receipt = adapter.submit(intent)
        except Exception:
            intent.state = SettlementState.FAILED
            self.ledger.append("settlement_event", {
                "type": "settlement.failed",
                "intent_id": intent.intent_id,
                "at": rfc3339(),
            })
            raise

        expected = (
            receipt.intent_id == intent.intent_id
            and receipt.adapter_id == intent.adapter_id
            and receipt.idempotency_key == intent.idempotency_key
            and receipt.payer == intent.payer
            and receipt.payee == intent.payee
            and receipt.amount == intent.amount
            and receipt.currency == intent.currency
            and receipt.reality_status == intent.reality_status
            and receipt.status == "succeeded"
            and adapter.verify_receipt(intent, receipt)
        )
        if not expected:
            intent.state = SettlementState.DISPUTED
            self.integrity_incidents += 1
            self.issuer.set_state(
                credential.credential_id,
                CredentialState.SUSPENDED,
                authority_id=self.router_id,
                reason="settlement receipt failed reconciliation",
            )
            self.ledger.append("settlement_event", {
                "type": "settlement.reconciliation_failed",
                "intent_id": intent.intent_id,
                "at": rfc3339(),
            })
            raise TrustRailRefused("adapter receipt failed reconciliation")

        receipt.reconciled = True
        intent.state = SettlementState.RECONCILED
        self._receipts[intent_id] = receipt
        self.ledger.append("settlement_receipt", receipt.to_dict())
        self.ledger.append("settlement_event", {
            "type": "settlement.reconciled",
            "intent_id": intent.intent_id,
            "credential_id": credential.credential_id,
            "receipt_id": receipt.receipt_id,
            "at": rfc3339(),
        })
        self.reputation.record_reconciled(credential, intent, receipt)
        return receipt

    def open_dispute(self, *, credential_id: str, intent_id: str | None,
                     opened_by: str, reason: str) -> DisputeRecord:
        credential = self.issuer.get(credential_id)
        allowed = {"alfonso", credential.legal_principal, credential.verifier_id}
        if opened_by not in allowed:
            self._refuse("dispute opener lacks standing")
        if not reason.strip():
            self._refuse("dispute reason is required")
        if intent_id is not None:
            intent = self.get_intent(intent_id)
            if intent.credential_id != credential_id:
                self._refuse("dispute intent does not use this credential")
            prior_id = self._intent_dispute.get(intent_id)
            if prior_id:
                return self._disputes[prior_id]
            intent.state = SettlementState.DISPUTED
        dispute = DisputeRecord(
            dispute_id=str(uuid.uuid4()),
            credential_id=credential_id,
            intent_id=intent_id,
            opened_by=opened_by,
            reason=reason.strip(),
            opened_at=rfc3339(),
        )
        self._disputes[dispute.dispute_id] = dispute
        if intent_id:
            self._intent_dispute[intent_id] = dispute.dispute_id
        self.issuer.set_state(
            credential_id,
            CredentialState.SUSPENDED,
            authority_id=self.router_id,
            reason=f"open dispute {dispute.dispute_id}",
        )
        self.ledger.append("settlement_dispute", dispute.to_dict())
        self.reputation.mark_disputed(
            dispute_id=dispute.dispute_id,
            intent_id=intent_id,
            credential=credential,
        )
        return dispute

    def resolve_dispute(self, dispute_id: str, *, resolved_by: str,
                        resolution: str, note: str) -> DisputeRecord:
        try:
            dispute = self._disputes[dispute_id]
        except KeyError as exc:
            raise TrustRailRefused("unknown dispute") from exc
        credential = self.issuer.get(dispute.credential_id)
        if resolved_by not in self.dispute_resolvers | {credential.legal_principal}:
            self._refuse("dispute resolver lacks constitutional authority")
        if dispute.state != "open":
            return dispute
        if resolution not in {"upheld", "invalidated"}:
            self._refuse("resolution must be upheld or invalidated")
        dispute.state = resolution
        new_state = (
            CredentialState.ACTIVE if resolution == "upheld" else CredentialState.REVOKED
        )
        self.issuer.set_state(
            credential.credential_id,
            new_state,
            authority_id=self.router_id,
            reason=f"dispute {dispute_id} {resolution}: {note}",
        )
        if dispute.intent_id:
            intent = self.get_intent(dispute.intent_id)
            if resolution == "upheld":
                intent.state = (
                    SettlementState.RECONCILED
                    if dispute.intent_id in self._receipts
                    else SettlementState.AUTHORIZED
                )
                self._intent_dispute.pop(dispute.intent_id, None)
            else:
                intent.state = SettlementState.DISPUTED
        self.ledger.append("settlement_dispute", {
            **dispute.to_dict(),
            "type": "settlement.dispute_resolved",
            "resolved_by": resolved_by,
            "resolution": resolution,
            "note": note,
            "resolved_at": rfc3339(),
        })
        return dispute

    def get_intent(self, intent_id: str) -> SettlementIntent:
        try:
            return self._intents[intent_id]
        except KeyError as exc:
            raise TrustRailRefused("unknown settlement intent") from exc

    def metrics(self) -> dict[str, int]:
        return {
            "settlement_intents": len(self._intents),
            "reconciled_settlements": len(self._receipts),
            "rejected_before_effect": self.rejected_before_effect,
            "unauthorized_external_effects": self.unauthorized_external_effects,
            "integrity_incidents": self.integrity_incidents,
            "open_disputes": sum(d.state == "open" for d in self._disputes.values()),
        }
