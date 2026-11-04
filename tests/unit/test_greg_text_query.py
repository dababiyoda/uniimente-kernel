"""A question about a file of any size is answered over all of it (directive of 2026-10-22, section VIII: a bounded
verified traversal that produces a compact authenticated result with coverage evidence; claim 6516513997, item 2).

``fs.read`` refuses a file over 256 KiB, and a receipt keeps an output whole only up to 1 MiB of canonical JSON, so a
check on a large log could not be decided: GREG asked the founder. ``fs.search`` (greg/textquery.py) streams the
file in 64 KiB chunks and answers each phrase over every character it read, in one normalization form. It returns a
result of a few hundred bytes that states its coverage: bytes read, their digest, the encoding, and whether it
reached the end. Absence is claimed only over a complete, faithful reading.

In-process Body with a test clock and a per-test founder key, not Alfonso's (SANDBOX).
"""
from __future__ import annotations

import codecs
import json
import tracemalloc
import unicodedata

import pytest

from greg.capabilities import BUILTINS, MAX_READ_BYTES, CapabilityError, InvocationContext, SecretBroker, fs_read
from greg.missions import FALSE, INSUFFICIENT, TRUE, judge
from greg.planner import PlannerContext, template_route
from greg.textquery import CHUNK_BYTES, MAX_OPEN_CHARS, Query, fs_search
import greg.textquery
from greg.missions import validate_mission
from tests.greg_fixtures import Clock, make_body, mission
from tests.unit.test_greg_missions import events, run, submit

LINE = b"2026-10-30T07:00:00Z worker=7 status=ok latency_ms=12 route=/settle\n"
FATAL = "FATAL: ledger corrupt at seq 88123"


def _ctx(tmp_path):
    (tmp_path / "data").mkdir(exist_ok=True)
    return InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path / "data",),
                             secrets=SecretBroker(tmp_path / "secrets.json"), manifest=BUILTINS["fs.search"][0])


def _log(path, megabytes, *, insert=None, at=None):
    """A log of about ``megabytes`` MiB, with ``insert`` written at byte offset ``at`` (or at the end)."""
    body = LINE * (megabytes * 1024 * 1024 // len(LINE))
    if insert is not None:
        at = len(body) if at is None else at
        body = body[:at] + insert + body[at:]
    path.write_bytes(body)
    return path


def p(op, value, field):
    return {"op": op, "field": field, "value": value}


def _search(params, ctx):
    return fs_search(params, ctx)


# -- the question is answered over every byte, in bounded memory ------------------------------------------------------

def test_a_phrase_past_any_receipt_limit_is_found_and_an_absent_one_is_proved_absent(tmp_path):
    ctx = _ctx(tmp_path)
    log = _log(tmp_path / "data" / "app.log", 12, insert=f"\n{FATAL}\n".encode())
    with pytest.raises(CapabilityError, match="file exceeds read ceiling"):
        fs_read({"path": str(log)}, ctx)                                        # before: the only reader refused
    tracemalloc.start()
    try:
        out = _search({"path": str(log), "phrases": [FATAL, "status=error"]}, ctx)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert out["complete"] is True and out["bytes_read"] == out["size"] == log.stat().st_size
    assert [q["found"] for q in out["queries"]] == [True, False]
    assert out["queries"][0]["first_offset"] > 12 * 1024 * 1024 - 100
    assert peak < 2 * 1024 * 1024, peak                                           # a 12 MiB file, read in 64 KiB
    assert len(json.dumps(out)) < 2048                                            # fits any receipt whole
    import hashlib
    assert out["read_sha256"] == hashlib.sha256(log.read_bytes()).hexdigest()    # bound to the exact bytes
    assert judge(p("equals", True, "queries.0.found"), out)[0] == TRUE
    assert judge(p("equals", False, "queries.1.found"), out)[0] == TRUE


@pytest.mark.parametrize("offset", [CHUNK_BYTES - 7, CHUNK_BYTES - 1, CHUNK_BYTES, 3 * CHUNK_BYTES - 20])
def test_a_phrase_across_two_chunks_is_found_once(tmp_path, offset):
    ctx = _ctx(tmp_path)
    log = _log(tmp_path / "data" / "app.log", 1, insert=FATAL.encode(), at=offset)
    out = _search({"path": str(log), "phrases": [FATAL]}, ctx)
    assert out["queries"][0] == {"phrase": FATAL, "found": True, "first_offset": offset, "occurrences": 1}


def test_a_short_phrase_in_the_carried_tail_is_counted_once(tmp_path):
    ctx = _ctx(tmp_path)
    at = CHUNK_BYTES - len(FATAL) - 5                       # the short phrase ends inside the tail carried onward
    log = _log(tmp_path / "data" / "app.log", 1, insert=FATAL.encode(), at=at)
    out = _search({"path": str(log), "phrases": [FATAL, "seq 88123"]}, ctx)
    assert [(q["found"], q["occurrences"]) for q in out["queries"]] == [(True, 1), (True, 1)]


def test_an_accent_in_the_next_chunk_is_part_of_the_letter_before_it(tmp_path):
    ctx = _ctx(tmp_path)
    head = b"x" * (CHUNK_BYTES - 4) + b"cafe"                                     # chunk 1 ends on the bare letter
    (tmp_path / "data" / "menu.txt").write_bytes(head + "́ au lait".encode() + b"y" * 100)
    out = _search({"path": str(tmp_path / "data" / "menu.txt"), "phrases": ["cafe au", "café au"]}, ctx)
    assert [q["found"] for q in out["queries"]] == [False, True]                  # one text, in NFC


def test_line_breaks_inside_a_phrase_count_as_one_space_when_asked(tmp_path):
    ctx = _ctx(tmp_path)
    (tmp_path / "data" / "terms.txt").write_bytes(b"a" * (CHUNK_BYTES - 12) + b" Either party may terminate\n   "
                                                  b"\n without \t notice. " + b"b" * 100)
    params = {"path": str(tmp_path / "data" / "terms.txt"), "phrases": ["terminate  without\nnotice"]}
    assert _search(params, ctx)["queries"][0]["found"] is False                   # exact: different text
    assert _search({**params, "whitespace": "collapse"}, ctx)["queries"][0]["found"] is True


# -- coverage: a reading cut short decides only what more of the file could not undo -----------------------------------

def test_a_reading_stopped_by_its_byte_limit_proves_what_it_found_and_nothing_it_did_not(tmp_path):
    ctx = _ctx(tmp_path)
    log = _log(tmp_path / "data" / "app.log", 3, insert=f"\n{FATAL}\n".encode())
    out = _search({"path": str(log), "phrases": ["latency_ms=12", FATAL], "max_bytes": 1024 * 1024}, ctx)
    assert out["complete"] is False and out["bytes_read"] == 1024 * 1024 and "byte limit" in out["stopped"]
    assert [q["found"] for q in out["queries"]] == [True, None]
    assert judge(p("equals", True, "queries.0.found"), out)[0] == TRUE            # found is found
    verdict, detail = judge(p("equals", False, "queries.1.found"), out)
    assert verdict == INSUFFICIENT and "byte limit" in detail                      # absence is not proved
    assert judge(p("equals", 1024 * 1024, "bytes_read"), out)[0] == TRUE


def test_a_file_exactly_at_the_byte_limit_is_read_whole(tmp_path):
    ctx = _ctx(tmp_path)
    exact = tmp_path / "data" / "exact.log"
    exact.write_bytes(b"z" * (2 * CHUNK_BYTES))
    out = _search({"path": str(exact), "phrases": ["FATAL"], "max_bytes": 2 * CHUNK_BYTES}, ctx)
    assert out["complete"] is True and out["queries"][0]["found"] is False


def test_a_reading_stopped_by_its_time_limit_says_so(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path)
    log = _log(tmp_path / "data" / "app.log", 1)
    ticks = iter(range(0, 10_000, 5))                                             # each look at the clock: 5 s on
    monkeypatch.setattr(greg.textquery.time, "monotonic", lambda: next(ticks))
    out = _search({"path": str(log), "phrases": ["FATAL"], "max_seconds": 12}, ctx)
    assert out["complete"] is False and "time limit" in out["stopped"] and out["queries"][0]["found"] is None
    assert 0 < out["bytes_read"] < log.stat().st_size


# -- faithful reading -------------------------------------------------------------------------------------------------

def test_a_utf16_log_is_read_in_its_own_encoding_or_not_at_all(tmp_path):
    ctx = _ctx(tmp_path)
    text = ("status=ok\n" * 20000 + FATAL + "\n").encode("utf-16-le")
    (tmp_path / "data" / "marked.log").write_bytes(codecs.BOM_UTF16_LE + text)
    out = _search({"path": str(tmp_path / "data" / "marked.log"), "phrases": [FATAL]}, ctx)
    assert out["encoding"] == "utf-16" and out["queries"][0]["found"] is True
    (tmp_path / "data" / "unmarked.log").write_bytes(text)
    out = _search({"path": str(tmp_path / "data" / "unmarked.log"), "phrases": [FATAL, "status"]}, ctx)
    assert "NUL bytes" in out["unreadable"] and [q["found"] for q in out["queries"]] == [None, None]
    verdict, detail = judge(p("equals", False, "queries.0.found"), out)
    assert verdict == INSUFFICIENT and "NUL bytes" in detail                       # never "absent"


def test_a_byte_that_is_not_utf8_midway_leaves_every_answer_open(tmp_path):
    ctx = _ctx(tmp_path)
    log = _log(tmp_path / "data" / "app.log", 1, insert=b"caf\xe9 ", at=CHUNK_BYTES * 5)
    out = _search({"path": str(log), "phrases": ["latency_ms", FATAL]}, ctx)
    assert out["unreadable"].startswith("not valid utf-8 near byte") and out["complete"] is False
    assert [q["found"] for q in out["queries"]] == [None, None]          # an encoding guessed wrong reads nothing


def test_marks_with_no_starter_are_refused_before_memory_grows(tmp_path):
    ctx = _ctx(tmp_path)
    (tmp_path / "data" / "zalgo.txt").write_bytes(b"a" + "́".encode() * (MAX_OPEN_CHARS + CHUNK_BYTES))
    tracemalloc.start()
    try:
        out = _search({"path": str(tmp_path / "data" / "zalgo.txt"), "phrases": ["a"]}, ctx)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert "no normalization boundary" in out["unreadable"] and out["queries"][0]["found"] is None
    assert peak < 4 * 1024 * 1024, peak


def test_a_query_fed_in_any_pieces_answers_the_same():
    text = ("Payé José " + FATAL + " fin. ").encode() * 300
    whole = Query(["José " + FATAL, "absent"])
    whole.feed(text)
    whole.finish()
    for size in (1, 3, 7, 64):
        pieces = Query(["José " + FATAL, "absent"])
        for i in range(0, len(text), size):
            pieces.feed(text[i:i + size])
        pieces.finish()
        assert pieces.result() == whole.result(), size


@pytest.mark.parametrize("params", [{"phrases": []}, {"phrases": [" "]}, {"phrases": ["x"] * 17},
                                    {"phrases": "FATAL"}, {"phrases": ["x"], "whitespace": "fold"},
                                    {"phrases": ["x"], "max_bytes": 0}, {"phrases": ["x"], "max_seconds": 3600}],
                         ids=["none", "blank", "too-many", "not-a-list", "bad-whitespace", "zero-bytes", "too-long"])
def test_a_malformed_question_is_refused(tmp_path, params):
    ctx = _ctx(tmp_path)
    (tmp_path / "data" / "a.txt").write_text("x")
    with pytest.raises(CapabilityError):
        _search({"path": str(tmp_path / "data" / "a.txt"), **params}, ctx)


def test_a_fifo_swapped_in_after_the_file_check_is_refused_without_blocking(tmp_path, monkeypatch):
    import os
    from pathlib import Path
    import threading
    ctx = _ctx(tmp_path)
    os.mkfifo(tmp_path / "data" / "pipe")
    monkeypatch.setattr(Path, "is_file", lambda self: True)            # it was a file when GREG looked
    raised = []
    def search():
        try:
            _search({"path": str(tmp_path / "data" / "pipe"), "phrases": ["x"]}, ctx)
        except CapabilityError as exc:
            raised.append(str(exc))
    reader = threading.Thread(target=search, daemon=True)
    reader.start()
    reader.join(10)
    assert raised == ["pipe is not a regular file"]


def test_a_directory_where_a_file_was_expected_is_a_failed_read_not_an_absent_file(tmp_path):
    """Before: a directory read as ``exists: false``, so "never mentions" on it was a measured failure and the
    founder was asked what to do about the check, not told the sensor could not read (section IX scenario 7)."""
    ctx = _ctx(tmp_path)
    (tmp_path / "data" / "audit.log").mkdir()
    with pytest.raises(CapabilityError, match="audit.log is not a regular file"):
        _search({"path": str(tmp_path / "data" / "audit.log"), "phrases": ["x"]}, ctx)


def test_reads_stay_inside_the_permitted_roots(tmp_path):
    ctx = _ctx(tmp_path)
    (tmp_path / "secret.txt").write_text("founder secret")
    with pytest.raises(CapabilityError, match="outside permitted roots"):
        _search({"path": str(tmp_path / "secret.txt"), "phrases": ["secret"]}, ctx)
    assert _search({"path": str(tmp_path / "data" / "none.txt"), "phrases": ["x"]}, ctx) == {
        "path": str((tmp_path / "data" / "none.txt").resolve()), "exists": False}


# -- on the mission path: the founder's words, the engine, and the separate appraiser ---------------------------------

def _search_check(check_id, path, phrase, *, absent):
    return {"check_id": check_id, "description": f"{path.name} {'never mentions' if absent else 'mentions'} {phrase}",
            "sensor": {"capability": "fs.search", "params": {"path": str(path), "phrases": [phrase]},
                       "target": f"fs:{path.name}"},
            "predicate": {"op": "equals", "field": "queries.0.found", "value": not absent}}


def test_a_large_log_is_proved_clean_and_the_appraiser_agrees(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    log = _log(data / "app.log", 3)
    clean = _search_check("clean", log, FATAL, absent=True)
    submit(home, key, body_id, "MISSION", mission("m:clean-log", checks=[clean], strategies=[],
                                                  capabilities=["fs.search"], ceiling="read_only"))
    missions, requests = run(home, Clock(), ticks=4)
    assert missions["m:clean-log"].status == "ACHIEVED"                           # before: fs.read refused, an ask
    assert not [r for r in requests if r.get("mission_id") == "m:clean-log"]
    appraised = [e for e in events(home, "mission.appraised") if e["mission_id"] == "m:clean-log"]
    assert appraised and appraised[-1]["verdict"] == "VERIFIED"
    with log.open("ab") as stream:                                                # the world changes afterwards
        stream.write(f"\n{FATAL}\n".encode())
    from greg.body import Body
    with Body(home) as body:
        verdict = body.appraise("m:clean-log")                                    # the appraiser reads it again
    assert verdict["checks"]["world_reobserved"] is False
    assert any("world no longer matches" in f for f in verdict["findings"])


def test_a_fault_deep_in_a_large_log_keeps_the_mission_open(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    log = _log(data / "app.log", 3, insert=f"\n{FATAL}\n".encode(), at=2 * 1024 * 1024 + 17)
    clean = _search_check("clean", log, FATAL, absent=True)
    submit(home, key, body_id, "MISSION", mission("m:clean-log", checks=[clean], strategies=[],
                                                  capabilities=["fs.search"], ceiling="read_only"))
    missions, requests = run(home, Clock(), ticks=4, step=600.0)
    assert missions["m:clean-log"].status != "ACHIEVED"
    observed = [e for e in events(home, "mission.observed") if e["mission_id"] == "m:clean-log"]
    assert observed and all(not e["passed"] and "insufficient evidence" not in e["detail"] for e in observed)
    assert [r.get("kind") for r in requests if r.get("mission_id") == "m:clean-log"] == ["NO_STRATEGY"]


def test_the_founders_words_become_a_read_only_search_mission(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "app.log").write_text("ok\n")
    ctx = PlannerContext(read_roots=(str(data),), capabilities=[], workspace=tmp_path / "ws")
    proposal = template_route(f'Check that {data / "app.log"} never mentions "FATAL" or "ledger corrupt"', ctx)
    assert proposal["status"] == "PROPOSED" and proposal["origin"] == "template:file-search"
    spec = validate_mission(proposal["spec"])
    assert spec["light_cone"]["capabilities"] == ["fs.search"] and spec["light_cone"]["max_consequence_class"] == \
        "read_only" and spec["strategies"] == []
    assert [c["predicate"] for c in spec["success_checks"]] == [
        {"op": "equals", "field": "queries.0.found", "value": False},
        {"op": "equals", "field": "queries.1.found", "value": False}]
    found = template_route(f'Does {data / "app.log"} mention "ok"?', ctx)
    assert found["spec"]["success_checks"][0]["predicate"]["value"] is True
    unrelated = template_route(f'Note "buy milk" in {data / "todo.txt"}', ctx)
    assert unrelated["origin"] == "template:workspace-note"                       # other routes keep their words


@pytest.mark.parametrize("words, phrases, present", [
    ('Check that {f} mentions "connection not established"', ["connection not established"], [True]),
    ("Check that {f} doesn't mention \"FATAL\"", ["FATAL"], [False]),
    ("Check that {f} doesn’t mention ‘FATAL’", ["FATAL"], [False]),
    ("Check that {f} mentions 'don't panic'", ["don't panic"], [True]),
    ("Check that the server's log {f} mentions \"OK\"", ["OK"], [True]),
    ('Check that {f} contains none of "FATAL", "panic"', ["FATAL", "panic"], [False, False]),
    ('"FATAL" is not mentioned in {f}', ["FATAL"], [False]),
])
def test_only_words_outside_the_quotes_say_whether_a_phrase_must_appear(tmp_path, words, phrases, present):
    """The review of #229 (blocking): polarity was read over the whole request, quoted phrase included, so "mentions
    "connection not established"" drafted a check that the file never mentions it, and the apostrophe in "doesn't"
    opened a quote, so the phrase searched for was "t mention "."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "app.log").write_text("ok\n")
    ctx = PlannerContext(read_roots=(str(tmp_path / "data"),), capabilities=[], workspace=tmp_path / "ws")
    proposal = template_route(words.format(f=tmp_path / "data" / "app.log"), ctx)
    assert proposal["status"] == "PROPOSED" and proposal["origin"] == "template:file-search"
    checks = validate_mission(proposal["spec"])["success_checks"]
    assert checks[0]["sensor"]["params"]["phrases"] == phrases
    assert [c["predicate"]["value"] for c in checks] == present


@pytest.mark.parametrize("words, unclear", [
    ('Check that {f} mentions "OK", not just "WARN"', "'not', 'just'"),
    ('Check that {f} mentions "OK" but never mentions "FATAL"', "the request says both"),
])
def test_words_that_leave_the_polarity_open_are_asked_not_guessed(tmp_path, words, unclear):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "app.log").write_text("ok\n")
    ctx = PlannerContext(read_roots=(str(tmp_path / "data"),), capabilities=[], workspace=tmp_path / "ws")
    asked = template_route(words.format(f=tmp_path / "data" / "app.log"), ctx)
    assert asked["status"] == "NEEDS_INPUT" and asked["origin"] == "template:file-search" and "spec" not in asked
    assert unclear in asked["questions"][0] and "never mention them?" in asked["questions"][0]


def test_an_apostrophe_inside_a_note_keeps_the_whole_note(tmp_path):
    """The same defect in the planner's note route: "don't" cut the note to "don"."""
    ctx = PlannerContext(read_roots=(str(tmp_path),), capabilities=[], workspace=tmp_path / "ws")
    note = template_route(f'Note "don\'t forget the invoice" in {tmp_path / "todo.txt"}', ctx)
    assert note["origin"] == "template:workspace-note"
    assert note["spec"]["success_checks"][0]["predicate"]["value"] == "don't"
    assert "don't forget the invoice" in json.dumps(note["spec"]["strategies"])


def test_a_phrase_with_not_in_it_closes_only_on_a_file_that_mentions_it(tmp_path):
    """The same review's consequence: an inverted check certified a file that lacks the phrase."""
    for name, text, closes in (("lacks.log", "connection established\n", False),
                               ("has.log", "warn: connection not established\n", True)):
        root = tmp_path / name.split(".")[0]
        root.mkdir()
        home, key, body_id, data = make_body(root)
        (data / name).write_text(text)
        ctx = PlannerContext(read_roots=(str(data),), capabilities=[], workspace=root / "ws")
        spec = template_route(f'Check that {data / name} mentions "connection not established"', ctx)["spec"]
        submit(home, key, body_id, "MISSION", spec)
        missions, _ = run(home, Clock(), ticks=4, step=600.0)
        assert (missions[spec["mission_id"]].status == "ACHIEVED") is closes


def test_a_utf8_mark_before_utf16_bytes_is_refused_like_unmarked_utf8(tmp_path):
    """The review of #228 (finding 4), applied to the query's own decoder: its NUL guard tested the codec name
    "utf-8", and a UTF-8 byte-order mark reads as "utf-8-sig"."""
    ctx = _ctx(tmp_path)
    (tmp_path / "data" / "odd.log").write_bytes(codecs.BOM_UTF8 + ("status=ok\n" + FATAL).encode("utf-16-le"))
    out = _search({"path": str(tmp_path / "data" / "odd.log"), "phrases": [FATAL, "status"]}, ctx)
    assert "NUL bytes" in out["unreadable"] and [q["found"] for q in out["queries"]] == [None, None]


def test_a_link_swapped_in_after_the_path_was_checked_is_not_followed(tmp_path, monkeypatch):
    from pathlib import Path
    import greg.textquery
    ctx = _ctx(tmp_path)
    secret = tmp_path / "outside.log"
    secret.write_text(FATAL)
    (tmp_path / "data" / "app.log").symlink_to(secret)
    monkeypatch.setattr(greg.textquery, "_inside", lambda path, roots: Path(path))   # checked before the swap
    with pytest.raises(CapabilityError, match="became a link"):
        _search({"path": str(tmp_path / "data" / "app.log"), "phrases": [FATAL]}, ctx)


# -- a PDF is not text: its bytes are page syntax, not the words a reader shows ----------------------------------------
# The planner sent a question about a PDF to fs.search, which read the file's bytes (scout of #229, direction A). In
# an uncompressed PDF a line is one text operator: a phrase over two lines is not in the bytes, and an operator or
# font name is. Before: "never mentions" closed ACHIEVED on a PDF whose reader shows the phrase, and "mentions" on a
# name only the page syntax holds.

LEASE = ["The renewal term is twelve months", "with notice due net thirty."]
SHOWN = "twelve months with notice"            # what pdftotext reads (two lines); not in the bytes
SYNTAX = "BaseFont /Helvetica"                 # in the bytes; not in the text a reader shows


def _pdf(lines, *, junk=b""):
    """An uncompressed one-page PDF that draws ``lines`` in Helvetica, all ASCII (no binary comment line, which the
    format leaves optional), with ``junk`` before its header (readers look for the header in the first 1024 bytes)."""
    ops = ["BT", "/F1 12 Tf", "16 TL", "72 720 Td"] + [f"({line}) Tj\nT*" for line in lines] + ["ET"]
    stream = "\n".join(ops).encode("latin-1")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> "
               b"/Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
               b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return junk + bytes(out)


# a header at byte 0, after junk, and starting at byte 1019: its last byte is byte 1023, the last a reader looks at
JUNK = {"at-0": b"", "after-junk": b"HTTP/1.1 200 OK\r\n" * 30, "last-start": b"J" * 1018 + b"\n"}


@pytest.mark.parametrize("junk", list(JUNK.values()), ids=list(JUNK))
def test_a_pdf_is_never_answered_from_its_bytes(tmp_path, junk):
    ctx = _ctx(tmp_path)
    pdf = tmp_path / "data" / "lease.pdf"
    pdf.write_bytes(_pdf(LEASE, junk=junk))
    assert SHOWN not in " ".join(pdf.read_bytes().decode("ascii").split()) and SYNTAX.encode() in pdf.read_bytes()
    out = _search({"path": str(pdf), "phrases": [SHOWN, SYNTAX], "whitespace": "collapse"}, ctx)
    # before: [False, True], complete: the reader's phrase "absent" and a font name "mentioned"
    assert [q["found"] for q in out["queries"]] == [None, None] and out["complete"] is False
    assert out["unreadable"] == ("a PDF: its text is drawn by page operators, not stored as text; read it with "
                                 "document.text")
    for value, field in ((False, "queries.0.found"), (True, "queries.1.found")):
        verdict, detail = judge(p("equals", value, field), out)
        assert verdict == INSUFFICIENT and "a PDF" in detail
    data = pdf.read_bytes()
    for size in (1, 7, 1000):                                                     # the header split over pieces
        pieces = Query([SHOWN, SYNTAX], whitespace="collapse")
        for i in range(0, len(data), size):
            pieces.feed(data[i:i + size])
        pieces.finish()
        got = pieces.result()        # it stops reading at the header, so bytes_read depends on where pieces end
        assert [q["found"] for q in got["queries"]] == [None, None] and got["unreadable"] == out["unreadable"], size


@pytest.mark.parametrize("at", [1020, 5000, CHUNK_BYTES + 3])
def test_a_text_that_quotes_a_pdf_header_past_where_readers_look_is_read_as_text(tmp_path, at):
    """A log that records "%PDF-1.7" is not a PDF unless the header is where a reader looks for it."""
    ctx = _ctx(tmp_path)
    log = tmp_path / "data" / "upload.log"
    log.write_bytes(b"x" * at + b"received %PDF-1.7 from the scanner\n" + LINE * 40)
    assert log.read_bytes().index(b"%PDF-") == at + 9
    out = _search({"path": str(log), "phrases": ["%PDF-1.7 from the scanner", FATAL]}, ctx)
    assert "unreadable" not in out and out["complete"] is True
    assert [q["found"] for q in out["queries"]] == [True, False]


def test_a_reading_stopped_before_a_reader_would_find_the_header_decides_nothing(tmp_path):
    """A byte limit under 1024 stops before the bytes that tell a PDF from text: what it found may be junk before a
    PDF's header, which no reader shows."""
    ctx = _ctx(tmp_path)
    pdf = tmp_path / "data" / "download.pdf"
    pdf.write_bytes(_pdf(LEASE, junk=b"Content-Type: application/pdf\r\n" + b"J" * 600 + b"\r\n"))
    out = _search({"path": str(pdf), "phrases": ["application/pdf"], "max_bytes": 100}, ctx)
    assert out["queries"][0]["found"] is None and "byte limit" in out["stopped"]   # before: True
    assert judge(p("equals", True, "queries.0.found"), out)[0] == INSUFFICIENT
    log = tmp_path / "data" / "app.log"                                           # text: 1024 bytes are enough
    log.write_bytes(b"application/json\n" + b"y" * 2000)
    for limit, found in ((1023, None), (1024, True)):
        out = _search({"path": str(log), "phrases": ["application/json"], "max_bytes": limit}, ctx)
        assert out["queries"][0]["found"] is found and out["complete"] is False, limit
    short = tmp_path / "data" / "short.log"                                       # a file shorter than 1024 bytes
    short.write_bytes(b"application/json\n")
    assert _search({"path": str(short), "phrases": ["application/json"], "max_bytes": 100}, ctx)["queries"][0][
        "found"] is True


def _pdf_mission(home, key, body_id, mission_id, pdf, phrase, *, absent):
    submit(home, key, body_id, "MISSION", mission(mission_id, checks=[
        {"check_id": "c", "description": f"{pdf.name} {'never mentions' if absent else 'mentions'} {phrase}",
         "sensor": {"capability": "fs.search", "params": {"path": str(pdf), "phrases": [phrase],
                                                          "whitespace": "collapse"}, "target": f"fs:{pdf.name}"},
         "predicate": {"op": "equals", "field": "queries.0.found", "value": not absent}}],
        strategies=[], capabilities=["fs.search"], ceiling="read_only"))


def test_a_search_mission_never_closes_on_a_pdfs_bytes(tmp_path):
    """The scout's repro, with fs.search named by hand: "never mentions" a phrase the reader shows closed ACHIEVED."""
    home, key, body_id, data = make_body(tmp_path)
    pdf = data / "lease.pdf"
    pdf.write_bytes(_pdf(LEASE))
    _pdf_mission(home, key, body_id, "m:never", pdf, SHOWN, absent=True)
    _pdf_mission(home, key, body_id, "m:font", pdf, SYNTAX, absent=False)
    missions, requests = run(home, Clock(), ticks=12, step=600.0)
    for mission_id in ("m:never", "m:font"):
        assert missions[mission_id].status != "ACHIEVED", mission_id               # before: ACHIEVED, both
        observed = [e for e in events(home, "mission.observed") if e["mission_id"] == mission_id]
        assert observed and all(not e["passed"] and "a PDF: its text is drawn by page operators" in e["detail"]
                                for e in observed)                               # the reason, on every reading
        assert [r.get("kind") for r in requests if r.get("mission_id") == mission_id] == ["SENSOR_FAILURE"]
    assert not [e for e in events(home, "mission.appraised") if e["mission_id"] in ("m:never", "m:font")]


@pytest.mark.parametrize("junk", [b"", b"%!PS-Adobe junk a mail gateway added\n" * 12], ids=["at-0", "after-junk"])
def test_the_founders_words_about_a_pdf_are_asked_when_no_reader_is_known(tmp_path, monkeypatch, junk):
    """On a body whose genesis knows no PDF reader (document.text is #201's), GREG asks, with the reason, instead of
    drafting a search of the PDF's bytes. A text file that quotes a header deep inside is still searched."""
    from greg import genesis
    monkeypatch.delitem(genesis.CATALOG, "document.text", raising=False)
    data = tmp_path / "data"
    data.mkdir()
    (data / "lease.pdf").write_bytes(_pdf(LEASE, junk=junk))
    ctx = PlannerContext(read_roots=(str(data),), capabilities=[], workspace=tmp_path / "ws")
    asked = template_route(f'Confirm {data / "lease.pdf"} never mentions "{SHOWN}"', ctx)
    assert asked["status"] == "NEEDS_INPUT" and "spec" not in asked                # before: a fs.search mission
    assert asked["origin"] == "template:document-phrase"
    assert "is a PDF" in asked["questions"][0] and "document.text" in asked["questions"][0]
    (data / "notes.txt").write_bytes(b"n" * 2000 + b"%PDF-1.4 is the header\n")
    searched = template_route(f'Confirm {data / "notes.txt"} never mentions "{SHOWN}"', ctx)
    assert searched["status"] == "PROPOSED" and searched["origin"] == "template:file-search"


@pytest.mark.parametrize("words, present", [('Confirm {f} never mentions "{a}" or "{b}"', [False, False]),
                                            ('Does {f} mention "{a}" and "{b}"?', [True, True])],
                         ids=["never", "mentions"])
def test_the_founders_words_about_a_pdf_go_to_its_reader_when_genesis_has_one(tmp_path, words, present):
    from greg import genesis
    assert "document.text" in genesis.CATALOG                                    # #201's reader, on #196
    data = tmp_path / "data"
    data.mkdir()
    pdf = data / "lease.pdf"
    pdf.write_bytes(_pdf(LEASE))
    ctx = PlannerContext(read_roots=(str(data),), capabilities=[], workspace=tmp_path / "ws")
    proposal = template_route(words.format(f=pdf, a=SHOWN, b="net thirty"), ctx)
    assert proposal["status"] == "PROPOSED" and proposal["origin"] == "template:document-phrase"
    spec = validate_mission(proposal["spec"])
    assert [c["sensor"] for c in spec["success_checks"]] == [
        {"function": "document.text", "params": {"path": str(pdf.resolve()), "phrase": phrase},
         "target": "fs:lease.pdf"} for phrase in (SHOWN, "net thirty")]
    assert [c["predicate"] for c in spec["success_checks"]] == [
        {"op": "equals", "field": "found", "value": value} for value in present]
    assert spec["light_cone"]["capabilities"] == ["acquired.document.text.*"]
    assert spec["light_cone"]["max_consequence_class"] == "read_only" and spec["light_cone"]["budget_usd"] == 0
    assert spec["auto_attach"] == {"max_consequence_class": "read_only"} and spec["strategies"] == []
    assert "fs.search" not in json.dumps(spec)


@pytest.mark.parametrize("swap", ["fifo", "link"])
def test_a_file_swapped_after_the_planner_checked_it_is_not_opened_through(tmp_path, monkeypatch, swap):
    """The planner opens the file the words name to look for a PDF header: a FIFO swapped in never blocks it, and a
    link swapped in after the roots were checked is not followed to a PDF outside them. Both are left to fs.search,
    which refuses them when it reads."""
    import os
    import threading
    from pathlib import Path
    from greg import genesis
    assert "document.text" in genesis.CATALOG                                    # #201's reader, on #196
    data = tmp_path / "data"
    data.mkdir()
    named = data / "lease.pdf"
    if swap == "fifo":
        os.mkfifo(named)
        monkeypatch.setattr(Path, "is_file", lambda self: True)                  # it was a file when GREG looked
    else:
        (tmp_path / "outside.pdf").write_bytes(_pdf(LEASE))
        named.write_text("ok\n")
        real = Path.resolve
        monkeypatch.setattr(Path, "resolve", lambda self, strict=False: self if self == named else real(self, strict))
        named.unlink()
        named.symlink_to(tmp_path / "outside.pdf")                                # swapped in after the check
    ctx = PlannerContext(read_roots=(str(data),), capabilities=[], workspace=tmp_path / "ws")
    proposals = []
    planner = threading.Thread(target=lambda: proposals.append(
        template_route(f'Confirm {named} never mentions "{SHOWN}"', ctx)), daemon=True)
    planner.start()
    planner.join(10)
    assert proposals and proposals[0]["origin"] == "template:file-search", swap


def test_the_founders_words_about_a_pdf_are_decided_by_what_its_reader_shows(tmp_path):
    """End to end on #196, with #201's reader and the real pinned poppler: the planner's document route, genesis
    acquiring pdftotext, the engine, the judge and the appraiser. The reader shows the phrase over two lines, and a
    font name only the page syntax holds is absent: "mentions" the shown phrase and "never mentions" the font name
    close, verified; "never mentions" the shown phrase and "mentions" the font name stay open on the reader's answer,
    not on a sensor failure."""
    pytest.importorskip("greg.documents")
    from greg import genesis
    if genesis.installed_binary("pdftotext") is None or genesis.installed_binary("pdfimages") is None:
        pytest.skip("pdftotext and pdfimages are needed to read the PDF")
    home, key, body_id, data = make_body(tmp_path)
    pdf = data / "lease.pdf"
    pdf.write_bytes(_pdf(LEASE))
    ctx = PlannerContext(read_roots=(str(data),), capabilities=[], workspace=home / "ws")
    cases = {"never-shown": (f'Confirm {pdf} never mentions "{SHOWN}"', True, False),       # (words, found, closes)
             "mentions-shown": (f'Confirm {pdf} mentions "{SHOWN}"', True, True),
             "never-syntax": (f'Confirm {pdf} never mentions "{SYNTAX}"', False, True),
             "mentions-syntax": (f'Does {pdf} mention "{SYNTAX}"?', False, False)}
    specs = {}
    for name, (words, _, _) in cases.items():
        proposal = template_route(words, ctx)
        assert proposal["origin"] == "template:document-phrase", proposal
        specs[name] = proposal["spec"]
        submit(home, key, body_id, "MISSION", specs[name])
    missions, requests = run(home, Clock(), ticks=8, step=120.0)
    for name, (_, found, closes) in cases.items():
        mission_id = specs[name]["mission_id"]
        observed = [e for e in events(home, "mission.observed") if e["mission_id"] == mission_id]
        assert observed and all(e["detail"].startswith(f"{found} == ") for e in observed), (name, observed)
        appraised = [e for e in events(home, "mission.appraised") if e["mission_id"] == mission_id]
        if closes:
            assert missions[mission_id].status == "ACHIEVED", name
            assert appraised and appraised[-1]["verdict"] == "VERIFIED", name
        else:                                       # before: "never-shown" ACHIEVED on the bytes (scout repro)
            assert missions[mission_id].status != "ACHIEVED" and not appraised, name
            assert all(not e["passed"] for e in observed), name
            assert [r.get("kind") for r in requests if r.get("mission_id") == mission_id] == ["NO_STRATEGY"], name
