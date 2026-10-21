"""Decision-aware optional cognition; mandatory verification is never traded away."""
from .contracts import CognitionError, number


def optional_step(*, decision_improvement_range, total_cost_range, remaining_seconds,
                  required_verification_seconds, extra_seconds):
    for interval in (decision_improvement_range, total_cost_range):
        if len(interval) != 2 or any(number(x, low=0) != x for x in interval) or interval[0] > interval[1]:
            raise CognitionError("ordered finite ranges required")
    for value in (remaining_seconds, required_verification_seconds, extra_seconds):
        number(value, low=0)
    if remaining_seconds < required_verification_seconds:
        return {"continue": False, "reason": "BUDGET_EXHAUSTED: required verification cannot be supported", "outcome": "ABSTAIN"}
    if remaining_seconds < required_verification_seconds + extra_seconds:
        return {"continue": False, "reason": "reserve mandatory verification", "outcome": "CONDITIONAL_RESULT"}
    if decision_improvement_range[0] <= total_cost_range[1]:
        return {"continue": False, "reason": "decision improvement does not robustly justify total cost", "outcome": "STOP"}
    return {"continue": True, "reason": "lower decision value exceeds upper total cost within budget", "outcome": "SMALL_EXPERIMENT"}
