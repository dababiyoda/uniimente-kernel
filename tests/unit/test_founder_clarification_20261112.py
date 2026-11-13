"""The founder's clarification of 2026-11-12 is kept whole, and it moves priority and sequence only.

It asks for a composed candidate and checks on that exact revision. It must not turn composition into approval, or a
rehearsal into acceptance: VEPMC still needs the founder tier.
"""
import hashlib
import json
import re
from pathlib import Path

from greg import metrics

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/intent/sources/CONVERGENCE-CLARIFICATION-2026-11-12-source.md"
RECORD = ROOT / "docs/intent/INTENT-20261112-CONVERGENCE-USEFUL-PATH.json"
REQUIRED = ["intent_id", "statement", "source_refs", "owner", "state", "binding_scope", "constitutional_constraints",
            "success_evidence", "failure_evidence", "dependencies", "conflicts", "next_review_trigger", "supersedes",
            "superseded_by", "implementation_refs"]
PINNED = [
    "Green results on separate branches do not establish compatibility.",
    "Final merge approval and developmental composition are separate boundaries.",
    "Bind an appraisal to the specific closure and evidence it actually evaluates.",
    "Record where retained value goes, who consumes it, what behavior changes, and how that change is verified.",
    "Inspect what is available and attempt the permitted local test before declaring the entire capability unavailable.",
    "Market demand and commercial viability remain separate questions to investigate honestly.",
    "If the simpler method continues to win, retain it for that task.",
    "Permit explicit requalification when justified; avoid turning one rejection into an unexplained permanent "
    "prohibition across unrelated missions.",
    "A timeout does not establish measured failure.",
    "Only claim a skill, worker, browser, or tool was used when it was actually available and its execution was "
    "observed.",
    "Keep my authority fixed. Make operational competence grow.",
]


def block() -> str:
    text = SOURCE.read_text(encoding="utf-8")
    [body] = re.findall(r"^## F\. [^\n]*\n\n````text\n(.*?)\n````$", text, flags=re.S | re.M)
    return body


def test_the_message_is_kept_whole_and_its_digest_matches():
    body, text = block(), SOURCE.read_text(encoding="utf-8")
    [(size, digest)] = re.findall(r"^\| F \| [^|]+ \| +(\d+) \| `([0-9a-f]{64})` \|$", text, flags=re.M)
    assert (len(body), hashlib.sha256(body.encode("utf-8")).hexdigest()) == (int(size), digest)
    # both texts the message holds are there: ten numbered parts, then twelve
    first, second = body.split("Claude, continue from the existing workspace, workers, claims, and branches.")
    assert {int(n) for n in re.findall(r"^(\d{1,2})\. [A-Z]", first, flags=re.M)} >= set(range(1, 11))
    assert {int(n) for n in re.findall(r"^(\d{1,2})\. [A-Z]", second, flags=re.M)} >= set(range(1, 13))


def test_the_sentences_later_work_relies_on_are_in_the_message_word_for_word():
    body = block()
    for sentence in PINNED:
        assert sentence in body, sentence


def test_the_record_has_every_ledger_field_and_quotes_only_what_the_source_says():
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    assert not [f for f in REQUIRED if f not in record]
    assert record["state"] == "active" and record["authority_delta"] == "none"
    body = block()
    assert record["statement"] in body and record["exact_source_excerpt"] in body
    for ref in record["source_refs"]:
        assert (ROOT / ref).is_file(), ref
    ledger = (ROOT / "docs/FOUNDER_INTENT_LEDGER.md").read_text(encoding="utf-8")
    [entry] = re.findall(r"^## Convergence, then a useful operational path — 2026-11-12\n(.*?)(?=^## )", ledger,
                         flags=re.S | re.M)
    assert "`INTENT-20261112-CONVERGENCE-USEFUL-PATH`" in entry
    quotes = re.findall(r'"([^"]{12,})"', entry)
    assert len(quotes) >= 2
    for quoted in quotes:
        assert quoted in body, f"the ledger entry quotes words the source does not contain: {quoted}"


def test_the_clarification_moves_no_acceptance_measure():
    """A composed candidate and a sandbox case are evidence for engineering; neither moves VEPMC."""
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    assert any("VEPMC" in c and "rehearsal" in c for c in record["constitutional_constraints"])
    assert any("evidence only" in c for c in record["constitutional_constraints"])
    assert callable(metrics.founder_tier)
