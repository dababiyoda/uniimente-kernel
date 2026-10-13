# Recombined from PR #145 at 680a0d438e94a004ab596ab3287e28878bfb747d; no routing-gain claim.
"""Bounded native qualification and coherent forgeries, distinct from routing gain."""
from copy import deepcopy
from dataclasses import asdict
import math

import pytest

from greg.cognition.catalog import FAMILIES
from greg.cognition.contracts import CognitionError, ProblemGeometry, ProofArtifact
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


@pytest.mark.parametrize("family,operation,data", CASES)
def test_replacement_preserves_source_binding_and_version_partition(family, operation, data):
    from greg.capabilities import BUILTINS
    manifest = BUILTINS["cognition." + family][0]
    assert manifest.version == "0.3.0"
    assert "PR #145 680a0d438e94" in manifest.cognitive_profile["lineage"]
    answer = SOLVERS[family](deepcopy(data), GEOMETRY)
    answer["proof"]["input_digest"] = "sha256:" + "0" * 64
    assert verify(family, data, answer, FAMILIES[family][3])["verdict"] == "REFUTED"


def test_game_zero_budget_remains_unknown_not_an_optimum():
    data = {"payoffs": [[1, -1], [-1, 1]], "solver_budget_seconds": 0}
    answer = SOLVERS["game"](data, GEOMETRY)
    assert answer["status"] == answer["formal_validity"] == "UNKNOWN"
    assert answer["output"] == {"solver_status": "NOT_SOLVED"}
    assert verify("game", data, answer, "game_model")["verdict"] == "STRUCTURALLY_VERIFIED"


def test_selected_method_cannot_relabel_its_proof_type():
    data = CASES[0][2]
    answer = SOLVERS["probabilistic"](data, GEOMETRY)
    with pytest.raises(CognitionError, match="false proof type"):
        verify("probabilistic", data, answer, "human_judgment")
