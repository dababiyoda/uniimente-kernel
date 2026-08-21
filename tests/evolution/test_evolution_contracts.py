"""WP-05 evolution contract suite — validation discipline of the Phase 2 set.

Every contract is frozen, extra-forbid, tz-aware (KernelModel base), with
Literal enums enforced, ExperimentSpec bounds pinned, the pre_registered
literal unconstructable-False, and the SpiderWebAudit overall/findings
consistency validator checked in BOTH directions. All hermetic.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from kernel.contracts import CONTRACTS
from kernel.contracts import AuditFinding as RegistryAuditFinding
from kernel.contracts.evolution import (
    AuditFinding,
    ClosureLoop,
    EvolutionCapsule,
    ExperimentSpec,
    RetainRegressKillDecision,
    SpiderWebAudit,
    StrategyBranch,
    StrategyTree,
    VerifierRecord,
)

TZ = timezone.utc


def make_finding(result: str = "pass", **overrides) -> AuditFinding:
    fields = dict(dimension="correctness_risk", attack="a", result=result)
    fields.update(overrides)
    return AuditFinding(**fields)


def make_branch(**overrides) -> StrategyBranch:
    fields = dict(
        title="B",
        hypothesis="h",
        metric_id="m",
        expected_delta=-0.5,
        scores={"expected_value": 0.8, "risk": 0.1, "reversibility": 1.0, "cost": 0.2},
    )
    fields.update(overrides)
    return StrategyBranch(**fields)


def make_spec(**overrides) -> ExperimentSpec:
    fields = dict(
        branch_id="b" * 32,
        metric_id="pg_spine_bulk_append_ops",
        metric_unit="connection_ops",
        baseline_value=40.0,
        threshold_improvement=0.5,
        direction="decrease",
        harness_ref="scripts/wp05_bench.py",
        workload_id="append10-pinned-events",
        pre_registered=True,
    )
    fields.update(overrides)
    return ExperimentSpec(**fields)


def make_capsule(**overrides) -> EvolutionCapsule:
    fields = dict(
        loop_id="a" * 32,
        cycle_index=1,
        capsule_path="proof/wp05_evolution_capsule.json",
        capsule_hash="c" * 64,
        sealed_head_hash="d" * 64,
        verdict="baseline_beaten",
    )
    fields.update(overrides)
    return EvolutionCapsule(**fields)


def test_01_contracts_are_frozen():
    branch = make_branch()
    with pytest.raises(ValidationError):
        branch.title = "mutated"
    spec = make_spec()
    with pytest.raises(ValidationError):
        spec.baseline_value = 1.0


def test_02_extra_fields_rejected():
    with pytest.raises(ValidationError):
        make_branch(smuggled=True)
    with pytest.raises(ValidationError):
        make_spec(smuggled=True)
    with pytest.raises(ValidationError):
        make_capsule(smuggled=True)


def test_03_naive_datetimes_rejected():
    with pytest.raises(ValidationError, match="timezone-aware"):
        make_branch(created_at=datetime(2026, 8, 21, 12, 0, 0))  # naive
    aware = make_branch(created_at=datetime(2026, 8, 21, 12, 0, 0, tzinfo=TZ))
    assert aware.created_at.tzinfo is not None


def test_04_literal_enums_enforced():
    with pytest.raises(ValidationError):
        make_finding(result="maybe")
    with pytest.raises(ValidationError):
        RetainRegressKillDecision(
            branch_id="b" * 32,
            loop_id="a" * 32,
            decision="keep",
            rationale="r",
            decided_by="founder",
        )
    with pytest.raises(ValidationError):
        make_spec(direction="flat")
    with pytest.raises(ValidationError):
        make_capsule(verdict="won")
    with pytest.raises(ValidationError):
        make_branch(status="retained")  # transitions are events, never mutations


@pytest.mark.parametrize("bad", [0.0, 1.0, -0.1, 1.5])
def test_05_threshold_improvement_bounds(bad):
    with pytest.raises(ValidationError):
        make_spec(threshold_improvement=bad)
    assert make_spec(threshold_improvement=0.5).threshold_improvement == 0.5


def test_06_pre_registered_false_is_unconstructable():
    with pytest.raises(ValidationError):
        make_spec(pre_registered=False)


def test_07_audit_overall_findings_consistency_both_directions():
    # overall="fail" iff any finding failed; mismatch raises.
    with pytest.raises(ValidationError, match="contradicts findings"):
        SpiderWebAudit(
            branch_id="b" * 32,
            auditor_id="operator",
            findings=[make_finding("pass"), make_finding("fail", dimension="governance_risk")],
            overall="pass",
        )
    with pytest.raises(ValidationError, match="contradicts findings"):
        SpiderWebAudit(
            branch_id="b" * 32,
            auditor_id="operator",
            findings=[make_finding("pass")],
            overall="fail",
        )
    ok_pass = SpiderWebAudit(
        branch_id="b" * 32, auditor_id="operator", findings=[make_finding("pass")], overall="pass"
    )
    ok_fail = SpiderWebAudit(
        branch_id="b" * 32, auditor_id="operator", findings=[make_finding("fail")], overall="fail"
    )
    assert ok_pass.overall == "pass" and ok_fail.overall == "fail"
    # An audit needs at least one finding.
    with pytest.raises(ValidationError):
        SpiderWebAudit(branch_id="b" * 32, auditor_id="operator", findings=[], overall="pass")


def test_08_capsule_hash_fields_require_64_hex():
    with pytest.raises(ValidationError):
        make_capsule(capsule_hash="not-a-hash")
    with pytest.raises(ValidationError):
        make_capsule(sealed_head_hash="F" * 64)  # uppercase is not lowercase hex
    assert make_capsule().capsule_hash == "c" * 64


def test_09_registry_has_31_contracts_plus_two_subrecords():
    # WP-06 (SPEC-WP06 3.1) forced amendment, same pattern as the WP-05 A2
    # count-test amendment: 28 -> 31 contracts + 2 sub-records.
    assert len(CONTRACTS) == 31
    for name in (
        "StrategyBranch",
        "StrategyTree",
        "SpiderWebAudit",
        "ExperimentSpec",
        "VerifierRecord",
        "RetainRegressKillDecision",
        "ClosureLoop",
        "EvolutionCapsule",
        "ComparisonReport",
        "FailureAnalysis",
        "ImprovementProposal",
    ):
        assert name in CONTRACTS
    # AuditFinding and ComparisonEntry are sub-records, not standalone contracts.
    assert "AuditFinding" not in CONTRACTS
    assert RegistryAuditFinding is AuditFinding
    from kernel.contracts import ComparisonEntry as RegistryComparisonEntry
    from kernel.contracts.evolution import ComparisonEntry

    assert "ComparisonEntry" not in CONTRACTS
    assert RegistryComparisonEntry is ComparisonEntry
