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
    r = reason(req("optimize", MODEL), registry=registry)
    assert r["output"]["solver_status"] == "OPTIMAL"
    assert r["evaluator_result"]["checks"]["optimality_cross_engine"] is True
    lie = _forge(r, solution={"x": 10, "y": 0}, objective_value=10.0)
    checked = verify("optimization", MODEL, lie, "optimization_certificate")
    assert checked["verdict"] == "REFUTED" and checked["checks"]["optimality_cross_engine"] is False


def test_an_infeasibility_claim_about_a_feasible_model_is_refuted(registry):
    infeasible = deepcopy(MODEL)
    infeasible["constraints"].append({"coefficients": {"x": 1, "y": 1}, "op": "<=", "rhs": 2})
    r = reason(req("optimize", infeasible), registry=registry)
    assert r["output"]["solver_status"] == "INFEASIBLE"
    assert r["evaluator_result"]["checks"]["infeasibility_cross_engine"] is True
    assert any("corroborated by Z3" in d for d in r["evaluator_result"]["dissent"])
    feasible = req("optimize", MODEL)
    honest = reason(feasible, registry=registry)
    lie = _forge(honest, solver_status="INFEASIBLE", solution={}, objective_value=None)
    lie["proof"].update({"bound": None, "optimality_gap": None})
    assert verify("optimization", MODEL, lie, "optimization_certificate")["verdict"] == "REFUTED"


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


def test_a_missing_second_engine_is_inconclusive_and_said_so_never_a_pass(registry, monkeypatch):
    import sys
    from greg.cognition.verification import _z3_integer_check
    fractional = deepcopy(MODEL)
    fractional["constraints"][0]["coefficients"]["x"] = 1.5  # not the integer model CP-SAT accepts
    assert _z3_integer_check(fractional) is None  # silent, not truncated to 1
    r = reason(req("optimize", MODEL), registry=registry)
    answer = {"output": r["output"], "proof": r["proof_artifact"], "status": "ANSWER",
              "formal_validity": "VALID_CONDITIONAL_ON_MODEL"}
    monkeypatch.setitem(sys.modules, "z3", None)  # import z3 now raises ImportError
    checked = verify("optimization", MODEL, answer, "optimization_certificate")
    assert "optimality_cross_engine" not in checked["checks"]
    assert checked["inconclusive"] == ["optimality_cross_engine"]
    assert any("rests on CP-SAT's report" in d for d in checked["dissent"])


def test_the_second_engine_stays_inside_the_verifier_budget():
    # verify() runs in the cognition worker under the request's latency limit; an exhausted budget is
    # undecided, and a large core is re-checked without spending one solve per member.
    from greg.cognition.verification import MINIMALITY_CAP, _z3_core_check, _z3_integer_check
    assert _z3_integer_check(MODEL, budget_s=0) is None
    model = {"variables": {"x": [0, 10]},
             "constraints": [{"coefficients": {"x": 1}, "op": ">=", "rhs": 8},
                             {"coefficients": {"x": 1}, "op": "<=", "rhs": 3}]
             + [{"coefficients": {"x": 1}, "op": ">=", "rhs": 0}] * MINIMALITY_CAP}
    core = [f"constraint_{i}" for i in range(len(model["constraints"]))]
    assert _z3_core_check(model, core, budget_s=0)["core_unsat"] is None
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
