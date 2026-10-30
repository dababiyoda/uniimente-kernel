"""A mission whose only route waits on a precondition the world must satisfy resumes when the world satisfies it.

Before: every remaining strategy was held by a failing ``requires`` check that no strategy advances, so the engine
raised one NO_STRATEGY ask and blocked. Its watcher then waited for every failing check to pass on its own, but the
checks the held strategy advances can pass only after it runs: the mission stayed blocked for good, even after the
precondition was observed passing (found by tests/integration/test_one_mission_fifteen_steps.py). Now the ask is
withdrawn as moot once observation says the precondition passes, and the held strategy runs. Timing, scope and
authority are unchanged: the precondition is still only observed, never acted on.
"""
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

MID = "m:gated"
CADENCE = 3600


def spec(home, data):
    ws = workspace(home, MID)
    return mission(MID, checks=[note_check("gate", data / "request.txt", "go"), note_check("out", ws / "out.txt", "done")],
                   strategies=[write_strategy("work", "out.txt", "done", ["out"], requires=["gate"])],
                   capabilities=["fs.read", "fs.write"], closure={"kind": "bounded", "cadence_seconds": CADENCE})


def run(tmp_path, *, request: str | None):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", spec(home, data)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(3):
            body.tick()
            clock.advance(31)
        assert [e.payload["kind"] for e in body.journal.replay("decision.requested")] == ["NO_STRATEGY"]
        if request is not None:
            (data / "request.txt").write_text(request)
        clock.advance(CADENCE + 1)                       # the mission's own cadence: no goal, no pull
        states = []
        for _ in range(4):
            states.append(body.tick()["missions"][0]["state"])
            clock.advance(31)
        events = {k: [e.payload for e in body.journal.replay(k)]
                  for k in ("decision.requested", "decision.withdrawn", "mission.action", "mission.achieved")}
    return states, events


def test_the_held_strategy_runs_once_its_precondition_is_observed_passing(tmp_path):
    states, events = run(tmp_path, request="go")
    assert events["mission.achieved"], states
    [withdrawn] = events["decision.withdrawn"]
    assert "the precondition that held work now passes" in withdrawn["why"]
    assert [(a["action_id"], a["status"]) for a in events["mission.action"]] == [("work", "DONE")]
    assert [r["kind"] for r in events["decision.requested"]] == ["NO_STRATEGY"]       # nothing new was asked


def test_a_precondition_still_failing_keeps_the_mission_waiting_without_a_second_ask(tmp_path):
    states, events = run(tmp_path, request="not yet")
    assert not events["mission.achieved"] and not events["mission.action"] and not events["decision.withdrawn"]
    assert [r["kind"] for r in events["decision.requested"]] == ["NO_STRATEGY"]
    assert set(states) <= {"WAITING", "BLOCKED"}, states
