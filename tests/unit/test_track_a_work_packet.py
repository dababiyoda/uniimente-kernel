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


def test_no_value_was_silently_truncated(packet):
    """The ``#`` failure mode: a value that parsed fine but lost its meaning."""
    suspicious = [
        f"{k}={v!r}" for k, v in packet.items()
        if isinstance(v, str) and 0 < len(v.strip()) < 4
    ]
    assert not suspicious, (
        f"these values look truncated by unquoted YAML punctuation: {suspicious}"
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


def test_a_claimed_counterfactual_run_has_a_recorded_artifact(packet):
    """The packet may not claim a run that left no record behind."""
    status = str(packet["runtime_counterfactual_status"])
    if "PROVEN" in status:
        record = os.path.join(REPO_ROOT, "runtime", "evidence", "P3_EPISODE.json")
        assert os.path.exists(record), (
            f"packet claims {status!r} but {record} does not exist"
        )


def test_closure_count_stays_honest(packet):
    """`VERIFIED_DEVELOPMENTAL_CLOSURES` moves only on all twelve conditions.

    Nothing in the seam work satisfies conditions 3-7 or 10-12, so a packet
    claiming a closure here would be claiming one that was never adjudicated.
    """
    assert packet["closure_count"] == 0, (
        "closure_count moved without a twelve-condition adjudication"
    )
