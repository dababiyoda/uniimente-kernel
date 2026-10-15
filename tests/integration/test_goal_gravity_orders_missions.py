"""Directive Stage 2: Goal Gravity selects the work on the Body path, inside founder-signed cones.

Goal Gravity (greg.gravity.select) ranks the founder-signed ACTIVE missions every tick; the engine
steps them in that order; each change of the ranking is a ledger fact a verifier re-derives from the
ledger before it (greg.gravity.consistent). It is authority-neutral: it adds no mission, drops none,
and widens no cone.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

from events.spine import EventSpine
from greg import gravity, routing
from greg.body import Body
from greg.journal import Journal
from provenance.ledger import EvidenceLedger
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy


def open_ended(home, mid, priority):
    """A mission that stays ACTIVE: its check reads a file no strategy writes."""
    target = workspace(home, mid) / "never.md"
    return mission(mid, checks=[note_check("never", target, "done")],
                   strategies=[write_strategy("write", "other.md", "x", ["never"])],
                   capabilities=["fs.read", "fs.write"], priority=priority)


def test_goal_gravity_orders_the_signed_missions_and_every_ranking_rederives(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    for mid, priority in (("m:low", 20), ("m:high", 80)):
        drop(home, signed(key, body_id, "MISSION", open_ended(home, mid, priority)), name=mid.replace(":", "_") + ".json")
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(3):
            tick = body.tick()
            stepped = [m["mission_id"] for m in tick["missions"]]
            assert stepped == ["m:high", "m:low"] and all(m["state"] != "NOT_STEPPED" for m in tick["missions"])
            clock.advance(31)
        assert all(e.payload["selected"] == "m:high" and e.payload["authority_created"] is False
                   for e in body.journal.replay("gravity.ranked"))
    with Body(home, clock=clock) as body:              # a new process re-derives every recorded ranking exactly
        ranked = body.journal.replay("gravity.ranked")
        assert ranked and all(gravity.consistent(body.journal, e) == [] for e in ranked)


def test_a_forged_ranking_is_detected_by_rederivation(tmp_path):
    """Review finding: the verifier must re-derive membership and learned reliability, not just check a
    recorded list against itself. A ranking that drops the higher-priority mission, or swaps learned
    reliabilities, or names another mission selected, is refused."""
    home, key, body_id, _ = make_body(tmp_path)
    for mid, priority in (("m:low", 20), ("m:high", 80)):
        drop(home, signed(key, body_id, "MISSION", open_ended(home, mid, priority)), name=mid.replace(":", "_") + ".json")
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        body.tick()
        genuine = body.journal.replay("gravity.ranked")[-1]
        assert gravity.consistent(body.journal, genuine) == []
        dropped = {**genuine.payload, "ranking": [r for r in genuine.payload["ranking"] if r["mission_id"] == "m:low"],
                   "selected": "m:low"}
        swapped = {**genuine.payload, "ranking": [{**r, "reliability": 0.99} if r["mission_id"] == "m:low" else r
                                                  for r in genuine.payload["ranking"]]}
        for i, forged in enumerate((dropped, swapped)):
            event = body.journal.record("gravity.ranked", forged, key=["forged", i])
            assert gravity.consistent(body.journal, event), forged


def test_learned_reliability_breaks_ties_and_paused_missions_are_excluded(tmp_path):
    journal = Journal(EventSpine(EvidenceLedger("sha256:" + "4" * 64, path=str(tmp_path / "l.jsonl"))),
                      actor="spiffe://uniimente.internal/test/gravity")
    for i in range(3):     # fs.read was refused three times (a status routing counts); fs.write succeeded three times
        journal.record("mission.action", {"mission_id": "m:hist", "action_id": f"r{i}", "status": "REFUSED",
                                          "capability": "fs.read"}, key=["r", i])
        journal.record("mission.action", {"mission_id": "m:hist", "action_id": f"w{i}", "status": "DONE",
                                          "capability": "fs.write"}, key=["w", i])
    record = routing.track_record(journal)
    assert routing.reliability(record.get("fs.read")) < 0.5 < routing.reliability(record.get("fs.write"))

    def state(mid, capability, paused=False):
        return NS(mission_id=mid, status="ACTIVE", paused=paused,
                  spec={"priority": 50, "strategies": [{"capability": capability}]})
    selection = gravity.select([state("m:a-reads", "fs.read"), state("m:b-writes", "fs.write"),
                                state("m:c-paused", "fs.write", paused=True)], journal)
    assert [r["mission_id"] for r in selection["ranking"]] == ["m:b-writes", "m:a-reads"]
    assert selection["ranking"][1]["reliability"] < 0.5
    assert selection["excluded"] == [{"mission_id": "m:c-paused", "reason": "paused by the founder"}]


def test_every_unselected_tick_is_recorded(tmp_path, monkeypatch):
    """Review finding: an unavailable selector was recorded once and then silently re-used."""
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", open_ended(home, "m:one", 50)), name="m_one.json")

    def broken(missions, journal):
        raise RuntimeError("selector down")
    monkeypatch.setattr(gravity, "select", broken)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(3):
            assert [m["mission_id"] for m in body.tick()["missions"]] == ["m:one"]     # missions still run
            clock.advance(31)
        assert len(body.journal.replay("gravity.unavailable")) == 3
