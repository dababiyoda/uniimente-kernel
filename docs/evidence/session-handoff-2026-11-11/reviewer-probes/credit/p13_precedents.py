"""What the memory.precedents sensor still returns about a mission the founder rejected."""
from rc_common import *
from greg.capabilities import BUILTINS, InvocationContext
from greg.precedents import precedents
body, sign, clock, data, (home, key, body_id) = open_body(tmp(), attach=())
try:
    j = body.journal
    for n in (0, 1):
        sign("MISSION", note_mission(home, f"m:note-{n}", f"done {n}"))
    turn(body, clock, 4)
    manifest, _ = BUILTINS["memory.precedents"]
    ctx = InvocationContext(workspace=workspace(home, "m:ask"), read_roots=(data,), secrets=body.secrets,
                            manifest=manifest, journal=j, target="memory:fs.write")
    def view():
        o = precedents({"capability": "fs.write"}, ctx)
        return {"locally_appraised_mission_count": o["locally_appraised_mission_count"], "action_evidence.count": o["action_evidence"]["count"],
                "by_validation_and_result": o["action_evidence"]["by_validation_and_result"], "recent shown": o["action_evidence"]["shown"]}
    out("before", view())
    for n in (0, 1):
        reject(sign, closure_of(j, f"m:note-{n}").event_id, "wrong")
    turn(body, clock, 1)
    out("after the founder rejects both", view())
finally:
    body.close()
