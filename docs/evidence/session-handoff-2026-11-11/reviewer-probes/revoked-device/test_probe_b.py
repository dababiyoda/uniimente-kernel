"""Reviewer probes, set B: wrong voids, review robustness, malformed commands through the inbox, history."""
import json

import pytest

from greg import revocation
from greg.body import status
from tests.greg_fixtures import drop, mission, note_check, workspace, write_strategy
from tests.unit.test_greg_revoked_device_authority import (World, actions, asked, explode_once, open_asks,  # noqa
                                                           trail)


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_B1_voiding_a_devices_reconciliation_answer_leaves_the_founders_approval_of_the_action(world):
    """The FOUNDER approved the write; its first dispatch's completion is unknown; the phone answers the
    reconciliation; the phone is revoked before the engine records that answer. Only the phone's answer is void: the
    founder's approval of the action's exact scope must still stand (a RECONCILIATION ask carries the action's scope
    digest, so a careless void would take the founder's approval with it)."""
    mid = "m:gated"
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body, mid=mid)
        calls = explode_once(body)
        body.apply(world.approve(ask["request_id"]))                       # the founder's own approval
        world.tick(body, 2)
        [question] = open_asks(body, mid, kind="RECONCILIATION")
        assert question["scope_digest"] == ask["scope_digest"]
        drop(world.home, world.approve(question["request_id"], key=phone, answer="reconcile_not_executed"), "a.json")
        drop(world.home, world.revoke("phone"), "b.json")
        world.tick(body, 2)
        assert question["request_id"] in body.engine.book.voided
        assert body.engine.book.missions[mid].approved_scopes == {ask["scope_digest"]}, \
            "the founder's approval of the action was taken by the void of the device's reconciliation answer"
        [again] = open_asks(body, mid, kind="RECONCILIATION")
        body.apply(world.approve(again["request_id"], answer="reconcile_not_executed"))
        world.tick(body, 4)
        assert note.exists() and open_asks(body, mid) == []                # the retry ran on the founder's approval


def test_B2_a_review_of_a_device_that_signed_every_kind_it_may_builds_and_changes_no_old_record(world):
    with world.body() as body:
        phone = world.enroll(body, "phone", ("DECISION", "CRITIQUE", "LIFECYCLE", "BODY_PAUSE", "BODY_RESUME",
                                             "BODY_STOP", "GOAL_CONTROL"))
        note, ask = asked(world, body, mid="m:gated")
        note2 = world.gated(body, "m:second")
        world.tick(body, 2)
        [ask2] = open_asks(body, "m:second")
        signed = [world.approve(ask["request_id"], key=phone)]
        body.apply(signed[-1])
        world.tick(body, 3)
        [ran] = actions(body, "m:gated")
        signed.append(world.approve(ask2["request_id"], key=phone, answer="reject"))
        body.apply(signed[-1])
        target = body.journal.replay("mission.action")[0].event_id
        signed.append(world.sign("CRITIQUE", {"target_event_id": target, "verdict": "wrong", "evidence_type": "opinion",
                                              "text": "x" * 5000, "exclude_strategy": True}, key=phone))
        try:
            body.apply(signed[-1])
        except Exception as exc:                                             # the verdict vocabulary is the tribunal's
            print("critique refused:", type(exc).__name__, str(exc)[:120])
            signed.pop()
        for kind, payload in (("LIFECYCLE", {"mission_id": "m:second", "state": "PAUSED", "reason": "p" * 3000}),
                              ("BODY_PAUSE", {}), ("BODY_RESUME", {})):
            signed.append(world.sign(kind, payload, key=phone))
            body.apply(signed[-1])
        before = [(r.seq, r.hash) for r in body.ledger.by_type("event")]
        result = body.apply(world.revoke("phone", suspected_compromise=True))["result"]
        world.tick(body, 3)
        after = [(r.seq, r.hash) for r in body.ledger.by_type("event")]
        assert after[:len(before)] == before                                 # nothing before the revocation changed
        [review] = [e.payload for e in body.journal.replay(revocation.REVIEW_RECORD)]
        print("status:", review["status"], "kinds:", [c["kind"] for c in review["commands"]])
        print("effects:", [(x["effect"], x.get("mission_id")) for x in review["effects"]])
        print("standing:", [c.get("standing", "")[:40] for c in review["commands"] if c["kind"] == "DECISION"])
        assert review["status"] == "OPEN_FOR_FOUNDER_REVIEW"
        from provenance.ledger import sha256_json
        assert [c["command_digest"] for c in review["commands"]] == [sha256_json(c) for c in signed]
        assert all(c["signature_verifies"] for c in review["commands"])
        assert body.ledger.verify_chain()[0]
        assert [a for a in actions(body, "m:gated")][0] == ran
    shown = [r for r in status(world.home)["decisions_required"] if r["kind"] == revocation.REVIEW_ASK]
    assert len(shown) == 1 and shown[0].get("answerable") is not False


MALFORMED = [{"device_key_id": {"a": 1}}, {"device_key_id": None}, {"device_key_id": ["x"]}, {},
             {"suspected_compromise": True}, {"device_key_id": "KID", "suspected_compromise": None},
             {"device_key_id": "KID", "suspected_compromise": 1}, {"device_key_id": "KID", "suspected_compromise": "true"},
             {"device_key_id": "KID", "suspected_compromise": [True]}, {"device_key_id": "KID", "extra": 1},
             {"device_key_id": "KID" * 5000, "suspected_compromise": True},
             {"device_key_id": "ed25519:" + "0" * 32, "suspected_compromise": True}]


def test_B4_malformed_revocations_through_the_inbox_are_rejected_and_the_body_keeps_turning(world):
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=phone))
        for i, bad in enumerate(MALFORMED):
            payload = json.loads(json.dumps(bad).replace('"KID"', json.dumps(world.kid("phone"))))
            drop(world.home, world.sign("DEVICE_REVOKE", payload), f"{i:03d}.json")
        body.apply(world.sign("BODY_PAUSE", {}))
        turn = world.tick(body)                                 # a paused body reads its inbox
        print([c["status"] for c in turn["commands"]])
        assert all(c["status"] != "APPLIED" for c in turn["commands"])
        assert world.kid("phone") in body.device_keys() and body.journal.replay("device.revoked") == []
        body.apply(world.sign("BODY_RESUME", {}))
        world.tick(body, 3)
        assert note.read_text() == "approved"                   # the phone was never revoked: its approval ran


def test_B5_a_second_suspicion_and_a_suspicion_for_a_key_never_delegated_are_refused(world):
    from greg.missions import MissionError
    with world.body() as body:
        world.enroll(body, "phone")
        body.apply(world.revoke("phone"))
        body.apply(world.revoke("phone", suspected_compromise=True))
        with pytest.raises(MissionError):
            body.apply(world.revoke("phone", suspected_compromise=True))
        with pytest.raises(MissionError):
            body.apply(world.sign("DEVICE_REVOKE", {"device_key_id": "ed25519:" + "1" * 32, "suspected_compromise": True}))
        from greg.founder import key_id, public_bytes
        founder_kid = key_id(public_bytes(world.key.public_key()).hex())
        with pytest.raises(MissionError):
            body.apply(world.sign("DEVICE_REVOKE", {"device_key_id": founder_kid, "suspected_compromise": True}))
        world.tick(body, 2)
        assert len(body.journal.replay(revocation.REVIEW_RECORD)) == 1
        assert len(body.journal.replay("device.revoked")) == 2
