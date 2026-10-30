"""The one text interpretation contract for a document reading.

Extraction (``greg.documents.find_phrase``), PDF reading (the ``document.text`` words parser and its
qualification oracle), mission judgment (``greg.missions.judge``) and independent appraisal
(``greg.appraisal``) all apply the rules in ``RULES``. A receipt records ``record()``. Judgment and
appraisal accept a reading only when ``agrees`` with that record, so a later change of these rules
cannot verify an older one.

The form is the one ``document.text`` already declared (NFKC, typographic quotes and dashes, soft
hyphens, collapsed whitespace, case kept) and the match is the one phrase extraction already declared
(whole words, and a hyphenated phrase also with its hyphens removed). Case is kept: folding it would
make "US" occur in "us".
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
        "typographic dashes and minus to ASCII hyphen",
        "soft hyphens removed",
        "whitespace collapsed to one space and stripped",
        "case preserved",
    ],
    "matching": [
        "whole words",
        "a match starts at the beginning, after whitespace, or after an opening bracket or quote",
        "a match ends at whitespace or the end, after optional closing punctuation",
        "a hyphenated phrase also matches with hyphens removed",
        "one form found is found; absence needs every form to miss",
    ],
}

# Typographic quotes, dashes and the soft hyphen. Case is not in this table.
_FOLD = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
                       "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u2033": '"',
                       "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
                       "\u00ad": None})

# Before a phrase: the start, whitespace, or an opening bracket or quote. After it: optional closing
# punctuation, then whitespace or the end. "renewal term" does not occur in "nonrenewal term".
_BEFORE, _AFTER = r"(?:^|(?<=[\s(\[\"']))", r"(?=[.,;:!?)\]\"']*(?:\s|$))"


def normalize(text: str) -> str:
    """``text`` in the contract's comparison form."""
    return " ".join(unicodedata.normalize("NFKC", text).translate(_FOLD).split())


def _forms(needle: str) -> list[str]:
    """The phrase, and with hyphens removed: a reader joins a line-end hyphen ("non-" / "compete")."""
    joined = needle.replace("-", "")
    return [needle] + ([joined] if joined != needle and joined.strip() else [])


def occurrences(text: str, phrase: str) -> int:
    """How many times ``phrase`` occurs in ``text`` under this contract. Both sides are normalized first."""
    if not isinstance(text, str) or not isinstance(phrase, str) or not phrase.split():
        return 0
    needle, folded = normalize(phrase), normalize(text)
    return sum(len(re.findall(_BEFORE + re.escape(form) + _AFTER, folded)) for form in _forms(needle))


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
