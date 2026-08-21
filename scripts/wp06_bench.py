#!/usr/bin/env python3
"""WP-06 bench harness — the pinned, hermetic matrix workload (SPEC-WP06 3.6).

Measures PEAK BUFFERED ROWS during chain verification on a 1000-record pinned
chain, against an in-memory fake DBAPI — NO DSN, no network, no wall clock
anywhere in the measurement (Hard Rule 5: the metric is a deterministic
invariant, verifier hierarchy level 1).

    Workload:  CHAIN_LEN = 1000 pinned events appended with ONE
               ``append_many`` (WP-05 dogfood: the previous cycle's retained
               win accelerates this one), then conn.reset().
    Baseline:  verify_fetchall  — current behavior (iter(): fetchall buffers
               the whole chain, then Python verify)  -> peak 1000
    Variants (harness-local sandbox incubation, SPEC-WP06 ADR-2):
               stream            SELECT + fetchone loop + commit -> peak 1
               chunk64           fetchmany(64) loop  + commit    -> peak 64
               chunk256          fetchmany(256) loop + commit    -> peak 256
               no_commit_stream  stream without the closing commit (the cycle
                                 audit-kills its branch pre-experiment and
                                 never asks for it; the harness CAN still run
                                 it when asked directly)

Every strategy returns the chain verdict along with peak buffered rows; a
strategy whose verdict differs from the frozen reference verdict
(``verify_fetchall`` on the same chain) is a HARNESS ERROR — the harness
never lets the system's opinion of itself serve as proof.

``BufferTrackingConnection`` extends the WP-05 CountingConnection idea: the
same SQL dispatch, op counting and honest transaction emulation, PLUS a
buffer tracker — fetchall sets buffered = len(rows), fetchone sets 1 (0 when
exhausted), fetchmany(k) sets <= k — with ``peak_buffered`` recorded.

The module doubles as the BenchmarkAdapter's pinned WP-06 harness: the
adapter loads it by path and calls ``measure_baseline()`` /
``measure_matrix()``, then verifies the baseline value, per-variant values
AND trace order against the pinned matrix protocol.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from kernel.contracts.institutional import InstitutionalEvent  # noqa: E402
from kernel.crypto.hashing import canonical_json, sha256_hex  # noqa: E402
from kernel.spine import GENESIS_HASH, PostgresSpine  # noqa: E402

FAKE_DSN = "dbname=wp06-bench"  # never opened; the tracking fake ignores it
TABLE = "spine_records"

WORKLOAD_ID = "verify1000-pinned-chain"
METRIC_ID = "pg_spine_verify_peak_rows"
METRIC_UNIT = "rows"
MEASURED_SOURCE = "kernel/spine/pg.py"  # the production code under measurement

CHAIN_LEN = 1000
BASELINE_VALUE = 1000.0  # fetchall buffers the whole chain
THRESHOLD_IMPROVEMENT = 0.90  # pre-registered in SPEC-WP06 3.5

_RECORD_KEYS = ("seq", "prev_hash", "kind", "refs", "payload")
_SELECT_ALL = (
    "SELECT seq, prev_hash, kind, refs, payload, record_hash "
    f"FROM {TABLE} ORDER BY seq ASC"
)

# Fully pinned events (fixed id + created_at) so every payload — and therefore
# every spine record hash — is deterministic across runs and machines.
_PINNED_BASE = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)

PINNED_EVENTS: list[InstitutionalEvent] = [
    InstitutionalEvent(
        event_type="WP06_BENCH_WORKLOAD",
        actor_id="wp06-bench",
        organ_id="evolution-organ",
        payload_hash=sha256_hex(f"wp06-pinned-event-{i}".encode("utf-8")),
        id=f"{i:032d}",
        created_at=_PINNED_BASE + timedelta(seconds=i),
    )
    for i in range(CHAIN_LEN)
]


class HarnessError(Exception):
    """The harness refuses: unknown variant, or a strategy verdict that
    contradicts the frozen reference verdict (Hard Rule 4, fail closed)."""


# ------------------------------------------------- buffer-tracking fake DBAPI


class FakeDBError(Exception):
    """Emulates a psycopg.OperationalError-style failure."""


class BufferTrackingCursor:
    """Advancing cursor that reports buffered-row counts to the connection."""

    def __init__(self, conn: "BufferTrackingConnection", rows):
        self._conn = conn
        self._rows = list(rows)
        self._pos = 0

    def fetchone(self):
        self._conn.trace.append("fetchone")
        if self._pos >= len(self._rows):
            self._conn._set_buffered(0)
            return None
        row = self._rows[self._pos]
        self._pos += 1
        self._conn._set_buffered(1)
        return row

    def fetchall(self):
        self._conn.trace.append("fetchall")
        remaining = self._rows[self._pos :]
        self._pos = len(self._rows)
        self._conn._set_buffered(len(remaining))
        return remaining

    def fetchmany(self, size: int):
        self._conn.trace.append("fetchmany")
        batch = self._rows[self._pos : self._pos + size]
        self._pos += len(batch)
        self._conn._set_buffered(len(batch))
        return batch


class BufferTrackingConnection:
    """Fake DBAPI connection + op counter + op trace + buffer tracker.

    Same SQL dispatch and honest transaction emulation as the WP-05
    CountingConnection (staged inserts are rolled back out of the store on
    ``rollback()``; DDL is construction, never counted nor traced), PLUS:
    every fetch reports the rows it buffers and ``peak_buffered`` tracks the
    maximum. ``fetchone`` ADVANCES (unlike the WP-05 one-row cursor) so
    streaming loops terminate honestly.
    """

    def __init__(self, store):
        self._store = store  # {table: [row dict, ...]}
        self._pending: list[tuple[str, dict]] = []  # uncommitted staged rows
        self.executes = 0
        self.commits = 0
        self.rollbacks = 0
        self.trace: list[str] = []
        self.buffered = 0
        self.peak_buffered = 0

    @property
    def op_count(self) -> int:
        """Connection ops since the last reset: execute() + commit() calls."""
        return self.executes + self.commits

    def reset(self) -> None:
        """Zero counters, trace and buffer tracking (drops construction)."""
        self.executes = 0
        self.commits = 0
        self.rollbacks = 0
        self.trace = []
        self.buffered = 0
        self.peak_buffered = 0

    def _set_buffered(self, n: int) -> None:
        self.buffered = n
        self.peak_buffered = max(self.peak_buffered, n)

    def _count(self, label: str) -> None:
        self.executes += 1
        self.trace.append(label)

    def execute(self, sql, params=()):
        norm = " ".join(sql.split())
        m = re.match(r"CREATE TABLE IF NOT EXISTS (\w+)", norm)
        if m:
            # DDL is construction, not workload: neither counted nor traced.
            self._store.setdefault(m.group(1), [])
            return BufferTrackingCursor(self, [])
        if norm.startswith("SELECT pg_advisory_xact_lock"):
            self._count("lock")
            return BufferTrackingCursor(self, [])  # lock no-op; never fetched from
        m = re.match(r"SELECT seq, record_hash FROM (\w+) ORDER BY seq DESC", norm)
        if m:
            self._count("head")
            rows = self._store[m.group(1)]
            head = rows[-1] if rows else None
            return BufferTrackingCursor(
                self, [] if head is None else [(head["seq"], head["record_hash"])]
            )
        m = re.match(
            r"SELECT seq, prev_hash, kind, refs, payload, record_hash FROM (\w+)", norm
        )
        if m:
            self._count("select")
            rows = self._store[m.group(1)]
            if "WHERE seq = %s" in norm:
                rows = [r for r in rows if r["seq"] == params[0]]
            return BufferTrackingCursor(self, [dict(r) for r in rows])
        m = re.match(r"INSERT INTO (\w+)", norm)
        if m:
            self._count("insert")
            seq, prev_hash, kind, refs_json, payload_json, record_hash = params
            row = {
                "seq": seq,
                "prev_hash": prev_hash,
                "kind": kind,
                # JSONB decode emulation: values come back as objects.
                "refs": json.loads(refs_json),
                "payload": json.loads(payload_json),
                "record_hash": record_hash,
            }
            self._store[m.group(1)].append(row)
            self._pending.append((m.group(1), row))
            return BufferTrackingCursor(self, [])
        raise AssertionError(f"fake DB received unexpected SQL: {norm!r}")

    def commit(self):
        self.commits += 1
        self.trace.append("commit")
        self._pending.clear()

    def rollback(self):
        self.rollbacks += 1
        # Honest transaction emulation: uncommitted staged rows leave the store.
        for table, row in self._pending:
            self._store[table].remove(row)
        self._pending.clear()


# --------------------------------------------------------------- the workload


def build_chain() -> tuple[PostgresSpine, BufferTrackingConnection]:
    """Fresh store; the 1000-record chain built with ONE ``append_many``
    (WP-05 dogfood, SPEC-WP06 ADR-8). DDL is construction and reset away;
    the batch profile stays on the trace for the dogfood assertion.
    """
    store: dict[str, list[dict]] = {}
    conn = BufferTrackingConnection(store)
    spine = PostgresSpine(FAKE_DSN, table=TABLE, connect=lambda dsn: conn)
    conn.reset()  # DDL execute+commit are construction, not workload
    spine.append_many(list(PINNED_EVENTS))
    return spine, conn


def _verify_rows_python(records) -> bool:
    """The candidate's Python-side verification logic — BYTE-IDENTICAL in
    behavior to PostgresSpine.verify_chain's loop (hash formula, key set,
    seq continuity, prev_hash linkage). Harness-local on purpose: candidates
    incubate in the sandbox; only the ratified winner lands in pg.py.
    """
    expected_seq = 0
    prev = GENESIS_HASH
    for rec in records:
        if not isinstance(rec, dict) or set(rec.keys()) != set(_RECORD_KEYS) | {"record_hash"}:
            return False
        if rec["seq"] != expected_seq:
            return False
        if rec["prev_hash"] != prev:
            return False
        body = {k: rec[k] for k in _RECORD_KEYS}
        if sha256_hex(canonical_json(body).encode("utf-8")) != rec["record_hash"]:
            return False
        prev = rec["record_hash"]
        expected_seq += 1
    return True


# -------------------------------------------- variant strategies (sandboxed)


def verify_fetchall(spine: PostgresSpine, conn: BufferTrackingConnection):
    """The control: current behavior — iter() fetchall, then Python verify."""
    verdict = spine.verify_chain()
    return verdict, float(conn.peak_buffered)


def verify_stream(spine: PostgresSpine, conn: BufferTrackingConnection):
    """stream: SELECT + fetchone loop + a single closing commit -> peak 1."""
    cur = conn.execute(_SELECT_ALL)
    verdict = _verify_rows_python(iter(lambda: cur.fetchone(), None))
    conn.commit()
    return verdict, float(conn.peak_buffered)


def _verify_chunked(conn: BufferTrackingConnection, size: int):
    cur = conn.execute(_SELECT_ALL)

    def rows():
        while True:
            batch = cur.fetchmany(size)
            if not batch:
                return
            yield from batch

    verdict = _verify_rows_python(rows())
    conn.commit()
    return verdict, float(conn.peak_buffered)


def verify_chunk64(spine: PostgresSpine, conn: BufferTrackingConnection):
    """chunk64: fetchmany(64) loop + commit -> peak 64."""
    return _verify_chunked(conn, 64)


def verify_chunk256(spine: PostgresSpine, conn: BufferTrackingConnection):
    """chunk256: fetchmany(256) loop + commit -> peak 256."""
    return _verify_chunked(conn, 256)


def verify_no_commit_stream(spine: PostgresSpine, conn: BufferTrackingConnection):
    """no_commit_stream: stream WITHOUT the closing commit.

    The cycle audit-kills this branch pre-experiment and never asks for it;
    the harness can still run it when asked directly (it is measurable).
    """
    cur = conn.execute(_SELECT_ALL)
    verdict = _verify_rows_python(iter(lambda: cur.fetchone(), None))
    return verdict, float(conn.peak_buffered)  # deliberately NO commit


STRATEGIES = {
    "fetchall": verify_fetchall,
    "stream": verify_stream,
    "chunk64": verify_chunk64,
    "chunk256": verify_chunk256,
    "no_commit_stream": verify_no_commit_stream,
}

# The audit-passing variants the pinned matrix measures (the control is the
# baseline; no_commit_stream is audit-killed pre-experiment, never asked).
MATRIX_VARIANTS = ("stream", "chunk64", "chunk256")

# Pre-registered pins (SPEC-WP06 3.5): values AND full op-trace order.
# The chunk loops terminate on an empty fetchmany, so each trace carries one
# final empty-batch call after the ceil(CHAIN_LEN / size) row-bearing batches.
STREAM_TRACE = ["select"] + ["fetchone"] * (CHAIN_LEN + 1) + ["commit"]
CHUNK64_TRACE = ["select"] + ["fetchmany"] * (-(-CHAIN_LEN // 64) + 1) + ["commit"]
CHUNK256_TRACE = ["select"] + ["fetchmany"] * (-(-CHAIN_LEN // 256) + 1) + ["commit"]
NO_COMMIT_STREAM_TRACE = ["select"] + ["fetchone"] * (CHAIN_LEN + 1)
BASELINE_TRACE = ["select", "fetchall", "commit"]

VARIANT_PEAKS = {"stream": 1.0, "chunk64": 64.0, "chunk256": 256.0}
VARIANT_TRACES = {
    "stream": STREAM_TRACE,
    "chunk64": CHUNK64_TRACE,
    "chunk256": CHUNK256_TRACE,
}


def run_strategy(variant: str) -> tuple[bool, float, list[str]]:
    """Run one variant on a FRESH store (isolated testing, SPEC-WP06 1.2);
    returns (verdict, peak_buffered, trace). Unknown variant -> HarnessError.
    """
    strategy = STRATEGIES.get(variant)
    if strategy is None:
        raise HarnessError(f"unknown variant {variant!r}; fail closed")
    spine, conn = build_chain()
    conn.reset()  # the chain build is setup, not measurement
    verdict, peak = strategy(spine, conn)
    return verdict, peak, list(conn.trace)


def measure_baseline() -> tuple[float, list[str]]:
    """The control measurement: (1000.0, BASELINE_TRACE)."""
    verdict, peak, trace = run_strategy("fetchall")
    if verdict is not True:
        raise HarnessError(
            "baseline verdict contradicts the frozen reference (True); harness error"
        )
    return peak, trace


def measure_matrix(variants=MATRIX_VARIANTS) -> tuple[dict[str, float], dict[str, list[str]]]:
    """The matrix measurement over the audit-passing variants, each on a
    fresh store. A strategy whose verdict differs from the frozen reference
    verdict is a harness error (Hard Rule 4).
    """
    reference_verdict, _, _ = run_strategy("fetchall")
    values: dict[str, float] = {}
    traces: dict[str, list[str]] = {}
    for variant in variants:
        verdict, peak, trace = run_strategy(variant)
        if verdict != reference_verdict:
            raise HarnessError(
                f"variant {variant!r} verdict {verdict} contradicts the frozen "
                f"reference verdict {reference_verdict}; harness error"
            )
        values[variant] = peak
        traces[variant] = trace
    return values, traces


if __name__ == "__main__":
    baseline_value, baseline_trace = measure_baseline()
    values, traces = measure_matrix()
    print(
        "WP-06 BENCH: "
        f"workload_id={WORKLOAD_ID} metric={METRIC_ID} "
        f"baseline_peak_rows={baseline_value} "
        f"variant_peaks={values} "
        f"traces_ok={baseline_trace == BASELINE_TRACE and traces == VARIANT_TRACES}"
    )
