"""Fail-closed checks for the cathedral source map and dual proof policy."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "docs" / "architecture"
SOURCE = ROOT / "docs" / "founder-sources" / "CATHEDRAL-MASTER-SOURCE-MANIFEST-2026-08-29.md"


def _load(name: str) -> dict:
    return json.loads((ARCH / name).read_text(encoding="utf-8"))


def test_crosswalk_covers_all_31_source_sections_and_is_not_canonical_registry():
    crosswalk = _load("cathedral-source-capability-crosswalk.json")

    assert crosswalk["does_not_replace_canonical_registry"] is True
    assert crosswalk["canonical_capability_registry"] == "blueprint/registry.py"
    assert crosswalk["artifact_kind"] == (
        "GENERATED_CROSSWALK_NOT_SOURCE_OR_CAPABILITY_REGISTRY"
    )

    covered = {
        section
        for entry in crosswalk["entries"]
        for section in entry["source_sections"]
    }
    assert covered == set(range(1, 32))


def test_current_reality_remains_zero_and_no_lifecycle_stage_auto_promotes():
    policy = _load("dual-proof-gates.json")
    reality = policy["current_reality"]

    assert reality["vdm_count"] == 0
    assert reality["cvo_count"] == 0
    assert reality["hardened_count"] == 0
    assert reality["whole_body_closure"] is False
    assert all(stage["automatic_promotion"] is False for stage in policy["lifecycle"])


def test_vdm_and_cvo_are_distinct_and_neither_creates_authority():
    policy = _load("dual-proof-gates.json")
    gates = {gate["gate_id"]: gate for gate in policy["gates"]}

    assert set(gates) == {"VDM", "CVO"}
    assert gates["VDM"]["creates_authority"] is False
    assert gates["CVO"]["creates_authority"] is False
    assert gates["VDM"]["may_create_external_consequence"] is False
    assert gates["CVO"]["may_create_external_consequence"] is True
    assert gates["CVO"]["requires_founder_live_graduation"] is True
    assert gates["CVO"]["prerequisite_stages"] == ["VDM"]


def test_vdm_requires_interruption_restart_lineage_and_independent_verification():
    policy = _load("dual-proof-gates.json")
    vdm = next(gate for gate in policy["gates"] if gate["gate_id"] == "VDM")
    assertions = set(vdm["required_assertions"])

    assert "deliberate_interruption_after_committed_progress" in assertions
    assert "exact_restart_from_committed_state" in assertions
    assert "no_duplicate_consequential_tasks" in assertions
    assert "complete_event_action_provenance_evaluator_and_dissent_lineage" in assertions
    assert "independent_verifier_pass_under_frozen_criteria" in assertions
    assert "successful_run_without_interruption" in vdm["forbidden_substitutes"]


def test_cvo_requires_real_changed_state_legal_operator_and_reconciliation():
    policy = _load("dual-proof-gates.json")
    cvo = next(gate for gate in policy["gates"] if gate["gate_id"] == "CVO")
    assertions = set(cvo["required_assertions"])

    assert "named_legal_operator_and_real_decision_actor" in assertions
    assert (
        "real_payment_permission_routing_contract_or_equivalent_state_change"
        in assertions
    )
    assert "named_external_verifier_independent_of_builder_and_operator" in assertions
    assert "uncertain_external_effect_reconciled_before_retry" in assertions
    assert "simulated_settlement" in cvo["forbidden_substitutes"]


def test_promotion_policy_blocks_self_judgment_authority_gain_and_gate_conflation():
    promotion = _load("dual-proof-gates.json")["promotion_policy"]

    assert promotion["builder_is_final_judge"] is False
    assert promotion["correlated_agents_are_independent_verifiers"] is False
    assert promotion["capability_gain_expands_authority"] is False
    assert promotion["pass_one_gate_implies_other_gate"] is False
    assert promotion["merge_implies_live_graduation"] is False
    assert promotion["static_workflow_wins_ties"] is True


def test_source_manifest_cannot_masquerade_as_verbatim_source():
    manifest = SOURCE.read_text(encoding="utf-8")
    normalized = " ".join(manifest.split())

    assert "not a byte-for-byte transcript" in normalized
    assert "authenticated conversation turn remains the verbatim source" in normalized
    assert "All 31 sections are mapped" in normalized
