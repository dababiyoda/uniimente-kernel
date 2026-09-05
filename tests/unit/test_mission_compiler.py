"""Tests for OMNIMORPH's mission-level coupled compiler."""

from __future__ import annotations

import copy

import pytest

from omnimorph.mission_compiler import MissionCompiler
from omnimorph.organization_compiler import content_digest
from tests.unit.test_organizational_morphogenesis_contracts import (
    valid_mission,
    validator,
)


def test_mission_compiler_emits_two_content_bound_artifacts():
    mission = valid_mission()
    result = MissionCompiler().compile(mission)

    manifest = result.capability_manifest
    validator("capability-manifest.schema.json").validate(manifest)

    assert manifest["mission_digest"] == result.mission_digest
    assert manifest["digest"] == content_digest(manifest, excluding=("digest",))
    assert manifest["authority_refs"] == mission["authority_refs"]
    assert manifest["resource_envelope"] == mission["resource_envelope"]
    assert len(manifest["capabilities"]) == len(mission["required_capabilities"])
    assert result.organization.decision["decision_status"] == "HYPOTHESIS_ONLY"
    assert all(
        genome["mission_digest"] == result.mission_digest
        for genome in result.organization.genomes
    )


def test_capability_manifest_and_topology_hypotheses_share_mission_identity():
    result = MissionCompiler().compile(valid_mission())

    assert result.capability_manifest["mission_ref"] == (
        result.organization.genomes[0]["mission_ref"]
    )
    assert result.capability_manifest["execution_admission"] == (
        "REFUSED_PENDING_SEPARATE_PHASE_DECISION"
    )
    assert result.capability_manifest["authority_created"] == 0
    assert result.organization.decision["authority_created"] == 0
    assert result.organization.decision["external_effects"] == 0


def test_compiler_does_not_mutate_mission_or_promote_a_topology():
    mission = valid_mission()
    original = copy.deepcopy(mission)

    result = MissionCompiler().compile(mission)

    assert mission == original
    assert result.organization.decision["recommendation"]["automatic_instantiation"] is False
    assert result.organization.decision["recommendation"]["execution_admission"].startswith(
        "REFUSED"
    )


def test_unknown_manifest_fields_fail_closed():
    manifest = MissionCompiler().compile(valid_mission()).capability_manifest
    altered = copy.deepcopy(manifest)
    altered["self_authorize"] = True

    with pytest.raises(Exception):
        validator("capability-manifest.schema.json").validate(altered)
