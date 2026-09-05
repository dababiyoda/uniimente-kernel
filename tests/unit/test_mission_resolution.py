"""Tests for the mechanism-first Mission Resolution Router."""

from __future__ import annotations

import copy

import pytest

from egregore.mission_resolution import (
    RESOLUTION_CLASSES,
    MissionResolutionError,
    MissionResolutionRouter,
    ResolutionCandidate,
)
from omnimorph.mission_compiler import MissionCompiler
from tests.unit.test_organizational_morphogenesis_contracts import valid_mission, validator


def direct_candidate(
    *,
    quality: float = 0.95,
    evidence: str = "TESTED",
    coordination: float = 0.1,
) -> ResolutionCandidate:
    return ResolutionCandidate(
        candidate_id="capability:read-only-audit",
        resolution_class="direct_capability",
        description="one existing read-only capability",
        available=True,
        execution_eligible=True,
        evidence_maturity=evidence,
        expected_quality=quality,
        estimated_cost_usd=0.1,
        coordination_units=coordination,
        founder_attention_minutes=0,
        reversible=True,
        reason="a direct capability covers the bounded internal objective",
        evidence_refs=("evidence:direct-capability",),
    )


def test_router_retains_every_resolution_class_and_picks_smallest_sufficient():
    mission = copy.deepcopy(valid_mission())
    mission["consequence_ceiling"] = "read_only"
    result = MissionResolutionRouter().route(
        mission,
        candidates=(direct_candidate(),),
        compiled_organization=MissionCompiler().compile(mission),
    )

    validator("mission-resolution.schema.json").validate(result.to_dict())
    assert {candidate.resolution_class for candidate in result.candidates} == set(
        RESOLUTION_CLASSES
    )
    assert result.selected is not None
    assert result.selected.resolution_class == "direct_capability"
    assert result.execution_authority == "none"
    assert result.to_dict()["authority_created"] == 0
    assert result.to_dict()["external_effects"] == 0
    assert result.to_dict()["losers_preserved"] is True


def test_static_workflow_wins_an_exact_score_tie():
    mission = copy.deepcopy(valid_mission())
    mission["consequence_ceiling"] = "read_only"
    result = MissionResolutionRouter().route(
        mission,
        candidates=(direct_candidate(quality=0.75, coordination=1.0),),
    )

    assert result.selected is not None
    assert result.selected.resolution_class == "static_durable_workflow"


def test_external_or_high_consequence_mission_escalates_or_refuses():
    mission = valid_mission()
    result = MissionResolutionRouter().route(
        mission,
        candidates=(direct_candidate(),),
        unresolved_reasons=("manifest pin drift requires founder disposition",),
    )
    # valid_mission is internal_write, so this is intentionally not an external
    # action. The resolver still refuses work only when the policy is explicit.
    assert result.selected is not None
    assert result.selected.resolution_class == "direct_capability"

    mission["consequence_ceiling"] = "financial"
    mission["external_effect_policy"] = "gate_required"
    result = MissionResolutionRouter().route(
        mission,
        candidates=(direct_candidate(),),
        unresolved_reasons=("financial authority is reserved",),
    )
    assert result.selected is not None
    assert result.selected.resolution_class == "human_escalation"
    assert any(
        row["resolution_class"] == "direct_capability" and not row["eligible"]
        for row in result.ranking
    )


def test_compiled_organization_is_retained_but_never_activated_by_router():
    mission = copy.deepcopy(valid_mission())
    mission["consequence_ceiling"] = "read_only"
    compiled = MissionCompiler().compile(mission)
    result = MissionResolutionRouter().route(
        mission,
        compiled_organization=compiled,
    )
    org = next(
        candidate for candidate in result.candidates
        if candidate.resolution_class == "compiled_temporary_organization"
    )
    assert org.available is True
    assert org.execution_eligible is False
    assert result.selected is not org


def test_no_action_is_the_fail_closed_result_when_nothing_is_available():
    mission = copy.deepcopy(valid_mission())
    mission["consequence_ceiling"] = "read_only"
    result = MissionResolutionRouter().route(
        mission,
        static_baseline_available=False,
    )

    assert result.selected is not None
    assert result.selected.resolution_class == "no_action"


def test_unknown_candidate_fields_are_refused():
    mission = valid_mission()
    bad = direct_candidate().to_dict()
    bad["authority"] = "A9"
    with pytest.raises(MissionResolutionError):
        MissionResolutionRouter().route(mission, candidates=(bad,))
