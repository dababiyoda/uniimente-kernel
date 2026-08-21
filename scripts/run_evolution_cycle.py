#!/usr/bin/env python3
"""WP-05 First Evolution Cycle — one sealed improvement cycle beating baseline.

Runs the full eight-stage ClosureLoop on a FILE spine in a temp dir (ADR-7:
hermetic proof; Postgres-resident cycles are a later WP), with the compiled
WP-02 constitution driving the gate, the BenchmarkAdapter executing the
pinned WP-05 bench protocol under a founder approval, and the terminal
RetainRegressKillDecision set sealed per branch.

Stages (SPEC-WP05 3.2), all machine-recorded on the spine:
    1. propose_tree   — B1 (append_many), B2 (server-side hashing),
                        B3 (connection pooling), scores pre-registered in
                        SPEC-WP05 3.4
    2. audit          — SpiderWebAudit kills B2 and B3, passes B1
    3. select         — the selection rule picks B1
    4. register       — ExperimentSpec sealed BEFORE any execution
    5. run_experiment — the ONLY gated side effect (C2, REQUIRE_HUMAN,
                        founder approval)
    6. verify         — independent re-run of both harnesses + test suite
    7. decide         — retain B1 (iff threshold met), kill B2, kill B3
    8. seal_capsule   — proof/wp05_evolution_capsule.json + ClosureLoop +
                        EvolutionCapsule (ADR-8 dual-reference order)

Hermetic: no DSN, no network, no credentials anywhere. Determinism: measured
facts are op counts on a fake DBAPI; the verdict line carries stable scalars
only. Exit 0 only if the cycle completed, the verdict is baseline_beaten,
the capsule verifies against its sealed hash, and the spine chain verifies.

Usage (from the slice root):
    python scripts/run_evolution_cycle.py

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
    AuditFinding,
    ExperimentSpec,
    StrategyBranch,
)
from kernel.crypto.hashing import canonical_json, sha256_hex  # noqa: E402
from kernel.evolution import EvolutionCycle  # noqa: E402
from kernel.gate.pipeline import Gate  # noqa: E402
from kernel.spine import Spine  # noqa: E402
from kernel.ucl import Constitution, compile_policy_fn  # noqa: E402
from kernel.ucl.version import constitution_version_from_dir, policy_version  # noqa: E402

from scripts import wp05_bench as bench  # noqa: E402

CAPSULE_PATH = REPO_ROOT / "proof" / "wp05_evolution_capsule.json"
CAPSULE_REF = "proof/wp05_evolution_capsule.json"
HARNESS_REF = "scripts/wp05_bench.py"
CYCLE_INDEX = 1
THRESHOLD_IMPROVEMENT = 0.5  # pre-registered in SPEC-WP05 3.4

SELECTION_RULE = (
    "max scores.expected_value among audit-passing branches with "
    "scores.risk <= 0.3 and scores.reversibility >= 0.8; ties -> lower scores.cost"
)


def make_branches() -> tuple[StrategyBranch, StrategyBranch, StrategyBranch]:
    """The three operator-authored branch drafts of SPEC-WP05 3.4 (exact scores)."""
    b1 = StrategyBranch(
        title="Batch append API (append_many)",
        hypothesis="bulk append ops drop by >=50% via one transaction per batch",
        metric_id=bench.METRIC_ID,
        expected_delta=-0.5,
        scores={"expected_value": 0.8, "risk": 0.1, "reversibility": 1.0, "cost": 0.2},
    )
    b2 = StrategyBranch(
        title="Server-side hash chaining in SQL",
        hypothesis="hash chaining inside Postgres removes Python round-trips",
        metric_id=bench.METRIC_ID,
        expected_delta=-0.6,
        scores={"expected_value": 0.6, "risk": 0.9, "reversibility": 0.4, "cost": 0.5},
    )
    b3 = StrategyBranch(
        title="Connection pooling for parallel appends",
        hypothesis="parallel writers hide append latency",
        metric_id=bench.METRIC_ID,
        expected_delta=-0.3,
        scores={"expected_value": 0.5, "risk": 0.8, "reversibility": 0.3, "cost": 0.7},
    )
    return b1, b2, b3


def run_audits(cycle: EvolutionCycle, branches) -> list:
    """SPEC-WP05 3.4: B2 and B3 are KILLED by the audit; B1 passes all."""
    b1, b2, b3 = branches
    a1 = cycle.audit(
        b1.id,
        "operator",
        [
            AuditFinding(
                dimension="correctness_risk",
                attack="frozen hash formula replicated per record",
                result="pass",
                note="hash-parity test proves byte-identical records vs append",
            ),
            AuditFinding(
                dimension="governance_risk",
                attack="additive-only change to WP-04 surface",
                result="pass",
                note="zero edits to any previously verified method",
            ),
            AuditFinding(
                dimension="regression_risk",
                attack="single-transaction batch semantics",
                result="pass",
                note="all-or-nothing rollback proven by test",
            ),
            AuditFinding(
                dimension="reversibility",
                attack="purely additive API; removal is a delete",
                result="pass",
            ),
        ],
    )
    a2 = cycle.audit(
        b2.id,
        "operator",
        [
            AuditFinding(
                dimension="correctness_risk",
                attack="database becomes a trusted verifier",
                result="fail",
                note="violates WP-04 ADR-1; JSONB key-order canonicalization "
                "hazard; non-portable hashes",
            ),
            AuditFinding(
                dimension="governance_risk",
                attack="hash verification leaves Python-side auditability",
                result="fail",
                note="the database is storage, never a trusted verifier",
            ),
        ],
    )
    a3 = cycle.audit(
        b3.id,
        "operator",
        [
            AuditFinding(
                dimension="regression_risk",
                attack="multiplies writer connections against a single-chain "
                "advisory-lock design",
                result="fail",
                note="writer serialization regression risk",
            ),
            AuditFinding(
                dimension="reversibility",
                attack="benefit unproven at current scale",
                result="fail",
                note="reverting pooled writers mid-flight is not clean",
            ),
        ],
    )
    return [a1, a2, a3]


def pinned_protocol() -> dict:
    """The pre-registered pinned protocol document (carried by the witness)."""
    return {
        "workload_id": bench.WORKLOAD_ID,
        "harness_ref": HARNESS_REF,
        "baseline_ops": bench.BASELINE_OPS,
        "candidate_ops": bench.CANDIDATE_OPS,
        "metric": bench.METRIC_ID,
        "baseline_trace": bench.BASELINE_TRACE,
        "candidate_trace": bench.CANDIDATE_TRACE,
    }


def rerun_harnesses() -> tuple[float, float]:
    """The verifier's independent re-execution of both harnesses."""
    baseline_ops, _ = bench.measure_baseline()
    candidate_ops, _ = bench.measure_candidate()
    return float(baseline_ops), float(candidate_ops)


def rerun_test_suite() -> bool:
    """Honestly re-run the full test suite as a subprocess (hermetic)."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


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
    spine_dir = Path(args.spine_dir) if args.spine_dir else Path(tempfile.mkdtemp(prefix="wp05-spine-"))

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
    adapter = BenchmarkAdapter(witness_public_key=authority.public_key)
    gate.register_adapter(adapter.adapter_id, adapter.public_key_hex)
    cycle = EvolutionCycle(
        gate,
        spine,
        authority,
        actor_id="uniimente-kernel",
        organ_id="evolution-organ",
        cycle_index=CYCLE_INDEX,
    )

    # 1-3. Tree, audits (B2/B3 killed), selection (B1 wins).
    branches = make_branches()
    tree = cycle.propose_tree(
        "Reduce connection-operation count of bulk appends on PostgresSpine",
        "wp05",
        SELECTION_RULE,
        list(branches),
    )
    audits = run_audits(cycle, branches)
    selected = cycle.select(tree, audits)
    b1, b2, b3 = branches
    if selected.id != b1.id:
        print(f"REFUSAL: selection picked {selected.title!r}, expected B1", file=sys.stderr)
        return 1

    # 4. Pre-registered ExperimentSpec, sealed BEFORE any execution.
    spec = ExperimentSpec(
        branch_id=b1.id,
        metric_id=bench.METRIC_ID,
        metric_unit=bench.METRIC_UNIT,
        baseline_value=float(bench.BASELINE_OPS),
        threshold_improvement=THRESHOLD_IMPROVEMENT,
        direction="decrease",
        harness_ref=HARNESS_REF,
        workload_id=bench.WORKLOAD_ID,
        pre_registered=True,
    )
    cycle.register_experiment(spec)

    # 5. The ONLY gated side effect: C2 evolution_experiment, founder approval.
    intent = ActionIntent(
        actor_id="uniimente-kernel",
        organ_id="evolution-organ",
        legal_principal="Uniimente Ltd",
        objective=(
            "WP-05 evolution cycle: measure PostgresSpine append_many vs "
            "sequential append connection ops on the pinned workload"
        ),
        action_type="evolution_experiment",
        resource="kernel",
        target="bench://wp05/pg-spine-bulk-append",
        payload={"experiment_spec_id": spec.id},
        consequence_class="C2",
        evidence_ids=[],
        expected_outcome=canonical_json(pinned_protocol()),
        rollback=None,
        expiry_minutes=30,
    )
    approval = authority.issue_approval(gate.fingerprint(intent))
    episode = cycle.run_experiment(intent, adapter, approval)

    # 6. Independent verification: harness re-run + test suite re-run.
    # --skip-test-rerun seals reran_tests_green=False honestly (the in-process
    # end-to-end test uses it to avoid recursive pytest).
    tests_green = rerun_test_suite() if not args.skip_test_rerun else False
    verifier = cycle.verify(
        spec,
        rerun_harnesses,
        verifier_id="verifier:independent-rerun",
        tests_green=tests_green,
    )

    # 7. Terminal decisions: retain B1 (iff threshold met), kill B2, kill B3.
    verdict = "baseline_beaten" if verifier.threshold_met else "baseline_held"
    cycle.decide(
        b1,
        decision="retain" if verifier.threshold_met else "regress",
        rationale=(
            f"measured improvement {verifier.improvement_ratio} "
            f">= pre-registered threshold {spec.threshold_improvement}"
            if verifier.threshold_met
            else "threshold unmet; branch regressed to draft"
        ),
        threshold_met=verifier.threshold_met,
        revert_plan="append_many is additive; removal deletes one method",
    )
    cycle.decide(
        b2,
        decision="kill",
        rationale="audit killed: violates WP-04 ADR-1 (database is never a "
        "trusted verifier); JSONB canonicalization hazard",
    )
    cycle.decide(
        b3,
        decision="kill",
        rationale="audit killed: multiplies writers against the single-chain "
        "advisory-lock design; benefit unproven at current scale",
    )

    # 8. Seal: capsule file + ClosureLoop + EvolutionCapsule (ADR-8 order).
    loop, capsule = cycle.seal_capsule(capsule_path, verdict, capsule_ref=capsule_ref)

    # Post-seal checks: chain verifies, capsule file matches its sealed hash.
    chain_ok = spine.verify_chain()
    capsule_text = capsule_path.read_text(encoding="utf-8")
    capsule_doc = json.loads(capsule_text)
    capsule_hash_ok = sha256_hex(capsule_text.encode("utf-8")) == capsule.capsule_hash
    # The sealed head attestation is verifiable on-chain: it is the capsule
    # record's prev_hash (= head after the ClosureLoop seal append).
    records = list(spine.iter())
    capsule_record = records[-1]
    sealed_head_ok = (
        capsule_record["kind"] == "EvolutionCapsule"
        and capsule_record["prev_hash"] == capsule.sealed_head_hash
        and records[-2]["record_hash"] == capsule.sealed_head_hash
        and records[-2]["payload"]["id"] == loop.id
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
    )

    print(
        "WP-05 EVOLUTION CYCLE: "
        f"ok={ok} "
        f"verdict={verdict} "
        f"cycle_index={CYCLE_INDEX} "
        f"baseline_value={verifier.baseline_value} "
        f"measured_value={verifier.measured_value} "
        f"improvement_ratio={verifier.improvement_ratio} "
        f"threshold_improvement={spec.threshold_improvement} "
        f"threshold_met={verifier.threshold_met} "
        f"tests_green={verifier.reran_tests_green} "
        f"decisions=retain:{b1.title!r},kill:{b2.title!r},kill:{b3.title!r} "
        f"records={len(records)} "
        f"chain_verified={chain_ok} "
        f"capsule_hash_ok={capsule_hash_ok} "
        f"-> {capsule_ref}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
