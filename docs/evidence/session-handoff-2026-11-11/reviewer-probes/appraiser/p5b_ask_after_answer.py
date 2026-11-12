"""After a failure closure the founder answers the NO_STRATEGY ask. Does the head re-ask every tick?"""
from p5_unmet_roundtrip import build, turns, state, MID2
from lib import *
import sys
for ans in ("reject", "approve"):
    tmp = tmpdir("p5b")
    body, key, body_id, clock, note = build(tmp)
    try:
        turns(body, clock, 4)
        m = body.engine.book.missions[MID2]
        rid = m.blocker["request_id"]
        body.apply(signed(key, body_id, "DECISION", {"request_id": rid, "answer": ans}))
        res = turns(body, clock, 8, 3600)
        reqs = [(e.payload["kind"], e.payload["request_id"][:10]) for e in body.journal.replay("decision.requested")]
        show(f"{ans} | ticks", res)
        show(f"{ans} | decision.requested", reqs)
        show(f"{ans} | state, unmet, appraised", (state(body), len(body.journal.replay("mission.unmet")), [e.payload["verdict"] for e in body.journal.replay("mission.appraised")]))
        show(f"{ans} | mission.* fact count", len(body.journal.replay("mission.")))
        turns(body, clock, 4, 3600)
        show(f"{ans} | mission.* fact count after 4 more", len(body.journal.replay("mission.")))
    finally:
        body.close()
