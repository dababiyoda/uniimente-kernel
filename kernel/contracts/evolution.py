"""Evolution contracts (WP-05) — the Phase 2 closure-loop set.

These eight contracts (plus the AuditFinding sub-record) make institutional
self-improvement a first-class sealed activity: a StrategyTree of proposed
branches, a SpiderWebAudit that attacks each branch, a pre-registered
ExperimentSpec, an independent VerifierRecord, one RetainRegressKillDecision
per branch, and the terminal ClosureLoop/EvolutionCapsule pair that binds the
whole cycle to the spine.

Hard Rule 4 (fail closed): cross-contract consistency (selection rule,
retain-requires-threshold, seal order) is enforced by the ENGINE
(``kernel/evolution/cycle.py``), never by the contracts; each contract
validates only its own fields. Hard Rule 1 (frozen discipline): status
transitions are InstitutionalEvents, never contract mutations — every model
here is frozen and extra-forbid, exactly like the WP-01 set.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from .base import KernelModel

_HEX64 = frozenset("0123456789abcdef")


def _require_hex64(field: str, value: str) -> str:
    # A hash field that is not a sha256 hex digest is ambiguous; fail closed.
    if len(value) != 64 or any(c not in _HEX64 for c in value):
        raise ValueError(f"{field} must be a 64-char lowercase sha256 hex digest")
    return value


class AuditFinding(KernelModel):
    """One attack dimension of a SpiderWebAudit (pass/fail + note)."""

    dimension: str
    attack: str
    result: Literal["pass", "fail"]
    note: str = ""


class StrategyBranch(KernelModel):
    """One proposed evolution branch of a StrategyTree.

    ``tree_id`` is assigned by the engine at seal time (``""`` while draft);
    the draft the operator authors is never mutated — the engine seals a
    ``model_copy``. ``scores`` is the pre-registered rubric (e.g.
    expected_value, risk, reversibility, cost) the selection rule reads.
    """

    tree_id: str = ""  # set by the engine at seal time; "" while draft
    parent_id: str | None = None
    title: str
    hypothesis: str
    metric_id: str
    expected_delta: float  # signed, pre-registered
    scores: dict[str, float]
    status: Literal["proposed"] = "proposed"


class StrategyTree(KernelModel):
    """A single-horizon tree of candidate evolution branches."""

    root_objective: str
    horizon: str
    selection_rule: str  # human-readable, mirrored by the engine's code
    branch_ids: list[str]
    created_by: str


class SpiderWebAudit(KernelModel):
    """Adversarial audit of one branch; a single failed finding fails it."""

    branch_id: str
    auditor_id: str
    findings: list[AuditFinding] = Field(min_length=1)
    overall: Literal["pass", "fail"]

    @model_validator(mode="after")
    def _overall_consistent_with_findings(self):
        # overall == "fail" iff any finding failed; "pass" iff all pass.
        any_fail = any(f.result == "fail" for f in self.findings)
        expected = "fail" if any_fail else "pass"
        if self.overall != expected:
            raise ValueError(
                f"overall {self.overall!r} contradicts findings "
                f"(expected {expected!r}); ambiguity fails closed"
            )
        return self


class ExperimentSpec(KernelModel):
    """The pre-registered experiment: metric, baseline, threshold, harness."""

    branch_id: str
    metric_id: str
    metric_unit: str
    baseline_value: float
    threshold_improvement: float = Field(gt=0.0, lt=1.0)  # a ratio
    direction: Literal["decrease", "increase"]
    harness_ref: str  # script path
    workload_id: str
    pre_registered: Literal[True]  # a False value is unconstructable


class VerifierRecord(KernelModel):
    """Independent re-measurement of a sealed experiment (the verifier)."""

    experiment_spec_id: str
    verifier_id: str
    baseline_value: float  # re-measured
    measured_value: float
    improvement_ratio: float
    threshold_met: bool
    reran_tests_green: bool
    notes: str = ""


class RetainRegressKillDecision(KernelModel):
    """Terminal per-branch decision; killed branches are sealed memory."""

    branch_id: str
    loop_id: str
    decision: Literal["retain", "regress", "kill"]
    rationale: str
    decided_by: str
    revert_plan: str = ""


class ClosureLoop(KernelModel):
    """Sealed LAST: binds one full evolution cycle end to end.

    ``capsule_id`` references the EvolutionCapsule contract id; ADR-8
    (SPEC-WP05 3.1): both models are pre-constructed in memory so the
    dual reference is honest — no placeholder fields, no mutation. The
    empty string is permitted ONLY on the aborted path (no capsule).
    """

    cycle_index: int
    tree_id: str
    selected_branch_id: str
    audit_ids: list[str]
    experiment_spec_id: str
    verifier_record_id: str
    decision_ids: list[str]  # one per branch: retain/regress/kill
    capsule_id: str
    baseline_ref: str
    status: Literal["completed", "aborted"]


class EvolutionCapsule(KernelModel):
    """The proof artifact binding: capsule file hash + sealed spine head."""

    loop_id: str
    cycle_index: int
    capsule_path: str
    capsule_hash: str  # 64-hex sha256 of the capsule JSON file
    sealed_head_hash: str  # 64-hex spine head this capsule attests
    verdict: Literal["baseline_beaten", "baseline_held", "cycle_aborted"]

    @field_validator("capsule_hash", "sealed_head_hash")
    @classmethod
    def _require_sha256_hex(cls, v: str, info):
        return _require_hex64(info.field_name, v)
