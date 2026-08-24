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
from typing import ClassVar


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
    #: The author's honest forecast that this experiment succeeds, 0..1.
    #:
    #: Optional, and `None` is a real answer meaning "not forecast" — never
    #: coerced to a number. Added 2026-08-24 because `prediction` above is prose
    #: ("the sandbox run records a value") and nothing on this spec was a
    #: probability, so Bridge C had nothing to put in the witness field
    #: CONTRADICTION-0003 created and `predicted_versus_realized` reads. The
    #: calibration join gated on a forecast that no committing path supplied.
    #:
    #: Deliberately NOT derived. Nothing here can compute how likely an
    #: experiment is to succeed, and a derived number would be the fabricated
    #: field `adapters/` forbids — the same reason Bridge B makes the caller
    #: state its own threshold. A low value is legitimate and expected: for a
    #: novel experiment, uncertainty is often the reason it exists.
    #:
    #: Governs nothing. `policy.engine.evaluate` never reads it, and admission
    #: is decided by `evidence_confidence` alone. This is the number reality
    #: later grades, not the number that buys entry.
    predicted_success_probability: float | None = None

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
        # Absent is fine and means "not forecast". Present-and-nonsensical is
        # not: a forecast outside 0..1 would reach the calibration join and be
        # scored as if it meant something.
        if self.predicted_success_probability is not None and not (
                0.0 <= self.predicted_success_probability <= 1.0):
            problems.append("predicted_success_probability must be within 0..1")
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

    #: Fields dropped from `to_dict()` when unset, so that adding one cannot
    #: move a hash computed before it existed. See `to_dict`.
    _OPTIONAL: ClassVar[frozenset[str]] = frozenset({"predicted_success_probability"})

    def to_dict(self) -> dict:
        """Serialise, omitting unset optional fields rather than emitting null.

        This is not a style choice. `evolution/repair/spec.py` and
        `evolution/migration/spec.py` both embed a literal `ExperimentSpec` in
        their frozen tables as `EXPERIMENT.to_dict()`, so this dict is inside
        two sealed historical hashes. A plain `asdict` meant that **adding any
        field to this dataclass silently moved both seals** — the type could not
        evolve without breaking a record of what a past experiment was.

        Found 2026-08-24 by adding `predicted_success_probability` and watching
        six sealed-experiment tests fail. The seals were right to fail: the
        bytes they cover really had changed.

        The remedy is the one already ratified here for Witness v2, which had
        the identical problem — absent v2 fields are dropped from the signed
        payload rather than written as null, so every historical signature
        still verifies. Same technique, same reason. A spec that sets no
        forecast serialises exactly as it did before the field existed, and
        both seals sit where they always sat: **no historical hash was updated
        to make current implementation pass**, which is what
        FOUNDER-RULING-2026-08-23 forbids.

        A spec that *does* set a forecast serialises it, and any hash taken over
        that spec is a new hash over a genuinely different experiment.
        """
        payload = asdict(self)
        return {key: value for key, value in payload.items()
                if not (value is None and key in self._OPTIONAL)}


class ExperimentCompiler:
    """Compiles a decisive unknown into an ExperimentSpec. Refuses hopes."""

    def compile(self, spec: ExperimentSpec) -> ExperimentSpec:
        problems = spec.validate()
        if problems:
            raise ValueError(f"experiment does not compile: {problems}")
        return spec
