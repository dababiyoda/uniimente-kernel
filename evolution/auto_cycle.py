"""Phase 3: the fast capability-evolution cycle.

One machine-run pass: generate all eleven candidate branches, test each
in isolation, analyze every failure, compare against baseline, and hand
the champion to the ClosureLoop for the ledgered, verified decision.

Hard bounds (fail closed):
  - The cycle PROPOSES; only the ClosureLoop disposes. The decision still
    requires a verifier that may authorize promotion — hypothesis-only
    evidence (same-model critique, intrinsic confidence) is refused here,
    before any execution.
  - A structural doctrinal refusal (the same refusal class across
    branches) halts the cycle. The machine never routes around doctrine.
  - When no candidate beats baseline, the cycle records "no_improvement"
    and stops. do_nothing is a valid outcome; manufacturing a winner is not.
"""
from __future__ import annotations

from dataclasses import dataclass

from evolution.branch_generator import BranchGenerator
from evolution.capsule import HYPOTHESIS_ONLY, EvolutionCapsule
from evolution.comparison import Comparison, IsolatedResult, RankedCandidate
from evolution.experiment import ExperimentSpec
from evolution.failure_analysis import FailureReport, analyze
from evolution.loop import ClosureLoop, CycleRefused
from evolution.spider_web import SpiderWebAudit


@dataclass
class AutoCycleReport:
    tree: object
    results: list[IsolatedResult]
    failures: FailureReport
    champion: RankedCandidate | None
    capsule: EvolutionCapsule | None          # None when no improvement was found
    outcome: str                              # "retained" | "regressed" | "killed" | "no_improvement"


class AutoEvolutionCycle:
    def __init__(self, ledger, *, closure_loop: ClosureLoop | None = None):
        self.ledger = ledger
        self.loop = closure_loop or ClosureLoop(ledger)
        self.generator = BranchGenerator()

    def _log(self, kind: str, payload: dict) -> None:
        self.ledger.append("event", {"type": f"auto_cycle.{kind}", **payload})

    def run(self, *, bottleneck: str, objective: str, decisive_unknown: str,
            metric: str, baseline: float, threshold: float, direction: str,
            budget_ceiling_usd: float, audit: SpiderWebAudit,
            isolated_tester,                     # (branch) -> IsolatedResult
            executor,                            # final mediated run for the capsule
            verifier_level: str, verifier_evidence: str,
            workflow: str, rollback_path: str, kill_condition: str) -> AutoCycleReport:
        if verifier_level in HYPOTHESIS_ONLY:
            raise CycleRefused(
                f"verifier level {verifier_level!r} is hypothesis-only; "
                "the fast cycle may not self-authorize")

        # 1. generate: all eleven kinds, complete coverage
        tree = self.generator.propose_tree(
            bottleneck=bottleneck, objective=objective,
            decisive_unknown=decisive_unknown, metric=metric,
            baseline=baseline, budget_ceiling_usd=budget_ceiling_usd)
        self._log("generated", {"tree_id": tree.tree_id, "coverage": tree.coverage()})

        # 2. isolated testing: fresh sandbox per branch, tester injected
        results: list[IsolatedResult] = []
        for branch in tree.branches:
            res = isolated_tester(branch)
            results.append(res)
            self._log("branch_tested", {"branch_id": branch.branch_id, "kind": branch.kind,
                                        "measured": res.measured, "executed": res.executed,
                                        "attempts": len(res.attempts)})

        # 3. failure analysis: every failure classified and kept
        report = analyze(results)
        self._log("failures_analyzed", {"total_failures": report.total_failures,
                                        "by_class": report.by_class,
                                        "structural": report.structural})
        if report.structural and report.dominant_class == "doctrinal_refusal":
            self._log("refused", {"reason": "structural doctrinal refusal; halting"})
            raise CycleRefused(
                "the constitution refused across branches; amend doctrine or stop — "
                "the cycle will not route around it")

        # 4. comparison against baseline
        comp = Comparison(baseline=baseline, threshold=threshold, direction=direction)
        champ = comp.champion(results)
        if champ is None:
            self._log("no_improvement", {"baseline": baseline,
                                         "note": "no candidate beat baseline; do_nothing stands"})
            return AutoCycleReport(tree=tree, results=results, failures=report,
                                   champion=None, capsule=None, outcome="no_improvement")
        self._log("champion", {"branch_id": champ.result.branch_id,
                               "kind": champ.result.kind, "measured": champ.result.measured})

        # 5. improvement proposal -> ClosureLoop decides (ledgered, verified)
        spec = ExperimentSpec(
            decisive_unknown=decisive_unknown,
            hypothesis=f"branch {champ.result.kind} beats baseline on {metric}",
            prediction=f"{metric} reaches {threshold} ({direction})",
            metric=metric, baseline=baseline, threshold=threshold, direction=direction,
            workflow=workflow,
            required_capabilities=[f"execute.{champ.result.kind}"],
            authority_requirements=["founder_ratification"],
            budget_usd=budget_ceiling_usd, reversible=True,
            rollback_path=rollback_path, kill_condition=kill_condition,
            verification=verifier_level)
        capsule = self.loop.run_cycle(
            bottleneck=bottleneck, objective=objective,
            branches=tree.branches, selected_branch_id=champ.result.branch_id,
            decisive_unknown=decisive_unknown, audit=audit, experiment=spec,
            executor=executor, verifier_level=verifier_level,
            verifier_evidence=verifier_evidence,
            decided_by="auto_evolution_cycle",
            notes=f"fast cycle over {len(results)} isolated candidates; "
                  f"{report.total_failures} failures preserved")
        return AutoCycleReport(tree=tree, results=results, failures=report,
                               champion=champ, capsule=capsule,
                               outcome=str(capsule.decision["decision"]))
