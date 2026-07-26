"""IVIO v1 contract and compiler acceptance/adversarial tests."""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from reality.ivio import (
    CANONICALIZATION_PROFILE,
    CompileError,
    bind_integrity,
    canonical_json_bytes,
    compile_instruction,
    content_digest,
    verify_integrity,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts" / "ivio" / "v1" / "schema.json"
MANIFEST_PATH = ROOT / "contracts" / "ivio" / "v1" / "manifest.json"
VECTORS_PATH = ROOT / "contracts" / "ivio" / "v1" / "canonicalization-vectors.json"
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
NOW = "2026-07-22T12:00:00Z"
CASE_ID = "case:REQ-88421"
SPIFFE = "spiffe://uniimente.internal/cells/ride-outcome-verifier"


@pytest.fixture(scope="module")
def schema():
    value = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


@pytest.fixture(scope="module")
def validator(schema):
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _bound(**document):
    return bind_integrity(document)


def instruction_intent(**overrides):
    value = {
        "case_id": CASE_ID,
        "requested_at": NOW,
        "purpose": "complete-nemt-ride",
        "legal_principal": "alfonso_lopez",
        "actor": {
            "workload_spiffe_id": SPIFFE,
            "human_delegate": "founder:alfonso-lopez",
        },
        "action": "ride.complete",
        "resource": "ride:REQ-88421",
        "parameters": {
            "pickup_window_start": "2026-07-22T13:00:00Z",
            "pickup_window_end": "2026-07-22T13:20:00Z",
            "dropoff_facility": "facility:TGH-clinic-3",
        },
        "data_rights": {
            "allowed": ["eligibility.read", "dispatch.write", "receipt.write"],
            "forbidden": ["marketing.use", "model_training.use"],
        },
        "budget": {"currency": "USD", "amount_minor": 18_000},
        "ttl_seconds": 7_200,
        "evidence_requirements": [
            "pickup.attested",
            "arrival.attested",
            "vehicle_and_driver.bound",
            "policy_version.bound",
        ],
        "approvals_required": ["policy:auto", "human:ops-manager"],
        "expected_effect": "ride_service_completed",
        "receipt_type": "verified_ride_outcome",
        "reconciliation_contract": "match_receipt_to_request_and_gps.v1",
        "reversibility": "economic_only",
        "compensation_path": "manual_exception_case",
        "settlement_path": "healthcare_claims",
        "kill_conditions": [
            "identity_expired",
            "grant_revoked",
            "policy_version_changed",
        ],
        "policy_version": "policy.ride.v0.4.2",
        "constitution_digest": SHA_A,
        "reality_status": "sandbox",
    }
    value.update(overrides)
    return value


def contract_samples():
    compiled = compile_instruction(instruction_intent())
    values = [
        _bound(
            object_type="case",
            version="ivio.v1",
            case_id=CASE_ID,
            case_type="nemt.discharge_transport",
            opened_at=NOW,
            opened_by=SPIFFE,
            legal_principal="alfonso_lopez",
            subject_ref="subject:opaque-88421",
            policy_version="policy.ride.v0.4.2",
            required_proof_types=["pickup.attested", "arrival.attested"],
            verifier_ids=["verifier:tgh-billing"],
            sensitivity="restricted",
            reality_status="sandbox",
        ),
        _bound(
            object_type="outcome_event",
            version="ivio.v1",
            specversion="1.0",
            event_id="event:01JX0000000000000000000001",
            event_type="ride.completed",
            source=SPIFFE,
            actor_identity=SPIFFE,
            legal_principal="alfonso_lopez",
            occurred_at=NOW,
            case_id=CASE_ID,
            causal_parent=None,
            policy_version="policy.ride.v0.4.2",
            idempotency_key="ride-REQ-88421-complete-v1",
            evidence_refs=[SHA_A],
            sensitivity="restricted",
            reality_status="sandbox",
            data={"ride_ref": "ride:REQ-88421"},
        ),
        _bound(
            object_type="evidence_blob",
            version="ivio.v1",
            evidence_id="evidence:pickup-attestation-1",
            case_id=CASE_ID,
            captured_at=NOW,
            captured_by=SPIFFE,
            media_type="application/json",
            content_digest=SHA_A,
            storage_ref="vault:restricted/pickup-attestation-1",
            source_type="primary",
            source_uri=None,
            claim_status="observed",
            contains_phi=True,
            minimization_applied=True,
            sensitivity="restricted",
        ),
        compiled,
        _bound(
            object_type="capability_grant",
            version="ivio.v1",
            grant_id="grant:01JX0000000000000000000001",
            case_id=CASE_ID,
            instruction_digest=compiled["integrity"]["digest"],
            subject_spiffe_id=SPIFFE,
            legal_principal="alfonso_lopez",
            allowed_action="ride.complete",
            resource="ride:REQ-88421",
            parameter_digest=compiled["parameter_digest"],
            budget={"currency": "USD", "amount_minor": 18_000},
            issued_at=NOW,
            expires_at="2026-07-22T14:00:00Z",
            approval_refs=[SHA_B],
            policy_version="policy.ride.v0.4.2",
            issued_by="founder:alfonso-lopez",
            revocable=True,
            non_transferable=True,
            single_use=True,
            revoked=False,
            revoked_at=None,
            revocation_reason=None,
        ),
        _bound(
            object_type="exception_request",
            version="ivio.v1",
            exception_request_id="exception_request:missing-doc-1",
            case_id=CASE_ID,
            requested_at=NOW,
            requested_by=SPIFFE,
            missing_requirements=["facility.signature"],
            proposed_deviation="accept authorized nurse attestation",
            reason="facility signer unavailable inside discharge window",
            consequence_if_denied="case held for manual review",
            consequence_if_approved="proof checklist may continue",
            expires_at="2026-07-22T13:00:00Z",
            status="pending",
            evidence_refs=[SHA_A],
            reality_status="sandbox",
        ),
        _bound(
            object_type="exception_decision",
            version="ivio.v1",
            exception_decision_id="exception_decision:missing-doc-1",
            exception_request_id="exception_request:missing-doc-1",
            case_id=CASE_ID,
            decided_at=NOW,
            decided_by="human:ops-manager",
            legal_principal="alfonso_lopez",
            outcome="approved",
            rationale="named substitute is permitted by the bound policy",
            conditions=["nurse identity verified"],
            authorized_substitutions=["nurse.attestation"],
            expires_at="2026-07-22T13:00:00Z",
            policy_version="policy.ride.v0.4.2",
            signature="hmac-sha256:illustrative",
        ),
        _bound(
            object_type="action_attempt",
            version="ivio.v1",
            attempt_id="attempt:ride-complete-1",
            case_id=CASE_ID,
            instruction_digest=compiled["integrity"]["digest"],
            grant_id="grant:01JX0000000000000000000001",
            attempted_at=NOW,
            executor_spiffe_id=SPIFFE,
            idempotency_key="ride-REQ-88421-action-v1",
            action="ride.complete",
            resource="ride:REQ-88421",
            parameter_digest=compiled["parameter_digest"],
            commit_witness_digest=SHA_B,
            status="succeeded",
            reality_status="sandbox",
        ),
        _bound(
            object_type="receipt",
            version="ivio.v1",
            receipt_id="receipt:ride-complete-1",
            case_id=CASE_ID,
            attempt_id="attempt:ride-complete-1",
            received_at=NOW,
            receipt_type="verified_ride_outcome",
            issuer="adapter:chario",
            external_id="chario:completion-88421",
            status="accepted",
            content_digest=SHA_B,
            raw_storage_ref="vault:restricted/receipt-1",
            signature_verified=True,
            evidence_refs=[SHA_A],
        ),
        _bound(
            object_type="outcome_credential",
            version="ivio.v1",
            id="credential:ride-outcome-1",
            **{
                "@context": [
                    "https://www.w3.org/ns/credentials/v2",
                    "https://uniimente.internal/contexts/ivio/v1",
                ],
                "type": [
                    "VerifiableCredential",
                    "IVIOVerifiedOutcomeCredential",
                ],
            },
            issuer="did:web:uniimente.internal",
            validFrom=NOW,
            credentialSubject={
                "caseId": CASE_ID,
                "outcomeStatus": "payment_eligible",
                "proofChecklistDigest": SHA_A,
                "exceptionDecisionRefs": [SHA_B],
                "policyVersion": "policy.ride.v0.4.2",
                "evidenceDigests": [SHA_A, SHA_B],
                "verificationResult": "matched",
                "finalConsequence": "billing_submission_ready",
                "realityStatus": "sandbox",
            },
            credentialStatus={
                "id": "https://status.uniimente.internal/ivio/1#0",
                "type": "BitstringStatusListEntry",
                "statusPurpose": "revocation",
                "statusListCredential": "https://status.uniimente.internal/ivio/1",
            },
            credentialSchema={
                "id": "https://uniimente.internal/contracts/ivio/v1/schema.json#/$defs/OutcomeCredential",
                "type": "JsonSchema",
            },
            proof={
                "type": "DataIntegrityProof",
                "cryptosuite": "eddsa-rdfc-2022",
                "created": NOW,
                "verificationMethod": "did:web:uniimente.internal#key-1",
                "proofPurpose": "assertionMethod",
                "proofValue": "zIllustrativeProof",
            },
        ),
        _bound(
            object_type="settlement_intent",
            version="ivio.v1",
            settlement_intent_id="settlement_intent:ride-1",
            case_id=CASE_ID,
            outcome_credential_digest=SHA_C,
            created_at=NOW,
            created_by=SPIFFE,
            legal_principal="alfonso_lopez",
            rail="healthcare_claims",
            consequence_type="claim_submission",
            amount={"currency": "USD", "amount_minor": 18_000},
            counterparty_ref="payer:design-partner",
            idempotency_key="settlement-REQ-88421-v1",
            authorization={
                "payable_ready": True,
                "proof_checklist_digest": SHA_A,
                "verifier_receipt_id": "receipt:verifier-acceptance-1",
                "commit_witness_digest": SHA_B,
            },
            status="created",
            reality_status="sandbox",
        ),
        _bound(
            object_type="settlement_receipt",
            version="ivio.v1",
            settlement_receipt_id="settlement_receipt:ride-1",
            settlement_intent_id="settlement_intent:ride-1",
            case_id=CASE_ID,
            received_at=NOW,
            rail="healthcare_claims",
            external_event_id="payer-event:88421",
            status="accepted",
            amount={"currency": "USD", "amount_minor": 18_000},
            content_digest=SHA_C,
            raw_storage_ref="vault:restricted/settlement-receipt-1",
            signature_verified=True,
            idempotency_key="payer-event-88421-v1",
        ),
        _bound(
            object_type="reconciliation_record",
            version="ivio.v1",
            reconciliation_id="reconciliation:ride-1",
            case_id=CASE_ID,
            settlement_intent_id="settlement_intent:ride-1",
            settlement_receipt_refs=["settlement_receipt:ride-1"],
            reconciled_at=NOW,
            reconciled_by=SPIFFE,
            expected={
                "status": "accepted",
                "amount": {"currency": "USD", "amount_minor": 18_000},
                "effect_digest": SHA_A,
            },
            actual={
                "status": "accepted",
                "amount": {"currency": "USD", "amount_minor": 18_000},
                "effect_digest": SHA_A,
            },
            result="matched",
            discrepancy_codes=[],
            next_action=None,
            economic_finality=False,
            outcome_credential_status="active",
        ),
        _bound(
            object_type="invalidation",
            version="ivio.v1",
            invalidation_id="invalidation:evidence-1",
            case_id=CASE_ID,
            target_digest=SHA_A,
            issued_at=NOW,
            issued_by="human:auditor",
            reason_code="source_retracted",
            reason="the originating source withdrew the attestation",
            evidence_refs=[SHA_B],
            propagates_to=[SHA_C],
            action="freeze_settlement",
            resolution_status="open",
        ),
        _bound(
            object_type="metrics_sample",
            version="ivio.v1",
            metric_sample_id="metric:unauthorized-effects-1",
            case_id=CASE_ID,
            recorded_at=NOW,
            metric_name="unauthorized_external_effect_count",
            value=0,
            labels={"rail": "ivio", "reality_status": "sandbox"},
            reality_status="sandbox",
        ),
    ]
    return values


def test_schema_and_manifest_are_complete(schema):
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    expected = {
        "case", "outcome_event", "evidence_blob", "compiled_instruction",
        "capability_grant", "exception_request", "exception_decision",
        "action_attempt", "receipt", "outcome_credential", "settlement_intent",
        "settlement_receipt", "reconciliation_record", "invalidation",
        "metrics_sample",
    }
    assert manifest["version"] == "ivio.v1"
    assert set(manifest["objects"]) == expected
    assert len(schema["oneOf"]) == len(expected)


def test_all_contract_samples_roundtrip(validator):
    samples = contract_samples()
    assert len(samples) == 15
    for sample in samples:
        validator.validate(sample)
        assert verify_integrity(sample), sample["object_type"]
        wire = json.loads(canonical_json_bytes(sample))
        assert wire == sample


def test_compiler_is_deterministic_and_schema_valid(validator):
    first = compile_instruction(instruction_intent())
    second = compile_instruction(copy.deepcopy(instruction_intent()))
    assert first == second
    assert first["integrity"]["canonicalization"] == CANONICALIZATION_PROFILE
    assert verify_integrity(first)
    validator.validate(first)


def test_canonicalization_vectors_are_stable():
    suite = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
    assert suite["profile"] == CANONICALIZATION_PROFILE
    for vector in suite["vectors"]:
        wire = canonical_json_bytes(vector["value"])
        assert wire.decode("utf-8") == vector["canonical_utf8"]
        assert "sha256:" + hashlib.sha256(wire).hexdigest() == vector["sha256"]
    for vector in suite["refusals"]:
        with pytest.raises(CompileError):
            canonical_json_bytes(vector["value"])


def test_mutation_changes_all_relevant_bindings():
    first = compile_instruction(instruction_intent())
    changed_intent = instruction_intent()
    changed_intent["parameters"]["dropoff_facility"] = "facility:TGH-clinic-4"
    second = compile_instruction(changed_intent)
    assert first["source_intent_digest"] != second["source_intent_digest"]
    assert first["parameter_digest"] != second["parameter_digest"]
    assert first["integrity"]["digest"] != second["integrity"]["digest"]

    tampered = copy.deepcopy(first)
    tampered["parameters"]["dropoff_facility"] = "facility:attacker"
    assert not verify_integrity(tampered)


def test_compiler_does_not_authorize_or_execute():
    compiled = compile_instruction(instruction_intent())
    forbidden_runtime_state = {
        "approved", "authorized", "grant_id", "executed", "receipt",
        "payable_ready", "settled",
    }
    assert forbidden_runtime_state.isdisjoint(compiled)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda x: x.update(legal_principal="UNIIMENTE"), "never the legal actor"),
        (lambda x: x.update(legal_principal="not a principal"), "institutional identifier"),
        (lambda x: x.update(ttl_seconds=0), "ttl_seconds"),
        (lambda x: x.update(action="CompleteRide"), "namespaced lowercase"),
        (lambda x: x.update(reversibility="irreversible", reality_status="live"), "refuses live irreversible"),
        (lambda x: x.update(extra_authority="self"), "unknown fields"),
        (lambda x: x["parameters"].update(confidence=0.99), "floating-point"),
        (
            lambda x: x.update(
                data_rights={
                    "allowed": ["patient.read"],
                    "forbidden": ["patient.read"],
                }
            ),
            "both allowed and forbidden",
        ),
        (
            lambda x: x.update(
                data_rights={
                    "allowed": ["patient.read", "patient.read"],
                    "forbidden": [],
                }
            ),
            "duplicate rights",
        ),
    ],
)
def test_compiler_fails_closed(change, message):
    value = instruction_intent()
    change(value)
    with pytest.raises(CompileError, match=message):
        compile_instruction(value)


def test_instruction_expiry_is_derived_not_wall_clock():
    compiled = compile_instruction(instruction_intent(ttl_seconds=90))
    start = datetime.fromisoformat(compiled["not_before"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(compiled["expires_at"].replace("Z", "+00:00"))
    assert end - start == timedelta(seconds=90)


def test_schema_rejects_hidden_fields(validator):
    case = contract_samples()[0]
    case["hidden_bypass"] = True
    case = bind_integrity(case)
    with pytest.raises(ValidationError):
        validator.validate(case)


@pytest.mark.parametrize("principal", ["UNIIMENTE", "uniimente", "Uniimente"])
def test_schema_rejects_institution_as_legal_principal(validator, principal):
    case = contract_samples()[0]
    case["legal_principal"] = principal
    case = bind_integrity(case)
    with pytest.raises(ValidationError):
        validator.validate(case)


def test_credential_proof_is_strict_data_integrity_shape(validator):
    credential = next(
        value for value in contract_samples()
        if value["object_type"] == "outcome_credential"
    )
    credential["proof"]["ambient_authority"] = True
    credential = bind_integrity(credential)
    with pytest.raises(ValidationError):
        validator.validate(credential)


def test_settlement_requires_explicit_payable_ready(validator):
    settlement = next(
        value for value in contract_samples()
        if value["object_type"] == "settlement_intent"
    )
    settlement["authorization"]["payable_ready"] = False
    settlement = bind_integrity(settlement)
    with pytest.raises(ValidationError):
        validator.validate(settlement)


def test_idempotency_key_rejects_personal_data_shape(validator):
    event = next(
        value for value in contract_samples()
        if value["object_type"] == "outcome_event"
    )
    event["idempotency_key"] = "patient@example.com"
    event = bind_integrity(event)
    with pytest.raises(ValidationError):
        validator.validate(event)


def test_negative_evidence_and_invalidation_remain_first_class(validator):
    evidence = next(
        value for value in contract_samples()
        if value["object_type"] == "evidence_blob"
    )
    evidence["claim_status"] = "invalidated"
    evidence = bind_integrity(evidence)
    validator.validate(evidence)

    invalidation = next(
        value for value in contract_samples()
        if value["object_type"] == "invalidation"
    )
    validator.validate(invalidation)
    assert invalidation["propagates_to"]
