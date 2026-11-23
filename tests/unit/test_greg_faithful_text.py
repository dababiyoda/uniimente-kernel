"""Text a check judges is the text the evidence holds (directive of 2026-10-22, section VI test 8: Unicode, malformed
encoding and normalization; section VIII: limits enforced before uncontrolled buffering).

Three ways a check used to reach a verdict the evidence did not support:

* **Normalization.** The judge compared code points, so a forbidden phrase written in another normalization form (an
  accented letter as one code point, or as the letter and a combining accent) passed ``not_contains``, and a kept
  prefix ending just before an accent "contained" the bare letter. Text is now compared in NFC, and a kept prefix is
  read only up to the last point no continuation can renormalize (``greg.missions._stable``).
* **Lossy decoding.** ``fs.read``, ``http.get``, ``browser.render``, the shell helper and ``business.reconcile``
  decoded with ``errors="replace"``, so UTF-16 read as UTF-8 hid every phrase in it and ``not_contains`` passed. Text
  is now read in the encoding a byte-order mark names, else strict UTF-8; when no faithful reading exists the output
  says why and declares itself incomplete, so no check on its text decides either way.
* **Buffering before refusing.** ``fs.read`` read the whole file and then compared its size to the ceiling. It now
  refuses by the size the file states and never reads more than the ceiling and one byte.

In-process Body with a test clock and a per-test founder key, not Alfonso's (SANDBOX).
"""
from __future__ import annotations

import codecs
from dataclasses import replace
import os
import random
import subprocess
import threading
import tracemalloc
import unicodedata

import pytest

from greg.authority import RECEIPT_TEXT_LIMIT, keep_output
from greg.business_loop import reconcile
from greg.capabilities import (BUILTINS, MAX_READ_BYTES, CapabilityError, InvocationContext, SecretBroker,
                               bounded_read, browser_render, faithful_text, fs_read, http_get, run_cli, with_text)
import greg.capabilities
from greg.missions import FALSE, INSUFFICIENT, TRUE, judge, judge_receipt
from greg.textform import stable as _stable
from tests.greg_fixtures import Clock, make_body, mission, note_check
from tests.unit.test_greg_missions import events, run, submit

NFC = lambda s: unicodedata.normalize("NFC", s)       # noqa: E731
NFD = lambda s: unicodedata.normalize("NFD", s)       # noqa: E731
SIGNED = "José Núñez"                                  # as a founder types it: NFC
FILLER = "proof settlement notice delivery party shall net due. " * 400
assert len(FILLER) > RECEIPT_TEXT_LIMIT + 4000


def p(op, value, field="text"):
    return {"op": op, "field": field, "value": value}


def receipt(output, root):
    kept, whole = keep_output(output, root)
    return {"output": kept, **({"output_artifact": whole} if whole else {})}


def _ctx(tmp_path, capability="fs.read"):
    (tmp_path / "data").mkdir(exist_ok=True)
    return InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path / "data",),
                             secrets=SecretBroker(tmp_path / "secrets.json"), manifest=BUILTINS[capability][0])


def _peak(call, *, warm):
    """``call``'s refusal and the most memory it held, measured after ``warm`` ran once (imports and caches on the
    same path), outside pytest's own bookkeeping, so a test run alone measures what one run in the suite does."""
    for attempt in (warm, call):
        tracemalloc.start()
        try:
            try:
                attempt()
                refused = None
            except CapabilityError as exc:
                refused = str(exc)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
    return refused, peak


# -- normalization: one text, whichever form it is written in --------------------------------------------------------

def test_a_forbidden_name_in_another_normalization_form_is_found():
    output = {"text": f"Signed by {NFD(SIGNED)} on 1 May."}          # macOS file names and many PDFs are NFD
    assert NFD(SIGNED) != SIGNED and SIGNED not in output["text"]    # the code points differ
    assert judge(p("not_contains", SIGNED), output) == (FALSE, f"not contains {SIGNED!r}")    # before: TRUE
    assert judge(p("contains", SIGNED), output)[0] == TRUE                                     # before: FALSE
    assert judge(p("equals", NFD(SIGNED)), {"text": SIGNED})[0] == TRUE                       # before: FALSE
    assert judge(p("contains", NFD(SIGNED), "names"), {"names": [SIGNED, "Ann"]})[0] == TRUE   # list members too
    assert judge(p("equals", {SIGNED: 1}, "row"), {"row": {NFD(SIGNED): 1}})[0] == TRUE       # and object keys


def test_two_keys_spelling_one_text_decide_nothing():
    assert judge(p("equals", {SIGNED: 1}, "row"), {"row": {SIGNED: 1, NFD(SIGNED): 2}})[0] == INSUFFICIENT


def test_singleton_decompositions_are_the_same_text():
    # KELVIN SIGN and ANGSTROM SIGN are canonically K and Å; GREEK QUESTION MARK is ";"
    assert judge(p("not_contains", "5 K;"), {"text": "cooled to 5 K; done"})[0] == FALSE
    assert judge(p("equals", "Å"), {"text": "Å"})[0] == TRUE


def test_a_prefix_ending_before_an_accent_no_longer_contains_the_bare_letter(tmp_path):
    cut_at = RECEIPT_TEXT_LIMIT
    text = "x" * (cut_at - 4) + "cafe" + "́ au lait. " + FILLER      # the receipt keeps "...cafe", not the accent
    result = receipt({"text": text}, tmp_path)
    assert result["output"]["text"]["prefix"].endswith("cafe")
    assert judge(p("contains", "cafe"), result["output"])[0] == INSUFFICIENT          # before: TRUE from the prefix
    assert judge(p("not_contains", "cafe"), result["output"])[0] == INSUFFICIENT      # before: FALSE
    assert judge_receipt(p("contains", "cafe"), result, tmp_path)[0] == FALSE          # the whole reads "café"
    assert judge_receipt(p("contains", "café"), result, tmp_path)[0] == TRUE


def test_a_long_string_equal_as_text_is_never_called_different_by_its_digest(tmp_path):
    whole = FILLER + NFD(SIGNED)
    result = receipt({"text": whole}, tmp_path)
    expected = FILLER + SIGNED                                        # the same text, NFC
    assert judge(p("equals", expected), result["output"])[0] == INSUFFICIENT          # before: FALSE by digest
    assert judge_receipt(p("equals", expected), result, tmp_path)[0] == TRUE
    assert judge(p("equals", whole), result["output"])[0] == TRUE                     # same code points: digest
    assert judge(p("equals", "y" + FILLER), result["output"])[0] == FALSE             # differs in the kept part


# Characters that stress NFC at a boundary: starters, accents of several combining classes, precomposed letters,
# Hangul jamo that compose by rule, an Indic vowel sign that composes backwards with combining class 0, a Tibetan
# vowel whose decomposition starts with a mark, singletons, and plain ASCII.
ALPHABET = ["a", "e", "o", "u", "A", " ", ";", "K", "́", "̀", "̧", "̣", "̛", "ͅ",
            "̈", "é", "Å", "ᄀ", "ᅡ", "ᆨ", "가", "େ", "ା", "ཱ",
            "ི", "ཱི", "Å", "K", ";", "̈́", "ḋ", "̇", "ྲ", "ྀ"]


def _strings(rng, n, length):
    return ["".join(rng.choice(ALPHABET) for _ in range(rng.randint(0, length))) for _ in range(n)]


def test_the_stable_part_of_a_prefix_starts_the_normalized_whole_whatever_follows():
    rng = random.Random(20261030)
    for head, tail in zip(_strings(rng, 4000, 12), _strings(rng, 4000, 8)):
        assert NFC(head + tail).startswith(NFC(_stable(head))), (head, tail)


def test_verdicts_do_not_depend_on_the_normalization_form_of_either_side():
    rng = random.Random(1030)
    for value, phrase in zip(_strings(rng, 1500, 10), _strings(rng, 1500, 3)):
        for op in ("contains", "not_contains", "equals"):
            verdicts = {judge(p(op, form_p(phrase)), {"text": form_v(value)})[0]
                        for form_v in (NFC, NFD) for form_p in (NFC, NFD)}
            assert len(verdicts) == 1, (op, value, phrase, verdicts)


def test_a_verdict_from_a_kept_prefix_never_contradicts_the_whole(tmp_path):
    rng = random.Random(30)
    pad = "q" * (RECEIPT_TEXT_LIMIT - 6)
    for end, rest, phrase in zip(_strings(rng, 600, 8), _strings(rng, 600, 8), _strings(rng, 600, 3)):
        whole = pad + end + rest + "z" * 64
        kept = keep_output({"text": whole}, tmp_path)[0]
        for op in ("contains", "not_contains", "equals"):
            for value in (phrase, NFD(whole), NFC(whole), whole):
                from_prefix = judge(p(op, value), kept)[0]
                if from_prefix != INSUFFICIENT:
                    assert from_prefix == judge(p(op, value), {"text": whole}, whole=True)[0], (op, end, rest, value)


# -- decoding: read the bytes in their own encoding, or say no faithful reading exists -------------------------------

@pytest.mark.parametrize("codec, mark", [("utf-16-le", codecs.BOM_UTF16_LE), ("utf-16-be", codecs.BOM_UTF16_BE),
                                         ("utf-32-le", codecs.BOM_UTF32_LE), ("utf-8", codecs.BOM_UTF8)],
                         ids=["utf16le", "utf16be", "utf32le", "utf8"])
def test_a_marked_unicode_file_is_read_in_its_own_encoding(tmp_path, codec, mark):
    ctx = _ctx(tmp_path)
    path = tmp_path / "data" / "notice.txt"
    path.write_bytes(mark + f"Either party may terminate without notice. {SIGNED}".encode(codec))
    out = fs_read({"path": str(path)}, ctx)
    assert out["text"] == f"Either party may terminate without notice. {SIGNED}" and "complete" not in out
    assert judge(p("not_contains", "terminate without notice"), out)[0] == FALSE      # before (UTF-16): TRUE
    assert judge(p("contains", SIGNED), out)[0] == TRUE


@pytest.mark.parametrize("data, why", [
    ("Either party may terminate without notice.".encode("utf-16-le"), "NUL bytes"),    # UTF-16 with no mark
    ("Résumé of José, café terms: terminate without notice".encode("latin-1"), "not valid utf-8"),
    (b"terminate \xed\xa0\x80 without notice", "not valid utf-8"),                         # an encoded surrogate
    (codecs.BOM_UTF16_LE + b"t\x00\x00\xd8x\x00", "not valid utf-16"),                    # a lone surrogate
], ids=["utf16-unmarked", "latin1", "utf8-surrogate", "utf16-lone-surrogate"])
def test_an_unreadable_file_decides_no_check_on_its_text_either_way(tmp_path, data, why):
    ctx = _ctx(tmp_path)
    path = tmp_path / "data" / "notice.txt"
    path.write_bytes(data)
    out = fs_read({"path": str(path)}, ctx)
    assert "text" not in out and why in out["text_unreadable"] and out["complete"] is False
    for predicate in (p("not_contains", "terminate without notice"), p("contains", "terminate without notice"),
                      p("contains", "�"), p("equals", ""), {"op": "exists", "field": "text"}):
        assert judge(predicate, out)[0] == INSUFFICIENT, predicate         # before: not_contains TRUE (UTF-16)
    assert judge(p("equals", len(data), "bytes"), out)[0] == TRUE             # what was read whole still decides
    assert judge(p("equals", out["sha256"], "sha256"), out)[0] == TRUE


def test_a_cut_stream_drops_only_a_split_character():
    data = ("é" * 10).encode()
    assert faithful_text(data[:-1], cut=True) == ("é" * 9, "utf-8")
    assert faithful_text(data[:-1])[0] is None                                       # whole: a truncated character
    assert with_text({"n": 1}, b"\xff\xfe\x00")["decided"] == ["n", "text_unreadable"]


def test_a_statement_in_another_encoding_is_not_reported_unmatched(tmp_path):
    ctx = _ctx(tmp_path, "business.reconcile")
    statement = tmp_path / "data" / "statement.csv"
    statement.write_bytes("date,description,amount,currency\n2026-10-30,Payé CASE-41927,99.00,USD\n".encode("cp1252"))
    params = {"path": str(statement), "amount": "99.00", "currency": "USD", "reference": "CASE-41927"}
    out = reconcile(params, ctx)
    assert "matched" not in out and out["complete"] is False                       # before: read with U+FFFD
    assert judge(p("equals", False, "matched"), out)[0] == INSUFFICIENT
    for posted, signed in ((NFD("CASÉ-41927"), "CASÉ-41927"), ("CASÉ-41927", NFD("CASÉ-41927"))):
        statement.write_bytes(f"date,description,amount,currency\n2026-10-30,Payé {posted},99.00,USD\n".encode())
        out = reconcile({**params, "reference": signed}, ctx)
        assert out["matched"] is True, (posted, signed)                              # before: no posting carries it


def test_an_oversized_statement_is_refused_before_it_is_read(tmp_path):
    ctx = _ctx(tmp_path, "business.reconcile")
    statement = tmp_path / "data" / "statement.csv"
    with open(statement, "wb") as stream:
        stream.truncate(64 * 1024 * 1024)
    params = {"path": str(statement), "amount": "99.00", "currency": "USD", "reference": "CASE-41927"}
    refused, peak = _peak(lambda: reconcile(params, ctx), warm=lambda: reconcile(params, ctx))
    assert refused == "statement exceeds read ceiling" and peak < MAX_READ_BYTES // 4, peak   # before: 64 MiB


@pytest.mark.parametrize("body, readable", [(codecs.BOM_UTF16_LE + "terminate without notice".encode("utf-16-le"),
                                             True),
                                            ("terminate without notice".encode("utf-16-le"), False),
                                            ("Payé: terminate without notice".encode("latin-1"), False)],
                         ids=["utf16-marked", "utf16-unmarked", "latin1"])
def test_a_fetched_page_is_read_faithfully_or_not_at_all(tmp_path, monkeypatch, body, readable):
    from tests.fake_web import FakeWeb
    FakeWeb({"https://example.com/terms": (200, None, body)}).install(monkeypatch)
    out = http_get({"url": "https://example.com/terms"}, _ctx(tmp_path, "http.get"))
    verdict = judge(p("not_contains", "terminate without notice"), out)[0]
    assert verdict == (FALSE if readable else INSUFFICIENT)                         # before (UTF-16): TRUE
    assert judge(p("equals", 200, "status"), out)[0] == TRUE


def _render(monkeypatch, tmp_path, dom: bytes):
    monkeypatch.setattr(greg.capabilities, "chrome_binary", lambda: "/usr/bin/chromium")
    monkeypatch.setattr(greg.capabilities.subprocess, "run",
                        lambda argv, **kw: subprocess.CompletedProcess(argv, 0, dom, b""))
    return browser_render({"url": "https://example.com/terms"}, _ctx(tmp_path, "browser.render"))


def test_a_page_longer_than_the_kept_text_decides_only_what_more_could_not_undo(tmp_path, monkeypatch):
    page = f"<html><head><title>{'T' * 400}</title></head><body><p>{'clause. ' * 40000}</p>" \
           "<p>Either party may terminate without notice.</p></body></html>"
    out = _render(monkeypatch, tmp_path, page.encode())
    assert len(out["text"]) == MAX_READ_BYTES and out["complete"] is False             # the text was cut
    assert judge(p("not_contains", "terminate without notice"), out)[0] == INSUFFICIENT  # before: TRUE
    assert judge(p("contains", "clause."), out)[0] == TRUE                                  # what was kept proves
    assert judge(p("equals", "T" * 300, "title"), out)[0] == INSUFFICIENT                  # before: TRUE, cut at 300
    assert judge(p("equals", len(page.encode()), "dom_bytes"), out)[0] == TRUE             # the whole page's size
    assert out["cut_at"] == {"text": "end", "title": "end"}          # both kept as their start (review of #228, 1)
    short = _render(monkeypatch, tmp_path, b"<html><title>t</title><p>whole page</p></html>")
    assert "complete" not in short and judge(p("not_contains", "terminate"), short)[0] == TRUE


def test_a_page_cut_by_the_dom_limit_decides_only_what_more_could_not_undo(tmp_path, monkeypatch):
    page = (f"<html><title>t</title><script>var pad = '{'x' * (4 * MAX_READ_BYTES)}';</script>"
            "<p>Either party may terminate without notice.</p></html>").encode()
    out = _render(monkeypatch, tmp_path, page)
    assert out["dom_bytes"] == len(page) and out["complete"] is False                     # before: the cut's size
    assert judge(p("not_contains", "terminate without notice"), out)[0] == INSUFFICIENT    # before: TRUE
    assert out["cut_at"] == {"text": "end", "title": "end"}


def test_a_page_in_another_encoding_decides_nothing_on_its_text(tmp_path, monkeypatch):
    out = _render(monkeypatch, tmp_path, "<p>Payé: terminate without notice</p>".encode("latin-1"))
    assert "text" not in out and "not valid utf-8" in out["text_unreadable"]
    assert judge(p("not_contains", "terminate without notice"), out)[0] == INSUFFICIENT


def test_command_output_cut_or_unreadable_decides_only_what_more_could_not_undo(tmp_path, monkeypatch):
    ctx = replace(_ctx(tmp_path), manifest=replace(BUILTINS["fs.read"][0], binaries=("/bin/report",)))
    def fake(stdout, stderr=b""):
        monkeypatch.setattr(greg.capabilities, "run_isolated",
                            lambda argv, **kw: subprocess.CompletedProcess(argv, 0, stdout, stderr))
        return run_cli({"argv": ["/bin/report"]}, ctx)
    long = fake(b"ok " * MAX_READ_BYTES + b"FATAL: ledger corrupt", "é".encode() * 2001 + b"warning: disk")
    assert long["complete"] is False and set(long["decided"]) == {"argv", "returncode"}
    assert judge(p("not_contains", "FATAL", "stdout"), long)[0] == INSUFFICIENT          # before: TRUE
    assert judge(p("contains", "ok ok", "stdout"), long)[0] == TRUE
    assert long["stderr"].endswith("warning: disk") and long["stderr"].startswith("é")   # cut mid-character
    assert judge(p("equals", 0, "returncode"), long)[0] == TRUE
    utf16 = fake("FATAL: ledger corrupt".encode("utf-16-le"))
    assert "stdout" not in utf16 and "NUL bytes" in utf16["stdout_unreadable"]
    assert judge(p("not_contains", "FATAL", "stdout"), utf16)[0] == INSUFFICIENT         # before: TRUE
    whole = fake(b"all clear")
    assert "complete" not in whole and judge(p("not_contains", "FATAL", "stdout"), whole)[0] == TRUE


# -- reading: refuse by size before buffering -----------------------------------------------------------------------

def test_an_oversized_file_is_refused_before_it_is_read(tmp_path):
    ctx = _ctx(tmp_path)
    huge = tmp_path / "data" / "huge.log"
    with open(huge, "wb") as stream:
        stream.truncate(64 * 1024 * 1024)                                           # sparse: no disk used
    refused, peak = _peak(lambda: fs_read({"path": str(huge)}, ctx), warm=lambda: fs_read({"path": str(huge)}, ctx))
    assert refused == "file exceeds read ceiling"
    assert peak < MAX_READ_BYTES // 4, peak             # refused by its stated size, nothing read; before: 64 MiB


def test_a_file_that_misstates_its_size_is_read_no_further_than_the_ceiling(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path)
    growing = tmp_path / "data" / "status"
    with open(growing, "wb") as stream:
        stream.truncate(64 * 1024 * 1024)
    real = os.fstat
    monkeypatch.setattr(greg.capabilities.os, "fstat",                              # a /proc file states size 0
                        lambda fd: os.stat_result((*real(fd)[:6], 0, *real(fd)[7:])))
    read = lambda: fs_read({"path": str(growing)}, ctx)      # noqa: E731
    refused, peak = _peak(read, warm=read)
    assert refused == "file exceeds read ceiling" and peak < 2 * MAX_READ_BYTES, peak    # before: 64 MiB


def test_a_fifo_swapped_in_for_a_file_is_refused_without_blocking(tmp_path):
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)                                       # no writer: a blocking open would wait forever
    raised = []
    def read():
        try:
            bounded_read(fifo, "too big")
        except CapabilityError as exc:
            raised.append(str(exc))
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    reader.join(10)
    assert raised == ["pipe is not a regular file"]


def test_a_file_at_the_ceiling_is_still_read(tmp_path):
    ctx = _ctx(tmp_path)
    exact = tmp_path / "data" / "exact.txt"
    exact.write_bytes(b"a" * MAX_READ_BYTES)
    assert fs_read({"path": str(exact)}, ctx)["bytes"] == MAX_READ_BYTES


# -- on the mission path: a signed check is never closed on a reading the evidence does not support ------------------

def test_a_forbidden_clause_in_a_utf16_contract_keeps_the_mission_open(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    contract = data / "contract.txt"
    contract.write_bytes(codecs.BOM_UTF16_LE + "Either party may terminate without notice.".encode("utf-16-le"))
    check = note_check("clean", contract, "terminate without notice")
    check["predicate"]["op"] = "not_contains"
    submit(home, key, body_id, "MISSION", mission("m:clean", checks=[check], strategies=[],
                                                  capabilities=["fs.read"], ceiling="read_only"))
    missions, requests = run(home, Clock(), ticks=4, step=600.0)
    assert missions["m:clean"].status != "ACHIEVED"                                # before: ACHIEVED
    observed = [e for e in events(home, "mission.observed") if e["mission_id"] == "m:clean"]
    # the clause was read and found, a measured failure: not an unreadable file, not a question about the sensor
    assert observed and all(not e["passed"] and "insufficient evidence" not in e["detail"] for e in observed)
    assert [r.get("kind") for r in requests if r.get("mission_id") == "m:clean"] == ["NO_STRATEGY"]


def test_an_unreadable_contract_is_asked_about_not_certified(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    contract = data / "contract.txt"
    contract.write_bytes("Either party may terminate without notice.".encode("utf-16-le"))     # no mark
    check = note_check("clean", contract, "terminate without notice")
    check["predicate"]["op"] = "not_contains"
    submit(home, key, body_id, "MISSION", mission("m:clean", checks=[check], strategies=[],
                                                  capabilities=["fs.read"], ceiling="read_only"))
    missions, requests = run(home, Clock(), ticks=4, step=600.0)
    assert missions["m:clean"].status != "ACHIEVED"                                # before: ACHIEVED
    observed = [e for e in events(home, "mission.observed") if e["mission_id"] == "m:clean"]
    assert observed and all("insufficient evidence" in e["detail"] and "NUL bytes" in e["detail"] for e in observed)
    assert [r for r in requests if r.get("mission_id") == "m:clean"]               # the founder decides


def test_a_name_signed_in_one_form_closes_against_a_file_in_the_other(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    note = data / "note.txt"
    note.write_text(f"Countersigned by {NFD(SIGNED)}.")
    submit(home, key, body_id, "MISSION", mission("m:signed", checks=[note_check("signed", note, SIGNED)],
                                                  strategies=[], capabilities=["fs.read"], ceiling="read_only"))
    missions, requests = run(home, Clock(), ticks=4)
    assert missions["m:signed"].status == "ACHIEVED"                               # before: never, and an ask
    appraised = [e for e in events(home, "mission.appraised") if e["mission_id"] == "m:signed"]
    assert appraised and appraised[-1]["verdict"] == "VERIFIED"


# -- a failed read is not a measured absence (directive 2026-10-22, section IX scenario 7) ----------------------------

def test_a_directory_or_fifo_where_a_file_was_expected_is_a_failed_read_not_an_absent_file(tmp_path):
    """Before: fs.read answered ``exists: false`` for anything that was not a regular file, so a directory standing
    where a log should be read as a measured absence, and the founder was asked what to do about a failed check
    instead of about a sensor that could not read."""
    ctx, data = _ctx(tmp_path), tmp_path / "data"
    (data / "audit.log").mkdir()
    os.mkfifo(data / "pipe.log")
    for name in ("audit.log", "pipe.log"):
        with pytest.raises(CapabilityError, match="not a regular file"):
            fs_read({"path": str(data / name)}, ctx)
    missing = fs_read({"path": str(data / "missing.log")}, ctx)
    assert missing["exists"] is False and "text" not in missing


def test_a_check_on_a_missing_file_says_the_path_does_not_exist():
    verdict, detail = judge({"op": "contains", "field": "text", "value": "x"}, {"path": "/x", "exists": False})
    assert verdict == FALSE and detail == "field 'text' absent; the path does not exist"
    assert judge({"op": "contains", "field": "text", "value": "x"}, {"exists": True})[1] == "field 'text' absent"


# -- review of #228 (session_01Kucyfm2rRpECfxggpZqMes): a text the capability cut itself, keys, marks, links --------

def _incomplete(cut_at=None, **fields):
    return {**fields, "complete": False, "decided": [], **({"cut_at": cut_at} if cut_at else {})}


def test_a_text_the_capability_cut_itself_is_searched_only_where_no_continuation_can_renormalize():
    """Finding 1. A text a capability cut and declared incomplete (``complete: false``) was searched whole, so a
    phrase that ended where the cut fell ahead of a combining accent was "found": the whole holds "café", not "cafe".
    The capability names the side it cut at (``cut_at``), and the text is searched only where the rest cannot change
    it."""
    end = _incomplete({"text": "end"}, text="..cafe")
    assert judge(p("contains", "cafe"), end)[0] == INSUFFICIENT                                    # before: TRUE
    assert judge(p("not_contains", "cafe"), end)[0] == INSUFFICIENT                                # before: FALSE
    assert judge(p("contains", "caf"), end)[0] == TRUE                                             # still provable
    # a tail (stderr keeps its last bytes) may begin with marks of a character it did not keep: in the whole,
    # "é" + "x", not a bare accent followed by "x"; a vowel jamo there joins a consonant before it into one syllable
    start = {"stderr": "start"}
    assert judge(p("not_contains", "́x", "stderr"), _incomplete(start, stderr="́x and more"))[0] \
        == INSUFFICIENT                                                                            # before: FALSE
    assert judge(p("contains", "ᅡx", "stderr"), _incomplete(start, stderr="ᅡx and more"))[0] == INSUFFICIENT
    assert judge(p("contains", "x and more", "stderr"), _incomplete(start, stderr="́x and more"))[0] == TRUE
    # a side the judge does not know is read as both
    assert judge(p("contains", "x and more", "stderr"),
                 _incomplete({"stderr": "middle"}, stderr="́x and more"))[0] == INSUFFICIENT
    # a field the capability vouches for in ``decided`` is judged whole; so is a text whole in an output that is
    # not (document.text's words on a partly scanned PDF: what more pages add comes after a space)
    assert judge(p("contains", "cafe"), {**end, "decided": ["text"]})[0] == TRUE
    assert judge(p("contains", "cafe"), _incomplete(text="..cafe"))[0] == TRUE


def test_command_output_cut_before_an_accent_does_not_contain_the_bare_letter(tmp_path, monkeypatch):
    """Finding 1's reproduction through the real run_cli: stdout cut at the read ceiling between "cafe" and its
    accent."""
    ctx = replace(_ctx(tmp_path), manifest=replace(BUILTINS["fs.read"][0], binaries=("/bin/report",)))
    stdout = b"x" * (MAX_READ_BYTES - 4) + "café tail".encode()
    monkeypatch.setattr(greg.capabilities, "run_isolated",
                        lambda argv, **kw: subprocess.CompletedProcess(argv, 0, stdout, "é".encode() * 2001))
    out = run_cli({"argv": ["/bin/report"]}, ctx)
    assert out["stdout"].endswith("cafe") and out["complete"] is False
    assert out["cut_at"] == {"stdout": "end", "stderr": "start"}
    assert judge(p("contains", "cafe", "stdout"), out)[0] == INSUFFICIENT                          # before: TRUE
    assert judge(p("contains", "cafe", "stdout"), {"stdout": stdout.decode()}, whole=True)[0] == FALSE
    # the receipt's own cut of a tail the capability cut: its leading marks are not the whole's either
    kept = keep_output(_incomplete({"stderr": "start"}, stderr="́x" + FILLER), tmp_path)[0]
    assert set(kept["stderr"]) >= {"prefix", "sha256", "length"}
    assert judge(p("not_contains", "́x", "stderr"), kept)[0] == INSUFFICIENT                 # before: FALSE


def test_a_verdict_on_a_text_cut_on_either_side_never_contradicts_the_whole():
    """Finding 1, as a property: whatever was cut at the side declared, a TRUE or FALSE from what was kept is the
    whole's."""
    rng = random.Random(228)
    for head, kept_text, tail, phrase in zip(_strings(rng, 3000, 6), _strings(rng, 3000, 10),
                                             _strings(rng, 3000, 6), _strings(rng, 3000, 3)):
        for side, whole in (("end", kept_text + tail), ("start", head + kept_text), ("both", head + kept_text + tail)):
            for op in ("contains", "not_contains"):
                for value in (phrase, NFD(phrase), NFC(phrase)):
                    verdict = judge(p(op, value), _incomplete({"text": side}, text=kept_text))[0]
                    if verdict != INSUFFICIENT:
                        assert verdict == judge(p(op, value), {"text": whole}, whole=True)[0], (side, whole, value)


def test_a_field_path_names_a_key_in_either_normalization_form():
    """Finding 3. ``exists`` and ``absent`` used to depend on the form a key was written in; a key from external
    JSON arrives in either. Two keys spelling the path's text leave the check undecided."""
    out = {NFD("café"): "x"}
    assert judge(p("exists", None, NFC("café")), out)[0] == TRUE                                   # before: FALSE
    assert judge(p("absent", None, NFC("café")), out)[0] == FALSE                                  # before: TRUE
    assert judge(p("exists", None, NFD("café")), out)[0] == TRUE
    assert judge(p("absent", None, "cafe"), out)[0] == TRUE
    assert judge(p("exists", None, NFC("café")), {NFC("café"): 1, NFD("café"): 2})[0] == INSUFFICIENT
    # an incomplete observation under a key in the other form still limits the verdict on what it holds
    nested = {NFD("café"): _incomplete({"text": "end"}, text="..cafe")}
    assert judge(p("contains", "cafe", NFC("café") + ".text"), nested)[0] == INSUFFICIENT
    assert judge(p("equals", "..cafe", NFC("café") + ".text"), nested)[0] == INSUFFICIENT


def test_an_undecidable_whole_comparison_is_never_false():
    from greg.missions import _judge_whole
    colliding = {SIGNED: 1, NFD(SIGNED): 2}
    assert _judge_whole("equals", colliding, dict(colliding))[0] == INSUFFICIENT                   # before: FALSE


def test_a_utf8_mark_before_utf16_bytes_is_refused_like_unmarked_utf8():
    """Finding 4: the NUL guard tested the codec name "utf-8", and a UTF-8 byte-order mark reads as "utf-8-sig"."""
    text, why = faithful_text(codecs.BOM_UTF8 + "a\x00b".encode("utf-16-le"))
    assert text is None and "NUL" in why                                          # before: 'a\x00\x00\x00b\x00'
    assert faithful_text(codecs.BOM_UTF8 + "café".encode()) == ("café", "utf-8-sig")


def test_a_link_swapped_in_after_the_path_was_checked_is_not_followed(tmp_path):
    secret = tmp_path / "outside.txt"
    secret.write_text("not for the sensor")
    link = tmp_path / "data.txt"
    link.symlink_to(secret)
    with pytest.raises(CapabilityError, match="became a link"):
        bounded_read(link, "too big")                                             # before: read outside the roots


def test_a_repository_whose_history_is_not_utf8_is_a_failed_read_not_a_crash(tmp_path):
    from greg.capabilities import git_inspect
    repo = tmp_path / "data" / "repo"
    repo.mkdir(parents=True)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": "/dev/null"}
    def git(*args, data=b""):
        return subprocess.run(["git", "-C", str(repo), *args], check=True, env=env, capture_output=True,
                              input=data).stdout.decode().strip()
    git("init", "-q")
    tree = git("hash-object", "-t", "tree", "-w", "--stdin")
    # a commit object as older tools stored it: a Latin-1 subject and no encoding header (``git commit`` itself now
    # re-encodes such a message)
    commit = git("hash-object", "-t", "commit", "-w", "--stdin", data=(
        f"tree {tree}\nauthor t <t@t> 0 +0000\ncommitter t <t@t> 0 +0000\n\n".encode() + "caf\u00e9".encode("latin-1")))
    git("update-ref", "HEAD", commit)
    with pytest.raises(CapabilityError, match="not valid UTF-8"):                 # before: UnicodeDecodeError
        git_inspect({"path": str(repo)}, _ctx(tmp_path, "git.inspect"))


def test_a_kept_prefix_is_searched_in_either_form_of_the_phrase(tmp_path):
    """Finding 5: no test held the needle's normalization in the cut path. A name in the kept prefix is found whichever
    form the founder signed it in."""
    kept = keep_output({"text": f"Signed by {SIGNED}. " + FILLER}, tmp_path)[0]
    assert set(kept["text"]) >= {"prefix", "sha256", "length"}
    for phrase in (SIGNED, NFD(SIGNED)):
        assert judge(p("contains", phrase), kept)[0] == TRUE                       # mutant: INSUFFICIENT for NFD
        assert judge(p("not_contains", phrase), kept)[0] == FALSE
