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
