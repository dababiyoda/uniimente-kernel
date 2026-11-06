"""Section 45: a restatement separates fact from interpretation, and source quality decides acceptance.

An unlabelled interpretation that changes none of the six detected kinds of wording is a
supported sentence today. Acceptance is the same composition ``worker.appraise`` already
runs: ``read_claims``, then the evidence family, then ``coverage``.
"""
from __future__ import annotations

import json

from greg.cognition.restatement import answer, coverage, read_claims, source

SPAN = "the new routing method may reduce delays by 12%"
STUDY = "A study at two depots found the new routing method may reduce delays by 12%."
INTERPRETATION = "This means the routing method may reduce delays by 12%."
FACT = "The routing method may reduce delays by 12%."


def _judge(sentence: str, *, kind: str | None, quality: str) -> list[str]:
    claim = {"text": sentence, "quotes": [SPAN]}
    if kind is not None:
        claim["kind"] = kind
    claims, findings = read_claims(json.dumps([claim]), ["study.txt"])
    if not claims:
        return findings
    sources = [source("study.txt", STUDY, quality=quality, expires_at="2050-01-01T00:00:00Z",
                      provenance="synthetic depot summary")]
    receipts = answer(claims, sources, problem_prefix="s45")
    _truth, problems = coverage(sentence, receipts)
    return findings + problems


def test_an_unlabelled_interpretation_is_held():
    held = _judge(INTERPRETATION, kind=None, quality="primary")
    assert held and any("unlabelled" in f and "held" in f for f in held)


def test_source_quality_decides_whether_a_separated_reading_is_accepted():
    for quality in ("primary", "secondary", "unverified"):
        assert _judge(FACT, kind="fact", quality=quality) == [], quality
    assert _judge(INTERPRETATION, kind="interpretation", quality="primary") == []
    for quality in ("secondary", "unverified"):
        held = _judge(INTERPRETATION, kind="interpretation", quality=quality)
        assert held and any("held" in f and "primary" in f for f in held), quality
