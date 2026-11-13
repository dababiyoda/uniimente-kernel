"""Explicit, evidence-preserving recovery of a torn Evidence Ledger tail.

A process killed in the middle of an append can leave a partially written last line. ``EvidenceLedger``
refuses to open such a file, which protects history but leaves the body unable to restart: the founder-loop
entry gate's proof P2 (interruption and autonomous recovery) cannot pass while canonical history cannot be
reopened.

``recover_torn_tail`` is the repair, and it is never automatic. An accountable caller (a supervisor, an
operator, a test harness) names itself and a reason. The procedure:

1. takes the ledger's single-writer lock, so no live writer can be appending;
2. refuses unless every complete line verifies as a chain anchored to the expected constitution, so this
   repairs a torn tail and nothing else (a corrupted or tampered record is still refused);
3. copies the torn bytes, byte for byte, to ``<ledger>.torn-<sha256>`` beside the ledger, with a sidecar
   ``.json`` describing them, and makes both durable before anything is changed;
4. truncates the ledger to its last complete record;
5. appends one ``event`` of type ``ledger.torn_tail_quarantined`` naming the quarantine file, its digest,
   the head before recovery, who recovered it and why.

Why the torn record is quarantined and never re-admitted: ``EvidenceLedger._append`` writes, flushes and
fsyncs a record before it returns, and only then advances memory. A torn line therefore belongs to an append
that never returned to its caller, so nothing (no Gate dispatch, no executor call) can have relied on it.

One case is treated as suspect rather than torn: a final line that parses as a complete, correctly chained
record and lacks only its newline. A crash can produce it, but so can someone deleting one byte after the
record was acknowledged, and recovering it would quietly drop a real record. It is refused unless the caller
shows it was never acknowledged, by passing ``expected_head`` (the last head the caller knows was
acknowledged, which must equal the head before that line), or explicitly accepts the loss with
``quarantine_complete_record=True``. Either way the record is quarantined, never re-admitted, and the ledger
event says which proof was given.

Every step is idempotent and crash-safe: a quarantine file that exists without its ledger event (a crash
between steps 4 and 5) is completed on the next call, and nothing is ever overwritten or deleted except the
torn bytes themselves, after their copy is durable.

This module grants no authority and runs nothing; it repairs the file format so the canonical ledger can be
reopened and reconciled.
"""
from __future__ import annotations

import fcntl
import glob
import hashlib
import json
import os
import tempfile
from typing import Any

from .ledger import EvidenceLedger, LedgerRecord, WriterConflict, sha256_json

EVENT_TYPE = "ledger.torn_tail_quarantined"


class RecoveryRefused(RuntimeError):
    """The file is not a verifiable chain with only a torn final line; nothing was changed."""


def _fsync_dir(path: str) -> None:
    fd = os.open(os.path.dirname(os.path.abspath(path)) or ".", os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_durable(path: str, data: bytes) -> None:
    """Create ``path`` (never overwriting) with ``data`` and make it durable."""
    with open(path, "xb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    _fsync_dir(path)


def _require_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required: an accountable recovery names who ran it and why")
    return value.strip()


def _verified_prefix(path: str, constitution_hash: str, prefix: bytes) -> EvidenceLedger:
    """Verify the complete lines as a chain, read-only, from a temporary copy (the original is untouched)."""
    fd, tmp = tempfile.mkstemp(prefix=".recovery-check-", dir=os.path.dirname(os.path.abspath(path)) or ".")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(prefix)
        try:
            return EvidenceLedger(constitution_hash, path=tmp, read_only=True)
        except (ValueError, TypeError) as exc:
            raise RecoveryRefused(f"the complete records do not verify, so this is not a torn tail: {exc}") from exc
    finally:
        os.unlink(tmp)


def _classify(torn: bytes, prefix_ledger: EvidenceLedger) -> dict[str, Any]:
    """Informational only: a torn line may even be a whole, correctly chained record that lost its newline."""
    try:
        from adapters.contract_validation import strict_json
        rec = LedgerRecord(**strict_json(torn.decode("utf-8")))
    except Exception:   # any partial or malformed bytes
        return {"classification": "partial"}
    body = {"seq": rec.seq, "record_type": rec.record_type, "payload": rec.payload,
            "prev_hash": rec.prev_hash, "corrects": rec.corrects}
    if rec.hash_version == 2:
        body.update(ts_utc=rec.ts_utc, hash_version=2)
    chained = (rec.seq == len(prefix_ledger.records) and rec.prev_hash == prefix_ledger.head
               and isinstance(rec.payload, dict) and sha256_json(body) == rec.hash)
    if chained:
        return {"classification": "complete_unterminated", "torn_record_hash": rec.hash,
                "torn_record_type": rec.record_type}
    return {"classification": "partial"}


def _quarantine_files(path: str) -> list[str]:
    return sorted(p for p in glob.glob(glob.escape(path) + ".torn-*") if not p.endswith(".json"))


def recover_torn_tail(path: str, constitution_hash: str, *, recovered_by: str, reason: str,
                      expected_head: str | None = None, quarantine_complete_record: bool = False) -> dict[str, Any]:
    """Quarantine a torn final line, truncate to the last complete record and record the recovery in the chain.

    ``expected_head``, when given, is the last head the caller knows was acknowledged; the head before the
    torn line must equal it. Returns ``{"torn": False, ...}`` when the ledger ends cleanly (after completing
    any quarantine whose ledger event is missing). Raises ``WriterConflict`` while a writer holds the ledger,
    and ``RecoveryRefused`` when the complete records do not verify, no complete record exists, the head
    differs from ``expected_head``, or the final line is a complete record without proof it was never
    acknowledged; in each case nothing is changed.
    """
    recovered_by = _require_text("recovered_by", recovered_by)
    reason = _require_text("reason", reason)
    if not os.path.exists(path):
        raise RecoveryRefused("no ledger file at that path")
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
            cut = data.rfind(b"\n") + 1
            if cut == 0:
                raise RecoveryRefused("no complete record exists (the genesis line itself is torn)")
            prefix, torn = data[:cut], data[cut:]
            prefix_ledger = _verified_prefix(path, constitution_hash, prefix)
            if expected_head is not None and prefix_ledger.head != expected_head:
                raise RecoveryRefused("the head before the torn line is not the expected acknowledged head: "
                                      "truncation, a fork or an acknowledged record would be lost")
            digest = hashlib.sha256(torn).hexdigest()
            qpath = f"{path}.torn-{digest}"
            meta = {"torn_sha256": "sha256:" + digest, "torn_bytes": len(torn), "prior_head": prefix_ledger.head,
                    "complete_records": len(prefix_ledger.records), **_classify(torn, prefix_ledger)}
            if meta["classification"] == "complete_unterminated":
                if expected_head is None and not quarantine_complete_record:
                    raise RecoveryRefused(
                        "the final line is a complete, correctly chained record that lacks only its newline; it may "
                        "have been acknowledged. Pass expected_head (the last acknowledged head) or "
                        "quarantine_complete_record=True after checking")
                meta["unacknowledged_proof"] = ("expected_head matched" if expected_head is not None
                                                else "quarantine_complete_record accepted by the caller")
            elif expected_head is not None:
                meta["unacknowledged_proof"] = "expected_head matched"
            if os.path.exists(qpath):
                with open(qpath, "rb") as fh:
                    if fh.read() != torn:
                        raise RecoveryRefused(f"{os.path.basename(qpath)} exists with different bytes")
            else:
                _write_durable(qpath, torn)
            if not os.path.exists(qpath + ".json"):
                _write_durable(qpath + ".json", json.dumps(meta, sort_keys=True).encode("utf-8"))
            with open(path, "r+b") as fh:   # only after the copy is durable
                fh.truncate(cut)
                fh.flush()
                os.fsync(fh.fileno())
            _fsync_dir(path)
            quarantined = {"quarantine_file": os.path.basename(qpath), **meta}
    finally:
        lock.close()
    recorded = _record_quarantines(path, constitution_hash, recovered_by=recovered_by, reason=reason)
    return {"torn": quarantined is not None, "quarantined": quarantined, "recorded": recorded}


def _record_quarantines(path: str, constitution_hash: str, *, recovered_by: str, reason: str) -> list[dict[str, Any]]:
    """Append the ledger event for every quarantine file that has none yet (idempotent, under the writer lock)."""
    files = _quarantine_files(path)
    if not files:
        return []
    ledger = EvidenceLedger(constitution_hash, path=path)
    try:
        seen = {r.payload.get("torn_sha256") for r in ledger.by_type("event") if r.payload.get("type") == EVENT_TYPE}
        written = []
        for qpath in files:
            with open(qpath, "rb") as fh:
                torn = fh.read()
            digest = "sha256:" + hashlib.sha256(torn).hexdigest()
            if digest in seen:
                continue
            meta: dict[str, Any] = {"classification": "unknown: sidecar missing"}
            if os.path.exists(qpath + ".json"):
                with open(qpath + ".json", "rb") as fh:
                    meta = json.loads(fh.read().decode("utf-8"))
            payload = {"type": EVENT_TYPE, **meta, "torn_sha256": digest, "torn_bytes": len(torn),
                       "quarantine_file": os.path.basename(qpath), "recovered_by": recovered_by, "reason": reason,
                       "disposition": ("quarantined, not chained: the torn append never returned to its caller; "
                                       "its bytes are preserved beside the ledger")}
            record = ledger.append("event", payload)
            seen.add(digest)
            written.append({"quarantine_file": payload["quarantine_file"], "record_hash": record.hash})
        return written
    finally:
        ledger.close()
