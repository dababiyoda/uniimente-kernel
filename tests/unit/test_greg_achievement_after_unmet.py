"""An achievement after an appraised failure closure is appraised in its own right (review TXT-R4-1 on #221).

Body._close_out appraised a mission.achieved only when no mission.appraised named the mission at all. A bounded
mission that closed unmet carried a VERIFIED_UNMET appraisal, so its later achievement (the founder did the work and
approved the NO_STRATEGY ask) was never appraised, and settlement kept the failure's appraisal in force for it.
"""
from __future__ import annotations

from greg.body import Body
from greg.cognition import settlement
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy


def _ticks(body, clock, n, step=31):
    for _ in range(n):
        body.tick()
        clock.advance(step)


def test_an_achievement_after_an_appraised_unmet_closure_is_appraised(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    try:
        note = workspace(body.layout.home, "m:later") / "n.txt"
        body.apply(signed(key, body_id, "MISSION", mission(
            "m:later", checks=[note_check("n", note, "wanted")],
            strategies=[write_strategy("w", "other.txt", "something else", ["n"])],
            capabilities=["fs.read", "fs.write"])))
        _ticks(body, clock, 4)
        [unmet] = body.journal.replay("mission.unmet")
        [failure] = [e for e in body.journal.replay("mission.appraised") if e.payload["mission_id"] == "m:later"]
        assert failure.payload["verdict"] == "VERIFIED_UNMET" and failure.payload["closure_event"] == unmet.event_id

        note.write_text("wanted")                         # the founder does the work the check reads
        [ask] = [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "NO_STRATEGY"]
        drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"}))
        _ticks(body, clock, 8, step=600)             # past the re-observation back-off

        [achieved] = body.journal.replay("mission.achieved")
        assert achieved.payload["mission_id"] == "m:later"
        success = [e for e in body.journal.replay("mission.appraised")
                   if e.payload["mission_id"] == "m:later" and not e.payload.get("closure_event")]
        assert len(success) == 1 and success[0].payload["verdict"] == "VERIFIED"
        assert settlement._settling_appraisals(body.journal)["m:later"].event_id == success[0].event_id
    finally:
        body.close()


def test_a_failure_appraisal_does_not_settle_a_mission_achieved_after_it(tmp_path, monkeypatch):
    """While the achievement's own appraisal is unavailable, the earlier VERIFIED_UNMET settles nothing for it."""
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    try:
        note = workspace(body.layout.home, "m:later") / "n.txt"
        body.apply(signed(key, body_id, "MISSION", mission(
            "m:later", checks=[note_check("n", note, "wanted")],
            strategies=[write_strategy("w", "other.txt", "something else", ["n"])],
            capabilities=["fs.read", "fs.write"])))
        _ticks(body, clock, 4)
        assert settlement._settling_appraisals(body.journal)["m:later"].payload["verdict"] == "VERIFIED_UNMET"

        def unavailable(mission_id, *, closure_event=None):
            return {"mission_id": mission_id, "head": body.ledger.head, "verdict": "UNAVAILABLE", "checks": {},
                    "findings": ["the appraiser is down"], "appraiser": "separate process"}
        monkeypatch.setattr(body, "appraise", unavailable)
        note.write_text("wanted")
        [ask] = [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "NO_STRATEGY"]
        drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"}))
        _ticks(body, clock, 8, step=600)
        assert [e.payload["mission_id"] for e in body.journal.replay("mission.achieved")] == ["m:later"]
        assert "m:later" not in settlement._settling_appraisals(body.journal)
        assert not [o for o in settlement.measured_outcomes(body.journal) if o.get("mission_id") == "m:later"]
    finally:
        body.close()
