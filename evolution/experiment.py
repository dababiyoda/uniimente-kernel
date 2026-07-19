"""Experiment Compiler: decisive unknown -> smallest reversible experiment.

Doctrine: identify the decisive unknown controlling each decision; design
the smallest reversible experiment capable of resolving it; compile the
experiment into workflows, capabilities, authority, budgets, tests,
verification, rollback, and kill conditions.

An experiment that is not reversible, not falsifiable, or not budgeted is
not an experiment — it is a hope. The compiler refuses to emit those.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict


@dataclass
class ExperimentSpec:
    """The smallest reversible experiment resolving one decisive unknown."""
    decisive_unknown: str
    hypothesis: str
    prediction: str                 # what we expect, measurably
    metric: str                     # the external measure that decides
    baseline: float                 # current value of the metric
    threshold: float                # value that resolves the unknown
    direction: str                  # "gte" | "lte" — which way beats baseline
    workflow: str                   # the compiled workflow name
    required_capabilities: list[str]
    authority_requirements: list[str]
    budget_usd: float
    reversible: bool
    rollback_path: str
    kill_condition: str
    verification: str               # which verifier level decides (see capsule.VERIFIER_LEVELS)
    experiment_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def validate(self) -> list[str]:
        problems = []
        for f in ("decisive_unknown", "hypothesis", "prediction", "metric",
                  "workflow", "rollback_path", "kill_condition", "verification"):
            if not getattr(self, f):
                problems.append(f"missing {f}")
        if not self.reversible:
            problems.append("experiment must be reversible")
        if self.budget_usd < 0:
            problems.append("budget may not be negative")
        if self.direction not in ("gte", "lte"):
            problems.append("direction must be 'gte' or 'lte'")
        if self.direction == "gte" and self.threshold <= self.baseline:
            problems.append("gte threshold must exceed baseline")
        if self.direction == "lte" and self.threshold >= self.baseline:
            problems.append("lte threshold must be below baseline")
        if not self.required_capabilities:
            problems.append("experiment must name required capabilities")
        return problems

    def resolves(self, measured: float) -> bool:
        """Did the measured external value resolve the decisive unknown?"""
        if self.direction == "gte":
            return measured >= self.threshold
        return measured <= self.threshold

    def to_dict(self) -> dict:
        return asdict(self)


class ExperimentCompiler:
    """Compiles a decisive unknown into an ExperimentSpec. Refuses hopes."""

    def compile(self, spec: ExperimentSpec) -> ExperimentSpec:
        problems = spec.validate()
        if problems:
            raise ValueError(f"experiment does not compile: {problems}")
        return spec
