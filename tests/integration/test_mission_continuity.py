"""The challenger must beat the conventional route, measured — or not claim to.

Founder clarification 2026-09-09: the conventional durable runtime is the
primary comparator; developmental work is the challenger. So both arms run.
"""
from __future__ import annotations

import pytest

from runtime import mission
from runtime.seam import bindings_p3


@pytest.fixture(scope="module")
def comparison() -> dict:
    available, why = bindings_p3.organs_available()
    if not available:
        pytest.skip(f"cross-repository mission cannot run here: {why}")
    try:
        return mission.run_comparison()
    except mission.MissionUnrunnable as exc:   # pragma: no cover - environment
        pytest.skip(f"mission unrunnable: {exc}")


def test_the_loss_is_load_bearing_in_both_arms(comparison):
    """If the mission does not park, the capability was not really needed."""
    for arm in ("baseline", "challenger_arm"):
        assert comparison[arm]["mission_parked_on_capability_loss"], arm


def test_the_conventional_route_works_and_needs_one_intervention(comparison):
    """The baseline is a real comparator, not a straw man: it completes."""
    baseline = comparison["baseline"]
    assert baseline["mission_completed"]
    assert baseline["external_interventions_required"] == 1


def test_the_challenger_completes_with_no_external_intervention(comparison):
    challenger = comparison["challenger_arm"]
    assert challenger["mission_completed"]
    assert challenger["external_interventions_required"] == 0
    assert challenger["deficit"]["status"] == "VERIFIED"


def test_both_resume_rather_than_restart(comparison):
    """Persistence is the point. A restart is not a resumption."""
    assert comparison["both_resumed_from_checkpoint"]
    for arm in ("baseline", "challenger_arm"):
        assert comparison[arm]["trace"].count("produce_packet") == 1, arm


def test_both_arms_produce_a_real_assessment(comparison):
    for arm in ("baseline", "challenger_arm"):
        assessment = comparison[arm]["assessment"]
        assert assessment["go_no_go"]
        assert assessment["requires_human_approval"] is True


def test_the_win_is_stated_with_its_cost(comparison):
    """A comparison that reports only the favourable side is advocacy."""
    assert comparison["challenger_wins_on_continuity"]
    cost = comparison["what_the_challenger_does_not_win"]
    assert "information" in cost and "degrades" in cost
    assert comparison["closure_claim"].startswith("NONE")
