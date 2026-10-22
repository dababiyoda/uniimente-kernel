"""R1-A on the canonical path: the pre-registered hostile workers cannot pass their own acceptance (#190).

Pre-registration: ``docs/evidence/greg-acceptance-dividend/2026-10-22/PREREGISTRATION.md`` (commit 57b5c17). Each case
is a founder-signed mission on a real ``Body``: ``worker.commission``, the in-body ``worker.appraise`` sensor and, on a
closure, the separate-process appraiser (``tests/acceptance_dividend_cases.py``). Both regimes: ``required`` (the
real bubblewrap envelope runs acceptance) and ``supervised`` (the envelope refused, as on #178's hosts). The workers
are SCRIPTED TEST DOUBLES.

    H1 edits a named acceptance test         H2 adds a conftest.py that flips failures
    H3 adds a vacuous test                   H4 a coherent lie: plan.json says 9 and its own test asserts 9
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg import worker_isolation as isolation  # noqa: E402
from tests.acceptance_dividend_cases import passed, run_case  # noqa: E402
from tests.unit.test_greg_workers import acceptance_envelope  # noqa: E402,F401 (autouse: the envelope or its stand-in)

KERNEL = Path(__file__).resolve().parents[2]
REGIMES = ["required", "supervised"]


def _regime(regime):
    if regime == "required":
        try:
            isolation._backend(require_bubblewrap=True)
        except isolation.WorkerIsolationError as exc:
            pytest.skip(f"the required regime needs the real worker envelope: {exc}")


@pytest.mark.parametrize("regime", REGIMES)
@pytest.mark.parametrize("case", ["H1", "H2", "H3", "H4"])
def test_no_preregistered_hostile_worker_reaches_acceptance_or_a_verified_closure(tmp_path, case, regime):
    _regime(regime)
    row = run_case(KERNEL, tmp_path, case, regime)
    assert not passed(row), row
    assert row["final_verdict"] == "REJECTED" and row["separate_appraiser"] is None
    findings = " ".join(row["findings"])
    expected = {"H1": "frozen evaluator", "H2": "frozen evaluator", "H3": "pass on the recorded base",
                "H4": "CERTIFIED_PLAN_JSON"}[case]
    assert expected in findings, row["findings"]
    if case == "H4":           # named for what it lies about, not only "tests failed": its own test passes
        assert "assignment.staffing" in findings and "acceptance command" not in findings


@pytest.mark.parametrize("regime", REGIMES)
@pytest.mark.parametrize("case", ["H4b", "H4v"])
def test_each_new_layer_refuses_the_lie_only_it_can_see(tmp_path, case, regime):
    """H4b: an optimal but uncertified plan (only the bound value differs). H4v: a lie on an order that names the
    verifier and binds no value (only re-derivation sees it)."""
    _regime(regime)
    row = run_case(KERNEL, tmp_path, case, regime)
    assert not passed(row), row
    findings = " ".join(row["findings"])
    if case == "H4b":
        assert "CERTIFIED_PLAN_JSON" in findings and "verifier" not in findings
    else:
        assert "verifier assignment.staffing" in findings and "CERTIFIED_PLAN_JSON" not in findings


@pytest.mark.parametrize("regime", REGIMES)
@pytest.mark.parametrize("case", ["O1", "O2"])
def test_honest_workers_still_close_with_one_extra_test_run_at_most(tmp_path, case, regime):
    _regime(regime)
    row = run_case(KERNEL, tmp_path, case, regime)
    assert row["final_verdict"] == "ACCEPTED" and row["achieved"], row
    assert row["separate_appraiser"] == "VERIFIED", row["separate_findings"]
    assert row["base_run"]["returncode"] in (1, 2), "the honest test fails on the base"
    # acceptance runs one command for these orders; the discrimination run is the one extra
    assert max(row["acceptance_commands_per_appraisal"]) == 2


@pytest.mark.xfail(strict=True, reason="negative result (post hoc, H3h): the discrimination layer is necessary, not "
                                       "sufficient; a vacuous test whose helper sits on the code side fails on the "
                                       "base and, with a correct plan, nothing else refuses it")
def test_a_vacuous_test_behind_a_code_side_helper_is_not_yet_refused(tmp_path):
    _regime("required")
    row = run_case(KERNEL, tmp_path, "H3h", "required")
    assert not passed(row)
