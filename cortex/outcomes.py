"""The directive's explicit outcome taxonomy, mapped from existing states (directive section 6).

Outcomes: ANSWERED_WITHIN_SCOPE, CONDITIONAL_RESULT, ABSTAIN, WAIT,
REQUEST_EVIDENCE, SMALL_EXPERIMENT, ESCALATE.

Reasons: UNKNOWN_GEOMETRY, NO_ELIGIBLE_METHOD, INSUFFICIENT_EVIDENCE,
WORLD_UNVERIFIED, NON_IDENTIFIABLE, FORMALIZATION_INCOMPLETE, MODEL_INVALID,
SOLVER_UNKNOWN, TIMEOUT, BUDGET_EXHAUSTED, CONTRADICTION, OUT_OF_DISTRIBUTION,
HUMAN_JUDGMENT_REQUIRED, AUTHORITY_REQUIRED, POLICY_REFUSAL,
CAPABILITY_UNAVAILABLE.

"Map these into existing project statuses. Do not let a new taxonomy break
consumers." The existing cortex states and dispositions, and GREG's
AbstentionClass, stay the system of record; this module is a pure, total,
deterministic projection over them, so every consumer keeps working and every
receipt also carries the directive's vocabulary.
"""
from __future__ import annotations

OUTCOMES = ("ANSWERED_WITHIN_SCOPE", "CONDITIONAL_RESULT", "ABSTAIN", "WAIT", "REQUEST_EVIDENCE",
            "SMALL_EXPERIMENT", "ESCALATE")
REASONS = ("UNKNOWN_GEOMETRY", "NO_ELIGIBLE_METHOD", "INSUFFICIENT_EVIDENCE", "WORLD_UNVERIFIED",
           "NON_IDENTIFIABLE", "FORMALIZATION_INCOMPLETE", "MODEL_INVALID", "SOLVER_UNKNOWN", "TIMEOUT",
           "BUDGET_EXHAUSTED", "CONTRADICTION", "OUT_OF_DISTRIBUTION", "HUMAN_JUDGMENT_REQUIRED",
           "AUTHORITY_REQUIRED", "POLICY_REFUSAL", "CAPABILITY_UNAVAILABLE")
VERSION = "directive-outcomes/0.1"

# cortex state -> reasons it implies
_STATE_REASONS = {
    "OK": (),
    "WORLD_UNVERIFIED": ("WORLD_UNVERIFIED",),
    "NOT_IDENTIFIED": ("NON_IDENTIFIABLE",),
    "INSUFFICIENT_EVIDENCE": ("INSUFFICIENT_EVIDENCE",),
    "FORMALIZATION_INCOMPLETE": ("FORMALIZATION_INCOMPLETE",),
    "DEPENDENCY_UNAVAILABLE": ("CAPABILITY_UNAVAILABLE",),
    "TIMEOUT": ("TIMEOUT", "SOLVER_UNKNOWN"),
    "INCONCLUSIVE": ("SOLVER_UNKNOWN",),
    "BUDGET_EXHAUSTED": ("BUDGET_EXHAUSTED",),
    "CONTESTED": ("CONTRADICTION",),
    "MALFORMED_INPUT": ("MODEL_INVALID",),
    "DIMENSION_MISMATCH": ("MODEL_INVALID",),
    "UNSUPPORTED_GEOMETRY": ("UNKNOWN_GEOMETRY",),
    "NO_ELIGIBLE_METHOD": ("NO_ELIGIBLE_METHOD",),
    "GATE_FAILED": ("POLICY_REFUSAL",),
    "GATE_UNRESOLVED": ("AUTHORITY_REQUIRED",),
    "REQUIRES_HUMAN_AUTHORITY": ("HUMAN_JUDGMENT_REQUIRED",),
}


def classify_cortex(state: str, disposition: str, *, answer_present: bool, verifier_blocking: bool = False,
                    consequence_handoff: bool = False, refused_interventions: bool = False) -> dict:
    """Directive outcome for one cortex receipt."""
    reasons = list(_STATE_REASONS.get(state, ("SOLVER_UNKNOWN",)))
    if verifier_blocking:
        reasons.append("CONTRADICTION")
    if consequence_handoff:
        reasons.append("AUTHORITY_REQUIRED")
    if refused_interventions:
        reasons.append("POLICY_REFUSAL")
    if disposition == "recommend":
        outcome = "ANSWERED_WITHIN_SCOPE"
    elif disposition == "handoff":
        outcome = "ESCALATE"
    elif disposition == "bounded_test":
        outcome = "CONDITIONAL_RESULT" if answer_present else "SMALL_EXPERIMENT"
    elif state == "BUDGET_EXHAUSTED":
        outcome = "WAIT"
    elif state == "INSUFFICIENT_EVIDENCE":
        outcome = "REQUEST_EVIDENCE"
    elif answer_present and state == "INCONCLUSIVE":
        outcome = "CONDITIONAL_RESULT"   # e.g. FEASIBLE but not proven OPTIMAL
    else:
        outcome = "ABSTAIN"
    return {"outcome": outcome, "reasons": list(dict.fromkeys(reasons)), "taxonomy": VERSION}


# GREG CognitiveReceipt.abstention_state (greg/cognition/contracts.py AbstentionClass) -> (outcome, reasons)
_GREG = {
    "NONE": ("ANSWERED_WITHIN_SCOPE", ()),
    "ABSTAIN": ("ABSTAIN", ()),
    "PROHIBITED": ("ABSTAIN", ("POLICY_REFUSAL",)),
    "HUMAN_REVIEW_REQUIRED": ("ESCALATE", ("HUMAN_JUDGMENT_REQUIRED",)),
    "CAPABILITY_DEFICIT": ("ABSTAIN", ("CAPABILITY_UNAVAILABLE",)),
    "EVIDENCE_EXPIRED": ("REQUEST_EVIDENCE", ("INSUFFICIENT_EVIDENCE",)),
    "FORMALIZATION_INCOMPLETE": ("ABSTAIN", ("FORMALIZATION_INCOMPLETE",)),
    "WORLD_UNVERIFIED": ("CONDITIONAL_RESULT", ("WORLD_UNVERIFIED",)),
    "REFUTED": ("ABSTAIN", ("CONTRADICTION",)),
    "UNKNOWN": ("ABSTAIN", ("SOLVER_UNKNOWN",)),
    "UNIDENTIFIED": ("SMALL_EXPERIMENT", ("NON_IDENTIFIABLE",)),
    "NO_QUORUM": ("ABSTAIN", ("INSUFFICIENT_EVIDENCE",)),
}


def classify_greg(abstention_state: str, *, has_output: bool) -> dict:
    outcome, reasons = _GREG.get(abstention_state, ("ABSTAIN", ("SOLVER_UNKNOWN",)))
    if abstention_state == "UNKNOWN" and has_output:
        outcome = "CONDITIONAL_RESULT"
    return {"outcome": outcome, "reasons": list(reasons), "taxonomy": VERSION}
