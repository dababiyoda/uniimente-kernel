"""P6 v3: forecast_then_staff on the canonical cognition path, and the natural F6 family's integrity.

Development days only (60-73); the held-out days (74-163) are never generated here. Genome families start
registered-and-withheld (VERIFIED); these tests attach them in an in-memory registry view exactly as the
frozen evaluation does. Nothing here changes a body or creates authority.
"""
import copy
import hashlib
import math

import pytest

pytest.importorskip("scipy")

from cortex.evaluation.composition_lift import run_v3 as R  # noqa: E402
from cortex.evaluation.data import build_bank_calls  # noqa: E402
from greg.cognition import composition  # noqa: E402
from greg.cognition.composition import CognitionError, route, staffing_quantile  # noqa: E402
from greg.cognition.cortex import reason, registry_view  # noqa: E402
from greg.cognition.genomes.solvers_b import erlang_truth  # noqa: E402


def attached():
    registry = registry_view()
    for cid in R.EVAL_ATTACH:
        registry.set_state(cid, "ATTACHED")
    return registry


def small(day=60, blocks=3):
    item = R.f6(day)
    item = copy.deepcopy(item)
    item["payload"]["arrival_histories"] = item["payload"]["arrival_histories"][:blocks]
    item["truth"]["required"] = item["truth"]["required"][:blocks]
    return item


def chain(item, **kw):
    return {"problem_id": item["item_id"], "chain": {"question": "q", "payload": item["payload"], **kw}}


def test_the_critical_fractile_is_one_minus_cost_over_penalty_and_refuses_nonsense():
    assert staffing_quantile({"agent_cost": 1.0, "shortage_penalty": 10.0}) == 0.9
    assert staffing_quantile({"agent_cost": 1.0, "shortage_penalty": 3.0}) == pytest.approx(2 / 3, abs=1e-6)
    for plan in ({"agent_cost": 1.0, "shortage_penalty": 1.0}, {"agent_cost": 0.0, "shortage_penalty": 5.0}):
        with pytest.raises(CognitionError):
            staffing_quantile(plan)


def test_staffing_to_the_fractile_rate_minimises_expected_cost_under_the_predictive_distribution():
    # The Erlang requirement rises with the rate, so the q* quantile of the rate gives the q* quantile of
    # the requirement; brute force over staffing levels agrees on a discrete predictive distribution.
    plan = dict(R.STAFFING, shortage_penalty=10.0)
    rates = [0.6 + 0.02 * k for k in range(40)]              # equally likely arrival rates per second
    need = [erlang_truth({"arrival_rate": r, "mean_service_time": plan["mean_service_time"],
                          "target_wait": plan["target_wait"],
                          "max_wait_probability": plan["max_wait_probability"]}) for r in rates]

    def expected(n):
        return n + plan["shortage_penalty"] * sum(max(0, m - n) for m in need) / len(need)
    best = min(range(min(need), max(need) + 1), key=lambda n: (expected(n), n))
    level = staffing_quantile(plan)
    fractile = sorted(need)[math.ceil(level * len(need)) - 1]
    assert expected(fractile) == pytest.approx(expected(best))


def test_the_staffing_geometry_routes_to_its_recipe_only():
    item = small()
    assert route(item["payload"]) == "forecast_then_staff"
    with_newsvendor = {**item["payload"], "demand_histories": [], "newsvendor": {}}
    assert route(with_newsvendor) is None                     # ambiguous: no composition


def test_forecast_then_staff_answers_through_verified_stages_and_creates_no_authority():
    item = small()
    r = reason(chain(item), registry=attached())
    assert r["state"] == "ANSWERED" and r["authority_created"] is False
    assert [s["stage"] for s in r["stages"]] == [f"{k}:{b['block']}" for b in item["payload"]["arrival_histories"]
                                                 for k in ("forecast", "staff")]
    assert all(s["verifier"] == "STRUCTURALLY_VERIFIED" for s in r["stages"])
    assert r["answer"]["quantile_level"] == staffing_quantile(item["payload"]["staffing"])
    assert len(r["answer"]["agents"]) == 3 and all(type(n) is int and n > 0 for n in r["answer"]["agents"])
    assert R.f6_cost(item, r["answer"])[1] == "decided"


def test_a_malformed_staffing_plan_is_refused_not_guessed():
    item = small()
    item["payload"]["staffing"] = {**item["payload"]["staffing"], "overtime": 2}
    with pytest.raises(CognitionError):
        reason(chain(item), registry=attached())


def test_a_withheld_forecaster_makes_the_chain_abstain():
    registry = registry_view()
    registry.set_state("cognition.queue_erlang", "ATTACHED")      # the forecaster stays withheld
    r = reason(chain(small()), registry=registry)
    assert r["state"] == "STAGE_ABSTAINED" and r["answer"] is None


def test_the_payload_never_contains_the_day_it_is_scored_on():
    data = R.bank_calls()
    for day in (60, 66, 73):
        item = R.f6(day)
        for b, block in enumerate(item["payload"]["arrival_histories"]):
            assert len(block["history"]) == day
            assert block["history"][-1] == data["days"][day - 1]["blocks"][b]
        assert item["truth"]["actual"] == data["days"][day]["blocks"]
    with pytest.raises(ValueError):
        R.f6(59)                                                # fewer than 60 days of history


def test_scoring_separates_no_decision_infeasible_and_realised_cost():
    item = R.f6(61)
    required = item["truth"]["required"]
    assert R.f6_cost(item, None) == (None, "no_decision")
    assert R.f6_cost(item, {"agents": required[:-1]}) == (None, "wrong")
    assert R.f6_cost(item, {"agents": [-1] + required[1:]}) == (None, "wrong")
    exact, _ = R.f6_cost(item, {"agents": required})
    assert exact == item["truth"]["hindsight_cost"]             # perfect staffing costs exactly the hindsight
    penalty = item["payload"]["staffing"]["shortage_penalty"]
    short, _ = R.f6_cost(item, {"agents": [required[0] - 2] + required[1:]})
    assert short == exact - 2 + 2 * penalty


def test_the_requirement_is_the_erlang_answer_at_the_realised_rate_and_rises_with_arrivals():
    reqs = [R.requirement(n) for n in (0, 400, 800, 1600, 3200)]
    assert reqs[0] == 0 and reqs == sorted(reqs) and len(set(reqs)) == 5


def test_the_committed_data_rebuilds_byte_for_byte_from_the_recorded_source(tmp_path):
    data = R.bank_calls()
    assert data["source_sha256"] == build_bank_calls.SOURCE_SHA256 and len(data["days"]) == 164
    assert all(len(d["blocks"]) == 28 and all(n > 0 for n in d["blocks"]) for d in data["days"])
    # build() rejects any source whose digest differs from the recorded one
    forged = tmp_path / "bank_calls.csv"
    forged.write_text("rownames,DateTime,Calls\n1,2003-03-03T07:00:00Z,1\n")
    with pytest.raises(SystemExit):
        build_bank_calls.build(forged)
    assert hashlib.sha256(R.DATA.read_bytes()).hexdigest() == R.V1._sha(R.DATA).split(":", 1)[-1]


def test_the_freeze_hashes_every_module_the_run_can_execute():
    closure = set(R.code_closure())
    # the isolated runner, the dynamically imported genome modules, the sandbox filter and the data
    for path in ("greg/capabilities.py", "greg/cognition/worker.py", "greg/cognition/genomes/forecasting.py",
                 "greg/cognition/genomes/solvers_b.py", "greg/cognition/evidence.py", "tools/offline_test.py",
                 "cortex/evaluation/composition_lift/run.py", "cortex/evaluation/data/bank_calls_halfhour.json.gz"):
        assert path in closure
    assert all((R.ROOT / p).is_file() and "__pycache__" not in p for p in closure)
    assert set(R.inputs()["code"]) == closure


def test_sharded_days_come_back_in_suite_order_with_one_core_each(monkeypatch):
    import os
    if len(os.sched_getaffinity(0)) < 2:
        pytest.skip("needs two cores")

    def fake_arm(item, arm, static_recipe):
        return {"result": "decided", "cost": float(item["seed"]), "seconds": 0.0, "stages": 0, "state": "ANSWERED",
                "shortage": None, "answer": {"cores": sorted(os.sched_getaffinity(0))}}
    monkeypatch.setattr(R, "run_arm", fake_arm)
    items = [{"item_id": f"F6-{d}", "family": "F6", "seed": d, "truth": {}} for d in range(60, 66)]
    rows = R.run_items(items, "forecast_then_staff", workers=2)
    assert [r["item_id"] for r in rows] == [i["item_id"] for i in items]
    assert all(len(r["arms"]["routed_composition"]["answer"]["cores"]) == 1 for r in rows)
    sequential = R.run_items(items, "forecast_then_staff", workers=1)
    assert [[a["cost"] for a in r["arms"].values()] for r in rows] == \
        [[a["cost"] for a in r["arms"].values()] for r in sequential]
