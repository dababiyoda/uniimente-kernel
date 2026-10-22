"""Goal Gravity (the base's GOAL binding) joined with this trunk's engine (merge 6ad8944): the review of the merge.

Each test is a scenario an adversarial review reproduced on the merged tree: founder-signed commands and body
ticks only, with the test founder key of tests.greg_fixtures (NOT Alfonso's key).
- A compensation ask (undo an executed move) is never shown as the goal's own decision about that move.
- Asking ahead holds a strategy whose typed inputs cannot resolve, exactly as the mission's loop holds it.
- A read that did not measure the world (sensor refused, or inconclusive) is never goal evidence.
- A goal does not claim to be holding after GREG's own compensation undid the effect it observed.
"""
from __future__ import annotations

import pytest

from greg import goal_gravity as gg
from greg.capabilities import BUILTINS, CapabilityError
from greg.missions import first_choice, measured
from tests.greg_fixtures import mission, note_check, write_strategy
from tests.unit.test_greg_goal_gravity import MID, World, expected_w2_request, fast  # noqa: F401
from tests.unit.test_greg_goal_gravity_founder_effect import MANIFESTS

UNDO_C = {"capability": "fs.write", "params": {"relative_path": "c.txt", "content": "ok"},
          "target": "workspace:c.txt"}


class CompensatingWorld(World):
    """Mission F whose out-of-cone move w2 signs a compensation inside the cone."""

    def mission_spec(self, **kw):
        return mission(MID, checks=[note_check("c", self.ws / "c.txt", "ok"),
                                    note_check("d", self.ws / "d.txt", "shipped")],
                       strategies=[write_strategy("w", "c.txt", "ok", ["c"]),
                                   write_strategy("w2", "d.txt", "shipped", ["d"], compensate=UNDO_C)],
                       capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:c.txt"),
                       closure={"kind": "infinite", "ladder": [["c"], ["d"]], "cadence_seconds": 86400}, **kw)


def _ship(world):
    """Start the mission and its goal, then approve and run the goal's move w2."""
    gid, _ = world.start()
    rid, _ = expected_w2_request(world)
    world.tick(4)
    assert [r["request_id"] for r in world.w2_requests()] == [rid]
    world.submit("DECISION", {"request_id": rid, "answer": "approve", "reason": "ship it"})
    world.tick(4)
    assert (world.ws / "d.txt").read_text() == "shipped"
    return gid, rid


def test_a_compensation_ask_is_never_shown_as_the_goals_own_decision(tmp_path, fast):
    world = CompensatingWorld(tmp_path)
    gid, rid = _ship(world)
    world.submit("LIFECYCLE", {"mission_id": MID, "state": "SUPERSEDED", "reason": "replaced by a successor"})
    world.tick(3)
    undo = [r for r in world.w2_requests() if r["request_id"] != rid]
    assert len(undo) == 1 and undo[0]["kind"] == "APPROVAL"           # the superseded mission asks before undoing
    assert undo[0]["evidence"]["lifecycle"] == "SUPERSEDED"
    with world.body() as b:
        assert undo[0]["request_id"] in [r["request_id"] for r in b.engine.book.open_requests()]
        summary, view, ev = gg.status_summary(b.journal), gg.projection(b.journal), gg.evidence(b.journal, gid)
    # The ask is still the founder's to answer on the mission's surfaces; it is not the goal's move decision.
    assert undo[0]["request_id"] not in summary["goals"][0]["open_requests"]
    assert undo[0]["request_id"] not in view["goals"][0]["open_requests"]
    assert undo[0]["request_id"] not in [a["request_id"] for a in ev["asks"]]
    assert [a["request_id"] for a in ev["asks"]] == [rid]               # the move's own ask stays linked


HELD = {"action_id": "b", "capability": "fs.write", "target": "workspace:d.txt", "advances": ["d"],
        "params": {"relative_path": "d.txt",
                   "content": {"$from_action": {"action_id": "p", "field": "text", "type": "string"}}},
        "rationale": "write d from p's output (p never runs: c already passes)"}


class HeldInputWorld(World):
    """The signed first choice for d takes a typed input that cannot resolve: the loop holds it and runs w2."""

    def mission_spec(self, **kw):
        return mission(MID, checks=[note_check("c", self.ws / "c.txt", "ok"),
                                    note_check("d", self.ws / "d.txt", "shipped")],
                       strategies=[write_strategy("w", "c.txt", "ok", ["c"]), HELD,
                                   write_strategy("w2", "d.txt", "shipped", ["d"]),
                                   write_strategy("p", "c.txt", "ok", ["c"])],
                       capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:c.txt"),
                       closure={"kind": "infinite", "ladder": [["c"], ["d"]], "cadence_seconds": 86400}, **kw)


def test_asking_ahead_holds_a_strategy_whose_inputs_cannot_resolve_as_the_loop_does(tmp_path, fast):
    world = HeldInputWorld(tmp_path)
    gid, _ = world.start()
    rid, _ = expected_w2_request(world)
    world.tick(6)
    refused = [n for n in world.events("goal.notice") if n["goal_id"] == gid and "could change nothing" in n.get("why", "")]
    assert refused == []                                                # never "the mission runs b first"
    asks = world.w2_requests()
    assert [r["request_id"] for r in asks] == [rid]                     # one decision, one ask
    assert (asks[0].get("evidence") or {}).get("goal_id") == gid        # asked by the goal, ahead of the loop
    assert world.events("mission.action") and all(a["action_id"] != "b" for a in world.events("mission.action"))
    # Static callers (goal_from_mission has no ledger) keep the conservative signed order.
    spec = world.mission_spec()
    assert first_choice(spec, {"d"}, manifest_for=lambda s: MANIFESTS.get(s.get("capability")), records={}) == "b"
    assert first_choice(spec, {"d"}, manifest_for=lambda s: MANIFESTS.get(s.get("capability")), records={},
                        held={"b"}) == "w2"


@pytest.mark.parametrize("mode", ["refused", "inconclusive"])
def test_a_read_that_did_not_measure_the_world_never_reopens_a_completed_goal(tmp_path, fast, mode):
    world = World(tmp_path)
    spec = world.mission_spec()
    world.submit("MISSION", spec, "a.json")
    world.tick()
    world.submit("GOAL", gg.goal_from_mission(spec, MANIFESTS)["goal_command"], "b.json")
    world.tick(3)
    gid = world.projection()["goals"][0]["goal_id"]
    rid, _ = expected_w2_request(world)
    world.submit("DECISION", {"request_id": rid, "answer": "approve", "reason": "ship"})
    world.tick(6)
    assert world.registry().state(gid).status == "completed"
    real = BUILTINS["fs.read"][1]

    def host_down(params, ctx):                                        # c.txt is still "ok": only the host is down
        if str(params.get("path", "")).endswith("c.txt"):
            if mode == "refused":
                raise CapabilityError("capability refused: runner timed out", failure_class="transient")
            return {"capability_fault": {"capability_id": "fs.read", "failure_class": "transient",
                                         "detail": "capability refused: runner timed out"}}
        return real(params, ctx)

    world.clock.advance(1.1 * 86400)                                  # the cadence re-observes c
    pulls = len([e for e in world.events("mission.schedule") if "cause" in e])
    seen = len(world.events("mission.observed"))
    with world.body() as b:
        b.registry.adapters["fs.read"] = host_down
        for _ in range(4):
            b.tick()
            world.clock.advance(5)
    during = [o for o in world.events("mission.observed")[seen:] if o["check_id"] == "c"]
    assert during and not any(o["passed"] or measured(o) for o in during)      # each read failed, unmeasured
    assert world.registry().state(gid).status == "completed"
    assert not [r for r in world.records("egregore.goal_transition")
                if r["goal_id"] == gid and r["reason"].startswith("reopened")]
    assert len([e for e in world.events("mission.schedule") if "cause" in e]) == pulls   # no goal pull either
    assert measured({"detail": "contains 'ok'", "passed": False})      # a measured failure is still evidence


def test_a_goal_does_not_claim_to_hold_after_gregs_compensation_undid_its_effect(tmp_path, fast):
    """An infinite mission writes "draft" (its signed compensation restores "original"); a goal derived from it
    completes at observation tier. The founder abandons the mission: GREG's own compensation undoes the observed
    effect through the Gate, and the ended mission never observes again, so no regression can reopen the goal."""
    world = World(tmp_path)
    note = world.ws / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("original")
    restore = {"capability": "fs.write", "params": {"relative_path": "note.txt", "content": "original"},
               "target": "workspace:note.txt"}
    spec = mission(MID, checks=[note_check("c", note, "draft")],
                   strategies=[write_strategy("w", "note.txt", "draft", ["c"], compensate=restore)],
                   capabilities=["fs.read", "fs.write"],
                   closure={"kind": "infinite", "ladder": [["c"]], "cadence_seconds": 3600})
    world.submit("MISSION", spec, "a.json")
    world.submit("GOAL", gg.goal_from_mission(spec, MANIFESTS)["goal_command"], "b.json")
    world.tick(6, step=5)
    goal = world.projection()["goals"][0]
    assert goal["status"] == "completed" and goal["completion_label"].startswith("holding")
    world.submit("LIFECYCLE", {"mission_id": MID, "state": "ABANDONED", "reason": "done with it"})
    world.tick(4, step=5)
    assert [(c["action_id"], c["status"]) for c in world.events("mission.compensated")] == [("w", "DONE")]
    assert note.read_text() == "original"                             # the observed effect is undone
    world.clock.advance(7200)
    world.tick(3, step=3600)
    goal = world.projection()["goals"][0]
    assert goal["status"] == "completed"                               # nothing re-observes an ended mission
    label = goal["completion_label"]
    assert "holding" not in label and "reopens" not in label
    assert "no longer holds" in label and "compensat" in label and f"{MID}" in label and " w " in label
