"""GREG_CHROMIUM names an executable file the operating system cannot start (its interpreter is missing). Prints
what the mission records. usage: python unstartable_probe.py <scratch dir>"""
import json, sys
from pathlib import Path
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, signed

root = Path(sys.argv[1]); root.mkdir(parents=True)
check = {"check_id": "c", "description": "d", "sensor": {"capability": "browser.render",
         "params": {"url": "http://127.0.0.1:9/x"}, "target": "web:127.0.0.1"},
         "predicate": {"op": "contains", "field": "text", "value": "x"}}
home, key, body_id, _ = make_body(root)
drop(home, signed(key, body_id, "MISSION", mission("m:unstartable", checks=[check], strategies=[],
                                                   capabilities=["browser.render"], targets=("web:127.0.0.1",),
                                                   ceiling="read_only")))
clock = Clock()
with Body(home, clock=clock) as body:
    body.tick()
    observed = [(e.payload.get("passed"), e.payload.get("detail", "")[:160]) for e in body.journal.replay("mission.observed")]
    receipts = [r.payload["result"].get("observed_outcome", "")[:120] for r in body.ledger.by_type("receipt")]
print(json.dumps({"observed": observed, "receipts": receipts}))
