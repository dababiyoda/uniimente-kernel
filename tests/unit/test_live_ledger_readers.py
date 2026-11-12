"""Product readers of a ledger another process is appending to leave out the line still being written.

The writer appends each record line with one write(), but the kernel grows the file a page at a time while it copies
that write, so a reader that takes the size and reads up to it can find the file ending at a 4096-byte boundary
inside the line (measured for #313: every torn observation ended on a page boundary). That line was never
acknowledged. With the ledger's default tail policy ``refuse`` such a reader raised ``ValueError('partial or blank
history record')``: on ``greg serve`` the phone got no HTTP response at all; the local proof host's stop check
crashed its worker or recorded a host failure; a morning review or a research report failed.

Every file state below is one such a reader finds: complete history written by the real ledger writer, then that
writer's next line up to the first page boundary inside it; then the whole line once the kernel has copied the
rest. Floors kept: a complete line that is not a record is still refused, and a line torn by a crash (it never
completes) is still detected and reported.
"""
from __future__ import annotations

from datetime import datetime, timezone
import http.client
import json
import os
from pathlib import Path
import shutil
import threading

import pytest

from events.spine import EventSpine
from greg import remote
from greg.body import Body
from greg.founder import sign_read
from greg.journal import Journal
from provenance.ledger import EvidenceLedger, ReconciliationRequired
from tests.greg_fixtures import make_body

PAGE = 4096
BODY = "spiffe://uniimente.internal/greg/body"


def _cut_inside_next_line(path: Path, append) -> tuple[bytes, int, int]:
    """Run ``append`` (it writes one line longer than a page), then leave the file as a reader finds it while that
    write is being copied: (the whole file, where the line starts, the first page boundary inside it)."""
    start = path.stat().st_size
    append()
    whole = path.read_bytes()
    boundary = (start // PAGE + 1) * PAGE
    assert start < boundary < len(whole) and whole.endswith(b"\n")
    os.truncate(path, boundary)
    return whole, start, boundary


def _finish(path: Path, whole: bytes, boundary: int) -> None:
    with open(path, "ab") as fh:                    # the kernel copies the rest of the writer's line
        fh.write(whole[boundary:])


def _malformed_tail(path: Path) -> None:
    data = path.read_bytes()
    path.write_bytes(data[:data.rfind(b"\n") + 1] + b"not a record\n")


# --------------------------------------------------------------------------------------------- greg serve (remote)
def _body_accepting_a_command(tmp_path):
    """A body whose ledger ends inside the ``command.accepted`` line the body is writing."""
    home, key, body_id, _ = make_body(tmp_path)
    path = home / "ledger.jsonl"
    constitution = json.loads((home / "body.json").read_text())["constitution_hash"]

    def append():
        writer = EvidenceLedger(constitution, str(path))
        try:
            Journal(EventSpine(writer), actor=BODY).record("command.accepted", {
                "kind": "BODY_PAUSE", "nonce": "n" * 32, "signer": "founder", "channel": "inbox",
                "note": "y" * 6000})                # a receipt-sized line, crossing a page
        finally:
            writer.close()

    whole, start, boundary = _cut_inside_next_line(path, append)
    return home, key, body_id, whole, start, boundary


def _read(home, key, body_id, route):
    now = datetime.now(timezone.utc)
    code, _, payload = remote.handle(home, "GET", route, sign_read(key, body_id=body_id, method="GET", path=route,
                                                                   now=now), b"", now=now)
    return code, json.loads(payload)


def test_remote_reads_answer_while_the_body_writes_a_line_and_show_it_on_the_next_read(tmp_path):
    home, key, body_id, whole, _, boundary = _body_accepting_a_command(tmp_path)
    path = home / "ledger.jsonl"
    seen = path.read_bytes()

    for route in ("/api/status", "/api/decisions", "/api/vepmc"):
        assert _read(home, key, body_id, route)[0] == 200    # was: ValueError('partial or blank history record')
    code, data = _read(home, key, body_id, "/api/commands")
    assert code == 200 and data["principal"] == "founder" and data["recent"] == []   # not yet: never acknowledged
    assert path.read_bytes() == seen                         # a reader never touches the file

    _finish(path, whole, boundary)
    code, data = _read(home, key, body_id, "/api/commands")  # each request reads again: now it is there
    assert code == 200 and [c["nonce"] for c in data["recent"]] == ["n" * 32]


def test_remote_command_pre_verification_answers_while_the_body_writes_a_line(tmp_path):
    from greg.founder import sign_command
    home, key, body_id, *_ = _body_accepting_a_command(tmp_path)
    envelope = sign_command(key, "BODY_PAUSE", {}, body_id=body_id)
    code, _, payload = remote.handle(home, "POST", "/api/command", {}, json.dumps(envelope).encode())
    assert code == 202 and json.loads(payload)["signer"] == "founder"


def test_remote_refuses_a_malformed_complete_line_with_503_and_no_internals(tmp_path):
    home, key, body_id, *_ = _body_accepting_a_command(tmp_path)
    _malformed_tail(home / "ledger.jsonl")
    now = datetime.now(timezone.utc)
    for route in ("/api/status", "/api/commands"):
        with pytest.raises(remote.RemoteError) as refused:
            remote.handle(home, "GET", route, sign_read(key, body_id=body_id, method="GET", path=route, now=now),
                          b"", now=now)
        assert refused.value.status == 503 and str(refused.value) == remote.UNREADABLE
        assert str(home) not in str(refused.value)
    with pytest.raises(remote.RemoteError) as refused:
        remote.handle(home, "POST", "/api/command", {}, b"{}")
    assert refused.value.status == 503


def test_a_crash_torn_line_is_served_around_and_still_quarantined_by_the_body(tmp_path):
    """The body died mid-write, so the line never completes. The phone still reads the acknowledged history (the
    reason to look at it), the reader leaves the bytes alone, and the body's next start detects them, keeps them in a
    sidecar and records the recovery."""
    home, key, body_id, whole, start, boundary = _body_accepting_a_command(tmp_path)
    path = home / "ledger.jsonl"
    torn = path.read_bytes()[start:]
    assert _read(home, key, body_id, "/api/commands") == (200, {"principal": "founder", "recent": [], "rejected": []})
    assert path.read_bytes()[start:] == torn
    with Body(home) as body:
        tail = body.ledger.unacknowledged_tail
        assert tail["offset"] == start and tail["bytes"] == boundary - start
        assert Path(tail["sidecar"]).read_bytes() == torn
        assert [r.payload["kind"] for r in body.ledger.by_type("recovery")] == ["unacknowledged_tail_quarantined"]
    assert _read(home, key, body_id, "/api/status")[0] == 200


def test_a_reader_that_fails_after_opening_the_ledger_closes_it(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    opened = []

    class Tracked(EvidenceLedger):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            opened.append(self)

    def failing(journal):
        raise RuntimeError("history projection failed")
    monkeypatch.setattr(remote, "EvidenceLedger", Tracked)
    monkeypatch.setattr(remote, "consumed_nonces", failing)
    with pytest.raises(RuntimeError):
        _read(home, key, body_id, "/api/status")
    assert len(opened) == 1 and opened[0]._closed


@pytest.fixture
def server(tmp_path):
    started = []

    def start(home):
        srv = remote.make_server(home, port=0)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        started.append((srv, thread))
        return srv.server_address[1]

    yield start
    for srv, thread in started:
        srv.shutdown()
        srv.server_close()
        thread.join(5)


def _http(port, method, route, headers=None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.putrequest(method, route)
        for k, v in (headers or {}).items():
            conn.putheader(k, v)
        conn.endheaders(body)
        response = conn.getresponse()
        return response.status, json.loads(response.read())
    finally:
        conn.close()


def test_the_real_http_server_answers_every_request_while_the_body_writes(tmp_path, server):
    home, key, body_id, whole, _, boundary = _body_accepting_a_command(tmp_path)
    port = server(home)
    signed = lambda route: sign_read(key, body_id=body_id, method="GET", path=route)
    status, data = _http(port, "GET", "/api/commands", signed("/api/commands"))   # was: no response at all
    assert status == 200 and data["recent"] == []
    _finish(home / "ledger.jsonl", whole, boundary)
    status, data = _http(port, "GET", "/api/commands", signed("/api/commands"))
    assert status == 200 and len(data["recent"]) == 1
    _malformed_tail(home / "ledger.jsonl")
    assert _http(port, "GET", "/api/status", signed("/api/status")) == (503, {"error": remote.UNREADABLE})


def test_the_real_http_server_never_drops_a_request_or_leaks_an_unexpected_error(tmp_path, server, monkeypatch,
                                                                                capsys):
    home, *_ = make_body(tmp_path)
    port = server(home)
    for length in ("abc", "-5"):                    # was: a dropped connection, and for -5 a read until EOF
        assert _http(port, "POST", "/api/command", {"Content-Length": length}) == (
            400, {"error": "invalid Content-Length"})

    def broken(*args, **kwargs):
        raise KeyError(f"{home}/secrets/private-detail")
    monkeypatch.setattr(remote, "handle", broken)
    status, data = _http(port, "GET", "/api/status")
    assert status == 500 and data == {"error": "internal error; see the greg serve log on the body's computer"}
    err = capsys.readouterr().err
    assert "KeyError answering GET /api/status" in err and "private-detail" not in err


# ---------------------------------------------------------------------------- local proof host: the stop control
from egregore.local_mission import retained_stop  # noqa: E402

C = "sha256:" + "cd" * 32


def _control(tmp_path, *, stopped=False):
    path = tmp_path / "control.jsonl"
    writer = EvidenceLedger(C, str(path))
    writer.append("egregore.signal_ingested", {"signal": {"signal_id": "s-1"}})
    if stopped:
        writer.append("egregore.suspended", {"actor": "operator", "reason": "stop", "previously_suspended": False})
    writer.close()
    return path, {"control_ledger": str(path)}


def _appending(path, record_type, payload):
    def append():
        writer = EvidenceLedger(C, str(path))
        try:
            writer.append(record_type, {**payload, "note": "y" * 6000})
        finally:
            writer.close()
    return append


def _kernel_finishes_later(path, whole, boundary, delay=0.05):
    timer = threading.Timer(delay, _finish, (path, whole, boundary))
    timer.start()
    return timer


def test_a_stop_still_being_written_stops_the_mission(tmp_path):
    """The decision must not be 'no stop': the unacknowledged line may be the stop. Read past it alone and the
    mission dispatches while the operator's stop is in flight."""
    path, job = _control(tmp_path)
    whole, _, boundary = _cut_inside_next_line(path, _appending(
        path, "egregore.suspended", {"actor": "operator", "reason": "stop", "previously_suspended": False}))
    timer = _kernel_finishes_later(path, whole, boundary)
    try:
        assert retained_stop(job, C) is True        # was: ValueError; tail="ignore" alone answers False
    finally:
        timer.join()


def test_another_line_still_being_written_is_waited_out_and_is_no_stop(tmp_path):
    path, job = _control(tmp_path)
    whole, _, boundary = _cut_inside_next_line(path, _appending(
        path, "egregore.signal_ingested", {"signal": {"signal_id": "s-2"}}))
    timer = _kernel_finishes_later(path, whole, boundary)
    try:
        assert retained_stop(job, C) is False       # was: ValueError('partial or blank history record')
    finally:
        timer.join()


def test_an_acknowledged_stop_decides_without_waiting_for_a_later_line(tmp_path):
    path, job = _control(tmp_path, stopped=True)
    _cut_inside_next_line(path, _appending(path, "egregore.signal_ingested", {"signal": {"signal_id": "s-2"}}))
    assert retained_stop(job, C) is True             # waiting would end in ReconciliationRequired: it never ends


def test_a_control_line_that_never_completes_is_reported_not_read_as_no_stop(tmp_path):
    """A crash (or a stalled writer) left the line torn: whether it stops the mission is unknown, so nothing
    proceeds and the reason names it."""
    path, job = _control(tmp_path)
    _, start, boundary = _cut_inside_next_line(path, _appending(
        path, "egregore.signal_ingested", {"signal": {"signal_id": "s-2"}}))
    with pytest.raises(ReconciliationRequired, match=f"ends with {boundary - start} bytes of a line that was never "
                                                     "completed"):
        retained_stop(job, C)


def test_a_malformed_complete_control_line_is_still_refused(tmp_path):
    path, job = _control(tmp_path)
    _malformed_tail(path)
    with pytest.raises(ValueError, match="malformed"):
        retained_stop(job, C)


# ------------------------------------------------------------------------------------------------ morning review
from egregore.morning_review import append_note, review  # noqa: E402

SOURCE = Path(__file__).parents[1] / "evidence/greg-proof/adopted-repositories/ledger.jsonl"


def _history_with_a_note_being_written(tmp_path):
    path = tmp_path / "history.jsonl"
    shutil.copyfile(SOURCE, path)
    records = [json.loads(line) for line in path.read_text().splitlines()]
    anchor, head = records[0]["payload"]["constitution_hash"], records[-1]["hash"]
    mission = records[1]["payload"]["payload"]["mission_id"]
    note = dict(note_id="long-note", mission_id=mission, review_head=head, kind="preference", text="x" * 4096,
                evidence_refs=[])                    # the longest note a writer takes: its line crosses a page
    whole, start, boundary = _cut_inside_next_line(path, lambda: append_note(path, anchor, note))
    note_hash = json.loads(whole[start:].decode())["hash"]
    return path, anchor, mission, head, note_hash, whole, boundary


def test_a_morning_review_reads_while_a_note_is_being_written(tmp_path):
    path, anchor, mission, head, note_hash, whole, boundary = _history_with_a_note_being_written(tmp_path)
    seen = path.read_bytes()
    report = review(path, anchor, mission, head)    # was: ValueError('partial or blank history record')
    assert report["status"] == "RETAINED_AUDIT_COMPLETE" and report["review_notes"] == []
    assert path.read_bytes() == seen
    with pytest.raises(ValueError, match="never completed .* retry the review"):
        review(path, anchor, mission, note_hash)    # the head names the line still being written: not yet
    _finish(path, whole, boundary)
    assert [n["note"]["note_id"] for n in review(path, anchor, mission, note_hash)["review_notes"]] == ["long-note"]


def test_a_crash_torn_note_is_still_refused_by_the_writer_and_a_malformed_line_by_the_reader(tmp_path):
    path, anchor, mission, head, *_ = _history_with_a_note_being_written(tmp_path)
    another = dict(note_id="another", mission_id=mission, review_head=head, kind="preference", text="y",
                   evidence_refs=[])
    with pytest.raises(ValueError, match="partial"):
        append_note(path, anchor, another)          # the writer holds the lock: a torn line is a crash's
    _malformed_tail(path)
    with pytest.raises(ValueError, match="malformed"):
        review(path, anchor, mission, head)


# ----------------------------------------------------------------------------------------------- research report
def _research_ledger_being_written(tmp_path):
    path = tmp_path / "research.jsonl"
    writer = EvidenceLedger(C, str(path))
    writer.append("workflow", {"workflow_id": "w-1", "status": "running", "state": {}})
    writer.close()

    def append():
        w = EvidenceLedger(C, str(path))
        try:
            w.append("workflow", {"workflow_id": "w-1", "status": "completed", "state": {"note": "y" * 6000}})
        finally:
            w.close()
    whole, start, boundary = _cut_inside_next_line(path, append)
    return path, whole, start, boundary


def test_the_research_report_leaves_out_and_names_a_checkpoint_still_being_written(tmp_path, monkeypatch, capsys):
    from foundry import research_report
    path, whole, start, boundary = _research_ledger_being_written(tmp_path)
    # The DuckDB query is not what is tested (it is optional); what it is handed and what is printed are.
    monkeypatch.setattr(research_report, "report",
                        lambda ledger: {"statuses": [r.payload["status"] for r in ledger.by_type("workflow")]})
    monkeypatch.setattr("sys.argv", ["research_report", "--ledger", str(path), "--anchor", C])
    research_report.main()                          # was: ValueError('partial or blank history record')
    out = json.loads(capsys.readouterr().out)
    assert out["statuses"] == ["running"]
    assert out["unacknowledged_tail"]["offset"] == start and out["unacknowledged_tail"]["bytes"] == boundary - start
    _finish(path, whole, boundary)
    research_report.main()
    assert json.loads(capsys.readouterr().out) == {"statuses": ["running", "completed"]}
    _malformed_tail(path)
    with pytest.raises(ValueError, match="malformed"):
        research_report.main()
