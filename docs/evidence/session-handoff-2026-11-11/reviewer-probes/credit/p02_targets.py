"""Which signed rejections have a credit effect? Reject, in turn: an uncited earlier reading of the claim, the
appraisal event, the cognition.settled event, then (control) the cited reading."""
from rc_common import *
body, sign, clock, _, _k = open_body(tmp())
try:
    j, mid = body.journal, "m:two"
    note = workspace(body.layout.home, mid) / "n.txt"
    sign("MISSION", solve_mission(mid, note_check("note", note, "done"), solve_check("good1", "real:two:1", 3),
                                  solve_check("good2", "real:two:2", 4),
                                  strategies=[write_strategy("w", "n.txt", "done", ["note"])],
                                  capabilities=("fs.read", "fs.write", "cognition.solve"),
                                  targets=("fs:*", "workspace:*", "cognition:*"), ceiling="internal_write"))
    turn(body, clock, 4)
    out("credited0", credited(j))
    readings = [e for e in j.replay("mission.observed") if e.payload["check_id"] == "good1"]
    cited = closure_of(j, mid).payload["evidence"]
    out("good1 readings cited?", [e.payload["receipt"] in cited for e in readings])
    def step(name, event_id):
        r = reject(sign, event_id, f"founder rejects: {name}")
        turn(body, clock, 2)
        out(name, {"critique": r.get("critique_id"), "target_type": r.get("target_type"), "causes": causes(j),
                   "contained": contained(j), "credit": credit(body), "credited": credited(j)})
    step("A reject the EARLIER, uncited reading of good1", readings[0].event_id)
    [appraised] = [e for e in j.replay("mission.appraised") if e.payload["mission_id"] == mid]
    step("B reject the mission.appraised event", appraised.event_id)
    settled = [e for e in j.replay("cognition.settled") if e.payload["check_id"] == "good1"]
    step("C reject the cognition.settled event of good1", settled[-1].event_id)
    [registered] = [e for e in j.replay("mission.registered") if e.payload["mission_id"] == mid]
    step("D reject the mission.registered event", registered.event_id)
    step("E (control) reject the cited reading of good1", readings[-1].event_id)
finally:
    body.close()
