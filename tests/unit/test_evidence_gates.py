"""Existence is not evidence. Each gate must refuse the empty version of itself.

Three kinds passed on mere presence: a test that exists, a path that exists, a
schema that parses. So `def test_x(): pass` bought BUILT, a zero-byte file bought
SKETCHED, and `{}` bought PROVEN. The first is the thin-test vector this ladder's
own adversarial pass recorded as unresolved and accepted with a threshold.

None of this closes that objection. A body containing `print("ok")` still passes,
because a call can raise and the binder cannot tell a real check from a decorative
one without running it. The floor moves from "it exists" to "it could fail".
"""
from __future__ import annotations

import json
import os

import pytest

from blueprint.evidence import EvidenceRef, resolve, weak_spec_anchors
from blueprint.ladder import EvidenceKind
from blueprint.registry import BINDINGS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _test_ref(locator: str) -> EvidenceRef:
    return EvidenceRef(EvidenceKind.TEST_NODE, locator)


def _write(tmp_path, name: str, body: str) -> str:
    (tmp_path / name).write_text(body, encoding="utf-8")
    return str(tmp_path)


# ------------------------------------------------------------------ TEST_NODE
@pytest.mark.parametrize("body,why", [
    ("def test_thin():\n    pass\n", "bare pass"),
    ('def test_thin():\n    """Only a docstring."""\n', "docstring only"),
    ("def test_thin():\n    assert True\n", "assert True asserts nothing"),
    ("def test_thin():\n    assert 1\n", "truthy constant"),
    ('def test_thin():\n    assert "yes"\n', "truthy string"),
    ("def test_thin():\n    x = 2 + 2\n", "no failing statement"),
])
def test_a_body_that_cannot_fail_is_refused(tmp_path, body, why):
    root = _write(tmp_path, "t.py", body)
    resolution = resolve(_test_ref("t.py::test_thin"), root)
    assert not resolution.ok, why
    assert "cannot fail" in resolution.detail


@pytest.mark.parametrize("body", [
    "def test_real():\n    assert 2 + 2 == 4\n",
    "import jsonschema\ndef test_real():\n    jsonschema.validate({}, {})\n",
    "import pytest\ndef test_real():\n    with pytest.raises(ValueError):\n        int('x')\n",
    "def test_real():\n    raise SystemExit(0)\n",
    "def test_real():\n    assert True\n    assert 2 + 2 == 4\n",
])
def test_a_body_that_can_fail_resolves(tmp_path, body):
    root = _write(tmp_path, "t.py", body)
    resolution = resolve(_test_ref("t.py::test_real"), root)
    assert resolution.ok, resolution.detail
    assert "able to fail" in resolution.detail


def test_a_raising_call_counts_even_with_no_assert_keyword(tmp_path):
    """The false negative that taught this check its shape.

    `jsonschema.validate(grant, schema)` raises on failure and is a stronger
    check than `assert`. My first draft of this detector looked only for the
    `assert` keyword and wrongly flagged a real test in
    tests/unit/test_consequence_gate.py.
    """
    root = _write(tmp_path, "t.py",
                  "import jsonschema\n"
                  "def test_real():\n"
                  "    jsonschema.validate({'a': 1}, {'required': ['a']})\n")
    assert resolve(_test_ref("t.py::test_real"), root).ok


def test_an_unparseable_test_file_fails_closed(tmp_path):
    root = _write(tmp_path, "t.py", "def test_real(:\n")
    resolution = resolve(_test_ref("t.py::test_real"), root)
    assert not resolution.ok
    assert "could not be parsed" in resolution.detail


def test_an_absent_function_is_still_refused(tmp_path):
    root = _write(tmp_path, "t.py", "def test_other():\n    assert False\n")
    assert not resolve(_test_ref("t.py::test_missing"), root).ok


# --------------------------------------------------------- IMPLEMENTATION_PATH
def test_a_zero_byte_file_is_not_code(tmp_path):
    (tmp_path / "empty.py").write_text("", encoding="utf-8")
    resolution = resolve(
        EvidenceRef(EvidenceKind.IMPLEMENTATION_PATH, "empty.py"), str(tmp_path))
    assert not resolution.ok
    assert "zero bytes" in resolution.detail


def test_an_empty_directory_is_not_code(tmp_path):
    (tmp_path / "pkg").mkdir()
    resolution = resolve(
        EvidenceRef(EvidenceKind.IMPLEMENTATION_PATH, "pkg"), str(tmp_path))
    assert not resolution.ok
    assert "empty" in resolution.detail


def test_a_populated_path_resolves(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "m.py").write_text("x = 1\n", encoding="utf-8")
    assert resolve(EvidenceRef(EvidenceKind.IMPLEMENTATION_PATH, "pkg"),
                   str(tmp_path)).ok
    assert resolve(EvidenceRef(EvidenceKind.IMPLEMENTATION_PATH, "pkg/m.py"),
                   str(tmp_path)).ok


# ------------------------------------------------------------ CONTRACT_SCHEMA
@pytest.mark.parametrize("schema", ["{}", '{"title": "Anything"}', '{"type": "object"}'])
def test_a_schema_that_constrains_nothing_types_no_boundary(tmp_path, schema):
    (tmp_path / "contracts").mkdir()
    (tmp_path / "contracts" / "hollow.schema.json").write_text(schema, encoding="utf-8")
    resolution = resolve(
        EvidenceRef(EvidenceKind.CONTRACT_SCHEMA, "hollow"), str(tmp_path))
    assert not resolution.ok
    assert "constrains nothing" in resolution.detail


def test_a_constraining_schema_resolves(tmp_path):
    (tmp_path / "contracts").mkdir()
    (tmp_path / "contracts" / "real.schema.json").write_text(
        json.dumps({"type": "object", "required": ["a"],
                    "properties": {"a": {"type": "string"}}}), encoding="utf-8")
    assert resolve(EvidenceRef(EvidenceKind.CONTRACT_SCHEMA, "real"),
                   str(tmp_path)).ok


# ------------------------------------------------------------- the real ladder
def test_the_tightening_cost_this_repository_nothing():
    """Every committed reference still resolves, so no rung fell."""
    from blueprint.registry import audit

    problems = [(a.technology_id, a.problems) for a in audit() if a.problems]
    assert problems == [], f"the stricter gates dropped a rung: {problems}"


def test_every_committed_test_node_can_actually_fail():
    refs = [(tid, r.locator) for tid, b in BINDINGS.items() for r in b.evidence
            if r.kind is EvidenceKind.TEST_NODE]
    assert refs
    unresolved = [(tid, loc) for tid, loc in refs
                  if not resolve(_test_ref(loc), ROOT).ok]
    assert unresolved == []


# ------------------------------------------------------- the weakness left open
def test_the_prose_only_spec_anchors_are_pinned_and_cannot_grow_silently():
    """SPEC_DOCUMENT still accepts an anchor found anywhere in the document.

    Tightening it to require a heading would drop these five to UNSUPPORTED,
    which is a founder-level call about what counts as a specification. It is
    surfaced instead of decided, and pinned so a sixth cannot appear unnoticed.
    """
    assert weak_spec_anchors() == (
        (7, "docs/ARCHITECTURE.md#Identity + Authority Fabric"),
        (17, "docs/ARCHITECTURE.md#Causal Memory + Portfolio Governor"),
        (31, "docs/PHASE_ZERO_REPORT.md#embassy pattern"),
        (38, "docs/UNIIMENTE_FINAL_BUILD_ORDER.md#Bridge H: Revenue-to-Regeneration"),
        (54, "docs/UNIIMENTE_FINAL_BUILD_ORDER.md#Bridge H: Revenue-to-Regeneration"),
    )


def test_weak_anchor_reporting_changes_no_rung():
    """It reports. If it ever starts refusing, that is a standard change."""
    for _, locator in weak_spec_anchors():
        assert resolve(EvidenceRef(EvidenceKind.SPEC_DOCUMENT, locator), ROOT).ok
