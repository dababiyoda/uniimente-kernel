"""A standing mission: the founder rejects its hold; its own next cadence read delivers the same answer again."""
from rc_common import *
body, sign, clock, _, _k = open_body(tmp())
try:
    j, mid = body.journal, "m:stand"
    note = workspace(body.layout.home, mid) / "n.txt"
    spec = solve_mission(mid, note_check("note", note, "done"), solve_check("good", "real:stand", 3),
                         strategies=[write_strategy("w", "n.txt", "done", ["note"])],
                         capabilities=("fs.read", "fs.write", "cognition.solve"),
                         targets=("fs:*", "workspace:*", "cognition:*"), ceiling="internal_write")
    spec["closure"] = {"kind": "infinite", "cadence_seconds": 60}
    sign("MISSION", spec)
    turn(body, clock, 4)
    held = [e for e in j.replay("mission.held")]
    out("held", len(held)); out("appraisals", [(e.payload["verdict"], bool(e.payload.get("closure_event"))) for e in j.replay("mission.appraised")])
    out("credit before", credit(body)); out("readings", len([e for e in j.replay("mission.observed") if e.payload["check_id"] == "good"]))
    reject(sign, held[-1].event_id, "this standing answer is wrong")
    body.tick()                       # the tick that records the correction (clock not advanced past the cadence)
    out("causes", causes(j)); out("contained", contained(j)); out("credit right after reject", credit(body))
    n = len([e for e in j.replay("mission.observed") if e.payload["check_id"] == "good"])
    for i in range(4):
        clock.advance(61); body.tick()
        m = len([e for e in j.replay("mission.observed") if e.payload["check_id"] == "good"])
        out(f"after cadence tick {i+1}", {"new readings of good": m - n, "credit": credit(body), "contained": contained(j),
                                         "claims": [(c["mission_id"], c["kind"], c["state"]) for c in corrections.claims(j, clock())]})
    out("settled_records", settled_records(j))
finally:
    body.close()
