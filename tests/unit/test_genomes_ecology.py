"""Ecology bidding genome (compute budget among solver species): contract, withheld registration, canonical path,
Competency Compiler reachability, independent verification, refutation of corrupted answers, invalid input,
abstention, the exact oracle, non-anticipation of every arm and the reputation mechanism.

Development seeds 0-9 only; held-out admission seeds are never generated here.
"""
from __future__ import annotations

import copy
import itertools
import json
import math

import pytest

from greg.cognition import catalog, worlds
from greg.cognition.genomes import ecology as ec
from greg.cognition.genomes import library
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

FAMILY = "collective_ecology_bidding"
ITEM = ec.INTELLIGENCES[0]
QUICK = (0, 1, 2, 3, 4, 5)
BUDGET = {"latency_s": 8.0, "compute": 100000}
_CACHE: dict = {}


def dev(seed):
    assert 0 <= seed < 10                                      # never a held-out seed
    if seed not in _CACHE:
        _CACHE[seed] = ITEM.instance(seed)
    data, truth = _CACHE[seed]
    return copy.deepcopy(data), truth


def solved(seed):
    key = ("solved", seed)
    if key not in _CACHE:
        data, _ = dev(seed)
        _CACHE[key] = ITEM.solve(data, BUDGET)
    data, truth = dev(seed)
    return data, truth, copy.deepcopy(_CACHE[key])


def _ok(data, output, cert):
    return all(ITEM.verify(data, output, cert).values())


# ------------------------------------------------------------------ genome contract and registration
def test_genome_validates_with_declared_identity():
    g = ITEM.genome
    assert isinstance(g, IntelligenceGenome) and g.validate() is g
    assert (g.family, g.layer, g.operation, g.epistemic_class, g.evidence_type, g.dependency) == (
        FAMILY, 2, "allocate_compute_by_ecology", "optimization", "collective_trace", None)
    assert g.buildability == "BUILDABLE_NOW" and g.standalone_decision and g.version == "1.0.0"
    assert g.authority_ceiling == g.consequence_limit == "read_only"
    assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
    assert "seeds 0-9 dev" in g.benchmark_suite and "synthetic" in g.benchmark_suite
    assert ITEM.subregion is not None and ITEM.competitor_deployable
    assert ITEM.competitor is ec.ecology_certainty_equivalent and ITEM.baseline is ec.ecology_baseline


def test_registered_in_the_one_catalog_withheld_and_declared_a_simulated_world():
    assert library.executables()[FAMILY] is ITEM
    g = ITEM.genome
    assert catalog.FAMILIES[FAMILY] == (g.layer, (g.operation,), (g.epistemic_class,), "genome_certificate", None)
    assert catalog.initial_state(f"cognition.{FAMILY}") == "VERIFIED"         # registered, never auto-attached
    assert worlds.world("genome", FAMILY) == "simulated_world"


def test_module_imports_no_heavy_package_at_top_level():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(ec))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top for a in n.names} | {
        n.module.split(".")[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"numpy", "scipy", "networkx", "ortools", "z3"}


def test_instances_are_deterministic_and_cover_every_regime():
    assert ITEM.instance(3) == ITEM.instance(3)
    assert {dev(s)[1]["regime"] for s in range(4)} == set(ec.EC_REGIMES)
    data, _ = dev(0)
    assert len(json.dumps(data)) < 64 * 1024


# ------------------------------------------------------------------ solve / verify on development seeds
@pytest.mark.parametrize("seed", QUICK)
def test_solve_answers_and_its_answer_verifies(seed):
    data, truth, out = solved(seed)
    assert out["status"] == "ANSWER", out["missing"]
    json.dumps(out, allow_nan=False)
    checks = ITEM.verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    s = ITEM.score(data, truth, out["output"])
    assert s["category"] == "correct" and 0 < s["quality"] <= 1 + 1e-12
    assert ITEM.solve(copy.deepcopy(data), BUDGET) == out                     # deterministic


@pytest.mark.parametrize("seed", range(10))
def test_every_arm_is_feasible_and_bounded_by_the_exact_oracle(seed):
    data, truth = dev(seed)
    arms = (ITEM.solve(data, BUDGET)["output"], ec.ecology_baseline(data), ec.ecology_certainty_equivalent(data),
            ec.ecology_thompson(data))
    for out in arms:
        assert _ok(data, out, {"reputation": [0.0] * len(data["species"]),
                               "clearing_prices": [0.0] * len(data["tasks"])})
        s = ITEM.score(data, truth, out)
        assert s["category"] == "correct" and 0 <= s["quality"] <= 1 + 1e-12


def test_score_abstains_on_none_and_marks_an_infeasible_answer_wrong():
    data, truth, out = solved(0)
    assert ITEM.score(data, truth, None) == {"quality": 0.0, "category": "abstain"}
    over = copy.deepcopy(out["output"])
    over["bundles"][0][0] += data["budget"]          # far over budget (and over the tape length)
    assert ITEM.score(data, truth, over)["category"] == "wrong"


# ------------------------------------------------------------------ the exact oracle
def _brute(p, costs, ctx, vals, budget, cap):
    k, best = len(costs), 0.0
    per_task = [list(itertools.product(range(cap + 1), repeat=k)) for _ in ctx]
    for choice in itertools.product(*per_task):
        if sum(c * x for b in choice for c, x in zip(costs, b)) <= budget:
            best = max(best, ec.expected_value(p, ctx, vals, choice))
    return best


@pytest.mark.parametrize("case", range(6))
def test_oracle_equals_exhaustive_search_on_tiny_worlds(case):
    import random
    r = random.Random(f"tiny:{case}")
    k, c = 2, 2
    p = [[r.uniform(0.05, 0.9) for _ in range(c)] for _ in range(k)]
    costs = [r.randint(1, 2) for _ in range(k)]
    ctx = [r.randrange(c) for _ in range(3)]
    vals = [r.randint(1, 9) for _ in ctx]
    budget = r.randint(2, 6)
    assert math.isclose(ec.oracle_value(p, costs, ctx, vals, budget, 2), _brute(p, costs, ctx, vals, budget, 2),
                        rel_tol=1e-12, abs_tol=1e-12)


# ------------------------------------------------------------------ independent verification
def _corruptions(o, data):
    k = len(data["species"])
    tape = data["outcome_tape"]
    out = {}
    b = copy.deepcopy(o["bundles"])
    b[0] = [data["budget"]] * k
    out["over_budget"] = {**o, "bundles": b}
    b = copy.deepcopy(o["bundles"])
    b[1][0] = len(tape[0][0]) + 1
    out["beyond_tape"] = {**o, "bundles": b}
    b = copy.deepcopy(o["bundles"])
    b[2][0] = -1
    out["negative_runs"] = {**o, "bundles": b}
    b = copy.deepcopy(o["bundles"])
    b[0][0] = 1.0
    out["float_runs"] = {**o, "bundles": b}
    out["bundles_truncated"] = {**o, "bundles": o["bundles"][:-1]}
    out["spend_understated"] = {**o, "spend": o["spend"] - 1}
    out["spend_as_float"] = {**o, "spend": float(o["spend"])}
    flipped = list(o["solved"])
    flipped[0] = not flipped[0]
    out["solved_flag_flipped"] = {**o, "solved": flipped}
    out["all_claimed_solved"] = {**o, "solved": [True] * len(o["solved"])}
    out["value_inflated"] = {**o, "realised_value": o["realised_value"] + 1}
    out["value_as_float"] = {**o, "realised_value": float(o["realised_value"])}
    out["extra_field"] = {**o, "note": "trust me"}
    # a bundle moved onto runs whose tape entries are failures while the claimed outcomes stay unchanged
    b = copy.deepcopy(o["bundles"])
    for i, row in enumerate(b):
        if o["solved"][i]:
            b[i] = [0] * k
            break
    out["bought_runs_removed"] = {**o, "bundles": b}
    return out


@pytest.mark.parametrize("seed", QUICK)
def test_verifier_rejects_every_corruption(seed):
    data, _, out = solved(seed)
    o, cert = out["output"], out["certificate"]
    assert _ok(data, o, cert)
    for name, bad in _corruptions(o, data).items():
        assert not _ok(data, bad, cert), name
    for name, bad_cert in {"reputation_above_one": {**cert, "reputation": [2.0] * len(cert["reputation"])},
                           "reputation_short": {**cert, "reputation": cert["reputation"][:-1]},
                           "negative_price": {**cert, "clearing_prices": [-1.0] * len(cert["clearing_prices"])},
                           "nan_price": {**cert, "clearing_prices": [float("nan")] * len(cert["clearing_prices"])},
                           "empty": {}}.items():
        assert not _ok(data, o, bad_cert), name


def test_verifier_replays_the_tapes_not_the_claims():
    data, _, out = solved(1)
    o, cert = out["output"], out["certificate"]
    tampered = copy.deepcopy(data)
    for i, row in enumerate(o["bundles"]):              # erase every success the bought runs saw
        for m, x in enumerate(row):
            tape = tampered["outcome_tape"][i][m]
            tampered["outcome_tape"][i][m] = "0" * x + tape[x:]
    if any(o["solved"]):
        assert not _ok(tampered, o, cert)


def test_malformed_outputs_are_refuted_not_raised():
    data, _ = dev(0)
    for junk in (None, 3, [], {}, "answer", {"bundles": None, "spend": 0, "solved": [], "realised_value": 0},
                 {"bundles": [[None]], "spend": 0, "solved": [], "realised_value": 0}):
        assert not all(ITEM.verify(data, junk, {}).values())
    assert not all(ITEM.verify({}, {"bundles": []}, {}).values())


# ------------------------------------------------------------------ input bounds and abstention
def _bad_inputs():
    data, _ = dev(0)
    out = {}
    for name, change in {
        "not_a_dict": lambda d: [],
        "no_species": lambda d: {**d, "species": []},
        "cost_zero": lambda d: {**d, "species": [{"name": "a", "cost": 0}] + d["species"][1:]},
        "context_out_of_range": lambda d: {**d, "tasks": [{"context": d["contexts"], "value": 1}] + d["tasks"][1:]},
        "negative_budget": lambda d: {**d, "budget": -1},
        "successes_above_trials": lambda d: {**d, "warmup_history": [[0, 0, 5, 2]]},
        "repeated_cell": lambda d: {**d, "warmup_history": [[0, 0, 0, 1], [0, 0, 1, 1]]},
        "tape_bad_char": lambda d: {**d, "outcome_tape": [["2" * 10] * len(d["species"])] + d["outcome_tape"][1:]},
        "tape_ragged": lambda d: {**d, "outcome_tape": [["1"] * len(d["species"])] + d["outcome_tape"][1:]},
        "tape_rows_short": lambda d: {**d, "outcome_tape": d["outcome_tape"][:-1]},
        "rng_seed_float": lambda d: {**d, "rng_seed": 1.5},
        "too_many_tasks": lambda d: {**d, "tasks": d["tasks"] * 4},
    }.items():
        out[name] = change(copy.deepcopy(data))
    return out


@pytest.mark.parametrize("name", sorted(_bad_inputs()))
def test_invalid_input_raises_a_genome_error(name):
    bad = _bad_inputs()[name]
    with pytest.raises(GenomeError):
        ec.ecology_solve(bad, BUDGET)
    with pytest.raises(GenomeError):
        ec.ecology_certainty_equivalent(bad)


def test_planning_work_above_the_bound_is_unknown_not_attempted():
    data, _ = dev(0)
    big = copy.deepcopy(data)
    k = len(big["species"])
    big["tasks"] = (big["tasks"] * 3)[:ec.EC_MAX_TASKS]
    big["outcome_tape"] = (big["outcome_tape"] * 3)[:ec.EC_MAX_TASKS]
    big["budget"] = ec.EC_MAX_WORK // (len(big["tasks"]) * k) + 1
    assert big["budget"] <= ec.EC_MAX_BUDGET
    out = ec.ecology_solve(big, BUDGET)
    assert out["status"] == "UNKNOWN" and out["output"] is None and out["missing"]
    assert ec.ecology_certainty_equivalent(big) is None and ec.ecology_thompson(big) is None


def test_zero_budget_buys_nothing():
    data, truth = dev(2)
    data["budget"] = 0
    out = ec.ecology_solve(data, BUDGET)["output"]
    assert out["spend"] == 0 and out["realised_value"] == 0 and not any(out["solved"])


# ------------------------------------------------------------------ non-anticipation (replay honesty)
@pytest.mark.parametrize("arm", ["candidate", "competitor", "thompson"])
@pytest.mark.parametrize("seed", (0, 3, 6))
def test_no_arm_reads_an_outcome_before_buying_it(arm, seed):
    """Changing any tape entry an arm has not yet bought never changes a decision taken before it is revealed."""
    fn = {"candidate": lambda d: ec.ecology_solve(d, BUDGET)["output"],
          "competitor": ec.ecology_certainty_equivalent, "thompson": ec.ecology_thompson}[arm]
    data, _ = dev(seed)
    base = fn(data)["bundles"]
    for cut in (0, len(base) // 3, 2 * len(base) // 3):
        altered = copy.deepcopy(data)
        for i in range(len(base)):
            for m, x in enumerate(base[i]):
                bought = x if i < cut else 0               # tasks before the cut keep their revealed prefix
                tape = altered["outcome_tape"][i][m]
                altered["outcome_tape"][i][m] = tape[:bought] + "".join(
                    "1" if ch == "0" else "0" for ch in tape[bought:])
        assert fn(altered)["bundles"][:cut + 1] == base[:cut + 1], (arm, cut)


# ------------------------------------------------------------------ mechanism
def _world(tapes_for, k=2, n=12, budget=24, history=None):
    return {"species": [{"name": f"s{m}", "cost": 1} for m in range(k)], "contexts": 1,
            "tasks": [{"context": 0, "value": 10} for _ in range(n)], "budget": budget,
            "warmup_history": history or [], "outcome_tape": [[tapes_for(i, m) for m in range(k)] for i in range(n)],
            "rng_seed": 7}


def test_an_overclaiming_species_loses_reputation_and_a_good_one_keeps_it():
    """Species 0 always fails, species 1 always succeeds: species 0's optimistic claims score worse than its own mean
    (Brier), so its reputation falls; species 1's optimism is borne out and its reputation stays at 1."""
    data = _world(lambda i, m: "1" * 10 if m == 1 else "0" * 10,
                  history=[[0, 0, 2, 3], [1, 0, 1, 3]])
    out = ec.ecology_solve(data, BUDGET)
    rep = out["certificate"]["reputation"]
    assert rep[1] == 1.0 and rep[0] < 0.5
    assert all(ITEM.verify(data, out["output"], out["certificate"]).values())
    late = out["output"]["bundles"][len(data["tasks"]) // 2:]
    assert sum(b[1] for b in late) > sum(b[0] for b in late)          # the market moved compute to the good species


def test_restarts_of_one_dominant_species_are_native():
    """One species clearly better on every task (the antifragility v3b regime): the ecology buys repeated runs of it."""
    data = _world(lambda i, m: ("0101010101" if m == 0 else "0000000001"), budget=36,
                  history=[[0, 0, 5, 10], [1, 0, 1, 10]])
    bundles = ec.ecology_solve(data, BUDGET)["output"]["bundles"]
    assert any(b[0] >= 2 for b in bundles) and sum(b[0] for b in bundles) > sum(b[1] for b in bundles)


def test_baseline_is_static_on_the_best_warmup_species_split_evenly():
    data, _ = dev(4)
    out = ec.ecology_baseline(data)
    used = {m for b in out["bundles"] for m, x in enumerate(b) if x}
    assert len(used) <= 1
    counts = [sum(b) for b in out["bundles"]]
    assert max(counts) - min(counts) <= 1 and out["spend"] <= data["budget"]


def test_subregion_is_read_from_the_data():
    seen = {ITEM.subregion(dev(s)[0]) for s in range(10)}
    assert seen <= {f"{h}_history/{b}_budget" for h in ("sparse", "deep") for b in ("tight", "loose")}
    assert len(seen) >= 2


# ------------------------------------------------------------------ canonical path and compiler
def test_canonical_path_withholds_until_attached_and_creates_no_authority():
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    data, truth = dev(0)
    request = {"problem_id": "ecology-bidding", "operation": "allocate_compute_by_ecology", "data": data,
               "geometry": {"latency_limit": 30}}
    assert reason(request, registry=registry)["abstention_state"] == "CAPABILITY_DEFICIT"
    registry.set_state(f"cognition.{FAMILY}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["abstention_state"] == "NONE" and r["proof_type"] == "genome_certificate"
    assert r["proof_artifact"]["evidence_type"] == "collective_trace"
    assert r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" and r["authority_created"] is False
    assert ITEM.score(data, truth, r["output"])["category"] == "correct"


def test_the_competency_compiler_reaches_the_family_by_its_inputs(tmp_path, monkeypatch):
    """Evaluation only: an in-memory attach (no body, journal or founder pin) and an empty evidence index."""
    from greg.cognition import compiler
    from greg.cognition.cortex import reason, registry_view
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")
    data, truth = dev(0)
    request = {"problem_id": "ecology-compile", "compile": {"geometry": {"geometry": "optimization"}, "data": data}}
    registry = registry_view()
    withheld = reason(request, registry=registry)
    assert withheld["state"] == "CAPABILITY_DEFICIT"
    assert withheld["withheld_best_fit"]["method"] == f"cognition.{FAMILY}"
    registry.set_state(f"cognition.{FAMILY}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == f"cognition.{FAMILY}"
    assert r["authority_created"] is False
    assert ITEM.score(data, truth, r["result"])["category"] == "correct"
