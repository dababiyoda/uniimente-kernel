"""The founder's quotations A-D in the one-machine intent record stay byte-for-byte what he wrote.

The record is rewritten as implementation proceeds (implementation_refs grow); a rewrite that escapes or
normalizes characters would silently change founder wording. Each quotation must appear verbatim in the
preserved directive source, and the record must stay readable as UTF-8 text, not escape sequences.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "docs" / "intent" / "INTENT-20261014-ONE-MACHINE.json"
SOURCE = ROOT / "docs" / "intent" / "sources" / "ONE-MACHINE-CORRECTIVE-DIRECTIVE-2026-10-14-source.md"


def test_quotations_a_to_d_are_verbatim_in_the_preserved_directive():
    raw = RECORD.read_text(encoding="utf-8")
    quotations = json.loads(raw)["founder_quotations"]
    source = SOURCE.read_text(encoding="utf-8")
    assert set("ABCD") <= set(quotations)
    for letter in "ABCD":
        assert quotations[letter] in source, letter
        assert quotations[letter] in raw, f"{letter} is stored escaped, not as the founder's text"
