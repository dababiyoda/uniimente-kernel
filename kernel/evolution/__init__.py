"""Evolution engine (WP-05) — the ClosureLoop cycle.

``EvolutionCycle`` drives one manual, machine-recorded improvement cycle over
the eight Phase 2 contracts: propose a StrategyTree, attack every branch with
a SpiderWebAudit, select per the pre-registered rule, register and run the
gated experiment (the ONLY gated side effect, Hard Rule 1/3), verify by
independent re-run, decide retain/regress/kill per branch, and seal the
ClosureLoop/EvolutionCapsule pair (ADR-8 dual-reference order).

Every refusal raises ``CycleError`` and leaves the spine untouched — fail
closed (Hard Rule 4).
"""
from .cycle import CycleError, EvolutionCycle

__all__ = ["CycleError", "EvolutionCycle"]
