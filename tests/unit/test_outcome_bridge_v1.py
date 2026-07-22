"""Tests preventing commercial activity from being laundered into validation."""
import pytest

from business.commercial_loop import CustomerCase
from foundry.advantage import AdvantageRefused
from foundry.outcome_bridge import ReconciliationPacket, external_outcome_from_case

PAYMENT = "sha256:" + "a" * 64
DELIVERY = "sha256:" + "b" * 64
ACCEPTANCE = "sha256:" + "c" * 64
OUTCOME = "sha256:" + "d" * 64
RECONCILIATION = "sha256:" + "e" * 64


def case(**overrides):
    values = dict(
        case_id="case-1", business_id="business-1", buyer="facility CFO",
        stage="retention_or_termination", payment_receipt_hash=PAYMENT,
        delivery_receipt_hash=DELIVERY, outcome_verified_by="external_receipt",
        outcome_detail="facility accepted evidence and transport outcome",
        resolution="retained",
    )
    values.update(overrides)
    return CustomerCase(**values)


def reconciliation(**overrides):
    values = dict(
        economic_commitment_usd=500.0,
        fully_loaded_cost_usd=200.0,
        founder_hours=4.0,
        acceptance_receipt_ref=ACCEPTANCE,
        outcome_receipt_ref=OUTCOME,
        reconciliation_ref=RECONCILIATION,
        authority_incidents=0,
        critical_participant_harm_incidents=0,
        metric_results={"clean_verified_outcome_count": 1.0},
    )
    values.update(overrides)
    return ReconciliationPacket(**values)


def test_closed_case_and_reconciliation_produce_external_outcome():
    result = external_outcome_from_case(case(), reconciliation())
    assert result.economic_commitment_usd == 500.0
    assert result.contribution_margin_usd == 300.0
    assert result.accepted_delivery and result.externally_verified
    assert set(result.receipt_refs) == {
        PAYMENT, DELIVERY, ACCEPTANCE, OUTCOME, RECONCILIATION,
    }


def test_activity_before_resolution_is_not_validation():
    with pytest.raises(AdvantageRefused, match="retention or termination"):
        external_outcome_from_case(case(stage="customer_outcome"), reconciliation())


@pytest.mark.parametrize("field", ["payment_receipt_hash", "delivery_receipt_hash"])
def test_missing_execution_receipt_blocks_bridge(field):
    with pytest.raises(AdvantageRefused, match="recorded|delivery receipt"):
        external_outcome_from_case(case(**{field: None}), reconciliation())


def test_internal_self_report_does_not_verify_outcome():
    with pytest.raises(AdvantageRefused, match="accepted external verifier"):
        external_outcome_from_case(case(outcome_verified_by="self_report"), reconciliation())


def test_unreconciled_or_fake_reference_fails_closed():
    with pytest.raises(AdvantageRefused, match="canonical sha256"):
        external_outcome_from_case(
            case(), reconciliation(reconciliation_ref="spreadsheet-row-7")
        )


def test_incidents_are_carried_into_foundry_closure_not_hidden():
    result = external_outcome_from_case(
        case(), reconciliation(authority_incidents=1, critical_participant_harm_incidents=2)
    )
    assert result.authority_incidents == 1
    assert result.critical_participant_harm_incidents == 2
