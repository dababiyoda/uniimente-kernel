"""Decision-aware cognitive expenditure on the compile path (directive section 12).

Each test reproduced a defect on the branch before the controller existed. The compile request's
``latency_budget`` was handed to every inner run whole: the answer, the premises check and up to four sensitivity
re-runs could each take all of it, so one request could spend its budget six times. Nothing weighed whether an
optional re-run fitted, no stop reason was kept, and local compute was recorded as a ceiling, not a measurement.

The budget's clock is fake, but each inner run's latency limit is a real solver deadline (the solver gets 45% of
it). Just after a container restore, a first solve outlasted the 2.25s a default 5s limit gives the solver and
correctly came back UNKNOWN (TIMEOUT). The budgets below therefore give every inner run a real limit of 20s or
more, and the fake clock alone decides what is spent (tests/evidence/seed-genome-residuals-2026-10-13/cold-start.log).
"""
from types import SimpleNamespace

import pytest

pytest.importorskip("ortools")
pytest.importorskip("z3")

from cortex.evaluation.composition_lift import run_v2 as R  # noqa: E402
from greg.cognition import compiler, cortex  # noqa: E402
from greg.cognition.budget import MIN_STEP_SECONDS, Controller  # noqa: E402
from greg.cognition.contracts import CognitionError  # noqa: E402

MODEL = {"variables": {"x": [0, 10], "y": [0, 10]},
         "constraints": [{"coefficients": {"x": 1, "y": 1}, "op": ">=", "rhs": 5}],
         "objective": {"coefficients": {"x": 1, "y": 2}, "sense": "min"}, "formalization_complete": True}
# high consequence and stochastic: the sensitivity operator applies and re-runs each of three numeric inputs
SENSITIVE = {"geometry": "optimization", "consequence_class": "financial", "deterministic_or_stochastic": "stochastic"}


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@pytest.fixture
def registry():
    r = cortex.registry_view()
    for cid in R.EVAL_ATTACH:
        r.set_state(cid, "ATTACHED")
    return r


@pytest.fixture(autouse=True)
def no_index(tmp_path, monkeypatch):
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")


@pytest.fixture
def timed(monkeypatch):
    """Every inner cortex run takes ``cost`` seconds on the budget's clock; real computation still runs."""
    state = SimpleNamespace(cost=16.0, clock=Clock(), limits=[])
    monkeypatch.setattr(compiler, "CLOCK", state.clock)
    original = cortex.reason

    def reason(params, **kw):
        if "compile" in params:
            return original(params, **kw)
        state.limits.append(params.get("geometry", {}).get("latency_limit"))
        out = original(params, **kw)
        state.clock.now += state.cost
        return out
    monkeypatch.setattr(cortex, "reason", reason)
    return state


def compile_(registry, geometry, data):
    return cortex.reason({"problem_id": "budget", "compile": {"geometry": geometry, "data": data}}, registry=registry)


def test_required_steps_are_never_priced_away_and_optional_ones_must_fit_their_measured_tail():
    clock = Clock()
    b = Controller(10, clock=clock)
    assert b.allot("answer", required=True) == 10
    with pytest.raises(CognitionError):
        b.allot("again", required=True)                       # one step at a time, each closed with its cost
    clock.now = 4
    b.done("answer", cpu_seconds=0.5)
    assert b.cost_range() == [4.0, 4.0] and b.allot("sensitivity:a", required=False) == 6
    clock.now = 9
    b.done("sensitivity:a")
    assert b.allot("sensitivity:b", required=False) is None    # 1s left, the slowest measured step took 5s
    assert "slowest measured step" in b.stops()[-1]["reason"]
    assert b.allot("premises", required=True) == pytest.approx(1)   # a required step still runs in what is left
    clock.now = 9.95
    b.done("premises")
    assert b.allot("more", required=True) is None and b.stops()[-1]["reason"].startswith("BUDGET_EXHAUSTED")
    s = b.summary()
    assert s["measured_step_s"] == {"count": 3, "p50": 4.0, "max": 5.0, "note": s["measured_step_s"]["note"]}
    assert s["cpu_s"] == 0.5 and [x["step"] for x in s["stopped"]] == ["sensitivity:b", "more"]
    assert Controller(5, clock=clock).allot("x", required=False) == 5   # no measurement yet: nothing to price


def test_one_budget_covers_the_whole_compiled_decision(registry, timed, monkeypatch):
    r = compile_(registry, {**SENSITIVE, "latency_budget": 40}, MODEL)
    assert r["state"] == "WORLD_UNVERIFIED" and isinstance(r["result"], dict)
    sens, budget = r["sensitivity"], r["resource_use"]["budget"]
    # answer 16s (24 left), first re-run 16s (8 left), then the 16s tail no longer fits: two inputs stay untested
    assert list(sens["inputs"]) == ["constraints"] and set(sens["not_run"]) == {"objective", "variables"}
    assert timed.limits == [30, 24]                      # the 30s step ceiling, then only what remained
    assert len(r["intermediate_receipts"]) == 1 + len(sens["inputs"])
    assert any("not tested within the thinking budget" in d for d in r["dissent"])
    assert budget["total_source"] == "declared latency_budget" and budget["spent_s"] == 32
    assert [s["decision"] for s in budget["steps"]] == ["RUN", "RUN", "STOP", "STOP"]
    # with room for every re-run, all of them run: the budget narrows only when it binds
    timed.clock.now, timed.limits[:] = 0.0, []
    wide = compile_(registry, {**SENSITIVE, "latency_budget": 70}, MODEL)
    assert set(wide["sensitivity"]["inputs"]) == {"constraints", "objective", "variables"}
    assert wide["sensitivity"]["not_run"] == {}


def test_a_spent_budget_narrows_the_result_instead_of_skipping_required_evidence(registry, timed):
    claim = {"variables": {"x": [0, 10], "y": [0, 10]},
             "constraints": [{"coefficients": {"x": 1, "y": 1}, "op": "<=", "rhs": 10}],
             "property": {"coefficients": {"x": 1}, "op": "<=", "rhs": 10}}
    timed.cost = 29.95
    r = compile_(registry, {"geometry": "deductive", "latency_budget": 30}, {"claim": claim})
    # the claim holds within the model, but the vacuity check had no budget: the verdict says so
    assert r["result"]["claim"] == "HOLDS_WITHIN_MODEL"
    assert r["result"]["premises"].startswith("UNDECIDED (BUDGET_EXHAUSTED")
    timed.clock.now, timed.cost = 0.0, 0.0
    empty = compile_(registry, {**SENSITIVE, "latency_budget": MIN_STEP_SECONDS / 2}, MODEL)
    assert empty["state"] == "ABSTAIN" and empty["abstentions"][-1].startswith("BUDGET_EXHAUSTED")
    assert empty["intermediate_receipts"] == []          # nothing ran: no answer without its verification


def test_local_compute_is_measured_not_assumed_free(registry, monkeypatch):
    roomy = {"latency_limit": 30}
    r = cortex.reason({"problem_id": "cpu", "operation": "optimize", "data": dict(MODEL), "geometry": roomy},
                      registry=registry)
    assert r["output"] is not None
    cost = r["compute_cost"]
    assert cost["cpu_seconds"] > 0 and cost["peak_memory"] == "unmeasured" and cost["energy"] == "unmeasured"
    # where a platform offers no resource accounting, the receipt says unmeasured instead of crashing or saying 0
    with monkeypatch.context() as m:
        m.setattr(cortex, "_cpu_seconds", lambda: None)
        blind = cortex.reason({"problem_id": "cpu2", "operation": "optimize", "data": dict(MODEL), "geometry": roomy},
                              registry=registry)
    assert blind["compute_cost"]["cpu_seconds"] == "unmeasured" and blind["output"] == r["output"]
    compiled = compile_(registry, {"geometry": "optimization", "consequence_class": "internal_write"}, MODEL)
    budget = compiled["resource_use"]["budget"]
    assert budget["total_source"].startswith("default") and budget["total_s"] == compiler.DEFAULT_BUDGET_S
    assert budget["cpu_s"] > 0 and budget["measured_step_s"]["count"] == compiled["resource_use"]["stages"] == 1


def test_a_formed_mechanism_is_a_required_step_on_the_same_budget(tmp_path, monkeypatch):
    # The Capability Genesis route (a founder-attached formed mechanism) runs an installed engine. It used to run
    # outside the thinking budget: never refused when the budget was spent, never measured, never reported.
    pytest.importorskip("scipy")
    from greg import genesis as G
    from greg import mechanisms
    from greg.cognition import assignment as A
    (tmp_path / "index.json").write_text('{"genomes": {}, "recipes": {}, "routing": {}}')
    registry = cortex.registry_view()
    c = next(c for c in G.CATALOG[A.FUNCTION]["candidates"] if c.distribution == "scipy")
    card = mechanisms.card(c, A.FUNCTION, mechanisms.installed("scipy"))
    manifest = G.Genesis(journal=None, registry=registry, workspace_root=tmp_path / "ws")._package_manifest(
        A.FUNCTION, c, card, "budget-test")
    registry.register(manifest, G.package_adapter(A.FUNCTION, c), state="ATTACHED")
    step = f"formed:{manifest.capability_id}"
    costs = [[7, 3, 9, 4], [2, 8, 6, 5], [6, 4, 3, 8]]

    def assign(budget):
        return compile_(registry, {"geometry": "optimization", "latency_budget": budget}, {"costs": costs})

    r = assign(40)
    assert r["state"] == "ANSWERED" and r["selection_level"] == "formed_by_capability_genesis"
    [run] = r["resource_use"]["budget"]["steps"]
    assert run["step"] == step and run["decision"] == "RUN" and run["spent_s"] > 0 and run["limit_s"] == 30
    real, started = G.run_formed, []
    monkeypatch.setattr(G, "run_formed", lambda *a, **k: started.append(a) or real(*a, **k))
    spent = assign(MIN_STEP_SECONDS / 2)
    assert spent["state"] == "ABSTAIN" and spent["result"] is None and started == []   # refused before the engine
    assert spent["abstentions"][-1].startswith("BUDGET_EXHAUSTED")
    clock = Clock()
    monkeypatch.setattr(compiler, "CLOCK", clock)

    def slow(*a, **k):
        out = real(*a, **k)
        clock.now += 50
        return out
    monkeypatch.setattr(G, "run_formed", slow)
    late = assign(40)
    assert late["state"] == "ANSWERED" and late["resource_use"]["budget"]["spent_s"] == 50
    assert any("overran the thinking budget" in d for d in late["dissent"])            # disclosed, not hidden
