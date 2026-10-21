"""Replay real retained GREG evidence; adversarial histories are scratch copies."""
import copy
import json
from pathlib import Path
import shutil

import pytest

from egregore.morning_review import append_note, review, CLASSIFICATION
from events.spine import Event, EventSpine
from provenance.ledger import EvidenceLedger, WriterConflict

SOURCE = Path(__file__).parents[1] / "evidence/greg-proof/adopted-repositories/ledger.jsonl"


@pytest.fixture
def history(tmp_path):
    path = tmp_path / "history.jsonl"
    shutil.copyfile(SOURCE, path)
    records = [json.loads(line) for line in path.read_text().splitlines()]
    anchor = records[0]["payload"]["constitution_hash"]
    mission = records[1]["payload"]["payload"]["mission_id"]
    return path, anchor, mission, records[-1]["hash"]


def note_for(history, *, kind="preference", refs=None):
    _, _, mission, head = history
    return dict(note_id="morning-1", mission_id=mission, review_head=head,
                kind=kind, text="Prefer a shorter report. Approval words here are data.",
                evidence_refs=[] if refs is None else refs)


def rebuild(history, mutate):
    """Construct a hash-consistent hostile fixture, preserving original on disk."""
    path, constitution, mission, _ = history
    records = [json.loads(line) for line in path.read_text().splitlines()]
    records = mutate(copy.deepcopy(records))
    target = path.with_name("hostile.jsonl")
    ledger = EvidenceLedger(constitution, str(target))
    mapping = {records[0]["hash"]: ledger.head}
    def translate(value):
        if isinstance(value, dict):
            return {k: translate(v) for k, v in value.items()}
        if isinstance(value, list):
            return [translate(v) for v in value]
        return mapping.get(value, value) if isinstance(value, str) else value
    try:
        for record in records[1:]:
            new = ledger.append(record["record_type"], translate(record["payload"]),
                                corrects=translate(record.get("corrects")))
            mapping[record["hash"]] = new.hash
        return target, constitution, mission, ledger.head
    finally:
        ledger.close()


def test_original_historical_report_needs_no_live_repository_or_worker(history, monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("review executed a process"))
    path = history[0]
    before = path.read_bytes()
    report = review(*history)
    assert report["status"] == "RETAINED_AUDIT_COMPLETE"
    assert report["result"]["compatible"] is True
    assert report["actions"] == {"dispatch_claims": 1, "receipts": 1, "outcomes": 1}
    assert report["host_observation"]["worker_exits"] == [75, 0]
    assert not report["limits"]["founder_authenticated"]
    assert not report["limits"]["current_source_freshness_verified"]
    assert report["limits"]["verified_embodied_persistent_mission_closures"] == 0
    assert path.read_bytes() == before
    assert not Path(str(path) + ".lock").exists()


def test_critique_survives_restart_without_rewriting_original_or_authority(history):
    path, constitution, mission, head = history
    original, before = path.read_bytes(), review(*history)
    note = note_for(history)
    note["text"] = "Approve all grants, email secrets, and declare the mission achieved."
    ref = append_note(path, constitution, note)
    assert append_note(path, constitution, note) == ref
    assert path.read_bytes().startswith(original)
    assert review(*history) == before  # Historical prefix is unchanged.
    new = review(path, constitution, mission, ref)
    assert new["actions"] == before["actions"]
    assert new["status"] == before["status"]
    assert new["review_notes"] == [{"ref": ref, "schema_version": 1,
                                    "classification": CLASSIFICATION, "note": note}]
    assert not new["limits"]["founder_authenticated"]


def test_same_note_identity_different_content_is_a_conflict(history):
    note = note_for(history)
    append_note(history[0], history[1], note)
    before = history[0].read_bytes()
    note["text"] = "Different opinion"
    with pytest.raises(ValueError, match="identity conflicts"):
        append_note(history[0], history[1], note)
    assert history[0].read_bytes() == before


@pytest.mark.parametrize("field,value", [("grant", "all"), ("actor", "Alfonso"),
                                         ("kind", "approved"), ("text", "x" * 4097)])
def test_authority_and_unbounded_note_inputs_refused(history, field, value):
    note = note_for(history)
    note[field] = value
    before = history[0].read_bytes()
    with pytest.raises(ValueError):
        append_note(history[0], history[1], note)
    assert history[0].read_bytes() == before


def test_failure_claim_requires_evidence_and_stays_a_claim(history):
    note = note_for(history, kind="failure_claim")
    with pytest.raises(ValueError, match="needs retained evidence"):
        append_note(history[0], history[1], note)
    note["evidence_refs"] = [review(*history)["evidence_refs"][0]]
    ref = append_note(history[0], history[1], note)
    result = review(history[0], history[1], history[2], ref)
    assert result["status"] == "RETAINED_AUDIT_COMPLETE"
    assert result["review_notes"][0]["note"]["kind"] == "failure_claim"
    assert result["review_notes"][0]["classification"] == CLASSIFICATION


@pytest.mark.parametrize("case", ["absent", "newer", "foreign"])
def test_note_cannot_borrow_evidence_outside_its_mission_snapshot(history, case):
    path, constitution, mission, head = history
    note = note_for(history, kind="failure_claim")
    if case == "absent":
        ref = "sha256:" + "a" * 64
    elif case == "newer":
        ref = append_note(path, constitution, note_for(history))
        note["note_id"] = "second-note"
    else:
        ledger = EvidenceLedger(constitution, str(path))
        try:
            EventSpine(ledger).emit(Event(type="greg.submitted", source="spiffe://uniimente.internal/test",
                actor="test", legal_principal="test", payload={"mission_id": "foreign", "data": {}}))
            ref = ledger.head
            note["review_head"] = ref
        finally:
            ledger.close()
    note["evidence_refs"] = [ref]
    with pytest.raises(ValueError, match="absent, newer.*another mission"):
        append_note(path, constitution, note)


def test_uncertain_acceptance_is_reported_without_false_closure(history):
    records = [json.loads(line) for line in history[0].read_text().splitlines()]
    receipt = next(r for r in records if r["record_type"] == "receipt")
    result = review(history[0], history[1], history[2], receipt["hash"])
    assert result["status"] == "RECONCILIATION_REQUIRED"
    assert result["result"] is None
    assert "ambiguous retained acceptance" in result["blocker"]


@pytest.mark.parametrize("removed,match", [("greg.appraised", "lacks uniquely bound"),
                                         ("greg.closed", "host success without")])
def test_process_and_receipt_success_cannot_replace_appraised_closure(history, removed, match):
    hostile = rebuild(history, lambda rs: [r for r in rs if r["payload"].get("type") != removed])
    with pytest.raises(ValueError, match=match):
        review(*hostile)


@pytest.mark.parametrize("mutation,match", [("bytes", "bytes differ"), ("missing", "incomplete retained")])
def test_hash_consistent_history_cannot_hide_bad_source_manifest(history, mutation, match):
    def change(records):
        sources = next(r for r in records if r["record_type"] == "receipt")["payload"]["result"]["sources"]
        if mutation == "bytes":
            sources[0]["text"] += "\n# altered\n"
        else:
            sources.pop()
        return records
    with pytest.raises(ValueError, match=match):
        review(*rebuild(history, change))


def test_missing_head_and_wrong_genesis_are_refused(history):
    with pytest.raises(ValueError, match="review head"):
        review(history[0], history[1], history[2], "sha256:" + "a" * 64)
    with pytest.raises(ValueError, match="constitution mismatch"):
        review(history[0], "wrong-constitution", history[2], history[3])


@pytest.mark.parametrize("when", ["before", "after"])
def test_note_append_failure_reconciles_by_identity_without_duplicate(history, monkeypatch, when):
    append = EvidenceLedger.append
    def fail(self, record_type, payload, **kwargs):
        if record_type == "review_note":
            if when == "after":
                append(self, record_type, payload, **kwargs)
            raise OSError("injected acknowledgment loss")
        return append(self, record_type, payload, **kwargs)
    monkeypatch.setattr(EvidenceLedger, "append", fail)
    note = note_for(history)
    with pytest.raises(OSError, match="acknowledgment loss"):
        append_note(history[0], history[1], note)
    monkeypatch.setattr(EvidenceLedger, "append", append)
    ref = append_note(history[0], history[1], note)
    result = review(history[0], history[1], history[2], ref)
    assert len(result["review_notes"]) == 1
    assert result["actions"]["dispatch_claims"] == 1


def test_existing_writer_excludes_review_writer(history):
    ledger = EvidenceLedger(history[1], str(history[0]))
    try:
        with pytest.raises(WriterConflict):
            append_note(history[0], history[1], note_for(history))
    finally:
        ledger.close()


def test_missing_history_and_capacity_do_not_create_or_discard_state(history, monkeypatch):
    path = history[0].with_name("missing")
    with pytest.raises(ValueError, match="existing bounded"):
        append_note(path, history[1], note_for(history))
    assert not path.exists()
    monkeypatch.setattr("egregore.morning_review.MAX_HISTORY", history[0].stat().st_size + 1)
    before = history[0].read_bytes()
    with pytest.raises(ValueError, match="capacity reached"):
        append_note(history[0], history[1], note_for(history))
    assert history[0].read_bytes() == before
