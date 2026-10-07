"""Linked correctness regressions for proof jurisdiction and native artifacts."""
from copy import deepcopy
from dataclasses import asdict

import pytest

from greg.cognition.contracts import CognitiveReceipt, CognitionError, ProblemGeometry, ProofArtifact, digest
from greg.cognition.cortex import reason, registry_view
from greg.cognition.settlement import _valid_receipt
from greg.cognition.solvers import causal, exact, fermi, formal, optimization
from greg.cognition.verification import verify


MODEL = {"variables": {"x": [0, 8]}, "constraints": [{"coefficients": {"x": 1}, "op": ">=", "rhs": 3}]}
OPTIMIZATION = {**MODEL, "objective": {"coefficients": {"x": 1}, "sense": "min"}}


@pytest.fixture(scope="module")
def arithmetic_receipt():
    return reason({"problem_id": "boundary:arithmetic", "operation": "calculate", "data": {"expression": "1+1"}}, registry=registry_view())


def receipt_kwargs(receipt):
    return {k: deepcopy(v) for k, v in receipt.items() if k != "receipt_id"}


def test_integer_optimization_rejects_fractional_assignment():
    answer = optimization(deepcopy(OPTIMIZATION), asdict(ProblemGeometry()))
    # Keep the forged objective consistent with the forged assignment; numerical
    # objective checking alone must not hide violation of the integer domain.
    answer["output"]["solution"]["x"] = 3.5
    answer["output"]["objective_value"] = 3.5
    result = verify("optimization", OPTIMIZATION, answer, "optimization_certificate")
    assert result["checks"]["objective_substitution"]
    assert not result["checks"]["integer_domain"]
    assert result["verdict"] == "REFUTED"


@pytest.mark.parametrize("field,value", [("result", {"exact": "999"}), ("expression", "999"), ("variables", {"fake": 7})])
def test_exact_proof_cannot_disagree_with_computation(field, value):
    answer = exact({"expression": "1+1"}, asdict(ProblemGeometry()))
    answer["proof"][field] = value
    assert verify("exact", {"expression": "1+1"}, answer, "exact_calculation")["verdict"] == "REFUTED"


def test_exact_display_result_is_checked_independently():
    answer = exact({"expression": "1+1"}, asdict(ProblemGeometry()))
    answer["output"]["exact"] = "999"
    assert verify("exact", {"expression": "1+1"}, answer, "exact_calculation")["verdict"] == "REFUTED"


@pytest.mark.parametrize("field,value", [("constraints", []), ("objective", {"coefficients": {"x": 1}, "sense": "max"}), ("solver_status", "FEASIBLE"), ("variables", {"x": [0, 100]})])
def test_optimization_artifact_remains_bound_to_source_model(field, value):
    answer = optimization(deepcopy(OPTIMIZATION), asdict(ProblemGeometry()))
    answer["proof"][field] = value
    assert verify("optimization", OPTIMIZATION, answer, "optimization_certificate")["verdict"] == "REFUTED"


def test_estimation_range_artifact_matches_returned_result():
    data = {"factors": [{"name": "n", "low": 2, "central": 3, "high": 4}]}
    answer = fermi(data, {})
    answer["proof"]["range"] = {"low": 20, "central": 30, "high": 40}
    assert verify("estimation", data, answer, "bounded_estimate")["verdict"] == "REFUTED"


def test_causal_artifact_cannot_launder_another_effect():
    data = {"design": "randomized", "treated": [2, 3, 4, 5], "control": [0, 1, 2, 3], "synthetic": True}
    answer = causal(data, {})
    answer["proof"]["estimate"] = 999
    assert verify("causal", data, answer, "causal_identification")["verdict"] == "REFUTED"


def test_receipt_cannot_relabel_arithmetic_as_causal(arithmetic_receipt):
    data = receipt_kwargs(arithmetic_receipt)
    data["proof_type"] = "causal_identification"
    data["proof_artifact"] = {k: None for k in ("dag", "identification_assumptions", "estimand", "estimate", "confounders", "refutations")}
    with pytest.raises(CognitionError, match="method and proof"):
        CognitiveReceipt(**data)


def test_receipt_cannot_relabel_method_to_match_forged_proof(arithmetic_receipt):
    data = receipt_kwargs(arithmetic_receipt)
    data.update(method="cognition.causal", proof_type="causal_identification", proof_artifact={
        "dag": [], "identification_assumptions": [], "estimand": "effect", "estimate": 2, "confounders": [], "refutations": {}})
    with pytest.raises(CognitionError, match="epistemic claim"):
        CognitiveReceipt(**data)


@pytest.mark.parametrize("field,value", [("epistemic_class", "causal"), ("consequence_class", "financial")])
def test_receipt_envelope_classification_matches_geometry(arithmetic_receipt, field, value):
    data = receipt_kwargs(arithmetic_receipt); data[field] = value
    with pytest.raises(CognitionError, match="classification disagree"):
        CognitiveReceipt(**data)


def test_native_answer_cannot_drop_its_proof(arithmetic_receipt):
    data = receipt_kwargs(arithmetic_receipt); data.update(proof_type=None, proof_artifact=None)
    with pytest.raises(CognitionError, match="requires its proof"):
        CognitiveReceipt(**data)


def test_receipt_rejects_artifact_output_disagreement(arithmetic_receipt):
    data = receipt_kwargs(arithmetic_receipt)
    data["proof_artifact"]["result"] = {"exact": "999"}
    with pytest.raises(CognitionError, match="artifact and output disagree"):
        CognitiveReceipt(**data)
    data.update(abstention_state="REFUTED", outcome_state="ABSTAIN", evaluator_result={"verdict": "REFUTED"})
    CognitiveReceipt(**data)  # failed evidence remains inspectable, never a valid answer


def test_provisional_baselines_and_blocked_native_receipts_remain_valid(arithmetic_receipt):
    baseline = receipt_kwargs(arithmetic_receipt)
    baseline.update(method="baseline.always_local_llm", proof_type=None, proof_artifact=None, outcome_state="CONDITIONAL_RESULT")
    CognitiveReceipt(**baseline)
    blocked = receipt_kwargs(arithmetic_receipt)
    blocked.update(output=None, proof_type=None, proof_artifact=None, abstention_state="ABSTAIN", outcome_state="ABSTAIN")
    CognitiveReceipt(**blocked)


def test_older_valid_receipt_is_read_using_its_original_digest(arithmetic_receipt):
    from dataclasses import MISSING
    original = receipt_kwargs(arithmetic_receipt)
    for name, specification in CognitiveReceipt.__dataclass_fields__.items():
        if specification.default is not MISSING or specification.default_factory is not MISSING:
            original.pop(name, None)
    # authority_created was required by the old retained-receipt validator.
    original["authority_created"] = False
    original["method_version"] = "0.1.0"
    original["receipt_id"] = digest(original)
    assert _valid_receipt(original)


def test_future_profiles_keep_native_jurisdiction_without_activation(arithmetic_receipt):
    from greg.cognition.catalog import FAMILIES
    data = receipt_kwargs(arithmetic_receipt)
    data.update(method="cognition.pattern", epistemic_class="prediction", proof_type="pattern_evidence",
                proof_artifact={"observations": [], "model": "descriptive", "scores": [], "limits": "unqualified"})
    data["geometry"]["epistemic_class"] = "prediction"
    CognitiveReceipt(**data)
    assert FAMILIES["pattern"][3] == data["proof_type"]
    assert registry_view().usable("cognition.pattern")[0] is False
    data["method"] = "cognition.micro"
    with pytest.raises(CognitionError, match="epistemic claim"):
        CognitiveReceipt(**data)


def test_null_typed_proof_fields_are_not_valid_artifacts():
    with pytest.raises(CognitionError, match="wrong type"):
        ProofArtifact("causal_identification", {k: None for k in ("dag", "identification_assumptions", "estimand", "estimate", "confounders", "refutations")}).validate()


def test_unsat_and_unknown_preserve_native_status_without_new_certificate_claim():
    impossible = {**MODEL, "constraints": MODEL["constraints"] + [{"coefficients": {"x": 1}, "op": "<=", "rhs": 1}]}
    unsat = formal(impossible, asdict(ProblemGeometry()))
    verified = verify("formal", impossible, unsat, "formal_model")
    assert unsat["output"]["solver_status"] == "UNSAT" and verified["verdict"] == "STRUCTURALLY_VERIFIED"
    assert any("no independent infeasibility certificate" in text for text in verified["dissent"])
    unknown = formal(MODEL, asdict(ProblemGeometry(compute_limit=1)))
    assert verify("formal", MODEL, unknown, "formal_model")["checks"]["unknown_not_valid"]
