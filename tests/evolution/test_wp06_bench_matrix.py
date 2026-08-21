"""WP-06 bench-matrix + adapter-matrix suite (SPEC-WP06 4.5 + 4.7).

Pins: peak rows exactly {fetchall: 1000, stream: 1, chunk64: 64, chunk256:
256}; every strategy verdict-True on the honest chain; verdict parity across
ALL strategies on ALL FOUR WP-04 anomaly fixtures (all False); the chain is
built via ONE append_many (op profile shows batch use); no_commit_stream is
measurable when called directly (the cycle simply never asks).

Adapter matrix shape: the WP-05 single-pair protocol is still accepted by an
extended-allowlist adapter; the matrix protocol is accepted; a wrong
per-variant value, wrong trace order, an unknown variant, and a sabotaged
harness (stream reports pinned 1 but buffers 1000) are all refused BEFORE the
receipt (fail closed).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from kernel.adapters.benchmark import BenchmarkAdapter
from kernel.authority.approvals import ApprovalService
from kernel.crypto.hashing import canonical_json
from kernel.gate import errors
from kernel.gate.pipeline import Gate
from kernel.spine import Spine
from kernel.ucl import Constitution, compile_policy_fn
from kernel.ucl.version import constitution_version_from_dir, policy_version

from scripts import wp06_bench as bench
from scripts.run_evolution_cycle import pinned_protocol as wp05_pinned_protocol
from scripts.run_fast_cycle import pinned_matrix_protocol
from tests.evolution.test_cycle import make_intent, make_spec
from tests.ucl.conftest import _locate_constitution_dir

REPO_ROOT = Path(__file__).resolve().parents[2]

ALLOWLIST = ("scripts/wp05_bench.py", "scripts/wp06_bench.py")


def build_world_wp06(tmp_path, *, repo_root=None):
    """Compiled constitution + gate + BenchmarkAdapter with the WP-06
    extended harness allowlist on a file spine (mirrors test_cycle.build_world).
    """
    constitution_dir = _locate_constitution_dir()
    model = Constitution.from_directory(constitution_dir, current_state="normal")
    versions = {
        "policy_version": policy_version(model),
        "constitution_version": constitution_version_from_dir(constitution_dir),
    }
    policy_fn = compile_policy_fn(model, **versions)
    spine = Spine(tmp_path / "spine")
    authority = ApprovalService(approver_id="founder")
    gate = Gate(
        versions["policy_version"],
        versions["constitution_version"],
        authority,
        spine,
        policy_fn=policy_fn,
    )
    kwargs = {"witness_public_key": authority.public_key, "harness_allowlist": ALLOWLIST}
    if repo_root is not None:
        kwargs["repo_root"] = repo_root
    adapter = BenchmarkAdapter(**kwargs)
    gate.register_adapter(adapter.adapter_id, adapter.public_key_hex)
    return {"spine": spine, "authority": authority, "gate": gate, "adapter": adapter}


def run_protocol_intent(w, protocol):
    intent = make_intent(make_spec("b" * 32)).model_copy(
        update={"expected_outcome": canonical_json(protocol)}
    )
    approval = w["authority"].issue_approval(w["gate"].fingerprint(intent))
    return w["gate"].run(intent, adapter=w["adapter"], approval=approval)


# ------------------------------------------------------------- harness pins


def test_chain_built_via_one_append_many_batch():
    spine, conn = bench.build_chain()
    assert len(conn._store[bench.TABLE]) == bench.CHAIN_LEN == 1000
    # The batch profile: ONE lock, ONE head read, 1000 inserts, ONE commit.
    assert conn.trace.count("lock") == 1
    assert conn.trace.count("head") == 1
    assert conn.trace.count("insert") == 1000
    assert conn.trace.count("commit") == 1
    assert conn.trace[0] == "lock" and conn.trace[-1] == "commit"
    assert spine.verify_chain() is True


def test_baseline_peak_is_exactly_1000_with_pinned_trace():
    value, trace = bench.measure_baseline()
    assert value == bench.BASELINE_VALUE == 1000.0
    assert trace == bench.BASELINE_TRACE == ["select", "fetchall", "commit"]


def test_matrix_peaks_and_traces_exact():
    values, traces = bench.measure_matrix()
    assert values == {"stream": 1.0, "chunk64": 64.0, "chunk256": 256.0}
    assert values == bench.VARIANT_PEAKS
    assert traces == bench.VARIANT_TRACES
    assert traces["stream"] == ["select"] + ["fetchone"] * 1001 + ["commit"]
    assert traces["chunk64"].count("fetchmany") == 17  # 16 batches + terminator
    assert traces["chunk256"].count("fetchmany") == 5  # 4 batches + terminator


def test_all_strategies_verdict_true_on_honest_chain():
    for variant in bench.STRATEGIES:
        verdict, peak, trace = bench.run_strategy(variant)
        assert verdict is True, variant


def test_no_commit_stream_measurable_when_called_directly():
    verdict, peak, trace = bench.run_strategy("no_commit_stream")
    assert verdict is True
    assert peak == 1.0
    assert "commit" not in trace  # the dangerous property, honestly visible
    assert trace == bench.NO_COMMIT_STREAM_TRACE


def test_unknown_variant_is_a_harness_error():
    with pytest.raises(bench.HarnessError, match="unknown variant"):
        bench.run_strategy("chunk1024")


_ANOMALIES = {
    "flipped_payload_byte": lambda store: store[bench.TABLE][0]["payload"].__setitem__(
        "actor_id", store[bench.TABLE][0]["payload"]["actor_id"] + "X"
    ),
    "broken_prev_hash_link": lambda store: store[bench.TABLE][1].__setitem__(
        "prev_hash", "f" * 64
    ),
    "seq_gap": lambda store: store[bench.TABLE][1].__setitem__("seq", 5),
    "extra_key_in_row": lambda store: store[bench.TABLE][0].__setitem__("smuggled", True),
}


@pytest.mark.parametrize("anomaly", sorted(_ANOMALIES))
def test_verdict_parity_all_strategies_all_anomalies(anomaly):
    spine, conn = bench.build_chain()
    _ANOMALIES[anomaly](conn._store)
    conn.reset()
    reference = spine.verify_chain()
    assert reference is False  # the frozen WP-04 reference detects it
    for variant in ("stream", "chunk64", "chunk256", "no_commit_stream"):
        verdict, _peak = bench.STRATEGIES[variant](spine, conn)
        assert verdict is False, (anomaly, variant)


def test_chunk256_peak_rows_below_threshold_regression_pin():
    """THE pinned regression test referenced by the chunk256 FailureAnalysis
    (SPEC-WP06 3.5): chunk256's measured improvement is BELOW the
    pre-registered 0.90 threshold — this test failing means the metric moved.
    """
    verdict, peak, _trace = bench.run_strategy("chunk256")
    assert verdict is True
    assert peak == 256.0
    improvement = (bench.BASELINE_VALUE - peak) / bench.BASELINE_VALUE
    assert improvement == 0.744
    assert improvement < bench.THRESHOLD_IMPROVEMENT == 0.90


# ------------------------------------------------------- adapter matrix shape


def test_adapter_accepts_the_matrix_protocol(tmp_path):
    w = build_world_wp06(tmp_path)
    episode = run_protocol_intent(w, pinned_matrix_protocol())
    assert episode.closed and episode.close_reason == "completed"
    assert w["adapter"].calls == 1
    (receipt,) = [r for r in w["spine"].iter() if r["kind"] == "ExecutionReceipt"]
    import json

    facts = json.loads(receipt["payload"]["external_id"])
    assert facts["workload_id"] == bench.WORKLOAD_ID
    assert facts["metric"] == bench.METRIC_ID
    assert facts["baseline_value"] == 1000.0
    assert facts["candidate_variant"] == "stream"
    assert facts["candidate_value"] == 1.0
    assert facts["variant_values"] == {"stream": 1.0, "chunk64": 64.0, "chunk256": 256.0}
    assert w["spine"].verify_chain() is True


def test_adapter_still_accepts_the_wp05_single_pair_protocol(tmp_path):
    w = build_world_wp06(tmp_path)
    episode = run_protocol_intent(w, wp05_pinned_protocol())
    assert episode.closed and episode.close_reason == "completed"
    assert w["adapter"].calls == 1


def test_adapter_refuses_wrong_per_variant_value(tmp_path):
    w = build_world_wp06(tmp_path)
    protocol = pinned_matrix_protocol()
    protocol["variant_values"]["stream"] = 2.0
    with pytest.raises(errors.ExecutionRefusal, match="contradicts the pinned protocol"):
        run_protocol_intent(w, protocol)
    assert w["adapter"].calls == 0
    assert [r for r in w["spine"].iter() if r["kind"] == "ExecutionReceipt"] == []


def test_adapter_refuses_wrong_trace_order(tmp_path):
    w = build_world_wp06(tmp_path)
    protocol = pinned_matrix_protocol()
    protocol["variant_traces"]["stream"] = ["commit"] + bench.STREAM_TRACE[:-1]
    with pytest.raises(errors.ExecutionRefusal, match="trace order mismatch"):
        run_protocol_intent(w, protocol)
    assert w["adapter"].calls == 0


def test_adapter_refuses_unknown_variant_in_protocol(tmp_path):
    w = build_world_wp06(tmp_path)
    protocol = pinned_matrix_protocol()
    protocol["variant_values"]["chunk1024"] = 1024.0
    protocol["variant_traces"]["chunk1024"] = ["select", "commit"]
    with pytest.raises(errors.ExecutionRefusal, match="unknown variants in protocol"):
        run_protocol_intent(w, protocol)
    assert w["adapter"].calls == 0


def test_adapter_refuses_candidate_variant_outside_the_matrix(tmp_path):
    w = build_world_wp06(tmp_path)
    protocol = pinned_matrix_protocol()
    protocol["candidate_variant"] = "no_commit_stream"
    with pytest.raises(errors.ExecutionRefusal, match="candidate_variant"):
        run_protocol_intent(w, protocol)
    assert w["adapter"].calls == 0


def test_sabotaged_harness_stream_buffers_1000_is_refused(tmp_path):
    """Hostile: a harness whose 'stream' secretly fetchalls (buffers 1000)
    while the protocol pins 1 — the adapter refuses BEFORE the receipt."""
    root = tmp_path / "sabotaged-repo"
    (root / "scripts").mkdir(parents=True)
    (root / "kernel" / "spine").mkdir(parents=True)
    source = (REPO_ROOT / "scripts" / "wp06_bench.py").read_text(encoding="utf-8")
    sabotaged = source + "\n# SABOTAGE: stream secretly buffers the whole chain\nSTRATEGIES['stream'] = STRATEGIES['fetchall']\n"
    (root / "scripts" / "wp06_bench.py").write_text(sabotaged, encoding="utf-8")
    shutil.copy(REPO_ROOT / "kernel" / "spine" / "pg.py", root / "kernel" / "spine" / "pg.py")
    w = build_world_wp06(tmp_path / "world", repo_root=root)
    with pytest.raises(errors.ExecutionRefusal, match="contradicts the pinned protocol"):
        run_protocol_intent(w, pinned_matrix_protocol())
    assert w["adapter"].calls == 0
    assert [r for r in w["spine"].iter() if r["kind"] == "ExecutionReceipt"] == []
