"""Adversarial tests for proof -> settlement -> scoped reputation."""
from __future__ import annotations

import inspect
import json
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from integrations.openclaw import create_server
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
    CredentialState,
    RealityStatus,
    SettlementAuthorization,
    SettlementState,
    VerifierAttestation,
    now_utc,
    rfc3339,
)
from trustrail.openclaw import OpenClawTrustBoundary
from trustrail.rail import ProofToSettlementRail
from trustrail.reputation import ScopedReputationLedger
from trustrail.settlement import (
    SandboxSettlementAdapter,
    SettlementAuthorityRegistry,
    SettlementRouter,
    sign_settlement_authorization,
)


@pytest.fixture
def stack():
    ledger = EvidenceLedger("sha256:" + "c" * 64)
    action_id = str(uuid.uuid4())
    witness_id = str(uuid.uuid4())
    actor_id = "agent:openclaw:test"
    witness = {
        "witness_id": witness_id,
        "actor": actor_id,
        "legal_principal": "principal:test",
        "action_class": "device.inspect",
        "target": "sandbox:device/thermostat-1",
        "policy_version": "test-1",
        "evidence_refs": ["sensor:thermostat-1:before"],
    }
    ledger.append("witness", witness)
    execution_receipt = ledger.append("receipt", {
        "action_id": action_id,
        "witness_id": witness_id,
        "grant_id": str(uuid.uuid4()),
        "result": {"observed_outcome": "temperature read"},
    })
    outcome = {
        "outcome_id": str(uuid.uuid4()),
        "action_ref": action_id,
        "external_observation": "temperature read",
        "result_class": "positive",
        "evidence_refs": ["sensor:thermostat-1:after"],
    }
    ledger.append("outcome", outcome)
    ledger.append("event", {
        "type": "action.recorded",
        "action_id": action_id,
        "reconciled": True,
    })

    verifier_signer = HMACSigner("did:test:verifier", key=b"verifier-test-key-32-bytes-long")
    verifiers = VerifierRegistry(ratifiers={"human:test"})
    verifiers.register(
        verifier_id=verifier_signer.signer_id,
        owner_organ="test-lab",
        signer=verifier_signer,
        action_classes={"device.inspect"},
        ratified_by="human:test",
    )
    issuer = CredentialIssuer(
        ledger,
        verifiers,
        HMACSigner("did:test:issuer", key=b"issuer-test-key-is-32-bytes-long"),
        status_authorities={"human:test", "spiffe://uniimente.internal/kernel/settlement-router"},
    )
    now = now_utc()
    attestation = sign_attestation(VerifierAttestation(
        verifier_id=verifier_signer.signer_id,
        action_id=action_id,
        outcome_hash=sha256_json(outcome),
        receipt_hash=execution_receipt.hash,
        decision=AttestationDecision.ACCEPTED,
        evidence_refs=["camera:test:frame-42"],
        policy_version="test-1",
        observed_at=rfc3339(now),
        expires_at=rfc3339(now + timedelta(minutes=20)),
        reality_status=RealityStatus.SANDBOX,
    ), verifier_signer)
    credential = issuer.issue(action_id, attestation)

    adapter = SandboxSettlementAdapter()
    authority_signer = HMACSigner(
        "did:test:principal-authority", key=b"authority-test-key-32-bytes-long"
    )
    authorities = SettlementAuthorityRegistry(
        ratifiers={"human:test"}, maximum_ttl_seconds=3600
    )
    authorities.register(
        authority_id=authority_signer.signer_id,
        legal_principal="principal:test",
        signer=authority_signer,
        adapters={adapter.adapter_id},
        currencies={"USD"},
        reality_statuses={RealityStatus.SANDBOX},
        ratified_by="human:test",
    )
    reputation = ScopedReputationLedger(ledger)
    router = SettlementRouter(
        ledger, issuer, authorities, [adapter], reputation,
        dispute_resolvers={"human:test"},
    )

    def authorization(**overrides):
        current = now_utc()
        fields = dict(
            authority_id=authority_signer.signer_id,
            legal_principal="principal:test",
            credential_id=credential.credential_id,
            payer="sandbox:principal:test",
            payee=actor_id,
            max_amount="12.50",
            currency="USD",
            purpose="verified thermostat inspection",
            adapter_id=adapter.adapter_id,
            reality_status=RealityStatus.SANDBOX,
            issued_at=rfc3339(current),
            expires_at=rfc3339(current + timedelta(minutes=20)),
        )
        fields.update(overrides)
        return sign_settlement_authorization(
            SettlementAuthorization(**fields), authority_signer
        )

    return SimpleNamespace(
        ledger=ledger,
        action_id=action_id,
        actor_id=actor_id,
        outcome=outcome,
        execution_receipt=execution_receipt,
        verifier_signer=verifier_signer,
        verifiers=verifiers,
        issuer=issuer,
        attestation=attestation,
        credential=credential,
        adapter=adapter,
        authority_signer=authority_signer,
        authorities=authorities,
        reputation=reputation,
        router=router,
        authorization=authorization,
    )


def test_complete_sandbox_lifecycle_is_reconstructable(stack):
    auth = stack.authorization()
    intent = stack.router.create_intent(auth, requested_by=stack.actor_id, amount="12.50")
    receipt = stack.router.commit(intent.intent_id)
    assert receipt.reconciled
    assert intent.state == SettlementState.RECONCILED
    assert stack.adapter.calls == 1
    assert stack.router.metrics()["unauthorized_external_effects"] == 0
    ok, _ = stack.ledger.verify_chain()
    assert ok
    kinds = {record.record_type for record in stack.ledger.records}
    assert {
        "verifier_attestation", "outcome_credential", "settlement_authorization",
        "settlement_intent", "settlement_receipt", "reputation_evidence",
    } <= kinds


def test_credential_issuance_is_idempotent_per_action(stack):
    assert stack.issuer.issue(stack.action_id, stack.attestation) is stack.credential
    assert len(stack.ledger.by_type("outcome_credential")) == 1


def test_credential_requires_reconciled_action():
    ledger = EvidenceLedger("sha256:" + "0" * 64)
    registry = VerifierRegistry()
    issuer = CredentialIssuer(ledger, registry, HMACSigner("issuer", key=b"i" * 32))
    attestation = VerifierAttestation(
        verifier_id="verifier", action_id=str(uuid.uuid4()),
        outcome_hash="sha256:" + "1" * 64, receipt_hash="sha256:" + "2" * 64,
        decision=AttestationDecision.ACCEPTED, evidence_refs=["e"], policy_version="1",
        observed_at=rfc3339(), expires_at=rfc3339(now_utc() + timedelta(minutes=1)),
        reality_status=RealityStatus.SANDBOX,
    )
    with pytest.raises(TrustRailRefused, match="outcome record"):
        issuer.issue(attestation.action_id, attestation)


def test_actor_cannot_verify_own_outcome(stack):
    signer = HMACSigner(stack.actor_id, key=b"self-verifier-key-is-long-enough")
    stack.verifiers.register(
        verifier_id=stack.actor_id,
        owner_organ="self",
        signer=signer,
        action_classes={"device.inspect"},
        ratified_by="human:test",
    )
    att = VerifierAttestation(**{
        **stack.attestation.to_dict(),
        "attestation_id": str(uuid.uuid4()),
        "verifier_id": stack.actor_id,
        "decision": AttestationDecision.ACCEPTED,
        "reality_status": RealityStatus.SANDBOX,
        "signature": "",
    })
    sign_attestation(att, signer)
    with pytest.raises(TrustRailRefused, match="own outcome"):
        stack.issuer.issue(stack.action_id, att)


@pytest.mark.parametrize("field,value,match", [
    ("outcome_hash", "sha256:" + "9" * 64, "ledgered outcome"),
    ("receipt_hash", "sha256:" + "8" * 64, "execution receipt"),
    ("policy_version", "wrong", "policy version"),
])
def test_attestation_exactly_binds_action_lineage(stack, field, value, match):
    payload = stack.attestation.to_dict()
    payload.update({"attestation_id": str(uuid.uuid4()), field: value, "signature": ""})
    payload["decision"] = AttestationDecision(payload["decision"])
    payload["reality_status"] = RealityStatus(payload["reality_status"])
    att = sign_attestation(VerifierAttestation(**payload), stack.verifier_signer)
    with pytest.raises(TrustRailRefused, match=match):
        stack.issuer.issue(stack.action_id, att)


def test_tampered_verifier_signature_is_refused(stack):
    payload = stack.attestation.to_dict()
    payload.update({"attestation_id": str(uuid.uuid4()), "signature": "hmac-sha256:" + "0" * 64})
    payload["decision"] = AttestationDecision(payload["decision"])
    payload["reality_status"] = RealityStatus(payload["reality_status"])
    with pytest.raises(TrustRailRefused, match="signature invalid"):
        stack.issuer.issue(stack.action_id, VerifierAttestation(**payload))


def test_sandbox_action_cannot_be_relabelled_live(stack):
    payload = stack.attestation.to_dict()
    payload.update({
        "attestation_id": str(uuid.uuid4()),
        "reality_status": RealityStatus.LIVE,
        "decision": AttestationDecision.ACCEPTED,
        "signature": "",
    })
    att = sign_attestation(VerifierAttestation(**payload), stack.verifier_signer)
    with pytest.raises(TrustRailRefused, match="sandbox action"):
        stack.issuer.issue(stack.action_id, att)


def test_default_development_key_is_refused_in_production():
    with pytest.raises(TrustRailRefused, match="KMS signer"):
        HMACSigner("issuer", environment="production")


def test_amount_above_signed_ceiling_never_calls_adapter(stack):
    with pytest.raises(TrustRailRefused, match="exceeds"):
        stack.router.create_intent(
            stack.authorization(), requested_by=stack.actor_id, amount="12.51"
        )
    assert stack.adapter.calls == 0
    assert stack.router.metrics()["unauthorized_external_effects"] == 0


def test_noncanonical_amount_is_refused(stack):
    with pytest.raises(TrustRailRefused, match="canonical base-10"):
        stack.router.create_intent(
            stack.authorization(), requested_by=stack.actor_id, amount="1E+1"
        )
    assert stack.adapter.calls == 0


def test_tampered_authorization_never_calls_adapter(stack):
    auth = stack.authorization()
    auth.payee = "attacker"
    with pytest.raises(TrustRailRefused, match="signature invalid"):
        stack.router.create_intent(auth, requested_by=stack.actor_id, amount="1.00")
    assert stack.adapter.calls == 0


def test_uninstalled_or_live_adapter_scope_is_refused(stack):
    auth = stack.authorization(adapter_id="live-bank-v1", reality_status=RealityStatus.LIVE)
    with pytest.raises(TrustRailRefused):
        stack.router.create_intent(auth, requested_by=stack.actor_id, amount="1.00")
    assert stack.adapter.calls == 0


def test_settlement_replay_is_idempotent(stack):
    auth = stack.authorization()
    first_intent = stack.router.create_intent(auth, requested_by=stack.actor_id, amount="4.25")
    second_intent = stack.router.create_intent(auth, requested_by=stack.actor_id, amount="4.25")
    assert first_intent is second_intent
    first_receipt = stack.router.commit(first_intent.intent_id)
    second_receipt = stack.router.commit(first_intent.intent_id)
    assert first_receipt is second_receipt
    assert stack.adapter.calls == 1
    assert len(stack.ledger.by_type("settlement_receipt")) == 1


def test_credential_is_revalidated_at_commit(stack):
    intent = stack.router.create_intent(
        stack.authorization(), requested_by=stack.actor_id, amount="1.00"
    )
    stack.issuer.set_state(
        stack.credential.credential_id, CredentialState.SUSPENDED,
        authority_id="human:test", reason="test hold",
    )
    with pytest.raises(TrustRailRefused, match="suspended"):
        stack.router.commit(intent.intent_id)
    assert stack.adapter.calls == 0


def test_ledger_tamper_blocks_commit_before_adapter(stack):
    intent = stack.router.create_intent(
        stack.authorization(), requested_by=stack.actor_id, amount="1.00"
    )
    stack.ledger.by_type("outcome")[0].payload["external_observation"] = "tampered"
    with pytest.raises(TrustRailRefused, match="ledger integrity"):
        stack.router.commit(intent.intent_id)
    assert stack.adapter.calls == 0


def test_authorization_is_revalidated_at_commit(stack):
    auth = stack.authorization()
    intent = stack.router.create_intent(auth, requested_by=stack.actor_id, amount="1.00")
    auth.expires_at = rfc3339(now_utc() - timedelta(seconds=1))
    sign_settlement_authorization(auth, stack.authority_signer)
    with pytest.raises(TrustRailRefused, match="expired"):
        stack.router.commit(intent.intent_id)
    assert stack.adapter.calls == 0


def test_intent_mutation_breaks_idempotency_binding_before_effect(stack):
    intent = stack.router.create_intent(
        stack.authorization(), requested_by=stack.actor_id, amount="5.00"
    )
    intent.amount = "4.99"
    with pytest.raises(TrustRailRefused, match="idempotency binding"):
        stack.router.commit(intent.intent_id)
    assert stack.adapter.calls == 0


def test_bad_adapter_receipt_is_quarantined_and_suspends_proof(stack):
    class BadReceiptAdapter(SandboxSettlementAdapter):
        def submit(self, intent):
            receipt = super().submit(intent)
            receipt.payee = "attacker"
            return receipt

    bad = BadReceiptAdapter()
    router = SettlementRouter(
        stack.ledger, stack.issuer, stack.authorities, [bad], stack.reputation
    )
    intent = router.create_intent(
        stack.authorization(), requested_by=stack.actor_id, amount="2.00"
    )
    with pytest.raises(TrustRailRefused, match="failed reconciliation"):
        router.commit(intent.intent_id)
    assert router.metrics()["integrity_incidents"] == 1
    assert stack.issuer.state(stack.credential.credential_id) == CredentialState.SUSPENDED


def test_open_dispute_freezes_uncommitted_settlement(stack):
    intent = stack.router.create_intent(
        stack.authorization(), requested_by=stack.actor_id, amount="3.00"
    )
    dispute = stack.router.open_dispute(
        credential_id=stack.credential.credential_id,
        intent_id=intent.intent_id,
        opened_by="principal:test",
        reason="sensor evidence challenged",
    )
    assert dispute.state == "open"
    with pytest.raises(TrustRailRefused, match="disputed"):
        stack.router.commit(intent.intent_id)
    assert stack.adapter.calls == 0
    assert stack.router.metrics()["unauthorized_external_effects"] == 0


def test_invalidated_dispute_revokes_credential(stack):
    dispute = stack.router.open_dispute(
        credential_id=stack.credential.credential_id,
        intent_id=None,
        opened_by=stack.credential.verifier_id,
        reason="verification device compromised",
    )
    stack.router.resolve_dispute(
        dispute.dispute_id,
        resolved_by="human:test",
        resolution="invalidated",
        note="independent review confirmed compromise",
    )
    assert stack.issuer.state(stack.credential.credential_id) == CredentialState.REVOKED
    with pytest.raises(TrustRailRefused, match="revoked"):
        stack.issuer.verify(stack.credential.credential_id)


def test_reputation_requires_exact_scope_and_reconciliation(stack):
    intent = stack.router.create_intent(
        stack.authorization(), requested_by=stack.actor_id, amount="2.00"
    )
    stack.router.commit(intent.intent_id)
    snap = stack.reputation.snapshot(
        actor_id=stack.actor_id,
        action_class="device.inspect",
        legal_principal="principal:test",
        reality_status="SANDBOX",
    )
    assert snap.reconciled_count == 1
    assert snap.credential_ids == [stack.credential.credential_id]
    with pytest.raises(TrustRailRefused, match="exact risk scope"):
        stack.reputation.snapshot(
            actor_id=stack.actor_id,
            action_class="",
            legal_principal="principal:test",
            reality_status="SANDBOX",
        )


@dataclass
class FakeProposal:
    actor: str
    target: str


class FakeGate:
    def __init__(self):
        self.calls = 0

    def run(self, proposal, *, executor):
        self.calls += 1
        return executor(proposal)


def _boundary(stack):
    gate = FakeGate()
    rail = ProofToSettlementRail(stack.issuer, stack.router)
    boundary = OpenClawTrustBoundary(
        consequence_gate=gate,
        rail=rail,
        proposal_factory=lambda data: FakeProposal(data["actor"], data["target"]),
        executors={"inspect-v1": lambda proposal: {"target": proposal.target, "ok": True}},
        allowed_callers={stack.actor_id},
        allowed_target_prefixes=("sandbox:device/",),
        live_actions_enabled=False,
    )
    return boundary, gate


def test_openclaw_uses_only_named_executors(stack):
    boundary, gate = _boundary(stack)
    result = boundary.execute_action(
        caller_id=stack.actor_id,
        executor_id="inspect-v1",
        proposal_input={"actor": stack.actor_id, "target": "sandbox:device/thermostat-1"},
    )
    assert result["ok"] and gate.calls == 1
    with pytest.raises(TrustRailRefused, match="pre-registered"):
        boundary.execute_action(
            caller_id=stack.actor_id,
            executor_id="caller-supplied-lambda",
            proposal_input={"actor": stack.actor_id, "target": "sandbox:device/x"},
        )
    assert "executor" not in inspect.signature(boundary.execute_action).parameters


@pytest.mark.parametrize("caller,target,reality,match", [
    ("attacker", "sandbox:device/x", RealityStatus.SANDBOX, "allowlisted"),
    ("agent:openclaw:test", "live:device/x", RealityStatus.SANDBOX, "outside"),
    ("agent:openclaw:test", "sandbox:device/x", RealityStatus.LIVE, "disabled"),
])
def test_openclaw_boundary_refuses_untrusted_scope(stack, caller, target, reality, match):
    boundary, gate = _boundary(stack)
    with pytest.raises(TrustRailRefused, match=match):
        boundary.execute_action(
            caller_id=caller,
            executor_id="inspect-v1",
            proposal_input={"actor": caller, "target": target},
            reality_status=reality,
        )
    assert gate.calls == 0


def test_openclaw_cannot_commit_settlement(stack):
    boundary, _ = _boundary(stack)
    intent = boundary.request_settlement(
        stack.authorization(), caller_id=stack.actor_id, amount="1.00"
    )
    assert intent.state == SettlementState.AUTHORIZED
    assert not hasattr(boundary, "commit_settlement")
    assert stack.adapter.calls == 0


def test_mcp_server_binds_caller_identity_in_host_configuration():
    signature = inspect.signature(create_server)
    caller = signature.parameters["authenticated_caller_id"]
    assert caller.kind == inspect.Parameter.KEYWORD_ONLY
    assert caller.default is inspect.Parameter.empty


def test_wire_contracts_validate(stack):
    auth = stack.authorization()
    intent = stack.router.create_intent(auth, requested_by=stack.actor_id, amount="1.00")
    receipt = stack.router.commit(intent.intent_id)
    root = Path(__file__).resolve().parents[2] / "contracts"
    documents = {
        "verifier-attestation.schema.json": stack.attestation.to_dict(),
        "verified-outcome-credential.schema.json": stack.credential.as_verifiable_credential(
            stack.issuer.state(stack.credential.credential_id)
        ),
        "settlement-authorization.schema.json": auth.to_dict(),
        "settlement-intent.schema.json": intent.to_dict(),
        "settlement-receipt.schema.json": receipt.to_dict(),
    }
    for schema_name, document in documents.items():
        schema = json.loads((root / schema_name).read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        assert not list(validator.iter_errors(document)), schema_name
