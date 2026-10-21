"""Cortex 0.1.6: the named Epistemic Finality Rule and the typed CapabilityDeficit.

The finality rule says which kind of organ may decide which kind of claim; every
receipt cites it. A CapabilityDeficit is what an abstaining receipt hands to
capability formation: a typed request that names the gap and creates no
authority. Both are review-pass items (pass 2 §2, pass 1 §32, the build list's
"hooks for later cognition classes")."""
from __future__ import annotations

import pytest

from cortex.contracts import EPISTEMIC_CLASSES, HUMAN_AUTHORITY_CLASSES
from cortex.routing import FINALITY_RULE, Cortex, _jurisdiction
from cortex.schemas import validate

try:
    import z3  # noqa: F401
    HAVE_Z3 = True
except ModuleNotFoundError:
    HAVE_Z3 = False
needs_z3 = pytest.mark.skipif(not HAVE_Z3, reason="z3-solver not installed (see requirements-cortex.txt)")

DECL = {"consequence_class": "internal_write", "reversibility": "reversible"}
FORMAL_MODEL = {"requirement": "x + y <= 4",
                "variables": [{"name": "x", "sort": "int", "lo": 0, "hi": 4},
                              {"name": "y", "sort": "int", "lo": 0, "hi": 4}],
                "obligations": [{"id": "R1", "text": "x + y at most 4"}],
                "constraints": [{"id": "C1", "covers": ["R1"], "expr": ["<=", ["+", "x", "y"], 4]}]}
EST_MODEL = {"target": {"name": "c", "unit": "USD/week"}, "expression": ["*", "h", "r"],
             "variables": [{"name": "h", "unit": "hour/week", "low": 30, "high": 50},
                           {"name": "r", "unit": "USD/hour", "low": 40, "high": 60}]}


def run(payload, pid="p"):
    receipt = Cortex(clock=lambda: "2026-10-13T00:00:00Z").run({"problem_id": pid, "question": "q", "payload": payload})
    validate(receipt, "cortex-receipt")
    return receipt


# ------------------------------------------------------------------ the rule itself
def test_every_epistemic_class_has_exactly_one_jurisdiction():
    seen = [c for classes in FINALITY_RULE["jurisdictions"].values() for c in classes]
    assert sorted(seen) == sorted(EPISTEMIC_CLASSES)
    assert len(seen) == len(set(seen))
    assert _jurisdiction(None) == "none"


def test_human_authority_jurisdiction_is_the_single_kernel_constant():
    assert FINALITY_RULE["jurisdictions"]["human_authority"] == HUMAN_AUTHORITY_CLASSES


def test_the_rule_is_versioned_and_states_precedence_and_disagreement():
    assert FINALITY_RULE["version"] == "epistemic-finality/0.1"
    assert len(FINALITY_RULE["precedence"]) == 6
    assert "most cautious" in FINALITY_RULE["disagreement"]
    assert any("CapabilityDeficit" in line for line in FINALITY_RULE["precedence"])


# ------------------------------------------------------------------ receipts cite it
@needs_z3
def test_a_formal_receipt_is_decided_by_the_formal_jurisdiction():
    r = run({"formal_model": FORMAL_MODEL, "declared": DECL})
    fin = r["route"]["finality"]
    assert fin["rule"] == FINALITY_RULE["version"]
    assert fin["decides"] == "formal"
    assert fin["by_route"] == {"cortex.formal.z3@0.2.0": "formal"}
    assert r["capability_deficit"] is None


@needs_z3
def test_a_composed_receipt_is_decided_part_by_part_never_promoted_to_the_whole():
    r = run({"formal_model": FORMAL_MODEL, "estimation_model": EST_MODEL, "declared": DECL})
    fin = r["route"]["finality"]
    assert fin["by_route"] == {"cortex.formal.z3@0.2.0": "formal", "cortex.estimation.fermi@0.1.0": "empirical"}
    assert fin["decides"] == "per_route"


def test_human_authority_classes_are_handed_off_whatever_the_routes():
    for cls in HUMAN_AUTHORITY_CLASSES:
        r = run({"declared": {**DECL, "epistemic_class": cls}}, pid=cls)
        assert r["route"]["finality"]["decides"] == "human_authority"
        assert r["disposition"]["kind"] == "handoff"
        assert r["capability_deficit"] is None, "a handoff is not a capability gap"


# ------------------------------------------------------------------ the deficit
def test_unknown_geometry_abstains_with_a_typed_deficit():
    r = run({})
    assert r["disposition"]["kind"] == "abstain"
    d = r["capability_deficit"]
    assert d["kind"] == "CapabilityDeficit" and d["state"] == "UNSUPPORTED_GEOMETRY"
    assert d["geometry"] is None and d["jurisdiction"] == "none"
    assert d["why"] == r["disposition"]["reason"]
    assert r["route"]["finality"]["decides"] == "none"


def _registry_with_disabled(*keys):
    """The seed registry with the named organs disabled through the public registration API."""
    from dataclasses import replace as _replace
    from cortex.genome import IntelligenceGenome, IntelligenceRegistry, seed_registry
    seed, reg = seed_registry(), IntelligenceRegistry()
    for k in seed.keys():
        g = seed.get(k)
        if k in keys:
            g = IntelligenceGenome(g.capability, _replace(g.profile, enabled=False, lifecycle="SPECIFIED"))
        reg.register(g)
    return reg


def run_with(registry, payload, pid="p"):
    receipt = Cortex(registry=registry, clock=lambda: "2026-10-13T00:00:00Z").run(
        {"problem_id": pid, "question": "q", "payload": payload})
    validate(receipt, "cortex-receipt")
    return receipt


@pytest.mark.parametrize("cls", ["prediction", "strategic", "estimate", "constraint_feasibility"])
def test_a_known_class_without_its_input_is_missing_input_not_a_capability_gap(cls):
    # Review finding (pre-run, 0.1.6): an eligible route exists, the payload just lacks its input.
    r = run({"declared": {**DECL, "epistemic_class": cls}}, pid=cls)
    eligible = [e["key"] for e in r["eligibility"] if e["eligible"]]
    assert eligible, "the seed registry has an eligible route for this class"
    assert r["output"]["state"] == "INSUFFICIENT_EVIDENCE" and r["disposition"]["kind"] == "abstain"
    assert "none of their inputs" in r["disposition"]["reason"]
    assert r["capability_deficit"] is None


def test_a_class_whose_only_route_is_disabled_names_the_gap_and_the_disabled_families():
    reg = _registry_with_disabled("cortex.evidence_causal@0.1.0")
    r = run_with(reg, {"declared": {**DECL, "epistemic_class": "prediction"}})
    d = r["capability_deficit"]
    assert r["output"]["state"] == d["state"] == "NO_ELIGIBLE_METHOD"
    assert d["geometry"] == "prediction" and d["jurisdiction"] == _jurisdiction("prediction")
    assert d["why"] == r["disposition"]["reason"] == "no enabled route supports prediction"
    assert "cortex.evidence_causal@0.1.0" in d["registered_but_disabled"]
    assert "cortex.probabilistic.bayes@0.1.0" in d["registered_but_disabled"]   # reserved family, from the registry
    assert d["resolution_order"][0] == "existing capability" and d["resolution_order"][-1] == "new architecture"


@needs_z3
def test_a_part_with_no_eligible_route_is_unanswered_never_recommended_around():
    reg = _registry_with_disabled("cortex.semantic@0.1.0")
    r = run_with(reg, {"formal_model": FORMAL_MODEL, "sources": [{"id": "S1", "text": "The shift is ten hours."}],
                       "declared": DECL})
    assert r["route"]["selected"] == ["cortex.formal.z3@0.2.0"]
    assert r["disposition"]["kind"] == "abstain" and r["output"]["state"] == "NO_ELIGIBLE_METHOD"
    assert "cortex.semantic@0.1.0" in r["coverage"] and r["coverage"].startswith("incomplete")
    assert r["route"]["finality"]["by_route"] == {"cortex.formal.z3@0.2.0": "formal"}   # only what ran decides
    d = r["capability_deficit"]
    assert d["geometry"] == "semantic" and d["unanswered_parts"] == {"cortex.semantic@0.1.0": "semantic"}
    assert r["output"]["per_route"][0]["state"] == "OK"   # the answered part is still reported


def test_a_protection_handoff_carries_no_deficit():
    protect = {"relevant": True, "required_actions": ["immediate_protection", "evidence_preservation", "escalation"],
               "evidence_access": "need_to_know", "disclosure_controls": ["no disclosure without consent"]}
    for declared in (DECL, {**DECL, "epistemic_class": "prediction"}):
        r = run({"victim_protection": protect, "declared": declared})
        assert r["disposition"]["kind"] == "handoff"
        assert r["capability_deficit"] is None, "a handoff is not a capability gap"


@needs_z3
def test_an_option_rejected_after_routing_is_rejected_before_any_organ_runs():
    r = run({"formal_model": FORMAL_MODEL, "options": [{"label": "no option_id"}], "declared": DECL})
    assert r["output"]["state"] == "MALFORMED_INPUT"
    assert r["expenditure"]["solver_calls"] == 0 and r["route"]["selected"] == []


def test_a_deficit_requests_formation_and_never_authorizes_it():
    d = run({})["capability_deficit"]
    assert "requests nothing" in d["authority"] and "consequence authority" in d["authority"]
    r = run({"declared": {**DECL, "epistemic_class": "prediction"}})
    assert r["authority_created"] is False and r["execution_authority"] == "none"


def test_one_receipt_never_verifies_a_deficit():
    d = run({})["capability_deficit"]
    assert d["verified"] is False
    assert "recurrence across recorded cycles" in d["verification"]
    r = run({})
    r["capability_deficit"] = {**r["capability_deficit"], "verified": True}
    with pytest.raises(Exception):
        validate(r, "cortex-receipt")


def test_malformed_input_carries_the_rule_and_no_deficit():
    r = Cortex(clock=lambda: "2026-10-13T00:00:00Z").run({"problem_id": "m", "question": "q", "payload": "nope"})
    validate(r, "cortex-receipt")
    assert r["output"]["state"] == "MALFORMED_INPUT"
    assert r["route"]["finality"]["rule"] == FINALITY_RULE["version"]
    assert r["capability_deficit"] is None, "a malformed input is the caller's defect, not a capability gap"


def test_schema_rejects_a_deficit_that_is_not_typed():
    r = run({})
    r["capability_deficit"] = {**r["capability_deficit"], "kind": "Wish"}
    with pytest.raises(Exception):
        validate(r, "cortex-receipt")
    r = run({})
    del r["route"]["finality"]
    with pytest.raises(Exception):
        validate(r, "cortex-receipt")
