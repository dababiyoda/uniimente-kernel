"""Executable five-closure registration for the proof-to-settlement rail."""
from __future__ import annotations

import uuid
from datetime import timedelta

from closure.framework import ModuleClosures
from provenance.ledger import EvidenceLedger, sha256_json
from trustrail.credentials import (
    CredentialIssuer,
    HMACSigner,
    TrustRailRefused,
    VerifierRegistry,
    sign_attestation,
)
from trustrail.models import (
    AttestationDecision,
    RealityStatus,
    SettlementAuthorization,
    VerifierAttestation,
    now_utc,
    rfc3339,
)
from trustrail.reputation import ScopedReputationLedger
from trustrail.settlement import (
    SandboxSettlementAdapter,
    SettlementAuthorityRegistry,
    SettlementRouter,
    sign_settlement_authorization,
)


def _stack():
    ledger = EvidenceLedger("sha256:" + "0" * 64)
    action_id = str(uuid.uuid4())
    witness_id = str(uuid.uuid4())
    witness = {
        "witness_id": witness_id,
        "actor": "agent:closure",
        "legal_principal": "alfonso_lopez",
        "action_class": "draft.publish",
        "target": "sandbox:outbox",
        "policy_version": "1.0.0",
        "evidence_refs": ["sha256:" + "a" * 64],
    }
    ledger.append("witness", witness)
    receipt = ledger.append("receipt", {
        "action_id": action_id,
        "witness_id": witness_id,
        "grant_id": str(uuid.uuid4()),
        "result": {"observed_outcome": "draft queued"},
    })
    outcome = {
        "outcome_id": str(uuid.uuid4()),
        "action_ref": action_id,
        "external_observation": "draft queued",
        "evidence_refs": ["sha256:" + "b" * 64],
    }
    ledger.append("outcome", outcome)
    ledger.append("event", {
        "type": "action.recorded", "action_id": action_id, "reconciled": True
    })

    verifier_signer = HMACSigner("did:uniimente:verifier:closure", key=b"v" * 32)
    verifiers = VerifierRegistry()
    verifiers.register(
        verifier_id=verifier_signer.signer_id,
        owner_organ="adversarial-intelligence",
        signer=verifier_signer,
        action_classes={"draft.publish"},
        ratified_by="alfonso",
    )
    issuer = CredentialIssuer(
        ledger,
        verifiers,
        HMACSigner("did:uniimente:issuer:closure", key=b"i" * 32),
    )
    now = now_utc()
    attestation = sign_attestation(VerifierAttestation(
        verifier_id=verifier_signer.signer_id,
        action_id=action_id,
        outcome_hash=sha256_json(outcome),
        receipt_hash=receipt.hash,
        decision=AttestationDecision.ACCEPTED,
        evidence_refs=["sensor:closure:1"],
        policy_version="1.0.0",
        observed_at=rfc3339(now),
        expires_at=rfc3339(now + timedelta(minutes=30)),
        reality_status=RealityStatus.SANDBOX,
    ), verifier_signer)
    credential = issuer.issue(action_id, attestation)

    adapter = SandboxSettlementAdapter()
    authority_signer = HMACSigner("did:uniimente:authority:closure", key=b"a" * 32)
    authorities = SettlementAuthorityRegistry()
    authorities.register(
        authority_id=authority_signer.signer_id,
        legal_principal="alfonso_lopez",
        signer=authority_signer,
        adapters={adapter.adapter_id},
        currencies={"USD"},
        reality_statuses={RealityStatus.SANDBOX},
        ratified_by="alfonso",
    )
    reputation = ScopedReputationLedger(ledger)
    router = SettlementRouter(ledger, issuer, authorities, [adapter], reputation)
    authorization = sign_settlement_authorization(SettlementAuthorization(
        authority_id=authority_signer.signer_id,
        legal_principal="alfonso_lopez",
        credential_id=credential.credential_id,
        payer="sandbox:treasury",
        payee="sandbox:agent:closure",
        max_amount="10.00",
        currency="USD",
        purpose="verified draft delivery",
        adapter_id=adapter.adapter_id,
        reality_status=RealityStatus.SANDBOX,
        issued_at=rfc3339(now),
        expires_at=rfc3339(now + timedelta(minutes=30)),
    ), authority_signer)
    return ledger, issuer, router, adapter, credential, authorization, reputation


def register_trustrail_closures(registry) -> None:
    def technical():
        _, _, router, adapter, credential, authorization, _ = _stack()
        intent = router.create_intent(
            authorization, requested_by=credential.actor_id, amount="10.00"
        )
        receipt = router.commit(intent.intent_id)
        ok = receipt.reconciled and adapter.calls == 1
        return ok, "verified proof -> signed authority -> sandbox receipt -> reconciliation executes"

    def authority():
        _, _, router, adapter, credential, authorization, _ = _stack()
        try:
            router.create_intent(
                authorization, requested_by=credential.actor_id, amount="10.01"
            )
            return False, "amount above signed ceiling was admitted"
        except TrustRailRefused:
            return adapter.calls == 0, "authority overflow refused before adapter invocation"

    def evidence():
        ledger, _, router, _, credential, authorization, _ = _stack()
        intent = router.create_intent(
            authorization, requested_by=credential.actor_id, amount="10.00"
        )
        router.commit(intent.intent_id)
        ok, msg = ledger.verify_chain()
        kinds = {r.record_type for r in ledger.records}
        required = {
            "verifier_attestation", "outcome_credential", "settlement_authorization",
            "settlement_intent", "settlement_receipt", "reputation_evidence",
        }
        return ok and required <= kinds, f"{msg}; complete proof and settlement lineage present"

    def economic():
        _, _, router, adapter, credential, authorization, _ = _stack()
        intent = router.create_intent(
            authorization, requested_by=credential.actor_id, amount="10.00"
        )
        first = router.commit(intent.intent_id)
        second = router.commit(intent.intent_id)
        return first.receipt_id == second.receipt_id and adapter.calls == 1, \
            "idempotent replay preserves one adapter call and one receipt"

    def regenerative():
        _, _, router, adapter, credential, authorization, _ = _stack()
        intent = router.create_intent(
            authorization, requested_by=credential.actor_id, amount="10.00"
        )
        router.open_dispute(
            credential_id=credential.credential_id,
            intent_id=intent.intent_id,
            opened_by=credential.legal_principal,
            reason="closure challenge",
        )
        try:
            router.commit(intent.intent_id)
            return False, "disputed settlement executed"
        except TrustRailRefused:
            metrics = router.metrics()
            ok = adapter.calls == 0 and metrics["unauthorized_external_effects"] == 0
            return ok, "dispute freezes settlement; zero unauthorized external effects"

    registry.register(ModuleClosures("trustrail", {
        "technical": technical,
        "authority": authority,
        "evidence": evidence,
        "economic": economic,
        "regenerative": regenerative,
    }))
