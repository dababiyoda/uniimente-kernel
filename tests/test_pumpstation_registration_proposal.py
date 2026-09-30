import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_pumpstation_registration_proposal_matches_contract():
    schema = load_json("contracts/venture-cell-registration-proposal.schema.json")
    proposal = load_json("identity/proposals/pumpstation-venture-cell-registration.json")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(proposal), key=lambda error: list(error.path))
    assert errors == [], [error.message for error in errors]


def test_proposal_is_inactive_zero_budget_and_level_zero():
    proposal = load_json("identity/proposals/pumpstation-venture-cell-registration.json")
    assert proposal["status"] == "PROPOSED"
    assert proposal["activation_status"] == "INACTIVE"
    assert proposal["approval_status"] == "NOT_REQUESTED"
    assert proposal["capital_authorization_usd"] == 0
    assert proposal["max_autonomy_level"] == 0
    assert proposal["external_targets"] == []
    assert proposal["legal_principal"] == "alfonso_lopez"
    assert proposal["legal_principal"] != "UNIIMENTE"


def test_proposal_does_not_activate_canonical_service_identity():
    registry = yaml.safe_load(
        (ROOT / "identity/service-identities.yaml").read_text(encoding="utf-8")
    )
    identities = {service["id"] for service in registry["services"]}
    assert "spiffe://uniimente.internal/venture/pumpstation" not in identities


def test_proposal_contains_no_external_or_financial_capability():
    proposal = load_json("identity/proposals/pumpstation-venture-cell-registration.json")
    allowed = set(proposal["allowed_capabilities"])
    prohibited = set(proposal["prohibited_capabilities"])
    assert all(
        not capability.startswith(("trade.", "asset.", "wallet.", "external_effect."))
        for capability in allowed
    )
    for required in {
        "trade.place",
        "asset.transfer",
        "wallet.custody",
        "outside_capital.accept",
        "external_effect.execute",
    }:
        assert required in prohibited


def test_activation_requires_explicit_approvals_and_source_hash_binding():
    proposal = load_json("identity/proposals/pumpstation-venture-cell-registration.json")
    assert proposal["source_manifest_hash_status"] == "TO_BE_BOUND_AT_APPROVAL"
    assert {
        "founder_manifest_approval",
        "service_identity_registration",
        "legal_principal_confirmation",
        "kernel_contract_lock_approval",
        "security_review",
        "capability_grant_issuance",
    }.issubset(set(proposal["required_approvals"]))
