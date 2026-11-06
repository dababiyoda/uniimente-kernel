"""Section 42: Goal Gravity counts community intake once per independent source.

Two ingested copies from one community source are two ledger items. The gravity turn's
wake reason counts the signals that woke the goal. Copies of one source must not move
that count by their volume.
"""
from __future__ import annotations

import pytest

from greg import dataplane
from greg.body import Body
from tests.unit.test_greg_goal_gravity import World

MID_TEXT = "m:watch c.txt is broken"


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


@pytest.fixture
def fast(monkeypatch):
    """Skip the separate-process appraisal of each mission hold, as the goal-gravity suite does."""
    monkeypatch.setattr(Body, "_close_out", lambda self, now: None)


def _feed(world, source: str, content: str) -> None:
    with world.body() as body:
        dataplane.ingest(body.journal, source=source, content=content, channel="community")


def _wake_reason(world) -> str:
    return world.projection()["goals"][0]["wake_reason"]


def test_two_copies_of_one_community_source_count_once(world, fast):
    world.start()
    world.tick(6)
    _feed(world, "community://member-a", f"{MID_TEXT}, copy one")
    _feed(world, "community://member-a", f"{MID_TEXT}, copy two please")
    world.tick()
    assert _wake_reason(world) == "relevant evidence: 1 signal(s)"


def test_two_independent_community_sources_count_as_two(world, fast):
    world.start()
    world.tick(6)
    _feed(world, "community://member-a", f"{MID_TEXT} according to member a")
    _feed(world, "community://member-b", f"{MID_TEXT} according to member b")
    world.tick()
    assert _wake_reason(world) == "relevant evidence: 2 signal(s)"
