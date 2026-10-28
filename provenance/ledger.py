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
import sys
import threading
import time
from array import array
from collections.abc import Sequence
from dataclasses import dataclass, asdict, fields
from datetime import datetime, timezone

GENESIS_PREV = "sha256:" + "0" * 64
# Hot paths verify only records not yet verified; the whole chain is still reconstructed on open,
# on every explicit verify_chain(), and at least this often (FINDING-LEDGER-APPEND-COST-2026-10-14).
FULL_VERIFY_SECONDS = 300.0
_monotonic = time.monotonic
# A Commit Witness is the Consequence Gate's durability boundary (policy/consequence_gate.py step 9, before the
# dispatch claim and the executor). It is appended only onto a chain reconstructed whole at that moment, so no
# effect is witnessed, claimed or executed on history altered in memory. The check lives here because the Gate's
# source is a reviewed, hash-bound subject (evolution/repair/subjects.py SR-002) and so cannot change silently
# (installed-body merge; FINDING-LEDGER-APPEND-COST-2026-10-14).
COMMIT_RECORD_TYPES = ("witness",)
# A file-backed ledger keeps the payloads of its newest RESIDENT_RECORDS records in memory, exactly as before.
# An older payload is dropped from memory and read back from the ledger file when asked for; the bytes read
# must have the SHA-256 of the line this ledger itself wrote or verified, or the read is refused. Nothing
# written changes: the same lines, the same hashes. A body's memory then grows with the small per-record
# skeleton, not with history's payloads (FINDING-LEDGER-APPEND-COST-2026-10-14, "Next measured limit",
# option 1; docs/collaboration/FINDING-BODY-MEMORY-2026-10-28.md).
RESIDENT_RECORDS = 1024


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


@dataclass(slots=True)
class LedgerRecord:
    seq: int
    ts_utc: str
    record_type: str          # event | witness | receipt | outcome | seal | correction | decision
    payload: dict
    prev_hash: str
    hash: str
    corrects: str | None = None   # hash of the record this corrects (correction ancestry)
    hash_version: int = 1


def copy_json(value):
    """A caller-owned copy of JSON data (dicts, lists, scalars); faster than copy.deepcopy."""
    if type(value) is dict:
        return {k: copy_json(v) for k, v in value.items()}
    if type(value) is list:
        return [copy_json(v) for v in value]
    if isinstance(value, (dict, list)):
        return copy.deepcopy(value)
    return value


def _index_value(table: dict, value, position: int) -> None:
    try:
        table.setdefault(value, []).append(position)
    except TypeError:   # unhashable (an object or a list): equal to no hashable query value
        pass


_PAYLOAD = LedgerRecord.__dict__["payload"]   # the slot itself, under _Retained's payload property


class _LineSource:
    """Reads retained lines back from a ledger file, refusing any byte that is not the one verified."""

    def __init__(self, path: str):
        self.path = path
        # Reads that found changed bytes, and how many of those a later whole-file reconstruction has answered.
        # While failures > cleared every reconstruction, the commit path's included, reads the whole file. A
        # counter, not a flag: a failure found while a reconstruction is running is not erased by it.
        self.failures = 0
        self.cleared = 0
        self._fd = None
        self._lock = threading.Lock()

    @property
    def broken(self) -> bool:
        return self.failures > self.cleared

    def note_failure(self) -> None:
        with self._lock:
            self.failures += 1

    def _refuse(self, rec, why: str) -> None:
        self.note_failure()
        raise ValueError(f"payload hash mismatch at seq {getattr(rec, 'seq', '?')}: {why}")

    def _open(self) -> int:
        with self._lock:
            if self._fd is None:
                self._fd = os.open(self.path, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0))
            return self._fd

    def replaced(self) -> bool:
        """Whether the path now names another file than the one this source reads (or none)."""
        fd = self._open()
        try:
            here, there = os.fstat(fd), os.stat(self.path)
        except OSError:
            return True
        return (here.st_dev, here.st_ino) != (there.st_dev, there.st_ino)

    def read(self, rec: "_Retained") -> bytes:
        off, size, digest = rec._off, rec._len, rec._digest
        if type(off) is not int or type(size) is not int or type(digest) is not bytes or off < 0 or size < 1:
            self._refuse(rec, "its line pointer was altered in memory")
        data = os.pread(self._open(), size, off)
        if len(data) != size or hashlib.sha256(data).digest() != digest:
            self._refuse(rec, "the retained line changed on disk")
        return data

    def line(self, rec: "_Retained") -> dict:
        """The whole retained line, parsed. Its bytes are the ones strictly parsed and hash-verified before (their
        SHA-256 is checked), so the standard parser yields exactly what that parse yielded."""
        line = json.loads(self.read(rec))
        if type(line) is not dict or line.get("hash") != rec.hash or line.get("seq") != rec.seq:
            self._refuse(rec, "the retained line is another record")
        return line

    def payload(self, rec: "_Retained") -> dict:
        """The record's payload as a new object (the caller's own)."""
        return self.line(rec)["payload"]

    def close(self) -> None:
        with self._lock:
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None


class _Retained(LedgerRecord):
    """A record a file-backed ledger retains. While the record is among the newest RESIDENT_RECORDS its payload
    is the object in memory, as for any record; after that only its skeleton stays, and ``payload`` reads the
    line back from the file (a new object on every read). Other code sees an ordinary record."""
    __slots__ = ("_off", "_len", "_digest", "_src")

    @property
    def payload(self):
        p = _PAYLOAD.__get__(self, _Retained)
        return self._src.payload(self) if p is None else p

    @payload.setter
    def payload(self, value):
        _PAYLOAD.__set__(self, value)

    @property
    def resident(self) -> bool:
        return _PAYLOAD.__get__(self, _Retained) is not None

    def _header(self) -> tuple:
        return (self.seq, self.ts_utc, self.record_type, self.prev_hash, self.hash, self.corrects, self.hash_version)

    def _fields(self) -> tuple:
        return (self.seq, self.ts_utc, self.record_type, self.payload, self.prev_hash, self.hash, self.corrects,
                self.hash_version)

    def __eq__(self, other):
        if not isinstance(other, LedgerRecord):
            return NotImplemented
        theirs = (other.seq, other.ts_utc, other.record_type, other.prev_hash, other.hash, other.corrects,
                  other.hash_version)
        return self._header() == theirs and self.payload == other.payload   # the payload last: it may read the file

    __hash__ = None

    def __copy__(self):
        return LedgerRecord(*self._fields())

    def __deepcopy__(self, memo):
        return LedgerRecord(*copy.deepcopy(self._fields(), memo))

    def __reduce__(self):
        return (LedgerRecord, self._fields())


def _owned(rec: "LedgerRecord") -> dict:
    """The record's payload as the caller's own object. The slot is read once: a resident payload is copied, a
    dropped one is read back from the file (already a new object), whatever eviction does meanwhile."""
    if type(rec) is _Retained:
        held = _PAYLOAD.__get__(rec, _Retained)
        return rec._src.payload(rec) if held is None else copy_json(held)
    return copy_json(rec.payload)


def _handout(rec: "LedgerRecord", owned=None) -> "LedgerRecord":
    """The caller's own copy of a retained record. ``owned``, when given, is a payload object the caller owns."""
    return LedgerRecord(rec.seq, rec.ts_utc, rec.record_type, _owned(rec) if owned is None else owned,
                        rec.prev_hash, rec.hash, rec.corrects, rec.hash_version)


def _copy_record(rec: "LedgerRecord") -> "LedgerRecord":
    return _handout(rec)


def _conforms(rec) -> bool:
    """The exact types a dropped record's skeleton must keep; a change of type alone is an alteration."""
    return (type(rec) is _Retained and type(rec.seq) is int and type(rec.record_type) is str
            and type(rec.prev_hash) is str and type(rec.hash) is str and type(rec.ts_utc) is str
            and (rec.corrects is None or type(rec.corrects) is str) and type(rec.hash_version) is int
            and type(rec._off) is int and type(rec._len) is int and type(rec._digest) is bytes
            and len(rec._digest) == 32)


def _skeleton(rec: "_Retained") -> bytes:
    """What stays in memory of a record whose payload was dropped, as bytes the dropped-history digest covers.
    ascii() keeps types apart (None from 'None', 2 from '2') and is ASCII for any string, lone surrogates too."""
    return "\x1f".join(map(ascii, (rec.seq, rec.record_type, rec.prev_hash, rec.hash, rec.ts_utc, rec.corrects,
                                   rec.hash_version, rec._off, rec._len))).encode("ascii") + b"\x1e" + rec._digest


def _line_bytes(rec: "LedgerRecord", payload) -> bytes:
    """The line this ledger writes for a record (byte-identical to what it has always written)."""
    return (json.dumps(asdict(LedgerRecord(rec.seq, rec.ts_utc, rec.record_type, payload, rec.prev_hash, rec.hash,
                                           rec.corrects, rec.hash_version)), allow_nan=False) + "\n").encode("utf-8")


class RecordsView(Sequence):
    """Read-only view of retained history. Every record it yields is the caller's own copy, so
    changing one never changes what the ledger retains."""
    __slots__ = ("_records",)

    def __init__(self, records: list):
        self._records = records

    def __len__(self):
        return len(self._records)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [_copy_record(r) for r in self._records[index]]
        return _copy_record(self._records[index])

    def __iter__(self):
        return (_copy_record(r) for r in list(self._records))

    def __reversed__(self):
        return (_copy_record(r) for r in reversed(list(self._records)))

    def __contains__(self, value):
        return value in self._records

    def index(self, value, *args):
        return self._records.index(value, *args)

    def count(self, value):
        return self._records.count(value)

    def __eq__(self, other):
        theirs = other._records if isinstance(other, RecordsView) else other
        return isinstance(theirs, (list, tuple)) and list(self._records) == list(theirs)

    def __repr__(self):
        return f"RecordsView({self._records!r})"


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
                 tail: str = "refuse", resident: int | None = None):
        self.path = path
        # Payloads of records older than the newest `resident` ones live only in the file (RESIDENT_RECORDS).
        # An in-memory ledger has no file to read them back from, so it keeps every payload.
        resident = RESIDENT_RECORDS if resident is None else resident
        if type(resident) is not int or resident < 1:
            raise ValueError('resident must be a positive record count')
        self._resident = resident if path else None
        self._src = _LineSource(path) if path else None
        self._reset_dropped()
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
        # Retained records never leave this object: every read hands out a copy. A record verified
        # once therefore stays verified unless this private list itself is altered, which the
        # scheduled full reconstruction detects.
        self._records: list[LedgerRecord] = []
        self._verified = 0           # records[:_verified] passed verification
        self._full_at: float | None = None   # monotonic time of the last full reconstruction
        self._verified_tail: LedgerRecord | None = None   # the object records[_verified - 1] was
        self._reset_index()
        genesis_payload = {"kind": "genesis", "constitution_hash": constitution_hash}
        gh = sha256_json({"seq": 0, "payload": genesis_payload, "prev_hash": GENESIS_PREV})
        self._records.append(LedgerRecord(0, _now(), "genesis", genesis_payload, GENESIS_PREV, gh))
        try:
            if path and os.path.exists(path):
                self._load(path)
            elif path:
                if read_only or expected_head:
                    raise ValueError('expected history is missing')
                with open(path, "x", encoding="utf-8") as fh:
                    fh.write(json.dumps(asdict(self._records[0])) + "\n")
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
        if getattr(self, "_src", None) is not None:
            self._src.close()     # a later read of an old payload reopens the file read-only
        self._closed = True

    def __del__(self):
        if hasattr(self, '_writer'):
            self.close()

    @property
    def records(self) -> RecordsView:
        """Retained history, read-only; each record read from it is the caller's own copy."""
        return RecordsView(self._records)

    @records.setter
    def records(self, records) -> None:
        # Assigned history (a review snapshot) is copied in and verified again from the beginning.
        with self._lock:
            self._records = [_copy_record(r if isinstance(r, LedgerRecord) else LedgerRecord(**r)) for r in records]
            self._verified, self._full_at, self._verified_tail = 0, None, None
            self._reset_dropped()  # assigned records are plain copies with no line in the file: all stay resident

    @property
    def head(self) -> str:
        return self._records[-1].hash

    def _owned_payload(self, i: int) -> dict:
        """The payload of retained record ``i`` as the caller's own object (the event spine reads through this)."""
        return _owned(self._records[i])

    def append(self, record_type: str, payload: dict, *, corrects: str | None = None) -> LedgerRecord:
        with self._lock:
            return self._append(record_type, payload, corrects=corrects)

    def _append(self, record_type: str, payload: dict, *, corrects=None):
        if self.read_only or self._closed or os.getpid() != self._pid:
            raise WriterConflict('not the active ledger writer')
        if self._uncertain:
            raise ReconciliationRequired('previous append is uncertain; reopen verified history')
        ok, reason = (self._reconstruct(read_disk=False) if record_type in COMMIT_RECORD_TYPES
                      else self.verify_incremental())
        if not ok:
            raise ValueError(reason)
        if record_type in ('genesis', 'constitution_transition'):
            raise ValueError('unsupported constitutional transition; separate authority decision required')
        if not isinstance(record_type, str) or not (corrects is None or isinstance(corrects, str)):
            raise ValueError('record type and correction ancestry must be text')
        record_type = str.__str__(record_type)               # an exact str: what reading the line back yields
        corrects = corrects if corrects is None else str.__str__(corrects)
        # Snapshot caller data. Integrity does not establish truth or permission.
        payload = json.loads(json.dumps(payload, allow_nan=False))
        if not isinstance(payload, dict):
            raise ValueError('ledger payload must be an object')
        seq = len(self._records)
        prev = self.head
        ts = _now()
        body = {"seq": seq, "record_type": record_type, "payload": payload,
                "prev_hash": prev, "corrects": corrects, 'ts_utc': ts, 'hash_version': 2}
        h = sha256_json(body)
        rec = LedgerRecord(seq, ts, record_type, payload, prev, h, corrects, 2)
        if self.path:
            # The same bytes as before (json.dumps output is ASCII), written in binary to know where they land.
            # The retained form is built before the write, so nothing that can fail is left for after it.
            line = _line_bytes(rec, payload)
            rec = self._retain(rec, 0, line)
            # Opening failure is definite; after write starts, acknowledgment is
            # uncertain until flush/fsync finish. Never advance memory early.
            with open(self.path, "ab") as fh:
                try:
                    offset = fh.seek(0, os.SEEK_END)
                    fh.write(line)
                    fh.flush()
                    os.fsync(fh.fileno())
                except OSError as exc:
                    self._uncertain = True
                    raise ReconciliationRequired('append acknowledgment lost') from exc
            rec._off = offset
        try:
            self._records.append(rec)
            if self._verified == seq:
                # Built here from the verified head and hashed above: verified by construction.
                self._verified, self._verified_tail = seq + 1, rec
        except BaseException as exc:          # durable, but not in memory: never write this sequence number again
            self._uncertain = True
            raise ReconciliationRequired('append retained on disk but not in memory; reopen verified history') from exc
        self._evict()
        return _copy_record(rec)

    def _retain(self, rec: LedgerRecord, offset: int, line: bytes) -> "_Retained":
        """The retained form of a record whose line (exactly ``line``, at ``offset``) this ledger wrote or
        verified. Strings it shares with the previous record are shared, not duplicated."""
        kind = sys.intern(rec.record_type) if type(rec.record_type) is str else rec.record_type
        kept = _Retained(rec.seq, rec.ts_utc, kind, rec.payload, rec.prev_hash, rec.hash, rec.corrects,
                         rec.hash_version)
        if self._records and kept.prev_hash == self._records[-1].hash:
            kept.prev_hash = self._records[-1].hash
        kept._off, kept._len, kept._digest, kept._src = offset, len(line), hashlib.sha256(line).digest(), self._src
        return kept

    # -- dropped payloads --------------------------------------------------------------------------------
    # records[1:_dropped_end] keep only their skeleton in memory; the genesis record and every newer record keep
    # their payload. One running SHA-256 covers those skeletons and their line digests in order, so any change to
    # what stays in memory of dropped history is found by recomputing it (no file read), the way a changed payload
    # in memory is found by re-hashing it.

    def _reset_dropped(self) -> None:
        self._dropped_end = 1
        self._dropped_hash = hashlib.sha256()
        self._dropped_digest = self._dropped_hash.digest()

    def _drop(self, i: int) -> None:
        rec = self._records[i]
        self._dropped_hash.update(_skeleton(rec))
        rec.payload = None
        self._dropped_end = i + 1

    def _pointer_ok(self, i: int) -> tuple[bool, str]:
        """Whether resident record i's line pointer names exactly the bytes of that record. Checked before its payload
        is dropped: once dropped, reads trust the pointer's digest, so a pointer altered while the payload was still
        in memory must not be folded into the dropped-history digest (independent review F1, 2026-10-28)."""
        rec = self._records[i]
        if type(rec) is not _Retained or not _conforms(rec) or rec._src is not self._src or not rec.resident:
            return True, ''                    # not droppable (assigned, loaded with unusual types, or dropped): no claim
        held = _PAYLOAD.__get__(rec, _Retained)
        try:
            line = _line_bytes(rec, held)
            if len(line) == rec._len and hashlib.sha256(line).digest() == rec._digest:
                return True, ''
            # A line this ledger did not write itself (an older writer's formatting): compare the file's record.
            disk = LedgerRecord(**self._src.line(rec))
            if disk == LedgerRecord(rec.seq, rec.ts_utc, rec.record_type, held, rec.prev_hash, rec.hash, rec.corrects,
                                    rec.hash_version):
                return True, ''
        except (TypeError, ValueError):
            pass
        return False, f"retained line pointer altered in memory at seq {i}"

    def _evict(self) -> None:
        """Drop from memory the payloads of records older than the newest ``resident`` ones.

        Only a payload that still hashes to its record, and whose line pointer still names that record's bytes, is
        dropped, in order. Anything altered in memory stays (and so does everything after it), so a reconstruction
        still finds the alteration instead of the file quietly serving the original. Never raises: dropping is an
        optimization, and the record it could not drop stays for reconstruction to judge.
        """
        if self._resident is None:
            return
        records, end, start = self._records, len(self._records) - self._resident, self._dropped_end
        try:
            for i in range(start, end):
                rec = records[i]
                if not (type(rec) is _Retained and _conforms(rec) and rec.resident and rec._src is self._src
                        and self._verify_record(i)[0] and self._pointer_ok(i)[0]):
                    break
                self._drop(i)
        except Exception:
            pass
        if self._dropped_end != start:
            self._dropped_digest = self._dropped_hash.digest()

    def _verify_dropped(self, read_disk: bool) -> tuple[bool, str]:
        """Check what stays in memory of dropped history against its running digest; with ``read_disk``, also
        re-derive every dropped record from the file: its bytes must be the ones verified and must hash to it."""
        records, end = self._records, self._dropped_end
        if end <= 1:
            return True, ''
        if end > len(records):
            return False, 'retained history is shorter than its dropped prefix'
        digest = hashlib.sha256()
        for i in range(1, end):
            rec = records[i]
            if not _conforms(rec) or rec._src is not self._src or rec.seq != i:
                return False, f"retained record altered in memory at seq {i}"
            if rec.prev_hash != records[i - 1].hash:
                return False, f"chain break at seq {i}"
            if rec.resident:     # a payload put back after it was dropped is held to its record like any other
                ok, why = self._verify_record(i)
                if not ok:
                    return False, why
            digest.update(_skeleton(rec))
        if digest.digest() != self._dropped_digest:
            return False, f"retained history altered in memory between seq 1 and {end - 1}"
        if read_disk:
            if self._src.replaced():          # appending to another file would fork history: refuse until it is back
                self._src.note_failure()
                return False, f"the ledger file at {self.path} was replaced after it was opened"
            for i in range(1, end):
                ok, why = self._rederive(i)
                if not ok:
                    return False, why
        return True, ''

    def _rederive(self, i: int) -> tuple[bool, str]:
        """Reconstruct dropped record i from the file alone and hold it to the skeleton in memory."""
        rec = self._records[i]
        try:
            disk = LedgerRecord(**self._src.line(rec))
        except (TypeError, ValueError) as exc:
            return False, str(exc) or f"payload hash mismatch at seq {i}"
        if (disk.seq, disk.ts_utc, disk.record_type, disk.prev_hash, disk.hash, disk.corrects,
                disk.hash_version) != rec._header():
            return False, f"retained record at seq {i} differs from its line in the file"
        return self._check(i, disk, disk.payload)

    def seal(self, *, sealed_by: str, reason: str) -> LedgerRecord:
        """Seal the head (shutdown propagation step 5). Returns the seal record."""
        return self.append("seal", {"sealed_by": sealed_by, "reason": reason, "head": self.head})

    def verify_chain(self) -> tuple[bool, str]:
        """Independently reconstruct and verify every link (evidence closure).

        Records still in memory are re-hashed from their payloads, as always. For history whose payloads were
        dropped, what stays in memory is checked against its running digest and every line in the file against the
        digest of the bytes that were hash-verified (RESIDENT_RECORDS)."""
        return self._reconstruct(read_disk=True)

    def _reconstruct(self, *, read_disk: bool) -> tuple[bool, str]:
        with self._lock:
            src = self._src
            # Once a read has found changed bytes in the file, every reconstruction (the commit path's included)
            # reads all of it until one finds it intact; failures found while this one runs stay counted.
            read_disk = read_disk or (src is not None and src.broken)
            mark = src.failures if src is not None else 0
            records = self._records
            if not records:
                return False, 'empty history'
            ok, reason = self._verify_record(0)
            if ok:
                ok, reason = self._verify_dropped(read_disk)
            if ok:
                limit = len(records) - self._resident if self._resident is not None else 0
                for i in range(max(1, self._dropped_end), len(records)):
                    ok, reason = self._verify_record(i)
                    if ok and i < limit:          # kept in memory past the window: its pointer is judged too
                        ok, reason = self._pointer_ok(i)
                    if not ok:
                        break
            if not ok:
                self._verified, self._full_at = 0, None
                return False, reason
            self._verified, self._full_at, self._verified_tail = len(records), _monotonic(), records[-1]
            if src is not None and read_disk:
                src.cleared = max(src.cleared, mark)
            return True, f"chain intact: {len(records)} records"

    def verify_incremental(self) -> tuple[bool, str]:
        """Verify the records not yet verified; reconstruct the whole chain on schedule.

        Retained records never leave this object (reads hand out copies), so a verified record stays
        verified unless the private list itself is altered. A full reconstruction runs on open, on
        every explicit verify_chain(), whenever the verified prefix is not the one last seen, and at
        least every FULL_VERIFY_SECONDS; it detects such an alteration within that window.
        """
        with self._lock:
            records, done = self._records, self._verified
            if self._src is not None and self._src.broken:
                return self._reconstruct(read_disk=False)   # reads the file: a read found changed bytes in it
            if (self._full_at is None or not 0 < done <= len(records)
                    or records[done - 1] is not self._verified_tail
                    or _monotonic() - self._full_at >= FULL_VERIFY_SECONDS):
                return self._reconstruct(read_disk=False)
            for i in range(done, len(records)):
                ok, reason = self._verify_record(i)
                if not ok:
                    self._verified, self._full_at = 0, None
                    return False, reason
            self._verified, self._verified_tail = len(records), records[-1]
            return True, f"chain intact: {len(records)} records"

    def _verify_record(self, i: int) -> tuple[bool, str]:
        rec = self._records[i]
        if type(rec.seq) is not int or rec.seq != i:
            return False, f"sequence break at {i}"
        try:
            payload = rec.payload        # read back from the file, byte-checked, if no longer in memory
        except ValueError as exc:
            return False, str(exc)
        return self._check(i, rec, payload)

    def _check(self, i: int, rec: LedgerRecord, payload) -> tuple[bool, str]:
        """Re-derive record i's hash from its fields and ``payload``, and its link to record i - 1."""
        if type(rec.seq) is not int or rec.seq != i:
            return False, f"sequence break at {i}"
        if (type(payload) is not dict or type(rec.hash_version) is not int
                or rec.hash_version not in (1, 2)):
            return False, f'unsupported record at {i}'
        if rec.record_type == 'constitution_transition':
            return False, 'unsupported amendment history: authority not established'
        if i == 0:
            expected = {'kind': 'genesis', 'constitution_hash': self.constitution_hash}
            if (rec.prev_hash != GENESIS_PREV or rec.record_type != 'genesis'
                    or payload != expected or rec.corrects is not None
                    or rec.hash_version != 1):
                return False, "genesis structure or expected constitution mismatch"
            if sha256_json({'seq': 0, 'payload': expected, 'prev_hash': GENESIS_PREV}) != rec.hash:
                return False, 'genesis hash mismatch'
            return True, ''
        if rec.record_type == 'genesis':
            return False, 'second genesis refused'
        if rec.prev_hash != self._records[i - 1].hash:
            return False, f"chain break at seq {i}"
        body = {"seq": rec.seq, "record_type": rec.record_type, "payload": payload,
                "prev_hash": rec.prev_hash, "corrects": rec.corrects}
        if rec.hash_version == 2:
            body.update(ts_utc=rec.ts_utc, hash_version=2)
        if sha256_json(body) != rec.hash:
            return False, f"payload hash mismatch at seq {i}"
        return True, ''

    # -- lookups ------------------------------------------------------------------------------------
    # Answered from indexes of positions in the retained list, kept like the event spine's views: each
    # lookup indexes only the records added since the last one, and a different record where the last
    # indexed one was (history assigned or reloaded) rebuilds them from the beginning. Every answer is
    # re-checked against the record itself and handed out as the caller's own copy.

    def _reset_index(self) -> None:
        self._indexed, self._indexed_tail = 0, None
        self._by_hash: dict[str, int] = {}               # hash -> position of its first record
        self._by_type: dict[str, array] = {}             # record type -> positions (8 bytes each)
        self._by_field: dict[str, dict[str, dict]] = {}  # record type -> payload field -> value -> positions

    def _index_new(self) -> None:
        records, done = self._records, self._indexed
        if done and (done > len(records) or records[done - 1] is not self._indexed_tail):
            self._reset_index()
            done = 0
        for i in range(done, len(records)):
            rec = records[i]
            self._by_hash.setdefault(rec.hash, rec.seq if rec.seq == i else i)   # one int object per record, not two
            self._by_type.setdefault(rec.record_type, array("q")).append(i)
            for field, table in self._by_field.get(rec.record_type, {}).items():
                _index_value(table, rec.payload.get(field), i)
        if len(records) > done:
            self._indexed, self._indexed_tail = len(records), records[-1]

    def find(self, record_hash: str) -> LedgerRecord | None:
        with self._lock:
            self._index_new()
            i = self._by_hash.get(record_hash)
            if i is None:
                return None
            if self._records[i].hash == record_hash:
                return _copy_record(self._records[i])
            # The private list was altered in place: answer as a scan of it would.
            return next((_copy_record(r) for r in self._records if r.hash == record_hash), None)

    def by_type(self, record_type: str) -> list[LedgerRecord]:
        return self.select(record_type)

    def select(self, record_type: str, **where) -> list[LedgerRecord]:
        """Records of this type whose payload has every ``field=value`` given, in ledger order.

        Exactly ``[r for r in records if r.record_type == record_type and all(r.payload.get(f) == v ...)]``
        without reading the rest of history: the first field is looked up in an index of that type's
        payload values, built on first use and kept up to date like the others. (A record altered in
        place in the private list, which verification detects, is never returned for a value it no
        longer holds, and is not found by the value written into it.)"""
        with self._lock:
            self._index_new()
            records = self._records
            positions = self._by_type.get(record_type, ())
            if where:
                field, value = next(iter(where.items()))
                tables = self._by_field.setdefault(record_type, {})
                if field not in tables:
                    table = tables[field] = {}
                    for i in positions:
                        _index_value(table, records[i].payload.get(field), i)
                try:
                    positions = tables[field].get(value, ())
                except TypeError:     # an unhashable value is never indexed: compare record by record
                    pass
            found = []
            for i in positions:
                rec = records[i]
                if rec.record_type != record_type:
                    continue
                held = _PAYLOAD.__get__(rec, _Retained) if type(rec) is _Retained else rec.payload
                if held is None:                # dropped: read once from the file; that object is the caller's
                    owned = rec._src.payload(rec)
                    if all(owned.get(f) == v for f, v in where.items()):
                        found.append(_handout(rec, owned))
                elif all(held.get(f) == v for f, v in where.items()):
                    found.append(_copy_record(rec))
            return found

    def _load(self, path: str) -> None:
        # Durable history supplies transition truth only after full verification.
        # Hash consistency is not factual appraisal, permission or authentication.
        # Read line by line and verified as read, so opening a long history never holds all of it in memory: only
        # the newest `resident` payloads stay. Failures are reported in the order a whole-file read reported them
        # (a torn tail, then a blank or malformed line anywhere, then the first verification failure).
        from adapters.contract_validation import strict_json
        size = os.path.getsize(path)
        complete_end = _complete_end(path, size)
        if complete_end < size:
            if self._tail_policy == "refuse":
                raise ValueError('partial or blank history record')
            with open(path, "rb") as fh:
                fh.seek(complete_end)
                torn = fh.read()
            self.unacknowledged_tail = {"offset": complete_end, "bytes": len(torn),
                                        "sha256": "sha256:" + hashlib.sha256(torn).hexdigest(),
                                        "_bytes": torn}
        self._records = []
        failure = None
        with open(path, "rb") as fh:
            offset = 0
            while offset < complete_end:
                chunk = fh.readline()
                try:
                    line = chunk.decode("utf-8")
                    if not line.strip():
                        raise ValueError('partial or blank history record')
                    rec = LedgerRecord(**strict_json(line))
                except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError('malformed retained history') from exc
                if failure is None:
                    i = len(self._records)
                    self._records.append(self._retain(rec, offset, chunk))
                    ok, msg = self._verify_record(i)
                    if not ok:
                        failure = msg
                    elif (i - self._resident == self._dropped_end
                          and _conforms(self._records[i - self._resident])):
                        self._drop(i - self._resident)     # verified just now from these very bytes, then untouched
                offset += len(chunk)
        if self.unacknowledged_tail and self._tail_policy == "ignore":
            self.unacknowledged_tail.pop("_bytes")
        if failure is None and not self._records:
            failure = self.verify_chain()[1]
        if failure is not None:
            self._verified, self._full_at = 0, None
            raise ValueError(f"ledger at {path} failed verification on load: {failure}")
        records = self._records
        self._dropped_digest = self._dropped_hash.digest()
        self._verified, self._full_at, self._verified_tail = len(records), _monotonic(), records[-1]


def _complete_end(path: str, size: int) -> int:
    """Offset just past the last newline of the file (0 when there is none): the end of its complete lines."""
    block = 1 << 16
    with open(path, "rb") as fh:
        end = size
        while end > 0:
            start = max(0, end - block)
            fh.seek(start)
            found = fh.read(end - start).rfind(b"\n")
            if found >= 0:
                return start + found + 1
            end = start
    return 0
