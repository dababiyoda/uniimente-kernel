"""Explicit, evidence-preserving recovery of a torn Evidence Ledger tail.

A process killed in the middle of an append can leave a partially written last line. ``EvidenceLedger``
refuses to open such a file, which protects history but leaves the body unable to restart: the founder-loop
entry gate's proof P2 (interruption and autonomous recovery) cannot pass while canonical history cannot be
reopened. Opening a torn ledger still fails closed; this module is the repair, and it is never automatic.

``recover_torn_tail`` runs only for an accountable caller (a supervisor, an operator, a test harness) that
names itself and a reason. Holding the ledger's single-writer lock for the whole procedure, it:

1. refuses unless every complete line verifies, in memory, as a chain anchored to the expected constitution;
2. refuses unless the tail is something one interrupted append can leave: a byte prefix of the next record's
   line as ``EvidenceLedger`` serializes it (printable ASCII JSON in a fixed field order beginning
   ``{"seq": <n>, "ts_utc": "``, whose ``prev_hash``, once written, is this chain's head), optionally followed
   by NUL padding, or a run of NULs from a zero-filled extent. Anything else is refused as not a torn append:
   a complete object followed by more bytes, a fork, a field the writer never writes, control or non-ASCII
   bytes, and NULs inside the content (a storage stack that reorders writes after power loss can leave such a
   hole, but so can zeroing an acknowledged record; that case is left to a person);
3. refuses unless the caller has acknowledged, by name, every risk that cannot be excluded (below);
4. writes, atomically and durably, a copy of the torn bytes to ``<ledger>.torn-<16 hex of the prior head>-<sha256>``
   and a ``.json`` sidecar that records what was found, who is recovering it, and the exact
   ``ledger.torn_tail_quarantined`` event line it is about to write (the plan);
5. applies the plan in place: writes the event over the torn bytes, cuts the file to the event's length, then
   writes the event's newline, with an fsync after each step. Until the newline is written the file never ends
   with a newline, so ``EvidenceLedger`` keeps refusing to open it: no restarting writer can ever append to a
   ledger whose repair is not yet recorded. A call that finds a plan already being applied (a crash in step 5)
   completes that plan; a plan whose application never began is replaced by the new caller's own.

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
* ``"complete_record"``: the record's hash was fully written (``complete_unterminated``, ``content_complete`` or
  ``content_complete_unverified``). From then on the record's identity is fixed, and a crash in its last bytes
  and damage after it was acknowledged leave the same bytes; no checkpoint taken before it can tell them apart,
  so this risk must be named even when ``expected_head`` matches.
* ``"stop_record"``: the torn bytes show a stop: a ledger seal, a standing-cognition suspension, a founder
  preference or answer, a capability detach, a goal revocation, supersession or pause, or an event whose type
  or status names a suspension, revocation, disable, demotion, halt, kill, pause, stop, seal, freeze, detach
  or shutdown. It never took effect, so recovery does not undo it, but whoever issued it may believe it did;
  the stop must be re-issued before the body restarts. A tail whose type or content cannot exclude a stop
  carries the same warning in the event without a required acknowledgment.

Not recoverable here, on purpose: an empty file and a torn or zero-filled genesis line. Nothing distinguishes
them from an acknowledged history truncated to nothing, so a person decides (rename the file aside as
evidence, then start a fresh ledger).

Debris: a crash while a copy is written can leave a ``.tmp-`` file beside the ledger (an incomplete copy of
bytes that are still in the ledger, or a second link to a complete quarantine). Such files are never taken for
quarantines and never chained. Quarantine files whose name is not recorded in this chain (another ledger once
kept at the same path, a file changed after it was written) are reported, never chained.

This module grants no authority and runs nothing; it repairs the file format so the canonical ledger can be
reopened and reconciled. The writer lock is keyed on the path string (as in ``EvidenceLedger``), so a
symlinked path, or a ledger file with more than one hard link, is refused: it cannot prove there is no live
writer. Directories in the path are resolved physically, as the operating system resolves them.
"""
from __future__ import annotations

import fcntl
import hashlib
import io
import json
import os
import re
from dataclasses import asdict
from typing import Any

from .ledger import EvidenceLedger, LedgerRecord, WriterConflict, sha256_json

EVENT_TYPE = "ledger.torn_tail_quarantined"
RISKS = ("unanchored", "complete_record", "stop_record")
STOP_RECORD_TYPES = frozenset({"seal", "egregore.suspended", "egregore.goal_preference", "egregore.founder_answer",
                               "egregore.capability_detached"})
# Record types that carry a stop depending on what they say: a goal revoked, superseded or paused; an event
# whose type or status names a stop.
CONTENT_STOP_TYPES = frozenset({"egregore.goal_transition", "event"})
# Record types known never to carry a stop. Every other type is treated as a possible stop (a warning).
NON_STOP_RECORD_TYPES = frozenset({
    "grant_dispatch", "witness", "receipt", "outcome", "workflow", "checkpoint", "capsule",
    "egregore.acquisition_plan", "egregore.advancement_report", "egregore.advancement_resolved",
    "egregore.asset_retained", "egregore.capability_attached", "egregore.capability_deficit",
    "egregore.capability_qualification", "egregore.change_proposed", "egregore.cognition_cycle",
    "egregore.cycle_conflict", "egregore.deficit", "egregore.discrepancy_reviewed", "egregore.experience_conflict",
    "egregore.experience_contradiction", "egregore.experience_integrated", "egregore.founder_ask",
    "egregore.goal_authorized", "egregore.goal_candidate_bound", "egregore.goal_conflict", "egregore.goal_drift",
    "egregore.goal_intake_draft", "egregore.gps_fix", "egregore.gravity_turn", "egregore.gravity_turn_conflict",
    "egregore.intersection_detected", "egregore.intervention", "egregore.intervention_classified",
    "egregore.opportunity_package", "egregore.outcome_discrepancy", "egregore.outcome_verified",
    "egregore.prepared_work", "egregore.reconciliation", "egregore.reserved_source_refused", "egregore.resumed",
    "egregore.return_report", "egregore.signal_conflict", "egregore.signal_ingested",
    "egregore.signal_not_monitored",
})
_STOP_MARKER = re.compile(r'"(?:type|status|kind)": "[^"]*(?:suspend|revok|supersed|paus|disabl|demot|halt|kill'
                          r'|stop|seal|freez|detach|shutdown)[^"]*"|"reason": "(?:revoked by|superseded by)')
_ROUTINE_TRANSITION = re.compile(r'"reason": "(?:wake|sleep): ')
_TYPE = re.compile(r'"record_type": "([A-Za-z0-9_.:-]+)"')
_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_HEAD_KEYS = ["seq", "ts_utc", "record_type", "payload"]   # the fields the writer serializes before prev_hash
_PREV = ', "prev_hash": '
_CORRECTS = ', "corrects": '
_STOP_WARNING = ("the torn record may have been a stop (a seal, suspension, founder control, revocation or "
                 "detach) that never took effect; re-issue it before the body restarts")


class RecoveryRefused(RuntimeError):
    """Nothing was changed in the ledger: the file is not a verifiable chain with only a torn final line, a risk
    that cannot be excluded was not acknowledged, or a precondition (space, ownership, aliasing) does not hold."""


class RecoveryInterrupted(RuntimeError):
    """The plan was durable and its application failed part way. The ledger is still unopenable; calling
    ``recover_torn_tail`` again completes the same plan."""


def _fsync_dir(path: str) -> None:
    fd = os.open(os.path.dirname(path) or ".", os.O_RDONLY)
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


def _verified_prefix(constitution_hash: str, prefix: bytes) -> EvidenceLedger:
    """Verify the complete lines as a chain, in memory, with the same checks ``EvidenceLedger._load`` applies
    (text mode with universal newlines, every line terminated and non-blank, strict JSON, exact fields)."""
    from adapters.contract_validation import strict_json
    records = []
    try:
        for line in io.TextIOWrapper(io.BytesIO(prefix), encoding="utf-8"):
            if not line.endswith("\n") or not line.strip():
                raise ValueError("partial or blank history record")
            records.append(LedgerRecord(**strict_json(line)))
    except (TypeError, ValueError) as exc:
        raise RecoveryRefused(f"the complete records do not verify, so this is not a torn tail: {exc}") from exc
    ledger = EvidenceLedger(constitution_hash)   # pathless: nothing is read or written
    ledger.records = records
    ok, msg = ledger.verify_chain()
    if not ok:
        raise RecoveryRefused(f"the complete records do not verify, so this is not a torn tail: {msg}")
    return ledger


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


def _top_level_prev(text: str) -> tuple[int, dict] | None:
    """Where the record's own ``prev_hash`` field begins, with the fields before it, if it is visible.

    The payload may contain the same text; only the occurrence that closes exactly the writer's leading fields
    parses, because a nested one leaves the payload's braces open."""
    start = 0
    while True:
        at = text.find(_PREV, start)
        if at < 0:
            return None
        try:
            head = json.loads(text[:at] + "}")
        except ValueError:
            start = at + 1
            continue
        if not isinstance(head, dict):
            start = at + 1
            continue
        if list(head) != _HEAD_KEYS:
            raise RecoveryRefused("the tail's fields are not the ones the writer serializes, in its order: "
                                  "not a torn append")
        return at, head


def _hash_prefix_ok(value: str) -> bool:
    """``value`` can be the beginning of a ``sha256:<64 hex>`` string."""
    return ("sha256:".startswith(value) if len(value) <= 7 else
            value.startswith("sha256:") and re.fullmatch(r"[0-9a-f]{0,64}", value[7:]) is not None)


def _content_complete(text: str, at: int, head: dict, prefix_ledger: EvidenceLedger) -> dict[str, Any] | None:
    """Check what follows the record's ``prev_hash`` and classify a tail whose hash was fully written.

    Returns ``None`` while the hash is incomplete (an ordinary partial write). Once the hash's 64 hex digits are
    written the record's identity is fixed, so the tail is never ``partial``. ``corrects`` follows the hash and may
    be any string, so it is rebuilt from what is visible (null, a complete string, or a chain hash the visible part
    begins) and the record is verified by recomputing its hash. A fork, bytes after the hash that cannot be the
    closing fields, or a fully visible record whose hash does not match are refused."""
    after_prev = text[at + len(_PREV):]
    expected_prev = json.dumps(prefix_ledger.head) + ', "hash": "'
    if not after_prev.startswith(expected_prev):
        if expected_prev.startswith(after_prev):
            return None
        raise RecoveryRefused("the tail's prev_hash is not this chain's head: a fork or damage, not a torn append")
    hash_text = after_prev[len(expected_prev):]
    if len(hash_text) < 71:
        if _hash_prefix_ok(hash_text):
            return None
        raise RecoveryRefused("the tail's hash field holds bytes no hash has: not a torn append")
    claimed, after = hash_text[:71], hash_text[71:]
    if not _HASH.fullmatch(claimed):
        raise RecoveryRefused("the tail's hash field holds bytes no hash has: not a torn append")
    template = '"' + _CORRECTS   # closing quote of the hash, then corrects, then "hash_version": 2
    visible = None
    visible_complete = False
    if after.startswith(template):
        try:
            visible, _ = json.JSONDecoder().raw_decode(after[len(template):])
            visible_complete = True
        except ValueError:
            pass
        if visible_complete and visible is not None and not isinstance(visible, str):
            raise RecoveryRefused("the tail's corrects field is neither null nor a string: not a torn append")
    elif not template.startswith(after):
        raise RecoveryRefused("the bytes after the tail's hash are not the record's closing fields: not a torn append")
    candidates = [visible] if visible_complete else [None, *(r.hash for r in prefix_ledger.records)]
    for corrects in candidates:
        if not ('%s%s, "hash_version": 2}' % (template, json.dumps(corrects))).startswith(after):
            continue
        rec = _chained({**head, "prev_hash": prefix_ledger.head, "hash": claimed, "corrects": corrects,
                        "hash_version": 2}, prefix_ledger)
        if rec is not None:
            return {"classification": "content_complete", "torn_record_hash": rec.hash,
                    "torn_record_type": rec.record_type}
    if visible_complete:
        raise RecoveryRefused("the tail's written hash does not match its own fields: not a torn append")
    # corrects is cut, or not yet written, and is no hash of this chain: the record cannot be rebuilt, but its
    # hash was written, so it is treated as complete
    return {"classification": "content_complete_unverified", "torn_record_hash_written": claimed,
            "torn_record_type": head.get("record_type") if isinstance(head.get("record_type"), str) else None}


def _stop_assessment(torn_type: str | None, text: str, payload_closed: bool) -> str:
    """``"stop"`` (needs ``stop_record``), ``"possible"`` (warned) or ``"no"``."""
    if torn_type is None:
        return "possible"
    if torn_type in STOP_RECORD_TYPES:
        return "stop"
    if torn_type in CONTENT_STOP_TYPES:
        at = text.find('"payload": ')
        if at >= 0 and _STOP_MARKER.search(text, at):
            return "stop"
        if torn_type == "egregore.goal_transition" and at >= 0 and _ROUTINE_TRANSITION.search(text, at):
            return "no"   # GoalRegistry.wake and sleep never revoke, supersede or pause
        return "no" if payload_closed else "possible"
    return "no" if torn_type in NON_STOP_RECORD_TYPES else "possible"


def _classify(torn: bytes, prefix_ledger: EvidenceLedger) -> dict[str, Any]:
    """Decide whether the tail can be a torn write of the next record, how complete it is, and whether it may be a
    stop. Raises ``RecoveryRefused`` for anything a single interrupted append cannot have produced."""
    if not torn.strip(b"\x00"):
        return {"classification": "zero_fill", "torn_record_type": None, "stop": "possible"}
    core = torn.rstrip(b"\x00")
    if b"\x00" in core:
        raise RecoveryRefused("the tail has a zero-filled hole inside the record. A storage stack that reorders writes "
                              "can leave that, but so can zeroing an acknowledged record: not accepted; investigate")
    if any(b > 0x7E or b < 0x20 for b in core):
        raise RecoveryRefused("the tail holds bytes the writer never writes (control or non-ASCII): not a torn append")
    text = core.decode("ascii")
    expected = '{"seq": %d, "ts_utc": "' % len(prefix_ledger.records)
    if not (text.startswith(expected) or expected.startswith(text)):
        raise RecoveryRefused("the tail is not the beginning of the next record: not a torn append")
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
                "torn_record_type": rec.record_type,
                "stop": _stop_assessment(rec.record_type, text, payload_closed=True)}
    top = _top_level_prev(text)
    found_complete = _content_complete(text, top[0], top[1], prefix_ledger) if top else None
    if found_complete is not None:
        found_complete["stop"] = _stop_assessment(found_complete["torn_record_type"], text, payload_closed=True)
        return found_complete
    return {"classification": "partial", "torn_record_type": torn_type,
            "stop": _stop_assessment(torn_type, text, payload_closed=top is not None)}


def _quarantine_name(path: str, prior_head: str, digest_hex: str) -> str:
    return f"{path}.torn-{prior_head.split(':', 1)[-1][:16]}-{digest_hex}"


def _quarantine_files(path: str) -> list[str]:
    """Exactly the quarantine files this module writes (never backups, editor files, scratch or sidecars)."""
    directory, base = os.path.split(path)
    pattern = re.compile(re.escape(base) + r"\.torn-[0-9a-f]{16}-[0-9a-f]{64}")
    return sorted(os.path.join(directory, name) for name in os.listdir(directory or ".") if pattern.fullmatch(name))


def _read_json(path: str) -> dict | None:
    try:
        with open(path, "rb") as fh:
            value = json.loads(fh.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _plan_in_progress(path: str, cut: int, tail: bytes, prefix_ledger: EvidenceLedger) -> dict | None:
    """The plan whose application a crash interrupted, if the tail is exactly a mix of its event line and the
    torn bytes it is replacing (byte by byte, the event's byte, the torn byte or a zero) and differs from the torn
    bytes (a plan whose application never began is simply replaced)."""
    head16 = prefix_ledger.head.split(":", 1)[-1][:16]
    for qpath in _quarantine_files(path):
        if not os.path.basename(qpath).startswith(f"{os.path.basename(path)}.torn-{head16}-"):
            continue
        side = _read_json(qpath + ".json")
        plan = side.get("plan") if side else None
        if not isinstance(plan, dict) or plan.get("cut") != cut or side.get("prior_head") != prefix_ledger.head:
            continue
        try:
            with open(qpath, "rb") as fh:
                original = fh.read()
            line = plan["event_line"].encode("ascii")
        except (OSError, KeyError, AttributeError, UnicodeError):
            continue
        if not qpath.endswith("-" + hashlib.sha256(original).hexdigest()) or tail == original:
            continue
        # a write that stopped part way leaves anything from the torn bytes' length up to the event's; a cut to the
        # event's length can be shorter than the torn bytes
        if not (len(original) <= len(tail) <= max(len(original), len(line)) or len(tail) == len(line)):
            continue
        if all(b in (line[i] if i < len(line) else None, original[i] if i < len(original) else None, 0)
               for i, b in enumerate(tail)):
            return side
    return None


def _apply(path: str, cut: int, line: bytes) -> None:
    """Write the event line over the torn bytes, cut the file to it, then terminate it; fsync after each step, so
    the file ends with a newline only once the whole event is durable."""
    fd = os.open(path, os.O_RDWR)
    try:
        os.pwrite(fd, line, cut)
        os.fsync(fd)
        os.ftruncate(fd, cut + len(line))
        os.fsync(fd)
        os.pwrite(fd, b"\n", cut + len(line))
        os.fsync(fd)
    finally:
        os.close(fd)


def _unrecorded(path: str, ledger_records: list[LedgerRecord]) -> list[str]:
    seen = {r.payload.get("quarantine_file") for r in ledger_records
            if r.record_type == "event" and r.payload.get("type") == EVENT_TYPE}
    return [os.path.basename(q) for q in _quarantine_files(path) if os.path.basename(q) not in seen]


def recover_torn_tail(path: str, constitution_hash: str, *, recovered_by: str, reason: str,
                      expected_head: str | None = None, acknowledged_risks: tuple[str, ...] | list[str] = ()
                      ) -> dict[str, Any]:
    """Quarantine a torn final line and replace it, in place, with a chained record of the recovery.

    Returns ``{"torn", "quarantined", "recorded", "resumed", "unrecorded_quarantines"}``. ``torn`` is False when
    the ledger ends cleanly (nothing is changed then). ``resumed`` is True when this call completed a plan a
    crashed call had begun applying; that plan's caller, risks and anchor stand, and this caller is returned as
    ``completed_by``. Raises ``WriterConflict`` while a writer holds the ledger, ``RecoveryRefused`` when the tail
    is not a torn append, the complete records do not verify, the head differs from ``expected_head``, a risk
    applies that ``acknowledged_risks`` does not name, or a precondition does not hold (nothing in the ledger is
    changed in any of those cases), and ``RecoveryInterrupted`` if applying a durable plan fails part way.
    """
    recovered_by = _require_text("recovered_by", recovered_by)
    reason = _require_text("reason", reason)
    acknowledged = sorted(set(acknowledged_risks))
    unknown = [r for r in acknowledged if r not in RISKS]
    if unknown:
        raise ValueError(f"unknown risks {unknown}; the risks are {list(RISKS)}")
    if os.path.islink(path):
        raise RecoveryRefused("call recovery with the ledger's own path, not a symlink to it")
    path = os.path.join(os.path.realpath(os.path.dirname(path) or "."), os.path.basename(path))
    if not os.path.isfile(path):
        raise RecoveryRefused("no ledger file at that path")
    if os.stat(path).st_nlink > 1:   # a hard link is another path, with its own lock file, to the same bytes
        raise RecoveryRefused("the ledger file has more than one hard link, so a writer holding the lock through "
                              "another name would not be seen; remove the extra links before recovering")
    lock = open(path + ".lock", "a")
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise WriterConflict("the ledger has a live writer; stop it before recovering") from exc
        with open(path, "rb") as fh:
            data = fh.read()
        if not data:
            raise RecoveryRefused("the ledger file is empty: nothing distinguishes an interrupted first write from an "
                                  "acknowledged history truncated to nothing, so a person decides")
        if data.endswith(b"\n"):
            try:
                ledger = EvidenceLedger(constitution_hash, path=path, read_only=True)
            except ValueError as exc:
                raise RecoveryRefused(f"the ledger ends cleanly but does not verify: {exc}") from exc
            return {"torn": False, "quarantined": None, "recorded": [], "resumed": False,
                    "unrecorded_quarantines": _unrecorded(path, ledger.records)}
        cut = data.rfind(b"\n") + 1
        if cut == 0:
            raise RecoveryRefused("no complete record exists (the genesis line itself is torn): nothing distinguishes "
                                  "that from an acknowledged history cut back to it, so a person decides")
        prefix, torn = data[:cut], data[cut:]
        prefix_ledger = _verified_prefix(constitution_hash, prefix)
        if expected_head is not None and prefix_ledger.head != expected_head:
            raise RecoveryRefused("the head before the torn line is not the expected acknowledged head: "
                                  "truncation, a fork or an acknowledged record would be lost")
        side = _plan_in_progress(path, cut, torn, prefix_ledger)
        if side is not None:
            meta = {k: v for k, v in side.items() if k != "plan"}
            line = side["plan"]["event_line"].encode("ascii")
            resumed = True
        else:
            meta, line = _plan(path, constitution_hash, cut, torn, prefix_ledger, recovered_by=recovered_by,
                               reason=reason, expected_head=expected_head, acknowledged=acknowledged)
            resumed = False
        try:
            _apply(path, cut, line)
        except OSError as exc:
            raise RecoveryInterrupted(f"applying the recovery failed part way ({exc}); the plan is durable and the "
                                      "ledger still refuses to open; call recover_torn_tail again to complete it") from exc
        try:
            ledger = EvidenceLedger(constitution_hash, path=path, read_only=True)   # verifies the result end to end
        except ValueError as exc:
            raise RecoveryInterrupted(f"the ledger after recovery does not verify: {exc}") from exc
        record = ledger.records[-1]
        if (len(ledger.records) != len(prefix_ledger.records) + 1 or record.record_type != "event"
                or record.payload.get("quarantine_file") != meta["quarantine_file"]):
            raise RecoveryInterrupted("the ledger after recovery is not the verified prefix plus its recovery event")
        out_meta = {**meta, "completed_by": recovered_by} if resumed else meta
        return {"torn": True, "quarantined": out_meta, "resumed": resumed,
                "recorded": [{"quarantine_file": meta["quarantine_file"], "record_hash": record.hash}],
                "unrecorded_quarantines": _unrecorded(path, ledger.records)}
    finally:
        lock.close()


def _plan(path: str, constitution_hash: str, cut: int, torn: bytes, prefix_ledger: EvidenceLedger, *,
          recovered_by: str, reason: str, expected_head: str | None,
          acknowledged: list[str]) -> tuple[dict[str, Any], bytes]:
    """Classify, check the acknowledgments, then write the quarantine copy and its sidecar with the exact event
    line to apply. Everything is durable before the ledger is touched."""
    found = _classify(torn, prefix_ledger)
    stop = found.pop("stop")
    torn_type = found.get("torn_record_type")
    risks = []
    if expected_head is None:
        risks.append("unanchored")
    if found["classification"] in ("complete_unterminated", "content_complete", "content_complete_unverified"):
        risks.append("complete_record")   # a stale checkpoint matches as well as a fresh one (review R1b)
    if stop == "stop":
        risks.append("stop_record")
    missing = [r for r in risks if r not in acknowledged]
    if missing:
        why = {"unanchored": "no expected_head, so an acknowledged record cut back to look torn cannot be excluded",
               "complete_record": ("the tail holds a complete record (its hash was written); it may have been "
                                   "acknowledged and damaged later, and no checkpoint taken before it can exclude that"),
               "stop_record": (f"the torn record is a {torn_type} that shows a stop which never took effect; whoever "
                               "issued it must re-issue it before the body restarts")}
        raise RecoveryRefused("acknowledge these risks to proceed, or supply expected_head where it applies: "
                              + "; ".join(f"{r}: {why[r]}" for r in missing))
    digest = hashlib.sha256(torn).hexdigest()
    qpath = _quarantine_name(path, prefix_ledger.head, digest)
    anchored = expected_head is not None
    meta = {"type": EVENT_TYPE, "quarantine_file": os.path.basename(qpath), "torn_sha256": "sha256:" + digest,
            "torn_bytes": len(torn), "prior_head": prefix_ledger.head, "complete_records": len(prefix_ledger.records),
            **found, "may_have_been_a_stop": stop != "no",
            "stop_warning": _STOP_WARNING if stop != "no" else None,
            "anchor": ("expected_head matched" if anchored else
                       "none supplied: an acknowledged record cut back to look like a partial write cannot be excluded"),
            "acknowledged_risks": risks, "recovered_by": recovered_by, "reason": reason,
            "disposition": ("quarantined, not chained: the head before it matched the caller's expected head; if "
                            "that was the writer's last acknowledged head, this append never returned" if anchored else
                            "quarantined, not chained, unanchored: assumed to be an append that never returned; an "
                            "acknowledged record cut back to look torn cannot be excluded")}
    scratch = EvidenceLedger(constitution_hash)   # pathless: builds the event exactly as the writer would
    scratch.records = list(prefix_ledger.records)
    record = scratch.append("event", meta)
    line = json.dumps(asdict(record), allow_nan=False).encode("ascii")
    if os.path.exists(qpath):
        with open(qpath, "rb") as fh:
            if fh.read() != torn:
                raise RecoveryRefused(f"{os.path.basename(qpath)} exists with different bytes; investigate before "
                                      "recovering")
    sidecar = {**meta, "plan": {"cut": cut, "event_line": line.decode("ascii"), "event_hash": record.hash}}
    try:
        if not os.path.exists(qpath):
            _write_atomic(qpath, torn, replace=False)
        # The sidecar describes this incident and holds the plan. A plan whose application never began (the torn
        # bytes are still exactly in place) is replaced here by this caller's own.
        _write_atomic(qpath + ".json", json.dumps(sidecar, sort_keys=True).encode("utf-8"), replace=True)
    except OSError as exc:
        raise RecoveryRefused(f"the quarantine copy could not be written ({exc}); the ledger is unchanged") from exc
    return meta, line
