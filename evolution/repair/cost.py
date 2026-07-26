"""Adapter 4 of 4 — the repair-cost meter.

Measures what a repair actually cost, using the weights frozen in
`spec.REPAIR_COST_WEIGHTS` before any candidate existed. Every term is read
from source or from the clock; none is a judgement call.

    new_source_lines          non-blank, non-comment lines in the candidate
    new_module_dependencies   top-level imports the original did not need
    decision_points           if / for / while / except / ternary / comp-if
    runtime_ms                median wall time over the measurement corpus
    rollback_steps            operations to return to the original path

UNITS ARE REPAIR POINTS, NOT DOLLARS. This package spends $0.00. Nothing here
should ever be read as money, which is why the field is not called `cost_usd`
and why the value is never passed into a field that means currency.

Restoring the original is expected to dominate this meter, and that is the
correct answer rather than an embarrassment: re-enabling working code is
genuinely cheaper than writing new code. The meter exists to make that
comparison numeric, not to flatter the replacements.
"""
from __future__ import annotations

import ast
import statistics
import time
from dataclasses import asdict, dataclass

from evolution.repair.spec import REPAIR_COST_WEIGHTS, SECONDARY_ORDER_TERMS

#: Counted as one decision each. A branch, a loop, a handler, or a filtered
#: comprehension all represent a place the implementation chooses.
_DECISION_NODES = (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.IfExp,
                   ast.Try, ast.Match)


def _docstring_line_numbers(tree: ast.AST) -> set[int]:
    """Every physical line occupied by a docstring.

    Computed from AST line spans rather than by subtracting a docstring's own
    line count from the total. Subtraction is off by however many lines inside
    the docstring were blank — it silently over-charges terse code and
    under-charges verbose code. The span is exact.
    """
    occupied: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                and isinstance(first.value.value, str):
            end = first.value.end_lineno or first.value.lineno
            occupied.update(range(first.value.lineno, end + 1))
    return occupied


def _source_metrics(source: str) -> tuple[int, int, set[str]]:
    """(effective lines, decision points, top-level module names) for one file."""
    tree = ast.parse(source)

    # Docstrings are documentation, not implementation. Charging for them would
    # penalise a candidate for explaining itself, which is exactly backwards.
    doc_lines = _docstring_line_numbers(tree)

    lines = 0
    for number, raw in enumerate(source.splitlines(), start=1):
        stripped = raw.strip()
        if stripped and not stripped.startswith("#") and number not in doc_lines:
            lines += 1

    decisions = 0
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, _DECISION_NODES):
            decisions += 1
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp,
                               ast.GeneratorExp)):
            decisions += sum(len(gen.ifs) for gen in node.generators)
        elif isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                imports.add(node.module.split(".")[0])

    return lines, decisions, imports


@dataclass(frozen=True)
class RepairCost:
    candidate_id: str
    new_source_lines: int
    new_module_dependencies: int
    decision_points: int
    runtime_ms: float
    rollback_steps: int
    repair_cost: float

    def to_dict(self) -> dict:
        d = asdict(self)
        d["units"] = "repair_points"
        d["usd"] = 0.0
        return d

    def secondary_key(self) -> tuple:
        """The frozen tie-break, lower-is-better on every term. Applied ONLY
        among candidates that tie on the primary function metric."""
        return tuple(getattr(self, term) for term in SECONDARY_ORDER_TERMS)


class RepairCostMeter:
    """Scores one candidate against the frozen weights."""

    def __init__(self, baseline_imports: set[str]):
        #: The original's own import set. Anything a candidate imports beyond
        #: this is a dependency the repair introduced.
        self.baseline_imports = set(baseline_imports)

    @classmethod
    def from_original_sources(cls, sources: list[str]) -> "RepairCostMeter":
        imports: set[str] = set()
        for src in sources:
            imports |= _source_metrics(src)[2]
        return cls(imports)

    def measure(self, *, candidate_id: str, sources: list[str],
                runner, rollback_steps: int, repeats: int = 5) -> RepairCost:
        """Measure source terms statically and runtime by executing `runner`.

        `runner` is called `repeats` times and must be side-effect free; the
        median is taken so one scheduling hiccup cannot decide a ranking.
        """
        lines = decisions = 0
        imports: set[str] = set()
        for src in sources:
            l, d, i = _source_metrics(src)
            lines += l
            decisions += d
            imports |= i

        new_deps = imports - self.baseline_imports
        # A candidate importing the shared interface is not paying for a new
        # dependency — every candidate uses it, so it cannot discriminate.
        new_deps -= {"evolution"}

        samples = []
        for _ in range(max(repeats, 1)):
            start = time.perf_counter()
            runner()
            samples.append((time.perf_counter() - start) * 1000.0)
        runtime_ms = round(statistics.median(samples), 4)

        terms = {"new_source_lines": lines,
                 "new_module_dependencies": len(new_deps),
                 "decision_points": decisions,
                 "runtime_ms": runtime_ms,
                 "rollback_steps": rollback_steps}
        total = round(sum(REPAIR_COST_WEIGHTS[k] * v for k, v in terms.items()), 4)

        return RepairCost(candidate_id=candidate_id, repair_cost=total, **terms)
