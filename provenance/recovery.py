"""Explicit, evidence-preserving recovery of a torn Evidence Ledger tail.

A process killed in the middle of an append can leave a partially written last line. ``EvidenceLedger``
refuses to open such a file, which protects history but leaves the body unable to restart: the founder-loop
entry gate's proof P2 (interruption and autonomous recovery) cannot pass while canonical history cannot be
reopened. Opening a torn ledger still fails closed; this module is the repair, and it is never automatic.

``recover_torn_tail`` runs only for an accountable caller (a supervisor, an operator, a test harness) that
names itself and a reason. Holding the ledger's single-writer lock for the whole procedure, it:

1. refuses unless every complete line verifies, in memory, as a chain anchored to the expected constitution;
2. refuses unless the tail is something one interrupted append can leave: a byte prefix of the next record's
   line exactly as ``EvidenceLedger`` serializes it, optionally followed by NUL padding, or a run of NULs from
   a zero-filled extent. The checks run as far as the bytes go: the header ``{"seq": <n>, "ts_utc": "<time>",
   "record_type": "<type>", "payload": {``; once the record's own ``prev_hash`` is visible, the fields before it
   re-serialize to exactly those bytes and ``prev_hash`` is this chain's head; once hash digits are visible, they
   begin the hash those fields give with ``corrects`` null or a hash of this chain (otherwise the tail is
   ``partial_unverified``); once the hash is complete, the closing fields are this record's own. Anything else is
   refused as not a torn append: a complete object followed by more bytes, a fork, a field the writer never
   writes or writes elsewhere, control or non-ASCII bytes, and NULs inside the content (a storage stack that
   reorders writes after power loss can leave such a hole, but so can zeroing an acknowledged record; that case
   is left to a person). Damage inside a field that is still being written (a flipped payload byte before any
   hash digit is visible) cannot be seen in the bytes, and is the residual ``unanchored`` names;
3. refuses unless the caller has acknowledged, by name, every risk that cannot be excluded (below);
4. writes, atomically and durably, a copy of the torn bytes to ``<ledger>.torn-<16 hex of the prior head>-<sha256>``
   and a ``.json`` sidecar that records what was found, who is recovering it, and the plan: the exact
   ``ledger.torn_tail_quarantined`` event line to write, the offset, and the digest of the verified prefix;
5. applies the plan in place: writes the event over the torn bytes (every byte, checked by reading it back),
   cuts the file to the event's length, then writes the event's newline, with an fsync after each step. Until
   the newline is written the file never ends with a newline, so ``EvidenceLedger`` keeps refusing to open it:
   no restarting writer can ever append to a ledger whose repair is not yet recorded. The plan is then marked
   applied in its sidecar.

A call that finds a plan part-way applied completes it. The plan must be unapplied, written for exactly these
prefix bytes and offset, and the tail must show at least one of its event bytes in place of a torn byte (every
other byte being the event's, the torn bytes' own, the newline or a zero). The completing caller is added to the
sidecar before the plan is applied; the plan's caller, anchor and acknowledgments stand, and the caller's own
``expected_head`` is still checked. A plan whose application never began is replaced by the new caller's own.

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
  ``content_complete_unverified``), or its visible hash digits match no record this chain can hold
  (``partial_unverified``). From then on a crash in the record's last bytes and damage after it was
  acknowledged cannot be told apart; no checkpoint taken before it can either, so this risk must be named even
  when ``expected_head`` matches.
* ``"stop_record"``: the torn bytes show a stop that never took effect: a ledger seal, a standing-cognition
  suspension, a founder preference or answer, a capability detach, a goal revocation or supersession (the old
  goal's transition, or the replacement's authorization), an evolution capsule deciding kill or regress, or an
  event of a known stop type (an autonomy regression, a business termination, a provider withdrawal, a
  component disabled, a node or organ retired, an action revoked). Recovery does not undo it, but whoever
  issued it may believe it took effect; the stop must be re-issued before the body restarts. Record and event
  types are judged against explicit registries (tests require every type the code writes to be in one), never
  by words in their names. A tail whose type or content cannot exclude a stop (an unknown record or event type,
  or a cut before the deciding field) carries the same warning in the event without a required
  acknowledgment.

Not recoverable here, on purpose: an empty file and a torn or zero-filled genesis line. Nothing distinguishes
them from an acknowledged history truncated to nothing, so a person decides (rename the file aside as
evidence, then start a fresh ledger). A tail that is a recovery event whose plan is missing is refused too.

Debris: a crash while a copy is written can leave a ``.tmp-`` file beside the ledger (an incomplete copy of
bytes that are still in the ledger, or a second link to a complete quarantine); a failed write removes its own.
Such files are never taken for quarantines and never chained. Quarantine files whose name is not recorded in
this chain (another ledger once kept at the same path, a file changed after it was written) are reported, never
chained. On a ledger that ends cleanly, a last record that is a recovery event is returned as ``last_recovery``,
so a caller whose recovery was cut off after its event became durable still sees its stop warning.

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
# Record types that carry a stop depending on what they say.
CONTENT_STOP_TYPES = frozenset({"egregore.goal_transition", "egregore.goal_authorized", "capsule", "event"})
# Record types known never to carry a stop. Every other type is treated as a possible stop (a warning).
NON_STOP_RECORD_TYPES = frozenset({
    "grant_dispatch", "witness", "receipt", "outcome", "workflow", "checkpoint",
    "egregore.acquisition_plan", "egregore.advancement_report", "egregore.advancement_resolved",
    "egregore.asset_retained", "egregore.capability_attached", "egregore.capability_deficit",
    "egregore.capability_qualification", "egregore.change_proposed", "egregore.cognition_cycle",
    "egregore.cycle_conflict", "egregore.deficit", "egregore.discrepancy_reviewed", "egregore.experience_conflict",
    "egregore.experience_contradiction", "egregore.experience_integrated", "egregore.founder_ask",
    "egregore.goal_candidate_bound", "egregore.goal_conflict", "egregore.goal_drift",
    "egregore.goal_intake_draft", "egregore.gps_fix", "egregore.gravity_turn", "egregore.gravity_turn_conflict",
    "egregore.intersection_detected", "egregore.intervention", "egregore.intervention_classified",
    "egregore.opportunity_package", "egregore.outcome_discrepancy", "egregore.outcome_verified",
    "egregore.prepared_work", "egregore.reconciliation", "egregore.reserved_source_refused", "egregore.resumed",
    "egregore.return_report", "egregore.signal_conflict", "egregore.signal_ingested",
    "egregore.signal_not_monitored",
})
# Event payload types written by this code base, by what they mean. Any other event type is a possible stop.
STOP_EVENT_TYPES = frozenset({
    "action.revoked", "autonomy.regressed", "business.terminated", "foundry.node_retired", "omnimorph.organ_retired",
    "repair.component_disabled", "repair.provider_withdrawn",
})
NON_STOP_EVENT_TYPES = frozenset({
    *(f"action.{s}" for s in ("proposed", "evaluating", "pending_human", "granted", "executing", "committed",
                              "recorded", "refused", "failed", "reconciled")),
    *(f"autonomy.{k}" for k in ("issued", "promoted", "promotion_refused", "renewed")),
    *(f"auto_cycle.{k}" for k in ("branch_tested", "champion", "failures_analyzed", "generated", "no_improvement",
                                  "refused")),
    *(f"business.case_{s}" for s in ("buyer", "offer", "payment", "delivery", "customer_outcome")),
    "advantage.architecture_compiled", "advantage.closure_evaluated", "advantage.external_outcome_submitted",
    "advantage.genome_sealed", "advantage.opportunity_intake", "advantage.opportunity_replay_refused",
    "advantage.pipeline_snapshot", "advantage.route_tournament_completed", "advantage.tribunal_completed",
    "capabilities.competency_registered", "capabilities.routing_decision", "foundry.node_corrected",
    "omnimorph.activation_proposed", "omnimorph.gate_activation_recorded", "omnimorph.manifest_composed",
    "omnimorph.simulation_completed",
    "business.genome_compiled", "business.genome_refused", "capabilities.genome_registered",
    "capabilities.routing_outcome", "evolution.audit_complete", "evolution.audit_failed",
    "evolution.experiment_measured", "evolution.experiment_refused", "evolution.tree_selected",
    "evolution.whole_body", "foundry.distribution_evaluated", "incident.effect_mismatch", "loom.pattern_woven",
    "provenance.merkle_checkpoint", "repair.capability_loss_detected", "repair.capsule_recorded",
    "repair.component_restored", "repair.provider_registered", "repair.trial_complete", "treasury.allocated",
    "treasury.debt_recorded", "treasury.debt_repaid", "treasury.posted", "treasury.waterfall_stopped",
    "twins.verdict", "workflow.candidate_trial", "workflow.checkpoint_refused",
    "workflow.malformed_checkpoint_control", "workflow.provider_activated", "workflow.provider_restored",
    EVENT_TYPE,
})
_TYPE = re.compile(r'"record_type": "([A-Za-z0-9_.:-]+)"')
_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_HEAD_KEYS = ["seq", "ts_utc", "record_type", "payload"]   # the fields the writer serializes before prev_hash
_PREV = ', "prev_hash": '
_CORRECTS = ', "corrects": '
_STOP_WARNING = ("the torn record may have been a stop (a seal, suspension, founder control, revocation, "
                 "supersession, detach or kill) that never took effect; re-issue it before the body restarts")


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
    try:
        with open(tmp, "xb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
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


def _check_header(text: str, seq: int) -> None:
    """The visible bytes must begin ``{"seq": <seq>, "ts_utc": "<time>", "record_type": "<type>", "payload": {``,
    checked as far as they go (a time is digits, ``-``, ``:``, ``.``, ``T`` and ``Z``; a type is
    ``[A-Za-z0-9_.:-]``)."""
    parts = [('{"seq": %d, "ts_utc": "' % seq, None), (None, "0123456789-:.TZ"), ('", "record_type": "', None),
             (None, "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.:-"), ('", "payload": {', None)]
    i = 0
    for literal, alphabet in parts:
        if i >= len(text):
            return
        if literal is not None:
            seen = text[i:i + len(literal)]
            if not literal.startswith(seen):
                raise RecoveryRefused("the tail does not begin the way the writer serializes a record: not a torn "
                                      "append")
            i += len(literal)
        else:
            j = i
            while j < len(text) and text[j] in alphabet:
                j += 1
            if j == i and j < len(text):
                raise RecoveryRefused("the tail does not begin the way the writer serializes a record: not a torn "
                                      "append")
            i = j


def _payload_end(text: str) -> int | None:
    """Index just past the payload object's closing brace, found by a string-aware scan, if it is written."""
    start = text.find('"payload": {')
    if start < 0:
        return None
    depth, in_string, escaped = 0, False, False
    for i in range(start + len('"payload": '), len(text)):
        c = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_string = False
        elif c == '"':
            in_string = True
        elif c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0:
                return i + 1
    return None


def _top_level_prev(text: str) -> tuple[int, dict] | None:
    """Where the record's own ``prev_hash`` field begins, with the fields before it, once the payload is written.

    After the payload's closing brace the writer writes exactly ``, "prev_hash": ``; anything else is refused. The
    fields before it must re-serialize to exactly the visible bytes, so separators, order and spelling are the
    writer's."""
    at = _payload_end(text)
    if at is None:
        return None
    try:   # checked as soon as the payload closes, whether or not prev_hash is visible yet
        head = json.loads(text[:at] + "}")
    except ValueError as exc:
        raise RecoveryRefused("the tail's fields before prev_hash are not valid JSON: not a torn append") from exc
    if (not isinstance(head, dict) or list(head) != _HEAD_KEYS or not isinstance(head["payload"], dict)
            or json.dumps(head)[:-1] != text[:at]):
        raise RecoveryRefused("the tail's fields are not the ones the writer serializes, as it serializes them: "
                              "not a torn append")
    rest = text[at:]
    if not (rest.startswith(_PREV) or _PREV.startswith(rest)):
        raise RecoveryRefused("the bytes after the tail's payload are not the writer's prev_hash field: not a torn "
                              "append")
    return at, head


def _hash_prefix_ok(value: str) -> bool:
    """``value`` can be the beginning of a ``sha256:<64 hex>`` string."""
    return ("sha256:".startswith(value) if len(value) <= 7 else
            value.startswith("sha256:") and re.fullmatch(r"[0-9a-f]{0,64}", value[7:]) is not None)


def _candidate_hashes(head: dict, prefix_ledger: EvidenceLedger, corrects_values):
    """Lazily, the v2 hash these fields give with each ``corrects`` value (null first: nearly every record)."""
    body = {"seq": head["seq"], "record_type": head["record_type"], "payload": head["payload"],
            "prev_hash": prefix_ledger.head, "ts_utc": head["ts_utc"], "hash_version": 2}
    for c in corrects_values:
        yield c, sha256_json({**body, "corrects": c})


def _content_complete(text: str, at: int, head: dict, prefix_ledger: EvidenceLedger) -> dict[str, Any] | None:
    """Check what follows the record's ``prev_hash`` and classify the tail by how much of the record it holds.

    Returns ``None`` for an ordinary partial write. While hash digits are being written they must begin the hash
    these fields give with ``corrects`` null or a hash of this chain; if none does, the tail is
    ``partial_unverified``. Once the hash's 64 hex digits are written the record's identity is fixed and the tail
    is complete: ``corrects`` is rebuilt from what is visible (null, a complete string, or a chain hash the visible
    part begins) and the record is verified by recomputing its hash. A fork, bytes after the hash that cannot be
    the closing fields, or a fully visible record whose hash does not match are refused."""
    after_prev = text[at + len(_PREV):]
    expected_prev = json.dumps(prefix_ledger.head) + ', "hash": "'
    if not after_prev.startswith(expected_prev):
        if expected_prev.startswith(after_prev):
            return None
        raise RecoveryRefused("the tail's prev_hash is not this chain's head: a fork or damage, not a torn append")
    hash_text = after_prev[len(expected_prev):]
    if len(hash_text) < 71:
        if not _hash_prefix_ok(hash_text):
            raise RecoveryRefused("the tail's hash field holds bytes no hash has: not a torn append")
        if len(hash_text) <= 7:
            return None
        candidates = _candidate_hashes(head, prefix_ledger, [None, *(r.hash for r in prefix_ledger.records)])
        if any(h.startswith(hash_text) for _, h in candidates):
            return None
        return {"classification": "partial_unverified", "torn_record_type": head["record_type"]}
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
    values = [visible] if visible_complete else [None, *(r.hash for r in prefix_ledger.records)]
    values = [c for c in values if ('%s%s, "hash_version": 2}' % (template, json.dumps(c))).startswith(after)]
    for corrects, computed in _candidate_hashes(head, prefix_ledger, values):
        if computed == claimed:
            return {"classification": "content_complete", "torn_record_hash": claimed,
                    "torn_record_type": head["record_type"]}
    if visible_complete:
        raise RecoveryRefused("the tail's written hash does not match its own fields: not a torn append")
    # corrects is cut, or not yet written, and is no hash of this chain: the record cannot be rebuilt, but its
    # hash was written, so it is treated as complete
    return {"classification": "content_complete_unverified", "torn_record_hash_written": claimed,
            "torn_record_type": head["record_type"]}


def _event_assessment(event_type: str | None) -> str:
    """An event is judged by its own type against the registries; any other type is a possible stop (warned)."""
    if event_type in STOP_EVENT_TYPES:
        return "stop"
    return "no" if event_type in NON_STOP_EVENT_TYPES else "possible"


def _stop_assessment(torn_type: str | None, text: str, payload: dict | None) -> str:
    """``"stop"`` (needs ``stop_record``), ``"possible"`` (warned) or ``"no"``. ``payload`` is given once the record's
    payload is completely written; before that the visible text decides what it can."""
    if torn_type is None:
        return "possible"
    if torn_type in STOP_RECORD_TYPES:
        return "stop"
    if torn_type not in CONTENT_STOP_TYPES:
        return "no" if torn_type in NON_STOP_RECORD_TYPES else "possible"
    at = text.find('"payload": ')
    body = text[at:] if at >= 0 else ""
    if torn_type == "event":
        if payload is not None:
            t = payload.get("type")
            return _event_assessment(t if isinstance(t, str) else None)
        first = re.match(r'"payload": \{"type": "([^"]*)"', body)   # the writers put the type first
        return _event_assessment(first.group(1)) if first else "possible"
    if torn_type == "egregore.goal_transition":
        if re.search(r'"reason": "(?:revoked by|superseded by)', body) or re.search(
                r'"status": "(?:revoked|superseded)"', body):
            return "stop"
        if re.search(r'"reason": "(?:wake|sleep): ', body):
            return "no"   # GoalRegistry.wake and sleep never revoke or supersede
        return "no" if payload is not None else "possible"
    if torn_type == "egregore.goal_authorized":   # the first append of GoalRegistry.supersede
        if re.search(r'"supersedes": "', body):
            return "stop"
        if re.search(r'"supersedes": null', body) or payload is not None:
            return "no"
        return "possible"
    # capsule: an evolution decision
    if re.search(r'"decision": "(?:kill|regress)"', body, re.IGNORECASE):
        return "stop"
    return "no" if payload is not None else "possible"


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
    _check_header(text, len(prefix_ledger.records))
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
        if rec is None or rec.hash_version != 2 or json.dumps(asdict(rec), allow_nan=False) != text:
            raise RecoveryRefused("the tail is a complete object that is not the next record of this chain as the "
                                  "writer serializes it")
        if rec.record_type == "event" and rec.payload.get("type") == EVENT_TYPE:
            raise RecoveryRefused("the tail is a recovery event whose plan is missing; restore its sidecar or "
                                  "investigate before recovering")
        return {"classification": "complete_unterminated", "torn_record_hash": rec.hash,
                "torn_record_type": rec.record_type, "stop": _stop_assessment(rec.record_type, text, rec.payload)}
    top = _top_level_prev(text)
    found_complete = _content_complete(text, top[0], top[1], prefix_ledger) if top else None
    payload = top[1]["payload"] if top else None
    if found_complete is not None:
        found_complete["stop"] = _stop_assessment(found_complete["torn_record_type"], text, payload)
        return found_complete
    return {"classification": "partial", "torn_record_type": torn_type,
            "stop": _stop_assessment(torn_type, text, payload)}


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


def _plan_in_progress(path: str, cut: int, prefix_digest: str, tail: bytes,
                      prefix_ledger: EvidenceLedger) -> tuple[str, dict] | None:
    """The sidecar of the plan whose application a crash interrupted, if there is exactly that.

    The plan must be unapplied and written for these prefix bytes and this offset; its event line must be the
    next record of this chain; its quarantine's bytes must match the name; and the tail must differ from the torn
    bytes, show at least one event byte where it differs from the torn byte, and be, byte by byte, the event's
    byte, the torn byte, the newline right after the event, or a zero, with a length an interrupted application
    can leave."""
    head16 = prefix_ledger.head.split(":", 1)[-1][:16]
    for qpath in _quarantine_files(path):
        if not os.path.basename(qpath).startswith(f"{os.path.basename(path)}.torn-{head16}-"):
            continue
        side = _read_json(qpath + ".json")
        plan = side.get("plan") if side else None
        if (not isinstance(plan, dict) or plan.get("cut") != cut
                or plan.get("prefix_sha256") != prefix_digest or side.get("prior_head") != prefix_ledger.head):
            continue
        try:
            with open(qpath, "rb") as fh:
                original = fh.read()
            line = plan["event_line"].encode("ascii")
            rec = _chained(json.loads(line), prefix_ledger)
        except (OSError, KeyError, AttributeError, TypeError, ValueError):
            continue
        if (rec is None or rec.record_type != "event" or rec.payload.get("quarantine_file") != os.path.basename(qpath)
                or not qpath.endswith("-" + hashlib.sha256(original).hexdigest()) or tail == original):
            continue
        # An applied plan is resumed only when its own event line is exactly in place and only its newline is missing
        # (it can only be the same incident); anything else at that offset is a later tear.
        if plan.get("applied") and not (tail[:len(line)] == line and not tail[len(line):].strip(b"\x00")):
            continue
        if not (len(original) <= len(tail) <= max(len(original), len(line) + 1) or len(tail) in (len(line), len(line) + 1)):
            continue
        allowed_ok = all(b == 0 or (i < len(line) and b == line[i]) or (i == len(line) and b == 0x0A)
                         or (i < len(original) and b == original[i]) for i, b in enumerate(tail))
        began = any(i < len(line) and b == line[i] and b != 0 and (i >= len(original) or original[i] != b)
                    for i, b in enumerate(tail))
        if allowed_ok and began:
            return qpath, side
    return None


def _pwrite_all(fd: int, data: bytes, offset: int) -> None:
    view = memoryview(data)
    while view:
        written = os.pwrite(fd, view, offset)
        if written <= 0:
            raise OSError(28, "no bytes written")
        view, offset = view[written:], offset + written


def _apply(path: str, cut: int, line: bytes) -> None:
    """Write the event line over the torn bytes and read it back, cut the file to it, then terminate it, with an
    fsync after each step, so the file ends with a newline only once the whole event is durable."""
    fd = os.open(path, os.O_RDWR)
    try:
        _pwrite_all(fd, line, cut)
        os.fsync(fd)
        if os.pread(fd, len(line), cut) != line:
            raise OSError(5, "the event line did not read back as written")
        os.ftruncate(fd, cut + len(line))
        os.fsync(fd)
        _pwrite_all(fd, b"\n", cut + len(line))
        os.fsync(fd)
        if os.fstat(fd).st_size != cut + len(line) + 1 or os.pread(fd, len(line) + 1, cut) != line + b"\n":
            os.ftruncate(fd, cut + len(line))   # back to the resumable, unopenable state
            os.fsync(fd)
            raise OSError(5, "the recovery event did not read back as written")
    finally:
        os.close(fd)


def _unrecorded(path: str, ledger_records: list[LedgerRecord]) -> list[str]:
    seen = {r.payload.get("quarantine_file") for r in ledger_records
            if r.record_type == "event" and r.payload.get("type") == EVENT_TYPE}
    return [os.path.basename(q) for q in _quarantine_files(path) if os.path.basename(q) not in seen]


def _update_sidecar(qpath: str, side: dict, **plan_fields: Any) -> dict:
    updated = {**side, "plan": {**side["plan"], **plan_fields}}
    _write_atomic(qpath + ".json", json.dumps(updated, sort_keys=True).encode("utf-8"), replace=True)
    return updated


def recover_torn_tail(path: str, constitution_hash: str, *, recovered_by: str, reason: str,
                      expected_head: str | None = None, acknowledged_risks: tuple[str, ...] | list[str] = ()
                      ) -> dict[str, Any]:
    """Quarantine a torn final line and replace it, in place, with a chained record of the recovery.

    Returns ``{"torn", "quarantined", "recorded", "resumed", "unrecorded_quarantines"}`` (plus ``"last_recovery"``
    when the ledger ends cleanly). ``torn`` is False when the ledger ends cleanly (nothing is changed then).
    ``resumed`` is True when this call completed a plan a crashed call had begun applying; that plan's caller,
    risks and anchor stand, and this caller is returned as ``completed_by`` and added to the sidecar. Raises
    ``WriterConflict`` while a writer holds the ledger, ``RecoveryRefused`` when the tail is not a torn append, the
    complete records do not verify, the head differs from ``expected_head``, a risk applies that
    ``acknowledged_risks`` does not name, or a precondition does not hold (nothing in the ledger is changed in any
    of those cases), and ``RecoveryInterrupted`` if applying a durable plan fails part way.
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
            last = ledger.records[-1]
            last_recovery = ({**last.payload, "record_hash": last.hash}
                             if last.record_type == "event" and last.payload.get("type") == EVENT_TYPE else None)
            return {"torn": False, "quarantined": None, "recorded": [], "resumed": False,
                    "unrecorded_quarantines": _unrecorded(path, ledger.records), "last_recovery": last_recovery}
        cut = data.rfind(b"\n") + 1
        if cut == 0:
            raise RecoveryRefused("no complete record exists (the genesis line itself is torn): nothing distinguishes "
                                  "that from an acknowledged history cut back to it, so a person decides")
        prefix, torn = data[:cut], data[cut:]
        prefix_ledger = _verified_prefix(constitution_hash, prefix)
        if expected_head is not None and prefix_ledger.head != expected_head:
            raise RecoveryRefused("the head before the torn line is not the expected acknowledged head: "
                                  "truncation, a fork or an acknowledged record would be lost")
        prefix_digest = "sha256:" + hashlib.sha256(prefix).hexdigest()
        found = _plan_in_progress(path, cut, prefix_digest, torn, prefix_ledger)
        if found is not None:
            qpath, side = found
            try:   # the completing caller is on record before the plan is applied
                side = _update_sidecar(qpath, side, completions=[*side["plan"].get("completions", []),
                                                                 {"completed_by": recovered_by, "reason": reason}])
            except OSError as exc:
                raise RecoveryRefused(f"the sidecar could not be updated ({exc}); the ledger is unchanged") from exc
            meta = {k: v for k, v in side.items() if k != "plan"}
            line = side["plan"]["event_line"].encode("ascii")
            resumed = True
        else:
            qpath, side, line = _plan(path, constitution_hash, cut, torn, prefix_ledger, prefix_digest,
                                      recovered_by=recovered_by, reason=reason, expected_head=expected_head,
                                      acknowledged=acknowledged)
            meta = {k: v for k, v in side.items() if k != "plan"}
            resumed = False
        try:
            _apply(path, cut, line)
        except OSError as exc:
            raise RecoveryInterrupted(f"applying the recovery failed part way ({exc}); the plan is durable and the "
                                      "ledger still refuses to open; call recover_torn_tail again to complete it") from exc
        record = _chained(json.loads(line), prefix_ledger)   # the bytes before the cut were never written
        try:
            _update_sidecar(qpath, side, applied=record.hash)
        except OSError:
            pass   # the event is durable; an unmarked plan cannot match: its prefix bytes no longer end the ledger
        out_meta = {**meta, "completed_by": recovered_by} if resumed else meta
        return {"torn": True, "quarantined": out_meta, "resumed": resumed,
                "recorded": [{"quarantine_file": meta["quarantine_file"], "record_hash": record.hash}],
                "unrecorded_quarantines": _unrecorded(path, [*prefix_ledger.records, record])}
    finally:
        lock.close()


def _plan(path: str, constitution_hash: str, cut: int, torn: bytes, prefix_ledger: EvidenceLedger,
          prefix_digest: str, *, recovered_by: str, reason: str, expected_head: str | None,
          acknowledged: list[str]) -> tuple[str, dict, bytes]:
    """Classify, check the acknowledgments, then write the quarantine copy and its sidecar with the exact event
    line to apply. Everything is durable before the ledger is touched."""
    found = _classify(torn, prefix_ledger)
    stop = found.pop("stop")
    torn_type = found.get("torn_record_type")
    risks = []
    if expected_head is None:
        risks.append("unanchored")
    if found["classification"] in ("complete_unterminated", "content_complete", "content_complete_unverified",
                                   "partial_unverified"):
        risks.append("complete_record")   # a stale checkpoint matches as well as a fresh one (review R1b)
    if stop == "stop":
        risks.append("stop_record")
    missing = [r for r in risks if r not in acknowledged]
    if missing:
        why = {"unanchored": "no expected_head, so an acknowledged record cut back to look torn cannot be excluded",
               "complete_record": ("the tail holds a complete record (its hash was written), or hash digits no record "
                                   "of this chain gives; it may have been acknowledged and damaged later, and no "
                                   "checkpoint taken before it can exclude that"),
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
    side = {**meta, "plan": {"cut": cut, "prefix_sha256": prefix_digest, "event_line": line.decode("ascii"),
                             "event_hash": record.hash, "applied": None, "completions": []}}
    if not os.path.exists(qpath):
        try:
            _write_atomic(qpath, torn, replace=False)
        except OSError as exc:
            raise RecoveryRefused(f"the quarantine copy could not be written ({exc}); the ledger is unchanged") from exc
    try:
        # The sidecar describes this incident and holds the plan. A plan whose application never began (the torn
        # bytes are still exactly in place) is replaced here by this caller's own.
        _write_atomic(qpath + ".json", json.dumps(side, sort_keys=True).encode("utf-8"), replace=True)
    except OSError as exc:
        raise RecoveryRefused(f"the quarantine copy was written but its sidecar (the plan) could not be ({exc}); the "
                              "ledger is unchanged; a retry reuses the copy") from exc
    return qpath, side, line
