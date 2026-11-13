"""A person's work is noticed when it lands, not at the next hourly observation slot.

Found by rehearsing the business case (N3) on the installed body: the founder dropped
acceptance.txt into the case folder and GREG did not see it for the rest of the hour, because a
mission waiting on HUMAN_WORK re-observed only at its cadence. Now the body looks at the metadata
of the deliverable paths its founder-signed mission declares; when one appears or changes, the
governed observation runs immediately. While nothing has landed, nothing is observed, granted or
recorded between slots.

Also exercised (PR #184's port of #168 ``924bede``) with this branch's own ``templates.human_work``, whose one
deliverable is the file the mission's sensor reads.

The fixture clock starts an hour in the past so that real file timestamps (which a fake clock
cannot move) are newer than the moment the mission blocked, as they are on a real body.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from greg.body import Body, Layout
from greg.templates import human_work
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


def test_the_exported_payment_statement_is_noticed_within_minutes(tmp_path):
    """The payment step's sensor is business.reconcile, not fs.read: it was still noticed only at the
    hourly slot (review of 2026-10-14). Any read-only sensor naming a file path now counts."""
    from tests.unit.test_greg_business_case import HEADER, REF as CASE_REF, case_spec, human_asks
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock(datetime.now(timezone.utc) - timedelta(hours=1))
    body = Body(home, clock=clock).open()
    body.boot()
    try:
        drop(home, signed(key, body_id, "BODY_DESIGNATE", {"purpose": "first_founder_body"}, now=clock.now))
        body.tick()
        spec = case_spec(home)
        mid, folder = spec["mission_id"], workspace(home, spec["mission_id"])
        drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))
        for _ in range(3):
            body.tick()
            clock.advance(1)
        (folder / "acceptance.txt").write_text(f"Acme accepts {CASE_REF}: summary within 5 business days\n")
        quiet_ticks(body, clock, n=2)
        [_, collect] = human_asks(body, mid)
        assert collect["evidence"]["function"] == "human.collect_payment"
        quiet_ticks(body, clock, n=5)              # the person takes five minutes; GREG's observation round ran
        (folder / "statement.csv").write_text(HEADER + f"2026-10-02,Payment {CASE_REF},250.00,USD\n")
        quiet_ticks(body, clock, n=2)              # two minutes later, well inside the hour
        withdrawn = {e.payload["request_id"] for e in body.journal.replay("decision.withdrawn")}
        assert collect["request_id"] in withdrawn
    finally:
        body.close()


def start_template(tmp_path):
    """A mission built by ``templates.human_work``: one person, one deliverable file, one HUMAN_WORK ask."""
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock(datetime.now(timezone.utc) - timedelta(hours=1))
    body = Body(home, clock=clock).open()
    body.boot()
    drop(home, signed(key, body_id, "BODY_DESIGNATE", {"purpose": "first_founder_body"}, now=clock.now))
    body.tick()
    spec = human_work(function="professional.legal_review", purpose="Have my lease reviewed before I sign it",
                      deliverable="lease-review.pdf", workspace_root=Layout(home).workspace)
    drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))
    for _ in range(3):
        body.tick()
        clock.advance(1)
    [ask] = [e.payload for e in body.journal.replay("decision.requested")]
    path = Path(ask["evidence"]["deliverable_observed_by"][0]["params"]["path"])
    return body, clock, spec["mission_id"], ask, path


def test_a_template_deliverable_is_observed_within_minutes_not_at_the_next_hourly_slot(tmp_path):
    body, clock, mid, ask, path = start_template(tmp_path)
    try:
        assert ask["kind"] == "HUMAN_WORK"
        before = counts(body)
        quiet_ticks(body, clock)                                   # five minutes, nothing delivered
        assert counts(body) == before                              # no reads, grants or records between slots
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"%PDF-1.4 attorney opinion\n")           # the person's deliverable arrives
        quiet_ticks(body, clock, n=2)                              # two minutes later, well inside the hour
        withdrawn = {e.payload["request_id"] for e in body.journal.replay("decision.withdrawn")}
        assert ask["request_id"] in withdrawn
        assert [e.payload["mission_id"] for e in body.journal.replay("mission.achieved")] == [mid]
        assert not body.journal.replay("mission.action")          # GREG still did nothing itself
    finally:
        body.close()


def test_an_unrelated_file_beside_a_template_deliverable_does_not_trigger_an_early_observation(tmp_path):
    body, clock, mid, ask, path = start_template(tmp_path)
    try:
        before = counts(body)
        path.parent.mkdir(parents=True, exist_ok=True)
        (path.parent / "notes.txt").write_text("not the deliverable\n")
        quiet_ticks(body, clock, n=3)
        assert counts(body) == before
    finally:
        body.close()
