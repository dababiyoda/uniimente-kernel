"""Tests for the canonical Phase Zero -> Advantage Foundry boundary."""
from copy import deepcopy

import pytest

from foundry.advantage import AdvantageRefused
from foundry.intake import FoundryIntakeSupplement, opportunity_from_canonical

HASH = "sha256:" + "d" * 64
APPROVAL = "sha256:" + "e" * 64
PACKET_ID = "123e4567-e89b-12d3-a456-426614174000"
ASSESSMENT_ID = "123e4567-e89b-12d3-a456-426614174001"


def packet():
    return {
        "packet_id": PACKET_ID,
        "schema_version": "1.1",
        "created_by": "spiffe://uniimente.internal/daleobanks",
        "created_at": "2026-07-22T10:00:00Z",
        "observed_failure": "a parser rejects a synthetic input record",
        "affected_actors": ["test_operator", "test_workspace", "test_runner"],
        "pain_owner": "test_maintainer",
        "budget_owner": "test_buyer",
        "payer": "test_buyer",
        "mandate_capable_actor": "test_reviewer",
        "existing_workaround": "manually convert a synthetic record",
        "missing_proof": "parser output matches its schema",
        "governing_bottleneck": "parser compatibility",
        "smallest_intervention": "run one synthetic parser test",
        "cheapest_decisive_test": "run one parser test",
        "possible_business_form": "parser test utility",
        "capital_requirement_usd": 5000.0,
        "key_risks": ["privacy", "workflow adoption"],
        "wedge_to_control_path": "test input to parsed output",
        "evidence_refs": [HASH],
    }


def assessment():
    return {
        "assessment_id": ASSESSMENT_ID,
        "packet_id": PACKET_ID,
        "schema_version": "1.1",
        "assessed_by": "spiffe://uniimente.internal/wealthmachine",
        "assessed_at": "2026-07-22T10:05:00Z",
        "verdict": "go",
        "opportunity_score": 0.88,
        "adversarial_cases": {
            "bull": "an accepted input format reduces conversion work",
            "bear": "the input format may be unsupported",
            "fraud_manipulation": "expected output could be copied without parsing",
            "incumbent_response": "an existing parser may support the format",
            "adoption_friction": "the test should run with one command",
            "do_nothing": "manual conversion remains necessary",
            "opportunity_cost": "another parser may already work",
        },
        "structured_reasons": ["buyer and bottleneck are identifiable"],
        "evidence_state": {"confidence": 0.82, "evidence_refs": [HASH]},
        "requires_human_approval": True,
        "execution_authority": False,
    }


def supplement(**overrides):
    values = dict(
        buyer="test_buyer",
        beneficiary="test_operator",
        recurring_transaction="parse a synthetic input record",
        accepted_artifact="parsed-record.json",
        external_consequence="test operator accepts the parsed record",
        lawful_path="test operator grants permission to parse synthetic input",
        legal_operator="alfonso_lopez",
        trapped_value_usd=250000.0,
        human_approval_record_hash=APPROVAL,
        constraints=("pilot only",),
        prohibitions=("no production inputs",),
    )
    values.update(overrides)
    return FoundryIntakeSupplement(**values)


def test_valid_phase_zero_contracts_create_governing_transaction():
    result = opportunity_from_canonical(packet(), assessment(), supplement())
    assert result.buyer == "test_buyer"
    assert result.mandate_actor == "test_reviewer"
    assert APPROVAL in result.evidence_refs
    assert any("human_approval_record_hash" in item for item in result.constraints)
    assert "privacy" in result.prohibitions


def test_assessment_and_packet_identity_must_match():
    bad = assessment()
    bad["packet_id"] = "123e4567-e89b-12d3-a456-426614174099"
    with pytest.raises(AdvantageRefused, match="does not belong"):
        opportunity_from_canonical(packet(), bad, supplement())


@pytest.mark.parametrize("verdict", ["defer", "kill", "needs_more_evidence"])
def test_only_go_enters_foundry(verdict):
    bad = assessment()
    bad["verdict"] = verdict
    with pytest.raises(AdvantageRefused, match="only a GO"):
        opportunity_from_canonical(packet(), bad, supplement())


def test_unresolved_capping_case_blocks_foundry():
    bad = assessment()
    bad["adversarial_cases"]["capping_cases"] = ["fraud_manipulation"]
    with pytest.raises(AdvantageRefused, match="capping cases"):
        opportunity_from_canonical(packet(), bad, supplement())


def test_schema_rejects_any_execution_authority():
    bad = assessment()
    bad["execution_authority"] = True
    with pytest.raises(AdvantageRefused, match="canonical contract"):
        opportunity_from_canonical(packet(), bad, supplement())


def test_missing_commercial_fact_is_not_inferred():
    with pytest.raises(AdvantageRefused, match="supplement is incomplete"):
        opportunity_from_canonical(packet(), assessment(), supplement(accepted_artifact=""))


def test_uniimente_cannot_be_legal_operator():
    with pytest.raises(AdvantageRefused, match="never the legal operator"):
        opportunity_from_canonical(packet(), assessment(), supplement(legal_operator="UNIIMENTE"))


def test_invalid_human_approval_reference_fails_closed():
    with pytest.raises(AdvantageRefused, match="canonical sha256"):
        opportunity_from_canonical(
            packet(), assessment(), supplement(human_approval_record_hash="approved-by-chat")
        )
