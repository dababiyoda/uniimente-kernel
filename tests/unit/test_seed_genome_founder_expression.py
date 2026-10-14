"""The 2026-10-13 founder message ("Build this: …") is preserved byte for byte:
a verbatim preface plus the two review passes already preserved on 2026-09-30.
Nothing in the preserved files may drift without this test noticing."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "docs/intent/sources"
SOURCE = SOURCES / "POLYINTELLIGENCE-SEED-GENOME-FOUNDER-EXPRESSION-2026-10-13.md"
MESSAGE_SHA256 = "de5db69c6c7a93aad302c422ae950c53ff25487bf919edd6ce504eb37e024acf"
MESSAGE_CHARS = 97219
PREFACE_SHA256 = "8e4e8dd683ae0da93779304e9007bb338c13514b6a0e9774723ddbb99ec9ce39"
PREFACE_CHARS = 3910


def _verbatim(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text.split("=== BEGIN VERBATIM TEXT ===\n", 1)[1].rsplit("\n=== END VERBATIM TEXT ===", 1)[0]


def _preface() -> str:
    text = SOURCE.read_text(encoding="utf-8")
    return text.split("=== BEGIN VERBATIM TEXT ===\n", 1)[1].split("=== END VERBATIM TEXT ===", 1)[0]


def test_preface_is_preserved_byte_for_byte():
    preface = _preface()
    assert len(preface) == PREFACE_CHARS
    assert hashlib.sha256(preface.encode("utf-8")).hexdigest() == PREFACE_SHA256
    assert preface.startswith("Build this:\n\n￼ ￼ ￼ in GitHub be sure you achieve the following Goal set:")
    assert preface.endswith("when the repertoire is insufficient. ￼\n\n")
    assert preface.count("￼") == 4
    assert "FOLLOW ALL INSTRUCTIONS VERBATIM MEET THE  LEVEL" in preface
    assert "absolute meniscus" in preface and "Competency Compiler" in preface


def test_message_rebuilds_from_preserved_files():
    pass_1 = _verbatim(SOURCES / "POLYINTELLIGENCE-CORTEX-REVIEW-PASS-1-2026-09-30.md")
    pass_2 = _verbatim(SOURCES / "POLYINTELLIGENCE-CORTEX-REVIEW-PASS-2-2026-09-30.md")
    assert pass_1.startswith("I reran the review")
    message = _preface() + pass_1 + "\n\n" + pass_2.rstrip("\n") + "\n"
    assert len(message) == MESSAGE_CHARS
    assert hashlib.sha256(message.encode("utf-8")).hexdigest() == MESSAGE_SHA256
    text = SOURCE.read_text(encoding="utf-8")
    assert MESSAGE_SHA256 in text and PREFACE_SHA256 in text and str(MESSAGE_CHARS) in text


def test_source_declares_no_authority():
    text = SOURCE.read_text(encoding="utf-8")
    assert "creates no runtime authority" in text
    assert "Repetition creates\n  no additional authority" in text or "Repetition creates no additional authority" in text


def test_every_protocol_intent_statement_quotes_the_message_verbatim():
    import json
    pass_1 = _verbatim(SOURCES / "POLYINTELLIGENCE-CORTEX-REVIEW-PASS-1-2026-09-30.md")
    pass_2 = _verbatim(SOURCES / "POLYINTELLIGENCE-CORTEX-REVIEW-PASS-2-2026-09-30.md")
    message = _preface() + pass_1 + "\n\n" + pass_2.rstrip("\n") + "\n"
    intents = json.loads((ROOT / "docs/collaboration/intents-polyintelligence-seed-genome-20261013.json")
                         .read_text(encoding="utf-8"))["intents"]
    assert len(intents) >= 12
    for record in intents:
        assert record["statement"] in message, record["intent_id"]
        assert record["status"] != "implemented" or record["implementation_refs"], record["intent_id"]
        for path in record["evidence_refs"] + record["implementation_refs"]:
            assert (ROOT / path.rstrip("/")).exists(), (record["intent_id"], path)
    literal = next(r for r in intents if "systemic dominance" in r["statement"])
    assert literal["status"] == "prohibited"


REISSUE_SHA256 = "a1f3efcaac7edcbb39e942cbbf2358a2d378092a26633938b97ca646fb873e56"


def test_the_2026_10_14_reissue_is_the_same_message_without_its_final_newline():
    pass_1 = _verbatim(SOURCES / "POLYINTELLIGENCE-CORTEX-REVIEW-PASS-1-2026-09-30.md")
    pass_2 = _verbatim(SOURCES / "POLYINTELLIGENCE-CORTEX-REVIEW-PASS-2-2026-09-30.md")
    message = _preface() + pass_1 + "\n\n" + pass_2.rstrip("\n") + "\n"
    assert hashlib.sha256(message[:-1].encode("utf-8")).hexdigest() == REISSUE_SHA256
    deliveries = SOURCE.read_text(encoding="utf-8").split("## Deliveries", 1)[1].split("\n## ", 1)[0]
    assert f"| 2026-10-13T14:42:11Z | {len(message)} | `{MESSAGE_SHA256}` | the message itself |" in deliveries
    assert f"| 2026-10-14T04:46:50Z | {len(message) - 1} | `{REISSUE_SHA256}` |" in deliveries
    assert "Repetition creates no additional authority" in deliveries
    assert "does not widen the approved scope" in deliveries
