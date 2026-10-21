"""Builds are booked on the light cone exactly as Genesis books them on the signed build budget.

Merge review of 8be3909 (base ddcab38, H.G7, joined with this trunk's cone booking of builds):
- a builder call the body died inside stays charged at its reserved ceiling (Genesis._build_spend); the cone that
  admits every later paid action must count it too, or a paid action runs past the signed budget with no ask;
- a build is carved from what the cone has left after every open reservation (committed_usd), including a
  dispatch of unknown outcome held at its worst case.
"""
from __future__ import annotations

import pytest

from greg import builders
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy
from tests.unit.test_greg_genesis_builder import CONTRACT, FUNCTION, GOOD


class Killed(BaseException):
    pass


class DiesInside(builders.StaticBuilder):
    max_budget_usd = 0.6

    def build(self, request, feedback=None):
        raise Killed("the body was killed inside the builder's call")


class Bills(builders.StaticBuilder):
    max_budget_usd = 0.6
    cost_usd = 0.3

    def build(self, request, feedback=None):
        return {**super().build(request, feedback), "cost_usd": self.cost_usd}


def setup(tmp_path, mid):
    home, key, body_id, data = make_body(tmp_path)
    doc = data / "FIRST_MISSION.md"
    doc.write_text("# Runbook\n- [x] install\n- [ ] enroll key\n  - [ ] load launchd\n* [ ] accept closure\n")
    counted = {"check_id": "counted", "description": "open steps known",
               "sensor": {"function": FUNCTION, "params": {"path": str(doc)}, "target": "fs:FIRST_MISSION.md"},
               "predicate": {"op": "equals", "field": "unchecked", "value": 3}}
    spec = mission(mid, checks=[counted, note_check("note", workspace(home, mid) / "c.txt", "ok")],
                   strategies=[write_strategy("w", "c.txt", "ok", ["note"], cost_usd=0.6)],
                   capabilities=["fs.read", "fs.write", f"built.{FUNCTION}.*"], budget=1.0, auto_attach=True)
    spec["capability_specs"] = [dict(CONTRACT, build_budget_usd=1.0)]
    drop(home, signed(key, body_id, "MISSION", spec))
    return home


def facts(body, mid):
    j = body.journal
    deficits = {e.payload["deficit_id"] for e in j.replay("deficit.opened")}
    done = [a for a in (e.payload for e in j.replay("mission.action")) if a["status"] == "DONE"]
    asks = [r for r in (e.payload for e in j.replay("decision.requested")) if r.get("mission_id") == mid]
    return body.genesis._build_spend(deficits), done, asks


def test_a_build_the_body_died_inside_stays_reserved_on_the_cone_and_paid_actions_past_it_ask(tmp_path):
    home, clock = setup(tmp_path, "m:killed-build"), Clock()
    body = Body(home, clock=clock, builder=DiesInside(GOOD, identity="paid")).open()
    body.boot()
    with pytest.raises(Killed):
        for _ in range(4):
            clock.advance(30)
            body.tick()
    body.close()

    body = Body(home, clock=clock, builder=Bills(GOOD, identity="paid")).open()
    try:
        body.boot()
        m = body.engine.book.missions["m:killed-build"]
        assert m.reserved_usd == pytest.approx(0.6), "the interrupted call is held at its ceiling on the cone"
        for _ in range(10):
            clock.advance(60)
            body.tick()
        build_spend, done, asks = facts(body, "m:killed-build")
        m = body.engine.book.missions["m:killed-build"]
        assert build_spend == pytest.approx(0.9) and m.committed_usd == pytest.approx(0.9)
        assert [a["action_id"] for a in done if a.get("cost_usd")] == []
        assert any(r["kind"] == "APPROVAL" and r["action_id"] == "w" for r in asks), \
            "the paid write past what the books leave goes to the founder"
    finally:
        body.close()


def test_a_build_is_carved_only_from_what_the_open_reservations_leave(tmp_path):
    home, clock = setup(tmp_path, "m:held"), Clock()
    body = Body(home, clock=clock, builder=Bills(GOOD, identity="paid")).open()
    try:
        body.boot()
        body.ingest_inbox()
        # A paid dispatch of unknown outcome (a retry-safe one the body stopped inside): its cap stays reserved. A
        # non-retry-safe one is reconciled with the founder before anything else runs (#184 _resume_unsettled).
        body.journal.record("mission.action", {"mission_id": "m:held", "action_id": "w", "attempt": 0,
                                               "status": "UNCERTAIN", "reasons": ["stopped inside"], "receipt": None,
                                               "capability": "fs.read", "route": "internal", "cost_usd": 0.0,
                                               "reserved_usd": 0.6, "at": "2026-10-21T00:00:00Z",
                                               "input_bindings": []}, key=["m:held", "w", 0])
        body.engine.book.rebuild()
        for _ in range(3):
            clock.advance(30)
            body.tick()
        m = body.engine.book.missions["m:held"]
        started = [e.payload["reserved_usd"] for e in body.journal.replay("genesis.build_started")]
        assert started and max(started) <= 0.4 + 1e-9, "a build never takes the money held for the open dispatch"
        assert m.committed_usd <= m.cone.budget_usd + 1e-9
    finally:
        body.close()
