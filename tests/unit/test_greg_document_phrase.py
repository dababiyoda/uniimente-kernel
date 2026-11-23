"""A phrase is found as a reader sees it (#201 review DOC-4, DOC-5, DOC-6, DOC-7's document half).

Each case is a PDF GREG writes, read by the real pinned pdftotext argv plus the pdfimages companion, then judged by
``documents.find_phrase`` exactly as the document.text capability does. Before: a hyphen broken across a line, a
typographic apostrophe and a ligature each made a visible phrase "absent" on a complete extraction, and a phrase
was "found" inside a word that negates it.
"""
from __future__ import annotations

import subprocess

import pytest

from greg import documents, genesis as genesis_mod

needs_reader = pytest.mark.skipif(genesis_mod.installed_binary("pdftotext") is None
                                  or genesis_mod.installed_binary("pdfimages") is None,
                                  reason="pdftotext and pdfimages are needed to read the PDFs")


def read(tmp_path, pages, phrase):
    path = tmp_path / "doc.pdf"
    path.write_bytes(documents.write_pdf(pages, compress=True))
    raw = subprocess.run([genesis_mod.installed_binary("pdftotext"), "-enc", "UTF-8", "-q", str(path), "-"],
                         capture_output=True, text=True).stdout
    images = subprocess.run([genesis_mod.installed_binary("pdfimages"), "-list", str(path)],
                            capture_output=True, text=True).stdout
    out = documents.find_phrase(genesis_mod.PARSERS["words"](raw), {"phrase": phrase}, raw, {"pdfimages": images})
    return out["complete"], out["found"]


@needs_reader
@pytest.mark.parametrize("lines, phrase", [
    (["The employee accepts a non-", "compete covenant for twelve months."], "non-compete covenant"),   # DOC-4
    (["See section 4-", "2 of the lease."], "section 4-2"),
    (["The Tenant\x92s deposit is held in trust."], "Tenant's deposit"),                                   # DOC-5
    (["The Tenant's deposit is held in trust."], "Tenant\u2019s deposit"),
])
def test_a_visible_phrase_is_found_whatever_its_typography(tmp_path, lines, phrase):
    assert read(tmp_path, [lines], phrase) == (True, True)


@needs_reader
@pytest.mark.parametrize("line, phrase", [
    ("The nonrenewal term is twelve months.", "renewal term"),                                         # DOC-6
    ("Liability is capped at $1,000,000 per claim.", "capped at $1,000"),
    ("The non-renewal term is twelve months.", "renewal term"),
])
def test_a_phrase_inside_a_word_that_negates_it_is_not_found(tmp_path, line, phrase):
    assert read(tmp_path, [[line]], phrase) == (True, False)


@needs_reader
@pytest.mark.parametrize("line", ["The renewal term is twelve months.", "(renewal term) applies.",
                                  "Note the renewal term.", "\x93renewal term\x94 applies."])
def test_a_whole_phrase_with_punctuation_around_it_is_found(tmp_path, line):
    assert read(tmp_path, [[line]], "renewal term") == (True, True)


def test_the_folded_form_removes_ligatures_quotes_dashes_and_soft_hyphens():
    assert documents.fold("notiﬁcation of  re­newal – the Tenant’s “term”") == \
        "notification of renewal - the Tenant's \"term\""


def test_the_output_names_the_form_a_text_predicate_must_compare_in():
    out = documents.find_phrase("a b", {"phrase": "a"}, "a b\n", {"pdfimages": ""})
    assert out["text_form"] == documents.FOLDING
