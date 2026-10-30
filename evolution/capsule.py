"""Evolution Capsule: the machine-recorded improvement cycle.

Every improvement attempt is preserved: the bottleneck, the tree, the
audit, the experiment, what happened, which verifier decided, and the
Retain/Regress/Kill decision. Successes, failures, contradictions,
incidents, and corrections all enter causal institutional memory.

Verifier discipline (doctrine, strongest first):
    1. formal_proof            - deterministic invariant
    2. external_outcome        - independently observable external result
    3. cryptographic_receipt   - verified external receipt
    4. qualified_human_review  - expert review
    5. independent_model_review
    6. same_model_critique     - hypotheses only; may not authorize promotion
    7. intrinsic_confidence    - hypotheses only; may not authorize promotion

Levels 6 and 7 generate hypotheses. They may NEVER independently
authorize institutional promotion.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

VERIFIER_LEVELS = (
    "formal_proof", "external_outcome", "cryptographic_receipt",
    "qualified_human_review", "independent_model_review",
    "same_model_critique", "intrinsic_confidence",
)
HYPOTHESIS_ONLY = ("same_model_critique", "intrinsic_confidence")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class VerifierRecord:
    """Which verifier judged the result, at what strength."""
    level: str                    # one of VERIFIER_LEVELS
    evidence: str                 # what the verifier observed
    decided_by: str               # who/what ran the verification
    decided_at: str = field(default_factory=_now)

    def validate(self) -> list[str]:
        problems = []
        if self.level not in VERIFIER_LEVELS:
            problems.append(f"unknown verifier level {self.level!r}")
        if not self.evidence:
            problems.append("verifier record must name its evidence")
        return problems

    @property
    def may_authorize_promotion(self) -> bool:
        return self.level not in HYPOTHESIS_ONLY


class RetainRegressKill(str):
    RETAIN = "retain"
    REGRESS = "regress"
    KILL = "kill"


@dataclass
class RetainRegressKillDecision:
    decision: str                 # retain | regress | kill
    reason: str
    decided_by: str
    verifier: VerifierRecord
    decided_at: str = field(default_factory=_now)

    def validate(self) -> list[str]:
        problems = []
        if self.decision not in (RetainRegressKill.RETAIN, RetainRegressKill.REGRESS, RetainRegressKill.KILL):
            problems.append(f"decision must be retain|regress|kill, got {self.decision!r}")
        if not self.reason:
            problems.append("decision must carry a reason")
        problems.extend(self.verifier.validate())
        # Retain is a promotion decision: hypothesis-only verifiers cannot make it.
        if self.decision == RetainRegressKill.RETAIN and not self.verifier.may_authorize_promotion:
            problems.append(f"verifier level {self.verifier.level} may not authorize retain "
                            "(hypothesis-only levels 6-7 cannot promote)")
        return problems


@dataclass
class EvolutionCapsule:
    """One complete, machine-recorded improvement cycle."""
    bottleneck: str
    tree: dict                    # StrategyTree.to_dict()
    audit: dict                   # SpiderWebAudit.to_dict()
    experiment: dict              # ExperimentSpec.to_dict()
    measured_value: float | None
    outcome_class: str            # positive | negative | zero_response | inconclusive | harm
    verifier: dict                # VerifierRecord as dict
    decision: dict                # RetainRegressKillDecision as dict
    beats_baseline: bool | None
    notes: str = ""
    capsule_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return asdict(self)
