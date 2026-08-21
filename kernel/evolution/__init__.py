"""Evolution engine (WP-05) — the ClosureLoop cycle.

``EvolutionCycle`` drives one manual, machine-recorded improvement cycle over
the eight Phase 2 contracts: propose a StrategyTree, attack every branch with
a SpiderWebAudit, select per the pre-registered rule, register and run the
gated experiment (the ONLY gated side effect, Hard Rule 1/3), verify by
independent re-run, decide retain/regress/kill per branch, and seal the
ClosureLoop/EvolutionCapsule pair (ADR-8 dual-reference order).

Every refusal raises ``CycleError`` and leaves the spine untouched — fail
closed (Hard Rule 4).

WP-06 (SPEC-WP06) adds the fast-loop organs on top of the UNCHANGED engine:
``MutationSpace``/``BranchGenerator`` (mechanical branch generation with an
agent_callable injection point), ``RuleBasedAuditor`` + the five shipped
``AuditRule``s (automated SpiderWeb audit), and ``build_report`` /
``build_proposal`` (pure deterministic comparison + pending proposal).
"""
# Import-order guard (additive, WP-06): cycle.py imports
# kernel.authority.approvals, which imports kernel.gate.errors, whose package
# __init__ imports kernel.gate.pipeline, which imports approvals back — a
# latent WP-05 cycle that breaks `import kernel.evolution` standalone.
# Initializing kernel.gate.pipeline FIRST resolves it in the safe direction.
from ..gate import pipeline as _gate_pipeline  # noqa: F401
from .cycle import CycleError, EvolutionCycle
from .generate import BranchGenerator, MutationSpace
from .audit_rules import (
    AuditRule,
    DeclaredReversibilityRule,
    NoExternalDepsRule,
    NoFrozenSurfaceRule,
    ReadPathOnlyRule,
    RuleBasedAuditor,
    SHIPPED_RULES,
    TransactionSemanticsRule,
    parse_variant_config,
)
from .compare import build_proposal, build_report

__all__ = [
    "CycleError",
    "EvolutionCycle",
    "MutationSpace",
    "BranchGenerator",
    "AuditRule",
    "ReadPathOnlyRule",
    "NoFrozenSurfaceRule",
    "NoExternalDepsRule",
    "TransactionSemanticsRule",
    "DeclaredReversibilityRule",
    "RuleBasedAuditor",
    "SHIPPED_RULES",
    "parse_variant_config",
    "build_report",
    "build_proposal",
]
