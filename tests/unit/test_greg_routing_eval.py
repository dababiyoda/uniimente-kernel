"""The frozen shadow-versus-static comparison is reproducible, tamper-refusing and honest about loss."""
from __future__ import annotations

import json

import pytest

pytest.importorskip("z3")
pytest.importorskip("ortools")

from greg.cognition import routing_eval  # noqa: E402
from greg.cognition.contracts import digest  # noqa: E402

EVIDENCE = routing_eval.ROOT / "tests" / "evidence" / "greg-shadow-vs-static-v0.1"


def test_the_committed_freeze_matches_the_generator_and_a_changed_suite_is_refused(monkeypatch):
    frozen = json.loads((EVIDENCE / "freeze.json").read_text())
    assert digest(routing_eval.suite(frozen["seed"])) == frozen["suite_digest"]
    assert routing_eval.suite(frozen["seed"]) == routing_eval.suite(frozen["seed"])
    with pytest.raises(ValueError, match="does not match its freeze"):
        routing_eval.run({**frozen, "suite_digest": "sha256:" + "0" * 64})


def test_the_recorded_result_is_bound_to_its_freeze_and_reports_no_gain():
    frozen = json.loads((EVIDENCE / "freeze.json").read_text())
    result = json.loads((EVIDENCE / "results.json").read_text())
    assert result["freeze_digest"] == digest(frozen) and result["suite_digest"] == frozen["suite_digest"]
    assert result["verdict"] == "NO_GAIN" and result["policies_differ_on"] == 0 and result["hard_failures"] == 0
    assert len(result["rows"]) == result["n"] == frozen["items"]["heldout"]


def test_truth_is_brute_force_and_a_wrong_or_unoptimal_answer_costs_the_full_loss():
    item = routing_eval.suite(20261014)["development"][0]
    truth = item["truth"]
    good = {"abstention_state": "NONE", "latency": 0.5,
            "output": {"answer": {"feasible": truth["feasible"], "objective": truth["objective"], "optimal": True}}}
    assert routing_eval.correct(item, good) and routing_eval.loss(item, good) == pytest.approx(0.1)
    wrong = json.loads(json.dumps(good)); wrong["output"]["answer"]["feasible"] = not truth["feasible"]
    assert routing_eval.loss(item, wrong) == 1.0
    assert routing_eval.loss(item, {**good, "abstention_state": "ABSTAIN"}) == 1.0
    opt = next(i for i in routing_eval.suite(20261014)["heldout"] if i["kind"] == "optimize" and i["truth"]["feasible"])
    stated = {"abstention_state": "NONE", "latency": 0.2,
              "output": {"answer": {"feasible": True, "objective": opt["truth"]["objective"] + 1, "optimal": True}}}
    assert routing_eval.loss(opt, stated) == 1.0, "a wrong value stated as optimal is a full loss"
    slow = {**good, "latency": 60}
    assert routing_eval.correct(item, slow) and routing_eval.loss(item, slow) == 1.0, "latency is capped at 5 s"
