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
    # Baseline is origin/main, not the freeze commit. First draft compared
    # against 627ec48 and flagged four files — which main itself had changed in
    # later Package 4 work, not this branch. The question is whether THIS branch
    # touched the seal relative to the integration target.
    sealed = ["evolution/repair/spec.py", "tests/unit/test_repair_spec_frozen.py",
              "tests/unit/test_repair_adapters.py",
              "tests/unit/test_repair_candidates.py",
              "tests/unit/test_repair_inertness.py",
              "tests/unit/test_repair_harness.py"]
    changed = subprocess.run(
        ["git", "diff", "--name-only", "origin/main", "HEAD", "--", *sealed],
        cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert not changed, f"this branch modified sealed repair files: {changed}"

    # Everything this remedy adds lives under the corpus directory.
    added = subprocess.run(
        ["git", "diff", "--name-only", "origin/main", "HEAD", "--",
         "evolution/repair/"],
        cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert all(p.startswith("evolution/repair/corpus/") for p in added), added


def test_the_spec_seal_itself_is_untouched():
    assert spec.spec_hash() == spec.SPEC_SHA256
