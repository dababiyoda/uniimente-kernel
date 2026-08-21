"""Postgres spine backend — same frozen contract as the JSONL file spine.

WP-04: puts the WP-01 spine interface on Postgres (Neon-hosted) so the
institution has a production-grade memory. The hash formula is FROZEN and
replicated exactly from ``kernel/spine/log.py``:

    record keys: ``seq``, ``prev_hash``, ``kind``, ``refs``, ``payload``,
                 ``record_hash``
    record_hash = sha256_hex(canonical_json({seq, prev_hash, kind, refs,
                                             payload}))
    GENESIS_HASH = "0"*64; seq starts at 0; prev_hash chains

Design rules (SPEC-WP04 section 6 ADRs):
1. All hash verification is Python-side — the database is storage, never a
   trusted verifier. ``verify_chain`` re-reads every row and re-verifies
   every hash and link.
2. Concurrent writers serialize on a Postgres advisory transaction lock
   (``pg_advisory_xact_lock(hashtext(table))``); the chain is single-table.
3. ``refs``/``payload`` are stored as JSONB. JSONB round-trips values, not
   key order; ``canonical_json`` re-sorts keys, so record hashes are stable
   regardless of JSONB internal ordering.
4. ``psycopg`` (v3) is imported LAZILY in the constructor; file-spine users
   and the test suite never require the driver. Tests inject a fake
   connection factory via the ``connect`` parameter.
5. ``append_record`` is a clearly-marked REBUILD-ONLY API used by the
   rebuild drill; it re-validates every replayed record before accepting.
6. Credentials only ever arrive via the ``dsn`` argument (read by the CALLER
   from the environment). This class never touches ``os.environ``.

There is deliberately NO update/delete API. Ever.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Iterator

from ..contracts.base import KernelModel
from ..contracts.institutional import InstitutionalEvent
from ..crypto.hashing import canonical_json, sha256_hex
from .log import GENESIS_HASH, SpineError

_RECORD_KEYS = ("seq", "prev_hash", "kind", "refs", "payload")
_COLUMNS = ("seq", "prev_hash", "kind", "refs", "payload", "record_hash")
_IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_MAX_IDENT_LEN = 63  # Postgres NAMEDATALEN limit

_DDL = """CREATE TABLE IF NOT EXISTS {table} (
  seq         BIGINT PRIMARY KEY,
  prev_hash   TEXT NOT NULL,
  kind        TEXT NOT NULL,
  refs        JSONB NOT NULL,
  payload     JSONB NOT NULL,
  record_hash TEXT NOT NULL
)"""

_PSYCOG_GUIDANCE = (
    "PostgresSpine requires the psycopg v3 driver; install it with: "
    "pip install 'psycopg[binary]'"
)


def _validate_table_name(table: str) -> str:
    """Validate a table identifier; reject anything not matching the strict
    lowercase identifier grammar (it is never format-interpolated otherwise).
    """
    if (
        not isinstance(table, str)
        or not table
        or len(table) > _MAX_IDENT_LEN
        or not _IDENT_RE.match(table)
    ):
        raise ValueError(
            f"invalid spine table name {table!r}: must match {_IDENT_RE.pattern} "
            f"and be <= {_MAX_IDENT_LEN} chars"
        )
    return table


class PostgresSpine:
    """Append-only hash-chained Postgres spine. Drop-in for ``Spine``.

    Same public interface: ``append(model, *, kind=None, refs=None)``,
    ``append_record(record)`` (REBUILD-ONLY), ``get(seq)``, ``iter()``,
    ``verify_chain()``, and the ``next_seq`` property.
    """

    def __init__(
        self,
        dsn: str,
        *,
        table: str = "spine_records",
        connect: Callable[..., Any] | None = None,
    ):
        self._table = _validate_table_name(table)
        if connect is None:
            try:
                import psycopg  # lazy: file-spine users never need the driver
            except ImportError as exc:
                raise SpineError(_PSYCOG_GUIDANCE) from exc
            connect = psycopg.connect
        self._dsn = dsn
        try:
            self._conn = connect(dsn)
            self._conn.execute(_DDL.format(table=self._table))
            self._conn.commit()
        except Exception as exc:
            raise SpineError(f"postgres spine init failed: {exc!r}") from exc

    # -------------------------------------------------------------- reads

    @property
    def next_seq(self) -> int:
        head = self._head()
        return 0 if head is None else int(head[0]) + 1

    def get(self, seq: int) -> dict[str, Any] | None:
        cur = self._conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM {self._table} WHERE seq = %s",
            (seq,),
        )
        row = cur.fetchone()
        self._conn.commit()
        return None if row is None else self._row_to_record(row)

    def iter(self) -> Iterator[dict[str, Any]]:
        cur = self._conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM {self._table} ORDER BY seq ASC"
        )
        rows = cur.fetchall()
        self._conn.commit()
        for row in rows:
            yield self._row_to_record(row)

    def verify_chain(self) -> bool:
        """Re-read every row and re-verify every hash and link in Python.

        Returns False on ANY anomaly — including connection failure during
        verify — and never raises (fail closed, Hard Rule 4).
        """
        try:
            expected_seq = 0
            prev = GENESIS_HASH
            for rec in self.iter():
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
        except Exception:
            return False

    # ------------------------------------------------------------- writes

    def append(
        self,
        model: KernelModel,
        *,
        kind: str | None = None,
        refs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append a contract to the chain and return the sealed record.

        Single transaction: advisory xact lock serializes writers, the head
        is read, the record is computed in Python with the EXACT WP-01
        formula, inserted, committed. Any error rolls back -> SpineError.
        """
        if not isinstance(model, KernelModel):
            raise TypeError("the spine stores KernelModel instances only")
        try:
            head = self._locked_head()
            seq = 0 if head is None else int(head[0]) + 1
            prev_hash = GENESIS_HASH if head is None else str(head[1])
            if isinstance(model, InstitutionalEvent):
                # spine_seq is assigned by the spine on append, never by callers.
                model = model.model_copy(update={"spine_seq": seq})
            body: dict[str, Any] = {
                "seq": seq,
                "prev_hash": prev_hash,
                "kind": kind or type(model).__name__,
                "refs": refs or {},
                "payload": model.model_dump(mode="json"),
            }
            record_hash = sha256_hex(canonical_json(body).encode("utf-8"))
            record = {**body, "record_hash": record_hash}
            self._insert(record)
            self._conn.commit()
            return record
        except Exception as exc:
            self._rollback_quietly()
            raise SpineError(f"postgres spine append failed: {exc!r}") from exc

    def append_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """REBUILD-ONLY: re-seal an existing spine record verbatim.

        Used by the rebuild drill to replay an origin chain into a fresh
        table. This is the honest rebuild mechanism: every replayed record
        is re-validated before acceptance — exact key set, record_hash must
        match the frozen WP-01 formula over its own five fields, seq must
        continue this table's chain, and prev_hash must equal this table's
        current head. A faithful replay therefore reproduces identical
        hashes; any tampered or out-of-order record is refused (SpineError).
        NOT a general write path: normal callers use ``append``.
        """
        if not isinstance(record, dict) or set(record.keys()) != set(_RECORD_KEYS) | {"record_hash"}:
            raise SpineError("rebuild record has wrong key set; refusing replay")
        body = {k: record[k] for k in _RECORD_KEYS}
        if sha256_hex(canonical_json(body).encode("utf-8")) != record["record_hash"]:
            raise SpineError("rebuild record hash mismatch; refusing replay")
        try:
            head = self._locked_head()
            expected_seq = 0 if head is None else int(head[0]) + 1
            expected_prev = GENESIS_HASH if head is None else str(head[1])
            if record["seq"] != expected_seq:
                raise SpineError(
                    f"rebuild record seq {record['seq']!r} != expected {expected_seq}; "
                    "refusing replay"
                )
            if record["prev_hash"] != expected_prev:
                raise SpineError("rebuild record prev_hash breaks the chain; refusing replay")
            self._insert(record)
            self._conn.commit()
            return dict(record)
        except SpineError:
            self._rollback_quietly()
            raise
        except Exception as exc:
            self._rollback_quietly()
            raise SpineError(f"postgres spine rebuild append failed: {exc!r}") from exc

    # ------------------------------------------------------------ internals

    def _locked_head(self) -> tuple | None:
        """Take the advisory xact lock, then read the chain head."""
        self._conn.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))", (self._table,)
        )
        cur = self._conn.execute(
            f"SELECT seq, record_hash FROM {self._table} ORDER BY seq DESC LIMIT 1"
        )
        return cur.fetchone()

    def _head(self) -> tuple | None:
        cur = self._conn.execute(
            f"SELECT seq, record_hash FROM {self._table} ORDER BY seq DESC LIMIT 1"
        )
        row = cur.fetchone()
        self._conn.commit()
        return row

    def _insert(self, record: dict[str, Any]) -> None:
        self._conn.execute(
            f"INSERT INTO {self._table} "
            f"(seq, prev_hash, kind, refs, payload, record_hash) "
            f"VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s)",
            (
                record["seq"],
                record["prev_hash"],
                record["kind"],
                canonical_json(record["refs"]),
                canonical_json(record["payload"]),
                record["record_hash"],
            ),
        )

    @staticmethod
    def _decode_jsonb(value: Any) -> Any:
        # Real psycopg decodes JSONB to Python objects; the fake layer (and
        # any text-protocol path) may hand back a JSON string. Accept both.
        if isinstance(value, str):
            return json.loads(value)
        return value

    def _row_to_record(self, row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            rec = dict(row)
        else:
            rec = dict(zip(_COLUMNS, row))
        if "refs" in rec:
            rec["refs"] = self._decode_jsonb(rec["refs"])
        if "payload" in rec:
            rec["payload"] = self._decode_jsonb(rec["payload"])
        if "seq" in rec and rec["seq"] is not None:
            rec["seq"] = int(rec["seq"])
        return rec

    def _rollback_quietly(self) -> None:
        try:
            self._conn.rollback()
        except Exception:
            pass
