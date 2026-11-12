"""The host stalls a sensor-only compile question, and returns after N ticks (31 s apart). cwd = tree. usage: churn.py <recover_tick>"""
import sys
from rcu_common import *
from greg import asks
R = int(sys.argv[1])
host = Host()
with Run() as run:
    host.stall("timeout")
    run.sign("MISSION", question("m:nbr", fitness_check()))
    rows = []
    for i in range(R + 3):
        if i == R: host.recover()
        at = run.offset()
        state = run.tick("m:nbr")
        j = run.body.journal
        open_now = [r["kind"] for r in asks.open_requests(j.replay("decision.") + j.replay("mission.achieved") + j.replay("mission.lifecycle"))]
        rows.append((at, state, open_now))
    print("  [offset_s, state, open asks after the tick]:", rows)
    print("  asks:", [(run.offset(a["created_at"]), a["kind"], a["why_now"], a["recommendation"], a.get("alternatives")) for a in run.events("decision.requested")])
    print("  withdrawn:", [(run.offset(w["at"]), w["why"]) for w in run.events("decision.withdrawn")])
    print("  status:", run.mission("m:nbr").status)
