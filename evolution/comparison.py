"""Phase 3: isolated-test comparison of candidate branches.

Each candidate is tested in isolation (fresh sandbox per branch, tester
injected by the caller — the comparison layer never executes anything
itself). Results are ranked against the baseline and the experiment
threshold. The champion is the cheapest candidate that both resolves
the decisive unknown and beats baseline; ties break toward lower cost,
then toward greater reversibility.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IsolatedResult:
    """One branch's isolated test outcome."""
    branch_id: str
    kind: str
    measured: float                  # external metric value observed
    attempts: list[dict]             # every attempt, success or failure (kept, never deleted)
    cost_usd: float
    duration_days: int
    executed: bool = True            # False if the branch could not even be tested


@dataclass
class RankedCandidate:
    result: IsolatedResult
    resolves_unknown: bool
    beats_baseline: bool
    score: tuple                     # sortable: higher is better


def _directional_beats(measured: float, baseline: float, direction: str) -> bool:
    return measured > baseline if direction == "gte" else measured < baseline


class Comparison:
    """Ranks isolated results; never executes, never deletes."""

    def __init__(self, *, baseline: float, threshold: float, direction: str):
        if direction not in ("gte", "lte"):
            raise ValueError("direction must be 'gte' or 'lte'")
        self.baseline = baseline
        self.threshold = threshold
        self.direction = direction

    def rank(self, results: list[IsolatedResult]) -> list[RankedCandidate]:
        ranked = []
        for r in results:
            resolves = (r.measured >= self.threshold) if self.direction == "gte" \
                else (r.measured <= self.threshold)
            beats = _directional_beats(r.measured, self.baseline, self.direction)
            if self.direction == "gte":
                improvement = r.measured - self.baseline
            else:
                improvement = self.baseline - r.measured
            score = (1 if resolves else 0, 1 if beats else 0,
                     improvement, -r.cost_usd, -r.duration_days)
            ranked.append(RankedCandidate(result=r, resolves_unknown=resolves,
                                          beats_baseline=beats, score=score))
        ranked.sort(key=lambda rc: rc.score, reverse=True)
        return ranked

    def champion(self, results: list[IsolatedResult]) -> RankedCandidate | None:
        """The cheapest candidate that resolves the unknown AND beats baseline.
        None when nothing improves on the status quo — do_nothing wins by default."""
        ranked = self.rank(results)
        for rc in ranked:                                # already best-first
            if rc.resolves_unknown and rc.beats_baseline:
                return rc
        return None
