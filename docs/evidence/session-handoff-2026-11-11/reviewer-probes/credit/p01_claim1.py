from rc_common import *
body, sign, clock, _, _k = open_body(tmp())
try:
    j = body.journal
    for mid, seed in (("m:okay", 3), ("m:other", 4)):
        sign("MISSION", solve_mission(mid, solve_check("good", f"real:{mid}", seed)))
    turn(body, clock)
    out("appraisals", {e.payload["mission_id"]: e.payload["verdict"] for e in j.replay("mission.appraised")})
    out("credit_before", credit(body))
    reject(sign, closure_of(j, "m:okay").event_id, "this answer is wrong for my problem")
    turn(body, clock, 2)
    out("causes", causes(j))
    out("contained", contained(j))
    out("credit_after_reject", credit(body))
    out("credited", credited(j))
    out("settled_records", settled_records(j))
finally:
    body.close()
