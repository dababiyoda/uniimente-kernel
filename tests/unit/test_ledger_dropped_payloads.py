"""A file-backed ledger keeps only its newest payloads in memory; older ones are read back from the file.

FINDING-BODY-MEMORY-2026-10-28: a body observing once a minute grew by about 2.5 KB of memory per retained
record, so a 4 GB Chromebook would run out within months. These tests pin what changes and what must not:
the file is byte-for-byte the same; every read returns what a ledger holding everything in memory returns;
a payload read back from the file is refused unless its bytes are the ones verified; and anything altered in
memory, before or after its payload was dropped, is still found by the next reconstruction (the commit path
included), never silently replaced by the file's copy.
"""
from __future__ import annotations

import copy
import json
import pickle
from dataclasses import asdict

import pytest

import provenance.ledger as ledger_module
from events.spine import Event, EventError, EventSpine
from provenance.ledger import EvidenceLedger, LedgerRecord

ANCHOR = "sha256:" + "0" * 64
SRC = "spiffe://uniimente.internal/test"


def _event(i, kind="work.done"):
    return Event(type=kind, source=SRC, actor="tester", legal_principal="Alfonso Lopez",
                 payload={"i": i, "items": [i, {"nested": str(i)}]})


def grown(tmp_path, n=40, resident=4):
    path = str(tmp_path / "l.jsonl")
    led = EvidenceLedger(ANCHOR, path, resident=resident)
    spine = EventSpine(led)
    for i in range(n):
        spine.emit(_event(i, "work.done" if i % 3 else "work.started"))
        led.append("grant_dispatch", {"proposal_id": f"p{i}", "grant_id": f"g{i % 5}"})
    return led, spine, path


def everything_in_memory(path):
    return EvidenceLedger(ANCHOR, path, read_only=True, resident=10 ** 9)


def readout(led, spine):
    return ([asdict(r) for r in led.records], [asdict(r) for r in led.by_type("grant_dispatch")],
            [asdict(r) for r in led.select("grant_dispatch", grant_id="g3")], asdict(led.find(led.records[7].hash)),
            [asdict(e) for e in spine.replay()], [asdict(e) for e in spine.replay("work.started")],
            [asdict(e) for e in spine.since("work.", None)[0]], dict(spine.positions("work.")),
            asdict(spine.latest(spine.replay()[2].event_id)), spine.record_hash(spine.replay()[2].event_id))


def test_old_payloads_leave_memory_and_every_read_is_what_a_ledger_holding_everything_returns(tmp_path):
    led, spine, path = grown(tmp_path)
    retained = led._records
    assert all(not r.resident for r in retained[1:len(retained) - 4])          # dropped: only the skeleton stays
    assert getattr(retained[0], "resident", True) and all(r.resident for r in retained[-4:])  # genesis, newest stay
    assert not hasattr(spine, "_payloads")                                     # the spine keeps positions only
    full = everything_in_memory(path)
    assert readout(led, spine) == readout(full, EventSpine(full))
    assert led.verify_chain()[0] and led.verify_incremental()[0]


def test_the_file_is_byte_for_byte_what_a_ledger_holding_everything_writes(tmp_path):
    led, _, path = grown(tmp_path, n=12, resident=2)
    lines = open(path, "rb").read().splitlines()
    assert [json.loads(line) for line in lines] == [asdict(r) for r in led.records]
    assert [line.decode() for line in lines] == [json.dumps(asdict(r), allow_nan=False) for r in led.records]
    led.close()
    reopened = EvidenceLedger(ANCHOR, path, resident=2)
    assert reopened.head == led.head and reopened.verify_chain()[0]
    assert [asdict(r) for r in reopened.records] == [asdict(r) for r in everything_in_memory(path).records]


def test_reading_a_dropped_payload_hands_out_a_new_object_each_time(tmp_path):
    led, _, _ = grown(tmp_path)
    first, second = led.records[3], led.records[3]
    assert first.payload == second.payload and first.payload is not second.payload
    first.payload["i"] = "changed by a reader"
    assert led.records[3].payload == second.payload and led.verify_chain()[0]
    assert type(first) is LedgerRecord and type(first.payload) is dict          # readers get plain types


def _rewrite_line(path, seq, old: bytes, new: bytes):
    lines = open(path, "rb").read().split(b"\n")
    assert old in lines[seq] and len(old) == len(new)
    lines[seq] = lines[seq].replace(old, new, 1)
    open(path, "wb").write(b"\n".join(lines))


def test_a_dropped_line_changed_on_disk_is_refused_when_read_and_stops_further_appends(tmp_path):
    led, spine, path = grown(tmp_path)
    seq = next(r.seq for r in led.records if r.record_type == "grant_dispatch" and r.payload["proposal_id"] == "p5")
    _rewrite_line(path, seq, b'"p5"', b'"p6"')                        # same length: only the digest can tell
    with pytest.raises(ValueError, match=f"payload hash mismatch at seq {seq}"):
        led.records[seq]
    with pytest.raises(ValueError, match=f"payload hash mismatch at seq {seq}"):
        led.select("grant_dispatch", proposal_id="p5")
    ok, why = led.verify_chain()
    assert not ok and f"payload hash mismatch at seq {seq}" in why
    with pytest.raises(ValueError, match=f"payload hash mismatch at seq {seq}"):
        led.append("event", {"n": 1})                                 # fail closed until history is reconciled
    with pytest.raises(ValueError):
        led.append("witness", {"w": 1})
    led.close()
    with pytest.raises(ValueError, match="failed verification on load"):
        EvidenceLedger(ANCHOR, path)


def test_a_line_changed_on_disk_is_refused_by_the_read_and_then_by_every_append(tmp_path):
    led, spine, path = grown(tmp_path)
    _rewrite_line(path, 5, b'"i": 2', b'"i": 9')                       # event 2 is record 5, long dropped
    with pytest.raises(ValueError, match="payload hash mismatch at seq 5"):
        spine.replay()
    with pytest.raises(EventError, match="payload hash mismatch at seq 5"):
        spine.emit(_event(99))                                        # the hot path now reads the whole file


@pytest.mark.parametrize("field, value", [
    ("record_type", "grant_dispatch_x"), ("hash", "sha256:" + "e" * 64), ("ts_utc", "2000-01-01T00:00:00Z"),
    ("corrects", "sha256:" + "c" * 64), ("_off", 0), ("_digest", b"\0" * 32),
])
def test_what_stays_in_memory_of_dropped_history_is_held_to_its_digest_on_the_commit_path(tmp_path, field, value):
    """The Commit Witness reconstructs the whole chain. For dropped history that means the skeleton and line
    digests against their running digest (no file read on the commit path); an altered field is found."""
    led, _, _ = grown(tmp_path)
    target = led._records[6]
    assert not target.resident
    assert led.verify_incremental()[0]
    setattr(target, field, value)
    with pytest.raises(ValueError):
        led.append("witness", {"w": 1})
    assert not led.by_type("witness")
    assert not led.verify_chain()[0]


def test_a_dropped_records_link_is_checked(tmp_path):
    led, _, _ = grown(tmp_path)
    led._records[8].prev_hash = "sha256:" + "e" * 64
    ok, why = led.verify_chain()
    assert not ok and "chain break at seq 8" in why


def test_a_plain_record_put_in_a_dropped_position_is_refused(tmp_path):
    led, _, _ = grown(tmp_path)
    led._records[9] = copy.deepcopy(led._records[9])                   # equal content, but not the retained one
    ok, why = led.verify_chain()
    assert not ok and "retained record replaced at seq 9" in why


def test_a_payload_altered_in_memory_is_never_dropped_so_the_file_cannot_quietly_heal_it(tmp_path):
    path = str(tmp_path / "l.jsonl")
    led = EvidenceLedger(ANCHOR, path, resident=3)
    for i in range(3):
        led.append("event", {"n": i})
    led._records[2].payload["n"] = 999                                # altered while still in memory
    for i in range(3, 10):
        led.append("event", {"n": i})                                 # pushes record 2 out of the window
    assert led._records[2].resident and led._records[2].payload["n"] == 999   # kept, altered, for detection
    ok, why = led.verify_chain()
    assert not ok and "payload hash mismatch at seq 2" in why
    with pytest.raises(ValueError, match="payload hash mismatch at seq 2"):
        led.append("witness", {"w": 1})


def test_a_dropped_payload_put_back_in_memory_is_held_to_its_record(tmp_path):
    led, _, _ = grown(tmp_path)
    led._records[4].payload = {"forged": True}
    ok, why = led.verify_chain()
    assert not ok and "payload hash mismatch at seq 4" in why


def test_opening_a_long_history_keeps_only_the_window_and_still_verifies_all_of_it(tmp_path):
    led, _, path = grown(tmp_path, n=60, resident=1000)
    led.close()
    reopened = EvidenceLedger(ANCHOR, path, resident=5)
    assert sum(r.resident for r in reopened._records) == 1 + 5           # genesis and the window
    assert reopened.verify_chain()[0]
    assert [asdict(r) for r in reopened.records] == [asdict(r) for r in everything_in_memory(path).records]
    reopened.append("event", {"after": "reopen"})
    assert reopened.verify_chain()[0] and reopened.verify_incremental()[0]


def test_opening_reports_a_malformed_line_before_an_earlier_hash_failure_as_a_whole_file_read_did(tmp_path):
    led, _, path = grown(tmp_path, n=8)
    led.close()
    _rewrite_line(path, 3, b'"i": 1', b'"i": 7')                       # event 1 is record 3
    with pytest.raises(ValueError, match="failed verification on load"):
        EvidenceLedger(ANCHOR, path, resident=2)
    with open(path, "ab") as fh:
        fh.write(b"{not json\n")
    with pytest.raises(ValueError, match="malformed"):
        EvidenceLedger(ANCHOR, path, resident=2)


def test_copies_equality_and_pickling_of_retained_records_are_plain_records(tmp_path):
    led, _, _ = grown(tmp_path)
    retained = led._records[5]
    plain = led.records[5]
    for other in (copy.copy(retained), copy.deepcopy(retained), pickle.loads(pickle.dumps(retained))):
        assert type(other) is LedgerRecord and other == plain
    assert retained == plain and plain == retained and plain in led.records and led.records.index(plain) == 5


def test_assigned_history_is_held_in_memory_and_reverified(tmp_path):
    led, _, _ = grown(tmp_path)
    history = list(led.records)
    led.records = history
    assert all(type(r) is LedgerRecord for r in led._records) and led.verify_chain()[0]


def test_reads_after_close_reopen_the_file(tmp_path):
    led, _, _ = grown(tmp_path)
    expected = asdict(led.records[3])
    led.close()
    assert asdict(led.records[3]) == expected


def test_an_in_memory_ledger_keeps_every_payload(tmp_path):
    led = EvidenceLedger(ANCHOR)
    for i in range(ledger_module.RESIDENT_RECORDS + 10):
        led.append("event", {"n": i})
    assert all(type(r) is LedgerRecord for r in led._records)


def test_the_window_must_be_a_positive_count(tmp_path):
    for bad in (0, -1, 2.5, True):
        with pytest.raises(ValueError):
            EvidenceLedger(ANCHOR, str(tmp_path / f"x{bad}.jsonl"), resident=bad)
