"""WP-06 compare suite (SPEC-WP06 4.4): build_report + build_proposal.

The pre-registered matrix outcome is computed BY the machinery: stream rank 1
(best), chunk64 rank 2 (beaten), chunk256 rank 3 (below_threshold),
no_commit_stream rank 4 (not_measured). Plus threshold classification,
winner binding, determinism (same inputs -> byte-identical canonical content
modulo fresh ids), and fail-closed paths (no winner, unknown variant, missing
branch, zero baseline, bad direction).
"""
from __future__ import annotations

import pytest

from kernel.contracts.evolution import StrategyTree
from kernel.crypto.hashing import canonical_json
from kernel.evolution import CycleError, build_proposal, build_report
from kernel.evolution.audit_rules import parse_variant_config

from scripts.run_fast_cycle import make_generator, make_space

LOOP_ID = "f" * 32
MEASURED = {"stream": 1.0, "chunk64": 64.0, "chunk256": 256.0}


def make_inputs(measured=None):
    drafts = make_generator().generate(make_space())
    tree = StrategyTree(
        root_objective="test objective",
        horizon="wp06-test",
        selection_rule="test rule",
        branch_ids=[d.id for d in drafts],
        created_by="test",
    )
    spec_map = {d.id: d for d in drafts}
    return drafts, tree, spec_map, measured or dict(MEASURED)


def build(measured=None, **overrides):
    drafts, tree, spec_map, measured = make_inputs(measured)
    kwargs = dict(
        loop_id=LOOP_ID,
        tree=tree,
        spec_map=spec_map,
        measured=measured,
        baseline_value=1000.0,
        threshold=0.90,
        direction="decrease",
        metric_unit="rows",
    )
    kwargs.update(overrides)
    return drafts, build_report(**kwargs)


def test_preregistered_matrix_outcome_is_computed_by_the_machinery():
    drafts, report = build()
    variant_of = {d.id: parse_variant_config(d)["variant_id"] for d in drafts}
    entries = {e.variant_id: e for e in report.entries}
    assert entries["stream"].rank == 1
    assert entries["stream"].disposition == "best"
    assert entries["stream"].improvement_ratio == 0.999
    assert entries["chunk64"].rank == 2
    assert entries["chunk64"].disposition == "beaten"
    assert entries["chunk64"].improvement_ratio == 0.936
    assert entries["chunk256"].rank == 3
    assert entries["chunk256"].disposition == "below_threshold"
    assert entries["chunk256"].improvement_ratio == 0.744
    assert entries["no_commit_stream"].rank == 4
    assert entries["no_commit_stream"].disposition == "not_measured"
    assert entries["no_commit_stream"].measured_value == 1000.0
    assert entries["no_commit_stream"].improvement_ratio == 0.0
    assert report.winner_branch_id == entries["stream"].branch_id
    assert report.baseline_value == 1000.0
    assert report.metric_unit == "rows"
    assert report.loop_id == LOOP_ID


def test_beaten_vs_below_threshold_classification_boundary():
    # Exactly at threshold -> meets it (beaten); just below -> below_threshold.
    drafts, report = build({"stream": 1.0, "chunk64": 100.0, "chunk256": 100.0000001})
    entries = {e.variant_id: e for e in report.entries}
    assert entries["chunk64"].improvement_ratio == 0.9
    assert entries["chunk64"].disposition == "beaten"
    assert entries["chunk256"].disposition == "below_threshold"


def test_increase_direction_improvement():
    drafts, report = build(
        {"stream": 1500.0, "chunk64": 1200.0, "chunk256": 1001.0},
        baseline_value=1000.0,
        threshold=0.4,
        direction="increase",
    )
    entries = {e.variant_id: e for e in report.entries}
    assert entries["stream"].improvement_ratio == 0.5
    assert entries["stream"].disposition == "best"
    assert entries["chunk256"].disposition == "below_threshold"


def test_no_threshold_meeting_branch_fails_closed():
    drafts, tree, spec_map, _ = make_inputs()
    with pytest.raises(CycleError, match="no measured branch met the threshold"):
        build_report(
            LOOP_ID,
            tree,
            spec_map,
            {"stream": 900.0, "chunk64": 950.0, "chunk256": 999.0},
            1000.0,
            0.90,
            "decrease",
            metric_unit="rows",
        )


def test_unknown_measured_variant_and_missing_branch_fail_closed():
    drafts, tree, spec_map, _ = make_inputs()
    with pytest.raises(CycleError, match="do not bind to any tree branch"):
        build_report(
            LOOP_ID, tree, spec_map, {"mystery": 1.0}, 1000.0, 0.9, "decrease",
            metric_unit="rows",
        )
    del spec_map[drafts[0].id]
    with pytest.raises(CycleError, match="missing from the branch map"):
        build_report(
            LOOP_ID, tree, spec_map, dict(MEASURED), 1000.0, 0.9, "decrease",
            metric_unit="rows",
        )
    with pytest.raises(CycleError, match="baseline is zero"):
        build_report(
            LOOP_ID, tree, {d.id: d for d in drafts}, dict(MEASURED), 0.0, 0.9,
            "decrease", metric_unit="rows",
        )
    with pytest.raises(CycleError, match="direction"):
        build_report(
            LOOP_ID, tree, {d.id: d for d in drafts}, dict(MEASURED), 1000.0, 0.9,
            "flat", metric_unit="rows",
        )


def test_report_determinism_byte_identical_canonical_content():
    drafts, tree, spec_map, measured = make_inputs()
    r1 = build_report(LOOP_ID, tree, spec_map, measured, 1000.0, 0.9, "decrease", metric_unit="rows")
    r2 = build_report(LOOP_ID, tree, spec_map, measured, 1000.0, 0.9, "decrease", metric_unit="rows")
    strip = {"id", "created_at"}
    d1 = r1.model_dump(mode="json")
    d2 = r2.model_dump(mode="json")
    for doc in (d1, d2):
        doc.pop("id"), doc.pop("created_at")
        for entry in doc["entries"]:
            entry.pop("id"), entry.pop("created_at")
    assert canonical_json(d1) == canonical_json(d2)
    assert r1.id != r2.id  # only the fresh base fields differ


def test_build_proposal_binds_report_winner_and_stays_pending():
    drafts, report = build()
    proposal = build_proposal(report, LOOP_ID, "adopt verify_chain_streaming additively")
    assert proposal.report_id == report.id
    assert proposal.loop_id == LOOP_ID
    assert proposal.recommended_branch_id == report.winner_branch_id
    assert proposal.authority_class == "C2"
    assert proposal.ratification == "pending"  # never self-ratifies
    with pytest.raises(CycleError, match="loop_id"):
        build_proposal(report, "0" * 32, "x")
    with pytest.raises(CycleError, match="ComparisonReport"):
        build_proposal("not-a-report", LOOP_ID, "x")
