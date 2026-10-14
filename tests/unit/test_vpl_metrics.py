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


def _rows(family, arms_per_item):
    return [{"item_id": f"{family}-{i}", "family": family, "truth": {}, "arms": arms}
            for i, arms in enumerate(arms_per_item)]


def _res(result, seconds=1.0):
    return {"result": result, "seconds": seconds}


def test_accounting_reports_latency_without_inventing_a_netting_rule_and_flags_a_degenerate_static_arm():
    rows = _rows("F3", [{"routed_composition": _res("correct", 2.0), "best": _res("suboptimal", 0.5),
                         "static_composition": _res("no_decision", 0.0)} for _ in range(6)])
    run = {"source_commit": "x", "heldout": rows,
           "summary": {"F3": {"best_constituent": "best", "lift": True}, "VPL_v2": {}}}
    acc = M.accounting([run])
    f3 = acc["families"]["F3"]
    assert f3["latency"] == {"routed_median_s": 2.0, "best_constituent_median_s": 0.5, "ratio": 4.0, "added_s": 1.5}
    assert acc["latency_sensitivity"]["lifts_within_multiplier_of_best_constituent_median"] == {
        "1x": [], "1.5x": [], "2x": [], "5x": ["F3"]}
    assert f3["routed_vs_static"]["static_arm"] == "DEGENERATE" and f3["routed_vs_static"]["identical_answers"] == 0
    assert acc["routing_beyond_static"]["families_where_static_is_degenerate"] == ["F3"]
    assert acc["label"].startswith("POST_HOC")


def test_f7_counts_an_optimal_answer_as_correct_and_names_its_practitioners():
    rows = _rows("F7", [{"routed_composition": _res("optimal", 1.2), "graph_alone_greedy": _res(r, 0.2),
                         "static_composition": _res("optimal", 1.2), "shortest_path_upgrade": _res(r, 0.0),
                         "parametric_min_cost_flow": _res("optimal", 0.0)}
                        for r in ("suboptimal", "suboptimal", "optimal")])
    run = {"source_commit": "x", "heldout": rows,
           "summary": {"F7": {"best_constituent": "graph_alone_greedy", "lift": True}, "VPL_v4": {}}}
    f7 = M.accounting([run])["families"]["F7"]
    assert f7["routed_vs_static"]["static_arm"] == "DECIDES"
    assert f7["practitioner"]["shortest_path_upgrade"]["wins"] == 2
    assert f7["practitioner"]["parametric_min_cost_flow"] == {"wins": 0, "losses": 0, "ties": 3,
                                                              "sign_test_p_one_sided": 1.0}


def test_accounting_on_the_frozen_runs_matches_their_recorded_verdicts():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "docs/evidence/greg-composition-lift"
    reports = [json.loads((root / p).read_text()) for p in
               ("2026-10-07/results.json", "2026-10-08/results-v2.json", "2026-10-14-v3/results-v3.json")]
    acc = M.accounting(reports)
    assert acc["frozen_vpl"]["families_with_lift"] == ["F1", "F2R", "F3", "F4", "F6"]
    f6 = acc["families"]["F6"]
    assert f6["routed_vs_static"]["identical_answers"] == 90                   # routing chose the static recipe
    assert f6["practitioner"]["weekly_mean_then_staff"]["wins"] == 40
    assert acc["practitioner_beaten_significantly"]["F6"] == {"weekly_mean_then_staff": False,
                                                              "median_forecast_then_staff": False}
    assert acc["latency_sensitivity"]["lifts_within_multiplier_of_best_constituent_median"]["1x"] == []


def _prereg(**over):
    doc = {"family_id": "F7", "natural": True, "n_heldout": 60, "partition_rule": "last 60 days",
           "data_provenance": {"source": "https://example.org/data.csv", "sha256": "0" * 64, "licence": "CC-BY-4.0"},
           "constituents": ["a", "b"], "static_arm": {"chosen_on": "development", "must_decide": True},
           "routed_arm": {"entry": "chain"}, "compiled_arm": {"entry": "compile"},
           "practitioner_arms": ["moving average"], "cost_metric": "realised cost",
           "latency_rule": {"kind": "multiplier", "value": 2.0}, "rule": "sign test", "alpha": 0.05,
           "declared_before_heldout": True}
    doc.update(over)
    return doc


def test_a_complete_preregistration_passes_and_each_gap_the_frozen_runs_had_is_named():
    assert M.validate_preregistration(_prereg()) == []
    assert any("static_arm" in p for p in M.validate_preregistration(_prereg(static_arm={"chosen_on": "development"})))
    assert any("compiled_arm" in p for p in M.validate_preregistration(_prereg(compiled_arm={"entry": "chain"})))
    assert any("practitioner" in p for p in M.validate_preregistration(_prereg(practitioner_arms=[])))
    assert any("latency_rule" in p for p in M.validate_preregistration(_prereg(latency_rule={"kind": "vibes"})))
    assert any("licence" in p for p in M.validate_preregistration(_prereg(data_provenance={"source": "x"})))
    assert any("before" in p for p in M.validate_preregistration(_prereg(declared_before_heldout=False)))
    assert M.validate_preregistration({"family_id": "F7"})[0].startswith("missing")
