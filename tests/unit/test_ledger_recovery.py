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
import provenance.recovery as recovery
from provenance.recovery import (EVENT_TYPE, RISKS, RecoveryInterrupted, RecoveryRefused,
                                 recover_torn_tail)
from provenance.recovery import STOP_RECORD_TYPES as STOP_TYPES

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
    assert _recover(path) == {**{"torn": False, "quarantined": None, "recorded": [], "resumed": False, "unrecorded_quarantines": []}, "last_recovery": None}
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
    again = _recover(path)   # idempotent; the last recovery is shown to the next caller
    assert {k: v for k, v in again.items() if k != "last_recovery"} == {"torn": False, "quarantined": None, "recorded": [], "resumed": False, "unrecorded_quarantines": []}
    assert again["last_recovery"]["quarantine_file"] == q["quarantine_file"]
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
    (tmp_path / "b").mkdir()
    path2 = str(tmp_path / "b" / "ledger.jsonl")
    ledger = EvidenceLedger(ANCHOR, path=path2)
    ledger.append("event", {"type": "action.committed", "action_id": "A"})   # a known, ordinary event type
    ledger.close()
    _tear_last(path2, lambda line: len(line) // 2)
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


# --- applying the plan: the ledger never opens before its recovery is recorded (second review: crash:0, crash:3) ---

class _Killed(BaseException):
    pass


_APPLY_STEPS = ["write_event", "fsync_event", "cut", "fsync_cut", "newline"]


@pytest.mark.parametrize("step", _APPLY_STEPS)
def test_a_crash_at_any_step_of_applying_the_plan_never_leaves_an_openable_unrecorded_ledger(tmp_path, monkeypatch, step):
    path, head = _ledger(tmp_path)
    torn, probe = _tear_next(path, lambda line: len(line) // 2)
    calls = {"pwrite": 0, "fsync": 0}
    real_pwrite, real_fsync, real_ftruncate = os.pwrite, os.fsync, os.ftruncate

    def pwrite(fd, data, offset):
        calls["pwrite"] += 1
        if step == "write_event" and calls["pwrite"] == 1:
            real_pwrite(fd, data[: len(data) // 3], offset)   # killed in the middle of writing the event
            raise _Killed()
        result = real_pwrite(fd, data, offset)
        if step == "newline" and calls["pwrite"] == 2:
            raise _Killed()   # the newline reached the page cache; its fsync never ran
        return result

    def fsync(fd):
        real_fsync(fd)
        calls["fsync"] += 1
        if (step, calls["fsync"]) in (("fsync_event", 1), ("fsync_cut", 2)):
            raise _Killed()

    def ftruncate(fd, length):
        real_ftruncate(fd, length)
        if step == "cut":
            raise _Killed()
    monkeypatch.setattr(recovery, "_apply", lambda p, c, l, _apply=recovery._apply: _patched_apply(
        _apply, p, c, l, monkeypatch, pwrite, fsync, ftruncate))
    with pytest.raises(_Killed):
        recover_torn_tail(path, ANCHOR, recovered_by="supervisor:A", reason="body died", acknowledged_risks=("unanchored",))
    monkeypatch.undo()
    if step != "newline":
        with pytest.raises(ValueError):
            EvidenceLedger(ANCHOR, path=path)   # no restarting writer can append before the repair is recorded
        out = recover_torn_tail(path, ANCHOR, recovered_by="supervisor:B", reason="routine restart",
                                acknowledged_risks=("unanchored",))
        assert out["torn"] and out["resumed"]
        q = out["quarantined"]
        assert (q["recovered_by"], q["completed_by"]) == ("supervisor:A", "supervisor:B")
    [event] = _events(path)   # exactly one recovery event, attributed to the caller whose plan it was
    assert event["recovered_by"] == "supervisor:A" and event["prior_head"] == head
    ledger = EvidenceLedger(ANCHOR, path=path, read_only=True)
    assert ledger.verify_chain()[0] and ledger.find(probe.hash) is None and len(ledger.records) == 4
    assert _recover(path)["torn"] is False


def _patched_apply(apply, path, cut, line, monkeypatch, pwrite, fsync, ftruncate):
    with monkeypatch.context() as m:
        m.setattr(recovery.os, "pwrite", pwrite)
        m.setattr(recovery.os, "fsync", fsync)
        m.setattr(recovery.os, "ftruncate", ftruncate)
        apply(path, cut, line)


def test_a_plan_whose_application_never_began_is_replaced_by_the_retry_with_its_own_proof(tmp_path, monkeypatch):
    path, head, probe = _whole_record_without_newline(tmp_path)

    def died(*args, **kwargs):
        raise _Killed()   # the copy and the plan are durable; the ledger was never touched
    monkeypatch.setattr(recovery, "_apply", died)
    with pytest.raises(_Killed):
        recover_torn_tail(path, ANCHOR, recovered_by="ops:x", reason="first try",
                          acknowledged_risks=("unanchored", "complete_record"))
    monkeypatch.undo()
    out = recover_torn_tail(path, ANCHOR, recovered_by="ops:y", reason="second try", expected_head=head,
                            acknowledged_risks=("complete_record",))
    assert out["resumed"] is False
    [event] = _events(path)
    assert (event["recovered_by"], event["anchor"], event["acknowledged_risks"]) == (
        "ops:y", "expected_head matched", ["complete_record"]) == (
        out["quarantined"]["recovered_by"], out["quarantined"]["anchor"], out["quarantined"]["acknowledged_risks"])


def test_a_sidecar_edited_while_its_plan_waited_is_replaced_and_never_reaches_the_chain(tmp_path, monkeypatch):
    path, _ = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    monkeypatch.setattr(recovery, "_apply", lambda *a, **k: (_ for _ in ()).throw(_Killed()))
    with pytest.raises(_Killed):
        _recover(path)
    monkeypatch.undo()
    [sidecar] = glob.glob(path + ".torn-*.json")
    meta = json.loads(_bytes(sidecar))
    _write(sidecar, json.dumps({**meta, "type": "something.else", "recovered_by": "nobody",
                                "disposition": "fine", "plan": {**meta["plan"], "event_line": "{}"}}).encode())
    _recover(path)
    [event] = _events(path)
    assert event["type"] == EVENT_TYPE and event["recovered_by"] == "ops:test" and "not chained" in event["disposition"]


def test_an_apply_failure_is_reported_as_interrupted_and_the_next_call_completes_it(tmp_path, monkeypatch):
    path, head = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)

    def no_space(fd, length):
        raise OSError(28, "No space left on device")
    with monkeypatch.context() as m:
        m.setattr(recovery.os, "ftruncate", no_space)
        with pytest.raises(RecoveryInterrupted, match="call recover_torn_tail again"):
            _recover(path)
    with pytest.raises(ValueError):
        EvidenceLedger(ANCHOR, path=path)
    out = _recover(path)
    assert out["resumed"] and len(_events(path)) == 1


def test_a_quarantine_copy_that_cannot_be_written_refuses_with_the_ledger_unchanged(tmp_path, monkeypatch):
    path, _ = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    data = _bytes(path)

    def no_space(*args, **kwargs):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(recovery, "_write_atomic", no_space)
    with pytest.raises(RecoveryRefused, match="ledger is unchanged"):
        _recover(path)
    assert _bytes(path) == data


def test_recovery_writes_no_copy_of_history(tmp_path):
    """Second review, crash:4 and honesty:5: verification is in memory, so recovery needs no free space the size of
    the ledger and a killed attempt leaves no copy of canonical history behind."""
    path, _ = _ledger(tmp_path, n=50)
    _tear_next(path, lambda line: 30)
    q = _recover(path)["quarantined"]
    names = sorted(os.listdir(tmp_path))
    assert names == sorted([os.path.basename(path), os.path.basename(path) + ".lock", q["quarantine_file"],
                            q["quarantine_file"] + ".json"])


# --- quarantine files that are not this chain's (second review: crash:1, crash:2, honesty:1, honesty:2) ---

def test_quarantines_from_another_ledger_at_the_same_path_are_reported_never_chained(tmp_path):
    path, _ = _ledger(tmp_path, n=3)
    _tear_next(path, lambda line: 30)
    old = _recover(path)["quarantined"]["quarantine_file"]
    os.unlink(path)
    os.unlink(path + ".lock")
    _ledger(tmp_path, n=1)   # an operator archives the ledger and starts a new one at the same path
    out = _recover(path)
    assert out["torn"] is False and out["recorded"] == [] and out["unrecorded_quarantines"] == [old]
    assert _events(path) == []


def test_an_altered_unrecorded_quarantine_neither_blocks_nor_joins_a_later_recovery(tmp_path):
    path, head = _ledger(tmp_path)
    stray = f"{path}.torn-{'1' * 16}-{'2' * 64}"
    _write(stray, b"bytes that do not match the digest in the name\n")
    _tear_next(path, lambda line: 30)
    out = _recover(path)
    assert out["torn"] and out["unrecorded_quarantines"] == [os.path.basename(stray)]
    [event] = _events(path)
    assert event["quarantine_file"] == out["quarantined"]["quarantine_file"] and event["prior_head"] == head


# --- tails the writer can never produce (second review: classifier:2) -------------------------------------------

def _serialized_next(path, **changes):
    ledger = EvidenceLedger(ANCHOR, path=path)
    rec = ledger.append("grant_dispatch", {"proposal_id": "P", "grant_id": "G"})
    ledger.close()
    data = _bytes(path)
    body, line = data[:-1].rsplit(b"\n", 1)
    _write(path, body + b"\n")
    return json.loads(line), rec


@pytest.mark.parametrize("kind", ["fork", "control_byte", "extra_field", "hash_version_3", "wrong_order",
                                  "compact_complete", "version_1_complete"])
def test_a_tail_the_writer_cannot_produce_is_refused_even_with_every_risk_acknowledged(tmp_path, kind):
    path, _ = _ledger(tmp_path)
    obj, rec = _serialized_next(path)
    line = json.dumps(obj)
    if kind == "fork":
        line = line.replace(obj["prev_hash"], "sha256:" + "9" * 64)[:-1]   # another chain's prev_hash, '}' lost
    elif kind == "control_byte":
        line = line.replace('"ts_utc": "', '"ts_utc": "\x01')[:-2]
    elif kind == "extra_field":
        line = line.replace(', "prev_hash"', ', "extra": 1, "prev_hash"')[:-1]
    elif kind == "hash_version_3":
        line = line.replace('"hash_version": 2', '"hash_version": 3')[:-1]
    elif kind == "compact_complete":
        line = json.dumps(obj, separators=(",", ":"))   # the same record, serialized as the writer never does
    elif kind == "version_1_complete":
        from provenance.ledger import sha256_json
        v1 = {**obj, "hash_version": 1}
        v1["hash"] = sha256_json({k: v1[k] for k in ("seq", "record_type", "payload", "prev_hash", "corrects")})
        line = json.dumps(v1)   # the writer only writes version 2
    else:
        line = json.dumps({k: obj[k] for k in ("seq", "ts_utc", "payload", "record_type", "prev_hash", "hash",
                                                "corrects", "hash_version")})[:-1]
    with open(path, "ab") as fh:
        fh.write(line.encode("ascii"))
    data = _bytes(path)
    with pytest.raises(RecoveryRefused):
        _recover(path, acknowledged_risks=RISKS)
    assert _bytes(path) == data and glob.glob(path + ".torn-*") == []


def test_a_cut_just_before_the_hashs_closing_quote_is_a_complete_record(tmp_path):
    """Second review, classifier:0: once the hash's 64 hex digits are written the record is complete."""
    path, head = _ledger(tmp_path)
    torn, probe = _tear_next(path, lambda line: line.index(b'"hash": "') + len(b'"hash": "') + 71)
    with pytest.raises(RecoveryRefused, match="complete_record"):
        _recover(path, expected_head=head)
    q = _recover(path, expected_head=head, acknowledged_risks=("complete_record",))["quarantined"]
    assert q["classification"] == "content_complete" and q["torn_record_hash"] == probe.hash


# --- stops (second review: classifier:1, honesty:0) -------------------------------------------------------------

def _tear_last(path, keep):
    data = _bytes(path)
    body, line = data[:-1].rsplit(b"\n", 1)
    _write(path, body + b"\n" + line[:keep(line)])
    return line


def _goal_ledger(tmp_path):
    from egregore.goals import GoalRegistry, GoalSpec
    path = str(tmp_path / "ledger.jsonl")
    ledger = EvidenceLedger(ANCHOR, path=path)
    registry = GoalRegistry(ledger=ledger)
    return path, ledger, registry


@pytest.mark.parametrize("control", ["revoke", "supersede", "supersede_authorization", "detach", "kill_capsule",
                                     "autonomy.regressed", "business.terminated", "repair.provider_withdrawn",
                                     "omnimorph.organ_retired", "foundry.node_retired"])
def test_a_torn_founder_control_needs_stop_record_and_the_event_warns(tmp_path, control):
    path = str(tmp_path / "ledger.jsonl")
    ledger = EvidenceLedger(ANCHOR, path=path)
    if control == "revoke":
        ledger.append("egregore.goal_transition", {"source": "s", "goal_id": "g", "reason": "revoked by alfonso_lopez: done",
                                                   "state": {"status": "revoked"}})
    elif control == "supersede":
        ledger.append("egregore.goal_transition", {"source": "s", "goal_id": "g", "reason": "superseded by goal:x (alfonso)",
                                                   "state": {"status": "superseded"}})
    elif control == "supersede_authorization":   # supersede's first append: the replacement goal
        ledger.append("egregore.goal_authorized", {"source": "s", "goal": {"title": "new", "supersedes": "goal:old"},
                                                   "authorized_at": "2026-11-21T00:00:00Z"})
    elif control == "detach":
        ledger.append("egregore.capability_detached", {"genome_id": "x", "reason": "founder detach"})
    elif control == "kill_capsule":
        ledger.append("capsule", {"capsule_id": "c", "decision": {"decision": "kill", "reason": "harm"}})
    elif control == "omnimorph.organ_retired":
        ledger.append("event", {"type": control, "organ": "o", "status": "RETIRED"})
    else:
        ledger.append("event", {"type": control, "subject": "x"})
    head = ledger.records[-2].hash
    ledger.close()
    _tear_last(path, lambda line: len(line) - 3)
    data = _bytes(path)
    with pytest.raises(RecoveryRefused, match="stop_record"):
        _recover(path, expected_head=head, acknowledged_risks=("complete_record",))
    assert _bytes(path) == data
    q = _recover(path, expected_head=head, acknowledged_risks=("complete_record", "stop_record"))["quarantined"]
    assert q["may_have_been_a_stop"] and "re-issue it" in _events(path)[0]["stop_warning"]


@pytest.mark.parametrize("reason,keep,warned", [
    ("wake: signal", lambda line: line.index(b'"state"') + 5, False),   # the reason excludes a stop
    ("sleep: nothing due", lambda line: len(line) - 3, False),
    ("revoked by alfonso_lopez: x", lambda line: line.index(b'"reason"') + 4, True),   # cut before the reason
])
def test_an_ordinary_goal_transition_is_not_a_stop_and_an_unreadable_one_is_warned(tmp_path, reason, keep, warned):
    path = str(tmp_path / "ledger.jsonl")
    ledger = EvidenceLedger(ANCHOR, path=path)
    ledger.append("egregore.goal_transition", {"source": "s", "goal_id": "g", "reason": reason,
                                               "state": {"status": "awake" if reason.startswith("wake") else "dormant"}})
    ledger.close()
    _tear_last(path, keep)
    q = _recover(path, acknowledged_risks=("unanchored", "complete_record"))["quarantined"]
    assert q["may_have_been_a_stop"] is warned and "stop_record" not in q["acknowledged_risks"]


def test_an_unknown_record_type_is_warned_about(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    ledger = EvidenceLedger(ANCHOR, path=path)
    ledger.append("organ.something_new", {"x": 1})
    ledger.close()
    _tear_last(path, lambda line: len(line) // 2)
    q = _recover(path)["quarantined"]
    assert q["torn_record_type"] == "organ.something_new" and q["may_have_been_a_stop"]


def test_every_record_type_the_runtime_declares_is_classified_as_a_stop_or_not():
    """A new founder control cannot fall outside the stop rule unnoticed."""
    import pathlib
    import re as _re
    root = pathlib.Path(__file__).resolve().parents[2]
    declared = set()
    for source in (root / "egregore").glob("*.py"):
        declared |= set(_re.findall(r'_?RECORD\s*=\s*"(egregore\.[a-z_]+)"', source.read_text()))
    classified = recovery.STOP_RECORD_TYPES | recovery.CONTENT_STOP_TYPES | recovery.NON_STOP_RECORD_TYPES
    assert declared and declared <= classified, sorted(declared - classified)


# --- verification in memory matches EvidenceLedger._load ----------------------------------------------------------

@pytest.mark.parametrize("variant", ["clean", "blank_line", "non_dict", "extra_key", "carriage_return", "duplicate_key"])
def test_in_memory_verification_accepts_exactly_what_the_ledger_loads(tmp_path, variant):
    path, _ = _ledger(tmp_path, n=3)
    data = _bytes(path)
    lines = data.split(b"\n")
    if variant == "blank_line":
        data = b"\n".join(lines[:2]) + b"\n\n" + b"\n".join(lines[2:])
    elif variant == "non_dict":
        data = data + b"[1, 2]\n"
    elif variant == "extra_key":
        lines[1] = lines[1][:-1] + b', "extra": 1}'
        data = b"\n".join(lines)
    elif variant == "carriage_return":
        data = data.replace(b"\n", b"\r\n")
    elif variant == "duplicate_key":
        lines[1] = lines[1][:-1] + b', "seq": 1}'
        data = b"\n".join(lines)
    _write(path, data)
    try:
        EvidenceLedger(ANCHOR, path=path, read_only=True)
        loads = True
    except ValueError:
        loads = False
    try:
        recovery._verified_prefix(ANCHOR, data)
        verifies = True
    except RecoveryRefused:
        verifies = False
    assert loads == verifies


def test_a_dotdot_through_a_symlinked_directory_acts_on_the_file_the_os_opens(tmp_path):
    """Second review, crash:5: directories are resolved physically."""
    (tmp_path / "store" / "shards").mkdir(parents=True)
    os.symlink(tmp_path / "store" / "shards", tmp_path / "current")
    path, _ = _ledger(tmp_path / "store")
    _tear_next(path, lambda line: 30)
    named = str(tmp_path / "current" / ".." / "ledger.jsonl")
    assert os.path.samefile(named, path)
    assert _recover(named)["torn"]
    assert len(_events(path)) == 1


# --- every cut offset of real serialized records ------------------------------------------------------------------

_KINDS = {
    "event": lambda ledger: ledger.append("event", {"type": "probe", "n": 99, "note": "the append that never returned"}),
    "grant_dispatch": lambda ledger: ledger.append("grant_dispatch", {
        "proposal_id": "P-1", "grant_id": "G-1", "witness_id": "W-1", "effect_digest": "sha256:" + "e" * 64}),
    "seal": lambda ledger: ledger.seal(sealed_by="founder:test", reason="stop é \"quoted\""),
    "correction": lambda ledger: ledger.append("event", {"type": "correction"}, corrects=ledger.records[1].hash),
    "correction_free_text": lambda ledger: ledger.append("event", {"type": "correction"}, corrects="note: not a hash"),
    "payload_mimics_fields": lambda ledger: ledger.append("event", {   # the fields' own text, inside the payload
        "type": "x", "record_type": "seal", "prev_hash": ledger.head, "hash": "sha256:" + "f" * 64, "corrects": 1}),
}


def _line_of_next(tmp_path, make):
    path = str(tmp_path / "base.jsonl")
    ledger = EvidenceLedger(ANCHOR, path=path)
    for i in range(2):
        ledger.append("event", {"type": "probe", "n": i})
    head = ledger.head
    record = make(ledger)
    ledger.close()
    data = _bytes(path)
    body, line = data[:-1].rsplit(b"\n", 1)
    return body + b"\n", line, head, record


@pytest.mark.parametrize("kind", sorted(_KINDS))
def test_every_cut_of_a_real_record_is_recovered_and_classified_by_what_was_written(tmp_path, kind):
    """Sweep every byte offset an interrupted append can stop at, and a zero-filled extent after the cut at the
    boundaries and every ninth offset. A tail is ``partial`` until the record's hash is fully written; from then on
    it is a complete record (verified by recomputing its hash, or ``content_complete_unverified`` while a free-text
    ``corrects`` value is cut) and needs ``complete_record``. The record type is reported only once its value is
    written, and never from payload text."""
    prefix, line, head, record = _line_of_next(tmp_path, _KINDS[kind])
    text = line.decode("ascii")
    hash_written = text.index('"hash": "%s' % record.hash) + len('"hash": "%s' % record.hash)
    type_written = text.index('"record_type": "%s"' % record.record_type) + len('"record_type": "%s"' % record.record_type)
    corrects_written = text.index('"corrects": ') + len('"corrects": ') + len(json.dumps(record.corrects))
    digits_visible = text.index('"hash": "') + len('"hash": "sha256:')
    stop = record.record_type in STOP_TYPES
    boundaries = {1, type_written - 1, type_written, hash_written - 1, hash_written, len(line) - 1, len(line)}
    for keep in range(1, len(line) + 1):
        for pad in ((b"", b"\x00" * 13) if keep in boundaries or keep % 9 == 0 else (b"",)):
            torn = line[:keep] + pad
            case = tmp_path / f"k{keep}-{len(pad)}"
            case.mkdir()
            path = str(case / "ledger.jsonl")
            _write(path, prefix + torn)
            out = recover_torn_tail(path, ANCHOR, recovered_by="ops:sweep", reason="every offset",
                                    acknowledged_risks=RISKS)
            q = out["quarantined"]
            if keep == len(line):
                want = "complete_unterminated"
            elif keep >= hash_written:
                want = ("content_complete_unverified" if kind == "correction_free_text" and keep < corrects_written
                        else "content_complete")
            elif kind == "correction_free_text" and keep > digits_visible:
                want = "partial_unverified"   # its hash digits match no record this chain can hold
            else:
                want = "partial"
            assert q["classification"] == want, (kind, keep, len(pad), q["classification"])
            if want in ("complete_unterminated", "content_complete"):
                assert q["torn_record_hash"] == record.hash, (kind, keep)
            assert q["torn_record_type"] == (record.record_type if keep >= type_written else None), (kind, keep)
            assert ("complete_record" in q["acknowledged_risks"]) == (want != "partial"), (kind, keep)
            assert ("stop_record" in q["acknowledged_risks"]) == (stop and keep >= type_written), (kind, keep)
            assert _bytes(str(case / q["quarantine_file"])) == torn
            ledger = EvidenceLedger(ANCHOR, path=path, read_only=True)
            assert ledger.find(record.hash) is None   # never admitted
            assert ledger.records[-1].payload["prior_head"] == head
            assert ledger.verify_chain()[0]


# --- third verification round -------------------------------------------------------------------------------------

@pytest.mark.parametrize("record_type,payload", [
    ("event", {"type": "treasury.waterfall_stopped", "amount": 1}),   # a routine treasury event, not a stop
    ("event", {"type": "advantage.genome_sealed", "genome": {"id": "g"}}),   # the foundry's normal final step
    ("egregore.goal_transition", {"source": "s", "goal_id": "g", "reason": "review: noted",
                                  "state": {"status": "paused"}}),   # a routine transition of an already-paused goal
    ("egregore.goal_authorized", {"source": "s", "goal": {"title": "t", "supersedes": None}}),
    ("capsule", {"capsule_id": "c", "decision": {"decision": "retain"}}),
])
def test_ordinary_records_that_mention_stop_words_are_not_refused(tmp_path, record_type, payload):
    path = str(tmp_path / "ledger.jsonl")
    ledger = EvidenceLedger(ANCHOR, path=path)
    ledger.append(record_type, payload)
    head = ledger.records[-2].hash
    ledger.close()
    _tear_last(path, lambda line: len(line) - 3)
    q = _recover(path, expected_head=head, acknowledged_risks=("complete_record",))["quarantined"]
    assert "stop_record" not in q["acknowledged_risks"] and q["may_have_been_a_stop"] is False


def test_a_completed_plan_is_never_resumed_for_a_later_tear(tmp_path):
    """Round 3 (fix-space:1, adv-protocol:1): a restore puts the ledger back to the state the plan was made for, and a
    zero-filled tear of the same length lands at the same cut; the applied plan must not be replayed."""
    path, head = _ledger(tmp_path)
    before_tear = _bytes(path)
    _tear_next(path, lambda line: 30)
    first = _recover(path)
    _write(path, before_tear + b"\x00" * 200)   # restored, then a zero-filled extent after a power loss
    second = _recover(path)
    assert second["resumed"] is False and second["quarantined"]["classification"] == "zero_fill"
    assert second["quarantined"]["quarantine_file"] != first["quarantined"]["quarantine_file"]


def test_a_plan_written_for_another_ledger_at_the_same_path_is_never_resumed(tmp_path, monkeypatch):
    path, _ = _ledger(tmp_path, n=0)   # genesis only: every ledger of this constitution shares this head
    _tear_next(path, lambda line: 30)
    monkeypatch.setattr(recovery, "_apply", lambda *a, **k: (_ for _ in ()).throw(_Killed()))
    with pytest.raises(_Killed):
        _recover(path)
    monkeypatch.undo()
    os.unlink(path)
    os.unlink(path + ".lock")
    _ledger(tmp_path, n=0)   # a new ledger at the same path: same genesis hash, different genesis bytes
    with open(path, "ab") as fh:
        fh.write(b"\x00" * 120)
    out = _recover(path)
    assert out["resumed"] is False and out["quarantined"]["classification"] == "zero_fill"


def test_a_lost_final_newline_read_back_as_zero_is_completed_from_the_plan(tmp_path, monkeypatch):
    """Round 3 (adv-protocol:0, fix-apply:1): power loss in the newline step can leave the event line plus a NUL."""
    path, head = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    real = recovery._apply

    def newline_lost(p, cut, line):
        real(p, cut, line)
        with open(p, "r+b") as fh:
            fh.seek(cut + len(line))
            fh.write(b"\x00")   # the grown byte reads back as zero
        raise _Killed()
    monkeypatch.setattr(recovery, "_apply", newline_lost)
    with pytest.raises(_Killed):
        recover_torn_tail(path, ANCHOR, recovered_by="supervisor:A", reason="r", acknowledged_risks=("unanchored",))
    monkeypatch.undo()
    out = recover_torn_tail(path, ANCHOR, recovered_by="supervisor:B", reason="r2", acknowledged_risks=("unanchored",))
    assert out["resumed"] and len(_events(path)) == 1
    sidecar = json.loads(_bytes(glob.glob(path + ".torn-*.json")[0]))
    assert sidecar["plan"]["applied"] and sidecar["plan"]["completions"][0]["completed_by"] == "supervisor:B"


def test_a_short_write_is_completed_and_never_terminates_a_damaged_event(tmp_path, monkeypatch):
    """Round 3 (fix-space:0, adv-protocol:2): os.pwrite may write fewer bytes than asked."""
    path, _ = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    real = os.pwrite
    monkeypatch.setattr(recovery.os, "pwrite", lambda fd, data, off: real(fd, bytes(data)[: max(1, len(data) // 3)], off))
    out = _recover(path)
    monkeypatch.undo()
    assert out["torn"] and len(_events(path)) == 1


def test_an_event_that_reads_back_wrong_is_never_terminated_and_the_retry_completes_it(tmp_path, monkeypatch):
    path, _ = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    real = os.pread
    calls = {"n": 0}

    def flaky(fd, n, off):
        calls["n"] += 1
        data = real(fd, n, off)
        return data[:-1] + b"#" if calls["n"] == 1 else data
    monkeypatch.setattr(recovery.os, "pread", flaky)
    with pytest.raises(RecoveryInterrupted):
        _recover(path)
    monkeypatch.undo()
    with pytest.raises(ValueError):
        EvidenceLedger(ANCHOR, path=path)
    assert _recover(path)["resumed"] and len(_events(path)) == 1


def test_a_recovery_event_whose_plan_is_missing_is_refused_not_quarantined_as_a_record(tmp_path, monkeypatch):
    path, _ = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    real = recovery._apply

    def without_newline(p, cut, line):
        fd = os.open(p, os.O_RDWR)
        try:
            os.pwrite(fd, line, cut)
            os.ftruncate(fd, cut + len(line))
        finally:
            os.close(fd)
        raise _Killed()
    monkeypatch.setattr(recovery, "_apply", without_newline)
    with pytest.raises(_Killed):
        _recover(path)
    monkeypatch.undo()
    for sidecar in glob.glob(path + ".torn-*.json"):
        os.unlink(sidecar)   # the plan is lost
    data = _bytes(path)
    with pytest.raises(RecoveryRefused, match="plan is missing"):
        _recover(path, acknowledged_risks=RISKS)
    assert _bytes(path) == data


def test_a_recovery_cut_off_after_its_event_still_reaches_the_next_caller(tmp_path):
    """Round 3 (adv-protocol:3): the stop warning is not lost if the first caller never sees its return value."""
    path, _ = _ledger(tmp_path)
    _tear_a_seal(path)
    _recover(path, acknowledged_risks=("unanchored", "stop_record"))
    out = _recover(path)
    assert out["torn"] is False and "re-issue it" in out["last_recovery"]["stop_warning"]


@pytest.mark.parametrize("kind", ["foreign_field_first", "reordered", "list_payload", "compact_separators",
                                  "not_a_time"])
def test_a_tail_out_of_the_writers_template_is_refused_before_its_hash_is_visible(tmp_path, kind):
    """Round 3 (fix-classifier:0): the header and the fields before prev_hash are checked as far as they go."""
    path, _ = _ledger(tmp_path)
    obj, _ = _serialized_next(path)
    if kind == "foreign_field_first":
        text = '{"seq": %d, "extra": 1, "ts_utc": "%s"' % (obj["seq"], obj["ts_utc"])
    elif kind == "reordered":
        text = '{"seq": %d, "ts_utc": "%s", "payload": {"a": 1}' % (obj["seq"], obj["ts_utc"])
    elif kind == "list_payload":
        text = json.dumps({**obj, "payload": [1]})
        text = text[: text.index(', "hash"') + 20]
    elif kind == "compact_separators":
        text = json.dumps({**obj, "payload": {"a": 1}}, separators=(",", ":"))
        text = '{"seq": %d, "ts_utc": "%s", "record_type": "x", "payload": {"a":1}, "prev_hash": "' % (
            obj["seq"], obj["ts_utc"])
    else:
        text = '{"seq": %d, "ts_utc": "yesterday' % obj["seq"]
    with open(path, "ab") as fh:
        fh.write(text.encode("ascii"))
    data = _bytes(path)
    with pytest.raises(RecoveryRefused):
        _recover(path, acknowledged_risks=RISKS)
    assert _bytes(path) == data


def test_hash_digits_that_match_no_record_of_this_chain_demand_complete_record(tmp_path):
    """Round 3 (fix-classifier:0): a payload byte flipped in an acknowledged record cut inside its hash."""
    path = str(tmp_path / "ledger.jsonl")
    ledger = EvidenceLedger(ANCHOR, path=path)
    ledger.append("event", {"type": "probe"})
    checkpoint = ledger.head
    ledger.append("grant_dispatch", {"proposal_id": "P", "grant_id": "G"})
    ledger.close()
    data = _bytes(path)
    body, line = data[:-1].rsplit(b"\n", 1)
    line = line.replace(b'"grant_id": "G"', b'"grant_id": "F"')   # damage
    cut = line.index(b'"hash": "') + len(b'"hash": "sha256:') + 20
    _write(path, body + b"\n" + line[:cut])
    with pytest.raises(RecoveryRefused, match="complete_record"):
        _recover(path, expected_head=checkpoint)
    q = _recover(path, expected_head=checkpoint, acknowledged_risks=("complete_record",))["quarantined"]
    assert q["classification"] == "partial_unverified"


def test_every_event_type_the_code_writes_is_classified_as_a_stop_or_not():
    """A new stop written as an event cannot fall outside the stop rule unnoticed (round 3, fix-stops:1)."""
    import pathlib
    import re as _re
    root = pathlib.Path(__file__).resolve().parents[2]
    found = set()
    for source in root.rglob("*.py"):
        rel = source.relative_to(root).parts
        if rel[0] in ("tests", ".venv", "venv") or "sandbox" in rel:
            continue
        text = source.read_text(errors="ignore")
        if 'append("event"' not in text and "append('event'" not in text:
            continue
        found |= set(_re.findall(r'"type": "([a-z_]+\.[a-z_]+)"', text))
        found |= set(_re.findall(r'(?:_record|_log|_emit|_event)\("([a-z_]+\.[a-z_]+)"', text))
        found |= set(_re.findall(r'event_type ?=+ ?"([a-z_]+\.[a-z_]+)"', text))
    families = {"action": ("proposed", "evaluating", "pending_human", "granted", "executing", "committed", "recorded",
                           "refused", "failed", "reconciled", "revoked"),
                "autonomy": ("issued", "promoted", "promotion_refused", "regressed", "renewed")}
    found |= {f"{f}.{k}" for f, kinds in families.items() for k in kinds}
    classified = recovery.STOP_EVENT_TYPES | recovery.NON_STOP_EVENT_TYPES
    assert found and found <= classified, sorted(found - classified)


def test_a_damaged_delimiter_cannot_hide_a_complete_record(tmp_path):
    """Round 3 (adv-semantics:1): one flipped byte in ', "prev_hash": ' must not turn a complete, acknowledged record
    into a 'partial' one that a stale checkpoint drops with no risk named."""
    path = str(tmp_path / "ledger.jsonl")
    ledger = EvidenceLedger(ANCHOR, path=path)
    ledger.append("event", {"type": "probe"})
    checkpoint = ledger.head
    ledger.append("grant_dispatch", {"proposal_id": "P", "grant_id": "G"})
    ledger.close()
    data = _bytes(path)
    body, line = data[:-1].rsplit(b"\n", 1)
    line = line.replace(b', "prev_hash": ', b', "prev_hash"; ')[:-1]   # the closing brace is lost too
    _write(path, body + b"\n" + line)
    damaged = _bytes(path)
    for kwargs in ({"expected_head": checkpoint}, {"expected_head": checkpoint, "acknowledged_risks": RISKS}):
        with pytest.raises(RecoveryRefused):
            _recover(path, **kwargs)
    assert _bytes(path) == damaged


def test_a_closed_payload_is_checked_before_prev_hash_is_visible(tmp_path):
    """Replay of round 3: compact separators inside a payload that has closed, with prev_hash not yet written."""
    path, _ = _ledger(tmp_path)
    obj, _ = _serialized_next(path)
    text = '{"seq": %d, "ts_utc": "%s", "record_type": "grant_dispatch", "payload": {"proposal_id":"P"}' % (
        obj["seq"], obj["ts_utc"])
    with open(path, "ab") as fh:
        fh.write(text.encode("ascii"))
    data = _bytes(path)
    with pytest.raises(RecoveryRefused):
        _recover(path, acknowledged_risks=RISKS)
    assert _bytes(path) == data


def test_an_applied_plan_whose_newline_was_lost_is_completed_not_refused(tmp_path):
    """Replay of round 3 (fix-apply p8): the event line is exactly in place and only its newline reads back as zero."""
    path, _ = _ledger(tmp_path)
    _tear_next(path, lambda line: 30)
    out = _recover(path)
    data = _bytes(path)
    _write(path, data[:-1] + b"\x00")
    again = _recover(path)
    assert again["resumed"] and _bytes(path) == data and len(_events(path)) == 1
    assert again["quarantined"]["quarantine_file"] == out["quarantined"]["quarantine_file"]


def test_a_founder_supersede_writes_its_stop_first(tmp_path):
    """Round 3 (fix-stops:0): a crash between supersede's two appends leaves the old goal stopped, never live, and a
    tear of its first append is a stop that needs stop_record."""
    from egregore.goals import GoalRegistry
    from tests.unit.test_goal_gravity import robotics_goal
    from tests.unit.test_goal_gravity_seams import variant
    path = str(tmp_path / "ledger.jsonl")
    ledger = EvidenceLedger(ANCHOR, path=path)
    registry = GoalRegistry(ledger=ledger)
    old_id = registry.authorize(robotics_goal(), now="2026-11-21T00:00:00Z")
    head = ledger.head
    replacement = variant(robotics_goal(second_node=False), supersedes=old_id, desired_state="an inspection-drone plan")
    order = []
    real = ledger.append
    ledger.append = lambda record_type, payload, **kw: (order.append(record_type), real(record_type, payload, **kw))[1]
    registry.supersede(old_id, replacement, actor="alfonso_lopez", reason="narrowed", now="2026-11-21T01:00:00Z")
    ledger.append = real
    ledger.close()
    assert order[:2] == ["egregore.goal_transition", "egregore.goal_authorized"]
    data = _bytes(path)
    lines = data.split(b"\n")
    first = next(i for i, l in enumerate(lines) if b'"superseded by' in l)
    _write(path, b"\n".join(lines[:first]) + b"\n" + lines[first][: len(lines[first]) - 3])   # torn: the stop
    with pytest.raises(RecoveryRefused, match="stop_record"):
        _recover(path, expected_head=head, acknowledged_risks=("complete_record",))
