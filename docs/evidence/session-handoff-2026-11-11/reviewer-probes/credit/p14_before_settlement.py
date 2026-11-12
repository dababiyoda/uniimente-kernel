"""The correction arrives before the settlement: the appraiser is unavailable when the mission closes, the founder
rejects the closure, and the appraisal lands afterwards."""
from rc_common import *
body, sign, clock, _, _k = open_body(tmp())
try:
    j = body.journal
    real = body.appraise
    down = {"on": True}
    def appraise(mid, *, closure_event=None):
        if down["on"]:
            return {"mission_id": mid, "head": body.ledger.head, "verdict": "UNAVAILABLE", "checks": {}, "findings": ["the appraiser is down"], "appraiser": "separate process"}
        return real(mid, closure_event=closure_event)
    body.appraise = appraise
    sign("MISSION", solve_mission("m:early", solve_check("good", "real:early", 3)))
    body.tick(); clock.advance(31)
    out("closed, unappraised", {"achieved": len(j.replay("mission.achieved")), "appraised": [e.payload["verdict"] for e in j.replay("mission.appraised")], "credit": credit(body)})
    reject(sign, closure_of(j, "m:early").event_id, "wrong")
    body.tick(); clock.advance(31)
    out("rejected before any appraisal", {"causes": causes(j), "contained": contained(j), "settled rows": len(j.replay("cognition.settled"))})
    down["on"] = False
    turn(body, clock, 3)
    out("appraisal lands afterwards", {"appraised": [e.payload["verdict"] for e in j.replay("mission.appraised")], "credit": credit(body), "credited": credited(j),
                                       "settled rows": settled_records(j), "contained": contained(j)})
finally:
    body.close()
