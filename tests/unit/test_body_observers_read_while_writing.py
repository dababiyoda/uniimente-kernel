"""The integration tests' observers read a running body's ledger without failing on the line it is still writing.

CI job 131435015364 (run 43290461166, #304 at e3053b72) failed the ten-step whole-machine test at step 10 with
``ValueError: partial or blank history record``. The raise came from the test's own observer:
Episode.run_to_closure -> request_for -> test_greg_body_supervised.events -> history(), which opened the body's live
ledger read-only with the default tail policy ``refuse``. The body appends each record line with one write(), but
the kernel grows the file a page at a time while it copies that write, so a reader that takes the size and reads up
to it can find the line cut at a page boundary (measured: every torn observation ended on a 4096-byte boundary).
That line was never acknowledged; greg.body.observe and every other process test leave it out (tail="ignore").

The file states below are exactly what such a reader finds: complete history, then the writer's line up to the
first page boundary inside it, then the whole line once the kernel has copied the rest.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from events.spine import EventSpine
from greg.journal import Journal
from provenance.ledger import EvidenceLedger
from tests.integration import test_greg_body_midflight_kill as midflight
from tests.integration import test_greg_body_supervised as supervised

C = "sha256:" + "ab" * 32
PAGE = 4096


def _body_writing_a_line(home: Path) -> tuple[bytes, int, int]:
    """A body home whose writer has appended r-1 and is part way through r-2: (r-2's whole file, where its line
    starts, the page boundary inside it the kernel has copied up to)."""
    home.mkdir()
    (home / "body.json").write_text(json.dumps({"constitution_hash": C}))
    path = home / "ledger.jsonl"
    writer = EvidenceLedger(C, str(path))
    journal = Journal(EventSpine(writer), actor="spiffe://uniimente.internal/greg/body")
    journal.record("decision.requested", {"mission_id": "m-1", "request_id": "r-1", "kind": "DECISION",
                                          "note": "x" * 3000})
    start = path.stat().st_size
    journal.record("decision.requested", {"mission_id": "m-1", "request_id": "r-2", "kind": "DECISION",
                                          "note": "y" * 6000})            # a receipt-sized line, crossing a page
    whole = path.read_bytes()
    writer.close()
    boundary = (start // PAGE + 1) * PAGE
    assert start < boundary < len(whole) and whole.endswith(b"\n")
    os.truncate(path, boundary)
    return whole, start, boundary


def _supervised(home):
    return [e["request_id"] for e in supervised.events(home, "decision.requested")]


def _midflight(home):
    return [e["request_id"] for e in midflight.read(home)["decision.requested"]]


@pytest.mark.parametrize("observe", [_supervised, _midflight], ids=["supervised.events", "midflight.read"])
def test_an_observer_leaves_out_the_line_the_body_is_still_writing(tmp_path, observe):
    home = tmp_path / "body"
    whole, _, boundary = _body_writing_a_line(home)
    path = home / "ledger.jsonl"
    seen = path.read_bytes()

    assert observe(home) == ["r-1"]                  # was: ValueError('partial or blank history record')
    assert path.read_bytes() == seen                 # an observer never touches the file

    with open(path, "ab") as fh:                     # the kernel finishes copying the writer's line
        fh.write(whole[boundary:])
    assert observe(home) == ["r-1", "r-2"]


def test_the_supervised_observer_still_reports_the_unacknowledged_line(tmp_path):
    """Left out is not hidden: the ledger it hands back names the bytes it did not read."""
    home = tmp_path / "body"
    whole, start, boundary = _body_writing_a_line(home)
    ledger, journal = supervised.history(home)
    try:
        assert ledger.unacknowledged_tail is not None
        assert ledger.unacknowledged_tail["offset"] == start
        assert ledger.unacknowledged_tail["bytes"] == boundary - start
        assert ledger.verify_chain()[0]
        assert [e.payload["request_id"] for e in journal.replay("decision.requested")] == ["r-1"]
    finally:
        ledger.close()


def test_a_malformed_complete_line_is_still_refused(tmp_path):
    """Only the unterminated last line is left out; a complete line that is not a record is corruption."""
    home = tmp_path / "body"
    _body_writing_a_line(home)
    path = home / "ledger.jsonl"
    data = path.read_bytes()
    cut = data.rfind(b"\n") + 1                      # the start of the partial line
    path.write_bytes(data[:cut] + b"not a record\n")
    with pytest.raises(ValueError, match="malformed"):
        supervised.events(home, "decision.requested")
    with pytest.raises(ValueError, match="malformed"):
        midflight.read(home)
