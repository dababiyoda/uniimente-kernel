"""document.text reads what a person sees, and its runs are contained (#201 review, documents lane).

Owned findings: DOC-1 (ink that is neither text nor a listed image was vouched for), DOC-5 (Unicode forms made a
visible phrase "absent"), DOC-6 (a phrase inside a longer word was "found"), DOC-7 (the judge compared a raw value
with normalized text), DOC-12 (letter spacing and sticky notes). Directive of 2026-10-22, section VIII, for the
pdftotext path: output units, time, memory, filesystem writes, stream bombs, stdout/stderr/exit status, truncated
or damaged output, the refusal's cause in the mission record, and scanned PDFs.

Every test marked "fails on a1d2abfb" was run against that commit and failed there; the controls pass on both.
The fixtures are PDFs GREG writes itself (greg/documents.py and the small writers below); the scanned page is a
real raster of a text page, made with the installed pdftoppm.
"""
from __future__ import annotations

import hashlib
import os
import sys
import time
import zlib
from pathlib import Path

import pytest

from greg import documents, genesis as genesis_mod
from greg.body import Body
from greg.capabilities import CapabilityError, InvocationContext
from greg.missions import FALSE, INSUFFICIENT, TRUE, judge
from tests.greg_fixtures import Clock, make_body, mission
from tests.unit.test_greg_missions import events, run, submit

needs_poppler = pytest.mark.skipif(
    any(genesis_mod.installed_binary(b) is None for b in ("pdftotext", "pdfimages", "pdffonts", "pdftoppm")),
    reason="poppler-utils not installed on this body; genesis would correctly escalate")
SCOPE = dict(capabilities=["fs.read", "acquired.document.text.*"], ceiling="read_only", auto_attach=True)
FONTS = "name type encoding emb sub uni object ID\n---- ---- -------- --- --- --- ---------\n"
LISTING = "page   num  type\n------------------\n"


class Blank:
    """Readers that render every page white and lay out no words: the page ink check finds nothing to explain."""
    pages_per_run = 2

    def __init__(self, pages=2, ink=False, extra_pages=0):
        self.pages, self.ink, self.extra = pages, ink, extra_pages

    def boxes(self, first, last):
        return "level\tpage_num\n" + "".join(f"1\t{p}\t0\t0\t0\t0\t0\t0\t8\t8\t-1\t###PAGE###\n"
                                               for p in range(first, last + 1)), "", ""

    def render(self, first, last):
        last = min(last, self.pages + self.extra)
        pixel = b"\x00" if self.ink else b"\xff"
        return b"".join(b"P5 8 8 255\n" + pixel * 64 for _ in range(first, last + 1)), "", ""


def whole(raw):
    """The companions' outputs for a text-only document every check vouches for."""
    return {"pdfimages": LISTING, "pdffonts": FONTS, "pages": Blank(raw.count("\f") or 1)}


def answer(text, phrase, **params):
    raw = text + "\f"
    return documents.find_phrase(" ".join(text.split()), {"phrase": phrase, **params}, raw, whole(raw))


# -- small PDF writers for content the oracle writer does not draw -------------------------------------------------

def raw_pdf(contents: list, *, images=None, encrypt=None) -> bytes:
    """One page per content stream (bytes), Helvetica as /F1; ``images`` maps a page index to (w, h, grey pixels)
    drawn full page as /Im0. ``encrypt``: (user, owner, permissions) under the standard RC4 40-bit handler."""
    n = len(contents)
    font = 3 + 2 * n
    body = [b"<< /Type /Catalog /Pages 2 0 R >>",
            f"<< /Type /Pages /Kids [{' '.join(f'{3 + 2 * i} 0 R' for i in range(n))}] /Count {n} >>".encode()]
    extra, key = [], None
    fid = hashlib.md5(b"".join(contents)).digest()
    if encrypt:
        user, owner, perms = encrypt
        o = _rc4(hashlib.md5((owner + _PAD)[:32]).digest()[:5], (user + _PAD)[:32])
        key = hashlib.md5((user + _PAD)[:32] + o + perms.to_bytes(4, "little", signed=True) + fid).digest()[:5]
        crypt = (f"<< /Filter /Standard /V 1 /R 2 /O <{o.hex()}> /U <{_rc4(key, _PAD).hex()}> "
                 f"/P {perms} >>").encode()
    for i, content in enumerate(contents):
        xobject = ""
        if images and i in images:
            w, h, pixels = images[i]
            extra.append(f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceGray "
                         f"/BitsPerComponent 8 /Filter /FlateDecode /Length ".encode() + b"%d >>\nstream\n"
                         % len(zlib.compress(pixels)) + zlib.compress(pixels) + b"\nendstream")
            xobject = f" /XObject << /Im0 {font + len(extra)} 0 R >>"
        body.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font} 0 R >>"
                    f"{xobject} >> /Contents {4 + 2 * i} 0 R >>".encode())
        data = content
        if key:
            data = _rc4(hashlib.md5(key + (4 + 2 * i).to_bytes(3, "little") + b"\0\0").digest()[:10], content)
        body.append(b"<< /Length %d >>\nstream\n" % len(data) + data + b"\nendstream")
    body.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    body += extra
    if encrypt:
        body.append(crypt)
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, obj in enumerate(body, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(body) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offsets)
    trailer = f"/Size {len(body) + 1} /Root 1 0 R" + (f" /Encrypt {len(body)} 0 R /ID [<{fid.hex()}> <{fid.hex()}>]"
                                                      if encrypt else "")
    out += f"trailer\n<< {trailer} >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


_PAD = bytes.fromhex("28BF4E5E4E758A4164004E56FFFA01082E2E00B6D0683E802F0CA9FE6453697A")


def _rc4(key: bytes, data: bytes) -> bytes:
    s, j = list(range(256)), 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) % 256
        s[i], s[j] = s[j], s[i]
    i = j = 0
    out = bytearray()
    for byte in data:
        i = (i + 1) % 256
        j = (j + s[i]) % 256
        s[i], s[j] = s[j], s[i]
        out.append(byte ^ s[(s[i] + s[j]) % 256])
    return bytes(out)


def text_ops(*lines, at=720) -> bytes:
    return ("BT /F1 12 Tf 16 TL 72 %d Td " % at + " ".join(f"({line}) Tj T*" for line in lines) + " ET\n").encode()


CLAUSE = "Either party may terminate without notice."


def reader(tmp_path):
    """The acquired reader exactly as genesis forms it (catalog candidate, pinned companions and tools)."""
    candidate = genesis_mod.CATALOG["document.text"]["candidates"][0]
    binary = genesis_mod.installed_binary("pdftotext")
    manifest = genesis_mod.Genesis._manifest_for(object(), "document.text", candidate, binary, "deficit")
    adapter = genesis_mod.catalog_adapter("document.text", candidate, binary)
    ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path,), secrets=None, manifest=manifest)

    def read(data, phrase=None, name="in.pdf"):
        target = tmp_path / name
        if data is not None:
            target.write_bytes(data)
        return adapter({"path": str(target), **({"phrase": phrase} if phrase else {})}, ctx)
    return read


def found_check(path, phrase, expected=True):
    return {"check_id": "found", "description": f"{path.name} {'states' if expected else 'never states'} {phrase!r}",
            "sensor": {"function": "document.text", "params": {"path": str(path), "phrase": phrase},
                       "target": f"fs:{path.name}"},
            "predicate": {"op": "equals", "field": "found", "value": expected}}


def text_check(path, op, value):
    return {"check_id": "text", "description": f"{path.name} {op} {value!r}",
            "sensor": {"function": "document.text", "params": {"path": str(path)}, "target": f"fs:{path.name}"},
            "predicate": {"op": op, "field": "text", "value": value}}


def run_mission(tmp_path, data, check, ticks=4):
    home, key, body_id, folder = make_body(tmp_path)
    target = folder / "doc.pdf"
    target.write_bytes(data)
    check = check(target)
    submit(home, key, body_id, "MISSION", mission("m:doc", checks=[check], strategies=[], **SCOPE))
    missions, _ = run(home, Clock(), ticks=ticks)
    return missions["m:doc"], home


def last_output(home):
    with Body(home) as body:
        receipts = [r for r in body.ledger.by_type("receipt") if (r.payload.get("result") or {}).get("output")]
    return receipts[-1].payload["result"]["output"]


# -- DOC-6: a phrase is found only as a whole -----------------------------------------------------------------------

@pytest.mark.parametrize("text, phrase", [("The nonrenewal term is twelve months.", "renewal term"),
                                          ("Liability is capped at $1,000,000 in total.", "capped at $1,000"),
                                          ("The non-renewal term applies.", "renewal term")])
def test_a_phrase_inside_a_longer_word_or_number_is_not_found(text, phrase):
    # fails on a1d2abfb: found True from a bare substring count
    out = answer(text, phrase)
    assert out["found"] is None and out["occurrences"] == 0 and "decided" not in out
    assert "inside a longer word" in out["undecided"]


@pytest.mark.parametrize("text", ["The renewal term is twelve months.", "(renewal term) applies", "a renewal term.",
                                  "“renewal term” here", "end: renewal term"])
def test_a_whole_phrase_with_punctuation_around_it_is_found(text):
    # control: passes on a1d2abfb too
    assert answer(text, "renewal term")["found"] is True


@needs_poppler
def test_a_states_mission_does_not_close_on_a_phrase_inside_a_longer_word(tmp_path):
    # fails on a1d2abfb: the mission closed ACHIEVED on "nonrenewal term"
    pdf = documents.write_pdf([["The nonrenewal term is twelve months."]])
    m, home = run_mission(tmp_path, pdf, lambda p: found_check(p, "renewal term"))
    assert m.status != "ACHIEVED"
    assert last_output(home)["found"] is None


# -- DOC-5 and the directive's Unicode test: forms a reader cannot tell apart -----------------------------------------

@pytest.mark.parametrize("text, phrase", [
    ("The Tenant’s deposit is held in trust.", "Tenant's deposit"),         # typographic apostrophe
    ("Rent is due on the ﬁrst day.", "due on the first day"),                # ligature fi
    ("Notice to the café owner.", "café owner"),                            # decomposed accent (NFD)
    ("Notice to the café owner.", "café owner"),                            # decomposed in the phrase
    ("The term is １２ months.", "term is 12 months"),                     # full-width digits
    ("The renewal term is set.", "renewal term"),                             # no-break space
    ("Payment net‑30 days.", "net-30 days"),                                  # non-breaking hyphen
    ("A soft re­newal term.", "renewal term")])                               # soft hyphen inside a word
def test_unicode_forms_of_one_phrase_are_one_phrase(text, phrase):
    # fails on a1d2abfb: compared raw code points, so each read found False on a "complete" extraction
    assert answer(text, phrase)["found"] is True


@needs_poppler
def test_a_never_states_mission_does_not_close_on_a_typographic_apostrophe(tmp_path):
    # fails on a1d2abfb: byte 0x92 extracts as U+2019, "Tenant's deposit" read absent, the mission ACHIEVED
    pdf = documents.write_pdf([["The Tenant\x92s deposit is held in trust."]])
    m, home = run_mission(tmp_path, pdf, lambda p: found_check(p, "Tenant's deposit", expected=False))
    assert m.status != "ACHIEVED"
    assert last_output(home)["found"] is True


def test_case_insensitive_matching_is_opt_in_and_a_case_difference_is_never_absence():
    # fails on a1d2abfb: a case difference read as absent; there was no opt-in
    assert answer("AUTOMATIC RENEWAL applies.", "automatic renewal")["found"] is None
    assert answer("AUTOMATIC RENEWAL applies.", "automatic renewal", ignore_case=True)["found"] is True


# -- DOC-12: letter spacing ------------------------------------------------------------------------------------------

def test_a_letter_spaced_phrase_is_never_proved_absent():
    # fails on a1d2abfb: "N O T I C E O F R E N E W A L" read as complete and the phrase absent
    out = answer("Lease terms. N O T I C E\n\nO F\n\nR E N E W A L", "NOTICE OF RENEWAL")
    assert out["complete"] is True and out["found"] is None
    assert answer("Lease terms are set out below.", "notice of renewal")["found"] is False      # control


def test_a_phrase_across_a_page_break_is_found():
    # control (directive VIII): pdftotext's form feed is whitespace between the pages' words
    raw = "The automatic renewal\f term is twelve months.\f"
    out = documents.find_phrase(" ".join(raw.split()), {"phrase": "renewal term"}, raw, whole(raw))
    assert out["pages"] == 2 and out["found"] is True


# -- DOC-7: the judge reads a declared text field by the reader's own rules ---------------------------------------

DECLARED = {"text_match": {"text": "document.phrase/1"}}     # documents.PHRASE_RULES, spelled out


@pytest.mark.parametrize("value", ["renewal  term", "renewal term\nis twelve", "renewal\tterm"])
def test_not_contains_on_document_text_matches_the_reader_whatever_the_whitespace(value):
    # fails on a1d2abfb: TRUE (absence "proved") for a value the text holds
    output = {"text": "The renewal term is twelve months", "complete": True, **DECLARED}
    assert judge({"op": "not_contains", "field": "text", "value": value}, output)[0] == FALSE
    assert judge({"op": "contains", "field": "text", "value": value}, output)[0] == TRUE


def test_contains_on_document_text_never_takes_a_longer_word_for_the_phrase():
    # fails on a1d2abfb: contains TRUE on "nonrenewal term"
    output = {"text": "The nonrenewal term is twelve months", "complete": True, **DECLARED}
    assert judge({"op": "contains", "field": "text", "value": "renewal term"}, output)[0] == INSUFFICIENT
    assert judge({"op": "not_contains", "field": "text", "value": "renewal term"}, output)[0] == INSUFFICIENT
    assert judge({"op": "not_contains", "field": "text", "value": "termination fee"}, output)[0] == TRUE


def test_a_kept_prefix_ending_at_the_phrase_is_not_a_whole_occurrence():
    # fails on a1d2abfb: the prefix "... renewal term" (the text went on "renewal terms") gave contains TRUE
    cut = {"truncated": True, "prefix": "x " * 50 + "renewal term", "length": 20000, "sha256": "0" * 64}
    output = {"text": cut, "complete": True, **DECLARED}
    assert judge({"op": "contains", "field": "text", "value": "renewal term"}, output)[0] == INSUFFICIENT
    early = {**cut, "prefix": "the renewal term is twelve months " + "x " * 50}
    assert judge({"op": "contains", "field": "text", "value": "renewal term"}, {**output, "text": early})[0] == TRUE


def test_absence_on_an_incomplete_document_is_never_proved_by_the_judge():
    output = {"text": "The renewal is twelve months", "complete": False, **DECLARED}
    assert judge({"op": "not_contains", "field": "text", "value": "termination fee"}, output)[0] == INSUFFICIENT


def test_an_undeclared_text_field_keeps_its_plain_semantics():
    # control: other capabilities' text is compared as before
    output = {"text": "The nonrenewal term", "complete": True}
    assert judge({"op": "contains", "field": "text", "value": "renewal term"}, output)[0] == TRUE


@needs_poppler
def test_a_text_check_with_a_double_space_does_not_prove_absence_on_the_mission_path(tmp_path):
    # fails on a1d2abfb: not_contains "renewal  term" passed on a document that states "renewal term"
    pdf = documents.write_pdf([["The renewal term is twelve months."]])
    m, _ = run_mission(tmp_path, pdf, lambda p: text_check(p, "not_contains", "renewal  term"))
    assert m.status != "ACHIEVED"


# -- DOC-1 and DOC-12: ink that is neither text nor a listed image ------------------------------------------------

@needs_poppler
@pytest.mark.parametrize("kind, why", [("pattern", "pages_with_unexplained_ink"),
                                       ("outline", "pages_with_unexplained_ink"),
                                       ("note", "pages_with_unexplained_ink"),
                                       ("type3", "type3_fonts")])
def test_visible_content_outside_the_text_layer_is_never_vouched_for(tmp_path, kind, why):
    # fails on a1d2abfb: complete true, so "automatic renewal" (drawn there, not in the text layer) read absent
    out = reader(tmp_path)(documents.write_pdf([documents.Drawn(kind, ["Lease terms are set out below."])]),
                           documents.HIDDEN)
    assert out["complete"] is False and out["found"] is None
    assert out[why], out
    assert out["text"] == "Lease terms are set out below." + (" x" if kind == "type3" else "")


@needs_poppler
def test_a_forbidden_clause_painted_by_a_pattern_does_not_close_the_mission(tmp_path):
    # fails on a1d2abfb: ACHIEVED, though pdftoppm renders the clause
    pdf = documents.write_pdf([documents.Drawn("pattern", ["Lease terms are set out below."])], compress=True)
    m, home = run_mission(tmp_path, pdf, lambda p: found_check(p, documents.HIDDEN, expected=False))
    assert m.status != "ACHIEVED"
    out = last_output(home)
    assert out["complete"] is False and out["pages_with_unexplained_ink"] == [1]


@needs_poppler
def test_rules_underlines_and_table_borders_do_not_cost_a_page_its_vouching(tmp_path):
    # control: the ordinary non-text ink of a contract (rules, a table grid, an underline) is explained
    ops = text_ops("Invoice 2026-117", "Consulting services 12 1200.00", "Total due 1500.00") + (
        b"0.8 w 72 690 m 540 690 l S 72 600 468 60 re S 300 600 m 300 660 l S 72 630 m 540 630 l S "
        b"72 707 m 170 707 l S\n")
    out = reader(tmp_path)(raw_pdf([ops]), "terminate without notice")
    assert out["complete"] is True and out["found"] is False


@pytest.mark.parametrize("pages, tools, expect", [
    (2, Blank(2), []), (2, Blank(2, ink=True), [1, 2]), (2, None, None), (2, Blank(2, extra_pages=1), None),
    (301, Blank(301), None)])                                   # one past documents.INK_MAX_PAGES
def test_the_ink_check_vouches_only_for_pages_it_rendered_and_explained(pages, tools, expect):
    # fails on a1d2abfb (no ink check): a render with ink, no render, a document longer than its text and a document
    # past the page limit each leave the pages unvouched
    assert documents.ink_check(pages, tools)["pages_with_unexplained_ink"] == expect


def test_a_reader_that_reported_the_document_damaged_vouches_for_nothing():
    raw = "First clause stands.\f"
    out = documents.find_phrase("First clause stands.", {"phrase": "terminate"}, raw,
                                {**whole(raw), "stderr": {"pdfimages": "Syntax Error (340): Dictionary key must be a"
                                                                       " name object"}})
    assert out["complete"] is False and out["found"] is None and out["reader_errors"]


@needs_poppler
def test_the_oracle_rejects_a_reader_that_ignores_drawn_ink(tmp_path, monkeypatch):
    # the frozen oracle's new cases require the check: without it, qualification fails on exactly those cases
    monkeypatch.setattr(documents, "unexplained_ink", lambda image, page: 0)
    from greg.capabilities import CapabilityManifest
    candidate = genesis_mod.CATALOG["document.text"]["candidates"][0]
    binary = genesis_mod.installed_binary("pdftotext")
    manifest = genesis_mod.Genesis._manifest_for(object(), "document.text", candidate, binary, "deficit")
    passed, report = genesis_mod.Genesis._verify(object(), "document.text", candidate, binary, 7, manifest)
    assert isinstance(manifest, CapabilityManifest) and not passed
    assert {f["case"] for f in report["failures"]} == {"case8.pdf", "case9.pdf", "case11.pdf"}


# -- directive VIII: damaged, empty, unreadable and encrypted documents ---------------------------------------------

@needs_poppler
def test_a_damaged_page_that_drops_a_clause_is_not_read_as_complete(tmp_path):
    # fails on a1d2abfb: pdftotext exits 0 with the first clause only; complete true, the second clause "absent"
    ops = text_ops("First clause stands.") + b"<<<< ]]]] (\n" + text_ops(CLAUSE, at=700)
    out = reader(tmp_path)(raw_pdf([ops]), "terminate without notice")
    assert out["text"] == "First clause stands."
    assert out["complete"] is False and out["found"] is None
    assert any("Syntax Error" in line for line in out["reader_errors"])


@needs_poppler
@pytest.mark.parametrize("data, cause", [
    (b"", "could not be opened as a PDF"),
    (b"%PDF-1.4\nthis is not a pdf at all\n%%EOF\n", "could not be opened as a PDF"),
    (raw_pdf([text_ops(CLAUSE)], encrypt=(b"secret", b"owner", -4)), "encrypted with a password")])
def test_a_refusal_names_its_cause(tmp_path, data, cause):
    # fails on a1d2abfb: "pdftotext exited 1" and nothing more (-q silences poppler's own message)
    with pytest.raises(CapabilityError, match=cause):
        reader(tmp_path)(data, "terminate")


@needs_poppler
def test_an_unreadable_path_is_refused_with_its_cause(tmp_path):
    (tmp_path / "folder.pdf").mkdir()
    with pytest.raises(CapabilityError, match="could not be opened as a PDF"):
        reader(tmp_path)(None, "terminate", name="folder.pdf")
    if os.geteuid() != 0:                                     # root reads a 000 file anyway
        locked = tmp_path / "locked.pdf"
        locked.write_bytes(documents.write_pdf([[CLAUSE]]))
        locked.chmod(0)
        with pytest.raises(CapabilityError, match="could not be opened as a PDF"):
            reader(tmp_path)(None, "terminate", name="locked.pdf")


@needs_poppler
def test_an_encrypted_pdf_without_a_user_password_is_read(tmp_path):
    # control: standard RC4 encryption with an empty user password opens for every reader
    out = reader(tmp_path)(raw_pdf([text_ops(CLAUSE)], encrypt=(b"", b"owner", -4)), "terminate without notice")
    assert out["found"] is True


@needs_poppler
def test_the_cause_of_a_refusal_reaches_the_mission_record(tmp_path):
    # fails on a1d2abfb: the record said only "pdftotext exited 1"
    m, home = run_mission(tmp_path, b"%PDF-1.4\nthis is not a pdf at all\n%%EOF\n",
                          lambda p: found_check(p, "terminate"), ticks=2)
    assert m.status != "ACHIEVED"
    assert any("could not be opened as a PDF" in e["detail"] for e in events(home, "mission.observed"))


# -- directive VIII: scanned PDFs ------------------------------------------------------------------------------------

def _scan_of(tmp_path, lines) -> tuple:
    """A real raster of a text page, by the installed pdftoppm: what a scanner hands back."""
    import subprocess
    page = tmp_path / "original.pdf"
    page.write_bytes(documents.write_pdf([lines]))
    pgm = subprocess.run([genesis_mod.installed_binary("pdftoppm"), "-gray", "-r", "60", str(page)],
                         capture_output=True, check=True).stdout
    magic, w, h, depth, pixels = pgm.split(maxsplit=4)
    assert magic == b"P5" and depth == b"255"
    return int(w), int(h), pixels[:int(w) * int(h)]


@needs_poppler
def test_a_scanned_pdf_is_never_text_complete(tmp_path):
    # directive VIII (verified, passes on a1d2abfb too): an image-only page, the clause in its pixels
    w, h, pixels = _scan_of(tmp_path, ["Residential lease.", CLAUSE])
    scan = raw_pdf([b"q 612 0 0 792 0 0 cm /Im0 Do Q\n"], images={0: (w, h, pixels)})
    out = reader(tmp_path)(scan, "terminate without notice", name="scan.pdf")
    assert out["complete"] is False and out["found"] is None
    assert out["pages_without_text"] == [1] and out["pages_with_images"] == [1]
    # the same scan with a stamped page number: text, but far less than the page holds
    stamped = raw_pdf([b"q 612 0 0 792 0 0 cm /Im0 Do Q\n" + text_ops("Page 1", at=30)], images={0: (w, h, pixels)})
    out = reader(tmp_path)(stamped, "terminate without notice", name="stamped.pdf")
    assert out["text"] == "Page 1" and out["complete"] is False and out["found"] is None


@needs_poppler
def test_neither_a_states_nor_a_never_states_mission_closes_on_a_scan(tmp_path):
    w, h, pixels = _scan_of(tmp_path, [CLAUSE])
    scan = raw_pdf([b"q 612 0 0 792 0 0 cm /Im0 Do Q\n"], images={0: (w, h, pixels)})
    for expected, sub in ((True, "a"), (False, "b")):
        (tmp_path / sub).mkdir()
        m, _ = run_mission(tmp_path / sub, scan, lambda p: found_check(p, "terminate without notice", expected))
        assert m.status != "ACHIEVED"


# -- directive VIII: output units, stderr, time, filesystem writes, stream bombs --------------------------------------

def _binary_adapter(tmp_path, binary, argv):
    from greg.capabilities import CapabilityManifest
    candidate = genesis_mod.Candidate("probe", argv, "words")
    adapter = genesis_mod.catalog_adapter("document.text", candidate, binary)
    target = tmp_path / "in.pdf"
    target.write_bytes(b"%PDF-1.4\n")
    ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path,), secrets=None,
                            manifest=CapabilityManifest.__new__(CapabilityManifest))
    object.__setattr__(ctx.manifest, "provenance", {})
    return lambda: adapter({"path": str(target)}, ctx), tmp_path / "ws"


@pytest.mark.parametrize("size, refused", [(64, False), (65, True)])
def test_the_output_ceiling_is_exact_in_bytes(tmp_path, monkeypatch, size, refused):
    # verified (passes on a1d2abfb too): MAX_OUTPUT bytes are accepted, one byte more is refused before buffering
    monkeypatch.setattr(genesis_mod.mechanisms, "MAX_OUTPUT", 64)
    write = f"import sys; sys.stdout.buffer.write(b'x' * {size})"
    call, _ = _binary_adapter(tmp_path, sys.executable, ("{binary}", "-I", "-c", write))
    if refused:
        with pytest.raises(CapabilityError, match="exceeds 64 bytes"):
            call()
    else:
        assert call()["text"] == "x" * 64


def test_a_flood_of_warnings_is_not_reported_as_an_oversized_answer(tmp_path):
    # fails on a1d2abfb: SIGXFSZ from stderr was reported as "output exceeds"
    shell = genesis_mod.installed_binary("sh")
    if shell is None or genesis_mod.installed_binary("yes") is None:
        pytest.skip("no sh or yes on this body")
    call, _ = _binary_adapter(tmp_path, shell, ("{binary}", "-c", "exec yes 1>&2"))
    with pytest.raises(CapabilityError, match="stderr exceeds"):
        call()


def test_a_binary_that_never_finishes_is_stopped_at_the_time_ceiling(tmp_path, monkeypatch):
    # fails on a1d2abfb: no time ceiling to set; the run held for the fixed 30 seconds
    monkeypatch.setattr(genesis_mod, "BINARY_TIMEOUT", 2, raising=False)
    call, _ = _binary_adapter(tmp_path, sys.executable, ("{binary}", "-I", "-c", "import time; time.sleep(60)"))
    started = time.monotonic()
    with pytest.raises(Exception) as caught:          # typed by the gates lane (DOC-10); here TimeoutExpired
        call()
    assert time.monotonic() - started < 15
    assert "timed out" in str(caught.value) or "did not finish" in str(caught.value)


def _landlock() -> bool:
    from greg import isolation
    return sys.platform.startswith("linux") and bool(isolation.available().get("available"))


@pytest.mark.skipif(not _landlock(), reason="no Landlock on this host: where a binary may write is not confined here")
def test_an_acquired_binary_can_write_no_file(tmp_path):
    # fails on a1d2abfb: the binary created a file next to its input
    planted = tmp_path / "planted.txt"
    write = f"open({str(planted)!r}, 'w').write('x')"
    call, _ = _binary_adapter(tmp_path, sys.executable, ("{binary}", "-I", "-c", write))
    with pytest.raises(CapabilityError, match="Permission"):
        call()
    assert not planted.exists()
    report = genesis_mod.ceilings()
    assert report["seconds"] == genesis_mod.BINARY_TIMEOUT and "Landlock" in report["filesystem_writes"]


def _bomb(payload: bytes, times: int) -> bytes:
    """A page whose Flate content stream inflates to ``times`` copies of ``payload`` (a stream bomb)."""
    squeeze = zlib.compressobj(9)
    data = b"".join(squeeze.compress(payload * 4096) for _ in range(times // 4096)) + squeeze.flush()
    return raw_pdf([b""]).replace(b"<< /Length 0 >>\nstream\n\nendstream",
                                  b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(data) + data
                                  + b"\nendstream")


@needs_poppler
def test_a_stream_bomb_that_inflates_to_words_is_stopped_by_a_ceiling_and_says_which(tmp_path):
    # 160 MB of drawn words inflate from a few hundred KB. pdftotext gathers a page's words before writing any, so on
    # this host the 2 GiB memory ceiling stops it (SIGABRT) before the 4 MiB output ceiling would; either way nothing
    # is reported read. Fails on a1d2abfb only on the named cause ("pdftotext exited -6")
    bomb = _bomb(b"BT /F1 12 Tf 72 700 Td (renewal) Tj ET\n", 4_194_304)
    assert len(bomb) < 2_000_000
    started = time.monotonic()
    with pytest.raises(CapabilityError, match="exceeds .* bytes|at the memory ceiling"):
        reader(tmp_path)(bomb, "terminate")
    assert time.monotonic() - started < genesis_mod.BINARY_TIMEOUT + 10


@needs_poppler
def test_a_stream_bomb_that_inflates_to_nothing_is_stopped_at_the_time_ceiling(tmp_path, monkeypatch):
    # about 1 GB of inflated whitespace from 1 MB: pdftotext parses it for about 9 s here. Under a 1 s ceiling it is
    # stopped. Fails on a1d2abfb: the ceiling was fixed at 30 s, so the run went on until pdftotext finished
    monkeypatch.setattr(genesis_mod, "BINARY_TIMEOUT", 1, raising=False)
    bomb = _bomb(b" " * 256, 4_194_304)
    started = time.monotonic()
    with pytest.raises(Exception) as caught:          # typed by the gates lane (DOC-10); here TimeoutExpired
        reader(tmp_path)(bomb, "terminate")
    assert "timed out" in str(caught.value) or "did not finish" in str(caught.value)
    assert time.monotonic() - started < 8
