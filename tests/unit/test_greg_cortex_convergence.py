"""Real engines on one canonical cognition seam; laboratory keys are not Alfonso."""
from __future__ import annotations

import pytest

from cortex.evaluation.build_suites import schedule
from greg.body import Body
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext
from greg.cognition import solve, status
from greg.cortex_bridge import dependency_deficits, run
from tests.greg_fixtures import Clock, make_body, mission, signed

DECL = {"consequence_class": "internal_write", "reversibility": "reversible"}


def problem(function):
    payload = {"declared": DECL}
    if function == "graph.shortest_path":
        payload["graph"] = {"kind": "shortest_path", "source": "A", "target": "C",
                            "edges": [["A", "B", 1], ["B", "C", 2], ["A", "C", 7]]}
    elif function == "graph.max_flow":
        payload["graph"] = {"kind": "max_flow", "source": "s", "sink": "t",
                            "edges": [["s", "a", 3], ["a", "t", 2], ["s", "t", 1]]}
    else:
        payload["linear_program"] = {
            "variables": [{"name": "x", "lower": 0}, {"name": "y", "lower": 0}],
            "objective": {"sense": "min", "coefficients": {"x": 1, "y": 2}},
            "constraints": [{"op": ">=", "coefficients": {"x": 1, "y": 1}, "rhs": 4}]}
    return {"dialect": "cortex", "problem_id": "p-" + function.replace(".", "-"),
            "question": function, "payload": payload, "budget_ms": 30000}


def spec(p, function, auto_attach):
    return mission("m:typed-cortex", checks=[{
        "check_id": "answer", "description": "current certified encoded computation",
        "sensor": {"capability": "cognition.status", "target": "cognition:" + p["problem_id"],
                   "params": {"problem_id": p["problem_id"]}},
        "predicate": {"op": "equals", "field": "answered", "value": True}}],
        strategies=[{"action_id": "compute", "capability": "cognition.solve", "target": "cognition:" + p["problem_id"],
                     "params": {"problem": p}, "advances": ["answer"], "rationale": "certified package computation"}],
        capabilities=["cognition.solve", "cognition.status", "acquired." + function + ".*"],
        targets=["cognition:" + p["problem_id"]], ceiling="read_only", auto_attach=auto_attach)


def context(body, tmp_path):
    return InvocationContext(tmp_path, (), None, BUILTINS["cognition.solve"][0], registry=body.registry,
                             journal=body.journal, mission_id="m:typed-cortex",
                             authority_ref="laboratory-signed-test-scope", grant_id="laboratory-test-grant")


@pytest.mark.parametrize("function", ["graph.shortest_path", "graph.max_flow", "lp.optimize"])
def test_package_genesis_then_same_cognition_problem_runs_and_reobserves(tmp_path, function):
    pytest.importorskip("networkx")
    pytest.importorskip("scipy")
    home, key, bid, _ = make_body(tmp_path)
    p = problem(function)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.apply(signed(key, bid, "MISSION", spec(p, function, True)))
        m = body.engine.book.missions["m:typed-cortex"]
        assert dependency_deficits(p, body.registry) == [function]
        ctx = context(body, tmp_path)
        negative = solve({"problem": p}, ctx)
        assert not negative["answered"] and negative["dependency_deficits"] == [function]
        acquired = body.genesis.resolve(mission=m, function=function, purpose="same signed cognition problem", now=clock())
        assert acquired is not None and acquired.provenance["mode"] == "DEPEND"
        assert body.registry.state[acquired.capability_id] == "ATTACHED"
        positive = solve({"problem": p}, ctx)
        assert positive["answered"] and positive["dependency_deficits"] == []
        assert positive["supersedes"] == negative["receipt_id"] and positive["revision"] == 1
        assert len(body.journal.replay("cognition.receipt")) == 2
        assert status({"problem_id": p["problem_id"]}, ctx)["answered"]
        result = positive["output"]["answer"]
        assert result["certified"] and positive["authority_created"] is False
        assert (result["distance"] if function.endswith("shortest_path") else
                result["value"] if function.endswith("max_flow") else result["objective"]) == (4 if function == "lp.optimize" else 3)
        body.registry.set_state(acquired.capability_id, "DETACHED")
        assert not status({"problem_id": p["problem_id"]}, ctx)["answered"]
        assert dependency_deficits(p, body.registry) == [function]


def test_qualification_does_not_attach_outside_signed_auto_attach_scope(tmp_path):
    pytest.importorskip("networkx")
    pytest.importorskip("scipy")
    function = "graph.shortest_path"
    home, key, bid, _ = make_body(tmp_path)
    p = problem(function)
    with Body(home) as body:
        body.apply(signed(key, bid, "MISSION", spec(p, function, False)))
        m = body.engine.book.missions["m:typed-cortex"]
        assert body.genesis.resolve(mission=m, function=function, purpose="qualification only", now=Clock()()) is None
        manifests = body.registry.by_function(function)
        assert manifests and all(body.registry.state[x.capability_id] == "VERIFIED" for x in manifests)
        assert dependency_deficits(p, body.registry) == [function]
        assert not run(p, registry=body.registry)["answered"]
        assert body.journal.replay("deficit.awaiting_attach")


def test_solver_fallback_and_explicit_dialect_preserve_legacy_entry():
    model, _, _ = schedule([("A", 2), ("B", 3)], 8, [])
    p = {"dialect": "cortex", "problem_id": "fallback", "question": "Feasible?",
         "payload": {"declared": DECL, "formal_model": model, "faults": {"solver_available": False}}}
    result = run(p)
    assert result["authority_created"] is False
    assert result["cortex_receipt"]["versions"]["cortex"].startswith("0.")
    assert result["answered"]
    assert result["cortex_receipt"]["route"]["selected"] == ["cortex.optimization.cpsat@0.2.0"]
    with pytest.raises(CapabilityError, match="explicit cortex dialect"):
        run({k: v for k, v in p.items() if k != "dialect"})


def test_typed_cortex_still_requires_existing_canonical_grant(tmp_path):
    ctx = InvocationContext(tmp_path, (), None, BUILTINS["cognition.solve"][0])
    with pytest.raises(CapabilityError, match="authority"):
        solve({"problem": problem("graph.shortest_path")}, ctx)
