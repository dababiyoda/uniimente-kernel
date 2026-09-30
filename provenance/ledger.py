"""Evidence Ledger: append-only, hash-chained institutional memory.

The provenance backbone for Layer 3 receipts and Layer 10 cryptographic
institutional memory. Every record carries the hash of its predecessor;
the genesis record anchors the constitution hash, so the entire chain is
bound to the exact doctrine that authorized it.

Negative evidence is kept. Nothing is ever deleted; corrections are new
records with correction ancestry (Layer 10 adds signatures and Merkle
batching on top of this chain).
"""
from __future__ import annotations

import hashlib
import json
import os
import copy
import fcntl
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

GENESIS_PREV = "sha256:" + "0" * 64


class ReconciliationRequired(RuntimeError):
    """Persistence may have succeeded. Reopen and inspect; do not blindly retry."""


class WriterConflict(RuntimeError):
    """This POSIX ledger supports exactly one writer process."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_json(obj) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


@dataclass
class LedgerRecord:
    seq: int
    ts_utc: str
    record_type: str          # event | witness | receipt | outcome | seal | correction | decision
    payload: dict
    prev_hash: str
    hash: str
    corrects: str | None = None   # hash of the record this corrects (correction ancestry)
    hash_version: int = 1


TAIL_POLICIES = ("refuse", "ignore", "quarantine")


class EvidenceLedger:
    """Append-only hash chain. In-memory by default; optional JSONL persistence.

    ``tail`` decides what to do with a final line that has no newline. ``append``
    acknowledges a record only after the whole line and its newline are fsynced,
    so such a line was never acknowledged: it is a write torn by power loss or a
    crash, or a write still in progress in another process.

    * ``refuse`` (default): fail closed, as before.
    * ``ignore``: read-only observers load the complete prefix and report the tail
      in ``unacknowledged_tail``. A reader racing the writer no longer fails.
    * ``quarantine``: the writer copies the torn bytes to a sidecar file, truncates
      the ledger to its last complete line and appends a ``recovery`` record. The
      bytes are preserved, never silently discarded.

    A malformed complete line is corruption under every policy and is refused.
    """

    def __init__(self, constitution_hash: str, path: str | None = None,
                 *, read_only: bool = False, expected_head: str | None = None,
                 tail: str = "refuse"):
        self.path = path
        self.constitution_hash = constitution_hash
        self.read_only = read_only
        self._lock = threading.RLock()
        self._writer = None
        self._pid = os.getpid()
        self._uncertain = False
        self._closed = False
        self.unacknowledged_tail: dict | None = None
        if tail not in TAIL_POLICIES:
            raise ValueError(f'unknown tail policy {tail!r}')
        if tail == "quarantine" and read_only:
            raise ValueError('a read-only observer cannot quarantine history; use tail="ignore"')
        self._tail_policy = tail
        if not isinstance(constitution_hash, str) or not constitution_hash.strip():
            raise ValueError('expected constitutional anchor is required')
        if path and not read_only:
            self._writer = open(path + '.lock', 'a')
            try:
                fcntl.flock(self._writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                self.close()
                raise WriterConflict('ledger already has a writer') from exc
        self.records: list[LedgerRecord] = []
        genesis_payload = {"kind": "genesis", "constitution_hash": constitution_hash}
        gh = sha256_json({"seq": 0, "payload": genesis_payload, "prev_hash": GENESIS_PREV})
        self.records.append(LedgerRecord(0, _now(), "genesis", genesis_payload, GENESIS_PREV, gh))
        try:
            if path and os.path.exists(path):
                self._load(path)
            elif path:
                if read_only or expected_head:
                    raise ValueError('expected history is missing')
                with open(path, "x", encoding="utf-8") as fh:
                    fh.write(json.dumps(asdict(self.records[0])) + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
            if expected_head and self.head != expected_head:
                raise ValueError('history differs from expected head: truncation or fork')
            if self.unacknowledged_tail and self._tail_policy == "quarantine":
                self._quarantine_tail()
        except Exception:
            self.close()
            raise

    def _quarantine_tail(self) -> None:
        """Move never-acknowledged bytes aside, keep them, and record the recovery."""
        tail = self.unacknowledged_tail
        data = tail.pop("_bytes")
        sidecar = f"{self.path}.unacknowledged-{tail['sha256'][7:23]}"
        try:
            fd = os.open(sidecar, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            with open(sidecar, "rb") as fh:
                if fh.read() != data:
                    raise ValueError('a different quarantined tail already uses this name')
        else:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
        with open(self.path, "r+b") as fh:
            fh.truncate(tail["offset"])
            fh.flush()
            os.fsync(fh.fileno())
        tail["sidecar"] = sidecar
        self.append("recovery", {
            "kind": "unacknowledged_tail_quarantined", "offset": tail["offset"], "bytes": tail["bytes"],
            "sha256": tail["sha256"], "sidecar": os.path.basename(sidecar),
            "meaning": "a write that was never acknowledged (torn by power loss or crash); its bytes are kept "
                       "in the sidecar for reconciliation and were not replayed"})

    def close(self):
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        self._closed = True

    def __del__(self):
        if hasattr(self, '_writer'):
            self.close()

    @property
    def head(self) -> str:
        return self.records[-1].hash

    def append(self, record_type: str, payload: dict, *, corrects: str | None = None) -> LedgerRecord:
        with self._lock:
            return self._append(record_type, payload, corrects=corrects)

    def _append(self, record_type: str, payload: dict, *, corrects=None):
        if self.read_only or self._closed or os.getpid() != self._pid:
            raise WriterConflict('not the active ledger writer')
        if self._uncertain:
            raise ReconciliationRequired('previous append is uncertain; reopen verified history')
        ok, reason = self.verify_chain()
        if not ok:
            raise ValueError(reason)
        if record_type in ('genesis', 'constitution_transition'):
            raise ValueError('unsupported constitutional transition; separate authority decision required')
        # Snapshot caller data. Integrity does not establish truth or permission.
        payload = json.loads(json.dumps(payload, allow_nan=False))
        if not isinstance(payload, dict):
            raise ValueError('ledger payload must be an object')
        seq = len(self.records)
        prev = self.head
        ts = _now()
        body = {"seq": seq, "record_type": record_type, "payload": payload,
                "prev_hash": prev, "corrects": corrects, 'ts_utc': ts, 'hash_version': 2}
        h = sha256_json(body)
        rec = LedgerRecord(seq, ts, record_type, payload, prev, h, corrects, 2)
        if self.path:
            # Opening failure is definite; after write starts, acknowledgment is
            # uncertain until flush/fsync finish. Never advance memory early.
            with open(self.path, "a", encoding="utf-8") as fh:
                try:
                    fh.write(json.dumps(asdict(rec), allow_nan=False) + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
                except OSError as exc:
                    self._uncertain = True
                    raise ReconciliationRequired('append acknowledgment lost') from exc
        self.records.append(rec)
        return copy.deepcopy(rec)

    def seal(self, *, sealed_by: str, reason: str) -> LedgerRecord:
        """Seal the head (shutdown propagation step 5). Returns the seal record."""
        return self.append("seal", {"sealed_by": sealed_by, "reason": reason, "head": self.head})

    def verify_chain(self) -> tuple[bool, str]:
        """Independently reconstruct and verify every link (evidence closure)."""
        if not self.records:
            return False, 'empty history'
        for i, rec in enumerate(self.records):
            if type(rec.seq) is not int or rec.seq != i:
                return False, f"sequence break at {i}"
            if (type(rec.payload) is not dict or type(rec.hash_version) is not int
                    or rec.hash_version not in (1, 2)):
                return False, f'unsupported record at {i}'
            if rec.record_type == 'constitution_transition':
                return False, 'unsupported amendment history: authority not established'
            if i == 0:
                expected = {'kind': 'genesis', 'constitution_hash': self.constitution_hash}
                if (rec.prev_hash != GENESIS_PREV or rec.record_type != 'genesis'
                        or rec.payload != expected or rec.corrects is not None
                        or rec.hash_version != 1):
                    return False, "genesis structure or expected constitution mismatch"
                if sha256_json({'seq': 0, 'payload': expected, 'prev_hash': GENESIS_PREV}) != rec.hash:
                    return False, 'genesis hash mismatch'
                continue
            if rec.record_type == 'genesis':
                return False, 'second genesis refused'
            if rec.prev_hash != self.records[i - 1].hash:
                return False, f"chain break at seq {i}"
            body = {"seq": rec.seq, "record_type": rec.record_type, "payload": rec.payload,
                    "prev_hash": rec.prev_hash, "corrects": rec.corrects}
            if rec.hash_version == 2:
                body.update(ts_utc=rec.ts_utc, hash_version=2)
            if sha256_json(body) != rec.hash:
                return False, f"payload hash mismatch at seq {i}"
        return True, f"chain intact: {len(self.records)} records"

    def find(self, record_hash: str) -> LedgerRecord | None:
        for r in self.records:
            if r.hash == record_hash:
                return r
        return None

    def by_type(self, record_type: str) -> list[LedgerRecord]:
        return [r for r in self.records if r.record_type == record_type]

    def _load(self, path: str) -> None:
        # Durable history supplies transition truth only after full verification.
        # Hash consistency is not factual appraisal, permission or authentication.
        loaded = []
        with open(path, "rb") as fh:
            raw = fh.read()
        complete_end = raw.rfind(b"\n") + 1
        if complete_end < len(raw):
            if self._tail_policy == "refuse":
                raise ValueError('partial or blank history record')
            torn = raw[complete_end:]
            self.unacknowledged_tail = {"offset": complete_end, "bytes": len(torn),
                                        "sha256": "sha256:" + hashlib.sha256(torn).hexdigest(),
                                        "_bytes": torn}
        try:
            from adapters.contract_validation import strict_json
            for chunk in raw[:complete_end].split(b"\n")[:-1]:
                line = chunk.decode("utf-8") + "\n"
                if not line.strip():
                    raise ValueError('partial or blank history record')
                d = strict_json(line)
                loaded.append(LedgerRecord(**d))
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError('malformed retained history') from exc
        if self.unacknowledged_tail and self._tail_policy == "ignore":
            self.unacknowledged_tail.pop("_bytes")
        self.records = loaded
        ok, msg = self.verify_chain()
        if not ok:
            raise ValueError(f"ledger at {path} failed verification on load: {msg}")
