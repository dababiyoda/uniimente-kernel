"""The gap register is the founder's shortest list. It had drifted.

`blueprint/registry.py` carries the institution's own account of what is wrong
with it, ten entries of which belong to the founder. Nothing checked whether
those entries still described the repository, and one of them had stopped:
#26 says `adapters/` is imported by no non-test module, which Bridge A changed.
"""
import ast
import os

import pytest

from blueprint.registry import BINDINGS
from governance import gap_audit
from governance.gap_audit import Verdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- nothing is dropped -------------------------------------------------------

def test_every_registered_gap_appears_exactly_once():
    """An audit that silently omitted a gap would be worse than none.

    The register is the subject; the audit is a projection of it, so the two
    must have the same population.
    """
    rows = gap_audit.audit()
    checked = [r for r in rows if r.verdict is not Verdict.ANCHOR_LOST]

    registered = [(tid, gap)
                  for tid, binding in BINDINGS.items()
                  for gap in binding.gaps]
    reported = [(r.technology_id, r.gap) for r in checked]

    assert sorted(reported) == sorted(registered)
    assert len(reported) == len(set(reported)), "a gap was reported twice"


def test_unchecked_prose_is_counted_rather_than_hidden():
    """Most gap text is prose no static reading can settle.

    Reporting only the checkable ones would make the audit look far more
    authoritative than it is — the exact overstatement it exists to catch.
    """
    rows = gap_audit.audit()
    unchecked = [r for r in rows if r.verdict is Verdict.UNCHECKED]

    assert unchecked, "expected most gaps to be unverifiable prose"
    assert len(unchecked) > len(rows) - len(unchecked), (
        "if most gaps were machine-checked, this claim needs revisiting")


# --- the drift it was built to find -------------------------------------------

def test_a_closed_gap_still_listed_is_reported_stale(monkeypatch):
    """The mechanism, proved against a check that says the gap has closed.

    This audit's first run found a real one: #26 claimed `adapters/` had no
    non-test importer, which stopped being true when Bridge A imported it. That
    gap has since been closed in the register as an authored change, so the
    drift is no longer live — which is why this test drives the mechanism
    directly rather than depending on a defect staying unrepaired.
    """
    real = BINDINGS[7].gaps[0]
    monkeypatch.setattr(gap_audit, "CHECKS", (
        (7, real[:40], lambda: (False, "the repository now says otherwise")),
    ))

    rows = gap_audit.audit()
    stale = [r for r in rows if r.verdict is Verdict.STALE]

    assert len(stale) == 1
    assert stale[0].technology_id == 7
    assert stale[0].evidence == "the repository now says otherwise"
    assert stale[0].needs_attention is True


def test_the_register_currently_carries_no_stale_gap():
    """The standing assertion: the founder's list describes the repository.

    If a future change closes a gap without correcting the register, this fails
    and names it — which is the whole point of the instrument.
    """
    rows = gap_audit.audit()
    stale = [r for r in rows if r.verdict is Verdict.STALE]

    assert stale == [], (
        "the register lists gaps the repository has closed: "
        + "; ".join(f"#{r.technology_id} {r.evidence}" for r in stale))


def test_stale_and_anchor_lost_both_need_attention():
    rows = gap_audit.audit()

    for row in rows:
        expected = row.verdict in (Verdict.STALE, Verdict.ANCHOR_LOST)
        assert row.needs_attention is expected


# --- a check that stops guarding must say so ---------------------------------

def test_a_lost_anchor_reports_rather_than_silently_skipping(monkeypatch):
    """The failure mode that let the drift survive in the first place.

    If a gap is reworded, a check anchored to the old wording matches nothing.
    Dropping it would remove a guard without anyone noticing — so it reports
    ANCHOR_LOST instead.
    """
    monkeypatch.setattr(gap_audit, "CHECKS", (
        (26, "a phrase that appears in no gap anywhere", lambda: (True, "unused")),
    ))

    rows = gap_audit.audit()
    lost = [r for r in rows if r.verdict is Verdict.ANCHOR_LOST]

    assert len(lost) == 1
    assert lost[0].technology_id == 26
    assert "stopped guarding" in lost[0].evidence


def test_every_registered_anchor_currently_matches_a_real_gap():
    """The live counterpart: no check in `CHECKS` is already orphaned."""
    for technology_id, anchor, _check in gap_audit.CHECKS:
        binding = BINDINGS.get(technology_id)
        assert binding is not None, f"#{technology_id} is not a registered technology"
        assert any(anchor in gap for gap in binding.gaps), (
            f"#{technology_id} has no gap containing {anchor!r}")


# --- the audit reports; it does not edit --------------------------------------

def test_the_audit_never_writes_to_the_register():
    """A system that rewrote its own account of what is wrong with it would be
    deleting evidence. Asserted structurally, because the damage would already
    be done by the time a behavioural test noticed.
    """
    path = os.path.join(ROOT, "governance", "gap_audit.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    # `open` for reading is fine; what must never appear is a write mode. An
    # earlier draft of this test also carried `assert x != "open" or True`,
    # which asserts nothing — the exact tautology this suite exists to catch,
    # written into the suite itself.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for arg in node.args + [k.value for k in node.keywords]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    assert arg.value not in ("w", "a", "w+", "a+", "wb", "ab"), (
                        "gap_audit opens something for writing")

    # And it does not import the writers.
    source = open(path, encoding="utf-8").read()
    for forbidden in ("shutil", "os.remove", "os.replace", "Path.write_text"):
        assert forbidden not in source


def test_checks_return_a_reason_not_just_a_boolean():
    """Every verdict in this module has to be able to say why."""
    for _tid, _anchor, check in gap_audit.CHECKS:
        still_open, evidence = check()
        assert isinstance(still_open, bool)
        assert isinstance(evidence, str) and evidence.strip(), (
            "a check returned no evidence")


# --- the checks are honest about what they measure ----------------------------

def test_the_external_reach_check_is_tied_to_the_measured_egress_count():
    """Several gaps are one fact: nothing external can be connected while the
    institution holds zero egress sites. The check must read that measurement
    rather than restate the belief."""
    from assurance.side_effects import Family, inventory

    still_open, evidence = gap_audit._no_external_reach()
    measured = [s for s in inventory(ROOT) if s.family is Family.NETWORK]

    assert still_open is (len(measured) == 0)
    assert str(len(measured)) in evidence


def test_the_importer_check_ignores_tests_and_scripts():
    """A gap about what *runs* must not be satisfied by a test importing it."""
    importers = gap_audit._non_test_importers("adapters")

    assert importers, "expected at least one non-test importer"
    for module in importers:
        head = module.split(os.sep)[0]
        assert head not in ("tests", "scripts")
