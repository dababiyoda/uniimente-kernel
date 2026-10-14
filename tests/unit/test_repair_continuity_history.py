"""The frozen continuity history (CONTRADICTION-0002 Option A), attacked.

The sealed Package 3 experiment now reads byte-identical copies of the twelve
continuity artifacts its subject bindings pin, so a lawful change to a live file
no longer reads as the experiment breaking. A history that always reproduces is
only worth something if it is the RIGHT history and if damage to it is caught:

* every copy is named by its own digest and equals git at the binding's commit;
* the store holds exactly what the bindings pin, and the bindings are unchanged;
* live drift moves the live reading and not the historical one;
* a tampered copy fails the thirteen SR002 dependent tests, run here against it.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from evolution.repair import continuity, spec
from evolution.repair.harness import (
    ReplacementExperiment, continuity_fingerprint, live_continuity_fingerprint,
)
from evolution.repair.subjects import FROZEN, SR001, SR002
from provenance.ledger import EvidenceLedger

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads((continuity.STORE / "MANIFEST.json").read_text())
BINDINGS = (FROZEN, SR001, SR002)
GATE = "policy/consequence_gate.py"


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True)


def _have(commit):
    return _git("cat-file", "-e", f"{commit}^{{commit}}").returncode == 0


# -- the store is the right history -----------------------------------------

def test_every_object_is_named_by_its_own_digest():
    names = sorted(p.name for p in continuity.OBJECTS.iterdir())
    assert names, "the frozen history is empty"
    for name in names:
        raw = (continuity.OBJECTS / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == name, f"{name} was altered"
        assert continuity.read_frozen(name) == raw


def test_the_store_holds_exactly_what_the_bindings_pin():
    pinned = {digest for binding in BINDINGS for _, digest in binding.artifacts}
    stored = {p.name for p in continuity.OBJECTS.iterdir()}
    assert stored == pinned
    assert set(MANIFEST["objects"]) == pinned
    assert len(pinned) == 16


def test_every_binding_reproduces_from_its_frozen_history():
    for binding in BINDINGS:
        assert len(binding.artifacts) == 12
        assert binding.matches(), binding.subject_id
        assert binding.fingerprint() == binding.continuity_sha256
    # FROZEN is exactly the sealed spec's table, read from history.
    assert dict(FROZEN.artifacts) == spec.CONTINUITY_ARTIFACT_SHA256
    assert FROZEN.continuity_sha256 == spec.CONTINUITY_COMBINED_SHA256
    assert spec.spec_hash() == spec.SPEC_SHA256
    assert continuity_fingerprint() == SR002.continuity_sha256
    assert continuity_fingerprint(subject=FROZEN) == spec.CONTINUITY_COMBINED_SHA256


def test_the_manifest_records_each_binding_exactly():
    assert MANIFEST["pinned_digests_changed"] is False
    for binding in BINDINGS:
        entry = MANIFEST["subjects"][binding.subject_id]
        assert entry["source_commit"] == binding.source_commit
        assert entry["continuity_sha256"] == binding.continuity_sha256
        assert [tuple(pair) for pair in entry["artifacts"]] == list(binding.artifacts)


def test_history_equals_git_at_each_binding_commit():
    """Materialised from git at each binding's own source commit. SR-002's
    commit is not in this repository's object store, so its reachable witness
    (the #103 merge that recorded the binding) is required instead; any source
    commit that is present is checked as well."""
    checked = 0
    for binding in BINDINGS:
        entry = MANIFEST["subjects"][binding.subject_id]
        witness = entry["reachable_witness"]
        assert _have(witness), f"{binding.subject_id}: witness {witness} missing"
        commits = [witness] + ([binding.source_commit]
                               if _have(binding.source_commit) else [])
        for commit in commits:
            for relative, digest in binding.artifacts:
                shown = _git("show", f"{commit}:{relative}")
                assert shown.returncode == 0, (commit, relative)
                assert shown.stdout == continuity.read_frozen(digest), \
                    f"{binding.subject_id}: {relative} differs from git at {commit[:12]}"
                checked += 1
    assert checked >= 36


def test_no_frozen_copy_is_a_second_constitution_or_gate():
    """The singleton check globs by name; content addressing keeps the
    historical copies from ever looking like a second source of authority."""
    for path in continuity.STORE.rglob("*"):
        assert path.name not in {"constitution.ucl", "consequence_gate.py",
                                 "authority-matrix.yaml", "legal-principals.yaml",
                                 "organ-registry.yaml", "agent-registry.yaml"}


# -- the two readings are separate -------------------------------------------

def test_live_drift_moves_the_live_reading_and_not_history(tmp_path):
    tree = continuity.materialize(SR002.artifacts, tmp_path)
    assert SR002.matches(tree)
    with (tree / GATE).open("ab") as handle:
        handle.write(b"\n# a later, separately governed change\n")
    assert not SR002.matches(tree)
    assert continuity_fingerprint(str(tree)) != SR002.continuity_sha256
    assert SR002.matches()
    assert continuity_fingerprint() == SR002.continuity_sha256


def test_the_run_record_says_what_reads_history_and_what_reads_live():
    record = ReplacementExperiment(subject=SR002).run()
    readings = record["readings"]
    assert any("frozen" in r for r in readings["history"])
    assert any("organs" in r for r in readings["live"])
    assert any("compiled by the live compiler" in r for r in readings["live"])
    assert "governance.integrity" in readings["not_answered_here"]
    continuity_record = record["continuity"]
    assert "frozen copies of subject sr002-0.1.0" in continuity_record["reading"]
    assert continuity_record["historical_reproduces"] is True
    live = continuity_record["live"]
    assert live["unchanged_by_this_run"] is True
    assert live["before"] == live["after"] == live_continuity_fingerprint()
    assert live["matches_subject"] == SR002.matches(ROOT)
    assert any("governance.integrity" in lim for lim in record["limitations"])


def test_the_frozen_subject_reproduces_the_sealed_package3_evidence_record():
    """Reproducibility is the property the ruling preserved. The sealed
    Package 3 evidence record is the freeze-time truth; a run bound to the
    original subject must reproduce it from history while the live files have
    since moved (SR-001, SR-002)."""
    sealed = json.loads((ROOT / "docs/release/package-3/EVIDENCE_RECORD.json").read_text())
    record = ReplacementExperiment(subject=FROZEN).run()
    for stage in ("before", "while_absent", "after", "unchanged", "artifact_count"):
        assert record["continuity"][stage] == sealed["continuity"][stage], stage
    assert record["continuity"]["before"] == spec.CONTINUITY_COMBINED_SHA256
    assert record["selection"] == sealed["selection"]
    assert record["decision"]["decision"] == sealed["decision"]["decision"]
    assert record["prediction_review"]["summary"] == sealed["prediction_review"]["summary"]
    for cid, trial in sealed["trials"].items():
        assert record["trials"][cid]["function_score"] == trial["function_score"]
        assert record["trials"][cid]["gates"] == trial["gates"]


def test_a_run_that_disturbs_the_live_artifacts_is_not_continuous(monkeypatch):
    """History reproducing is not enough: the run must also leave the live
    artifacts exactly as it found them. Simulated by a live reading that moves
    after the experiment is constructed."""
    from evolution.repair import harness

    readings = iter(["live-at-start"])
    monkeypatch.setattr(harness, "live_continuity_fingerprint",
                        lambda root=None: next(readings, "live-disturbed"))
    record = ReplacementExperiment(subject=SR002).run()
    assert record["continuity"]["historical_reproduces"] is True
    assert record["continuity"]["live"]["unchanged_by_this_run"] is False
    assert record["continuity"]["unchanged"] is False
    assert all(t["gates"]["continuity_unchanged"] is False
               and t["function_score"] == 0.0 for t in record["trials"].values())


# -- a tampered frozen copy fails the SR002 dependent tests ------------------

@pytest.fixture()
def tampered(tmp_path, monkeypatch):
    objects = tmp_path / "objects"
    shutil.copytree(continuity.OBJECTS, objects)
    victim = dict(SR002.artifacts)[GATE]
    with (objects / victim).open("ab") as handle:
        handle.write(b"\n# altered after freezing\n")
    monkeypatch.setattr(continuity, "OBJECTS", objects)
    return objects


def test_a_tampered_copy_stops_every_binding_that_reads_it(tampered, tmp_path):
    assert not SR002.matches()
    assert not SR001.matches()      # shares the same gate bytes
    assert FROZEN.matches()         # pins a different gate; untouched
    with pytest.raises(continuity.FrozenHistoryError, match="altered"):
        SR002.frozen_bytes(GATE)
    with pytest.raises(continuity.FrozenHistoryError):
        continuity.materialize(SR002.artifacts, tmp_path / "tree")
    assert continuity_fingerprint() != SR002.continuity_sha256


def test_moving_bytes_between_copies_is_refused_although_the_sum_is_unchanged(
        tmp_path, monkeypatch):
    """Shift one byte from the end of one artifact to the start of the next:
    the concatenation, and so the combined fingerprint, is unchanged. Only the
    per-artifact digests see it, and the historical verdict must use them."""
    objects = tmp_path / "objects"
    shutil.copytree(continuity.OBJECTS, objects)
    (first, d1), (second, d2) = SR002.artifacts[0], SR002.artifacts[1]
    a, b = (objects / d1).read_bytes(), (objects / d2).read_bytes()
    (objects / d1).write_bytes(a[:-1])
    (objects / d2).write_bytes(a[-1:] + b)
    monkeypatch.setattr(continuity, "OBJECTS", objects)
    assert continuity_fingerprint() == SR002.continuity_sha256
    assert not SR002.matches()
    record = ReplacementExperiment(subject=SR002).run()
    assert record["continuity"]["historical_reproduces"] is False
    assert record["continuity"]["unchanged"] is False


def test_a_missing_copy_does_not_reproduce(tampered):
    (tampered / dict(SR002.artifacts)[GATE]).unlink()
    assert not SR002.matches()
    with pytest.raises(continuity.FrozenHistoryError, match="no frozen copy"):
        continuity_fingerprint()


def test_a_tampered_copy_fails_the_thirteen_dependent_tests(tampered, tmp_path):
    """docs/decisions/SR002-GATE-HARDENING-01.json lists thirteen tests that were
    the historical tripwire. They pass on frozen history; here each one is run
    against a tampered history and must fail."""
    from tests.unit import test_repair_adapters as adapters
    from tests.unit import test_repair_harness as harness
    from tests.unit import test_shared_compatibility as shared

    ledger = EvidenceLedger("sha256:package3-tampered-history")
    record = ReplacementExperiment(ledger=ledger, subject=SR002).run()
    assert record["continuity"]["historical_reproduces"] is False
    assert record["continuity"]["unchanged"] is False
    assert record["continuity"]["live"]["unchanged_by_this_run"] is True
    assert all(t["gates"]["continuity_unchanged"] is False
               and t["function_score"] == 0.0 for t in record["trials"].values())

    run = (record, ledger)
    against_the_run = [
        harness.test_governance_and_continuity_held_while_the_function_was_absent,
        harness.test_continuity_is_unchanged_before_during_and_after,
        harness.test_selection_reports_the_two_questions_separately,
        harness.test_installation_is_verified_by_the_blind_detector,
        harness.test_installation_scope_is_stated_and_the_live_path_is_untouched,
        harness.test_rollback_restores_the_original_and_the_original_survived,
        harness.test_the_capsule_records_the_whole_cycle,
        harness.test_the_ledger_chain_verifies_and_is_append_only,
        harness.test_the_r3_prediction_is_recorded_as_wrong,
    ]
    for test in against_the_run:
        with pytest.raises((AssertionError, KeyError)):
            test(run)
    with pytest.raises(AssertionError):
        adapters.test_identity_authority_and_shutdown_survive_the_component_being_absent()
    with pytest.raises(continuity.FrozenHistoryError):
        shared.test_current_binding_does_not_revalidate_the_old_subject(tmp_path / "a")
    with pytest.raises(continuity.FrozenHistoryError):
        shared.test_changed_source_fails_instead_of_learning_a_new_fingerprint(tmp_path / "b")

    # The thirteenth runs the module entry point in a fresh process; run that
    # same entry point against the tampered history and require a refusal.
    child = (
        "import sys\nfrom pathlib import Path\n"
        "from evolution.repair import continuity\n"
        f"continuity.OBJECTS = Path({str(tampered)!r})\n"
        "from evolution.repair.__main__ import main\n"
        "sys.argv = ['evolution.repair', '--subject', 'sr002']\n"
        "raise SystemExit(main())\n")
    proc = subprocess.run([sys.executable, "-c", child], cwd=ROOT,
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 1, proc.stderr[-2000:]
    assert json.loads(proc.stdout)["continuity"]["unchanged"] is False
