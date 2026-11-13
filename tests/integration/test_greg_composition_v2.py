"""P6 v2 composition recipes on the operation path of the canonical cognition (real workers and verifiers).

Genome families start registered-and-withheld (VERIFIED); these tests attach them in an in-memory
registry view exactly as the frozen evaluation does. Nothing here changes a body or creates authority.
"""
import copy

import pytest

pytest.importorskip("ortools")
pytest.importorskip("networkx")

from cortex.evaluation.composition_lift import run_v2 as R  # noqa: E402
from greg.cognition import composition  # noqa: E402
from greg.cognition.composition import route  # noqa: E402
from greg.cognition.cortex import reason, registry_view  # noqa: E402


def attached():
    registry = registry_view()
    for cid in R.EVAL_ATTACH:
        registry.set_state(cid, "ATTACHED")
    return registry


def chain(item, **kw):
    return {"problem_id": item["item_id"], "chain": {"question": "q", "payload": item["payload"], **kw}}


def test_each_new_geometry_routes_to_its_recipe_only():
    assert route(R.f3(1)["payload"]) == "graph_then_allocate"
    assert route(R.f4(1)["payload"]) == "bayes_then_voi"
    assert route(R.f5(0)["payload"]) == "forecast_then_allocate"
    assert route({**R.f3(1)["payload"], **R.f4(1)["payload"]}) is None       # ambiguous: no composition


def test_graph_then_allocate_reaches_the_certified_optimum_and_cross_checks_it():
    item = R.f3(2)
    r = reason(chain(item), registry=attached())
    assert r["state"] == "ANSWERED" and r["authority_created"] is False
    assert [s["stage"] for s in r["stages"]] == ["compile", "optimize", "cross_check"]
    assert all(s["verifier"] == "STRUCTURALLY_VERIFIED" for s in r["stages"])
    assert R.f3_score(item, r["answer"]) == "correct"


def test_a_cross_intelligence_disagreement_is_a_translation_failure(monkeypatch):
    real = composition._operation

    def forged(reason_fn, pid, operation, data, **kw):
        out = real(reason_fn, pid, operation, data, **kw)
        if operation == "optimize" and out.get("output"):
            out = copy.deepcopy(out)
            out["output"]["objective_value"] += 5          # the optimiser over-claims its flow
        return out
    monkeypatch.setattr(composition, "_operation", forged)
    r = reason(chain(R.f3(2)), registry=attached())
    assert r["state"] == "TRANSLATION_FAILED" and r["answer"] is None and r["translation_failures"]


def test_bayes_then_voi_chooses_the_bayes_optimal_next_action():
    for seed in (1, 2, 3):
        item = R.f4(seed)
        r = reason(chain(item), registry=attached())
        assert r["state"] == "ANSWERED"
        assert r["answer"]["action"] in item["truth"]["optimal_actions"]


def test_forecast_then_allocate_returns_a_feasible_four_week_plan_on_real_m4_series():
    item = R.f5(0)
    r = reason(chain(item), registry=attached())
    assert r["state"] == "ANSWERED"
    cost, status = R.f5_cost(item, r["answer"])
    assert status == "decided" and cost >= item["truth"]["hindsight_cost"] - 1e-9
    assert len(r["stages"]) == 3 + 2 * R.F5_WEEKS


def test_a_withheld_genome_makes_the_chain_abstain_without_inventing_a_route():
    r = reason(chain(R.f3(2)), registry=registry_view())          # genome families withheld by default
    assert r["state"] == "STAGE_ABSTAINED" and r["answer"] is None
    assert r["stages"][0]["abstention_state"] == "CAPABILITY_DEFICIT"
