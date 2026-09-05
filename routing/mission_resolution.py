"""Bounded mechanism-family recommendation. No execution or authority API.

CMC-EXP-001: declared eligibility rules, not learned topology intelligence.
The existing capability router still owns ranking implementations of a contract.
This preceding decision asks whether a capability, workflow, human or organization
is needed at all. OMNIMORPH supplies designs and can never admit their execution.
"""
from __future__ import annotations

from dataclasses import dataclass

from omnimorph.organization_compiler import content_digest
from omnimorph.mission_compiler import MissionCompiler
from routing.mission_selector import MissionResolutionRouter as CanonicalRouter, ResolutionCandidate

FAMILIES = (
    "no_action_wait_refusal", "direct_existing_capability", "single_model_or_tool",
    "existing_workflow", "static_durable_workflow", "fixed_specialists",
    "human_escalation", "omnimorph_temporary_organization",
)


@dataclass(frozen=True)
class ResolutionFacts:
    goal_pending: bool = True
    direct_capability_available: bool = True
    single_tool_available: bool = True
    matching_workflow_available: bool = False
    human_direction_required: bool = False

    def __post_init__(self):
        if any(type(value) is not bool for value in vars(self).values()):
            raise ValueError("resolution facts must be explicit booleans")


class MissionResolutionRouter:
    """Legacy fact adapter, not a second ranking implementation.

    Canonical source/owner: routing.mission_selector. Expiry: the historical
    CMC-EXP-001 probe adopts canonical candidates. Removal: no legacy callers.
    Original rules remain in checkpoint 6b2547298eb2ef7c452bb5699f9e59a562b7d4d9.
    """
    def route(self, mission: dict, facts: ResolutionFacts) -> dict:
        compiled = MissionCompiler().compile(mission)
        r = mission["resource_envelope"]
        admitted = (facts.goal_pending and mission["external_effect_policy"] == "none"
            and mission["consequence_ceiling"] in {"read_only", "internal_write"}
            and r["model_call_ceiling"] >= 3 and r["compute_ceiling"] >= 1
            and r["budget_ceiling_usd"] > 0 and r["time_ceiling_seconds"] > 0)
        working = admitted and not facts.human_direction_required
        single_task = mission["problem_geometry"]["expected_task_volume"] == 1
        classes = ("no_action", "direct_capability", "single_model_or_tool",
                   "existing_workflow", "static_durable_workflow",
                   "fixed_specialist_configuration", "human_escalation",
                   "compiled_temporary_organization")
        available = (True, working and facts.direct_capability_available and single_task,
            working and facts.single_tool_available, working and facts.matching_workflow_available,
            working and facts.direct_capability_available and not single_task,
            False, admitted, True)
        quality = (0, .95, .85, .9, .95, 0,
                   1 if facts.human_direction_required else .5, 0)
        reasons = (
            "Refusal or waiting remains available; it does not imply closure.",
            "Declared typed Linker capability for one read-only audit.",
            "A single inspection tool is sufficient when no typed capability exists.",
            "A matching existing workflow is declared by the frozen facts.",
            "Protected static comparator for multiple dependent steps; wins ties.",
            "Fixed WMI roster retained as a competitor, not a route-audit capability.",
            "Human direction is required or simpler available work is insufficient.",
            "Compiled organization is a hypothesis; activation is prohibited.")
        candidates = tuple(ResolutionCandidate(
            candidate_id="legacy:" + family, resolution_class=kind,
            description=reason, available=exists,
            execution_eligible=exists and kind != "compiled_temporary_organization",
            evidence_maturity="DECLARED", expected_quality=q,
            estimated_cost_usd=0, coordination_units=0, founder_attention_minutes=0,
            reversible=True, reason=reason)
            for family, kind, exists, q, reason in zip(FAMILIES, classes, available, quality, reasons))
        decision = CanonicalRouter().route(mission, candidates=candidates,
            static_baseline_available=False, compiled_organization=compiled)
        selected = decision.selected_candidate_id.removeprefix("legacy:")
        result = {
            "version": "CMC-1", "mission_digest": content_digest(mission),
            "basis": "declared_rules_not_learned_performance",
            "selected_family": selected,
            "comparisons": [{"family": family, "available": exists,
                "selected": family == selected, "reason": reason}
                for family, exists, reason in zip(FAMILIES, available, reasons)],
            "organization_decision": compiled.organization.decision,
            "canonical_resolution": decision.to_dict(),
            "authority_created": 0, "execution_authority": "none",
            "organization_activation": False, "losers_preserved": True,
        }
        result["digest"] = content_digest(result)
        return result
