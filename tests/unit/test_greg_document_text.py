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

import os

# Only the tests that run the acquired reader need poppler. Where CI provisions it (GREG_REQUIRE_PDFTOTEXT=1), a
# missing binary fails instead of skipping, so the mutation gate never passes on skipped tests.
if os.environ.get("GREG_REQUIRE_PDFTOTEXT") == "1" and genesis_mod.installed_binary("pdftotext") is None:
    raise RuntimeError("GREG_REQUIRE_PDFTOTEXT=1 but pdftotext is not installed")
needs_pdftotext = pytest.mark.skipif(genesis_mod.installed_binary("pdftotext") is None,
                                     reason="pdftotext not installed on this body; genesis would correctly escalate")

LEASE = [["Residential lease between the parties."], ["The renewal term is twelve months", "with notice due net thirty."]]
SCOPE = dict(capabilities=["fs.read", "acquired.document.text.*"], ceiling="read_only", auto_attach=True)


def pdf_check(path, phrase):
    return {"check_id": "states", "description": f"{path.name} states {phrase!r}",
            "sensor": {"function": "document.text", "params": {"path": str(path)}, "target": f"fs:{path.name}"},
            "predicate": {"op": "contains", "field": "text", "value": phrase}}


@needs_pdftotext
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
    assert verified["passed"] and verified["report"]["failures"] == [] and verified["report"]["cases"] == 8
    with Body(home) as body:
        manifest = body.registry.manifests["acquired.document.text.pdftotext"]
    license_ = manifest.provenance.get("license_assessment")
    if licensing.system_binary(genesis_mod.installed_binary("pdftotext")) is not None:     # a dpkg body
        assert license_["verdict"] == "CLEARED_WITH_OBLIGATIONS" and license_["class"] == licensing.STRONG_COPYLEFT
        assert "GPL" in manifest.provenance["license"]


@needs_pdftotext
def test_a_pdf_that_does_not_state_the_fact_does_not_close_the_mission(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "lease.pdf"
    lease.write_bytes(documents.write_pdf([["The renewal term is six months."]], compress=True))
    submit(home, key, body_id, "MISSION", mission("m:lease", checks=[pdf_check(lease, "renewal term is twelve months")],
                                                  strategies=[], **SCOPE))
    missions, _ = run(home, Clock(), ticks=4)
    assert missions["m:lease"].status != "ACHIEVED"
    assert events(home, "deficit.resolved")              # the reader was acquired; the document says otherwise


@needs_pdftotext
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


@needs_pdftotext
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


@needs_pdftotext
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


# -- review of bd7e3f9 (separate agent, same session): each test below failed or was missing before its fix -----

def _long_pdf(tail_line: str) -> bytes:
    filler = [[" ".join(["proof", "settlement", "notice", "delivery", "party", "shall", "net", "due"])] * 40] * 8
    return documents.write_pdf(filler + [[tail_line]], compress=True)     # about 18 KiB of words before the tail


def found_check(path, phrase, expected=True):
    return {"check_id": "found", "description": f"{path.name} {'states' if expected else 'never states'} {phrase!r}",
            "sensor": {"function": "document.text", "params": {"path": str(path), "phrase": phrase},
                       "target": f"fs:{path.name}"},
            "predicate": {"op": "equals", "field": "found", "value": expected}}


@needs_pdftotext
def test_a_phrase_past_the_receipt_prefix_is_found_over_the_whole_document(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "long.pdf"
    lease.write_bytes(_long_pdf("The renewal term is twelve months."))
    submit(home, key, body_id, "MISSION", mission("m:long", checks=[found_check(lease, "renewal term is twelve months")],
                                                  strategies=[], **SCOPE))
    missions, _ = run(home, Clock(), ticks=4)
    assert missions["m:long"].status == "ACHIEVED"
    [observed] = [e for e in events(home, "mission.observed") if e["mission_id"] == "m:long"][-1:]
    assert observed["passed"] is True


@needs_pdftotext
def test_a_forbidden_phrase_past_the_receipt_prefix_is_not_missed(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "long.pdf"
    lease.write_bytes(_long_pdf("Either party may terminate without notice."))
    submit(home, key, body_id, "MISSION", mission("m:never", checks=[found_check(lease, "terminate without notice",
                                                                                 expected=False)],
                                                  strategies=[], **SCOPE))
    missions, _ = run(home, Clock(), ticks=4)
    assert missions["m:never"].status != "ACHIEVED"                   # the clause is there, after 16 KiB


@needs_pdftotext
def test_an_oversized_extraction_is_refused(tmp_path, monkeypatch):
    from greg import mechanisms
    monkeypatch.setattr(mechanisms, "MAX_OUTPUT", 64)
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "lease.pdf"
    lease.write_bytes(documents.write_pdf(LEASE * 4))
    submit(home, key, body_id, "MISSION", mission("m:big", checks=[pdf_check(lease, "renewal term")],
                                                  strategies=[], **SCOPE))
    missions, _ = run(home, Clock(), ticks=4)
    assert missions["m:big"].status != "ACHIEVED"
    [verified] = [e for e in events(home, "genesis.verified") if e["capability_id"].endswith("pdftotext")]
    assert not verified["passed"] and verified["report"]["failures"]      # refused at qualification, not trusted


def test_a_network_copyleft_term_holds_a_binary_whatever_else_is_unclassified():
    text = ("Format: x\n\nFiles: *\nCopyright: a\nLicense: AGPL-3+\n\n"
            "Files: doc/*\nCopyright: b\nLicense: Some-Unknown-Doc-License\n")
    parsed = licensing.dep5(text)
    assert parsed["class"] == licensing.UNKNOWN and licensing._held_terms(parsed["terms"])

    class Manifest:
        provider = "installed:/usr/bin/tool"
        provenance = {"license_assessment": {"class": parsed["class"], "parts": [{"terms": parsed["terms"]}],
                                             "reason": "AGPL-3+"}}
    assert licensing.attach_check(Manifest())[0] is False


@pytest.mark.parametrize("name, cls", [
    ("AGPL-3.0-or-later", licensing.NETWORK_COPYLEFT), ("AGPL-3.0+", licensing.NETWORK_COPYLEFT),
    ("SSPL-1", licensing.NOT_OPEN), ("BUSL-1.1", licensing.NOT_OPEN), ("non-free", licensing.NOT_OPEN),
    ("GPL-1+ or Artistic, and BSD-3-clause", licensing.WEAK_COPYLEFT)])
def test_dep5_reads_spdx_spellings_not_open_names_and_comma_precedence(name, cls):
    assert licensing._debian_class(name) == cls


@needs_pdftotext
def test_an_unclassified_binary_card_says_it_keeps_prior_behaviour():
    a = licensing.system_binary(genesis_mod.installed_binary("pdftotext"))
    if a is not None:
        assert a["auto_attach"] is True and a["held"] is False


# -- directive of 2026-10-22, section VI-VIII: incomplete extraction and containment ------------------------------
# Each test below fails on fe82005: a scanned page was read as "phrase absent", and a binary's output was fully
# buffered before its size was checked, with no memory ceiling.

SCANNED = [["Residential lease between the parties."], documents.SCAN, ["Signed by both parties."]]


@needs_pdftotext
def test_a_scanned_page_never_proves_a_phrase_absent(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "scanned.pdf"
    lease.write_bytes(documents.write_pdf(SCANNED, compress=True))
    submit(home, key, body_id, "MISSION", mission("m:scan", checks=[found_check(lease, "terminate without notice",
                                                                                expected=False)],
                                                  strategies=[], **SCOPE))
    missions, _ = run(home, Clock(), ticks=4)
    assert missions["m:scan"].status != "ACHIEVED"          # page 2 is pixels; the clause could be there
    with Body(home) as body:
        receipt = [r for r in body.ledger.by_type("receipt")
                   if (r.payload.get("result") or {}).get("output", {}).get("phrase")][-1]
    output = receipt.payload["result"]["output"]
    assert output["complete"] is False and output["pages_without_text"] == [2] and output["found"] is None


@needs_pdftotext
def test_a_phrase_found_on_a_text_page_of_a_partly_scanned_pdf_is_still_found(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "scanned.pdf"
    lease.write_bytes(documents.write_pdf(SCANNED, compress=True))
    submit(home, key, body_id, "MISSION", mission("m:hit", checks=[found_check(lease, "Signed by both parties")],
                                                  strategies=[], **SCOPE))
    missions, _ = run(home, Clock(), ticks=4)
    seen = [(e["passed"], e["detail"][:160]) for e in events(home, "mission.observed")]
    checked = [(e["capability_id"], e["passed"], e["report"].get("failures")) for e in events(home, "genesis.verified")]
    assert missions["m:hit"].status == "ACHIEVED", (seen, checked)    # a hit on a page that has text is proof


@needs_pdftotext
def test_the_oracle_rejects_a_reader_that_claims_a_scanned_page_was_read(tmp_path, monkeypatch):
    monkeypatch.setattr(documents, "coverage", lambda raw, images=None: {"pages": 1, "pages_without_text": [],
                                                                          "complete": True})
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "lease.pdf"
    lease.write_bytes(documents.write_pdf(LEASE, compress=True))
    submit(home, key, body_id, "MISSION", mission("m:lease", checks=[pdf_check(lease, "renewal term is twelve months")],
                                                  strategies=[], **SCOPE))
    missions, _ = run(home, Clock(), ticks=4)
    assert missions["m:lease"].status != "ACHIEVED"
    [verified] = [e for e in events(home, "genesis.verified") if e["capability_id"].endswith("pdftotext")]
    assert not verified["passed"]
    assert {f["case"] for f in verified["report"]["failures"]} == {"case3.pdf", "case6.pdf", "case7.pdf"}


def _adapter(tmp_path, binary, argv):
    from greg.capabilities import CapabilityManifest, InvocationContext
    candidate = genesis_mod.Candidate("probe", argv, "words")
    adapter = genesis_mod.catalog_adapter("document.text", candidate, binary)
    target = tmp_path / "in.pdf"
    target.write_bytes(b"%PDF-1.4\n")
    ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path,), secrets=None,
                            manifest=CapabilityManifest.__new__(CapabilityManifest))
    object.__setattr__(ctx.manifest, "provenance", {})
    return lambda: adapter({"path": str(target)}, ctx), tmp_path / "ws"


def test_an_oversized_output_is_stopped_at_the_ceiling_without_being_buffered(tmp_path):
    import sys
    import time
    from greg.capabilities import CapabilityError
    flood = "import sys, time; sys.stdout.buffer.write(b'x' * (8 << 20)); sys.stdout.flush(); time.sleep(25)"
    call, workspace = _adapter(tmp_path, sys.executable, ("{binary}", "-I", "-c", flood))
    started = time.monotonic()
    with pytest.raises(CapabilityError, match="never buffered"):
        call()
    assert time.monotonic() - started < 20                  # killed at 4 MiB, not after the writer finished
    assert not any(workspace.glob(".out-*"))                # the spool is removed


def test_an_acquired_binary_runs_under_a_memory_ceiling_and_reports_its_stderr(tmp_path):
    import sys
    from greg.capabilities import CapabilityError
    if not sys.platform.startswith("linux"):
        pytest.skip("RLIMIT_AS is enforced on Linux")
    probe = "import resource,sys; print(resource.getrlimit(resource.RLIMIT_AS)[0]); sys.stderr.write('done-x')"
    call, _ = _adapter(tmp_path, sys.executable, ("{binary}", "-I", "-c", probe))
    assert call()["text"] == str(genesis_mod.BINARY_MEMORY)
    failing, _ = _adapter(tmp_path, sys.executable, ("{binary}", "-I", "-c", "import sys; sys.exit('bad-pdf-x')"))
    with pytest.raises(CapabilityError, match="bad-pdf-x"):
        failing()


# -- independent review of f929246 (session_01Xt7KBAgrod4jhY9uDnsDkR, #201): each test below fails on 09b60e2 -----

STAMPED = [["Residential lease between the parties."], documents.Stamped("BATES-000002"), ["Signed by both parties."]]


@needs_pdftotext
def test_a_stamped_scan_never_proves_a_phrase_absent(tmp_path):
    # finding 1: a Bates stamp gave the scanned page text, so it counted as read and absence was "proved"
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "stamped.pdf"
    lease.write_bytes(documents.write_pdf(STAMPED, compress=True))
    submit(home, key, body_id, "MISSION", mission("m:stamp", checks=[found_check(lease, "terminate without notice",
                                                                                 expected=False)],
                                                  strategies=[], **SCOPE))
    missions, _ = run(home, Clock(), ticks=4)
    assert missions["m:stamp"].status != "ACHIEVED"
    with Body(home) as body:
        receipt = [r for r in body.ledger.by_type("receipt")
                   if (r.payload.get("result") or {}).get("output", {}).get("phrase")][-1]
    output = receipt.payload["result"]["output"]
    assert output["pages_without_text"] == [] and output["pages_with_images"] == [2]
    assert output["complete"] is False and output["found"] is None


def test_without_an_image_listing_no_page_is_vouched_for():
    raw = "one two\f three four\f"
    assert documents.coverage(raw)["complete"] is False
    assert documents.coverage(raw)["image_check"] == "unavailable on this body"
    listing = "page   num  type\n------------------\n"
    assert documents.coverage(raw, listing)["complete"] is True
    assert documents.coverage(raw, listing + "   2     0 image\n")["pages_with_images"] == [2]


def test_a_hit_is_declared_decided_and_a_miss_is_not():
    # finding 2b, the reader's side: a found phrase holds however much more could have been read
    hit = documents.find_phrase("a b c", {"phrase": "b"}, "a b c\f\f")
    assert hit["found"] is True and hit["complete"] is False and hit["decided"] == ["found"]
    miss = documents.find_phrase("a b c", {"phrase": "z"}, "a b c\f\f")
    assert miss["found"] is None and "decided" not in miss


@needs_pdftotext
def test_a_body_without_pdfimages_still_reads_but_never_proves_absence(tmp_path, monkeypatch):
    real = genesis_mod.installed_binary
    monkeypatch.setattr(genesis_mod, "installed_binary", lambda name, *a, **k: None if name == "pdfimages"
                        else real(name, *a, **k))
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "lease.pdf"
    lease.write_bytes(documents.write_pdf(LEASE, compress=True))
    submit(home, key, body_id, "MISSION", mission("m:both", checks=[
        found_check(lease, "renewal term is twelve months"), {**found_check(lease, "terminate", expected=False),
                                                              "check_id": "never"}], strategies=[], **SCOPE))
    missions, _ = run(home, Clock(), ticks=4)
    assert missions["m:both"].status != "ACHIEVED"            # the absence half cannot be proved
    observed = {e["check_id"]: e["passed"] for e in events(home, "mission.observed")}
    assert observed["found"] is True and observed["never"] is False


def test_the_qualification_report_states_the_ceilings_applied():
    report = genesis_mod.ceilings()
    assert report["output_bytes"] == genesis_mod.mechanisms.MAX_OUTPUT
    assert report["memory_enforced"] is __import__("sys").platform.startswith("linux")


def test_a_held_companion_license_holds_the_binary():
    class M:
        capability_id, provider = "acquired.document.text.pdftotext", "installed:/usr/bin/pdftotext"
        provenance = {"license_assessment": {"held": False, "class": licensing.STRONG_COPYLEFT, "parts": []},
                      "companions": {"pdfimages": {"license_assessment": {
                          "held": True, "class": licensing.NETWORK_COPYLEFT, "parts": [], "reason": "AGPL companion"}}}}
    assert licensing.attach_check(M()) == (False, "AGPL companion")


def test_a_writer_that_honours_sigxfsz_is_killed_at_the_ceiling(tmp_path):
    # finding 4: the Python flood writer ignores SIGXFSZ, so the kill path was never exercised
    from greg.capabilities import CapabilityError
    yes = genesis_mod.installed_binary("yes")
    if yes is None:
        pytest.skip("no yes(1) on this body")
    call, workspace = _adapter(tmp_path, yes, ("{binary}",))
    with pytest.raises(CapabilityError, match="killed at the ceiling by SIGXFSZ"):
        call()
    assert not any(workspace.glob(".out-*"))


@pytest.mark.skipif(not __import__("sys").platform.startswith("linux"), reason="/proc/self/fd is Linux")
def test_a_binary_that_swaps_its_spool_file_is_refused(tmp_path):
    # finding 3: the parent read its spool file by path, through a link the binary planted (/dev/zero: unbounded)
    import sys
    from greg.capabilities import CapabilityError
    swap = "import os; p = os.readlink('/proc/self/fd/1'); os.unlink(p); os.symlink('/dev/zero', p)"
    call, _ = _adapter(tmp_path, sys.executable, ("{binary}", "-I", "-c", swap))
    with pytest.raises(CapabilityError, match="spool file .* was replaced"):
        call()
    fifo = "import os; p = os.readlink('/proc/self/fd/1'); os.unlink(p); os.mkfifo(p)"
    call, _ = _adapter(tmp_path, sys.executable, ("{binary}", "-I", "-c", fifo))
    with pytest.raises(CapabilityError, match="no longer a regular file"):
        call()
