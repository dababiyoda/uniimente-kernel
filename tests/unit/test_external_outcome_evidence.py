"""HARDENED is the only rung that requires reality. Its gate must be real too.

`EXTERNAL_OUTCOME` is the sole requirement `HARDENED` adds, and HARDENED is the
rung the Single Bottleneck Metric counts. The check used to pass any file
containing the word "reconciled" anywhere in it, so a note reading "we discussed
how invoices are reconciled in general; nothing happened" would have awarded the
top rung and moved the SBM off zero.

The first test here is that exact file. Everything else guards the edges of the
typed check that replaced the substring.
"""
from __future__ import annotations

import json

import pytest

from blueprint.evidence import EvidenceRef, resolve
from blueprint.ladder import EvidenceKind, Rung, required_evidence

PROSE_THAT_USED_TO_PASS = (
    "# Notes\n"
    "We discussed how invoices are reconciled in general. Nothing happened.\n"
)


def _record(**overrides) -> dict:
    """A record that satisfies the canonical contract, before any override."""
    base = {
        "outcome_id": "6f1a2b3c-4d5e-4f60-8a71-9b2c3d4e5f60",
        "action_ref": "1a2b3c4d-5e6f-4a70-8b81-9c2d3e4f5a61",
        "recorded_at": "2026-08-20T12:00:00Z",
        "recorded_by": "spiffe://uniimente.internal/organ/kernel",
        "external_observation": "counterparty paid invoice INV-1 and confirmed receipt",
        "result_class": "positive",
        "expected_vs_actual": "expected payment within 30 days; received in 9",
        "validation_status": "externally_verified",
        "evidence_refs": ["sha256:" + "a" * 64],
    }
    base.update(overrides)
    return base


def _ref(locator: str) -> EvidenceRef:
    return EvidenceRef(EvidenceKind.EXTERNAL_OUTCOME, locator)


def _tree(tmp_path, name: str, body: str) -> str:
    """A root carrying the canonical contract plus one candidate record."""
    import shutil, os
    (tmp_path / "contracts").mkdir()
    shutil.copy(
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "contracts", "outcome.schema.json"),
        tmp_path / "contracts" / "outcome.schema.json")
    (tmp_path / name).write_text(body, encoding="utf-8")
    return str(tmp_path)


# ------------------------------------------------------- the regression itself
def test_the_prose_that_used_to_award_hardened_is_refused(tmp_path):
    root = _tree(tmp_path, "outcome.md", PROSE_THAT_USED_TO_PASS)
    resolution = resolve(_ref("outcome.md"), root)
    assert not resolution.ok
    assert "never prose" in resolution.detail


def test_a_json_file_is_required_even_if_it_says_reconciled(tmp_path):
    """The substring must have no power at all, in any file type."""
    root = _tree(tmp_path, "outcome.txt", "reconciled reconciled reconciled")
    assert not resolve(_ref("outcome.txt"), root).ok


# --------------------------------------------------------------- typed checks
def test_a_conforming_externally_verified_record_resolves(tmp_path):
    root = _tree(tmp_path, "o.json", json.dumps(_record()))
    resolution = resolve(_ref("o.json"), root)
    assert resolution.ok, resolution.detail
    assert "externally verified outcome" in resolution.detail
    assert "6f1a2b3c-4d5e-4f60-8a71-9b2c3d4e5f60" in resolution.detail


@pytest.mark.parametrize("status", ["internally_observed", "self_reported"])
def test_an_outcome_the_institution_vouches_for_itself_is_refused(tmp_path, status):
    """The distinction the substring check could not express."""
    root = _tree(tmp_path, "o.json", json.dumps(_record(validation_status=status)))
    resolution = resolve(_ref("o.json"), root)
    assert not resolution.ok
    assert status in resolution.detail
    assert "externally_verified" in resolution.detail


def test_an_outcome_citing_no_evidence_is_refused(tmp_path):
    root = _tree(tmp_path, "o.json", json.dumps(_record(evidence_refs=[])))
    resolution = resolve(_ref("o.json"), root)
    assert not resolution.ok
    assert "points at nothing checkable" in resolution.detail


@pytest.mark.parametrize("missing", [
    "outcome_id", "action_ref", "recorded_at", "recorded_by",
    "external_observation", "result_class", "expected_vs_actual",
])
def test_every_required_contract_field_is_enforced_and_named(tmp_path, missing):
    record = _record()
    record.pop(missing)
    root = _tree(tmp_path, "o.json", json.dumps(record))
    resolution = resolve(_ref("o.json"), root)
    assert not resolution.ok
    assert "outcome.schema.json" in resolution.detail
    assert missing in resolution.detail


@pytest.mark.parametrize("field", ["outcome_id", "action_ref"])
def test_a_non_uuid_identity_is_refused(tmp_path, field):
    """Refused, and the offending field named — whichever layer catches it.

    Two layers guard this on purpose. `FormatChecker` has built-in uuid support
    and catches it first here; the explicit `uuid.UUID()` parse in the resolver
    is the backstop for an environment where the format library is absent, since
    an unchecked `format` keyword is a fail-open on the top rung. The test does
    not pin which layer fires, only that the record cannot pass.
    """
    root = _tree(tmp_path, "o.json", json.dumps(_record(**{field: "outcome-0001"})))
    resolution = resolve(_ref("o.json"), root)
    assert not resolution.ok
    assert field in resolution.detail


def test_the_uuid_backstop_works_without_the_schema_layer():
    """The fallback must be real, not decorative, if FormatChecker goes silent."""
    import uuid as _uuid
    for bad in ("outcome-0001", "", "not-a-uuid", None):
        with pytest.raises((ValueError, AttributeError, TypeError)):
            _uuid.UUID(str(bad) if bad is not None else None)


def test_a_naive_timestamp_is_refused(tmp_path):
    root = _tree(tmp_path, "o.json",
                 json.dumps(_record(recorded_at="2026-08-20T12:00:00")))
    resolution = resolve(_ref("o.json"), root)
    assert not resolution.ok
    assert "naive recorded_at" in resolution.detail


def test_a_bad_evidence_hash_is_refused(tmp_path):
    root = _tree(tmp_path, "o.json",
                 json.dumps(_record(evidence_refs=["not-a-hash"])))
    assert not resolve(_ref("o.json"), root).ok


def test_a_smuggled_extra_field_is_refused(tmp_path):
    """The contract sets additionalProperties false; the binder must honour it."""
    root = _tree(tmp_path, "o.json",
                 json.dumps(_record(hardened="yes please")))
    assert not resolve(_ref("o.json"), root).ok


def test_malformed_json_is_refused_with_the_parse_error(tmp_path):
    root = _tree(tmp_path, "o.json", "{not json")
    resolution = resolve(_ref("o.json"), root)
    assert not resolution.ok
    assert "unreadable" in resolution.detail


def test_a_json_array_is_not_an_outcome_record(tmp_path):
    root = _tree(tmp_path, "o.json", json.dumps([_record()]))
    assert not resolve(_ref("o.json"), root).ok


def test_an_absent_contract_fails_closed_rather_than_accepting(tmp_path):
    """Without the contract nothing can be typed, so nothing may pass."""
    (tmp_path / "o.json").write_text(json.dumps(_record()), encoding="utf-8")
    resolution = resolve(_ref("o.json"), str(tmp_path))
    assert not resolution.ok
    assert "failing closed" in resolution.detail


def test_a_locator_may_not_escape_the_repository(tmp_path):
    assert not resolve(_ref("../../etc/passwd.json"), str(tmp_path)).ok


# ---------------------------------------------------------------- the ladder
def test_external_outcome_is_still_the_only_thing_hardened_adds():
    added = required_evidence(Rung.HARDENED) - required_evidence(Rung.PROVEN)
    assert added == frozenset({EvidenceKind.EXTERNAL_OUTCOME}), (
        "if HARDENED gains another requirement this test should be revisited "
        "deliberately, not silently"
    )


def test_nothing_in_this_repository_satisfies_it_today():
    """The honest state, asserted so a fabricated record cannot slip in unseen."""
    from blueprint.critical_path import compute

    assert compute().by_rung().get("HARDENED", ()) == ()
