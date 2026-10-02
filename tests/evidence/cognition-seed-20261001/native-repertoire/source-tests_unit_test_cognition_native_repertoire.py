"""Bounded native qualification and coherent forgeries, distinct from routing gain."""
from copy import deepcopy
from dataclasses import asdict
import math

import pytest

from greg.cognition.catalog import FAMILIES, initial_state
from greg.cognition.contracts import CognitionError, ProblemGeometry, ProofArtifact
from greg.cognition.cortex import reason, registry_view
from greg.cognition.solvers import SOLVERS
from greg.cognition.verification import verify


GEOMETRY = asdict(ProblemGeometry(latency_limit=10, compute_limit=100000))
CASES = [
    ("probabilistic", "beta_update", {"alpha": 1, "beta": 1, "successes": 3, "failures": 1}),
    ("control", "pid", {"observed": 2, "target": 10, "kp": 2, "correction_limit": 3}),
    ("information", "value_of_information", {"prior_best_value": 10, "cost": 2, "posterior_scenarios": [{"probability": .5, "best_value": 16}, {"probability": .5, "best_value": 12}]}),
    ("simulation", "simulate", {"seed": 5, "samples": 16, "steps": 3, "step_probability": 1}),
    ("game", "minimax", {"payoffs": [[1, -1], [-1, 1]]}),
    ("pattern", "anomalies", {"observations": [0, 0, 0, 0, 0, 10], "threshold": 2}),
    ("sequential", "mdp", {"transitions": {"s": {"stay": {"s": 1}}}, "rewards": {"s": {"stay": 2}}, "horizon": 3}),
    ("collective", "quorum", {"observations": [{"observer_id": str(i), "independence_group": str(i), "choice": "a", "weight": 1} for i in range(3)]}),
    ("evolutionary", "evolve_vector", {"center": [3], "bounds": [[-1, 1]], "seed": 7, "generations": 3}),
    ("human", "human_review", {"participants": ["proposed:expert"], "expertise": ["unverified"], "conflicts": [], "dissent": [], "decision_authority": None}),
    ("micro", "setpoint", {"observed": 2, "low": 3, "high": 7}),
]


@pytest.mark.parametrize("family,operation,data", CASES)
def test_native_artifact_has_actual_source_checks(family, operation, data):
    answer = SOLVERS[family](deepcopy(data), GEOMETRY)
    report = verify(family, data, answer, FAMILIES[family][3])
    assert report["verdict"] == "STRUCTURALLY_VERIFIED", report
    assert len(report["checks"]) >= 3
    assert answer["empirical_validity"] == "WORLD_UNVERIFIED"
    output = answer["output"]
    if family == "probabilistic":
        assert output["mean"] == pytest.approx(2/3) and output["variance"] == pytest.approx(2/63)
    elif family == "control":
        assert output == {"correction": 3, "state": {"integral": 0, "previous_error": 8}}
    elif family == "information":
        assert output == {"net_value": 2, "acquire": True, "gross_value": 4}
    elif family == "simulation":
        assert output == {"mean": 3, "minimum": 3, "maximum": 3}
    elif family == "game":
        assert output["value"] == pytest.approx(0) and output["mixed_strategy"] == pytest.approx([.5, .5])
    elif family == "pattern":
        assert output["anomalies"] == [5]
    elif family == "sequential":
        assert output == {"values": {"s": 6}, "policy": {"s": "stay"}}
    elif family == "collective":
        assert output == {"choice": "a", "quorum_crossed": True, "scores": {"a": 3}}
    elif family == "evolutionary":
        assert output["fitness"] >= 4 and answer["proof"]["analytic_baseline"] == {"candidate": [1], "fitness": 4}
    elif family == "human":
        assert output["decision"] is None and answer["status"] == "HUMAN_REVIEW_REQUIRED"
    else:
        assert output == {"state": "stimulate"}


@pytest.mark.parametrize("family,operation,data", CASES)
def test_coherent_forgery_is_not_verified_by_shape_and_matching_proof(family, operation, data):
    answer = SOLVERS[family](deepcopy(data), GEOMETRY)
    output, artifact = answer["output"], answer["proof"]
    if family == "probabilistic":
        output["mean"] = artifact["posterior"]["mean"] = .99
    elif family == "control":
        output["state"]["integral"] = artifact["state"]["integral"] = 8  # defeats anti-windup
    elif family == "information":
        output["gross_value"] = artifact["expected_value"] = 500
        output["net_value"] = 498
    elif family == "simulation":
        output.update({"mean": 200, "maximum": 200})
    elif family == "game":
        output["mixed_strategy"] = artifact["strategies"] = [1, 0]
        output["value"] = artifact["value"] = 1
    elif family == "pattern":
        output["anomalies"] = []
    elif family == "sequential":
        output["values"]["s"] = artifact["value_trace"][-1]["s"] = 100
    elif family == "collective":
        output["choice"] = artifact["trace"]["choice"] = "b"
    elif family == "evolutionary":
        output["fitness"] = -1
    elif family == "human":
        output["decision"] = "software authorizes legal action"
        answer["status"] = "ANSWER"
    else:
        output["state"] = artifact["scores"][0] = "inhibit"
    assert verify(family, data, answer, FAMILIES[family][3])["verdict"] == "REFUTED"


@pytest.mark.parametrize("family,operation,data", CASES)
def test_unconsumed_authority_clause_and_compute_exhaustion_prevent_execution(family, operation, data):
    with pytest.raises(CognitionError, match="restricted"):
        SOLVERS[family]({**data, "authority_created": True}, GEOMETRY)
    with pytest.raises(CognitionError, match="BUDGET_EXHAUSTED"):
        SOLVERS[family](data, {**GEOMETRY, "compute_limit": 1})


@pytest.mark.parametrize("family,operation,data", CASES[:-1])
def test_future_method_stays_unattached_and_signed_research_route_stays_world_unverified(family, operation, data):
    assert initial_state("cognition." + family) == "VERIFIED"
    registry = registry_view()
    request = {"problem_id": "native:" + family, "operation": operation, "data": data, "geometry": {"latency_limit": 10, "compute_limit": 100000}}
    before = reason(request, registry=registry)
    assert before["abstention_state"] == ("HUMAN_REVIEW_REQUIRED" if family == "human" else "CAPABILITY_DEFICIT")
    registry.set_state("cognition." + family, "ATTACHED")
    after = reason(request, registry=registry)
    assert after["abstention_state"] == ("HUMAN_REVIEW_REQUIRED" if family == "human" else "NONE"), after
    assert after["authority_created"] is False and after["empirical_validity"] == "WORLD_UNVERIFIED"
    if family != "human":
        assert after["method_version"] == "0.3.0"
        assert after["evaluator_result"]["execution_contract"].startswith("separate network-denied")


def test_game_native_unsolved_is_preserved_without_fabricated_optimum():
    data = {"payoffs": [[1, -1], [-1, 1]], "solver_budget_seconds": 0}
    answer = SOLVERS["game"](data, GEOMETRY)
    assert answer["status"] == "UNKNOWN" and answer["formal_validity"] == "UNKNOWN"
    assert verify("game", data, answer, "game_model")["verdict"] == "STRUCTURALLY_VERIFIED"
    answer["status"] = "ANSWER"
    assert verify("game", data, answer, "game_model")["verdict"] == "REFUTED"


def test_evolution_minimum_population_is_counted_before_search():
    data = {"center": [0], "bounds": [[-1, 1]], "seed": 2, "population": 2, "generations": 1}
    # scipy's minimum population is five; 2 * 5 evaluations * 5 arithmetic units.
    with pytest.raises(CognitionError, match="BUDGET_EXHAUSTED"):
        SOLVERS["evolutionary"](data, {**GEOMETRY, "compute_limit": 49})
    answer = SOLVERS["evolutionary"](data, {**GEOMETRY, "compute_limit": 50})
    assert answer["output"]["evaluations"] <= 10
    answer["output"]["evaluations"] = 11
    assert verify("evolutionary", data, answer, "collective_trace")["verdict"] == "REFUTED"


def test_declared_quorum_correlation_and_dissent_cannot_be_erased():
    data = deepcopy(CASES[7][2])
    data["observations"][1]["independence_group"] = "0"
    with pytest.raises(CognitionError, match="correlated"):
        SOLVERS["collective"](data, GEOMETRY)
    data = deepcopy(CASES[7][2])
    data["observations"][-1]["choice"] = "minority"
    data["threshold"] = .6
    answer = SOLVERS["collective"](data, GEOMETRY)
    assert any(row["choice"] == "minority" for row in answer["proof"]["dissent"])
    answer["proof"]["dissent"].pop()
    assert verify("collective", data, answer, "collective_trace")["verdict"] == "REFUTED"


def test_pid_long_saturation_recovers_without_integrator_windup():
    state = {"integral": 0, "previous_error": 0}
    for _ in range(20):
        data = {"observed": 0, "target": 10, "kp": 1, "ki": 1, "correction_limit": 2, "state": state}
        answer = SOLVERS["control"](data, GEOMETRY)
        assert verify("control", data, answer, "control_trace")["verdict"] == "STRUCTURALLY_VERIFIED"
        state = answer["output"]["state"]
        assert state["integral"] == 0 and answer["output"]["correction"] == 2
    data = {**data, "observed": 10, "state": state}
    assert SOLVERS["control"](data, GEOMETRY)["output"]["correction"] == 0


def test_voi_zero_entropy_gain_still_requires_decision_value_and_ties_stop():
    data = {"prior_best_value": 10, "cost": 0, "posterior_scenarios": [{"probability": .5, "best_value": 10}, {"probability": .5, "best_value": 10}]}
    answer = SOLVERS["information"](data, GEOMETRY)
    assert answer["output"] == {"net_value": 0, "acquire": False, "gross_value": 0}
    assert verify("information", data, answer, "information_value")["verdict"] == "STRUCTURALLY_VERIFIED"


def test_simulation_full_distribution_is_checked_past_retained_prefix():
    data = {"seed": 8, "samples": 125, "steps": 2, "step_probability": .5}
    answer = SOLVERS["simulation"](data, GEOMETRY)
    assert len(answer["proof"]["scenarios"]) == 100 and answer["proof"]["scenario_prefix_only"] is True
    assert verify("simulation", data, answer, "simulation_trace")["verdict"] == "STRUCTURALLY_VERIFIED"
    answer["proof"]["scenario_digest"] = "sha256:" + "0"*64
    assert verify("simulation", data, answer, "simulation_trace")["verdict"] == "REFUTED"


def test_bellman_choices_use_future_value_and_every_source_reward_is_consumed():
    data = {"transitions": {"a": {"now": {"a": 1}, "later": {"b": 1}}, "b": {"stay": {"b": 1}}},
            "rewards": {"a": {"now": 3, "later": 0}, "b": {"stay": 10}}, "horizon": 2}
    answer = SOLVERS["sequential"](data, GEOMETRY)
    assert answer["output"]["policy"]["a"] == "later" and answer["output"]["values"]["a"] == 10
    assert verify("sequential", data, answer, "search_trace")["verdict"] == "STRUCTURALLY_VERIFIED"
    data["rewards"]["a"]["hidden"] = 10000
    with pytest.raises(CognitionError, match="matching"):
        SOLVERS["sequential"](data, GEOMETRY)


@pytest.mark.parametrize("coefficients,expected", [
    ([-4, 0, 1], ["-2", "2"]), ([3, 2], ["-3/2"]), ([0, 0, 1], ["0"]),
    ([1, 0, 1], []), ([1, 0, 0, 0, 1], []), ([-2, 3, 0, -1], ["-2", "1"]),
])
def test_exact_polynomial_roots_and_multiplicities_are_checked_without_sympy_checker(coefficients, expected):
    data = {"polynomial": coefficients}
    answer = SOLVERS["exact"](data, GEOMETRY)
    assert answer["output"]["real_roots"] == expected
    report = verify("exact", data, answer, "exact_calculation")
    assert report["verdict"] == "STRUCTURALLY_VERIFIED", report
    assert report["checks"]["sturm_real_root_completeness"] and report["checks"]["exact_root_multiplicity"]


@pytest.mark.parametrize("attack", ["missing_root", "false_interval", "wrong_multiplicity", "lying_display", "wrong_factor", "factor_code"])
def test_polynomial_coherent_false_certificate_and_code_are_refuted(attack):
    data = {"polynomial": [-2, 0, 1]}
    answer = SOLVERS["exact"](data, GEOMETRY)
    output, artifact = answer["output"], answer["proof"]
    if attack == "missing_root":
        artifact["isolated_real_roots"].pop()
        output["real_roots"].pop()
    elif attack == "false_interval":
        artifact["isolated_real_roots"][0].update({"lower": "3", "upper": "4"})
    elif attack == "wrong_multiplicity":
        artifact["isolated_real_roots"][0]["multiplicity"] = 2
    elif attack == "lying_display":
        output["real_roots"] = ["-99", "99"]
    elif attack == "wrong_factor":
        output["factored"] = "x**2 - 3"
    else:
        output["factored"] = "__import__('os').system('false')"
    artifact["result"] = deepcopy(output)  # do not rely on simple artifact/output mismatch
    report = verify("exact", data, answer, "exact_calculation")
    assert report["verdict"] == "REFUTED", report


@pytest.mark.parametrize("coefficients", [[0, 0], [1, 0, 0], [1]*6])
def test_zero_or_unsupported_polynomial_domain_is_truthfully_rejected(coefficients):
    with pytest.raises(CognitionError):
        SOLVERS["exact"]({"polynomial": coefficients}, GEOMETRY)


@pytest.mark.parametrize("family,data,attack", [
    ("simulation", {"seed": 1, "samples": 2, "steps": 2, "step_probability": 0}, "scenario"),
    ("simulation", {"seed": 1, "samples": 1, "steps": 2, "step_probability": 0}, "samples"),
    ("pattern", {"observations": [0, 0, 0], "threshold": 0}, "index"),
    ("pattern", {"observations": [0, 0, 0], "threshold": 0}, "observation"),
    ("micro", {"observed": 0, "low": 1, "high": 2}, "observation"),
    ("micro", {"observed": 0, "low": 1, "high": 2}, "model"),
])
def test_boolean_equal_to_numeric_value_is_not_a_native_integer_or_observation(family, data, attack):
    answer = SOLVERS[family](data, GEOMETRY)
    if attack == "scenario":
        answer["proof"]["scenarios"][0] = False
    elif attack == "samples":
        answer["proof"]["samples"] = True
    elif attack == "index":
        answer["output"]["anomalies"][0] = False
    elif attack == "model":
        answer["proof"]["model"]["low"] = True
    else:
        answer["proof"]["observations"][0] = False
    assert verify(family, data, answer, FAMILIES[family][3])["verdict"] == "REFUTED"
