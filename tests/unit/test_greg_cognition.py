"""Real library engines and adversarial controls; no live model/market/hardware claims."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from greg.capabilities import BUILTINS, CapabilityError, InvocationContext
from greg.cognition.contracts import CognitionError, ConsequenceVector, ProblemGeometry
from greg.cognition.cortex import compile_problem, reason, registry_view, solve, compose
from greg.cognition.verification import verify


MODEL = {"variables": {"x": [0, 10], "y": [0, 10]},
         "constraints": [{"coefficients": {"x": 1, "y": 1}, "op": ">=", "rhs": 5}]}
CASES = [
    ("calculate", {"expression": "0.1 + 0.2"}, "exact", "exact", "3/10"),
    ("polynomial", {"polynomial": [-4, 0, 1]}, "exact", "real_roots", ["-2", "2"]),
    ("estimate", {"factors": [{"name": "n", "low": 2, "central": 3, "high": 4}, {"name": "p", "low": 5, "central": 6, "high": 7}]}, "estimation", "central", 18),
    ("constraints", MODEL, "formal", "solver_status", "SAT"),
    ("optimize", {**MODEL, "objective": {"coefficients": {"x": 1, "y": 2}, "sense": "min"}}, "optimization", "objective_value", 5),
    ("shortest_path", {"edges": [["a", "b", 2], ["b", "c", 3], ["a", "c", 9]], "start": "a", "goal": "c"}, "graph", "cost", 5),
    ("state_search", {"edges": [["a", "b", 2], ["b", "c", 3]], "start": "a", "goal": "c"}, "search", "path", ["a", "b", "c"]),
    ("beta_update", {"alpha": 1, "beta": 1, "successes": 3, "failures": 1}, "probabilistic", "alpha", 4),
    ("treatment_effect", {"design": "randomized", "treated": [4, 6], "control": [1, 3], "dag": [["X", "Y"]]}, "causal", "effect", 3),
    ("pid", {"observed": 2, "target": 10, "kp": 2, "correction_limit": 3}, "control", "correction", 3),
    ("value_of_information", {"prior_best_value": 10, "cost": 2, "posterior_scenarios": [{"probability": .5, "best_value": 16}, {"probability": .5, "best_value": 12}]}, "information", "net_value", 2),
    ("simulate", {"seed": 3, "samples": 10, "steps": 2, "step_probability": 1}, "simulation", "mean", 2),
    ("minimax", {"payoffs": [[1, -1], [-1, 1]]}, "game", "value", 0),
    ("anomalies", {"observations": [0, 0, 0, 0, 0, 10], "threshold": 2}, "pattern", "anomalies", [5]),
    ("setpoint", {"observed": 2, "low": 3, "high": 7}, "micro", "state", "stimulate"),
    ("mdp", {"transitions": {"s": {"stay": {"s": 1}}}, "rewards": {"s": {"stay": 2}}, "horizon": 3}, "sequential", "values", {"s": 6}),
    ("quorum", {"observations": [{"observer_id": str(i), "independence_group": str(i), "choice": "a", "weight": 1} for i in range(3)]}, "collective", "choice", "a"),
]


def request(operation, data, **kw):
    return {"problem_id": "test:" + operation, "operation": operation, "data": deepcopy(data), **kw}


@pytest.mark.parametrize("operation,data,family,field,expected", CASES)
def test_real_bounded_cognition_selects_different_mechanisms(operation, data, family, field, expected):
    receipt = reason(request(operation, data), registry=registry_view())
    assert receipt["abstention_state"] == "NONE", receipt["missing_information"]
    assert receipt["method"] == "cognition." + family
    assert receipt["output"][field] == expected
    assert receipt["proof_artifact"] and receipt["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED"
    assert receipt["authority_created"] is False
    assert receipt["empirical_validity"] == "WORLD_UNVERIFIED"


def test_unsat_is_a_formal_answer_and_unknown_is_never_success():
    model = deepcopy(MODEL)
    model["constraints"].append({"coefficients": {"x": 1, "y": 1}, "op": "<=", "rhs": 2})
    r = reason(request("constraints", model), registry=registry_view())
    assert r["output"]["solver_status"] == "UNSAT" and r["proof_artifact"]["unsat_core"]
    assert r["empirical_validity"] == "WORLD_UNVERIFIED"


def test_high_risk_does_not_create_formal_or_empirical_certainty():
    r = reason(request("constraints", MODEL, consequences={"financial": .9}), registry=registry_view())
    assert r["abstention_state"] == "FORMALIZATION_INCOMPLETE" and r["output"] is None
    r = reason(request("constraints", {**MODEL, "formalization_complete": True}, consequences={"financial": .9}), registry=registry_view())
    assert r["formal_validity"] == "VALID_CONDITIONAL_ON_MODEL"
    assert r["abstention_state"] == "WORLD_UNVERIFIED"
    assert r["legitimate_authority"] == "EXISTING_KERNEL_GATE_REQUIRED"


@pytest.mark.parametrize("kw", [{"rights": .01}, {"lawful": False}, {"consent": False}, {"discrimination": .1}])
def test_hard_constraints_cannot_be_bought_off_with_upside(kw):
    r = reason(request("calculate", {"expression": "1+1"}, consequences=kw), registry=registry_view())
    assert r["abstention_state"] == "PROHIBITED" and r["output"] is None


def test_causal_legal_and_normative_questions_have_honest_routes():
    r = reason(request("treatment_effect", {"design": "observational", "treated": [4], "control": [2]}), registry=registry_view())
    assert r["abstention_state"] == "UNIDENTIFIED" and r["output"]["effect"] is None
    r = reason(request("calculate", {"expression": "1+1"}, geometry={"legal_content": True}), registry=registry_view())
    assert r["abstention_state"] == "HUMAN_REVIEW_REQUIRED"
    r = reason(request("human_review", {"participants": ["expert"]}), registry=registry_view())
    assert r["abstention_state"] == "HUMAN_REVIEW_REQUIRED"


def test_missing_model_detached_solver_and_unknown_geometry_are_deficits():
    registry = registry_view()
    r = reason(request("interpret", {"text": "choose a strategy"}), registry=registry)
    assert r["abstention_state"] == "ABSTAIN" and "local model" in r["missing_information"][0]
    registry.set_state("cognition.exact", "DETACHED")
    r = reason(request("calculate", {"expression": "1+1"}), registry=registry)
    assert r["abstention_state"] == "CAPABILITY_DEFICIT" and r["output"] is None
    r = reason(request("invent_unknown_intelligence", {}), registry=registry)
    assert r["abstention_state"] == "CAPABILITY_DEFICIT"


@pytest.mark.parametrize("expression", ["__import__('os').system('true')", "[1][0]", "2**99999", "1/0"])
def test_data_never_becomes_executable_python(expression):
    r = reason(request("calculate", {"expression": expression}), registry=registry_view())
    assert r["abstention_state"] == "ABSTAIN" and r["output"] is None


def test_malformed_unknown_and_unbounded_inputs_fail_closed():
    for bad in [{"authority_created": True}, {"geometry": {"latency_limit": float("nan")}},
                {"geometry": {"compute_limit": True}}, {"geometry": {"epistemic_class": "causal"}},
                {"data": {"text": "x" * 66000}}]:
        with pytest.raises((CognitionError, ValueError, TypeError)):
            compile_problem({**request("calculate", {"expression": "1"}), **bad})
    with pytest.raises(CognitionError):
        ConsequenceVector(privacy=-1)
    with pytest.raises(CognitionError):
        ProblemGeometry(rights_impact="false")
    with pytest.raises(CognitionError):
        compile_problem(request("calculate", {"expression": "1"}, evidence_expires_at="2026-01-01T00:00:00"))
    # A complete receipt must survive the body's existing retention limits unchanged.
    from greg.cognition.contracts import retained_data
    with pytest.raises(CognitionError):
        retained_data({"proof": list(range(1001))})


def test_repeated_correlated_votes_cannot_create_a_quorum():
    observations = [{"observer_id": str(i), "independence_group": "one-model", "choice": "a", "weight": 1} for i in range(3)]
    r = reason(request("quorum", {"observations": observations}), registry=registry_view())
    assert r["abstention_state"] == "ABSTAIN" and "correlated" in r["missing_information"][0]


def test_independent_verifier_refutes_a_solver_lie():
    r = reason(request("constraints", MODEL), registry=registry_view())
    answer = {"output": {"solver_status": "SAT", "solution": {"x": "0", "y": "0"}}, "proof": r["proof_artifact"]}
    assert verify("formal", MODEL, answer, "formal_model")["verdict"] == "REFUTED"


def test_independent_verifier_refutes_a_longer_route_and_a_false_no_route():
    data = {"edges": [["a", "b", 2], ["b", "c", 3], ["a", "c", 9]], "start": "a", "goal": "c"}
    r = reason(request("shortest_path", data), registry=registry_view())
    assert r["output"]["cost"] == 5
    proof_class = "search_trace"                     # greg/cognition/catalog.py: graph
    longer = {"output": {"path": ["a", "c"], "cost": 9, "reachable": True}, "proof": r["proof_artifact"]}
    verdict = verify("graph", data, longer, proof_class)
    assert verdict["verdict"] == "REFUTED" and verdict["checks"]["path_optimal"] is False
    hidden = {"output": {"path": [], "cost": None, "reachable": False}, "proof": r["proof_artifact"]}
    assert verify("graph", data, hidden, proof_class)["checks"]["unreachable_confirmed"] is False


def test_a_cheaper_parallel_edge_is_never_overwritten_by_a_later_one():
    data = {"edges": [["a", "b", 2], ["a", "b", 5], ["b", "c", 1]], "start": "a", "goal": "c"}
    r = reason(request("shortest_path", data), registry=registry_view())
    assert r["output"]["cost"] == 3 and r["abstention_state"] == "NONE"


def test_symbolic_and_evolutionary_mechanisms_are_bounded_not_general_genesis():
    r = reason(request("evolve_vector", {"center": [1], "bounds": [[-2, 2]], "seed": 7, "generations": 10}), registry=registry_view())
    assert r["abstention_state"] == "NONE" and r["output"]["fitness"] < .01
    assert "stronger baseline" in r["proof_artifact"]["baseline_status"]
    r = reason(request("simulate", {"seed": 0, "samples": 100, "steps": 100, "step_probability": .5}, geometry={"compute_limit": 10}), registry=registry_view())
    assert r["abstention_state"] == "ABSTAIN"


def test_no_profile_creates_a_second_authority_or_changes_legacy_digests():
    for family in ("exact", "causal", "formal"):
        manifest = BUILTINS["cognition." + family][0]
        assert not manifest.genome().validate()
        bad = replace(manifest, cognitive_profile={**manifest.cognitive_profile, "authority_ceiling": "financial"})
        assert bad.validate()
    manifest = BUILTINS["fs.read"][0]
    assert "cognitive_profile" not in manifest.to_dict()


def test_composition_preserves_jurisdiction_and_dissent(tmp_path):
    ctx = InvocationContext(workspace=tmp_path, read_roots=(), secrets=None, manifest=BUILTINS["cognition.compose"][0],
                            target="cognition:test", capability_registry=registry_view())
    out = compose({"requests": [request("calculate", {"expression": "2+2"}), request("treatment_effect", {"design": "observational"})]}, ctx)
    assert out["metaconsensus"]["state"] == "ABSTAIN" and len(out["receipts"]) == 2
    assert out["metaconsensus"]["dissent"] and out["authority_created"] is False
    with pytest.raises(CapabilityError):
        compose({"requests": [request("calculate", {"expression": "1"}, geometry={"latency_limit": 20})] * 2}, ctx)
    from greg.cognition.verification import metaconsensus
    a = reason(request("calculate", {"expression": "1"}), registry=registry_view())
    b = reason({**request("calculate", {"expression": "2"}), "problem_id": "another-question"}, registry=registry_view())
    assert metaconsensus([a, b])["state"] == "RECOMMENDATION_ONLY"
    b["problem_id"] = a["problem_id"]
    assert metaconsensus([a, b])["state"] == "CONFLICT"


def test_protection_preserves_vectors_and_requires_authentic_human_authority():
    data = {"affected_party": {"affected_party": "pseudonym:1", "immediate_harm": .8, "evidence_at_risk": True},
            "interventions": [{"id": "hypothetical", "lawful": True, "consent": True,
                               "exploit_payoff": 10, "opportunity": .5, "detection_probability": .8,
                               "evidence_durability": .9, "accountability_probability": .5, "restitution_cost": 10,
                               "consequences": {"rights": .1}}]}
    r = reason(request("deterrence_model", data), registry=registry_view())
    assert r["abstention_state"] == "HUMAN_REVIEW_REQUIRED"
    assert r["output"]["interventions"][0]["blocked"] is True
    assert "preserve_evidence" in r["output"]["review_priorities"]
    assert r["output"]["recommendation"] is None and r["authority_created"] is False
    from greg.cognition.protection import AffectedParty
    with pytest.raises(CognitionError):
        AffectedParty("p", retaliation_risk=-1)


def test_cli_builds_an_existing_signed_mission_and_inventory(tmp_path, capsys):
    from greg.cli import main
    p = tmp_path / "request.json"
    p.write_text(json.dumps(request("calculate", {"expression": "1+1"})))
    assert main(["--home", str(tmp_path / "absent"), "cognition", "mission", "--request", str(p),
                 "--id", "m:cortex", "--field", "output.exact", "--equals", '"2"', "--print-only"]) == 0
    spec = json.loads(capsys.readouterr().out)
    assert spec["light_cone"]["budget_usd"] == 0
    assert spec["success_checks"][0]["predicate"]["value"] == "2"
    assert spec["strategies"][0]["capability"] == "cognition.solve"
    assert main(["--home", str(tmp_path / "absent"), "cognition", "inventory"]) == 0
    assert any(r["capability_id"] == "cognition.protection" for r in json.loads(capsys.readouterr().out))
