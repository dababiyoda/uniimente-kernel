"""P2 — the evaluator boundary must be proven by attack, not asserted.

These tests fail the build if the chamber stops being a boundary, and — equally
important — if the hostile probe stops being able to detect that. A probe that
reports "denied" in both an isolated and a deliberately broken chamber is dead,
and would certify any configuration at all.

Skipped rather than failed when the environment cannot construct a chamber:
an unprivileged runner genuinely cannot mount, and reporting that as a boundary
failure would be as wrong as reporting it as a pass.
"""
from __future__ import annotations

import pytest

from runtime.evaluator import isolation


@pytest.fixture(scope="module")
def verdict() -> isolation.IsolationVerdict:
    try:
        return isolation.prove_isolation()
    except isolation.IsolationUnavailable as exc:
        pytest.skip(f"chamber cannot be built here: {exc}")


def test_isolated_chamber_denies_every_prohibited_route(verdict):
    assert verdict.isolated.breaches == [], (
        f"candidate escaped an isolated chamber via {verdict.isolated.breaches}"
    )


def test_probe_examined_every_declared_route(verdict):
    """Non-vacuity: a clean sheet is only meaningful if every route was tried."""
    attempted = set(verdict.isolated.receipts)
    missing = set(isolation.PROHIBITED_ROUTES) - attempted
    assert not missing, f"probe never attempted {sorted(missing)}"


def test_the_probe_can_still_detect_a_breach(verdict):
    """Negative control. Without this the whole proof is worthless."""
    assert verdict.broken.breaches, (
        "the hostile probe reported no breach even in a deliberately broken "
        "chamber — the instrument is dead and certifies nothing"
    )


def test_isolated_and_broken_are_distinguishable(verdict):
    assert verdict.discriminates
    assert verdict.verdict == "EVALUATOR_ISOLATION_PROVEN"


def test_the_repository_is_what_the_broken_chamber_exposes(verdict):
    """The control must breach on repository reads specifically.

    A broken chamber that leaked something unrelated would prove the probe
    detects *a* difference, not that it detects the difference that matters.
    """
    for route in ("read_frozen_contract", "read_repair_spec", "traverse_to_parent_repo"):
        assert route in verdict.broken.breaches, f"{route} did not breach in the control"


def test_candidate_can_still_write_its_own_workspace(verdict):
    """Inverse control: a chamber that denies everything is broken, not isolated."""
    assert verdict.isolated.receipts[isolation.REQUIRED_SUCCESS_ROUTE] == "OK_EXPECTED"


def test_network_is_denied_in_both_configurations(verdict):
    """Net namespace is independent of the filesystem bind — verify separately."""
    for result in (verdict.isolated, verdict.broken):
        assert result.receipts["network_ifaces"] == "denied"
        assert result.receipts["network_connect"] == "denied"


def test_host_environment_does_not_cross_the_boundary(verdict):
    """Measured leak: a live cloud credential reached the chamber until env -i."""
    assert verdict.isolated.receipts["env_leaks_protected"] == "denied"


def test_unavailable_environment_raises_rather_than_returning_a_pass():
    """'Could not run' must never be reachable as 'nothing breached'."""
    assert issubclass(isolation.IsolationUnavailable, RuntimeError)
    with pytest.raises(ValueError):
        isolation.run_probe("not-a-mode")
