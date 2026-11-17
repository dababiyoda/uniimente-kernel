"""Residual safeguards ported from the 2026-10-01 convergence work onto the Mind frontier.

Each test first reproduced a defect on `claude/greg-polyintelligence-mind@d57d47e`:

* a CP-SAT "OPTIMAL" claim that is only feasible, and an "INFEASIBLE" claim about a feasible
  model, both passed verification, because only substitution and artifact consistency were
  checked (the verifier's own dissent said no infeasibility certificate was established);
* a Z3 unsat core naming a satisfiable subset passed;
* a protection intervention marked `lawful: true, consent: true` was modeled as permitted,
  which is the unsupported "Law = 1" assertion the directive forbids (section 13).
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from greg.cognition.cortex import reason, registry_view
from greg.cognition.verification import verify

MODEL = {"variables": {"x": [0, 10], "y": [0, 10]},
         "constraints": [{"coefficients": {"x": 1, "y": 1}, "op": ">=", "rhs": 5}],
         "objective": {"coefficients": {"x": 1, "y": 2}, "sense": "min"}}
SHA = "sha256:" + "a" * 64
LAW = {"gate": "law", "state": "supported", "origin": "qualified_human", "scope": "US-NY", "provenance": SHA,
       "reviewer": "counsel:1"}
CONSENT = {"gate": "consent", "state": "supported", "origin": "consent_capture", "scope": "pilot", "provenance": "ledger:2"}
RIGHTS = {"gate": "rights", "state": "not_applicable", "origin": "kernel_policy_engine", "scope": "no rights impact",
          "provenance": "policy:1"}
AUTH = {"gate": "authority", "state": "supported", "origin": "founder_signed", "scope": "pilot", "provenance": "ledger:1"}


@pytest.fixture(scope="module")
def registry():
    return registry_view()


def req(operation, data, **kw):
    return {"problem_id": "residual:" + operation, "operation": operation, "data": deepcopy(data), **kw}


def _forge(receipt, **output):
    """A self-consistent lie: output and artifact agree, so consistency checks cannot see it."""
    out = {**receipt["output"], **output}
    proof = {**receipt["proof_artifact"], "solution": out.get("solution", {}),
             "solver_status": out["solver_status"]}
    return {"output": out, "proof": proof, "status": "ANSWER", "formal_validity": "VALID_CONDITIONAL_ON_MODEL"}


# ------------------------------------------------------------------ optimization and feasibility claims
def test_a_feasible_but_not_optimal_claim_is_refuted_by_a_second_engine(registry):
    # Since 4430138 the base's Z3 certificate is the second engine (it superseded this branch's own check).
    r = reason(req("optimize", MODEL), registry=registry)
    assert r["output"]["solver_status"] == "OPTIMAL"
    assert r["evaluator_result"]["checks"]["no_strictly_better_assignment_found"] is True
    lie = _forge(r, solution={"x": 10, "y": 0}, objective_value=10.0)
    lie["proof"].update({"bound": 10.0, "optimality_gap": 0.0})   # consistent with itself, so only Z3 can see it
    checked = verify("optimization", MODEL, lie, "optimization_certificate")
    assert checked["verdict"] == "REFUTED" and checked["checks"]["no_strictly_better_assignment_found"] is False
    assert checked["certificate"]["status"] == "REFUTED"


def test_an_infeasibility_claim_about_a_feasible_model_is_refuted(registry):
    infeasible = deepcopy(MODEL)
    infeasible["constraints"].append({"coefficients": {"x": 1, "y": 1}, "op": "<=", "rhs": 2})
    r = reason(req("optimize", infeasible), registry=registry)
    assert r["output"]["solver_status"] == "INFEASIBLE"
    assert r["evaluator_result"]["checks"]["no_feasible_assignment_found"] is True
    assert any("independently certified" in d for d in r["evaluator_result"]["dissent"])
    feasible = req("optimize", MODEL)
    honest = reason(feasible, registry=registry)
    lie = _forge(honest, solver_status="INFEASIBLE", solution={}, objective_value=None)
    lie["proof"].update({"bound": None, "optimality_gap": None})
    forged = verify("optimization", MODEL, lie, "optimization_certificate")
    assert forged["verdict"] == "REFUTED" and forged["checks"]["no_feasible_assignment_found"] is False


def test_unsat_cores_are_rechecked_and_tested_for_minimality(registry):
    model = {"variables": {"x": [0, 10], "y": [0, 10]},
             "constraints": [{"coefficients": {"x": 1}, "op": ">=", "rhs": 8},
                             {"coefficients": {"x": 1}, "op": "<=", "rhs": 3},
                             {"coefficients": {"y": 1}, "op": ">=", "rhs": 1}]}
    r = reason(req("constraints", model), registry=registry)
    core = r["evaluator_result"]["cross_checks"]["unsat_core"]
    assert r["output"]["solver_status"] == "UNSAT" and core["core_unsat"] is True and core["minimal"] is True
    assert r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED"
    padded = {**r, "proof_artifact": {**r["proof_artifact"], "unsat_core": ["constraint_0", "constraint_1", "constraint_2"]}}
    answer = {"output": r["output"], "proof": padded["proof_artifact"], "status": "ANSWER",
              "formal_validity": "VALID_CONDITIONAL_ON_MODEL"}
    padded_check = verify("formal", model, answer, "formal_model")
    assert padded_check["cross_checks"]["unsat_core"]["minimal"] is False
    assert any("not minimal" in d for d in padded_check["dissent"])
    answer["proof"] = {**r["proof_artifact"], "unsat_core": ["constraint_2"]}
    assert verify("formal", model, answer, "formal_model")["verdict"] == "REFUTED"


def test_the_shared_engine_is_disclosed_not_hidden(registry):
    model = {"variables": {"x": [0, 1]}, "constraints": [{"coefficients": {"x": 1}, "op": ">=", "rhs": 2}]}
    r = reason(req("constraints", model), registry=registry)
    assert any("same engine" in d for d in r["evaluator_result"]["dissent"])


def _without_z3(tmp_path):
    """A real interpreter with no third-party packages: the verifier worker launched with it cannot import Z3."""
    import subprocess
    import venv
    venv.EnvBuilder(with_pip=False, system_site_packages=False).create(tmp_path / "bare")
    bare = str(tmp_path / "bare" / "bin" / "python")
    probe = subprocess.run([bare, "-I", "-c", "import z3"], capture_output=True, text=True)
    assert probe.returncode != 0 and "No module named 'z3'" in probe.stderr     # genuinely absent, recorded
    return bare


def _optimum(registry):
    r = reason(req("optimize", MODEL), registry=registry)
    answer = {"output": r["output"], "proof": r["proof_artifact"], "status": "ANSWER",
              "formal_validity": "VALID_CONDITIONAL_ON_MODEL"}
    return r, answer


def test_the_real_verifier_worker_without_z3_certifies_nothing_and_claims_no_finding(registry, monkeypatch,
                                                                                         tmp_path):
    # Review 2026-11-17 (finding 1): the old test ran reason() with Z3 present, then removed Z3 from this process
    # only. Here the actual verifier worker (cortex.independent_verify, a separate isolated process) runs once under
    # an interpreter that has Z3 and once under one that genuinely has none.
    import sys
    from greg.cognition import cortex
    from greg.cognition.verification import certified_for
    _, answer = _optimum(registry)
    geometry, _ = cortex.compile_problem(req("optimize", MODEL))
    present = cortex.independent_verify("optimization", MODEL, answer, "optimization_certificate", geometry)
    monkeypatch.setattr(sys, "executable", _without_z3(tmp_path))
    absent = cortex.independent_verify("optimization", MODEL, answer, "optimization_certificate", geometry)
    assert present["certificate"]["status"] == "CERTIFIED"
    assert present["checks"]["no_strictly_better_assignment_found"] is True
    assert certified_for(present, MODEL, answer["proof"], "OPTIMAL")
    assert absent["certificate"]["status"] == "NOT_RUN" and absent["certificate"]["reason"] == "z3-solver is not installed"
    # the optional diagnostic is not falsely refuted, and no check is named for a finding nobody made (finding 3)
    assert absent["verdict"] == "STRUCTURALLY_VERIFIED"
    assert "no_strictly_better_assignment_found" not in absent["checks"]
    assert "no_strictly_better_assignment_found" in absent["inconclusive"]
    assert any("not independently certified" in d for d in absent["dissent"])
    # a reader that needs certification is blocked (finding 2)
    assert not certified_for(absent, MODEL, answer["proof"], "OPTIMAL")
    fractional = deepcopy(MODEL)
    fractional["constraints"][0]["coefficients"]["x"] = 1.5  # not the integer model CP-SAT accepts
    from greg.cognition.verification import _z3_certificate
    assert _z3_certificate(fractional, integers=True)["status"] == "NOT_RUN"  # not truncated to 1


def test_a_certificate_counts_only_for_its_own_problem_candidate_claim_and_verifier(registry):
    # Review 2026-11-17 (finding 2): a status of CERTIFIED alone may belong to anything. Each binding is attacked.
    from greg.cognition import composition as K
    from greg.cognition.verification import certified_for
    solved, answer = _optimum(registry)
    assert K._optimality(solved, MODEL) == "proven" and certified_for(solved["evaluator_result"], MODEL,
                                                                     solved["proof_artifact"], "OPTIMAL")
    other = deepcopy(MODEL)
    other["constraints"][0]["rhs"] = 6
    certificate = solved["evaluator_result"]["certificate"]

    def with_certificate(**binding):
        forged = deepcopy(solved)
        forged["evaluator_result"]["certificate"] = {**deepcopy(certificate),
                                                     "binding": {**certificate["binding"], **binding}}
        return forged
    status_only = deepcopy(solved)
    status_only["evaluator_result"]["certificate"].pop("binding")
    foreign_candidate = deepcopy(solved)
    foreign_candidate["proof_artifact"] = {**solved["proof_artifact"], "objective_value": 999}
    stale = with_certificate(verifier={"module": "greg.cognition.verification", "source": "sha256:" + "0" * 64})
    for attacked, model in ((solved, other), (status_only, MODEL), (foreign_candidate, MODEL), (stale, MODEL),
                            (with_certificate(claim="FEASIBLE"), MODEL),
                            (with_certificate(obligation="no_feasible_assignment"), MODEL)):
        assert K._optimality(attacked, model) != "proven"
    unrun = deepcopy(solved)
    unrun["evaluator_result"]["certificate"]["status"] = "UNKNOWN"
    assert K._optimality(unrun, MODEL) != "proven"


def test_the_second_engine_stays_inside_the_verifier_budget():
    # verify() runs in the cognition worker under the request's latency limit; an exhausted budget is
    # undecided, and a large core is re-checked without spending one solve per member.
    import time
    from fractions import Fraction
    from greg.cognition.verification import MINIMALITY_CAP, _z3_certificate, _z3_core_check
    assert _z3_certificate(MODEL, integers=True, better_than=Fraction(5), sense="min",
                           deadline=time.monotonic())["status"] == "NOT_RUN"
    model = {"variables": {"x": [0, 10]},
             "constraints": [{"coefficients": {"x": 1}, "op": ">=", "rhs": 8},
                             {"coefficients": {"x": 1}, "op": "<=", "rhs": 3}]
             + [{"coefficients": {"x": 1}, "op": ">=", "rhs": 0}] * MINIMALITY_CAP}
    core = [f"constraint_{i}" for i in range(len(model["constraints"]))]
    assert _z3_core_check(model, core, budget_s=0)["core_unsat"] is None
    assert _z3_core_check(model, core, deadline=time.monotonic())["core_unsat"] is None   # the caller's deadline binds
    large = _z3_core_check(model, core)
    assert large["core_unsat"] is True and large["minimal"] is None and "not tested" in large["status"]
    assert _z3_core_check(model, core[:2])["minimal"] is True


# ------------------------------------------------------------------ legitimacy is evidence, not assertion
BASE = {"exploit_payoff": 10, "opportunity": .5, "detection_probability": .5, "evidence_durability": .9,
        "accountability_probability": .5, "restitution_cost": 10}


def _intervention(registry, **option):
    # The protection adapter is registered but not attached on this frontier, so the solver is
    # exercised directly; attaching it remains the founder's decision.
    from greg.cognition.protection import assess
    data = {"affected_party": {"affected_party": "pseudonym:1", "immediate_harm": .2},
            "interventions": [{"id": "audit", **BASE, **option}]}
    r = assess(data, {})
    return r, r["output"]["interventions"][0]


def test_a_bare_lawful_and_consent_assertion_no_longer_permits(registry):
    r, modeled = _intervention(registry, lawful=True, consent=True)
    assert modeled["blocked"] is True
    assert set(modeled["blocked_by"]) >= {"law: unresolved", "consent: unresolved"}
    assert r["status"] == "HUMAN_REVIEW_REQUIRED" and r["output"]["recommendation"] is None


def test_permission_bearing_records_unblock_and_prohibitions_still_block(registry):
    _, modeled = _intervention(registry, legitimacy=[LAW, CONSENT, RIGHTS, AUTH])
    assert modeled["blocked"] is False and modeled["legitimacy"]["verdict"] == "PASS"
    _, modeled = _intervention(registry, legitimacy=[LAW, CONSENT, RIGHTS, AUTH], lawful=False)
    assert modeled["blocked"] is True
    expired = {**LAW, "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}
    _, modeled = _intervention(registry, legitimacy=[expired, CONSENT, RIGHTS, AUTH])
    assert modeled["blocked"] is True and "law: unresolved" in modeled["blocked_by"]


def test_records_are_typed_and_context_never_settles_a_gate():
    from greg.cognition.legitimacy import LegitimacyRecord, evaluate
    from greg.cognition.contracts import CognitionError
    assert evaluate([{**LAW, "origin": "model_interpretation"}], consequential=True)["gates"]["law"]["state"] == "unresolved"
    no_reviewer = {k: v for k, v in LAW.items() if k != "reviewer"}
    assert evaluate([no_reviewer], consequential=True)["gates"]["law"]["state"] == "unresolved"
    assert evaluate([{**CONSENT, "origin": "kernel_policy_engine"}], consequential=True)["gates"]["consent"]["state"] == "unresolved"
    rumour = {**LAW, "state": "prohibited", "origin": "model_interpretation"}
    assert evaluate([rumour], consequential=False)["gates"]["law"]["state"] == "unresolved"
    assert evaluate([], consequential=False)["verdict"] == "PASS"
    for bad in ({**LAW, "state": "unresolved"}, {**LAW, "origin": "rumour"}, {**LAW, "gate": "vibes"}):
        with pytest.raises(CognitionError):
            LegitimacyRecord.from_dict(bad)


def test_strict_inequalities_are_rechecked_not_crashed(registry):
    # The frontier's formal models accept strict < and > (real-valued). The core re-check must pose them too;
    # before this, an honest UNSAT over strict constraints crashed the verifier worker and abstained.
    model = {"variables": {"x": [0, 10]},
             "constraints": [{"coefficients": {"x": 1}, "op": ">", "rhs": 5},
                             {"coefficients": {"x": 1}, "op": "<", "rhs": 3}]}
    r = reason(req("constraints", model), registry=registry)
    assert r["output"]["solver_status"] == "UNSAT" and r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED"
    assert r["evaluator_result"]["cross_checks"]["unsat_core"]["core_unsat"] is True
    from greg.cognition.verification import _z3_core_check
    assert _z3_core_check({"variables": {"x": [0, 1]}, "constraints": [{"coefficients": {"x": 1}, "op": "~", "rhs": 0}]},
                          ["constraint_0"])["core_unsat"] is None   # an unknown operator is undecided, not a crash
