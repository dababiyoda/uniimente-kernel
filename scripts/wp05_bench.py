#!/usr/bin/env python3
"""WP-05 bench harness — the pinned, hermetic op-count workload (SPEC-WP05 3.5).

Measures the connection-operation cost of bulk appends on ``PostgresSpine``
against an in-memory fake DBAPI — NO DSN, no network, no wall clock anywhere
in the measurement (Hard Rule 5: the metric is deterministic by construction).

    Baseline  (existing, untouched): 10 x ``append``
              = 10 x (lock + head + insert + commit) = 40 ops
    Candidate (WP-05 additive):     1 x ``append_many``
              = 1 lock + 1 head + 10 inserts + 1 commit   = 13 ops

``CountingConnection`` extends the WP-04 FakeConnection idea with an op
counter and an op trace, plus honest transaction emulation: staged inserts
are rolled back out of the store on ``rollback()``. DDL (CREATE TABLE and its
commit) is construction, not workload: it is never counted nor traced.

The module doubles as the BenchmarkAdapter's pinned harness: the adapter
loads it by path and calls ``measure_baseline()`` / ``measure_candidate()``,
then verifies counts AND trace order against the pinned protocol.
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
from kernel.crypto.hashing import sha256_hex  # noqa: E402
from kernel.spine import PostgresSpine  # noqa: E402

FAKE_DSN = "dbname=wp05-bench"  # never opened; the counting fake ignores it
TABLE = "spine_records"

WORKLOAD_ID = "append10-pinned-events"
METRIC_ID = "pg_spine_bulk_append_ops"
METRIC_UNIT = "connection_ops"
MEASURED_SOURCE = "kernel/spine/pg.py"  # the production code under measurement

BASELINE_OPS = 40
CANDIDATE_OPS = 13
BASELINE_TRACE = ["lock", "head", "insert", "commit"] * 10
CANDIDATE_TRACE = ["lock", "head"] + ["insert"] * 10 + ["commit"]

# Fully pinned events (fixed id + created_at) so every payload — and therefore
# every spine record hash — is deterministic across runs and machines.
_PINNED_BASE = datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)

PINNED_EVENTS: list[InstitutionalEvent] = [
    InstitutionalEvent(
        event_type="WP05_BENCH_WORKLOAD",
        actor_id="wp05-bench",
        organ_id="evolution-organ",
        payload_hash=sha256_hex(f"wp05-pinned-event-{i}".encode("utf-8")),
        id=f"{i:032d}",
        created_at=_PINNED_BASE + timedelta(seconds=i),
    )
    for i in range(10)
]


# ------------------------------------------------------- counting fake DBAPI


class FakeDBError(Exception):
    """Emulates a psycopg.OperationalError-style mid-transaction failure."""


class FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class CountingConnection:
    """Fake DBAPI connection + op counter + op trace, over a list store.

    Emulates the exact SQL surface PostgresSpine issues (same dispatch as the
    WP-04 fake), and additionally: counts every execute() and commit() as one
    connection op, appends a label to the op trace, and stages inserts so a
    ``rollback()`` honestly undoes the uncommitted batch. Set
    ``fail_at_insert`` to raise FakeDBError on the k-th insert since the last
    reset (mid-batch failure injection). DDL ops are never counted.
    """

    def __init__(self, store):
        self._store = store  # {table: [row dict, ...]}
        self._pending: list[tuple[str, dict]] = []  # uncommitted staged rows
        self.fail_at_insert: int | None = None
        self.executes = 0
        self.commits = 0
        self.rollbacks = 0
        self.trace: list[str] = []
        self._inserts_since_reset = 0

    @property
    def op_count(self) -> int:
        """Connection ops since the last reset: execute() + commit() calls."""
        return self.executes + self.commits

    def reset(self) -> None:
        """Zero the counters and trace (drops construction/DDL from counts)."""
        self.executes = 0
        self.commits = 0
        self.rollbacks = 0
        self.trace = []
        self._inserts_since_reset = 0

    def _count(self, label: str) -> None:
        self.executes += 1
        self.trace.append(label)

    def execute(self, sql, params=()):
        norm = " ".join(sql.split())
        m = re.match(r"CREATE TABLE IF NOT EXISTS (\w+)", norm)
        if m:
            # DDL is construction, not workload: neither counted nor traced.
            self._store.setdefault(m.group(1), [])
            return FakeCursor([])
        if norm.startswith("SELECT pg_advisory_xact_lock"):
            self._count("lock")
            return FakeCursor([])  # lock no-op; never fetched from
        m = re.match(r"SELECT seq, record_hash FROM (\w+) ORDER BY seq DESC", norm)
        if m:
            self._count("head")
            rows = self._store[m.group(1)]
            head = rows[-1] if rows else None
            return FakeCursor([] if head is None else [(head["seq"], head["record_hash"])])
        m = re.match(
            r"SELECT seq, prev_hash, kind, refs, payload, record_hash FROM (\w+)", norm
        )
        if m:
            self._count("select")
            rows = self._store[m.group(1)]
            if "WHERE seq = %s" in norm:
                rows = [r for r in rows if r["seq"] == params[0]]
            return FakeCursor([dict(r) for r in rows])
        m = re.match(r"INSERT INTO (\w+)", norm)
        if m:
            self._count("insert")
            if (
                self.fail_at_insert is not None
                and self._inserts_since_reset == self.fail_at_insert
            ):
                raise FakeDBError("simulated mid-batch connection failure")
            self._inserts_since_reset += 1
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
            return FakeCursor([])
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


def _fresh_spine() -> tuple[PostgresSpine, CountingConnection]:
    store: dict[str, list[dict]] = {}
    conn = CountingConnection(store)
    spine = PostgresSpine(FAKE_DSN, table=TABLE, connect=lambda dsn: conn)
    conn.reset()  # DDL execute+commit are construction, not workload
    return spine, conn


def measure_baseline() -> tuple[int, list[str]]:
    """10 sequential ``append`` calls over the pinned events -> (40, trace)."""
    spine, conn = _fresh_spine()
    for event in PINNED_EVENTS:
        spine.append(event)
    return conn.op_count, list(conn.trace)


def measure_candidate() -> tuple[int, list[str]]:
    """One ``append_many`` over the pinned events -> (13, trace)."""
    spine, conn = _fresh_spine()
    spine.append_many(list(PINNED_EVENTS))
    return conn.op_count, list(conn.trace)


if __name__ == "__main__":
    baseline_ops, baseline_trace = measure_baseline()
    candidate_ops, candidate_trace = measure_candidate()
    print(
        "WP-05 BENCH: "
        f"baseline_ops={baseline_ops} candidate_ops={candidate_ops} "
        f"improvement={(baseline_ops - candidate_ops) / baseline_ops} "
        f"baseline_trace_ok={baseline_trace == BASELINE_TRACE} "
        f"candidate_trace_ok={candidate_trace == CANDIDATE_TRACE}"
    )
