"""Layer 5 active inference (expected-free-energy sequential fault diagnosis): contract, withheld registration,
canonical path, Competency Compiler reachability, independent verification, refutation of corrupted policies and
forged certificates, the DP truth against brute force, invalid input, abstention, scoring and determinism.

Development seeds 0-9 only; held-out admission seeds are never generated here.
"""
from __future__ import annotations

import copy
import itertools
import json
import math

import pytest

from greg.cognition import catalog
from greg.cognition.genomes import active_inference as ai
from greg.cognition.genomes import library
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

ITEM = ai.INTELLIGENCES[0]
FAMILY = "meta_active_inference"
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


def _tiny():
    """3 hypotheses, 2 binary tests: small enough for a brute-force policy enumeration."""
    return {"fault_prior": [0.5, 0.3, 0.2],
            "fault_tests": [{"cost": 2.0, "likelihood": [[0.9, 0.1], [0.1, 0.9], [0.1, 0.9]]},
                            {"cost": 3.0, "likelihood": [[0.8, 0.2], [0.8, 0.2], [0.05, 0.95]]}],
            "misdiagnosis_loss": 100.0, "escalation_cost": 45.0}


# ------------------------------------------------------------------ genome contract and registration
def test_genome_validates_with_declared_identity():
    g = ITEM.genome
    assert isinstance(g, IntelligenceGenome) and g.validate() is g
    assert (g.family, g.layer, g.operation, g.epistemic_class, g.evidence_type, g.dependency) == (
        FAMILY, 5, "active_infer_diagnose", "causal", "decision_analysis", None)
    assert g.buildability == "BUILDABLE_NOW" and g.standalone_decision and g.version == "1.0.0"
    assert g.authority_ceiling == g.consequence_limit == "read_only"
    assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
    assert g.known_failure_modes and g.counterindications and g.abstention_conditions
    assert g.baseline and g.competitor and ITEM.subregion is not None and ITEM.competitor_deployable
    assert "seeds 0-9 dev" in g.benchmark_suite
    assert any("double-counts" in m for m in g.known_failure_modes)


def test_registered_in_the_one_catalog_and_withheld():
    assert library.executables()[FAMILY] is ITEM
    g = ITEM.genome
    assert catalog.FAMILIES[FAMILY] == (5, ("active_infer_diagnose",), ("causal",), "genome_certificate", None)
    assert catalog.initial_state(f"cognition.{FAMILY}") == "VERIFIED"       # registered, never auto-attached
    assert g.operation not in {x.genome.operation for f, x in library.executables().items() if f != FAMILY}


def test_module_imports_no_heavy_package_at_top_level():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(ai))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top for a in n.names} | {
        n.module.split(".")[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"numpy", "scipy", "networkx", "ortools", "z3"}


def test_instances_are_deterministic_synthetic_and_cover_every_regime():
    seen = set()
    for seed in range(10):
        a, ta = ITEM.instance(seed)
        b, tb = ITEM.instance(seed)
        assert a == b and ta == tb
        seen.add(ta["regime"])
        assert ITEM.subregion(a) in ("binary_tests", "ternary_tests", "mixed_tests")
        assert len(json.dumps(a, allow_nan=False)) < 16 * 1024          # far below the 1 MiB request limit
    assert seen == set(ai.REGIMES)


# ------------------------------------------------------------------ the DP truth is the optimum
def _brute_force(data):
    """Minimum expected loss over every deterministic policy, by recursion over policies (not values)."""
    prior, tests, big_l, big_e = ai._model(data)

    def policies(avail):
        yield ("stop",)
        for j in avail:
            rest = tuple(x for x in avail if x != j)
            k = len(tests[j][1][0])
            for subs in itertools.product(list(policies(rest)), repeat=k):
                yield (j, subs)

    def loss(policy, joint):
        mass = sum(joint)
        if policy[0] == "stop":
            return min(big_l * (mass - max(joint)), big_e * mass)
        j, subs = policy
        cost, lik = tests[j]
        return cost * mass + sum(loss(s, [joint[h] * lik[h][o] for h in range(len(joint))])
                                 for o, s in enumerate(subs))
    return min(loss(p, prior) for p in policies(tuple(range(len(tests)))))


def test_dp_optimum_equals_a_brute_force_search_over_policies():
    data = _tiny()
    assert math.isclose(ai.optimal_loss(data), _brute_force(data), rel_tol=1e-12, abs_tol=1e-12)
    # and no arm beats it on dev seeds
    for seed in QUICK:
        d, truth = dev(seed)
        for arm in (ai.baseline, ai.bayes_lookahead2, ai.voi_myopic, ai.ig_per_cost):
            assert arm(d)["expected_loss"] >= truth["optimal_loss"] - 1e-9


# ------------------------------------------------------------------ solve / verify on development seeds
@pytest.mark.parametrize("seed", QUICK)
def test_solve_answers_and_its_answer_verifies(seed):
    data, truth, out = solved(seed)
    assert out["status"] == "ANSWER", out["missing"]
    assert len(json.dumps(out, allow_nan=False)) < 64 * 1024
    checks = ITEM.verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    sc = ITEM.score(data, truth, out["output"])
    assert sc["category"] == "correct" and sc["quality"] <= 1e-9          # never better than the optimum
    assert ITEM.solve(copy.deepcopy(data), BUDGET) == out                # deterministic
    assert out["certificate"]["horizon"] == 2
    assert math.isclose(out["certificate"]["lambda"], data["misdiagnosis_loss"] / math.log(100))


@pytest.mark.parametrize("seed", QUICK[:3])
def test_arms_answer_in_the_scored_contract(seed):
    data, truth = dev(seed)
    for arm in (ITEM.baseline, ITEM.competitor, ai.voi_myopic, ai.ig_per_cost):
        out = arm(data)
        assert ITEM.score(data, truth, out)["category"] == "correct"
        assert not ai._enumerate(data, out["policy"])[1]
    assert ITEM.score(data, truth, None)["category"] == "abstain"


def test_competitor_is_the_epistemic_free_ablation_of_the_candidate():
    """With the epistemic weight at zero the candidate's planner is the competitor's (one parameter apart)."""
    data, _ = dev(0)
    prior, tests, big_l, big_e = ai._model(data)
    clock = ai._Clock(30)
    pol = ai._expand(prior, tests, big_l, big_e,
                     lambda b, av: ai._plan_action(b, av, tests, big_l, big_e, ai._lam(big_l), 0.0, clock)[0], clock)
    comp = ai.bayes_lookahead2(data)
    assert pol[0] == comp["policy"] and math.isclose(pol[1], comp["expected_loss"])


def test_root_efe_table_matches_a_hand_computation_on_the_tiny_problem():
    data = _tiny()
    out = ITEM.solve(data, BUDGET)
    lam = 100.0 / math.log(100)
    assert math.isclose(out["certificate"]["root_efe"]["stop"], min(100 * 0.5, 45.0) / lam)
    table, vlam = ai._root_efe(data)
    assert math.isclose(vlam, lam)
    for k, v in table.items():
        assert math.isclose(out["certificate"]["root_efe"][k], v, rel_tol=1e-9)


# ------------------------------------------------------------------ independent verification refutes corruptions
def _first_leaf(tree, kind):
    stack = [tree]
    while stack:
        node = stack.pop()
        if node is None:
            continue
        if kind in node:
            return node
        stack.extend(node.get("branches", []))
    return None


def _first_test(tree):
    return tree if "test" in tree else None


def _corruptions(data, out):
    o, cert = out["output"], out["certificate"]
    muts = {}
    n = len(data["fault_prior"])
    muts["expected_loss_understated"] = ({**o, "expected_loss": o["expected_loss"] * 0.9}, cert)
    muts["expected_loss_nan"] = ({**o, "expected_loss": float("nan")}, cert)
    muts["certificate_loss_forged"] = (o, {**cert, "expected_loss": cert["expected_loss"] + 1.0})
    muts["horizon_misdeclared"] = (o, {**cert, "horizon": 3})
    muts["lambda_misdeclared"] = (o, {**cert, "lambda": cert["lambda"] * 2})
    table = dict(cert["root_efe"])
    first = next(iter(sorted(table)))
    table[first] += 0.5
    muts["root_efe_forged"] = (o, {**cert, "root_efe": table})
    other = "stop" if cert["root_action"] != "stop" else next(k for k in cert["root_efe"] if k != "stop")
    muts["root_action_misreported"] = (o, {**cert, "root_action": other})
    muts["stop_at_root"] = ({"policy": {"declare": 0}, "expected_loss": o["expected_loss"]}, cert)
    muts["shape_extra_key"] = ({**o, "note": 1}, cert)
    root = o["policy"]
    if "test" in root:
        t = copy.deepcopy(root)
        t["test"] = len(data["fault_tests"])
        muts["unknown_test"] = ({**o, "policy": t}, cert)
        t = copy.deepcopy(root)
        t["branches"] = t["branches"][:-1]
        muts["branch_list_truncated"] = ({**o, "policy": t}, cert)
        t = copy.deepcopy(root)
        live = [i for i, b in enumerate(t["branches"]) if b is not None]
        t["branches"][live[0]] = None
        muts["positive_branch_dropped"] = ({**o, "policy": t}, cert)
        t = copy.deepcopy(root)
        t["branches"][live[0]] = {"test": root["test"], "branches": copy.deepcopy(root["branches"])}
        muts["test_repeated"] = ({**o, "policy": t}, cert)
        t = copy.deepcopy(root)
        t["branches"][live[0]] = {"declare": n}
        muts["unknown_hypothesis"] = ({**o, "policy": t}, cert)
        t = copy.deepcopy(root)
        t["branches"][live[0]] = {"escalate": "yes"}
        muts["malformed_leaf"] = ({**o, "policy": t}, cert)
    t = copy.deepcopy(root)
    leaf = _first_leaf(t, "declare")
    if leaf is not None:
        leaf["declare"] = (leaf["declare"] + 1) % n                     # a different hypothesis: loss changes
        muts["declaration_changed"] = ({**o, "policy": t}, cert)
    t = copy.deepcopy(root)
    leaf = _first_leaf(t, "declare")
    if leaf is not None:
        leaf.clear()
        leaf["escalate"] = True
        muts["leaf_swapped_to_escalate"] = ({**o, "policy": t}, cert)
    t = copy.deepcopy(root)
    leaf = _first_leaf(t, "escalate")
    if leaf is not None:
        leaf.clear()
        leaf["declare"] = 0
        muts["escalation_swapped_to_declare"] = ({**o, "policy": t}, cert)
    return muts


@pytest.mark.parametrize("seed", QUICK)
def test_verifier_rejects_every_corruption(seed):
    data, _, out = solved(seed)
    for name, (o, cert) in _corruptions(data, out).items():
        if o == out["output"] and cert == out["certificate"]:
            continue
        if name in ("leaf_swapped_to_escalate", "escalation_swapped_to_declare") and math.isclose(
                ai._enumerate(data, o["policy"])[0], out["output"]["expected_loss"], rel_tol=1e-7):
            continue                                                       # loss-neutral swap: not a corruption
        assert not _ok(data, o, cert), name


def test_zero_posterior_declaration_and_impossible_subtree_are_wrong():
    data = {"fault_prior": [0.6, 0.4],
            "fault_tests": [{"cost": 1.0, "likelihood": [[1.0, 0.0], [0.0, 1.0]]}],
            "misdiagnosis_loss": 50.0, "escalation_cost": 40.0}
    truth = {"optimal_loss": ai.optimal_loss(data)}
    assert math.isclose(truth["optimal_loss"], 1.0)
    good = {"policy": {"test": 0, "branches": [{"declare": 0}, {"declare": 1}]}, "expected_loss": 1.0}
    assert ITEM.score(data, truth, good) == {"quality": 0.0, "category": "correct"}
    contradicted = {"policy": {"test": 0, "branches": [{"declare": 1}, {"declare": 1}]}, "expected_loss": 31.0}
    assert ITEM.score(data, truth, contradicted)["category"] == "wrong"     # declares h=1 after excluding it
    impossible = {"fault_prior": [1.0, 0.0], "fault_tests": data["fault_tests"],
                  "misdiagnosis_loss": 50.0, "escalation_cost": 40.0}
    hung = {"policy": {"test": 0, "branches": [{"declare": 0}, {"declare": 0}]}, "expected_loss": 1.0}
    assert ai._enumerate(impossible, hung["policy"])[1]                   # subtree on a zero-probability outcome
    lie = {**good, "expected_loss": 0.5}
    assert ITEM.score(data, truth, lie)["category"] == "wrong"            # claimed loss is false


def test_malformed_outputs_are_refuted_not_raised():
    data, _, out = solved(0)
    for bad in (None, [], {"policy": None}, {"policy": "x", "expected_loss": 1.0},
                {"policy": {"test": 0}, "expected_loss": 1.0}, {"expected_loss": 1.0}):
        checks = ITEM.verify(data, bad, out["certificate"])
        assert not all(checks.values())
    assert not _ok(data, out["output"], None)


# ------------------------------------------------------------------ bounds, abstention, refusal
@pytest.mark.parametrize("bad", [
    {"fault_prior": [1.0], "fault_tests": [], "misdiagnosis_loss": 1.0, "escalation_cost": 1.0},
    {**_tiny(), "fault_prior": [0.5, 0.3, 0.3]},
    {**_tiny(), "fault_prior": [0.5, 0.5, float("nan")]},
    {**_tiny(), "fault_tests": []},
    {**_tiny(), "fault_tests": [_tiny()["fault_tests"][0]] * 8},
    {**_tiny(), "fault_tests": [{"cost": 1.0, "likelihood": [[0.5, 0.5]] * 2}]},
    {**_tiny(), "fault_tests": [{"cost": 1.0, "likelihood": [[0.25] * 4] * 3}]},
    {**_tiny(), "fault_tests": [{"cost": 1.0, "likelihood": [[0.6, 0.6]] * 3}]},
    {**_tiny(), "fault_tests": [{"cost": -1.0, "likelihood": [[0.5, 0.5]] * 3}]},
    {**_tiny(), "fault_tests": [{"cost": 1.0, "likelihood": [[0.5, 0.5]] * 3, "run": "rm"}]},
    {**_tiny(), "misdiagnosis_loss": 0.0},
    {**_tiny(), "escalation_cost": "1"},
    "not a dict",
])
def test_invalid_input_raises_a_genome_error(bad):
    with pytest.raises(GenomeError):
        ITEM.solve(bad, BUDGET)


def test_abstains_when_the_latency_budget_is_exhausted():
    data, _ = dev(5)
    out = ITEM.solve(data, {"latency_s": 0.0})
    # the floor is 0.05 s; a large instance may still answer, but never a partial policy
    assert out["status"] in ("ANSWER", "UNKNOWN")
    if out["status"] == "UNKNOWN":
        assert out["output"] is None and out["missing"]
    import greg.cognition.genomes.active_inference as mod
    orig = mod._Clock.check
    try:
        mod._Clock.check = lambda self: (_ for _ in ()).throw(TimeoutError())
        out = ITEM.solve(data, BUDGET)
    finally:
        mod._Clock.check = orig
    assert out["status"] == "UNKNOWN" and out["output"] is None


def test_escalation_cheaper_than_any_test_exposes_the_epistemic_failure_mode():
    """Declared failure mode: information gain is valued for its own sake, so the candidate buys tests even when
    escalating at once is optimal; the epistemic-free competitor and the DP escalate. The policy is legal and its
    loss is exact (correct, with positive regret)."""
    data = {**_tiny(), "escalation_cost": 1.0}
    assert math.isclose(ai.optimal_loss(data), 1.0)
    comp = ai.bayes_lookahead2(data)
    assert comp["policy"] == {"escalate": True} and math.isclose(comp["expected_loss"], 1.0)
    out = ITEM.solve(data, BUDGET)
    assert _ok(data, out["output"], out["certificate"])
    assert "test" in out["output"]["policy"] and out["output"]["expected_loss"] > 1.0
    sc = ITEM.score(data, {"optimal_loss": 1.0}, out["output"])
    assert sc["category"] == "correct" and sc["quality"] < 0


# ------------------------------------------------------------------ canonical path and Competency Compiler
def test_canonical_path_withholds_until_attached_and_creates_no_authority():
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    data, truth = dev(0)
    request = {"problem_id": "active-inference-dev", "operation": "active_infer_diagnose", "data": data,
               "geometry": {"latency_limit": 30}}
    assert reason(request, registry=registry)["abstention_state"] == "CAPABILITY_DEFICIT"
    registry.set_state(f"cognition.{FAMILY}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["abstention_state"] == "NONE" and r["proof_type"] == "genome_certificate"
    assert r["proof_artifact"]["evidence_type"] == "decision_analysis"
    assert r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" and r["authority_created"] is False
    assert ITEM.score(data, truth, r["output"])["category"] == "correct"


def test_the_competency_compiler_reaches_the_family_by_its_inputs(tmp_path, monkeypatch):
    """Evaluation only: an in-memory attach (no body, journal or founder pin) and an empty evidence index."""
    from greg.cognition import compiler
    from greg.cognition.cortex import reason, registry_view
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")
    data, truth = dev(0)
    request = {"problem_id": "active-inference-compile", "compile": {"geometry": {"geometry": "causal"}, "data": data}}
    registry = registry_view()
    withheld = reason(request, registry=registry)
    assert withheld["state"] == "CAPABILITY_DEFICIT"
    assert withheld["withheld_best_fit"]["method"] == f"cognition.{FAMILY}"
    registry.set_state(f"cognition.{FAMILY}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == f"cognition.{FAMILY}"
    assert r["methods_considered"] == [f"cognition.{FAMILY}"]
    assert r["derived_geometry"]["fits_by_inputs"] == ["causal"] and r["authority_created"] is False
    assert ITEM.score(data, truth, r["result"])["category"] == "correct"
