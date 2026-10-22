"""GREG reads a PDF on the mission path by acquiring installed software (directive 2026-10-22).

A founder-signed mission checks a fact inside a PDF. GREG has no document reader: observing the check opens one
verified CapabilityDeficit. Capability Genesis finds the installed ``pdftotext`` (poppler-utils), qualifies it on
a frozen oracle of PDFs GREG writes itself (greg/documents.py, no shared code with poppler), reads its license
from the OS package's DEP-5 copyright file, attaches it under the mission's signed read-only scope and the mission
closes on the document's own words. Nothing is installed. In-process Body with a test clock (SANDBOX); the
founder key is a per-test key.
"""
from __future__ import annotations

import pytest

from greg import documents, genesis as genesis_mod, licensing
from greg.body import Body
from tests.greg_fixtures import Clock, make_body, mission, note_check
from tests.unit.test_greg_missions import events, run, submit

pytestmark = pytest.mark.skipif(genesis_mod.installed_binary("pdftotext") is None,
                                reason="pdftotext not installed on this body; genesis would correctly escalate")

LEASE = [["Residential lease between the parties."], ["The renewal term is twelve months", "with notice due net thirty."]]
SCOPE = dict(capabilities=["fs.read", "acquired.document.text.*"], ceiling="read_only", auto_attach=True)


def pdf_check(path, phrase):
    return {"check_id": "states", "description": f"{path.name} states {phrase!r}",
            "sensor": {"function": "document.text", "params": {"path": str(path)}, "target": f"fs:{path.name}"},
            "predicate": {"op": "contains", "field": "text", "value": phrase}}


def test_a_mission_checks_a_fact_inside_a_pdf_by_acquiring_installed_software(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "lease.pdf"
    lease.write_bytes(documents.write_pdf(LEASE, compress=True))
    submit(home, key, body_id, "MISSION", mission("m:lease", checks=[pdf_check(lease, "renewal term is twelve months")],
                                                  strategies=[], **SCOPE))
    missions, _ = run(home, Clock(), ticks=4)
    assert missions["m:lease"].status == "ACHIEVED"
    [opened] = events(home, "deficit.opened")
    assert opened["function"] == "document.text"
    [resolved] = events(home, "deficit.resolved")
    assert resolved["capability_id"] == "acquired.document.text.pdftotext"
    [verified] = [e for e in events(home, "genesis.verified") if e["capability_id"].endswith("pdftotext")]
    assert verified["passed"] and verified["report"]["failures"] == [] and verified["report"]["cases"] == 6
    with Body(home) as body:
        manifest = body.registry.manifests["acquired.document.text.pdftotext"]
    license_ = manifest.provenance.get("license_assessment")
    if licensing.system_binary(genesis_mod.installed_binary("pdftotext")) is not None:     # a dpkg body
        assert license_["verdict"] == "CLEARED_WITH_OBLIGATIONS" and license_["class"] == licensing.STRONG_COPYLEFT
        assert "GPL" in manifest.provenance["license"]


def test_a_pdf_that_does_not_state_the_fact_does_not_close_the_mission(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "lease.pdf"
    lease.write_bytes(documents.write_pdf([["The renewal term is six months."]], compress=True))
    submit(home, key, body_id, "MISSION", mission("m:lease", checks=[pdf_check(lease, "renewal term is twelve months")],
                                                  strategies=[], **SCOPE))
    missions, _ = run(home, Clock(), ticks=4)
    assert missions["m:lease"].status != "ACHIEVED"
    assert events(home, "deficit.resolved")              # the reader was acquired; the document says otherwise


def test_the_baseline_reads_bytes_and_cannot_see_the_words_of_a_compressed_pdf(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "lease.pdf"
    lease.write_bytes(documents.write_pdf(LEASE, compress=True))
    submit(home, key, body_id, "MISSION", mission("m:raw", checks=[note_check("raw", lease, "renewal term")],
                                                  strategies=[], capabilities=["fs.read"], ceiling="read_only"))
    missions, _ = run(home, Clock(), ticks=4)
    assert missions["m:raw"].status != "ACHIEVED"
    [observed] = events(home, "mission.observed")[-1:]
    assert observed["capability"] == "fs.read" and observed["passed"] is False   # it read the bytes; no words


def test_a_pdf_outside_the_read_roots_is_refused_by_the_acquired_reader(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    secret = outside / "secret.pdf"
    secret.write_bytes(documents.write_pdf(LEASE))
    submit(home, key, body_id, "MISSION", mission("m:out", checks=[pdf_check(secret, "renewal term")],
                                                  strategies=[], **SCOPE))
    missions, _ = run(home, Clock(), ticks=4)
    assert missions["m:out"].status != "ACHIEVED"
    assert any("outside permitted roots" in e["detail"] for e in events(home, "mission.observed"))


def test_the_oracle_rejects_a_reader_that_drops_words(tmp_path, monkeypatch):
    monkeypatch.setitem(genesis_mod.PARSERS, "words", lambda out: " ".join(out.split()[:-1]))
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "lease.pdf"
    lease.write_bytes(documents.write_pdf(LEASE, compress=True))
    submit(home, key, body_id, "MISSION", mission("m:lease", checks=[pdf_check(lease, "renewal term is twelve months")],
                                                  strategies=[], **SCOPE))
    missions, _ = run(home, Clock(), ticks=4)
    assert missions["m:lease"].status != "ACHIEVED"
    [verified] = [e for e in events(home, "genesis.verified") if e["capability_id"].endswith("pdftotext")]
    assert not verified["passed"] and verified["report"]["failures"]


# -- licenses of installed system binaries (DEP-5) ------------------------------------------------------------

DEP5 = """Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: x

Files: *
Copyright: someone
License: {files}

License: GPL-2
 The text of a license definition paragraph does not apply by itself.
"""


@pytest.mark.parametrize("files, cls", [
    ("GPL-2 or GPL-3", licensing.STRONG_COPYLEFT), ("Expat", licensing.PERMISSIVE),
    ("GPL-3+ and BSD-4-clause-UC", licensing.STRONG_COPYLEFT), ("LGPL-2.1+ or Expat", licensing.PERMISSIVE),
    ("AGPL-3+", licensing.NETWORK_COPYLEFT), ("GPL-2+ with OpenSSL exception", licensing.STRONG_COPYLEFT),
    ("Acme-Proprietary", licensing.UNKNOWN)])
def test_a_dep5_file_is_read_per_files_paragraph(files, cls):
    assert licensing.dep5(DEP5.format(files=files))["class"] == cls


def test_a_copyright_file_that_is_not_dep5_is_not_interpreted():
    assert licensing.dep5("This package was debianized by someone.\nLicense: GPL") is None


def test_a_binary_is_held_only_on_a_known_uncleared_license():
    class Manifest:
        provider = "installed:/usr/bin/tool"

        def __init__(self, cls):
            self.provenance = {"license_assessment": {"class": cls, "auto_attach": cls == licensing.PERMISSIVE,
                                                      "reason": cls}}
    assert licensing.attach_check(Manifest(licensing.NOT_OPEN))[0] is False
    assert licensing.attach_check(Manifest(licensing.NETWORK_COPYLEFT))[0] is False
    assert licensing.attach_check(Manifest(licensing.UNKNOWN))[0] is True        # undeterminable: prior behaviour
    assert licensing.attach_check(Manifest(licensing.STRONG_COPYLEFT))[0] is True


def test_on_a_body_without_dpkg_the_card_says_the_license_was_not_readable(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert licensing.system_binary("/usr/bin/pdftotext") is None
    assert "not readable" in genesis_mod._binary_license("/usr/bin/pdftotext")["license"]
