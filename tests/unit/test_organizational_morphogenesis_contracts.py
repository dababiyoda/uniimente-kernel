"""Phase-1 contract tests for the Organizational Morphogenesis experiment.

These tests deliberately contain negative controls. They validate semantics
only; they do not claim a runtime, a topology win, or a durable mission closure.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
DIGEST = "sha256:" + "a" * 64
OTHER_DIGEST = "sha256:" + "b" * 64
MISSION_ID = "7e4df12e-bae5-4ec4-a2db-b3257e0b7029"
GENOME_ID = "1bbacacc-09f1-430d-9b54-dae3bdd119bc"
EPISODE_ID = "69035ab8-97a0-43bc-97c8-716fd6772276"


def schema(name: str) -> dict:
    with (CONTRACTS / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def validator(name: str) -> Draft202012Validator:
    document = schema(name)
    Draft202012Validator.check_schema(document)
    return Draft202012Validator(document, format_checker=FormatChecker())


def valid_geometry() -> dict:
    dimensions = {
        "decomposability": 0.8,
        "task_coupling": 0.4,
        "parallelizability": 0.7,
        "sequential_dependency": 0.5,
        "information_sharing_requirement": 0.6,
        "uncertainty": 0.7,
        "search_space_size": 0.6,
        "specialist_diversity": 0.8,
        "latency_sensitivity": 0.3,
        "failure_severity": 0.4,
        "failure_correlation": 0.3,
        "coordination_cost": 0.5,
        "context_sharing_burden": 0.5,
        "verification_burden": 0.9,
        "consequence_severity": 0.2,
        "reversibility": 1.0,
        "resource_scarcity": 0.5,
        "deadline_pressure": 0.4,
        "independent_dissent_need": 1.0,
    }
    return {
        **dimensions,
        "expected_task_volume": 5,
        "basis": "mixed",
        "assumptions": ["internal read-only corpus"],
        "evidence_refs": ["evidence:geometry-preregistration-v1"],
    }


def valid_mission() -> dict:
    return {
        "mission_id": MISSION_ID,
        "schema_version": "1.0",
        "founder_intent_ref": "INTENT-OM-2026-08-28",
        "objective": "Evaluate one DALEOBANKS opportunity through WealthMachine with independent dissent and no external effect.",
        "beneficiaries": ["UNIIMENTE institution"],
        "legal_principal": "alfonso_lopez",
        "authority_refs": ["authority:internal-sandbox-only"],
        "issued_at": "2026-08-28T12:00:00Z",
        "deadline": "2026-09-30T23:59:59Z",
        "resource_envelope": {
            "budget_ceiling_usd": 50,
            "compute_ceiling": 100,
            "compute_unit": "normalized_compute_unit",
            "model_call_ceiling": 30,
            "founder_attention_ceiling_minutes": 60,
            "time_ceiling_seconds": 3600,
        },
        "consequence_ceiling": "internal_write",
        "required_capabilities": [
            {"capability": "opportunity.evaluate", "version_constraint": ">=1.0.0", "purpose": "bounded venture assessment"},
            {"capability": "evidence.adversarial_review", "version_constraint": ">=1.0.0", "purpose": "independent dissent"},
        ],
        "success_conditions": [
            {"condition_id": "closure", "metric": "verified_internal_closure", "operator": "eq", "target": True, "hard": True}
        ],
        "evidence_requirements": [
            {"requirement_id": "lineage", "artifact_type": "causal_receipts", "verifier_role": "independent_evaluator", "minimum_count": 1, "source_policy": "canonical interfaces only"}
        ],
        "risk_class": "low",
        "data_constraints": {
            "allowed_classifications": ["public", "synthetic"],
            "prohibited_data": ["credentials", "personal_sensitive_data"],
            "retention_ceiling_seconds": 2592000,
        },
        "prohibited_actions": ["publish", "contact_external_party", "move_money"],
        "reversibility": {"required": True, "maximum_irreversible_scope": "none", "rollback_authority_ref": "authority:alfonso"},
        "kill_conditions": ["authority invariant violation", "coordination amplification above threshold"],
        "escalation_rules": [
            {"trigger": "required evaluator disagreement", "destination_identity_ref": "human:alfonso", "required_evidence": ["assessment receipts", "dissent record"]}
        ],
        "external_effect_policy": "none",
        "acceptance_authority": {"identity_ref": "human:alfonso", "authority_ref": "authority:alfonso"},
        "closure_condition": {
            "required_success_condition_ids": ["closure"],
            "require_no_active_tasks": True,
            "require_no_open_obligations": True,
            "require_closure_receipt": True,
        },
        "organization_policy": {
            "allowed_phenotypes": ["static_durable_workflow", "centralized", "hierarchical", "hybrid", "do_not_instantiate"],
            "maximum_hierarchy_depth": 2,
            "independent_evaluation_required": True,
            "static_baseline_required": True,
        },
        "authority_invariants": {
            "organization_may_create_authority": False,
            "worker_inherits_supervisor_authority": False,
            "consequence_gate_bypass_permitted": False,
            "organization_may_rewrite_mission": False,
        },
        "problem_geometry": valid_geometry(),
    }


def valid_genome() -> dict:
    return {
        "genome_id": GENOME_ID,
        "schema_version": "1.0",
        "version": "1.0.0",
        "digest": DIGEST,
        "digest_scope": "RFC8785_CANONICAL_JSON_EXCLUDING_DIGEST",
        "mission_ref": MISSION_ID,
        "mission_digest": OTHER_DIGEST,
        "evidence_status": "experiment_candidate",
        "topology": {
            "phenotype": "static_durable_workflow",
            "nodes": [
                {"node_id": "wmi-evaluation", "role": "venture evaluation", "power": "organization_execution", "identity_policy_ref": "identity:worker-lease"},
                {"node_id": "adversarial-evaluator", "role": "independent review", "power": "independent_evaluation", "identity_policy_ref": "identity:evaluator-lease"},
            ],
            "edges": [
                {"from": "wmi-evaluation", "to": "adversarial-evaluator", "event_types": ["task.submitted"]}
            ],
            "hierarchy_depth": 0,
            "allowed_communication_channels": ["canonical-event-spine"],
        },
        "command": {
            "coordinator_identity_ref": None,
            "rights": [],
            "authority_minting_rights": False,
            "mission_rewrite_rights": False,
            "evaluator_suppression_rights": False,
        },
        "worker_pools": [
            {
                "role": "venture_evaluator",
                "required_capability": "opportunity.evaluate",
                "minimum_workers": 1,
                "maximum_workers": 1,
                "concurrency_ceiling": 1,
                "provider_eligibility": ["provider-neutral"],
                "context_policy_ref": "context:minimum-required",
                "tool_policy_ref": "tools:read-only",
                "lease_required": True,
            }
        ],
        "task_policy": {
            "contract_ref": "contract:task-envelope-deferred-phase-2",
            "priority_policy": "fixed preregistered order",
            "idempotency_required": True,
            "lease_duration_seconds": 300,
            "timeout_seconds": 240,
            "retry": {"maximum_attempts": 2, "backoff_policy": "exponential", "external_effect_retry_mode": "RECONCILE_BEFORE_RETRY"},
            "reconciliation_required_for_uncertain_effect": True,
            "completion_proof": ["typed result", "evidence refs", "independent assessment"],
        },
        "communication": [
            {
                "event_contract": "event",
                "allowed_senders": ["wmi-evaluation"],
                "allowed_receivers": ["adversarial-evaluator"],
                "channel": "canonical-event-spine",
                "sensitivity": "internal",
                "ordering_requirement": "per_subject",
            }
        ],
        "evaluators": [
            {
                "role": "adversarial_evaluator",
                "identity_ref": "identity:independent-evaluator",
                "independent_from_command": True,
                "required_assessments": ["evidence sufficiency", "dissent"],
                "conflict_rule": "escalate disagreement without suppression",
                "dissent_preservation": True,
                "escalation_destination_ref": "human:alfonso",
            }
        ],
        "resources": {
            "model_call_ceiling": 30,
            "compute_ceiling": 100,
            "compute_unit": "normalized_compute_unit",
            "cost_ceiling_usd": 50,
            "time_ceiling_seconds": 3600,
            "reserved_capacity": 5,
        },
        "failure": {
            "timeout_behavior": "expire lease and preserve receipt",
            "worker_loss_behavior": "replace with a fresh least-authority lease",
            "coordinator_loss_behavior": "resume from canonical durable checkpoint",
            "poison_task_policy": "quarantine",
            "dead_letter_policy": "preserve and escalate",
            "split_brain_protection": "single canonical workflow owner",
            "degraded_mode": "static durable workflow",
        },
        "reconfiguration": {
            "permitted": False,
            "permitted_changes": [],
            "triggers": [],
            "state_transfer_requirements": ["not applicable in phase 1"],
            "evidence_requirement": ["new linked deliberation"],
            "rollback": "use static durable workflow",
            "maximum_change_scope": "none",
            "live_self_rewrite_permitted": False,
        },
        "dissolution": {
            "require_task_closure": True,
            "require_resource_release": True,
            "require_credential_expiry": True,
            "require_worker_termination": True,
            "require_evidence_preservation": True,
            "require_obligation_reconciliation": True,
        },
        "metrics": {
            "mission": ["verified_durable_mission_closure"],
            "topology": ["coordination_message_amplification"],
            "failure": ["task_loss_rate", "restart_state_exactness"],
            "cost": ["model_calls", "cost_usd"],
        },
        "fallback": {"phenotype": "static_durable_workflow", "genome_ref": None, "trigger": "any hard invariant or dynamic-topology deficit"},
        "kill_conditions": ["authority violation", "blind retry of uncertain effect"],
        "authority_refs": ["authority:internal-sandbox-only"],
        "authority_invariants": {
            "declares_authority": False,
            "worker_inherits_coordinator_authority": False,
            "replacement_inherits_failed_worker_authority": False,
            "may_bypass_consequence_gate": False,
        },
        "selection_basis": {
            "problem_geometry_digest": DIGEST,
            "scorecard_ref": "experiment:preregistered-scorecard-v1",
            "compared_phenotypes": ["static_durable_workflow", "hybrid"],
            "executed_episode_refs": [],
            "claim": "EXPERIMENT_CANDIDATE",
        },
    }


def valid_episode() -> dict:
    return {
        "episode_id": EPISODE_ID,
        "schema_version": "1.0",
        "record_kind": "EXECUTED_TOPOLOGY_EPISODE",
        "mission_ref": MISSION_ID,
        "mission_digest": OTHER_DIGEST,
        "problem_geometry_digest": DIGEST,
        "orchestration_genome_digest": DIGEST,
        "capability_genome_versions": [{"capability": "opportunity.evaluate", "version": "1.0.0", "digest": DIGEST}],
        "worker_composition": [{"role": "venture_evaluator", "worker_count": 1, "lease_refs": ["lease:1"]}],
        "provider_composition": [{"role": "venture_evaluator", "provider": "test-provider", "model": "test-model", "calls": 1}],
        "task_graph_digest": DIGEST,
        "resource_consumption": {"model_calls": 1, "compute_used": 1, "compute_unit": "normalized_compute_unit", "founder_attention_minutes": 0, "wall_time_seconds": 1},
        "coordination_message_amplification": 1,
        "failure_events": [],
        "reconfigurations": [],
        "dissent_records": ["dissent:1"],
        "completion_quality": 1,
        "verification_quality": 1,
        "cost_usd": 0,
        "latency_ms": 1000,
        "recovery": {"interruptions": 0, "restart_state_exactness": 1, "rto_seconds": 0, "rpo_seconds": 0, "lost_tasks": 0, "duplicate_consequential_work": 0},
        "external_outcome_ref": None,
        "closure_disposition": "CLOSED_UNVERIFIED",
        "metrics": {
            "task_loss_rate": 0,
            "duplicate_work_rate": 0,
            "unresolved_task_rate": 0,
            "failure_containment_rate": 1,
            "worker_utilization": 1,
            "maximum_coordinator_load": 0,
            "evidence_lineage_completeness": 1,
            "dissent_preservation_rate": 1,
            "context_policy_violation_count": 0,
        },
        "lineage": {
            "founder_intent_ref": "INTENT-OM-2026-08-28",
            "mission_ref": MISSION_ID,
            "task_receipt_refs": ["receipt:task:1"],
            "result_refs": ["result:1"],
            "assessment_refs": ["assessment:1"],
            "closure_receipt_ref": None,
        },
        "authority_results": {
            "unauthorized_external_effect_count": 0,
            "authority_violation_count": 0,
            "authority_created_by_organization_count": 0,
            "required_evaluator_suppression_count": 0,
            "unknown_external_effect_blind_retry_count": 0,
        },
        "evidence_refs": ["evidence:episode:1"],
        "verified_durable_mission_closure": False,
        "promotion_disposition": "NOT_EVALUATED",
        "model_prediction": False,
    }


@pytest.mark.parametrize(
    ("contract", "document"),
    [
        ("mission-contract.schema.json", valid_mission()),
        ("orchestration-genome.schema.json", valid_genome()),
        ("topology-episode.schema.json", valid_episode()),
    ],
)
def test_valid_contract_examples(contract: str, document: dict):
    validator(contract).validate(document)


@pytest.mark.parametrize(
    ("contract", "document"),
    [
        ("mission-contract.schema.json", valid_mission()),
        ("orchestration-genome.schema.json", valid_genome()),
        ("topology-episode.schema.json", valid_episode()),
    ],
)
def test_contracts_fail_closed_on_unknown_fields(contract: str, document: dict):
    document["unowned_semantic"] = "must fail"
    with pytest.raises(Exception):
        validator(contract).validate(document)


def test_topology_cannot_create_or_inherit_authority():
    document = valid_genome()
    document["authority_invariants"]["declares_authority"] = True
    document["authority_invariants"]["worker_inherits_coordinator_authority"] = True
    with pytest.raises(Exception):
        validator("orchestration-genome.schema.json").validate(document)


def test_commander_cannot_suppress_independent_evaluator():
    document = valid_genome()
    document["command"]["evaluator_suppression_rights"] = True
    document["evaluators"][0]["independent_from_command"] = False
    with pytest.raises(Exception):
        validator("orchestration-genome.schema.json").validate(document)


def test_prediction_cannot_be_promoted_as_validated_knowledge():
    document = valid_genome()
    document["evidence_status"] = "validated"
    document["selection_basis"]["claim"] = "SUPPORTED_BY_EXECUTED_EPISODES"
    document["selection_basis"]["executed_episode_refs"] = []
    with pytest.raises(Exception):
        validator("orchestration-genome.schema.json").validate(document)


def test_external_consequence_requires_gate_policy():
    document = valid_mission()
    document["consequence_ceiling"] = "financial"
    document["external_effect_policy"] = "none"
    with pytest.raises(Exception):
        validator("mission-contract.schema.json").validate(document)


def test_uniimente_cannot_be_legal_principal():
    document = valid_mission()
    document["legal_principal"] = "UNIIMENTE"
    with pytest.raises(Exception):
        validator("mission-contract.schema.json").validate(document)


def test_verified_durable_closure_cannot_be_claimed_without_interruption_receipt():
    document = valid_episode()
    document["verified_durable_mission_closure"] = True
    document["closure_disposition"] = "CLOSED_VERIFIED"
    with pytest.raises(Exception):
        validator("topology-episode.schema.json").validate(document)


def test_verified_durable_closure_fails_on_authority_violation_negative_control():
    document = valid_episode()
    document["verified_durable_mission_closure"] = True
    document["closure_disposition"] = "CLOSED_VERIFIED"
    document["interruption_evidence_refs"] = ["evidence:restart:1"]
    document["lineage"]["closure_receipt_ref"] = "receipt:closure:1"
    document["recovery"]["interruptions"] = 1
    document["authority_results"]["authority_violation_count"] = 1
    with pytest.raises(Exception):
        validator("topology-episode.schema.json").validate(document)


def test_verified_durable_closure_accepts_only_full_invariant_evidence():
    document = valid_episode()
    document["verified_durable_mission_closure"] = True
    document["closure_disposition"] = "CLOSED_VERIFIED"
    document["interruption_evidence_refs"] = ["evidence:restart:1"]
    document["lineage"]["closure_receipt_ref"] = "receipt:closure:1"
    document["recovery"]["interruptions"] = 1
    validator("topology-episode.schema.json").validate(document)


def test_model_prediction_cannot_pose_as_executed_episode():
    document = valid_episode()
    document["model_prediction"] = True
    with pytest.raises(Exception):
        validator("topology-episode.schema.json").validate(document)
