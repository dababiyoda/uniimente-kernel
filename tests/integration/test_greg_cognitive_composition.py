"""P6 cognitive composition: geometry-routed chains of real cortex organs with typed translation.

Real Fermi, causal and CP-SAT organs in the bounded worker. The founder key is a per-test key.
"""
import copy

import pytest

pytest.importorskip("z3")
pytest.importorskip("ortools")

from greg.body import Body  # noqa: E402
from greg.cognition.composition import RECIPES, TranslationError, route, substitute  # noqa: E402
from greg.cognition.contracts import CognitionError  # noqa: E402
from greg.cognition.cortex import reason, registry_view  # noqa: E402
from cortex.evaluation.composition_lift.run import f1, f2, score  # noqa: E402
from tests.greg_fixtures import drop, make_body, mission, signed  # noqa: E402


def chain(item, **kw):
    return {"problem_id": item["item_id"], "chain": {"question": "q", "payload": item["payload"], **kw}}


def test_geometry_routes_each_family_to_its_recipe_and_nothing_else():
    assert route(f1(1)["payload"]) == "estimate_then_optimize"
    assert route(f2(1)["payload"]) == "identify_then_optimize"
    assert route({"formal_template": {}}) is None
    assert route({**f1(1)["payload"], **f2(1)["payload"]}) is None          # ambiguous: no composition


def test_estimate_then_optimize_covers_the_true_quantile_where_a_point_estimate_does_not():
    item = f1(3)
    r = reason(chain(item), registry=registry_view())
    assert r["state"] == "ANSWERED" and r["routed_by"] == "geometry" and score(item, r["answer"]) == "correct"
    assert [s["stage"] for s in r["stages"]] == ["estimate", "optimize"]
    assert r["bindings"][0]["slot"] == "estimate.high" and r["bindings"][0]["bound"] >= r["bindings"][0]["value"]
    assert r["authority_created"] is False


def test_identify_then_optimize_uses_identified_effects_not_association():
    item = f2(3)                                # confounding flips the naive ranking on this seed
    r = reason(chain(item), registry=registry_view())
    assert r["state"] == "ANSWERED" and score(item, r["answer"]) == "correct"
    assert {b["slot"] for b in r["bindings"]} == {"effect.a", "effect.b"}


def test_a_pinned_recipe_that_does_not_fit_abstains():
    r = reason(chain(f2(1), recipe="estimate_then_optimize"), registry=registry_view())
    assert r["state"] == "NO_RECIPE" and r["answer"] is None and r["routed_by"] == "fixed"


def test_a_failed_translation_abstains_and_is_recorded():
    item = copy.deepcopy(f1(1))
    item["payload"]["formal_template"]["constraints"][0]["expr"][2] = {"$param": "estimate.p99"}
    r = reason(chain(item), registry=registry_view())
    assert r["state"] == "TRANSLATION_FAILED" and r["translation_failures"] and r["answer"] is None


def test_an_abstaining_stage_stops_the_chain():
    item = copy.deepcopy(f2(1))
    item["payload"]["causal_studies"]["a"]["causal_spec"]["identification_basis"] = {"origin": "model_generated",
                                                                                     "ref": "llm dag"}
    r = reason(chain(item), registry=registry_view())
    assert r["state"] == "STAGE_ABSTAINED" and r["answer"] is None
    assert [s["stage"] for s in r["stages"]] == ["identify:a"]


def test_slots_are_typed():
    with pytest.raises(TranslationError, match="finite number"):
        substitute({"$param": "x"}, {"x": "12"}, [])
    with pytest.raises(TranslationError, match="takes"):
        substitute({"$param": "x", "extra": 1}, {"x": 1}, [])
    with pytest.raises(CognitionError):
        reason({"problem_id": "x", "chain": {"payload": {}, "recipe": "anything"}}, registry=registry_view())
    assert {"estimate_then_optimize", "identify_then_optimize"} <= set(RECIPES)   # v1 recipes retained
    assert set(RECIPES) == {"estimate_then_optimize", "identify_then_optimize", "graph_then_allocate",
                            "bayes_then_voi", "forecast_then_allocate"}


def test_a_signed_mission_closes_on_a_composed_answer(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    step = {"capability": "cognition.solve", "target": "cognition:staffing", "params": chain(f1(3))}
    spec = mission("m:composed-staffing", checks=[{
        "check_id": "plan", "description": "a certified least-cost plan for p95 demand", "sensor": step,
        "predicate": {"op": "equals", "field": "state", "value": "ANSWERED"}}],
        strategies=[{"action_id": "solve", **step, "advances": ["plan"], "rationale": "estimate then optimise"}],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        assert body.journal.replay("mission.appraised")[-1].payload["verdict"] == "VERIFIED"
