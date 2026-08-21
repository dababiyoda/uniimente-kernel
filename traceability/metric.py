"""The Single Bottleneck Metric.

    Percentage of completed goals that remain traceable from founder intent to
    decision, action, evidence, and outcome without unauthorized external effects.

Why this metric and not a dashboard
-----------------------------------
It is one number that cannot be satisfied by any single subsystem. Raising it
requires intelligence (goals actually got done), governance (every effect had a
grant), continuity (the chain survives), and honesty (claims match records) at
the same time. Optimising any one of those alone leaves it flat.

Three refusals are built in, because a metric that cannot report bad news is
decoration:

1.  With zero completed goals the rate is `None`, never 100%. A denominator of
    nothing is not perfection.
2.  A goal counts as traced only if the whole chain resolves AND no unauthorized
    external effect is attributed to it. Partial credit would let a system with a
    strong middle and no ends look healthy.
3.  Unauthorized external effects belonging to no goal still contaminate the
    report. An effect nobody asked for is worse than one traced to a bad goal,
    not better, and per-goal scoring would hide it entirely.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .chain import LINKS, GoalTrace, TraceabilityWalker, UnauthorizedEffect


@dataclass
class MetricReport:
    """The metric, plus everything needed to argue with it."""
    completed_goals: int = 0
    traceable_goals: int = 0
    rate: float | None = None
    refusal: str | None = None
    unauthorized_external_effects: int = 0
    contaminated: bool = False
    false_completions: list[str] = field(default_factory=list)
    broken_link_counts: dict = field(default_factory=dict)
    goals: list[dict] = field(default_factory=list)
    unattributed_effects: list[dict] = field(default_factory=list)
    dangling_link_assertions: list[dict] = field(default_factory=list)

    @property
    def reportable(self) -> bool:
        return self.rate is not None

    def to_dict(self) -> dict:
        return {
            "metric": "single_bottleneck_metric",
            "definition": (
                "percentage of completed goals traceable from founder intent to "
                "decision, action, evidence and outcome with no unauthorized "
                "external effects"),
            "completed_goals": self.completed_goals,
            "traceable_goals": self.traceable_goals,
            "rate": self.rate,
            "refusal": self.refusal,
            "unauthorized_external_effects": self.unauthorized_external_effects,
            "contaminated": self.contaminated,
            "false_completions": self.false_completions,
            "broken_link_counts": self.broken_link_counts,
            "goals": self.goals,
            "unattributed_effects": self.unattributed_effects,
            "dangling_link_assertions": self.dangling_link_assertions,
        }

    def summary(self) -> str:
        if self.rate is None:
            head = f"SBM: NOT REPORTABLE ({self.refusal})"
        else:
            head = (f"SBM: {self.rate:.1f}% "
                    f"({self.traceable_goals}/{self.completed_goals} completed goals traceable)")
        if self.contaminated:
            head += (f"  [CONTAMINATED: {self.unauthorized_external_effects} "
                     "unauthorized external effect(s)]")
        if self.dangling_link_assertions:
            head += (f"  [{len(self.dangling_link_assertions)} link assertion(s) "
                     "naming an action with no receipt]")
        return head


def single_bottleneck_metric(ledger) -> MetricReport:
    """Compute the metric over a ledger. Read-only; grants nothing."""
    walker = TraceabilityWalker(ledger)
    traces: list[GoalTrace] = walker.trace_all()
    completed = [t for t in traces if t.claims_completion]

    unattributed: list[UnauthorizedEffect] = walker.unattributed_effects()
    attributed = sum(len(t.unauthorized_effects) for t in traces)
    total_unauthorized = attributed + len(unattributed)

    report = MetricReport(
        completed_goals=len(completed),
        traceable_goals=sum(1 for t in completed if t.traceable),
        unauthorized_external_effects=total_unauthorized,
        contaminated=total_unauthorized > 0,
        false_completions=[t.goal_id for t in completed if not t.traceable],
        goals=[t.to_dict() for t in traces],
        unattributed_effects=[e.to_dict() for e in unattributed],
        dangling_link_assertions=walker.dangling_link_assertions(),
    )

    counts = {link: 0 for link in LINKS}
    for trace in completed:
        for link in trace.broken_links:
            counts[link] += 1
    report.broken_link_counts = {k: v for k, v in counts.items() if v}

    if not completed:
        # Refusal 1: no denominator, no number.
        report.refusal = (
            "no goal claims completion (no IntentRecord in state 'implemented'); "
            "a rate over an empty denominator would assert governance that has "
            "not been exercised")
        return report

    report.rate = 100.0 * report.traceable_goals / report.completed_goals
    return report
