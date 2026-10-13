"""Convergence of the cortex lineages onto the GREG cognition path (directive 2026-10-01).

Each test attacks one mechanism this change adds: the §6 outcome/reason vocabulary,
evidence-backed legitimacy gates, v0.2 receipts that keep v0.1 receipts settling,
failure-diverse verification, the causal estimator against known synthetic truth, the
decision-aware thinking budget, jurisdiction-aware metaconsensus, the typed pipeline,
the AdvantageCase, protection, and the availability ladder. Synthetic data is labelled.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import json
import random

import pytest

from greg.capabilities import BUILTINS, CapabilityError, InvocationContext
from greg.cognition import budget as B
from greg.cognition.contracts import CognitionError, CognitiveReceipt, ConsequenceVector, ProblemGeometry
from greg.cognition.cortex import reason, registry_view
from greg.cognition.gates import LegitimacyRecord, evaluate
from greg.cognition.outcomes import OUTCOMES, REASONS, availability, outcome_for, project, summary
from greg.cognition.pipeline import execute as pipeline
from greg.cognition.verification import metaconsensus, verify

SHA = "sha256:" + "a" * 64
LAW = {"gate": "law", "state": "supported", "origin": "qualified_human", "scope": "US-NY", "provenance": SHA,
       "reviewer": "counsel:1"}
AUTH = {"gate": "authority", "state": "supported", "origin": "founder_signed", "scope": "pilot", "provenance": "ledger:1"}
CONSENT = {"gate": "consent", "state": "supported", "origin": "consent_capture", "scope": "pilot", "provenance": "ledger:2"}
RIGHTS = {"gate": "rights", "state": "not_applicable", "origin": "kernel_policy_engine", "scope": "no rights impact",
          "provenance": "policy:1"}
MODEL = {"variables": {"x": [0, 10], "y": [0, 10]},
         "constraints": [{"coefficients": {"x": 1, "y": 1}, "op": ">=", "rhs": 5}],
         "objective": {"coefficients": {"x": 1, "y": 2}, "sense": "min"}}


def req(operation, data, **kw):
    return {"problem_id": "conv:" + operation, "operation": operation, "data": deepcopy(data), **kw}


@pytest.fixture(scope="module")
def registry():
    return registry_view()


# ------------------------------------------------------------------ §6 outcomes and reasons
def test_outcomes_and_reasons_are_closed_vocabularies_mapped_onto_existing_statuses(registry):
    r = reason(req("calculate", {"expression": "1/3+1/6"}), registry=registry)
    assert r["receipt_version"] == "0.2" and r["outcome"] == "ANSWERED_WITHIN_SCOPE" and r["reasons"] == []
    assert r["abstention_state"] == "NONE"   # the canonical status every consumer reads is unchanged
    r = reason(req("estimate", {"factors": [{"name": "n", "low": 1, "central": 2, "high": 3}]}), registry=registry)
    assert r["outcome"] == "CONDITIONAL_RESULT" and r["reasons"] == ["WORLD_UNVERIFIED"]
    with pytest.raises(ValueError):
        outcome_for("NONE", "arithmetic", False, ["MADE_UP"])
    assert set(OUTCOMES) == {"ANSWERED_WITHIN_SCOPE", "CONDITIONAL_RESULT", "ABSTAIN", "WAIT", "REQUEST_EVIDENCE",
                             "SMALL_EXPERIMENT", "ESCALATE"}
    assert len(REASONS) == 16


@pytest.mark.parametrize("request_,outcome,code", [
    (req("calculate", {"expression": "1"}, geometry={"unknown_geometry": True}), "ABSTAIN", "UNKNOWN_GEOMETRY"),
    (req("invent_unknown_intelligence", {}), "ABSTAIN", "UNKNOWN_GEOMETRY"),
    (req("treatment_effect", {"design": "observational", "treated": [1, 2], "control": [0, 1]}),
     "SMALL_EXPERIMENT", "NON_IDENTIFIABLE"),
    (req("constraints", MODEL | {"objective": None}, consequences={"financial": .9}),
     "REQUEST_EVIDENCE", "FORMALIZATION_INCOMPLETE"),
    (req("calculate", {"expression": "[1][0]"}), "ABSTAIN", "MODEL_INVALID"),
    (req("simulate", {"seed": 0, "samples": 10, "steps": 100, "step_probability": .5}, geometry={"compute_limit": 10}),
     "ABSTAIN", "BUDGET_EXHAUSTED"),
    (req("calculate", {"expression": "1"}, geometry={"legal_content": True}), "ESCALATE", "HUMAN_JUDGMENT_REQUIRED"),
    (req("calculate", {"expression": "1"}, consequences={"lawful": False}), "ABSTAIN", "POLICY_REFUSAL"),
    (req("interpret", {"text": "x"}), "ABSTAIN", "CAPABILITY_UNAVAILABLE"),
    (req("calculate", {"expression": "1"}, evidence_expires_at="2020-01-01T00:00:00Z"),
     "REQUEST_EVIDENCE", "INSUFFICIENT_EVIDENCE"),
    (req("calculate", {"expression": "1"}, geometry={"out_of_distribution": True}, consequences={"financial": .9}),
     "ESCALATE", "OUT_OF_DISTRIBUTION"),
    (req("calculate", {"expression": "1"}, consequences={"financial": .9}), "CONDITIONAL_RESULT", "AUTHORITY_REQUIRED"),
    (req("value_of_information", {"prior_best_value": 1, "cost": 0, "posterior_scenarios": [
        {"probability": .5, "best_value": 4}, {"probability": .5, "best_value": 2}]}), "REQUEST_EVIDENCE", None),
])
def test_each_branch_records_its_reason_code(registry, request_, outcome, code):
    if request_["data"].get("objective", 1) is None:
        request_["data"].pop("objective")
    r = reason(request_, registry=registry)
    assert r["outcome"] == outcome, (r["abstention_state"], r["reasons"], r["missing_information"])
    if code:
        assert code in r["reasons"]
    assert all(c in REASONS for c in r["reasons"])


def test_old_receipts_project_without_rewriting(registry):
    r = reason(req("calculate", {"expression": "2"}), registry=registry)
    legacy = {k: v for k, v in r.items() if k not in ("outcome", "reasons")}
    view = project(legacy)
    assert view == {"outcome": "ANSWERED_WITHIN_SCOPE", "reasons": [], "derived_from_status": True}
    assert any("Answer" in line for line in summary(r)) and "grants nothing" in summary(r)[-1]


# ------------------------------------------------------------------ legitimacy gates
def test_a_bare_assertion_or_a_missing_prohibition_is_not_permission():
    asserted = [{**LAW, "origin": "self_asserted"}, {**AUTH, "origin": "model_interpretation"}]
    result = evaluate(asserted, consequential=True)
    assert result["verdict"] == "UNRESOLVED" and set(result["unresolved"]) == {"law", "consent", "rights", "authority"}
    assert evaluate([], consequential=True)["verdict"] == "UNRESOLVED"
    assert evaluate([LAW, AUTH, CONSENT, RIGHTS], consequential=True)["verdict"] == "PASS"
    assert evaluate([], consequential=False)["verdict"] == "PASS"


def test_law_needs_a_reviewer_consent_needs_the_person_and_expiry_counts():
    no_reviewer = {k: v for k, v in LAW.items() if k != "reviewer"}
    assert evaluate([no_reviewer, AUTH, CONSENT, RIGHTS], consequential=True)["gates"]["law"]["state"] == "unresolved"
    policy_consent = {**CONSENT, "origin": "kernel_policy_engine"}
    assert evaluate([LAW, AUTH, policy_consent, RIGHTS], consequential=True)["gates"]["consent"]["state"] == "unresolved"
    exempt = {**CONSENT, "origin": "kernel_policy_engine", "state": "not_applicable"}
    assert evaluate([LAW, AUTH, exempt, RIGHTS], consequential=True)["verdict"] == "PASS"
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    result = evaluate([{**LAW, "expires_at": past}, AUTH, CONSENT, RIGHTS], consequential=True)
    assert result["gates"]["law"]["state"] == "unresolved" and result["gates"]["law"]["expired"]


def test_prohibitions_block_even_harmless_computation_and_rumours_force_review(registry):
    prohibited = {**AUTH, "state": "prohibited"}
    r = reason(req("calculate", {"expression": "1"}, legitimacy=[prohibited]), registry=registry)
    assert r["abstention_state"] == "PROHIBITED" and r["output"] is None
    rumour = {**LAW, "state": "prohibited", "origin": "model_interpretation"}
    assert evaluate([rumour], consequential=False)["gates"]["law"]["state"] == "unresolved"
    with pytest.raises(CognitionError):
        LegitimacyRecord.from_dict({**LAW, "state": "unresolved"})
    with pytest.raises((CognitionError, CapabilityError, ValueError)):
        reason(req("calculate", {"expression": "1"}, legitimacy=[{**LAW, "origin": "rumour"}]), registry=registry)


# ------------------------------------------------------------------ receipts
def test_v01_receipts_keep_their_identity_and_still_settle(registry):
    from greg.cognition.settlement import _valid_receipt
    r = reason(req("calculate", {"expression": "2"}), registry=registry)
    assert _valid_receipt(r)
    fields = {k: v for k, v in r.items() if k != "receipt_id"}
    legacy = CognitiveReceipt(**{k: v for k, v in fields.items() if k in CognitiveReceipt.__dataclass_fields__
                                 and k not in ("receipt_version", "outcome", "reasons", "mission_id", "claim_ids",
                                               "model_provenance", "execution_mode", "l1_checks", "legitimacy",
                                               "budget")}).to_dict()
    assert "outcome" not in legacy and "details" not in legacy["consequence_vector"] and _valid_receipt(legacy)
    tampered = dict(r, output={"exact": "3"})
    assert not _valid_receipt(tampered)
    with pytest.raises(CognitionError):
        CognitiveReceipt(**{**fields, "execution_mode": "live"})
    with pytest.raises(CognitionError):
        CognitiveReceipt(**{**fields, "outcome": "DONE"})


def test_l1_checks_and_legitimacy_are_on_every_receipt(registry):
    r = reason(req("calculate", {"expression": "2"}), registry=registry)
    assert {c["check"] for c in r["l1_checks"]} >= {"schema_valid", "evidence_fresh", "money_budget_zero", "method_available"}
    assert all(c["layer"] == "L1" for c in r["l1_checks"])
    assert r["legitimacy"]["verdict"] == "PASS" and r["legitimacy"]["authority_created"] is False
    r = reason(req("calculate", {"expression": "2"}, consequences={"financial": .9}, legitimacy=[LAW, AUTH, CONSENT, RIGHTS]),
               registry=registry)
    assert r["legitimacy"]["verdict"] == "PASS" and "AUTHORITY_REQUIRED" in r["reasons"]  # world authority still separate


def test_consequence_vector_details_are_typed():
    ConsequenceVector(financial=.4, details={"financial": {"severity": .4, "likelihood": [.1, .3],
                                                           "affected_parties": ["customer"], "mitigations": ["refund"]}})
    for bad in ({"made_up": {}}, {"financial": {"likelihood": [.5, .1]}}, {"financial": {"colour": "red"}}):
        with pytest.raises(CognitionError):
            ConsequenceVector(details=bad)
    assert ProblemGeometry(out_of_distribution=True).out_of_distribution


# ------------------------------------------------------------------ failure-diverse verification
def test_cp_sat_optimality_is_attacked_by_a_second_engine(registry):
    r = reason(req("optimize", MODEL), registry=registry)
    assert r["output"]["solver_status"] == "OPTIMAL"
    assert r["evaluator_result"]["checks"]["optimality_cross_engine"] is True
    lie = {"output": {**r["output"], "solution": {"x": 10, "y": 0}, "objective_value": 10.0}, "proof": r["proof_artifact"]}
    checked = verify("optimization", MODEL, lie, "optimization_certificate")
    assert checked["verdict"] == "REFUTED" and checked["checks"]["optimality_cross_engine"] is False


def test_infeasibility_claims_are_cross_checked(registry):
    infeasible = deepcopy(MODEL)
    infeasible["constraints"].append({"coefficients": {"x": 1, "y": 1}, "op": "<=", "rhs": 2})
    r = reason(req("optimize", infeasible), registry=registry)
    assert r["output"]["solver_status"] == "INFEASIBLE"
    assert r["evaluator_result"]["checks"]["infeasibility_cross_engine"] is True
    lie = {"output": {"solver_status": "INFEASIBLE", "solution": {}, "objective_value": None}, "proof": r["proof_artifact"]}
    assert verify("optimization", MODEL, lie, "optimization_certificate")["verdict"] == "REFUTED"


def test_unsat_cores_are_rechecked_and_tested_for_minimality(registry):
    model = {"variables": {"x": [0, 10], "y": [0, 10]},
             "constraints": [{"coefficients": {"x": 1}, "op": ">=", "rhs": 8},
                             {"coefficients": {"x": 1}, "op": "<=", "rhs": 3},
                             {"coefficients": {"y": 1}, "op": ">=", "rhs": 1}]}
    r = reason(req("constraints", model), registry=registry)
    cross = r["evaluator_result"]["cross_checks"]["unsat_core"]
    assert r["output"]["solver_status"] == "UNSAT" and cross["core_unsat"] is True and cross["minimal"] is True
    padded = {"output": r["output"], "proof": {**r["proof_artifact"], "unsat_core": ["constraint_0", "constraint_1", "constraint_2"]}}
    assert verify("formal", model, padded, "formal_model")["cross_checks"]["unsat_core"]["minimal"] is False
    wrong = {"output": r["output"], "proof": {**r["proof_artifact"], "unsat_core": ["constraint_2"]}}
    assert verify("formal", model, wrong, "formal_model")["verdict"] == "REFUTED"


def test_a_suboptimal_path_is_refuted_by_an_independent_dijkstra(registry):
    data = {"edges": [["a", "b", 2], ["b", "c", 3], ["a", "c", 9]], "start": "a", "goal": "c"}
    r = reason(req("shortest_path", data), registry=registry)
    assert r["evaluator_result"]["checks"]["path_optimal_recheck"] is True
    lie = {"output": {"path": ["a", "c"], "cost": 9, "reachable": True}, "proof": r["proof_artifact"]}
    assert verify("graph", data, lie, "search_trace")["verdict"] == "REFUTED"
    unreachable = {"output": {"path": [], "cost": None, "reachable": False}, "proof": r["proof_artifact"]}
    assert verify("graph", data, unreachable, "search_trace")["verdict"] == "REFUTED"


def test_model_invalid_is_not_an_unknown(monkeypatch):
    from ortools.sat.python import cp_model
    from greg.cognition import solvers
    monkeypatch.setattr(cp_model.CpSolver, "solve", lambda self, model: cp_model.MODEL_INVALID)
    monkeypatch.setattr(cp_model.CpSolver, "status_name", lambda self, status: "MODEL_INVALID")
    out = solvers.optimization(deepcopy(MODEL), {"latency_limit": 1})
    assert out["status"] == "MODEL_INVALID" and out["formal_validity"] == "UNKNOWN"
    assert outcome_for("MODEL_INVALID", "optimization", False, ["MODEL_INVALID"])[0] == "ABSTAIN"


# ------------------------------------------------------------------ causal (synthetic, labelled)
def _trial(effect, n, seed, *, missing=None, shift=0.0):
    rng = random.Random(seed)
    control = [rng.gauss(10, 2) for _ in range(n)]
    treated = [rng.gauss(10 + effect, 2) for _ in range(n)]
    data = {"design": "randomized", "treated": treated, "control": control, "synthetic": True,
            "treatment": "synthetic intervention", "outcome": "synthetic outcome", "seed": 1}
    if missing:
        data["missing"] = missing
    if shift:
        data["pre_treatment"] = {"treated": [rng.gauss(5 + shift, 1) for _ in range(n)],
                                 "control": [rng.gauss(5, 1) for _ in range(n)]}
    return data


def test_identified_synthetic_effect_recovers_known_ground_truth(registry):
    truth = 2.0
    r = reason(req("treatment_effect", _trial(truth, 200, 11)), registry=registry)
    out = r["output"]
    assert r["abstention_state"] == "NONE" and out["identified_conditionally"] is True
    assert out["ci"][0] <= out["effect"] <= out["ci"][1] and abs(out["effect"] - truth) < .6
    assert out["permutation_p_value"] < .01 and r["proof_artifact"]["synthetic"] is True
    assert r["evaluator_result"]["checks"]["estimate_recompute"] is True
    assert r["outcome"] == "CONDITIONAL_RESULT"   # identification is conditional, never world truth


def test_the_95_percent_interval_covers_the_known_effect_at_its_nominal_rate():
    """One seeded interval may miss the truth; that is what 95% means. Coverage is the property."""
    from greg.cognition.solvers import causal
    hits = 0
    for seed in range(100):
        out = causal(_trial(2.0, 40, 1000 + seed), {})["output"]
        hits += out["ci"][0] <= 2.0 <= out["ci"][1]
    assert 88 <= hits <= 100, hits


def test_unidentified_and_inadequately_evidenced_claims_abstain(registry):
    r = reason(req("treatment_effect", {**_trial(2, 50, 3), "design": "observational"}), registry=registry)
    assert r["abstention_state"] == "UNIDENTIFIED" and r["outcome"] == "SMALL_EXPERIMENT"
    r = reason(req("treatment_effect", {"design": "randomized", "treated": [1.0], "control": [0.0, 1.0]}), registry=registry)
    assert r["abstention_state"] == "ABSTAIN" and "INSUFFICIENT_EVIDENCE" in r["reasons"]
    attrited = {**_trial(2, 40, 5, missing={"treated": 30, "control": 0}), "outcome_bounds": [-10, 40]}
    r = reason(req("treatment_effect", attrited), registry=registry)
    assert r["abstention_state"] == "UNIDENTIFIED" and r["output"]["effect"] is None
    low, high = r["output"]["identified_set"]
    assert low < 2 < high
    r = reason(req("treatment_effect", _trial(2, 80, 7, shift=2.0)), registry=registry)
    assert r["abstention_state"] == "UNIDENTIFIED" and "placebo" in r["missing_information"][0]


def test_a_lying_causal_estimate_is_refuted(registry):
    data = _trial(2.0, 60, 9)
    r = reason(req("treatment_effect", data), registry=registry)
    lie = {"output": {**r["output"], "effect": 9.0}, "proof": r["proof_artifact"]}
    assert verify("causal", data, lie, "causal_identification")["verdict"] == "REFUTED"


# ------------------------------------------------------------------ thinking budget
DECISION = {"question": "launch or hold the pilot?",
            "states": [{"id": "good", "prior": "0.5"}, {"id": "bad", "prior": "0.5"}],
            "actions": [{"id": "launch", "payoffs": {"good": 100, "bad": -60}}, {"id": "hold", "payoffs": {"good": 0, "bad": 0}}],
            "rates": {"per_second": "0.01", "per_founder_minute": "2"}, "rates_owner": "founder policy ledger:rates-1"}
PERFECT = {"good": {"pos": 1}, "bad": {"neg": 1}}
NOISE = {"good": {"pos": "0.5", "neg": "0.5"}, "bad": {"pos": "0.5", "neg": "0.5"}}


def test_evsi_is_exact_and_bounded_by_evpi():
    result = B.evsi(DECISION, PERFECT)
    assert result["evsi"] == Fraction(30) and result["evpi"] == Fraction(30)
    assert B.evsi(DECISION, NOISE)["evsi"] == 0
    rng = random.Random(4)
    for _ in range(200):
        p = Fraction(rng.randint(1, 99), 100)
        decision = {"states": [{"id": "s", "prior": str(p)}, {"id": "t", "prior": str(1 - p)}],
                    "actions": [{"id": a, "payoffs": {"s": rng.randint(-50, 50), "t": rng.randint(-50, 50)}}
                                for a in ("a", "b", "c")]}
        q = Fraction(rng.randint(0, 100), 100)
        out = B.evsi(decision, {"s": {"x": str(q), "y": str(1 - q)}, "t": {"x": str(1 - q), "y": str(q)}})
        assert 0 <= out["evsi"] <= out["evpi"]


def test_budget_runs_skips_waits_and_refuses_what_is_mandatory():
    step = {"id": "lookup", "kind": "lookup", "likelihoods": PERFECT, "cost": {"seconds": 10}}
    assert B.decide(DECISION, step)["verdict"] == "RUN"
    expensive = {**step, "cost": {"founder_minutes": 20}}
    assert B.decide(DECISION, expensive)["verdict"] == "SKIP"
    noise = {**step, "likelihoods": NOISE}
    assert B.decide(DECISION, noise)["stopping_reason"] == "no possible result changes the best action"
    soon = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    later = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    assert B.decide({**DECISION, "deadline": later}, {**step, "cost": {}, "available_at": soon})["verdict"] == "WAIT"
    for bad in ({**step, "kind": "verification"}, {**step, "cost": {"usd": 1}}):
        with pytest.raises(CognitionError):
            B.decide(DECISION, bad)
    with pytest.raises(CognitionError):
        B.decide({k: v for k, v in DECISION.items() if k != "rates_owner"}, step)


def test_uncertain_priors_and_founder_interruptions_state_the_decision():
    decision = {**DECISION, "alternative_priors": [{"good": "0.95", "bad": "0.05"}],
                "authority_needed": "founder judgment on launch", "cost_of_waiting": "one week of pilot data"}
    ask = {"id": "ask", "kind": "founder_interruption", "likelihoods": PERFECT, "cost": {"founder_minutes": 6}}
    verdict = B.decide(decision, ask)
    assert verdict["verdict"] == "UNCERTAIN"
    escalation = verdict["escalation"]
    assert escalation["decision"] == "launch or hold the pilot?" and escalation["urgency"].startswith("none manufactured")
    assert escalation["options"] and escalation["authority_needed"] and escalation["if_waiting"]


def test_compose_runs_only_optional_requests_worth_their_cost(tmp_path, registry):
    ctx = InvocationContext(workspace=tmp_path, read_roots=(), secrets=None, manifest=BUILTINS["cognition.compose"][0],
                            target="cognition:test", capability_registry=registry)
    from greg.cognition.cortex import compose
    requests = [req("calculate", {"expression": "1"}), req("calculate", {"expression": "2"})]
    out = compose({"requests": requests, "decision": DECISION,
                   "optional": {"1": {"id": "second", "kind": "calculation", "likelihoods": NOISE, "cost": {"seconds": 1}}}}, ctx)
    assert len(out["receipts"]) == 1 and out["budget_log"][0]["verdict"] == "SKIP"
    assert out["receipts"][0]["budget"]["stopping_reason"] == "mandatory request in a bounded composition"
    with pytest.raises(CapabilityError):
        compose({"requests": requests, "optional": {"1": {"kind": "lookup"}}}, ctx)


# ------------------------------------------------------------------ metaconsensus by jurisdiction
def test_non_identification_and_infeasibility_are_not_outvoted(registry):
    causal = reason({**req("treatment_effect", {"design": "observational", "treated": [3, 4], "control": [1, 2]}),
                     "claim_ids": ["pilot-raises-revenue"]}, registry=registry)
    estimate = reason({**req("estimate", {"factors": [{"name": "uplift", "low": 1, "central": 2, "high": 3}]}),
                       "claim_ids": ["pilot-raises-revenue"]}, registry=registry)
    result = metaconsensus([causal, estimate])
    assert result["state"] == "BLOCKED_BY_JURISDICTION"
    governing = result["governing_findings"][0]
    assert governing["epistemic_class"] == "causal" and governing["overrides"] == [estimate["receipt_id"]]
    assert "randomized" in result["next_decisive_test"]["test"]
    alone = reason({**req("calculate", {"expression": "1"}), "claim_ids": ["other"]}, registry=registry)
    assert metaconsensus([alone])["next_decisive_test"] is None


# ------------------------------------------------------------------ typed pipeline
TEXT = "Schedule shifts x and y. Each between 0 and 10 hours. Together at least 5 hours. Minimize cost x + 2y."


def test_pipeline_runs_heterogeneous_stages_with_typed_edges(registry):
    out = pipeline({"pipeline": "schedule_from_request", "source": {"text": TEXT}, "model": MODEL}, registry=registry)
    assert [s["status"] for s in out["stages"]] == ["DECLARED", "PASSED", "NONE", "READY"]
    assert [e["type"] for e in out["edges"]] == ["linear_integer_model", "validated_model", "cognitive_receipt"]
    assert out["receipt"]["evaluator_result"]["checks"]["optimality_cross_engine"] is True
    assert out["outcome"] == "ANSWERED_WITHIN_SCOPE" and out["authority_created"] is False


def test_the_l1_check_catches_an_extractor_that_drops_or_invents_numbers(registry):
    dropped = deepcopy(MODEL); dropped["constraints"] = []
    out = pipeline({"pipeline": "schedule_from_request", "source": {"text": TEXT}, "model": dropped}, registry=registry)
    assert out["reasons"] == ["FORMALIZATION_INCOMPLETE"] and len(out["stages"]) == 2 and out["receipt"] is None
    invented = deepcopy(MODEL); invented["constraints"][0]["rhs"] = 7
    extractor = lambda text: (invented, None)   # labelled fixture extractor, not a model
    out = pipeline({"pipeline": "schedule_from_request", "source": {"text": TEXT}}, registry=registry, client_extract=extractor)
    assert out["model_origin"] == "extracted_supplied_client" and out["reasons"] == ["FORMALIZATION_INCOMPLETE"]
    assert out["stages"][1]["detail"]["model_numbers_not_in_source"] == [7.0]
    out = pipeline({"pipeline": "schedule_from_request", "source": {"text": TEXT}}, registry=registry)
    assert out["reasons"] == ["CAPABILITY_UNAVAILABLE"] and out["outcome"] == "ABSTAIN"


# ------------------------------------------------------------------ AdvantageCase
def _option(oid, kind, benefit, **kw):
    return {"id": oid, "kind": kind, "criteria": {"expected_benefit": benefit, "evidence_strength": kw.pop("ev", .5),
            "durability": .5, "optionality": .5, "residual_exposure": kw.pop("exp", .2), "resource_burden": kw.pop("cost", 1),
            "reversibility": "reversible"}, **kw}


def test_gates_come_before_any_ranking_and_assertions_are_not_legality(registry):
    data = {"options": [_option("hold", "do_nothing", [0, 0], cost=0),
                        _option("pilot", "smallest_intervention", [1, 5], legitimacy=[LAW, AUTH, CONSENT, RIGHTS]),
                        _option("bet", "proposal", [10, 90], lawful=True, consent=True)]}
    r = reason(req("advantage_case", data), registry=registry)
    out = r["output"]
    assert "bet" in [e["id"] for e in out["excluded"]] and out["recommendation"] is None
    assert r["outcome"] == "ESCALATE" and set(out["frontier"]) == {"hold", "pilot"}
    assert set(out["sections"]) == {"evidence", "institutional_leverage", "accountability", "deterrence",
                                    "victim_protection", "minimal_collateral_harm"}
    assert "no multiplicative leverage score" in out["score_note"]
    with pytest.raises(Exception):
        from greg.cognition.advantage import assess
        assess({"options": [_option("pilot", "proposal", [1, 2]), _option("x", "proposal", [1, 2])]}, {})


def test_only_a_stable_founder_policy_ranks_the_frontier(registry):
    options = [_option("hold", "do_nothing", [0, 0], ev=1, exp=0),
               _option("pilot", "smallest_intervention", [1, 5], legitimacy=[LAW, AUTH, CONSENT, RIGHTS], ev=.6, exp=.3)]
    weights = {"owner": "founder", "policy_ref": "ledger:w", "version": "1",
               "weights": {"benefit_low": .6, "evidence_strength": .2, "residual_exposure": .2}}
    r = reason(req("advantage_case", {"options": options, "weights": weights}), registry=registry)
    assert r["output"]["ranking"]["top"] == "pilot" and r["output"]["recommendation"] == "pilot"
    close = {**weights, "weights": {"benefit_low": .5, "evidence_strength": .25, "residual_exposure": .25}}
    r = reason(req("advantage_case", {"options": options, "weights": close}), registry=registry)
    assert "changes" in r["output"]["ranking"]["sensitivity"] and r["output"]["recommendation"] is None
    r = reason(req("advantage_case", {"options": options, "weights": {"weights": {"benefit_low": 1}}}), registry=registry)
    assert r["abstention_state"] == "ABSTAIN" and "MODEL_INVALID" in r["reasons"]


# ------------------------------------------------------------------ protection
def test_coercion_is_refused_and_assertions_do_not_unblock_interventions(registry):
    base = {"exploit_payoff": 10, "opportunity": .5, "detection_probability": .5, "evidence_durability": .9,
            "accountability_probability": .5, "restitution_cost": 10}
    data = {"affected_party": {"affected_party": "pseudonym:1", "immediate_harm": .8, "evidence_at_risk": True,
                               "retaliation_risk": .7},
            "interventions": [{"id": "threaten", "kind": "threat", **base},
                              {"id": "audit", "kind": "independent_audit", "lawful": True, "consent": True,
                               "moves": ["detection_probability"], **base},
                              {"id": "fine", "kind": "contractual_remedy", "moves": ["restitution_cost"],
                               "legitimacy": [LAW, AUTH, CONSENT, RIGHTS], **base}]}
    r = reason(req("deterrence_model", data), registry=registry)
    out = r["output"]
    assert [x["id"] for x in out["refused"]] == ["threaten"]
    modeled = {m["id"]: m for m in out["interventions"]}
    assert modeled["audit"]["blocked"] and modeled["audit"]["levers"] == ["certainty"]
    assert not modeled["fine"]["blocked"] and modeled["fine"]["severity_only"] and modeled["fine"]["reaches_another_party"]
    assert out["review_priorities"][:3] == ["protect_now", "preserve_evidence", "contain_harm"]
    assert any("retaliation" in g for g in out["gaps"]) and any("safe contact" in g for g in out["gaps"])
    assert r["abstention_state"] == "HUMAN_REVIEW_REQUIRED" and out["recommendation"] is None
    with pytest.raises(Exception):
        from greg.cognition.protection import assess
        assess({"affected_party": {"affected_party": "p"}, "interventions": [{"id": "x", "kind": "invented", **base}]}, {})


# ------------------------------------------------------------------ availability ladder
def test_availability_rungs_are_separate(registry, monkeypatch):
    rungs = availability("cognition.exact", BUILTINS["cognition.exact"][0], registry)
    assert rungs["installed"] and rungs["available"] and rungs["externally_verified"] is False
    assert "never by being listed" in rungs["authorized"]
    view = registry_view()
    view.set_state("cognition.exact", "DETACHED")
    assert availability("cognition.exact", BUILTINS["cognition.exact"][0], view)["available"] is False
    import importlib.metadata as md
    real = md.version
    monkeypatch.setattr(md, "version", lambda name: (_ for _ in ()).throw(md.PackageNotFoundError(name))
                        if name == "sympy" else real(name))
    gone = availability("cognition.exact", BUILTINS["cognition.exact"][0], registry)
    assert gone["installed"] is False and "sympy" in gone["why_not_available"]


def test_formalization_coverage_reports_omissions_and_blocks_consequential_use(registry):
    model = deepcopy(MODEL)
    model["requirements"] = [{"id": "R1", "text": "at least 5 hours"}, {"id": "R2", "text": "x at most 4"}]
    model["constraints"][0]["covers"] = ["R1"]
    r = reason(req("optimize", model), registry=registry)
    cov = r["proof_artifact"]["formalization_coverage"]
    assert cov["represented"] == ["R1"] and cov["omitted"] == ["R2"] and "not decidable" in cov["completeness"]
    r = reason(req("optimize", {**model, "formalization_complete": True}, consequences={"financial": .9}), registry=registry)
    assert r["abstention_state"] == "FORMALIZATION_INCOMPLETE" and "R2" in r["missing_information"][0]
    model["constraints"].append({"coefficients": {"x": 1}, "op": "<=", "rhs": 4, "covers": ["R2"]})
    r = reason(req("optimize", {**model, "formalization_complete": True}, consequences={"financial": .9}), registry=registry)
    assert r["abstention_state"] == "WORLD_UNVERIFIED" and r["proof_artifact"]["formalization_coverage"]["omitted"] == []


def test_the_build_directive_is_preserved_byte_exact():
    import hashlib
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    text = (root / "docs/intent/sources/POLYINTELLIGENCE-CORTEX-BUILD-DIRECTIVE-SEED-GENOME-2026-10-01.md").read_text("utf-8")
    body = text.split("=== BEGIN VERBATIM TEXT ===\n", 1)[1].rsplit("\n=== END VERBATIM TEXT ===", 1)[0]
    assert hashlib.sha256(body.encode()).hexdigest() == "3a18620e43e3e38496ad916a5426591e56ce78d6c915f71cc73b4a793cc8d342"


# ------------------------------------------------------------------ safeguards the mutation harness attacks
def test_a_forged_unknown_is_never_success(registry, monkeypatch):
    from greg.cognition import cortex
    real = cortex._numeric

    def unknown(family, data, geometry):
        answer = real(family, data, geometry)
        return {**answer, "status": "UNKNOWN"}
    monkeypatch.setattr(cortex, "_numeric", unknown)
    r = reason(req("constraints", {"variables": {"x": [0, 10]}, "constraints": [
        {"coefficients": {"x": 1}, "op": ">=", "rhs": 3}]}), registry=registry)
    assert r["abstention_state"] == "UNKNOWN" and r["outcome"] == "ABSTAIN" and r["reasons"] == ["SOLVER_UNKNOWN"]


def test_a_paid_route_never_serves_semantic_cognition(registry):
    for config in ({"order": ["anthropic"], "anthropic_model": "any"}, {"order": ["openai", "ollama"]}):
        r = reason(req("interpret", {"text": "x"}), registry=registry, model_config=config)
        assert r["abstention_state"] == "ABSTAIN" and r["reasons"] == ["CAPABILITY_UNAVAILABLE"]
        assert r["model_calls"] if False else r["compute_cost"]["model_calls"] == 0


def test_duplicate_outcome_delivery_settles_once(tmp_path):
    from greg.body import Body
    from greg.cognition.settlement import competence, reconcile
    from tests.greg_fixtures import drop, make_body, mission, signed
    home, key, body_id, _ = make_body(tmp_path)
    params = {"problem_id": "dup:numeric", "operation": "calculate", "data": {"expression": "1/4"}}
    spec = mission("m:duplicate-delivery", checks=[{
        "check_id": "exact", "description": "exact arithmetic",
        "sensor": {"capability": "cognition.solve", "target": "cognition:arithmetic", "params": params},
        "predicate": {"op": "equals", "field": "output.exact", "value": "1/4"}}],
        strategies=[], capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        body.tick()
        observed = [e for e in body.journal.replay("mission.observed") if e.payload["mission_id"] == "m:duplicate-delivery"]
        assert observed
        body.journal.record("mission.observed", dict(observed[-1].payload), key="duplicate-delivery")
        reconcile(body.journal)
        reconcile(body.journal)
        rows = competence(body.journal)
        assert [v["count"] for v in rows.values()] == [1]
        assert len([e for e in body.journal.replay("cognition.settled")]) == 1


# ------------------------------------------------------------------ evaluation harness
def test_the_evaluation_refuses_changed_inputs_and_contaminated_splits(tmp_path, monkeypatch):
    from greg.cognition import evaluation as E
    assert E.score({"item_id": "x", "stratum": "s", "family": "f",
                    "expected": {"answer": False, "outcomes": ["ESCALATE"], "check": None, "hard_if_answered": True}},
                   {"outcome": "ANSWERED_WITHIN_SCOPE", "output": {}, "authority_created": False}, 0)["hard_failure"]
    row = E.score({"item_id": "x", "stratum": "s", "family": "f",
                   "expected": {"answer": True, "outcomes": ["CONDITIONAL_RESULT"],
                                "check": {"field": "v", "value": 1, "tol": None, "kind": "equals"}}},
                  {"outcome": "ANSWERED_WITHIN_SCOPE", "output": {"v": 1}, "authority_created": False}, 0)
    assert row["label"] == "scope_overclaim"
    monkeypatch.setattr(E, "FREEZE", tmp_path / "freeze.json")
    with pytest.raises(SystemExit, match="no freeze manifest"):
        E.run("heldout")
    (tmp_path / "freeze.json").write_text(json.dumps({"inputs": {**E.freeze_inputs(), "loss": {"correct": 1}}}))
    with pytest.raises(SystemExit, match="frozen inputs changed"):
        E.run("heldout")
