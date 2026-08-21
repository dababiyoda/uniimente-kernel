"""The resume packet must stay parseable and must not outrun its evidence.

Two defects have now shipped in this file for the same underlying reason —
YAML punctuation inside unquoted scalars. An unquoted ``#`` silently truncated
four values (two node titles became ``'PR'`` and ``'Issue'``) with no error and
no schema failure; later an unquoted ``:`` in a run command broke the parse
outright. The first was worse, because it was silent.

So: parse it, and check that what it claims has something behind it. A resume
packet that a fresh context cannot read, or that promises evidence which is not
on disk, is worse than no packet — the next session would resume from it.
"""
from __future__ import annotations

import os
import re

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACKET = os.path.join(REPO_ROOT, "runtime", "TRACK_A_WORK_PACKET.yaml")


@pytest.fixture(scope="module")
def packet() -> dict:
    assert os.path.exists(PACKET), "the resume packet is missing"
    with open(PACKET, encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh)
    assert isinstance(loaded, dict), "the packet did not parse as a mapping"
    return loaded


def _unquoted_hash_lines(text: str) -> list[str]:
    """Lines where an unquoted ``#`` silently truncates the value.

    This detects the CAUSE rather than a symptom. The length heuristic below
    is kept, but it is the weaker check: the first version of this guard only
    inspected top-level scalars, so when the bug recurred inside a nested list
    — eating ``PR #66 remains immutable at a6f14d3`` down to ``"PR"``, the
    single most important standing constraint in the file — the guard passed.

    A guard written for a bug that does not catch that bug where it actually
    recurs is worse than no guard: it certifies the file.
    """
    offenders = []
    for number, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^(?:-\s+|[\w.\-]+:\s+)(.*)$", stripped)
        if not match:
            continue
        value = match.group(1)
        if value[:1] in ("'", '"', "|", ">"):        # quoted or block scalar
            continue
        if " #" in value:
            offenders.append(f"line {number}: {stripped}")
    return offenders


def test_no_unquoted_hash_truncates_a_value():
    """The root cause, checked against the raw text rather than the parse."""
    with open(PACKET, encoding="utf-8") as fh:
        offenders = _unquoted_hash_lines(fh.read())
    assert not offenders, (
        "an unquoted '#' silently truncates these values on load: " + str(offenders)
    )


def test_the_truncation_detector_can_actually_fire():
    """Negative control, using the exact line that defeated the old guard."""
    assert _unquoted_hash_lines("protected_invariants:\n  - PR #66 immutable at a6f14d3\n")
    assert _unquoted_hash_lines("head: 45b0d7f  # plus this commit\n")
    # ...and stays silent on the legitimate forms.
    assert not _unquoted_hash_lines('  - "PR #66 immutable at a6f14d3"\n')
    assert not _unquoted_hash_lines("# a whole-line comment about #66\n")
    assert not _unquoted_hash_lines("closure_count: 0\n")


def test_no_value_was_silently_truncated(packet):
    """Symptom check, applied to the WHOLE tree rather than the top level.

    Kept alongside the root-cause check because truncation has other causes
    than ``#`` — a stray ``:`` or a bad quote can shorten a value too.
    """
    suspicious = []

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, str) and 0 < len(node.strip()) < 4:
            suspicious.append(f"{path}={node!r}")

    walk(packet, "")
    assert not suspicious, (
        f"these values look truncated by YAML punctuation: {suspicious}"
    )


#: Artifacts a fresh context must be able to find FROM THE PACKET ALONE.
#: The packet is the resume mechanism; an artifact absent from its index does
#: not exist for the next session. An audit found all five of these missing —
#: including the founder's own standing interpretation rule — while
#: ``test_every_declared_evidence_path_exists`` passed, because verifying that
#: listed paths exist says nothing about what was never listed.
REQUIRED_EVIDENCE = (
    "docs/FOUNDER_VOCABULARY_AND_MECHANISM_NEUTRALITY.md",
    "runtime/contract.py",
    "runtime/seam",
    "runtime/evidence/P3_EPISODE.json",
    "runtime/contract_events.py",
)


def test_the_index_lists_every_artifact_a_fresh_context_needs(packet):
    """The complement of the check below: what is *missing* from the index."""
    listed = " ".join(str(v) for v in packet["evidence_paths"].values())
    absent = [p for p in REQUIRED_EVIDENCE if p not in listed]
    assert not absent, (
        f"a fresh context resuming from this packet would never find: {absent}"
    )


def test_every_declared_evidence_path_exists(packet):
    """Assert the subject exists. A path nobody can open is not evidence."""
    missing = []
    for key, value in packet["evidence_paths"].items():
        # Values may carry a parenthetical run hint; the path is the first token.
        path = str(value).split()[0]
        if not os.path.exists(os.path.join(REPO_ROOT, path)):
            missing.append(f"{key} -> {path}")
    assert not missing, f"evidence_paths point at nothing: {missing}"


#: Any of these in the counterfactual status means a run is being claimed.
#: The list is broad on purpose: two sessions worded the same claim differently
#: ("RUNTIME_CONSUMPTION_PROVEN" and "PASS_LOCAL_AND_CANONICAL_CI_EXACT_PINS"),
#: and a guard keyed to one wording would sit silently inert against the other.
CLAIM_MARKERS = ("PROVEN", "PASS", "GREEN", "VERIFIED")

#: A claimed run must point at one of these. Either implementation's record
#: satisfies it — the guard is about evidence existing, not about which seam
#: produced it.
COUNTERFACTUAL_RECORDS = (
    os.path.join("runtime", "evidence", "P3_EPISODE.json"),
    os.path.join("runtime", "P3_ROUTE_B_DELIBERATION.json"),
)


def test_a_claimed_counterfactual_run_has_a_recorded_artifact(packet):
    """The packet may not claim a run that left no record behind."""
    status = str(packet["runtime_counterfactual_status"]).upper()
    if not any(marker in status for marker in CLAIM_MARKERS):
        pytest.skip(f"no run is being claimed: {status!r}")
    present = [r for r in COUNTERFACTUAL_RECORDS
               if os.path.exists(os.path.join(REPO_ROOT, r))]
    assert present, (
        f"packet claims {status!r} but none of {list(COUNTERFACTUAL_RECORDS)} exists"
    )


def test_the_artifact_guard_is_not_inert(packet):
    """Negative control: the marker list must actually match this packet.

    Without this, broadening the markers could quietly turn the guard above
    into a permanent skip — which reads as green and checks nothing.
    """
    status = str(packet["runtime_counterfactual_status"]).upper()
    assert any(marker in status for marker in CLAIM_MARKERS), (
        f"no CLAIM_MARKER matches {status!r}; the artifact guard is now inert "
        "and would pass on a packet claiming a run that never happened"
    )


def test_closure_count_stays_honest(packet):
    """`VERIFIED_DEVELOPMENTAL_CLOSURES` moves only on all twelve conditions.

    Nothing in the seam work satisfies conditions 3-7 or 10-12, so a packet
    claiming a closure here would be claiming one that was never adjudicated.
    """
    assert packet["closure_count"] == 0, (
        "closure_count moved without a twelve-condition adjudication"
    )
