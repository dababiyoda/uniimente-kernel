"""Five-closure extension for MICA/CDPE TARGET_FORM_001."""
from __future__ import annotations

from closure.framework import ClosureRegistry, ModuleClosures
from developmental import (
    DevelopmentalError,
    DevelopmentalProgramExecutor,
    DevelopmentalVerdict,
    IntelligenceGenome,
    LocalRuleGenome,
    MICAField,
)


def register_developmental_closures(registry: ClosureRegistry) -> ClosureRegistry:
    def technical():
        report = DevelopmentalProgramExecutor().run()
        return (
            report.verdict
            is DevelopmentalVerdict.MECHANICS_VALIDATED_NOT_PRODUCTION_AUTHORIZED
            and report.distributed.delivered > 0
            and report.adaptive_central.delivered > 0,
            "120-cell local field recovers transport after 20% loss and route obstruction",
        )

    def authority():
        report = DevelopmentalProgramExecutor().run()
        refused_external = False
        refused_production = False
        try:
            DevelopmentalProgramExecutor(
                rules=LocalRuleGenome(external_effects_allowed=True)
            )
        except DevelopmentalError:
            refused_external = True
        try:
            DevelopmentalProgramExecutor(
                intelligence=IntelligenceGenome(production_authority=True)
            )
        except DevelopmentalError:
            refused_production = True
        return (
            report.authorization_state == "SIMULATED_NOT_AUTHORIZED"
            and report.external_effects == 0
            and refused_external
            and refused_production,
            "simulation carries zero external or production authority and rejects authority mutation",
        )

    def evidence():
        first = DevelopmentalProgramExecutor().run()
        second = DevelopmentalProgramExecutor().run()
        return (
            first.benchmark_id == second.benchmark_id
            and first.original_route == second.original_route
            and first.recovered_route == second.recovered_route
            and first.metadata["removed_cell_ids"] == second.metadata["removed_cell_ids"]
            and first.metadata["blocked_original_edges"]
            == len(first.original_route) - 1,
            "deterministic benchmark id, damage set, blocked route, and recovery route are reconstructable",
        )

    def economic():
        report = DevelopmentalProgramExecutor().run()
        return (
            report.recovery_throughput_ratio >= 0.90
            and report.compute_ratio_vs_adaptive_central <= 4.0
            and report.static_central.delivered == 0
            and report.adaptive_central.delivered > 0,
            "distributed recovery matches adaptive-central throughput within the declared compute ceiling and beats static orchestration",
        )

    def regenerative():
        report = DevelopmentalProgramExecutor().run()
        return (
            report.removed_fraction == 0.20
            and report.original_route_blocked
            and report.recovered_route != report.original_route
            and report.false_activations == 0
            and report.exact_restoration_attempts == 0
            and report.distributed.delivered > 0,
            "function recovers through a novel route without restoring removed cells or activating damaged units",
        )

    registry.register(ModuleClosures("developmental_substrate", {
        "technical": technical,
        "authority": authority,
        "evidence": evidence,
        "economic": economic,
        "regenerative": regenerative,
    }))
    return registry
