"""Goal Gravity on the GREG body: the founder effect (ADR-GOAL-GRAVITY-002, second review stage).

Regressions for the founder-effect reviewer's findings. Each test drives a real Body with a real Ed25519 test
founder key (tests.greg_fixtures; NOT Alfonso's key) and asserts the corrected behaviour:

* a paused or abandoned bound mission never faults the turn, and other goals keep pulling their missions;
* intake wakes a goal by what its content names, not merely by the channel it arrived on;
* a goal derived without code (``authorize --from-mission``) wakes on external evidence;
* a goal of an infinite (maintenance) mission never completes for good and still takes founder controls;
* a goal never asks for a move its mission's loop would never run;
* review-then-sign (``--print-only`` then ``authorize FILE``) and supersede work from the CLI.

Passing these tests proves the mechanism on this tree; it is not evidence of any external effect.
"""
from __future__ import annotations

from datetime import timedelta
import json

import pytest

from egregore.goals import GoalSpec, InterventionSpec, PlanNode, WakeCondition
from greg import goal_gravity as gg
from greg.capabilities import BUILTINS
from greg.missions import MissionError
from tests.greg_fixtures import mission, note_check, workspace, write_strategy
from tests.unit.test_greg_goal_gravity import GOAL, MID, expected_w2_request, fast, world  # noqa: F401

MANIFESTS = {m.capability_id: m for m, _ in BUILTINS.values()}
OTHER = "m:other"


def _goal(mid, intent, *, moves=True, wake=None, nodes=None):
    """A founder GOAL body bound to ``mid`` (the ship move outside its cone unless ``moves`` is False)."""
    move = InterventionSpec.build(intervention_id="ship", description="write d.txt (outside the mission's cone)",
                                  action_class="greg.fs.write", requested_capability="fs.write",
                                  consequence_class="internal_write", target="workspace:d.txt",
                                  expected_outcome="d.txt says shipped", payload={"mission_id": mid, "action_id": "w2"})
    plan = nodes or [PlanNode.build(node_id="ship", outcome="d shipped", gate="founder decides", sbm=f"{mid}.d",
                                    sbm_direction="eq", sbm_target=True, interventions=(move,) if moves else ())]
    spec = GoalSpec.build(
        founder_intent=intent, desired_state=f"{intent}: done", priority=2,
        authority={"authorized_by": "x", "authorization_ref": "x", "legal_principal": "alfonso_lopez",
                   "max_consequence_class": "internal_write"}, time_horizon="weeks", plan=plan,
        wake_conditions=wake if wake is not None else (WakeCondition.build(kind="subject", match=mid),
                                                       WakeCondition.build(kind="domain", match="ops")),
        review_cadence_seconds=7 * 86400)
    body = {k: v for k, v in spec.to_dict().items() if k not in gg.DERIVED_GOAL_FIELDS}
    return {"goal": body, "missions": [mid], "max_consequence_class": "internal_write"}


def _gid(world, intent):
    return next(g["goal_id"] for g in world.projection()["goals"] if g["founder_intent"] == intent)


def _pulls(world):
    return len([e for e in world.events("mission.schedule") if "cause" in e])


# -- finding 1 (blocking): a paused or abandoned bound mission never faults the turn -----------------------

def _other_mission(world):
    ws2 = workspace(world.home, OTHER)
    spec = mission(OTHER, checks=[note_check("c", ws2 / "c.txt", "ok")],
                   strategies=[write_strategy("w", "c.txt", "ok", ["c"])],
                   capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:c.txt"),
                   closure={"kind": "infinite", "ladder": [["c"]], "cadence_seconds": 86400})
    return spec, ws2


@pytest.mark.parametrize("state", ["PAUSED", "ABANDONED"])
def test_a_closed_bound_mission_never_faults_the_turn_and_other_goals_keep_pulling(world, fast, state):
    other, ws2 = _other_mission(world)
    world.submit("MISSION", world.mission_spec(), "a1.json")
    world.submit("MISSION", other, "a2.json")
    world.tick()
    world.submit("GOAL", _goal(MID, "goal A"), "b1.json")      # asks for w2 on m:watch
    world.submit("GOAL", _goal(OTHER, "goal B", moves=False, nodes=[PlanNode.build(
        node_id="c", outcome="c healthy", gate="watch", sbm=f"{OTHER}.c", sbm_direction="eq", sbm_target=True),
        PlanNode.build(node_id="n1", outcome="developmental node N1", gate="VEPMC", sbm="greg.path.N1",
                       sbm_direction="eq", sbm_target=True)]), "b2.json")
    world.submit("LIFECYCLE", {"mission_id": MID, "state": state, "reason": "the founder holds A"}, "c1.json")
    world.tick()
    world.tick(6)
    assert (ws2 / "c.txt").read_text() == "ok"
    b_id = _gid(world, "goal B")
    (ws2 / "c.txt").write_text("damaged")                     # B's mission needs its next look now
    out = []
    for n in range(3):
        world.ingest("ops", f"c.txt report {n}: the note looks broken")   # names both missions' c.txt
        out += world.tick(2, step=120.0)
    gravity = [x["gravity"] for x in out if "gravity" in x]
    assert all(g["state"] != "FAULT" for g in gravity), gravity
    assert not world.events("goal_gravity.fault")
    assert any(b_id in g.get("woken", []) and OTHER in g.get("missions_pulled", []) for g in gravity)
    assert (ws2 / "c.txt").read_text() == "ok"                 # goal B's mission was pulled and repaired in cone
    refused = [n for n in world.events("goal.notice") if n["kind"] == "ask_not_recorded"]
    assert len(refused) == 1 and "unknown, closed or paused" in refused[0]["why"]   # one notice, not one per wake
    assert world.w2_requests() == []                           # nothing was asked for the founder's held mission


def test_a_refused_ask_is_settled_until_the_founder_resumes_the_mission_then_asked_once(world, fast):
    world.submit("MISSION", world.mission_spec(), "a.json")
    world.tick()
    world.submit("GOAL", GOAL(), "b.json")
    world.submit("LIFECYCLE", {"mission_id": MID, "state": "PAUSED", "reason": "hold"}, "c.json")
    world.tick()
    gid = world.projection()["goals"][0]["goal_id"]
    for n in range(3):
        world.ingest("ops", f"is the watch healthy? ({n})")
        assert all(x["gravity"]["state"] != "FAULT" for x in world.tick(2, step=120.0))
    assert len([n for n in world.events("goal.notice") if n["kind"] == "ask_not_recorded"]) == 1
    world.submit("LIFECYCLE", {"mission_id": MID, "state": "ACTIVE", "reason": "go on"}, "d.json")
    world.tick()
    world.ingest("ops", "is the watch healthy now?")
    world.tick(3, step=120.0)
    asks = world.w2_requests()
    assert len(asks) == 1 and asks[0]["kind"] == "APPROVAL" and asks[0]["evidence"]["goal_id"] == gid
    assert not world.events("goal_gravity.fault")
