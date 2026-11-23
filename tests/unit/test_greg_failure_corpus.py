"""S17.A1: every input that broke a formed capability becomes a permanent regression vector for its function.

Before this, only the very next builder candidate after a self-repair replayed the breaking input, and it re-read the
original file at rebuild time: once that file changed, or the next re-formation had a different cause (a tampered
source quarantined at restart), a candidate with the same latent bug was registered again. Now the breaking bytes
are kept in the body's own content-addressed store when the capability is quarantined, and every later candidate
for the function, on every file-reading route, in any mission, after any restart, must run cleanly on them.
"""
import hashlib
import json

import pytest

from greg import builders, genesis as genesis_mod
from greg.body import Body
from greg.capabilities import CapabilityError
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_genesis_builder import FUNCTION, GOOD
from tests.unit.test_greg_self_repair import BUGGY, _events, _holding, _ticks

LONG = "- [x] a finished step with a longer description\n" * 12


def _break_and_repair(tmp_path, builder):
    """Form the function with BUGGY, grow the input past its bug, let the two-strike repair re-form it."""
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _holding(data)))
    clock = Clock()
    body = Body(home, clock=clock, builder=builder).open()
    body.boot()
    _ticks(body, clock, 4, 30)
    doc = data / "FIRST_MISSION.md"
    doc.write_text(doc.read_text() + LONG)
    breaking = doc.read_bytes()
    states = [r["state"] for r in _ticks(body, clock, 6)]
    assert "REPAIRED" in states and states[-1] == "HOLDING", states
    return home, data, clock, body, breaking


def test_the_breaking_input_is_kept_by_content_when_the_capability_is_quarantined(tmp_path):
    home, data, clock, body, breaking = _break_and_repair(tmp_path, builders.StaticBuilder(BUGGY, BUGGY, GOOD))
    [vector] = _events(body, "genesis.failure_vector")
    first = _events(body, "capability.registered")[0]["manifest"]["capability_id"]
    assert vector["function"] == FUNCTION and vector["capability_id"] == first
    assert vector["input"].startswith("sha256:") and vector["bytes"] == len(breaking)
    assert "built capability raised ValueError" in vector["failure"]
    assert body.genesis.objects.read(vector["input"]) == breaking           # the bytes, not the path
    assert "done step" not in json.dumps(vector) and "finished step" not in json.dumps(vector)
    [kept] = body.genesis.failure_corpus(FUNCTION)
    assert kept["data"] == breaking and kept["capability_id"] == first
    body.close()


def test_a_later_reformation_refuses_the_same_bug_after_the_file_changed_and_the_body_restarted(tmp_path):
    home, data, clock, body, breaking = _break_and_repair(tmp_path, builders.StaticBuilder(BUGGY, BUGGY, GOOD))
    good = [s for s in _events(body, "capability.state") if s["state"] == "ATTACHED"][-1]["capability_id"]
    # An input larger than the store's ceiling (which equals built code's input ceiling) is not kept: it is said.
    (data / "huge.md").write_text("- [ ] x\n" * 40_000)
    manifest = body.genesis.registry.manifests[_events(body, "capability.registered")[0]["manifest"]["capability_id"]]
    body.genesis._record_failure_vector(type("M", (), {"mission_id": "m:x"})(), manifest, "raised",
                                        {"path": str(data / "huge.md")}, "incident-huge", clock())
    huge = [v for v in _events(body, "genesis.failure_vector") if v["incident"] == "incident-huge"][0]
    assert huge["input"] is None and "could not be kept" in huge["why_not_kept"]
    assert body.genesis.objects.max_object_bytes <= builders.MAX_INPUT
    body.close()
    # The runbook is shortened again, so the input that broke BUGGY no longer exists anywhere on disk; then the
    # attached GOOD source is tampered with, so the next re-formation's cause is not an input at all.
    (data / "FIRST_MISSION.md").write_text("# Runbook\n- [x] install\n- [ ] enroll key\n  - [ ] load launchd\n"
                                           "* [ ] accept closure\n")
    stored = home / "capabilities" / "built" / f"{hashlib.sha256(GOOD.encode()).hexdigest()}.py"
    assert good.endswith(stored.stem[:12]) and stored.read_text() == GOOD
    stored.write_text(stored.read_text() + "\nimport os\n")

    rebuild = builders.StaticBuilder(BUGGY, GOOD, identity="static-test-2")
    body = Body(home, clock=clock, builder=rebuild).open()
    body.boot()
    states = [r["state"] for r in _ticks(body, clock, 5)]
    assert states[-1] == "HOLDING", states
    repair = [d for d in _events(body, "deficit.opened") if d.get("repair")][-1]
    assert repair["repair"]["failure"].startswith("quarantined")             # not an input failure
    verdicts = [v for v in _events(body, "genesis.verified") if v["deficit_id"] == repair["deficit_id"]]
    # BUGGY passes the founder's frozen oracle, and the live file is short again: only the kept vector refuses it.
    assert [v["passed"] for v in verdicts] == [False, True], verdicts
    corpus = verdicts[0]["report"]["failure_corpus"]
    assert corpus["vectors"] == 1 and len(corpus["failures"]) == 1
    assert corpus["failures"][0]["error"] == "ValueError"
    assert verdicts[1]["report"]["failure_corpus"] == {"vectors": 1, "failures": [], "unavailable": []}
    assert len(rebuild.calls) == 2
    assert "raised on real input" in rebuild.calls[1]["feedback"][0]       # the error, never the input
    assert all("finished step" not in json.dumps(c) for c in rebuild.calls)
    attached = [s for s in _events(body, "capability.state") if s["state"] == "ATTACHED"][-1]
    assert attached["deficit_id"] == repair["deficit_id"]
    body.close()


def test_an_input_that_cannot_be_kept_is_recorded_with_the_reason(tmp_path):
    home, data, clock, body, _ = _break_and_repair(tmp_path, builders.StaticBuilder(BUGGY, BUGGY, GOOD))
    gen = body.genesis
    manifest = gen.registry.manifests[_events(body, "capability.registered")[0]["manifest"]["capability_id"]]
    mission = type("M", (), {"mission_id": "m:other"})()
    outside = tmp_path / "outside.txt"
    outside.write_text("not inside the read roots")
    gen._record_failure_vector(mission, manifest, "raised", {"path": str(outside)}, "incident-outside", clock())
    gen._record_failure_vector(mission, manifest, "raised", {}, "incident-nopath", clock())
    kept = {v["incident"]: v for v in _events(body, "genesis.failure_vector")}
    assert kept["incident-outside"]["input"] is None
    assert "not a readable file inside the body's read roots" in kept["incident-outside"]["why_not_kept"]
    assert kept["incident-nopath"]["why_not_kept"] == "the failing call named no input file"
    assert len(gen.failure_corpus(FUNCTION)) == 1                           # recorded, never replayed
    body.close()


def test_a_kept_input_whose_bytes_were_damaged_is_reported_unavailable_not_silently_dropped(tmp_path):
    home, data, clock, body, _ = _break_and_repair(tmp_path, builders.StaticBuilder(BUGGY, BUGGY, GOOD))
    [vector] = _events(body, "genesis.failure_vector")
    path = body.genesis.objects.path(vector["input"])
    path.chmod(0o600)
    path.write_bytes(b"something else")
    [entry] = body.genesis.failure_corpus(FUNCTION)
    assert "data" not in entry and "disagree" in entry["unavailable"]
    report = body.genesis._corpus_report([entry], [])
    assert report["vectors"] == 0 and report["unavailable"][0]["input"] == vector["input"]
    body.close()


def test_installed_software_candidates_are_judged_on_the_kept_inputs_too(tmp_path, monkeypatch):
    """The catalog and discovery routes qualify through ``_verify``: a tool that raises on a kept input fails."""
    home, data, clock, body, breaking = _break_and_repair(tmp_path, builders.StaticBuilder(BUGGY, BUGGY, GOOD))
    gen = body.genesis

    def fragile(function, candidate, binary, spec=None):
        def run(params, ctx):
            text = open(params["path"], "rb").read()
            if b"finished step" in text:
                raise ValueError("the tool chokes on this input")
            return {"words": 0}
        return run

    monkeypatch.setattr(genesis_mod, "catalog_adapter", fragile)
    manifest = gen.registry.manifests[_events(body, "capability.registered")[0]["manifest"]["capability_id"]]
    candidate = genesis_mod.Candidate("wc", ("wc", "-w"), "first_int")
    spec = {"output_field": "words", "description": "words"}
    vectors = [{"name": "case0.txt", "data": b"", "expected": 0}]
    passed, report = gen._verify(FUNCTION, candidate, "/bin/true", None, manifest, vectors=vectors, spec=spec)
    assert passed is False
    assert report["failure_corpus"]["failures"][0]["error"] == "ValueError"
    assert report["failures"][-1]["case"].startswith("failure-vector:")

    def transient(function, candidate, binary, spec=None):
        def run(params, ctx):
            if b"finished step" in open(params["path"], "rb").read():
                raise CapabilityError("host busy", failure_class="transient")
            return {"words": 0}
        return run

    monkeypatch.setattr(genesis_mod, "catalog_adapter", transient)
    with pytest.raises(CapabilityError):                                    # an outage is no verdict either way
        gen._verify(FUNCTION, candidate, "/bin/true", None, manifest, vectors=vectors, spec=spec)
    body.close()


def test_a_kept_input_binds_only_its_own_function(tmp_path):
    home, data, clock, body, breaking = _break_and_repair(tmp_path, builders.StaticBuilder(BUGGY, BUGGY, GOOD))
    gen = body.genesis
    other = type("Manifest", (), {"function": "text.word_count", "capability_id": "built.text.word_count.abc"})()
    mission = type("M", (), {"mission_id": "m:other"})()
    (data / "words.txt").write_text("one two three")
    gen._record_failure_vector(mission, other, "raised", {"path": str(data / "words.txt")}, "incident-words", clock())
    assert [v["data"] for v in gen.failure_corpus(FUNCTION)] == [breaking]
    assert [v["data"] for v in gen.failure_corpus("text.word_count")] == [b"one two three"]
    body.close()
