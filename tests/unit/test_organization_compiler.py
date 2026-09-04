"""Phase-3 compiler and zero-trust design-profile tests.

These tests prove deterministic design compilation and refusal behavior only.
They do not prove runtime enforcement, topology performance, or closure.
"""
from __future__ import annotations

import copy
from hashlib import sha256
import inspect
import json

import pytest
from jsonschema import ValidationError

from omnimorph import organization_compiler as compiler_module
from omnimorph.organization_compiler import (
    OrganizationCompilationError,
    OrganizationCompiler,
    content_digest,
)
from test_organizational_morphogenesis_contracts import (
    valid_genome,
    valid_mission,
    validator,
)


EXPECTED_MECHANISMS = {
    "M11-content-bound-genome",
    "M12-transparent-receipt-without-chain",
    "M13-per-transition-zero-trust",
    "M14-fresh-workload-capability",
    "M15-three-party-attestation",
    "M16-thresholded-improvement-proposal",
    "M17-static-security-fallback",
}


@pytest.fixture
def compiler() -> OrganizationCompiler:
    return OrganizationCompiler()


def compile_mission(compiler: OrganizationCompiler, **geometry_changes):
    mission = valid_mission()
    mission["problem_geometry"].update(geometry_changes)
    return mission, compiler.compile(mission)


def test_compile_generates_only_admitted_design_candidates(compiler):
    mission = valid_mission()
    mission["organization_policy"]["allowed_phenotypes"].extend(
        ["decentralized", "developmental_local"]
    )

    result = compiler.compile(mission)

    assert {genome["topology"]["phenotype"] for genome in result.genomes} == {
        "static_durable_workflow",
        "centralized",
        "hierarchical",
        "hybrid",
        "do_not_instantiate",
    }
    assert {item["phenotype"] for item in result.decision["deferred_phenotypes"]} == {
        "decentralized",
        "developmental_local",
    }
    assert result.decision["executed_episode_refs"] == []
    assert result.decision["decision_status"] == "HYPOTHESIS_ONLY"


def test_generated_artifacts_validate_and_bind_their_content(compiler):
    mission, result = compile_mission(compiler)
    genome_validator = validator("orchestration-genome.schema.json")
    decision_validator = validator("topology-decision.schema.json")

    for genome in result.genomes:
        genome_validator.validate(genome)
        assert genome["digest"] == content_digest(genome, excluding=("digest",))
        assert genome["mission_digest"] == content_digest(mission)
    decision_validator.validate(result.decision)
    assert result.decision["digest"] == content_digest(
        result.decision, excluding=("digest",)
    )


def test_compilation_is_deterministic_and_input_mutation_changes_identity(compiler):
    mission = valid_mission()
    first = compiler.compile(mission)
    second = compiler.compile(copy.deepcopy(mission))
    changed = copy.deepcopy(mission)
    changed["objective"] += " Preserve the negative result."
    third = compiler.compile(changed)

    assert first == second
    assert first.mission_digest != third.mission_digest
    assert first.decision["digest"] != third.decision["digest"]
    assert {g["genome_id"] for g in first.genomes}.isdisjoint(
        {g["genome_id"] for g in third.genomes}
    )


def test_rfc8785_digest_is_order_independent_and_known(compiler):
    expected = "sha256:" + sha256(b'{"a":2,"b":1}').hexdigest()
    assert content_digest({"b": 1, "a": 2}) == expected
    assert content_digest({"a": 2, "b": 1}) == expected


def test_digest_refuses_excluding_authority_or_noncanonical_integer():
    with pytest.raises(OrganizationCompilationError, match="only the self-referential"):
        content_digest({"authority_refs": ["authority:a"]}, excluding=("authority_refs",))
    with pytest.raises(OrganizationCompilationError, match="canonicalization refused"):
        content_digest({"outside_i_json_safe_range": 2**60})


def test_zero_trust_profile_uses_mutated_primitives_without_chain_or_token(compiler):
    _, result = compile_mission(compiler)
    profiles = [genome["zero_trust_profile"] for genome in result.genomes]

    assert {profile["digest"] for profile in profiles} == {
        compiler.zero_trust_profile_digest
    }
    for profile in profiles:
        assert set(profile["mechanism_refs"]) == EXPECTED_MECHANISMS
        assert profile["enforcement_status"] == "DESIGN_ONLY"
        assert profile["identity"]["identity_is_authority"] is False
        assert profile["authorization"]["strict_attenuation_required"] is True
        assert profile["freshness"]["replay_rejection_required"] is True
        assert profile["integrity"]["canonical_event_spine_only"] is True
        assert profile["integrity"]["blockchain_required"] is False
        assert profile["integrity"]["token_required"] is False
        assert profile["integrity"]["independent_external_witness"] == "NOT_IMPLEMENTED"
        assert profile["attestation"]["attestation_is_authorization"] is False
        assert profile["attestation"]["hardware_attestation_status"] == "NOT_IMPLEMENTED"
        assert profile["improvement"]["live_self_rewrite_permitted"] is False
        assert profile["improvement"]["human_ratification_required"] is True


def test_zero_trust_schema_negative_controls_fail_closed(compiler):
    _, result = compile_mission(compiler)
    genome_validator = validator("orchestration-genome.schema.json")
    genome = result.genome_for("hybrid")

    mutations = (
        ("identity", "identity_is_authority", True),
        ("authorization", "coordinator_may_mint_authority", True),
        ("freshness", "stale_decision_reuse_permitted", True),
        ("integrity", "blockchain_required", True),
        ("attestation", "attestation_is_authorization", True),
        ("improvement", "live_self_rewrite_permitted", True),
        ("consequence", "blind_retry_permitted", True),
    )
    for section, field, unsafe in mutations:
        altered = copy.deepcopy(genome)
        altered["zero_trust_profile"][section][field] = unsafe
        with pytest.raises(ValidationError):
            genome_validator.validate(altered)


def test_schema_version_transition_preserves_v1_and_requires_profile_for_v1_1(compiler):
    genome_validator = validator("orchestration-genome.schema.json")
    legacy = valid_genome()
    genome_validator.validate(legacy)

    illegal_legacy = copy.deepcopy(legacy)
    illegal_legacy["zero_trust_profile"] = compiler.compile(valid_mission()).genomes[0][
        "zero_trust_profile"
    ]
    with pytest.raises(ValidationError):
        genome_validator.validate(illegal_legacy)

    missing = compiler.compile(valid_mission()).genome_for("static_durable_workflow")
    del missing["zero_trust_profile"]
    with pytest.raises(ValidationError):
        genome_validator.validate(missing)


def test_every_candidate_has_equal_authority_resources_and_no_execution_admission(compiler):
    mission, result = compile_mission(compiler)
    expected_resources = {
        "model_call_ceiling": mission["resource_envelope"]["model_call_ceiling"],
        "compute_ceiling": mission["resource_envelope"]["compute_ceiling"],
        "compute_unit": mission["resource_envelope"]["compute_unit"],
        "cost_ceiling_usd": mission["resource_envelope"]["budget_ceiling_usd"],
        "time_ceiling_seconds": mission["resource_envelope"]["time_ceiling_seconds"],
        "reserved_capacity": 0,
    }

    for genome in result.genomes:
        assert genome["authority_refs"] == mission["authority_refs"]
        assert genome["resources"] == expected_resources
        assert genome["authority_invariants"] == {
            "declares_authority": False,
            "worker_inherits_coordinator_authority": False,
            "replacement_inherits_failed_worker_authority": False,
            "may_bypass_consequence_gate": False,
        }
        assert genome["selection_basis"]["executed_episode_refs"] == []
        assert genome["selection_basis"]["claim"] == "HYPOTHESIS_ONLY"
    assert all(not candidate["execution_eligible"] for candidate in result.decision["candidates"])
    assert result.decision["recommendation"]["automatic_instantiation"] is False
    assert result.decision["recommendation"]["authority_delta"] == 0
    assert result.decision["external_effects"] == 0


def test_evaluator_is_structurally_independent_and_dissent_cannot_be_suppressed(compiler):
    _, result = compile_mission(compiler)
    for genome in result.genomes:
        evaluator = genome["evaluators"][0]
        assert evaluator["independent_from_command"] is True
        assert evaluator["dissent_preservation"] is True
        assert genome["command"]["evaluator_suppression_rights"] is False
        powers = {node["power"] for node in genome["topology"]["nodes"]}
        assert "mission_authority" not in powers
        assert "consequence_authority" not in powers


def test_problem_geometry_materially_changes_transparent_recommendation(compiler):
    _, centralized = compile_mission(
        compiler,
        task_coupling=1.0,
        information_sharing_requirement=1.0,
        latency_sensitivity=1.0,
        context_sharing_burden=1.0,
        expected_task_volume=1,
        specialist_diversity=0.0,
        parallelizability=0.0,
        coordination_cost=0.1,
        basis="measured",
    )
    _, hierarchical = compile_mission(
        compiler,
        decomposability=1.0,
        specialist_diversity=1.0,
        expected_task_volume=20,
        sequential_dependency=1.0,
        verification_burden=0.8,
        independent_dissent_need=0.6,
        parallelizability=0.4,
        task_coupling=0.2,
        coordination_cost=0.1,
        basis="measured",
    )

    assert centralized.decision["recommendation"]["phenotype"] == "centralized"
    assert hierarchical.decision["recommendation"]["phenotype"] == "hierarchical"
    assert centralized.problem_geometry_digest != hierarchical.problem_geometry_digest
    assert centralized.decision["candidates"][0]["components"]


def test_static_wins_exact_score_ties():
    candidates = [
        {"phenotype": "hybrid", "final_score_basis_points": 100},
        {"phenotype": "centralized", "final_score_basis_points": 100},
        {"phenotype": "static_durable_workflow", "final_score_basis_points": 100},
    ]
    assert sorted(candidates, key=compiler_module._rank_key)[0]["phenotype"] == (
        "static_durable_workflow"
    )


@pytest.mark.parametrize("changes", [
    {"risk_class": "critical"},
    {"external_effect_policy": "proposal_only"},
    {"consequence_ceiling": "financial", "external_effect_policy": "gate_required"},
])
def test_unenforced_high_consequence_design_recommends_do_not_instantiate(
    compiler, changes
):
    mission = valid_mission()
    mission.update(changes)
    result = compiler.compile(mission)
    assert result.decision["recommendation"]["phenotype"] == "do_not_instantiate"
    assert result.decision["recommendation"]["execution_admission"].startswith("REFUSED")


@pytest.mark.parametrize("required", ["static_durable_workflow", "do_not_instantiate"])
def test_compiler_refuses_policy_without_protected_fallback(compiler, required):
    mission = valid_mission()
    mission["organization_policy"]["allowed_phenotypes"].remove(required)
    with pytest.raises(OrganizationCompilationError, match=required):
        compiler.compile(mission)


def test_hierarchy_depth_filters_candidates_without_rewriting_policy(compiler):
    mission = valid_mission()
    original = copy.deepcopy(mission)
    mission["organization_policy"]["maximum_hierarchy_depth"] = 0
    result = compiler.compile(mission)

    assert {item["phenotype"] for item in result.decision["candidates"]} == {
        "static_durable_workflow",
        "do_not_instantiate",
    }
    assert {"centralized", "hierarchical", "hybrid"}.issubset(
        result.decision["excluded_phenotypes"]
    )
    original["organization_policy"]["maximum_hierarchy_depth"] = 0
    assert mission == original


def test_unknown_mission_field_is_refused(compiler):
    mission = valid_mission()
    mission["topology_may_authorize"] = True
    with pytest.raises(OrganizationCompilationError, match="MissionContract refused"):
        compiler.compile(mission)


def test_compiler_has_no_runtime_or_external_effect_imports():
    source = inspect.getsource(compiler_module)
    prohibited_imports = (
        "from events",
        "import events",
        "from authority",
        "import authority",
        "from identity",
        "import identity",
        "from gate",
        "import gate",
        "requests",
        "socket",
    )
    assert not any(token in source for token in prohibited_imports)
    assert "PROPOSED_NOT_EXECUTED" not in source
    assert "REFUSED_PENDING_SEPARATE_PHASE_DECISION" in source


def test_decision_schema_rejects_execution_or_knowledge_theater(compiler):
    decision_validator = validator("topology-decision.schema.json")
    decision = compiler.compile(valid_mission()).decision

    for field, unsafe in (
        ("authority_created", 1),
        ("external_effects", 1),
        ("losers_preserved", False),
        ("executed_episode_refs", ["episode:imaginary"]),
    ):
        altered = copy.deepcopy(decision)
        altered[field] = unsafe
        with pytest.raises(ValidationError):
            decision_validator.validate(altered)

    altered = copy.deepcopy(decision)
    altered["recommendation"]["automatic_instantiation"] = True
    with pytest.raises(ValidationError):
        decision_validator.validate(altered)


def test_policy_and_profile_digests_are_stable_sha256_identifiers(compiler):
    assert compiler.policy_digest.startswith("sha256:")
    assert compiler.zero_trust_profile_digest.startswith("sha256:")
    assert len(compiler.policy_digest) == 71
    assert len(compiler.zero_trust_profile_digest) == 71
    assert compiler.policy_digest != compiler.zero_trust_profile_digest


def test_profile_digest_detects_security_control_mutation(compiler):
    profile = compiler.compile(valid_mission()).genomes[0]["zero_trust_profile"]
    assert profile["digest"] == content_digest(profile, excluding=("digest",))
    altered = copy.deepcopy(profile)
    altered["identity"]["revocation_check_required"] = False
    assert altered["digest"] != content_digest(altered, excluding=("digest",))


def test_json_round_trip_preserves_compiled_artifacts(compiler):
    result = compiler.compile(valid_mission())
    assert json.loads(json.dumps(result.decision)) == result.decision
    assert [json.loads(json.dumps(item)) for item in result.genomes] == list(result.genomes)
