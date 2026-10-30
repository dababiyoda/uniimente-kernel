"""The one text interpretation contract for a document reading.

Extraction (``greg.documents.find_phrase``), PDF reading (the ``document.text`` words parser and its
qualification oracle), mission judgment (``greg.missions.judge``) and independent appraisal
(``greg.appraisal``) all apply the rules in ``RULES``. A receipt records ``record()``. Judgment and
appraisal accept a reading only when ``agrees`` with that record, so a later change of these rules
cannot verify an older one.

The form is the one ``document.text`` already declared (NFKC, typographic quotes and dashes, the
modifier letter apostrophe, soft hyphens, collapsed whitespace, case kept) and the match is the one
phrase extraction already declared (whole words, and a hyphenated phrase also with its hyphens removed).
Case is kept: folding it would make "US" occur in "us".

Which reading decides depends on the claim (review of #244, the direction rule from the owner of
#209/#228/#229). A presence claim is true only on a whole word. An absence claim is true only when the
phrase is absent even as a substring, the hyphen-joined form included. When the two readings disagree,
neither claim is true, so the disagreement cannot close a mission. The fold is applied until it is
stable: one pass is not a comparison form if a second pass would still change it.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata

CONTRACT_ID = "greg.text-interpretation/1"
SUMMARY = "NFKC; typographic quotes and dashes to ASCII; soft hyphens removed; whitespace collapsed"

RULES = {
    "normalization": [
        "NFKC",
        "typographic quotes and primes to ASCII",
        "modifier letter apostrophe to ASCII",
        "typographic dashes and minus to ASCII hyphen",
        "soft hyphens removed",
        "whitespace collapsed to one space and stripped",
        "case preserved",
        "repeated until stable",
    ],
    "matching": [
        "whole words",
        "a match starts at the beginning, after whitespace, or after an opening bracket or quote",
        "a match ends at whitespace or the end, after optional closing punctuation",
        "a hyphenated phrase also matches with hyphens removed",
        "presence is true only on a whole word",
        "absence is true only when the phrase is also absent as a substring, hyphen-joined form included",
        "a phrase of whitespace only decides neither claim",
    ],
}

# Typographic quotes, dashes and the soft hyphen. Case is not in this table.
_FOLD = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
                       "\u02bc": "'",  # modifier letter apostrophe, which NFKC leaves unchanged
                       "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u2033": '"',
                       "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
                       "\u00ad": None})

# Before a phrase: the start, whitespace, or an opening bracket or quote. After it: optional closing
# punctuation, then whitespace or the end. "renewal term" does not occur in "nonrenewal term".
_BEFORE, _AFTER = r"(?:^|(?<=[\s(\[\"']))", r"(?=[.,;:!?)\]\"']*(?:\s|$))"


def _fold_once(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).translate(_FOLD).split())


def normalize(text: str) -> str:
    """``text`` in the contract's comparison form. A second application changes nothing."""
    folded = _fold_once(text)
    for _ in range(3):
        nxt = _fold_once(folded)
        if nxt == folded:
            return folded
        folded = nxt
    return folded


def _forms(needle: str) -> list[str]:
    """The phrase, and with hyphens removed: a reader joins a line-end hyphen ("non-" / "compete")."""
    joined = needle.replace("-", "")
    return [needle] + ([joined] if joined != needle and joined.strip() else [])


def _prepared(text, phrase):
    """The normalized text and phrase forms, or None when ``phrase`` is not a phrase (blank, or not text)."""
    if not isinstance(text, str) or not isinstance(phrase, str) or not phrase.split():
        return None
    needle = normalize(phrase)
    return normalize(text), _forms(needle)


def _word_spans(folded: str, form: str):
    return list(re.finditer(_BEFORE + re.escape(form) + _AFTER, folded))


def occurrences(text: str, phrase: str) -> int:
    """How many times ``phrase`` occurs in ``text`` as a whole word. Both sides are normalized first."""
    prepared = _prepared(text, phrase)
    if prepared is None:
        return 0
    folded, forms = prepared
    return sum(len(_word_spans(folded, form)) for form in forms)


def loose(text, phrase) -> bool:
    """Whether ``phrase`` occurs in ``text`` under the loosest reading: a substring, hyphen-joined form included.

    A phrase of whitespace only occurs nowhere. An absence claim uses this reading, so a possessive or a
    plural cannot make the shorter word count as missing."""
    prepared = _prepared(text, phrase)
    if prepared is None:
        return False
    folded, forms = prepared
    return any(form in folded for form in forms)


def interior(text, phrase) -> bool:
    """Whether a whole-word hit of ``phrase`` ends before the end of ``text``.

    A hit that ends where a kept prefix was cut is not proof the whole word is there: the next character,
    which was not kept, may continue it ("renewal" cut out of "renewals")."""
    prepared = _prepared(text, phrase)
    if prepared is None:
        return False
    folded, forms = prepared
    for form in forms:
        for match in _word_spans(folded, form):
            if match.end() < len(folded):
                return True
    return False


def same(left, right) -> bool:
    """Whether two strings are one text in this contract's form."""
    return isinstance(left, str) and isinstance(right, str) and normalize(left) == normalize(right)


def present(text, phrase) -> bool:
    """A presence claim: true only on a whole word."""
    return occurrences(text, phrase) > 0


def absent(text, phrase) -> bool:
    """An absence claim: true only when every reading misses. A blank phrase decides nothing."""
    if not isinstance(phrase, str) or not phrase.split():
        return False
    return not loose(text, phrase)


def phrase_found(text: str, phrase: str, *, complete: bool) -> bool | None:
    """The ``found`` bit extraction records: true when the phrase occurs, false only on a complete reading,
    and unknown when an incomplete reading did not contain it."""
    count = occurrences(text, phrase)
    if count:
        return True
    return False if complete else None


def digest() -> str:
    """Digest of the id and the rules. A rule change changes it."""
    payload = {"id": CONTRACT_ID, "rules": RULES}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def record() -> dict:
    """What a receipt keeps so a later appraisal can require these same rules."""
    return {"id": CONTRACT_ID, "sha256": digest(), "rules": RULES}


def agrees(recorded) -> bool:
    """Whether ``recorded`` is this contract, rules and digest together."""
    if not isinstance(recorded, dict):
        return False
    return (recorded.get("id") == CONTRACT_ID and recorded.get("rules") == RULES
            and recorded.get("sha256") == digest())
