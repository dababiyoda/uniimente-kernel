"""The founder drops a reject and a ratification into the inbox together: one tick ingests both."""
from rc_common import *
from tests.greg_fixtures import drop
body, sign, clock, _, (home, key, body_id) = open_body(tmp(), attach=())
try:
    j = body.journal
    for n in (0, 1, 2):
        sign("MISSION", note_mission(home, f"m:note-{n}", f"done {n}"))
    turn(body, clock, 5)
    [proposal] = [e.payload for e in j.replay("sop.proposed")]
    drop(home, signed(key, body_id, "CRITIQUE", {"target_event_id": closure_of(j, "m:note-0").event_id, "verdict": "reject",
                                                 "evidence_type": "founder_judgment", "text": "this note is wrong"}), "001.json")
    drop(home, signed(key, body_id, "SOP_RATIFY", {"procedure_id": proposal["procedure_id"]}), "002.json")
    r = body.tick(); clock.advance(31)
    out("commands in the tick", [(c.get("kind"), c.get("status") or c.get("accepted") or c.get("error")) for c in r["commands"]] if isinstance(r.get("commands"), list) else r.get("commands"))
    turn(body, clock, 2)
    out("critiques", [(e.payload["verdict"]) for e in j.replay("critique.recorded")])
    out("ratified rows", [e.payload["procedure_id"] for e in j.replay("sop.ratified")])
    out("contained missions", contained(j)["missions"]); out("closed_procedures", sorted(sop.closed_procedures(j)))
finally:
    body.close()
