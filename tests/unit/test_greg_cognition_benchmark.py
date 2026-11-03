"""The competency characterization measures; it does not describe.

Every dimension of every method carries a number from a native workload, or says why it does not
apply, or names what would measure it. The error-correction workload corrupts one leaf of each
verified answer and counts what the independent falsifier catches, so a weakened falsifier shows
up as a lower rate, not as unchanged prose.
"""
from __future__ import annotations

import json

import pytest

from greg.cognition import benchmark, verification
from greg.cognition.cortex import reason, registry_view
from greg.templates import venture_assessment

SUITE = json.loads(benchmark.SUITE.read_text())
CASES = {case["id"]: case for case in SUITE["cases"]}
WITH_TEETH = ("causal", "collective", "control", "estimation", "exact", "formal", "game", "graph", "information",
              "micro", "optimization", "pattern", "probabilistic", "search", "sequential", "simulation")


@pytest.fixture(scope="module")
def report():
    return benchmark.assess()


def test_every_method_carries_every_dimension_with_a_number_or_an_explicit_reason(report):
    ch = report["characterization"]
    assert ch["dimensions"] == list(benchmark.DIMENSIONS) and len(ch["methods"]) >= 17
    for method, dims in ch["methods"].items():
        assert set(dims) == set(benchmark.DIMENSIONS), method
        for name, dim in dims.items():
            assert dim["status"] in benchmark.STATUSES, (method, name)
            if dim["status"] == "measured":
                assert dim["value"] is not None and dim["workload"], (method, name)
            else:
                assert dim["value"] is None and dim["reason"], (method, name)
            if dim["status"] == "not_measured_here":
                assert dim["would_measure"], (method, name)
    summary = ch["summary"]
    assert summary["methods"] == len(ch["methods"])
    assert sum(summary[s] for s in benchmark.STATUSES) == len(ch["methods"]) * len(benchmark.DIMENSIONS)
    assert report["correct"] == report["total"] == len(SUITE["cases"])      # the CI fields stay


def test_the_falsifier_catches_every_single_leaf_corruption_where_it_has_teeth(report):
    methods = report["characterization"]["methods"]
    for family in WITH_TEETH:
        dim = methods["cognition." + family]["error_correction"]
        assert dim["status"] == "measured", family
        assert dim["value"]["detection_rate"] == 1.0 and dim["value"]["undetected_fields"] == [], (family, dim["value"])
        assert dim["value"]["perturbations"] >= 1
    semantic = methods["cognition.semantic"]["error_correction"]
    assert semantic["status"] == "not_measured_here" and "no structurally verified answer" in semantic["reason"]


def test_a_weakened_falsifier_lowers_the_measured_rate_instead_of_the_prose(monkeypatch):
    receipt = reason(CASES["bounded:pid"]["request"], registry=registry_view())
    assert receipt["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED"
    trials = benchmark.perturbation_trials("control", CASES["bounded:pid"]["request"]["data"], receipt)
    assert trials and all(t["outcome"] == "refuted" for t in trials)
    typed_only = {"verdict": "STRUCTURALLY_VERIFIED", "checks": {"typed_artifact": True}, "dissent": []}
    monkeypatch.setattr(benchmark, "verify", lambda *a, **k: typed_only)
    weak = benchmark.perturbation_trials("control", CASES["bounded:pid"]["request"]["data"], receipt)
    assert [t["field"] for t in weak] == [t["field"] for t in trials]
    assert all(t["outcome"] == "accepted" for t in weak)
    rate = benchmark._error_correction("control", {"bounded:pid": CASES["bounded:pid"]}, [{**receipt, "_case": "bounded:pid"}])
    assert rate["status"] == "measured" and rate["value"]["detection_rate"] == 0.0
    assert rate["value"]["undetected_fields"] == sorted(t["field"] for t in trials)


def test_perturbations_corrupt_exactly_one_leaf_each_and_name_it():
    output = {"n": 3, "ok": True, "ratio": "3/10", "name": "stimulate", "rows": [[1, "2"]], "empty": {}}
    trials = dict(("".join(map(str, path)) if isinstance(path, str) else ".".join(map(str, path)), changed)
                  for path, changed in benchmark.perturbations(output))
    assert set(trials) == {"n", "ok", "ratio", "name", "rows.0.0", "rows.0.1"}
    assert trials["n"]["n"] == 3 + benchmark.LARGE and trials["n"]["ok"] is True
    assert trials["ok"]["ok"] is False
    assert trials["ratio"]["ratio"] == str(benchmark.Fraction("3/10") + benchmark.LARGE)
    assert trials["name"]["name"] == "stimulate~"
    assert trials["rows.0.1"]["rows"] == [[1, str(2 + benchmark.LARGE)]] and trials["rows.0.1"]["n"] == 3
    assert output == {"n": 3, "ok": True, "ratio": "3/10", "name": "stimulate", "rows": [[1, "2"]], "empty": {}}


@pytest.mark.parametrize("case_id, family, field, bad", [
    ("bounded:polynomial", "exact", "factored", "(x - 3)*(x + 2)"),
    ("bounded:estimate", "estimation", "high", 29),
    ("bounded:treatment_effect", "causal", "effect", 0.25),
    ("bounded:pid", "control", "correction", 16),
    ("bounded:value_of_information", "information", "acquire", False),
    ("bounded:simulate", "simulation", "mean", 1.5),
    ("bounded:anomalies", "pattern", "anomalies", [4]),
    ("bounded:setpoint", "micro", "state", "abstain"),
    ("bounded:mdp", "sequential", "policy", {"s": "stay~"}),
    ("bounded:quorum", "collective", "quorum_crossed", False),
])
def test_the_new_exact_rechecks_refute_a_plausible_wrong_answer_and_pass_the_right_one(case_id, family, field, bad):
    data = CASES[case_id]["request"]["data"]
    receipt = reason(CASES[case_id]["request"], registry=registry_view())
    assert receipt["abstention_state"] == "NONE" and receipt["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED"
    answer = {"output": receipt["output"], "proof": receipt["proof_artifact"]}
    assert verification.verify(family, data, answer, receipt["proof_type"])["verdict"] == "STRUCTURALLY_VERIFIED"
    wrong = {"output": {**receipt["output"], field: bad}, "proof": receipt["proof_artifact"]}
    result = verification.verify(family, data, wrong, receipt["proof_type"])
    assert result["verdict"] == "REFUTED", result["checks"]
    assert not all(result["checks"].values())


def test_an_unknown_solver_status_with_no_solution_is_refuted():
    data = CASES["bounded:constraints"]["request"]["data"]
    receipt = reason(CASES["bounded:constraints"]["request"], registry=registry_view())
    proof = receipt["proof_artifact"]
    for status, solution in (("UNSAT", {}), ("UNKNOWN", {})):
        verdict = verification.verify("formal", data, {"output": {"solver_status": status, "solution": solution}, "proof": proof},
                                      receipt["proof_type"])["verdict"]
        assert verdict == "STRUCTURALLY_VERIFIED", status
    for status, solution in (("SAT~", {}), ("UNSAT", {"x": "3"}), ("DONE", {})):
        verdict = verification.verify("formal", data, {"output": {"solver_status": status, "solution": solution}, "proof": proof},
                                      receipt["proof_type"])["verdict"]
        assert verdict == "REFUTED", status


def test_higher_scale_consumers_match_what_the_venture_template_actually_asks(tmp_path):
    from tests.unit import test_greg_ventures as vt
    root = tmp_path / "data"
    rs, wmi, signal = root / "railscout", root / "wmi", root / "signal"
    vt._write(rs / "railscout" / "__init__.py", "")
    vt._write(rs / "railscout" / "appraise.py", vt.RAILSCOUT_STUB)
    vt._write(wmi / "src" / "services" / "opportunity_intake.py", vt.WMI_STUB)
    organs = {"railscout_root": str(rs), "wmi_root": str(wmi), "manifest": str(vt._manifest(signal)),
              "source_root": str(signal)}
    spec = venture_assessment(**organs, economics=vt.ECONOMICS)
    asked = {step["params"]["operation"] for step in spec["strategies"] if step.get("capability") == "cognition.solve"}
    assert asked == set(benchmark.HIGHER_SCALE_CONSUMERS)
    assert all("venture.assess" in benchmark.HIGHER_SCALE_CONSUMERS[op] for op in asked)
    plain = venture_assessment(**organs)
    assert not any(step.get("capability") == "cognition.solve" for step in plain["strategies"])


def test_generalization_is_reported_for_the_cortex_arm_from_the_frozen_evidence_and_never_for_a_family(report, tmp_path):
    methods = report["characterization"]["methods"]
    cortex = methods["cognition.cortex"]["generalization"]
    assert cortex["status"] == "measured" and cortex["value"]["verdict"] == "GAIN_VERIFIED_AGAINST_RUN_BASELINES"
    strata = cortex["value"]["by_stratum"]
    assert set(strata) == {"causal", "estimation", "formal", "mixed_abstention", "scheduling_optimization", "semantic_strategy"}
    for row in strata.values():
        assert row["gap_heldout_minus_selection"] == pytest.approx(row["heldout_mean_loss"] - row["selection_mean_loss"])
        assert row["heldout_n"] == 200 and row["selection_n"] == 6
    assert "not_run" in cortex["value"] and "claim_limit" in cortex
    assert methods["cognition.cortex"]["responsiveness"]["value"]["n"] == 1200
    assert methods["cognition.formal"]["generalization"]["status"] == "not_measured_here"
    absent = benchmark.characterize_cortex(benchmark.cortex_evidence(tmp_path))
    assert absent["generalization"]["status"] == "not_measured_here" and "absent" in absent["generalization"]["reason"]


def test_adaptability_and_memory_depth_are_computed_from_the_candidate_rows(report):
    methods = report["characterization"]["methods"]
    exact = methods["cognition.exact"]
    assert exact["memory_depth"]["value"] == {"settled_outcomes_consulted": 0, "journal_supplied": False,
                                              "forgetting": "none; competence is recomputed by full replay of the canonical journal"}
    assert exact["adaptability"]["value"]["eligible_alternatives"] == 0
    assert exact["adaptability"]["value"]["selection_can_change"] is False
    assert benchmark.refutations_to_demote({"quality": 0.5, "evidence": 0}, []) is None
    # Equal priors: one settled refutation drops 1/2 to 1/3, below a rival still at 1/2.
    assert benchmark.refutations_to_demote({"quality": 0.5, "evidence": 0}, [{"quality": 0.5}]) == 1
    # Four verified outcomes (5/6) survive two refutations against a rival at 1/2 and fall on the third... 5/8 > 1/2, 5/9 > 1/2, 5/10 = 1/2 not below.
    assert benchmark.refutations_to_demote({"quality": 5 / 6, "evidence": 4}, [{"quality": 0.5}]) == 5
    assert methods["cognition.simulation"]["prediction_horizon"]["value"]["max_declared_steps"] == 2
    assert methods["cognition.sequential"]["prediction_horizon"]["value"]["fields"] == ["horizon"]
    assert methods["cognition.exact"]["prediction_horizon"]["status"] == "not_applicable"
    assert methods["cognition.exact"]["persistence"]["status"] == "not_applicable"
    assert methods["cognition.exact"]["persistence"]["measured_at_body_scale_by"] == list(benchmark.PERSISTENCE_EVIDENCE)


def test_quantile_interpolates_and_a_single_value_is_every_quantile():
    assert benchmark.quantile([], .5) is None
    assert benchmark.quantile([3.0], .95) == 3.0
    assert benchmark.quantile([1.0, 2.0, 3.0, 4.0, 5.0], .5) == 3.0
    assert benchmark.quantile([1.0, 2.0, 3.0, 4.0, 5.0], .95) == pytest.approx(4.8)


def test_moment_consistency_alone_catches_a_corrupted_mean_when_the_proof_truncates_the_scenarios():
    request = {"problem_id": "sim:large", "operation": "simulate",
               "data": {"seed": 7, "samples": 200, "steps": 2, "step_probability": 0.5}}
    receipt = reason(request, registry=registry_view())
    assert receipt["abstention_state"] == "NONE" and len(receipt["proof_artifact"]["scenarios"]) == 100 < 200
    good = verification.verify("simulation", request["data"], {"output": receipt["output"], "proof": receipt["proof_artifact"]},
                               receipt["proof_type"])
    assert good["verdict"] == "STRUCTURALLY_VERIFIED" and "moments_recomputed" not in good["checks"]
    for field, bad in (("mean", 3.0), ("minimum", 2.5), ("maximum", -1), ("mean", 1.0005)):
        wrong = {"output": {**receipt["output"], field: bad}, "proof": receipt["proof_artifact"]}
        assert verification.verify("simulation", request["data"], wrong, receipt["proof_type"])["verdict"] == "REFUTED", (field, bad)


def test_a_valid_but_non_maximizing_policy_is_refuted_even_when_the_values_are_right():
    request = {"problem_id": "mdp:two-actions", "operation": "mdp",
               "data": {"transitions": {"s": {"stay": {"s": 1}, "leave": {"s": 1}}},
                        "rewards": {"s": {"stay": 2, "leave": 1}}, "horizon": 3}}
    receipt = reason(request, registry=registry_view())
    assert receipt["abstention_state"] == "NONE" and receipt["output"] == {"values": {"s": 6.0}, "policy": {"s": "stay"}}
    wrong = {"output": {"values": {"s": 6.0}, "policy": {"s": "leave"}}, "proof": receipt["proof_artifact"]}
    result = verification.verify("sequential", request["data"], wrong, receipt["proof_type"])
    assert result["verdict"] == "REFUTED" and result["checks"]["backward_induction_values"] is True
    assert result["checks"]["policy_maximizes"] is False
