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


# ---------------------------------------------------------------- WP-06 set
# WP-06 (SPEC-WP06 3.1) appends the fast-evolution contracts: ComparisonEntry
# (sub-record, like AuditFinding), ComparisonReport, FailureAnalysis and
# ImprovementProposal. Same discipline: frozen, extra-forbid, each contract
# validates only its own fields; cross-contract enforcement stays in the
# engine/scripts (Hard Rule 4).


class ComparisonEntry(KernelModel):
    """One ranked branch of a ComparisonReport (sub-record, not a contract)."""

    branch_id: str
    variant_id: str
    measured_value: float
    improvement_ratio: float
    rank: int = Field(ge=1)
    disposition: Literal["best", "beaten", "below_threshold", "not_measured"]


class ComparisonReport(KernelModel):
    """Sealed ranking of all measured branches against the baseline.

    Cross-field invariants (fail closed on ambiguity): exactly one entry is
    disposition ``best`` and ``winner_branch_id`` binds to it; the ranks of
    ALL entries are a permutation of 1..len(entries), with the measured
    entries (best/beaten/below_threshold) holding ranks 1..#measured and the
    unmeasured (audit-killed pre-experiment) entries ranked last.
    """

    loop_id: str
    tree_id: str
    metric_id: str
    metric_unit: str
    baseline_value: float
    ranking_rule: str
    entries: list[ComparisonEntry] = Field(min_length=1)
    winner_branch_id: str

    @model_validator(mode="after")
    def _winner_ranks_consistent(self):
        bests = [e for e in self.entries if e.disposition == "best"]
        if len(bests) != 1:
            raise ValueError(
                f"a comparison report needs exactly one 'best' entry, got {len(bests)}"
            )
        if bests[0].branch_id != self.winner_branch_id:
            raise ValueError(
                "winner_branch_id must equal the 'best' entry's branch_id; "
                "ambiguity fails closed"
            )
        ranks = sorted(e.rank for e in self.entries)
        if ranks != list(range(1, len(self.entries) + 1)):
            raise ValueError("entry ranks must be a permutation of 1..len(entries)")
        measured = [
            e
            for e in self.entries
            if e.disposition in ("best", "beaten", "below_threshold")
        ]
        if sorted(e.rank for e in measured) != list(range(1, len(measured) + 1)):
            raise ValueError(
                "measured entries must hold ranks 1..#measured; unmeasured "
                "branches rank last"
            )
        return self


class FailureAnalysis(KernelModel):
    """Sealed analysis of one killed or below-threshold branch.

    A failure that does not become a regression test is refused:
    ``regression_test_ref`` must name a pinned test for the failure classes
    ``threshold_unmet`` and ``regression_detected``. ``experiment_spec_id``
    is empty when the branch was killed pre-experiment (audit kill).
    """

    branch_id: str
    experiment_spec_id: str = ""  # empty when killed pre-experiment
    failure_class: Literal[
        "threshold_unmet",
        "harness_error",
        "protocol_violation",
        "regression_detected",
        "verifier_disagreement",
        "audit_killed",
    ]
    diagnosis: str
    evidence_refs: list[str] = []
    regression_test_ref: str = ""

    @model_validator(mode="after")
    def _regression_test_pinned(self):
        if self.failure_class in ("threshold_unmet", "regression_detected") and not (
            isinstance(self.regression_test_ref, str) and self.regression_test_ref
        ):
            raise ValueError(
                f"failure_class {self.failure_class!r} requires a pinned "
                "regression_test_ref; a failure that does not become a "
                "regression test is refused"
            )
        return self


class ImprovementProposal(KernelModel):
    """A sealed recommendation to adopt the comparison winner.

    Sovereignty: the proposal RECOMMENDS; the founder ratifies. The contract
    is constructable ONLY as ``pending`` — ratification/rejection is an
    InstitutionalEvent (RATIFICATION / REJECTION) carrying a founder approval
    reference, never a mutation of this frozen record.
    """

    report_id: str
    loop_id: str
    recommended_branch_id: str
    patch_summary: str
    authority_class: Literal["C2"]
    ratification: Literal["pending", "ratified", "rejected"] = "pending"

    @model_validator(mode="after")
    def _sealed_pending_only(self):
        if self.ratification != "pending":
            raise ValueError(
                "an ImprovementProposal is sealed pending only; ratification "
                "is a gated founder InstitutionalEvent, never self-ratification"
            )
        return self
