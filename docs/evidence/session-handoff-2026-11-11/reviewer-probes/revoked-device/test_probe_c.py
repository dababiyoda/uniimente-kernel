"""Reviewer probes, set C: the separate appraiser must not refute an honest closure (tests the builder's gate lacks:
mutants R3 and R4 survive its 50 tests)."""
import pytest

from tests.unit.test_greg_revoked_device_authority import World, actions, asked, open_asks  # noqa


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def verdict_of(body):
    return body.journal.replay("mission.appraised")[-1].payload


def test_C3_another_devices_revocation_between_approval_and_dispatch_refutes_nothing(world):
    with world.body() as body:
        body.boot()
        phone, laptop = world.enroll(body, "phone"), world.enroll(body, "laptop")
        note, ask = asked(world, body)
        body.apply(world.approve(ask["request_id"], key=laptop))      # the laptop approves
        body.apply(world.revoke("phone"))                             # the PHONE is revoked before the dispatch
        world.tick(body, 4)
        assert note.read_text() == "approved"
        verdict = verdict_of(body)
        print(verdict["verdict"], verdict["findings"])
        assert verdict["checks"]["approval_boundaries_honored"] is True, verdict["findings"]


def test_C4_a_fresh_approval_of_a_re_delegated_key_is_not_refuted_for_the_keys_earlier_revocation(world):
    with world.body() as body:
        body.boot()
        phone = world.enroll(body, "phone")
        note, ask = asked(world, body)
        body.apply(world.revoke("phone"))                             # revoked before it approved anything
        world.clock.advance(60)
        world.enroll(body, "phone")                                   # the same key, delegated again
        world.clock.advance(5)
        body.apply(world.approve(ask["request_id"], key=phone))       # signed under the new delegation
        world.tick(body, 4)
        assert note.read_text() == "approved"
        verdict = verdict_of(body)
        print(verdict["verdict"], verdict["findings"])
        assert verdict["checks"]["approval_boundaries_honored"] is True, verdict["findings"]
