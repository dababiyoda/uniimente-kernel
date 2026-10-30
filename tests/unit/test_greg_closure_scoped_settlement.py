"""Observations settle under the appraisal of their own closure (review TXT-R5-1 on #221, of #196's afcd75f3).

afcd75f3 dropped a mission's VERIFIED_UNMET once the mission was recorded achieved, so a success claim the separate
appraiser then refuted erased a failure that appraiser had verified: measured_outcomes went from the failure to
nothing. An observation now belongs to the first closure recorded at or after it, and settles only under that
closure's own appraisal. The success claim here is recorded directly (a false report); the appraisals are the real
separate process, run by the body.
"""
from __future__ import annotations

from greg.cognition import settlement
from tests.unit.test_greg_failure_closure import blackbox, run


def _falsely_achieved(body, mid):
    body.journal.record("mission.achieved", {
        "mission_id": mid, "evidence": [], "actions_done": 1,
        "closure_rule": "every success check re-observed passing through the Gate",
        "founder_authenticated_mission": True, "at": "2026-10-30T00:00:00Z"}, key=[mid, "achieved"])


def _settled(body):
    return sorted((o["mission_id"], o["correct"]) for o in settlement.measured_outcomes(body.journal))


def test_a_refuted_success_claim_does_not_erase_a_verified_failure(tmp_path):
    body, _, _, clock = run(tmp_path, [blackbox("m:fails", 1, 0.0)])
    try:
        assert _settled(body) == [("m:fails", False)]
        _falsely_achieved(body, "m:fails")
        body._close_out(clock())                                 # the separate appraiser judges the success claim
        success = [e.payload for e in body.journal.replay("mission.appraised")
                   if e.payload["mission_id"] == "m:fails" and not e.payload.get("closure_event")]
        assert [s["verdict"] for s in success] == ["REFUTED"]
        assert _settled(body) == [("m:fails", False)]           # still the verified failure
    finally:
        body.close()


def test_a_verified_failure_still_settles_while_the_later_success_awaits_its_appraisal(tmp_path, monkeypatch):
    body, _, _, clock = run(tmp_path, [blackbox("m:fails", 1, 0.0)])
    try:
        _falsely_achieved(body, "m:fails")
        monkeypatch.setattr(body, "appraise", lambda mid, *, closure_event=None: {
            "mission_id": mid, "head": body.ledger.head, "verdict": "UNAVAILABLE", "checks": {},
            "findings": ["the appraiser is down"], "appraiser": "separate process"})
        body._close_out(clock())
        assert _settled(body) == [("m:fails", False)]
    finally:
        body.close()
