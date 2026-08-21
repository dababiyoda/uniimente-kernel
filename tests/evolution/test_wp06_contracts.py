"""WP-06 fast-evolution contract suite — validation discipline (SPEC-WP06 4.1).

ComparisonEntry / ComparisonReport / FailureAnalysis / ImprovementProposal:
frozen, extra-forbid, Literal enums, report winner/best consistency, rank
permutation (measured entries hold 1..#measured, unmeasured rank last), the
FailureAnalysis regression-test-ref rule in BOTH directions, and
pending-only proposal construction.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from kernel.contracts import CONTRACTS
from kernel.contracts.evolution import (
    ComparisonEntry,
    ComparisonReport,
    FailureAnalysis,
    ImprovementProposal,
)


def make_entry(**overrides) -> ComparisonEntry:
    fields = dict(
        branch_id="a" * 32,
        variant_id="stream",
        measured_value=1.0,
        improvement_ratio=0.999,
        rank=1,
        disposition="best",
    )
    fields.update(overrides)
    return ComparisonEntry(**fields)


def make_report(**overrides) -> ComparisonReport:
    fields = dict(
        loop_id="c" * 32,
        tree_id="d" * 32,
        metric_id="pg_spine_verify_peak_rows",
        metric_unit="rows",
        baseline_value=1000.0,
        ranking_rule="rank by measured improvement descending",
        entries=[
            make_entry(),
            make_entry(
                branch_id="b" * 32,
                variant_id="chunk64",
                measured_value=64.0,
                improvement_ratio=0.936,
                rank=2,
                disposition="beaten",
            ),
        ],
        winner_branch_id="a" * 32,
    )
    fields.update(overrides)
    return ComparisonReport(**fields)


def make_failure(**overrides) -> FailureAnalysis:
    fields = dict(
        branch_id="b" * 32,
        failure_class="threshold_unmet",
        diagnosis="improvement below the pre-registered threshold",
        regression_test_ref="tests/evolution/test_wp06_bench_matrix.py::test_x",
    )
    fields.update(overrides)
    return FailureAnalysis(**fields)


def make_proposal(**overrides) -> ImprovementProposal:
    fields = dict(
        report_id="e" * 32,
        loop_id="c" * 32,
        recommended_branch_id="a" * 32,
        patch_summary="adopt verify_chain_streaming additively",
        authority_class="C2",
    )
    fields.update(overrides)
    return ImprovementProposal(**fields)


def test_new_contracts_are_frozen():
    for model in (make_entry(), make_report(), make_failure(), make_proposal()):
        with pytest.raises(ValidationError):
            model.id = "mutated"


def test_new_contracts_extra_fields_rejected():
    for factory in (make_entry, make_report, make_failure, make_proposal):
        with pytest.raises(ValidationError):
            factory(smuggled=True)


def test_new_contracts_tz_aware_created_at():
    from datetime import datetime

    for factory in (make_entry, make_report, make_failure, make_proposal):
        with pytest.raises(ValidationError, match="timezone-aware"):
            factory(created_at=datetime(2026, 9, 4, 12, 0, 0))  # naive


def test_entry_rank_and_disposition_literals():
    with pytest.raises(ValidationError):
        make_entry(rank=0)
    with pytest.raises(ValidationError):
        make_entry(disposition="winner")
    assert make_entry(disposition="not_measured").disposition == "not_measured"


def test_report_requires_exactly_one_best():
    with pytest.raises(ValidationError, match="exactly one 'best'"):
        make_report(
            entries=[
                make_entry(),
                make_entry(branch_id="b" * 32, variant_id="v2", rank=2, disposition="best"),
            ]
        )
    with pytest.raises(ValidationError, match="exactly one 'best'"):
        make_report(
            entries=[
                make_entry(disposition="beaten"),
                make_entry(
                    branch_id="b" * 32,
                    variant_id="v2",
                    rank=2,
                    disposition="beaten",
                ),
            ]
        )


def test_report_winner_must_bind_the_best_entry():
    with pytest.raises(ValidationError, match="winner_branch_id"):
        make_report(winner_branch_id="b" * 32)


def test_report_ranks_must_be_a_permutation_with_measured_first():
    # Rank gap: [1, 3] is not a permutation of 1..2.
    with pytest.raises(ValidationError, match="permutation"):
        make_report(
            entries=[
                make_entry(),
                make_entry(
                    branch_id="b" * 32, variant_id="v2", rank=3, disposition="beaten"
                ),
            ]
        )
    # An unmeasured entry must rank AFTER the measured ones.
    with pytest.raises(ValidationError, match="measured entries must hold ranks"):
        make_report(
            entries=[
                make_entry(),
                make_entry(
                    branch_id="b" * 32,
                    variant_id="v2",
                    rank=2,
                    disposition="not_measured",
                ),
                make_entry(
                    branch_id="c" * 32,
                    variant_id="v3",
                    rank=3,
                    disposition="below_threshold",
                ),
            ],
        )
    # Honest shape: measured 1..2, unmeasured last.
    ok = make_report(
        entries=[
            make_entry(),
            make_entry(branch_id="b" * 32, variant_id="v2", rank=2, disposition="beaten"),
            make_entry(
                branch_id="c" * 32,
                variant_id="v3",
                measured_value=1000.0,
                improvement_ratio=0.0,
                rank=3,
                disposition="not_measured",
            ),
        ]
    )
    assert ok.entries[2].disposition == "not_measured"


def test_report_needs_at_least_one_entry():
    with pytest.raises(ValidationError):
        make_report(entries=[])


def test_failure_analysis_regression_ref_rule_both_directions():
    # threshold_unmet / regression_detected REQUIRE a pinned regression test.
    with pytest.raises(ValidationError, match="regression_test_ref"):
        make_failure(regression_test_ref="")
    with pytest.raises(ValidationError, match="regression_test_ref"):
        make_failure(failure_class="regression_detected", regression_test_ref="")
    # audit_killed (pre-experiment) may carry an empty ref and empty spec id.
    ok = make_failure(
        failure_class="audit_killed",
        experiment_spec_id="",
        regression_test_ref="",
    )
    assert ok.experiment_spec_id == ""
    # With the ref pinned, both required classes construct.
    assert make_failure(failure_class="regression_detected").failure_class == (
        "regression_detected"
    )


def test_failure_class_literal_enforced():
    with pytest.raises(ValidationError):
        make_failure(failure_class="mystery")


def test_proposal_is_pending_only_and_c2_only():
    with pytest.raises(ValidationError, match="pending only"):
        make_proposal(ratification="ratified")
    with pytest.raises(ValidationError, match="pending only"):
        make_proposal(ratification="rejected")
    with pytest.raises(ValidationError):
        make_proposal(authority_class="C1")
    assert make_proposal().ratification == "pending"


def test_registry_carries_the_wp06_contracts_but_not_the_subrecord():
    for name in ("ComparisonReport", "FailureAnalysis", "ImprovementProposal"):
        assert name in CONTRACTS
    assert "ComparisonEntry" not in CONTRACTS  # sub-record, like AuditFinding
