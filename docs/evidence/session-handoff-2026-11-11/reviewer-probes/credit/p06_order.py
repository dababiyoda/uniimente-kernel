"""Order and replay: ratify in the same breath as the rejection; lag; restart; twice; a later accept."""
from rc_common import *
d = tmp()
body, sign, clock, _, (home, key, body_id) = open_body(d, attach=(METHOD,))
try:
    j = body.journal
    for n in (0, 1, 2):
        sign("MISSION", note_mission(home, f"m:note-{n}", f"done {n}"))
    for mid, seed in (("m:okay", 3), ("m:other", 4)):
        sign("MISSION", solve_mission(mid, solve_check("good", f"real:{mid}", seed)))
    turn(body, clock, 5)
    [proposal] = [e.payload for e in j.replay("sop.proposed")]
    out("proposal missions", proposal["missions"]); out("credit0", credit(body))
    # (a) the founder rejects one of the proposal's runs and one cognition answer, and ratifies before any tick
    reject(sign, closure_of(j, "m:note-0").event_id, "this note is wrong")
    reject(sign, closure_of(j, "m:okay").event_id, "this answer is wrong")
    out("(e) credit after the signed reject, before the next tick", credit(body))
    out("(e) closed_procedures before the next tick", sorted(sop.closed_procedures(j)))
    try:
        r = sign("SOP_RATIFY", {"procedure_id": proposal["procedure_id"]})
        out("(a) SOP_RATIFY right after the reject", {"ratified": r.get("state"), "rows": len(j.replay("sop.ratified"))})
    except Exception as exc:
        out("(a) SOP_RATIFY right after the reject", f"refused: {exc}")
    turn(body, clock, 2)
    out("after the tick", {"contained": contained(j), "credit": credit(body), "ratified rows": len(j.replay("sop.ratified")),
                           "closed_procedures": sorted(sop.closed_procedures(j))})
    # (c) the same closure rejected a second time; (d) then accepted
    reject(sign, closure_of(j, "m:okay").event_id, "still wrong")
    turn(body, clock, 2)
    out("(c) rejected twice", {"causes": causes(j), "credit": credit(body), "settled rows": len(j.replay("cognition.settled"))})
    reject(sign, closure_of(j, "m:okay").event_id, "I was mistaken, this is right", verdict="accept")
    turn(body, clock, 2)
    out("(d) a later signed accept", {"credit": credit(body), "requalified": len(j.replay("evidence.requalified")),
                                      "claims": [(c["mission_id"], c["state"]) for c in corrections.claims(j, clock()) if c["mission_id"] == "m:okay"]})
    # (b) restart: the projection and the record counts
    def snap():
        return {"credit": credit(body), "credited": credited(body.journal), "contained": contained(body.journal),
                "counts": {k: len(body.journal.replay(k)) for k in ("cognition.settled", "evidence.invalidated", "evidence.correction", "evidence.requalified", "decision.requested", "sop.proposed")},
                "withheld": sorted(settlement._measure(body.journal)[1].values(), key=str) if hasattr(settlement, "_measure") else None}
    before = snap()
    body.close()
    body = Body(home, clock=clock).open(); body.boot()
    at_boot = snap()
    turn(body, clock, 3)
    after = snap()
    out("(b) identical right after restart", before == at_boot); out("(b) identical after 3 more ticks", before == after)
    if before != after: out("before", before); out("after", after)
finally:
    body.close()
