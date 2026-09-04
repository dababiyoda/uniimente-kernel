"""Deterministic, non-authorizing organizational design compiler.

Phase 3 turns a schema-valid MissionContract and its ProblemGeometry into
materially different OrchestrationGenome hypotheses plus one transparent
TopologyDecision.  It does not import a runtime, EventSpine, model, network,
identity issuer, Consequence Gate, scheduler, or worker executor.

The compiler's arithmetic is a preregistered hypothesis.  It is not evidence
that a topology works.  Every output is design-only, preserves the static
DurableWorkflow and do-not-instantiate choices, and refuses execution admission.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID, uuid5

import rfc8785
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


COMPILER_VERSION = "0.1.0"
_NAMESPACE = UUID("1354b97a-75b8-5f34-a19c-e4c910f79f06")
_CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
_DIGEST_SCOPE = "RFC8785_CANONICAL_JSON_EXCLUDING_DIGEST"

_GENERATABLE = (
    "static_durable_workflow",
    "centralized",
    "hierarchical",
    "hybrid",
    "do_not_instantiate",
)
_EVIDENCE_GATED = ("decentralized", "developmental_local")
_TIE_PRIORITY = {
    "static_durable_workflow": 0,
    "centralized": 1,
    "hierarchical": 2,
    "hybrid": 3,
    "do_not_instantiate": 4,
}

# Positive-only weights consume either the named signal or an explicitly named
# inverse signal. Contributions are integer basis points, so the score trace is
# stable and inspectable. These weights are frozen for OM-EXP-001 Phase 4.
_WEIGHTS: dict[str, tuple[tuple[str, int], ...]] = {
    "static_durable_workflow": (
        ("sequential_dependency", 1600),
        ("task_coupling", 1500),
        ("information_sharing_requirement", 1200),
        ("context_sharing_burden", 1100),
        ("coordination_cost", 1000),
        ("resource_scarcity", 800),
        ("inverse_parallelizability", 1400),
        ("inverse_task_volume", 900),
        ("geometry_evidence_quality", 500),
    ),
    "centralized": (
        ("task_coupling", 1900),
        ("information_sharing_requirement", 1700),
        ("latency_sensitivity", 1300),
        ("context_sharing_burden", 1400),
        ("inverse_task_volume", 1100),
        ("inverse_specialist_diversity", 700),
        ("geometry_evidence_quality", 500),
    ),
    "hierarchical": (
        ("decomposability", 1900),
        ("specialist_diversity", 1600),
        ("task_volume", 1400),
        ("sequential_dependency", 700),
        ("verification_burden", 700),
        ("independent_dissent_need", 500),
        ("geometry_evidence_quality", 400),
    ),
    "hybrid": (
        ("decomposability", 1500),
        ("parallelizability", 1400),
        ("task_coupling", 800),
        ("specialist_diversity", 1300),
        ("verification_burden", 1000),
        ("independent_dissent_need", 1000),
        ("uncertainty", 500),
        ("geometry_evidence_quality", 400),
    ),
    "do_not_instantiate": (
        ("risk_severity", 2000),
        ("consequence_severity", 1800),
        ("failure_severity", 1600),
        ("failure_correlation", 800),
        ("inverse_reversibility", 1800),
        ("resource_scarcity", 700),
        ("inverse_geometry_evidence_quality", 800),
    ),
}
_COMPLEXITY_PENALTY = {
    "static_durable_workflow": 0,
    "centralized": 400,
    "hierarchical": 900,
    "hybrid": 1200,
    "do_not_instantiate": 0,
}
_COORDINATION_MULTIPLIER = {
    "static_durable_workflow": 100,
    "centralized": 400,
    "hierarchical": 900,
    "hybrid": 1200,
    "do_not_instantiate": 0,
}
_SECURITY_GAP_PENALTY = {
    "static_durable_workflow": 200,
    "centralized": 350,
    "hierarchical": 600,
    "hybrid": 700,
    "do_not_instantiate": 0,
}


class OrganizationCompilationError(ValueError):
    """The mission or generated design failed a constitutional invariant."""


@dataclass(frozen=True)
class CompilationResult:
    """Portable Phase-3 artifacts; none is execution admission."""

    mission_digest: str
    problem_geometry_digest: str
    compiler_policy_digest: str
    zero_trust_profile_digest: str
    genomes: tuple[dict[str, Any], ...]
    decision: dict[str, Any]

    def genome_for(self, phenotype: str) -> dict[str, Any]:
        for genome in self.genomes:
            if genome["topology"]["phenotype"] == phenotype:
                return copy.deepcopy(genome)
        raise KeyError(phenotype)


def content_digest(document: Any, *, excluding: Iterable[str] = ()) -> str:
    """Return SHA-256 over RFC-8785 bytes after explicit top-level exclusions.

    Canonicalization failure is a refusal. A digest identifies content; it does
    not assert truth, authorization, execution, or successful outcome.
    """

    excluded = tuple(excluding)
    unsupported = set(excluded) - {"digest"}
    if unsupported:
        raise OrganizationCompilationError(
            "only the self-referential top-level digest field may be excluded"
        )
    value = copy.deepcopy(document)
    if excluded:
        if not isinstance(value, dict):
            raise OrganizationCompilationError("digest exclusions require an object")
        for field in excluded:
            value.pop(field, None)
    try:
        payload = rfc8785.dumps(value)
    except (rfc8785.CanonicalizationError, TypeError, ValueError) as exc:
        raise OrganizationCompilationError(f"RFC8785 canonicalization refused: {exc}") from exc
    return "sha256:" + sha256(payload).hexdigest()


def _validator(name: str) -> Draft202012Validator:
    with (_CONTRACTS / name).open(encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _validated(validator: Draft202012Validator, value: dict[str, Any], label: str) -> None:
    try:
        validator.validate(value)
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path) or "<root>"
        raise OrganizationCompilationError(f"{label} refused at {path}: {exc.message}") from exc


def _zero_trust_profile() -> dict[str, Any]:
    profile: dict[str, Any] = {
        "profile_id": "zero-trust-organizational-v1",
        "version": "1.0.0",
        "digest_scope": _DIGEST_SCOPE,
        "enforcement_status": "DESIGN_ONLY",
        "mechanism_refs": [
            "M11-content-bound-genome",
            "M12-transparent-receipt-without-chain",
            "M13-per-transition-zero-trust",
            "M14-fresh-workload-capability",
            "M15-three-party-attestation",
            "M16-thresholded-improvement-proposal",
            "M17-static-security-fallback",
        ],
        "identity": {
            "policy_ref": "identity:canonical-workload-pki-and-mesh",
            "workload_identity_required": True,
            "identity_is_authority": False,
            "short_lived_credentials_required": True,
            "revocation_check_required": True,
            "replacement_reverification_required": True,
        },
        "authorization": {
            "policy_ref": "authority:canonical-strict-attenuation",
            "capability_grant_required": True,
            "strict_attenuation_required": True,
            "commit_time_revalidation_required": True,
            "topology_may_authorize": False,
            "coordinator_may_mint_authority": False,
        },
        "freshness": {
            "nonce_required": True,
            "timestamp_or_epoch_required": True,
            "replay_rejection_required": True,
            "stale_decision_reuse_permitted": False,
        },
        "integrity": {
            "canonicalization": "RFC8785",
            "digest_algorithm": "SHA-256",
            "canonical_event_spine_only": True,
            "append_only_receipts_required": True,
            "merkle_checkpoint_required": True,
            "blockchain_required": False,
            "token_required": False,
            "independent_external_witness": "NOT_IMPLEMENTED",
        },
        "attestation": {
            "producer_verifier_relying_party_separated": True,
            "attestation_is_authorization": False,
            "hardware_attestation_status": "NOT_IMPLEMENTED",
            "verifier_independent_from_command": True,
        },
        "enforcement": {
            "default_deny": True,
            "missing_identity": "DO_NOT_INSTANTIATE",
            "missing_authority": "DO_NOT_INSTANTIATE",
            "missing_integrity": "STATIC_OR_DO_NOT_INSTANTIATE",
            "missing_verifier": "NO_VERIFIED_CLOSURE",
        },
        "improvement": {
            "live_self_rewrite_permitted": False,
            "versioned_proposal_required": True,
            "independent_evidence_required": True,
            "human_ratification_required": True,
            "authority_expansion_permitted": False,
        },
        "consequence": {
            "gate_only": True,
            "blind_retry_permitted": False,
            "reconciliation_before_retry": True,
        },
    }
    profile["digest"] = content_digest(profile, excluding=("digest",))
    return profile


_ZERO_TRUST_PROFILE = _zero_trust_profile()


def _policy_document() -> dict[str, Any]:
    return {
        "compiler_version": COMPILER_VERSION,
        "generatable": list(_GENERATABLE),
        "evidence_gated": list(_EVIDENCE_GATED),
        "weights": {key: [list(item) for item in value] for key, value in _WEIGHTS.items()},
        "complexity_penalty": _COMPLEXITY_PENALTY,
        "coordination_multiplier": _COORDINATION_MULTIPLIER,
        "security_gap_penalty": _SECURITY_GAP_PENALTY,
        "tie_priority": _TIE_PRIORITY,
        "static_wins_ties": True,
        "automatic_instantiation": False,
        "zero_trust_profile_digest": _ZERO_TRUST_PROFILE["digest"],
    }


_POLICY_DIGEST = content_digest(_policy_document())


def _basis_points(value: float) -> int:
    return max(0, min(10000, int(round(float(value) * 10000))))


def _signals(geometry: dict[str, Any], risk_class: str) -> dict[str, int]:
    signals = {
        key: _basis_points(value)
        for key, value in geometry.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        and key != "expected_task_volume"
    }
    task_volume = min(int(geometry["expected_task_volume"]), 20)
    signals["task_volume"] = task_volume * 500
    signals["inverse_task_volume"] = 10000 - signals["task_volume"]
    for key in (
        "parallelizability",
        "specialist_diversity",
        "reversibility",
    ):
        signals[f"inverse_{key}"] = 10000 - signals[key]
    quality = {"measured": 10000, "mixed": 6000, "estimated": 2500}[geometry["basis"]]
    signals["geometry_evidence_quality"] = quality
    signals["inverse_geometry_evidence_quality"] = 10000 - quality
    signals["risk_severity"] = {
        "low": 1000,
        "moderate": 4000,
        "high": 7500,
        "critical": 10000,
    }[risk_class]
    return signals


def _score(phenotype: str, signals: dict[str, int]) -> dict[str, Any]:
    components = []
    for signal, weight in _WEIGHTS[phenotype]:
        value = signals[signal]
        contribution = value * weight // 10000
        components.append({
            "signal": signal,
            "input_basis_points": value,
            "weight_basis_points": weight,
            "contribution_basis_points": contribution,
        })
    raw = sum(item["contribution_basis_points"] for item in components)
    complexity = _COMPLEXITY_PENALTY[phenotype]
    coordination = signals["coordination_cost"] * _COORDINATION_MULTIPLIER[phenotype] // 10000
    security = _SECURITY_GAP_PENALTY[phenotype]
    return {
        "raw_score_basis_points": raw,
        "complexity_penalty_basis_points": complexity,
        "coordination_penalty_basis_points": coordination,
        "security_gap_penalty_basis_points": security,
        "final_score_basis_points": raw - complexity - coordination - security,
        "components": components,
    }


def _rank_key(candidate: dict[str, Any]) -> tuple[int, int]:
    """Higher score first; exact ties resolve to static then simpler forms."""

    return (-candidate["final_score_basis_points"], _TIE_PRIORITY[candidate["phenotype"]])


def _topology(phenotype: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    worker = {"node_id": "mission-worker", "role": "mission-bounded execution", "power": "organization_execution", "identity_policy_ref": "identity:canonical-worker-lease"}
    evaluator = {"node_id": "independent-evaluator", "role": "independent evidence and dissent appraisal", "power": "independent_evaluation", "identity_policy_ref": "identity:canonical-independent-evaluator"}
    coordinator = {"node_id": "mission-coordinator", "role": "bounded decomposition and synthesis", "power": "coordination", "identity_policy_ref": "identity:existing-coordinator-binding-required"}
    if phenotype == "static_durable_workflow":
        return [worker, evaluator], [{"from": "mission-worker", "to": "independent-evaluator", "event_types": ["task.submitted"]}], 0
    if phenotype == "centralized":
        return [coordinator, worker, evaluator], [
            {"from": "mission-coordinator", "to": "mission-worker", "event_types": ["task.admitted"]},
            {"from": "mission-worker", "to": "independent-evaluator", "event_types": ["task.submitted"]},
        ], 1
    if phenotype == "hierarchical":
        domain = {"node_id": "domain-coordinator", "role": "bounded specialist-domain coordination", "power": "coordination", "identity_policy_ref": "identity:existing-domain-coordinator-binding-required"}
        return [coordinator, domain, worker, evaluator], [
            {"from": "mission-coordinator", "to": "domain-coordinator", "event_types": ["task.admitted"]},
            {"from": "domain-coordinator", "to": "mission-worker", "event_types": ["task.leased"]},
            {"from": "mission-worker", "to": "independent-evaluator", "event_types": ["task.submitted"]},
        ], 2
    if phenotype == "hybrid":
        research = {"node_id": "research-worker", "role": "parallel bounded evidence work", "power": "organization_execution", "identity_policy_ref": "identity:canonical-worker-lease"}
        synthesis = {"node_id": "synthesis-worker", "role": "bounded result synthesis", "power": "organization_execution", "identity_policy_ref": "identity:canonical-worker-lease"}
        return [coordinator, research, synthesis, evaluator], [
            {"from": "mission-coordinator", "to": "research-worker", "event_types": ["task.admitted"]},
            {"from": "research-worker", "to": "synthesis-worker", "event_types": ["task.submitted"]},
            {"from": "synthesis-worker", "to": "independent-evaluator", "event_types": ["task.submitted"]},
        ], 1
    if phenotype == "do_not_instantiate":
        return [], [], 0
    raise OrganizationCompilationError(f"unsupported Phase-3 phenotype {phenotype!r}")


def _command(phenotype: str) -> dict[str, Any]:
    coordinated = phenotype in {"centralized", "hierarchical", "hybrid"}
    return {
        "coordinator_identity_ref": "unbound:existing-canonical-identity-required" if coordinated else None,
        "rights": [
            "decompose",
            "sequence",
            "prioritize",
            "route",
            "request_workers",
            "allocate_authorized_internal_resources",
            "synthesize",
            "request_reconfiguration",
            "escalate",
        ] if coordinated else [],
        "authority_minting_rights": False,
        "mission_rewrite_rights": False,
        "evaluator_suppression_rights": False,
    }


def _worker_pools(mission: dict[str, Any], phenotype: str) -> list[dict[str, Any]]:
    if phenotype == "do_not_instantiate":
        return []
    maximum = {
        "static_durable_workflow": 1,
        "centralized": 1,
        "hierarchical": 2,
        "hybrid": 2,
    }[phenotype]
    maximum = min(maximum, max(1, int(mission["problem_geometry"]["expected_task_volume"])))
    return [
        {
            "role": f"bounded_{item['capability'].replace('.', '_')}",
            "required_capability": item["capability"],
            "minimum_workers": 1,
            "maximum_workers": maximum,
            "concurrency_ceiling": maximum,
            "provider_eligibility": ["provider-neutral"],
            "context_policy_ref": "context:minimum-required",
            "tool_policy_ref": "tools:mission-bounded",
            "lease_required": True,
        }
        for item in mission["required_capabilities"]
    ]


def _communications(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "event_contract": "event",
            "allowed_senders": [edge["from"]],
            "allowed_receivers": [edge["to"]],
            "channel": "canonical-event-spine",
            "sensitivity": "mission-bounded",
            "ordering_requirement": "per_subject",
        }
        for edge in edges
    ]


def _genome(
    mission: dict[str, Any],
    mission_digest: str,
    geometry_digest: str,
    phenotype: str,
    compared: list[str],
) -> dict[str, Any]:
    nodes, edges, depth = _topology(phenotype)
    resource = mission["resource_envelope"]
    genome_id = str(uuid5(_NAMESPACE, f"{mission_digest}|{_POLICY_DIGEST}|{phenotype}"))
    genome: dict[str, Any] = {
        "genome_id": genome_id,
        "schema_version": "1.1",
        "version": "0.1.0",
        "digest_scope": _DIGEST_SCOPE,
        "mission_ref": mission["mission_id"],
        "mission_digest": mission_digest,
        "evidence_status": "hypothesis",
        "zero_trust_profile": copy.deepcopy(_ZERO_TRUST_PROFILE),
        "topology": {
            "phenotype": phenotype,
            "nodes": nodes,
            "edges": edges,
            "hierarchy_depth": depth,
            "allowed_communication_channels": ["canonical-event-spine"],
        },
        "command": _command(phenotype),
        "worker_pools": _worker_pools(mission, phenotype),
        "task_policy": {
            "contract_ref": "contract:task-envelope-v1",
            "priority_policy": "preregistered-order-with-mission-bounded-priority",
            "idempotency_required": True,
            "lease_duration_seconds": 300,
            "timeout_seconds": 240,
            "retry": {
                "maximum_attempts": 2,
                "backoff_policy": "exponential",
                "external_effect_retry_mode": "RECONCILE_BEFORE_RETRY",
            },
            "reconciliation_required_for_uncertain_effect": True,
            "completion_proof": ["typed result", "evidence refs", "independent assessment"],
        },
        "communication": _communications(edges),
        "evaluators": [{
            "role": "independent_adversarial_evaluator",
            "identity_ref": "unbound:existing-independent-evaluator-required",
            "independent_from_command": True,
            "required_assessments": ["evidence sufficiency", "authority invariants", "dissent"],
            "conflict_rule": "preserve and escalate disagreement without suppression",
            "dissent_preservation": True,
            "escalation_destination_ref": mission["acceptance_authority"]["identity_ref"],
        }],
        "resources": {
            "model_call_ceiling": resource["model_call_ceiling"],
            "compute_ceiling": resource["compute_ceiling"],
            "compute_unit": resource["compute_unit"],
            "cost_ceiling_usd": resource["budget_ceiling_usd"],
            "time_ceiling_seconds": resource["time_ceiling_seconds"],
            "reserved_capacity": 0,
        },
        "failure": {
            "timeout_behavior": "expire lease and preserve receipt",
            "worker_loss_behavior": "replace only after fresh identity and attenuated lease verification",
            "coordinator_loss_behavior": "resume from canonical durable checkpoint or degrade to static",
            "poison_task_policy": "quarantine",
            "dead_letter_policy": "preserve and escalate",
            "split_brain_protection": "single canonical workflow owner and content-bound decision",
            "degraded_mode": "static durable workflow or do not instantiate",
        },
        "reconfiguration": {
            "permitted": False,
            "permitted_changes": [],
            "triggers": [],
            "state_transfer_requirements": ["new content-bound genome and explicit state-transfer proof"],
            "evidence_requirement": ["new linked two-pass deliberation and executed episode evidence"],
            "rollback": "use static durable workflow or do not instantiate",
            "maximum_change_scope": "none in Phase 3",
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
            "topology": ["coordination_message_amplification", "topology_selection_accuracy"],
            "failure": ["task_loss_rate", "restart_state_exactness", "authority_violation_count"],
            "cost": ["model_calls", "cost_usd", "founder_attention_minutes"],
        },
        "fallback": {
            "phenotype": "static_durable_workflow" if phenotype != "do_not_instantiate" else "do_not_instantiate",
            "genome_ref": None,
            "trigger": "tie, hard-invariant failure, missing verifier, uncertain state or dynamic deficit",
        },
        "kill_conditions": sorted(set(mission["kill_conditions"] + [
            "authority created or widened by organization",
            "blind retry of uncertain external effect",
            "required evaluator unavailable or suppressed",
            "security design represented as runtime enforcement",
        ])),
        "authority_refs": list(mission["authority_refs"]),
        "authority_invariants": {
            "declares_authority": False,
            "worker_inherits_coordinator_authority": False,
            "replacement_inherits_failed_worker_authority": False,
            "may_bypass_consequence_gate": False,
        },
        "selection_basis": {
            "problem_geometry_digest": geometry_digest,
            "scorecard_ref": f"sha256:{_POLICY_DIGEST.split(':', 1)[1]}",
            "compared_phenotypes": compared,
            "executed_episode_refs": [],
            "claim": "HYPOTHESIS_ONLY",
        },
    }
    genome["digest"] = content_digest(genome, excluding=("digest",))
    return genome


class OrganizationCompiler:
    """Compile designs, never an executing organization."""

    def __init__(self) -> None:
        self._mission_validator = _validator("mission-contract.schema.json")
        self._genome_validator = _validator("orchestration-genome.schema.json")
        self._decision_validator = _validator("topology-decision.schema.json")

    @property
    def policy_digest(self) -> str:
        return _POLICY_DIGEST

    @property
    def zero_trust_profile_digest(self) -> str:
        return _ZERO_TRUST_PROFILE["digest"]

    def compile(self, mission_contract: dict[str, Any]) -> CompilationResult:
        mission = copy.deepcopy(mission_contract)
        _validated(self._mission_validator, mission, "MissionContract")

        allowed = list(mission["organization_policy"]["allowed_phenotypes"])
        for required in ("static_durable_workflow", "do_not_instantiate"):
            if required not in allowed:
                raise OrganizationCompilationError(
                    f"organization policy must preserve {required!r}"
                )

        mission_digest = content_digest(mission)
        geometry_digest = content_digest(mission["problem_geometry"])
        maximum_depth = mission["organization_policy"]["maximum_hierarchy_depth"]

        generated: list[str] = []
        excluded: list[str] = []
        for phenotype in _GENERATABLE:
            if phenotype not in allowed:
                excluded.append(phenotype)
            elif phenotype == "hierarchical" and maximum_depth < 2:
                excluded.append(phenotype)
            elif phenotype in {"centralized", "hybrid"} and maximum_depth < 1:
                excluded.append(phenotype)
            else:
                generated.append(phenotype)

        deferred = []
        for phenotype in _EVIDENCE_GATED:
            if phenotype in allowed:
                deferred.append({
                    "phenotype": phenotype,
                    "reason": "current evidence does not justify Phase-3 admission",
                    "revival_evidence": "canonical executed TopologyEpisodes that beat or complement static under the frozen envelope",
                })
            else:
                excluded.append(phenotype)

        compared = list(generated)
        genomes = [
            _genome(mission, mission_digest, geometry_digest, phenotype, compared)
            for phenotype in generated
        ]
        for genome in genomes:
            _validated(self._genome_validator, genome, "OrchestrationGenome")

        signals = _signals(mission["problem_geometry"], mission["risk_class"])
        summaries: list[dict[str, Any]] = []
        for genome in genomes:
            phenotype = genome["topology"]["phenotype"]
            scored = _score(phenotype, signals)
            summaries.append({
                "phenotype": phenotype,
                "genome_id": genome["genome_id"],
                "genome_digest": genome["digest"],
                "design_eligible": True,
                "execution_eligible": False,
                **scored,
                "hard_gates": [
                    {"gate": "mission_contract_schema", "passed": True, "evidence": mission_digest},
                    {"gate": "authority_delta_zero", "passed": True, "evidence": "authority refs copied exactly"},
                    {"gate": "resource_envelope_equal", "passed": True, "evidence": "mission ceilings copied exactly"},
                    {"gate": "independent_evaluator", "passed": True, "evidence": "independent_from_command=true"},
                    {"gate": "runtime_security_enforcement", "passed": False, "evidence": "zero-trust profile status DESIGN_ONLY"},
                ],
                "reason": "design candidate only; execution requires a separate phase decision and runtime enforcement evidence",
            })

        summaries.sort(key=_rank_key)
        for rank, summary in enumerate(summaries, start=1):
            summary["rank"] = rank

        force_refusal = (
            mission["risk_class"] == "critical"
            or mission["external_effect_policy"] != "none"
            or mission["consequence_ceiling"] in {"external_contact", "financial", "irreversible"}
        )
        if force_refusal:
            recommendation = next(item for item in summaries if item["phenotype"] == "do_not_instantiate")
            rationale = "design-only controls cannot admit a critical or external-effect mission"
        else:
            recommendation = summaries[0]
            rationale = "highest transparent design score after explicit complexity, coordination and security-gap penalties; still not execution-admitted"

        decision_id = str(uuid5(_NAMESPACE, f"{mission_digest}|{_POLICY_DIGEST}|decision"))
        decision: dict[str, Any] = {
            "decision_id": decision_id,
            "schema_version": "1.0",
            "compiler_version": COMPILER_VERSION,
            "decision_status": "HYPOTHESIS_ONLY",
            "digest_scope": _DIGEST_SCOPE,
            "mission_ref": mission["mission_id"],
            "mission_digest": mission_digest,
            "problem_geometry_digest": geometry_digest,
            "compiler_policy_digest": _POLICY_DIGEST,
            "protected_competitors": ["static_durable_workflow", "current_wmi_fixed_roster", "do_not_instantiate"],
            "candidates": summaries,
            "deferred_phenotypes": deferred,
            "excluded_phenotypes": sorted(set(excluded)),
            "comparison_invariants": {
                "same_mission_digest": True,
                "same_resource_envelope": True,
                "same_authority_refs": True,
                "same_external_effect_policy": True,
                "static_baseline_present": True,
                "do_not_instantiate_present": True,
                "independent_evaluator_required": True,
                "zero_trust_profile_digest": _ZERO_TRUST_PROFILE["digest"],
            },
            "recommendation": {
                "phenotype": recommendation["phenotype"],
                "genome_digest": recommendation["genome_digest"],
                "tie_breaker": "STATIC_THEN_SIMPLER",
                "automatic_instantiation": False,
                "execution_admission": "REFUSED_PENDING_SEPARATE_PHASE_DECISION",
                "authority_delta": 0,
                "rationale": rationale,
            },
            "losers_preserved": True,
            "executed_episode_refs": [],
            "knowledge_claim": "MODEL_AND_RULE_OUTPUT_IS_HYPOTHESIS_NOT_ORGANIZATIONAL_KNOWLEDGE",
            "authority_created": 0,
            "external_effects": 0,
            "implementation_gaps": [
                "canonical runtime composition unresolved between PR #70 and PR #87",
                "compiled security profile has no runtime enforcement",
                "production key custody unavailable",
                "distributed revocation propagation unavailable",
                "hardware workload attestation not implemented",
                "independent external anti-equivocation witness not implemented",
                "no executed topology comparison or durable cross-organ closure",
            ],
        }
        decision["digest"] = content_digest(decision, excluding=("digest",))
        _validated(self._decision_validator, decision, "TopologyDecision")

        by_digest = {genome["digest"]: genome for genome in genomes}
        ordered_genomes = tuple(copy.deepcopy(by_digest[item["genome_digest"]]) for item in summaries)
        return CompilationResult(
            mission_digest=mission_digest,
            problem_geometry_digest=geometry_digest,
            compiler_policy_digest=_POLICY_DIGEST,
            zero_trust_profile_digest=_ZERO_TRUST_PROFILE["digest"],
            genomes=ordered_genomes,
            decision=copy.deepcopy(decision),
        )


__all__ = [
    "COMPILER_VERSION",
    "CompilationResult",
    "OrganizationCompilationError",
    "OrganizationCompiler",
    "content_digest",
]
