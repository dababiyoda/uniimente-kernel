"""Section IX scenarios 5 and 6 on the acquisition path (directive of 2026-10-22, re-issued 2026-10-30).

5. A held or unknown-license component cannot be silently attached: a mission whose signed scope pre-authorizes a
   read-only attach still waits for the founder when the reader's OS package declares a held license, and the
   reason names the license.
6. A known compatible component is reused without unnecessary reconstruction: a second PDF mission runs on the
   reader the first one acquired, with no second deficit, qualification or attach.

Real installed ``pdftotext`` (poppler-utils), real bodies with per-test founder keys, a test clock (SANDBOX).
"""
from __future__ import annotations

import pytest

from greg import documents, licensing
from tests.greg_fixtures import Clock, make_body, mission
from tests.unit.test_greg_document_text import LEASE, SCOPE, needs_pdftotext, pdf_check
from tests.unit.test_greg_missions import events, run, submit

DEP5 = ("Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/\n\n"
        "Files: *\nCopyright: 2005 The poppler developers\nLicense: GPL-2+\n\n"
        "Files: data/*\nCopyright: 2024 Example\nLicense: {held}\n")


@needs_pdftotext
@pytest.mark.parametrize("held", ["AGPL-3+", "Llama-2-Community", "CC-BY-NC-4.0"])
def test_a_reader_whose_package_declares_a_held_license_waits_for_the_founder(tmp_path, monkeypatch, held):
    """Llama-2-Community fails on 083c91ea: the name was unclassified, so P0 let the binary attach."""
    monkeypatch.setattr(licensing, "system_binary",
                        lambda binary: licensing.binary_assessment("poppler-utils", DEP5.format(held=held)))
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "lease.pdf"
    lease.write_bytes(documents.write_pdf(LEASE, compress=True))
    submit(home, key, body_id, "MISSION", mission("m:lease", checks=[pdf_check(lease, "renewal term is twelve months")],
                                                  strategies=[], **SCOPE))
    missions, _ = run(home, Clock(), ticks=4)
    assert missions["m:lease"].status != "ACHIEVED"
    assert not events(home, "deficit.resolved")
    assert not [e for e in events(home, "capability.state") if e["state"] == "ATTACHED"]
    [waiting] = [e for e in events(home, "deficit.awaiting_attach") if e["capability_id"].endswith("pdftotext")]
    assert "its license needs your decision" in waiting["why"]


@needs_pdftotext
def test_a_second_pdf_mission_reuses_the_reader_the_first_acquired(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    lease, invoice = data / "lease.pdf", data / "invoice.pdf"
    lease.write_bytes(documents.write_pdf(LEASE, compress=True))
    invoice.write_bytes(documents.write_pdf([["Invoice 1042"], ["Amount due: 4,200 USD, net thirty."]], compress=True))
    submit(home, key, body_id, "MISSION", mission("m:lease", checks=[pdf_check(lease, "renewal term is twelve months")],
                                                  strategies=[], **SCOPE))
    clock = Clock()
    missions, _ = run(home, clock, ticks=4)
    assert missions["m:lease"].status == "ACHIEVED"
    before = {kind: len(events(home, kind)) for kind in ("deficit.opened", "genesis.verified", "deficit.resolved")}
    submit(home, key, body_id, "MISSION", mission("m:invoice", checks=[pdf_check(invoice, "Amount due: 4,200 USD")],
                                                  strategies=[], **SCOPE))
    missions, _ = run(home, clock, ticks=4)
    assert missions["m:invoice"].status == "ACHIEVED"
    after = {kind: len(events(home, kind)) for kind in before}
    assert after == before, (before, after)          # no second deficit, qualification or attach
    readings = [e for e in events(home, "mission.observed") if e["mission_id"] == "m:invoice"]
    assert readings and {e["capability"] for e in readings} == {"acquired.document.text.pdftotext"}
    assert all(e["passed"] for e in readings[-1:])
