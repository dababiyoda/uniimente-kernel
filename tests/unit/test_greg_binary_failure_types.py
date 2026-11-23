"""What an acquired binary's failure means (#201 review DOC-3, GATE-5, GATE-6, DOC-10).

DOC-3: pdftotext exits 1 on a file that is not a PDF, and that exit was read as a fault of the reader, so bad input
quarantined it (and led into DOC-2's crash-loop). GATE-5: a changed companion raised an untyped refusal, so the
reader was never quarantined or re-formed and refused every read. GATE-6: the ``--version`` probe ran with no
ceiling and its whole first line was stored. DOC-10: a binary that ran past its wall clock escaped as
``TimeoutExpired``, filed as an executor exception with an unknown outcome. In-process Body with a test clock
(SANDBOX); the founder key is a per-test key.
"""
from __future__ import annotations

import hashlib
import os
import signal
import stat
import types

import pytest

from greg import documents, genesis as genesis_mod, mechanisms
from greg.body import Body
from greg.capabilities import CapabilityError, CapabilityManifest, InvocationContext
from tests.greg_fixtures import Clock, make_body, mission
from tests.unit.test_greg_document_text import SCOPE, needs_pdftotext, pdf_check
from tests.unit.test_greg_missions import events, run, submit

READER = types.SimpleNamespace(provider="installed:/usr/bin/pdftotext", binaries=["/usr/bin/pdftotext"])


def _script(tmp_path, name, body):
    path = tmp_path / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


@pytest.mark.parametrize("returncode, stderr, failure_class", [
    (1, "Syntax Error: Couldn't find trailer dictionary", None),     # not a PDF: the world
    (99, "", None),                                                   # no pages
    (-signal.SIGSEGV, "", None),                                     # crashed on this input
    (-signal.SIGABRT, "terminate called after throwing an instance of 'std::bad_alloc'", "budget_exceeded"),
    (-signal.SIGKILL, "", "budget_exceeded"),
    (-signal.SIGXCPU, "", "budget_exceeded"),
])
def test_an_exit_is_typed_by_what_it_says_about_the_binary(returncode, stderr, failure_class):
    refusal = genesis_mod._exit_refusal("pdftotext", returncode, stderr)
    assert refusal.failure_class == failure_class
    assert not genesis_mod.is_capability_fault(READER, "capability refused: " + str(refusal), refusal.failure_class)


@needs_pdftotext
def test_unreadable_input_never_quarantines_the_reader(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    good, junk = data / "lease.pdf", data / "junk.pdf"
    good.write_bytes(documents.write_pdf([["The renewal term is twelve months."]], compress=True))
    junk.write_bytes(b"%PDF-1.4\nthis is not a pdf at all\n%%EOF\n")
    submit(home, key, body_id, "MISSION", mission("m:good", checks=[pdf_check(good, "renewal term")],
                                                  strategies=[], **SCOPE))
    clock = Clock()
    missions, _ = run(home, clock, ticks=4)
    assert missions["m:good"].status == "ACHIEVED"
    submit(home, key, body_id, "MISSION", mission("m:junk", checks=[pdf_check(junk, "renewal term")],
                                                  strategies=[], **SCOPE))
    run(home, clock, ticks=8, step=900.0)
    run(home, clock, ticks=2, step=900.0)                         # and across a restart
    states = [e["state"] for e in events(home, "capability.state")
              if e["capability_id"] == "acquired.document.text.pdftotext"]
    assert "QUARANTINED" not in states, states
    with Body(home) as body:
        assert body.registry.state["acquired.document.text.pdftotext"] == "ATTACHED"


def test_a_changed_companion_is_a_fault_of_the_capability(tmp_path):
    companion = _script(tmp_path, "pdfimages", "echo page\n")
    digest = hashlib.sha256(open(companion, "rb").read()).hexdigest()
    with open(companion, "a") as f:
        f.write("# changed\n")
    manifest = CapabilityManifest.__new__(CapabilityManifest)
    object.__setattr__(manifest, "provenance", {"companions": {"pdfimages": {"binary": companion, "binary_sha256": digest}}})
    ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path,), secrets=None, manifest=manifest)
    candidate = genesis_mod.Candidate("pdftotext", ("{binary}", "{file}", "-"), "words",
                                      companions=(("pdfimages", ("{binary}", "-list", "{file}")),))
    with pytest.raises(CapabilityError) as raised:
        genesis_mod._companion_outputs(candidate, tmp_path / "x.pdf", ctx)
    assert raised.value.failure_class == "executor_error"
    assert genesis_mod.is_capability_fault(READER, "capability refused: " + str(raised.value),
                                           raised.value.failure_class)


def test_a_binary_past_its_wall_clock_is_a_typed_transient_refusal(tmp_path, monkeypatch):
    monkeypatch.setattr(genesis_mod, "BINARY_SECONDS", 1)
    slow = _script(tmp_path, "slow", "sleep 20\n")
    (tmp_path / "ws").mkdir()
    with pytest.raises(CapabilityError) as raised:
        genesis_mod._run_bounded([slow], tmp_path / "ws", "slow")
    assert raised.value.failure_class == "transient" and "did not finish within 1s" in str(raised.value)


def test_the_version_probe_is_bounded_and_its_line_truncated(tmp_path, monkeypatch):
    spec = genesis_mod.CATALOG["text.wordcount"]["candidates"][0]
    long_line = _script(tmp_path, "wc-long", "head -c 5000 /dev/zero | tr '\\000' x; echo\n")
    m = genesis_mod.Genesis._manifest_for(object(), "text.wordcount", spec, long_line, "d")
    assert len(m.provenance["version"]) == genesis_mod.VERSION_LINE
    flood = _script(tmp_path, "wc-flood", f"head -c {mechanisms.MAX_OUTPUT + 1024} /dev/zero | tr '\\000' x\n")
    m = genesis_mod.Genesis._manifest_for(object(), "text.wordcount", spec, flood, "d")
    assert m.provenance["version"].startswith("unknown (") and len(m.provenance["version"]) <= 220
    monkeypatch.setattr(genesis_mod, "BINARY_SECONDS", 1)
    endless = _script(tmp_path, "wc-endless", "sleep 20\n")
    with pytest.raises(CapabilityError) as raised:                  # never TimeoutExpired out of Body.tick
        genesis_mod.Genesis._manifest_for(object(), "text.wordcount", spec, endless, "d")
    assert raised.value.failure_class == "transient"


@needs_pdftotext
def test_text_and_image_listing_come_from_one_snapshot_of_the_input(tmp_path, monkeypatch):
    """DOC-11: the file is replaced after pdftotext read it and before pdfimages runs. Both must have read the
    same bytes: the stamped scan's image still counts, so absence is not proved."""
    from tests.unit.test_greg_document_text import _adapter
    path = tmp_path / "in.pdf"
    path.write_bytes(documents.write_pdf([documents.Stamped("BATES-000002")]))
    real = genesis_mod._companion_outputs

    def swapped(candidate, file, ctx):
        path.write_bytes(documents.write_pdf([["BATES-000002"]]))       # a clean text page, no image
        return real(candidate, file, ctx)
    monkeypatch.setattr(genesis_mod, "_companion_outputs", swapped)
    spec = genesis_mod.CATALOG["document.text"]["candidates"][0]
    adapter = genesis_mod.catalog_adapter("document.text", spec, genesis_mod.installed_binary("pdftotext"))
    manifest = CapabilityManifest.__new__(CapabilityManifest)
    pdfimages = genesis_mod.installed_binary("pdfimages")
    object.__setattr__(manifest, "provenance", {"companions": {"pdfimages": {
        "binary": pdfimages, "binary_sha256": hashlib.sha256(open(pdfimages, "rb").read()).hexdigest()}}})
    ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path,), secrets=None, manifest=manifest)
    out = adapter({"path": str(path), "phrase": "automatic renewal"}, ctx)
    assert out["complete"] is False and out["found"] is None and out["input_sha256"]
    assert not list((tmp_path / "ws").glob(".in-*")), "the snapshot is removed after the run"


def test_a_reader_with_companions_refuses_what_is_not_a_regular_file(tmp_path):
    fifo = tmp_path / "pipe.pdf"
    os.mkfifo(fifo)
    (tmp_path / "ws").mkdir()
    with pytest.raises(CapabilityError, match="not a regular file"):
        genesis_mod._snapshot(fifo, tmp_path / "ws")
