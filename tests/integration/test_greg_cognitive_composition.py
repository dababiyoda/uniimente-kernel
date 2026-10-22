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
                            "bayes_then_voi", "forecast_then_allocate", "forecast_then_staff", "track_then_staff"}


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


# ---------------------------------------------------------------- review of PR #179, 2026-10-15 (M8, M9)
def _three_stage(seed=1):
    """F1's estimate feeds capacity and F2's identified effects price the objective: both template roots."""
    a, b = f1(seed)["payload"], f2(seed)["payload"]
    template = {**b["formal_template"],
                "constraints": b["formal_template"]["constraints"] + [
                    {"id": "C2", "covers": ["B"], "expr": [">=", ["+", ["*", 40, "a"], ["*", 20, "b"]],
                                                           {"$param": "estimate.low"}]}]}
    return {"estimation_model": a["estimation_model"], "causal_studies": b["causal_studies"],
            "formal_template": template}


def test_derive_builds_chains_by_dataflow_and_abstains_without_a_producer():
    """M9: derive() had no unit coverage; a mutant returning None passed every test."""
    from greg.cognition.composition import derive
    assert derive(_three_stage()) == ("estimate", "identify", "optimize")
    assert derive(f1(1)["payload"]) == ("estimate", "optimize")
    assert derive(f2(1)["payload"]) == ("identify", "optimize")
    assert derive({"formal_template": {"constraints": [{"expr": {"$param": "unknown.x"}}]}}) is None
    assert derive({"estimation_model": {}}) is None                         # no template
    no_producer = {"formal_template": f1(1)["payload"]["formal_template"]}  # root without its producer's input
    assert derive(no_producer) is None


def test_a_derived_chain_runs_on_the_one_path_when_it_consumes_every_matched_recipe():
    """M9 integration: the three-stage payload matches both template recipes; the derived chain consumes both, so it
    runs (routed by dataflow) and reports no unconsumed input."""
    r = reason({"problem_id": "trackb:m9", "chain": {"payload": _three_stage()}}, registry=registry_view())
    assert r["routed_by"] == "dataflow" and r["recipe"] == "derived:estimate+identify+optimize"
    assert [s["stage"].split(":")[0] for s in r["stages"]][:2] == ["estimate", "identify"]
    assert r["unconsumed_inputs"] == []


def test_an_ambiguous_geometry_is_refused_not_silently_narrowed():
    """M8: derive() overrode the ambiguity refusal and dropped inputs. f1 + f2 merged keeps F1's template (estimate
    root only), so causal_studies would be ignored; f1 + a capacity network would ignore the network."""
    merged = {**f2(1)["payload"], **f1(1)["payload"]}
    r = reason({"problem_id": "trackb:m8a", "chain": {"payload": merged}}, registry=registry_view())
    assert r["state"] == "NO_RECIPE" and "ambiguous" in r["reason"] and r["recipe"] is None
    network = {"capacity_network": {"edges": [["s", "t", 1, 1, 1]], "source": "s", "sink": "t", "budget": 1}}
    r = reason({"problem_id": "trackb:m8b", "chain": {"payload": {**f1(1)["payload"], **network}}},
               registry=registry_view())
    assert r["state"] == "NO_RECIPE" and "graph_then_allocate" in r["reason"]


def test_the_competency_compiler_reaches_a_derived_chain_and_never_answers_part_of_it():
    """M7: the compiler used route() only, so a three-stage payload planned Fermi (the estimate alone) and, executed,
    abstained with no deficit. It now adds the derived chain, rejects Fermi as a relaxation, and answers by dataflow."""
    payload = _three_stage()
    planned = reason({"problem_id": "trackb:m7", "compile": {"geometry": {}, "data": payload, "execute": False}},
                     registry=registry_view())
    assert planned["method_or_composition_selected"] == "composition:derived:estimate+identify+optimize"
    rejected = {r["method"]: r["why"] for r in planned["methods_rejected"]}
    assert any("relaxation" in why for m, why in rejected.items() if "estimation" in m), rejected
    executed = reason({"problem_id": "trackb:m7x", "compile": {"geometry": {}, "data": payload}},
                      registry=registry_view())
    assert executed["state"] in ("ANSWERED", "STAGE_ABSTAINED")
    assert executed["method_or_composition_selected"] == "composition:derived:estimate+identify+optimize"


def test_an_exact_single_genome_competes_on_a_recipe_shaped_capacity_request():
    """M10: genome rows matched top-level keys only, so a capacity_network request could only ever run the
    three-stage composition, whatever flow_expansion_mcf's admission. #158's part rows ask the one-part request of
    the methods its part fits; the genome, admitted DEFAULT at admission v3, answers it on the one path once attached."""
    from cortex.evaluation.composition_lift.run_v2 import f3
    from greg.cognition import compiler as C
    payload = f3(3)["payload"]
    rows = {r["method"]: r for r in C.candidates(payload, C.CompetencyGeometry(), C.evidence_index())}
    row = rows["cognition.flow_expansion_mcf"]
    assert row["part"] == "capacity_network" and not row["rejected"]
    assert row["status"] == "DEFAULT_FOR_GEOMETRY"                    # admission v3, pre-registered at 878f76c
    assert "composition:graph_then_allocate" in rows
    registry = registry_view()
    registry.set_state("cognition.flow_expansion_mcf", "ATTACHED")     # what a founder attach would record
    r = reason({"problem_id": "trackb:m10", "compile": {"geometry": {}, "data": payload}}, registry=registry)
    assert r["method_or_composition_selected"] == "cognition.flow_expansion_mcf" and r["state"] == "ANSWERED"
