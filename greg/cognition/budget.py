"""Decision-aware bounded cognition (directive section 12); mandatory verification is never traded away.

Three controls share one rule: a required step is never priced away, and an optional step runs only when the
budget can hold it.

* ``optional_step`` prices one optional step when its decision value and its total cost are stated in the same
  unit, for a caller that holds such a decision model.
* ``ThinkingBudget`` is one invocation's non-replenishing wall-clock/call plan inside the existing GREG
  invocation (``cortex.reason``, ``bridge.reason_cortex``, ``seed_path``). No optional step executes there:
  advisory proposals are priced with ``optional_step`` as recommendations only. Decision value is a provisional
  range in one explicit common unit, not entropy, model confidence, authority, or a reward. The existing
  ResourceGovernor counts local model attempts; the Kernel remains responsible for grants and reservations.
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
from __future__ import annotations

from datetime import datetime, timezone
import time

from egregore.resources import ResourceGovernor
from .contracts import CognitionError, integer, number

POLICY_VERSION = "seed-thinking-budget/0.1"
REQUIRED_COST_SCOPE = frozenset(("compute", "latency", "attention", "maintenance", "retry", "verification"))
KINDS = frozenset(("calculation", "model", "simulation", "lookup", "founder_attention"))


def _range(interval, *, high=1e12):
    if not isinstance(interval, (list, tuple)) or len(interval) != 2:
        raise CognitionError("ordered finite ranges required")
    for value in interval:
        number(value, low=0, high=high)
    if interval[0] > interval[1]:
        raise CognitionError("ordered finite ranges required")
    return interval

# Below this an inner run cannot solve (45% of its limit) and still verify; the cortex floors the solver at 10 ms.
MIN_STEP_SECONDS = 0.1


def optional_step(*, decision_improvement_range, total_cost_range, remaining_seconds,
                  required_verification_seconds, extra_seconds):
    for interval in (decision_improvement_range, total_cost_range):
        _range(interval)
    for value in (remaining_seconds, required_verification_seconds, extra_seconds):
        number(value, low=0)
    if remaining_seconds < required_verification_seconds:
        return {"continue": False, "reason": "BUDGET_EXHAUSTED: required verification cannot be supported", "outcome": "ABSTAIN"}
    if remaining_seconds < required_verification_seconds + extra_seconds:
        return {"continue": False, "reason": "reserve mandatory verification", "outcome": "CONDITIONAL_RESULT"}
    if decision_improvement_range[0] <= total_cost_range[1]:
        return {"continue": False, "reason": "decision improvement does not robustly justify total cost", "outcome": "STOP"}
    return {"continue": True, "reason": "lower decision value exceeds upper total cost within budget", "outcome": "SMALL_EXPERIMENT"}


def validate_request(request):
    """Validate advisory extra-cognition proposals; no resource or authority override."""
    if request is None:
        return []
    if not isinstance(request, dict) or set(request) != {"optional_steps"}:
        raise CognitionError("thinking_budget accepts only optional_steps; ceilings come from the enclosing invocation")
    steps = request["optional_steps"]
    if not isinstance(steps, list) or len(steps) > 4:
        raise CognitionError("at most four optional cognition proposals")
    allowed = {"id", "kind", "decision_improvement_range", "total_cost_range", "value_unit", "valuation_basis",
               "cost_scope", "extra_seconds", "compute_operations", "money_usd", "attention_seconds", "required_capability"}
    identities = set()
    for step in steps:
        if not isinstance(step, dict) or set(step) - allowed or not {"id", "kind", "extra_seconds", "compute_operations", "money_usd", "attention_seconds", "required_capability"} <= set(step):
            raise CognitionError("invalid optional cognition proposal fields")
        for name in ("id", "required_capability"):
            if not isinstance(step[name], str) or not 1 <= len(step[name]) <= 128:
                raise CognitionError("optional proposal requires bounded identity and capability")
        if step["id"] in identities:
            raise CognitionError("duplicate optional proposal identity")
        identities.add(step["id"])
        if not isinstance(step["kind"], str) or step["kind"] not in KINDS:
            raise CognitionError("unsupported optional cognition kind")
        for name in ("extra_seconds", "attention_seconds"):
            number(step[name], low=0, high=30)
        number(step["money_usd"], low=0)
        integer(step["compute_operations"], low=0, high=100000)
        for name in ("decision_improvement_range", "total_cost_range"):
            if step.get(name) is not None:
                _range(step[name], high=1)
        if step.get("value_unit") not in (None, "normalized_decision_loss"):
            raise CognitionError("decision improvement and total cost require the same normalized decision-loss unit")
        if step.get("valuation_basis") is not None and (not isinstance(step["valuation_basis"], str) or not 1 <= len(step["valuation_basis"]) <= 512):
            raise CognitionError("bounded valuation basis required")
        if step.get("cost_scope") is not None and (not isinstance(step["cost_scope"], list) or
                len(step["cost_scope"]) > 6 or any(name not in REQUIRED_COST_SCOPE for name in step["cost_scope"])):
            raise CognitionError("unknown optional cost scope")
    return steps


def _instant(value):
    if not isinstance(value, str):
        raise CognitionError("deadline requires an offset-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CognitionError("invalid cognition deadline") from exc
    if parsed.tzinfo is None:
        raise CognitionError("deadline requires an offset-aware timestamp")
    return parsed


class ThinkingBudget:
    """One invocation's non-replenishing wall-clock/call plan, never a scheduler.

    Ordinary numeric work retains its 45% share and semantic work its existing
    half-budget timeout. Half the total is reserved for required verification;
    classification consumes slack and can narrow, never increase, execution.
    Optional ranges are evaluated as recommendations only because no extra
    execution edge/contract or grant is supplied by an advisory proposal.
    """
    def __init__(self, geometry, *, family, started, request=None, caller_window=None, shared_deadline=None,
                 shared_compute_limit=None):
        self.started = started
        self.steps = validate_request(request)
        self.family = family
        self.total_seconds = geometry.latency_limit
        self.compute_limit = geometry.compute_limit
        if shared_compute_limit is not None:
            self.compute_limit = min(self.compute_limit, integer(shared_compute_limit, low=0, high=100000))
        self.money_limit = geometry.financial_limit
        self.attention_limit = number(geometry.attention_ceiling_seconds, low=0, high=86400)
        self.window = caller_window
        self.authority_created = False
        self.deadlines = []
        now = datetime.now(timezone.utc)
        if geometry.deadline is not None:
            self.deadlines.append(("requested_deadline", (_instant(geometry.deadline) - now).total_seconds()))
        if caller_window is not None:
            self.total_seconds = min(self.total_seconds, number(caller_window.latency_ceiling_seconds, low=0, high=30))
            self.compute_limit = min(self.compute_limit, integer(caller_window.compute_ceiling_operations, low=0, high=100000))
            self.money_limit = min(self.money_limit, number(caller_window.remaining_money_usd, low=0))
            for name in ("horizon", "grant_expires_at"):
                self.deadlines.append((name, (_instant(getattr(caller_window, name)) - now).total_seconds()))
        self.deadline = started + self.total_seconds
        for _, remaining in self.deadlines:
            self.deadline = min(self.deadline, time.monotonic() + remaining)
        if shared_deadline is not None:
            number(shared_deadline, low=0)
            self.deadline = min(self.deadline, shared_deadline)
        # The cortex route verifies inside its own worker process (adversarial verifier + schema +
        # content address); only the body's receipt check follows, so it reserves a tenth, not half.
        self.verification_reserve = max(.01, self.total_seconds * (.1 if family == "cortex" else .5))
        self.resources = ResourceGovernor(max_model_calls=1 if family == "semantic" else 0,
                                          max_estimated_cost_usd=self.money_limit)
        self.invoked = False
        self.verification_invoked = False
        self.stop_reason = "smallest sufficient computation; optional cognition has no demonstrated marginal value"

    def remaining(self):
        return max(0.0, self.deadline - time.monotonic())

    def execution_seconds(self):
        requested = self.total_seconds * (.5 if self.family == "semantic" else .85 if self.family == "cortex" else .45)
        seconds = min(requested, self.remaining() - self.verification_reserve)
        if seconds < .01 or self.compute_limit < 1:
            self.stop_reason = "BUDGET_EXHAUSTED: cannot reserve required verification and bounded execution"
            raise CognitionError(self.stop_reason)
        return seconds

    def before_execution(self):
        seconds = self.execution_seconds()
        if self.invoked:
            raise CognitionError("BUDGET_EXHAUSTED: single seed computation already attempted")
        self.invoked = True
        return seconds

    def before_model_call(self):
        if self.family != "semantic" or not self.invoked:
            raise CognitionError("model use is outside the declared seed plan")
        self.resources.consume_call(component="cognition.semantic", estimated_cost_usd=0)

    def before_verification(self):
        remaining = self.remaining()
        if remaining < .01:
            self.stop_reason = "BUDGET_EXHAUSTED: required verification cannot be supported"
            raise CognitionError(self.stop_reason)
        self.verification_invoked = True
        return min(30, remaining)

    def optional_recommendations(self, registry=None):
        recommendations = []
        # An additional experiment would itself need mandatory verification.
        # Completion of this seed's check is never a rebate for optional work.
        protected = self.verification_reserve
        for step in self.steps:
            result = {"id": step["id"], "kind": step["kind"], "execute": False, "authority_created": False,
                      "outcome": "STOP", "reason": "missing decision-value/cost estimates or valuation basis",
                      "eligibility": {"catalog_available": None, "task_eligibility": "not_established",
                                      "grant_authorization": "not_established_by_advisory_proposal",
                                      "supported_execution_edge": False},
                      "estimates": {k: step.get(k) for k in ("decision_improvement_range", "total_cost_range", "value_unit", "valuation_basis", "cost_scope")},
                      "resource_request": {k: step[k] for k in ("extra_seconds", "compute_operations", "money_usd", "attention_seconds", "required_capability")}}
            complete = (step.get("decision_improvement_range") is not None and step.get("total_cost_range") is not None and
                        step.get("value_unit") == "normalized_decision_loss" and bool(step.get("valuation_basis")) and
                        set(step.get("cost_scope") or ()) == REQUIRED_COST_SCOPE)
            if any(self.stop_reason.startswith(code + ":") for code in
                   ("POLICY_REFUSAL", "AUTHORITY_REQUIRED", "HUMAN_JUDGMENT_REQUIRED")):
                result["reason"] = "terminal refusal or legitimate human authority path; optional cognition cannot reroute it"
            elif complete:
                decision = optional_step(decision_improvement_range=step["decision_improvement_range"], total_cost_range=step["total_cost_range"],
                                         remaining_seconds=self.remaining(), required_verification_seconds=protected, extra_seconds=step["extra_seconds"])
                result.update({k: decision[k] for k in ("outcome", "reason")})
                if decision["continue"]:
                    if step["money_usd"] > self.money_limit or step["attention_seconds"] > self.attention_limit or step["compute_operations"] > self.compute_limit:
                        result.update(outcome="STOP", reason="optional resource request exceeds an enclosing ceiling")
                    else:
                        available, why = registry.usable(step["required_capability"]) if registry is not None else (False, "no registry projection")
                        result["eligibility"].update(catalog_available=available, availability_reason=why)
                        if not available:
                            result.update(outcome="STOP", reason="CAPABILITY_UNAVAILABLE: optional catalog entry is unavailable; task eligibility is separate")
                        else:
                            result["reason"] += "; recommendation only: catalog availability establishes neither task eligibility nor a grant; a typed bounded experiment and existing authority path are required"
            recommendations.append(result)
        return recommendations

    def snapshot(self, registry=None):
        optional = self.optional_recommendations(registry)
        return {"policy_version": POLICY_VERSION, "total_seconds_ceiling": self.total_seconds,
                "remaining_seconds": self.remaining(), "numeric_execution_fraction": .45,
                "required_verification_reserve_seconds": self.verification_reserve,
                "mandatory_verification_invoked": self.verification_invoked, "seed_attempted": self.invoked,
                "compute_operations_ceiling": self.compute_limit, "money_ceiling_usd": self.money_limit,
                "attention_ceiling_seconds": self.attention_limit,
                "model_calls_attempted": self.resources.used_model_calls,
                "enclosing_limit_source": "canonical_grant_projection" if self.window is not None else "inert_standalone_evaluation; no live grant",
                "authority_refs": {name: getattr(self.window, name) for name in
                                   ("grant_id", "grant_digest", "authority_ref", "mission_id", "scope_digest", "proposal_id", "witness_id", "dispatch_effect_digest")
                                   if getattr(self.window, name) is not None} if self.window else {},
                "optional_steps": optional, "optional_execution_supported": False,
                "optional_compute_remaining": "unmeasured; proposals do not reserve or invoke extra computation",
                "stop_reason": self.stop_reason, "authority_created": False}


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
