"""Every arsenal status must be backed by checkable evidence.

FoundryComposer ranks technologies by status, so an unsupported status changes
composition decisions. These tests keep the label honest and the doctrine
document in sync with the registry.
"""
from dataclasses import replace
from pathlib import Path

from foundry.arsenal import ARSENAL
from foundry.arsenal_evidence import (
    TABLE_BEGIN, TABLE_END, Evidence, audit, load_evidence, render_table,
)

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "ASYMMETRIC_ADVANTAGE_ARSENAL.md"


def test_current_arsenal_has_no_unsupported_claims():
    assert audit() == []


def test_evidence_covers_exactly_the_55_technologies():
    assert set(load_evidence()) == set(range(1, 56))


def test_executable_without_kernel_code_is_refused():
    # The pre-audit label: Web servers were "executable" with no kernel server.
    arsenal = dict(ARSENAL)
    arsenal[31] = replace(ARSENAL[31], status="executable")
    problems = audit(arsenal=arsenal)
    assert any("technology 31" in p and "implementation path" in p for p in problems)
    assert any("technology 31" in p and "test path" in p for p in problems)


def test_partial_without_any_evidence_is_refused():
    arsenal = dict(ARSENAL)
    arsenal[40] = replace(ARSENAL[40], status="partial")
    assert any("technology 40" in p and "partial requires" in p for p in audit(arsenal=arsenal))


def test_fabricated_evidence_path_is_refused():
    evidence = load_evidence()
    evidence[5] = replace(evidence[5], implementation=("events/does_not_exist.py",))
    assert any("does_not_exist" in p for p in audit(evidence=evidence))


def test_target_with_kernel_evidence_must_be_reaudited():
    evidence = load_evidence()
    evidence[28] = replace(evidence[28], implementation=("events/spine.py",))
    assert any("technology 28" in p and "re-audit" in p for p in audit(evidence=evidence))


def test_missing_gap_or_adoption_route_is_refused():
    evidence = load_evidence()
    evidence[6] = Evidence(6, evidence[6].implementation, evidence[6].tests, (), "", ())
    problems = audit(evidence=evidence)
    assert any("gap is required" in p for p in problems)
    assert any("commodity mechanisms" in p for p in problems)


def test_doc_status_table_matches_registry():
    text = DOC.read_text(encoding="utf-8")
    start, end = text.index(TABLE_BEGIN), text.index(TABLE_END) + len(TABLE_END)
    assert text[start:end] == render_table(), (
        "regenerate with: python -m foundry.arsenal_evidence --table"
    )
