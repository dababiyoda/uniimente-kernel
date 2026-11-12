"""Records with the right kind and no signature: does the credit projection follow them?"""
from rc_common import *
body, sign, clock, _, _k = open_body(tmp())
try:
    j = body.journal
    for mid, seed in (("m:aaa", 3), ("m:bbb", 4), ("m:ccc", 5)):
        sign("MISSION", solve_mission(mid, solve_check("good", f"real:{mid}", seed)))
    turn(body, clock)
    out("credit0", credit(body))
    accepted0 = len(j.replay("command.accepted"))
    # 1. an unsigned critique.recorded row: no command.accepted behind it, no command_digest
    j.record("critique.recorded", {"critique_id": "crit-forged", "target_event_id": closure_of(j, "m:aaa").event_id,
                                   "verdict": "reject", "text": "not the founder"}, key="crit-forged")
    turn(body, clock, 2)
    out("1 unsigned critique row", {"causes": causes(j), "credit": credit(body), "credited": credited(j),
                                    "new command.accepted": len(j.replay("command.accepted")) - accepted0})
    # 2. an evidence.correction row written directly: no cause, no critique, no reading behind it
    rb = closure_of(j, "m:bbb").payload["evidence"]
    j.record("evidence.correction", {"cause_id": "cause-forged", "class": "REPLICATION_FAILED", "impugns_measurement": True,
                                     "root": {"mission_id": "m:bbb"}, "affected": {"receipts": rb, "claims": [{"mission_id": "m:bbb", "claim": "x", "kind": "achieved"}],
                                     "path": [], "actions": [], "decisions": [], "outcomes": [], "procedures": [], "unaffected_claims": 0}},
             key=["cause-forged", "correction"])
    turn(body, clock, 2)
    out("2 bare evidence.correction row", {"credit": credit(body), "credited": credited(j), "contained": contained(j),
                                           "invalidated rows": len(j.replay("evidence.invalidated"))})
    # 3. a real founder rejection of m:c, then an evidence.requalified row written directly for its cause
    reject(sign, closure_of(j, "m:ccc").event_id, "wrong")
    turn(body, clock, 2)
    out("3a after a real signed reject of m:c", {"credit": credit(body), "credited": credited(j)})
    cid = [e.payload["cause_id"] for e in j.replay("evidence.invalidated") if e.payload["root"]["mission_id"] == "m:ccc"][0]
    j.record("evidence.requalified", {"cause_id": cid, "root": "x", "by": {"event_id": "nothing"}, "restores_permission": False},
             key=[cid, "requalified"])
    turn(body, clock, 2)
    out("3b after a bare evidence.requalified row for the founder's rejection", {"credit": credit(body), "credited": credited(j),
        "claims": [(c["mission_id"], c["state"]) for c in corrections.claims(j, clock())]})
finally:
    body.close()
