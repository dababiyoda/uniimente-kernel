"""WP-05 BenchmarkAdapter + bench determinism + end-to-end cycle suite.

Bench determinism pins (SPEC-WP05 3.4): baseline is EXACTLY 40 ops, candidate
EXACTLY 13, traces match the pinned op order, and the harness module sha256 is
stable across runs. Hostile tests fail closed: non-allowlisted harness_ref,
protocol/trace mismatch, verifier rerun disagreement, tampered capsule file,
and witness-less adapter calls (Hard Rule 1 regression).

The end-to-end test runs ``run_evolution_cycle.main()`` in-process against a
temp file spine (--skip-test-rerun avoids recursive pytest; the sealed record
then honestly carries reran_tests_green=False).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from kernel.adapters.benchmark import BenchmarkAdapter
from kernel.authority.approvals import ApprovalService
from kernel.crypto.hashing import canonical_json, sha256_hex
from kernel.evolution import CycleError
from kernel.gate import errors
from kernel.gate.pipeline import Gate
from kernel.spine import Spine
from kernel.ucl import Constitution, compile_policy_fn
from kernel.ucl.version import constitution_version_from_dir, policy_version

from scripts import run_evolution_cycle
from scripts import wp05_bench as bench
from scripts.run_evolution_cycle import make_branches, pinned_protocol
from tests.evolution.test_cycle import build_world, make_intent, make_spec
from tests.ucl.conftest import _locate_constitution_dir

HARNESS_PATH = Path(__file__).resolve().parents[2] / "scripts" / "wp05_bench.py"


# ------------------------------------------------------------ bench pins


def test_24_bench_baseline_is_exactly_40_ops():
    ops, trace = bench.measure_baseline()
    assert ops == bench.BASELINE_OPS == 40
    assert trace == bench.BASELINE_TRACE


def test_25_bench_candidate_is_exactly_13_ops():
    ops, trace = bench.measure_candidate()
    assert ops == bench.CANDIDATE_OPS == 13
    assert trace == bench.CANDIDATE_TRACE


def test_26_bench_traces_match_pinned_op_order():
    _, baseline_trace = bench.measure_baseline()
    _, candidate_trace = bench.measure_candidate()
    assert baseline_trace == ["lock", "head", "insert", "commit"] * 10
    assert candidate_trace == ["lock", "head"] + ["insert"] * 10 + ["commit"]


def test_27_harness_module_sha256_stable_across_runs():
    first = sha256_hex(HARNESS_PATH.read_bytes())
    second = sha256_hex(HARNESS_PATH.read_bytes())
    assert first == second
    assert len(first) == 64


# ------------------------------------------------------ adapter hostility


def _run_protocol_intent(w, protocol) -> None:
    intent = make_intent(make_spec("b" * 32)).model_copy(
        update={"expected_outcome": canonical_json(protocol)}
    )
    approval = w["authority"].issue_approval(w["gate"].fingerprint(intent))
    w["gate"].run(intent, adapter=w["adapter"], approval=approval)


def test_28_adapter_refuses_non_allowlisted_harness_ref(tmp_path):
    w = build_world(tmp_path)
    protocol = {**pinned_protocol(), "harness_ref": "scripts/evil.py"}
    with pytest.raises(errors.ExecutionRefusal, match="not in the benchmark allowlist"):
        _run_protocol_intent(w, protocol)
    assert w["adapter"].calls == 0
    assert [r for r in w["spine"].iter() if r["kind"] == "ExecutionReceipt"] == []
    assert w["spine"].verify_chain() is True


def test_29_adapter_raises_on_protocol_op_trace_mismatch(tmp_path):
    w = build_world(tmp_path)
    # Pinned counts disagree with what the harness actually executes.
    bad_counts = {**pinned_protocol(), "candidate_ops": 12}
    with pytest.raises(errors.ExecutionRefusal, match="contradicts the pinned protocol"):
        _run_protocol_intent(w, bad_counts)
    # Pinned trace ORDER disagrees with the executed workload.
    w2 = build_world(tmp_path / "second")
    bad_trace = {
        **pinned_protocol(),
        "candidate_trace": ["head", "lock"] + ["insert"] * 10 + ["commit"],
    }
    with pytest.raises(errors.ExecutionRefusal, match="contradicts the pinned protocol"):
        _run_protocol_intent(w2, bad_trace)
    assert w2["adapter"].calls == 0
    assert w2["spine"].verify_chain() is True


def test_30_direct_adapter_call_without_witness_refused(tmp_path):
    w = build_world(tmp_path)
    adapter = w["adapter"]
    # (a) Protocol level: witness is a required argument.
    with pytest.raises(TypeError):
        adapter.execute()
    # (b) No witness, no execute (Hard Rule 1).
    with pytest.raises(errors.WitnessMissing):
        adapter.execute(None)
    # (c) A non-witness object is refused.
    with pytest.raises(errors.WitnessRefusal):
        adapter.execute({"intent_fingerprint": "f" * 64})
    assert adapter.calls == 0


# --------------------------------------------- verifier + capsule hostility


def _run_through_experiment(tmp_path):
    """Stages 1-5 of the cycle against a fresh world; returns context."""
    w = build_world(tmp_path)
    cycle = w["cycle"]
    branches = list(make_branches())
    tree = cycle.propose_tree("objective", "wp05", "rule", branches)
    b1, b2, b3 = branches
    audits = run_evolution_cycle.run_audits(cycle, branches)
    cycle.select(tree, audits)
    spec = make_spec(b1.id)
    cycle.register_experiment(spec)
    intent = make_intent(spec)
    approval = w["authority"].issue_approval(w["gate"].fingerprint(intent))
    episode = cycle.run_experiment(intent, w["adapter"], approval)
    return w, branches, spec, episode


def test_31_verifier_rerun_value_mismatch_raises_cycleerror(tmp_path):
    w, branches, spec, episode = _run_through_experiment(tmp_path)
    before = w["spine"].next_seq
    with pytest.raises(CycleError, match="contradicts the adapter-attested"):
        w["cycle"].verify(
            spec,
            lambda: (40.0, 12.0),  # lying re-run: candidate was 13.0
            verifier_id="verifier:test",
            tests_green=False,
        )
    assert w["spine"].next_seq == before  # fail closed: nothing sealed
    assert [r for r in w["spine"].iter() if r["kind"] == "VerifierRecord"] == []


def test_32_tampered_capsule_file_detected_via_capsule_hash(tmp_path):
    w, branches, spec, episode = _run_through_experiment(tmp_path)
    cycle = w["cycle"]
    verifier = cycle.verify(
        spec,
        lambda: (40.0, 13.0),
        verifier_id="verifier:test",
        tests_green=False,
    )
    assert verifier.threshold_met is True
    b1, b2, b3 = branches
    cycle.decide(b1, decision="retain", rationale="r", threshold_met=True)
    cycle.decide(b2, decision="kill", rationale="killed")
    cycle.decide(b3, decision="kill", rationale="killed")
    capsule_path = tmp_path / "capsule.json"
    loop, capsule = cycle.seal_capsule(capsule_path, "baseline_beaten")

    # Honest file matches the sealed hash; one flipped byte breaks it.
    text = capsule_path.read_text(encoding="utf-8")
    assert sha256_hex(text.encode("utf-8")) == capsule.capsule_hash
    tampered = text.replace('"baseline_beaten"', '"baseline_held"', 1)
    capsule_path.write_text(tampered, encoding="utf-8")
    assert sha256_hex(tampered.encode("utf-8")) != capsule.capsule_hash
    # The sealed head attestation is verifiable on-chain.
    records = list(w["spine"].iter())
    assert records[-1]["kind"] == "EvolutionCapsule"
    assert records[-1]["prev_hash"] == capsule.sealed_head_hash
    assert records[-2]["payload"]["id"] == loop.id
    assert w["spine"].verify_chain() is True


# ------------------------------------------------------------- end to end


def test_33_run_evolution_cycle_end_to_end(tmp_path):
    capsule_path = tmp_path / "wp05_evolution_capsule.json"
    spine_dir = tmp_path / "spine-root"
    rc = run_evolution_cycle.main(
        [
            "--capsule",
            str(capsule_path),
            "--spine-dir",
            str(spine_dir),
            "--skip-test-rerun",
        ]
    )
    assert rc == 0
    capsule = json.loads(capsule_path.read_text(encoding="utf-8"))
    assert capsule["ok"] is True
    assert capsule["verdict"] == "baseline_beaten"
    assert capsule["baseline_value"] == 40.0
    assert capsule["measured_value"] == 13.0
    assert capsule["improvement_ratio"] == 0.675
    assert capsule["threshold_met"] is True
    outcomes = {d["outcome"] for d in capsule["decisions"]}
    assert outcomes == {"retain", "kill"}

    spine = Spine(spine_dir / "spine")
    kinds = {r["kind"] for r in spine.iter()}
    for kind in (
        "StrategyBranch",
        "StrategyTree",
        "SpiderWebAudit",
        "ExperimentSpec",
        "VerifierRecord",
        "RetainRegressKillDecision",
        "ClosureLoop",
        "EvolutionCapsule",
    ):
        assert kind in kinds
    assert spine.verify_chain() is True
