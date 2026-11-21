"""Explicit, evidence-preserving recovery of a torn Evidence Ledger tail.

A process killed in the middle of an append can leave a partially written last line. ``EvidenceLedger``
refuses to open such a file, which protects history but leaves the body unable to restart: the founder-loop
entry gate's proof P2 (interruption and autonomous recovery) cannot pass while canonical history cannot be
reopened. Opening a torn ledger still fails closed; this module is the repair, and it is never automatic.

``recover_torn_tail`` runs only for an accountable caller (a supervisor, an operator, a test harness) that
names itself and a reason. Holding the ledger's single-writer lock for the whole procedure, it:

1. refuses unless every complete line verifies as a chain anchored to the expected constitution;
2. refuses unless the tail is something one interrupted append can leave: a byte prefix of the next record's
   line (records are pure-ASCII JSON beginning ``{"seq": <n>, "ts_utc": "``), optionally followed by NUL
   padding, or a run of NULs from a zero-filled extent. A complete object followed by more bytes, non-ASCII
   bytes, NULs inside content or any other beginning is corruption and is refused;
3. refuses unless the caller has acknowledged, by name, every risk that cannot be excluded (below);
4. copies the torn bytes, byte for byte, to ``<ledger>.torn-<prior head>-<sha256>`` beside the ledger, with a
   ``.json`` sidecar recording what was found and who is recovering it, each written atomically and durably;
5. truncates the ledger to its last complete record;
6. appends one ``event`` of type ``ledger.torn_tail_quarantined`` describing all of it, still under the lock,
   so no restarting writer can append between the truncation and its record.

Why the torn record is quarantined and never re-admitted: ``EvidenceLedger._append`` writes, flushes and
fsyncs a record before it returns, and only then advances memory. A torn append therefore never returned to
its caller, so nothing (no Gate dispatch, no executor call, no suspension) took effect from it. Its bytes stay
beside the ledger as evidence.

Risks a byte-level check cannot exclude, each refused unless named in ``acknowledged_risks``:

* ``"unanchored"``: no ``expected_head`` was supplied. Someone who cuts an acknowledged record back far enough
  produces bytes identical to a genuine torn write; only the caller's last acknowledged head excludes that.
  With ``expected_head``, the head before the torn line must equal it. A match proves the torn append never
  returned only if that head is the writer's last acknowledged one: a checkpoint taken even one append
  earlier matches too, so the event says what was matched, not more.
* ``"complete_record"``: the tail holds a complete, correctly chained record missing only its newline or its
  closing fields. A crash can leave that, but so can deleting a byte or two after the record was
  acknowledged, and a checkpoint taken before the record cannot tell the two apart, so this risk must be
  named even when ``expected_head`` matches.
* ``"stop_record"``: the torn bytes name a stop: a ledger seal, a standing-cognition suspension, a founder
  control or a founder answer. It never took effect, so recovery does not undo it, but whoever issued it may
  believe it did; the stop must be re-issued before the body restarts. A tail cut before its record type
  carries the same warning in the event without a required acknowledgment.

Every step is idempotent and crash-safe: copies are created atomically (temporary file, fsync, link or
replace), a quarantine whose ledger event is missing (a crash between steps 5 and 6) is recorded on the next
call under the identity of whoever truncated it, and nothing is overwritten or deleted except the torn bytes
themselves, after their copy is durable. Stray ``.tmp-`` files left by a crash are incomplete scratch copies
and are ignored.

This module grants no authority and runs nothing; it repairs the file format so the canonical ledger can be
reopened and reconciled. The writer lock is keyed on the path string (as in ``EvidenceLedger``), so a
symlinked path, or a ledger file with more than one hard link, is refused: it cannot prove there is no live writer.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
from typing import Any

from .ledger import EvidenceLedger, LedgerRecord, WriterConflict, sha256_json

EVENT_TYPE = "ledger.torn_tail_quarantined"
RISKS = ("unanchored", "complete_record", "stop_record")
STOP_RECORD_TYPES = frozenset({"seal", "egregore.suspended", "egregore.goal_preference", "egregore.founder_answer"})
_TAIL = ', "corrects": null, "hash_version": 2}'   # the closing fields of an ordinary appended record
_SIDECAR_KEYS = ("classification", "prior_head", "complete_records", "torn_record_hash", "torn_record_type",
                 "may_have_been_a_stop", "anchor", "acknowledged_risks", "recovered_by", "reason")
_TYPE = re.compile(r'"record_type": "([A-Za-z0-9_.:-]+)"')


class RecoveryRefused(RuntimeError):
    """Nothing was changed: the file is not a verifiable chain with only a torn final line, or a risk that
    cannot be excluded was not acknowledged."""


def _fsync_dir(path: str) -> None:
    fd = os.open(os.path.dirname(os.path.abspath(path)) or ".", os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_atomic(final: str, data: bytes, *, replace: bool) -> None:
    """Write ``data`` to ``final`` so that a crash leaves either no file or the complete file, never part of it."""
    tmp = f"{final}.tmp-{os.getpid()}-{os.urandom(4).hex()}"
    with open(tmp, "xb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        if replace:
            os.replace(tmp, final)
        else:
            os.link(tmp, final)   # fails if ``final`` exists; never overwrites
            os.unlink(tmp)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    _fsync_dir(final)


def _require_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required: an accountable recovery names who ran it and why")
    return value.strip()


def _open_for_append(path: str, constitution_hash: str) -> EvidenceLedger:
    """A verifying ledger that appends while THIS module holds the writer lock.

    ``EvidenceLedger`` takes the lock itself on open. To reuse its append (rather than re-implement the record
    format) while keeping our lock continuous, it is opened read-only and the flag is lifted under our lock."""
    ledger = EvidenceLedger(constitution_hash, path=path, read_only=True)
    ledger.read_only = False
    return ledger


def _verified_prefix(path: str, constitution_hash: str, prefix: bytes) -> EvidenceLedger:
    """Verify the complete lines as a chain, read-only, from a temporary copy (the original is untouched)."""
    tmp = f"{path}.check-{os.getpid()}-{os.urandom(4).hex()}"
    try:
        with open(tmp, "xb") as fh:
            fh.write(prefix)
        try:
            return EvidenceLedger(constitution_hash, path=tmp, read_only=True)
        except (ValueError, TypeError) as exc:
            raise RecoveryRefused(f"the complete records do not verify, so this is not a torn tail: {exc}") from exc
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _chained(obj: Any, prefix_ledger: EvidenceLedger) -> LedgerRecord | None:
    """The object as the next record of this chain, if it is exactly that."""
    if not isinstance(obj, dict):
        return None
    try:
        rec = LedgerRecord(**obj)
    except TypeError:
        return None
    if not isinstance(rec.payload, dict) or rec.seq != len(prefix_ledger.records) or rec.prev_hash != prefix_ledger.head:
        return None
    body = {"seq": rec.seq, "record_type": rec.record_type, "payload": rec.payload,
            "prev_hash": rec.prev_hash, "corrects": rec.corrects}
    if rec.hash_version == 2:
        body.update(ts_utc=rec.ts_utc, hash_version=2)
    return rec if sha256_json(body) == rec.hash else None


def _classify(torn: bytes, prefix_ledger: EvidenceLedger) -> dict[str, Any]:
    """Decide whether the tail can be a torn write of the next record, and how complete it is.

    Raises ``RecoveryRefused`` for anything a single interrupted append cannot have produced."""
    if not torn.strip(b"\x00"):
        return {"classification": "zero_fill", "torn_record_type": None}   # a zero-filled extent after power loss
    core = torn.rstrip(b"\x00")
    if b"\x00" in core or any(b > 0x7F for b in core):
        raise RecoveryRefused("the tail holds bytes no ledger append writes (NUL inside content or non-ASCII): corruption")
    text = core.decode("ascii")
    expected = '{"seq": %d, "ts_utc": "' % len(prefix_ledger.records)
    if not (text.startswith(expected) or expected.startswith(text)):
        raise RecoveryRefused("the tail is not the beginning of the next record: corruption, not a torn append")
    found = _TYPE.search(text)
    torn_type = found.group(1) if found else None
    try:
        obj, end = json.JSONDecoder().raw_decode(text)
    except ValueError:
        obj, end = None, 0
    if obj is not None:
        if text[end:]:
            raise RecoveryRefused("the tail holds a complete object followed by more bytes; one interrupted append "
                                  "cannot produce that (a newline was overwritten or lines were joined)")
        rec = _chained(obj, prefix_ledger)
        if rec is None:
            raise RecoveryRefused("the tail is a complete object that is not the next record of this chain")
        return {"classification": "complete_unterminated", "torn_record_hash": rec.hash,
                "torn_record_type": rec.record_type}
    for j in range(len(_TAIL) + 1):   # content complete, only closing fields missing?
        try:
            rec = _chained(json.loads(text + _TAIL[j:]), prefix_ledger)
        except ValueError:
            continue
        if rec is not None:
            return {"classification": "content_complete", "torn_record_hash": rec.hash,
                    "torn_record_type": rec.record_type}
    return {"classification": "partial", "torn_record_type": torn_type}


def _quarantine_name(path: str, prior_head: str, digest_hex: str) -> str:
    return f"{path}.torn-{prior_head.split(':', 1)[-1][:16]}-{digest_hex}"


def _quarantine_files(path: str) -> list[str]:
    """Exactly the quarantine files this module writes (never backups, editor files, scratch or sidecars)."""
    directory, base = os.path.split(path)
    pattern = re.compile(re.escape(base) + r"\.torn-[0-9a-f]{16}-[0-9a-f]{64}")
    return sorted(os.path.join(directory, name) for name in os.listdir(directory or ".") if pattern.fullmatch(name))


def recover_torn_tail(path: str, constitution_hash: str, *, recovered_by: str, reason: str,
                      expected_head: str | None = None, acknowledged_risks: tuple[str, ...] | list[str] = ()
                      ) -> dict[str, Any]:
    """Quarantine a torn final line, truncate to the last complete record and record the recovery in the chain.

    Returns ``{"torn": False, ...}`` when the ledger ends cleanly (after recording any quarantine whose ledger
    event is missing). Raises ``WriterConflict`` while a writer holds the ledger and ``RecoveryRefused`` when the
    tail is not a torn append, the complete records do not verify, the head differs from ``expected_head``, or a
    risk applies that ``acknowledged_risks`` does not name; in each of those cases nothing is changed.
    """
    recovered_by = _require_text("recovered_by", recovered_by)
    reason = _require_text("reason", reason)
    acknowledged = sorted(set(acknowledged_risks))
    unknown = [r for r in acknowledged if r not in RISKS]
    if unknown:
        raise ValueError(f"unknown risks {unknown}; the risks are {list(RISKS)}")
    if os.path.islink(path):
        raise RecoveryRefused("call recovery with the ledger's own path, not a symlink to it")
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise RecoveryRefused("no ledger file at that path")
    if os.stat(path).st_nlink > 1:   # a hard link is another path, with its own lock file, to the same bytes
        raise RecoveryRefused("the ledger file has more than one hard link, so a writer holding the lock through "
                              "another name would not be seen; remove the extra links before recovering")
    quarantined: dict[str, Any] | None = None
    lock = open(path + ".lock", "a")
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise WriterConflict("the ledger has a live writer; stop it before recovering") from exc
        with open(path, "rb") as fh:
            data = fh.read()
        if not data:
            raise RecoveryRefused("the ledger file is empty; there is no genesis to recover to")
        if not data.endswith(b"\n"):
            quarantined = _quarantine_and_truncate(path, constitution_hash, data, recovered_by=recovered_by,
                                                   reason=reason, expected_head=expected_head, acknowledged=acknowledged)
        recorded = _record_quarantines(path, constitution_hash, recorded_by=recovered_by)
    finally:
        lock.close()
    return {"torn": quarantined is not None, "quarantined": quarantined, "recorded": recorded}


def _quarantine_and_truncate(path: str, constitution_hash: str, data: bytes, *, recovered_by: str, reason: str,
                             expected_head: str | None, acknowledged: list[str]) -> dict[str, Any]:
    cut = data.rfind(b"\n") + 1
    if cut == 0:
        raise RecoveryRefused("no complete record exists (the genesis line itself is torn)")
    prefix, torn = data[:cut], data[cut:]
    prefix_ledger = _verified_prefix(path, constitution_hash, prefix)
    if expected_head is not None and prefix_ledger.head != expected_head:
        raise RecoveryRefused("the head before the torn line is not the expected acknowledged head: "
                              "truncation, a fork or an acknowledged record would be lost")
    found = _classify(torn, prefix_ledger)
    torn_type = found.get("torn_record_type")
    risks = []
    if expected_head is None:
        risks.append("unanchored")
    if found["classification"] in ("complete_unterminated", "content_complete"):
        risks.append("complete_record")   # a stale checkpoint matches as well as a fresh one (review R1b)
    if torn_type in STOP_RECORD_TYPES:
        risks.append("stop_record")
    missing = [r for r in risks if r not in acknowledged]
    if missing:
        why = {"unanchored": "no expected_head, so an acknowledged record cut back to look torn cannot be excluded",
               "complete_record": ("the tail holds a complete, correctly chained record; it may have been acknowledged "
                                   "and damaged later, and no checkpoint taken before it can exclude that"),
               "stop_record": (f"the torn record is a {torn_type}, a stop that never took effect; whoever issued it "
                               "must re-issue it before the body restarts")}
        raise RecoveryRefused("acknowledge these risks to proceed, or supply expected_head where it applies: "
                              + "; ".join(f"{r}: {why[r]}" for r in missing))
    digest = hashlib.sha256(torn).hexdigest()
    qpath = _quarantine_name(path, prefix_ledger.head, digest)
    meta = {"torn_sha256": "sha256:" + digest, "torn_bytes": len(torn), "prior_head": prefix_ledger.head,
            "complete_records": len(prefix_ledger.records), **found,
            "may_have_been_a_stop": torn_type is None or torn_type in STOP_RECORD_TYPES,
            "anchor": ("expected_head matched" if expected_head is not None else
                       "none supplied: an acknowledged record cut back to look like a partial write cannot be excluded"),
            "acknowledged_risks": risks, "recovered_by": recovered_by, "reason": reason}
    if os.path.exists(qpath):
        with open(qpath, "rb") as fh:
            if fh.read() != torn:
                raise RecoveryRefused(f"{os.path.basename(qpath)} exists with different bytes; investigate before recovering")
    else:
        _write_atomic(qpath, torn, replace=False)
    # The sidecar describes the incident this call is about to truncate, so this call (re)writes it.
    _write_atomic(qpath + ".json", json.dumps(meta, sort_keys=True).encode("utf-8"), replace=True)
    with open(path, "r+b") as fh:   # only after the copy and its description are durable
        fh.truncate(cut)
        fh.flush()
        os.fsync(fh.fileno())
    _fsync_dir(path)
    return {"quarantine_file": os.path.basename(qpath), **meta}


def _record_quarantines(path: str, constitution_hash: str, *, recorded_by: str) -> list[dict[str, Any]]:
    """Append the ledger event for every quarantine file that has none yet. Called only under the writer lock."""
    files = _quarantine_files(path)
    if not files:
        return []
    ledger = _open_for_append(path, constitution_hash)
    try:
        seen = {r.payload.get("quarantine_file") for r in ledger.by_type("event") if r.payload.get("type") == EVENT_TYPE}
        written = []
        for qpath in files:
            name = os.path.basename(qpath)
            if name in seen:
                continue
            with open(qpath, "rb") as fh:
                torn = fh.read()
            digest_hex = hashlib.sha256(torn).hexdigest()
            if not name.endswith("-" + digest_hex):
                raise RecoveryRefused(f"{name} no longer holds the bytes its name records; investigate before recording")
            meta: dict[str, Any] = {"classification": "unknown: sidecar missing or unreadable"}
            try:
                with open(qpath + ".json", "rb") as fh:
                    side = json.loads(fh.read().decode("utf-8"))
                prior = str(side.get("prior_head", ""))
                if side.get("torn_sha256") == "sha256:" + digest_hex and name.endswith(
                        f".torn-{prior.split(':', 1)[-1][:16]}-{digest_hex}"):
                    meta = {k: side[k] for k in _SIDECAR_KEYS if k in side}
                else:   # a sidecar is an unchained description; one that contradicts its file is not trusted
                    meta = {"classification": "unknown: sidecar inconsistent with its quarantine file"}
            except (OSError, ValueError, AttributeError, TypeError):
                pass
            payload = {**meta, "type": EVENT_TYPE, "torn_sha256": "sha256:" + digest_hex, "torn_bytes": len(torn),
                       "quarantine_file": name, "recovered_by": meta.get("recovered_by", "unknown: sidecar missing"),
                       "reason": meta.get("reason", "unknown: sidecar missing"), "recorded_by": recorded_by,
                       "stop_warning": (("the torn record may have been a stop (seal, suspension or founder control) "
                                         "that never took effect; re-issue it before the body restarts")
                                        if meta.get("may_have_been_a_stop", True) else None),
                       "disposition": ("quarantined, not chained: the head before it matched the caller's "
                                       "expected head; if that was the writer's last acknowledged head, this "
                                       "append never returned"
                                       if meta.get("anchor") == "expected_head matched" else
                                       "quarantined, not chained, unanchored: assumed to be an append that never "
                                       "returned; an acknowledged record cut back to look torn cannot be excluded")}
            record = ledger.append("event", payload)
            seen.add(name)
            written.append({"quarantine_file": name, "record_hash": record.hash})
        return written
    finally:
        ledger.read_only = True
        ledger.close()
