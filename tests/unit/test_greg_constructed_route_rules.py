"""Fourth review of the Track B merge (COG-1, COG-2, COG-3): a construction answering inside the Competency
Compiler meets the rules every other compile route meets.

* Under high consequence a construction (optimisation-class) needs a complete formal model and returns a
  conditional result, never ANSWERED.
* Its call is a required step on the decision's one thinking budget: refused below the minimum step, measured,
  and recorded.
* The sensitivity operator, when it applies, re-runs the construction on perturbed inputs.
* The geometry the inputs imply counts the constructions that fit them.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from greg.cognition import compiler
from greg.cognition.cortex import registry_view

CID = "composed.assignment.staffing.t"
DATA = {"workers": [{"id": "Ana", "skills": ["a"], "capacity": 2}, {"id": "Bo", "skills": ["a"], "capacity": 3}],
        "orders": [{"id": "O", "skill": "a", "demand": 4}]}


class WithConstruction:
    """The canonical registry view plus one attached, read-only construction."""

    def __init__(self, adapter):
        self.base = registry_view()
        manifest = NS(capability_id=CID, function="assignment.staffing", provider="composed:staffing-via-maxflow",
                      consequence_class="read_only", provenance={"baseline": "re-proved per call"})
        self.manifests = {**self.base.manifests, CID: manifest}
        self.adapters = {**self.base.adapters, CID: adapter}

    def by_function(self, function):
        return [m for m in self.manifests.values() if getattr(m, "function", None) == function]

    def usable(self, cid):
        return (True, "attached") if cid == CID else self.base.usable(cid)

    def __getattr__(self, name):
        return getattr(self.base, name)


@pytest.fixture(autouse=True)
def no_index(tmp_path, monkeypatch):
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")


def staffing(calls):
    def adapter(request, ctx):
        calls.append(request)
        staffed = min(sum(w["capacity"] for w in request["workers"]), sum(o["demand"] for o in request["orders"]))
        return {"certified": True, "staffed": staffed, "certificate": {"kind": "max-flow/min-cut"}}
    return adapter


def compile_(registry, geometry, **extra):
    return compiler.run({"problem_id": "p", "compile": {"geometry": geometry, "data": DATA, **extra}},
                        registry=registry)


def test_the_construction_is_the_selected_route_for_these_inputs():
    calls = []
    r = compile_(WithConstruction(staffing(calls)), {"geometry": "optimization"})
    assert r["method_or_composition_selected"] == CID and r["state"] == "ANSWERED" and len(calls) == 1
    assert r["confidence_type"] == compiler.CERTIFIED


@pytest.mark.parametrize("extra", [{"geometry": {"geometry": "optimization", "consequence_class": "financial"}},
                                   {"geometry": {"geometry": "optimization"}, "consequence": {"financial": 0.8}}])
def test_a_high_consequence_construction_answer_needs_a_formal_model_and_is_conditional(extra):
    calls = []
    registry = WithConstruction(staffing(calls))
    r = compiler.run({"problem_id": "p", "compile": {"data": DATA, **extra}}, registry=registry)
    assert r["state"] == "FORMALIZATION_INCOMPLETE" and calls == []
    complete = {**DATA, "formalization_complete": True}
    r = compiler.run({"problem_id": "p", "compile": {"data": complete, **extra}}, registry=registry)
    assert r["state"] == "WORLD_UNVERIFIED" and r["result"]["staffed"] == 4
    assert r["confidence_type"] == compiler.CERTIFIED and "not verified" in r["uncertainty"]


def test_the_construction_call_is_a_required_step_on_the_decision_budget():
    calls = []
    registry = WithConstruction(staffing(calls))
    r = compile_(registry, {"geometry": "optimization", "latency_budget": 0.01})
    assert r["state"] == "ABSTAIN" and calls == []
    assert any("BUDGET_EXHAUSTED" in a for a in r["abstentions"])
    r = compile_(registry, {"geometry": "optimization"})
    assert f"constructed:{CID}" in [s["step"] for s in r["resource_use"]["budget"]["steps"]]


def test_the_sensitivity_operator_re_runs_the_construction():
    calls = []
    r = compiler.run({"problem_id": "p", "compile": {
        "geometry": {"geometry": "optimization", "consequence_class": "financial",
                     "deterministic_or_stochastic": "stochastic"},
        "data": {**DATA, "formalization_complete": True}}}, registry=WithConstruction(staffing(calls)))
    assert any(t["operator_id"] == "sensitivity_analysis" for t in r["transformations"])
    assert r["state"] == "WORLD_UNVERIFIED"
    assert set(r["sensitivity"]["inputs"]) | set(r["sensitivity"]["not_run"]) == {"orders", "workers"}
    assert len(calls) == 1 + len(r["sensitivity"]["inputs"]) >= 2


def test_the_implied_geometry_counts_a_construction_the_declaration_excludes():
    r = compile_(WithConstruction(staffing([])), {"geometry": "feasibility"})
    assert "optimization" in r["derived_geometry"]["fits_by_inputs"]
    assert r["derived_geometry"]["agrees"] is False
    assert any("declared geometry 'feasibility'" in d for d in r["dissent"])
