"""What does the head record per tick after the founder answers the failure ask?"""
from p5_unmet_roundtrip import build, turns, state, MID2
from lib import *
from collections import Counter
for step in (31, 3600):
    tmp = tmpdir("p5c")
    body, key, body_id, clock, note = build(tmp)
    try:
        turns(body, clock, 4)
        rid = body.engine.book.missions[MID2].blocker["request_id"]
        body.apply(signed(key, body_id, "DECISION", {"request_id": rid, "answer": "reject"}))
        turns(body, clock, 2, step)
        before = Counter(e.type for e in body.journal.replay(""))
        n0 = len(body.ledger.by_type("receipt"))
        turns(body, clock, 10, step)
        after = Counter(e.type for e in body.journal.replay(""))
        show(f"step {step}s | facts added over 10 ticks", {k: after[k] - before[k] for k in after if after[k] != before[k]})
        show(f"step {step}s | receipts added over 10 ticks", len(body.ledger.by_type("receipt")) - n0)
        show(f"step {step}s | state", state(body))
    finally:
        body.close()
