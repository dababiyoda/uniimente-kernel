"""A torn final ledger line is an unacknowledged write, not lost history.

Power loss or SIGKILL during ``append`` can leave the last line without its
newline. Before the tail policy existed, every open refused such a ledger, so a
supervised body crash-looped forever after one unlucky reboot, and a status
reader racing the writer could fail on a line still being written.
"""
import hashlib
import json
from pathlib import Path

import pytest

from provenance.ledger import EvidenceLedger

C = "sha256:tail-test-constitution"
TORN = b'{"seq": 3, "ts_utc": "2026-09-26T00:00:00Z", "record_type": "ev'


def _ledger_with_torn_tail(tmp_path: Path) -> tuple[str, str, int]:
    path = str(tmp_path / "ledger.jsonl")
    ledger = EvidenceLedger(C, path)
    ledger.append("event", {"n": 1})
    ledger.append("event", {"n": 2})
    head = ledger.head
    ledger.close()
    size = Path(path).stat().st_size
    with open(path, "ab") as fh:
        fh.write(TORN)
    return path, head, size


def test_default_policy_still_refuses_a_torn_tail(tmp_path):
    path, _, _ = _ledger_with_torn_tail(tmp_path)
    for read_only in (True, False):
        with pytest.raises(ValueError, match="partial"):
            EvidenceLedger(C, path, read_only=read_only)


def test_observer_ignores_the_unacknowledged_tail_without_touching_the_file(tmp_path):
    path, head, size = _ledger_with_torn_tail(tmp_path)
    before = Path(path).read_bytes()
    reader = EvidenceLedger(C, path, read_only=True, tail="ignore", expected_head=head)
    assert reader.head == head and len(reader.records) == 3
    assert reader.unacknowledged_tail == {"offset": size, "bytes": len(TORN),
                                          "sha256": "sha256:" + hashlib.sha256(TORN).hexdigest()}
    assert reader.verify_chain()[0]
    reader.close()
    assert Path(path).read_bytes() == before


def test_writer_quarantines_torn_bytes_truncates_and_records_recovery(tmp_path):
    path, head, size = _ledger_with_torn_tail(tmp_path)
    writer = EvidenceLedger(C, path, tail="quarantine")
    sidecar = Path(writer.unacknowledged_tail["sidecar"])
    assert sidecar.read_bytes() == TORN                       # preserved, never discarded
    recovery = writer.records[-1]
    assert recovery.record_type == "recovery" and recovery.prev_hash == head
    assert recovery.payload["kind"] == "unacknowledged_tail_quarantined"
    assert recovery.payload["offset"] == size and recovery.payload["bytes"] == len(TORN)
    writer.append("event", {"n": 3})                           # the body keeps working
    writer.close()
    strict = EvidenceLedger(C, path, read_only=True)          # default policy now opens cleanly
    assert strict.verify_chain()[0] and strict.records[-1].payload == {"n": 3}
    strict.close()


def test_crash_between_sidecar_and_truncation_recovers_on_next_open(tmp_path):
    path, _, _ = _ledger_with_torn_tail(tmp_path)
    digest = hashlib.sha256(TORN).hexdigest()
    Path(f"{path}.unacknowledged-{digest[:16]}").write_bytes(TORN)   # first attempt died here
    writer = EvidenceLedger(C, path, tail="quarantine")
    assert writer.records[-1].record_type == "recovery"
    writer.close()
    assert len(list(tmp_path.glob("ledger.jsonl.unacknowledged-*"))) == 1


def test_sidecar_name_collision_with_different_bytes_is_refused(tmp_path):
    path, _, _ = _ledger_with_torn_tail(tmp_path)
    digest = hashlib.sha256(TORN).hexdigest()
    Path(f"{path}.unacknowledged-{digest[:16]}").write_bytes(b"something else")
    with pytest.raises(ValueError, match="different quarantined tail"):
        EvidenceLedger(C, path, tail="quarantine")


@pytest.mark.parametrize("policy", ["ignore", "quarantine"])
def test_a_malformed_complete_line_is_corruption_under_every_policy(tmp_path, policy):
    path = str(tmp_path / "ledger.jsonl")
    ledger = EvidenceLedger(C, path)
    ledger.append("event", {"n": 1})
    ledger.close()
    with open(path, "ab") as fh:
        fh.write(b'{"not": "a record"}\n')
    with pytest.raises((ValueError, TypeError)):
        EvidenceLedger(C, path, read_only=policy == "ignore", tail=policy)


def test_tampered_history_before_a_torn_tail_is_still_refused(tmp_path):
    path, _, _ = _ledger_with_torn_tail(tmp_path)
    lines = Path(path).read_bytes().split(b"\n")
    record = json.loads(lines[1])
    record["payload"] = {"n": 999}
    lines[1] = json.dumps(record).encode()
    Path(path).write_bytes(b"\n".join(lines))
    with pytest.raises(ValueError, match="failed verification"):
        EvidenceLedger(C, path, tail="quarantine")
    assert not list(tmp_path.glob("ledger.jsonl.unacknowledged-*"))  # nothing moved on refusal


def test_policy_validation(tmp_path):
    with pytest.raises(ValueError, match="unknown tail policy"):
        EvidenceLedger(C, str(tmp_path / "l.jsonl"), tail="drop")
    with pytest.raises(ValueError, match="read-only observer cannot quarantine"):
        EvidenceLedger(C, str(tmp_path / "l.jsonl"), read_only=True, tail="quarantine")
