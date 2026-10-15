"""A person's work is noticed when it lands, not at the next hourly observation slot.

Ported from #168 (``924bede``), which found it by rehearsing the business case on the installed body: the founder
dropped the deliverable into the case folder and GREG did not see it for the rest of the hour, because a mission
waiting on HUMAN_WORK re-observed only at its cadence. Here it is exercised with this branch's own
``templates.human_work``. While nothing has landed, nothing is observed, granted or recorded between slots.

The fixture clock starts an hour in the past so that real file timestamps (which a fake clock cannot move) are newer
than the moment the mission blocked, as they are on a real body.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from greg.body import Body, Layout
from greg.templates import human_work
from tests.greg_fixtures import Clock, drop, make_body, signed


def start(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock(datetime.now(timezone.utc) - timedelta(hours=1))
    body = Body(home, clock=clock).open()
    body.boot()
    spec = human_work(function="professional.legal_review", purpose="Have my lease reviewed before I sign it",
                      deliverable="lease-review.pdf", workspace_root=Layout(home).workspace)
    drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))
    for _ in range(3):
        body.tick()
        clock.advance(1)
    [ask] = [e.payload for e in body.journal.replay("decision.requested")]
    path = Path(ask["evidence"]["deliverable_observed_by"][0]["params"]["path"])
    return body, clock, spec["mission_id"], ask, path


def quiet_ticks(body, clock, n=5, step=60):
    for _ in range(n):
        clock.advance(step)
        body.tick()


def counts(body):
    return {name: len(body.journal.replay(name))
            for name in ("mission.observed", "mission.action", "decision.requested", "decision.withdrawn")}


def test_the_deliverable_is_observed_within_minutes_not_at_the_next_hourly_slot(tmp_path):
    body, clock, mid, ask, path = start(tmp_path)
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


def test_an_unrelated_file_does_not_trigger_an_early_observation(tmp_path):
    body, clock, mid, ask, path = start(tmp_path)
    try:
        before = counts(body)
        path.parent.mkdir(parents=True, exist_ok=True)
        (path.parent / "notes.txt").write_text("not the deliverable\n")
        quiet_ticks(body, clock, n=3)
        assert counts(body) == before
    finally:
        body.close()
