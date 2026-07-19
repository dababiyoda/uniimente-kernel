"""Whole-Body Closure Controller tests."""
from closure.whole_body import (Loop, LoopEvidence, Verdict,
                                WholeBodyClosureController, evaluate_loop)


def test_open_when_nothing_happened():
    assert evaluate_loop(None) == Verdict.OPEN
    assert evaluate_loop(LoopEvidence(internal_ok=False, external_ok=False)) == Verdict.OPEN


def test_closed_requires_external_consequence():
    assert evaluate_loop(LoopEvidence(internal_ok=True, external_ok=True)) == Verdict.CLOSED


def test_partial_when_external_but_internal_flat():
    assert evaluate_loop(LoopEvidence(internal_ok=False, external_ok=True)) == Verdict.PARTIALLY_CLOSED


def test_falsely_closed_when_internal_metric_without_external_consequence():
    # impressions increased but owned relationships did not
    assert evaluate_loop(LoopEvidence(internal_ok=True, external_ok=False)) == Verdict.FALSELY_CLOSED


def test_controller_flags_false_closure_and_requires_regression():
    c = WholeBodyClosureController()
    result = c.evaluate("change-1", {
        Loop.DISTRIBUTION: LoopEvidence(internal_ok=True, external_ok=False,
                                        detail="impressions up, owned relationships flat"),
        Loop.EXECUTION: LoopEvidence(internal_ok=True, external_ok=True),
    })
    assert result.overall == "FALSELY_CLOSED"
    assert "distribution" in result.falsely_closed
    assert "investigate_false_closure" in result.required_actions
    assert "regress_change" in result.required_actions


def test_controller_closed_when_all_applicable_close():
    c = WholeBodyClosureController()
    result = c.applicable("change-2", {
        Loop.AUTHORITY: LoopEvidence(internal_ok=True, external_ok=True),
        Loop.EXECUTION: LoopEvidence(internal_ok=True, external_ok=True),
        Loop.CONTINUITY: LoopEvidence(internal_ok=True, external_ok=True),
    }, applicable={Loop.AUTHORITY, Loop.EXECUTION, Loop.CONTINUITY})
    assert result.overall == "CLOSED"
    assert result.required_actions == []


def test_a_component_is_not_complete_because_its_code_runs():
    c = WholeBodyClosureController()
    # code ran (technical internal) but nothing external verified anywhere
    result = c.evaluate("change-3", {
        Loop.EXECUTION: LoopEvidence(internal_ok=True, external_ok=False, detail="tests pass locally"),
    })
    assert result.overall == "FALSELY_CLOSED"
