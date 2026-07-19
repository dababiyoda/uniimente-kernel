"""Phase 3: failure analysis across isolated candidate tests.

Doctrine (EVOLUTION + PROVENANCE): failure is evidence. Every failed
attempt is classified, counted, and preserved — the report names the
dominant failure class and the cheapest fix direction, and it never
deletes or summarises-away a failure. A class that repeats across
branches signals a structural (not branch-local) problem.
"""
from __future__ import annotations

from dataclasses import dataclass, field

FAILURE_CLASSES = (
    "transient",                 # retry-worthy infrastructure noise
    "doctrinal_refusal",         # the constitution refused the attempt — do not route around
    "capability_missing",        # the organ lacks a required capability
    "budget_exceeded",           # cost ceiling hit
    "verifier_insufficient",     # evidence below the required verifier level
    "executor_error",            # the adapter/executor itself failed
)

_FIX_DIRECTION = {
    "transient": "retry with backoff; if it persists, reclassify as executor_error",
    "doctrinal_refusal": "stop: amend doctrine through the amendment pipeline or drop the branch",
    "capability_missing": "build or contract the named capability, then re-test",
    "budget_exceeded": "narrow the experiment scope or raise the ceiling via founder ratification",
    "verifier_insufficient": "escalate the verifier level; never promote on weak evidence",
    "executor_error": "repair the adapter against its contract tests, then re-run",
}


@dataclass
class FailureReport:
    total_attempts: int
    total_failures: int
    by_class: dict[str, int]
    dominant_class: str | None
    recommended_fix: str | None
    structural: bool               # True when one class spans multiple branches
    failures: list[dict]           # the raw failure records, preserved verbatim


def classify(attempt: dict) -> str:
    """Map one failed attempt to its class. Explicit class wins; else infer."""
    explicit = attempt.get("failure_class")
    if explicit in FAILURE_CLASSES:
        return explicit
    err = str(attempt.get("error", "")).lower()
    if "refused" in err or "deny" in err or "prohibited" in err:
        return "doctrinal_refusal"
    if "budget" in err or "cost" in err:
        return "budget_exceeded"
    if "verifier" in err or "evidence" in err:
        return "verifier_insufficient"
    if "timeout" in err or "connection" in err:
        return "transient"
    if "capability" in err or "grant" in err:
        return "capability_missing"
    return "executor_error"


def analyze(results) -> FailureReport:
    """Analyze IsolatedResult list (or any objects with .attempts/.branch_id)."""
    failures: list[dict] = []
    branch_count = len(results)
    for r in results:
        for a in r.attempts:
            if a.get("ok", False):
                continue
            failures.append({**a, "branch_id": r.branch_id, "kind": getattr(r, "kind", None),
                             "failure_class": classify(a)})
    by_class: dict[str, int] = {}
    class_branches: dict[str, set] = {}
    for f in failures:
        by_class[f["failure_class"]] = by_class.get(f["failure_class"], 0) + 1
        class_branches.setdefault(f["failure_class"], set()).add(f["branch_id"])
    dominant = max(by_class, key=by_class.get) if by_class else None
    structural = bool(dominant and len(class_branches[dominant]) > 1 and branch_count > 1)
    return FailureReport(
        total_attempts=sum(len(r.attempts) for r in results),
        total_failures=len(failures),
        by_class=by_class,
        dominant_class=dominant,
        recommended_fix=_FIX_DIRECTION.get(dominant) if dominant else None,
        structural=structural,
        failures=failures)
