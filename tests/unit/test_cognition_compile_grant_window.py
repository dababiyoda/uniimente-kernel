"""Fourth review of the Track B merge (COG-5, present in both parents): the compile and chain routes carry the
caller's canonical grant window into every inner run.

Before, ``cortex.reason`` dropped ``caller_window`` on the compile and chain branches. A compile under an
expired grant still ran its solver and verifier, a compile under a live grant was labelled an inert standalone
evaluation, and the window's latency ceiling did not bound the decision.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import time

import pytest

from greg.capabilities import InvocationBudgetWindow
from greg.cognition import compiler, composition
from greg.cognition.cortex import reason, registry_view
from greg.cognition.solvers import exact


def window(**over):
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    values = dict(horizon=future, grant_expires_at=future, remaining_money_usd=0,
                  authority_ref="test-pointer", grant_id="test-grant")
    return InvocationBudgetWindow(**{**values, **over})


def expired():
    past = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    return window(horizon=past, grant_expires_at=past)


@pytest.fixture(autouse=True)
def no_index(tmp_path, monkeypatch):
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")


@pytest.fixture
def mechanism_calls(monkeypatch):
    calls = []

    def numeric(family, data, geometry):
        calls.append("compute")
        return exact(data, asdict(geometry))

    def check(family, data, answer, proof_class, geometry):
        calls.append("verify")
        return {"verdict": "STRUCTURALLY_VERIFIED", "dissent": [], "execution_contract": "test fixture"}

    monkeypatch.setattr("greg.cognition.cortex._numeric", numeric)
    monkeypatch.setattr("greg.cognition.cortex.independent_verify", check)
    return calls


def compile_request():
    return {"problem_id": "c", "compile": {"geometry": {}, "data": {"expression": "2+3"}}}


def test_without_a_window_the_compile_answers_as_a_standalone_evaluation(mechanism_calls):
    r = reason(compile_request(), registry=registry_view())
    assert r["state"] == "ANSWERED" and mechanism_calls == ["compute", "verify"]
    assert r["selected_receipt"]["authority_refs"]["live_grant"] is False
    assert "window" not in r["resource_use"]["budget"]


def test_an_expired_grant_runs_no_mechanism_on_the_compile_route(mechanism_calls):
    r = reason(compile_request(), registry=registry_view(), caller_window=expired())
    assert mechanism_calls == []
    assert r["state"] == "ABSTAIN" and any("BUDGET_EXHAUSTED" in a for a in r["abstentions"])
    assert r["resource_use"]["budget"]["total_source"] == "the caller's grant window"


def test_a_live_grant_is_named_on_the_compiled_answer_and_bounds_the_decision(mechanism_calls):
    # 15 s: binding below the 20 s default, and room for a cold process (the compile's own preparation is timed too)
    r = reason(compile_request(), registry=registry_view(), caller_window=window(latency_ceiling_seconds=15))
    assert r["state"] == "ANSWERED", r["abstentions"]
    refs = r["selected_receipt"]["authority_refs"]
    assert refs["live_grant"] is True and refs["scope"] == "canonical_Kernel_dispatch"
    budget = r["resource_use"]["budget"]
    assert budget["total_s"] <= 15 and budget["window"]["bounds"]["latency_ceiling"] == 15
    assert budget["total_source"] == "the caller's grant window"


def test_a_passed_shared_deadline_bounds_the_compile_decision(mechanism_calls):
    r = reason(compile_request(), registry=registry_view(), shared_deadline=time.monotonic() - 1)
    assert mechanism_calls == [] and r["state"] == "ABSTAIN"


def test_the_chain_route_carries_the_window_into_every_stage(monkeypatch):
    seen = []

    def recorder(params, *, registry, journal=None, model_config=None, **window_kwargs):
        seen.append(window_kwargs)
        return {"receipt_id": "r", "method": "m", "abstention_state": "BUDGET_EXHAUSTED", "output": None,
                "latency": 0.0}

    monkeypatch.setattr("greg.cognition.cortex.reason", recorder)
    w = window(latency_ceiling_seconds=2)
    out = composition.run({"problem_id": "chain", "chain": {"question": "pilot?", "payload": {
        "beta_evidence": {"successes": 3, "failures": 1}, "pilot_option": {"cost": 1},
        "decision_model": {"customers": 10, "value_per_success": 1, "fixed_cost": 1}}}},
        registry=registry_view(), caller_window=w)
    assert out["state"] == "STAGE_ABSTAINED" and seen
    assert all(k["caller_window"] is w and k["shared_deadline"] <= time.monotonic() + 2 for k in seen)
