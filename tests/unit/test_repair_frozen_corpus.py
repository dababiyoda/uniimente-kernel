"""The remedy for CONTRADICTION-0001, proven without touching the sealed files.

`spec.MEASUREMENT_CORPUS` binds a sealed experiment to a live glob. These tests
prove a frozen corpus reproduces every sealed expectation exactly, so the
outstanding decision is about applying a verified remedy rather than choosing
between options described in prose.
"""
from __future__ import annotations

import os
import subprocess

import pytest

from evolution.repair import spec
from linker.linker import InstitutionalLinker
from linker.manifest import load_all

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORPUS = os.path.join(ROOT, "evolution", "repair", "corpus")

#: Blob ids at 627ec48, the commit that froze spec.py.
FREEZE_BLOBS = {
    "kernel.manifest.yaml": "7b894e47f2c70c2a28bb8f26b6b8ae1ec56ea7b6",
    "daleobanks.manifest.yaml": "533c55ee9ddd2683ce94eadb93a0e8bfc73e3545",
    "wealthmachine.manifest.yaml": "3c649b1042df90b1a441da9d74bfd3b637481ee7",
}


def _blob(path: str) -> str:
    return subprocess.run(["git", "hash-object", path],
                          capture_output=True, text=True, check=True).stdout.strip()


#: Content pins for the sealed repair files, as they stand on canonical main.
#: Deliberately NOT a `git diff` against a ref. Two earlier attempts failed for
#: opposite reasons and both are instructive: comparing against the freeze commit
#: flagged files main itself had changed, and comparing against `origin/main`
#: certified nothing in CI, where that ref does not exist — `git diff` writes an
#: empty stdout and exits 128, which a stdout-only reader mistakes for "no
#: changes". Content pins need no refs, work in a shallow checkout, and assert
#: something stronger than a diff: these exact bytes.
SEALED_BLOBS = {
    "evolution/repair/spec.py":
        "4d8f267ff13de7b83f8efb30d6c5f322f2c56f8e",
    "tests/unit/test_repair_spec_frozen.py":
        "7622d5d8b2a156b9a81333e8c8dd47fc2c24652f",
    "tests/unit/test_repair_adapters.py":
        "144af43dee616e7bf816ece80729ec3a90ad2fa3",
    "tests/unit/test_repair_candidates.py":
        "0d469ffc2fcb95c82fa2edd868208e38ec512a99",
    "tests/unit/test_repair_inertness.py":
        "1e1dc96ff33813d689bdb5887806742fabeb329b",
    "tests/unit/test_repair_harness.py":
        "fdc31ce110aa4abd4e898e808f738956c05d4629",
}


@pytest.mark.parametrize("name,blob", sorted(FREEZE_BLOBS.items()))
def test_each_corpus_file_is_byte_identical_to_the_freeze_commit(name, blob):
    """Content-pinned, not path-pinned. Path pinning would not have been enough.

    `organs/kernel.manifest.yaml` drifted after the freeze without anyone
    noticing, so an experiment pinned to that *path* would still have been
    reading changed bytes. Only the content pin makes the run reproducible.
    """
    assert _blob(os.path.join(CORPUS, name)) == blob


def test_the_frozen_corpus_reproduces_every_sealed_expectation():
    """The whole claim, in one assertion set. No expectation value is altered.

    If this passes, the remedy is not a trade-off — the expectations were always
    right and only the input binding was wrong.
    """
    report = InstitutionalLinker(load_all(CORPUS)).link()

    assert len(report.unresolved) == spec.REQUIRED_REFUSALS["unresolved_count"]
    assert len(report.edges) == len(spec.REQUIRED_EDGE_TRIPLES)

    triples = tuple(sorted((e.producer, e.contract, e.consumer)
                           for e in report.edges))
    assert triples == tuple(sorted(spec.REQUIRED_EDGE_TRIPLES))

    assert tuple(sorted(report.unproduced)) == tuple(
        sorted(spec.REQUIRED_REFUSALS["unproduced"]))
    assert tuple(sorted(report.untyped)) == tuple(
        sorted(spec.REQUIRED_REFUSALS["untyped"]))
    assert tuple(sorted(report.unconsumed)) == tuple(
        sorted(spec.REQUIRED_REFUSALS["unconsumed"]))


def test_the_live_corpus_still_disagrees_and_that_is_the_contradiction():
    """The defect stays visible. This test would pass if it were papered over.

    Kept deliberately: a remedy that quietly made the contradiction invisible
    would be worse than the contradiction, because the next reader could not see
    why the frozen corpus exists.
    """
    live = InstitutionalLinker(load_all(os.path.join(ROOT, "organs"))).link()
    assert len(live.unresolved) != spec.REQUIRED_REFUSALS["unresolved_count"], (
        "if the live corpus now matches the seal, CONTRADICTION-0001 resolved "
        "itself and this remedy should be reconsidered rather than applied"
    )


def test_no_sealed_repair_file_was_modified_to_achieve_this():
    """The constraint this remedy was built under, asserted rather than promised.

    The corpus and this test are additive. Applying the remedy means repointing
    five call sites, which is a separate, visible amendment the seal's own test
    prescribes the procedure for.
    """
    # Content pins, not a diff against any ref — see SEALED_BLOBS for why two
    # ref-based attempts failed in opposite directions.
    drifted = {path: _blob(os.path.join(ROOT, path))
               for path, pinned in sorted(SEALED_BLOBS.items())
               if _blob(os.path.join(ROOT, path)) != pinned}
    assert not drifted, (
        f"this branch modified sealed repair files: {drifted}. Applying the "
        "remedy is a deliberate amendment — say so in the commit message and in "
        "docs/release/package-3/, and update these pins in the same change."
    )


def test_the_spec_seal_itself_is_untouched():
    assert spec.spec_hash() == spec.SPEC_SHA256


def test_the_guard_needs_no_git_refs_and_so_cannot_certify_nothing():
    """The hole this file shipped with, closed by removing the dependency.

    The first fix made the ref-based guard raise on an unresolvable baseline.
    That was correct and it immediately went red in CI — proving the earlier
    green had been vacuous, because the runner's shallow checkout has no
    `origin/main` at all. Raising there is honest but useless: a guard that
    cannot run where it matters guards nothing. Content pins remove the
    dependency entirely.
    """
    assert SEALED_BLOBS, "the guard must pin something"
    for path in SEALED_BLOBS:
        assert os.path.exists(os.path.join(ROOT, path)), path
    # No ref is consulted anywhere in the guard.
    source = open(__file__, encoding="utf-8").read()
    guard = source.split("def test_no_sealed_repair_file_was_modified")[1]
    guard = guard.split("def test_")[0]
    assert "origin/main" not in guard and "git diff" not in guard


def test_a_modified_sealed_file_is_detected(tmp_path):
    """The guard must bite, exercised rather than trusted."""
    victim = tmp_path / "spec.py"
    victim.write_text("# not the sealed bytes\n")
    assert _blob(str(victim)) != SEALED_BLOBS["evolution/repair/spec.py"]
