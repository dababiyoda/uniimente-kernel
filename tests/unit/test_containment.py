from __future__ import annotations

import ast
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from containment import (
    REQUIRED_CONTROLS,
    ContainmentAttestation,
    ContainmentBroker,
    ContainmentRefused,
    ContainmentRequirement,
    ContainmentTier,
    EnforcementKind,
    ProviderDeclaration,
    local_runtime_inventory,
)
from moduleloader.integrity import sha256_bytes
from moduleloader import FrozenContractSchemas


NOW = datetime(2026, 8, 12, 0, 0, tzinfo=timezone.utc)


def broker(verifier=None):
    return ContainmentBroker(
        trusted_verifiers=("verifier:independent",),
        verify_attestation=verifier or (lambda item: (True, "signature:test")),
    )


def declaration(tier=ContainmentTier.MICROVM):
    return ProviderDeclaration(
        provider_id=f"provider:{tier.value}",
        tier=tier,
        runtime_name=f"runtime:{tier.value}",
        enforcement_kind={
            ContainmentTier.IN_PROCESS: EnforcementKind.POLICY_ONLY,
            ContainmentTier.HARDENED_CONTAINER: EnforcementKind.OS_KERNEL_BOUNDARY,
            ContainmentTier.MICROVM: EnforcementKind.HYPERVISOR_BOUNDARY,
            ContainmentTier.WASM_COMPONENT: EnforcementKind.WASM_SANDBOX,
        }[tier],
    )


def attestation(item: ProviderDeclaration, **updates):
    values = {
        "provider_id": item.provider_id,
        "verifier_id": "verifier:independent",
        "tier": item.tier,
        "runtime_name": item.runtime_name,
        "enforcement_kind": item.enforcement_kind,
        "runtime_digest": sha256_bytes(b"pinned runtime image"),
        "controls": REQUIRED_CONTROLS[item.tier],
        "evidence_refs": ("test:runtime-controls",),
        "issued_at": NOW - timedelta(minutes=1),
        "expires_at": NOW + timedelta(hours=1),
        "nonce": "0123456789abcdef",
        "verification_ref": "signature:test",
    }
    values.update(updates)
    return ContainmentAttestation(**values)


def generated_requirement(tier=ContainmentTier.MICROVM):
    return ContainmentRequirement(
        module_id="candidate-r3",
        consequence_class="internal_write",
        trust="generated",
        required_tier=tier,
        resource_limits={"cpu_ms": 1000, "memory_mb": 128, "network": "denied"},
    )


def test_unavailable_is_an_honest_schema_valid_decision_not_a_downgrade():
    decision = broker().select(generated_requirement(), now=NOW)
    assert decision.status == "UNAVAILABLE"
    assert decision.as_document() == {
        "requirement_version": "1.0.0",
        "module_id": "candidate-r3",
        "consequence_class": "internal_write",
        "trust": "generated",
        "required_tier": "microvm",
        "granted_tier": "UNAVAILABLE",
        "enforcement_kind": "policy_only",
        "attested": False,
        "attestation_evidence": None,
        "resource_limits": {"cpu_ms": 1000, "memory_mb": 128, "network": "denied"},
    }
    assert decision.provider_id is None


def test_provider_declaration_alone_never_proves_availability():
    instance = broker()
    item = declaration()
    instance.register(item)
    assert instance.select(generated_requirement(), now=NOW).granted_tier == "UNAVAILABLE"


def test_fresh_independent_attestation_selects_policy_match_not_execution():
    instance = broker()
    item = declaration()
    instance.register(item)
    evidence_digest = instance.accept_attestation(attestation(item), now=NOW)
    decision = instance.select(generated_requirement(), now=NOW)
    assert decision.status == "VERIFIED_POLICY_MATCH_NOT_EXECUTION"
    assert decision.granted_tier == "microvm"
    assert decision.enforcement_kind == EnforcementKind.HYPERVISOR_BOUNDARY
    assert decision.attested is True
    assert decision.attestation_evidence == evidence_digest
    assert decision.as_document()["attestation_evidence"] == evidence_digest
    assert decision.as_document()["granted_tier"] != "UNAVAILABLE"


def test_provider_cannot_attest_itself_and_missing_controls_are_refused():
    instance = broker()
    item = declaration()
    instance.register(item)
    with pytest.raises(ContainmentRefused) as error:
        instance.accept_attestation(
            attestation(item, verifier_id=item.provider_id), now=NOW
        )
    assert error.value.code == "SELF_ATTESTATION"
    with pytest.raises(ContainmentRefused) as error:
        instance.accept_attestation(
            attestation(item, controls=frozenset(), nonce="fedcba9876543210"), now=NOW
        )
    assert error.value.code == "MISSING_CONTROLS"


def test_attestation_nonce_replay_is_refused_and_history_is_preserved():
    instance = broker()
    item = declaration()
    instance.register(item)
    first = attestation(item)
    instance.accept_attestation(first, now=NOW)
    with pytest.raises(ContainmentRefused) as error:
        instance.accept_attestation(first, now=NOW)
    assert error.value.code == "ATTESTATION_REPLAY"
    second = attestation(
        item,
        nonce="fedcba9876543210",
        issued_at=NOW,
        expires_at=NOW + timedelta(hours=2),
    )
    instance.accept_attestation(second, now=NOW)
    assert instance.attestation_history(item.provider_id) == (first, second)


def test_attestation_is_reverified_at_selection_and_failure_reports_unavailable():
    verifier_state = {"ok": True}
    instance = broker(lambda item: (verifier_state["ok"], "live verifier"))
    item = declaration()
    instance.register(item)
    instance.accept_attestation(attestation(item), now=NOW)
    verifier_state["ok"] = False
    decision = instance.select(generated_requirement(), now=NOW)
    assert decision.granted_tier == "UNAVAILABLE"
    assert decision.attested is False


@pytest.mark.parametrize(
    ("trust", "tier"),
    [
        ("generated", ContainmentTier.HARDENED_CONTAINER),
        ("foreign", ContainmentTier.IN_PROCESS),
        ("internal_untrusted", ContainmentTier.IN_PROCESS),
    ],
)
def test_risk_cannot_silently_downgrade_to_insufficient_tier(trust, tier):
    requirement = ContainmentRequirement(
        module_id="candidate",
        consequence_class="read_only",
        trust=trust,
        required_tier=tier,
    )
    with pytest.raises(ContainmentRefused) as error:
        broker().select(requirement, now=NOW)
    assert error.value.code == "INSUFFICIENT_TIER"


def test_in_process_can_only_claim_policy_enforcement():
    item = ProviderDeclaration(
        provider_id="provider:bad",
        tier=ContainmentTier.IN_PROCESS,
        runtime_name="python",
        enforcement_kind=EnforcementKind.OS_KERNEL_BOUNDARY,
    )
    with pytest.raises(ContainmentRefused) as error:
        broker().register(item)
    assert error.value.code == "ENFORCEMENT_MISMATCH"


def test_local_inventory_never_claims_verified_isolation():
    rows = local_runtime_inventory()
    assert {row["tier"] for row in rows} == {
        "in_process", "hardened_container", "microvm", "wasm_component"
    }
    assert all(row["status"] in {"POLICY_ONLY", "UNAVAILABLE", "UNVERIFIED_EXECUTABLE_PRESENCE"} for row in rows)
    assert all("claim_limit" in row for row in rows)


def test_containment_source_has_no_launch_or_network_primitive():
    source = Path(__file__).parents[2] / "containment" / "policy.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    forbidden_imports = {"subprocess", "socket", "requests", "httpx", "importlib"}
    observed = set()
    forbidden_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            observed.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            observed.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else (
                node.func.attr if isinstance(node.func, ast.Attribute) else ""
            )
            if name in {"Popen", "run", "system", "exec", "eval", "__import__"}:
                forbidden_calls.append(name)
    assert observed.isdisjoint(forbidden_imports)
    assert forbidden_calls == []


def test_containment_evidence_is_frozen_schema_valid():
    path = Path(__file__).parents[2] / "containment" / "EVIDENCE.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    assert FrozenContractSchemas().validate_evidence_record(document) == document
