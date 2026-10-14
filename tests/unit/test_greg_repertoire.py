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
