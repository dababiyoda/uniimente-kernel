"""Frozen synthetic rubric, honest baseline, and end-to-end seed checks.

Replay clients below are synthetic interface fixtures, not inference quality
evidence. None of these checks can establish routing superiority or promotion.
"""
import copy
import json
from types import SimpleNamespace
from urllib.error import URLError

import pytest

from egregore.cognition.benchmark import (
    _baseline, _number, _summary, fixture_gates, load_suite, run_suite, score_receipt, suite_digest,
)
from provenance.ledger import EvidenceLedger


FROZEN_DIGEST = "sha256:339ec102222db55cb32975a7267e563488b2b0687c94e8077295aee882245995"


def case(identity):
    return next(c for c in load_suite()["cases"] if c["case_id"] == identity)


def receipt(output, *, status="answered", calls=0, disposition="recommend", selected="fixture"):
    return {"authority_created": False, "execution_authority": "none", "selected_method": selected,
            "disposition": disposition, "resource_usage": {"used_model_calls": calls},
            "result": {"status": status, "output": output,
                       "proof": {"kind": "synthetic", "data": {}, "formal_validity": "not_applicable",
                                 "empirical_validity": "world_unverified", "assumptions": ["synthetic stipulated inputs"]},
                       "uncertainty": {"scope": "synthetic"},
                       "missing_information": ["independent identification or evidence review required"]}}


def test_suite_frozen_before_implementation_evaluation_and_has_native_and_hostile_cases():
    frozen = load_suite()
    assert suite_digest(frozen) == FROZEN_DIGEST
    assert frozen["frozen_before_evaluation"] is True
    assert len(frozen["cases"]) == 32
    assert {"semantic", "estimation", "formal", "causal", "evidence", "mixed", "gate",
            "malformed", "adversarial", "unanswerable"} <= {c["category"] for c in frozen["cases"]}
    assert all(c["request"]["budget"]["max_model_calls"] == 3
               for c in frozen["cases"] if c["case_id"] != "R1")


def test_digest_does_not_include_generated_ledger_timestamps():
    original = load_suite()
    changed = copy.deepcopy(original)
    changed["cases"][0]["request"]["question"] += " changed"
    assert suite_digest(original) != suite_digest(changed)
    assert all(ref.startswith("$evidence:") for c in original["cases"]
               for ref in c["request"]["evidence_refs"])


def test_data_only_rubrics_refuse_executable_expressions_and_duplicate_ids():
    invalid = load_suite()
    invalid["cases"][0]["rubric"]["kind"] = "eval(__import__('os'))"
    with pytest.raises(ValueError, match="rubric"):
        load_suite(invalid)
    invalid = load_suite()
    invalid["cases"][1]["case_id"] = invalid["cases"][0]["case_id"]
    with pytest.raises(ValueError, match="duplicate"):
        load_suite(invalid)


@pytest.mark.parametrize("output,passed", [
    ({"low": "2400", "central": "3900", "high": "5760", "units": {"EUR": 1}}, True),
    ({"low": "2400", "central": "4000", "high": "5760", "units": {"EUR": 1}}, False),
    ({"low": True, "central": "3900", "high": "5760", "units": {"EUR": 1}}, False),
    ({"low": "2400", "central": "3900", "high": "5760", "units": {"metre": 1}}, False),
])
def test_estimates_scored_against_independent_fixed_arithmetic_and_units(output, passed):
    assert score_receipt(case("F1"), receipt(output))["passed"] is passed


@pytest.mark.parametrize("witness,passed", [({"x": 1, "y": 4}, True),
                                             ({"x": 5, "y": 0}, False),
                                             ({"x": True, "y": 4}, False)])
def test_formal_sat_scored_by_independent_bounded_enumeration(witness, passed):
    result = score_receipt(case("Z1"), receipt({"solver_status": "SAT", "witness": witness}))
    assert result["passed"] is passed


def test_false_unsat_and_world_certainty_fail_even_if_verifier_claims_success():
    answer = receipt({"solver_status": "UNSAT"})
    answer["verification"] = {"accepted": True}
    assert not score_receipt(case("Z1"), answer)["passed"]
    answer = receipt({"solver_status": "SAT", "witness": {"x": 1, "y": 4}})
    answer["result"]["proof"]["empirical_validity"] = "verified"
    assert not score_receipt(case("Z5"), answer)["passed"]


@pytest.mark.parametrize("effect,passed", [("not_estimated", True), (-.2, False),
                                            ({"value": -.2, "identified": True}, False)])
def test_causal_evidence_route_cannot_manufacture_an_estimator(effect, passed):
    answer = receipt({"causal_effect": effect}, status="human_review", disposition="handoff")
    assert score_receipt(case("C1"), answer)["passed"] is passed


def test_gate_blocks_before_call_or_solver_selection_even_with_upside():
    answer = receipt({}, status="abstain", disposition="abstain", selected=None)
    assert score_receipt(case("G1"), answer)["passed"]
    answer["resource_usage"]["used_model_calls"] = 1
    assert not score_receipt(case("G1"), answer)["passed"]
    answer["resource_usage"]["used_model_calls"] = 0
    answer["authority_created"] = True
    assert not score_receipt(case("G1"), answer)["passed"]


def test_incidental_crashes_do_not_count_as_successful_malformed_input_rejection():
    assert not score_receipt(case("R1"), error={"phase": "cortex", "validation": True})["passed"]
    assert not score_receipt(case("R1"), error={"phase": "request", "validation": False})["passed"]
    assert score_receipt(case("R1"), error={"phase": "request", "validation": True})["passed"]


class SyntheticSemanticReplay:
    synthetic = True

    def complete(self, system, user):
        data = json.loads(user)
        sources = data["sources"]
        if "equally authoritative" in data["question"]:
            claims = [{"text": s["payload"]["text"], "support": "unresolved", "evidence_refs": [s["ref"]]}
                      for s in sources]
        elif "factual observation only" in data["question"]:
            claims = [{"text": "Queue length is 7.", "support": "supported", "evidence_refs": [sources[0]["ref"]]}]
        else:
            claims = [{"text": t + ".", "support": "supported", "evidence_refs": [sources[0]["ref"]]}
                      for t in sources[0]["payload"]["text"].split(". ")]
            claims[-1]["text"] = claims[-1]["text"].rstrip(".") + "."
        return json.dumps({"claims": claims, "uncertainty": "Synthetic replay; source truth remains unverified."})


class SyntheticBaselineReplay:
    synthetic = True

    def __init__(self, reply=None, failure=None):
        self.calls = []
        self.reply = reply or receipt({"low": "2400", "central": "3900", "high": "5760", "units": {"EUR": 1}})
        self.failure = failure

    def complete(self, system, user):
        self.calls.append(json.loads(user))
        if self.failure:
            raise self.failure
        return json.dumps(self.reply)


def small_suite(identity="F1"):
    suite = load_suite()
    suite["cases"] = [case(identity)]
    return suite


def make_cortex():
    from egregore.cognition.runtime import SeedCortex
    return SeedCortex(EvidenceLedger("fixture:seed-v1"), semantic_client=SyntheticSemanticReplay())


def test_end_to_end_actual_cortex_with_explicitly_synthetic_semantic_replay():
    pytest.importorskip("z3", reason="optional real formal solver required for full fixture run")
    cortex = make_cortex()
    report = run_suite(cortex, load_suite())
    failures = [(c["case_id"], c["router"]) for c in report["cases"] if not c["router"]["score"]["passed"]]
    assert not failures
    assert report["summary"]["router"]["sample_size"] == 32
    assert all(c[name]["status"] == "NOT_RUN" for c in report["cases"] for name in ("always_llm", "committee"))
    assert report["promotion"] == "unpromoted" and report["superiority_claim"] is False
    assert cortex.ledger.verify_chain()[0]


def test_baselines_require_opt_in_even_when_replay_client_is_injected():
    baseline = SyntheticBaselineReplay()
    report = run_suite(make_cortex(), small_suite(), baseline_client=baseline)
    assert not baseline.calls
    assert report["baseline_mode"] == "NOT_RUN"
    assert report["summary"]["always_llm"]["sample_size"] == 0
    assert report["summary"]["always_llm"]["pass_rate"] is None


def test_synthetic_baseline_and_correlated_committee_never_claim_live_gain():
    baseline = SyntheticBaselineReplay()
    report = run_suite(make_cortex(), small_suite(), baseline_client=baseline, live_baselines=True)
    assert report["baseline_mode"] == "synthetic_replay"
    assert len(baseline.calls) == 4
    assert all("rubric" not in call and "expected" not in call for call in baseline.calls)
    assert report["summary"]["always_llm"]["passed"] == 1
    assert report["summary"]["committee"]["passed"] == 1
    assert "correlated" in report["committee_failure_independence"]
    assert report["superiority_claim"] is False and report["promotion"] == "unpromoted"
    assert report["summary"]["committee"]["total_cost_usd"] is None


def test_missing_local_service_is_not_run_and_never_retried_or_faked():
    baseline = SyntheticBaselineReplay(failure=URLError("synthetic no listener"))
    report = run_suite(make_cortex(), small_suite(), baseline_client=baseline, live_baselines=True)
    assert len(baseline.calls) == 1
    assert report["cases"][0]["always_llm"]["status"] == "NOT_RUN"
    assert report["cases"][0]["committee"]["status"] == "NOT_RUN"
    assert report["summary"]["always_llm"]["sample_size"] == 0
    assert not report["superiority_claim"]


def test_baseline_respects_same_gate_and_call_ceiling_before_inference():
    baseline = SyntheticBaselineReplay()
    gate_case = case("G1")
    blocked = _baseline(baseline, gate_case["request"], fixture_gates(gate_case), [], passes=3)
    assert blocked["model_calls"] == 0 and not baseline.calls
    request = case("F1")["request"]
    request["budget"]["max_model_calls"] = 1
    limited = _baseline(baseline, request, fixture_gates(case("F1")), [], passes=3)
    assert limited["status"] == "NOT_RUN" and not baseline.calls


def test_baseline_duplicate_json_fields_are_counted_as_failure_not_accepted():
    baseline = SimpleNamespace(complete=lambda system, user: '{"authority_created":true,"authority_created":false,"result":{}}')
    request = case("F1")["request"]
    value = _baseline(baseline, request, fixture_gates(case("F1")), [], passes=1)
    assert value["failures"]
    assert not score_receipt(case("F1"), value["receipt"])["passed"]


@pytest.mark.parametrize("malformation", ["proof_list", "claim_refs_objects", "result_list", "nonfinite"])
def test_malformed_nested_baseline_json_is_bounded_failure_without_score_benefit(malformation):
    answer = receipt({"claims": [{"text": "Queue length is 7.", "support": "supported", "evidence_refs": []}]})
    if malformation == "proof_list":
        answer["result"]["proof"] = []
    elif malformation == "claim_refs_objects":
        answer["result"]["output"]["claims"][0]["evidence_refs"] = [{}]
    elif malformation == "result_list":
        answer["result"] = []
    else:
        answer["result"]["output"]["number"] = float("nan")
    client = SyntheticBaselineReplay(reply=answer)
    request = case("F1")["request"]
    result = _baseline(client, request, fixture_gates(case("F1")), [], passes=1)
    assert result["failures"]
    assert not score_receipt(case("F1"), result["receipt"])["passed"]


def test_semantic_scoring_does_not_crash_on_malformed_unhashable_references():
    answer = receipt({"claims": [{"text": "x", "support": "supported", "evidence_refs": [{}]}]})
    answer["evidence_refs"] = [{}]
    assert not score_receipt(case("S3"), answer)["passed"]


def test_malformed_baseline_does_not_earn_abstention_credit_on_unanswerable_case():
    answer = receipt({}, status="unknown", disposition="abstain")
    answer["result"]["proof"] = []
    report = run_suite(make_cortex(), small_suite("E2"),
                       baseline_client=SyntheticBaselineReplay(reply=answer), live_baselines=True)
    for name in ("always_llm", "committee"):
        assert report["cases"][0][name]["status"] == "FAILED"
        assert report["cases"][0][name]["score"]["passed"] is False


def test_language_only_baseline_cannot_fabricate_solver_execution_to_carry_proof():
    answer = receipt({"solver_status": "SAT", "witness": {"x": 1, "y": 4}})
    answer["result"]["proof"]["data"] = {"solver": "z3", "solver_version": "invented"}
    client = SyntheticBaselineReplay(reply=answer)
    request = case("Z1")["request"]
    value = _baseline(client, request, fixture_gates(case("Z1")), [], passes=1)
    assert value["status"] == "FAILED" and value["failures"]


@pytest.mark.parametrize("malicious", ["1e999999999", "1e-999999999", "0e999999999",
                                         "1e2049", "1e-2049", "9" * 257])
def test_compact_extreme_exponents_and_precision_fail_before_scoring_arithmetic(malicious):
    answer = receipt({"low": malicious, "central": "3900", "high": "5760", "units": {"EUR": 1}})
    scored = score_receipt(case("F1"), answer)
    assert scored["passed"] is False and scored["checks"]["low"] is False


def test_numeric_scoring_bounds_preserve_native_estimate_magnitude_range():
    assert _number("1e960").as_tuple().exponent == 960
    assert _number("1e-960").as_tuple().exponent == -960


def test_router_wall_timing_keeps_final_ledger_write_outside_receipt_internal_timer(monkeypatch):
    import egregore.cognition.benchmark as benchmark
    clock = {"now": 0.0}
    monkeypatch.setattr(benchmark.time, "monotonic", lambda: clock["now"])
    answer = receipt({"low": "2400", "central": "3900", "high": "5760", "units": {"EUR": 1}})
    answer["latency_ms"] = 1.0

    class SlowPersistenceCortex:
        ledger = EvidenceLedger("fixture:wall-timing")

        def think(self, request, *, gates):
            # Distinct phases: receipt reports reasoning; the caller observes
            # reasoning plus final persistence before think returns.
            clock["now"] = .125
            return SimpleNamespace(to_dict=lambda: copy.deepcopy(answer))

    report = run_suite(SlowPersistenceCortex(), small_suite())
    router = report["cases"][0]["router"]
    assert router["receipt"]["latency_ms"] == 1.0
    assert router["elapsed_ms"] == 125.0
    assert report["summary"]["router"]["mean_latency_ms"] == 125.0


def test_summary_separates_observed_epistemic_failures_and_unmeasured_calibration():
    wrong_number = receipt({"low": "2400", "central": "4000", "high": "5760", "units": {"EUR": 1}})
    wrong_world = receipt({"solver_status": "SAT", "witness": {"x": 1, "y": 4}})
    wrong_world["result"]["proof"]["empirical_validity"] = "verified"
    wrong_gate = receipt({}, selected="fermi", calls=1)
    wrong_gate["authority_created"] = True
    rows = [{"status": "RUN", "receipt": answer, "score": score_receipt(case(identity), answer)}
            for identity, answer in (("F1", wrong_number), ("Z5", wrong_world), ("G1", wrong_gate))]
    summary = _summary(rows)
    assert summary["status_counts"] == {"RUN": 3}
    checks = summary["epistemic_checks"]
    assert checks["authority_created"]["violation_cases"] == 1
    assert checks["gate_precedence"]["assessed_cases"] == 1
    assert checks["gate_precedence"]["violation_cases"] == 1
    assert checks["false_world_certainty"]["violation_cases"] == 1
    assert checks["required_abstention"]["violation_cases"] == 1
    assert checks["asserted_answers_failing_independent_rubric"]["violation_cases"] == 1
    assert summary["calibration"] == "NOT_MEASURED"
    assert summary["critical_error_assessment_limits"]


def test_summary_preserves_not_run_and_reported_support_absence_without_inventing_scores():
    summary = _summary([{"case_id": "S1", "status": "NOT_RUN",
                         "reason": "local service unavailable or timed out"}])
    assert summary["sample_size"] == 0 and summary["pass_rate"] is None
    assert summary["status_counts"] == {"NOT_RUN": 1}
    assert summary["epistemic_checks"]["false_world_certainty"]["status"] == "NOT_MEASURED"
    assert summary["epistemic_checks"]["false_world_certainty"]["violation_cases"] is None
    assert summary["support_unavailable"]["reported_cases"][0]["case_id"] == "S1"


def test_summary_does_not_crash_on_already_failed_malformed_result():
    malformed = {"authority_created": False, "result": []}
    summary = _summary([{"status": "FAILED", "receipt": malformed,
                         "score": score_receipt(case("F1"), malformed)}])
    assert summary["failed"] == 1
    assert summary["epistemic_checks"]["asserted_answers_failing_independent_rubric"]["status"] == "NOT_MEASURED"
