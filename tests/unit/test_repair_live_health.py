"""The live check must not become the sealed experiment wearing a new name.

The founder approved Option A of DEC-OM-002 with a condition attached, because
Option A has an adversarial weakness: once the sealed experiment reads a frozen
corpus it always passes, and a reader could mistake that green for evidence
that the live institution is fine. It is not evidence of that.

> The frozen experiment answers "can I reproduce the historical experiment?"
> The live check answers "is the institution healthy now?" Never let one
> masquerade as the other.

`evolution/repair/live_health.py` is the second reading. The obvious failure
mode is drift: someone later "tidies" it by importing the expectations that
already exist next door, and the institution silently goes back to one reading
pretending to be two.

Prose cannot prevent that. These tests assert the separation **structurally**,
over the module's AST, so the masquerade fails the build rather than passing
review. Structural, not substring: PR #70 recorded a substring guard firing on
the identifier `max_subprocesses_per_candidate`, and that precedent is followed
here — every check below parses the module and inspects real nodes.
"""
from __future__ import annotations

import ast
import os

import pytest

from evolution.repair import live_health, spec

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULE = os.path.join(ROOT, "evolution", "repair", "live_health.py")

#: The historical expectation. If this literal ever appears in a comparison in
#: the live module, the live module has become the sealed experiment.
FROZEN_UNRESOLVED = 7


def _tree() -> ast.Module:
    with open(MODULE, encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=MODULE)


# ----------------------------------------------------- the separation, asserted
def test_the_live_check_imports_no_expectation_from_the_sealed_spec():
    """The masquerade begins with an import. Refuse it at the source.

    Note what is *not* forbidden: importing `spec` for a path constant would be
    harmless in isolation. It is forbidden anyway, because the distinction
    between "borrowed a path" and "borrowed an expectation" is exactly the
    judgement call a future editor will get wrong under time pressure. A flat
    rule holds; a nuanced one erodes.
    """
    offenders = []
    for node in ast.walk(_tree()):
        if isinstance(node, ast.ImportFrom) and node.module:
            if "repair.spec" in node.module or node.module == "spec":
                offenders.append(f"from {node.module} import ...")
            if any(a.name == "spec" for a in node.names):
                offenders.append(f"from {node.module} import spec")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.endswith("repair.spec"):
                    offenders.append(f"import {alias.name}")
    assert not offenders, (
        f"the live health check imports the sealed spec: {offenders}. It must "
        "carry no frozen expectation — that is the whole reason it exists."
    )


def test_the_live_check_never_compares_against_the_frozen_expectation():
    """No comparison against 7, however the 7 is spelled.

    Walks every `Compare` node and rejects the literal on either side. A module
    that asserted `unresolved == 7` would be re-running the sealed experiment
    against a corpus that legitimately grew, which is precisely the defect
    Amendment 001 removed.
    """
    offenders = []
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Compare):
            continue
        for operand in [node.left, *node.comparators]:
            if isinstance(operand, ast.Constant) and \
                    operand.value == FROZEN_UNRESOLVED:
                offenders.append(ast.unparse(node))
    assert not offenders, (
        f"the live check compares against the frozen expectation: {offenders}"
    )


def test_the_live_check_holds_no_seal_and_no_frozen_table():
    """A seal would make it a second sealed experiment, not a live reading."""
    names = {t.id
             for node in ast.walk(_tree())
             if isinstance(node, ast.Assign)
             for t in node.targets if isinstance(t, ast.Name)}
    sealed = {n for n in names
              if "SHA256" in n or "FROZEN" in n or "REQUIRED_" in n
              or "EXPECTED" in n}
    assert not sealed, f"the live check declares sealed state: {sorted(sealed)}"
    assert not hasattr(live_health, "spec_hash")
    assert not hasattr(live_health, "SPEC_SHA256")


def test_the_live_check_reports_a_reading_rather_than_a_verdict():
    """No pass/fail. A green light over the whole institution hides the finding.

    The reading exposes the numbers and the named findings; deciding what they
    mean is the reader's job. `structural_findings` is offered as the count
    that would indicate something is *wrong* rather than merely *open*, but it
    is a number, not a judgement.
    """
    reading = live_health.read()
    assert not hasattr(reading, "passed")
    assert not hasattr(reading, "ok")
    assert not hasattr(reading, "verdict")
    # It is a plain reading of what is on disk.
    assert reading.organ_count == len(
        [n for n in os.listdir(os.path.join(ROOT, "organs"))
         if n.endswith(".manifest.yaml")])


# ------------------------------------------------- the two readings differ, live
def test_the_two_readings_genuinely_disagree_today():
    """If they ever agreed, one could stand in for the other undetected.

    This is the live-side counterpart to
    `test_repair_frozen_corpus.py::test_the_live_corpus_still_disagrees…`. Both
    are kept: that one guards the sealed module, this one guards the live module,
    and a single test could not fail for both reasons.
    """
    reading = live_health.read()
    assert reading.unresolved != spec.REQUIRED_REFUSALS["unresolved_count"], (
        "the live institution now matches the frozen expectation. The two "
        "readings have converged and could be mistaken for each other — "
        "re-examine DEC-OM-002 rather than deleting this test."
    )


def test_the_live_reading_reflects_organs_that_did_not_exist_at_the_freeze():
    """The reading is genuinely live, not the frozen corpus by another route."""
    reading = live_health.read()
    assert reading.organ_count > 3, (
        "the freeze-time corpus held three manifests; a live reading returning "
        "three suggests it is reading the frozen corpus"
    )


# ------------------------------------------------------- the guards can bite
def test_the_import_guard_would_catch_a_real_violation():
    """A guard never seen to fail is indistinguishable from a broken one."""
    tree = ast.parse("from evolution.repair.spec import REQUIRED_REFUSALS\n")
    caught = [n for n in ast.walk(tree)
              if isinstance(n, ast.ImportFrom) and n.module
              and "repair.spec" in n.module]
    assert caught, "the import guard's own pattern does not match a real import"


def test_the_comparison_guard_would_catch_a_real_violation():
    tree = ast.parse("assert reading.unresolved == 7\n")
    caught = [n for n in ast.walk(tree)
              if isinstance(n, ast.Compare)
              and any(isinstance(o, ast.Constant) and o.value == 7
                      for o in [n.left, *n.comparators])]
    assert caught, "the comparison guard's own pattern does not match `== 7`"


# --------------------------------------------------------- behaviour, exercised
def test_reading_the_frozen_corpus_through_the_live_reader_gives_the_old_shape():
    """The reader is honest about whatever directory it is pointed at.

    Pointing it at the frozen corpus reproduces the freeze-time shape, which
    proves the difference between the two readings is the *corpus*, not the
    reader. Without this, a divergence could equally be a bug in this module.
    """
    frozen = live_health.read(spec.CORPUS_DIR)
    assert frozen.organ_count == 3
    assert frozen.unresolved == spec.REQUIRED_REFUSALS["unresolved_count"]

    live = live_health.read()
    assert live.organ_count != frozen.organ_count


def test_structural_findings_counts_defects_and_not_open_questions():
    """`unresolved` is excluded on purpose, and that choice is load-bearing.

    An unresolved field is the linker declining to invent an answer — an open
    question with an owner. Counting those as defects would make a growing
    institution look like a degrading one, which is the exact misreading that
    produced CONTRADICTION-0001.
    """
    reading = live_health.read()
    assert reading.structural_findings == (
        len(reading.untyped) + len(reading.unproduced)
        + len(reading.overlapping_authority))
    assert reading.unresolved > 0, "fixture assumption: live corpus has open fields"
    # Growth in open questions must not move the defect count.
    assert reading.structural_findings < reading.unresolved


@pytest.mark.parametrize("field", [
    "organ_count", "edges", "unresolved", "untyped", "unproduced",
    "unconsumed", "overlapping_authority", "fully_connected",
])
def test_the_reading_is_frozen_so_a_caller_cannot_edit_it_into_a_better_story(
        field):
    reading = live_health.read()
    with pytest.raises(Exception):
        setattr(reading, field, None)
