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
    assert r["result"]["premises"] == "SATISFIABLE" and len(r["intermediate_receipts"]) == 2
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
    # review finding 9: these raised TypeError out of reason() instead of being refused
    {"variables": BOX, "constraints": BUDGET, "property": {"coefficients": {"x": 1}, "op": [], "rhs": 1}},
    {"variables": BOX, "constraints": BUDGET, "property": {"coefficients": {"x": 1}, "op": {}, "rhs": 1}},
    {"variables": BOX, "constraints": BUDGET, "property": {"coefficients": [1], "op": "<=", "rhs": 1}},
    {"variables": BOX, "constraints": ["x <= 1"], "property": {"coefficients": {"x": 1}, "op": "<=", "rhs": 1}},
])
def test_malformed_claims_are_refused(bad):
    with pytest.raises(CognitionError):
        compiler.invert_claim(bad)


def test_inconsistent_premises_never_make_a_claim_hold():
    """Review finding 8: x <= 1 and x >= 2 make 'constraints AND NOT property' unsatisfiable for every property,
    so 'x == 100' held 'within the model'. The premises are checked on their own first."""
    r = check({"variables": {"x": [0, 200]},
               "constraints": [{"coefficients": {"x": 1}, "op": "<=", "rhs": 1},
                               {"coefficients": {"x": 1}, "op": ">=", "rhs": 2}],
               "property": {"coefficients": {"x": 1}, "op": "==", "rhs": 100}})
    assert r["state"] == "ANSWERED" and r["result"]["claim"] == "PREMISES_INCONSISTENT"


def test_a_malformed_claim_is_refused_through_the_canonical_path_not_raised_as_a_crash():
    with pytest.raises(CognitionError):
        check({"variables": BOX, "constraints": BUDGET, "property": {"coefficients": {"x": 1}, "op": [], "rhs": 1}})
