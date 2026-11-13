"""A check whose sensor call the host stopped is not pursued (review of composed candidate #299, on #196).

#298 stopped pursuing a check that a faulted capability could not read, and the Mind's path already treats a
construction stopped by the host (`transient`) or by a resource ceiling (`budget_exceeded`) as inconclusive. The
ordinary sensor-call path did not: a plain `fs.read` that timed out put its check in `sensor_errors` but not in
`inconclusive`. Next to a real failure of another check, the pass then pursued the unread check and dispatched its
completed write again, overwriting a line a person had added since. A failure the host caused measures nothing, so
the check waits for a re-observation and no strategy is replayed.
"""
from __future__ import annotations

import pytest

from greg import builders
from greg.capabilities import CapabilityError
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy
from tests.unit.test_greg_functional_reconstitution import _events, _open, _ticks


@pytest.mark.parametrize("failure_class", ["transient", "budget_exceeded"])
def test_a_completed_write_is_not_dispatched_again_when_its_check_cannot_be_read(tmp_path, failure_class):
    home, key, body_id, data = make_body(tmp_path)
    note = workspace(home, "m:replay") / "note.md"
    (data / "request.txt").write_text("go")
    spec = mission("m:replay", checks=[note_check("noted", note, "enroll key"),
                                       note_check("request", data / "request.txt", "go")],
                   strategies=[write_strategy("note", "note.md", "- [ ] enroll key\n", ["noted"])],
                   capabilities=["fs.read", "fs.write"], budget=1.0,
                   closure={"kind": "infinite", "cadence_seconds": 60})
    drop(home, signed(key, body_id, "MISSION", spec))
    clock, calls = Clock(), []
    body = _open(home, clock, builders.StaticBuilder(identity="static-test"), calls)
    try:
        before = _ticks(body, clock, 4)
        assert before[-1] == "HOLDING" and calls == ["note.md"], (before, calls)
        note.write_text(note.read_text() + "- [x] reviewed by a person\n")
        real = body.registry.adapters["fs.read"]

        def stopped_by_host(params, ctx):
            if str(params.get("path", "")).endswith("note.md"):
                raise CapabilityError("host timed out reading", failure_class=failure_class)
            return real(params, ctx)

        body.registry.adapters["fs.read"] = stopped_by_host
        (data / "request.txt").write_text("halt")          # an unrelated check really fails
        states = _ticks(body, clock, 3)
        acts = [(a["status"], a["attempt"]) for a in _events(body, "mission.action") if a["action_id"] == "note"]
        assert calls == ["note.md"], (states, calls, acts)  # the completed write was not dispatched again
        assert acts == [("DONE", 0)], acts
        assert "reviewed by a person" in note.read_text()
        observed = [o for o in _events(body, "mission.observed") if o["check_id"] == "noted" and not o["passed"]]
        assert observed and observed[-1].get("failure_class") == failure_class
        assert "inconclusive" in observed[-1]["detail"]
    finally:
        body.close()
