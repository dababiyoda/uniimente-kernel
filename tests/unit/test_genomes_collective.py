"""Layer 2 collective IntelligenceGenomes: contract shape, independent verification, abstention, scoring.

Development seeds only (0-9); the frozen held-out seeds (>= 1000) are never touched here.
"""
import copy
import itertools
import json
import math
import random

import pytest

from greg.cognition.genomes import collective as c
from greg.cognition.genomes import library
from greg.cognition.genomes.contract import CATEGORIES, EPISTEMIC_CLASSES, EVIDENCE_TYPES, GenomeError

FAMILIES = ("collective_quorum", "collective_aco", "collective_physarum", "collective_immune",
            "collective_market", "collective_flock")
DEV_SEED = {"collective_quorum": 0, "collective_aco": 3, "collective_physarum": 1, "collective_immune": 3,
            "collective_market": 7, "collective_flock": 3}
BUDGET = {"latency_s": 5.0, "compute": 100000}
_CACHE = {}


def dev(family):
    if family not in _CACHE:
        item = {x.genome.family: x for x in c.INTELLIGENCES}[family]
        data, truth = item.instance(DEV_SEED[family])
        _CACHE[family] = (item, data, truth, item.solve(copy.deepcopy(data), BUDGET))
    return _CACHE[family]


def _bounded_json(value, depth=0):
    """JSON types only, finite floats, lists <= 1000 entries."""
    assert depth < 20
    if isinstance(value, bool) or value is None or isinstance(value, (int, str)):
        return
    if isinstance(value, float):
        assert math.isfinite(value)
        return
    if isinstance(value, list):
        assert len(value) <= 1000
        for v in value:
            _bounded_json(v, depth + 1)
        return
    assert isinstance(value, dict), type(value)
    for k, v in value.items():
        assert isinstance(k, str)
        _bounded_json(v, depth + 1)


# ------------------------------------------------------------------ genome contract
def test_genomes_validate_and_project_into_library():
    genomes = [x.genome.validate() for x in c.INTELLIGENCES]
    assert {g.family for g in genomes} == set(FAMILIES)
    assert len({g.operation for g in genomes}) == len(genomes)
    for g in genomes:
        assert g.layer == 2 and g.family.startswith("collective_")
        assert g.evidence_type in EVIDENCE_TYPES and g.epistemic_class in EPISTEMIC_CLASSES
        assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
        assert g.authority_ceiling == g.consequence_limit == "read_only"
        assert g.buildability == "BUILDABLE_NOW" and g.standalone_decision
        assert g.operation != "quorum"                       # the seed collective family keeps its operation
    classes = {g.family: g.epistemic_class for g in genomes}
    assert classes["collective_quorum"] == classes["collective_immune"] == "prediction"
    assert {classes[f] for f in ("collective_aco", "collective_physarum", "collective_market")} == {"optimization"}
    assert classes["collective_flock"] == "physical"
    lib = library.executables()
    assert set(FAMILIES) <= set(lib)
    assert all(lib[f].genome.layer == 2 for f in FAMILIES)


def test_no_metaphor_claims_in_genomes():
    text = json.dumps([x.genome.to_dict() for x in c.INTELLIGENCES]).lower()
    for claim in ("conscious", "alive", "living organism", "general intelligence", "sentien"):
        assert claim not in text


# ------------------------------------------------------------------ solve -> verify (accept) on a dev instance
@pytest.mark.parametrize("family", FAMILIES)
def test_dev_instance_solves_verifies_and_scores(family):
    item, data, truth, out = dev(family)
    assert set(out) == {"output", "certificate", "status", "missing"}
    assert out["status"] == "ANSWER", out["missing"]
    for part in (out["output"], out["certificate"]):
        _bounded_json(part)
        assert len(json.dumps(part)) < 64 * 1024
    json.dumps(data)
    checks = item.verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    s = item.score(data, truth, out["output"])
    assert s["category"] == "correct"
    assert item.score(data, truth, None)["category"] == "abstain"
    assert item.score(data, truth, None)["quality"] < s["quality"] or family == "collective_immune"
    for arm in (item.baseline, item.competitor):
        result = arm(copy.deepcopy(data))
        assert item.score(data, truth, result)["category"] in CATEGORIES
    if item.subregion:
        assert isinstance(item.subregion(data), str)


# ------------------------------------------------------------------ verify REFUTES corrupted outputs
def _corrupt(family, data, output, certificate):
    out, cert = copy.deepcopy(output), copy.deepcopy(certificate)
    if family == "collective_quorum":
        out["choice"] = next(a for a in data["alternatives"] if a != out["choice"])
    elif family == "collective_aco":
        out["tour"][1] = out["tour"][0]                      # not a permutation
    elif family == "collective_physarum":
        out["objective"] = out["objective"] * 0.9            # claims a better objective than the design has
    elif family == "collective_immune":
        mean, _ = c._standardiser([tuple(p) for p in data["self_samples"]])
        nearest = min((i for i in range(len(data["test_points"])) if i not in out["flagged"]),
                      key=lambda i: math.dist(data["test_points"][i], mean))
        out["flagged"] = sorted(out["flagged"] + [nearest])  # flag the most self-like point, no witness
    elif family == "collective_market":
        tid = max(out["allocation"], key=out["allocation"].get)
        out["allocation"][tid] += 1                          # breaks capacity or equilibrium
    elif family == "collective_flock":
        flat = out["trajectories"][0]
        flat[len(flat) // 2] += 3.0                          # a teleport
    return out, cert


@pytest.mark.parametrize("family", FAMILIES)
def test_verify_rejects_corrupted_output(family):
    item, data, truth, out = dev(family)
    bad, cert = _corrupt(family, data, out["output"], out["certificate"])
    checks = item.verify(data, bad, cert)
    assert not all(checks.values()), checks


MALFORMED = (None, "x", {}, {"choice": ["A"], "posterior": "p", "tour": "t", "length": "l", "edges": "e",
                             "objective": "o", "flagged": "f", "self_radius": "r", "allocation": "a",
                             "clearing_price": "c", "payments": "p", "trajectories": "t"})


@pytest.mark.parametrize("family", FAMILIES)
def test_verify_refutes_malformed_output_without_crashing(family):
    item, data, truth, out = dev(family)
    for bad in MALFORMED:
        checks = item.verify(data, copy.deepcopy(bad), out["certificate"])
        assert checks and not all(checks.values()), (bad, checks)


def test_physarum_verify_refutes_a_false_robustness_claim():
    item, data, truth, out = dev("collective_physarum")
    bad = copy.deepcopy(out["output"])
    bad["expected_disconnected_pairs"] = bad["expected_disconnected_pairs"] + 0.5
    checks = item.verify(data, bad, out["certificate"])
    assert checks["candidate_edges_only_and_terminals_connected"] and not checks["robustness_recomputed"]


# ------------------------------------------------------------------ invalid input raises GenomeError
INVALID = {
    "collective_quorum": [{"alternatives": ["A"], "observers": []},
                          {"alternatives": ["A", "B"], "observers": [{"observer_id": "o", "group": "g",
                                                                      "accuracy": 1.5, "vote": "A"}]},
                          {"alternatives": ["A", "B"], "observers": [{"observer_id": "o", "group": "g",
                                                                      "accuracy": 0.7, "vote": "Z"}]},
                          {"alternatives": [["A"], ["B"]], "observers": []}],
    "collective_aco": [{"cities": [[0, 0], [1, 1]]}, {"cities": [[0, 0], [1, 1], [2, float("nan")], [3, 3]]},
                       {"cities": [[0, 0], [1, 1], [2, 2], [3, 3]], "local_search": "yes"}],
    "collective_physarum": [{"nodes": [[0, 0], [1, 0]], "edges": [[0, 0]], "terminals": [0, 1], "lambda": 1.0},
                            {"nodes": [[0, 0], [1, 0]], "edges": [[0, 1]], "terminals": [0, 5], "lambda": 1.0},
                            {"nodes": [[0, 0], [1, 0]], "edges": [[0, 1]], "terminals": [0, 1], "lambda": -1.0},
                            {"nodes": [[0, 0], [1, 0]], "edges": [[0, 1]], "terminals": [[0], [1]], "lambda": 1.0}],
    "collective_immune": [{"self_samples": [[0.0, 1.0]] * 10, "test_points": [[0.0]], "max_false_alarm_rate": 0.05},
                          {"self_samples": [[0.0]] * 10, "test_points": [[0.0]], "max_false_alarm_rate": 0.9}],
    "collective_market": [{"capacity": -1, "tasks": [{"task_id": "a", "marginal_values": [1.0]}]},
                          {"capacity": 3, "tasks": [{"task_id": "a", "marginal_values": [1.0]},
                                                    {"task_id": "a", "marginal_values": [2.0]}]},
                          {"capacity": 3, "tasks": [{"task_id": "a", "marginal_values": [True]}]}],
    "collective_flock": [{"starts": [[0, 0]], "goals": [[1, 1]]},
                         {"starts": [[0, 0], [0.5, 0]], "goals": [[5, 5], [9, 9]]},
                         {"starts": [[0, 0], [5, 0]], "goals": [[5, 5], [9, 9]], "steps": 5000}],
}


@pytest.mark.parametrize("family,bad", [(f, b) for f, items in INVALID.items() for b in items])
def test_invalid_input_raises(family, bad):
    item = {x.genome.family: x for x in c.INTELLIGENCES}[family]
    with pytest.raises(GenomeError):
        item.solve(bad, BUDGET)
    with pytest.raises(GenomeError):
        item.solve("not a dict", BUDGET)


# ------------------------------------------------------------------ abstention (counterindications)
def test_quorum_abstains_without_declared_correlation_or_quorum():
    obs = [{"observer_id": f"o{i}", "group": "faction", "accuracy": 0.7, "vote": "A"} for i in range(5)]
    obs += [{"observer_id": f"s{i}", "group": f"s{i}", "accuracy": 0.7, "vote": "B"} for i in range(3)]
    data = {"alternatives": ["A", "B"], "observers": obs, "groups": {}}
    out = c.quorum_solve(data, BUDGET)
    assert out["status"] == "ABSTAIN" and "faction" in out["missing"][0]
    data["groups"] = {"faction": {"shared_noise": 0.9}}
    data["minimum_independent"] = 10
    assert c.quorum_solve(data, BUDGET)["status"] == "ABSTAIN"            # too few independent groups
    data["minimum_independent"] = 3
    data["quorum"] = 0.99
    assert c.quorum_solve(data, BUDGET)["status"] == "ABSTAIN"            # evidence too weak for this quorum


def test_quorum_discounts_a_correlated_faction():
    """Five copies of one shared signal must not outvote three independent accurate observers."""
    obs = [{"observer_id": f"f{i}", "group": "faction", "accuracy": 0.7, "vote": "A"} for i in range(5)]
    obs += [{"observer_id": f"s{i}", "group": f"s{i}", "accuracy": 0.8, "vote": "B"} for i in range(3)]
    data = {"alternatives": ["A", "B"], "observers": obs, "groups": {"faction": {"shared_noise": 0.95}}}
    assert c.quorum_majority(data)["choice"] == "A"
    assert c.quorum_weighted_majority(data)["choice"] == "A"
    out = c.quorum_solve(data, BUDGET)
    assert out["status"] == "ANSWER" and out["output"]["choice"] == "B"
    assert all(c.quorum_verify(data, out["output"], out["certificate"]).values())
    data["groups"]["faction"]["shared_noise"] = 0.0                       # truly independent: faction wins
    assert c.quorum_solve(data, BUDGET)["output"]["choice"] == "A"


def test_aco_abstains_above_native_size_and_matches_exact_optimum():
    r = random.Random(5)
    big = {"cities": [[r.uniform(0, 100), r.uniform(0, 100)] for _ in range(41)]}
    assert c.aco_solve(big, BUDGET)["status"] == "ABSTAIN"
    pts = [[r.uniform(0, 100), r.uniform(0, 100)] for _ in range(7)]
    dist = [[math.dist(a, b) for b in pts] for a in pts]
    brute = min(sum(dist[t[i]][t[(i + 1) % 7]] for i in range(7))
                for t in ([0, *p] for p in itertools.permutations(range(1, 7))))
    assert math.isclose(c._held_karp(dist), brute, rel_tol=1e-12)
    out = c.aco_solve({"cities": pts, "seed": 1, "iterations": 30}, BUDGET)
    assert math.isclose(out["output"]["length"], brute, rel_tol=1e-9)


def test_physarum_objective_matches_brute_force_and_abstains_when_disconnected():
    data, _ = c.physarum_instance(2)
    coords, pairs, lengths, terms, lam = c._network_inputs(data)
    r = random.Random(0)
    for _ in range(25):
        chosen = [e for e in range(len(pairs)) if r.random() < 0.6]
        fast = c._design_value(len(coords), pairs, lengths, terms, lam, chosen)
        slow = c.network_evaluate(data, {"edges": [list(pairs[e]) for e in chosen]}) if chosen else None
        assert (fast is None) == (slow is None)
        if fast is not None:
            assert math.isclose(fast[0], slow["objective"], rel_tol=1e-9) and fast[2] == slow["split"]
    split = {"nodes": [[0, 0], [1, 0], [5, 0], [6, 0]], "edges": [[0, 1], [2, 3]], "terminals": [0, 3],
             "lambda": 1.0}
    assert c.physarum_solve(split, BUDGET)["status"] == "ABSTAIN"
    assert c.physarum_score(split, {"scale": 1.0}, {"edges": [[0, 1]]})["category"] == "wrong"


def test_immune_abstains_out_of_competence_and_scores_autoimmunity_as_wrong():
    r = random.Random(1)
    high = {"self_samples": [[r.gauss(0, 1) for _ in range(9)] for _ in range(80)],
            "test_points": [[0.0] * 9], "max_false_alarm_rate": 0.05}
    assert c.immune_solve(high, BUDGET)["status"] == "ABSTAIN"
    few = {"self_samples": [[r.gauss(0, 1), r.gauss(0, 1)] for _ in range(20)], "test_points": [[0.0, 0.0]],
           "max_false_alarm_rate": 0.05}
    assert c.immune_solve(few, BUDGET)["status"] == "ABSTAIN"
    item, data, truth, out = dev("collective_immune")
    batch = dict(data, test_points=data["test_points"] * 2)               # > 300 points: split the batch
    assert len(batch["test_points"]) > c.IMMUNE_MAX_TEST and c.immune_solve(batch, BUDGET)["status"] == "ABSTAIN"
    every = {"flagged": list(range(len(truth["labels"])))}           # flag everything: autoimmunity
    assert c.immune_score(data, truth, every)["category"] == "wrong"
    assert c.immune_score(data, truth, {"flagged": []}) == {"quality": 0.0, "category": "correct"}


def test_market_equilibrium_abstention_and_capacity_violation():
    data = {"capacity": 3, "reserve": 1.0, "increment": 0.5,
            "tasks": [{"task_id": "a", "marginal_values": [10.0, 4.0]}, {"task_id": "b", "marginal_values": [6.0, 3.0]},
                      {"task_id": "c", "marginal_values": [0.5]}]}
    out = c.market_solve(data, BUDGET)
    assert out["output"]["allocation"] == {"a": 2, "b": 1, "c": 0}      # the three units worth most
    assert 3.0 <= out["output"]["clearing_price"] <= 4.0                  # between 3rd and 4th unit values
    assert all(c.market_verify(data, out["output"], out["certificate"]).values())
    truth = {"optimal_welfare": c._optimal_welfare(3, 1.0, c._market_inputs(data)[3])}
    assert truth["optimal_welfare"] == pytest.approx(9.0 + 5.0 + 3.0)
    assert c.market_score(data, truth, out["output"]) == {"quality": pytest.approx(1.0), "category": "correct"}
    over = {"allocation": {"a": 2, "b": 2, "c": 0}}
    assert c.market_score(data, truth, over)["category"] == "wrong"
    data["tasks"][0]["marginal_values"] = [1.0, 5.0]                  # complementarity
    assert c.market_solve(data, BUDGET)["status"] == "ABSTAIN"


def test_flock_baseline_collides_and_candidate_is_contact_free():
    item, data, truth, out = dev("collective_flock")
    straight = c.flock_straight(data)
    assert c.flock_score(data, truth, straight) == {"quality": -1.0, "category": "wrong"}
    audit = c.flock_audit(data, out["output"])
    assert audit["clear"] and audit["min_separation"] >= 2 * c.FLOCK_R
    assert 0 < c.flock_score(data, truth, out["output"])["quality"] <= 1.0
    jammed = {"starts": [[0, 0], [3, 0]], "goals": [[3, 0.01], [0, 0.01]], "steps": 10}
    assert c.flock_solve(jammed, BUDGET)["status"] == "ABSTAIN"       # cannot finish inside 10 steps


# ------------------------------------------------------------------ score categories
def test_score_categories():
    _, qd, qt, _ = dev("collective_quorum")
    assert c.quorum_score(qd, qt, {"choice": qt["truth"]}) == {"quality": 1.0, "category": "correct"}
    wrong = next(a for a in qd["alternatives"] if a != qt["truth"])
    assert c.quorum_score(qd, qt, {"choice": wrong}) == {"quality": -1.0, "category": "wrong"}
    assert c.quorum_score(qd, qt, {"choice": None})["category"] == "abstain"
    _, ad, at, aout = dev("collective_aco")
    assert c.aco_score(ad, at, {"tour": [0, 0, 1]})["category"] == "wrong"
    assert c.aco_score(ad, at, aout["output"])["quality"] >= c.aco_score(ad, at, c.aco_nearest_neighbour(ad))["quality"]
    _, md, mt, _ = dev("collective_market")
    assert c.market_score(md, mt, {"allocation": {"nope": 1}})["category"] == "wrong"


def test_deterministic_given_data():
    for family in ("collective_aco", "collective_physarum", "collective_immune"):
        item, data, truth, out = dev(family)
        again = item.solve(copy.deepcopy(data), BUDGET)
        assert again["output"] == out["output"]
