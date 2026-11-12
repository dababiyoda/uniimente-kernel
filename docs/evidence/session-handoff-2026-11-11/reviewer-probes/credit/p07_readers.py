"""Readers the change left alone: what a founder-rejected mission still earns through them."""
from rc_common import *
from greg import routing, autonomy, compounding
body, sign, clock, _, (home, key, body_id) = open_body(tmp(), attach=())
try:
    j = body.journal
    def view():
        rec = routing.track_record(j).get("fs.write")
        rep = autonomy.report(j)
        rows = rep.get("tuples") or rep.get("rows") or rep
        mine = [r for r in (rows if isinstance(rows, list) else []) if (r.get("tuple") or {}).get("capability") == "fs.write"]
        tr = sop.trend(j)
        return {"fs.write track_record": rec, "fs.write reliability": round(routing.reliability(rec), 4),
                "autonomy fs.write": [{k: r.get(k) for k in ("runs", "verified", "refuted", "verified_since_last_failure", "level", "earned_level", "wilson_lower")} for r in mine],
                "closed_procedures": sorted(sop.closed_procedures(j)), "ratified": sorted(sop.ratified(j)),
                "sop.trend keys": sorted(tr)[:6] if isinstance(tr, dict) else str(type(tr))}
    for n in range(3):
        sign("MISSION", note_mission(home, f"m:note-{n}", f"done {n}"))
    turn(body, clock, 5)
    out("before", view())
    [proposal] = [e.payload for e in j.replay("sop.proposed")]
    r = sign("SOP_RATIFY", {"procedure_id": proposal["procedure_id"]})
    out("ratified before any rejection", r.get("state"))
    for n in range(3):
        reject(sign, closure_of(j, f"m:note-{n}").event_id, f"note {n} is wrong")
    turn(body, clock, 2)
    out("after the founder rejects ALL THREE runs", view())
    out("contained", contained(j))
    rec = sop.ratified(j)[proposal["procedure_id"]]["record"]
    try:
        slots = {name: ("x" if spec["type"] == "string" else 1) for name, spec in rec["workflow"]["slots"].items()}
        m = sop.instantiate(rec, slots, mission_id="m:from-sop")
        out("the ratified procedure still instantiates a mission", {"mission_id": m["mission_id"], "strategies": [s["action_id"] for s in m["strategies"]],
                                                                      "provenance": m.get("provenance")})
    except Exception as exc:
        out("instantiate", f"{type(exc).__name__}: {exc}")
    out("trend", json.loads(json.dumps(sop.trend(j), default=str))[proposal["procedure_id"]] if isinstance(sop.trend(j), dict) and proposal["procedure_id"] in sop.trend(j) else sop.trend(j))
    try:
        out("compounding.retained_reuse", compounding.retained_reuse(j))
    except Exception as exc:
        out("compounding.retained_reuse", f"{type(exc).__name__}: {exc}")
finally:
    body.close()
