"""The pipeline model for the institutional shell.

Doctrine (SHELL): this module composes reporters. It cannot act.

Specified by `docs/INSTITUTIONAL_SHELL_SPEC.md`. Two structural choices carry
the whole safety argument, and both are properties of the types rather than
promises in a docstring:

1. **A stage callable takes zero arguments.** There is therefore no parameter
   through which a caller could hand a stage a target, a path, a payload or a
   destination. A reporter that cannot be pointed at anything cannot be turned
   into an actuator by its caller.
2. **Stages do not pass values to one another.** There is no shared mutable
   context, so one stage cannot corrupt a later stage's reading and any stage
   produces the same answer alone as it does in sequence.

A stage that raises is reported as FAILED with the exception text; the pipeline
continues. A stage that cannot determine its answer reports UNRESOLVED with the
reason. Neither becomes a default, a zero, or silence — an operator surface
that hides a broken reporter manufactures confidence, which is worse than
having no operator surface at all.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class ShellError(ValueError):
    """A pipeline was declared in a shape the shell refuses. Fails closed."""


class Outcome(str, Enum):
    """How a stage ended. Ordered worst-last for exit-code selection."""

    OK = "OK"
    UNRESOLVED = "UNRESOLVED"   # the reporter ran and could not determine an answer
    FAILED = "FAILED"           # the reporter raised


_SEVERITY: dict[Outcome, int] = {Outcome.OK: 0, Outcome.UNRESOLVED: 1, Outcome.FAILED: 2}


@dataclass(frozen=True)
class StageResult:
    """One reporter's answer. Carries no institutional authority of any kind."""

    name: str
    outcome: Outcome
    headline: str
    detail: tuple[str, ...] = ()

    @property
    def severity(self) -> int:
        return _SEVERITY[self.outcome]


def ok(name: str, headline: str, detail: tuple[str, ...] = ()) -> StageResult:
    return StageResult(name, Outcome.OK, headline, detail)


def unresolved(name: str, reason: str, detail: tuple[str, ...] = ()) -> StageResult:
    return StageResult(name, Outcome.UNRESOLVED, reason, detail)


@dataclass(frozen=True)
class Stage:
    """A named, zero-argument reporter.

    The zero-argument requirement is enforced at construction rather than
    documented, because it is the property that keeps a reporter from becoming
    a target-accepting action.
    """

    name: str
    reporter: Callable[[], StageResult]
    reads: str = ""     # plain-language note on what this stage reads

    def __post_init__(self) -> None:
        if not callable(self.reporter):
            raise ShellError(f"stage {self.name!r} reporter is not callable")
        params = [
            p for p in inspect.signature(self.reporter).parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
        ]
        if params:
            raise ShellError(
                f"stage {self.name!r} takes required argument(s) "
                f"{[p.name for p in params]}; a shell stage must take none, so it "
                "cannot be handed a target"
            )

    def collect(self) -> StageResult:
        """Run the reporter, converting any failure into a reported result."""
        try:
            result = self.reporter()
        except Exception as exc:                      # noqa: BLE001 - deliberate
            return StageResult(self.name, Outcome.FAILED,
                               f"{type(exc).__name__}: {exc}")
        if not isinstance(result, StageResult):
            return StageResult(self.name, Outcome.FAILED,
                               f"reporter returned {type(result).__name__}, "
                               "not a StageResult")
        return result


@dataclass(frozen=True)
class Pipeline:
    """A named, ordered composition of stages. Declared as data, never built
    from caller input, so the set of things the shell can do is fixed at import
    and readable in one file."""

    name: str
    purpose: str
    stages: tuple[Stage, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.stages:
            raise ShellError(f"pipeline {self.name!r} declares no stages")
        names = [s.name for s in self.stages]
        if len(names) != len(set(names)):
            raise ShellError(f"pipeline {self.name!r} has duplicate stage names")


@dataclass(frozen=True)
class PipelineReport:
    pipeline: str
    purpose: str
    results: tuple[StageResult, ...]

    @property
    def worst(self) -> Outcome:
        return max((r.outcome for r in self.results), key=lambda o: _SEVERITY[o])

    @property
    def exit_code(self) -> int:
        """0 clean, 1 something unresolved, 2 a reporter failed."""
        return _SEVERITY[self.worst]

    def counts(self) -> dict[str, int]:
        out = {o.value: 0 for o in Outcome}
        for r in self.results:
            out[r.outcome.value] += 1
        return out


def report(pipeline: Pipeline) -> PipelineReport:
    """Collect every stage in declaration order.

    Named `report` rather than `run` or `execute` on purpose: the shell produces
    a reading of institutional state and has no other effect. Every stage is
    collected even when an earlier one failed, because a partial picture with a
    named hole is more useful than a truncated one.
    """
    return PipelineReport(
        pipeline=pipeline.name,
        purpose=pipeline.purpose,
        results=tuple(stage.collect() for stage in pipeline.stages),
    )
