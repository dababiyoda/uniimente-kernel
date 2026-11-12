"""The browser is gone between the office's precheck and the render (simulated: the precheck is told a browser is
installed, and none is). Prints what the mission records. usage: python vanished_probe.py <scratch dir>"""
import json, sys
from pathlib import Path
import greg.capabilities as c
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, signed

c.PLAYWRIGHT_BROWSERS, c.HEADLESS_SHELL_CANDIDATES, c.CHROME_CANDIDATES = "/nonexistent-pw", ("/nonexistent/s",), ("/nonexistent/c",)
c.AVAILABLE_AT_CALL_TIME["browser.render"] = lambda: (True, "available")      # the precheck saw a browser
root = Path(sys.argv[1]); root.mkdir(parents=True)
check = {"check_id": "c", "description": "d", "sensor": {"capability": "browser.render",
         "params": {"url": "http://127.0.0.1:9/x"}, "target": "web:127.0.0.1"},
         "predicate": {"op": "contains", "field": "text", "value": "x"}}
home, key, body_id, _ = make_body(root)
drop(home, signed(key, body_id, "MISSION", mission("m:vanished", checks=[check], strategies=[], capabilities=["browser.render"],
                                                   targets=("web:127.0.0.1",), ceiling="read_only")))
clock = Clock()
with Body(home, clock=clock) as body:
    for _ in range(3):
        print(str(body.tick())[:600])
        clock.advance(4000)
    observed = [(e.payload.get("passed"), e.payload.get("detail", "")[:160]) for e in body.journal.replay("mission.observed")]
    kinds = sorted({getattr(e, "event_type", None) or getattr(e, "type", "?") for e in body.journal.replay("mission.")})
    actions = [(e.payload.get("status"), str(e.payload.get("reasons", e.payload.get("detail", "")))[:200]) for e in body.journal.replay("mission.action")]
    receipts = [r.payload["result"].get("observed_outcome", "")[:120] for r in body.ledger.by_type("receipt")]
print(json.dumps({"observed": observed, "mission_kinds": kinds, "actions": actions, "receipts": receipts,
                  "state": body.engine.book.missions["m:vanished"].status if "m:vanished" in body.engine.book.missions else None}))
