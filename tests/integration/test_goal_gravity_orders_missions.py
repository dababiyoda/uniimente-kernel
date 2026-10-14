"""Directive Stage 2: Goal Gravity selects the work on the Body path, inside founder-signed cones.

Goal Gravity (greg.gravity.select) ranks the founder-signed ACTIVE missions every tick; the engine
steps them in that order; each change of order is a ledger fact a verifier can check against the
signed specs. It is authority-neutral: it adds no mission, drops none, and widens no cone.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

from events.spine import EventSpine
from greg import gravity
from greg.body import Body
from greg.journal import Journal
from provenance.ledger import EvidenceLedger
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy


def spec(home, mid, priority):
    target = workspace(home, mid) / "note.md"
    return mission(mid, checks=[note_check("noted", target, "done")],
                   strategies=[write_strategy("write", "note.md", "done", ["noted"])],
                   capabilities=["fs.read", "fs.write"], priority=priority)


def test_goal_gravity_orders_the_signed_missions_and_records_each_change(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    for mid, priority in (("m:low", 20), ("m:high", 80)):
        drop(home, signed(key, body_id, "MISSION", spec(home, mid, priority)), name=mid.replace(":", "_") + ".json")
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        first = body.tick()
        assert [m["mission_id"] for m in first["missions"]] == ["m:high", "m:low"]
        assert all(m["state"] != "NOT_STEPPED" for m in first["missions"])      # both still stepped
        [ranked] = body.journal.replay("gravity.ranked")
        selection = ranked.payload
        assert selection["selected"] == "m:high" and selection["authority_created"] is False
        signed_priority = {e.payload["mission_id"]: e.payload["spec"]["priority"]
                           for e in body.journal.replay("mission.registered")}
        assert gravity.consistent(selection, signed_priority) == []
        clock.advance(31)
        body.tick()
        # an unchanged order is not re-recorded; a mission that closed leaves the ranking (a new fact)
        rankings = [e.payload["ranking"] for e in body.journal.replay("gravity.ranked")]
        assert all(a != b for a, b in zip(rankings, rankings[1:]))
    with Body(home, clock=clock) as body:              # a restart re-derives the same order, records nothing new
        body.boot()
        before = len(body.journal.replay("gravity.ranked"))
        body.engine.book.rebuild()
        body._goal_gravity(sorted(body.engine.book.missions.values(), key=lambda m: m.mission_id))
        assert len(body.journal.replay("gravity.ranked")) == before


def test_a_forged_ranking_is_detected_against_the_signed_specs():
    selection = {"ranking": [{"mission_id": "m:a", "priority": 99, "reliability": 0.5},
                             {"mission_id": "m:b", "priority": 80, "reliability": 0.5}], "selected": "m:a"}
    assert gravity.consistent(selection, {"m:a": 10, "m:b": 80})          # m:a was signed at 10, not 99
    swapped = {**selection, "selected": "m:b"}
    assert gravity.consistent(swapped, {"m:a": 99, "m:b": 80})


def test_learned_reliability_breaks_ties_and_paused_missions_are_excluded(tmp_path):
    journal = Journal(EventSpine(EvidenceLedger("sha256:" + "4" * 64, path=str(tmp_path / "l.jsonl"))),
                      actor="spiffe://uniimente.internal/test/gravity")
    for i in range(3):     # fs.read has failed three times; fs.write has succeeded three times
        journal.record("mission.action", {"mission_id": "m:hist", "action_id": f"r{i}", "status": "FAILED",
                                          "capability": "fs.read"}, key=["r", i])
        journal.record("mission.action", {"mission_id": "m:hist", "action_id": f"w{i}", "status": "DONE",
                                          "capability": "fs.write"}, key=["w", i])

    def state(mid, capability, paused=False):
        return NS(mission_id=mid, status="ACTIVE", paused=paused,
                  spec={"priority": 50, "strategies": [{"capability": capability}]})
    selection = gravity.select([state("m:a-reads", "fs.read"), state("m:b-writes", "fs.write"),
                                state("m:c-paused", "fs.write", paused=True)], journal)
    assert [r["mission_id"] for r in selection["ranking"]] == ["m:b-writes", "m:a-reads"]
    assert selection["excluded"] == [{"mission_id": "m:c-paused", "reason": "paused by the founder"}]
