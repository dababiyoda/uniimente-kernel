"""The founder's three messages of 2026-11-11 are kept whole, and they move sequencing and evidence discipline only.

They say that engineering never waits for a device run, a customer or a founder-only decision ("VEPMC = 0 does not
stop Track A"). They must not loosen what counts as that device run: VEPMC still needs the founder tier.
"""
import hashlib
import json
import re
from pathlib import Path

from greg import metrics

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/intent/sources/ABSOLUTE-OPUS-MAXIMUS-2026-11-11-source.md"
RECORD = ROOT / "docs/intent/INTENT-20261111-ABSOLUTE-OPUS-MAXIMUS.json"
REQUIRED = ["intent_id", "statement", "source_refs", "owner", "state", "binding_scope", "constitutional_constraints",
            "success_evidence", "failure_evidence", "dependencies", "conflicts", "next_review_trigger", "supersedes",
            "superseded_by", "implementation_refs"]
PINNED = {
    "A": ["VEPMC = 0 does not stop development.", "Start with a real software defect, not another roadmap.",
          "Do not manufacture evidence for Track B.",
          "Do not create another grand architectural document as a substitute for engineering."],
    "B": ["Distinguish historical validity of a signature from its continuing authority to approve a new effect.",
          "Do not mix unrelated work into #291.",
          "A small PR is a unit of progress, never the definition of completion."],
    "C": ["A small build is the next step. It is never a substitute for the destination.",
          "VEPMC = 0 does not stop Track A.",
          "The current smallest next build is truthful recovery of a retained negative receipt.",
          "A genuinely unknown outcome remains uncertain and requires reconciliation.",
          "Requalification never restores revoked execution permission.",
          "Do not count a missing browser dependency as a passing test.",
          "One model using five lenses is self-review.",
          "Do not relabel unfinished software as an external blocker to improve a count.",
          "Keep constitutional authority fixed while operational competence grows.",
          "BUILD THE WHOLE CURRENTLY ACHIEVABLE BODY + ORGANS + MIND."],
}


def blocks() -> dict:
    """The three fenced messages, by letter, exactly as stored."""
    text = SOURCE.read_text(encoding="utf-8")
    found = re.findall(r"^## ([ABC])\. [^\n]*\n\n````text\n(.*?)\n````$", text, flags=re.S | re.M)
    return dict(found)


def test_the_three_messages_are_kept_whole_and_their_digests_match():
    kept, text = blocks(), SOURCE.read_text(encoding="utf-8")
    assert sorted(kept) == ["A", "B", "C"]
    stated = dict(re.findall(r"^\| ([ABC]) \| [^|]+ \| +\d+ \| `([0-9a-f]{64})` \|$", text, flags=re.M))
    sizes = dict(re.findall(r"^\| ([ABC]) \| [^|]+ \| +(\d+) \| `", text, flags=re.M))
    for letter, body in kept.items():
        assert hashlib.sha256(body.encode("utf-8")).hexdigest() == stated[letter], letter
        assert len(body) == int(sizes[letter]), letter
    # the long directive keeps all twenty-two of its sections, in both of the forms the founder sent
    assert {int(n) for n in re.findall(r"^(\d{1,2})\. [A-Z]", kept["C"], flags=re.M)} >= set(range(1, 23))


def test_the_sentences_later_work_relies_on_are_in_the_messages_word_for_word():
    kept = blocks()
    for letter, sentences in PINNED.items():
        for sentence in sentences:
            assert sentence in kept[letter], (letter, sentence)


def test_the_record_has_every_ledger_field_and_quotes_only_what_the_source_says():
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    assert not [f for f in REQUIRED if f not in record]
    assert record["state"] == "active" and record["authority_delta"] == "none"
    whole = "\n".join(blocks().values())
    assert record["statement"] in whole and record["exact_source_excerpt"] in whole
    for ref in record["source_refs"]:
        assert (ROOT / ref).is_file(), ref
    ledger = (ROOT / "docs/FOUNDER_INTENT_LEDGER.md").read_text(encoding="utf-8")
    # This record's own entry only: from its heading to the next one. Other entries may sit above or below it
    # (the ledger grows at the top, and two changes can each add one), and they quote their own sources.
    [entry] = re.findall(r"^## Complete-machine execution on two tracks — 2026-11-11\n(.*?)(?=^## )", ledger,
                         flags=re.S | re.M)
    assert "`INTENT-20261111-ABSOLUTE-OPUS-MAXIMUS`" in entry
    quotes = re.findall(r'"([^"]{12,})"', entry)
    assert len(quotes) >= 2
    for quoted in quotes:
        assert quoted in whole, f"the ledger entry quotes words the source does not contain: {quoted}"


def test_the_directive_moves_no_acceptance_measure():
    """Engineering continues without the device run; the device run is still the only thing that moves VEPMC."""
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    assert any("VEPMC" in c and "test key" in c for c in record["constitutional_constraints"])
    assert callable(metrics.founder_tier)
