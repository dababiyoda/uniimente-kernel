"""Acceptance and adversarial tests for the Cognitive Kingmaker protocol."""

from dataclasses import asdict
import json
from pathlib import Path

import pytest

from cognition.kingmaker import (
    CognitiveKingmaker,
    CognitiveRole,
    ConsequenceClass,
    FounderIntentPacket,
    ModelProfile,
    RoutingError,
    WorkRequest,
    build_invention_packet,
)


ROOT = Path(__file__).resolve().parents[2]


def _profiles():
    common = frozenset({"architecture", "coding", "evidence"})
    return (
        ModelProfile(
            model_id="openai-intent-governor",
            provider="openai",
            capabilities=common,
            novelty_score=0.72,
            intent_continuity_score=0.99,
            synthesis_score=0.97,
            implementation_score=0.95,
            adversarial_score=0.94,
            evidence_score=0.97,
            input_cost_per_million=5.0,
            output_cost_per_million=30.0,
            calibration_evidence_ref="sha256:" + "a" * 64,
        ),
        ModelProfile(
            model_id="anthropic-opus-5-novelty",
            provider="anthropic",
            capabilities=common,
            novelty_score=0.99,
            intent_continuity_score=0.84,
            synthesis_score=0.93,
            implementation_score=0.92,
            adversarial_score=0.91,
            evidence_score=0.89,
            input_cost_per_million=10.0,
            output_cost_per_million=50.0,
            calibration_evidence_ref="sha256:" + "b" * 64,
        ),
    )


def _intent():
    return FounderIntentPacket(
        intent_ref="doctrine:founder-intent:v1",
        mission="Build a persistent founder-directed institution that converts intelligence into verified outcomes.",
        protected_invariants=(
            "humans retain constitutional authority",
            "zero unauthorized external effects",
            "negative evidence is preserved",
            "model identity never becomes institutional identity",
        ),
        current_architecture_refs=(
            "kernel:consequence-gate",
            "capabilities:genome",
            "memory:causal",
        ),
        unresolved_contradiction="Use superior novelty cognition without losing founder intent or granting model authority.",
    )


def _request(**overrides):
    values = dict(
        request_id="cognitive-route-001",
        objective="Design a model ecology that uses Opus for novelty and the intent governor for integration.",
        intent=_intent(),
        required_capabilities=frozenset({"architecture", "evidence"}),
        ambiguity=0.9,
        novelty_required=True,
        implementation_required=False,
        evidence_required=True,
        dissent_required=True,
        consequence_class=ConsequenceClass.READ_ONLY,
        irreversible=False,
        budget_ceiling_usd=100.0,
        expected_input_tokens_per_call=50_000,
        expected_output_tokens_per_call=5_000,
    )
    values.update(overrides)
    return WorkRequest(**values)


def test_novelty_routes_to_opus_and_intent_stays_with_governor():
    decision = CognitiveKingmaker(_profiles()).route(_request())
    assert not decision.refused
    roles = {step.role: step for step in decision.steps}
    assert roles[CognitiveRole.NOVELTY_ARCHITECT].model_id == "anthropic-opus-5-novelty"
    assert roles[CognitiveRole.FOUNDER_INTENT_GOVERNOR].model_id == "openai-intent-governor"
    assert roles[CognitiveRole.INSTITUTIONAL_COMPILER].model_id == "openai-intent-governor"


def test_adversary_must_be_independent_from_novelty_lead():
    decision = CognitiveKingmaker(_profiles()).route(_request())
    roles = {step.role: step for step in decision.steps}
    assert roles[CognitiveRole.ADVERSARIAL_REVIEWER].model_id != roles[CognitiveRole.NOVELTY_ARCHITECT].model_id


def test_one_model_cannot_fake_independent_dissent():
    decision = CognitiveKingmaker((_profiles()[1],)).route(_request())
    assert decision.refused
    assert any("independent dissent" in reason for reason in decision.refusal_reasons)


def test_high_consequence_requires_human_and_independent_evidence_review():
    decision = CognitiveKingmaker(_profiles()).route(
        _request(
            consequence_class=ConsequenceClass.FINANCIAL,
            evidence_required=False,
            dissent_required=False,
        )
    )
    assert not decision.refused
    assert decision.requires_human_ratification is True
    assert any(step.role == CognitiveRole.EVIDENCE_AUDITOR for step in decision.steps)
    assert any(step.role == CognitiveRole.ADVERSARIAL_REVIEWER for step in decision.steps)


def test_model_council_never_authorizes_an_external_effect():
    decision = CognitiveKingmaker(_profiles()).route(_request())
    assert decision.external_effect_authorized is False
    assert decision.model_output_is_evidence is False
    assert all(step.output_status == "PROPOSED_NOT_EXECUTED" for step in decision.steps)


def test_budget_overrun_fails_closed_instead_of_hiding_cost():
    decision = CognitiveKingmaker(_profiles()).route(
        _request(budget_ceiling_usd=0.01)
    )
    assert decision.refused
    assert decision.total_estimated_cost_usd > 0.01
    assert any("exceeds budget ceiling" in reason for reason in decision.refusal_reasons)


def test_missing_capability_refuses_every_model():
    decision = CognitiveKingmaker(_profiles()).route(
        _request(required_capabilities=frozenset({"quantum-lab-control"}))
    )
    assert decision.refused
    assert any("required capabilities" in reason for reason in decision.refusal_reasons)


def test_invention_packet_forces_multiple_routes_and_do_nothing():
    request = _request()
    decision = CognitiveKingmaker(_profiles()).route(request)
    packet = build_invention_packet(request, decision)
    assert packet.assigned_model_id == "anthropic-opus-5-novelty"
    assert len(packet.required_routes) >= 6
    assert "one do-nothing alternative" in packet.required_routes
    assert "best simpler competitor" in packet.adversarial_obligations
    assert packet.authority_status == "PROPOSED_NOT_EXECUTED"


def test_refused_route_cannot_be_compiled_into_invention_packet():
    request = _request(budget_ceiling_usd=0.0)
    decision = CognitiveKingmaker(_profiles()).route(request)
    with pytest.raises(RoutingError, match="refused route"):
        build_invention_packet(request, decision)


def test_invalid_calibration_score_is_rejected():
    invalid = ModelProfile(
        model_id="inflated-model",
        provider="vendor",
        capabilities=frozenset(),
        novelty_score=1.5,
        intent_continuity_score=0.5,
        synthesis_score=0.5,
        implementation_score=0.5,
        adversarial_score=0.5,
        evidence_score=0.5,
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
        calibration_evidence_ref="sha256:" + "c" * 64,
    )
    with pytest.raises(RoutingError, match="novelty_score"):
        CognitiveKingmaker((invalid,))


def test_contracts_pin_proposal_only_authority_boundary():
    route_schema = json.loads(
        (ROOT / "contracts" / "cognitive-routing-decision.schema.json").read_text()
    )
    invention_schema = json.loads(
        (ROOT / "contracts" / "invention-packet.schema.json").read_text()
    )
    assert route_schema["properties"]["model_output_is_evidence"]["const"] is False
    assert route_schema["properties"]["external_effect_authorized"]["const"] is False
    assert invention_schema["properties"]["authority_status"]["const"] == "PROPOSED_NOT_EXECUTED"


def test_decision_is_stable_for_identical_inputs():
    router = CognitiveKingmaker(_profiles())
    first = router.route(_request())
    second = router.route(_request())
    assert first.decision_id == second.decision_id
    assert asdict(first) == asdict(second)
