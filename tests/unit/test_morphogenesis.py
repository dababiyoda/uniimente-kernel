from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from morphogenesis.contracts import (
    AssessmentState,
    AuthorityEnvelope,
    CandidateAction,
    DescendantProposal,
    Direction,
    MetricTarget,
    MorphogeneticSetPoint,
    StateObservation,
)
from morphogenesis.engine import MorphogeneticEngine, MorphogeneticError


NOW = datetime(2026, 7, 20, 16, 0, tzinfo=timezone.utc)


def _setpoint():
    """Neutral proving-cell setpoint (IVIO-NEMT retired by founder directive 2026-09-13).

    Replaces the deleted ventures.ivio_nemt.first_cell.build_ivio_first_setpoint
    fixture with an equivalent generic setpoint so the engine mechanics remain
    tested without treating a retired venture as active.
    """
    metrics = (
        MetricTarget(name="payment_usd", direction=Direction.GTE, target=1000.0, unit="usd"),
        MetricTarget(name="paid_pilot_commitments", direction=Direction.GTE, target=1.0),
        MetricTarget(name="delivery_accepted", direction=Direction.EQ, target=True),
        MetricTarget(name="external_outcome_verified", direction=Direction.EQ, target=True),
        MetricTarget(name="contribution_margin_usd", direction=Direction.GTE, target=250.0, unit="usd"),
        MetricTarget(name="clean_completion_rate", direction=Direction.GTE, target=0.95),
        MetricTarget(name="unresolved_obligations", direction=Direction.LTE, target=0.0),
        MetricTarget(name="critical_authority_incidents", direction=Direction.LTE, target=0.0),
        MetricTarget(name="participant_harm_incidents", direction=Direction.LTE, target=0.0),
        MetricTarget(name="founder_hours", direction=Direction.LTE, target=20.0, unit="hours"),
        MetricTarget(name="spend_usd", direction=Direction.LTE, target=750.0, unit="usd"),
    )
    return MorphogeneticSetPoint(
        setpoint_id="generic-proving-cell-setpoint-v1",
        venture_cell="GENERIC-CELL-001",
        legal_principal="alfonso_lopez",
        buyer="generic_buyer_001",
        beneficiary="generic_beneficiary",
        accepted_artifact="verified recurring service evidence packet",
        external_consequence="buyer accepts and pays for the bounded service",
        metrics=metrics,
        budget_ceiling_usd=1000.0,
        founder_attention_ceiling_hours=40.0,
        deadline=NOW + timedelta(days=60),
        prohibited_actions=("unapproved_external_contact",),
        kill_conditions=("critical_authority_incidents > 0",),
        requires_human_activation=True,
    )


def _closed_observations():
    values = {
        "paid_pilot_commitments": 1.0,
        "payment_usd": 1000.0,
        "delivery_accepted": True,
        "external_outcome_verified": True,
        "contribution_margin_usd": 250.0,
        "clean_completion_rate": 0.95,
        "unresolved_obligations": 0.0,
        "critical_authority_incidents": 0.0,
        "participant_harm_incidents": 0.0,
        "founder_hours": 20.0,
        "spend_usd": 750.0,
    }
    return {
        name: StateObservation(
            name=name,
            value=value,
            observed_at=NOW,
            source_ref=f"sha256:{name}",
            confidence=0.95,
        )
        for name, value in values.items()
    }


def _proposal(**kw):
    base = dict(
        proposal_id="desc-001",
        parent_venture_cell="GENERIC-CELL-001",
        target_venture_cell="GENERIC-CELL-002",
        legal_principal="alfonso_lopez",
        buyer="generic_buyer_002",
        market_failure="recurring missed or weakly evidenced service delivery",
        accepted_artifact="verified recurring service evidence packet",
        external_consequence="buyer accepts and pays for the bounded service",
        required_genomes=("request-accept-evidence@1.0.0",),
        requested_budget_usd=500.0,
        parent_validation_ref="sha256:parent",
        retention_evidence_ref="sha256:retention",
        reserve_evidence_ref="sha256:reserve",
    )
    base.update(kw)
    return DescendantProposal(**base)


def test_setpoint_is_complete_and_human_bound():
    target = _setpoint()
    assert target.validate() == []
    assert target.requires_human_activation


def test_uniimente_cannot_be_legal_principal():
    target = replace(_setpoint(), legal_principal="UNIIMENTE")
    with pytest.raises(MorphogeneticError, match="never a legal principal"):
        MorphogeneticEngine().evaluate(target, {}, now=NOW)


def test_missing_commercial_closure_metric_fails_closed():
    target = _setpoint()
    metrics = tuple(m for m in target.metrics if m.name != "payment_usd")
    with pytest.raises(MorphogeneticError, match="payment_usd"):
        MorphogeneticEngine().evaluate(replace(target, metrics=metrics), {}, now=NOW)


def test_missing_or_low_confidence_evidence_blocks_convergence():
    observations = _closed_observations()
    observations.pop("payment_usd")
    observations["delivery_accepted"] = replace(
        observations["delivery_accepted"], confidence=0.20
    )
    result = MorphogeneticEngine().evaluate(_setpoint(), observations, now=NOW)
    assert result.state is AssessmentState.INSUFFICIENT_EVIDENCE
    assert not result.target_reached
    assert any("missing observation: payment_usd" in item for item in result.blockers)
    assert any("low-confidence observation: delivery_accepted" in item for item in result.blockers)


def test_target_reached_never_equals_authorized():
    result = MorphogeneticEngine().evaluate(_setpoint(), _closed_observations(), now=NOW)
    assert result.state is AssessmentState.TARGET_REACHED_NOT_AUTHORIZED
    assert result.target_reached
    assert result.can_request_gate


def test_action_ranking_filters_unauthorized_and_over_budget_actions():
    observations = _closed_observations()
    observations["paid_pilot_commitments"] = replace(
        observations["paid_pilot_commitments"], value=0.0
    )
    actions = (
        CandidateAction(
            action_id="prepare_facility_packet",
            description="prepare a reviewable buyer packet",
            consequence_class="internal_write",
            estimated_cost_usd=10.0,
            projected_values={"paid_pilot_commitments": 1.0},
        ),
        CandidateAction(
            action_id="send_unapproved_outreach",
            description="contact the buyer without human approval",
            consequence_class="external_contact",
            estimated_cost_usd=0.0,
            projected_values={"paid_pilot_commitments": 1.0},
            requires_human=False,
        ),
        CandidateAction(
            action_id="buy_distribution",
            description="overspend to buy traffic",
            consequence_class="financial",
            estimated_cost_usd=5000.0,
            projected_values={"paid_pilot_commitments": 1.0},
            requires_human=True,
        ),
    )
    envelope = AuthorityEnvelope(
        max_consequence_class="external_contact",
        budget_remaining_usd=100.0,
        permitted_actions=(
            "prepare_facility_packet",
            "send_unapproved_outreach",
            "buy_distribution",
        ),
    )
    ranked = MorphogeneticEngine().rank_actions(_setpoint(), observations, actions, envelope)
    assert [item.action_id for item in ranked] == ["prepare_facility_packet"]
    assert not ranked[0].requires_gate


def test_descendant_cannot_arrive_pre_activated_or_with_receipt():
    closed = MorphogeneticEngine().evaluate(_setpoint(), _closed_observations(), now=NOW)
    decision = MorphogeneticEngine().assess_descendant(
        closed,
        _proposal(activation_state="ACTIVE", consequence_gate_receipt="forged"),
    )
    assert decision.status == "BLOCKED"
    assert any("cannot represent an activated cell" in reason for reason in decision.reasons)
    assert any("may not contain a Gate receipt" in reason for reason in decision.reasons)


def test_closed_parent_only_permits_ratification_request():
    closed = MorphogeneticEngine().evaluate(_setpoint(), _closed_observations(), now=NOW)
    decision = MorphogeneticEngine().assess_descendant(closed, _proposal())
    assert decision.status == "MAY_REQUEST_RATIFICATION"
    assert decision.proposal is not None
    assert decision.proposal.activation_state == "PROPOSED_NOT_EXECUTED"


def test_open_parent_cannot_propose_replication():
    observations = _closed_observations()
    observations["payment_usd"] = replace(observations["payment_usd"], value=0.0)
    open_state = MorphogeneticEngine().evaluate(_setpoint(), observations, now=NOW)
    decision = MorphogeneticEngine().assess_descendant(open_state, _proposal())
    assert decision.status == "BLOCKED"
    assert "not reached validated target state" in decision.reasons[0]
