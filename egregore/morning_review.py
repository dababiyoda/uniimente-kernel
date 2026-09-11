"""Portable review of GREG-001 history; criticism is inert, unverified data.

This trusted-local developer client does not authenticate Alfonso. It neither
executes capabilities nor imports an authority issuer. The canonical Ledger owns
durability, integrity and writer exclusion. A history projection is not a fresh
source audit or independent verification of the machine that wrote the history.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace

from adapters.contract_validation import strict_json
from egregore.local_mission import receipt_for
from egregore.repository_audit import FILES, MAX_BLOB, derive
from events.spine import EventSpine
from provenance.ledger import EvidenceLedger, ReconciliationRequired, sha256_json

MAX_HISTORY = 8 * 1024 * 1024
MAX_NOTE_INPUT = 8192
NOTE_FIELDS = {"note_id", "mission_id", "review_head", "kind", "text", "evidence_refs"}
NOTE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
CLASSIFICATION = "UNVERIFIED_LOCAL_REVIEW_DATA"


def _open(path, constitution, *, read_only):
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_HISTORY:
        raise ValueError("existing bounded regular history file required")
    return EvidenceLedger(constitution, str(path), read_only=read_only)


def _prefix(ledger, head):
    ok, reason = ledger.verify_chain()
    if not ok:
        raise ValueError(reason)
    anchor = ledger.find(head)
    if anchor is None:
        raise ValueError("review head is absent from retained history")
    # A temporary read-only instance of the SAME canonical owner, never a store.
    snapshot = EvidenceLedger(ledger.constitution_hash, read_only=True)
    snapshot.records = copy.deepcopy(ledger.records[:anchor.seq + 1])
    return snapshot


def _sources(job, sources):
    repos = job["repositories"]
    if len(repos) != 3 or {r["role"] for r in repos} != set(FILES):
        raise ValueError("three retained repository bindings required")
    expected = {(r["role"], r["commit"], name) for r in repos for name in FILES[r["role"]]}
    if not isinstance(sources, list) or len(sources) != len(expected):
        raise ValueError("incomplete retained source manifest")
    observed = set()
    for source in sources:
        if set(source) != {"role", "commit", "file", "blob", "text"}:
            raise ValueError("unsupported retained source")
        raw = source["text"].encode("utf-8")
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if len(raw) > MAX_BLOB or source["blob"] != blob:
            raise ValueError("retained source bytes differ from blob binding")
        observed.add((source["role"], source["commit"], source["file"]))
    if observed != expected:
        raise ValueError("retained source scope differs from mission")
    return derive(sources, job["expected_pin"], job["expected_version"])


def _project(ledger, mission_id, head):
    snapshot = _prefix(ledger, head)
    try:
        EventSpine(snapshot)  # Canonical event identity/conflict validation.
        events = [r for r in snapshot.by_type("event")
                  if r.payload.get("type", "").startswith("greg.")
                  and r.payload.get("payload", {}).get("mission_id") == mission_id]
        def of_type(kind):
            return [r for r in events if r.payload["type"] == "greg." + kind]
        def data(record):
            return record.payload["payload"]["data"]
        submissions = of_type("submitted")
        if len(submissions) != 1:
            raise ValueError("one retained mission submission required")
        job = data(submissions[0])["job"]
        if job["mission_id"] != mission_id:
            raise ValueError("submission mission binding differs")
        # GREG-001 v1 identity; no live path validation or execution on replay.
        p = SimpleNamespace(proposal_id="greg-audit-" + sha256_json(job), payload=job)
        proposals = [r for r in snapshot.by_type("event")
                     if r.payload.get("type") == "action.proposed"
                     and r.payload.get("proposal_id") == p.proposal_id]
        actions = {r.payload["action_id"] for r in proposals}
        claims = [r for r in snapshot.by_type("grant_dispatch")
                  if r.payload.get("proposal_id") == p.proposal_id]
        outcomes = [r for r in snapshot.by_type("outcome") if r.payload.get("action_ref") in actions]
        receipts = [r for r in snapshot.by_type("receipt") if r.payload.get("action_id") in actions]
        workflows = [r for r in snapshot.by_type("workflow") if r.payload.get("workflow_id") == mission_id]
        acceptance_error = None
        try:
            receipt = receipt_for(snapshot, p)
        except ReconciliationRequired as exc:
            receipt, acceptance_error = None, str(exc)
        closed, appraisals, stopped = of_type("closed"), of_type("appraised"), of_type("host_stopped")
        if len(closed) > 1:
            raise ValueError("conflicting retained closures")
        status, report = "RETAINED_PENDING", None
        if acceptance_error or (stopped and data(stopped[-1])["status"] != "COMPLETE"):
            status = "RECONCILIATION_REQUIRED"
        if closed:
            closure = data(closed[0])
            matches = [r for r in appraisals if data(r) == closure.get("appraisal")]
            if (acceptance_error or receipt is None or len(matches) != 1 or
                    closure.get("receipt") != receipt.hash or
                    closure.get("mission_id") != mission_id):
                raise ValueError("closure lacks uniquely bound retained acceptance/appraisal")
            appraisal_record = matches[0]
            appraisal = data(appraisal_record)
            if (appraisal.get("receipt") != receipt.hash or
                    appraisal.get("head") != appraisal_record.prev_hash or
                    not receipt.seq < appraisal_record.seq < closed[0].seq):
                raise ValueError("appraisal history binding differs")
            report = _sources(job, receipt.payload["result"]["sources"])
            if report != appraisal["report"]:
                raise ValueError("retained appraisal differs from source-derived result")
            completed = [r for r in workflows if r.payload["status"] == "completed"
                         and appraisal_record.seq < r.seq < closed[0].seq]
            if (not completed or completed[-1].payload["state"].get("receipt") != receipt.hash or
                    completed[-1].payload["state"].get("appraisal") != appraisal):
                raise ValueError("closure lacks completed bound workflow")
            status = "RETAINED_AUDIT_COMPLETE" if report["compatible"] else "RETAINED_AUDIT_DISCREPANCY"
        elif stopped and data(stopped[-1])["status"] == "COMPLETE":
            raise ValueError("host success without retained verified closure")
        notes = [r for r in snapshot.by_type("review_note")
                 if r.payload.get("note", {}).get("mission_id") == mission_id]
        for note in notes:
            if note.payload.get("schema_version") != 1 or note.payload.get("classification") != CLASSIFICATION:
                raise ValueError("unsupported review note version or classification")
            _validate_note(note.payload["note"])
        refs = [r.hash for r in events + proposals + claims + receipts + outcomes + workflows + notes]
        return {
            "schema_version": 1, "mission_id": mission_id, "as_of_head": head,
            "evidence_tier": "RETAINED_LOCAL_EVIDENCE_REVIEW", "status": status,
            "goal": {k: job[k] for k in ("mission_id", "expected_pin", "expected_version", "due", "deadline")},
            "why": "Retained fixed mission: audit the three approved cached repository snapshots.",
            "actions": {"dispatch_claims": len(claims), "receipts": len(receipts), "outcomes": len(outcomes)},
            "result": report,
            "host_observation": data(stopped[-1]) if stopped else None,
            "workflow_history": [{"ref": r.hash, "status": r.payload["status"],
                                  "note": r.payload.get("note")} for r in workflows],
            "blocker": acceptance_error or (data(stopped[-1]).get("pending_message") if stopped else None),
            "next_reconsideration": (data(stopped[-1]).get("next_reconsideration") if stopped
                                     else data(submissions[0]).get("next_reconsideration")),
            "review_notes": [{"ref": r.hash, **r.payload} for r in notes],
            "evidence_refs": refs,
            "learning": "No critique or retained result has been promoted into policy, tests or causal truth.",
            "next_step": "Review evidence and unresolved gates; any mission or authority change uses its canonical owner.",
            "limits": {"founder_authenticated": False, "current_source_freshness_verified": False,
                       "native_mac_verified": False, "CMC": 0, "VDM": 0,
                       "verified_embodied_persistent_mission_closures": 0},
        }
    finally:
        snapshot.close()


def review(path, constitution, mission_id, head):
    ledger = _open(path, constitution, read_only=True)
    try:
        return _project(ledger, mission_id, head)
    finally:
        ledger.close()


def _validate_note(note):
    if not isinstance(note, dict) or set(note) != NOTE_FIELDS:
        raise ValueError("unknown or missing note field; authority fields are not accepted")
    if not isinstance(note["note_id"], str) or not NOTE_ID.fullmatch(note["note_id"]):
        raise ValueError("bounded stable note identity required")
    if note["kind"] not in ("preference", "failure_claim", "question"):
        raise ValueError("note kind is not an evidence classification")
    if not isinstance(note["text"], str) or not 0 < len(note["text"].encode("utf-8")) <= 4096:
        raise ValueError("note text must be 1..4096 UTF-8 bytes")
    refs = note["evidence_refs"]
    if (not isinstance(refs, list) or len(refs) > 16 or
            any(not isinstance(r, str) for r in refs) or len(set(refs)) != len(refs)):
        raise ValueError("at most 16 distinct evidence references required")
    if note["kind"] == "failure_claim" and not refs:
        raise ValueError("failure claim needs retained evidence; it remains a claim")
    if any(not isinstance(note[k], str) or not note[k] for k in ("mission_id", "review_head")):
        raise ValueError("mission and review head required")
    if len(json.dumps(note).encode()) > MAX_NOTE_INPUT:
        raise ValueError("note input exceeds bound")


def append_note(path, constitution, note):
    """Trusted local writer only. No authenticated-human or approval semantics.

    Retry identical content and ID after an uncertain append by reopening; a
    different body at the same mission/note ID is an explicit conflict.
    """
    _validate_note(note)
    ledger = _open(path, constitution, read_only=False)
    try:
        with ledger._lock:
            report = _project(ledger, note["mission_id"], note["review_head"])
            if not set(note["evidence_refs"]).issubset(report["evidence_refs"]):
                raise ValueError("evidence reference is absent, newer than review, or from another mission")
            payload = {"schema_version": 1, "classification": CLASSIFICATION, "note": note}
            prior = [r for r in ledger.by_type("review_note")
                     if r.payload.get("note", {}).get("mission_id") == note["mission_id"]
                     and r.payload.get("note", {}).get("note_id") == note["note_id"]]
            if prior:
                if len(prior) != 1 or prior[0].payload != payload:
                    raise ValueError("note identity conflicts with retained content")
                return prior[0].hash
            if Path(path).stat().st_size + MAX_NOTE_INPUT + 2048 > MAX_HISTORY:
                raise ValueError("history capacity reached; retain and explicitly migrate")
            return ledger.append("review_note", payload).hash
    finally:
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--constitution", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    show = sub.add_parser("report")
    show.add_argument("--mission", required=True)
    show.add_argument("--head", required=True)
    note = sub.add_parser("note")
    note.add_argument("--input", required=True)
    args = parser.parse_args()
    if args.command == "report":
        result = review(args.ledger, args.constitution, args.mission, args.head)
    else:
        with open(args.input, "rb") as fh:
            raw = fh.read(MAX_NOTE_INPUT + 1)
        if len(raw) > MAX_NOTE_INPUT:
            raise ValueError("note input exceeds bound")
        result = {"note_ref": append_note(args.ledger, args.constitution, strict_json(raw)),
                  "classification": CLASSIFICATION}
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
