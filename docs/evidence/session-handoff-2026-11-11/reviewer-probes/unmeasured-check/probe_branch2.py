"""Second-branch fault (the Mind's answer names the construction that faulted): what the mission does on each pass."""
import sys, tempfile, pathlib
from greg.body import Body
from greg.cognition import network
from greg.templates import compiled_question
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.integration.test_greg_mind_constructs_capability import STAFFING, compile_receipts

tmp = pathlib.Path(tempfile.mkdtemp())
home, key, body_id, _ = make_body(tmp)
spec = compiled_question(problem_id="staff-3", data=STAFFING, allow_construction=True)
drop(home, signed(key, body_id, "MISSION", spec))
clock = Clock()
with Body(home, clock=clock) as body:
    body.boot()
    body.tick(); clock.advance(31)
    lie = network.RUNNERS["networkx.max_flow"].replace(
        "def solve(req):", "def solve(req):\n    return {'flows': [], 'value': 0}\ndef _honest(req):", 1)
    network.RUNNERS["networkx.max_flow"] = lie
    states = []
    for _ in range(8):
        states.append(body.tick()["missions"][0]["state"]); clock.advance(31)
    asks = [(e.payload.get("kind"), (e.payload.get("why") or "")[:70]) for e in body.journal.replay("decision.requested")]
    actions = [(e.payload["action_id"], e.payload["status"], e.payload["attempt"]) for e in body.journal.replay("mission.action")]
    blocked = [e.payload.get("blocker", {}).get("why") for e in body.journal.replay("mission.blocked")]
    print("states:", states)
    print("asks:", asks)
    print("actions:", actions)
    print("blocked:", blocked[:4])
