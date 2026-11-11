"""Reviewer probe H: the review's unbounded grant loop without a late suspicion. The phone's standing approval is
withdrawn by the real standing-approval regression (a run under it proved ineffective); the FOUNDER approves the
re-ask and the write runs again; then the still-delegated phone is revoked as a suspected compromise."""
import json

import pytest

from greg import revocation
from tests.greg_fixtures import mission, note_check, workspace, write_strategy
from tests.unit.test_greg_revoked_device_authority import World, actions, open_asks  # noqa


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def approved_grants(body):
    return [r for r in body.ledger.by_type("event")
            if r.payload.get("type") == "greg.authority.grant_issued" and r.payload.get("founder_approved_scope")]


def test_H1_review_after_a_regressed_approval_lists_the_founders_dispatch_as_the_devices(world):
    mid = "m:regress"
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note = workspace(world.home, mid) / "n.txt"
        # the write puts "draft" but the check wants "final": the run executes and proves ineffective
        body.apply(world.sign("MISSION", mission(
            mid, checks=[note_check("n", note, "final")], strategies=[write_strategy("w", "n.txt", "draft", ["n"])],
            capabilities=["fs.read"], ceiling="read_only",
            closure={"kind": "infinite", "ladder": [["n"]], "cadence_seconds": 60})))
        world.tick(body, 2)
        [ask] = open_asks(body, mid)
        body.apply(world.approve(ask["request_id"], key=phone))
        for _ in range(4):
            world.clock.advance(61)
            world.tick(body, 2)
        regressed = [e.payload for e in body.journal.replay("autonomy.regressed")]
        print("regressed:", [r["request_id"][-6:] for r in regressed], "phone ask:", ask["request_id"][-6:])
        assert regressed and regressed[0]["request_id"] == ask["request_id"]
        first = approved_grants(body)
        # the world passes once (by hand), then drifts: the strategy is eligible again and asks anew
        note.write_text("final")
        world.clock.advance(61); world.tick(body, 2)
        note.unlink()
        for _ in range(3):
            world.clock.advance(61)
            world.tick(body, 2)
        again = [r for r in open_asks(body, mid) if r["request_id"] != ask["request_id"]]
        assert again, [r["kind"] for r in body.engine.book.open_requests()]
        body.apply(world.approve(again[0]["request_id"]))                 # the FOUNDER approves
        for _ in range(2):
            world.clock.advance(61)
            world.tick(body, 2)
        second = [g for g in approved_grants(body) if g.seq > first[-1].seq]
        assert second, "the founder-approved dispatch did not run"
        body.apply(world.revoke("phone", suspected_compromise=True))      # the phone was delegated all along
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        rows = [{k: x.get(k) for k in ("effect", "grant_id", "receipt")} for x in review["effects"]]
        print(json.dumps(rows, indent=1))
        wrongly = [x for x in review["effects"] if x.get("grant_id") in {g.payload["grant_id"] for g in second}]
        assert wrongly, "clean: the founder-approved dispatch is not attributed to the phone"
