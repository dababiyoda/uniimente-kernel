"""Founder question 3 (a proposal that includes a mission rejected later) and question 4 (routing, earned autonomy)."""
from rc_common import *
from greg import routing, autonomy
body, sign, clock, _, (home, key, body_id) = open_body(tmp(), attach=())
try:
    j = body.journal
    out("fs.write reliability with no run", round(routing.reliability(routing.track_record(j).get("fs.write")), 4))
    for n in range(3):
        sign("MISSION", note_mission(home, f"m:note-{n}", f"done {n}"))
    turn(body, clock, 5)
    [proposal] = [e.payload for e in j.replay("sop.proposed")]
    def auto():
        rep = autonomy.report(j)
        rows = next((v for v in rep.values() if isinstance(v, list) and v and isinstance(v[0], dict) and "tuple" in v[0]), [])
        return [{k: v for k, v in r.items() if k != "outcomes"} for r in rows if r["tuple"]["capability"] == "fs.write"]
    out("Q4 before", {"track": routing.track_record(j).get("fs.write"), "reliability": round(routing.reliability(routing.track_record(j).get("fs.write")), 4), "autonomy": auto()})
    for n in range(3):
        reject(sign, closure_of(j, f"m:note-{n}").event_id, f"note {n} is wrong")
    turn(body, clock, 2)
    out("Q4 after the founder rejects every run", {"track": routing.track_record(j).get("fs.write"), "reliability": round(routing.reliability(routing.track_record(j).get("fs.write")), 4), "autonomy": auto(),
                                                   "regressed": len(j.replay("autonomy.regressed"))})
    def try_ratify():
        try:
            return sign("SOP_RATIFY", {"procedure_id": proposal["procedure_id"]}) and "RATIFIED"
        except Exception as exc:
            return f"refused: {exc}"
    out("Q3 ratify the proposal that rests on rejected runs", try_ratify())
    for n in range(3, 7):
        sign("MISSION", note_mission(home, f"m:note-{n}", f"done {n}"))
    turn(body, clock, 6)
    out("Q3 after four clean runs of the same procedure", {"closed_procedures": sorted(sop.closed_procedures(j)),
        "proposals": [(e.payload["procedure_id"], e.payload["missions"]) for e in j.replay("sop.proposed")], "ratify": try_ratify()})
finally:
    body.close()
