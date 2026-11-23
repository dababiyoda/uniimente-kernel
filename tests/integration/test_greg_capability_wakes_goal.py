"""Capability formation is perception for Goal Gravity (LEAP D joined to LEAP A).

A founder-signed goal is bound to a mission blocked on a function GREG cannot yet perform. When the
capability that unblocks it changes state on the ledger (formed or recovered: VERIFIED; attached by the
founder; quarantined or detached), Goal Gravity's sensorium perceives that change as an observation about
the blocked mission, and the goal wakes on it. Timing only: the wake attaches nothing, signs nothing and
widens no scope; a construction still waits for the founder (or a signed read-only auto_attach).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from egregore.goals import GoalSpec, PlanNode, WakeCondition  # noqa: E402
from greg import goal_gravity as gg  # noqa: E402
from greg.body import Body  # noqa: E402
from greg.templates import constructed_question  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed  # noqa: E402

STAFFING = {"workers": [{"id": "Ana", "capacity": 2, "skills": ["forklift"]},
                        {"id": "Ben", "capacity": 4, "skills": ["packing", "forklift"]}],
            "orders": [{"id": "Dock1", "demand": 4, "skill": "forklift"},
                       {"id": "Line", "demand": 2, "skill": "packing"}]}
ENGINE = "acquired.graph.max_flow.networkx"


def goal_for(mid):
    spec = GoalSpec.build(
        founder_intent="staff the docks", desired_state="a certified staffing answer", priority=2,
        authority={"authorized_by": "x", "authorization_ref": "x", "legal_principal": "alfonso_lopez",
                   "max_consequence_class": "read_only"}, time_horizon="weeks",
        plan=[PlanNode.build(node_id="answer", outcome="certified staffing", gate="none",
                             sbm=f"{mid}.certified-answer", sbm_direction="eq", sbm_target=True, interventions=())],
        wake_conditions=(WakeCondition.build(kind="subject", match=mid),), review_cadence_seconds=7 * 86400)
    return {"goal": {k: v for k, v in spec.to_dict().items() if k not in gg.DERIVED_GOAL_FIELDS},
            "missions": [mid], "max_consequence_class": "read_only"}


def settle(body, clock, n=4):
    out = []
    for _ in range(n):
        out.append(body.tick())
        clock.advance(3600)
    return out


def test_a_dormant_goal_wakes_when_the_capability_its_mission_waits_on_is_attached(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = constructed_question(function="assignment.staffing", params=STAFFING)     # no auto_attach
    mid = spec["mission_id"]
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        settle(body, clock, 1)
    drop(home, signed(key, body_id, "GOAL", goal_for(mid)))
    with Body(home, clock=clock) as body:
        body.boot()
        quiet = settle(body, clock, 5)
        [goal_id] = gg.binding_for(body).loop.registry.goals()
        assert quiet[-1]["gravity"]["state"] == "DORMANT"                          # nothing new: the goal sleeps
        assert body.engine.book.missions[mid].blocker["function"] == "assignment.staffing"
        assert body.registry.state[ENGINE] == "VERIFIED"                            # acquired, awaiting the founder
    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": ENGINE}))
    with Body(home, clock=clock) as body:
        body.boot()
        [first] = settle(body, clock, 1)
        world = gg.binding_for(body).loop.world
        belief = world.belief(mid, "capability:assignment.staffing")
        assert first["gravity"]["woken"] == [goal_id]                               # woke on the attach
        assert belief.value == "ATTACHED" and belief.trust_level == "attributed"
        # The wake is timing only: the construction formed over the engine is not attached by it.
        [composed] = [c for c in body.registry.manifests if c.startswith("composed.assignment.staffing.")]
        assert body.registry.state[composed] == "VERIFIED"
        [second] = settle(body, clock, 1)
        assert second["gravity"]["woken"] == [goal_id]                              # and on the formation
        assert world.belief(mid, "capability:assignment.staffing").value == "VERIFIED"
        assert body.registry.state[composed] == "VERIFIED"


def test_only_missions_blocked_on_the_function_or_its_engine_perceive_a_capability_change():
    class FakeGenesis:
        @staticmethod
        def construction_engine(function):
            return {"assignment.staffing": "graph.max_flow"}.get(function)
    m = lambda status, blocker: SimpleNamespace(status=status, blocker=blocker)     # noqa: E731
    book = SimpleNamespace(missions={
        "m:engine": m("BLOCKED", {"function": "assignment.staffing"}),
        "m:direct": m("BLOCKED", {"function": "graph.max_flow"}),
        "m:other": m("BLOCKED", {"function": "project.crash"}),
        "m:done": m("ACHIEVED", {"function": "graph.max_flow"}),
        "m:free": m("ACTIVE", None)})
    body = SimpleNamespace(genesis=FakeGenesis())
    assert gg._blocked_on(body, book, "graph.max_flow") == [("m:direct", "graph.max_flow"),
                                                           ("m:engine", "assignment.staffing")]
    assert gg._blocked_on(body, book, "assignment.staffing") == [("m:engine", "assignment.staffing")]
    assert gg._blocked_on(body, book, "lp.optimize") == []
