"""Cortex 0.1.6: four defects found by an independent read of the 0.1.5 code,
each reproduced before it was fixed. The reproductions stay as regression tests."""
from __future__ import annotations

import pytest

from cortex.contracts import CORTEX_VERSION
from cortex.gates import AuthorityRecord, Option, evaluate_gates
from cortex.memory import CompetenceLedger
from cortex.routing import FERMI, FORMAL, MAX_COMPOSITION, SEMANTIC, Cortex
from cortex.schemas import validate

try:
    import z3  # noqa: F401
    HAVE_Z3 = True
except ModuleNotFoundError:
    HAVE_Z3 = False
needs_z3 = pytest.mark.skipif(not HAVE_Z3, reason="z3-solver not installed (see requirements-cortex.txt)")

DECL = {"consequence_class": "internal_write", "reversibility": "reversible"}
FORMAL_MODEL = {"requirement": "x + y <= 4",
                "variables": [{"name": "x", "sort": "int", "lo": 0, "hi": 4}, {"name": "y", "sort": "int", "lo": 0, "hi": 4}],
                "obligations": [{"id": "R1", "text": "x + y at most 4"}],
                "constraints": [{"id": "C1", "covers": ["R1"], "expr": ["<=", ["+", "x", "y"], 4]}]}
EST_MODEL = {"target": {"name": "c", "unit": "USD/week"}, "expression": ["*", "h", "r"],
             "variables": [{"name": "h", "unit": "hour/week", "low": 30, "high": 50},
                           {"name": "r", "unit": "USD/hour", "low": 40, "high": 60}]}
SOURCES = [{"id": "S1", "text": "The shift is ten hours long."}]


def cortex():
    return Cortex(clock=lambda: "2026-10-13T00:00:00Z")


@needs_z3
def test_d1_settlement_requires_the_exact_method_and_version_that_ran():
    receipt = cortex().run({"problem_id": "d1", "question": "q", "payload": {"formal_model": FORMAL_MODEL, "declared": DECL}})
    ledger = CompetenceLedger()
    provenance = {"kind": "external_observation", "validation_status": "externally_verified"}
    attribution = [{"method": "cortex.formal.z3", "role": "final_answer", "uncertainty": "low"}]
    with pytest.raises(ValueError, match="method and version it actually selected"):
        ledger.settle(receipt=receipt, method="cortex.formal.z3", method_version="9.9.9",
                      outcome_status="verified_success", provenance=provenance, attribution=attribution)
    assert ledger.records() == []
    rec = ledger.settle(receipt=receipt, method="cortex.formal.z3", method_version="0.2.0",
                        outcome_status="verified_success", provenance=provenance, attribution=attribution)
    assert rec.method_version == "0.2.0"


@needs_z3
def test_d2_composed_routes_settle_under_the_geometry_of_their_own_part():
    receipt = cortex().run({"problem_id": "d2", "question": "q", "payload": {
        "formal_model": FORMAL_MODEL, "estimation_model": EST_MODEL, "declared": DECL}})
    assert receipt["route"]["composition"] is True
    assert receipt["route"]["part_geometries"] == {FORMAL: "constraint_feasibility", FERMI: "estimate"}
    assert receipt["outcome_link"]["memory_keys"] == [f"{FORMAL}|constraint_feasibility", f"{FERMI}|estimate"]
    ledger = CompetenceLedger()
    rec = ledger.settle(receipt=receipt, method="cortex.estimation.fermi", method_version="0.1.0",
                        outcome_status="verified_success",
                        provenance={"kind": "external_observation", "validation_status": "externally_verified"},
                        attribution=[{"method": "cortex.estimation.fermi", "role": "final_answer", "uncertainty": "medium"}])
    assert rec.geometry == "estimate"
    assert ledger.estimate("cortex.estimation.fermi", "0.1.0", "estimate")["weighted_outcomes"] > 0
    assert ledger.estimate("cortex.estimation.fermi", "0.1.0", "constraint_feasibility")["weighted_outcomes"] == 0
    validate(receipt, "cortex-receipt")


@needs_z3
def test_d3_a_route_dropped_by_the_composition_cap_is_disclosed_not_denied():
    receipt = cortex().run({"problem_id": "d3", "question": "q", "payload": {
        "formal_model": FORMAL_MODEL, "estimation_model": EST_MODEL, "sources": SOURCES, "declared": DECL}})
    assert len(receipt["route"]["selected"]) == MAX_COMPOSITION
    assert receipt["route"]["dropped_by_cap"] == [SEMANTIC]
    why = next(a["why_not"] for a in receipt["alternatives"] if a["route"] == SEMANTIC)
    assert any("composition is capped" in w for w in why) and not any("not required" in w for w in why)
    assert receipt["coverage"].startswith("incomplete") and SEMANTIC in receipt["coverage"]
    validate(receipt, "cortex-receipt")
    complete = cortex().run({"problem_id": "d3b", "question": "q", "payload": {"formal_model": FORMAL_MODEL, "declared": DECL}})
    assert complete["coverage"] == "complete" and complete["route"]["dropped_by_cap"] == []


def test_d4_an_expiring_mandate_without_an_as_of_does_not_pass_founder_scope():
    mandate = AuthorityRecord("m1", "founder_mandate", "founder_signed",
                              {"scope": {"action_classes": ["draft.*"], "targets": ["internal://*"],
                                         "max_consequence_class": "internal_write", "expires_at": "2020-01-01T00:00:00Z"}})
    allow = AuthorityRecord("p-O1", "policy_decision", "kernel_policy_engine", {"subject": "O1", "verdict": "allow"})
    option = Option.from_dict({"option_id": "O1", "action_class": "draft.prepare", "target": "internal://drafts",
                               "consequence_class": "internal_write", "reversibility": "reversible", "cost_usd": 0.0,
                               "harm": {}, "evidence_statuses": ["internally_observed"], "advantage": {"v": 1}})
    without = evaluate_gates(option, [allow, mandate], remaining_budget_usd=1.0, as_of=None)
    assert without.gates["founder_scope"].status == "FAIL"
    assert "no as_of" in without.gates["founder_scope"].reason
    expired = evaluate_gates(option, [allow, mandate], remaining_budget_usd=1.0, as_of="2026-09-30T00:00:00Z")
    assert expired.gates["founder_scope"].status == "FAIL" and "expired" in expired.gates["founder_scope"].reason
    current = AuthorityRecord("m2", "founder_mandate", "founder_signed",
                              {"scope": {"action_classes": ["draft.*"], "targets": ["internal://*"],
                                         "max_consequence_class": "internal_write", "expires_at": "2030-01-01T00:00:00Z"}})
    ok = evaluate_gates(option, [allow, current], remaining_budget_usd=1.0, as_of="2026-09-30T00:00:00Z")
    assert ok.gates["founder_scope"].status == "PASS"


@needs_z3
def test_d5_declared_harm_raises_the_consequence_class_never_lowers_it():
    """Ported from the #143 lineage (its crossgeo v0.2 hard failure): a requester may not declare
    internal_write while declaring high physical harm and get a recommendation."""
    understated = cortex().run({"problem_id": "d5", "question": "q", "payload": {
        "formal_model": FORMAL_MODEL,
        "declared": {"consequence_class": "internal_write", "reversibility": "reversible", "harm": {"physical": "high"}}}})
    assert understated["geometry"]["consequence_class"] == "financial"
    assert understated["geometry"]["provenance"]["consequence_class"]["source"] == "raised_by_declared_harm"
    assert any(r["field"] == "consequence_class" for r in understated["geometry"]["rejected_proposals"])
    assert understated["disposition"]["kind"] == "handoff"
    validate(understated, "cortex-receipt")
    validate(understated["geometry"], "cortex-problem-geometry")
    overstated = cortex().run({"problem_id": "d5b", "question": "q", "payload": {
        "formal_model": FORMAL_MODEL,
        "declared": {"consequence_class": "financial", "reversibility": "reversible", "harm": {"physical": "none"}}}})
    assert overstated["geometry"]["consequence_class"] == "financial"   # never lowered


@needs_z3
def test_d2_read_side_a_settled_composed_part_can_reorder():
    """The reorder read side uses the same per-part cell that settle writes; before 0.1.6 the FERMI
    evidence of a formal+fermi composition was invisible to routing."""
    from cortex.memory import MIN_OUTCOME_EVIDENCE
    receipt = cortex().run({"problem_id": "d2r", "question": "q", "payload": {
        "formal_model": FORMAL_MODEL, "estimation_model": EST_MODEL, "declared": DECL}})
    ledger = CompetenceLedger()
    ok = {"kind": "external_observation", "validation_status": "externally_verified"}
    for _ in range(int(MIN_OUTCOME_EVIDENCE) + 1):
        ledger.settle(receipt=receipt, method="cortex.estimation.fermi", method_version="0.1.0",
                      outcome_status="verified_success", provenance=ok,
                      attribution=[{"method": "cortex.estimation.fermi", "role": "final_answer", "uncertainty": "low"}])
        ledger.settle(receipt=receipt, method="cortex.formal.z3", method_version="0.2.0",
                      outcome_status="observed_failure", provenance=ok,
                      attribution=[{"method": "cortex.formal.z3", "role": "final_answer", "uncertainty": "low"}])
    from cortex.routing import derive_geometry
    from cortex.contracts import Problem
    geometry = derive_geometry(Problem.from_dict({"problem_id": "d2r", "question": "q", "payload": {
        "formal_model": FORMAL_MODEL, "estimation_model": EST_MODEL, "declared": DECL}}))
    parts = receipt["route"]["part_geometries"]
    assert ledger.reorder([FORMAL, FERMI], geometry, part_geometries=parts) == [FERMI, FORMAL]
    assert ledger.reorder([FORMAL, FERMI], geometry) == [FORMAL, FERMI]   # without part cells: no evidence, no change
    learned = Cortex(clock=lambda: "2026-10-13T00:00:00Z", memory=ledger).run({"problem_id": "d2r2", "question": "q",
        "payload": {"formal_model": FORMAL_MODEL, "estimation_model": EST_MODEL, "declared": DECL}})
    assert learned["route"]["selected"] == [FERMI, FORMAL]
    assert sorted(learned["route"]["selected"]) == sorted(receipt["route"]["selected"])   # reordered, never added


@needs_z3
def test_d3_coverage_reports_a_selected_route_that_was_refused_before_execution():
    refused = cortex().run({"problem_id": "d3c", "question": "q", "payload": {
        "sources": [{"id": "S1", "text": "t"}], "resources": {"max_model_calls": 0}, "declared": DECL}})
    assert refused["output"]["state"] == "BUDGET_EXHAUSTED" and refused["output"]["per_route"] == []
    assert refused["coverage"].startswith("none:") and SEMANTIC in refused["coverage"]


def test_version_records_the_sixth_disclosed_change():
    assert CORTEX_VERSION == "0.1.6"
