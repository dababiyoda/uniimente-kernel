"""Layer 3 pack C IntelligenceGenomes (strategic and temporal formal methods): contract, validation, independent
verification, abstention, scoring, determinism and dev-seed runtime.

Development seeds 0-9 and review seeds 3000-3999 only; held-out admission seeds are never generated here.
"""
from __future__ import annotations

import copy
import json
import math
import sys
import time
import types

import pytest

from greg.cognition.genomes import library, strategic
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

FAMILIES = ("bimatrix_nash", "mechanism_check", "verify_liveness")
OPS = {"bimatrix_nash": "bimatrix_nash_equilibrium", "mechanism_check": "mechanism_ic_ir_check",
       "verify_liveness": "model_check_liveness"}
CLASSES = {"bimatrix_nash": "strategic", "mechanism_check": "strategic", "verify_liveness": "deductive"}
EVIDENCE = {"bimatrix_nash": "exact_calculation", "mechanism_check": "exhaustive_check",
            "verify_liveness": "exhaustive_check"}
DEPS = {"bimatrix_nash": "scipy", "mechanism_check": None, "verify_liveness": "scipy"}
ANSWER_SEEDS = {"bimatrix_nash": (0, 1, 2, 3), "mechanism_check": (0, 1, 2, 4), "verify_liveness": (0, 1, 4, 6)}
BUDGET = {"latency_s": 5.0, "compute": 100000}
_CACHE: dict = {}


def item(family):
    return {x.genome.family: x for x in strategic.INTELLIGENCES}[family]


def dev(family, seed=1):
    assert 0 <= seed < 10 or 3000 <= seed < 4000            # never a held-out or reserved seed
    key = (family, seed)
    if key not in _CACHE:
        _CACHE[key] = item(family).instance(seed)
    data, truth = _CACHE[key]
    return copy.deepcopy(data), truth


def solved(family, seed=1):
    key = ("solved", family, seed)
    if key not in _CACHE:
        data, _ = dev(family, seed)
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
    assert sorted(x.genome.family for x in strategic.INTELLIGENCES) == sorted(FAMILIES)
    for x in strategic.INTELLIGENCES:
        g = x.genome
        assert isinstance(g, IntelligenceGenome) and g.validate() is g
        assert g.layer == 3 and g.buildability == "BUILDABLE_NOW" and g.standalone_decision
        assert g.operation == OPS[g.family] and g.epistemic_class == CLASSES[g.family]
        assert g.evidence_type == EVIDENCE[g.family] and g.dependency == DEPS[g.family]
        assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
        assert g.authority_ceiling == "read_only" and g.consequence_limit == "read_only"
        assert g.baseline and g.competitor and g.counterindications and g.abstention_conditions
        assert callable(x.subregion) and x.tolerance >= 0 and x.competitor_deployable and x.instance_key is None


def test_library_registers_pack_c_without_collisions_and_withholds_it():
    from greg.cognition import catalog
    families = library.executables()
    projected = library.catalog_families()
    assert "greg.cognition.genomes.strategic" in library.MODULES
    for family in FAMILIES:
        assert families[family].genome.operation == OPS[family]
        assert projected[family] == (3, (OPS[family],), (CLASSES[family],), library.PROOF_CLASS, DEPS[family])
        assert catalog.FAMILIES[family] == projected[family]
        assert catalog.initial_state(f"cognition.{family}") == "VERIFIED"        # registered, never auto-attached
    # the admitted safety checker is reused, not edited or shadowed
    assert families["verify_modelcheck"].genome.operation == "model_check_safety"


def test_module_top_level_imports_no_heavy_packages():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(strategic))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top for a in n.names} | {n.module.split(".")[0] for n in top
                                                                      if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"numpy", "scipy", "networkx", "ortools", "z3", "nashpy"}


def test_no_authority_or_side_effect_primitives_in_module():
    import inspect
    import re
    source = inspect.getsource(strategic)
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


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_path_withholds_until_attached_and_creates_no_authority(family):
    from greg.cognition.cortex import reason, registry_view
    data, _ = dev(family, 1)
    registry = registry_view()
    problem = {"problem_id": f"pack-c:{family}", "operation": OPS[family], "data": data,
               "geometry": {"latency_limit": 30}}
    assert reason(problem, registry=registry)["abstention_state"] == "CAPABILITY_DEFICIT"
    registry.set_state(f"cognition.{family}", "ATTACHED")                   # evaluation-only view
    r = reason(problem, registry=registry)
    assert r["abstention_state"] == "NONE" and r["proof_type"] == "genome_certificate"
    assert r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" and r["authority_created"] is False


def test_both_verdict_forms_are_exercised_on_dev_seeds():
    mech = {solved("mechanism_check", s)[2]["output"]["verdict"] for s in range(10)}
    live = {solved("verify_liveness", s)[2]["output"]["verdict"] for s in range(10)}
    kinds = {solved("verify_liveness", s)[2]["output"].get("counterexample") for s in range(10)}
    subregions = {item("bimatrix_nash").subregion(dev("bimatrix_nash", s)[0]) for s in range(10)}
    assert mech == {"HOLDS", "VIOLATION"} and live == {"HOLDS", "VIOLATED"} and "lasso" in kinds
    assert subregions == {"no_pure", "one_pure", "multi_pure"}


# ------------------------------------------------------------------ corrupted outputs are refuted
def _corrupt(family, data, out):
    o, c = copy.deepcopy(out["output"]), copy.deepcopy(out["certificate"])
    if family == "bimatrix_nash":              # move weight to another row without updating anything else
        x = o["row_strategy"]
        i = max(range(len(x)), key=lambda k: x[k])
        x[i], x[(i + 1) % len(x)] = x[(i + 1) % len(x)], x[i]
        if x[i] == x[(i + 1) % len(x)]:
            o["row_payoff"] += 1.0
    elif family == "mechanism_check":
        if o["verdict"] == "VIOLATION":        # claim the mechanism is fine
            o = {"verdict": "HOLDS", "dsic": {"holds": True, "max_gain": 0.0, "witness": None},
                 "ir": {"holds": True, "min_slack": 0.0, "witness": None}}
        else:                                  # invent a misreport
            o["verdict"] = "VIOLATION"
            o["dsic"] = {"holds": False, "max_gain": 1.0, "witness": {"agent": 0, "true_type": 0, "reported_type": 1,
                                                                      "others": [0] * (len(data["agents"]) - 1),
                                                                      "gain": 1.0}}
    else:
        if o["verdict"] == "VIOLATED":         # truncate the cycle (or the stem of a deadlock)
            if o["cycle"]:
                o["cycle"] = o["cycle"][:-1]
            else:
                o["stem"] = o["stem"][:-1]
        else:
            o["region_states"] += 1
    return o, c


@pytest.mark.parametrize("family,seed", [(f, s) for f in FAMILIES for s in ANSWER_SEEDS[f]])
def test_verify_refutes_a_corrupted_output(family, seed):
    data, _, out = solved(family, seed)
    o, c = _corrupt(family, data, out)
    checks = item(family).verify(data, o, c)
    assert not all(checks.values()), checks


def _leaf_mutants(value, path=()):
    """Every single-leaf corruption of an output: flip a bool, shift a number, drop a list's last element,
    suffix a string. A sound verifier refutes each one that changes a claim."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _leaf_mutants(v, path + (k,))
    elif isinstance(value, list):
        if value and all(not isinstance(v, (dict, list)) for v in value):
            yield path, value[:-1]
        for i, v in enumerate(value[:3]):
            yield from _leaf_mutants(v, path + (i,))
    elif type(value) is bool:
        yield path, not value
    elif isinstance(value, (int, float)):
        yield path, value * 1.37 + 1 if isinstance(value, float) else value + 1
    elif isinstance(value, str):
        yield path, value + "_x"


def _set(obj, path, value):
    for k in path[:-1]:
        obj = obj[k]
    obj[path[-1]] = value


@pytest.mark.parametrize("family", FAMILIES)
def test_every_single_leaf_corruption_of_an_answer_is_refuted(family):
    x = item(family)
    for seed in ANSWER_SEEDS[family]:
        data, _, out = solved(family, seed)
        survivors = []
        for path, value in _leaf_mutants(out["output"]):
            if not path:
                continue
            forged = copy.deepcopy(out["output"])
            _set(forged, path, value)
            try:
                accepted = all(x.verify(data, forged, out["certificate"]).values())
            except Exception:                      # a verifier must refute malformed output, not raise
                accepted = "raised"
            if accepted:
                survivors.append((path, accepted))
        assert not survivors, (family, seed, survivors)


# ------------------------------------------------------------------ bimatrix Nash
def _pure_profile(data, i, j):
    a, b = data["row_payoffs"], data["column_payoffs"]
    x, y = [0.0] * len(a), [0.0] * len(a[0])
    x[i], y[j] = 1.0, 1.0
    return {"row_strategy": x, "column_strategy": y, "row_payoff": float(a[i][j]),
            "column_payoff": float(b[i][j]), "welfare": float(a[i][j] + b[i][j])}


def test_nash_verify_refutes_a_lower_welfare_equilibrium_that_claims_to_be_maximal():
    data, truth, out = solved("bimatrix_nash", 1)                       # coordination: many equilibria
    assert truth["equilibria"] > 3 and truth["max_welfare"] > truth["min_welfare"]
    pure = strategic._pure_equilibria(data["row_payoffs"], data["column_payoffs"])
    worst = min(pure, key=lambda ij: data["row_payoffs"][ij[0]][ij[1]] + data["column_payoffs"][ij[0]][ij[1]])
    profile = _pure_profile(data, *worst)
    exact = {"row_strategy": [str(int(p)) for p in profile["row_strategy"]],
             "column_strategy": [str(int(q)) for q in profile["column_strategy"]],
             "row_payoff": str(int(profile["row_payoff"])), "column_payoff": str(int(profile["column_payoff"]))}
    cert = dict(out["certificate"], exact=exact)
    claimed = dict(profile, selection="max_welfare_nash", correlated=None)
    checks = strategic.nash_verify(data, claimed, cert)
    assert checks["row_payoff_equals_best_pure_response"] and checks["column_payoff_equals_best_pure_response"]
    assert checks["exact_certificate_is_an_exact_equilibrium"]
    assert checks["welfare_maximal_over_all_equilibria_by_independent_milp"] is False
    assert strategic.nash_score(data, truth, claimed)["category"] == "wrong"
    honest = dict(claimed, selection="nash")                            # an equilibrium, no welfare claim
    assert all(strategic.nash_verify(data, honest, cert).values())
    assert 0.5 <= strategic.nash_score(data, truth, honest)["quality"] < 1.0


def test_nash_verify_refutes_a_mixed_profile_that_is_not_an_equilibrium():
    data, _, out = solved("bimatrix_nash", 2)                           # no pure equilibrium
    m, n = len(data["row_payoffs"]), len(data["row_payoffs"][0])
    uniform = {"row_strategy": [1.0 / m] * m, "column_strategy": [1.0 / n] * n, "selection": "nash",
               "correlated": None}
    a, b = data["row_payoffs"], data["column_payoffs"]
    uniform["row_payoff"] = sum(a[i][j] for i in range(m) for j in range(n)) / (m * n)
    uniform["column_payoff"] = sum(b[i][j] for i in range(m) for j in range(n)) / (m * n)
    uniform["welfare"] = uniform["row_payoff"] + uniform["column_payoff"]
    checks = strategic.nash_verify(data, uniform, out["certificate"])
    assert checks["payoffs_recomputed"] and checks["valid_distributions"]
    assert not (checks["row_payoff_equals_best_pure_response"] and checks["column_payoff_equals_best_pure_response"])


def test_correlated_equilibrium_is_certified_by_its_dual_and_a_suboptimal_one_is_refuted():
    data, _, out = solved("bimatrix_nash", 3)
    ce, dual = out["output"]["correlated"], out["certificate"]["correlated_dual"]
    assert ce["welfare"] >= out["output"]["welfare"] - 1e-9                # every Nash equilibrium is correlated
    product = [[p * q for q in out["output"]["column_strategy"]] for p in out["output"]["row_strategy"]]
    a, b = data["row_payoffs"], data["column_payoffs"]
    welfare = sum(product[i][j] * (a[i][j] + b[i][j]) for i in range(len(a)) for j in range(len(a[0])))
    if welfare < ce["welfare"] - 1e-6:                                     # the product plan is a worse CE
        forged = dict(out["output"], correlated={"distribution": product, "welfare": welfare,
                                                 "objective": "max_welfare"})
        checks = strategic.nash_verify(data, forged, out["certificate"])
        assert checks["correlated_incentive_constraints_hold"]
        assert checks["correlated_welfare_optimal_by_dual_certificate"] is False
    lowered = dict(out["certificate"], correlated_dual=dict(dual, bound=dual["bound"] - 1.0))
    checks = strategic.nash_verify(data, out["output"], lowered)
    assert checks["correlated_welfare_optimal_by_dual_certificate"] is False
    inflated = copy.deepcopy(out["output"])
    inflated["correlated"]["welfare"] += 0.5
    assert strategic.nash_verify(data, inflated, out["certificate"])["correlated_welfare_recomputed"] is False


def test_nash_withholds_the_welfare_claim_on_a_degenerate_game():
    data = {"row_payoffs": [[1, 1], [1, 1]], "column_payoffs": [[2, 2], [2, 2]]}
    out = strategic.nash_solve(data, BUDGET)
    assert out["status"] == "ANSWER" and out["output"]["selection"] == "nash"
    assert out["certificate"]["degeneracy_symptoms"]["extra_pure_best_responses"]
    checks = strategic.nash_verify(data, out["output"], out["certificate"])
    assert all(checks.values()) and "welfare_maximal_over_all_equilibria_by_independent_milp" not in checks


def test_nash_matches_textbook_equilibria():
    pennies = {"row_payoffs": [[1, -1], [-1, 1]], "column_payoffs": [[-1, 1], [1, -1]]}
    out = strategic.nash_solve(pennies, BUDGET)
    assert out["output"]["row_strategy"] == [0.5, 0.5] and out["output"]["column_strategy"] == [0.5, 0.5]
    assert out["certificate"]["exact"]["row_strategy"] == ["1/2", "1/2"]
    assert strategic.nash_pure_search(pennies) is None                    # the baseline has no decision
    battle = {"row_payoffs": [[3, 0], [0, 2]], "column_payoffs": [[2, 0], [0, 3]]}
    out = strategic.nash_solve(battle, BUDGET)
    assert out["certificate"]["equilibria_found"] == 3 and out["output"]["welfare"] == 5.0
    assert out["certificate"]["exact"]["row_strategy"] in (["1", "0"], ["0", "1"])
    assert all(strategic.nash_verify(battle, out["output"], out["certificate"]).values())


def test_nash_competitor_is_honest_when_its_dynamics_do_not_converge():
    data, truth = dev("bimatrix_nash", 3089)                             # a 6 x 6 game where it fails
    assert strategic.nash_competitor(data) is None
    assert item("bimatrix_nash").score(data, truth, None)["category"] == "abstain"
    for seed in range(10):                                               # it never answers falsely
        data, truth = dev("bimatrix_nash", seed)
        result = strategic.nash_competitor(data)
        assert result is None or item("bimatrix_nash").score(data, truth, result)["category"] == "correct"


def test_nash_competitor_uses_lemke_howson_when_nashpy_is_installed(monkeypatch):
    data, _, out = solved("bimatrix_nash", 2)
    calls = []

    class Game:
        def __init__(self, A, B):
            self.shape = A.shape

        def lemke_howson(self, initial_dropped_label):
            calls.append(initial_dropped_label)
            if initial_dropped_label == 0:
                raise ValueError("pivoting failed")                       # a third-party failure is skipped
            return out["output"]["row_strategy"], out["output"]["column_strategy"]
    monkeypatch.setitem(sys.modules, "nashpy", types.SimpleNamespace(Game=Game))
    result = strategic.nash_competitor(data)
    assert calls == [0, 1] and result["method"].startswith("lemke_howson (nashpy)")
    assert item("bimatrix_nash").score(data, dev("bimatrix_nash", 2)[1], result)["category"] == "correct"


# ------------------------------------------------------------------ mechanism DSIC / IR
def _auction(kind, levels=((2, 5, 9), (1, 4, 8))):
    """Two-bidder single-item auction over small type grids, tables built by hand for analytic checks."""
    from itertools import product
    alloc, pay = [], []
    for prof in product(*[range(len(lv)) for lv in levels]):
        bids = [levels[i][t] for i, t in enumerate(prof)]
        w = 0 if bids[0] >= bids[1] else 1
        p = [0, 0]
        p[w] = bids[w] if kind == "first" else bids[1 - w]
        alloc.append(w + 1)
        pay.append(p)
    agents = [{"values": [[0, v if i == 0 else 0, v if i == 1 else 0] for v in lv]} for i, lv in enumerate(levels)]
    return {"agents": agents, "outcomes": ["none", "a0", "a1"], "allocation": alloc, "payments": pay}


def test_mechanism_matches_analytic_second_and_first_price_auctions():
    second = strategic.mech_solve(_auction("second"), BUDGET)["output"]
    assert second["verdict"] == "HOLDS" and second["dsic"]["holds"] and second["ir"]["holds"]
    first = strategic.mech_solve(_auction("first"), BUDGET)
    o = first["output"]
    # bidder 0 with value 9 facing a bid of 1 pays 9 truthfully; reporting 2 still wins and pays 2: gain 7
    assert o["verdict"] == "VIOLATION" and o["dsic"]["max_gain"] == 7.0 and o["ir"]["holds"]
    assert o["dsic"]["witness"] == {"agent": 0, "true_type": 2, "reported_type": 0, "others": [0], "gain": 7.0}
    assert all(strategic.mech_verify(_auction("first"), o, first["certificate"]).values())


def test_mechanism_verify_refutes_a_genuine_but_non_canonical_misreport():
    data = _auction("first")
    out = strategic.mech_solve(data, BUDGET)
    forged = copy.deepcopy(out["output"])
    # bidder 1 with value 8 facing a bid of 2 pays 8 truthfully; reporting 4 still wins and pays 4: gain 4
    forged["dsic"]["witness"] = {"agent": 1, "true_type": 2, "reported_type": 1, "others": [0], "gain": 4.0}
    checks = strategic.mech_verify(data, forged, out["certificate"])
    assert checks["dsic_witness_gain_replayed"] and checks["dsic_max_gain_recomputed"]   # a real profitable lie
    assert checks["dsic_witness_is_the_first_maximal_misreport"] is False


def test_mechanism_verify_refutes_holds_on_a_rare_violation_that_sampling_misses():
    data, truth, out = solved("mechanism_check", 2)                     # second price with a planted corner
    assert not truth["dsic_holds"] and truth["profitable_misreports"] < 20
    sampled = strategic.mech_sampled(data)
    assert sampled["verdict"] == "HOLDS"
    assert strategic.mech_score(data, truth, sampled)["category"] == "wrong"
    assert not all(strategic.mech_verify(data, sampled, out["certificate"]).values())
    assert strategic.mech_score(data, truth, out["output"]) == {"quality": 1.0, "category": "correct"}


def test_mechanism_milp_competitor_agrees_with_exhaustive_enumeration():
    for seed in range(10):
        data, truth, out = solved("mechanism_check", seed)
        milp = strategic.mech_milp(data)
        assert milp["dsic"]["holds"] == out["output"]["dsic"]["holds"]
        assert abs(milp["dsic"]["max_gain"] - out["output"]["dsic"]["max_gain"]) <= 1e-6
        assert abs(milp["ir"]["min_slack"] - out["output"]["ir"]["min_slack"]) <= 1e-6
        assert strategic.mech_score(data, truth, milp)["category"] == "correct"


def test_clarke_public_project_is_truthful_but_can_fail_participation():
    for seed in range(3000, 3100):
        data, truth = dev("mechanism_check", seed)
        if data["name"].startswith("public_project:clarke") and not truth["ir_holds"]:
            break
    else:
        pytest.fail("no Clarke project with a participation failure on the review seeds")
    out = strategic.mech_solve(data, BUDGET)["output"]
    assert out["dsic"]["holds"] and out["dsic"]["witness"] is None
    assert not out["ir"]["holds"] and out["ir"]["witness"]["slack"] < 0


# ------------------------------------------------------------------ liveness
def _counter(variant="reset", top=12, back=8):
    commands = [{"name": "inc", "guard": ["<", "x", top], "update": {"x": ["+", "x", 1]}},
                {"name": "tick", "guard": True, "update": {"t": ["mod", ["+", "t", 1], 2]}}]
    if variant == "reset":
        commands.append({"name": "reset", "guard": ["==", "x", back], "update": {"x": 0}})
    return {"system": {"variables": [{"name": "x", "min": 0, "max": top, "init": 0},
                                     {"name": "t", "min": 0, "max": 1, "init": 0}], "commands": commands},
            "goal": ["==", "x", top]}


def _lasso(data, initial, stem, cycle, loop, kind="lasso"):
    sysm, _ = strategic._live(data)
    by = {c[0]: c for c in sysm["commands"]}
    seq, s = [tuple(initial)], tuple(initial)
    for name in stem + cycle:
        s = strategic._live_enabled(sysm, by[name], s)
        seq.append(s)
    return {"verdict": "VIOLATED", "counterexample": kind, "initial": initial, "stem": stem, "cycle": cycle,
            "loop_state": loop, "trace_digest": strategic._trace_digest(seq)}


def test_liveness_finds_the_reset_lasso_and_bmc_misses_it():
    data = _counter()
    out = strategic.live_solve(data, BUDGET)
    o = out["output"]
    assert o["verdict"] == "VIOLATED" and o["counterexample"] == "lasso"
    assert set(o["cycle"]) >= {"inc", "reset", "tick"} and len(o["stem"]) + len(o["cycle"]) > strategic.LV_BMC_DEPTH
    assert all(strategic.live_verify(data, o, out["certificate"]).values())
    assert strategic.live_bmc(data)["verdict"] == "HOLDS"               # no lasso within depth 10: unsound
    assert strategic.live_networkx(data)["verdict"] == "VIOLATED"
    short = _counter(top=6, back=2)                                    # a short lasso is within the bound
    assert strategic.live_bmc(short)["verdict"] == "VIOLATED"
    assert all(strategic.live_verify(short, strategic.live_bmc(short), {}).values())


def test_liveness_holds_when_weak_fairness_forces_progress_and_fails_without_it():
    data = _counter("stutter")
    out = strategic.live_solve(data, BUDGET)
    assert out["output"] == {"verdict": "HOLDS", "region_states": 24}
    assert all(strategic.live_verify(data, out["output"], out["certificate"]).values())
    unfair = dict(data, fair=["tick"])                                # inc is no longer weakly fair
    o = strategic.live_solve(unfair, BUDGET)["output"]
    assert o["verdict"] == "VIOLATED" and o["cycle"] == ["tick", "tick"] and o["stem"] == []
    assert all(strategic.live_verify(unfair, o, {}).values())


def test_liveness_verify_refutes_an_unfair_lasso_and_a_goal_visiting_lasso():
    data = _counter("stutter")
    unfair = _lasso(data, [0, 0], [], ["tick", "tick"], [0, 0])         # inc stays enabled and is never taken
    checks = strategic.live_verify(data, unfair, {})
    assert checks["trace_replays"] and checks["trace_digest_matches_the_replay"]
    assert checks["cycle_is_weakly_fair"] is False
    reset = _counter(top=4, back=3)
    wrapped = dict(reset, system=dict(reset["system"], commands=reset["system"]["commands"] + [
        {"name": "wrap", "guard": ["==", "x", 4], "update": {"x": 0}}]))           # leaves the goal again
    through_goal = _lasso(wrapped, [0, 0], [], ["inc", "inc", "inc", "inc", "wrap", "tick", "tick"], [0, 0])
    checks = strategic.live_verify(wrapped, through_goal, {})
    assert checks["trace_replays"] and checks["cycle_returns_to_the_loop_state"]
    assert checks["every_state_avoids_the_goal"] is False


def test_liveness_verify_refutes_holds_copied_from_the_true_region():
    data, truth, out = solved("verify_liveness", 1)
    assert out["output"]["verdict"] == "VIOLATED" and not truth["holds"]
    sysm, fair = strategic._live(data)
    region = strategic._live_region(sysm, 10 ** 5)
    digest = strategic._mc_digest(map(tuple, region["states"].tolist()))
    forged = {"verdict": "HOLDS", "region_states": region["count"]}
    checks = strategic.live_verify(data, forged, {"region_digest": digest})
    assert checks["region_count_matches"] and checks["region_digest_matches"]
    assert checks["no_weakly_fair_goal_avoiding_component"] is False
    assert strategic.live_score(data, truth, forged) == {"quality": -1.0, "category": "wrong"}


def test_liveness_reports_a_reachable_deadlock():
    data = {"system": {"variables": [{"name": "x", "min": 0, "max": 2, "init": 0}],
                       "commands": [{"name": "inc", "guard": ["<", "x", 2], "update": {"x": ["+", "x", 1]}}]},
            "goal": ["==", "x", 5]}
    out = strategic.live_solve(data, BUDGET)
    o = out["output"]
    assert o["counterexample"] == "deadlock" and o["stem"] == ["inc", "inc"] and o["cycle"] == []
    assert all(strategic.live_verify(data, o, out["certificate"]).values())
    for arm in (strategic.live_bmc, strategic.live_networkx):
        assert arm(data)["counterexample"] == "deadlock"
    forged = dict(o, stem=["inc"], loop_state=[1])
    forged["trace_digest"] = strategic._trace_digest([(0,), (1,)])
    assert strategic.live_verify(data, forged, {})["deadlock_has_no_enabled_command"] is False


def test_weak_fairness_cannot_force_an_intermittently_enabled_entry():
    from greg.cognition.genomes.strategic import _lv_livelock
    import random
    for seed in range(200):
        system, goal, fair, label = _lv_livelock(random.Random(seed))
        if label.endswith("priority_weak"):
            break
    data = {"system": system, "goal": goal, "fair": fair}
    o = strategic.live_solve(data, BUDGET)["output"]
    assert o["verdict"] == "VIOLATED" and all(strategic.live_verify(data, o, {}).values())
    assert strategic.live_solve(dict(data, fairness="strong"), BUDGET)["status"] == "ABSTAIN"


def test_tarjan_matches_networkx_on_random_graphs():
    import random
    import networkx as nx
    r = random.Random(3001)
    for _ in range(30):
        size = r.randint(1, 40)
        adj = [sorted({r.randrange(size) for _ in range(r.randint(0, 3))}) for _ in range(size)]
        G = nx.DiGraph()
        G.add_nodes_from(range(size))
        G.add_edges_from((v, w) for v in range(size) for w in adj[v])
        ours = {frozenset(c) for c in strategic._tarjan(adj)}
        assert ours == {frozenset(c) for c in nx.strongly_connected_components(G)}


def test_liveness_fixpoint_agrees_with_the_solver_on_review_seeds():
    for seed in range(3000, 3020):
        data, truth = dev("verify_liveness", seed)
        out = strategic.live_solve(data, BUDGET)
        assert (out["output"]["verdict"] == "HOLDS") == truth["holds"], seed


def test_fixpoint_and_scipy_scc_test_agree_and_neither_shares_the_solvers_tarjan():
    cases = [dev("verify_liveness", s)[0] for s in (*range(10), *range(3020, 3040))]
    cases += [_counter(), _counter("stutter"), dict(_counter("stutter"), fair=["tick"]), dict(_counter(), fair=[])]
    for data in cases:
        sysm, fair = strategic._live(data)
        region = strategic._live_region(sysm, 10 ** 5)
        assert strategic._live_fixpoint(region, fair) == strategic._live_fair_scc(region, fair)
        holds = not strategic._live_deadlock(region) and not strategic._live_fair_scc(region, fair)
        assert holds == (strategic.live_solve(data, BUDGET)["output"]["verdict"] == "HOLDS")
    import inspect
    for fn in (strategic._live_region, strategic._live_fair_scc, strategic._live_fixpoint, strategic.live_verify):
        source = inspect.getsource(fn)
        assert "_tarjan" not in source and "_mc_step" not in source and "_mc_compiled" not in source


def test_holds_verification_near_the_state_cap_is_linear_not_quadratic():
    # builder review: an Emerson-Lei fixpoint as the verifier took 37 s here (one progress layer per iteration)
    data = _counter("stutter", top=1990)
    data["system"]["variables"][1]["max"] = 9
    data["system"]["commands"][1]["update"] = {"t": ["mod", ["+", "t", 1], 10]}
    out = strategic.live_solve(data, BUDGET)
    assert out["output"] == {"verdict": "HOLDS", "region_states": 19900}
    started = time.perf_counter()
    assert all(strategic.live_verify(data, out["output"], out["certificate"]).values())
    assert time.perf_counter() - started < 15.0


# ------------------------------------------------------------------ invalid input
_NASH = {"row_payoffs": [[1, 0], [0, 1]], "column_payoffs": [[1, 0], [0, 1]]}
_MECH = {"agents": [{"values": [[0, 1], [0, 2]]}], "outcomes": ["no", "yes"], "allocation": [1, 1],
         "payments": [[0], [0]]}
_LIVE = _counter()

INVALID = {
    "bimatrix_nash": [dict(_NASH, row_payoffs=[[1, 0], [0]]),                          # ragged
                      dict(_NASH, column_payoffs=[[1, 0]]),                            # shape mismatch
                      dict(_NASH, row_payoffs=[[1, float("nan")], [0, 1]]),
                      dict(_NASH, row_payoffs=[[True, 0], [0, 1]]),
                      dict(_NASH, row_payoffs=[[1e9, 0], [0, 1]]),
                      dict(_NASH, row_payoffs=[]), {"row_payoffs": [[1]]}, "a game"],
    "mechanism_check": [dict(_MECH, allocation=[1]),                                   # wrong length
                        dict(_MECH, allocation=[1, 2]),                                # outcome out of range
                        dict(_MECH, outcomes=["no", "no"]),                            # duplicate labels
                        dict(_MECH, payments=[[0], [0, 1]]),
                        dict(_MECH, agents=[{"values": [[0, 1, 2], [0, 2]]}]),          # ragged values
                        dict(_MECH, agents=[]), dict(_MECH, outside_option=[0, 0]),
                        dict(_MECH, allocation=[True, 1])],
    "verify_liveness": [dict(_LIVE, goal=["+", "x", 1]),                               # not boolean
                        {k: v for k, v in _LIVE.items() if k != "goal"},
                        dict(_LIVE, goal=["==", "y", 1]),                              # unknown variable
                        dict(_LIVE, fair=["inc", "nope"]), dict(_LIVE, fair=["inc", "inc"]),
                        dict(_LIVE, fair="inc"), dict(_LIVE, system="x := x + 1"),
                        dict(_LIVE, system={"variables": [], "commands": []})],
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


@pytest.mark.parametrize("family", FAMILIES)
def test_verify_refutes_malformed_outputs_without_raising(family):
    data, _, out = solved(family, ANSWER_SEEDS[family][0])
    for bad in (None, [], "ANSWER", {}, {"verdict": "HOLDS"}, {"verdict": "VIOLATED", "initial": "x"},
                {"verdict": "VIOLATION", "dsic": {}, "ir": {}}, {"row_strategy": [1.0]}):
        checks = item(family).verify(data, bad, out["certificate"])
        assert checks and not all(checks.values()), (family, bad)


# ------------------------------------------------------------------ abstention
def _big_mechanism():
    from itertools import product
    k = [8, 8, 8, 8]
    profiles = list(product(*[range(x) for x in k]))
    return {"agents": [{"values": [[0, t] for t in range(x)]} for x in k], "outcomes": ["no", "yes"],
            "allocation": [1] * len(profiles), "payments": [[0, 0, 0, 0] for _ in profiles]}


ABSTAIN = {
    "bimatrix_nash": [{"row_payoffs": [[i * j % 7 for j in range(8)] for i in range(8)],
                       "column_payoffs": [[(i + j) % 5 for j in range(8)] for i in range(8)]}],
    "mechanism_check": [dict(_MECH, randomized=True), _big_mechanism()],
    "verify_liveness": [dict(_LIVE, property="safety"), dict(_LIVE, fairness="strong"),
                        {"system": {"variables": [{"name": "x", "min": 0, "max": 200, "init": 0},
                                                  {"name": "y", "min": 0, "max": 200, "init": 0}],
                                    "commands": [{"name": "ix", "guard": True, "update": {"x": ["+", "x", 1]}},
                                                 {"name": "dx", "guard": True, "update": {"x": ["-", "x", 1]}},
                                                 {"name": "iy", "guard": True, "update": {"y": ["+", "y", 1]}},
                                                 {"name": "dy", "guard": True, "update": {"y": ["-", "y", 1]}}]},
                         "goal": ["==", "x", -1]}],
}


@pytest.mark.parametrize("family", FAMILIES)
def test_abstains_outside_native_competence(family):
    for data in ABSTAIN[family]:
        out = item(family).solve(copy.deepcopy(data), BUDGET)
        assert out["status"] == "ABSTAIN" and out["output"] is None and out["missing"], (family, out)
        _json_clean(out["certificate"])


def test_out_of_scope_liveness_requests_are_refused_by_every_arm():
    for data in ABSTAIN["verify_liveness"][:2]:
        assert strategic.live_bmc(data) is None and strategic.live_networkx(data) is None


# ------------------------------------------------------------------ scoring
def _wrong_output(family, data, out):
    if family == "bimatrix_nash":                             # a pure profile that is not an equilibrium
        a, b = data["row_payoffs"], data["column_payoffs"]
        pure = set(strategic._pure_equilibria(a, b))
        i, j = next((i, j) for i in range(len(a)) for j in range(len(a[0])) if (i, j) not in pure)
        return dict(_pure_profile(data, i, j), selection="nash", correlated=None)
    if family == "mechanism_check":
        return _corrupt(family, data, out)[0]
    return {"verdict": "HOLDS" if out["output"]["verdict"] == "VIOLATED" else "VIOLATED", "counterexample": "lasso",
            "initial": [], "stem": [], "cycle": [], "loop_state": [], "trace_digest": ""}


@pytest.mark.parametrize("family", FAMILIES)
def test_score_categories(family):
    x = item(family)
    data, truth, out = solved(family, ANSWER_SEEDS[family][1])
    correct = x.score(data, truth, out["output"])
    assert correct["category"] == "correct"
    abstain = x.score(data, truth, None)
    assert abstain["category"] == "abstain"
    wrong = x.score(data, truth, _wrong_output(family, data, out))
    assert wrong["category"] == "wrong"
    assert wrong["quality"] < abstain["quality"] < correct["quality"]


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


def test_bimatrix_candidate_selects_the_best_equilibrium_where_the_competitor_need_not():
    data, truth, out = solved("bimatrix_nash", 4)
    assert item("bimatrix_nash").score(data, truth, out["output"])["quality"] == 1.0
    assert out["output"]["welfare"] == pytest.approx(truth["max_welfare"])
    assert item("bimatrix_nash").score(data, truth, strategic.nash_competitor(data))["quality"] < 1.0


# ------------------------------------------------------------------ determinism and runtime
@pytest.mark.parametrize("family", FAMILIES)
def test_instances_and_solves_are_deterministic(family):
    seed = ANSWER_SEEDS[family][-1]
    first, _ = item(family).instance(seed)
    again, _ = item(family).instance(seed)
    assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)
    data, _, out = solved(family, seed)
    assert item(family).solve(copy.deepcopy(data), BUDGET) == out


def test_z3_backed_bmc_is_reproducible_within_one_process():
    data = _counter(top=6, back=2)                                    # each call uses a private Z3 context
    outs = {json.dumps(strategic.live_bmc(data), sort_keys=True) for _ in range(2)}
    assert len(outs) == 1 and json.loads(outs.pop())["verdict"] == "VIOLATED"


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
