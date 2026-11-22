"""Combined trace: a worker team finishes as mission B while Genesis holds mission A's build open.

This is the regression for the next slow capability (founder decision on #96, 2026-11-21). It needs #336 (the
Genesis builder call off the Body's turn) and #338 (WU-03 ``worker.team``) together:
- mission A opens a CapabilityDeficit, and its builder is held open;
- mission B fields two concurrent workers under one grant (Foundry #48 through ``foundry.apply``);
- B's team forms, works, records each member, dissolves, and is independently appraised, all while A's builder
  is held;
- the heartbeat keeps showing A as WORKING on its build, and A closes only after the test releases the builder.

It fails on #338 alone (the build holds the turn, so the team never closes) and on #336 alone (no worker.team).

The founder key is a per-test Ed25519 key, not Alfonso's; the builder and the workers are test doubles.
"""
from __future__ import annotations

import threading

from greg import workers
from greg.body import Body
from tests.greg_fixtures import drop, make_body, signed
from tests.unit.test_greg_genesis_build_off_turn import (FUNCTION, GOOD as BUILT, HoldingBuilder, achieved, events,
                                                         heartbeat, start, stop, wait_for, working)
from tests.unit.test_greg_genesis_builder import _mission
from tests.unit.test_greg_teams import MUL, MeteredHoldingWorker, team_mission, team_output
from tests.unit.test_greg_workers import GOOD, acceptance_envelope, make_repo  # noqa: F401


def test_a_worker_team_closes_as_mission_b_while_genesis_holds_mission_a(tmp_path, monkeypatch):
    home, key, body_id, data = make_body(tmp_path)
    repo = make_repo(data)
    building = _mission(data)
    building["priority"] = 10                                     # stepped first: its build starts first
    drop(home, signed(key, body_id, "MISSION", building))
    barrier, release, entered = threading.Barrier(2), threading.Event(), []
    release.set()                                                 # the team runs as soon as both members are in
    monkeypatch.setitem(workers.PROVIDERS, "team-a",
                        MeteredHoldingWorker(GOOD, cost=0.15, barrier=barrier, release=release, entered=entered))
    monkeypatch.setitem(workers.PROVIDERS, "team-b",
                        MeteredHoldingWorker(MUL, cost=0.25, barrier=barrier, release=release, entered=entered))
    builder = HoldingBuilder(BUILT)
    body = Body(home, builder=builder)
    loop = start(body)
    try:
        wait_for(lambda: builder.started, "mission A's build to start")
        drop(home, signed(key, body_id, "MISSION", team_mission(repo, priority=50)))
        wait_for(lambda: "m:team" in achieved(home), "the team mission to close while A's build is held")
        # B closed strictly while A's builder call was held: never released, never returned.
        assert not builder.release.is_set() and builder.returned == []
        assert len(entered) == 2 and len({thread for _, thread in entered}) == 2
        wait_for(lambda: working(home, "m:runbook"), "the heartbeat to show A WORKING on its build")
        row = next(m for m in heartbeat(home)["missions"] if m["mission_id"] == "m:runbook")
        assert row["action"] == f"genesis.build:{FUNCTION}"
        assert "m:runbook" not in achieved(home)
        builder.release.set()
        wait_for(lambda: "m:runbook" in achieved(home), "mission A to close once its build returns")
    finally:
        builder.release.set()
        stop(body, loop)
    out = team_output(home)
    assert out["team"]["state"] == "DISSOLVED" and sorted(out["members"]) == ["add-mul", "add-sub"]
    verdicts = {p["check_id"]: p["passed"] for p in events(home, "mission.observed")}
    assert verdicts["adder_accepted"] and verdicts["multiplier_accepted"]
    assert [p["build"] for p in events(home, "genesis.built")] == [1]          # A's one build, taken once
