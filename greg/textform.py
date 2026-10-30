"""Text as GREG compares it: one normalization form, and the part of a cut string no continuation can change.

Canonically equivalent texts (an accented letter as one code point, or as the letter and a combining accent; KELVIN
SIGN and K) are one text. Every check that compares text compares it in Unicode Normalization Form C, on both sides
(greg.missions.judge, greg.textquery, business.reconcile), so no verdict depends on which form either side is
written in (directive of 2026-10-22, section VI test 8).
"""
from __future__ import annotations

import functools
import unicodedata


def canon(text: str) -> str:
    """``text`` in Unicode Normalization Form C."""
    return unicodedata.normalize("NFC", text)


@functools.cache
def composes_backward() -> frozenset:
    """Starters that can join the character before them under NFC: the second half of a canonical pair, and the
    Hangul vowel and final-consonant jamo, which compose by rule instead of by table. Derived from the same
    ``unicodedata`` the normalizer uses, so the two cannot disagree."""
    seconds = set(range(0x1161, 0x1176)) | set(range(0x11A8, 0x11C3))
    for point in range(0x30000):           # no canonical decomposition lies above U+2FA1D
        parts = unicodedata.decomposition(chr(point)).split()
        if len(parts) == 2 and not parts[0].startswith("<"):
            seconds.add(int(parts[1], 16))
    return frozenset(seconds)


def stable(prefix: str) -> str:
    """The longest start of ``prefix`` whose NFC form begins the NFC form of every string ``prefix`` starts: all of
    it before its last character that starts a new normalization segment (a starter that joins nothing before it).
    That character may still compose with marks that follow it, so it is left out with what follows it."""
    backward = composes_backward()
    for i in range(len(prefix) - 1, -1, -1):
        first = unicodedata.normalize("NFD", prefix[i])[0]
        if unicodedata.combining(first) == 0 and not {ord(first), ord(prefix[i])} & backward:
            return prefix[:i]
    return ""
