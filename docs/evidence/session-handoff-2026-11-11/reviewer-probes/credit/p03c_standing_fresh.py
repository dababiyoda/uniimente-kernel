"""A standing mission whose hold the founder rejects before its next cadence read."""
from rc_common import *
body, sign, clock, _, _k = open_body(tmp())
try:
    j, mid = body.journal, "m:stand"
    note = workspace(body.layout.home, mid) / "n.txt"
    spec = solve_mission(mid, note_check("note", note, "done"), solve_check("good", "real:stand", 3),
                         strategies=[write_strategy("w", "n.txt", "done", ["note"])],
                         capabilities=("fs.read", "fs.write", "cognition.solve"),
                         targets=("fs:*", "workspace:*", "cognition:*"), ceiling="internal_write")
    spec["closure"] = {"kind": "infinite", "cadence_seconds": 600}
    sign("MISSION", spec)
    for _ in range(6):
        body.tick(); clock.advance(5)
        if j.replay("mission.held"): break
    body.tick()
    n = lambda: len([e for e in j.replay("mission.observed") if e.payload["check_id"] == "good"])
    [held] = j.replay("mission.held")
    out("before", {"readings of good": n(), "credit": credit(body), "appraisals": [e.payload["verdict"] for e in j.replay("mission.appraised")]})
    reject(sign, held.event_id, "this standing answer is wrong")
    body.tick(); clock.advance(5); body.tick()
    out("after the reject, before the next cadence read", {"readings of good": n(), "causes": causes(j), "credit": credit(body), "credited": credited(j)})
    clock.advance(601); body.tick(); body.tick()
    out("after the mission's own next cadence read", {"readings of good": n(), "credit": credit(body), "credited": credited(j), "contained": contained(j),
        "requalified": len(j.replay("evidence.requalified")), "claim": [(c["kind"], c["state"]) for c in corrections.claims(j, clock())]})
    out("settled rows", settled_records(j))
finally:
    body.close()
