"""A goal must not ask ahead about a move its body cannot run (second review of PR #184, finding 11).

AuthorityOffice.act returns UNAVAILABLE (capability not available on this body) or REFUSED (a target the manifest
does not admit) before it reaches the cone, so the mission's own loop never asks about such an act. The ask-ahead
predicate did not apply that test: a goal recorded an APPROVAL an approve could never act on, and it stayed on the
founder's queue next to the mission's NO_STRATEGY ask. Real Body, signed MISSION/GOAL, test founder key.
"""
import dataclasses
import sys

from greg import capabilities
from tests.greg_fixtures import mission, note_check, write_strategy
from tests.unit.test_greg_goal_gravity import GOAL, MID, World, fast, ship_move  # noqa: F401

NOTIFY = {"action_id": "w2", "capability": "mac.notify", "params": {"text": "d shipped"},
          "target": "founder:alfonso", "advances": ["d"], "rationale": "tell the founder d shipped"}


class NotifyWorld(World):
    def mission_spec(self, **kw):
        return mission(MID, checks=[note_check("c", self.ws / "c.txt", "ok"), note_check("d", self.ws / "d.txt", "shipped")],
                       strategies=[write_strategy("w", "c.txt", "ok", ["c"]), NOTIFY],
                       capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:c.txt"),
                       closure={"kind": "infinite", "ladder": [["c"], ["d"]], "cadence_seconds": 86400}, **kw)


def test_the_goal_does_not_ask_ahead_about_a_move_this_body_cannot_run(tmp_path, fast, monkeypatch):
    if sys.platform == "darwin":       # mac.notify is darwin-only: on a Mac make it the other platform's capability
        manifest, adapter = capabilities.BUILTINS["mac.notify"]
        monkeypatch.setitem(capabilities.BUILTINS, "mac.notify",
                            (dataclasses.replace(manifest, platforms=("linux",)), adapter))
    world = NotifyWorld(tmp_path)
    move = ship_move(action_class="greg.mac.notify", requested_capability="mac.notify",
                     target="founder:alfonso", description="notify the founder (outside the cone)")
    gid, _ = world.start(GOAL(moves=(move,)))
    world.tick(8)
    acts = [(e["action_id"], e["status"]) for e in world.events("mission.action")]
    assert ("w", "DONE") in acts and ("w2", "UNAVAILABLE") in acts      # the loop reached w2: it cannot run here
    assert [r for r in world.w2_requests() if (r.get("evidence") or {}).get("goal_id") == gid] == []
    assert [r for r in world.book().open_requests() if r.get("action_id") == "w2"] == []
    notices = [n for n in world.events("goal.notice") if n["kind"] == "ask_not_recorded"]
    assert notices and "cannot act here (UNAVAILABLE)" in notices[0]["why"]
    with world.body() as b:
        assert "cannot act here (UNAVAILABLE)" in b.engine.ask_refusal(MID, "w2", now=world.clock.now)
