"""The 2026-10-28 directive is kept whole, and the 2026-10-30 correction moves sequencing only.

The correction ("No real Chromebook run is needed. That is done when we completely build the
prompt") lets the build continue past the founder-device run. It must not loosen what counts as
that run: VEPMC still needs all nine ledger conditions, and only a founder-tier closure moves the
founder's path.
"""
import hashlib
import json
import re
from pathlib import Path

from greg import metrics

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "docs/intent/sources"
DIRECTIVE = SOURCES / "OPUS-MAXIMUS-MASTER-BUILD-DIRECTIVE-2026-10-28-source.md"
CORRECTION = SOURCES / "FOUNDER-CORRECTION-2026-10-30-source.md"
REQUIRED = ["intent_id", "statement", "source_refs", "owner", "state", "binding_scope", "constitutional_constraints",
            "success_evidence", "failure_evidence", "dependencies", "conflicts", "next_review_trigger", "supersedes",
            "superseded_by", "implementation_refs"]


def _fenced(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.index("````text\n") + len("````text\n")
    return text[start:text.rindex("\n````")]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("⸻", "")).strip()


def test_the_directive_is_kept_whole_and_its_digest_matches():
    body = _fenced(DIRECTIVE)
    stated = re.search(r"Its SHA-256 is\s+`([0-9a-f]{64})`", DIRECTIVE.read_text(encoding="utf-8")).group(1)
    assert hashlib.sha256(body.encode("utf-8")).hexdigest() == stated
    numbered = {int(n) for n in re.findall(r"^(\d{1,2})\. [A-Z]", body, flags=re.M)}
    assert set(range(1, 78)) <= numbered                    # all 77 sections, not a selection
    for clause in ("Different forms of intelligence as described by levin",
                   "whose public community influences it while it influences and helps that community",
                   "without confusing that appearance with biological consciousness",
                   "VERIFIED EMBODIED PERSISTENT MISSION CLOSURES",
                   "Do not merge automatically without explicit authority."):
        assert clause in body


def test_the_sections_kept_in_september_are_the_same_words_now():
    older = (SOURCES / "MASTER-BUILD-DIRECTIVE-2026-09-30-source.md").read_text(encoding="utf-8")
    now = _norm(_fenced(DIRECTIVE))
    sections = []
    for block in re.findall(r"```text\n(.*?)```", older, flags=re.S):
        sections += [s for s in re.split(r"\n(?=\d{1,2}\. [A-Z])", block) if s.strip()]
    assert len(sections) == 10
    for section in sections:
        assert _norm(section) in now, section.strip().splitlines()[0]


def test_the_correction_is_verbatim_and_both_records_are_complete():
    sentence = ("Continue building and doing the prompt verbatim. No real Chromebook run is needed. "
                "That is done when we completely build the prompt")
    assert sentence in CORRECTION.read_text(encoding="utf-8")
    for name in ("INTENT-20261030-BUILD-BEFORE-DEVICE-RUN", "INTENT-20261028-OPUS-MAXIMUS-REISSUE"):
        record = json.loads((ROOT / f"docs/intent/{name}.json").read_text(encoding="utf-8"))
        assert [k for k in REQUIRED if k not in record] == []
        assert record["intent_id"] == name and record["state"] == "active" and record["authority_delta"] == "none"
        for ref in record["source_refs"]:
            assert (ROOT / ref).exists(), ref
    correction = json.loads((ROOT / "docs/intent/INTENT-20261030-BUILD-BEFORE-DEVICE-RUN.json").read_text())
    assert correction["statement"] == sentence
    assert "final intended effect" in correction["changed_axis"] and "unchanged" in correction["changed_axis"]
    ledger = (ROOT / "docs/FOUNDER_INTENT_LEDGER.md").read_text(encoding="utf-8")
    assert "INTENT-20261030-BUILD-BEFORE-DEVICE-RUN" in ledger and "INTENT-20261028-OPUS-MAXIMUS-REISSUE" in ledger


def test_the_correction_does_not_loosen_what_counts_as_the_device_run():
    assert set(metrics.CONDITIONS) == {"founder_signed", "interface_detached", "persistent_runtime", "real_capability",
                                       "approval_boundary", "interruption_survived", "appraised_verified",
                                       "founder_accepted", "founder_body"}
    empty = type("J", (), {"replay": lambda self, *a: [], "ledger": type("L", (), {"by_type": lambda s, t: []})()})()
    result = metrics.vepmc(empty)
    assert result["founder_tier_count"] == result["VEPMC"] == 0 and result["evidence_level"] == "NONE"
