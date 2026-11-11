"""Reviewer probe F: a compensation approved by a device that is revoked before it is dispatched (the builder's 50
tests never mention a compensation)."""
import pytest

from tests.greg_fixtures import drop
from tests.unit.test_greg_revoked_device_authority import World, open_asks, trail  # noqa
from test_probe_e import MID, compensated, superseded_and_approved, receipts_of_compensation  # noqa


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def test_F1_a_compensation_approved_by_a_device_revoked_before_its_dispatch_does_not_run(world):
    with world.body() as body:
        phone = world.enroll(body, "phone")
        note, ask = superseded_and_approved(world, body, phone)       # the phone approved the compensation
        drop(world.home, world.revoke("phone"), "a-revoke.json")
        world.tick(body, 4)
        assert note.read_text() == "draft" and compensated(body) == [] and receipts_of_compensation(body) == []
        [again] = open_asks(body, MID)
        assert again["request_id"] != ask["request_id"] and again.get("compensation") is True
        [void] = trail(body, ask["request_id"])
        assert void["voids_approval"] is True
        body.apply(world.approve(again["request_id"]))                 # the founder approves: it runs once
        world.tick(body, 3)
        assert note.read_text() == "original" and [c["status"] for c in compensated(body)] == ["DONE"]
