"""First vertical target: IVIO-NEMT paid facility validation.

This declares a target. It does not claim a facility has accepted, paid, or
verified an outcome. Those facts must enter as provenance-backed observations.
"""
from __future__ import annotations

from datetime import datetime

from .contracts import Direction, MetricTarget, MorphogeneticSetPoint


def build_ivio_first_setpoint(*, deadline: datetime) -> MorphogeneticSetPoint:
    return MorphogeneticSetPoint(
        setpoint_id="ivio-nemt-first-validated-genome-v1",
        venture_cell="IVIO-NEMT",
        legal_principal="alfonso_lopez",
        buyer="founding_facility_001",
        beneficiary="facility discharge staff and NEMT patients",
        accepted_artifact="RAE evidence packet and reconciled pilot report",
        external_consequence=(
            "a facility pays for and accepts a bounded IVIO-NEMT pilot whose "
            "transport outcome is externally verified"
        ),
        metrics=(
            MetricTarget("paid_pilot_commitments", Direction.GTE, 1.0),
            MetricTarget("payment_usd", Direction.GTE, 1.0, unit="USD"),
            MetricTarget("delivery_accepted", Direction.EQ, True),
            MetricTarget("external_outcome_verified", Direction.EQ, True),
            MetricTarget("contribution_margin_usd", Direction.GTE, 0.0, unit="USD"),
            MetricTarget("clean_completion_rate", Direction.GTE, 0.93),
            MetricTarget("unresolved_obligations", Direction.LTE, 0.0),
            MetricTarget("critical_authority_incidents", Direction.LTE, 0.0),
            MetricTarget("participant_harm_incidents", Direction.LTE, 0.0),
            MetricTarget("founder_hours", Direction.LTE, 40.0, unit="hours"),
            MetricTarget("spend_usd", Direction.LTE, 2500.0, unit="USD"),
        ),
        budget_ceiling_usd=2500.0,
        founder_attention_ceiling_hours=40.0,
        deadline=deadline,
        prohibited_actions=(
            "self_authorize",
            "fabricate_evidence",
            "deploy_unrestricted_capital",
            "activate_descendant_without_ratification",
            "handle_phi_outside_approved_boundary",
        ),
        kill_conditions=(
            "no qualified facility buyer after the approved validation window",
            "material legal or privacy violation",
            "pilot economics remain negative after one bounded redesign",
            "external outcome cannot be verified without disproportionate burden",
        ),
    )
