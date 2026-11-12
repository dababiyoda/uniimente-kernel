"""A standing (infinite) compile question on a host that stalls for 2 minutes out of every cadence. cwd = tree."""
import sys
from rcu_common import *
host = Host()
with Run() as run:
    run.sign("MISSION", question("m:nbr", fitness_check(), closure={"kind": "infinite", "cadence_seconds": 600}))
    rows = []
    for cycle in range(4):
        # the host is up: one pass holds
        host.recover(); rows.append((run.offset(), "up", run.tick("m:nbr", step=600)))
        # the host stalls for the next reading and four ticks (124 s), then returns
        host.stall("timeout")
        for _ in range(5): rows.append((run.offset(), "down", run.tick("m:nbr")))
        host.recover()
        for _ in range(2): rows.append((run.offset(), "up", run.tick("m:nbr")))
    print("  ticks:", rows)
    print("  asks:", [(run.offset(a["created_at"]), a["kind"]) for a in run.events("decision.requested")])
    print("  withdrawn:", [(run.offset(w["at"])) for w in run.events("decision.withdrawn")])
    print("  observations:", [(run.offset(o["at"]), o["passed"], o.get("failure_class")) for o in run.events("mission.observed", "m:nbr")])
