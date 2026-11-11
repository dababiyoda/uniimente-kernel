"""Reviewer probe G: is a key the founder marked as a suspected compromise re-delegated without any friction?"""
import pytest

from greg import revocation
from tests.unit.test_greg_revoked_device_authority import World, asked, actions  # noqa


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_G1_a_key_marked_suspected_is_delegated_again_like_any_other(world):
    with world.body() as body:
        phone = world.enroll(body, "phone")
        body.apply(world.revoke("phone", suspected_compromise=True))
        assert len(body.journal.replay(revocation.REVIEW_RECORD)) == 1        # its review is open, unanswered
        world.clock.advance(60)
        result = world.enroll(body, "phone")                                   # the same key again
        print("re-delegated while its review is open:", world.kid("phone") in body.device_keys())
        note, ask = asked(world, body)
        world.clock.advance(5)
        body.apply(world.approve(ask["request_id"], key=phone))
        world.tick(body, 3)
        print("and its approval ran:", note.exists(), [a["status"] for a in actions(body, "m:gated")])
        assert note.exists()
