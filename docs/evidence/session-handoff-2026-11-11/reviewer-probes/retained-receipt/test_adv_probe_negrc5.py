"""Reviewer's scratch: the sensor variant with a clock that moves across the restart (the realistic case)."""
from __future__ import annotations

import pytest

from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, signed, write_strategy

MID = "m:adv5"


class Killed(BaseException):
    pass


def facts(body, kind):
    return [e.payload for e in body.journal.replay(kind) if e.payload.get("mission_id") == MID]


def test_p11_a_refused_read_killed_before_its_observation_with_a_moving_clock(tmp_path, capsys):
    home, key, body_id, _ = make_body(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("nothing here says error")
    check = {"check_id": "c", "description": "the reading reports no error",
             "sensor": {"capability": "fs.read", "params": {"path": str(outside)}, "target": "fs:outside.txt"},
             "predicate": {"op": "absent", "field": "error"}}
    drop(home, signed(key, body_id, "MISSION", mission(
        MID, checks=[check], strategies=[write_strategy("w", "w.txt", "x", ["c"])], capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        record = body.journal.record

        def dies(name, data, **kw):
            if name == "mission.observed":
                raise Killed()
            return record(name, data, **kw)
        body.journal.record = dies
        with pytest.raises(Killed):
            body.tick()
    clock.advance(0.000001)                       # one microsecond later
    with Body(home, clock=clock) as body:
        for _ in range(3):
            body.tick()
            clock.advance(1)
        obs = [(o["passed"], o["detail"][:40]) for o in facts(body, "mission.observed")]
        out = {"observed": obs[:2], "achieved": len(facts(body, "mission.achieved")),
               "status": body.engine.book.missions[MID].status,
               "receipts": [r.payload["result"]["result_class"] for r in body.ledger.by_type("receipt")][:3]}
    with capsys.disabled():
        print("\nP11:", out)
    assert out["achieved"] == 0 and out["status"] != "ACHIEVED" and all(not o[0] for o in obs)
