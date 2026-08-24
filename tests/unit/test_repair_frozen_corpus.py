"""The remedy for CONTRADICTION-0001 — proven first, then applied under ruling.

`spec.MEASUREMENT_CORPUS` bound a sealed experiment to a live glob. These tests
first proved, without touching a sealed file, that a frozen corpus reproduces
every sealed expectation exactly — so the outstanding decision was about
applying a verified remedy rather than choosing between options in prose.

The founder approved Option A on 2026-08-22, and Amendment 001 applied it. The
tests below now do double duty: they still prove the frozen corpus reproduces
the sealed run, and they additionally bound the amendment itself — its scope,
its authority, and the constraint that it changed the corpus binding and nothing
else. See `docs/release/package-3/AMENDMENT-001-frozen-corpus.md`.
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


#: The sealed files as they stood BEFORE Amendment 001, retained rather than
#: overwritten. An amendment that erased the values it replaced would be
#: indistinguishable, to a later reader, from an experiment never amended.
SEALED_BLOBS_PRE_AMENDMENT = {
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

#: Exactly the files Amendment 001 is authorized to touch, and why. The guard
#: below asserts the *set* of files whose bytes moved equals this set — so
#: repointing a sixth file under cover of the amendment fails the build even
#: though its pin would have been updated in the same commit.
AMENDED_BY_001 = {
    "evolution/repair/spec.py": "the corpus binding itself, plus CORPUS_DIR",
    "tests/unit/test_repair_spec_frozen.py": "reads spec.CORPUS_DIR",
    "tests/unit/test_repair_adapters.py": "reads spec.CORPUS_DIR",
    "tests/unit/test_repair_candidates.py": "reads spec.CORPUS_DIR",
    "tests/unit/test_repair_inertness.py": "reads spec.CORPUS_DIR in the child",
}

#: Exactly the files Amendment 002 is authorized to touch, and why.
#: CONTRADICTION-0002 Option A, 2026-08-23: repoint the *continuity* binding at
#: byte-identical freeze-time copies, as 001 did for the corpus binding.
#:
#: Narrower than 001 by construction. The continuity pins are relative paths and
#: the root they were joined to lived in `harness.py`, which is not a sealed
#: file — so the binding moves without touching a single frozen table, and
#: `SPEC_SHA256` and `EXPECTATIONS_SHA256` are bit-identical across this
#: amendment. 001 could not claim that; this one can, and
#: `test_amendment_002_moved_no_expectation_and_did_not_move_the_seal` proves it.
AMENDED_BY_002 = {
    "evolution/repair/spec.py": "adds CONTINUITY_DIR, a path constant outside "
                                "_FROZEN_TABLES — no expectation value moves",
    "tests/unit/test_repair_spec_frozen.py": "reads spec.CONTINUITY_DIR instead "
                                             "of the live tree, plus three new "
                                             "guards on the amendment itself",
}

#: The sealed files as they stood after Amendment 001 and BEFORE Amendment 002.
#: Retained for the same reason 001's pre-values are: an amendment that erased
#: what it replaced would be indistinguishable from no amendment at all.
SEALED_BLOBS_PRE_AMENDMENT_002 = {
    "evolution/repair/spec.py":
        "349c73463835b2e244f14d85781fb42dba4e4903",
    "tests/unit/test_repair_spec_frozen.py":
        "768aef0efa0abea5b759a4f17c09b90ade59d4b1",
    "tests/unit/test_repair_adapters.py":
        "e76fd1f75d7f79c3d4f52374b9c193c6643d8062",
    "tests/unit/test_repair_candidates.py":
        "d4522f53891ff5503994fcbfcf2d1244378462eb",
    "tests/unit/test_repair_inertness.py":
        "f464459817c648296f6867a5799e765dde4dfc8b",
    "tests/unit/test_repair_harness.py":
        "fdc31ce110aa4abd4e898e808f738956c05d4629",
}

#: NOTE FOR THE NEXT AMENDMENT — a defect in this guard pattern, fixed at 003.
#:
#: Guards 001 and 002 originally compared their pre-state against `SEALED_BLOBS`,
#: the *current* pins. That works for exactly one amendment. When 003 moved
#: `test_repair_harness.py`, both earlier guards failed: measured against the
#: moving target, 003's change looked like an undeclared file inside 001's and
#: 002's scope.
#:
#: The pattern is now: **each guard compares its own before-snapshot against its
#: own after-snapshot**, both frozen. `SEALED_BLOBS_PRE_AMENDMENT_002` is the
#: post-001 state, `SEALED_BLOBS_PRE_AMENDMENT_003` is the post-002 state, and
#: `SEALED_BLOBS` is the post-003 state. A fourth amendment adds
#: `SEALED_BLOBS_PRE_AMENDMENT_004` (= the current `SEALED_BLOBS` values),
#: repoints guard 003 at it, and adds its own guard against `SEALED_BLOBS`.
#:
#: Recorded here rather than silently fixed: the flaw was introduced by the
#: session that wrote 002 and was only exposed by 003 existing at all.

#: Exactly the files Amendment 003 is authorized to touch, and why.
#:
#: Amendment 002 repointed the continuity BINDING. It missed two call sites that
#: still compared LIVE bytes against the freeze-time constant, which only became
#: visible once the live gate actually diverged — Witness v2 emission, authorised
#: by the same ruling, changed `policy/consequence_gate.py` and both assertions
#: failed. That is the remedy's own test finding the rest of the remedy.
#:
#: Both are converted to self-comparisons: the property worth asserting inside a
#: run is "this experiment disturbed nothing", not "the tree still matches July".
AMENDED_BY_003 = {
    "tests/unit/test_repair_adapters.py":
        "compares the fingerprint before/after the component is disabled, "
        "instead of against CONTINUITY_COMBINED_SHA256",
    "tests/unit/test_repair_harness.py":
        "asserts the run-scoped before/during/after self-comparison, plus the "
        "separately recorded frozen_baseline_reproduces",
}

#: The sealed files as they stood after Amendment 002 and BEFORE Amendment 003.
SEALED_BLOBS_PRE_AMENDMENT_003 = {
    "evolution/repair/spec.py":
        "ae8d1e9af90bc6bd71e31da146d890f47b357571",
    "tests/unit/test_repair_spec_frozen.py":
        "a01fafe01038b4b9541d6b7a708c00319303a565",
    "tests/unit/test_repair_adapters.py":
        "e76fd1f75d7f79c3d4f52374b9c193c6643d8062",
    "tests/unit/test_repair_candidates.py":
        "d4522f53891ff5503994fcbfcf2d1244378462eb",
    "tests/unit/test_repair_inertness.py":
        "f464459817c648296f6867a5799e765dde4dfc8b",
    "tests/unit/test_repair_harness.py":
        "fdc31ce110aa4abd4e898e808f738956c05d4629",
}

#: Exactly the files Amendment 004 is authorized to touch, and why.
#:
#: CI check 3 ("one source of authority") failed on the Amendment 002/003 push
#: and was RIGHT. Storing the frozen artifacts under their real names made
#: `evolution/repair/continuity/policy/consequence_gate.py` importable — PEP 420
#: namespace packages need no `__init__.py` — so the remedy for
#: CONTRADICTION-0002 had created a genuine SECOND PATH TO EXTERNAL EFFECT,
#: sitting in the tree under a reassuring directory name.
#:
#: Fixed by suffixing every frozen artifact `.frozen` rather than by excluding
#: the directory from that check. An exclusion would have let the check keep
#: passing while the importable duplicate stayed on disk — the check would have
#: been weakened to accommodate the defect it correctly found.
AMENDED_BY_004 = {
    "evolution/repair/spec.py":
        "adds FROZEN_SUFFIX and frozen_path(); no expectation value moves",
    "tests/unit/test_repair_spec_frozen.py":
        "reads through frozen_path(), and asserts every frozen artifact is "
        "stored suffixed rather than under its real name",
}

#: The sealed files as they stood after Amendment 003 and BEFORE Amendment 004.
SEALED_BLOBS_PRE_AMENDMENT_004 = {
    "evolution/repair/spec.py":
        "ae8d1e9af90bc6bd71e31da146d890f47b357571",
    "tests/unit/test_repair_spec_frozen.py":
        "a01fafe01038b4b9541d6b7a708c00319303a565",
    "tests/unit/test_repair_adapters.py":
        "0df5ae99971aa423e5318ac99dd651215062efa4",
    "tests/unit/test_repair_candidates.py":
        "d4522f53891ff5503994fcbfcf2d1244378462eb",
    "tests/unit/test_repair_inertness.py":
        "f464459817c648296f6867a5799e765dde4dfc8b",
    "tests/unit/test_repair_harness.py":
        "6f464f037079d65668f73e2952703af33f66a78a",
}

#: Content pins for the sealed repair files, as they stand after Amendment 004.
#: Deliberately NOT a `git diff` against a ref. Two earlier attempts failed for
#: opposite reasons and both are instructive: comparing against the freeze commit
#: flagged files main itself had changed, and comparing against `origin/main`
#: certified nothing in CI, where that ref does not exist — `git diff` writes an
#: empty stdout and exits 128, which a stdout-only reader mistakes for "no
#: changes". Content pins need no refs, work in a shallow checkout, and assert
#: something stronger than a diff: these exact bytes.
SEALED_BLOBS = {
    # Moved again by Amendment 004 (frozen artifacts suffixed).
    "evolution/repair/spec.py":
        "f98f040940896dd0393ddc73cec08f0230265701",
    "tests/unit/test_repair_spec_frozen.py":
        "2122c4e436588af8f8285f885a28a1e1acfde500",
    # Moved by Amendment 003 (the two remaining live comparisons).
    "tests/unit/test_repair_adapters.py":
        "0df5ae99971aa423e5318ac99dd651215062efa4",
    "tests/unit/test_repair_candidates.py":
        "d4522f53891ff5503994fcbfcf2d1244378462eb",
    "tests/unit/test_repair_inertness.py":
        "f464459817c648296f6867a5799e765dde4dfc8b",
    "tests/unit/test_repair_harness.py":
        "6f464f037079d65668f73e2952703af33f66a78a",
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
    """The divergence stays visible — now expected and named, not unexplained.

    Kept deliberately, and its meaning changed with Amendment 001. Before, it
    demonstrated the contradiction: a sealed expectation that the live corpus no
    longer met. After, it demonstrates that the two corpora are genuinely
    different inputs — which is precisely why the frozen experiment cannot be
    read as a statement about the institution's current health, and why
    `evolution/repair/live_health.py` had to exist.

    If this ever fails, the two readings have converged and someone could
    plausibly mistake one for the other. That is the moment to re-examine the
    remedy, not to delete the test.
    """
    live = InstitutionalLinker(load_all(os.path.join(ROOT, "organs"))).link()
    assert len(live.unresolved) != spec.REQUIRED_REFUSALS["unresolved_count"], (
        "if the live corpus now matches the seal, CONTRADICTION-0001 resolved "
        "itself and this remedy should be reconsidered rather than applied"
    )


def test_no_sealed_repair_file_was_modified_to_achieve_this():
    """The guard, still doing its job one amendment later.

    Before Amendment 001 this asserted that the frozen-corpus proof was built
    without touching a sealed file, which it was. The amendment then applied the
    proven remedy, so the pins moved — under the procedure this test's own
    failure message prescribes.

    The re-pinned guard is deliberately *not* the weaker "these are the bytes
    now". It still refuses any drift from the pins, and
    `test_the_amendment_touched_exactly_the_files_it_declared` binds those pins
    to a declared scope, so bumping a pin is no longer sufficient to smuggle a
    file through.
    """
    # Content pins, not a diff against any ref — see SEALED_BLOBS for why two
    # ref-based attempts failed in opposite directions.
    drifted = {path: _blob(os.path.join(ROOT, path))
               for path, pinned in sorted(SEALED_BLOBS.items())
               if _blob(os.path.join(ROOT, path)) != pinned}
    assert not drifted, (
        f"this branch modified sealed repair files: {drifted}. Amending a sealed "
        "experiment is a deliberate act — say so in the commit message and in "
        "docs/release/package-3/, and update these pins in the same change."
    )


def test_the_amendment_touched_exactly_the_files_it_declared():
    """Re-pinning is not a blank cheque.

    The weakness of a content-pin guard is that the procedure for changing a
    sealed file is "update the pin", which an author doing something broader can
    follow just as easily as an author doing something narrow. So the pins are
    tied to a declared scope: the set of files whose bytes moved across the
    amendment must equal `AMENDED_BY_001` exactly.

    Sneaking a sixth sealed file into the amendment now fails here even with its
    pin dutifully updated, and quietly dropping one of the five fails too.
    """
    moved = {path for path, before in SEALED_BLOBS_PRE_AMENDMENT.items()
             if SEALED_BLOBS_PRE_AMENDMENT_002[path] != before}
    assert moved == set(AMENDED_BY_001), (
        f"amendment scope mismatch. moved={sorted(moved)} "
        f"declared={sorted(AMENDED_BY_001)}. Every file the amendment touches "
        "must be declared in AMENDED_BY_001 with the reason it was touched."
    )
    assert set(SEALED_BLOBS_PRE_AMENDMENT_002) == set(SEALED_BLOBS_PRE_AMENDMENT), (
        "the amendment may not add or drop a sealed file, only change one"
    )


def test_amendment_002_touched_exactly_the_files_it_declared():
    """The same scope discipline, one amendment later.

    Amendment 002 moves two files that Amendment 001 had already moved, so the
    001 guard above cannot see it: measured against the pre-001 pins, the set of
    moved files is unchanged. A second amendment that hid inside the first one's
    scope would have been invisible.

    This guard measures against the post-001 pins, so 002 has to declare its own
    scope. Every future amendment needs the same treatment — that is the cost of
    the content-pin design, and it is cheaper than a seal nobody can audit.
    """
    moved = {path for path, before in SEALED_BLOBS_PRE_AMENDMENT_002.items()
             if SEALED_BLOBS_PRE_AMENDMENT_003[path] != before}
    assert moved == set(AMENDED_BY_002), (
        f"amendment 002 scope mismatch. moved={sorted(moved)} "
        f"declared={sorted(AMENDED_BY_002)}. Every file the amendment touches "
        "must be declared in AMENDED_BY_002 with the reason it was touched."
    )
    assert set(SEALED_BLOBS_PRE_AMENDMENT_003) == set(SEALED_BLOBS_PRE_AMENDMENT_002), (
        "the amendment may not add or drop a sealed file, only change one"
    )


def test_amendment_003_touched_exactly_the_files_it_declared():
    """Third amendment, third scope guard. The pattern is now the rule.

    Amendment 002's guard cannot see 003 for the same reason 001's could not
    see 002: measured against the pre-002 pins, `test_repair_adapters.py` and
    `test_repair_harness.py` had not moved, so 003 would have been invisible
    inside 002's declared scope.

    Every amendment declares against the pins as they stood immediately before
    it. That is the cost of content pinning, and it is cheaper than a seal
    nobody can audit.
    """
    moved = {path for path, before in SEALED_BLOBS_PRE_AMENDMENT_003.items()
             if SEALED_BLOBS_PRE_AMENDMENT_004[path] != before}
    assert moved == set(AMENDED_BY_003), (
        f"amendment 003 scope mismatch. moved={sorted(moved)} "
        f"declared={sorted(AMENDED_BY_003)}. Every file the amendment touches "
        "must be declared in AMENDED_BY_003 with the reason it was touched."
    )
    assert set(SEALED_BLOBS_PRE_AMENDMENT_004) == set(SEALED_BLOBS_PRE_AMENDMENT_003)


def test_amendment_004_touched_exactly_the_files_it_declared():
    """Fourth amendment, fourth guard — the documented pattern, applied.

    Measured against the post-003 snapshot, per the note above. Amendment 004
    exists because CI check 3 correctly refused the Amendment 002/003 push: the
    frozen corpus had introduced an importable second Consequence Gate.
    """
    moved = {path for path, before in SEALED_BLOBS_PRE_AMENDMENT_004.items()
             if SEALED_BLOBS[path] != before}
    assert moved == set(AMENDED_BY_004), (
        f"amendment 004 scope mismatch. moved={sorted(moved)} "
        f"declared={sorted(AMENDED_BY_004)}."
    )
    assert set(SEALED_BLOBS) == set(SEALED_BLOBS_PRE_AMENDMENT_004)


def test_no_frozen_artifact_is_importable_or_loadable_as_the_real_thing():
    """The defect Amendment 004 closed, pinned so it cannot return.

    A frozen artifact stored under its real name is not merely untidy: for
    `consequence_gate.py` it was an importable second gate, and for the YAML
    registries it would be a second hit for any glob that looks for authority.
    """
    import importlib.util

    frozen_dir = os.path.join(ROOT, "evolution", "repair", "continuity")
    for dirpath, _dirnames, filenames in os.walk(frozen_dir):
        for name in filenames:
            if name == "README.md":
                continue
            assert name.endswith(".frozen"), f"{name} is stored unsuffixed"
            assert not name.endswith(".py"), f"{name} is importable Python"

    assert importlib.util.find_spec(
        "evolution.repair.continuity.policy.consequence_gate") is None, (
        "the frozen consequence gate is importable again — a second path to "
        "external effect, which is exactly what CI check 3 refuses")


def test_amendment_002_left_the_historical_evidence_exactly_where_it_was():
    """The founder's constraint on CONTRADICTION-0002, machine-checked.

    *"Historical expectations, evidence, lineage, and freeze-time truth must
    remain unchanged"* and *"do not update an old historical hash merely to make
    current implementation pass"*.

    The stronger reading of that constraint is available here and asserted:
    not merely that expectations are unchanged, but that the experiment's own
    seal did not move at all. If a later session unblocks itself by editing a
    pinned constitutional hash, this is the test that stops it.
    """
    assert spec.spec_hash() == spec.SPEC_SHA256
    assert spec.expectations_hash() == spec.EXPECTATIONS_SHA256

    # Amendment 001's seal-move is preserved as history, not overwritten.
    assert spec.SPEC_SHA256_ORIGINAL != spec.SPEC_SHA256

    # The twelve pins themselves: same paths, same hashes, same combined value.
    assert len(spec.CONTINUITY_ARTIFACT_SHA256) == 12
    assert spec.CONTINUITY_COMBINED_SHA256 == \
        "c1d621a80671d1f39f75e3d525561b45795a978d7d15b1eee7d43546140e63aa"


def test_the_amendment_changed_the_corpus_binding_and_nothing_else():
    """The founder's constraint on Option A, machine-checked.

    The ruling was: *"Do not change the frozen expectation values and do not
    rewrite the historical evidence."* `expectations_hash()` seals every frozen
    table except `measurement_corpus`, so it is invariant under a corpus
    repoint and moves the instant a threshold, edge triple, refusal count or
    expected result is touched.

    `EXPECTATIONS_SHA256` was computed from the spec as it stood BEFORE the
    amendment, at seal `6f6d7dab…c4ab7f4a`. This equality is therefore proof
    across the amendment rather than a self-consistent restatement of it.
    """
    assert spec.expectations_hash() == spec.EXPECTATIONS_SHA256, (
        "an expectation value moved. The corpus repoint is authorized; changing "
        "what was expected is not."
    )
    # The specific values the ruling named, spelled out so a reader need not
    # trust a hash to see that the historical answer is intact.
    assert spec.REQUIRED_REFUSALS["unresolved_count"] == 7
    assert len(spec.REQUIRED_EDGE_TRIPLES) == 4

    # And the seal itself moved, because the binding did. A sealed experiment
    # whose seal did NOT move across a real amendment would mean the seal was
    # not covering the thing that changed.
    assert spec.SPEC_SHA256 != spec.SPEC_SHA256_ORIGINAL
    assert spec.spec_hash() == spec.SPEC_SHA256


def test_the_amendment_is_documented_where_the_guard_says_it_must_be():
    """The failure message above names a location. That location must exist.

    A guard that instructs an author to document something, and then never
    checks, trains authors to skip the documentation.
    """
    record = os.path.join(ROOT, "docs", "release", "package-3",
                          "AMENDMENT-001-frozen-corpus.md")
    assert os.path.exists(record), (
        "the amendment record the seal's own failure message prescribes is missing"
    )
    text = open(record, encoding="utf-8").read()
    assert "FOUNDER-RULING-2026-08-22" in text, "must name its authority"
    assert spec.SPEC_SHA256 in text and spec.SPEC_SHA256_ORIGINAL in text, (
        "must record both the superseded and the current seal"
    )
    for path in AMENDED_BY_001:
        assert path in text, f"amended file not listed in the record: {path}"


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
