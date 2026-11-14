"""Review of the Track B join (budget.py 286 and 301): under a grant window the decision's clock starts when the
Controller is built, because planning time spends the window as surely as the steps do.

The join kept ours' grant-window Controller and theirs' lazy clock start (the clock starting at the first
allotment). Together, ``remaining()`` left out every second of planning (validation, evidence index, candidate
selection) while the window's total was fixed at construction:

* the routes that run on ``Controller.allot`` alone, with no inner ``ThinkingBudget`` to re-check the grant (a
  construction, a Genesis-formed engine), ran after the grant had expired;
* every other step's latency limit, and the optional-step rule, overstated the shared deadline by the planning
  time.

Without a window the lazy start stays (tests/unit/test_cognition_thinking_budget.py, planning time before the
first step never reaches its limit). These tests use the real clock, since the window's bounds are real instants.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
import time

import pytest

from greg.capabilities import InvocationBudgetWindow
from greg.cognition import compiler
from greg.cognition.budget import Controller
from greg.cognition.cortex import registry_view

PLANNING_S = 0.8


def window(*, expires_in=86400.0, **over):
    future = datetime.now(timezone.utc) + timedelta(days=1)
    values = dict(horizon=future.isoformat(),
                  grant_expires_at=(datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat(),
                  remaining_money_usd=0, authority_ref="test-pointer", grant_id="test-grant")
    return InvocationBudgetWindow(**{**values, **over})


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@pytest.fixture(autouse=True)
def no_index(tmp_path, monkeypatch):
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")


@pytest.fixture
def planning(monkeypatch):
    """Planning that takes PLANNING_S between the Controller's construction and its first allotment."""
    real = compiler.evidence_index

    def slow(*a, **k):
        time.sleep(PLANNING_S)
        return real(*a, **k)
    monkeypatch.setattr(compiler, "evidence_index", slow)


def test_a_grant_that_expires_during_planning_stops_the_first_step():
    budget = Controller(20, caller_window=window(expires_in=0.5))
    time.sleep(PLANNING_S)
    assert time.monotonic() > budget.inner["shared_deadline"]                 # the grant has expired
    assert budget.allot("constructed:x", required=True) is None
    assert budget.stops()[-1]["reason"].startswith("BUDGET_EXHAUSTED")
    assert budget.allot("formed:x", required=True) is None
    assert [s["decision"] for s in budget.summary()["steps"]] == ["STOP", "STOP"]


def test_the_first_limit_never_exceeds_what_the_shared_deadline_leaves():
    budget = Controller(2.0, shared_deadline=time.monotonic() + 2.0)
    time.sleep(2.0 - PLANNING_S)                                               # 0.8 s left on the shared deadline
    before = time.monotonic()
    limit = budget.allot("answer", required=True)
    assert limit is not None and limit <= budget.inner["shared_deadline"] - before
    assert budget.summary()["spent_s"] >= 2.0 - PLANNING_S                     # planning is reported as spent
    time.sleep(0.5)
    budget.done("answer")
    # about 0.3 s is really left and the measured step took 0.5 s: an optional re-run does not fit
    assert budget.allot("sensitivity:x", required=False) is None
    assert budget.stops()[-1]["reason"].startswith("STOP: the slowest measured step")
    assert budget.remaining() <= max(0.0, budget.inner["shared_deadline"] - time.monotonic()) + 1e-3


def test_only_a_window_starts_the_clock_at_construction():
    for kw in ({"caller_window": window()}, {"shared_deadline": time.monotonic() + 3600}):
        clock = Clock()
        budget = Controller(20, clock=clock, **kw)
        clock.now = 2.5
        assert budget.allot("answer", required=True) == pytest.approx(17.5)
    clock = Clock()
    lazy = Controller(20, clock=clock)                                         # theirs' lazy start, unchanged
    clock.now = 2.5
    assert lazy.allot("answer", required=True) == 20


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


def staffing(calls):
    def adapter(request, ctx):
        calls.append(request)
        staffed = min(sum(w["capacity"] for w in request["workers"]), sum(o["demand"] for o in request["orders"]))
        return {"certified": True, "staffed": staffed, "certificate": {"kind": "max-flow/min-cut"}}
    return adapter


def test_a_construction_never_runs_after_the_grant_expired(planning):
    calls = []
    registry = WithConstruction(staffing(calls))
    request = {"problem_id": "p", "compile": {"geometry": {"geometry": "optimization"}, "data": DATA}}
    r = compiler.run(request, registry=registry, caller_window=window(expires_in=0.5))
    assert calls == [] and r["state"] == "ABSTAIN"
    assert any(a.startswith("BUDGET_EXHAUSTED") for a in r["abstentions"])
    [step] = r["resource_use"]["budget"]["steps"]
    assert step["step"] == f"constructed:{CID}" and step["decision"] == "STOP"
    live = compiler.run(request, registry=registry, caller_window=window(latency_ceiling_seconds=15))
    assert live["state"] == "ANSWERED" and len(calls) == 1                     # the route does reach the construction


def test_a_formed_engine_never_runs_after_the_grant_expired(tmp_path, monkeypatch, planning):
    pytest.importorskip("scipy")
    from greg import genesis as G
    from greg import mechanisms
    from greg.cognition import assignment as A
    (tmp_path / "index.json").write_text('{"genomes": {}, "recipes": {}, "routing": {}}')
    registry = registry_view()
    c = next(c for c in G.CATALOG[A.FUNCTION]["candidates"] if c.distribution == "scipy")
    card = mechanisms.card(c, A.FUNCTION, mechanisms.installed("scipy"))
    manifest = G.Genesis(journal=None, registry=registry, workspace_root=tmp_path / "ws")._package_manifest(
        A.FUNCTION, c, card, "window-test")
    registry.register(manifest, G.package_adapter(A.FUNCTION, c), state="ATTACHED")
    real, started = G.run_formed, []
    monkeypatch.setattr(G, "run_formed", lambda *a, **k: started.append(a) or real(*a, **k))
    request = {"problem_id": "p", "compile": {"geometry": {"geometry": "optimization"},
                                              "data": {"costs": [[7, 3, 9, 4], [2, 8, 6, 5], [6, 4, 3, 8]]}}}
    r = compiler.run(request, registry=registry, caller_window=window(expires_in=0.5))
    assert started == [] and r["state"] == "ABSTAIN" and r["result"] is None
    assert r["abstentions"][-1].startswith("BUDGET_EXHAUSTED")
    [step] = r["resource_use"]["budget"]["steps"]
    assert step["step"] == f"formed:{manifest.capability_id}" and step["decision"] == "STOP"
    live = compiler.run(request, registry=registry, caller_window=window(latency_ceiling_seconds=15))
    assert live["state"] == "ANSWERED" and len(started) == 1                   # the route does reach the engine
