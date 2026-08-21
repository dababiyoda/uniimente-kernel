"""WP-04 PostgresSpine suite — in-memory fake DBAPI only, NO live database.

The FakeConnection/FakeCursor layer below emulates the exact psycopg v3
surface PostgresSpine uses (execute/fetchone/fetchall, advisory lock no-op,
commit/rollback) against a plain Python list store, including JSONB
value semantics (stored refs/payload come back decoded, as psycopg decodes
JSONB). It is injected via the ``connect`` callable parameter, so the driver
is never imported here.

Test 1 is the acceptance-critical hash-parity vector: the SAME fixed model
appended to the file Spine and to PostgresSpine-with-fake must produce a
byte-identical sealed record — the backends are interchangeable and proofs
are portable.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone

import pytest

from kernel.contracts.institutional import InstitutionalEvent
from kernel.crypto.hashing import canonical_json, sha256_hex
from kernel.spine import GENESIS_HASH, PostgresSpine, Spine, SpineError

FAKE_DSN = "dbname=fake"  # never opened; the fake connect ignores it
TABLE = "spine_records"

# A fully pinned model (fixed id + created_at) so payloads are deterministic
# across backends — the hash-parity vector depends on byte-identical inputs.
FIXED_CREATED_AT = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)


def fixed_event(**overrides) -> InstitutionalEvent:
    fields = dict(
        event_type="REBUILD_DRILL",
        actor_id="agent-7",
        organ_id="research-organ",
        payload_hash="a" * 64,
        id="b" * 32,
        created_at=FIXED_CREATED_AT,
    )
    fields.update(overrides)
    return InstitutionalEvent(**fields)


# ------------------------------------------------------------- fake DBAPI


class FakeDBError(Exception):
    """Emulates a psycopg.OperationalError-style mid-transaction failure."""


class FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class FakeConnection:
    """Emulates the exact SQL surface PostgresSpine issues, over a list store.

    Rows are stored as dicts keyed by column name. refs/payload arrive at
    INSERT as canonical JSON strings (the ``%s::jsonb`` parameters) and are
    stored DECODED, emulating psycopg's JSONB-to-dict decode on SELECT.
    """

    def __init__(self, store, *, fail_on_insert=False):
        self._store = store  # {table: [row dict, ...]}
        self.fail_on_insert = fail_on_insert
        self.commits = 0
        self.rollbacks = 0

    def execute(self, sql, params=()):
        norm = " ".join(sql.split())
        m = re.match(r"CREATE TABLE IF NOT EXISTS (\w+)", norm)
        if m:
            self._store.setdefault(m.group(1), [])
            return FakeCursor([])
        if norm.startswith("SELECT pg_advisory_xact_lock"):
            return FakeCursor([])  # lock no-op; never fetched from
        m = re.match(r"SELECT seq, record_hash FROM (\w+) ORDER BY seq DESC", norm)
        if m:
            rows = self._store[m.group(1)]
            head = rows[-1] if rows else None
            return FakeCursor([] if head is None else [(head["seq"], head["record_hash"])])
        m = re.match(
            r"SELECT seq, prev_hash, kind, refs, payload, record_hash FROM (\w+)", norm
        )
        if m:
            rows = self._store[m.group(1)]
            if "WHERE seq = %s" in norm:
                rows = [r for r in rows if r["seq"] == params[0]]
            return FakeCursor([dict(r) for r in rows])
        m = re.match(r"INSERT INTO (\w+)", norm)
        if m:
            if self.fail_on_insert:
                raise FakeDBError("simulated mid-append connection failure")
            seq, prev_hash, kind, refs_json, payload_json, record_hash = params
            self._store[m.group(1)].append(
                {
                    "seq": seq,
                    "prev_hash": prev_hash,
                    "kind": kind,
                    # JSONB decode emulation: values come back as objects.
                    "refs": json.loads(refs_json),
                    "payload": json.loads(payload_json),
                    "record_hash": record_hash,
                }
            )
            return FakeCursor([])
        raise AssertionError(f"fake DB received unexpected SQL: {norm!r}")

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def make_fake_connect(store=None, **conn_kwargs):
    """A ``connect`` factory whose connections share one store (reopen-safe)."""
    if store is None:
        store = {}

    def fake_connect(dsn):
        return FakeConnection(store, **conn_kwargs)

    return fake_connect


def pg_spine(store=None, *, table=TABLE, **conn_kwargs) -> PostgresSpine:
    return PostgresSpine(FAKE_DSN, table=table, connect=make_fake_connect(store, **conn_kwargs))


# --------------------------------------------------------------- the tests


def test_01_append_get_iter_parity_and_hash_vector_matches_file_spine(tmp_path):
    """THE hash-parity vector: identical appends -> identical record_hash."""
    file_spine = Spine(tmp_path / "spine")
    pg = pg_spine()

    file_record = file_spine.append(fixed_event(), refs={"origin": "wp04-vector"})
    pg_record = pg.append(fixed_event(), refs={"origin": "wp04-vector"})

    # Byte-identical sealed records across both backends.
    assert pg_record == file_record
    # And the hash matches the frozen WP-01 formula computed by hand.
    body = {k: pg_record[k] for k in ("seq", "prev_hash", "kind", "refs", "payload")}
    assert pg_record["record_hash"] == sha256_hex(canonical_json(body).encode("utf-8"))
    # get/iter round-trip with file-spine record shapes.
    assert pg.get(0) == file_record
    assert list(pg.iter()) == [file_record]
    assert pg.get(999) is None


def test_02_chain_continuity_across_reopen():
    store = {}
    first = pg_spine(store)
    first.append(fixed_event())
    head = first.append(fixed_event(id="c" * 32))["record_hash"]

    second = pg_spine(store)  # same fake store, new instance
    assert second.next_seq == 2
    rec = second.append(fixed_event(id="d" * 32))
    assert rec["seq"] == 2
    assert rec["prev_hash"] == head  # chain continues from the prior head
    assert second.verify_chain() is True


def test_03_verify_chain_true_on_honest_data_and_empty_spine_works():
    pg = pg_spine()
    # Empty-spine read paths must work.
    assert pg.get(0) is None
    assert list(pg.iter()) == []
    assert pg.verify_chain() is True
    assert pg.next_seq == 0

    for i in range(3):
        pg.append(fixed_event(id=f"{i}" * 32))
    assert pg.verify_chain() is True
    assert pg.next_seq == 3


def test_04_verify_chain_false_on_flipped_payload_byte():
    store = {}
    pg = pg_spine(store)
    pg.append(fixed_event())
    pg.append(fixed_event(id="c" * 32))
    # Tamper: flip payload bytes in the stored row (storage-level attack).
    store[TABLE][0]["payload"]["actor_id"] += "X"
    assert pg.verify_chain() is False


def test_04b_verify_chain_false_on_broken_prev_hash_link():
    store = {}
    pg = pg_spine(store)
    pg.append(fixed_event())
    pg.append(fixed_event(id="c" * 32))
    store[TABLE][1]["prev_hash"] = "f" * 64
    assert pg.verify_chain() is False


def test_04c_verify_chain_false_on_seq_gap():
    store = {}
    pg = pg_spine(store)
    pg.append(fixed_event())
    pg.append(fixed_event(id="c" * 32))
    store[TABLE][1]["seq"] = 5
    assert pg.verify_chain() is False


def test_04d_verify_chain_false_on_extra_key_in_row():
    store = {}
    pg = pg_spine(store)
    pg.append(fixed_event())
    # Fake store injects a bad row carrying an extra key.
    store[TABLE][0]["smuggled"] = True
    assert pg.verify_chain() is False


def test_05_append_rejects_non_kernel_model():
    pg = pg_spine()
    with pytest.raises(TypeError, match="KernelModel"):
        pg.append({"not": "a model"})
    with pytest.raises(TypeError, match="KernelModel"):
        pg.append("InstitutionalEvent")


def test_06_institutional_event_gets_spine_seq_assigned_on_append():
    pg = pg_spine()
    event = fixed_event()
    assert event.spine_seq == -1  # not yet sequenced
    record = pg.append(event)
    assert record["payload"]["spine_seq"] == 0
    record2 = pg.append(fixed_event(id="c" * 32))
    assert record2["payload"]["spine_seq"] == 1
    # The caller's frozen model is never mutated.
    assert event.spine_seq == -1


@pytest.mark.parametrize("bad", ["bad;DROP", "1bad", "", "a" * 64, "Bad", "has space"])
def test_07_table_name_validation_rejects_unsafe_identifiers(bad):
    with pytest.raises(ValueError, match="invalid spine table name"):
        PostgresSpine(FAKE_DSN, table=bad, connect=make_fake_connect())


def test_08_driver_missing_raises_spine_error_with_guidance(monkeypatch):
    # Force the lazy `import psycopg` in the constructor to fail.
    monkeypatch.setitem(sys.modules, "psycopg", None)
    with pytest.raises(SpineError, match=r"pip install 'psycopg\[binary\]'"):
        PostgresSpine(FAKE_DSN)  # no connect= -> real driver path


def test_09_mid_append_failure_rolls_back_no_partial_row():
    store = {}
    connect = make_fake_connect(store, fail_on_insert=False)
    pg = PostgresSpine(FAKE_DSN, connect=connect)
    pg.append(fixed_event())
    head_before = pg.get(0)["record_hash"]

    # Toggle the live fake connection into failing mode, mid-life.
    pg._conn.fail_on_insert = True
    with pytest.raises(SpineError, match="append failed"):
        pg.append(fixed_event(id="c" * 32))

    # Rolled back: no partial row, chain head unchanged, chain still verifies.
    assert len(store[TABLE]) == 1
    assert pg._conn.rollbacks >= 1
    assert pg.get(0)["record_hash"] == head_before
    assert pg.next_seq == 1
    assert pg.verify_chain() is True


def test_10_genesis_append_has_genesis_prev_hash_and_seq_zero():
    pg = pg_spine()
    record = pg.append(fixed_event())
    assert record["seq"] == 0
    assert record["prev_hash"] == GENESIS_HASH == "0" * 64


def test_11_append_record_rebuild_path_revalidates_replayed_records():
    """The rebuild-only API: faithful replay is accepted, tampering refused."""
    origin = pg_spine()
    records = [origin.append(fixed_event(id=f"{i}" * 32)) for i in range(3)]

    rebuilt = pg_spine(table="wp04_rebuilt")
    for rec in records:
        accepted = rebuilt.append_record(rec)
        assert accepted == rec
    assert [r["record_hash"] for r in rebuilt.iter()] == [r["record_hash"] for r in records]
    assert rebuilt.verify_chain() is True

    # A tampered replayed record is refused (hash re-validated pre-accept).
    tampered = dict(records[1], payload={**records[1]["payload"], "actor_id": "mallory"})
    with pytest.raises(SpineError, match="hash mismatch"):
        pg_spine(table="wp04_rebuilt2").append_record(tampered)  # wrong seq too
    fresh = pg_spine(table="wp04_rebuilt3")
    fresh.append_record(records[0])
    with pytest.raises(SpineError, match="hash mismatch"):
        fresh.append_record(tampered)
    # Out-of-order replay is refused (chain continuity enforced).
    with pytest.raises(SpineError, match="seq"):
        fresh.append_record(records[2])
