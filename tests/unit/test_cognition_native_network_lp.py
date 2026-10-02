"""Native P5 mechanisms checked against independent small exact workload oracles."""
from copy import deepcopy
from dataclasses import asdict
from fractions import Fraction
from itertools import combinations
import random

import pytest

from greg.cognition.catalog import initial_state
from greg.cognition.contracts import CognitionError, CognitiveReceipt, ProblemGeometry
from greg.cognition.cortex import reason, registry_view
from greg.cognition.solvers import SOLVERS
from greg.cognition.verification import verify


GEOMETRY = asdict(ProblemGeometry(latency_limit=10, compute_limit=100000))
PATH = {"edges": [["a", "b", 1], ["b", "c", 2], ["a", "c", 9]], "start": "a", "goal": "c"}
FLOW = {"edges": [["s", "a", 3], ["a", "t", 2], ["s", "t", 1]], "source": "s", "sink": "t"}
LP = {"variables": {"x": [0, 10], "y": [0, 10]}, "constraints": [{"coefficients": {"x": 1, "y": 1}, "op": ">=", "rhs": 5}],
      "objective": {"coefficients": {"x": 1, "y": 2}, "sense": "min"}}


def _oracle_shortest(data):
    # Enumerate simple paths; nonnegative weights never require a repeated vertex.
    adjacency = {}
    for u, v, weight in data["edges"]:
        adjacency.setdefault(u, []).append((v, Fraction(weight)))
        if not data.get("directed", True):
            adjacency.setdefault(v, []).append((u, Fraction(weight)))
    best = None
    def walk(node, visited, cost):
        nonlocal best
        if node == data["goal"]:
            best = cost if best is None else min(best, cost)
            return
        for target, weight in adjacency.get(node, []):
            if target not in visited:
                walk(target, visited | {target}, cost + weight)
    walk(data["start"], {data["start"]}, Fraction(0))
    return best


def _oracle_flow(data):
    nodes = set(data["nodes"])
    others = sorted(nodes - {data["source"], data["sink"]})
    best = None
    for count in range(len(others) + 1):
        for chosen in combinations(others, count):
            side = {data["source"], *chosen}
            value = sum(capacity for u, v, capacity in data["edges"] if u in side and v not in side)
            best = value if best is None else min(best, value)
    return best


@pytest.mark.parametrize("seed", range(20))
def test_shortest_certificate_and_unreachable_are_native_against_simple_path_oracle(seed):
    rng = random.Random(seed)
    nodes = [f"n{i}" for i in range(rng.randint(2, 6))]
    data = {"nodes": nodes, "edges": [[rng.choice(nodes), rng.choice(nodes), rng.randint(0, 20) / 4] for _ in range(12)],
            "start": nodes[0], "goal": nodes[-1], "directed": seed % 2 == 0}
    answer = SOLVERS["graph"](data, GEOMETRY)
    expected = _oracle_shortest(data)
    assert answer["output"]["reachable"] == (expected is not None)
    assert answer["output"]["cost"] == (float(expected) if expected is not None else None)
    assert verify("graph", data, answer, "search_trace")["verdict"] == "STRUCTURALLY_VERIFIED"


@pytest.mark.parametrize("seed", range(20))
def test_max_flow_certificate_against_brute_force_cut_oracle(seed):
    rng = random.Random(1000 + seed)
    nodes = [f"n{i}" for i in range(rng.randint(2, 6))]
    data = {"nodes": nodes, "edges": [[rng.choice(nodes), rng.choice(nodes), rng.randint(0, 10)] for _ in range(10)],
            "source": nodes[0], "sink": nodes[-1]}
    answer = SOLVERS["flow"](data, GEOMETRY)
    expected = _oracle_flow(data)
    assert answer["output"]["value"] == expected
    assert answer["output"]["min_cut"]["capacity"] == expected
    assert verify("flow", data, answer, "flow_certificate")["verdict"] == "STRUCTURALLY_VERIFIED"


def test_feasible_but_nonoptimal_path_is_rejected_including_coherent_forged_potential():
    answer = SOLVERS["graph"](PATH, GEOMETRY)
    answer["output"].update({"path": ["a", "c"], "cost": 9})
    answer["proof"].update({"path": ["a", "c"], "cost": 9})
    answer["proof"]["network_claim"]["distances"]["c"] = 9
    answer["proof"]["network_claim"]["predecessors"]["c"] = "a"
    report = verify("graph", PATH, answer, "search_trace")
    assert report["verdict"] == "REFUTED"
    assert report["checks"]["optimal_distance_potential_and_reachability"] is False


def test_false_unreachable_and_parallel_last_wins_claim_are_rejected():
    answer = SOLVERS["graph"](PATH, GEOMETRY)
    answer["output"].update({"reachable": False, "path": [], "cost": None})
    answer["proof"].update({"path": [], "cost": None})
    answer["proof"]["network_claim"] = {"distances": {"a": 0}, "predecessors": {}}
    assert verify("graph", PATH, answer, "search_trace")["verdict"] == "REFUTED"
    data = {"edges": [["s", "t", 2], ["s", "t", 9]], "start": "s", "goal": "t"}
    answer = SOLVERS["graph"](data, GEOMETRY)
    assert answer["output"]["cost"] == 2
    assert verify("graph", data, answer, "search_trace")["verdict"] == "STRUCTURALLY_VERIFIED"


def test_display_tolerance_does_not_allow_a_suboptimal_float_path():
    data = {"edges": [["s", "t", 1.0], ["s", "u", .5], ["u", "t", .5000000000001]], "start": "s", "goal": "t"}
    answer = SOLVERS["graph"](data, GEOMETRY)
    forged_cost = .5 + .5000000000001
    answer["proof"]["network_claim"]["predecessors"]["t"] = "u"
    answer["proof"]["network_claim"]["distances"]["t"] = forged_cost
    answer["output"].update({"path": ["s", "u", "t"], "cost": forged_cost})
    answer["proof"].update({"path": answer["output"]["path"], "cost": forged_cost})
    assert verify("graph", data, answer, "search_trace")["verdict"] == "REFUTED"


@pytest.mark.parametrize("attack", ["nonmaximum", "nonconserved", "wrong_cut", "forged_source", "boolean_value"])
def test_flow_false_certificate_cannot_close(attack):
    answer = SOLVERS["flow"](FLOW, GEOMETRY)
    if attack == "nonmaximum":
        answer["output"].update({"value": 1, "flows": [["s", "t", 1]]})
    elif attack == "nonconserved":
        answer["output"]["flows"] = [["s", "a", 2], ["a", "t", 1], ["s", "t", 1]]
    elif attack == "wrong_cut":
        answer["output"]["min_cut"]["capacity"] = 1000
    elif attack == "forged_source":
        answer["proof"]["source_model"] = {**FLOW, "source": "a"}
    else:
        answer["output"]["value"] = True
    answer["proof"]["flow"] = deepcopy(answer["output"])
    assert verify("flow", FLOW, answer, "flow_certificate")["verdict"] == "REFUTED"


@pytest.mark.parametrize("data,objective", [
    (LP, 5),
    ({"variables": {"x": [0, 5], "y": [0, 2]}, "constraints": [{"coefficients": {"x": 1, "y": 1}, "op": "<=", "rhs": 4}],
      "objective": {"coefficients": {"x": 1, "y": 3}, "sense": "max"}}, 8),
    ({"variables": {"x": [0, 3], "y": [0, 3]}, "constraints": [{"coefficients": {"x": 1, "y": 1}, "op": "==", "rhs": 1.5}],
      "objective": {"coefficients": {"x": 1, "y": 2}, "sense": "min"}}, 1.5),
])
def test_glop_real_bounded_primal_dual_optima(data, objective):
    answer = SOLVERS["linear"](data, GEOMETRY)
    assert answer["output"]["solver_status"] == "OPTIMAL" and answer["output"]["objective_value"] == objective
    report = verify("linear", data, answer, "linear_program_certificate")
    assert report["verdict"] == "STRUCTURALLY_VERIFIED", report
    assert report["checks"]["primal_dual_certificate"] is True
    assert answer["empirical_validity"] == "WORLD_UNVERIFIED"


def test_lp_infeasible_and_zero_budget_preserve_native_status_but_never_answer():
    data = {"variables": {"x": [0, 1]}, "constraints": [{"coefficients": {"x": 1}, "op": ">=", "rhs": 2}],
            "objective": {"coefficients": {"x": 1}, "sense": "min"}}
    answer = SOLVERS["linear"](data, GEOMETRY)
    assert answer["output"]["solver_status"] == "INFEASIBLE" and answer["status"] == "ABSTAIN"
    assert answer["proof"]["infeasibility_certificate"] is None
    assert verify("linear", data, answer, "linear_program_certificate")["verdict"] == "STRUCTURALLY_VERIFIED"
    answer = SOLVERS["linear"]({**LP, "solver_budget_seconds": 0}, GEOMETRY)
    assert answer["output"]["solver_status"] == "NOT_SOLVED" and answer["status"] == "UNKNOWN"
    assert answer["formal_validity"] == "UNKNOWN"


@pytest.mark.parametrize("attack", ["violated_bound", "wrong_dual", "false_objective", "source_substitution", "boolean_multiplier"])
def test_glop_candidate_and_dual_are_untrusted(attack):
    answer = SOLVERS["linear"](LP, GEOMETRY)
    if attack == "violated_bound":
        answer["proof"]["claim"]["x"][0] = -1
        answer["output"]["solution"]["x"] = -1
    elif attack == "wrong_dual":
        answer["proof"]["claim"]["y_ub"][0] = 0
    elif attack == "false_objective":
        answer["output"]["objective_value"] = -999
    elif attack == "source_substitution":
        answer["proof"]["model"]["b_ub"][0] = -1
    else:
        answer["proof"]["claim"]["y_ub"][0] = True
    assert verify("linear", LP, answer, "linear_program_certificate")["verdict"] == "REFUTED"


def test_profiles_do_not_attach_and_workload_budgets_precede_native_work():
    registry = registry_view()
    for family, operation, data in (("graph", "shortest_path", PATH), ("flow", "max_flow", FLOW), ("linear", "linear_program", LP)):
        assert initial_state("cognition." + family) == "VERIFIED"
        assert reason({"problem_id": "unattached", "operation": operation, "data": data}, registry=registry)["abstention_state"] == "CAPABILITY_DEFICIT"
        with pytest.raises(CognitionError, match="BUDGET_EXHAUSTED"):
            SOLVERS[family](data, {**GEOMETRY, "compute_limit": 1})
    assert initial_state("foundry.query") == "VERIFIED"


def test_raw_model_generated_code_invalid_edges_and_unbounded_lp_are_rejected():
    for family, data in (("flow", {**FLOW, "python": "print(1)"}), ("graph", {**PATH, "edges": [["a", "b", -1]]}),
                         ("linear", {**LP, "variables": {"x": [None, 1]}}),
                         ("linear", {**LP, "constraints": [{"coefficients": {"x": 1}, "op": "!=", "rhs": 1}]})):
        with pytest.raises(CognitionError):
            SOLVERS[family](data, GEOMETRY)


def test_new_typed_flow_receipt_cannot_be_relabelled_as_linear():
    registry = registry_view()
    registry.set_state("cognition.flow", "ATTACHED")
    out = reason({"problem_id": "typed:flow", "operation": "max_flow", "data": FLOW, "geometry": {"latency_limit": 10}}, registry=registry)
    assert out["abstention_state"] == "NONE" and out["method_version"] == "0.3.0"
    raw = deepcopy(out)
    raw.pop("receipt_id")
    raw["proof_type"] = "linear_program_certificate"
    with pytest.raises(CognitionError, match="method and proof"):
        CognitiveReceipt(**raw)


@pytest.mark.parametrize("family,data,field", [
    ("graph", {"edges": [["s", "t", 1]], "start": "s", "goal": "t"}, "cost"),
    ("flow", {"edges": [["s", "t", 1]], "source": "s", "sink": "t"}, "cut"),
    ("linear", {"variables": {"x": [1, 2]}, "objective": {"coefficients": {"x": 1}, "sense": "min"}}, "solution"),
    ("linear", {"variables": {"x": [1, 2]}, "objective": {"coefficients": {"x": 1}, "sense": "min"}}, "objective_value"),
])
def test_boolean_is_not_a_certified_numeric_output(family, data, field):
    answer = SOLVERS[family](data, GEOMETRY)
    if field == "cost":
        answer["output"]["cost"] = answer["proof"]["cost"] = True
    elif field == "cut":
        answer["output"]["min_cut"]["capacity"] = True
        answer["proof"]["flow"] = deepcopy(answer["output"])
    elif field == "solution":
        answer["output"]["solution"]["x"] = True
    else:
        answer["output"][field] = True
    proof = {"graph": "search_trace", "flow": "flow_certificate", "linear": "linear_program_certificate"}[family]
    assert verify(family, data, answer, proof)["verdict"] == "REFUTED"


@pytest.mark.parametrize("attack", ["wrong_sign", "stationarity_residual"])
def test_small_dual_error_cannot_be_amplified_by_large_source_bounds(attack):
    # Independent review supplied these two counterexamples. Both falsely
    # looked like zero-gap optima under the original componentwise tolerance.
    if attack == "wrong_sign":
        data = {"variables": {"x": [0, 1e9]}, "objective": {"coefficients": {"x": 1e-7}, "sense": "min"}}
        x, upper_multiplier, objective = 1e9, 1e-7, 100
    else:
        data = {"variables": {"x": [-1e9, 0]}, "objective": {"coefficients": {"x": 1e-8}, "sense": "min"}}
        x, upper_multiplier, objective = 0, 0, 0
    answer = SOLVERS["linear"](data, GEOMETRY)
    answer["proof"]["claim"].update({"x": [x], "z_l": [0], "z_u": [upper_multiplier]})
    answer["proof"].update({"bound": objective, "gap": 0})
    answer["output"].update({"solution": {"x": x}, "objective_value": objective})
    report = verify("linear", data, answer, "linear_program_certificate")
    assert report["verdict"] == "REFUTED" and report["checks"]["primal_dual_certificate"] is False


def test_source_schema_rejects_silently_ignored_nodes_and_lp_clauses():
    for family, data in (("graph", {**PATH, "nodes": "abc"}),
                         ("flow", {**FLOW, "edges": [[["unhashable"], "t", 1]]}),
                         ("linear", {**LP, "objective": {**LP["objective"], "unrepresented_requirement": "protect"}}),
                         ("linear", {**LP, "constraints": [{"coefficients": {"x": 1}, "op": "<=", "rhs": 2, "name": 1}]})):
        with pytest.raises(CognitionError):
            SOLVERS[family](data, GEOMETRY)
