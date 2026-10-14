"""A strategy may bind the exact evidence that satisfied its precondition (``from: {check_id}``).

Before this, ``bind`` read only another strategy's latest DONE receipt. When the producer's
answer arrives through a re-observation (the Mind answered only after Genesis attached a
construction), that receipt held the pre-construction deficit and the Hands could not be
handed the answer. A check-sourced edge reads the latest *passing* observation receipt of a
check the strategy already ``requires``; it is data, not authority.
"""
import pytest

from greg.body import Body
from greg.missions import MissionError, validate_mission
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy


def spec_for(home, mid="m:bind-check", *, requires=True):
    ws = workspace(home, mid)
    first, second = ws / "first.txt", ws / "second.txt"
    copy = write_strategy("copy", "second.txt", "", ["second"], requires=["first"] if requires else [])
    del copy["params"]["content"]
    copy["bind"] = [{"param": "content", "from": {"check_id": "first", "field": "text"}, "type": "string",
                     "template": "copied: {value}"}]
    return mission(mid, checks=[note_check("first", first, "alpha"), note_check("second", second, "copied: alpha")],
                   strategies=[write_strategy("write", "first.txt", "alpha", ["first"]), copy],
                   capabilities=["fs.read", "fs.write"])


def test_binding_from_a_check_the_strategy_does_not_require_is_refused(tmp_path):
    home = tmp_path / "h"
    with pytest.raises(MissionError, match="does not require"):
        validate_mission(spec_for(home, requires=False))


def test_check_sourced_binding_carries_the_passing_observation(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = spec_for(home)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        states = []
        for _ in range(6):
            states.append(body.tick()["missions"][0]["state"])
            clock.advance(31)
        assert "ACHIEVED" in states, states
        copy = [e.payload for e in body.journal.replay("mission.action")
                if e.payload["action_id"] == "copy" and e.payload["status"] == "DONE"][0]
        [binding] = copy["bindings"]
        passing = [e.payload["receipt"] for e in body.journal.replay("mission.observed")
                   if e.payload["check_id"] == "first" and e.payload["passed"]]
        assert binding["from_check"] == "first" and binding["from_receipt"] in passing
        assert "from_action" not in binding
        assert (workspace(home, spec["mission_id"]) / "second.txt").read_text() == "copied: alpha"
        appraised = [e.payload for e in body.journal.replay("mission.appraised")][-1]
        assert appraised["verdict"] == "VERIFIED", appraised
