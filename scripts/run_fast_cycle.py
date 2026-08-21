#!/usr/bin/env python3
"""WP-06 Fast Evolution Cycle — the first AUTOMATED capability cycle.

Runs the full ClosureLoop on a FILE spine in a temp dir (ADR-7: hermetic
proof) with NO operator-authored branches: the BranchGenerator mechanically
enumerates the declared MutationSpace into four StrategyBranch drafts, the
RuleBasedAuditor kills ``no_commit_stream`` (TransactionSemanticsRule +
DeclaredReversibilityRule), ONE gated C2 matrix experiment measures all three
audit-passing variants in isolation (fresh store per variant) under one
founder approval, the verifier stage independently re-runs the matrix and
cross-checks every per-variant value against the receipt facts, and the
ComparisonReport / pending ImprovementProposal / FailureAnalysis records are
sealed before the founder ratifies the winner (RATIFICATION event) and the
capsule seals.

Stages (SPEC-WP06 3.7), all machine-recorded on the spine:
    1. MutationSpace declared; BranchGenerator generates 4 drafts (control
       excluded). No operator-authored branches anywhere in this script.
    2. RuleBasedAuditor audits all drafts; no_commit_stream killed.
    3. Selection rule picks stream (max expected_value among passing).
    4. Per-branch ExperimentSpecs sealed for the 3 audit-passing branches;
       the selected spec id rides in intent.payload["experiment_spec_id"],
       siblings in payload["comparison_spec_ids"] (engine unchanged).
    5. ONE gated C2 matrix experiment via BenchmarkAdapter (allowlist gains
       scripts/wp06_bench.py by construction).
    6. Verifier stage re-runs the matrix independently; per-variant values
       must equal the receipt facts (any disagreement -> CycleError).
    7. build_report + build_proposal (pure functions); ComparisonReport,
       ImprovementProposal (pending) and FailureAnalysis records sealed.
    8. Decisions: retain stream, regress chunk64 (beaten), regress chunk256
       (below threshold), kill no_commit_stream.
    9. Founder ratification over the proposal fingerprint, sealed as a
       RATIFICATION event carrying the approval id.
   10. seal_capsule -> proof/wp06_fast_cycle_capsule.json; verdict line;
       exit 0 only if: completed, baseline_beaten, chain verifies, capsule
       hash verifies, all three decision types present, ratification sealed.

Hermetic: no DSN, no network, no credentials anywhere. Determinism: the
metric is peak buffered rows on a fake DBAPI; the verdict line carries
stable scalars only.

Usage (from the slice root):
    python scripts/run_fast_cycle.py

Exit codes: 0 = cycle completed and baseline beaten; 1 = any check failed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from kernel.adapters.benchmark import BenchmarkAdapter  # noqa: E402
from kernel.authority.approvals import ApprovalService  # noqa: E402
from kernel.contracts.action import ActionIntent  # noqa: E402
from kernel.contracts.evolution import (  # noqa: E402
    ComparisonReport,
    ExperimentSpec,
    FailureAnalysis,
    ImprovementProposal,
)
from kernel.contracts.institutional import InstitutionalEvent  # noqa: E402
from kernel.crypto.hashing import canonical_json, content_hash, sha256_hex  # noqa: E402
from kernel.evolution import (  # noqa: E402
    BranchGenerator,
    CycleError,
    EvolutionCycle,
    MutationSpace,
    RuleBasedAuditor,
    SHIPPED_RULES,
    build_proposal,
    build_report,
    parse_variant_config,
)
from kernel.gate.pipeline import Gate  # noqa: E402
from kernel.spine import Spine  # noqa: E402
from kernel.ucl import Constitution, compile_policy_fn  # noqa: E402
from kernel.ucl.version import constitution_version_from_dir, policy_version  # noqa: E402

from scripts import wp06_bench as bench  # noqa: E402

CAPSULE_PATH = REPO_ROOT / "proof" / "wp06_fast_cycle_capsule.json"
CAPSULE_REF = "proof/wp06_fast_cycle_capsule.json"
HARNESS_REF = "scripts/wp06_bench.py"
CYCLE_INDEX = 2  # WP-05's manual cycle was index 1
THRESHOLD_IMPROVEMENT = bench.THRESHOLD_IMPROVEMENT  # 0.90, SPEC-WP06 3.5
BASELINE_VALUE = bench.BASELINE_VALUE  # 1000.0
AUDITOR_ID = "rule-based-auditor:wp06-shipped-rules"
VERIFIER_ID = "verifier:independent-rerun"

OBJECTIVE = (
    "Cut peak buffered rows during PostgresSpine.verify_chain on a "
    "1000-record chain (read path)"
)
SELECTION_RULE = (
    "max scores.expected_value among audit-passing branches with "
    "scores.risk <= 0.3 and scores.reversibility >= 0.8; ties -> lower scores.cost"
)

# Pre-registered generator scoring config (SPEC-WP06 3.5, exact values).
SCORING: dict[str, dict[str, float]] = {
    "stream": {
        "expected_value": 0.9,
        "risk": 0.1,
        "reversibility": 1.0,
        "cost": 0.2,
        "expected_delta": -0.999,
    },
    "chunk64": {
        "expected_value": 0.7,
        "risk": 0.15,
        "reversibility": 1.0,
        "cost": 0.25,
        "expected_delta": -0.936,
    },
    "chunk256": {
        "expected_value": 0.5,
        "risk": 0.15,
        "reversibility": 1.0,
        "cost": 0.25,
        "expected_delta": -0.744,
    },
    "no_commit_stream": {
        "expected_value": 0.85,
        "risk": 0.6,
        "reversibility": 0.4,
        "cost": 0.2,
        "expected_delta": -0.999,
    },
}

# Pre-registered honest audit declarations per variant (SPEC-WP06 3.5): the
# no_commit_stream variant HONESTLY declares commit_strategy="commit_never" —
# the shipped rules then kill it mechanically.
_DECL_BASE = {"modifies": [], "touches": [], "new_dependencies": []}
DECLARATIONS: dict[str, dict] = {
    "stream": {**_DECL_BASE, "commit_strategy": "commit_after"},
    "chunk64": {**_DECL_BASE, "commit_strategy": "commit_after"},
    "chunk256": {**_DECL_BASE, "commit_strategy": "commit_after"},
    "no_commit_stream": {**_DECL_BASE, "commit_strategy": "commit_never"},
}

PATCH_SUMMARY = (
    "Adopt PostgresSpine.verify_chain_streaming(): SELECT + fetchone loop + "
    "single closing commit; byte-identical Python-side verification logic as "
    "verify_chain; additive method, verify_chain untouched; parity-tested on "
    "the honest chain and all four WP-04 anomaly fixtures."
)

# The pinned regression test the chunk256 FailureAnalysis points at (a REAL
# test, pinned into the suite — failure becomes an appreciating asset).
CHUNK256_REGRESSION_TEST_REF = (
    "tests/evolution/test_wp06_bench_matrix.py::"
    "test_chunk256_peak_rows_below_threshold_regression_pin"
)


def make_space() -> MutationSpace:
    """The declared MutationSpace (SPEC-WP06 3.5): axis fetch_strategy with
    the fetchall control and four candidate variants."""
    return MutationSpace(
        objective=OBJECTIVE,
        metric_id=bench.METRIC_ID,
        axes={
            "fetch_strategy": [
                "fetchall",
                "stream",
                "chunk64",
                "chunk256",
                "no_commit_stream",
            ]
        },
        control_variant="fetchall",
    )


def make_generator() -> BranchGenerator:
    return BranchGenerator(SCORING, declarations=DECLARATIONS)


def pinned_matrix_protocol() -> dict:
    """The pre-registered pinned MATRIX protocol (carried by the witness).

    A DIFFERENT 7-key shape than the WP-05 single-pair protocol; pins the
    baseline value, every per-variant peak AND every per-variant op trace
    (order included). Built from the harness's pinned constants, never from
    measured outputs.
    """
    return {
        "workload_id": bench.WORKLOAD_ID,
        "harness_ref": HARNESS_REF,
        "metric": bench.METRIC_ID,
        "candidate_variant": "stream",  # pre-registered selection outcome
        "baseline_value": BASELINE_VALUE,
        "variant_values": dict(bench.VARIANT_PEAKS),
        "variant_traces": dict(bench.VARIANT_TRACES),
    }


def receipt_facts(spine: Spine, episode) -> dict:
    """Read the adapter-attested receipt facts back off the spine."""
    for rec in spine.iter():
        if rec["kind"] == "ExecutionReceipt" and rec["payload"].get("id") == episode.receipt_id:
            return json.loads(rec["payload"]["external_id"])
    raise CycleError("no signed receipt facts on the spine; fail closed")


def remeasure_and_cross_check(facts: dict) -> tuple[float, float]:
    """The verifier's independent re-run of the WHOLE matrix.

    Every per-variant measured value must equal the adapter-attested receipt
    facts; any disagreement is a CycleError (fail closed) — the system's
    opinion of itself is never proof. Returns (baseline, candidate value of
    the pre-registered candidate_variant) for the engine's verifier stage.
    """
    baseline, _baseline_trace = bench.measure_baseline()
    values, _traces = bench.measure_matrix()
    pinned = facts.get("variant_values")
    if not isinstance(pinned, dict) or set(values) != set(pinned):
        raise CycleError(
            "verifier re-run contradicts the adapter-attested receipt facts "
            "(variant set mismatch)"
        )
    for variant in sorted(values):
        if float(values[variant]) != float(pinned[variant]):
            raise CycleError(
                "verifier re-run contradicts the adapter-attested receipt facts "
                f"(variant {variant!r}: rerun={values[variant]}, "
                f"attested={pinned[variant]})"
            )
    candidate = float(values[facts["candidate_variant"]])
    if candidate != float(facts["candidate_value"]):
        raise CycleError(
            "verifier re-run contradicts the adapter-attested receipt facts "
            f"(candidate {facts['candidate_variant']!r}: rerun={candidate}, "
            f"attested={facts['candidate_value']})"
        )
    if float(baseline) != float(facts["baseline_value"]):
        raise CycleError(
            "verifier re-run contradicts the adapter-attested receipt facts "
            f"(baseline: rerun={baseline}, attested={facts['baseline_value']})"
        )
    return float(baseline), candidate


def rerun_test_suite() -> bool:
    """Honestly re-run the full test suite as a subprocess (hermetic)."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def founder_ratify(
    spine: Spine,
    authority: ApprovalService,
    proposal: ImprovementProposal,
    *,
    approval,
    actor_id: str,
    organ_id: str,
) -> InstitutionalEvent:
    """Seal the founder RATIFICATION of a pending proposal (SPEC-WP06 3.7.9).

    GATED: the approval must be a valid founder ApprovalRecord over the
    proposal fingerprint (content hash of the sealed pending proposal);
    ``verify_approval`` fails closed on any mismatch and consumes the nonce.
    No approval -> CycleError, nothing appended, the proposal stays pending
    (frozen discipline: the contract never self-ratifies).
    """
    fingerprint = content_hash(proposal)
    if approval is None:
        raise CycleError(
            "ratification requires a founder approval over the proposal "
            "fingerprint; fail closed"
        )
    authority.verify_approval(approval, fingerprint)  # fail closed; one-use
    event = InstitutionalEvent(
        event_type="RATIFICATION",
        actor_id=actor_id,
        organ_id=organ_id,
        payload_hash=fingerprint,
    )
    spine.append(
        event,
        kind="RATIFICATION",
        refs={
            "proposal_id": proposal.id,
            "approval_id": approval.id,
            "loop_id": proposal.loop_id,
            "proposal_fingerprint": fingerprint,
        },
    )
    return event


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capsule", default=str(CAPSULE_PATH), help="capsule output path")
    parser.add_argument(
        "--capsule-ref",
        default=None,
        help="path string recorded in the EvolutionCapsule contract "
        "(default: the --capsule value)",
    )
    parser.add_argument(
        "--spine-dir",
        default=None,
        help="directory for the file spine (default: a fresh temp dir)",
    )
    parser.add_argument(
        "--skip-test-rerun",
        action="store_true",
        help="do not re-run pytest inside the cycle (used by the in-process "
        "end-to-end test to avoid recursive pytest; reran_tests_green=False "
        "is then sealed honestly)",
    )
    args = parser.parse_args(argv)
    capsule_path = Path(args.capsule)
    capsule_ref = args.capsule_ref or (
        CAPSULE_REF if capsule_path == CAPSULE_PATH else str(capsule_path)
    )
    spine_dir = Path(args.spine_dir) if args.spine_dir else Path(tempfile.mkdtemp(prefix="wp06-spine-"))

    # Compiled WP-02 constitution + gate + benchmark adapter + founder.
    constitution_dir = REPO_ROOT / "constitution"
    model = Constitution.from_directory(constitution_dir, current_state="normal")
    versions = {
        "policy_version": policy_version(model),
        "constitution_version": constitution_version_from_dir(constitution_dir),
    }
    policy_fn = compile_policy_fn(model, **versions)
    spine = Spine(spine_dir / "spine")
    authority = ApprovalService(approver_id="founder")
    gate = Gate(
        versions["policy_version"],
        versions["constitution_version"],
        authority,
        spine,
        policy_fn=policy_fn,
    )
    adapter = BenchmarkAdapter(
        witness_public_key=authority.public_key,
        harness_allowlist=("scripts/wp05_bench.py", HARNESS_REF),
    )
    gate.register_adapter(adapter.adapter_id, adapter.public_key_hex)
    cycle = EvolutionCycle(
        gate,
        spine,
        authority,
        actor_id="uniimente-kernel",
        organ_id="evolution-organ",
        cycle_index=CYCLE_INDEX,
    )

    # 1. MutationSpace declared; the generator mechanically enumerates it.
    space = make_space()
    drafts = make_generator().generate(space)  # NO operator-authored branches
    if len(drafts) != 4:
        print(f"REFUSAL: expected 4 generated drafts, got {len(drafts)}", file=sys.stderr)
        return 1
    tree = cycle.propose_tree(OBJECTIVE, "wp06", SELECTION_RULE, drafts)
    variant_of = {d.id: parse_variant_config(d)["variant_id"] for d in drafts}
    branch_of = {d.id: d for d in drafts}

    # 2. Mechanical audit; findings sealed via cycle.audit per branch.
    auditor = RuleBasedAuditor(SHIPPED_RULES)
    audits = {}
    for draft, findings in auditor.audit(drafts):
        audits[draft.id] = cycle.audit(draft.id, AUDITOR_ID, findings)
    killed = [d for d in drafts if audits[d.id].overall == "fail"]
    passing = [d for d in drafts if audits[d.id].overall == "pass"]
    if [variant_of[d.id] for d in killed] != ["no_commit_stream"] or len(passing) != 3:
        print("REFUSAL: audit outcome diverged from the pre-registered kill", file=sys.stderr)
        return 1

    # 3. Selection rule picks stream (max expected_value among passing).
    selected = cycle.select(tree, list(audits.values()))
    if variant_of[selected.id] != "stream":
        print(
            f"REFUSAL: selection picked {variant_of[selected.id]!r}, expected 'stream'",
            file=sys.stderr,
        )
        return 1

    # 4. Per-branch ExperimentSpecs for the 3 audit-passing branches; the
    # matrix protocol pins ALL variant measurements under each spec.
    specs = {}
    for draft in passing:
        spec = ExperimentSpec(
            branch_id=draft.id,
            metric_id=bench.METRIC_ID,
            metric_unit=bench.METRIC_UNIT,
            baseline_value=BASELINE_VALUE,
            threshold_improvement=THRESHOLD_IMPROVEMENT,
            direction="decrease",
            harness_ref=HARNESS_REF,
            workload_id=bench.WORKLOAD_ID,
            pre_registered=True,
        )
        cycle.register_experiment(spec)
        specs[draft.id] = spec
    selected_spec = specs[selected.id]
    sibling_spec_ids = [specs[d.id].id for d in passing if d.id != selected.id]

    # 5. ONE gated C2 matrix experiment (the ONLY gated side effect).
    intent = ActionIntent(
        actor_id="uniimente-kernel",
        organ_id="evolution-organ",
        legal_principal="Uniimente Ltd",
        objective=(
            "WP-06 fast cycle: measure peak buffered rows of the fetchall "
            "baseline vs the stream/chunk64/chunk256 variants on the pinned "
            "1000-record verification workload"
        ),
        action_type="evolution_experiment",
        resource="kernel",
        target="bench://wp06/pg-spine-verify-peak-rows",
        payload={
            "experiment_spec_id": selected_spec.id,
            "comparison_spec_ids": sibling_spec_ids,
        },
        consequence_class="C2",
        evidence_ids=[],
        expected_outcome=canonical_json(pinned_matrix_protocol()),
        rollback=None,
        expiry_minutes=30,
    )
    approval = authority.issue_approval(gate.fingerprint(intent))
    episode = cycle.run_experiment(intent, adapter, approval)
    facts = receipt_facts(spine, episode)

    # 6. Independent verification: the WHOLE matrix re-run and cross-checked
    # per variant inside the rerun callable; the engine then re-checks the
    # candidate/baseline pair and the threshold (fail closed on drift).
    tests_green = rerun_test_suite() if not args.skip_test_rerun else False
    verifier = cycle.verify(
        selected_spec,
        lambda: remeasure_and_cross_check(facts),
        verifier_id=VERIFIER_ID,
        tests_green=tests_green,
    )

    # 7. Comparison + proposal (pure functions); report, pending proposal and
    # FailureAnalysis records sealed.
    measured = {v: float(x) for v, x in facts["variant_values"].items()}
    report = build_report(
        cycle.loop_id,
        tree,
        branch_of,
        measured,
        float(facts["baseline_value"]),
        THRESHOLD_IMPROVEMENT,
        "decrease",
        metric_unit=bench.METRIC_UNIT,
    )
    spine.append(
        report,
        kind="ComparisonReport",
        refs={"loop_id": cycle.loop_id, "tree_id": tree.id},
    )
    proposal = build_proposal(report, cycle.loop_id, PATCH_SUMMARY)
    spine.append(
        proposal,
        kind="ImprovementProposal",
        refs={"loop_id": cycle.loop_id, "report_id": report.id},
    )
    entry_by_variant = {e.variant_id: e for e in report.entries}

    chunk256_branch = next(d for d in drafts if variant_of[d.id] == "chunk256")
    kill_branch = killed[0]
    fa_threshold = FailureAnalysis(
        branch_id=chunk256_branch.id,
        experiment_spec_id=specs[chunk256_branch.id].id,
        failure_class="threshold_unmet",
        diagnosis=(
            f"chunk256 measured peak 256 rows: improvement "
            f"{entry_by_variant['chunk256'].improvement_ratio} < pre-registered "
            f"threshold {THRESHOLD_IMPROVEMENT}; buffering 256-row batches "
            "keeps too much of the chain resident"
        ),
        evidence_refs=[report.id, specs[chunk256_branch.id].id],
        regression_test_ref=CHUNK256_REGRESSION_TEST_REF,
    )
    spine.append(
        fa_threshold,
        kind="FailureAnalysis",
        refs={"branch_id": chunk256_branch.id, "loop_id": cycle.loop_id},
    )
    fa_killed = FailureAnalysis(
        branch_id=kill_branch.id,
        experiment_spec_id="",  # killed pre-experiment
        failure_class="audit_killed",
        diagnosis=(
            "no_commit_stream killed mechanically by TransactionSemanticsRule "
            "(commit_strategy='commit_never' leaves a dangling transaction) and "
            "DeclaredReversibilityRule (reversibility 0.4 < 0.8)"
        ),
        evidence_refs=[audits[kill_branch.id].id],
        regression_test_ref="",
    )
    spine.append(
        fa_killed,
        kind="FailureAnalysis",
        refs={"branch_id": kill_branch.id, "loop_id": cycle.loop_id},
    )

    # 8. Terminal per-branch decisions: all three decision types FOR REAL.
    verdict = "baseline_beaten" if verifier.threshold_met else "baseline_held"
    cycle.decide(
        selected,
        decision="retain" if verifier.threshold_met else "regress",
        rationale=(
            f"stream peak 1 row: measured improvement "
            f"{verifier.improvement_ratio} >= pre-registered threshold "
            f"{selected_spec.threshold_improvement}"
            if verifier.threshold_met
            else "threshold unmet; branch regressed to draft"
        ),
        threshold_met=verifier.threshold_met,
        revert_plan="verify_chain_streaming is additive; removal deletes one method",
    )
    chunk64_branch = next(d for d in drafts if variant_of[d.id] == "chunk64")
    cycle.decide(
        chunk64_branch,
        decision="regress",
        rationale=(
            f"beaten by stream: chunk64 improvement "
            f"{entry_by_variant['chunk64'].improvement_ratio} met threshold but "
            "ranked 2 (stream ranked 1)"
        ),
    )
    cycle.decide(
        chunk256_branch,
        decision="regress",
        rationale=(
            f"below threshold: chunk256 improvement "
            f"{entry_by_variant['chunk256'].improvement_ratio} < "
            f"{THRESHOLD_IMPROVEMENT}; FailureAnalysis {fa_threshold.id} sealed "
            f"with regression test {CHUNK256_REGRESSION_TEST_REF}"
        ),
    )
    cycle.decide(
        kill_branch,
        decision="kill",
        rationale=(
            "audit killed: TransactionSemanticsRule + DeclaredReversibilityRule "
            f"failures; FailureAnalysis {fa_killed.id} sealed"
        ),
    )

    # 9. Founder ratification over the proposal fingerprint (gated act).
    ratification_approval = authority.issue_approval(content_hash(proposal))
    founder_ratify(
        spine,
        authority,
        proposal,
        approval=ratification_approval,
        actor_id="uniimente-kernel",
        organ_id="evolution-organ",
    )

    # 10. Seal: capsule file + ClosureLoop + EvolutionCapsule (ADR-8 order).
    loop, capsule = cycle.seal_capsule(capsule_path, verdict, capsule_ref=capsule_ref)

    # Post-seal checks: chain verifies, capsule matches its sealed hash, all
    # three decision types present, ratification event sealed.
    chain_ok = spine.verify_chain()
    capsule_text = capsule_path.read_text(encoding="utf-8")
    capsule_doc = json.loads(capsule_text)
    capsule_hash_ok = sha256_hex(capsule_text.encode("utf-8")) == capsule.capsule_hash
    records = list(spine.iter())
    capsule_record = records[-1]
    sealed_head_ok = (
        capsule_record["kind"] == "EvolutionCapsule"
        and capsule_record["prev_hash"] == capsule.sealed_head_hash
        and records[-2]["record_hash"] == capsule.sealed_head_hash
        and records[-2]["payload"]["id"] == loop.id
    )
    decision_counts = {"retain": 0, "regress": 0, "kill": 0}
    for rec in records:
        if rec["kind"] == "RetainRegressKillDecision":
            decision_counts[rec["payload"]["decision"]] += 1
    ratification_sealed = any(
        rec["kind"] == "RATIFICATION"
        and rec["refs"].get("proposal_id") == proposal.id
        and rec["refs"].get("approval_id") == ratification_approval.id
        for rec in records
    )
    ok = bool(
        episode.closed
        and episode.close_reason == "completed"
        and capsule_doc["ok"]
        and verdict == "baseline_beaten"
        and verifier.threshold_met
        and chain_ok
        and capsule_hash_ok
        and sealed_head_ok
        and decision_counts == {"retain": 1, "regress": 2, "kill": 1}
        and ratification_sealed
    )

    decisions_text = ",".join(
        f"{next(d.decision for d in cycle._decisions if d.branch_id == draft.id)}:"
        f"'{variant_of[draft.id]}'"
        for draft in drafts
    )
    print(
        "WP-06 FAST CYCLE: "
        f"ok={ok} "
        f"verdict={verdict} "
        f"cycle_index={CYCLE_INDEX} "
        f"baseline_value={verifier.baseline_value} "
        f"measured_value={verifier.measured_value} "
        f"improvement_ratio={verifier.improvement_ratio} "
        f"threshold_improvement={selected_spec.threshold_improvement} "
        f"threshold_met={verifier.threshold_met} "
        f"tests_green={verifier.reran_tests_green} "
        f"decisions={decisions_text} "
        f"records={len(records)} "
        f"chain_verified={chain_ok} "
        f"capsule_hash_ok={capsule_hash_ok} "
        f"ratification_sealed={ratification_sealed} "
        f"-> {capsule_ref}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
