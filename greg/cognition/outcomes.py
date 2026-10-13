"""Directive §6 outcomes and reasons, projected from the existing receipt statuses.

`abstention_state` stays the canonical status every existing consumer reads (journal
settlement, cells, metaconsensus, the appraiser). This module only adds the
founder-facing vocabulary on top of it:

    outcome  in ANSWERED_WITHIN_SCOPE | CONDITIONAL_RESULT | ABSTAIN | WAIT |
                REQUEST_EVIDENCE | SMALL_EXPERIMENT | ESCALATE
    reasons  a list of machine-readable codes (REASONS)

`reason()` in cortex.py records the reason code at the branch that decided it, so the
projection never has to guess from free text. A receipt written before this module
existed carries no codes; `project()` then derives the closest codes from its status
and says so (`derived_from_status`).

It also names the capability availability ladder (§5): a catalogued family is not an
installed one, an installed one is not eligible for this task, and none of those is
authorized or externally verified.
"""
from __future__ import annotations

OUTCOMES = ("ANSWERED_WITHIN_SCOPE", "CONDITIONAL_RESULT", "ABSTAIN", "WAIT", "REQUEST_EVIDENCE",
            "SMALL_EXPERIMENT", "ESCALATE")
REASONS = ("UNKNOWN_GEOMETRY", "NO_ELIGIBLE_METHOD", "INSUFFICIENT_EVIDENCE", "WORLD_UNVERIFIED",
           "NON_IDENTIFIABLE", "FORMALIZATION_INCOMPLETE", "MODEL_INVALID", "SOLVER_UNKNOWN", "TIMEOUT",
           "BUDGET_EXHAUSTED", "CONTRADICTION", "OUT_OF_DISTRIBUTION", "HUMAN_JUDGMENT_REQUIRED",
           "AUTHORITY_REQUIRED", "POLICY_REFUSAL", "CAPABILITY_UNAVAILABLE")

# Epistemic classes whose claim is about the supplied model itself. A read-only answer in
# one of these is answered within that scope; every other answer is conditional.
MODEL_SCOPED = ("arithmetic", "deductive", "constraint_feasibility", "optimization")

# Status -> (outcome, default reason codes) for receipts without recorded codes.
_STATUS = {
    "PROHIBITED": ("ABSTAIN", ("POLICY_REFUSAL",)),
    "HUMAN_REVIEW_REQUIRED": ("ESCALATE", ("HUMAN_JUDGMENT_REQUIRED",)),
    "CAPABILITY_DEFICIT": ("ABSTAIN", ("NO_ELIGIBLE_METHOD",)),
    "EVIDENCE_EXPIRED": ("REQUEST_EVIDENCE", ("INSUFFICIENT_EVIDENCE",)),
    "FORMALIZATION_INCOMPLETE": ("REQUEST_EVIDENCE", ("FORMALIZATION_INCOMPLETE",)),
    "REFUTED": ("ABSTAIN", ("CONTRADICTION",)),
    "UNKNOWN": ("ABSTAIN", ("SOLVER_UNKNOWN",)),
    "UNIDENTIFIED": ("SMALL_EXPERIMENT", ("NON_IDENTIFIABLE",)),
    "NO_QUORUM": ("ABSTAIN", ("INSUFFICIENT_EVIDENCE",)),
    "ABSTAIN": ("ABSTAIN", ("INSUFFICIENT_EVIDENCE",)),
    "WORLD_UNVERIFIED": ("CONDITIONAL_RESULT", ("WORLD_UNVERIFIED", "AUTHORITY_REQUIRED")),
}

# Capability availability (§5). Each rung needs its own evidence; none implies the next.
AVAILABILITY = ("catalogued", "installable", "installed", "tested", "available", "eligible_for_task",
                "authorized", "active", "externally_verified")


def outcome_for(status: str, epistemic_class: str, consequential: bool, codes=None, *,
                acquire: bool | None = None, wait: bool = False) -> tuple[str, list[str], bool]:
    """(outcome, reasons, derived_from_status).

    `acquire` is a value-of-information verdict that more evidence is worth its cost;
    `wait` means the decisive evidence is free and due before the decision deadline."""
    unknown = [c for c in codes or () if c not in REASONS]
    if unknown:
        raise ValueError(f"unknown reason codes {unknown}")
    if status == "NONE":
        reasons = list(codes or [])
        if wait:
            return "WAIT", reasons or ["INSUFFICIENT_EVIDENCE"], codes is None
        if acquire:
            return "REQUEST_EVIDENCE", reasons or ["INSUFFICIENT_EVIDENCE"], codes is None
        if epistemic_class in MODEL_SCOPED and not consequential and "OUT_OF_DISTRIBUTION" not in reasons:
            return "ANSWERED_WITHIN_SCOPE", reasons, codes is None
        return "CONDITIONAL_RESULT", reasons or ["WORLD_UNVERIFIED"], codes is None
    outcome, defaults = _STATUS.get(status, ("ABSTAIN", ("INSUFFICIENT_EVIDENCE",)))
    return outcome, list(codes) if codes else list(defaults), codes is None


def project(receipt: dict) -> dict:
    """Founder-facing outcome for a stored receipt of any version."""
    geometry = receipt.get("geometry") or {}
    vector = receipt.get("consequence_vector") or {}
    consequential = (geometry.get("consequence_class", "read_only") != "read_only" or
                     any(isinstance(v, (int, float)) and not isinstance(v, bool) and v >= .5
                         for k, v in vector.items() if k not in ("lawful", "consent")))
    output = receipt.get("output") or {}
    stored = receipt.get("outcome")
    if stored in OUTCOMES:
        return {"outcome": stored, "reasons": list(receipt.get("reasons") or []), "derived_from_status": False}
    outcome, reasons, derived = outcome_for(receipt.get("abstention_state", "ABSTAIN"),
                                            receipt.get("epistemic_class", "semantic"), consequential, None,
                                            acquire=output.get("acquire") if isinstance(output, dict) else None)
    return {"outcome": outcome, "reasons": reasons, "derived_from_status": derived}


def availability(capability_id, manifest, registry, journal=None) -> dict:
    """Each rung of the §5 ladder with its own evidence. Unknown stays unknown."""
    import importlib.metadata
    from pathlib import Path
    from .catalog import FAMILIES
    family = capability_id.removeprefix("cognition.")
    dependency = FAMILIES.get(family, (None,) * 5)[4]
    root = Path(__file__).resolve().parents[2]
    declared = (root / "requirements-cognition.txt").read_text() if (root / "requirements-cognition.txt").exists() else ""
    try:
        installed = dependency is None or bool(importlib.metadata.version(dependency))
    except importlib.metadata.PackageNotFoundError:
        installed = False
    usable, why = registry.usable(capability_id)
    used = None
    if journal is not None:
        used = sum(1 for r in journal.ledger.by_type("receipt")
                   if isinstance(r.payload.get("result", {}).get("output"), dict)
                   and r.payload["result"]["output"].get("method") == capability_id)
    return {
        "catalogued": True,
        "installable": dependency is None or dependency in declared,
        "installed": installed,
        "tested": all((root / t).exists() for t in manifest.tests) if manifest.tests else False,
        "available": usable and installed,
        "eligible_for_task": "decided per request by eligibility; not a property of the capability",
        "authorized": "only inside a founder-signed mission light cone; never by being listed",
        "active": used if used is not None else "unknown without the body journal",
        "externally_verified": False,
        "why_not_available": None if usable and installed else (why if not usable else f"dependency {dependency} not installed"),
    }


def summary(receipt: dict) -> list[str]:
    """Plain words for the founder surfaces (phone, Chromebook, console): no implementation trivia."""
    view = project(receipt)
    output = receipt.get("output")
    lines = [
        f"Problem: {receipt.get('problem_id')} (recognized kind: {receipt.get('epistemic_class', 'unknown').replace('_', ' ')}).",
        f"Method: {receipt.get('method')} ({receipt.get('method_version')})"
        + (f", chosen because {receipt.get('method_selection_reason')}." if receipt.get("method") != "none" else "; nothing eligible ran."),
        f"Outcome: {view['outcome'].replace('_', ' ').lower()}"
        + (f" ({', '.join(r.replace('_', ' ').lower() for r in view['reasons'])})." if view["reasons"] else "."),
    ]
    if output is not None:
        lines.append(f"Answer: {output}")
    verdict = (receipt.get("evaluator_result") or {}).get("verdict")
    if verdict and verdict != "NOT_RUN":
        lines.append(f"Independent check: {verdict.replace('_', ' ').lower()}.")
    if receipt.get("missing_information"):
        lines.append("Still missing: " + "; ".join(receipt["missing_information"]) + ".")
    lines.append(f"Uncertainty: the result holds only for the supplied model; real-world validity is "
                 f"{receipt.get('empirical_validity', 'WORLD_UNVERIFIED').replace('_', ' ').lower()}.")
    lines.append(f"Cost: ${receipt.get('money_cost', 0):.2f}, {receipt.get('latency', 0):.2f}s of local computation.")
    lines.append("Next permitted step: any action on this goes through a signed mission and the Gate; "
                 "this receipt grants nothing.")
    return lines
