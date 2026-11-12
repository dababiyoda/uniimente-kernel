"""The same answer delivered again under a new receipt after the founder rejected it."""
from rc_common import *
body, sign, clock, _, _k = open_body(tmp())
try:
    j = body.journal
    for mid, seed in (("m:okay", 3), ("m:other", 4)):
        sign("MISSION", solve_mission(mid, solve_check("good", f"real:{mid}", seed)))
    turn(body, clock)
    reject(sign, closure_of(j, "m:okay").event_id, "this answer is wrong for my problem")
    turn(body, clock, 2)
    out("credit after reject", credit(body))
    # the identical signed check (same problem id, same data, same predicate) in a new mission
    sign("MISSION", solve_mission("m:again", solve_check("good", "real:m:okay", 3)))
    turn(body, clock, 3)
    def answer(mid):
        e = [e for e in j.replay("mission.observed") if e.payload["mission_id"] == mid][-1]
        o = j.ledger.find(e.payload["receipt"]).payload["result"]["output"]
        return {"receipt": e.payload["receipt"][:16], "state": o.get("state"), "result": o.get("result")}
    out("answer m:okay", answer("m:okay")); out("answer m:again", answer("m:again"))
    out("same answer", answer("m:okay")["result"] == answer("m:again")["result"])
    out("appraisals", {e.payload["mission_id"]: e.payload["verdict"] for e in j.replay("mission.appraised")})
    out("causes", causes(j)); out("contained", contained(j))
    out("credit after the same question is signed again", credit(body))
    out("credited", credited(j))
    out("claims", [(c["mission_id"], c["state"]) for c in corrections.claims(j, clock())])
    out("requalified", [e.payload for e in j.replay("evidence.requalified")])
finally:
    body.close()
