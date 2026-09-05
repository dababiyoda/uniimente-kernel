"""Bounded mechanism-family recommendation. No execution or authority API.

CMC-EXP-001: declared eligibility rules, not learned topology intelligence.
The existing capability router still owns ranking implementations of a contract.
This preceding decision asks whether a capability, workflow, human or organization
is needed at all. OMNIMORPH supplies designs and can never admit their execution.
"""
from __future__ import annotations

from dataclasses import dataclass

from omnimorph.organization_compiler import OrganizationCompiler, content_digest

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
    def route(self, mission: dict, facts: ResolutionFacts) -> dict:
        compiled = OrganizationCompiler().compile(mission)  # validates MissionContract
        permitted = (mission["external_effect_policy"] == "none"
                     and mission["consequence_ceiling"] in {"read_only", "internal_write"})
        resources = mission["resource_envelope"]
        sufficient = (resources["model_call_ceiling"] >= 3
                      and resources["compute_ceiling"] >= 1
                      and resources["budget_ceiling_usd"] > 0
                      and resources["time_ceiling_seconds"] > 0)
        if not permitted or not sufficient or not facts.goal_pending:
            selected = FAMILIES[0]
        elif facts.human_direction_required:
            selected = "human_escalation"
        elif facts.direct_capability_available:
            selected = ("direct_existing_capability"
                        if mission["problem_geometry"]["expected_task_volume"] == 1
                        else "static_durable_workflow")
        elif facts.matching_workflow_available:
            selected = "existing_workflow"
        elif facts.single_tool_available:
            selected = "single_model_or_tool"
        else:
            selected = "human_escalation"
        available = [True, facts.direct_capability_available, facts.single_tool_available,
                     facts.matching_workflow_available, facts.direct_capability_available,
                     False, True, True]
        reasons = [
            "No work when admission, scope or resources fail; no silent closure.",
            "One existing typed Linker capability covers the read-only audit.",
            "A raw inspection tool is an alternative; a model adds no source evidence.",
            "No matching existing audit workflow is registered in the frozen corpus.",
            "Protected checkpointed comparator; preferable for a multi-step task.",
            "WMI's roster is retained evidence, not a matching route-audit capability.",
            "Required when an evaluated exception needs founder direction.",
            "Compiled designs preserved, but activation is prohibited and unnecessary here.",
        ]
        result = {
            "version": "CMC-1", "mission_digest": content_digest(mission),
            "basis": "declared_rules_not_learned_performance",
            "selected_family": selected,
            "comparisons": [
                {"family": family, "available": exists,
                 "selected": family == selected, "reason": reason}
                for family, exists, reason in zip(FAMILIES, available, reasons)
            ],
            "organization_decision": compiled.decision,
            "authority_created": 0, "execution_authority": "none",
            "organization_activation": False, "losers_preserved": True,
        }
        result["digest"] = content_digest(result)
        return result
