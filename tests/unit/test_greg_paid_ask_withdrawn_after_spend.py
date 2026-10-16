"""A paid ask whose spend state has passed can change nothing; it must not stay open as the goal's ask.
Third review of PR #184; pre-existing (#157), the same at 2cf4bdc.
"""
from tests.greg_fixtures import mission, note_check, write_strategy
from tests.unit.test_greg_goal_gravity import GOAL, MID, World, ship_move, fast  # noqa: F401


class PaidRepairWorld(World):
    """Mission F with a paid in-cone repair (w, $0.05) and a paid out-of-cone ship (w2, $0.10)."""
    def mission_spec(self, **kw):
        return mission(MID, checks=[note_check("c", self.ws / "c.txt", "ok"), note_check("d", self.ws / "d.txt", "shipped")],
                       strategies=[write_strategy("w", "c.txt", "ok", ["c"], cost_usd=0.05),
                                   write_strategy("w2", "d.txt", "shipped", ["d"], cost_usd=0.10)],
                       capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:c.txt"), budget=1.0,
                       closure={"kind": "infinite", "ladder": [["c"], ["d"]], "cadence_seconds": 86400}, **kw)


class TwoRepairWorld(World):
    """c, c2: paid in-cone repairs ($0.05 each); d: the goal's paid out-of-cone ship w2 ($0.10); e: free, out of cone."""
    def mission_spec(self, **kw):
        return mission(MID, checks=[note_check("c", self.ws / "c.txt", "ok"), note_check("c2", self.ws / "c2.txt", "ok2"),
                                    note_check("d", self.ws / "d.txt", "shipped"), note_check("e", self.ws / "e.txt", "extra")],
                       strategies=[write_strategy("w", "c.txt", "ok", ["c"], cost_usd=0.05),
                                   write_strategy("wb", "c2.txt", "ok2", ["c2"], cost_usd=0.05),
                                   write_strategy("w2", "d.txt", "shipped", ["d"], cost_usd=0.10),
                                   write_strategy("w3", "e.txt", "extra", ["e"])],
                       capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:c.txt", "workspace:c2.txt"),
                       budget=1.0, closure={"kind": "infinite", "ladder": [["c", "c2", "d", "e"]],
                                            "cadence_seconds": 86400}, **kw)


def _done(world, aid):
    return [e for e in world.events("mission.action") if e["action_id"] == aid and e["status"] == "DONE"]


def _open_w2(world):
    return [r["request_id"] for r in world.book().open_requests() if r.get("action_id") == "w2"]


def test_the_goals_open_paid_ask_after_a_preparation_spend_is_one_the_founder_can_approve(tmp_path, fast):
    world = PaidRepairWorld(tmp_path)
    gid, _ = world.start(GOAL(moves=(ship_move(estimated_cost_usd=0.10),)))
    world.tick(6)
    assert len([r for r in world.w2_requests() if (r.get("evidence") or {}).get("goal_id") == gid]) == 1
    spent = world.book().missions[MID].spent_usd
    (world.ws / "c.txt").write_text("damaged")
    world.ingest("ops", "c.txt looks broken")       # the goal wakes and pulls the blocked mission
    world.tick(5, step=30.0)                        # preparation re-runs the paid in-cone repair w
    assert world.book().missions[MID].spent_usd > spent
    shown = world.projection()["goals"][0]["open_requests"]
    assert len(shown) == 1, shown
    world.submit("DECISION", {"request_id": shown[0], "answer": "approve", "reason": "ship it"})
    world.tick(8)
    assert len(_done(world, "w2")) == 1, (
        f"the founder approved the goal's open ask {shown[0]}; w2 ran 0 times and the mission asks again: "
        f"{[r['request_id'] for r in world.w2_requests()]}")
    assert _open_w2(world) == []


def test_no_dead_paid_ask_for_the_move_stays_open_after_the_move_ran(tmp_path, fast):
    world = TwoRepairWorld(tmp_path)
    world.ws.mkdir(parents=True, exist_ok=True)
    (world.ws / "e.txt").write_text("extra")
    gid, _ = world.start(GOAL(moves=(ship_move(estimated_cost_usd=0.10),)))
    world.tick(3)
    blocker = world.book().missions[MID].blocker
    assert blocker and blocker.get("action_id") == "w2"
    world.submit("DECISION", {"request_id": blocker["request_id"], "answer": "approve", "reason": "ship it"})
    world.tick(6)
    assert len(_done(world, "w2")) == 1                                  # the move ran
    assert _open_w2(world) == [], "an ask for w2 that can never fund anything stays open after w2 ran"
    assert world.projection()["goals"][0]["open_requests"] == []
