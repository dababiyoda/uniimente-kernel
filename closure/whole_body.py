"""Whole-Body Closure Controller.

Doctrine (mission): do not judge completion through one metric. Every
major component must close every applicable independent loop:

    1.  REALITY           external signal -> verified evidence -> updated state
    2.  EPISTEMIC         evidence -> competing interpretations -> calibrated belief
    3.  STRATEGIC         objective -> different routes -> decisive unknown -> test
    4.  ARCHITECTURAL     route -> Spider-Web audit -> eligibility/routing/proof/
                          settlement/governance/continuity
    5.  AUTHORITY         intent -> identity -> legal principal -> policy ->
                          approval -> capability -> expiration/revocation
    6.  EXECUTION         authorized action -> fingerprint -> Commit Witness ->
                          one-time execution -> receipt -> reconciliation
    7.  COMMERCIAL        problem -> buyer -> offer -> payment -> delivery ->
                          customer outcome -> retention/termination
    8.  DISTRIBUTION      narrative -> qualified attention -> owned relationship ->
                          useful action -> measured value
    9.  AUTONOMY          supervised work -> verified competence -> bounded
                          promotion -> monitoring -> regression/renewal
    10. REGENERATIVE      value created -> burden measured -> debt repaired ->
                          capacity increased
    11. CAPITAL           surplus -> obligations -> reserves -> reinvestment ->
                          assets -> distributions
    12. CONTINUITY        failure/absence -> degraded mode -> recovery ->
                          root cause -> stronger control
    13. META_IMPROVEMENT  improvement attempt -> outcome -> diagnosis of the
                          improvement method -> better search/testing/routing

The controller evaluates each proposed change as:
    CLOSED            - loop closed with external consequence
    PARTIALLY_CLOSED  - loop started, external consequence incomplete
    FALSELY_CLOSED    - internal metric satisfied WITHOUT the intended
                        external consequence (triggers investigation + regression)
    OPEN              - loop not meaningfully started

A component is not complete because its code runs. A business is not
complete because it launches. Require external consequence and
whole-body closure.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum


class Loop(str, Enum):
    REALITY = "reality"
    EPISTEMIC = "epistemic"
    STRATEGIC = "strategic"
    ARCHITECTURAL = "architectural"
    AUTHORITY = "authority"
    EXECUTION = "execution"
    COMMERCIAL = "commercial"
    DISTRIBUTION = "distribution"
    AUTONOMY = "autonomy"
    REGENERATIVE = "regenerative"
    CAPITAL = "capital"
    CONTINUITY = "continuity"
    META_IMPROVEMENT = "meta_improvement"


class Verdict(str, Enum):
    CLOSED = "CLOSED"
    PARTIALLY_CLOSED = "PARTIALLY_CLOSED"
    FALSELY_CLOSED = "FALSELY_CLOSED"
    OPEN = "OPEN"


@dataclass
class LoopEvidence:
    """Evidence for one loop for one proposed change.

    internal_ok: the internal metric/step ran (code ran, impressions rose,
                 tasks completed, coverage increased, model self-rated higher).
    external_ok: the intended EXTERNAL consequence is independently
                 observable (owned relationships grew, bypasses closed,
                 reconciliation passed, external performance improved).
    detail: human-readable account.
    """
    internal_ok: bool
    external_ok: bool
    detail: str = ""


@dataclass
class ChangeEvaluation:
    change_id: str
    verdicts: dict[str, str]
    overall: str
    falsely_closed: list[str]
    open_loops: list[str]
    required_actions: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


# Canonical false-closure signatures from doctrine. Internal metric up,
# external consequence flat. The controller names them explicitly.
FALSE_CLOSURE_SIGNATURES = (
    "impressions increased but owned relationships did not",
    "code coverage increased but bypasses remained",
    "revenue increased but founder intervention became worse",
    "agents completed tasks but reconciliation failed",
    "a model rated itself higher but external performance did not improve",
)


def evaluate_loop(ev: LoopEvidence | None) -> Verdict:
    if ev is None or (not ev.internal_ok and not ev.external_ok):
        return Verdict.OPEN
    if ev.external_ok:
        # External consequence observed; internal state may or may not
        # have moved, but reality did. That is closure.
        return Verdict.CLOSED if ev.internal_ok else Verdict.PARTIALLY_CLOSED
    # internal ran, external flat: the dangerous case
    return Verdict.FALSELY_CLOSED if ev.internal_ok else Verdict.OPEN


class WholeBodyClosureController:
    """Evaluates proposed changes across all applicable loops."""

    def evaluate(self, change_id: str, loops: dict[Loop, LoopEvidence | None]) -> ChangeEvaluation:
        verdicts: dict[str, str] = {}
        falsely: list[str] = []
        open_loops: list[str] = []
        for loop in Loop:
            v = evaluate_loop(loops.get(loop))
            verdicts[loop.value] = v.value
            if v == Verdict.FALSELY_CLOSED:
                falsely.append(loop.value)
            elif v in (Verdict.OPEN, Verdict.PARTIALLY_CLOSED):
                open_loops.append(loop.value)

        required: list[str] = []
        if falsely:
            # False closure must trigger investigation and regression.
            required += ["investigate_false_closure", "regress_change"]
        if open_loops:
            required.append("close_open_loops_before_promotion")
        if not falsely and not open_loops:
            overall = Verdict.CLOSED.value
        elif falsely:
            overall = Verdict.FALSELY_CLOSED.value
        else:
            overall = Verdict.PARTIALLY_CLOSED.value

        return ChangeEvaluation(
            change_id=change_id, verdicts=verdicts, overall=overall,
            falsely_closed=falsely, open_loops=open_loops, required_actions=required)

    def applicable(self, change_id: str, loops: dict[Loop, LoopEvidence | None],
                   applicable: set[Loop]) -> ChangeEvaluation:
        """Evaluate only the loops applicable to this component; the rest are
        reported OPEN-by-omission and do not block."""
        full: dict[Loop, LoopEvidence | None] = {loop: None for loop in Loop}
        for loop, ev in loops.items():
            full[loop] = ev
        result = self.evaluate(change_id, full)
        # loops not applicable are excluded from the blocking set
        result.open_loops = [l for l in result.open_loops if Loop(l) in applicable]
        if not result.falsely_closed and not result.open_loops:
            result.overall = Verdict.CLOSED.value
            result.required_actions = []
        elif not result.falsely_closed:
            result.overall = Verdict.PARTIALLY_CLOSED.value
        return result
