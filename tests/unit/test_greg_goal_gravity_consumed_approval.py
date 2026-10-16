"""A paid goal approval funds one run (#157). Once that run is booked, it is not the founder's answer to the goal's
next ask about the same move: while the mission waits on another decision, only the goal can ask ahead for it."""
from egregore.gravity import GoalGravityLoop
from tests.greg_fixtures import mission, note_check, write_strategy
from tests.unit.test_greg_goal_gravity import GOAL, MID, World, ship_move, fast  # noqa: F401


class ThreeCheckWorld(World):
    """c: free in-cone w; d: paid out-of-cone w2 ($0.10, the goal's move); e: free out-of-cone w3."""
    def mission_spec(self, **kw):
        return mission(MID, checks=[note_check("c", self.ws / "c.txt", "ok"),
                                    note_check("d", self.ws / "d.txt", "shipped"),
                                    note_check("e", self.ws / "e.txt", "extra")],
                       strategies=[write_strategy("w", "c.txt", "ok", ["c"]),
                                   write_strategy("w2", "d.txt", "shipped", ["d"], cost_usd=0.10),
                                   write_strategy("w3", "e.txt", "extra", ["e"])],
                       capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:c.txt"), budget=1.0,
                       closure={"kind": "infinite", "ladder": [["c", "d", "e"]], "cadence_seconds": 86400}, **kw)


def test_a_consumed_paid_goal_approval_does_not_answer_the_goals_next_ask(tmp_path, fast):
    world = ThreeCheckWorld(tmp_path)
    world.ws.mkdir(parents=True, exist_ok=True)
    (world.ws / "e.txt").write_text("extra")
    gid, _ = world.start(GOAL(moves=(ship_move(estimated_cost_usd=0.10),)))
    world.tick(6)
    first = [r for r in world.w2_requests() if (r.get("evidence") or {}).get("goal_id") == gid]
    assert len(first) == 1
    world.submit("DECISION", {"request_id": first[0]["request_id"], "answer": "approve", "reason": "ship it"})
    world.tick(8)
    assert [e for e in world.events("mission.action") if e["action_id"] == "w2" and e["status"] == "DONE"]
    assert world.book().missions[MID].spent_usd >= 0.10            # the one run that approval funded is booked

    (world.ws / "e.txt").unlink()                                   # the mission now waits on its own ask for w3
    world.clock.advance(120)
    world.ingest("ops", "m:watch e.txt broken")
    world.tick(4)
    assert world.book().missions[MID].blocker["action_id"] == "w3"

    since = len(world.records(GoalGravityLoop.TURN_RECORD))
    (world.ws / "d.txt").unlink()                                   # the goal's move regresses meanwhile
    world.clock.advance(120)
    world.ingest("ops", "m:watch d.txt broken")
    world.tick(6)

    suppressed = [tuple(s) for t in world.records(GoalGravityLoop.TURN_RECORD)[since:]
                  for s in (t["turn"].get("routing") or {}).get("suppressed", [])]
    assert not [s for s in suppressed if s[1] == "already answered by founder"], suppressed
    asks = [r["request_id"] for r in world.w2_requests() if (r.get("evidence") or {}).get("goal_id") == gid]
    assert len(asks) == 2 and asks[0] == first[0]["request_id"]     # one new ask, at the booked spend state
    assert [r for r in world.book().open_requests() if r.get("action_id") == "w2"]
