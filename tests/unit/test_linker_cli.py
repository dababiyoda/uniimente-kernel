"""`python -m linker` must report the real graph, and must not shrink.

ChatGPT's Part 2 relay asked for "actual linker output with every unresolved
row preserved". The failure mode worth guarding is not a crash — it is a
report that quietly stops printing the rows that did not resolve, or that
recomputes the manifest/identity reconciliation and disagrees with
`discovery.service`.
"""
from __future__ import annotations

import io
import contextlib

import pytest

from discovery.service import CapabilityDiscoveryService
from linker.__main__ import main
from linker.linker import InstitutionalLinker
from linker.manifest import load_all


@pytest.fixture(scope="module")
def output() -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main([])
    assert code == 0
    return buf.getvalue()


def test_every_unresolved_row_is_printed(output):
    """The count in the header must equal the rows the linker actually holds."""
    report = InstitutionalLinker(load_all()).link()
    assert report.unresolved, "the fixture is meaningless if nothing is unresolved"
    assert f"UNRESOLVED — declared open by the organ itself, never invented here — " \
           f"{len(report.unresolved)}" in output
    for _organ, question in report.unresolved:
        assert question in output, f"unresolved row silently dropped: {question!r}"


def test_the_status_vocabulary_contradiction_survives_the_report(output):
    """BLK-4 must stay visible in the output ChatGPT consumes."""
    assert "STATUS VOCABULARY CONTRADICTION" in output


def test_reconciliation_agrees_with_discovery(output):
    """One answer to the organ arithmetic, not two that drift apart."""
    rec = CapabilityDiscoveryService().identity_reconciliation()
    assert f"manifests loaded      : {rec['manifests_published']}" in output
    assert f"identities registered : {rec['identity_registered']}" in output
    assert f"in both registers                        : {len(rec['both'])}" in output
    assert ("manifested without identity registration : "
            f"{len(rec['manifested_without_identity_registration'])}") in output
    assert ("registered without manifest              : "
            f"{len(rec['registered_without_manifest'])}") in output


def test_the_report_separates_discovery_from_activation(output):
    """Never let a manifest read as an activation."""
    assert "Neither column is activation" in output
    assert "grants nothing and activates nothing" in output


def test_unproduced_and_untyped_rows_are_named_not_summarised(output):
    report = InstitutionalLinker(load_all()).link()
    for organ, contract in report.unproduced:
        assert contract in output and organ in output
    for organ, contract in report.untyped:
        assert contract in output and organ in output


def test_overlapping_authority_is_reported(output):
    report = InstitutionalLinker(load_all()).link()
    assert "OVERLAPPING AUTHORITY" in output
    for _organ, capability in report.overlapping_authority:
        assert capability in output
