"""Phase 3: automated strategy-branch generation.

Doctrine (EVOLUTION): for one bottleneck the machine drafts candidate
branches across ALL eleven branch kinds — fastest_path through do_nothing.
Breadth is not optional: a tree missing kinds is a blind spot, and
do_nothing is always a legitimate contender (sometimes the truth is
"wait").

Every generated branch carries all twelve required fields; the generator
never emits a branch that fails StrategyBranch.validate(). Generation is
deterministic templating over the bottleneck context — creativity enters
through the context and the tester, never through skipped fields.
"""
from __future__ import annotations

from evolution.strategy_tree import BRANCH_KINDS, StrategyBranch, StrategyTree


# Per-kind generation stance: how each kind frames the same bottleneck.
_KIND_STANCE = {
    "fastest_path":           ("shortest time-to-proof", "strip every non-essential step"),
    "lowest_capital":         ("smallest cash outlay", "substitute attention and reuse for spend"),
    "maximum_ownership":      ("keep the whole asset", "build in-house; accept slower proof"),
    "maximum_reversibility":  ("every step undoable", "stage-gate each commitment behind a rollback"),
    "maximum_regeneration":   ("leave the system healthier", "route proceeds into restorative assets"),
    "strongest_partnership":  ("borrow capability", "contract with an incumbent under kernel contracts"),
    "acquisition":            ("buy the capability", "acquire a working organ instead of growing it"),
    "incumbent_compatible":   ("fit existing rails", "speak the incumbent's formats and settlement"),
    "radical_simplification": ("delete until it breaks", "remove components until the mechanism is bare"),
    "complete_removal":       ("the bottleneck should not exist", "eliminate the process that creates it"),
    "do_nothing":             ("inaction may be optimal", "hold position; measure the cost of waiting"),
}


class BranchGenerator:
    """Drafts a complete candidate tree for one bottleneck."""

    def generate(self, *, bottleneck: str, objective: str,
                 decisive_unknown: str, metric: str, baseline: float,
                 budget_ceiling_usd: float) -> list[StrategyBranch]:
        branches = []
        for kind in BRANCH_KINDS:
            assumption, mechanism = _KIND_STANCE[kind]
            b = StrategyBranch(
                kind=kind,
                title=f"{kind}: {bottleneck}",
                governing_assumption=f"{assumption} resolves '{bottleneck}'",
                mechanism=f"{mechanism} to move {metric} from baseline {baseline}",
                required_capabilities=[f"execute.{kind}"],
                cost_usd=0.0 if kind == "do_nothing" else min(budget_ceiling_usd, 100.0),
                founder_attention_minutes=0 if kind == "do_nothing" else 15,
                time_to_proof_days=1 if kind == "fastest_path" else 7,
                authority_requirements=["founder_ratification"],
                irreversible_downside="none: candidates are tested in isolation, reversibly",
                expected_result=f"{metric} improves beyond baseline {baseline}",
                strongest_counterargument=f"the {kind} stance may not address '{decisive_unknown}'",
                cheapest_falsification_test=f"isolated run measuring {metric} against {baseline}",
                kill_condition=f"{metric} fails to beat baseline {baseline} or refusal is doctrinal",
            )
            problems = b.validate()
            if problems:                                  # generator invariant: never emit invalid
                raise ValueError(f"generator produced invalid {kind} branch: {problems}")
            branches.append(b)
        return branches

    def propose_tree(self, **kwargs) -> StrategyTree:
        """A full StrategyTree with complete kind coverage."""
        tree = StrategyTree(bottleneck=kwargs["bottleneck"], objective=kwargs["objective"])
        for b in self.generate(**kwargs):
            tree.add(b)
        return tree
