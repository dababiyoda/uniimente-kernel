#!/usr/bin/env python3
"""Dependency-free IVIO v1 preflight.

The authoritative suite uses pytest + jsonschema. This preflight exists so the
core deterministic and fail-closed guarantees remain checkable in a bare Python
runtime and before dependency installation.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reality.ivio import CompileError, compile_instruction, verify_integrity

SCHEMA_PATH = ROOT / "contracts" / "ivio" / "v1" / "schema.json"
MANIFEST_PATH = ROOT / "contracts" / "ivio" / "v1" / "manifest.json"
VECTORS_PATH = ROOT / "contracts" / "ivio" / "v1" / "canonicalization-vectors.json"
SHA_A = "sha256:" + "a" * 64


def intent():
    return {
        "case_id": "case:REQ-88421",
        "requested_at": "2026-07-22T12:00:00Z",
        "purpose": "complete-nemt-ride",
        "legal_principal": "alfonso_lopez",
        "actor": {
            "workload_spiffe_id": "spiffe://uniimente.internal/cells/ride-outcome-verifier",
            "human_delegate": "founder:alfonso-lopez",
        },
        "action": "ride.complete",
        "resource": "ride:REQ-88421",
        "parameters": {"dropoff_facility": "facility:TGH-clinic-3"},
        "data_rights": {
            "allowed": ["dispatch.write", "receipt.write"],
            "forbidden": ["marketing.use", "model_training.use"],
        },
        "budget": {"currency": "USD", "amount_minor": 18_000},
        "ttl_seconds": 7_200,
        "evidence_requirements": ["pickup.attested", "arrival.attested"],
        "approvals_required": ["policy:auto", "human:ops-manager"],
        "expected_effect": "ride_service_completed",
        "receipt_type": "verified_ride_outcome",
        "reconciliation_contract": "match_receipt_to_request_and_gps.v1",
        "reversibility": "economic_only",
        "compensation_path": "manual_exception_case",
        "settlement_path": "healthcare_claims",
        "kill_conditions": ["identity_expired", "grant_revoked"],
        "policy_version": "policy.ride.v0.4.2",
        "constitution_digest": SHA_A,
        "reality_status": "sandbox",
    }


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def expect_refusal(mutator, phrase):
    candidate = intent()
    mutator(candidate)
    try:
        compile_instruction(candidate)
    except CompileError as exc:
        assert phrase in str(exc), (phrase, str(exc))
    else:
        raise AssertionError(f"unsafe intent was accepted; expected {phrase!r}")


def main():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    vectors = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].endswith("/ivio/v1/schema.json")
    assert manifest["version"] == "ivio.v1"
    assert len(manifest["objects"]) == 15
    assert len(schema["oneOf"]) == 15

    from reality.ivio import canonical_json_bytes
    assert vectors["profile"] == "UNIIMENTE-C14N-v1"
    for vector in vectors["vectors"]:
        wire = canonical_json_bytes(vector["value"])
        assert wire.decode("utf-8") == vector["canonical_utf8"]
        assert "sha256:" + hashlib.sha256(wire).hexdigest() == vector["sha256"]
    for vector in vectors["refusals"]:
        try:
            canonical_json_bytes(vector["value"])
        except CompileError:
            pass
        else:
            raise AssertionError(f"canonicalization refusal accepted: {vector['name']}")

    definitions = schema["$defs"]
    for object_type, ref in manifest["objects"].items():
        name = ref.removeprefix("#/$defs/")
        definition = definitions[name]
        assert definition["type"] == "object"
        assert definition["additionalProperties"] is False
        assert definition["properties"]["object_type"]["const"] == object_type
        assert {"object_type", "version", "integrity"} <= set(definition["required"])

    for node in walk(schema):
        if isinstance(node, dict) and "$ref" in node and node["$ref"].startswith("#/$defs/"):
            assert node["$ref"].removeprefix("#/$defs/") in definitions
        if isinstance(node, dict) and node.get("type") == "number":
            raise AssertionError("floating-point schema type is forbidden in IVIO v1")

    assert definitions["legalPrincipal"]["not"]["pattern"] == "^[Uu][Nn][Ii][Ii][Mm][Ee][Nn][Tt][Ee]$"
    assert definitions["legalPrincipal"]["pattern"] == "^[A-Za-z][A-Za-z0-9_.:-]{1,127}$"
    payable = definitions["SettlementIntent"]["properties"]["authorization"]
    assert payable["properties"]["payable_ready"]["const"] is True
    context = definitions["OutcomeCredential"]["properties"]["@context"]["prefixItems"]
    assert context[0]["const"] == "https://www.w3.org/ns/credentials/v2"
    proof = definitions["OutcomeCredential"]["properties"]["proof"]
    assert proof["additionalProperties"] is False
    assert {"cryptosuite", "verificationMethod", "proofValue"} <= set(proof["required"])

    first = compile_instruction(intent())
    second = compile_instruction(copy.deepcopy(intent()))
    assert first == second
    assert verify_integrity(first)
    assert first["expires_at"] == "2026-07-22T14:00:00Z"
    assert not ({"approved", "grant_id", "executed", "payable_ready", "settled"} & set(first))

    mutated_intent = intent()
    mutated_intent["parameters"]["dropoff_facility"] = "facility:TGH-clinic-4"
    mutated = compile_instruction(mutated_intent)
    assert first["parameter_digest"] != mutated["parameter_digest"]
    assert first["integrity"]["digest"] != mutated["integrity"]["digest"]

    tampered = copy.deepcopy(first)
    tampered["resource"] = "ride:attacker"
    assert not verify_integrity(tampered)

    expect_refusal(lambda x: x.update(legal_principal="UNIIMENTE"), "never the legal actor")
    expect_refusal(lambda x: x.update(legal_principal="not a principal"), "institutional identifier")
    expect_refusal(lambda x: x.update(ttl_seconds=0), "ttl_seconds")
    expect_refusal(lambda x: x.update(extra_authority="self"), "unknown fields")
    expect_refusal(lambda x: x["parameters"].update(confidence=0.99), "floating-point")
    expect_refusal(
        lambda x: x.update(reversibility="irreversible", reality_status="live"),
        "refuses live irreversible",
    )
    expect_refusal(
        lambda x: x.update(
            data_rights={"allowed": ["patient.read"], "forbidden": ["patient.read"]}
        ),
        "both allowed and forbidden",
    )
    expect_refusal(
        lambda x: x.update(
            data_rights={"allowed": ["patient.read", "patient.read"], "forbidden": []}
        ),
        "duplicate rights",
    )

    print("PASS IVIO v1 dependency-free preflight")
    print("  15 canonical objects mapped")
    print(f"  {len(vectors['vectors'])} Python canonicalization vectors verified")
    print(f"  {len(vectors['refusals'])} Python refusal vectors verified")
    print("  deterministic compiler and integrity binding verified")
    print("  mutation, authority, float, TTL, overlap, and irreversible refusals verified")


if __name__ == "__main__":
    main()
