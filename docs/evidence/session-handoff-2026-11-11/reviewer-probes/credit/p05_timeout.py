"""A later mission asks the same signed question and the solver worker is stopped by the host (timeout, then crash)."""
import subprocess
from rc_common import *
import greg.capabilities as caps
MODE = sys.argv[1] if len(sys.argv) > 1 else "timeout"
body, sign, clock, _, _k = open_body(tmp())
try:
    j = body.journal
    sign("MISSION", solve_mission("m:first", solve_check("good", "real:q", 3)))
    sign("MISSION", solve_mission("m:other", solve_check("good", "real:other", 4)))
    turn(body, clock)
    out("credit0", credit(body)); out("credited0", credited(j))
    real = caps.run_isolated
    def stalled(argv, *a, **kw):
        if any("worker.py" in str(x) for x in argv):
            if MODE == "timeout":
                raise subprocess.TimeoutExpired(argv, kw.get("timeout", 5))
            return subprocess.CompletedProcess(argv, 137, b"", b"killed")       # the host killed the worker (OOM)
        return real(argv, *a, **kw)
    caps.run_isolated = stalled
    sign("MISSION", solve_mission("m:second", solve_check("good", "real:q", 3)))   # the identical signed check
    body.tick(); clock.advance(31)
    obs = [e.payload for e in j.replay("mission.observed") if e.payload["mission_id"] == "m:second"]
    o = j.ledger.find(obs[-1]["receipt"]).payload["result"]["output"]
    out("m:second reading", {"passed": obs[-1]["passed"], "detail": obs[-1]["detail"][:120], "state": o.get("state"),
                             "abstentions": o.get("abstentions"), "has abstention_state key": "abstention_state" in o})
    body.tick(); clock.advance(31)
    out("causes", causes(j)); out("contained", contained(j))
    out("credit while the host stalls", credit(body)); out("credited", credited(j))
    out("asks", [r["kind"] for r in __import__("greg.asks", fromlist=["x"]).open_requests(j.replay())])
    out("settled", settled_records(j))
    caps.run_isolated = real
    for i in range(6):
        body.tick(); clock.advance(400)
    out("after 2400 s of recovered host", {"credit": credit(body), "m:second readings": len([e for e in j.replay("mission.observed") if e.payload["mission_id"] == "m:second"])})
    for i in range(4):
        body.tick(); clock.advance(3700)
    out("m:second readings", [(e.payload["passed"], e.payload["detail"][:50]) for e in j.replay("mission.observed") if e.payload["mission_id"] == "m:second"])
    out("requalified", [e.payload["cause_id"][:14] for e in j.replay("evidence.requalified")])
    out("credit after the host recovers", credit(body)); out("credited", credited(j))
finally:
    body.close()
