"""Cortex 0.2.2: the Seed Cortex 0.1.6 repairs (PR #167) ported onto the GREG integration line.

Each defect was reproduced on this line before it was ported (the elevation record of 2026-10-21); each
reproduction stays here as a regression test. Ported, not copied: this line's router has a formal slot with
fallback engines (``route.attempts``), a schedule-extraction composition and a host-withheld registry, so
several rules are adapted to those facts and say so.
"""
from __future__ import annotations

import copy

import pytest

from cortex.contracts import CORTEX_VERSION, Expenditure, OrganResult
from cortex.gates import AuthorityRecord, Option, evaluate_gates
from cortex.genome import seed_registry
from cortex.memory import MIN_OUTCOME_EVIDENCE, CompetenceLedger
from cortex.routing import CPSAT, FERMI, FORMAL, MAX_COMPOSITION, SEMANTIC, Cortex, derive_geometry
from cortex.contracts import Problem
from cortex.schemas import validate
from cortex import routing as cortex_routing

pytest.importorskip("z3")
pytest.importorskip("ortools")

CLOCK = "2026-10-21T00:00:00Z"
SCHEDULE_FEASIBLE = ("Shift: 10 hours. Job A takes 3 hours. Job B takes 4 hours. Job C takes 2 hours. A before C. "
                     "One machine; one job at a time.")
DECL = {"consequence_class": "internal_write", "reversibility": "reversible"}
FORMAL_MODEL = {"requirement": "x + y <= 4",
                "variables": [{"name": "x", "sort": "int", "lo": 0, "hi": 4},
                              {"name": "y", "sort": "int", "lo": 0, "hi": 4}],
                "obligations": [{"id": "R1", "text": "x + y at most 4"}],
                "constraints": [{"id": "C1", "covers": ["R1"], "expr": ["<=", ["+", "x", "y"], 4]}]}
EST_MODEL = {"target": {"name": "c", "unit": "USD/week"}, "expression": ["*", "h", "r"],
             "variables": [{"name": "h", "unit": "hour/week", "low": 30, "high": 50},
                           {"name": "r", "unit": "USD/hour", "low": 40, "high": 60}]}
SOURCES = [{"id": "S1", "text": "The shift is ten hours long."}]
OK_PROV = {"kind": "external_observation", "validation_status": "externally_verified"}


def attr(method):
    return [{"method": method, "role": "final_answer", "uncertainty": "low"}]


def run(payload, pid="p", registry=None, cortex=None):
    receipt = (cortex or Cortex(registry, clock=lambda: CLOCK)).run({"problem_id": pid, "question": "q",
                                                                   "payload": payload})
    validate(receipt, "cortex-receipt")
    return receipt


def test_version_records_the_ported_repairs():
    assert CORTEX_VERSION == "0.2.2"


# ------------------------------------------------------------------ settlement integrity (D1, PRR-13/14/15)
def test_d1_settlement_requires_the_exact_method_and_version_that_ran():
    receipt = run({"formal_model": FORMAL_MODEL, "declared": DECL}, "d1")
    ledger = CompetenceLedger()
    with pytest.raises(ValueError, match="method and version it actually selected"):
        ledger.settle(receipt=receipt, method="cortex.formal.z3", method_version="9.9.9",
                      outcome_status="verified_success", provenance=OK_PROV, attribution=attr("cortex.formal.z3"))
    assert ledger.records() == []
    rec = ledger.settle(receipt=receipt, method="cortex.formal.z3", method_version="0.2.0",
                        outcome_status="verified_success", provenance=OK_PROV, attribution=attr("cortex.formal.z3"))
    assert rec.method_version == "0.2.0"


def test_settlement_refuses_a_route_that_was_selected_but_never_ran():
    refused = run({"formal_model": FORMAL_MODEL, "declared": DECL, "resources": {"max_solver_calls": 0}}, "never")
    assert refused["route"]["selected"] == [FORMAL] and refused["output"]["per_route"] == []
    assert refused["coverage"].startswith("none:")
    ledger = CompetenceLedger()
    with pytest.raises(ValueError, match="actually ran"):
        ledger.settle(receipt=refused, method="cortex.formal.z3", method_version="0.2.0",
                      outcome_status="verified_success", provenance=OK_PROV, attribution=attr("cortex.formal.z3"))
    assert ledger.records() == []
    # a non-settling record (weight 0) is still kept
    ledger.settle(receipt=refused, method="cortex.formal.z3", method_version="0.2.0", outcome_status="absent_feedback",
                  provenance={"kind": "internal_observation"}, attribution=[])
    assert len(ledger.records()) == 1


class _TimedOut:
    """A formal lead that runs and times out, so the plan falls back to CP-SAT (this line's formal slot)."""
    def run(self, problem, geometry, limits):
        return OrganResult(organ_id=FORMAL, organ_version="0.2.0", state="TIMEOUT", answer=None,
                           proof={"proof_class": "formal"}, assumptions=(), uncertainty="timed out",
                           expenditure=Expenditure(solver_calls=1), dependencies=("z3",), origin="solver",
                           notes=("stub timeout",))


def test_a_superseded_lead_settles_only_its_failure_and_the_engine_that_answered_settles_its_answer():
    """Adapted to this line: _run_formal moves a lead that failed into route.attempts, so 'ran' reads per_route and
    attempts. Review of the port (2026-10-21): the fallback that answered is the real observation and may settle; a
    lead that timed out with no answer may settle only its failure, never verified_success."""
    cortex = Cortex(clock=lambda: CLOCK)
    cortex.organs[FORMAL] = _TimedOut()
    receipt = run({"formal_model": FORMAL_MODEL, "declared": DECL}, "fallback", cortex=cortex)
    assert receipt["route"]["selected"] == [FORMAL]
    assert [a["organ_id"] for a in receipt["route"]["attempts"]] == [FORMAL]
    assert receipt["output"]["per_route"][0]["organ_id"] == CPSAT
    assert receipt["route"]["part_geometries"][CPSAT] == "constraint_feasibility"
    assert f"{CPSAT}|constraint_feasibility" in receipt["outcome_link"]["memory_keys"]
    ledger = CompetenceLedger()
    with pytest.raises(ValueError, match="produced no answer"):
        ledger.settle(receipt=receipt, method="cortex.formal.z3", method_version="0.2.0",
                      outcome_status="verified_success", provenance=OK_PROV, attribution=attr("cortex.formal.z3"))
    rec = ledger.settle(receipt=receipt, method="cortex.formal.z3", method_version="0.2.0",
                        outcome_status="observed_failure", provenance=OK_PROV, attribution=attr("cortex.formal.z3"))
    assert rec.competence_update["weight"] > 0
    rec = ledger.settle(receipt=receipt, method="cortex.optimization.cpsat", method_version="0.2.0",
                        outcome_status="verified_success", provenance=OK_PROV,
                        attribution=attr("cortex.optimization.cpsat"))
    assert rec.geometry == "constraint_feasibility" and rec.competence_update["weight"] > 0
    alternatives = {a["route"]: a["why_not"] for a in receipt["alternatives"]}
    assert all("not required" not in w for w in alternatives.get(FORMAL, []))


def test_a_superseded_schedule_lead_may_settle_its_failure_on_the_schedule_path_too():
    cortex = Cortex(clock=lambda: CLOCK)
    cortex.organs[FORMAL] = _TimedOut()
    receipt = run({"schedule_request": {"text": SCHEDULE_FEASIBLE}, "declared": DECL}, "sched-fallback", cortex=cortex)
    assert [a["organ_id"] for a in receipt["route"]["attempts"]] == [FORMAL]
    rec = CompetenceLedger().settle(receipt=receipt, method="cortex.formal.z3", method_version="0.2.0",
                                    outcome_status="observed_failure", provenance=OK_PROV,
                                    attribution=attr("cortex.formal.z3"))
    assert rec.geometry == "constraint_feasibility"
    assert [w for a in receipt["alternatives"] if a["route"] == FORMAL for w in a["why_not"]] == \
        ["ran (superseded by fallback); not the route that answered"]


def test_settlement_refuses_a_receipt_whose_content_address_does_not_match():
    receipt = run({"formal_model": FORMAL_MODEL, "declared": DECL}, "tamper")
    receipt["route"] = {**receipt["route"], "selected": [SEMANTIC], "part_geometries": {SEMANTIC: "causal"}}
    ledger = CompetenceLedger()
    with pytest.raises(ValueError, match="content address"):
        ledger.settle(receipt=receipt, method="cortex.semantic", method_version="0.1.0",
                      outcome_status="verified_success", provenance=OK_PROV, attribution=attr("cortex.semantic"))
    assert ledger.records() == []


def test_one_receipt_settles_a_method_once():
    receipt = run({"formal_model": FORMAL_MODEL, "declared": DECL}, "once")
    ledger = CompetenceLedger()
    ledger.settle(receipt=receipt, method="cortex.formal.z3", method_version="0.2.0",
                  outcome_status="verified_success", provenance=OK_PROV, attribution=attr("cortex.formal.z3"))
    for status in ("verified_success", "observed_failure"):
        with pytest.raises(ValueError, match="already settled"):
            ledger.settle(receipt=receipt, method="cortex.formal.z3", method_version="0.2.0",
                          outcome_status=status, provenance=OK_PROV, attribution=attr("cortex.formal.z3"))
    assert len(ledger.records()) == 1
    est = ledger.estimate("cortex.formal.z3", "0.2.0", receipt["geometry"]["epistemic_class"])
    assert est["weighted_outcomes"] < MIN_OUTCOME_EVIDENCE   # one observation cannot move a default


# ------------------------------------------------------------------ composed routes (D2) and the cap (D3)
def test_d2_composed_routes_settle_under_the_geometry_of_their_own_part():
    receipt = run({"formal_model": FORMAL_MODEL, "estimation_model": EST_MODEL, "declared": DECL}, "d2")
    assert receipt["route"]["composition"] is True
    assert receipt["route"]["part_geometries"] == {FORMAL: "constraint_feasibility", FERMI: "estimate"}
    assert receipt["outcome_link"]["memory_keys"] == [f"{FORMAL}|constraint_feasibility", f"{FERMI}|estimate"]
    ledger = CompetenceLedger()
    rec = ledger.settle(receipt=receipt, method="cortex.estimation.fermi", method_version="0.1.0",
                        outcome_status="verified_success", provenance=OK_PROV,
                        attribution=attr("cortex.estimation.fermi"))
    assert rec.geometry == "estimate"
    assert ledger.estimate("cortex.estimation.fermi", "0.1.0", "estimate")["weighted_outcomes"] > 0
    assert ledger.estimate("cortex.estimation.fermi", "0.1.0", "constraint_feasibility")["weighted_outcomes"] == 0


def test_d2_read_side_a_settled_composed_part_can_reorder():
    payload = {"formal_model": FORMAL_MODEL, "estimation_model": EST_MODEL, "declared": DECL}
    ledger = CompetenceLedger()
    for n in range(int(MIN_OUTCOME_EVIDENCE) + 1):
        receipt = run(payload, f"d2r-{n}")
        ledger.settle(receipt=receipt, method="cortex.estimation.fermi", method_version="0.1.0",
                      outcome_status="verified_success", provenance=OK_PROV,
                      attribution=attr("cortex.estimation.fermi"))
        ledger.settle(receipt=receipt, method="cortex.formal.z3", method_version="0.2.0",
                      outcome_status="observed_failure", provenance=OK_PROV, attribution=attr("cortex.formal.z3"))
    geometry = derive_geometry(Problem.from_dict({"problem_id": "d2r", "question": "q", "payload": payload}))
    parts = receipt["route"]["part_geometries"]
    assert ledger.reorder([FORMAL, FERMI], geometry, part_geometries=parts) == [FERMI, FORMAL]
    assert ledger.reorder([FORMAL, FERMI], geometry) == [FORMAL, FERMI]   # no part cells: no evidence, no change
    learned = run(payload, "d2r-learned", cortex=Cortex(clock=lambda: CLOCK, memory=ledger))
    assert learned["route"]["selected"] == [FERMI, FORMAL]
    assert sorted(learned["route"]["selected"]) == sorted(receipt["route"]["selected"])   # reordered, never added


def test_greg_conditional_memory_keeps_the_fixed_policy_across_part_geometries():
    from greg.cognition.conditional_competence import ConditionalCompetence
    memory = ConditionalCompetence([]).bind({"kind": "feasibility"})
    geometry = type("G", (), {"epistemic_class": "constraint_feasibility"})
    keys = [FORMAL, FERMI]
    assert memory.reorder(keys, geometry, part_geometries={FORMAL: "constraint_feasibility",
                                                            FERMI: "estimate"}) == keys


def test_d3_a_route_dropped_by_the_composition_cap_is_disclosed_not_denied():
    receipt = run({"formal_model": FORMAL_MODEL, "estimation_model": EST_MODEL, "sources": SOURCES,
                   "declared": DECL}, "d3")
    assert len(receipt["route"]["selected"]) == MAX_COMPOSITION
    assert receipt["route"]["dropped_by_cap"] == [SEMANTIC]
    why = next(a["why_not"] for a in receipt["alternatives"] if a["route"] == SEMANTIC)
    assert any("composition is capped" in w for w in why) and not any("not required" in w for w in why)
    assert receipt["coverage"].startswith("incomplete") and SEMANTIC in receipt["coverage"]
    complete = run({"formal_model": FORMAL_MODEL, "declared": DECL}, "d3b")
    assert complete["coverage"] == "complete" and complete["route"]["dropped_by_cap"] == []


def test_coverage_reports_a_selected_route_that_was_refused_before_execution():
    refused = run({"sources": [{"id": "S1", "text": "t"}], "resources": {"max_model_calls": 0}, "declared": DECL}, "d3c")
    assert refused["output"]["state"] == "BUDGET_EXHAUSTED" and refused["output"]["per_route"] == []
    assert refused["coverage"].startswith("none:") and SEMANTIC in refused["coverage"]


# ------------------------------------------------------------------ deficit typing (PRR-00/01/02)
@pytest.mark.parametrize("cls", ["prediction", "strategic", "estimate", "constraint_feasibility", "causal",
                                 "optimization"])
def test_a_known_class_without_its_input_is_missing_input_not_a_capability_gap(cls):
    r = run({"declared": {**DECL, "epistemic_class": cls}}, cls)
    assert [e["key"] for e in r["eligibility"] if e["eligible"]], "the seed registry has an eligible route"
    assert r["output"]["state"] == "INSUFFICIENT_EVIDENCE" and r["disposition"]["kind"] == "abstain"
    assert "none of their inputs" in r["disposition"]["reason"]
    assert r["capability_deficit"] is None


def test_a_part_whose_only_reader_is_withheld_is_a_capability_gap_not_missing_input():
    """Found while porting (present in the 0.1.6 source as well): the payload carries the input, so 'the
    payload carries none of their inputs' would be false. Its part is unanswered and the deficit names it."""
    registry = seed_registry()
    registry.withhold(SEMANTIC, "founder detach")
    r = run({"sources": SOURCES, "declared": DECL}, "withheld", registry=registry)
    assert r["output"]["state"] == "NO_ELIGIBLE_METHOD" and r["disposition"]["kind"] == "abstain"
    d = r["capability_deficit"]
    assert d["unanswered_parts"] == {SEMANTIC: "semantic"} and SEMANTIC in d["withheld_by_host"]
    assert "none of their inputs" not in r["disposition"]["reason"]


def test_a_part_with_no_eligible_route_is_unanswered_never_recommended_around():
    registry = seed_registry()
    registry.withhold(SEMANTIC, "founder detach")
    r = run({"formal_model": FORMAL_MODEL, "sources": SOURCES, "declared": DECL}, "unanswered", registry=registry)
    assert r["route"]["selected"] == [FORMAL]
    assert r["disposition"]["kind"] == "abstain" and r["output"]["state"] == "NO_ELIGIBLE_METHOD"
    assert SEMANTIC in r["coverage"] and r["coverage"].startswith("incomplete")
    d = r["capability_deficit"]
    assert d["geometry"] == "semantic" and d["unanswered_parts"] == {SEMANTIC: "semantic"}
    assert r["output"]["per_route"][0]["state"] == "OK"   # the answered part is still reported


def test_unknown_geometry_abstains_with_a_typed_unverified_deficit():
    r = run({}, "unknown")
    d = r["capability_deficit"]
    assert r["disposition"]["kind"] == "abstain"
    assert d["kind"] == "CapabilityDeficit" and d["state"] == "UNSUPPORTED_GEOMETRY" and d["geometry"] is None
    assert d["why"] == r["disposition"]["reason"] and d["verified"] is False
    assert "requests nothing" in d["authority"] and r["authority_created"] is False
    forged = copy.deepcopy(r)
    forged["capability_deficit"]["verified"] = True
    with pytest.raises(Exception):
        validate(forged, "cortex-receipt")


def test_a_protection_handoff_carries_no_deficit():
    protect = {"relevant": True, "required_actions": ["immediate_protection", "evidence_preservation", "escalation"],
               "evidence_access": "need_to_know", "disclosure_controls": ["no disclosure without consent"]}
    for declared in (DECL, {**DECL, "epistemic_class": "prediction"}):
        r = run({"victim_protection": protect, "declared": declared}, "protect")
        assert r["disposition"]["kind"] == "handoff"
        assert r["capability_deficit"] is None, "a handoff is not a capability gap"


# ------------------------------------------------------------------ inputs parsed before spending (PRR-05)
def _option(**kw):
    return {"option_id": "O1", "action_class": "draft.prepare", "target": "internal://drafts",
            "consequence_class": "internal_write", "reversibility": "reversible", "cost_usd": 0.0, "harm": {},
            "evidence_statuses": ["internally_observed"], "advantage": {"v": 1}, **kw}


class _Counting:
    def __init__(self, organ):
        self.organ, self.calls = organ, 0

    def run(self, *a, **k):
        self.calls += 1
        return self.organ.run(*a, **k)


def test_a_malformed_option_is_rejected_before_any_organ_runs():
    cortex = Cortex(clock=lambda: CLOCK)
    cortex.organs[FORMAL] = counting = _Counting(cortex.organs[FORMAL])
    r = run({"formal_model": FORMAL_MODEL, "options": [{"label": "no option_id"}], "declared": DECL}, "badopt",
            cortex=cortex)
    assert r["output"]["state"] == "MALFORMED_INPUT" and "option rejected" in r["disposition"]["reason"]
    assert counting.calls == 0, "the solver ran for a request that was then rejected"
    assert r["expenditure"]["solver_calls"] == 0 and r["route"]["selected"] == []


def test_a_malformed_authority_record_is_named_as_such_before_any_organ_runs():
    cortex = Cortex(clock=lambda: CLOCK)
    cortex.organs[FORMAL] = counting = _Counting(cortex.organs[FORMAL])
    receipt = cortex.run(
        {"problem_id": "badrec", "question": "q", "payload": {"formal_model": FORMAL_MODEL, "options": [_option()],
                                                              "declared": DECL}},
        records=[{"kind": "not_a_kind", "origin": "founder_signed", "body": {}}])
    validate(receipt, "cortex-receipt")
    assert "authority record rejected" in receipt["disposition"]["reason"]
    assert counting.calls == 0 and receipt["expenditure"]["solver_calls"] == 0


def test_a_record_rejected_after_the_organs_ran_reports_what_they_spent():
    bad_expiry = {"kind": "founder_mandate", "origin": "founder_signed", "body": {"scope": {
        "action_classes": ["draft.*"], "targets": ["internal://*"], "max_consequence_class": "internal_write",
        "expires_at": "2027-01-01T00:00:00"}}}   # no timezone: rejected only when the gate reads it
    receipt = Cortex(clock=lambda: CLOCK).run(
        {"problem_id": "late", "question": "q", "payload": {"formal_model": FORMAL_MODEL, "options": [_option()],
                                                            "as_of": "2026-10-21T00:00:00Z", "declared": DECL}},
        records=[bad_expiry])
    validate(receipt, "cortex-receipt")
    assert receipt["output"]["state"] == "MALFORMED_INPUT"
    assert receipt["route"]["selected"] == [FORMAL] and receipt["expenditure"]["solver_calls"] >= 1
    assert "ran" in receipt["coverage"] and "before any cognition was spent" not in \
        receipt["budget_controller"]["note"]


# ------------------------------------------------------------------ mandate expiry (D4) and the trusted instant
def _mandate(expires):
    return AuthorityRecord("m1", "founder_mandate", "founder_signed",
                           {"scope": {"action_classes": ["draft.*"], "targets": ["internal://*"],
                                      "max_consequence_class": "internal_write", "expires_at": expires}})


ALLOW = {"record_id": "p-O1", "kind": "policy_decision", "origin": "kernel_policy_engine",
         "body": {"subject": "O1", "verdict": "allow"}}


def test_d4_an_expiring_mandate_without_an_as_of_does_not_pass_founder_scope():
    allow = AuthorityRecord.from_dict(ALLOW)
    option = Option.from_dict(_option())
    without = evaluate_gates(option, [allow, _mandate("2020-01-01T00:00:00Z")], remaining_budget_usd=1.0, as_of=None)
    assert without.gates["founder_scope"].status == "FAIL" and "no as_of" in without.gates["founder_scope"].reason
    expired = evaluate_gates(option, [allow, _mandate("2020-01-01T00:00:00Z")], remaining_budget_usd=1.0,
                             as_of="2026-09-30T00:00:00Z")
    assert expired.gates["founder_scope"].status == "FAIL" and "expired" in expired.gates["founder_scope"].reason
    ok = evaluate_gates(option, [allow, _mandate("2030-01-01T00:00:00Z")], remaining_budget_usd=1.0,
                        as_of="2026-09-30T00:00:00Z")
    assert ok.gates["founder_scope"].status == "PASS"


# ------------------------------------------------------------------ the GREG bridge (PRR-16, PRR-11)
def _greg_request(payload, pid="t:ports", **kw):
    return {"problem_id": pid, "problem": {"question": "q", "payload": {"declared": DECL, **payload}}, **kw}


def test_check_receipt_refuses_more_model_calls_than_the_serving_ceiling():
    from cortex.contracts import digest as cortex_digest
    from greg.cognition import bridge
    _, problem, records = bridge._validate(_greg_request({"formal_model": FORMAL_MODEL}))
    receipt = bridge.run_worker(problem, records, withheld_organs={}, semantic_model=None, cpu_seconds=10,
                                created_at=CLOCK)
    assert bridge.check_receipt(receipt, max_model_calls=1) is receipt
    forged = copy.deepcopy(receipt)
    forged["expenditure"] = dict(forged["expenditure"], model_calls=2)
    forged["receipt_id"] = cortex_digest({k: v for k, v in forged.items() if k != "receipt_id"})
    bridge.check_receipt(forged)                       # without a ceiling the contract alone accepts it
    with pytest.raises(bridge.CognitionError, match="model calls"):
        bridge.check_receipt(forged, max_model_calls=1)


def test_a_worker_reporting_calls_above_the_ceiling_is_refused_on_the_path(monkeypatch):
    from cortex.contracts import digest as cortex_digest
    from greg.cognition import bridge
    from greg.cognition.cortex import reason, registry_view
    real = bridge.run_worker

    def overspent(*a, **k):
        r = real(*a, **k)
        r["expenditure"] = dict(r["expenditure"], model_calls=2)
        r["receipt_id"] = cortex_digest({key: v for key, v in r.items() if key != "receipt_id"})
        return r
    monkeypatch.setattr(bridge, "run_worker", overspent)
    r = reason(_greg_request({"formal_model": FORMAL_MODEL}), registry=registry_view())
    assert r["abstention_state"] == "ABSTAIN" and "model calls" in r["missing_information"][0]


def test_the_decision_instant_is_the_body_clock_unless_the_declaration_is_later():
    from datetime import datetime, timezone
    from greg.cognition.bridge import _decision_instant
    now = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
    expiring = [{"kind": "founder_mandate", "origin": "founder_signed",
                 "body": {"scope": {"expires_at": "2027-01-01T00:00:00Z"}}}]
    assert _decision_instant({}, [], now) is None
    assert _decision_instant({"as_of": "2019-06-01"}, [ALLOW], now) is None          # no expiring record
    assert _decision_instant({}, expiring, now) == "2026-10-21T12:00:00Z"
    assert _decision_instant({"as_of": "2019-06-01T00:00:00Z"}, expiring, now) == "2026-10-21T12:00:00Z"
    assert _decision_instant({"as_of": "2030-01-01T00:00:00Z"}, expiring, now) == "2030-01-01T00:00:00Z"
    assert _decision_instant({"as_of": "not a date"}, expiring, now) is None          # left for the cortex to reject


def test_a_declared_past_instant_cannot_keep_an_expired_mandate_alive_on_the_greg_path():
    from greg.cognition.cortex import reason, registry_view
    expired = {"record_id": "m-old", "kind": "founder_mandate", "origin": "founder_signed", "body": {"scope": {
        "action_classes": ["draft.*"], "targets": ["internal://*"], "max_consequence_class": "internal_write",
        "expires_at": "2020-01-01T00:00:00Z"}}}
    for as_of in ({"as_of": "2019-06-01T00:00:00Z"}, {}):
        r = reason(_greg_request({"options": [_option()], **as_of}, records=[ALLOW, expired]),
                   registry=registry_view(), trusted_clock=True)
        cortex_receipt = r["proof_artifact"]
        assert cortex_receipt["gates"]["O1"]["gates"]["founder_scope"]["status"] == "FAIL"
        assert cortex_receipt["disposition"]["kind"] != "recommend" and r["abstention_state"] != "NONE"
        assert any("body clock" in a for a in r["assumptions"])


def test_a_direct_caller_keeps_its_declared_instant_so_frozen_evaluations_never_read_the_wall_clock():
    """Evaluation runners call reason() directly with a frozen as_of; the body clock is a signed mission's only."""
    from greg.cognition.cortex import reason, registry_view
    current = {"record_id": "m-now", "kind": "founder_mandate", "origin": "founder_signed", "body": {"scope": {
        "action_classes": ["draft.*"], "targets": ["internal://*"], "max_consequence_class": "internal_write",
        "expires_at": "2026-12-31T00:00:00Z"}}}
    r = reason(_greg_request({"options": [_option()], "as_of": "2026-10-01T00:00:00Z"}, records=[ALLOW, current]),
               registry=registry_view())
    assert not any("body clock" in a for a in r["assumptions"])
    assert r["proof_artifact"]["gates"]["O1"]["gates"]["founder_scope"]["status"] == "PASS"


def test_the_signed_mission_adapter_decides_at_the_body_clock(monkeypatch):
    from types import SimpleNamespace
    from greg.cognition import bridge, cortex
    seen = []
    monkeypatch.setattr(cortex, "reason", lambda params, **kw: seen.append(bridge._SIGNED_PATH.get()) or {"ok": True})
    ctx = SimpleNamespace(manifest=SimpleNamespace(capability_id="cognition.solve"), target="cognition:x",
                          capability_registry=object(), journal=None, cognition_model=None, cognition_budget=None)
    cortex.solve(_greg_request({"options": [_option()]}), ctx)
    assert seen == [True] and bridge._SIGNED_PATH.get() is False      # scoped to the signed call only


# ------------------------------------------------------------------ the Competency Compiler (PRR-00, narrowed)
@pytest.mark.parametrize("geometry", ["estimate", "prediction", "optimization", "constraint_feasibility", "causal"])
def test_a_compile_request_with_no_inputs_asks_for_them_and_forms_nothing(geometry, tmp_path, monkeypatch):
    from greg.cognition import compiler
    from greg.cognition.cortex import reason, registry_view
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")
    r = reason({"problem_id": f"empty-{geometry}", "compile": {"geometry": {"geometry": geometry}, "data": {}}},
               registry=registry_view())
    assert r["state"] == "ABSTAIN" and r["capability_deficit"] is None
    assert r["missing_information"] and all(m["missing_inputs"] for m in r["missing_information"])


def test_a_request_whose_inputs_no_method_reads_is_still_a_genuine_gap(tmp_path, monkeypatch):
    """The narrowing: only an empty request is missing input. A new data shape stays a deficit for Genesis."""
    from greg.cognition import compiler
    from greg.cognition.cortex import reason, registry_view
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")
    r = reason({"problem_id": "fold", "compile": {"geometry": {"geometry": "optimization",
                                                               "subgeometry": "protein folding"},
                                                  "data": {"sequence": "ACDE"}}}, registry=registry_view())
    assert r["state"] == "CAPABILITY_DEFICIT" and r["capability_deficit"]["function"]


# ------------------------------------------------------------------ defects present in both lineages (verified 2026-10-21)
def test_a_cap_dropped_part_is_never_recommended_around():
    from cortex.examples import _DETER
    from cortex.routing import DETERRENCE
    deter_external = {**_DETER, "interventions": [{"id": "I_report", "kind": "report_to_authority", "cost_usd": 0,
                                                   "effects": {"p_sanction": {"set": 0.95},
                                                               "p_detect": {"set": 0.6}}}]}
    for dropped, payload in ((SEMANTIC, {"sources": SOURCES}), (DETERRENCE, {"deterrence_model": deter_external})):
        r = run({"formal_model": FORMAL_MODEL, "estimation_model": EST_MODEL, **payload, "declared": DECL}, "cap")
        assert r["route"]["dropped_by_cap"] == [dropped] and r["disposition"]["kind"] != "recommend"
        assert "BUDGET_EXHAUSTED" in r["outcome"]["reasons"] and r["capability_deficit"] is None
    order = ("recommend", "bounded_test", "handoff", "abstain")
    base = run({"formal_model": FORMAL_MODEL, "sources": SOURCES, "declared": DECL}, "two")["disposition"]["kind"]
    more = run({"formal_model": FORMAL_MODEL, "estimation_model": EST_MODEL, "sources": SOURCES, "declared": DECL},
               "three")["disposition"]["kind"]
    assert order.index(more) >= order.index(base), (base, more)   # adding a part never turns caution into advice


@pytest.mark.parametrize("record", [{"origin": "founder_signed", "body": {}},
                                    {"kind": "founder_mandate", "body": {}},
                                    {"kind": "founder_mandate", "origin": "founder_signed", "body": "ab"},
                                    "not a record"])
def test_a_malformed_record_is_a_malformed_record_receipt_never_an_exception(record):
    receipt = Cortex(clock=lambda: CLOCK).run(
        {"problem_id": "rec", "question": "q", "payload": {"options": [_option()], "declared": DECL}},
        records=[record])
    validate(receipt, "cortex-receipt")
    assert receipt["output"]["state"] == "MALFORMED_INPUT"
    assert receipt["disposition"]["reason"].startswith("malformed input: authority record rejected")


MANDATE_SCOPE = {"action_classes": ["draft.*"], "targets": ["internal://*"], "max_consequence_class": "internal_write"}


def _weighted(rid, expires, weights=None, scope=None):
    body = {"scope": {**(scope or MANDATE_SCOPE), "expires_at": expires}, **({"weights": weights} if weights else {})}
    return {"record_id": rid, "kind": "founder_mandate", "origin": "founder_signed", "body": body}


def _rank(records):
    options = [_option(option_id="FAST", advantage={"speed": 0.9, "safety": 0.2}),
               _option(option_id="SAFE", advantage={"speed": 0.2, "safety": 0.9})]
    policy = [{"record_id": f"pol-{o}", "kind": "policy_decision", "origin": "kernel_policy_engine",
               "body": {"subject": o, "verdict": "allow"}} for o in ("FAST", "SAFE")]
    return Cortex(clock=lambda: CLOCK).run({"problem_id": "weights", "question": "Which draft plan?", "payload": {
        "options": options, "as_of": CLOCK, "declared": DECL}}, records=records + policy)


def test_ranking_weights_come_only_from_a_mandate_founder_scope_accepted():
    expired = _weighted("m-expired", "2020-01-01T00:00:00Z", {"speed": 1.0})
    current = _weighted("m-current", "2030-01-01T00:00:00Z")
    current_safe = _weighted("m-safe", "2030-01-01T00:00:00Z", {"safety": 1.0})
    other_domain = _weighted("m-pay", "2030-01-01T00:00:00Z", {"speed": 1.0},
                             {"action_classes": ["payments.*"], "targets": ["bank://*"],
                              "max_consequence_class": "financial"})
    r = _rank([expired, current])
    assert r["gates"]["FAST"]["gates"]["founder_scope"]["basis"] == ["m-current"]
    assert r["ranking"]["chosen"] is None and r["disposition"]["kind"] != "recommend"
    assert _rank([expired, current_safe])["ranking"]["chosen"] == "SAFE"      # expired never overrides current
    assert _rank([current, other_domain])["ranking"]["chosen"] is None        # out of scope never decides
    assert _rank([current_safe])["ranking"]["chosen"] == "SAFE"               # control
    fast = _weighted("m-fast", "2030-01-01T00:00:00Z", {"speed": 1.0})
    assert _rank([fast, current_safe])["ranking"]["chosen"] is None           # conflicting accepted weights:
    assert _rank([current_safe, fast])["ranking"]["chosen"] is None           # list order never decides


def _treasury(option_harm, ceiling):
    from cortex.contracts import HARM_DIMENSIONS
    none = {d: "none" for d in HARM_DIMENSIONS}
    records = [{"kind": "policy_decision", "origin": "kernel_policy_engine",
                "body": {"subject": "pay", "action_class": "funds.transfer", "verdict": "allow"}},
               {"kind": "founder_mandate", "origin": "founder_signed",
                "body": {"scope": {"action_classes": ["funds.*"], "targets": ["internal://*"],
                                   "max_consequence_class": ceiling}}}]
    return Cortex(clock=lambda: CLOCK).run({"problem_id": "opt-harm", "question": "Move the reserve now?", "payload": {
        "declared": {**DECL, "harm": none}, "as_of": "2026-10-05",
        "options": [{"option_id": "pay", "action_class": "funds.transfer", "target": "internal://treasury",
                     "consequence_class": "internal_write", "reversibility": "reversible", "cost_usd": 0.0,
                     "harm": {**none, **option_harm}, "evidence_statuses": ["externally_verified"] * 2,
                     "advantage": {"speed": 1.0}}]}}, records=records)


def test_an_options_own_harm_raises_its_class_never_lowers_it():
    assert _treasury({"financial": "high"}, "internal_write")["disposition"]["kind"] != "recommend"
    handed = _treasury({"financial": "high"}, "financial")
    validate(handed, "cortex-receipt")
    assert handed["disposition"]["kind"] == "handoff"
    assert any(b.get("source") == "option_declared" and "implies at least financial" in b["why"]
               for b in handed["gates"]["pay"]["rejected_bases"])
    assert _treasury({}, "internal_write")["disposition"]["kind"] == "recommend"     # control


def test_an_engine_the_schedule_composition_ran_is_never_listed_as_not_required():
    from cortex.examples import SCHEDULE_WORDS
    r = run(SCHEDULE_WORDS["payload"], "words")
    ran = {p["organ_id"] for p in r["output"]["per_route"]}
    assert ran & set(r["route"]["selected"]) - {"cortex.extraction.schedule@0.1.0"}
    listed = {a["route"] for a in r["alternatives"]}
    assert not (listed & set(r["route"]["selected"])), "a selected route is also an alternative"


def test_a_class_whose_only_route_is_withheld_names_the_founder_attach_not_registration():
    registry = seed_registry()
    registry.withhold("cortex.evidence_causal@0.1.0", "founder detach")
    r = run({"declared": {**DECL, "epistemic_class": "prediction"}}, "withheld-class", registry=registry)
    assert r["output"]["state"] == "NO_ELIGIBLE_METHOD"
    assert "withheld" in r["disposition"]["reason"] and "attach" in r["disposition"]["next_step"]
    assert "register and validate" not in r["disposition"]["next_step"]
    assert r["capability_deficit"]["withheld_by_host"] == ["cortex.evidence_causal@0.1.0"]


# ------------------------------------------------------------------ evaluation integrity (PRR-07)
_LOADED = '''
import json, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
from cortex.evaluation import run as R


class Fake:
    def complete(self, system, user):
        return json.dumps({"ok": True}) if user == "{}" else json.dumps({"disposition": "abstain", "answer": None})


R.run("smoke", ["routed_seed", "always_abstain", "always_llm", "llm_committee"], client_factory=Fake)
R.learning_checks()
print(json.dumps(sorted({str(pathlib.Path(m.__file__).resolve().relative_to(root)) for m in list(sys.modules.values())
                         if getattr(m, "__file__", None)
                         and str(pathlib.Path(m.__file__).resolve()).startswith(str(root) + "/")})))
'''


def test_every_in_repo_module_a_scored_run_loads_is_frozen(tmp_path):
    """Run the scored path in a fresh interpreter (pytest has already imported half the repository) and check
    that every repository module it loaded is hashed by the freeze."""
    import json
    import subprocess
    import sys
    from pathlib import Path
    from cortex.evaluation import run as R
    script = tmp_path / "loaded.py"
    script.write_text(_LOADED)
    out = subprocess.run([sys.executable, "-I", str(script), str(Path(R.ROOT))], capture_output=True, text=True,
                         cwd=tmp_path, timeout=600)
    assert out.returncode == 0, out.stderr[-2000:]
    loaded = json.loads(out.stdout.strip().splitlines()[-1])
    assert len(loaded) > len(R.FROZEN_CODE) // 2, "the probe saw too little of the scored path to be meaningful"
    assert sorted(set(loaded) - set(R.FROZEN_CODE)) == []


def test_a_schedule_optimize_lead_is_keyed_and_settled_under_its_own_class():
    sched = {"schedule_request": {"text": "Shift: 10 hours. Job A takes 3 hours. Job B takes 4 hours. Job C takes 2 "
                                          "hours. A before C. One machine; one job at a time. Minimize total "
                                          "completion time."}, "declared": DECL}
    r = run(sched, "sched-opt")
    lead = r["route"]["formal_plan"]["order"][0]
    assert r["route"]["formal_plan"]["query_kind"] == "optimize" and lead in r["route"]["selected"]
    assert r["route"]["part_geometries"][lead] == "optimization"
    assert f"{lead}|optimization" in r["outcome_link"]["memory_keys"]
    method, _, version = lead.partition("@")
    rec = CompetenceLedger().settle(receipt=r, method=method, method_version=version, outcome_status="observed_failure",
                                    provenance=OK_PROV, attribution=attr(method))
    assert rec.geometry == "optimization"


def test_a_resolved_class_with_no_runnable_route_is_never_an_unknown_geometry():
    from dataclasses import replace as _replace
    from cortex.genome import IntelligenceGenome, IntelligenceRegistry
    seed, registry = seed_registry(), IntelligenceRegistry()
    for k in seed.keys():
        g = seed.get(k)
        if g.profile.role == "solver":
            g = IntelligenceGenome(g.capability, _replace(g.profile, enabled=False, lifecycle="SPECIFIED"))
        registry.register(g)
    r = run({"declared": {**DECL, "epistemic_class": "prediction"},
             "claim": {"type": "prediction", "statement": "x rises", "evidence": []}}, "all-off", registry=registry)
    assert r["geometry"]["epistemic_class"] == "prediction"
    assert r["output"]["state"] == "NO_ELIGIBLE_METHOD" and "UNKNOWN_GEOMETRY" not in r["outcome"]["reasons"]


def test_a_reported_run_that_loads_unfrozen_code_cannot_report_a_verdict(monkeypatch, tmp_path):
    import json
    from cortex.evaluation import run as R
    manifest = tmp_path / "freeze.json"
    manifest.write_text(json.dumps({"inputs": R.freeze_inputs(), "frozen_at": "2026-10-21T00:00:00Z"}))
    monkeypatch.setattr(R, "MANIFEST", manifest)
    monkeypatch.setattr(R, "unfrozen_code_loaded", lambda: ["egregore/local_model.py"])
    out = R.run("heldout", ["routed_seed", "always_abstain"])
    assert out["unfrozen_code_loaded"] == ["egregore/local_model.py"]
    assert out["exit"]["verdict"] == "INCONCLUSIVE" and out["exit"]["promote"] is False



# ------------------------------------------------------------------ adversarial review of the port (2026-10-21)
@pytest.mark.parametrize("body,rid", [({"weights": [1, 2]}, None), ({"weights": 5}, None), ({"weights": "speed"}, None),
                                      ({"weights": {"speed": "fast"}}, None), ({"weights": {"speed": True}}, None),
                                      ({}, ["m-1"]), ({}, {"id": "m-1"})])
def test_a_mandate_with_malformed_weights_or_id_is_a_rejected_record_never_an_exception(body, rid):
    mandate = {"kind": "founder_mandate", "origin": "founder_signed",
               "body": {"scope": {**MANDATE_SCOPE, "expires_at": "2030-01-01T00:00:00Z"}, **body}}
    if rid is not None:
        mandate["record_id"] = rid
    r = _rank([mandate])
    assert r["output"]["state"] == "MALFORMED_INPUT"
    assert r["disposition"]["reason"].startswith("malformed input: authority record rejected")


@pytest.mark.parametrize("body", [{"scope": None}, {"scope": ["internal://*"]}, {"purposes": None},
                                  {"purposes": "draft.*"}])
def test_a_record_with_a_malformed_scope_or_purposes_is_rejected_as_a_record(body):
    r = _rank([{"kind": "founder_mandate", "origin": "founder_signed", "body": body}])
    assert r["output"]["state"] == "MALFORMED_INPUT"


def test_a_dominated_option_under_another_authority_does_not_remove_the_founders_weights():
    def plan(oid, target, advantage):
        return {"option_id": oid, "action_class": "draft.plan", "target": target, "consequence_class": "internal_write",
                "reversibility": "reversible", "cost_usd": 0, "evidence_statuses": ["externally_verified"],
                "advantage": advantage}
    founder = {"record_id": "m-founder", "kind": "founder_mandate", "origin": "founder_signed",
               "body": {"scope": {**MANDATE_SCOPE, "targets": ["internal://plans/*"]},
                        "weights": {"speed": 1.0, "safety": 0.2}}}
    grant = {"record_id": "g-ops", "kind": "capability_grant", "origin": "kernel_grant_issuer",
             "body": {"scope": {**MANDATE_SCOPE, "targets": ["internal://ops/*"]}}}
    fast, safe = plan("FAST", "internal://plans/fast", {"speed": 0.9, "safety": 0.2}), \
        plan("SAFE", "internal://plans/safe", {"speed": 0.2, "safety": 0.9})
    slow = plan("SLOW", "internal://ops/slow", {"speed": 0.1, "safety": 0.1})     # dominated, never choosable
    policy = [{"record_id": f"pol-{o}", "kind": "policy_decision", "origin": "kernel_policy_engine",
               "body": {"subject": o, "verdict": "allow"}} for o in ("FAST", "SAFE", "SLOW")]
    for opts, recs in (([fast, safe], [founder]), ([fast, safe, slow], [founder, grant])):
        r = Cortex(clock=lambda: CLOCK).run({"problem_id": "iia", "question": "Which plan?", "payload": {
            "options": opts, "as_of": CLOCK, "declared": DECL}}, records=recs + policy)
        assert r["ranking"]["front"] == ["FAST", "SAFE"]
        assert r["ranking"]["chosen"] == "FAST" and r["disposition"]["kind"] == "recommend", r["ranking"]


def _withheld(*keys):
    registry = seed_registry()
    for key in keys:
        registry.withhold(key, "founder detach")
    return registry


def test_a_schedule_whose_formal_engines_are_all_withheld_is_unanswered_not_recommended():
    r = run({"schedule_request": {"text": SCHEDULE_FEASIBLE + " Minimize total completion time.",
                                  "availability_evidence": "roster"}, "declared": DECL},
            "sched-withheld", registry=_withheld(FORMAL, CPSAT))
    assert r["disposition"]["kind"] == "abstain" and r["output"]["state"] == "NO_ELIGIBLE_METHOD"
    assert r["output"]["answer"] is None and r["coverage"].startswith("incomplete")
    assert {FORMAL, CPSAT} <= set(r["capability_deficit"]["withheld_by_host"])
    assert r["outcome"]["outcome"] != "ANSWERED_WITHIN_SCOPE"


def test_a_deficit_over_several_unanswered_parts_names_every_parts_withheld_family():
    r = run({"formal_model": FORMAL_MODEL, "sources": SOURCES, "declared": DECL}, "multi",
            registry=_withheld(FORMAL, CPSAT, SEMANTIC))
    deficit = r["capability_deficit"]
    assert deficit["unanswered_parts"] == {FORMAL: "constraint_feasibility", SEMANTIC: "semantic"}
    assert {FORMAL, CPSAT, SEMANTIC} <= set(deficit["withheld_by_host"])
    assert "semantic" in r["disposition"]["reason"]


class _Model:
    def __init__(self):
        self.calls = 0

    def complete(self, system, user):
        self.calls += 1
        raise OSError("no server")


def test_the_extractors_model_call_is_planned_before_any_organ_spends():
    from cortex.organs.schedule_extraction import ScheduleExtractionOrgan
    from cortex.organs.semantic import SemanticOrgan
    model = _Model()
    cortex = Cortex(clock=lambda: CLOCK)
    cortex.organs[cortex_routing.EXTRACT] = ScheduleExtractionOrgan(client=model)
    cortex.organs[SEMANTIC] = SemanticOrgan(client=model)
    free = {"schedule_request": {"text": "Please fit the welding and the painting into tomorrow, painting after "
                                         "welding."}, "sources": SOURCES, "declared": DECL,
            "resources": {"max_model_calls": 1}}
    r = run(free, "plan-calls", cortex=cortex)
    assert r["output"]["state"] == "BUDGET_EXHAUSTED" and model.calls == 0
    assert r["expenditure"]["model_calls"] == 0
    controlled = {**free, "schedule_request": {"text": SCHEDULE_FEASIBLE}}
    assert run(controlled, "plan-ok", cortex=cortex)["output"]["state"] != "BUDGET_EXHAUSTED"


def test_the_authority_instant_judges_expiry_and_the_payload_as_of_still_dates_the_question():
    allow = {**ALLOW}
    current = _weighted("m-cur", "2027-01-01T00:00:00Z")
    payload = {"options": [_option()], "as_of": "2026-09-15T00:00:00Z", "declared": DECL,
               "claim": {"id": "C", "type": "factual_support", "statement": "the shipment arrived"},
               "evidence": [{"id": "E1", "kind": "measurement", "validation_status": "externally_verified",
                             "observed_at": "2026-09-01", "max_age_days": 30, "stance": "supports",
                             "observation": "direct_observation", "source": "dock log"}]}
    direct = Cortex(clock=lambda: CLOCK).run({"problem_id": "inst", "question": "q", "payload": payload},
                                             records=[allow, current])
    signed = Cortex(clock=lambda: CLOCK).run({"problem_id": "inst", "question": "q", "payload": payload},
                                             records=[allow, current], authority_as_of="2026-10-21T00:00:00Z")
    assert signed["authority_as_of"] == "2026-10-21T00:00:00Z" and "authority_as_of" not in direct
    validate(signed, "cortex-receipt")
    # the question is unchanged: evidence fresh at the declared as_of stays fresh (it is stale at the body clock)
    assert signed["output"]["answer"] == direct["output"]["answer"]
    assert [(r["state"], r["answer"]) for r in signed["output"]["per_route"]] == \
        [(r["state"], r["answer"]) for r in direct["output"]["per_route"]]
    assert direct["output"]["per_route"][0]["answer"]["verdict"] == "supported"
    expired = _weighted("m-old", "2026-10-01T00:00:00Z")
    late = Cortex(clock=lambda: CLOCK).run({"problem_id": "inst", "question": "q", "payload": payload},
                                           records=[allow, expired], authority_as_of="2026-10-21T00:00:00Z")
    assert late["gates"]["O1"]["gates"]["founder_scope"]["status"] == "FAIL"
    early = Cortex(clock=lambda: CLOCK).run({"problem_id": "inst", "question": "q", "payload": payload},
                                            records=[allow, expired])
    assert early["gates"]["O1"]["gates"]["founder_scope"]["status"] == "PASS"


def test_unfrozen_code_ignores_dependencies_installed_inside_the_checkout(monkeypatch):
    import sys
    import types
    from cortex.evaluation import run as R
    fake = types.ModuleType("z3_in_venv")
    fake.__file__ = str(R.ROOT / ".venv" / "lib" / "python3.13" / "site-packages" / "z3" / "__init__.py")
    own = types.ModuleType("unfrozen_probe")
    own.__file__ = str(R.ROOT / "cortex" / "unfrozen_probe.py")
    monkeypatch.setitem(sys.modules, "z3_in_venv", fake)
    monkeypatch.setitem(sys.modules, "unfrozen_probe", own)
    loaded = R.unfrozen_code_loaded()
    assert "cortex/unfrozen_probe.py" in loaded
    assert not any(".venv" in p or "site-packages" in p for p in loaded)


def test_the_unfrozen_guard_keeps_the_verdict_it_replaced(monkeypatch, tmp_path):
    import json
    from cortex.evaluation import run as R
    manifest = tmp_path / "freeze.json"
    manifest.write_text(json.dumps({"inputs": R.freeze_inputs(), "frozen_at": "2026-10-21T00:00:00Z"}))
    monkeypatch.setattr(R, "MANIFEST", manifest)
    monkeypatch.setattr(R, "unfrozen_code_loaded", lambda: ["egregore/local_model.py"])
    out = R.run("heldout", ["routed_seed", "always_abstain", "always_llm"])
    before = out["exit"]["before_unfrozen_guard"]
    assert any("always_llm not run" in r for r in before["reasons"])       # the real reasons are kept
    assert set(before["reasons"]) <= set(out["exit"]["reasons"]) and out["exit"]["verdict"] == "INCONCLUSIVE"


class _Garbled:
    """A model that answers every item; its first reply is not JSON."""
    def __init__(self):
        self.n = 0

    def complete(self, system, user):
        import json
        if user == "{}":
            return json.dumps({"ok": True})
        self.n += 1
        return "Sure! {disposition: recommend}" if self.n == 1 else json.dumps({"disposition": "abstain",
                                                                                  "answer": None})


def test_a_malformed_reply_is_a_scored_failure_not_an_unrun_baseline():
    from cortex.evaluation import run as R
    out = R.run("smoke", ["routed_seed", "always_llm"], client_factory=_Garbled)
    arm = out["arms"]["always_llm"]
    assert arm["status"] == "RUN" and arm["summary"]["errors"] == 0
    assert not any("always_llm not run" in r for r in out["exit"]["reasons"])
    assert any(i["disposition"] == "malformed" and i["score"] == 0.0 for i in arm["items"])


class _DiesMidReply:
    """Answers the probe, then the server dies inside every call (a truncated body raises a non-OSError)."""
    def complete(self, system, user):
        import json
        from egregore.contracts import ContractError
        if user == "{}":
            return json.dumps({"ok": True})
        raise ContractError("invalid local model completion")


def test_a_model_that_dies_inside_the_call_is_unreached_in_both_runners(monkeypatch):
    from cortex.evaluation import crossgeo, crossgeo_arms
    from cortex.evaluation import run as R
    out = R.run("smoke", ["routed_seed", "always_llm"], client_factory=_DiesMidReply)
    assert out["arms"]["always_llm"]["summary"]["errors"] == out["arms"]["always_llm"]["summary"]["n"]
    assert any("always_llm not run" in r for r in out["exit"]["reasons"])
    monkeypatch.setattr(crossgeo_arms, "model_probe", lambda: (_DiesMidReply(), None))
    part = crossgeo.run_partition("dev", ("routed_greg", "always_llm"))
    assert part["arms"]["always_llm"]["status"] == "INCOMPLETE"
    assert "always_llm" not in part["rows"] and part["incomplete_rows"]["always_llm"]
    reported = crossgeo.report(part, part)
    assert reported["heldout"]["incomplete_rows"]["always_llm"] == part["incomplete_rows"]["always_llm"]
