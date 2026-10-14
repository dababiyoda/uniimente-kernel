"""Decision-aware cognitive expenditure (directive section 12); mandatory verification is never traded away.

Two controls share one rule: a required step is never priced away, and an optional step runs only when the
budget can hold it.

* ``optional_step`` prices one optional step when its decision value and its total cost are stated in the same
  unit, for a caller that holds such a decision model.
* ``Controller`` is the thinking budget of one compiled decision. Every inner run on the compile path (the
  answer, the premises check, each sensitivity re-run) draws on one total budget, the requester's declared
  ``latency_budget``. Each inner run reserves its own mandatory verification, because the cortex gives the
  solver 45% of a run's limit and the verifier the rest.
  - Required steps are never value-gated. When the budget cannot hold even a minimal step, the step is
    refused with BUDGET_EXHAUSTED and the caller returns a narrower result.
  - An optional step runs only when the tail of the measured step costs (the slowest step so far, not the
    mean) fits in what remains. The requester's budget is the stated value of the decision, so nothing beyond
    it is spent on any optional step.
  - Every decision, run or stop, is kept with its reason, its remaining budget and the measured cost range.
"""
import time

from .contracts import CognitionError, number

# Below this an inner run cannot solve (45% of its limit) and still verify; the cortex floors the solver at 10 ms.
MIN_STEP_SECONDS = 0.1


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


class Controller:
    """One bounded thinking budget for one decision, with a ledger of every spend and every stop."""

    RULE = ("one total budget per decision; required steps are never value-gated and stop only below the minimum "
            "step; an optional step runs only when the slowest measured step fits in the remaining budget")

    def __init__(self, total_seconds, *, declared=True, step_ceiling_seconds=30.0, clock=time.monotonic):
        self.total = float(number(total_seconds, low=0))
        self.ceiling = float(number(step_ceiling_seconds, low=MIN_STEP_SECONDS))
        self.declared, self.clock = declared, clock
        self.started = clock()
        self.ledger, self.costs, self.cpu = [], [], []
        self._open = None

    def remaining(self) -> float:
        return max(0.0, self.total - (self.clock() - self.started))

    def cost_range(self):
        """[fastest, slowest] measured step, in seconds; ``None`` before any step has been measured."""
        return [round(min(self.costs), 4), round(max(self.costs), 4)] if self.costs else None

    def allot(self, step: str, *, required: bool):
        """The latency limit this step may use, or ``None`` with the stop reason recorded."""
        if self._open is not None:
            raise CognitionError(f"step {self._open['step']} was allotted and never closed")
        remaining, cost = self.remaining(), self.cost_range()
        entry = {"step": step, "required": required, "remaining_s": round(remaining, 4), "cost_range_s": cost}
        if remaining < MIN_STEP_SECONDS:
            reason = (f"BUDGET_EXHAUSTED: {remaining:.3g}s left, below the {MIN_STEP_SECONDS}s minimum step that can "
                      "still solve and verify")
        elif not required and cost is not None and cost[1] > remaining:
            reason = (f"STOP: the slowest measured step ({cost[1]:.3g}s) exceeds the remaining budget "
                      f"({remaining:.3g}s); an optional step is not started without room to finish")
        else:
            limit = min(self.ceiling, remaining)
            self._open = {**entry, "decision": "RUN", "limit_s": round(limit, 4), "_at": self.clock()}
            return limit
        self.ledger.append({**entry, "decision": "STOP", "reason": reason})
        return None

    def done(self, step: str, *, cpu_seconds=None):
        """Close the allotted step: its measured wall time becomes cost evidence for the next decision."""
        if self._open is None or self._open["step"] != step:
            raise CognitionError(f"step {step} was not allotted")
        entry = self._open
        self._open = None
        spent = max(0.0, self.clock() - entry.pop("_at"))
        self.costs.append(spent)
        entry["spent_s"] = round(spent, 4)
        if isinstance(cpu_seconds, (int, float)) and not isinstance(cpu_seconds, bool):
            self.cpu.append(float(cpu_seconds))
            entry["cpu_s"] = round(float(cpu_seconds), 4)
        self.ledger.append(entry)

    def stops(self) -> list:
        return [e for e in self.ledger if e["decision"] == "STOP"]

    def summary(self) -> dict:
        costs = sorted(self.costs)
        return {"rule": self.RULE, "total_s": round(self.total, 4),
                "total_source": "declared latency_budget" if self.declared else "default (no latency_budget declared)",
                "spent_s": round(self.clock() - self.started, 4), "remaining_s": round(self.remaining(), 4),
                "steps": list(self.ledger),
                "measured_step_s": {"count": len(costs), "p50": round(costs[len(costs) // 2], 4) if costs else None,
                                    "max": round(costs[-1], 4) if costs else None,
                                    "note": "wall time per inner run, solver and verifier included"},
                "cpu_s": round(sum(self.cpu), 4) if self.cpu else None,
                "stopped": [{"step": e["step"], "reason": e["reason"]} for e in self.stops()],
                "unmeasured": ["peak memory per run", "energy"]}
