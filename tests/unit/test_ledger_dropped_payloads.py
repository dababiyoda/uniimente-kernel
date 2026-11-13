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
import errno
import fcntl
import hashlib
import json
import os
import pickle
import signal
import threading
import time
from dataclasses import asdict

import pytest

import provenance.ledger as ledger_module
from events.spine import Event, EventError, EventSpine
from provenance.ledger import EvidenceLedger, LedgerRecord, ReconciliationRequired

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
    ("corrects", "sha256:" + "c" * 64), ("_off", 0), ("_len", 1), ("_digest", b"\0" * 32),
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
    assert not ok and "retained record altered in memory at seq 9" in why


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


# -- Independent adversarial review of 45d65a30 (2026-10-28): each break reproduced, fixed, and pinned here ---------

def test_f1_a_line_pointer_altered_while_resident_is_never_dropped_and_is_reported(tmp_path):
    """The reviewer planted a parseable copy of a record (same hash and seq, forged payload) inside a later record's
    payload, pointed the still-resident record's line pointer at it, and let eviction run: every reader then saw the
    forgery and nothing detected it. Eviction now requires the pointer to name exactly the record's own bytes."""
    import hashlib
    path = str(tmp_path / "l.jsonl")
    led = EvidenceLedger(ANCHOR, path, resident=3)
    spine = EventSpine(led)
    spine.emit(Event(type="money.paid", source=SRC, actor="a", legal_principal="Alfonso Lopez", payload={"amount": 1}))
    target = led._records[1]
    forged = {**led.records[1].payload, "payload": {"amount": 1000000}, "legal_principal": "Mallory"}
    planted = {"hash": target.hash, "seq": 1, "payload": forged}
    led.append("note", {"quote": planted})
    blob = json.dumps(planted).encode()
    target._off, target._len, target._digest = open(path, "rb").read().index(blob), len(blob), \
        hashlib.sha256(blob).digest()
    for i in range(4):
        led.append("note", {"i": i})
    assert target.resident                                                    # not dropped ...
    assert spine.replay("money.")[0].payload == {"amount": 1}                 # ... so readers see the original
    ok, why = led.verify_chain()
    assert not ok and "retained line pointer altered in memory at seq 1" in why
    with pytest.raises(ValueError, match="retained line pointer altered in memory at seq 1"):
        led.append("witness", {"w": 1})


@pytest.mark.parametrize("field, value", [("corrects", "None"), ("hash_version", "2"), ("_off", "0"), ("seq", 3.0)])
def test_f2_a_change_of_type_alone_on_a_dropped_record_is_found(tmp_path, field, value):
    led, _, _ = grown(tmp_path)
    target = led._records[3]
    assert not target.resident
    setattr(target, field, value)
    ok, why = led.verify_chain()
    assert not ok and ("altered in memory" in why or "sequence break" in why)
    with pytest.raises(ValueError):
        led.append("witness", {"w": 1})


def test_f2_a_pointer_of_the_wrong_type_is_refused_not_crashed_on(tmp_path):
    led, _, _ = grown(tmp_path)
    led._records[3]._off = "0"
    with pytest.raises(ValueError, match="payload hash mismatch at seq 3"):
        led.records[3]


@pytest.mark.parametrize("record_type, corrects", [("note\ud800", None), ("correction", "sha256:\ud800")])
def test_f3_unusual_text_is_retained_dropped_and_reopened(tmp_path, record_type, corrects):
    path = str(tmp_path / "l.jsonl")
    led = EvidenceLedger(ANCHOR, path, resident=2)
    led.append(record_type, {"x": 1}, corrects=corrects)
    for i in range(4):
        led.append("note", {"i": i})                        # drops seq 1: its skeleton must encode
    assert not led._records[1].resident and led.verify_chain()[0]
    led.close()
    assert EvidenceLedger(ANCHOR, path, read_only=True, resident=2).verify_chain()[0]


def test_f3_a_str_subclass_record_type_is_stored_as_text_and_never_forks_the_file(tmp_path):
    class Kind(str):
        pass
    path = str(tmp_path / "l.jsonl")
    led = EvidenceLedger(ANCHOR, path, resident=2)
    led.append(Kind("note"), {"x": 1})
    for i in range(4):
        led.append("note", {"i": i})
    assert type(led._records[1].record_type) is str
    led.close()
    reopened = EvidenceLedger(ANCHOR, path, resident=2)
    assert reopened.verify_chain()[0] and len(reopened.records) == 6
    with pytest.raises(ValueError, match="must be text"):
        reopened.append(5, {"x": 1})                         # refused before anything is written
    assert len(EvidenceLedger(ANCHOR, path, read_only=True).records) == 6


def test_f4_a_reader_refused_while_a_reconstruction_runs_keeps_appends_refused(tmp_path):
    """A lock-free reader may find changed bytes after a whole-file reconstruction has already passed that line.
    The reconstruction must not erase that signal: failures are counted, and only those before it started clear."""
    import threading
    path = str(tmp_path / "l.jsonl")
    led = EvidenceLedger(ANCHOR, path, resident=2)
    for i in range(10):
        led.append("receipt", {"who": "p5" if i == 2 else "px"})
    target, last_dropped = 3, led._dropped_end - 1
    real_read, seen = led._src.read, {}

    def read(rec):
        data = real_read(rec)
        if rec.seq == last_dropped and not seen:
            seen["x"] = 1
            raw = open(path, "rb").read()
            open(path, "r+b").write(raw.replace(b'"p5"', b'"p6"', 1))
            def reader():
                try:
                    led.records[target]
                except ValueError as exc:
                    seen["refused"] = str(exc)
            t = threading.Thread(target=reader)
            t.start()
            t.join()
        return data

    led._src.read = read
    assert led.verify_chain()[0] and "changed on disk" in seen["refused"]
    led._src.read = real_read
    assert led._src.broken
    with pytest.raises(ValueError, match=f"payload hash mismatch at seq {target}"):
        led.append("witness", {"w": 1})


def test_f5_concurrent_readers_never_share_a_payload_object(tmp_path):
    """The slot is read once: a reader racing eviction gets a copy or a fresh read, never the retained object."""
    led, _, _ = grown(tmp_path, resident=4)
    rec = led._records[-1]
    held = rec.payload
    rec.payload = None if False else held          # resident
    first = ledger_module._owned(rec)
    assert first is not held
    rec.payload = None                             # as if evicted between two reads
    second = ledger_module._owned(rec)
    assert second == first and second is not held and second is not first


def test_membership_compares_headers_before_reading_a_payload_back(tmp_path, monkeypatch):
    led, _, _ = grown(tmp_path)
    wanted = led.records[-1]
    reads = []
    real = ledger_module._LineSource.payload
    monkeypatch.setattr(ledger_module._LineSource, "payload", lambda self, rec: reads.append(rec.seq) or real(self, rec))
    assert wanted in led.records and reads == []


def test_a_dropped_records_read_source_swapped_in_memory_is_found(tmp_path):
    """The skeleton digest does not cover a record's read source, so _verify_dropped checks it is the ledger's own."""
    led, _, _ = grown(tmp_path)
    target = led._records[6]
    assert not target.resident

    class Forged:
        def payload(self, rec):
            return {"proposal_id": "forged", "grant_id": "g0"}

    target._src = Forged()
    ok, why = led.verify_chain()
    assert not ok and "retained record altered in memory at seq 6" in why
    with pytest.raises(ValueError, match="altered in memory at seq 6"):
        led.append("witness", {"w": 1})


def test_a_dropped_records_pointer_moved_to_another_records_line_is_refused_when_read(tmp_path):
    """Record 6's line is verified bytes, so its digest passes; only the hash and seq check keeps record 6's payload
    from being served as record 5's."""
    led, _, _ = grown(tmp_path)
    a, b = led._records[5], led._records[6]
    assert not a.resident and not b.resident
    a._off, a._len, a._digest = b._off, b._len, b._digest
    with pytest.raises(ValueError, match="payload hash mismatch at seq 5: the retained line is another record"):
        led.records[5]


def test_a_payload_altered_in_memory_with_its_pointer_moved_to_a_planted_copy_is_never_dropped(tmp_path):
    """Review F1's planted copy, now carrying the altered payload: the pointer check accepts the planted line, so only
    eviction's own re-hash keeps the altered payload out of the dropped-history digest."""
    path = str(tmp_path / "l.jsonl")
    led = EvidenceLedger(ANCHOR, path, resident=3)
    led.append("event", {"amount": 1})
    target = led._records[1]
    led.verify_incremental()
    target.payload["amount"] = 1000000                                    # altered while resident
    planted = asdict(LedgerRecord(target.seq, target.ts_utc, target.record_type, target.payload,
                                  target.prev_hash, target.hash, target.corrects, target.hash_version))
    led.append("note", {"quote": planted})
    blob = json.dumps(planted).encode()
    target._off, target._len, target._digest = (open(path, "rb").read().index(blob), len(blob),
                                                hashlib.sha256(blob).digest())
    for i in range(4):
        led.append("note", {"i": i})
    assert target.resident
    with pytest.raises(ValueError, match="payload hash mismatch at seq 1"):
        led.append("witness", {"w": 1})


def test_explicit_verification_holds_a_dropped_skeleton_to_its_line_even_when_the_digest_is_recomputed(tmp_path):
    """The dropped-history digest is itself in memory. A skeleton changed together with it passes the commit path;
    verify_chain re-derives the record from the file and compares its header."""
    led, _, _ = grown(tmp_path)
    target = led._records[6]
    assert not target.resident
    target.ts_utc = "2000-01-01T00:00:00Z"
    digest = hashlib.sha256()
    for i in range(1, led._dropped_end):
        digest.update(ledger_module._skeleton(led._records[i]))
    led._dropped_hash, led._dropped_digest = digest, digest.digest()
    ok, why = led.verify_chain()
    assert not ok and "retained record at seq 6 differs from its line in the file" in why


# The file at the path holds this ledger's history only while it ends with this ledger's last line, byte for byte
# (independent reviews of #211, 2026-10-28). Content, not (device, inode): a deleted file's inode number is reused
# by the next file created beside it, and overlayfs copy-up or FUSE can renumber the very same file.

NOT_OURS = "no longer holds this ledger's history"


def _other_history(tmp_path, name="other.jsonl", n=6):
    path = str(tmp_path / name)
    other = EvidenceLedger("sha256:" + "1" * 64, path)
    for i in range(n):
        other.append("event", {"other": i})
    other.close()
    return path


def _in_thread(fn, timeout=10):
    import threading
    box = {}

    def run():
        try:
            box["value"] = fn()
        except BaseException as exc:          # noqa: BLE001 - reported to the test
            box["error"] = exc
    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout)
    assert not t.is_alive(), "blocked instead of refusing"
    return box


@pytest.mark.parametrize("reopen", [False, True])
def test_a_ledger_file_deleted_stops_appends_and_is_never_recreated(tmp_path, reopen):
    led, _, path = grown(tmp_path)
    if reopen:
        led.close()
        led = EvidenceLedger(ANCHOR, path, resident=4)
    os.remove(path)
    for kind in ("event", "witness"):
        with pytest.raises(ValueError, match=NOT_OURS):
            led.append(kind, {"n": 1})
    assert not os.path.exists(path)
    ok, why = led.verify_chain()
    assert not ok and NOT_OURS in why


@pytest.mark.parametrize("reopen", [False, True])
def test_another_history_put_in_place_never_receives_an_append(tmp_path, reopen):
    led, _, path = grown(tmp_path)
    if reopen:
        led.close()
        led = EvidenceLedger(ANCHOR, path, resident=4)
    other = _other_history(tmp_path)
    data = open(other, "rb").read()
    os.replace(other, path)
    for kind in ("witness", "event"):
        with pytest.raises(ValueError, match=NOT_OURS):
            led.append(kind, {"n": 1})
    assert open(path, "rb").read() == data
    ok, why = led.verify_chain()
    assert not ok and NOT_OURS in why


def test_an_inode_number_reused_by_another_file_is_not_this_ledger(tmp_path):
    """Deleting the file frees its inode; the next file created beside it usually gets the same number back."""
    led, _, path = grown(tmp_path)
    for _ in range(3):
        os.remove(path)
        with open(path, "wb") as fh:
            fh.write(b'{"forged": true}\n')
        with pytest.raises(ValueError, match=NOT_OURS):
            led.append("witness", {"w": 1})
        assert open(path, "rb").read() == b'{"forged": true}\n'


def test_two_atomic_saves_over_the_path_never_receive_an_append(tmp_path):
    import tempfile
    led, _, path = grown(tmp_path)
    for i in range(2):
        fd, tmp = tempfile.mkstemp(dir=str(tmp_path))
        os.write(fd, b'{"saved": %d}\n' % i)
        os.close(fd)
        os.replace(tmp, path)
        with pytest.raises(ValueError, match=NOT_OURS):
            led.append("event", {"n": i})
        assert open(path, "rb").read() == b'{"saved": %d}\n' % i


def test_a_file_of_the_same_size_ending_in_another_line_is_not_this_ledger(tmp_path):
    """The size alone is not the anchor: the last line must be this history's last record, byte for byte."""
    led, _, path = grown(tmp_path)
    data = bytearray(open(path, "rb").read())
    data[-3] = ord("0") if data[-3] != ord("0") else ord("1")
    with open(path + ".new", "wb") as fh:
        fh.write(bytes(data))
    os.replace(path + ".new", path)
    with pytest.raises(ValueError, match="last line is not this history's last record"):
        led.append("witness", {"w": 1})
    assert open(path, "rb").read() == bytes(data)


def test_a_byte_identical_copy_put_in_place_continues_the_same_history(tmp_path):
    """Appending to a file that holds exactly this history forks nothing; reads move to it with the appends."""
    led, spine, path = grown(tmp_path)
    led.records[3]                                       # the read source is open on the original file
    data = open(path, "rb").read()
    os.rename(path, path + ".old")
    open(path, "wb").write(data)
    for i in range(10):                                  # long enough for the first of them to leave memory
        led.append("event", {"after": i})
    first_after = len(led.records) - 10
    assert not led._records[first_after].resident
    assert led.records[first_after].payload == {"after": 0}
    assert led.verify_chain()[0]
    assert open(path + ".old", "rb").read() == data
    reopened = everything_in_memory(path)
    assert [asdict(r) for r in reopened.records] == [asdict(r) for r in led.records]


def test_an_old_payload_is_never_read_from_another_history_put_in_place(tmp_path):
    led, _, path = grown(tmp_path)
    os.replace(_other_history(tmp_path, n=60), path)
    with pytest.raises(ValueError, match="payload hash mismatch at seq 3"):
        led.records[3]


def test_a_missing_file_is_a_counted_refusal_when_an_old_payload_is_read(tmp_path):
    """No read descriptor is open yet, and the file is gone: the read refuses as a value error, counted, so the
    next reconstruction reads the file too."""
    led, _, path = grown(tmp_path)
    led.close()
    led = EvidenceLedger(ANCHOR, path, resident=4, read_only=True)
    os.remove(path)
    with pytest.raises(ValueError, match="cannot be read"):
        led.records[3]
    assert led._src.broken
    assert not led.verify_incremental()[0]
    with pytest.raises((EventError, ValueError)):
        EventSpine(led)


def test_a_small_ledgers_verification_reads_its_file(tmp_path):
    """Nothing has left memory, yet verify_chain() checks the file the path names: it never reports an intact
    chain while every append refuses."""
    path = str(tmp_path / "l.jsonl")
    led = EvidenceLedger(ANCHOR, path)
    for i in range(3):
        led.append("event", {"n": i})
    os.replace(_other_history(tmp_path), path)
    ok, why = led.verify_chain()
    assert not ok and NOT_OURS in why
    with pytest.raises(ValueError, match=NOT_OURS):
        led.append("event", {"n": 3})
    assert not led.verify_chain()[0] and not led.verify_incremental()[0]


@pytest.mark.parametrize("reopen", [False, True])
def test_a_fifo_put_in_place_is_refused_without_blocking(tmp_path, reopen):
    led, _, path = grown(tmp_path)
    if reopen:
        led.close()
        led = EvidenceLedger(ANCHOR, path, resident=4)
    os.rename(path, path + ".old")
    os.mkfifo(path)
    box = _in_thread(lambda: led.append("witness", {"w": 1}))
    assert isinstance(box.get("error"), ValueError) and NOT_OURS in str(box["error"])
    if reopen:                                           # no read descriptor yet: the read opens the FIFO
        box = _in_thread(lambda: led.records[3])
        assert isinstance(box.get("error"), ValueError) and "not a regular file" in str(box["error"])


def test_opening_reads_one_file_even_if_the_path_is_swapped_while_it_loads(tmp_path, monkeypatch):
    """The size, the complete end and every line come from one descriptor; the history it loaded is then held
    to the file at the path, which here is another one, so nothing is appended to it."""
    led, _, path = grown(tmp_path)
    led.close()
    later = str(tmp_path / "later.jsonl")
    open(later, "wb").write(open(path, "rb").read())
    continued = EvidenceLedger(ANCHOR, later, resident=4)
    for i in range(3):
        continued.append("event", {"later": i})
    count = len(continued.records)
    continued.close()
    real = ledger_module._complete_end

    def swap(fd, size):
        end = real(fd, size)
        os.replace(later, path)
        return end
    monkeypatch.setattr(ledger_module, "_complete_end", swap)
    led = EvidenceLedger(ANCHOR, path, resident=4)
    assert len(led.records) == count - 3
    with pytest.raises(ValueError, match=NOT_OURS):
        led.append("event", {"n": 1})
    monkeypatch.setattr(ledger_module, "_complete_end", real)
    assert len(everything_in_memory(path).records) == count


def test_quarantine_never_truncates_a_file_swapped_in_after_load(tmp_path, monkeypatch):
    led, _, path = grown(tmp_path)
    led.close()
    with open(path, "ab") as fh:
        fh.write(b'{"seq": 81, "ts_utc": "2026-09-26T00:00:00Z", "record_type": "ev')
    other = _other_history(tmp_path)
    data = open(other, "rb").read()
    real = EvidenceLedger._load

    def load_then_swap(self, p):
        real(self, p)
        os.replace(other, path)
    monkeypatch.setattr(EvidenceLedger, "_load", load_then_swap)
    with pytest.raises(ValueError, match=NOT_OURS):
        EvidenceLedger(ANCHOR, path, resident=4, tail="quarantine")
    assert open(path, "rb").read() == data
    assert not [n for n in os.listdir(tmp_path) if ".unacknowledged-" in n]


def test_a_read_only_observer_verifies_while_its_writer_appends(tmp_path):
    led, _, path = grown(tmp_path)
    observer = EvidenceLedger(ANCHOR, path, read_only=True, tail="ignore", resident=4)
    for i in range(10):
        led.append("event", {"n": i})
    assert observer.verify_chain()[0]
    assert observer.records[3] == led.records[3]


def test_an_ordinary_open_failure_propagates_and_is_not_counted_as_another_file(tmp_path, monkeypatch):
    """Permissions, descriptors or I/O failing the open are a definite failure before the write, as they always were:
    the error propagates, memory does not advance, and nothing claims the file is another history."""
    import errno
    led, _, path = grown(tmp_path)
    before = led.head

    def denied(p, flags):
        raise PermissionError(errno.EACCES, "Permission denied", p)
    monkeypatch.setattr(ledger_module, "_existing", denied)
    with pytest.raises(PermissionError):
        led.append("event", {"n": 1})
    assert led.head == before and not led._src.broken
    monkeypatch.undo()
    led.append("event", {"n": 1})
    assert led.verify_chain()[0]


# Fourth independent review of the content anchor (#211): each test fails on the code before its fix.

def test_a_read_finishes_before_an_append_that_adopts_another_file_closes_its_descriptor(tmp_path):
    """adopt() closed the cached read descriptor while another thread was between _open() and its pread, so the read
    failed with EBADF or, the number reused, counted a false failure. The read holds the source's lock; the append
    waits for it."""
    led, _, path = grown(tmp_path)
    assert led.records[2].payload                                    # a read descriptor cached on the original file
    with open(path, "rb") as fh:
        data = fh.read()
    with open(path + ".copy", "wb") as fh:
        fh.write(data)
    os.replace(path + ".copy", path)                                 # a byte-identical copy: accepted, then adopted
    src, real_open, seen = led._src, led._src._open, {}

    def opened():
        fd = real_open()
        if "append" not in seen:
            seen["append"] = threading.Thread(target=lambda: seen.update(seq=led.append("event", {"w": 1}).seq),
                                              daemon=True)
            seen["append"].start()
            seen["append"].join(0.5)                                 # the append would close fd here
            with open(tmp_path / "unrelated.bin", "wb") as fh:
                fh.write(b"z" * 4096)
            seen["other"] = os.open(tmp_path / "unrelated.bin", os.O_RDONLY)   # would take the freed number
        return fd
    failures = src.failures
    src._open = opened
    try:
        expected = everything_in_memory(path).records[3].payload
        assert led.records[3].payload == expected
    finally:
        del src._open
        seen["append"].join(10)
        os.close(seen["other"])
    assert src.failures == failures and seen["seq"] == len(led.records) - 1
    assert led.verify_chain()[0]


def _hold_lease(path, kind, release_after=0.3):
    """A child process takes a lease on the file and gives it up ``release_after`` seconds after the kernel asks.
    Skips only where leases are unsupported; a lease refused because a descriptor is open (EAGAIN) fails the test."""
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        try:
            try:
                fd = os.open(path, os.O_RDONLY if kind == fcntl.F_RDLCK else os.O_RDWR)
                signal.signal(signal.SIGIO, lambda *a: (time.sleep(release_after),
                                                        fcntl.fcntl(fd, fcntl.F_SETLEASE, fcntl.F_UNLCK)))
                fcntl.fcntl(fd, fcntl.F_SETLEASE, kind)
            except OSError as exc:
                os.write(w, str(exc.errno).encode())
                os._exit(0)
            os.write(w, b"ok")
            time.sleep(5)
        finally:
            os._exit(0)
    os.close(w)
    ready = os.read(r, 16)
    os.close(r)
    if ready != b"ok":
        os.waitpid(pid, 0)
        code = int(ready or 0)
        if code in (errno.EINVAL, errno.ENOSYS, errno.EPERM, errno.EACCES):
            pytest.skip(f"leases unavailable here ({errno.errorcode.get(code, code)})")
        pytest.fail(f"the lease was refused ({errno.errorcode.get(code, code)}): a descriptor is still open on {path}")
    return pid


def _release(pid):
    os.kill(pid, signal.SIGKILL)
    os.waitpid(pid, 0)


@pytest.mark.skipif(not hasattr(fcntl, "F_SETLEASE"), reason="Linux leases")
def test_an_append_waits_out_a_lease_break_instead_of_refusing(tmp_path):
    """An NFSv4 delegation, a Samba oplock or any F_SETLEASE holder makes a non-blocking open fail with EWOULDBLOCK
    while the kernel breaks the lease. That is not another history: wait for the break, as a blocking open does."""
    path = str(tmp_path / "l.jsonl")
    led = EvidenceLedger(ANCHOR, path)
    led.append("event", {"i": 0})
    led._src.close()                                                  # no descriptor of ours keeps a read lease off
    pid = _hold_lease(path, fcntl.F_RDLCK)
    try:
        assert led.append("event", {"i": 1}).seq == 2 and led._src.failures == 0
    finally:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    assert led.verify_chain()[0]


@pytest.mark.skipif(not hasattr(fcntl, "F_SETLEASE"), reason="Linux leases")
def test_an_observer_open_waits_out_a_lease_break(tmp_path):
    path = str(tmp_path / "l.jsonl")
    EvidenceLedger(ANCHOR, path).close()
    pid = _hold_lease(path, fcntl.F_WRLCK)
    try:
        assert EvidenceLedger(ANCHOR, path, read_only=True, tail="ignore").verify_chain()[0]
    finally:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)


def test_history_assigned_to_a_file_backed_writer_is_never_appended_onto_its_file(tmp_path):
    """The file still ends with its own last line, so the anchor alone accepted an append after an earlier snapshot
    or another valid history was assigned; the line written forked the file, found only at the next open."""
    led, _, path = grown(tmp_path)
    full = list(led.records)
    led.records = full[:5]
    for record_type in ("event", "witness"):
        with pytest.raises(ValueError, match="appending would fork it"):
            led.append(record_type, {"after": "assign"})
    led.records = full                                                # its own history again: appends continue
    led.append("event", {"after": "restore"})
    led.close()
    assert len(everything_in_memory(path).records) == len(full) + 1


def test_bytes_another_writer_appends_after_the_check_are_never_followed_by_ours(tmp_path, monkeypatch):
    """A writer that ignores the lock appends between the anchor check and our write: nothing of ours is written
    and the refusal is definite (the next append is refused by the anchor, not left uncertain)."""
    led, _, path = grown(tmp_path)
    head, intruder = led.head, b'{"intruder": 1}\n'
    with open(path, "rb") as fh:
        before = fh.read()
    real = led._holds

    def check_then_intrude(fd, *, exact):
        result = real(fd, exact=exact)
        if exact:
            with open(path, "ab") as fh:
                fh.write(intruder)
        return result
    monkeypatch.setattr(led, "_holds", check_then_intrude)
    with pytest.raises(ValueError, match=NOT_OURS):
        led.append("witness", {"w": 1})
    with open(path, "rb") as fh:
        assert fh.read() == before + intruder and led.head == head


def test_bytes_another_writer_appends_during_the_write_leave_the_append_uncertain(tmp_path, monkeypatch):
    """Bytes landing around ours after the offset check: the file is not this history plus our line, so the
    append is reported uncertain, never acknowledged."""
    led, _, path = grown(tmp_path)
    real, done = os.fsync, []

    def fsync(fd):
        if not done:
            done.append(fd)
            with open(path, "ab") as fh:
                fh.write(b'{"intruder": 1}\n')
        return real(fd)
    monkeypatch.setattr(ledger_module.os, "fsync", fsync)
    with pytest.raises(ReconciliationRequired):
        led.append("witness", {"w": 1})
    monkeypatch.undo()
    with pytest.raises(ReconciliationRequired, match="uncertain"):
        led.append("event", {"n": 1})


def test_a_fifo_or_device_at_the_writer_lock_is_refused_without_blocking(tmp_path):
    path = str(tmp_path / "l.jsonl")
    os.mkfifo(path + ".lock")
    box = _in_thread(lambda: EvidenceLedger(ANCHOR, path))
    assert isinstance(box.get("error"), ValueError) and "writer lock" in str(box["error"])
    os.unlink(path + ".lock")
    os.symlink(os.devnull, path + ".lock")
    box = _in_thread(lambda: EvidenceLedger(ANCHOR, path))
    assert isinstance(box.get("error"), ValueError) and "not a regular file" in str(box["error"])
    assert not os.path.exists(path)


def test_a_fifo_at_the_quarantine_sidecar_name_is_refused_without_blocking(tmp_path):
    led, _, path = grown(tmp_path)
    led.close()
    torn = b'{"seq": 81, "ts_utc": "2026-09-26T00:00:00Z", "record_type": "ev'
    with open(path, "ab") as fh:
        fh.write(torn)
    os.mkfifo(f"{path}.unacknowledged-{hashlib.sha256(torn).hexdigest()[:16]}")
    box = _in_thread(lambda: EvidenceLedger(ANCHOR, path, resident=4, tail="quarantine"))
    assert isinstance(box.get("error"), ValueError) and "a different quarantined tail" in str(box["error"])
    with open(path, "rb") as fh:
        assert fh.read().endswith(torn)                              # nothing truncated


def test_a_writers_verification_reports_bytes_appended_past_its_history(tmp_path):
    """A writer's file is exactly its history: bytes another process appended are reported by explicit verification
    itself, not left for the next append to find."""
    led, _, path = grown(tmp_path)
    with open(path, "ab") as fh:
        fh.write(b'{"intruder": 1}\n')
    ok, reason = led.verify_chain()
    assert not ok and NOT_OURS in reason


# Fifth independent review (#211): each test fails on f17ce785.
LEASES = pytest.mark.skipif(not hasattr(fcntl, "F_SETLEASE"), reason="Linux leases")


@LEASES
def test_the_writer_lock_open_waits_out_a_lease_break(tmp_path):
    path = str(tmp_path / "l.jsonl")
    EvidenceLedger(ANCHOR, path).close()
    pid = _hold_lease(path + ".lock", fcntl.F_RDLCK)
    try:
        led = EvidenceLedger(ANCHOR, path)                                   # waits for the break; never refuses
    finally:
        _release(pid)
    assert led.append("event", {"i": 1}).seq == 1
    led.close()


@LEASES
def test_quarantine_waits_out_a_lease_on_a_sidecar_holding_the_same_bytes(tmp_path):
    """An earlier quarantine wrote the sidecar and died before truncating: the next open finishes it."""
    led, _, path = grown(tmp_path)
    led.close()
    torn = b'{"seq": 81, "ts_utc": "2026-09-26T00:00:00Z", "record_type": "ev'
    with open(path, "ab") as fh:
        fh.write(torn)
    sidecar = f"{path}.unacknowledged-{hashlib.sha256(torn).hexdigest()[:16]}"
    with open(sidecar, "wb") as fh:
        fh.write(torn)
    pid = _hold_lease(sidecar, fcntl.F_WRLCK)
    try:
        led = EvidenceLedger(ANCHOR, path, resident=4, tail="quarantine")
    finally:
        _release(pid)
    assert led.records[-1].record_type == "recovery"
    with open(path, "rb") as fh:
        assert not fh.read().endswith(torn)
    led.close()


@LEASES
def test_explicit_verification_waits_out_a_lease_break(tmp_path):
    led, _, path = grown(tmp_path)
    led._src.close()                                                         # no descriptor of ours stops the lease
    pid = _hold_lease(path, fcntl.F_WRLCK)
    try:
        ok, why = led.verify_chain()
    finally:
        _release(pid)
    assert ok, why
    assert led._src.failures == 0


@LEASES
def test_an_old_payload_read_waits_out_a_lease_break(tmp_path):
    led, _, path = grown(tmp_path)
    expected = everything_in_memory(path).records[3].payload
    led._src.close()
    pid = _hold_lease(path, fcntl.F_WRLCK)
    try:
        assert led.records[3].payload == expected
    finally:
        _release(pid)
    assert led._src.failures == 0


def test_a_forked_child_reads_while_a_parent_thread_held_the_read_lock(tmp_path):
    """A parent thread in a read (waiting out a lease break) holds the read source's lock at the fork; in the child no
    thread will ever release it, so the child's lock is a new one."""
    led, _, path = grown(tmp_path)
    expected = everything_in_memory(path).records[3].payload
    held, release = threading.Event(), threading.Event()

    def reader():
        with led._src._lock:
            held.set()
            release.wait(10)
    t = threading.Thread(target=reader, daemon=True)
    t.start()
    held.wait(5)
    pid = os.fork()
    if pid == 0:
        signal.alarm(5)                                                      # a hang kills the child: the test fails
        try:
            os._exit(0 if led.records[3].payload == expected else 3)
        except BaseException:
            os._exit(4)
    _, status = os.waitpid(pid, 0)
    release.set()
    t.join(5)
    assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0, status


def test_close_waits_for_an_append_in_flight(tmp_path):
    """close() releases the writer lock only after an append another thread has started, so a second writer never
    opens the file while that append still writes to it."""
    led, _, path = grown(tmp_path)
    inside, done = threading.Event(), []
    real_adopt = led._src.adopt

    def slow_adopt(fd, **kw):
        inside.set()
        time.sleep(0.3)
        return real_adopt(fd, **kw)
    led._src.adopt = slow_adopt
    t = threading.Thread(target=lambda: done.append(led.append("witness", {"w": 1}).seq), daemon=True)
    t.start()
    assert inside.wait(5)
    led.close()
    assert done, "close() returned while the append was still writing"
    t.join(5)
    second = EvidenceLedger(ANCHOR, path, resident=4)                       # the append is in the file it opens
    assert second.records[-1].payload == {"w": 1} and second.append("event", {"after": "close"})
    second.close()


def test_an_overwrite_of_our_line_during_the_write_leaves_the_append_uncertain(tmp_path, monkeypatch):
    """Same length, other bytes: the file is not this history plus our line, so the append is not acknowledged."""
    led, _, path = grown(tmp_path)
    real, done = os.fsync, []

    def fsync(fd):
        if not done:
            done.append(fd)
            size = os.path.getsize(path)
            with open(path, "r+b") as fh:
                fh.seek(size - 3)
                fh.write(b"X")
        return real(fd)
    monkeypatch.setattr(ledger_module.os, "fsync", fsync)
    with pytest.raises(ReconciliationRequired):
        led.append("witness", {"w": 1})
