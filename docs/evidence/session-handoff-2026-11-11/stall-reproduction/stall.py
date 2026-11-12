"""A signed question whose solver worker the host stops (timeout or crash): what does the mission engine do?
usage (cwd = a worktree): stall.py timeout|crash [ticks]"""
import subprocess, sys
from rc_common import *
import greg.capabilities as caps
MODE, N = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 8
body, sign, clock, _, _k = open_body(tmp())
try:
    j = body.journal
    real = caps.run_isolated
    def stalled(argv, *a, **kw):
        if any("worker.py" in str(x) for x in argv):
            if MODE == "timeout":
                raise subprocess.TimeoutExpired(argv, kw.get("timeout", 5))
            return subprocess.CompletedProcess(argv, 137, b"", b"killed")
        return real(argv, *a, **kw)
    caps.run_isolated = stalled
    sign("MISSION", solve_mission("m:quest", solve_check("good", "real:q", 3)))
    states = []
    for i in range(N):
        if i == 4:
            caps.run_isolated = real          # the host recovers
        r = body.tick()["missions"]
        states.append(r[0]["state"] if r else None)
        clock.advance(31)
    m = body.engine.book.missions["m:quest"]
    ev = lambda k: [e.payload for e in j.replay(k)]
    out("states", states)
    out("asks", [r["kind"] for r in ev("decision.requested")]); out("withdrawn", len(ev("decision.withdrawn")))
    out("actions", [(a["action_id"], a["status"], a["attempt"]) for a in ev("mission.action")])
    out("failed", {k: v[:90] for k, v in m.failed.items()})
    out("observed", [(o["passed"], o.get("failure_class"), o["detail"][:70]) for o in ev("mission.observed")])
    out("routing", [(o["action_id"], o["verdict"]) for o in ev("routing.outcome")])
    out("unmet", [(u["failing_checks"], u.get("unmeasured_checks")) for u in ev("mission.unmet")])
    last = ev("mission.observed")[0]
    o = j.ledger.find(last["receipt"]).payload["result"]["output"]
    out("first reading output", {k: (str(v)[:100]) for k, v in o.items() if k in ("state", "abstentions", "abstention_state", "reason_code", "schema")})
finally:
    body.close()
