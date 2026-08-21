"""Gate A, enforced by the build rather than asserted in a document.

These tests fail if a second authority government appears. They are the reason
ACTIVE_CANONICAL_AUTHORITY_PROTOCOLS = 1 is a measurement and not a claim.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from aperture import dispositions as D

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Directories whose code runs on the canonical authority path. Superseded
# engines, their own tests, the conformance harness and historical trees are
# deliberately excluded: they are preserved, not canonical.
CANONICAL_DIRS = ("aperture",)


def test_exactly_one_implementation_may_issue_authority():
    """THE Gate A metric."""
    assert D.active_authority_count() == 1, (
        "more than one implementation is marked may_issue_authority: "
        f"{[d.module for d in D.DISPOSITIONS if d.may_issue_authority]}")


def test_exactly_one_canonical_active_classification():
    assert len(D.canonical_active()) == 1
    assert D.canonical_active()[0].module == "aperture_issuer.issuer"


def test_every_implementation_has_an_explicit_disposition():
    for d in D.DISPOSITIONS:
        assert d.classification in D.CLASSIFICATIONS
        assert d.rationale.strip(), f"{d.module} has no rationale"


def test_superseded_implementations_record_why_they_are_retained():
    """Preservation doctrine: superseded is not deleted, and the reason for
    keeping a thing is part of the institutional record."""
    for d in D.DISPOSITIONS:
        if d.classification in (D.SUPERSEDED, D.HISTORICAL, D.CONFORMANCE_FIXTURE):
            assert d.retained_because.strip(), (
                f"{d.module} is {d.classification} but does not say why it is kept")


def test_no_superseded_engine_may_issue_authority():
    for d in D.DISPOSITIONS:
        if d.classification != D.CANONICAL_ACTIVE:
            assert d.may_issue_authority is False, (
                f"{d.module} is {d.classification} but claims it may issue authority")


def _imports(path: pathlib.Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_canonical_path_does_not_import_a_superseded_engine():
    """Static detection of a second government reaching the canonical path."""
    offenders = []
    for d in CANONICAL_DIRS:
        for py in (ROOT / d).rglob("*.py"):
            for imp in _imports(py):
                for forbidden in D.FORBIDDEN_ON_CANONICAL_PATH():
                    if imp == forbidden or imp.startswith(forbidden + "."):
                        offenders.append(f"{py.relative_to(ROOT)} imports {imp}")
    assert not offenders, (
        "canonical authority code imports a superseded engine:\n  " +
        "\n  ".join(offenders))


def test_the_aperture_has_no_hardcoded_signing_key():
    """The previous signer fell back to a literal. Nothing here may."""
    suspicious = []
    for py in (ROOT / "aperture").rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for marker in ("uniimente-dev-witness-key", "dev-key", "DEV_KEY"):
            # A comment referring to the old defect is fine; an assignment is not.
            for line in text.splitlines():
                if marker in line and "=" in line and not line.strip().startswith("#"):
                    suspicious.append(f"{py.relative_to(ROOT)}: {line.strip()}")
    assert not suspicious, "possible hardcoded key material:\n  " + "\n  ".join(suspicious)


def test_verification_registry_exposes_no_signing_surface():
    """Verification capability must never imply signing capability."""
    from aperture import VerificationRegistry
    public = [a for a in dir(VerificationRegistry) if not a.startswith("_")]
    assert "sign" not in public
    for name in public:
        assert "sign" not in name.lower() or name == "verify", (
            f"VerificationRegistry.{name} looks like a signing surface")


def test_legacy_records_can_never_authorize():
    """Belt and braces: no classification except CANONICAL_ASYMMETRIC authorizes."""
    from aperture.legacy import (AUTHORIZING_CLASSIFICATIONS, CLASSIFICATIONS,
                                 CANONICAL_ASYMMETRIC)
    assert AUTHORIZING_CLASSIFICATIONS == {CANONICAL_ASYMMETRIC}
    for c in CLASSIFICATIONS:
        if c != CANONICAL_ASYMMETRIC:
            assert c not in AUTHORIZING_CLASSIFICATIONS
