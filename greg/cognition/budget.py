"""Decision-aware bounded cognition inside the existing GREG invocation.

No optional step executes here. Decision value is a provisional range in one
explicit common unit, not entropy, model confidence, authority, or a reward.
The existing ResourceGovernor counts local model attempts; the Kernel remains
responsible for grants and reservations.
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
        self.verification_reserve = max(.01, self.total_seconds * .5)
        self.resources = ResourceGovernor(max_model_calls=1 if family == "semantic" else 0,
                                          max_estimated_cost_usd=self.money_limit)
        self.invoked = False
        self.verification_invoked = False
        self.stop_reason = "smallest sufficient computation; optional cognition has no demonstrated marginal value"

    def remaining(self):
        return max(0.0, self.deadline - time.monotonic())

    def execution_seconds(self):
        requested = self.total_seconds * (.5 if self.family == "semantic" else .45)
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
