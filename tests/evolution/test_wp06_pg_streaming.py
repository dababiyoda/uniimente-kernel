"""WP-06 pg.verify_chain_streaming suite (SPEC-WP06 4.6).

The ratified winner, adopted additively into kernel/spine/pg.py: BYTE-IDENTICAL
verdict parity with verify_chain on the honest chain and ALL FOUR WP-04
anomaly fixtures; peak_buffered == 1 on the 1000-record pinned chain; a
single closing commit on every verdict path; fail-closed False on connection
error; empty chain True. verify_chain itself is untouched (the WP-04 19-test
suite stays green under the full-suite run).
"""
from __future__ import annotations

import pytest

from kernel.spine import PostgresSpine

from scripts import wp06_bench as bench
from tests.evolution.test_wp06_bench_matrix import _ANOMALIES


def fresh_spine():
    """Empty spine over a BufferTrackingConnection (no workload chain)."""
    store: dict[str, list[dict]] = {}
    conn = bench.BufferTrackingConnection(store)
    spine = PostgresSpine(bench.FAKE_DSN, table=bench.TABLE, connect=lambda dsn: conn)
    conn.reset()
    return spine, conn


def test_streaming_parity_with_verify_chain_on_honest_chain():
    spine, conn = bench.build_chain()
    conn.reset()
    assert spine.verify_chain() is True
    assert spine.verify_chain_streaming() is True


def test_streaming_peak_buffered_is_1_on_1000_records():
    spine, conn = bench.build_chain()
    conn.reset()
    assert spine.verify_chain_streaming() is True
    assert conn.peak_buffered == 1  # vs 1000 for verify_chain's fetchall
    assert conn.trace == ["select"] + ["fetchone"] * 1001 + ["commit"]
    # The untouched control still buffers the whole chain.
    spine2, conn2 = bench.build_chain()
    conn2.reset()
    assert spine2.verify_chain() is True
    assert conn2.peak_buffered == 1000


def test_streaming_uses_one_select_and_one_closing_commit():
    spine, conn = bench.build_chain()
    conn.reset()
    assert spine.verify_chain_streaming() is True
    assert conn.trace.count("select") == 1
    assert conn.commits == 1  # single closing commit


@pytest.mark.parametrize("anomaly", sorted(_ANOMALIES))
def test_streaming_parity_on_all_four_wp04_anomalies(anomaly):
    spine, conn = bench.build_chain()
    _ANOMALIES[anomaly](conn._store)
    conn.reset()
    reference = spine.verify_chain()
    commits_after_reference = conn.commits
    streamed = spine.verify_chain_streaming()
    assert reference is False
    assert streamed is False  # byte-identical verdict
    # The closing commit runs on every verdict path (exactly one more).
    assert conn.commits == commits_after_reference + 1


def test_streaming_fail_closed_on_connection_error():
    spine, conn = fresh_spine()
    spine.append(bench.PINNED_EVENTS[0])

    def boom(sql, params=()):
        raise bench.FakeDBError("connection dropped")

    conn.execute = boom
    assert spine.verify_chain_streaming() is False  # never raises
    assert spine.verify_chain() is False


def test_streaming_fail_closed_on_mid_stream_error():
    spine, conn = bench.build_chain()
    conn.reset()

    class MidStreamBoomCursor:
        def fetchone(self):
            raise bench.FakeDBError("mid-stream connection failure")

    original_execute = conn.execute

    def execute_with_boom(sql, params=()):
        if "FROM" in sql and "record_hash" in sql:
            return MidStreamBoomCursor()
        return original_execute(sql, params)

    conn.execute = execute_with_boom
    assert spine.verify_chain_streaming() is False


def test_streaming_empty_chain_is_true():
    spine, conn = fresh_spine()
    assert spine.verify_chain_streaming() is True
    assert spine.verify_chain() is True
    assert conn.commits == 2  # one closing commit per verifier call


def test_streaming_verdict_matches_harness_stream_strategy():
    """Sandbox-to-production parity: the incubated harness strategy and the
    ratified pg.py method agree on the honest chain and measure peak 1."""
    spine, conn = bench.build_chain()
    conn.reset()
    harness_verdict, harness_peak = bench.verify_stream(spine, conn)
    conn.reset()
    assert spine.verify_chain_streaming() is True
    assert harness_verdict is True
    assert harness_peak == 1.0
    assert conn.peak_buffered == 1
