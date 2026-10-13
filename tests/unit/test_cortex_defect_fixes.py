"""Cortex 0.1.6: four defects found by an independent read of the 0.1.5 code,
each reproduced before it was fixed. The reproductions stay as regression tests."""
from __future__ import annotations

import pytest

from cortex.contracts import CORTEX_VERSION
from cortex.gates import AuthorityRecord, Option, evaluate_gates
from cortex.memory import CompetenceLedger
from cortex.routing import FERMI, FORMAL, MAX_COMPOSITION, SEMANTIC, Cortex
from cortex.schemas import validate

pytestmark = pytest.mark.skipif(pytest.importorskip("z3", reason="z3-solver not installed") is None, reason="z3")

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


def test_version_records_the_sixth_disclosed_change():
    assert CORTEX_VERSION == "0.1.6"
