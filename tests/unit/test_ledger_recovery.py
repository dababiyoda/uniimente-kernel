"""Torn-tail recovery: quarantine, never delete; refuse anything that is not a pure torn tail."""
from __future__ import annotations

import glob
import hashlib
import json
import os

import pytest

from provenance.ledger import EvidenceLedger, WriterConflict
from provenance.recovery import EVENT_TYPE, RecoveryRefused, recover_torn_tail

ANCHOR = "sha256:" + "a" * 64


def _ledger(tmp_path, n=2):
    path = str(tmp_path / "ledger.jsonl")
    ledger = EvidenceLedger(ANCHOR, path=path)
    for i in range(n):
        ledger.append("event", {"type": "probe", "n": i})
    head = ledger.head
    ledger.close()
    return path, head


def _bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def _recover(path):
    return recover_torn_tail(path, ANCHOR, recovered_by="ops:test", reason="process killed mid-append")


def test_a_clean_ledger_is_left_exactly_as_it_was(tmp_path):
    path, _ = _ledger(tmp_path)
    before = _bytes(path)
    out = _recover(path)
    assert out == {"torn": False, "quarantined": None, "recorded": []}
    assert _bytes(path) == before and glob.glob(path + ".torn-*") == []


def test_a_torn_tail_is_quarantined_byte_for_byte_and_the_recovery_is_chained(tmp_path):
    path, head = _ledger(tmp_path)
    torn = b'{"seq": 3, "record_type": "event", "payl'
    with open(path, "ab") as fh:
        fh.write(torn)
    with pytest.raises(ValueError):
        EvidenceLedger(ANCHOR, path=path)   # fail-closed is unchanged: opening alone never repairs
    out = _recover(path)
    q = out["quarantined"]
    assert out["torn"] and q["classification"] == "partial" and q["prior_head"] == head and q["torn_bytes"] == len(torn)
    assert _bytes(str(tmp_path / q["quarantine_file"])) == torn
    assert q["torn_sha256"] == "sha256:" + hashlib.sha256(torn).hexdigest()
    ledger = EvidenceLedger(ANCHOR, path=path)
    ok, msg = ledger.verify_chain()
    assert ok, msg
    [event] = [r.payload for r in ledger.by_type("event") if r.payload.get("type") == EVENT_TYPE]
    assert event["torn_sha256"] == q["torn_sha256"] and event["recovered_by"] == "ops:test"
    assert event["prior_head"] == head and "not chained" in event["disposition"]
    assert ledger.records[-2].hash == head   # nothing before the tear changed
    ledger.close()
    after = _bytes(path)
    assert _recover(path) == {"torn": False, "quarantined": None, "recorded": []}   # idempotent
    assert _bytes(path) == after


def _unterminated(tmp_path):
    path, head = _ledger(tmp_path)
    ledger = EvidenceLedger(ANCHOR, path=path)
    probe = ledger.append("event", {"type": "probe", "n": 99})
    ledger.close()
    data = _bytes(path)
    with open(path, "wb") as fh:
        fh.write(data[:-1])   # only the record's own newline is missing
    return path, head, probe


def test_a_whole_record_that_lost_its_newline_is_suspect_and_refused_without_proof(tmp_path):
    path, head, probe = _unterminated(tmp_path)
    data = _bytes(path)
    with pytest.raises(RecoveryRefused, match="may have been acknowledged"):
        _recover(path)   # deleting one byte must never be enough to drop an acknowledged record
    with pytest.raises(RecoveryRefused, match="expected acknowledged head"):
        recover_torn_tail(path, ANCHOR, recovered_by="ops:test", reason="r", expected_head=probe.hash)
    assert _bytes(path) == data and glob.glob(path + ".torn-*") == []


@pytest.mark.parametrize("proof", ["expected_head", "explicit"])
def test_with_proof_a_whole_unterminated_record_is_quarantined_never_admitted(tmp_path, proof):
    path, head, probe = _unterminated(tmp_path)
    kwargs = {"expected_head": head} if proof == "expected_head" else {"quarantine_complete_record": True}
    q = recover_torn_tail(path, ANCHOR, recovered_by="ops:test", reason="r", **kwargs)["quarantined"]
    assert q["classification"] == "complete_unterminated" and q["torn_record_hash"] == probe.hash
    assert q["prior_head"] == head and q["unacknowledged_proof"].startswith(
        "expected_head" if proof == "expected_head" else "quarantine_complete_record")
    ledger = EvidenceLedger(ANCHOR, path=path)
    assert ledger.find(probe.hash) is None   # an append that never returned is never admitted
    [event] = [r.payload for r in ledger.by_type("event") if r.payload.get("type") == EVENT_TYPE]
    assert event["classification"] == "complete_unterminated" and event["unacknowledged_proof"] == q["unacknowledged_proof"]
    ledger.close()


def test_an_expected_head_that_does_not_match_is_refused(tmp_path):
    path, head = _ledger(tmp_path)
    with open(path, "ab") as fh:
        fh.write(b'{"partial')
    data = _bytes(path)
    with pytest.raises(RecoveryRefused):
        recover_torn_tail(path, ANCHOR, recovered_by="ops:test", reason="r", expected_head="sha256:" + "0" * 64)
    assert _bytes(path) == data
    out = recover_torn_tail(path, ANCHOR, recovered_by="ops:test", reason="r", expected_head=head)
    assert out["quarantined"]["unacknowledged_proof"] == "expected_head matched"


@pytest.mark.parametrize("damage", ["tampered", "blank", "genesis_torn", "empty"])
def test_anything_but_a_pure_torn_tail_is_refused_and_left_untouched(tmp_path, damage):
    path, _ = _ledger(tmp_path)
    data = _bytes(path)
    lines = data.split(b"\n")
    if damage == "tampered":
        lines[1] = lines[1].replace(b'"n": 0', b'"n": 7')
        data = b"\n".join(lines) + b'{"partial'
    elif damage == "blank":
        data = data + b"\n" + b'{"partial'
    elif damage == "genesis_torn":
        data = lines[0][:20]
    else:
        data = b""
    with open(path, "wb") as fh:
        fh.write(data)
    with pytest.raises(RecoveryRefused):
        _recover(path)
    assert _bytes(path) == data and glob.glob(path + ".torn-*") == []


def test_a_live_writer_blocks_recovery(tmp_path):
    path, _ = _ledger(tmp_path)
    with open(path, "ab") as fh:
        fh.write(b'{"partial')
    data = _bytes(path)
    holder = open(path + ".lock", "a")
    import fcntl
    fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(WriterConflict):
            _recover(path)
    finally:
        holder.close()
    assert _bytes(path) == data and glob.glob(path + ".torn-*") == []


def test_recovery_names_who_ran_it_and_why(tmp_path):
    path, _ = _ledger(tmp_path)
    with pytest.raises(ValueError):
        recover_torn_tail(path, ANCHOR, recovered_by="", reason="x")
    with pytest.raises(ValueError):
        recover_torn_tail(path, ANCHOR, recovered_by="ops:test", reason="  ")


def test_a_crash_after_truncation_is_completed_on_the_next_call_without_duplicates(tmp_path, monkeypatch):
    path, head = _ledger(tmp_path)
    torn = b'{"seq": 3, "rec'
    with open(path, "ab") as fh:
        fh.write(torn)
    import provenance.recovery as recovery

    def died(*args, **kwargs):
        raise SystemExit("killed between the truncation and the ledger event")
    monkeypatch.setattr(recovery, "_record_quarantines", died)
    with pytest.raises(SystemExit):
        _recover(path)
    monkeypatch.undo()
    assert _bytes(path).endswith(b"\n") and len(glob.glob(path + ".torn-*")) == 2   # copy and sidecar survive
    out = _recover(path)
    assert out["torn"] is False and len(out["recorded"]) == 1
    ledger = EvidenceLedger(ANCHOR, path=path)
    [event] = [r.payload for r in ledger.by_type("event") if r.payload.get("type") == EVENT_TYPE]
    assert event["classification"] == "partial" and event["prior_head"] == head
    ledger.close()
    assert _recover(path)["recorded"] == []


def test_a_quarantine_name_collision_with_different_bytes_is_refused(tmp_path):
    path, _ = _ledger(tmp_path)
    torn = b'{"partial'
    with open(path, "ab") as fh:
        fh.write(torn)
    data = _bytes(path)
    with open(f"{path}.torn-{hashlib.sha256(torn).hexdigest()}", "wb") as fh:
        fh.write(b"something else")
    with pytest.raises(RecoveryRefused):
        _recover(path)
    assert _bytes(path) == data


def test_the_sidecar_matches_the_quarantined_bytes(tmp_path):
    path, _ = _ledger(tmp_path)
    with open(path, "ab") as fh:
        fh.write(b'{"partial')
    q = _recover(path)["quarantined"]
    with open(str(tmp_path / q["quarantine_file"]) + ".json", "rb") as fh:
        meta = json.loads(fh.read())
    assert meta["torn_sha256"] == q["torn_sha256"] and meta["torn_bytes"] == q["torn_bytes"]
    assert os.path.basename(path) in q["quarantine_file"]
