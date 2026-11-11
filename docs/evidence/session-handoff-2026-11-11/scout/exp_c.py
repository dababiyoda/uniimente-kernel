"""Scratch experiment (not repository code): C's minimum test on the unchanged integration head.

A strategy passes its signed precondition at planning time and waits for a founder approval (outside the cone).
The prerequisite changes before the approval arrives. Expectation under test: the approved-but-stale action is
withheld and unrelated work in the same mission continues."""
import json, sys, tempfile
from pathlib import Path
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

MID = "m:plan"
tmp = Path(tempfile.mkdtemp(dir=sys.argv[1]))
home, key, body_id, data = make_body(tmp)
ws = workspace(home, MID)
(data / "request.txt").write_text("go")
(data / "late.txt").write_text("not yet")
spec = mission(MID,
    checks=[note_check("gate", data / "request.txt", "go"), note_check("out", ws / "out.txt", "done"),
            note_check("late-gate", data / "late.txt", "go"), note_check("late", ws / "late.txt", "ok")],
    strategies=[write_strategy("work", "out.txt", "done", ["out"], requires=["gate"]),
                write_strategy("late", "late.txt", "ok", ["late"], requires=["late-gate"])],
    capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:late.txt"),
    closure={"kind": "bounded", "cadence_seconds": 60})
drop(home, signed(key, body_id, "MISSION", spec))
clock = Clock()
out = {}
with Body(home, clock=clock) as body:
    body.boot()
    for _ in range(3):
        body.tick(); clock.advance(61)
    asked = [e.payload for e in body.journal.replay("decision.requested")]
    out["asked_at_planning"] = [(a["kind"], a.get("action_id")) for a in asked]
    out["gate_at_planning"] = [e.payload["passed"] for e in body.journal.replay("mission.observed") if e.payload["check_id"] == "gate"][-1]
    approval = next(a for a in asked if a["kind"] == "APPROVAL")
    # the decisive prerequisite changes between planning (the ask) and dispatch (after the approval)
    (data / "request.txt").write_text("halt")
    (data / "late.txt").write_text("go")
    drop(home, signed(key, body_id, "DECISION", {"request_id": approval["request_id"], "answer": "approve", "reason": "ok"}))
    states = []
    for _ in range(5):
        states.append(body.tick()["missions"][0]["state"]); clock.advance(61)
    acts = [(e.payload["action_id"], e.payload["status"]) for e in body.journal.replay("mission.action")]
    out["states_after_approval"] = states
    out["actions"] = acts
    out["out_file_exists"] = (ws / "out.txt").exists()
    out["late_file"] = (ws / "late.txt").read_text() if (ws / "late.txt").exists() else None
    out["asks_after"] = [(e.payload["kind"], e.payload.get("action_id"), (e.payload.get("evidence") or {}).get("held_by_precondition")) for e in body.journal.replay("decision.requested")]
    out["withdrawn"] = [e.payload.get("why", "")[:120] for e in body.journal.replay("decision.withdrawn")]
    # the prerequisite holds again: does the standing approval still admit the action without a new ask?
    (data / "request.txt").write_text("go")
    states = []
    for _ in range(4):
        states.append(body.tick()["missions"][0]["state"]); clock.advance(61)
    out["states_after_prereq_returns"] = states
    out["actions_final"] = [(e.payload["action_id"], e.payload["status"]) for e in body.journal.replay("mission.action")]
    out["asks_final"] = [(e.payload["kind"], e.payload.get("action_id")) for e in body.journal.replay("decision.requested")]
print(json.dumps(out, indent=1, default=str))
