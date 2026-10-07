"""Decision-aware stopping is invoked by the canonical bounded cognition path."""
from dataclasses import FrozenInstanceError, asdict
from datetime import datetime, timedelta, timezone

import pytest

from greg.capabilities import BUILTINS, InvocationBudgetWindow, InvocationContext
from greg.cognition.budget import REQUIRED_COST_SCOPE, ThinkingBudget, validate_request
from greg.cognition.contracts import CognitionError, ProblemGeometry
from greg.cognition.cortex import compile_problem, compose, reason, registry_view, solve
from greg.cognition.solvers import exact


def request(**over):
    return {"problem_id": "budget:sum", "operation": "calculate", "data": {"expression": "2+3"}, **over}


def window(**over):
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    values = dict(horizon=future, grant_expires_at=future, remaining_money_usd=0,
                  authority_ref="test-pointer", grant_id="test-grant")
    return InvocationBudgetWindow(**{**values, **over})


def proposal(**over):
    return {"id": "cheapest-measurement", "kind": "calculation", "extra_seconds": .01,
            "compute_operations": 1, "money_usd": 0, "attention_seconds": 0,
            "required_capability": "cognition.exact", "decision_improvement_range": [.4, .6],
            "total_cost_range": [.1, .2], "value_unit": "normalized_decision_loss",
            "valuation_basis": "provisional declared decision-loss/cost normalization; not a measured benefit",
            "cost_scope": sorted(REQUIRED_COST_SCOPE), **over}


@pytest.fixture
def bounded_functions(monkeypatch):
    calls = []

    def numeric(family, data, geometry):
        calls.append(("compute", geometry))
        return exact(data, asdict(geometry))

    def check(family, data, answer, proof_class, geometry):
        calls.append(("verify", geometry))
        return {"verdict": "STRUCTURALLY_VERIFIED", "dissent": [], "execution_contract": "test fixture; not an independent worker"}

    monkeypatch.setattr("greg.cognition.cortex._numeric", numeric)
    monkeypatch.setattr("greg.cognition.cortex.independent_verify", check)
    return calls


def test_mandatory_reserve_stops_before_any_mechanism(bounded_functions):
    receipt = reason(request(geometry={"latency_limit": .01}), registry=registry_view())
    assert bounded_functions == []
    assert receipt["reason_code"] == "BUDGET_EXHAUSTED" and receipt["output"] is None
    plan = receipt["compute_cost"]["budget_plan"]
    assert plan["seed_attempted"] is False and plan["mandatory_verification_invoked"] is False
    assert "required verification" in receipt["stopping_reason"]


def test_numeric_default_share_and_required_check_are_preserved(bounded_functions):
    receipt = reason(request(), registry=registry_view())
    assert [name for name, _ in bounded_functions] == ["compute", "verify"]
    assert bounded_functions[0][1].latency_limit == 2.25
    assert receipt["geometry"]["latency_limit"] == 5
    assert receipt["compute_cost"]["budget_plan"]["required_verification_reserve_seconds"] == 2.5
    assert receipt["compute_cost"]["budget_plan"]["mandatory_verification_invoked"] is True
    assert receipt["authority_refs"]["live_grant"] is False
    assert "no live grant" in receipt["compute_cost"]["budget_plan"]["enclosing_limit_source"]


@pytest.mark.parametrize("mutation", [
    {"decision_improvement_range": None}, {"total_cost_range": None}, {"valuation_basis": None},
    {"value_unit": None}, {"cost_scope": ["compute"]},
    {"decision_improvement_range": [0, 0]},
    {"decision_improvement_range": [.1, .4], "total_cost_range": [.2, .3]},
    {"total_cost_range": [.7, .8]},
])
def test_missing_irrelevant_uncertain_or_expensive_optional_cognition_stops(mutation, bounded_functions):
    receipt = reason(request(thinking_budget={"optional_steps": [proposal(**mutation)]}), registry=registry_view())
    step = receipt["compute_cost"]["budget_plan"]["optional_steps"][0]
    assert step["outcome"] == "STOP" and step["execute"] is False
    assert [name for name, _ in bounded_functions] == ["compute", "verify"]
    assert receipt["output"]["exact"] == "5" and receipt["authority_created"] is False


@pytest.mark.parametrize("mutation", [
    {"money_usd": .01}, {"attention_seconds": .01}, {"compute_operations": 10001},
    {"extra_seconds": 30},
])
def test_optional_proposal_cannot_expand_any_enclosing_resource_or_method(mutation, bounded_functions):
    receipt = reason(request(thinking_budget={"optional_steps": [proposal(**mutation)]}), registry=registry_view())
    step = receipt["compute_cost"]["budget_plan"]["optional_steps"][0]
    assert step["outcome"] in ("STOP", "CONDITIONAL_RESULT") and step["execute"] is False
    assert len(bounded_functions) == 2 and receipt["money_cost"] == 0


def test_valuable_proposal_remains_a_typed_experiment_recommendation(bounded_functions):
    receipt = reason(request(thinking_budget={"optional_steps": [proposal()]}), registry=registry_view())
    step = receipt["compute_cost"]["budget_plan"]["optional_steps"][0]
    assert step["outcome"] == "SMALL_EXPERIMENT" and step["execute"] is False
    assert "existing authority" in step["reason"] and step["authority_created"] is False
    assert step["eligibility"]["catalog_available"] is True
    assert step["eligibility"]["task_eligibility"] == "not_established"
    assert step["eligibility"]["supported_execution_edge"] is False
    assert len(bounded_functions) == 2 and receipt["outcome"]["outcome"] == "ANSWERED_WITHIN_SCOPE"


def test_detached_optional_capability_is_not_reactivated(bounded_functions):
    registry = registry_view()
    registry.set_state("cognition.collective", "DETACHED")
    receipt = reason(request(thinking_budget={"optional_steps": [proposal(required_capability="cognition.collective")]}),
                     registry=registry)
    step = receipt["compute_cost"]["budget_plan"]["optional_steps"][0]
    assert step["outcome"] == "STOP" and step["execute"] is False
    assert step["eligibility"]["catalog_available"] is False
    assert len(bounded_functions) == 2


def test_receipt_budget_fields_do_not_weaken_integrity_or_accept_unknown_fields(bounded_functions):
    from greg.cognition.contracts import digest
    from greg.cognition.settlement import _valid_receipt
    receipt = reason(request(), registry=registry_view())
    assert _valid_receipt(receipt)
    receipt["authority_refs"]["new_authority"] = True
    receipt["receipt_id"] = digest({k: v for k, v in receipt.items() if k != "receipt_id"})
    assert not _valid_receipt(receipt)
    receipt["authority_refs"]["new_authority"] = False
    receipt["unknown_budget_override"] = 100
    receipt["receipt_id"] = digest({k: v for k, v in receipt.items() if k != "receipt_id"})
    assert not _valid_receipt(receipt)


def test_expired_requested_deadline_or_grant_projection_cannot_invoke(bounded_functions):
    old = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    for kwargs in ({"params": request(geometry={"deadline": old})},
                   {"params": request(), "caller_window": window(horizon=old)}):
        params = kwargs.pop("params")
        receipt = reason(params, registry=registry_view(), **kwargs)
        assert receipt["reason_code"] == "BUDGET_EXHAUSTED" and receipt["output"] is None
    assert bounded_functions == []


def test_context_limits_narrow_serving_without_rewriting_signed_geometry(bounded_functions):
    ceiling = window(latency_ceiling_seconds=1, compute_ceiling_operations=7)
    receipt = reason(request(), registry=registry_view(), caller_window=ceiling)
    assert receipt["geometry"]["latency_limit"] == 5 and receipt["geometry"]["compute_limit"] == 10000
    assert bounded_functions[0][1].latency_limit == .45 and bounded_functions[0][1].compute_limit == 7
    plan = receipt["compute_cost"]["budget_plan"]
    assert plan["total_seconds_ceiling"] == 1 and plan["compute_operations_ceiling"] == 7
    assert receipt["authority_refs"]["grant_id"] == "test-grant"
    with pytest.raises(FrozenInstanceError):
        ceiling.remaining_money_usd = 100


def test_caller_cannot_supply_or_mutate_authority_projection():
    for field in ("caller_window", "cognition_budget", "authority_refs", "grant_id"):
        with pytest.raises(CognitionError):
            compile_problem(request(**{field: {"money": 100}}))
    with pytest.raises(CognitionError, match="ceilings"):
        compile_problem(request(thinking_budget={"optional_steps": [], "latency_limit": 30}))


@pytest.mark.parametrize("mutation", [{"decision_improvement_range": [1, 0]}, {"total_cost_range": [0, float("nan")]},
                                       {"value_unit": "entropy"}, {"money_usd": -1}, {"compute_operations": True}])
def test_malformed_values_and_entropy_proxy_are_rejected(mutation):
    with pytest.raises(CognitionError):
        validate_request({"optional_steps": [proposal(**mutation)]})


def test_existing_model_call_governor_counts_attempts_and_prevents_retries(monkeypatch):
    import time
    budget = ThinkingBudget(ProblemGeometry(epistemic_class="semantic"), family="semantic", started=time.monotonic())
    budget.before_execution(); budget.before_model_call()
    assert budget.snapshot()["model_calls_attempted"] == 1
    from egregore.resources import ResourceExhausted
    with pytest.raises(ResourceExhausted):
        budget.before_model_call()
    with pytest.raises(CognitionError, match="already attempted"):
        budget.before_execution()


def test_missing_local_model_consumes_no_model_call():
    receipt = reason({"problem_id": "budget:no-model", "operation": "interpret", "data": {"sources": []}},
                     registry=registry_view())
    assert receipt["reason_code"] == "CAPABILITY_UNAVAILABLE"
    assert receipt["compute_cost"]["model_calls"] == 0


def test_terminal_refusal_at_deadline_remains_refusal_without_retry(monkeypatch):
    from greg.models import Refusal
    clock, attempts = [1000.0], []
    monkeypatch.setattr("greg.cognition.cortex.time.monotonic", lambda: clock[0])

    class RefusingLocalRoute:
        def __init__(self, config):
            self.model = config.model

        def complete(self, *args, **kwargs):
            attempts.append("local call")
            clock[0] += 6
            raise Refusal("fixture policy refusal")

    monkeypatch.setattr("egregore.local_model.LocalModelClient", RefusingLocalRoute)
    receipt = reason({"problem_id": "budget:refusal", "operation": "interpret", "data": {"sources": []},
                      "thinking_budget": {"optional_steps": [proposal()]}},
                     registry=registry_view(), model_config={"order": ["ollama"], "ollama_model": "fixture"})
    assert attempts == ["local call"] and receipt["reason_code"] == "POLICY_REFUSAL"
    assert receipt["outcome"]["outcome"] == "ABSTAIN" and receipt["output"] is None
    assert receipt["compute_cost"]["model_calls"] == 1
    step = receipt["compute_cost"]["budget_plan"]["optional_steps"][0]
    assert step["outcome"] == "STOP" and "cannot reroute" in step["reason"]


def test_composition_child_cannot_widen_context_and_parent_deadline(tmp_path, bounded_functions, monkeypatch):
    manifest = BUILTINS["cognition.compose"][0]
    ctx = InvocationContext(workspace=tmp_path, read_roots=(), secrets=None, manifest=manifest,
                            target="cognition:budget", capability_registry=registry_view(),
                            cognition_budget=window(latency_ceiling_seconds=1, compute_ceiling_operations=7))
    receipt = compose({"requests": [request(geometry={"latency_limit": 30, "compute_limit": 100000})]}, ctx)["receipts"][0]
    assert receipt["geometry"]["latency_limit"] == 30 and receipt["geometry"]["compute_limit"] == 100000
    assert bounded_functions[0][1].latency_limit == .45 and bounded_functions[0][1].compute_limit == 7
    assert receipt["compute_cost"]["budget_plan"]["total_seconds_ceiling"] == 1


def test_shared_deadline_exhaustion_blocks_later_child_before_computation(bounded_functions):
    import time
    receipt = reason(request(), registry=registry_view(), shared_deadline=time.monotonic() - 1)
    assert bounded_functions == [] and receipt["reason_code"] == "BUDGET_EXHAUSTED"


def test_composition_declared_compute_allocations_never_refund_or_widen_parent(tmp_path, bounded_functions):
    ctx = InvocationContext(workspace=tmp_path, read_roots=(), secrets=None, manifest=BUILTINS["cognition.compose"][0],
                            target="cognition:budget", capability_registry=registry_view(),
                            cognition_budget=window(compute_ceiling_operations=7))
    receipts = compose({"requests": [request(), request(problem_id="budget:second")]}, ctx)["receipts"]
    assert receipts[0]["compute_cost"]["budget_plan"]["compute_operations_ceiling"] == 7
    assert receipts[1]["compute_cost"]["budget_plan"]["compute_operations_ceiling"] == 0
    assert receipts[1]["reason_code"] == "BUDGET_EXHAUSTED" and receipts[1]["output"] is None
    assert [kind for kind, _ in bounded_functions] == ["compute", "verify"]


def test_composition_latency_is_one_shared_parent_ceiling(tmp_path, monkeypatch):
    clock, calls = [1000.0], []
    monkeypatch.setattr("greg.cognition.cortex.time.monotonic", lambda: clock[0])

    def numeric(family, data, geometry):
        calls.append("compute"); clock[0] += .4
        return exact(data, asdict(geometry))

    def check(*args):
        calls.append("verify"); clock[0] += .3
        return {"verdict": "STRUCTURALLY_VERIFIED", "dissent": []}

    monkeypatch.setattr("greg.cognition.cortex._numeric", numeric)
    monkeypatch.setattr("greg.cognition.cortex.independent_verify", check)
    ctx = InvocationContext(workspace=tmp_path, read_roots=(), secrets=None, manifest=BUILTINS["cognition.compose"][0],
                            target="cognition:budget", capability_registry=registry_view(),
                            cognition_budget=window(latency_ceiling_seconds=1))
    receipts = compose({"requests": [request(), request(problem_id="budget:later")]}, ctx)["receipts"]
    assert receipts[0]["output"]["exact"] == "5"
    assert receipts[1]["reason_code"] == "BUDGET_EXHAUSTED" and receipts[1]["output"] is None
    assert calls == ["compute", "verify"] and clock[0] < 1001
