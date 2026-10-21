"""Layer 1/2/4 repertoire: real mechanisms, independent verification, hostile inputs, no activation."""
from copy import deepcopy
import random

import pytest

from greg.cognition.contracts import CognitionError
from greg.cognition.cortex import reason, registry_view
from greg.cognition.repertoire import crowd_label, evolve_blackbox, robust_anomalies, swarm_minimize
from greg.cognition.verification import verify

GEOMETRY = {"compute_limit": 100000, "latency_limit": 10.0}


def crowd(seed=3, items=60, reliable=(0.9, 0.85, 0.8), spammers=4):
    r = random.Random(seed)
    truth = {f"i{n}": r.choice("ab") for n in range(items)}
    rows = []
    for j, acc in enumerate(list(reliable) + [None] * spammers):
        for item, t in truth.items():
            label = r.choice("ab") if acc is None else (t if r.random() < acc else ("b" if t == "a" else "a"))
            rows.append({"item_id": item, "observer_id": f"o{j}", "independence_group": f"g{j}", "label": label})
    return {"classes": ["a", "b"], "labels": rows}, truth


def test_modified_z_flags_outliers_a_contaminated_z_score_masks():
    values = [0.1, -0.2, 0.0, 0.3, -0.1, 0.2, 9.0, 9.5, -0.3, 0.05]
    out = robust_anomalies({"observations": values}, GEOMETRY)["output"]
    assert out["anomalies"] == [6, 7]


def test_dawid_skene_beats_majority_when_spammers_outnumber_experts():
    data, truth = crowd()
    labels = crowd_label(data, GEOMETRY)["output"]["labels"]
    by = {}
    for row in data["labels"]:
        by.setdefault(row["item_id"], []).append(row["label"])
    majority = {i: max("ab", key=v.count) for i, v in by.items()}
    ds_errors = sum(labels[i] != t for i, t in truth.items())
    majority_errors = sum(majority[i] != t for i, t in truth.items())
    assert ds_errors < majority_errors


def test_correlated_observers_count_once():
    rows = [{"item_id": "x", "observer_id": f"c{k}", "independence_group": "same", "label": "b"} for k in range(5)]
    rows += [{"item_id": "x", "observer_id": f"o{k}", "independence_group": f"g{k}", "label": "a"} for k in range(2)]
    rows += [{"item_id": "y", "observer_id": f"o{k}", "independence_group": f"g{k}", "label": "a"} for k in range(2)]
    out = crowd_label({"classes": ["a", "b"], "labels": rows}, GEOMETRY)
    assert out["proof"]["participants"] == ["g0", "g1", "same"]
    assert out["output"]["labels"]["x"] == "a"


@pytest.mark.parametrize("mutate,message", [
    (lambda d: d["labels"].append(dict(d["labels"][0])), "once"),
    (lambda d: d["labels"].append({**d["labels"][0], "item_id": "new", "independence_group": "other"}), "one independence group"),
    (lambda d: d["labels"].append({**d["labels"][0], "item_id": "new", "label": "c"}), "outside the declared classes"),
    (lambda d: d.update(labels=[r for r in d["labels"] if r["independence_group"] in ("g0", "g1")]), "three independent"),
])
def test_crowd_refuses_malformed_or_inflated_votes(mutate, message):
    data, _ = crowd(items=5)
    mutate(data)
    with pytest.raises(CognitionError, match=message):
        crowd_label(data, GEOMETRY)


@pytest.mark.parametrize("solver", [swarm_minimize, evolve_blackbox])
def test_black_box_search_respects_budget_and_finds_the_declared_basin(solver):
    data = {"function": "sphere", "shift": [1.0, -2.0], "bounds": [[-5, 5], [-5, 5]], "budget": 800, "seed": 7}
    out = solver(data, GEOMETRY)["output"]
    assert out["evaluations"] <= 800 and out["fitness"] < 1e-2


@pytest.mark.parametrize("bad,message", [
    ({"function": "__import__('os')"}, "objective must be one of"),
    ({"shift": [9.0, 0.0]}, "inside the bounds"),
    ({"budget": 10 ** 9}, "integer"),
])
def test_black_box_objectives_are_a_closed_menu(bad, message):
    data = {"function": "rastrigin", "shift": [0.0, 0.0], "bounds": [[-5, 5], [-5, 5]], "budget": 100, "seed": 1, **bad}
    with pytest.raises(CognitionError, match=message):
        swarm_minimize(data, GEOMETRY)


def test_independent_verifier_refutes_forged_artifacts():
    data = {"function": "ackley", "shift": [0.5, 0.5], "bounds": [[-5, 5], [-5, 5]], "budget": 400, "seed": 2}
    answer = swarm_minimize(data, GEOMETRY)
    assert verify("swarm", data, answer, "collective_trace")["verdict"] == "STRUCTURALLY_VERIFIED"
    forged = deepcopy(answer)
    forged["output"]["fitness"] = 0.0
    assert verify("swarm", data, forged, "collective_trace")["verdict"] == "REFUTED"
    cdata, _ = crowd(items=20)
    canswer = crowd_label(cdata, GEOMETRY)
    assert verify("crowd", cdata, canswer, "collective_trace")["verdict"] == "STRUCTURALLY_VERIFIED"
    flipped = deepcopy(canswer)
    item = next(iter(flipped["output"]["labels"]))
    flipped["output"]["labels"][item] = "b" if flipped["output"]["labels"][item] == "a" else "a"
    assert verify("crowd", cdata, flipped, "collective_trace")["verdict"] == "REFUTED"
    pdata = {"observations": [0, 0.1, -0.1, 0.2, 8.0]}
    panswer = robust_anomalies(pdata, GEOMETRY)
    assert verify("robust_pattern", pdata, panswer, "pattern_evidence")["verdict"] == "STRUCTURALLY_VERIFIED"
    panswer["output"]["anomalies"] = []
    assert verify("robust_pattern", pdata, panswer, "pattern_evidence")["verdict"] == "REFUTED"


def test_new_families_are_built_not_activated_until_attached():
    data, _ = crowd(items=10)
    request = {"problem_id": "test:crowd", "operation": "crowd_label", "data": data}
    assert reason(request, registry=registry_view())["abstention_state"] == "CAPABILITY_DEFICIT"
    registry = registry_view()
    registry.set_state("cognition.crowd", "ATTACHED")       # what a founder attach would record
    receipt = reason(request, registry=registry)
    assert receipt["abstention_state"] == "NONE" and receipt["method"] == "cognition.crowd"
    assert receipt["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED"
    assert receipt["authority_created"] is False


# ---------------------------------------------------------------- review of PR #179, 2026-10-15 (H3, M4, M5, M6)
def _total_flip(answer, classes):
    forged = deepcopy(answer)
    for item, label in forged["output"]["labels"].items():
        if label is not None:
            forged["output"]["labels"][item] = classes[1 - classes.index(label)]
    forged["output"]["posteriors"] = {i: [1.0, 0.0] if forged["output"]["labels"][i] == classes[0] else [0.0, 1.0]
                                      for i in forged["output"]["posteriors"]}
    return forged


@pytest.mark.parametrize("seed", range(10))
def test_crowd_verifier_refutes_a_total_label_flip(seed):
    """H3: the verifier checked only internal consistency, so flipping every label with one-hot posteriors verified.
    It now recomputes the E-step from the fitted model and the raw votes."""
    data, truth = crowd(seed=seed, items=30)
    answer = crowd_label(data, GEOMETRY)
    assert verify("crowd", data, answer, "collective_trace")["verdict"] == "STRUCTURALLY_VERIFIED"
    forged = _total_flip(answer, data["classes"])
    assert sum(forged["output"]["labels"][i] != t for i, t in truth.items()) >= 20
    assert verify("crowd", data, forged, "collective_trace")["verdict"] == "REFUTED"


def test_crowd_verifier_refutes_a_flip_with_a_matching_flipped_model():
    """The forger also flips the fitted model (label switching): observers then look worse than chance."""
    data, _ = crowd(seed=4, items=30)
    answer = crowd_label(data, GEOMETRY)
    forged = _total_flip(answer, data["classes"])
    model = forged["proof"]["model"]
    model["prior"] = model["prior"][::-1]
    # switch the latent class only: row c of the new matrix is row 1-c of the old (observed labels keep their index)
    model["confusion"] = {g: rows[::-1] for g, rows in model["confusion"].items()}
    forged["output"]["posteriors"] = {i: p[::-1] for i, p in answer["output"]["posteriors"].items()}
    result = verify("crowd", data, forged, "collective_trace")
    assert result["verdict"] == "REFUTED"
    assert result["checks"]["observers_better_than_chance_on_average"] is False


def _self_consistent_forgery(answer, data):
    """Round-2 review of #179 (N1): claim non-convergence with a one-entry trace and ship any self-consistent model
    (a near-degenerate prior, symmetric confusions) with posteriors recomputed by one E-step from the raw votes."""
    import math
    forged = deepcopy(answer)
    classes = data["classes"]
    model = forged["proof"]["model"]
    model["prior"] = [1e-12, 1 - 1e-12]
    model["confusion"] = {g: [[.8, .2], [.2, .8]] for g in model["confusion"]}
    votes = {}
    for row in data["labels"]:
        votes.setdefault(str(row["item_id"]), {}).setdefault(str(row["independence_group"]), []).append(row["label"])
    post = {}
    for item, groups in votes.items():
        decided = {g: classes.index(v[0]) for g, v in groups.items() if len(set(v)) == 1 or
                   sorted(v.count(c) for c in set(v))[-1] != sorted(v.count(c) for c in set(v))[-2]}
        logs = [math.log(model["prior"][c]) + sum(math.log(model["confusion"][g][c][label])
                                                   for g, label in decided.items()) for c in range(2)]
        top = max(logs)
        total = sum(math.exp(x - top) for x in logs)
        post[item] = [math.exp(x - top) / total for x in logs]
    forged["output"]["posteriors"] = {i: post[i] for i in forged["output"]["posteriors"]}
    forged["output"]["labels"] = {i: (None if forged["output"]["labels"][i] is None else
                                      classes[max(range(2), key=lambda c: (post[i][c], -c))])
                                  for i in forged["output"]["labels"]}
    forged["proof"]["trace"]["em"] = forged["proof"]["trace"]["em"][:1]
    forged["output"]["iterations"] = 1
    return forged


@pytest.mark.parametrize("seed", range(10))
def test_crowd_verifier_refutes_a_self_consistent_model_that_claims_non_convergence(seed):
    """N1: the M-step fixed-point check ran only when the trace showed convergence, so a one-entry trace with any
    self-consistent model verified. The verifier now re-runs EM from the soft-majority start and compares."""
    data, truth = crowd(seed=seed, items=30)
    answer = crowd_label(data, GEOMETRY)
    assert verify("crowd", data, answer, "collective_trace")["verdict"] == "STRUCTURALLY_VERIFIED"
    forged = _self_consistent_forgery(answer, data)
    wrong = sum(forged["output"]["labels"][i] != t for i, t in truth.items())
    assert wrong > sum(answer["output"]["labels"][i] != t for i, t in truth.items())
    result = verify("crowd", data, forged, "collective_trace")
    assert result["verdict"] == "REFUTED"
    assert result["checks"]["em_rerun_matches_model"] is False


@pytest.mark.parametrize("function", ["sphere", "rastrigin", "ackley", "rosenbrock", "griewank"])
def test_blackbox_verifier_refutes_an_under_reported_evaluation_count(function):
    """M5 residual (round-2 review of #179): differential evolution may stop early, so the count had no check and an
    under-reported count verified. The verifier re-runs the declared method from its seed on its own objective."""
    import json
    data = {"function": function, "shift": [0.3, -0.2, 0.1], "bounds": [[-5, 5]] * 3, "budget": 1200, "seed": 7}
    answer = json.loads(json.dumps(evolve_blackbox(data, GEOMETRY), default=float))   # as the worker returns it
    assert verify("blackbox", data, answer, "collective_trace")["verdict"] == "STRUCTURALLY_VERIFIED"
    forged = deepcopy(answer)
    forged["output"]["evaluations"] -= answer["output"]["evaluations"] // 4
    result = verify("blackbox", data, forged, "collective_trace")
    assert result["verdict"] == "REFUTED" and result["checks"]["evaluation_count_matches_method"] is False


def test_robust_pattern_verifier_rederives_flags_when_mad_is_zero():
    """M4: with MAD == 0 the flag check was skipped, so an empty or wrong anomaly list verified."""
    data = {"observations": [0] * 9 + [50, -40, 0.1]}
    answer = robust_anomalies(data, GEOMETRY)
    assert answer["output"]["anomalies"] == [9, 10]
    assert verify("robust_pattern", data, answer, "pattern_evidence")["verdict"] == "STRUCTURALLY_VERIFIED"
    for forged_flags in ([], [0]):
        forged = deepcopy(answer)
        forged["output"]["anomalies"] = forged_flags
        assert verify("robust_pattern", data, forged, "pattern_evidence")["verdict"] == "REFUTED"


def test_search_verifier_is_not_common_mode_and_checks_the_evaluation_count(monkeypatch):
    """M5: the verifier reused the solver's objective code, so a patched objective verified its own answer;
    an under-reported evaluation count also verified."""
    from greg.cognition import repertoire
    data = {"function": "sphere", "shift": [1.0, -2.0], "bounds": [[-5, 5], [-5, 5]], "budget": 400, "seed": 7}
    honest = swarm_minimize(data, GEOMETRY)
    assert verify("swarm", data, honest, "collective_trace")["verdict"] == "STRUCTURALLY_VERIFIED"
    monkeypatch.setitem(repertoire.OBJECTIVES, "sphere", lambda x: 0.0)
    patched = swarm_minimize(data, GEOMETRY)
    assert patched["output"]["fitness"] == 0.0
    assert verify("swarm", data, patched, "collective_trace")["verdict"] == "REFUTED"
    monkeypatch.undo()
    undercount = deepcopy(honest)
    undercount["output"]["evaluations"] = 1
    assert verify("swarm", data, undercount, "collective_trace")["verdict"] == "REFUTED"
    for name in ("rastrigin", "ackley", "rosenbrock", "griewank"):   # the independent closed forms agree
        d = {**data, "function": name}
        assert verify("swarm", d, swarm_minimize(d, GEOMETRY), "collective_trace")["verdict"] == "STRUCTURALLY_VERIFIED"


def test_optimization_verifier_requires_the_bound_to_meet_an_optimal_objective():
    """M6: an OPTIMAL label with a suboptimal plan (proof bound 58 against objective 55) verified on feasibility."""
    from greg.cognition.solvers import SOLVERS
    data = {"variables": {"x": [0, 10], "y": [0, 10]},
            "constraints": [{"coefficients": {"x": 1, "y": 1}, "op": "<=", "rhs": 12}],
            "objective": {"sense": "max", "coefficients": {"x": 3, "y": 2}}}
    answer = SOLVERS["optimization"](data, {"compute_limit": 10000, "latency_limit": 10.0})
    assert answer["output"]["solver_status"] == "OPTIMAL"
    assert verify("optimization", data, answer, "optimization_certificate")["verdict"] == "STRUCTURALLY_VERIFIED"
    forged = deepcopy(answer)
    forged["output"]["solution"] = {"x": 10, "y": 1}            # feasible, objective 32 < optimum 34
    forged["proof"]["solution"] = forged["output"]["solution"]
    forged["output"]["objective_value"] = 32.0
    result = verify("optimization", data, forged, "optimization_certificate")
    assert result["verdict"] == "REFUTED" and result["checks"]["optimal_objective_meets_its_bound"] is False
