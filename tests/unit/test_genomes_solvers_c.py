"""Layer 3 batch C IntelligenceGenomes: contract, validation, independent verification, abstention, scoring,
determinism and dev-seed runtime.

Development seeds only (0-9); the held-out admission seeds (>= 1000) are never generated here.
"""
from __future__ import annotations

import copy
import json
import math
import time

import pytest

from greg.cognition.genomes import library, solvers_c
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

FAMILIES = ("mech_vcg", "verify_modelcheck", "control_mpc", "synth_cegis", "causal_backdoor", "info_experiment")
OPS = {"mech_vcg": "vcg_allocate_units", "verify_modelcheck": "model_check_safety", "control_mpc": "mpc_track",
       "synth_cegis": "cegis_synthesize", "causal_backdoor": "backdoor_ate", "info_experiment": "design_test_sequence"}
CLASSES = {"mech_vcg": "strategic", "verify_modelcheck": "deductive", "control_mpc": "physical",
           "synth_cegis": "constraint_feasibility", "causal_backdoor": "causal", "info_experiment": "strategic"}
EVIDENCE = {"mech_vcg": "decision_analysis", "verify_modelcheck": "exhaustive_check", "control_mpc": "control_trace",
            "synth_cegis": "exhaustive_check", "causal_backdoor": "statistical_estimate",
            "info_experiment": "decision_analysis"}
DEPS = {"mech_vcg": None, "verify_modelcheck": None, "control_mpc": "scipy", "synth_cegis": "z3-solver",
        "causal_backdoor": None, "info_experiment": None}
# dev seeds on which the candidate answers (others are deliberate counterindication instances)
ANSWER_SEEDS = {"mech_vcg": (0, 1, 2), "verify_modelcheck": (0, 1, 2, 3), "control_mpc": (0, 1, 2),
                "synth_cegis": (0, 1, 2, 3), "causal_backdoor": (0, 1, 2), "info_experiment": (0, 1, 2)}
BUDGET = {"latency_s": 5.0, "compute": 100000}
_CACHE: dict = {}


def item(family):
    return {x.genome.family: x for x in solvers_c.INTELLIGENCES}[family]


def dev(family, seed=1):
    assert 0 <= seed < 10                       # never a held-out seed
    key = (family, seed)
    if key not in _CACHE:
        _CACHE[key] = item(family).instance(seed)
    data, truth = _CACHE[key]
    return copy.deepcopy(data), truth


def solved(family, seed=1):
    key = ("solved", family, seed)
    if key not in _CACHE:
        data, truth = dev(family, seed)
        _CACHE[key] = item(family).solve(data, BUDGET)
    data, truth = dev(family, seed)
    return data, truth, copy.deepcopy(_CACHE[key])


def _json_clean(value):
    if isinstance(value, float):
        assert math.isfinite(value)
    elif isinstance(value, dict):
        assert all(isinstance(k, str) for k in value)
        for v in value.values():
            _json_clean(v)
    elif isinstance(value, list):
        assert len(value) <= 1000
        for v in value:
            _json_clean(v)
    else:
        assert value is None or type(value) in (str, int, bool)


# ------------------------------------------------------------------ genome contract
def test_genomes_validate_and_are_layer_three():
    assert sorted(x.genome.family for x in solvers_c.INTELLIGENCES) == sorted(FAMILIES)
    for x in solvers_c.INTELLIGENCES:
        g = x.genome
        assert isinstance(g, IntelligenceGenome) and g.validate() is g
        assert g.layer == 3 and g.buildability == "BUILDABLE_NOW" and g.standalone_decision
        assert g.operation == OPS[g.family] and g.epistemic_class == CLASSES[g.family]
        assert g.evidence_type == EVIDENCE[g.family] and g.dependency == DEPS[g.family]
        assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
        assert g.authority_ceiling == "read_only" and g.consequence_limit == "read_only"
        assert g.baseline and g.competitor and g.counterindications and g.abstention_conditions
        assert callable(x.subregion) and x.tolerance >= 0


def test_library_registers_batch_c_without_collisions():
    families = library.executables()
    catalog = library.catalog_families()
    for family in FAMILIES:
        assert families[family].genome.operation == OPS[family]
        assert catalog[family] == (3, (OPS[family],), (CLASSES[family],), library.PROOF_CLASS, DEPS[family])


def test_module_top_level_imports_no_heavy_packages():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(solvers_c))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top for a in n.names} | {n.module.split(".")[0] for n in top
                                                                      if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"numpy", "scipy", "networkx", "ortools", "z3"}


def test_no_authority_or_side_effect_primitives_in_module():
    import inspect
    import re
    source = inspect.getsource(solvers_c)
    for forbidden in (r"(?<![\w.])open\(", r"(?<![\w.])eval\(", r"(?<![\w.])exec\(", r"\bsubprocess\b",
                      r"\bos\.", r"\bsocket\b", r"\brequests\b", r"__import__", r"\bshutil\b"):
        assert not re.search(forbidden, source), forbidden


# ------------------------------------------------------------------ solve / verify round trip
@pytest.mark.parametrize("family,seed", [(f, s) for f in FAMILIES for s in ANSWER_SEEDS[f]])
def test_solve_returns_a_compact_json_answer_that_verifies(family, seed):
    data, truth, out = solved(family, seed)
    assert set(out) == {"output", "certificate", "status", "missing"} and out["status"] == "ANSWER"
    assert out["missing"] == []
    _json_clean(out["output"])
    _json_clean(out["certificate"])
    assert len(json.dumps(out, allow_nan=False)) < 64 * 1024
    json.dumps(data, allow_nan=False)
    checks = item(family).verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    assert item(family).score(data, truth, out["output"])["category"] == "correct"


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_adapter_runs_and_checks(family):
    data, _ = dev(family, ANSWER_SEEDS[family][1])
    result = library.run(family, data, {"latency_limit": 10})
    assert result["status"] == "ANSWER" and result["proof"]["evidence_type"] == EVIDENCE[family]
    checks = library.check(family, data, result["output"], result["proof"])
    assert all(checks.values()), checks


def test_both_verdict_forms_are_exercised_on_dev_seeds():
    mc = {solved("verify_modelcheck", s)[2]["output"]["verdict"] for s in ANSWER_SEEDS["verify_modelcheck"]}
    sy = {solved("synth_cegis", s)[2]["output"]["realizable"] for s in ANSWER_SEEDS["synth_cegis"]}
    assert mc == {"SAFE", "UNSAFE"} and sy == {True, False}


# ------------------------------------------------------------------ corrupted outputs are refuted
def _corrupt(family, data, out):
    o, c = copy.deepcopy(out["output"]), copy.deepcopy(out["certificate"])
    if family == "mech_vcg":                   # withhold one allocated unit, keep the efficiency claim
        values = [b["values"] for b in data["bidders"]]
        i = next(i for i, q in enumerate(o["allocation"]) if q > 0 and values[i][q - 1] > 0)
        o["allocation"][i] -= 1
    elif family == "verify_modelcheck":
        if o["verdict"] == "UNSAFE":           # truncate the counterexample
            o["commands"] = o["commands"][:-1]
        else:                                  # misreport the reachable-state count
            o["reachable_states"] += 1
    elif family == "control_mpc":              # perturb one input without updating the claimed cost
        o["inputs"][3] = max(-data["u_max"], min(data["u_max"], o["inputs"][3] + 0.1 * data["u_max"])) \
            if abs(o["inputs"][3]) < 0.9 * data["u_max"] else -o["inputs"][3]
    elif family == "synth_cegis":
        if o["realizable"]:                    # a constant rule cannot fit a labelling with both classes
            o["weights"], o["bias"] = [0] * len(o["weights"]), 1
        else:                                  # claim a rule where none exists
            o = {"realizable": True, "weights": [0] * data["n"], "bias": 1}
    elif family == "causal_backdoor":          # shift the estimate
        o["ate"] += 0.5
    elif family == "info_experiment":          # misreport the expected posterior on the truth
        o["expected_posterior_on_truth"] += 0.05
    return o, c


@pytest.mark.parametrize("family,seed", [(f, s) for f in FAMILIES for s in ANSWER_SEEDS[f][:2]])
def test_verify_refutes_a_corrupted_output(family, seed):
    data, _, out = solved(family, seed)
    o, c = _corrupt(family, data, out)
    checks = item(family).verify(data, o, c)
    assert not all(checks.values()), checks


def test_vcg_verify_refutes_tampered_payments_and_a_false_welfare():
    data, _, out = solved("mech_vcg", 1)
    o = copy.deepcopy(out["output"])
    winner = next(i for i, q in enumerate(o["allocation"]) if q > 0)
    o["payments"][winner] += 1.0
    checks = solvers_c.vcg_verify(data, o, out["certificate"])
    assert checks["allocatively_optimal_by_independent_dp"] and not checks["payments_equal_clarke_externalities"]
    o = dict(out["output"], welfare=out["output"]["welfare"] + 1.0)
    assert not solvers_c.vcg_verify(data, o, out["certificate"])["welfare_recomputed"]


def test_vcg_matches_the_analytic_clarke_pivot():
    single = {"units": 1, "bidders": [{"values": [10.0]}, {"values": [7.0]}, {"values": [3.0]}]}
    out = solvers_c.vcg_solve(single, BUDGET)["output"]
    assert out["allocation"] == [1, 0, 0] and out["payments"] == [7.0, 0.0, 0.0]       # second price
    two = {"units": 2, "bidders": [{"values": [10.0, 8.0]}, {"values": [9.0]}, {"values": [1.0]}]}
    out = solvers_c.vcg_solve(two, BUDGET)["output"]
    assert out["allocation"] == [1, 1, 0] and out["welfare"] == 19.0
    assert out["payments"] == [1.0, 8.0, 0.0]                                          # externalities
    general = {"units": 2, "bidders": [{"values": [1.0, 9.0]}, {"values": [6.0]}]}     # non-diminishing
    out = solvers_c.vcg_solve(general, BUDGET)
    assert out["output"]["allocation"] == [2, 0] and out["output"]["payments"] == [6.0, 0.0]
    assert all(solvers_c.vcg_verify(general, out["output"], out["certificate"]).values())


def test_modelcheck_verify_refutes_a_safe_claim_that_copies_the_true_count_and_digest():
    data, truth, out = solved("verify_modelcheck", 0)
    assert out["output"]["verdict"] == "UNSAFE" and truth["safe"] is False
    forged = {"verdict": "SAFE", "reachable_states": truth["reachable_states"]}
    checks = solvers_c.mc_verify(data, forged, {"state_digest": truth["digest"]})
    assert checks["reachable_count_matches"] and checks["reachable_set_digest_matches"]
    assert not checks["invariant_holds_on_every_reachable_state"]
    assert solvers_c.mc_score(data, truth, forged) == {"quality": -1.0, "category": "wrong"}


def test_modelcheck_safe_counts_match_the_independent_dfs_truth():
    for seed in (1, 3):
        data, truth, out = solved("verify_modelcheck", seed)
        assert out["output"] == {"verdict": "SAFE", "reachable_states": truth["reachable_states"]}
        assert out["certificate"]["state_digest"] == truth["digest"]


def test_modelcheck_counterexample_is_shortest_and_replays():
    data, _, out = solved("verify_modelcheck", 2)
    o = out["output"]
    assert o["verdict"] == "UNSAFE" and o["depth"] == len(o["commands"])
    assert all(solvers_c._mc_replay(solvers_c._mc_system(data), o).values())
    walk = solvers_c.mc_random_walk(data)
    if walk["verdict"] == "UNSAFE":                               # BFS is never longer than any found trace
        assert len(o["commands"]) <= len(walk["commands"])


def test_mpc_verify_refutes_a_bound_violation():
    data, _, out = solved("control_mpc", 1)
    o = copy.deepcopy(out["output"])
    o["inputs"][0] = 1.5 * data["u_max"]
    checks = solvers_c.mpc_verify(data, o, {})
    assert not checks["inputs_within_bounds"]


def test_mpc_reduces_to_lqr_when_bounds_are_inactive():
    data, _ = dev("control_mpc", 4)
    data.update(u_max=1e5, preview=False)
    mpc = solvers_c.mpc_solve(data, BUDGET)["output"]["inputs"]
    lqr = solvers_c.mpc_lqr(data)["inputs"]
    assert max(abs(a - b) for a, b in zip(mpc, lqr)) < 1e-5


def test_cegis_verify_refutes_a_false_unrealizability_claim():
    data, truth, _ = solved("synth_cegis", 0)
    assert truth["realizable"]
    checks = solvers_c.cegis_verify(data, {"realizable": False}, {"unsat_witness": list(range(30))})
    assert checks["witness_well_formed"] and not checks["witness_infeasible_by_independent_milp"]


def test_causal_verify_refutes_a_swapped_adjustment_set():
    data, _, out = solved("causal_backdoor", 1)
    o = dict(out["output"], adjustment_set=[])
    assert not solvers_c.causal_verify(data, o, out["certificate"])["adjustment_set_is_declared"]


def test_info_verify_refutes_a_self_consistent_but_non_greedy_policy():
    data, _, out = solved("info_experiment", 1)
    prior, tables, length = solvers_c._ie(data)
    import numpy as np

    def worst(post, P, depth):
        return int(np.argmin([solvers_c._eig(post, p) for p in P]))
    tree = solvers_c._ie_build(prior, tables, length, worst)
    forged = {"policy": tree, "expected_posterior_on_truth": solvers_c._ie_value(tree, prior, tables)}
    checks = solvers_c.ie_verify(data, forged, {})
    assert checks["policy_well_formed"] and checks["expected_value_recomputed"]
    assert not checks["every_node_maximises_information_gain"]


# ------------------------------------------------------------------ invalid input
def _mc_sys(**overrides):
    system = {"variables": [{"name": "x", "min": 0, "max": 3, "init": 0}],
              "commands": [{"name": "inc", "guard": ["<", "x", 3], "update": {"x": ["+", "x", 1]}}],
              "invariant": ["<=", "x", 3]}
    system.update(overrides)
    return {"system": system}


_MPC = {"dt": 0.1, "u_max": 1.0, "x0": [0.0, 0.0], "reference": [0.0, 1.0, 1.0], "disturbance": [0.0, 0.0],
        "weights": {"q_pos": 1.0, "r_u": 0.01}}
_CA = {"nodes": [{"name": "T", "type": "binary"}, {"name": "Y", "type": "continuous"}],
       "edges": [["T", "Y"]], "treatment": "T", "outcome": "Y", "adjustment_set": [],
       "samples": {"T": [0, 1] * 15, "Y": [float(i) for i in range(30)]}}
_IE = {"prior": [0.5, 0.5], "tests": [{"likelihood": [[0.9, 0.1], [0.2, 0.8]]}], "length": 1}

INVALID = {
    "mech_vcg": [{"units": 0, "bidders": [{"values": [1.0]}]}, {"units": 1, "bidders": []},
                 {"units": 1, "bidders": [{"values": [-1.0]}]}, {"units": 1, "bidders": [{"values": [float("nan")]}]},
                 {"units": True, "bidders": [{"values": [1.0]}]}],
    "verify_modelcheck": [
        _mc_sys(invariant=["<=", "y", 3]),                                           # unknown variable
        _mc_sys(invariant=["**", "x", 2]),                                           # unknown operator
        _mc_sys(invariant=["+", "x", 1]),                                            # not boolean
        _mc_sys(commands=[{"name": "sq", "guard": True, "update": {"x": ["*", "x", "x"]}}]),   # nonlinear
        _mc_sys(commands=[{"name": "big", "guard": True,
                           "update": {"x": ["*", ["*", ["*", ["*", "x", 99999], 99999], 99999], 99999]}}]),
        _mc_sys(variables=[{"name": "x", "min": 0, "max": 3, "init": 7}]),           # init out of range
        _mc_sys(variables=[{"name": "and", "min": 0, "max": 3, "init": 0}]),         # reserved name
        {"system": "x := x + 1"}],
    "control_mpc": [dict(_MPC, x0=[0.0, 0.0, 0.0]), dict(_MPC, reference=[0.0]),
                    dict(_MPC, disturbance=[0.0]), dict(_MPC, dt=float("nan")), dict(_MPC, preview="yes"),
                    dict(_MPC, u_max=-1.0)],
    "synth_cegis": [{"n": 3, "weight_bound": 4, "labels": "f"},                       # wrong width
                    {"n": 0, "weight_bound": 4, "labels": "1"},
                    {"n": 3, "weight_bound": 0, "labels": "0f"},
                    {"n": 3, "weight_bound": 4, "labels": "0F"},
                    {"n": 3, "weight_bound": 4, "labels": "0f", "spec": "sorting"}],
    "causal_backdoor": [dict(_CA, edges=[["T", "Y"], ["Y", "T"]]),                   # cycle
                        dict(_CA, treatment="Y", outcome="T"),                        # continuous treatment
                        dict(_CA, adjustment_set=["T"]),
                        dict(_CA, samples={"T": [0, 1] * 5, "Y": [0.0] * 10}),        # too few rows
                        dict(_CA, nodes=_CA["nodes"] + [{"name": "U", "observed": False}],
                             samples=dict(_CA["samples"], U=[0.0] * 30))],             # samples of a latent node
    "info_experiment": [dict(_IE, prior=[0.5, 0.6]), dict(_IE, tests=[{"likelihood": [[0.9, 0.2], [0.2, 0.8]]}]),
                        dict(_IE, tests=[{"likelihood": [[1.0], [1.0]]}]), dict(_IE, length=0),
                        dict(_IE, test_costs=3), dict(_IE, test_costs=[1.0, 2.0])],
}


@pytest.mark.parametrize("family", FAMILIES)
def test_invalid_input_raises_genome_error(family):
    for data in INVALID[family]:
        with pytest.raises(GenomeError):
            item(family).solve(copy.deepcopy(data), BUDGET)


@pytest.mark.parametrize("family", FAMILIES)
def test_invalid_input_raises_genome_error_in_verify_too(family):
    with pytest.raises(GenomeError):
        item(family).verify(copy.deepcopy(INVALID[family][0]), {}, {})


# ------------------------------------------------------------------ abstention
ABSTAIN = {
    "mech_vcg": [{"units": 2, "bidders": [{"values": [5.0]}, {"values": [3.0]}], "budgets": [4.0, 9.0]},
                 {"units": 2, "bidders": [{"values": [5.0]}, {"values": [3.0]}], "value_model": "common"},
                 {"units": 200, "bidders": [{"values": [float(v) for v in range(1, 21)]}] * 50}],
    "verify_modelcheck": [dict(_mc_sys(), property="liveness")],
    "control_mpc": [dict(_MPC, state_bounds={"position": [-1.0, 1.0]}), dict(_MPC, measurement="position_only")],
    "synth_cegis": [{"n": 14, "weight_bound": 4, "labels": "0" * 4096}],
    "causal_backdoor": [dict(_CA, nodes=_CA["nodes"] + [{"name": "Z", "type": "binary"}],
                             edges=[["T", "Y"], ["Z", "T"], ["Z", "Y"]])],               # confounder not adjusted
    "info_experiment": [dict(_IE, test_costs=[1.0, 5.0], tests=_IE["tests"] * 2),
                        dict(_IE, tests=[{"likelihood": [[0.25] * 4, [0.4, 0.2, 0.2, 0.2]]}], length=8)],
}


@pytest.mark.parametrize("family", FAMILIES)
def test_abstains_outside_native_competence(family):
    for data in ABSTAIN[family]:
        out = item(family).solve(copy.deepcopy(data), BUDGET)
        assert out["status"] == "ABSTAIN" and out["output"] is None and out["missing"], (family, out)
        _json_clean(out["certificate"])


def test_dev_counterindication_instances_abstain():
    for family, seeds in (("verify_modelcheck", (4,)), ("causal_backdoor", (3, 4))):
        for seed in seeds:
            data, truth, out = solved(family, seed)
            assert out["status"] == "ABSTAIN" and out["missing"]
            assert item(family).score(data, truth, None)["category"] == "abstain"
    data, _, out = solved("verify_modelcheck", 4)
    assert "state explosion" in out["missing"][0]


def test_causal_abstains_on_a_positivity_failure():
    data = dict(_CA, nodes=_CA["nodes"] + [{"name": "Z", "type": "binary"}],
                edges=[["T", "Y"], ["Z", "T"], ["Z", "Y"]], adjustment_set=["Z"],
                samples={"T": [0, 1] * 15, "Y": [float(i) for i in range(30)], "Z": [0] * 28 + [1, 1]})
    data["samples"]["T"][28:] = [1, 1]                       # stratum Z=1 has no control units
    out = solvers_c.causal_solve(data, BUDGET)
    assert out["status"] == "ABSTAIN" and "positivity" in out["missing"][0]


def test_modelcheck_competitor_is_bounded_by_one_total_budget(monkeypatch):
    data, _ = dev("verify_modelcheck", 4)                    # a deep bug beyond BMC depth: inconclusive
    monkeypatch.setattr(solvers_c, "MC_Z3_SECONDS", 0.5)
    started = time.perf_counter()
    assert solvers_c.mc_bmc_kinduction(data) is None
    assert time.perf_counter() - started < 2.5


# ------------------------------------------------------------------ scoring
def _wrong_output(family, data, out):
    if family == "mech_vcg":                                 # a false efficiency claim
        return _corrupt(family, data, out)[0]
    if family == "verify_modelcheck":
        return {"verdict": "SAFE" if out["output"]["verdict"] == "UNSAFE" else "UNSAFE", "initial": [],
                "commands": [], "violating_state": []}
    if family == "control_mpc":                              # an input-bound violation
        return dict(out["output"], inputs=[2.0 * data["u_max"]] * len(out["output"]["inputs"]), cost=None)
    if family == "synth_cegis":
        return _corrupt(family, data, out)[0]
    if family == "causal_backdoor":                          # a causal claim from a non-identifying set
        return {"ate": out["output"]["ate"], "adjustment_set": [], "estimator": "difference_in_means"}
    return {"policy": {"test": 10 ** 6, "next": []}}         # an impossible test


@pytest.mark.parametrize("family", FAMILIES)
def test_score_categories(family):
    x = item(family)
    data, truth, out = solved(family, ANSWER_SEEDS[family][0])
    correct = x.score(data, truth, out["output"])
    assert correct["category"] == "correct"
    abstain = x.score(data, truth, None)
    assert abstain["category"] == "abstain"
    wrong = x.score(data, truth, _wrong_output(family, data, out))
    assert wrong["category"] == "wrong"
    assert wrong["quality"] < abstain["quality"] and wrong["quality"] < correct["quality"]


def test_causal_answering_a_non_identified_instance_is_wrong_and_abstaining_is_not():
    data, truth = dev("causal_backdoor", 3)
    assert not truth["identified"]
    naive = solvers_c.causal_naive(data)
    assert solvers_c.causal_score(data, truth, naive)["category"] == "wrong"
    assert solvers_c.causal_score(data, truth, None) == {"quality": 0.0, "category": "abstain"}


def test_vcg_scores_individual_rationality_violations_as_wrong():
    data, truth, out = solved("mech_vcg", 1)
    o = copy.deepcopy(out["output"])
    i = next(i for i, q in enumerate(o["allocation"]) if q > 0)
    o["payments"][i] = sum(data["bidders"][i]["values"]) + 1.0
    assert solvers_c.vcg_score(data, truth, o) == {"quality": -1.0, "category": "wrong"}


@pytest.mark.parametrize("family", FAMILIES)
def test_candidate_is_not_worse_than_the_baseline_on_a_dev_instance(family):
    x = item(family)
    data, truth, out = solved(family, ANSWER_SEEDS[family][1])
    assert x.score(data, truth, out["output"])["quality"] >= x.score(data, truth, x.baseline(data))["quality"] - 1e-9


def test_competitors_answer_in_contract_on_a_dev_instance():
    for family in FAMILIES:
        x = item(family)
        data, truth = dev(family, 1)
        result = x.score(data, truth, x.competitor(data))
        assert result["category"] in ("correct", "wrong", "abstain") and math.isfinite(result["quality"])


# ------------------------------------------------------------------ determinism and runtime
@pytest.mark.parametrize("family", FAMILIES)
def test_instances_and_solves_are_deterministic(family):
    seed = ANSWER_SEEDS[family][-1]
    first, _ = item(family).instance(seed)
    again, _ = item(family).instance(seed)
    assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)
    data, _, out = solved(family, seed)
    assert item(family).solve(copy.deepcopy(data), BUDGET) == out


def test_z3_backed_arms_are_reproducible_within_one_process():
    # Z3 models depend on term ids in a shared context; each call must use a private context.
    for seed in (0, 1, 4):
        data, _ = dev("synth_cegis", seed)
        outs = {json.dumps(solvers_c.cegis_solve(copy.deepcopy(data), BUDGET), sort_keys=True) for _ in range(3)}
        assert len(outs) == 1
        assert len({json.dumps(solvers_c.cegis_sample(data), sort_keys=True) for _ in range(2)}) == 1
    data, _ = dev("verify_modelcheck", 0)
    assert len({json.dumps(solvers_c.mc_bmc_kinduction(data), sort_keys=True) for _ in range(2)}) == 1


@pytest.mark.parametrize("family", FAMILIES)
def test_dev_seeds_run_within_budget_and_never_answer_falsely(family):
    x = item(family)
    for seed in range(10):
        started = time.perf_counter()
        data, truth = dev(family, seed)
        t0 = time.perf_counter()
        out = x.solve(copy.deepcopy(data), BUDGET)
        solve_s = time.perf_counter() - t0
        assert solve_s < 2.0, (family, seed, solve_s)
        if out["status"] == "ANSWER":
            assert all(x.verify(data, out["output"], out["certificate"]).values()), (family, seed)
            assert x.score(data, truth, out["output"])["category"] == "correct", (family, seed)
        else:
            assert out["status"] in ("ABSTAIN", "UNKNOWN") and out["missing"]
        assert time.perf_counter() - started < 5.0, (family, seed)
