"""Torn-tail recovery: quarantine, never delete; refuse anything a single interrupted append cannot produce.

Torn tails here are cut from real serialized records, exactly as a crash mid-append leaves them.
"""
from __future__ import annotations

import fcntl
import glob
import hashlib
import json
import os

import pytest

from provenance.ledger import EvidenceLedger, WriterConflict
from provenance.recovery import EVENT_TYPE, RISKS, RecoveryRefused, recover_torn_tail

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


def _write(path, data):
    with open(path, "wb") as fh:
        fh.write(data)


def _tear_next(path, keep):
    """Append one more real record, then cut its line as an interrupted append would: keep(line) bytes of it."""
    ledger = EvidenceLedger(ANCHOR, path=path)
    probe = ledger.append("event", {"type": "probe", "n": 99, "note": "the append that never returned"})
    ledger.close()
    data = _bytes(path)
    body, line = data[:-1].rsplit(b"\n", 1)
    line += b"\n"
    torn = line[:keep(line)]
    _write(path, body + b"\n" + torn)
    return torn, probe


def _recover(path, **kwargs):
    if "expected_head" not in kwargs:
        kwargs.setdefault("acknowledged_risks", ("unanchored",))   # the operator accepts the unanchored case
    return recover_torn_tail(path, ANCHOR, recovered_by="ops:test", reason="process killed mid-append", **kwargs)


def _events(path):
    ledger = EvidenceLedger(ANCHOR, path=path)
    try:
        return [r.payload for r in ledger.by_type("event") if r.payload.get("type") == EVENT_TYPE]
    finally:
        ledger.close()


def test_a_clean_ledger_is_left_exactly_as_it_was(tmp_path):
    path, _ = _ledger(tmp_path)
    before = _bytes(path)
    assert _recover(path) == {"torn": False, "quarantined": None, "recorded": []}
    assert _bytes(path) == before and glob.glob(path + ".torn-*") == []


@pytest.mark.parametrize("keep", [3, 24, lambda line: len(line) // 2])
def test_a_torn_tail_is_quarantined_byte_for_byte_and_the_recovery_is_chained(tmp_path, keep):
    path, head = _ledger(tmp_path)
    torn, probe = _tear_next(path, keep if callable(keep) else (lambda line, k=keep: k))
    with pytest.raises(ValueError):
        EvidenceLedger(ANCHOR, path=path)   # fail-closed is unchanged: opening alone never repairs
    out = _recover(path)
    q = out["quarantined"]
    assert out["torn"] and q["classification"] == "partial" and q["prior_head"] == head and q["torn_bytes"] == len(torn)
    assert _bytes(str(tmp_path / q["quarantine_file"])) == torn
    assert q["torn_sha256"] == "sha256:" + hashlib.sha256(torn).hexdigest()
    assert q["anchor"].startswith("none supplied")
    ledger = EvidenceLedger(ANCHOR, path=path)
    ok, msg = ledger.verify_chain()
    assert ok, msg
    assert ledger.find(probe.hash) is None and ledger.records[-2].hash == head   # nothing before the tear changed
    ledger.close()
    [event] = _events(path)
    assert event["prior_head"] == head and event["recovered_by"] == "ops:test" and "not chained" in event["disposition"]
    after = _bytes(path)
    assert _recover(path) == {"torn": False, "quarantined": None, "recorded": []}   # idempotent
    assert _bytes(path) == after


def test_a_zero_filled_tail_from_power_loss_is_recovered(tmp_path):
    path, head = _ledger(tmp_path)
    with open(path, "ab") as fh:
        fh.write(b"\x00" * 512)
    q = _recover(path)["quarantined"]
    assert q["classification"] == "zero_fill" and q["prior_head"] == head


def test_a_partial_record_padded_with_zeros_is_recovered(tmp_path):
    path, head = _ledger(tmp_path)
    torn, _ = _tear_next(path, lambda line: 40)
    with open(path, "ab") as fh:
        fh.write(b"\x00" * 100)
    assert _recover(path)["quarantined"]["classification"] == "partial"


def _whole_record_without_newline(tmp_path):
    path, head = _ledger(tmp_path)
    torn, probe = _tear_next(path, lambda line: len(line) - 1)
    return path, head, probe


def _record_missing_its_closing_fields(tmp_path):
    path, head = _ledger(tmp_path)
    torn, probe = _tear_next(path, lambda line: len(line) - 2)   # "}\n" gone: content complete
    return path, head, probe


@pytest.mark.parametrize("make", [_whole_record_without_newline, _record_missing_its_closing_fields])
def test_a_tail_with_complete_content_is_suspect_and_refused_without_proof(tmp_path, make):
    path, head, probe = make(tmp_path)
    data = _bytes(path)
    with pytest.raises(RecoveryRefused, match="may have been acknowledged"):
        _recover(path)   # deleting a byte or two must never be enough to drop an acknowledged record
    with pytest.raises(RecoveryRefused, match="expected acknowledged head"):
        _recover(path, expected_head=probe.hash)
    assert _bytes(path) == data and glob.glob(path + ".torn-*") == []


@pytest.mark.parametrize("make,classification", [(_whole_record_without_newline, "complete_unterminated"),
                                                 (_record_missing_its_closing_fields, "content_complete")])
@pytest.mark.parametrize("proof", ["expected_head", "explicit"])
def test_with_proof_a_complete_tail_is_quarantined_never_admitted(tmp_path, make, classification, proof):
    path, head, probe = make(tmp_path)
    if proof == "expected_head":   # a matching head is not enough on its own for a complete record (review R1b)
        with pytest.raises(RecoveryRefused, match="complete_record"):
            _recover(path, expected_head=head)
    kwargs = ({"expected_head": head, "acknowledged_risks": ("complete_record",)} if proof == "expected_head"
              else {"acknowledged_risks": ("unanchored", "complete_record")})
    q = _recover(path, **kwargs)["quarantined"]
    assert q["classification"] == classification and q["torn_record_hash"] == probe.hash and q["prior_head"] == head
    assert q["acknowledged_risks"] == (["complete_record"] if proof == "expected_head"
                                       else ["unanchored", "complete_record"])
    ledger = EvidenceLedger(ANCHOR, path=path)
    assert ledger.find(probe.hash) is None   # an append that never returned is never admitted
    ledger.close()
    [event] = _events(path)
    assert event["classification"] == classification and event["acknowledged_risks"] == q["acknowledged_risks"]
    assert event["disposition"].startswith("quarantined, not chained: the head" if proof == "expected_head"
                                           else "quarantined, not chained, unanchored")


def _flip_final_newline(path):
    data = _bytes(path)
    _write(path, data[:-1] + b"\x0b")


def _join_last_two_lines(path):
    data = _bytes(path)
    body, a, b = data[:-1].rsplit(b"\n", 2)
    _write(path, body + b"\n" + a + b)


def _non_ascii_tail(path):
    with open(path, "ab") as fh:
        fh.write('{"seq": 3, "ts_utc": "2026-11-13é'.encode("utf-8"))


def _nul_inside_tail(path):
    with open(path, "ab") as fh:
        fh.write(b'{"seq": 3, "ts\x00utc": "')


def _wrong_beginning(path):
    with open(path, "ab") as fh:
        fh.write(b'{"seq": 3, "record_type": "event", "payl')


def _wrong_sequence(path):
    with open(path, "ab") as fh:
        fh.write(b'{"seq": 9, "ts_utc": "2026')


@pytest.mark.parametrize("damage", [_flip_final_newline, _join_last_two_lines, _non_ascii_tail, _nul_inside_tail,
                                    _wrong_beginning, _wrong_sequence])
def test_corruption_that_no_interrupted_append_produces_is_refused_even_with_proof(tmp_path, damage):
    path, head = _ledger(tmp_path, n=3)
    damage(path)
    data = _bytes(path)
    for kwargs in ({}, {"acknowledged_risks": RISKS}):
        with pytest.raises(RecoveryRefused):
            _recover(path, **kwargs)
    assert _bytes(path) == data and glob.glob(path + ".torn-*") == []


@pytest.mark.parametrize("damage", ["tampered", "blank", "genesis_torn", "empty"])
def test_a_prefix_that_does_not_verify_is_refused_and_left_untouched(tmp_path, damage):
    path, _ = _ledger(tmp_path)
    data = _bytes(path)
    lines = data.split(b"\n")
    if damage == "tampered":
        lines[1] = lines[1].replace(b'"n": 0', b'"n": 7')
        data = b"\n".join(lines) + b'{"seq": 3, "ts_utc'
    elif damage == "blank":
        data = data + b"\n" + b'{"seq": 3, "ts_utc'
    elif damage == "genesis_torn":
        data = lines[0][:20]
    else:
        data = b""
    _write(path, data)
    with pytest.raises(RecoveryRefused):
        _recover(path)
    assert _bytes(path) == data and glob.glob(path + ".torn-*") == []


def test_another_constitution_is_refused(tmp_path):
    path, _ = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    data = _bytes(path)
    with pytest.raises(RecoveryRefused):
        recover_torn_tail(path, "sha256:" + "b" * 64, recovered_by="ops:test", reason="r")
    assert _bytes(path) == data


def test_an_expected_head_that_does_not_match_is_refused(tmp_path):
    path, head = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    data = _bytes(path)
    with pytest.raises(RecoveryRefused):
        _recover(path, expected_head="sha256:" + "0" * 64)
    assert _bytes(path) == data
    q = _recover(path, expected_head=head)["quarantined"]
    assert q["anchor"] == "expected_head matched" and q["acknowledged_risks"] == []


def test_a_live_writer_blocks_recovery(tmp_path):
    path, _ = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    data = _bytes(path)
    holder = open(path + ".lock", "a")
    fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(WriterConflict):
            _recover(path)
    finally:
        holder.close()
    assert _bytes(path) == data and glob.glob(path + ".torn-*") == []


def test_a_symlinked_path_is_refused_because_the_writer_lock_is_keyed_on_the_path(tmp_path):
    path, _ = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    alias = str(tmp_path / "current.jsonl")
    os.symlink(path, alias)
    data = _bytes(path)
    with pytest.raises(RecoveryRefused, match="symlink"):
        _recover(alias)
    assert _bytes(path) == data


def test_a_hard_linked_ledger_is_refused_for_the_same_reason(tmp_path):
    path, _ = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    alias = str(tmp_path / "current.jsonl")
    os.link(path, alias)
    holder = open(alias + ".lock", "a")   # a live writer that opened the ledger through the other name
    fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
    data = _bytes(path)
    try:
        for name in (path, alias):
            with pytest.raises(RecoveryRefused, match="hard link"):
                _recover(name)
    finally:
        holder.close()
    assert _bytes(path) == data and glob.glob(path + ".torn-*") == []
    os.unlink(alias)
    assert _recover(path)["torn"]


def test_recovery_names_who_ran_it_and_why(tmp_path):
    path, _ = _ledger(tmp_path)
    with pytest.raises(ValueError):
        recover_torn_tail(path, ANCHOR, recovered_by="", reason="x")
    with pytest.raises(ValueError):
        recover_torn_tail(path, ANCHOR, recovered_by="ops:test", reason="  ")
    with pytest.raises(ValueError):
        recover_torn_tail(path, ANCHOR, recovered_by="ops:test", reason="r", acknowledged_risks=("everything",))


def test_a_crash_after_truncation_is_completed_on_the_next_call_without_duplicates(tmp_path, monkeypatch):
    path, head = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    import provenance.recovery as recovery

    def died(*args, **kwargs):
        raise SystemExit("killed between the truncation and the ledger event")
    monkeypatch.setattr(recovery, "_record_quarantines", died)
    with pytest.raises(SystemExit):
        _recover(path)
    monkeypatch.undo()
    assert _bytes(path).endswith(b"\n") and len(glob.glob(path + ".torn-*")) == 2   # copy and sidecar survive
    out = recover_torn_tail(path, ANCHOR, recovered_by="ops:someone-else", reason="routine check")
    assert out["torn"] is False and len(out["recorded"]) == 1
    [event] = _events(path)
    assert event["classification"] == "partial" and event["prior_head"] == head
    # The truncation is attributed to whoever did it; the later caller only completed the record.
    assert (event["recovered_by"], event["reason"], event["recorded_by"]) == (
        "ops:test", "process killed mid-append", "ops:someone-else")
    assert _recover(path)["recorded"] == []


def test_two_separate_tears_with_identical_bytes_each_get_their_own_event(tmp_path):
    path, head1 = _ledger(tmp_path)
    with open(path, "ab") as fh:
        fh.write(b'{"seq": ')   # every record line starts with these bytes
    first = _recover(path)
    ledger = EvidenceLedger(ANCHOR, path=path)
    ledger.append("event", {"type": "probe", "n": "after the first recovery"})
    head2 = ledger.head
    ledger.close()
    with open(path, "ab") as fh:
        fh.write(b'{"seq": ')
    second = _recover(path)
    assert first["quarantined"]["torn_sha256"] == second["quarantined"]["torn_sha256"]
    assert first["quarantined"]["quarantine_file"] != second["quarantined"]["quarantine_file"]
    assert len(second["recorded"]) == 1
    assert [e["prior_head"] for e in _events(path)] == [head1, head2]


def test_backups_and_editor_files_beside_the_ledger_are_never_taken_for_quarantines(tmp_path):
    path, _ = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    q = _recover(path)["quarantined"]
    qpath = str(tmp_path / q["quarantine_file"])
    for stray in (qpath + ".json.bak", qpath + "~", path + ".torn-notes", path + ".torn-" + "0" * 64):
        _write(stray, b"not a quarantine")
    assert _recover(path)["recorded"] == []
    assert len(_events(path)) == 1


def test_a_sidecar_cannot_rewrite_the_event_it_describes(tmp_path, monkeypatch):
    path, _ = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    import provenance.recovery as recovery
    monkeypatch.setattr(recovery, "_record_quarantines", lambda *a, **k: [])
    q = _recover(path)["quarantined"]
    monkeypatch.undo()
    sidecar = str(tmp_path / q["quarantine_file"]) + ".json"
    meta = json.loads(_bytes(sidecar))
    _write(sidecar, json.dumps({**meta, "type": "something.else", "recorded_by": "nobody", "disposition": "fine"}).encode())
    _recover(path)
    [event] = _events(path)
    assert event["type"] == EVENT_TYPE and event["recorded_by"] == "ops:test" and "not chained" in event["disposition"]


def test_a_sidecar_that_contradicts_its_quarantine_file_is_not_trusted(tmp_path, monkeypatch):
    path, _ = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    import provenance.recovery as recovery
    monkeypatch.setattr(recovery, "_record_quarantines", lambda *a, **k: [])
    q = _recover(path)["quarantined"]
    monkeypatch.undo()
    sidecar = str(tmp_path / q["quarantine_file"]) + ".json"
    meta = json.loads(_bytes(sidecar))
    _write(sidecar, json.dumps({**meta, "prior_head": "sha256:" + "f" * 64, "recovered_by": "nobody"}).encode())
    _recover(path)
    [event] = _events(path)
    assert event["classification"].startswith("unknown: sidecar inconsistent") and event["recovered_by"].startswith("unknown")


def test_a_quarantine_name_collision_with_different_bytes_is_refused(tmp_path):
    path, head = _ledger(tmp_path)
    torn, _ = _tear_next(path, lambda line: 30)
    data = _bytes(path)
    _write(f"{path}.torn-{head.split(':', 1)[1][:16]}-{hashlib.sha256(torn).hexdigest()}", b"something else")
    with pytest.raises(RecoveryRefused):
        _recover(path)
    assert _bytes(path) == data


def test_the_sidecar_matches_the_quarantined_bytes(tmp_path):
    path, _ = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    q = _recover(path)["quarantined"]
    meta = json.loads(_bytes(str(tmp_path / q["quarantine_file"]) + ".json"))
    assert meta["torn_sha256"] == q["torn_sha256"] and meta["torn_bytes"] == q["torn_bytes"]
    assert os.path.basename(path) in q["quarantine_file"]


def test_an_unanchored_recovery_is_refused_until_acknowledged(tmp_path):
    path, _ = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    data = _bytes(path)
    with pytest.raises(RecoveryRefused, match="unanchored"):
        recover_torn_tail(path, ANCHOR, recovered_by="ops:test", reason="r")
    assert _bytes(path) == data and glob.glob(path + ".torn-*") == []


def _tear_a_seal(path):
    ledger = EvidenceLedger(ANCHOR, path=path)
    ledger.seal(sealed_by="alfonso_lopez", reason="shutdown")
    ledger.close()
    data = _bytes(path)
    body, line = data[:-1].rsplit(b"\n", 1)
    _write(path, body + b"\n" + line[: len(line) // 2])


def test_a_torn_stop_needs_its_own_acknowledgment_and_the_event_warns(tmp_path):
    path, _ = _ledger(tmp_path)
    _tear_a_seal(path)
    data = _bytes(path)
    with pytest.raises(RecoveryRefused, match="stop_record"):
        _recover(path)
    assert _bytes(path) == data
    q = _recover(path, acknowledged_risks=("unanchored", "stop_record"))["quarantined"]
    assert q["torn_record_type"] == "seal" and q["may_have_been_a_stop"]
    [event] = _events(path)
    assert "re-issue it before the body restarts" in event["stop_warning"]


def test_a_tail_cut_before_its_type_is_warned_about_without_an_acknowledgment(tmp_path):
    path, _ = _ledger(tmp_path)
    _tear_next(path, lambda line: 12)   # '{"seq": 3, "' : the record type is unknowable
    q = _recover(path)["quarantined"]
    assert q["torn_record_type"] is None and q["may_have_been_a_stop"]
    assert _events(path)[0]["stop_warning"]
    path2, _ = _ledger(tmp_path / "b" if (tmp_path / "b").mkdir() is None else tmp_path)
    _tear_next(path2, lambda line: len(line) // 2)   # an ordinary event's type is visible: no warning
    _recover(path2)
    assert _events(path2)[0]["stop_warning"] is None


def test_no_restarting_writer_can_append_between_the_truncation_and_its_record(tmp_path):
    import threading
    path, _ = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    stop = threading.Event()

    def restart_loop():
        while not stop.is_set():
            try:
                body = EvidenceLedger(ANCHOR, path=path)
            except (WriterConflict, ValueError):
                continue
            body.append("event", {"type": "body.restarted"})
            body.close()
            stop.set()
    contender = threading.Thread(target=restart_loop)
    contender.start()
    try:
        for _ in range(200):
            torn_before = not _bytes(path).endswith(b"\n")
            try:
                _recover(path)
                break
            except WriterConflict:
                assert not _bytes(path).endswith(b"\n") or not torn_before   # refused before changing anything
    finally:
        stop.set()
        contender.join(timeout=10)
    ledger = EvidenceLedger(ANCHOR, path=path)
    kinds = [r.payload.get("type") for r in ledger.records[1:]]
    ledger.close()
    assert EVENT_TYPE in kinds
    restarted = [i for i, k in enumerate(kinds) if k == "body.restarted"]
    assert all(i > kinds.index(EVENT_TYPE) for i in restarted)   # nothing lands between truncation and record


@pytest.mark.parametrize("step", ["copy", "sidecar"])
def test_a_crash_while_writing_a_copy_never_leaves_a_partial_file_that_blocks_recovery(tmp_path, monkeypatch, step):
    path, head = _ledger(tmp_path)
    torn, _ = _tear_next(path, lambda line: 30)
    data = _bytes(path)
    import provenance.recovery as recovery
    target = "link" if step == "copy" else "replace"
    real = getattr(os, target)

    def died(*args, **kwargs):
        raise SystemExit(f"killed inside the atomic {step} write")
    monkeypatch.setattr(recovery.os, target, died)
    with pytest.raises(SystemExit):
        _recover(path)
    monkeypatch.setattr(recovery.os, target, real)
    assert _bytes(path) == data   # not truncated: the crash came before the copy and description were durable
    out = _recover(path)
    assert out["torn"] and _bytes(str(tmp_path / out["quarantined"]["quarantine_file"])) == torn
    [event] = _events(path)
    assert event["classification"] == "partial" and event["prior_head"] == head


def test_a_retry_records_its_own_proof_not_an_earlier_attempts(tmp_path, monkeypatch):
    path, head, probe = _whole_record_without_newline(tmp_path)
    import provenance.recovery as recovery
    real_truncate_open = recovery.open if hasattr(recovery, "open") else None

    class Died(BaseException):
        pass
    calls = {"n": 0}
    real_open = open

    def open_then_die(file, mode="r", *args, **kwargs):
        if mode == "r+b":
            raise Died()   # after the sidecar is durable, before truncation
        return real_open(file, mode, *args, **kwargs)
    monkeypatch.setattr(recovery, "open", open_then_die, raising=False)
    with pytest.raises(Died):
        recover_torn_tail(path, ANCHOR, recovered_by="ops:x", reason="first try",
                          acknowledged_risks=("unanchored", "complete_record"))
    monkeypatch.undo()
    assert real_truncate_open is None
    out = recover_torn_tail(path, ANCHOR, recovered_by="ops:y", reason="second try", expected_head=head,
                            acknowledged_risks=("complete_record",))
    [event] = _events(path)
    assert (event["recovered_by"], event["anchor"], event["acknowledged_risks"]) == (
        "ops:y", "expected_head matched", ["complete_record"]) == (
        out["quarantined"]["recovered_by"], out["quarantined"]["anchor"], out["quarantined"]["acknowledged_risks"])


def test_a_checkpoint_one_append_stale_cannot_drop_an_acknowledged_record_silently(tmp_path):
    """Review R1b: a checkpoint taken before the last acknowledged append matches the head before the torn
    line just as a fresh one would, so a matching expected_head never excuses a complete record."""
    path = str(tmp_path / "ledger.jsonl")
    ledger = EvidenceLedger(ANCHOR, path=path)
    ledger.append("event", {"type": "probe"})
    checkpoint = ledger.head
    acked = ledger.append("grant_dispatch", {"proposal_id": "P", "grant_id": "G"})   # returned: acknowledged
    ledger.close()
    _write(path, _bytes(path)[:-1])   # later damage: only the newline is lost
    data = _bytes(path)
    with pytest.raises(RecoveryRefused, match="complete_record"):
        _recover(path, expected_head=checkpoint)
    assert _bytes(path) == data and glob.glob(path + ".torn-*") == []
    q = _recover(path, expected_head=checkpoint, acknowledged_risks=("complete_record",))["quarantined"]
    assert q["torn_record_hash"] == acked.hash and q["acknowledged_risks"] == ["complete_record"]
    [event] = _events(path)
    assert "if that was the writer's last acknowledged head" in event["disposition"]
