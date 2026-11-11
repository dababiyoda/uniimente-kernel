"""Reviewer probes, set D: review rows the builder's tests never exercise (their mutants R6-R10 survive):
a critique's exclusion, an abandon's compensation, a recorded reconciliation, a device-signed GOAL_CONTROL."""
import json

import pytest

from greg import revocation
from tests.greg_fixtures import mission, note_check, workspace, write_strategy
from tests.unit.test_greg_revoked_device_authority import World, actions, open_asks, uncertain  # noqa

RESTORE = {"capability": "fs.write", "params": {"relative_path": "note.txt", "content": "original"},
           "target": "workspace:note.txt"}


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_D1_the_review_lists_an_exclusion_an_abandons_compensation_and_a_settled_reconciliation(world):
    with world.body() as body:
        phone = world.enroll(body, "phone", ("DECISION", "CRITIQUE", "LIFECYCLE"))
        # a mission whose executed write has a signed compensation, abandoned by the phone; the compensation runs
        note = workspace(world.home, "m:comp") / "note.txt"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text("original")
        body.apply(world.sign("MISSION", mission(
            "m:comp", checks=[note_check("c", note, "draft")],
            strategies=[write_strategy("w", "note.txt", "draft", ["c"], compensate=RESTORE)],
            capabilities=["fs.read", "fs.write"],
            closure={"kind": "infinite", "ladder": [["c"]], "cadence_seconds": 3600})))
        world.tick(body, 3)
        body.apply(world.sign("LIFECYCLE", {"mission_id": "m:comp", "state": "ABANDONED", "reason": "phone"}, key=phone))
        world.tick(body, 3)
        assert note.read_text() == "original"
        # an interrupted dispatch the phone reconciles as executed; the engine records it
        note2, ask, calls = uncertain(world, body)
        body.apply(world.approve(ask["request_id"], key=phone, answer="reconcile_executed"))
        world.tick(body, 2)
        # a critique that excludes a strategy
        target = [e for e in body.journal.replay("mission.action") if e.payload["mission_id"] == "m:uncertain"][0]
        body.apply(world.sign("CRITIQUE", {"target_event_id": target.event_id, "verdict": "reject",
                                           "evidence_type": "founder_judgment", "text": "not this way",
                                           "exclude_strategy": True}, key=phone))
        body.apply(world.revoke("phone", suspected_compromise=True))
        world.tick(body, 2)
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        effects = [x["effect"] for x in review["effects"]]
        print(review["status"], json.dumps(effects, indent=1))
        assert review["status"] == "OPEN_FOR_FOUNDER_REVIEW"
        assert "a compensation run after it ended the mission" in effects
        assert "an interrupted dispatch settled by its answer" in effects
        assert "a strategy excluded by its critique" in effects
        assert [c["kind"] for c in review["commands"]] == ["LIFECYCLE", "DECISION", "CRITIQUE"]
