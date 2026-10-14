"""A person's work is noticed when it lands, not at the next hourly observation slot.

Found by rehearsing the business case (N3) on the installed body: the founder dropped
acceptance.txt into the case folder and GREG did not see it for the rest of the hour, because a
mission waiting on HUMAN_WORK re-observed only at its cadence. Now the body looks at the metadata
of the deliverable paths its founder-signed mission declares; when one appears or changes, the
governed observation runs immediately. While nothing has landed, nothing is observed, granted or
recorded between slots.

The fixture clock starts an hour in the past so that real file timestamps (which a fake clock
cannot move) are newer than the moment the mission blocked, as they are on a real body.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, signed, workspace
from tests.unit.test_greg_shared_work import REF, asks, work_spec


def start(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock(datetime.now(timezone.utc) - timedelta(hours=1))
    body = Body(home, clock=clock).open()
    body.boot()
    drop(home, signed(key, body_id, "BODY_DESIGNATE", {"purpose": "first_founder_body"}, now=clock.now))
    body.tick()
    spec = work_spec(home)
    drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))
    for _ in range(3):
        body.tick()
        clock.advance(1)
    return body, clock, spec["mission_id"], workspace(home, spec["mission_id"])


def quiet_ticks(body, clock, n=5, step=60):
    for _ in range(n):
        clock.advance(step)
        body.tick()


def counts(body):
    return {name: len(body.journal.replay(name))
            for name in ("mission.observed", "mission.action", "decision.requested", "decision.withdrawn")}


def test_the_deliverable_is_observed_within_a_minute_not_an_hour(tmp_path):
    body, clock, mid, folder = start(tmp_path)
    try:
        [agree] = asks(body, mid)
        assert agree["action_id"] == "agree-terms"
        before = counts(body)
        quiet_ticks(body, clock)                                    # five minutes, nothing delivered
        assert counts(body) == before                               # no reads, grants or records between slots

        (folder / "consent.txt").write_text(f"I, Dana Reyes, agree to {REF} as written.\n")
        quiet_ticks(body, clock, n=2)                               # two minutes later, well inside the hour
        withdrawn = {e.payload["request_id"] for e in body.journal.replay("decision.withdrawn")}
        assert agree["request_id"] in withdrawn
        assert [a["action_id"] for a in asks(body, mid)] == ["agree-terms", "do-the-work"]

        (folder / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        quiet_ticks(body, clock, n=2)
        assert [a["action_id"] for a in asks(body, mid)][-1] == "review"
    finally:
        body.close()


def test_a_refusal_note_is_also_noticed_promptly(tmp_path):
    body, clock, mid, folder = start(tmp_path)
    try:
        (folder / "declined.txt").write_text(f"Dana declines {REF}: no capacity this month\n")
        quiet_ticks(body, clock, n=2)
        [honored] = [e.payload for e in body.journal.replay("human.refusal_honored")]
        assert honored["action_id"] == "agree-terms"
    finally:
        body.close()


def test_an_unrelated_file_does_not_trigger_an_early_observation(tmp_path):
    body, clock, mid, folder = start(tmp_path)
    try:
        before = counts(body)
        (folder / "notes.txt").write_text("scratch\n")             # not a path the mission declared
        (folder / "logo.png").write_bytes(b"png")                   # a later step's file, not the one waited on
        quiet_ticks(body, clock)
        assert counts(body) == before
    finally:
        body.close()
