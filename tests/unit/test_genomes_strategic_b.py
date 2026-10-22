"""Layer 3 strategic pack B (repeated-game sustainability, Nash bargaining, Stackelberg commitment): contract,
withheld registration, canonical path, Competency Compiler reachability, independent verification, refutation of
corrupted answers, references against independent methods, invalid input and determinism.

Development seeds 0-9 only; held-out admission seeds are never generated here.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import itertools
import json
import random

import pytest

from greg.cognition import catalog
from greg.cognition.genomes import library, strategic_b
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

ITEMS = {x.genome.family: x for x in strategic_b.INTELLIGENCES}
FAMILIES = tuple(sorted(ITEMS))
SPEC = {  # family: (layer, operation, epistemic class, evidence type, dependency)
    "game_repeated_sustain": (3, "repeated_game_sustainability", "strategic", "exact_calculation", "z3-solver"),
    "game_nash_bargaining": (3, "nash_bargaining_solution", "strategic", "optimality_certificate", "scipy"),
    "game_stackelberg_commit": (3, "stackelberg_commitment", "strategic", "optimality_certificate", None),
}
BUDGET = {"latency_s": 8.0, "compute": 100000}
_CACHE: dict = {}


def dev(family, seed=1):
    assert 0 <= seed < 10                                   # never a held-out seed
    key = (family, seed)
    if key not in _CACHE:
        _CACHE[key] = ITEMS[family].instance(seed)
    data, truth = _CACHE[key]
    return copy.deepcopy(data), truth


def solved(family, seed=1):
    key = ("solved", family, seed)
    if key not in _CACHE:
        data, _ = dev(family, seed)
        _CACHE[key] = ITEMS[family].solve(data, BUDGET)
    data, truth = dev(family, seed)
    return data, truth, copy.deepcopy(_CACHE[key])


def _ok(family, data, output, cert):
    return all(ITEMS[family].verify(data, output, cert).values())


# ------------------------------------------------------------------ genome contract and registration
def test_genomes_validate_with_declared_identity():
    assert set(FAMILIES) == set(SPEC)
    for family, x in ITEMS.items():
        g = x.genome
        assert isinstance(g, IntelligenceGenome) and g.validate() is g
        assert (g.layer, g.operation, g.epistemic_class, g.evidence_type, g.dependency) == SPEC[family]
        assert g.buildability == "BUILDABLE_NOW" and g.standalone_decision and g.version == "1.0.0"
        assert g.authority_ceiling == g.consequence_limit == "read_only"
        assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
        assert g.baseline and g.competitor and x.subregion is not None and x.competitor_deployable
        assert "seeds 0-9 dev" in g.benchmark_suite


def test_registered_in_the_one_catalog_and_withheld():
    families = library.executables()
    for family in FAMILIES:
        assert families[family] is ITEMS[family]
        g = ITEMS[family].genome
        assert catalog.FAMILIES[family] == (g.layer, (g.operation,), (g.epistemic_class,), "genome_certificate",
                                            g.dependency)
        assert catalog.initial_state(f"cognition.{family}") == "VERIFIED"      # registered, never auto-attached


def test_module_imports_no_heavy_package_at_top_level():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(strategic_b))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top for a in n.names} | {
        n.module.split(".")[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"numpy", "scipy", "networkx", "ortools", "z3", "sympy"}


# ------------------------------------------------------------------ solve / verify on development seeds
@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("seed", range(10))
def test_solve_answers_and_its_answer_verifies(family, seed):
    data, truth, out = solved(family, seed)
    assert out["status"] == "ANSWER", out["missing"]
    assert len(json.dumps(out, allow_nan=False)) < 256 * 1024
    checks = ITEMS[family].verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    assert ITEMS[family].score(data, truth, out["output"]) == {"quality": 1.0, "category": "correct"}


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_path_withholds_until_attached_and_creates_no_authority(family):
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    data, truth = dev(family, 3)
    request = {"problem_id": f"strategic-b-{family}", "operation": SPEC[family][1], "data": data,
               "geometry": {"latency_limit": 30}}
    assert reason(request, registry=registry)["abstention_state"] == "CAPABILITY_DEFICIT"
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["abstention_state"] == "NONE" and r["proof_type"] == "genome_certificate"
    assert r["proof_artifact"]["evidence_type"] == SPEC[family][3]
    assert r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" and r["authority_created"] is False
    assert ITEMS[family].score(data, truth, r["output"])["category"] == "correct"


@pytest.mark.parametrize("family", FAMILIES)
def test_the_competency_compiler_reaches_the_family_by_its_inputs(family, tmp_path, monkeypatch):
    """Evaluation only: an in-memory attach (no body, journal or founder pin) and an empty evidence index."""
    from greg.cognition import compiler
    from greg.cognition.cortex import reason, registry_view
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")
    data, truth = dev(family, 1)
    request = {"problem_id": f"strategic-b-compile-{family}",
               "compile": {"geometry": {"geometry": "strategic"}, "data": data}}
    registry = registry_view()
    withheld = reason(request, registry=registry)
    assert withheld["state"] == "CAPABILITY_DEFICIT"
    assert withheld["withheld_best_fit"]["method"] == f"cognition.{family}"
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == f"cognition.{family}"
    assert r["authority_created"] is False
    assert ITEMS[family].score(data, truth, r["result"])["category"] == "correct"


# ------------------------------------------------------------------ repeated games
def _rep_seed(pred):
    for seed in range(10):
        data, truth = dev("game_repeated_sustain", seed)
        if pred(truth):
            return seed
    pytest.skip("no development seed of that shape")


def test_repeated_verifier_refutes_corrupted_answers():
    seed = _rep_seed(lambda t: t["delta_star"] not in (None, "0"))
    data, _, out = solved("game_repeated_sustain", seed)
    o, c = out["output"], out["certificate"]
    star = Fraction(o["delta_star_exact"])
    nudged = star + Fraction(1, 1000)
    corrupted = [
        {**o, "delta_star_exact": f"{nudged.numerator}/{nudged.denominator}", "delta_star": float(nudged)},
        {**o, "delta_star": o["delta_star"] + 1e-6},
        {**o, "sustainable": not o["sustainable"]},
        {**o, "target_payoff": [o["target_payoff"][0] + "1", o["target_payoff"][1]]},
        {**o, "deviation_payoff": [o["deviation_payoff"][1], o["deviation_payoff"][0] + "0"]},
        {**o, "delta_star": None, "delta_star_exact": None},
        {**o, "enforceable_payoff": None if o["sustainable"] else o["target_payoff"]},
        {**o, "punishment": None},
        {**o, "delta_star_exact": "1/0"},
    ]
    pun = o["punishment"]
    rows = len(pun["row_strategy"])
    pure = ["1"] + ["0"] * (rows - 1)
    if pun["row_strategy"] != pure:
        corrupted.append({**o, "punishment": {**pun, "row_strategy": pure}})
    for bad in corrupted:
        assert not _ok("game_repeated_sustain", data, bad, c), bad
    assert _ok("game_repeated_sustain", data, o, c)


def test_repeated_prisoners_dilemma_matches_the_textbook_threshold():
    """delta* = (T - R) / (T - P) for cooperation in a prisoner's dilemma under grim trigger."""
    r = random.Random("test:pd")
    for _ in range(20):
        s, p = r.randint(-5, 2), r.randint(3, 6)
        rr = p + r.randint(2, 8)
        t = rr + r.randint(1, 10)
        a = [[rr, s], [t, p]]
        data = {"row_payoffs": a, "column_payoffs": [list(x) for x in zip(*a)], "target_profile": [0, 0],
                "discount": 0.5}
        out = strategic_b.rep_solve(data, BUDGET)["output"]
        assert Fraction(out["delta_star_exact"]) == Fraction(t - rr, t - p)
        assert out["sustainable"] is (Fraction(0.5) >= Fraction(t - rr, t - p))
        assert out["punishment"]["payoff"] == [str(p), str(p)]


def test_repeated_target_that_is_a_stage_equilibrium_needs_no_patience_and_unsustainable_targets_say_so():
    pd = [[3, 0], [5, 1]]
    base = {"row_payoffs": pd, "column_payoffs": [list(x) for x in zip(*pd)], "discount": 0.3}
    out = strategic_b.rep_solve({**base, "target_profile": [1, 1]}, BUDGET)["output"]
    assert out["delta_star_exact"] == "0" and out["sustainable"] is True
    # a target below the only stage equilibrium's payoff for the column player cannot be sustained
    out = strategic_b.rep_solve({**base, "target_profile": [1, 0]}, BUDGET)["output"]
    assert out["delta_star"] is None and out["sustainable"] is False and out["punishment"] is None
    assert _ok("game_repeated_sustain", {**base, "target_profile": [1, 0]}, out, {})


def test_repeated_degenerate_stage_game_abstains():
    zeros = [[0, 0], [0, 0]]
    data = {"row_payoffs": zeros, "column_payoffs": zeros, "target_profile": [0, 0], "discount": 0.9}
    assert strategic_b.rep_solve(data, BUDGET)["status"] == "ABSTAIN"


def test_repeated_reference_agrees_with_pure_equilibrium_brute_force_where_only_pure_equilibria_exist():
    for seed in range(10):
        data, truth = dev("game_repeated_sustain", seed)
        a, b, (ti, tj) = data["row_payoffs"], data["column_payoffs"], data["target_profile"]
        ref = strategic_b.rep_reference(a, b, (ti, tj))
        pure = [eq for eq in ref["equilibria"] if all(v in (0, 1) for v in eq["x"] + eq["y"])]
        assert len(pure) == len(strategic_b._rep_pure_nash(a, b))   # Z3 finds every pure stage equilibrium
        if len(pure) == len(ref["equilibria"]) and pure:
            best = None
            for eq in pure:
                i, j = eq["x"].index(1), eq["y"].index(1)
                thr = []
                for p, (v, d, e) in enumerate(((a[ti][tj], max(r[tj] for r in a), a[i][j]),
                                               (b[ti][tj], max(b[ti]), b[i][j]))):
                    thr.append(Fraction(0) if d <= v else (None if v <= e else Fraction(d - v, d - e)))
                if None not in thr and (best is None or max(thr) < best):
                    best = max(thr)
            assert ref["delta_star"] == best


@pytest.mark.parametrize("arm", ["baseline", "competitor"])
def test_repeated_arms_answer_in_the_scored_contract(arm):
    data, truth = dev("game_repeated_sustain", 0)
    out = getattr(ITEMS["game_repeated_sustain"], arm)(data)
    s = ITEMS["game_repeated_sustain"].score(data, truth, out)
    assert s["category"] == ("abstain" if arm == "baseline" else "correct")


# ------------------------------------------------------------------ Nash bargaining
def test_bargaining_verifier_refutes_corrupted_answers():
    data, _, out = solved("game_nash_bargaining", 3)                # three players, solution on a face
    o, c = out["output"], out["certificate"]
    d = data["disagreement"]

    def consistent(point):
        gains = [point[i] - d[i] for i in range(len(d))]
        w = [1 / g for g in gains]
        s = sum(w)
        w = [x / s for x in w]
        prod = 1.0
        for g in gains:
            prod *= g
        return {"point": point, "gains": gains, "nash_product": prod, "supporting_weights": w,
                "support_value": sum(x * y for x, y in zip(w, point))}
    # a feasible point of the same face that is not the optimum: the convex combination with a vertex
    weights = dict((i, w) for i, w in c["convex_weights"])
    vertex = data["vertices"][max(weights, key=weights.get)]
    moved = [0.9 * x + 0.1 * y for x, y in zip(o["point"], vertex)]
    corrupted = [
        consistent(moved),                                                  # feasible, consistent, not optimal
        consistent([0.98 * x + 0.02 * y for x, y in zip(o["point"], d)]),   # dominated interior point
        consistent([x * 1.01 for x in o["point"]]),                         # outside the hull
        {**o, "supporting_weights": [o["supporting_weights"][1], o["supporting_weights"][0]]
         + o["supporting_weights"][2:]},
        {**o, "gains": [g + 1e-3 for g in o["gains"]]},
        {**o, "nash_product": o["nash_product"] * 1.001},
        {**o, "support_value": o["support_value"] + 1e-3},
        {**o, "point": list(d)},                                            # no gain over disagreement
        {**o, "point": o["point"][:-1]},
    ]
    for bad in corrupted:
        assert not _ok("game_nash_bargaining", data, bad, c), bad
    assert _ok("game_nash_bargaining", data, o, c)


@pytest.mark.parametrize("seed", [0, 1, 4, 5, 8, 9])
def test_bargaining_reference_matches_a_dense_scan_of_every_segment_in_two_players(seed):
    data, truth = dev("game_nash_bargaining", seed)
    V, d = data["vertices"], data["disagreement"]
    best = 0.0
    for a, b in itertools.combinations(V, 2):
        for k in range(401):
            s = k / 400
            g = [a[i] + s * (b[i] - a[i]) - d[i] for i in range(2)]
            if min(g) > 0:
                best = max(best, g[0] * g[1])
    assert truth["product"] >= best * (1 - 1e-12)
    assert truth["product"] <= best * 1.01


def test_bargaining_symmetric_problem_splits_equally():
    data = {"vertices": [[0, 0], [10, 0], [0, 10]], "disagreement": [0, 0]}
    out = strategic_b.nb_solve(data, BUDGET)["output"]
    assert out["point"] == pytest.approx([5.0, 5.0], abs=1e-9)
    ref = strategic_b.nb_reference(data["vertices"], data["disagreement"])
    assert ref["point"] == pytest.approx([5.0, 5.0], abs=1e-12)


@pytest.mark.parametrize("arm", ["baseline", "competitor"])
def test_bargaining_arms_are_feasible_points(arm):
    data, truth = dev("game_nash_bargaining", 2)
    out = getattr(ITEMS["game_nash_bargaining"], arm)(data)
    s = ITEMS["game_nash_bargaining"].score(data, truth, out)
    assert s["category"] in ("correct", "wrong") and 0.0 < s["quality"] <= 1.0


# ------------------------------------------------------------------ Stackelberg commitment
def test_stackelberg_verifier_refutes_corrupted_answers():
    data, _, out = solved("game_stackelberg_commit", 0)               # a security game: mixed commitment
    o, c = out["output"], out["certificate"]
    x = [Fraction(s) for s in o["leader_strategy_exact"]]
    shifted = [x[0] + Fraction(1, 100), x[1] - Fraction(1, 100)] + x[2:]
    others = [j for j in range(len(data["leader_payoffs"][0])) if j != o["follower_response"]]
    bad_bounds = copy.deepcopy(c)
    bad_bounds["dual_bounds"][0]["z"] = str(Fraction(o["leader_value_exact"]) + 1)
    neg_mu = copy.deepcopy(c)
    k = 1 if o["follower_response"] == 0 else 0
    neg_mu["dual_bounds"][o["follower_response"]]["mu"][k] = "-1"
    zero_mu = copy.deepcopy(c)
    zero_mu["dual_bounds"][o["follower_response"]]["mu"] = ["0"] * (len(others) + 1)
    corrupted = [
        ({**o, "leader_value_exact": str(Fraction(o["leader_value_exact"]) + Fraction(1, 7))}, c),
        ({**o, "leader_strategy_exact": [str(v) for v in shifted],
          "leader_strategy": [float(v) for v in shifted]}, c),
        ({**o, "follower_response": others[0]}, c),
        ({**o, "leader_strategy_exact": ["1/2"] * len(x)}, c),
        ({**o, "leader_strategy": [v + 1e-6 for v in o["leader_strategy"]]}, c),
        ({**o, "leader_value": o["leader_value"] + 1e-6}, c),
        (o, bad_bounds),
        (o, neg_mu),
        (o, zero_mu),
        (o, {}),
    ]
    for bad, cert in corrupted:
        assert not _ok("game_stackelberg_commit", data, bad, cert), (bad, cert)
    assert _ok("game_stackelberg_commit", data, o, c)


def test_stackelberg_suboptimal_commitments_cannot_borrow_the_certificate():
    """A pure or Nash commitment worth less than the optimum fails the dual-bound check with the true duals."""
    data, truth, out = solved("game_stackelberg_commit", 0)
    pure = ITEMS["game_stackelberg_commit"].baseline(data)
    assert Fraction(pure["leader_value_exact"]) < Fraction(out["output"]["leader_value_exact"])
    assert not _ok("game_stackelberg_commit", data, pure, out["certificate"])


def test_exact_simplex_agrees_with_highs_on_random_lps():
    import numpy as np
    from scipy.optimize import linprog
    r = random.Random("test:simplex")
    for _ in range(40):
        nv, mu = r.randint(2, 6), r.randint(1, 6)
        c = [r.randint(-5, 9) for _ in range(nv)]
        A = [[r.randint(-4, 6) for _ in range(nv)] for _ in range(mu)]
        b = [r.randint(-3, 12) for _ in range(mu)]
        Aeq, beq = ([[1] * nv], [r.randint(1, 5)]) if r.random() < 0.5 else ([], [])
        mine = strategic_b._simplex(c, A, b, Aeq, beq, float("inf"))
        res = linprog(-np.array(c, float), A_ub=np.array(A, float), b_ub=b, A_eq=np.array(Aeq, float) if Aeq else None,
                      b_eq=beq or None, bounds=(0, None), method="highs")
        status = {0: "optimal", 2: "infeasible", 3: "unbounded"}[res.status]
        assert mine[0] == status
        if status == "optimal":
            assert float(mine[2]) == pytest.approx(-res.fun, abs=1e-7)
            xs = mine[1]
            assert all(v >= 0 for v in xs)
            assert all(sum(Fraction(a) * v for a, v in zip(row, xs)) <= bb for row, bb in zip(A, b))


@pytest.mark.parametrize("seed", range(10))
def test_stackelberg_value_weakly_dominates_nash_and_pure_commitment(seed):
    data, truth, out = solved("game_stackelberg_commit", seed)
    value = Fraction(out["output"]["leader_value_exact"])
    assert value >= Fraction(ITEMS["game_stackelberg_commit"].baseline(data)["leader_value_exact"])
    nash = ITEMS["game_stackelberg_commit"].competitor(data)
    assert value >= Fraction(nash["leader_value_exact"])
    assert float(value) == pytest.approx(truth["leader_value"], abs=1e-9)


def test_classic_inspection_commitment():
    """Inspect (row 0) or not; comply (column 0) or violate. Commit to inspect with probability 1/3."""
    data = {"leader_payoffs": [[-1, 2], [0, -6]], "follower_payoffs": [[0, -4], [0, 2]]}
    out = strategic_b.sc_solve(data, BUDGET)["output"]
    assert out["leader_strategy_exact"] == ["1/3", "2/3"] and out["follower_response"] == 0
    assert out["leader_value_exact"] == "-1/3"


# ------------------------------------------------------------------ invalid input, malformed output, determinism
@pytest.mark.parametrize("family,bad", [
    ("game_repeated_sustain", {"row_payoffs": [[1, 2]], "column_payoffs": [[1, 2]], "target_profile": [0, 2],
                               "discount": 0.5}),
    ("game_repeated_sustain", {"row_payoffs": [[1, 2]], "column_payoffs": [[1, 2]], "target_profile": [0, 0],
                               "discount": 1.0}),
    ("game_repeated_sustain", {"row_payoffs": [[1, 2]], "column_payoffs": [[1]], "target_profile": [0, 0],
                               "discount": 0.5}),
    ("game_repeated_sustain", {"row_payoffs": [[1] * 7] * 7, "column_payoffs": [[1] * 7] * 7,
                               "target_profile": [0, 0], "discount": 0.5}),
    ("game_nash_bargaining", {"vertices": [[0, 0], [1, 1]], "disagreement": [2, 2]}),
    ("game_nash_bargaining", {"vertices": [[0, 0, 0, 0]], "disagreement": [0, 0, 0, 0]}),
    ("game_nash_bargaining", {"vertices": [[0, float("nan")], [1, 1]], "disagreement": [0, 0]}),
    ("game_stackelberg_commit", {"leader_payoffs": [[1, 2]], "follower_payoffs": [[1, 2], [3, 4]]}),
    ("game_stackelberg_commit", {"leader_payoffs": [[1, "x"]], "follower_payoffs": [[1, 2]]}),
])
def test_invalid_input_raises_a_genome_error(family, bad):
    with pytest.raises(GenomeError):
        ITEMS[family].solve(bad, BUDGET)


@pytest.mark.parametrize("family", FAMILIES)
def test_malformed_outputs_are_refuted_not_raised(family):
    data, _ = dev(family, 1)
    for junk in (None, 3, [], {}, {"x": None}, "answer"):
        assert not all(ITEMS[family].verify(data, junk, {}).values())


def test_instances_and_answers_are_deterministic_by_seed():
    for family in FAMILIES:
        a, b = ITEMS[family].instance(4)[0], ITEMS[family].instance(4)[0]
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
        assert ITEMS[family].solve(a, BUDGET)["output"] == ITEMS[family].solve(b, BUDGET)["output"]
