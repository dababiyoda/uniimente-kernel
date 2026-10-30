"""An acquired binary keeps its founder decisions and its companions across a restart (#201 review GATE-1, GATE-2/DOC-8).

GATE-1: a binary the founder DETACHED, then changed (or briefly missing) at a restart, was re-registered QUARANTINED,
so the next scoped mission's recovery re-attached it "by founder-signed mission auto_attach" and the founder's
detach was undone. GATE-2/DOC-8: a restart rebuilt the reader without its pinned companion (pdfimages), so no page
was vouched for again and a "never states" check could not close after a restart. In-process Body with a test
clock (SANDBOX); the founder key is a per-test key.
"""
from __future__ import annotations

import shutil

import pytest

from greg import documents, genesis as genesis_mod
from greg.body import Body
from tests.greg_fixtures import Clock, make_body, mission
from tests.unit.test_greg_document_text import SCOPE, found_check, needs_pdftotext, pdf_check
from tests.unit.test_greg_missions import events, run, submit

READER = "acquired.document.text.pdftotext"


def _copies(tmp_path, monkeypatch):
    """Serve pdftotext and pdfimages from copies this test may change, as an OS upgrade would."""
    served = {}
    for name in ("pdftotext", "pdfimages"):
        real = genesis_mod.installed_binary(name)
        if real is None:
            pytest.skip(f"{name} not installed on this body")
        copy = tmp_path / "bin" / name
        copy.parent.mkdir(exist_ok=True)
        shutil.copy2(real, copy)
        served[name] = copy
    real_installed = genesis_mod.installed_binary
    monkeypatch.setattr(genesis_mod, "installed_binary",
                        lambda name, *a, **k: str(served[name]) if name in served else real_installed(name, *a, **k))
    return served


def _states(home):
    return [(e["capability_id"], e["state"], e.get("by")) for e in events(home, "capability.state")
            if e["capability_id"] == READER]


@needs_pdftotext
@pytest.mark.parametrize("change", ["altered", "missing_then_restored"])
def test_a_founder_detach_survives_a_restart_whatever_happened_to_the_binary(tmp_path, monkeypatch, change):
    served = _copies(tmp_path, monkeypatch)
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "lease.pdf"
    lease.write_bytes(documents.write_pdf([["The renewal term is twelve months."]], compress=True))
    submit(home, key, body_id, "MISSION", mission("m:first", checks=[pdf_check(lease, "renewal term")],
                                                  strategies=[], **SCOPE))
    clock = Clock()
    missions, _ = run(home, clock, ticks=4)
    assert missions["m:first"].status == "ACHIEVED"
    submit(home, key, body_id, "CAPABILITY_DETACH", {"capability_id": READER})
    run(home, clock, ticks=1)
    original = served["pdftotext"].read_bytes()
    if change == "altered":
        served["pdftotext"].write_bytes(original + b"\0")
    else:
        served["pdftotext"].unlink()
        run(home, clock, ticks=1)                                    # one boot with the binary missing
        served["pdftotext"].write_bytes(original)
        served["pdftotext"].chmod(0o755)
    submit(home, key, body_id, "MISSION", mission("m:second", checks=[pdf_check(lease, "renewal term")],
                                                  strategies=[], **SCOPE))
    run(home, clock, ticks=4)
    with Body(home) as body:
        assert body.registry.state[READER] == "DETACHED"
    after = _states(home)[_states(home).index((READER, "DETACHED", "founder command")) + 1:]
    assert not [s for s in after if s[1] == "ATTACHED"], after        # never re-attached behind the founder
    assert not [s for s in after if s[1] == "QUARANTINED"], after


@needs_pdftotext
def test_a_restarted_reader_still_runs_its_companion_and_proves_absence(tmp_path):
    if genesis_mod.installed_binary("pdfimages") is None:
        pytest.skip("pdfimages not installed on this body")
    home, key, body_id, data = make_body(tmp_path)
    first, second = data / "a.pdf", data / "b.pdf"
    for f in (first, second):
        f.write_bytes(documents.write_pdf([["The renewal term is twelve months."]], compress=True))
    submit(home, key, body_id, "MISSION", mission("m:first", checks=[found_check(first, "terminate", expected=False)],
                                                  strategies=[], **SCOPE))
    clock = Clock()
    missions, _ = run(home, clock, ticks=4)
    assert missions["m:first"].status == "ACHIEVED"
    # run() opens a fresh Body each time: this mission is served by the capability restore() rebuilt
    submit(home, key, body_id, "MISSION", mission("m:second", checks=[found_check(second, "terminate", expected=False)],
                                                  strategies=[], **SCOPE))
    missions, _ = run(home, clock, ticks=4)
    assert missions["m:second"].status == "ACHIEVED"
    with Body(home) as body:
        output = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                  if (r.payload.get("result") or {}).get("output", {}).get("phrase")][-1]
    assert output["complete"] is True and output["found"] is False and output["image_check"] != "unavailable on this body"


@needs_pdftotext
def test_a_changed_companion_quarantines_the_reader_at_restart(tmp_path, monkeypatch):
    served = _copies(tmp_path, monkeypatch)
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "lease.pdf"
    lease.write_bytes(documents.write_pdf([["The renewal term is twelve months."]], compress=True))
    submit(home, key, body_id, "MISSION", mission("m:first", checks=[pdf_check(lease, "renewal term")],
                                                  strategies=[], **SCOPE))
    missions, _ = run(home, Clock(), ticks=4)
    assert missions["m:first"].status == "ACHIEVED"
    served["pdfimages"].write_bytes(served["pdfimages"].read_bytes() + b"\0")
    with Body(home) as body:
        assert body.registry.state[READER] == "QUARANTINED"
