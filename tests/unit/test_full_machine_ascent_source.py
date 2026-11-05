"""The October 22 directive's part 1, as the founder re-issued it on 2026-10-30, is kept byte for byte.

The record's header states the SHA-256 of the text between its fences. This test pins that digest as well, so a
changed byte fails here even when the header is restated to match it. Part 2 of the same message is also the
2026-10-22 record's text, and the two copies must not drift apart.
"""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "docs/intent/sources"
SOURCE = SOURCES / "OPUS-MAXIMUS-FULL-MACHINE-ASCENT-2026-10-22-source.md"
PART_TWO = SOURCES / "GREG-FULL-MACHINE-COMPLETION-2026-10-22-source.md"
DIGEST = "8c900e05284c2a683f829d4aea68ba07885fb5aa7b99aeddb1033a41864c0b0a"
SECTIONS = ["I. YOUR ULTIMATE ASSIGNMENT", "II. PRESERVE THE FOUNDER’S EXACT WORDS",
            "III. RECONSTRUCT CURRENT TRUTH BEFORE EDITING", "IV. OPERATE AS ONE PROFESSIONAL ENGINEERING TEAM",
            "V. PR #201: WHAT IS BUILT, WHAT IS NOT", "VI. PRIORITY ZERO — MAKE MISSION EVIDENCE LOGICALLY SOUND",
            "VII. PRIORITY ZERO — MAKE OPEN-SOURCE ACQUISITION TRUSTWORTHY",
            "VIII. OUTPUT LIMITS AND DOCUMENT RELIABILITY",
            "IX. INTEGRATE THE FULL MACHINE, NOT A COLLECTION OF FEATURES", "X. MECHANISM RECOMBINATION FOUNDRY",
            "XI. PARALLEL ENGINEERING AND HANDOFF QUALITY", "XII. ACCEPTANCE GATES", "XIII. REQUIRED FINAL REPORT"]


def _fenced(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.index("````text\n") + len("````text\n")
    return text[start:text.rindex("\n````")]


def test_part_one_is_kept_whole_and_its_digest_matches():
    body = _fenced(SOURCE)
    stated = re.search(r"Its SHA-256 is\s+`([0-9a-f]{64})`", SOURCE.read_text(encoding="utf-8")).group(1)
    assert hashlib.sha256(body.encode("utf-8")).hexdigest() == stated == DIGEST
    assert (len(body.encode("utf-8")), len(body), body.count("\n") + 1) == (48823, 48550, 1019)
    assert re.findall(r"^[IVX]+\. .+$", body, flags=re.M) == SECTIONS     # all thirteen, in order, no more


def test_part_two_is_the_october_22_record_word_for_word():
    recorded = PART_TWO.read_text(encoding="utf-8").splitlines(keepends=True)
    assert recorded[9].startswith("You are the engineering lead and production coordinator for UNIIMENTE / GREG.")
    assert _fenced(SOURCE).endswith("".join(recorded[9:368]).removesuffix("\n"))
