"""Inversion as an executable representation operator (directive section 6): a claim becomes a formal instance."""
from fractions import Fraction

import pytest

pytest.importorskip("z3")

from greg.cognition import compiler  # noqa: E402
from greg.cognition.contracts import CognitionError  # noqa: E402
from greg.cognition.cortex import reason, registry_view  # noqa: E402


@pytest.fixture(autouse=True)
def no_index(tmp_path, monkeypatch):
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")


def check(claim):
    return reason({"problem_id": "inv", "compile": {"geometry": {"geometry": "deductive"}, "data": {"claim": claim}}},
                  registry=registry_view())


BOX = {"x": [0, 10], "y": [0, 10]}
BUDGET = [{"coefficients": {"x": 1, "y": 1}, "op": "<=", "rhs": 10}]


def test_a_true_claim_holds_within_the_model():
    r = check({"variables": BOX, "constraints": BUDGET, "property": {"coefficients": {"x": 1}, "op": "<=", "rhs": 10}})
    assert r["state"] == "ANSWERED" and r["result"]["claim"] == "HOLDS_WITHIN_MODEL"
    assert r["method_or_composition_selected"] == "cognition.formal"
    step = next(t for t in r["transformations"] if t["operator_id"] == "inversion")
    assert step["effect_kind"] == "representation" and step["input_digest"] != step["output_digest"]


def test_a_false_claim_is_refuted_by_a_counterexample_that_violates_it_exactly():
    claim = {"variables": BOX, "constraints": BUDGET, "property": {"coefficients": {"x": 1, "y": 1}, "op": "<=", "rhs": 5}}
    r = check(claim)
    assert r["result"]["claim"] == "REFUTED"
    cx = {k: Fraction(v) for k, v in r["result"]["counterexample"].items()}
    assert cx["x"] + cx["y"] <= 10 and cx["x"] + cx["y"] > 5                   # satisfies the constraints, breaks it


def test_the_negation_is_exact_at_a_strict_boundary():
    # x < 10 on [0, 10] fails only at x = 10 exactly; an epsilon negation (x >= 10 + e) would call it true
    strict = check({"variables": {"x": [0, 10]}, "constraints": [],
                    "property": {"coefficients": {"x": 1}, "op": "<", "rhs": 10}})
    assert strict["result"]["claim"] == "REFUTED" and Fraction(strict["result"]["counterexample"]["x"]) == 10
    loose = check({"variables": {"x": [0, 10]}, "constraints": [],
                   "property": {"coefficients": {"x": 1}, "op": "<=", "rhs": 10}})
    assert loose["result"]["claim"] == "HOLDS_WITHIN_MODEL"


@pytest.mark.parametrize("bad", [
    {"variables": BOX, "constraints": BUDGET},                                       # no property
    {"variables": BOX, "constraints": BUDGET, "property": {"coefficients": {"x": 1}, "op": "~", "rhs": 1}},
    {"variables": BOX, "constraints": BUDGET, "property": {"coefficients": {"x": 1}, "op": "<=", "rhs": 1},
     "extra": True},
])
def test_malformed_claims_are_refused(bad):
    with pytest.raises(CognitionError):
        compiler.invert_claim(bad)


def test_the_independent_core_recheck_accepts_the_exact_strict_negation():
    # The cross-engine unsat-core re-check came from another lineage with only <=, >=, ==, != and crashed the
    # independent verifier (MODEL_INVALID) on every claim that holds; every re-check shares one table now.
    from greg.cognition import verification
    negated = compiler.invert_claim({"variables": {"x": [0, 10]}, "constraints": [],
                                     "property": {"coefficients": {"x": 1}, "op": "<=", "rhs": 10}})
    assert negated["constraints"][-1]["op"] == ">"
    assert verification._z3_core_check(negated, ["constraint_0"])["core_unsat"] is True
    assert all(verification._holds(op, 10, 10) is want for op, want in
               {"<=": True, ">=": True, "==": True, "!=": False, "<": False, ">": False}.items())
