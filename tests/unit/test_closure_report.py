"""Registration must stop being worth a rung.

The founder's reconciliation of PR #73 named the defect precisely: the evidence
binder recognised a closure through a textual `ModuleClosures(...)` match without
proving that its five checks passed, so a registration with five trivially-true
stubs would have lifted a technology to EXERCISED. The required remedy was "bind a
commit-pinned passing closure report or leave the ladder at the lower rung".

The decisive test here is `test_a_registration_with_no_proof_earns_nothing`: it
builds a tree that registers a module and proves nothing about it, and asserts the
rung is refused. Everything else guards the edges of that rule.
"""
from __future__ import annotations

import json
import os

import pytest

from blueprint.evidence import EvidenceRef, resolve
from blueprint.ladder import EvidenceKind, Rung, rung_at_or_above
from blueprint.registry import BINDINGS
from closure.report import (
    REPORT_VERSION,
    ClosureReportError,
    generate,
    load,
    proven_closure_modules,
)

STUB = "stub_module"


def _tree(tmp_path, *, report: dict | None) -> str:
    """A minimal root: one registration, and whatever proof we choose to give it."""
    closure_dir = tmp_path / "closure"
    closure_dir.mkdir()
    (closure_dir / "fake_registry.py").write_text(
        f'reg.register(ModuleClosures("{STUB}", {{}}))\n', encoding="utf-8")
    if report is not None:
        (closure_dir / "CLOSURE_REPORT.json").write_text(
            json.dumps(report), encoding="utf-8")
    return str(tmp_path)


def _report(commit: str = "a" * 40, *, complete: bool,
            module: str = STUB, open_closures=()) -> dict:
    return {
        "report_version": REPORT_VERSION,
        "commit": commit,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "modules": {module: {"complete": complete,
                             "open_closures": list(open_closures)}},
    }


def _ref() -> EvidenceRef:
    return EvidenceRef(EvidenceKind.CLOSURE_MODULE, STUB)


# ------------------------------------------------------- the rule that matters
def test_a_registration_with_no_proof_earns_nothing(tmp_path):
    """Textual registration, zero proof. This used to resolve; it must not."""
    root = _tree(tmp_path, report=None)
    resolution = resolve(_ref(), root)
    assert not resolution.ok
    assert "registered" in resolution.detail
    assert "no commit-pinned closure report" in resolution.detail


def test_a_registration_the_report_does_not_cover_earns_nothing(tmp_path):
    """A stale report must not vouch for a module added after it was taken."""
    root = _tree(tmp_path, report=_report(complete=True, module="something_else"))
    resolution = resolve(_ref(), root)
    assert not resolution.ok
    assert "does not cover it" in resolution.detail


def test_a_module_the_report_records_as_incomplete_earns_nothing(tmp_path):
    root = _tree(tmp_path, report=_report(
        complete=False, open_closures=("economic", "regenerative")))
    resolution = resolve(_ref(), root)
    assert not resolution.ok
    assert "incomplete" in resolution.detail
    assert "economic" in resolution.detail, "the open closures must be named"


def test_a_module_proved_passing_earns_the_rung(tmp_path):
    root = _tree(tmp_path, report=_report(complete=True))
    resolution = resolve(_ref(), root)
    assert resolution.ok
    assert "five closures observed passing" in resolution.detail


def test_an_unregistered_module_is_refused_even_with_a_report(tmp_path):
    """Proof without registration is still nothing: both are required."""
    closure_dir = tmp_path / "closure"
    closure_dir.mkdir()
    (closure_dir / "CLOSURE_REPORT.json").write_text(
        json.dumps(_report(complete=True)), encoding="utf-8")
    resolution = resolve(_ref(), str(tmp_path))
    assert not resolution.ok
    assert "no closure registry registers" in resolution.detail


# ----------------------------------------------------------- report integrity
def test_an_unanchored_report_cannot_be_generated():
    for commit in ("", "HEAD", "not-a-sha"):
        with pytest.raises(ClosureReportError):
            generate(commit)


@pytest.mark.parametrize("mutate", [
    lambda r: r.update({"report_version": REPORT_VERSION + 1}),
    lambda r: r.update({"commit": "nonsense"}),
    lambda r: r.update({"modules": {}}),
])
def test_a_malformed_report_reads_as_no_proof_not_as_pass(tmp_path, mutate):
    """Every unreadable shape must degrade to 'no proof', never to 'assume ok'."""
    report = _report(complete=True)
    mutate(report)
    root = _tree(tmp_path, report=report)
    assert load(root) is None
    assert proven_closure_modules(root) == frozenset()
    assert not resolve(_ref(), root).ok


def test_unparseable_json_reads_as_no_proof(tmp_path):
    closure_dir = tmp_path / "closure"
    closure_dir.mkdir()
    (closure_dir / "fake_registry.py").write_text(
        f'ModuleClosures("{STUB}", {{}})\n', encoding="utf-8")
    (closure_dir / "CLOSURE_REPORT.json").write_text("{not json", encoding="utf-8")
    assert load(str(tmp_path)) is None


# --------------------------------------------------- the committed report is true
def test_the_committed_report_matches_a_live_run():
    """A hand-edited status must fail the suite rather than raise a rung.

    The commit SHA in the report is provenance; this content check is the guard.
    """
    committed = load()
    assert committed is not None, "the repository must carry a closure report"
    live = generate("0" * 40)["modules"]
    assert set(live) == set(committed.modules), (
        "the committed report covers a different module set than a live run; "
        "regenerate with: python -m closure.report write"
    )
    disagreements = [
        name for name, (ok, _) in committed.modules.items()
        if ok != live[name]["complete"]
    ]
    assert disagreements == [], (
        f"the committed report disagrees with a live run for {disagreements}"
    )


def test_every_binding_at_exercised_or_above_has_a_proved_closure():
    """The ladder's own bindings must satisfy the rule, not just the rule exist."""
    proven = proven_closure_modules()
    for tech_id, binding in sorted(BINDINGS.items()):
        if binding.claimed_rung is None:
            continue
        if not rung_at_or_above(binding.claimed_rung, Rung.EXERCISED):
            continue
        modules = [ref.locator for ref in binding.evidence
                   if ref.kind is EvidenceKind.CLOSURE_MODULE]
        assert modules, f"#{tech_id} claims {binding.claimed_rung.value} with no closure ref"
        for module in modules:
            assert module in proven, (
                f"#{tech_id} claims {binding.claimed_rung.value} on closure "
                f"{module!r}, which no commit-pinned report proves passing"
            )


def test_the_report_grants_nothing():
    import closure.report as report_module

    for name in ("authorize", "activate", "promote", "grant", "approve"):
        assert not hasattr(report_module, name)


def test_cli_show_does_not_write(tmp_path):
    from closure.report import REPORT_PATH, main

    before = os.path.getmtime(REPORT_PATH)
    assert main(["show", "--commit", "b" * 40]) == 0
    assert os.path.getmtime(REPORT_PATH) == before
