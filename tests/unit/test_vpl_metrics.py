"""VPL tracking metrics (directive section 16) are a reader over frozen results, never a verdict."""
from cortex.evaluation.composition_lift import vpl_metrics as M


def _arm(cost, result="decided", seconds=1.0, agents=None):
    return {"cost": cost, "result": result, "seconds": seconds, "answer": {"agents": agents} if agents else None}


def report():
    rows = [
        {"item_id": "F6-75", "family": "F6", "truth": {"required": [10, 10]},          # 75 % 3 = 0: P 3, q* 2/3
         "arms": {"routed_composition": _arm(20.0, agents=[10, 10]), "forecast_alone": _arm(25.0, agents=[12, 13]),
                  "weekly_mean_then_staff": _arm(18.0, agents=[9, 9])}},
        {"item_id": "F6-76", "family": "F6", "truth": {"required": [10, 10]},          # P 10, q* 0.9
         "arms": {"routed_composition": _arm(30.0, seconds=3.0, agents=[9, 10]),
                  "forecast_alone": _arm(None, result="no_decision"),
                  "weekly_mean_then_staff": _arm(40.0, agents=[8, 8])}},
    ]
    return {"source_commit": "abc", "heldout": rows,
            "summary": {"F6": {"best_constituent": "forecast_alone"}, "VPL_v3": {}}}


def test_metrics_compare_routed_with_the_best_constituent_and_the_hindsight_best_arm():
    m = M.metrics(report())["families"]["F6"]
    assert m["cost_delta"] == {"absolute": -5.0, "relative": -0.2, "paired_items": 1}
    assert m["routing_regret"] == {"mean": 1.0, "total": 2.0, "items_with_zero_regret": 1, "items": 2}
    assert m["abstention_delta"] == -1 and m["false_answer_delta"] == 0
    cal = m["calibration"]["routed_composition"]
    assert cal["0.666667"]["covered"] == 1.0 and cal["0.9"]["covered"] == 0.5
    assert M.metrics(report())["role"] == "reported metrics, never a verdict"


def test_families_without_per_item_costs_are_skipped_not_invented():
    r = report()
    r["summary"]["F1"] = {"best_constituent": "x"}
    assert "F1" not in M.metrics(r)["families"]
