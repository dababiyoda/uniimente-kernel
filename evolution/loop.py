"""ClosureLoop: one complete, machine-recorded improvement cycle.

The recursive self-improvement loop, exactly:

    bottleneck -> materially different branches -> branch selection
    -> Spider-Web audit (must be COMPLETE) -> decisive unknown
    -> smallest reversible experiment -> execution -> measurement
    -> strongest-available verification -> comparison vs baseline
    -> Retain / Regress / Kill -> Evolution Capsule on the ledger
    -> whole-body closure evaluation of the change itself

The system's opinion of itself is never sufficient proof: the verifier
level is declared, and levels 6-7 (same-model critique, intrinsic
confidence) cannot authorize a retain decision.
"""
from __future__ import annotations

from typing import Callable

from closure.whole_body import WholeBodyClosureController, Loop, LoopEvidence
from evolution.capsule import (EvolutionCapsule, VerifierRecord,
                               RetainRegressKill, RetainRegressKillDecision)
from evolution.experiment import ExperimentSpec, ExperimentCompiler
from evolution.spider_web import SpiderWebAudit
from evolution.strategy_tree import StrategyTree, StrategyBranch
from provenance.ledger import EvidenceLedger


class CycleRefused(ValueError):
    """The cycle cannot proceed; it fails closed with named reasons."""


class ClosureLoop:
    def __init__(self, ledger: EvidenceLedger):
        self.ledger = ledger
        self.compiler = ExperimentCompiler()
        self.whole_body = WholeBodyClosureController()

    def run_cycle(self, *,
                  bottleneck: str,
                  objective: str,
                  branches: list[StrategyBranch],
                  selected_branch_id: str,
                  decisive_unknown: str,
                  audit: SpiderWebAudit,
                  experiment: ExperimentSpec,
                  executor: Callable[[ExperimentSpec], tuple[float, str]],
                  verifier_level: str,
                  verifier_evidence: str,
                  decided_by: str = "closure_loop",
                  notes: str = "") -> EvolutionCapsule:
        # 1. strategic loop: materially different routes; losers preserved
        tree = StrategyTree(bottleneck=bottleneck, objective=objective)
        for b in branches:
            tree.add(b)
        tree.select(selected_branch_id, decisive_unknown=decisive_unknown,
                    reason="best expected verified value per unit of founder attention")
        self.ledger.append("event", {"type": "evolution.tree_selected",
                                     "tree": tree.to_dict()})

        # 2. architectural loop: spider-web audit must be COMPLETE
        removed = audit.remove_decorative()
        if audit.verdict != "COMPLETE":
            self.ledger.append("event", {"type": "evolution.audit_failed",
                                         "audit": audit.to_dict()})
            raise CycleRefused(f"spider-web audit incomplete: failed sides={audit.sides_failed}, "
                               f"missing={audit.missing_completeness}")
        self.ledger.append("event", {"type": "evolution.audit_complete",
                                     "decorative_removed": removed})

        # 3. compile the smallest reversible experiment
        try:
            spec = self.compiler.compile(experiment)
        except ValueError as e:
            self.ledger.append("event", {"type": "evolution.experiment_refused", "error": str(e)})
            raise CycleRefused(str(e))

        # 4-5. execute + measure (external consequence, not self-report)
        measured, outcome_class = executor(spec)
        self.ledger.append("event", {"type": "evolution.experiment_measured",
                                     "experiment_id": spec.experiment_id,
                                     "measured": measured, "outcome_class": outcome_class})

        # 6. verify with the strongest available verifier
        verifier = VerifierRecord(level=verifier_level, evidence=verifier_evidence,
                                  decided_by=decided_by)
        problems = verifier.validate()
        if problems:
            raise CycleRefused(f"verifier invalid: {problems}")

        # 7. compare against baseline; decide
        beats = spec.resolves(measured)
        if outcome_class == "harm":
            decision = RetainRegressKill.KILL
            reason = "experiment produced harm; kill and repair"
        elif beats:
            decision = RetainRegressKill.RETAIN
            reason = (f"measured {measured} resolves the decisive unknown vs baseline "
                      f"{spec.baseline} (threshold {spec.threshold} {spec.direction})")
        else:
            decision = RetainRegressKill.REGRESS
            reason = (f"measured {measured} did not beat baseline {spec.baseline}; "
                      "roll back via the experiment's rollback path")
        rrk = RetainRegressKillDecision(decision=decision, reason=reason,
                                        decided_by=decided_by, verifier=verifier)
        problems = rrk.validate()
        if problems:
            raise CycleRefused(f"decision invalid: {problems}")

        # 8. capsule: preserved forever, including failures
        from dataclasses import asdict
        capsule = EvolutionCapsule(
            bottleneck=bottleneck, tree=tree.to_dict(), audit=audit.to_dict(),
            experiment=spec.to_dict(), measured_value=measured,
            outcome_class=outcome_class, verifier=asdict(verifier),
            decision=asdict(rrk), beats_baseline=beats, notes=notes)
        self.ledger.append("capsule", capsule.to_dict())

        # 9. whole-body evaluation of the change itself (meta-improvement loop)
        wb = self.whole_body.applicable(
            f"cycle:{capsule.capsule_id}",
            {Loop.STRATEGIC: LoopEvidence(True, True, "tree with rejected branches preserved"),
             Loop.ARCHITECTURAL: LoopEvidence(True, True, "spider-web audit COMPLETE"),
             Loop.EXECUTION: LoopEvidence(True, outcome_class == "positive",
                                          f"measured={measured} class={outcome_class}"),
             Loop.REGENERATIVE: LoopEvidence(True, outcome_class != "harm",
                                             "no harm outcome" if outcome_class != "harm" else "HARM"),
             Loop.META_IMPROVEMENT: LoopEvidence(True, True, "capsule recorded on ledger")},
            applicable={Loop.STRATEGIC, Loop.ARCHITECTURAL, Loop.EXECUTION,
                        Loop.REGENERATIVE, Loop.META_IMPROVEMENT})
        self.ledger.append("event", {"type": "evolution.whole_body",
                                     "capsule_id": capsule.capsule_id,
                                     "evaluation": wb.to_dict()})
        return capsule
