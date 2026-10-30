"""Layer 3 batch B genomes (resolution proofs, MDL model selection, convex QP with a duality certificate): contract,
withheld registration, canonical path, Competency Compiler reachability, independent verification, refutation of
corrupted answers, invalid input and scoring.

Development seeds 0-9 only; held-out admission seeds are never generated here.
"""
from __future__ import annotations

import copy
import json
import math

import pytest

from greg.cognition import catalog
from greg.cognition.genomes import formal_b, library
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

ITEMS = {x.genome.family: x for x in formal_b.INTELLIGENCES}
FAMILIES = tuple(sorted(ITEMS))
SPEC = {  # family: (layer, operation, epistemic class, evidence type, dependency)
    "prove_resolution": (3, "prove_clausal_entailment", "deductive", "exhaustive_check", None),
    "mdl_model_select": (3, "select_polynomial_degree", "estimate", "exact_calculation", None),
    "convex_qp_dual": (3, "solve_convex_qp", "optimization", "optimality_certificate", None),
}
QUICK = {"prove_resolution": (0, 1, 2, 3, 5, 6, 7, 9), "mdl_model_select": (0, 1, 2, 3, 5, 6, 7),
         "convex_qp_dual": (0, 2, 3, 6, 9)}
BUDGET = {"latency_s": 8.0, "compute": 100000}
_CACHE: dict = {}


def dev(family, seed):
    assert 0 <= seed < 10                                      # never a held-out seed
    key = (family, seed)
    if key not in _CACHE:
        _CACHE[key] = ITEMS[family].instance(seed)
    data, truth = _CACHE[key]
    return copy.deepcopy(data), truth


def solved(family, seed):
    key = ("solved", family, seed)
    if key not in _CACHE:
        data, _ = dev(family, seed)
        _CACHE[key] = ITEMS[family].solve(data, BUDGET)
    data, truth = dev(family, seed)
    return data, truth, copy.deepcopy(_CACHE[key])


def _all(family, data, output, cert):
    return all(ITEMS[family].verify(data, output, cert).values())


def _json_clean(value):
    if isinstance(value, float):
        assert math.isfinite(value)
    elif isinstance(value, dict):
        assert all(isinstance(k, str) for k in value)
        for v in value.values():
            _json_clean(v)
    elif isinstance(value, list):
        for v in value:
            _json_clean(v)
    else:
        assert value is None or isinstance(value, (str, int, bool))


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
        assert g.known_failure_modes and g.counterindications and g.abstention_conditions
        assert g.baseline and g.competitor and x.subregion is not None and x.competitor_deployable
        assert "seeds 0-9 dev" in g.benchmark_suite
    # the prover is explicit that Z3 is the stronger engine and that its scoring is declared
    prover = ITEMS["prove_resolution"]
    assert any("Z3 is the stronger" in m for m in prover.genome.known_failure_modes)
    assert "declared" in prover.notes["scoring"]


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
    tree = ast.parse(inspect.getsource(formal_b))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top for a in n.names} | {
        n.module.split(".")[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"numpy", "scipy", "networkx", "ortools", "z3"}


def test_no_overlap_with_the_reconciliation_qp_geometry():
    lib = library.executables()
    assert set(lib["reconcile_qp"].genome.required_inputs).isdisjoint(ITEMS["convex_qp_dual"].genome.required_inputs)
    data, _ = dev("convex_qp_dual", 0)
    import numpy as np
    q = np.array(data["hessian"])
    assert np.abs(q - np.diag(np.diag(q))).max() > 0.1                      # dense, coupled Hessian
    assert min(data["inequality_rhs"]) != 0 or len(data["inequality_rhs"]) > 1


# ------------------------------------------------------------------ solve / verify on development seeds
@pytest.mark.parametrize("family,seed", [(f, s) for f in FAMILIES for s in QUICK[f]])
def test_solve_answers_compactly_and_its_answer_verifies(family, seed):
    data, truth, out = solved(family, seed)
    assert out["status"] == "ANSWER", out["missing"]
    _json_clean(out["output"])
    _json_clean(out["certificate"])
    json.dumps(out, allow_nan=False)
    json.dumps(data, allow_nan=False)
    checks = ITEMS[family].verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    score = ITEMS[family].score(data, truth, out["output"])
    if family != "mdl_model_select":                       # degree recovery is an estimate, not guaranteed
        assert score["category"] == "correct"


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_path_withholds_until_attached_and_creates_no_authority(family):
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    data, truth = dev(family, QUICK[family][0])
    request = {"problem_id": f"formal-b-{family}", "operation": SPEC[family][1], "data": data,
               "geometry": {"latency_limit": 30}}
    assert reason(request, registry=registry)["abstention_state"] == "CAPABILITY_DEFICIT"
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["abstention_state"] == "NONE" and r["proof_type"] == "genome_certificate"
    assert r["proof_artifact"]["evidence_type"] == SPEC[family][3]
    assert r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" and r["authority_created"] is False
    assert ITEMS[family].score(data, truth, r["output"])["quality"] > 0


@pytest.mark.parametrize("family", FAMILIES)
def test_the_competency_compiler_reaches_the_family_by_its_inputs(family, tmp_path, monkeypatch):
    """Evaluation only: an in-memory attach (no body, journal or founder pin) and an empty evidence index."""
    from greg.cognition import compiler
    from greg.cognition.cortex import reason, registry_view
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")
    data, truth = dev(family, QUICK[family][0])
    cls = SPEC[family][2]
    request = {"problem_id": f"formal-b-compile-{family}", "compile": {"geometry": {"geometry": cls}, "data": data}}
    registry = registry_view()
    withheld = reason(request, registry=registry)
    assert withheld["state"] == "CAPABILITY_DEFICIT"
    assert withheld["withheld_best_fit"]["method"] == f"cognition.{family}"
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == f"cognition.{family}"
    assert r["methods_considered"] == [f"cognition.{family}"]
    assert r["derived_geometry"]["fits_by_inputs"] == [cls] and r["authority_created"] is False


# ------------------------------------------------------------------ resolution prover
def test_prover_verdicts_agree_with_z3_and_the_truth_table_on_dev_seeds():
    for seed in QUICK["prove_resolution"]:
        data, truth, out = solved("prove_resolution", seed)
        assert (out["output"]["verdict"] == formal_b.PROVED) == truth["entailed"], seed
        table = formal_b.prove_truth_table(data)
        if table is not None:
            assert (table["verdict"] == formal_b.PROVED) == truth["entailed"], seed


def test_prover_emits_proofs_on_entailed_and_countermodels_on_non_entailed_seeds():
    kinds = set()
    for seed in QUICK["prove_resolution"]:
        data, truth, out = solved("prove_resolution", seed)
        o = out["output"]
        if truth["entailed"]:
            assert len(o["proofs"]) == len(data["goal_clauses"]) and o["countermodel"] is None
            assert all(p[-1]["clause"] == [] for p in o["proofs"])
            kinds.add("proof")
        else:
            assert o["proofs"] is None and set(o["countermodel"]) and o["failed_goal"] is not None
            kinds.add("model")
    assert kinds == {"proof", "model"}


def _proved():
    data, truth, out = solved("prove_resolution", 6)
    assert truth["entailed"] and out["output"]["verdict"] == formal_b.PROVED
    return data, truth, out["output"], out["certificate"]


def _first(steps, rule):
    return next(i for i, s in enumerate(steps) if s["rule"] == rule)


def test_proof_checker_rejects_corrupted_proofs():
    data, truth, o, cert = _proved()
    assert _all("prove_resolution", data, o, cert)
    steps = o["proofs"][0]
    r = _first(steps, "resolve")
    corruptions = []
    c = copy.deepcopy(o)                                      # 1 drop the empty clause at the end
    c["proofs"][0] = c["proofs"][0][:-1]
    corruptions.append(c)
    c = copy.deepcopy(o)                                      # 2 a resolvent with a literal added
    extra = next(s for s in data["premise_clauses"][0])
    c["proofs"][0][r]["clause"] = sorted(set(c["proofs"][0][r]["clause"]) | {extra.lstrip("~")} | {"zz_new"})
    corruptions.append(c)
    c = copy.deepcopy(o)                                      # 3 a wrong pivot
    c["proofs"][0][r]["pivot"] = "zz_not_an_atom"
    corruptions.append(c)
    c = copy.deepcopy(o)                                      # 4 a parent that comes later (forward reference)
    c["proofs"][0][r]["parents"] = [r, 0]
    corruptions.append(c)
    c = copy.deepcopy(o)                                      # 5 a fabricated premise
    p = _first(steps, "premise")
    c["proofs"][0][p]["clause"] = ["zz_fabricated"]
    corruptions.append(c)
    c = copy.deepcopy(o)                                      # 6 a negated-goal step that negates nothing in the goal
    g = _first(steps, "negated_goal")
    c["proofs"][0][g]["clause"] = ["~zz_other"]
    corruptions.append(c)
    c = copy.deepcopy(o)                                      # 7 the verdict without its proofs
    c["proofs"] = []
    corruptions.append(c)
    c = copy.deepcopy(o)                                      # 8 the opposite verdict
    c["verdict"] = formal_b.NOT_PROVED
    corruptions.append(c)
    c = copy.deepcopy(o)                                      # 9 the empty clause asserted without derivation
    c["proofs"][0] = [{"clause": [], "rule": "premise", "source": 0}]
    corruptions.append(c)
    for n, bad in enumerate(corruptions, 1):
        assert not _all("prove_resolution", data, bad, cert), n
        assert ITEMS["prove_resolution"].score(data, truth, bad)["category"] == "wrong", n


def test_countermodel_checks_reject_corrupted_countermodels():
    data, truth, out = solved("prove_resolution", 0)
    o, cert = out["output"], out["certificate"]
    assert not truth["entailed"] and _all("prove_resolution", data, o, cert)
    goal = data["goal_clauses"][o["failed_goal"]]
    bad = []
    c = copy.deepcopy(o)                                      # make a goal literal true
    lit = goal[0]
    c["countermodel"][lit.lstrip("~")] = not lit.startswith("~")
    bad.append(c)
    c = copy.deepcopy(o)                                      # drop an atom
    c["countermodel"].pop(sorted(c["countermodel"])[0])
    bad.append(c)
    c = copy.deepcopy(o)                                      # every atom flipped
    c["countermodel"] = {a: not v for a, v in c["countermodel"].items()}
    bad.append(c)
    c = copy.deepcopy(o)                                      # an out-of-range goal index
    c["failed_goal"] = 99
    bad.append(c)
    c = copy.deepcopy(o)                                      # a non-boolean value
    c["countermodel"][sorted(c["countermodel"])[0]] = 1
    bad.append(c)
    c = copy.deepcopy(o)                                      # the opposite verdict
    c["verdict"] = formal_b.PROVED
    bad.append(c)
    for n, b in enumerate(bad, 1):
        assert not _all("prove_resolution", data, b, cert), n


def test_declared_scoring_separates_checked_proofs_from_bare_verdicts():
    data, truth, o, _ = _proved()
    score = ITEMS["prove_resolution"].score
    assert score(data, truth, o) == {"quality": 1.0, "category": "correct"}
    z3 = formal_b.prove_z3(data)
    assert z3["verdict"] == formal_b.PROVED and z3["proofs"] is None
    assert score(data, truth, z3) == {"quality": 0.5, "category": "correct"}
    assert score(data, truth, None)["category"] == "abstain"
    nd, nt, nout = solved("prove_resolution", 0)
    assert score(nd, nt, formal_b.prove_z3(nd))["quality"] == 1.0           # a Z3 model is a checkable countermodel


def test_prover_reports_unknown_when_its_budget_is_exhausted(monkeypatch):
    holes = 6
    premises = [[f"In({p},{h})" for h in range(holes)] for p in range(holes + 1)]
    premises += [[f"~In({p},{h})", f"~In({q},{h})"] for h in range(holes) for p in range(holes + 1)
                 for q in range(p + 1, holes + 1)]
    monkeypatch.setattr(formal_b, "TP_MAX_GENERATED", 2000)
    out = formal_b.prove_solve({"premise_clauses": premises, "goal_clauses": [[]]}, BUDGET)
    assert out["status"] == "UNKNOWN" and out["output"] is None


def test_prover_honours_the_request_latency_budget():
    import time
    holes = 7
    premises = [[f"In({p},{h})" for h in range(holes)] for p in range(holes + 1)]
    premises += [[f"~In({p},{h})", f"~In({q},{h})"] for h in range(holes) for p in range(holes + 1)
                 for q in range(p + 1, holes + 1)]
    started = time.monotonic()
    out = formal_b.prove_solve({"premise_clauses": premises, "goal_clauses": [[]]}, {"latency_s": 0.5})
    assert out["status"] == "UNKNOWN" and time.monotonic() - started < 5.0


@pytest.mark.parametrize("bad", [
    {"premise_clauses": [["p"]], "goal_clauses": []},
    {"premise_clauses": [["p q"]], "goal_clauses": [["p"]]},
    {"premise_clauses": [["~~p"]], "goal_clauses": [["p"]]},
    {"premise_clauses": "p", "goal_clauses": [["p"]]},
    {"premise_clauses": [[1]], "goal_clauses": [["p"]]},
])
def test_prover_refuses_malformed_input(bad):
    with pytest.raises(GenomeError):
        formal_b.prove_solve(bad, BUDGET)


# ------------------------------------------------------------------ MDL
def test_mdl_verifier_rejects_corrupted_answers():
    data, truth, out = solved("mdl_model_select", 1)
    o, cert = out["output"], out["certificate"]
    assert _all("mdl_model_select", data, o, cert)
    d = o["degree"]
    bad = []
    c = copy.deepcopy(o)                                      # 1 a degree that is not the argmin
    other = 0 if d else 1
    c["degree"] = other
    c["coefficients"] = formal_b._mdl_answer(*formal_b._mdl_input(data)[:2], other)["coefficients"]
    bad.append(c)
    c = copy.deepcopy(o)                                      # 2 a code length altered
    c["code_lengths_bits"][d] -= 5.0
    bad.append(c)
    c = copy.deepcopy(o)                                      # 3 a coefficient altered
    c["coefficients"][0] += 1.0
    bad.append(c)
    c = copy.deepcopy(o)                                      # 4 a wrong frame
    c["center"] += 0.5
    bad.append(c)
    c = copy.deepcopy(o)                                      # 5 a code length missing
    c["code_lengths_bits"] = c["code_lengths_bits"][:-1]
    bad.append(c)
    c = copy.deepcopy(o)                                      # 6 coefficients of the wrong length
    c["coefficients"] = c["coefficients"] + [0.0]
    bad.append(c)
    c = copy.deepcopy(o)                                      # 7 every code length shifted equally (argmin kept)
    c["code_lengths_bits"] = [v + 1.0 for v in c["code_lengths_bits"]]
    bad.append(c)
    c = copy.deepcopy(o)                                      # 8 a NaN-free but non-number entry
    c["degree"] = float(d)
    bad.append(c)
    for n, b in enumerate(bad, 1):
        assert not _all("mdl_model_select", data, b, cert), n


def test_mdl_code_length_matches_a_direct_formula_and_baselines_are_honest():
    import numpy as np
    data, truth, out = solved("mdl_model_select", 2)
    x, y, top = formal_b._mdl_input(data)
    n, k = len(x), 1                                         # degree 0: yhat is the mean
    yhat = np.full(n, y.mean())
    rss, fit = float(((y - yhat) ** 2).sum()), float((yhat ** 2).sum())
    direct = 0.5 * ((n - k) * math.log(rss / (n - k)) + k * math.log(fit / k) + math.log(k * (n - k))) / math.log(2)
    assert abs(out["output"]["code_lengths_bits"][0] - direct) < 1e-6 * abs(direct)
    assert formal_b.mdl_max_degree(data)["degree"] == top == 8
    for fn in (formal_b.mdl_bic, formal_b.mdl_cv):
        assert 0 <= fn(data)["degree"] <= top
    assert ITEMS["mdl_model_select"].score(data, truth, out["output"])["quality"] == 1.0
    assert ITEMS["mdl_model_select"].score(data, truth, None)["category"] == "abstain"


@pytest.mark.parametrize("bad", [
    {"observations_x": [1, 2, 3], "observations_y": [1, 2, 3]},
    {"observations_x": [1, 1, 1, 1], "observations_y": [1, 2, 3, 4]},
    {"observations_x": [1, 2, 3, 4], "observations_y": [1, 2, 3]},
    {"observations_x": [1, 2, 3, 4], "observations_y": [1, 2, 3, float("nan")]},
    {"observations_x": [1, 2, 3, 4], "observations_y": [1, 2, 3, 4], "max_degree": 9},
])
def test_mdl_refuses_malformed_input(bad):
    with pytest.raises(GenomeError):
        formal_b.mdl_solve(bad, BUDGET)


# ------------------------------------------------------------------ convex QP
def test_qp_verifier_rejects_corrupted_answers_and_certificates():
    data, truth, out = solved("convex_qp_dual", 0)
    o, cert = out["output"], out["certificate"]
    assert _all("convex_qp_dual", data, o, cert)
    lam = cert["multipliers"]
    active = max(range(len(lam)), key=lambda i: lam[i])
    cases = []
    c = copy.deepcopy(o)                                      # 1 x moved
    c["x"][0] += 0.05
    c["objective"] = formal_b._cqp_objective(__import__("numpy").array(c["x"]), *formal_b._cqp_input(data)[:2])
    cases.append((c, cert))
    c = copy.deepcopy(o)                                      # 2 objective misreported
    c["objective"] -= 1.0
    cases.append((c, cert))
    k = copy.deepcopy(cert)                                   # 3 a negative multiplier
    k["multipliers"][active] = -abs(k["multipliers"][active]) - 1.0
    cases.append((o, k))
    k = copy.deepcopy(cert)                                   # 4 all multipliers zero (stationarity and gap fail)
    k["multipliers"] = [0.0] * len(lam)
    cases.append((o, k))
    k = copy.deepcopy(cert)                                   # 5 multipliers scaled
    k["multipliers"] = [2 * v for v in lam]
    cases.append((o, k))
    k = copy.deepcopy(cert)                                   # 6 certificate missing
    k.pop("multipliers")
    cases.append((o, k))
    c = copy.deepcopy(o)                                      # 7 x scaled out of the feasible set
    c["x"] = [3 * v + 1 for v in c["x"]]
    cases.append((c, cert))
    k = copy.deepcopy(cert)                                   # 8 multiplier on an inactive row
    inactive = min(range(len(lam)), key=lambda i: lam[i])
    k["multipliers"][inactive] += 1.0
    cases.append((o, k))
    for n, (out_bad, cert_bad) in enumerate(cases, 1):
        assert not _all("convex_qp_dual", data, out_bad, cert_bad), n


def test_qp_reference_and_solver_agree_and_the_gap_bounds_suboptimality():
    import numpy as np
    for seed in QUICK["convex_qp_dual"]:
        data, truth, out = solved("convex_qp_dual", seed)
        q, c, g, h = formal_b._cqp_input(data)
        x = np.array(out["output"]["x"])
        lam = np.array(out["certificate"]["multipliers"])
        dual = formal_b._dual_value(lam, q, c, g, h)
        assert dual <= truth["optimum"] + 1e-7 * (1 + abs(truth["optimum"]))      # weak duality
        assert abs(formal_b._cqp_objective(x, q, c) - truth["optimum"]) <= 1e-7 * (1 + abs(truth["optimum"]))


def test_qp_abstains_on_an_indefinite_hessian():
    data = {"hessian": [[1.0, 0.0], [0.0, -1.0]], "linear_cost": [0.0, 0.0],
            "inequality_matrix": [[1.0, 0.0]], "inequality_rhs": [1.0]}
    assert formal_b.cqp_solve(data, BUDGET)["status"] == "ABSTAIN"


@pytest.mark.parametrize("bad", [
    {"hessian": [[1.0, 2.0], [0.0, 1.0]], "linear_cost": [0, 0], "inequality_matrix": [[1, 0]], "inequality_rhs": [1]},
    {"hessian": [[1.0]], "linear_cost": [0, 0], "inequality_matrix": [[1, 0]], "inequality_rhs": [1]},
    {"hessian": [[1.0]], "linear_cost": [0], "inequality_matrix": [], "inequality_rhs": []},
    {"hessian": [[1.0]], "linear_cost": [0], "inequality_matrix": [[1]], "inequality_rhs": [1, 2]},
])
def test_qp_refuses_malformed_input(bad):
    with pytest.raises(GenomeError):
        formal_b.cqp_solve(bad, BUDGET)
