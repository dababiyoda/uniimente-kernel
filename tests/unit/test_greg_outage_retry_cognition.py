"""Fourth review of the Track B merge (F1): #184's outage retry re-ran Genesis for a Track B cognition residual
without the compiler's deficit and at a later time, so its search pass named a mechanism attached during the
back-off as already tried, and Genesis.serving() never reported the need as served: the mission blocked forever
while a mission arriving now was answered by that mechanism.

The compile's deficit now says which formed mechanisms it ran with no answer, and the outage blocker carries
that deficit into the retry. Reproduction by the review's finder, kept as the regression."""
from __future__ import annotations

import json

import pytest

pytest.importorskip("scipy")

from greg import genesis as G
from greg.body import Body
from greg.capabilities import CapabilityError
from greg.cognition import compiler
from tests.greg_fixtures import Clock, make_body, signed
from tests.unit.test_greg_cognition_genesis import COSTS, SCIPY, compile_mission


@pytest.fixture
def index(tmp_path, monkeypatch):
    path = tmp_path / "index.json"
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", path)
    path.write_text(json.dumps({"genomes": {}, "recipes": {}, "routing": {}}))
    return path


def _tick(body, clock, n, mid):
    out = []
    for _ in range(n):
        out += [s for s in body.tick()["missions"] if s["mission_id"] == mid]
        clock.advance(31)
    return out


@pytest.mark.parametrize("outage", [False, True])
def test_a_mechanism_attached_during_an_outage_backoff_serves_the_waiting_mission(tmp_path, index, monkeypatch,
                                                                                  outage):
    geometry = {"geometry": "optimization", "subgeometry": "assignment"}
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    real = G.qualify_package
    calls = []

    def flaky(*a, **kw):
        calls.append(1)
        if outage and len(calls) == 1:
            raise CapabilityError("runner timed out (host under load)", failure_class="transient")
        return real(*a, **kw)

    monkeypatch.setattr(G, "qualify_package", flaky)
    with Body(home, clock=clock) as body:
        body.boot()
        body.apply(signed(key, body_id, "MISSION", compile_mission("m:bbb", geometry, {"costs": COSTS})))
        states = _tick(body, clock, 1, "m:bbb")
        b = body.engine.book.missions["m:bbb"]
        if outage:
            assert b.blocker["type"] == "outage", states
        # a second mission with the same need forms the mechanism on a host that now works
        body.apply(signed(key, body_id, "MISSION", compile_mission("m:ccc", geometry,
                                                                    {"costs": [[0.5, 2.25], [1.75, 0.125]]})))
        body.tick()                     # B's back-off (60 s) has not elapsed; C forms the mechanism
        clock.advance(5)
        assert body.registry.state[SCIPY] == "VERIFIED"
        if outage:
            assert body.engine.book.missions["m:bbb"].blocker["type"] == "outage"
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": SCIPY}))
        for _ in range(8):
            body.tick()
            clock.advance(31)
        book = body.engine.book
        assert book.missions["m:ccc"].status == "ACHIEVED"
        assert book.missions["m:bbb"].status == "ACHIEVED"
