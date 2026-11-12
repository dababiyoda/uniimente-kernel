"""The founder answers the SENSOR_FAILURE question while the host is still down: what does the mission do next? cwd = tree."""
import sys
from rcu_common import *
ANSWER = sys.argv[1] if len(sys.argv) > 1 else "approve"
host = Host()
with Run() as run:
    host.stall("timeout")
    run.sign("MISSION", question("m:nbr", fitness_check()))
    s1 = [run.tick("m:nbr") for _ in range(5)]
    asks_ = run.events("decision.requested")
    print("  before the answer:", s1, [a["kind"] for a in asks_])
    try:
        r = run.sign("DECISION", {"request_id": asks_[0]["request_id"], "answer": ANSWER, "mission_id": "m:nbr"})
        print("  DECISION", ANSWER, "->", str(r)[:100])
    except Exception as e:
        print("  DECISION refused:", type(e).__name__, str(e)[:200])
    s2 = [run.tick("m:nbr") for _ in range(12)] + [run.tick("m:nbr", step=3700) for _ in range(4)]
    print("  after the answer (12 ticks 31 s, 4 ticks 3700 s):", s2)
    print("  asks:", [(run.offset(a["created_at"]), a["kind"]) for a in run.events("decision.requested")], "| answered:", [(a.get("answer")) for a in run.events("decision.answered")])
    print("  observations:", len(run.events("mission.observed", "m:nbr")), "| blocker:", (run.mission("m:nbr").blocker or {}).get("why"), "| status:", run.mission("m:nbr").status)
