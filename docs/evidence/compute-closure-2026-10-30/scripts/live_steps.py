"""LOCAL-REAL: a signed fs.write mission closes on a real body while real /proc telemetry is recorded around it; the
step time is read back from the ledger and recommend() is called on the real window. A second, paid mission waits
for an approval (test key) for WAIT seconds; that wait must not be booked as step time.
Usage: python -B live_steps.py SCRATCH_DIR > live-mission-step-timing.json"""
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from greg import compute  # noqa: E402
from greg.body import Body  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy  # noqa

WAIT = 2.0
tmp = Path(tempfile.mkdtemp(prefix="wu05-steps-", dir=sys.argv[1]))
home, key, body_id, _ = make_body(tmp)
straight, paid = "m:compute-closure-steps", "m:compute-closure-approval"
ws = workspace(home, straight)
drop(home, signed(key, body_id, "MISSION", mission(
    straight, checks=[note_check("n", ws / "n.txt", "done")], strategies=[write_strategy("w", "n.txt", "done", ["n"])],
    capabilities=["fs.read", "fs.write"])))
ws2 = workspace(home, paid)
drop(home, signed(key, body_id, "MISSION", mission(
    paid, checks=[note_check("filed", ws2 / "f.txt", "filed")], capabilities=["fs.read"], budget=1.0,
    strategies=[write_strategy("file", "f.txt", "filed", ["filed"], cost_usd=0.5, rationale="file now")])))
clock = Clock()
with Body(home, clock=clock) as body:
    compute.record_telemetry(body.journal, body.layout.home)
    for _ in range(4):
        body.tick()
        clock.advance(1)
    rid = next(e.payload["request_id"] for e in body.journal.replay("decision.requested")
               if e.payload["kind"] == "APPROVAL")
time.sleep(WAIT)                                       # the founder takes a while to approve
drop(home, signed(key, body_id, "DECISION", {"request_id": rid, "answer": "approve"}))
with Body(home, clock=clock) as body:
    for _ in range(4):
        body.tick()
        clock.advance(1)
    for _ in range(compute.SUSTAINED_SAMPLES - 1):
        compute.record_telemetry(body.journal, body.layout.home)
    steps = compute.step_times(body.journal)
    window = body.journal.replay("compute.telemetry")[-compute.SUSTAINED_SAMPLES:]
    found = compute.quantify(body.journal, window)
    actions = [(e.payload["mission_id"], e.payload["status"]) for e in body.journal.replay("mission.action")]
    ask = compute.recommend(body.journal)
    achieved = [e.payload["mission_id"] for e in body.journal.replay("mission.achieved")]
print(json.dumps({"wait_seconds": WAIT, "achieved": achieved, "actions": actions, "steps": steps,
                  "quantify": found, "samples": [{k: e.payload.get(k) for k in ("at", "load_ratio", "psi_cpu_some_avg60",
                                                 "psi_memory_some_avg60", "psi_io_some_avg60", "mem_available_ratio")}
                                                 for e in window],
                  "ask": None if ask is None else {"request_id": ask["request_id"],
                                                   "bottleneck": ask["evidence"]["bottleneck"]["resource"],
                                                   "first_option": ask["options"][0]["option"],
                                                   "delay_basis": ask["evidence"]["delay"]["basis"]}}, indent=1))
