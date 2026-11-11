"""A running body (import succeeded) when a build directory with a non-decimal digit appears in the listing.
Every browser.render then raises ValueError inside the adapter. What does the mission path do with it?"""
import functools, glob, http.server, json, os, sys, threading
from pathlib import Path
sys.path.insert(0, os.getcwd())
from greg import capabilities
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, signed, workspace, write_strategy
tmp = Path(sys.argv[1]); tmp.mkdir(parents=True, exist_ok=True)
home, key, body_id, _ = make_body(tmp)
mid = "m:odd"; ws = workspace(home, mid); ws.mkdir(parents=True, exist_ok=True)
check = {"check_id": "c", "description": "page", "sensor": {"capability": "browser.render", "params": {"url": "http://127.0.0.1:9/x"}, "target": "web:127.0.0.1"},
         "predicate": {"op": "contains", "field": "text", "value": "never"}}
spec = mission(mid, checks=[check], strategies=[write_strategy("w", "x.txt", "x", ["c"])],
               capabilities=["browser.render", "fs.write"], targets=("web:127.0.0.1", "workspace:*"))
drop(home, signed(key, body_id, "MISSION", spec))
real = glob.glob
ODD = "/opt/pw-browsers/chromium_headless_shell-1243²/chrome-headless-shell-linux64/chrome-headless-shell"
capabilities.glob.glob = lambda p, *a, **k: real(p, *a, **k) + ([ODD] if "chromium_headless_shell-*" in p else [])
clock = Clock(); rows = []
with Body(home, clock=clock) as body:
    for i in range(int(sys.argv[2])):
        try:
            body.tick(); r = "ok"
        except Exception as exc:
            r = f"tick raised {type(exc).__name__}: {str(exc)[:80]}"
        clock.advance(float(sys.argv[3]))
        rows.append(r)
    kinds = {}
    for rec in body.ledger.by_type("event"):
        t = rec.payload.get("type", ""); kinds[t] = kinds.get(t, 0) + 1
    print(json.dumps({"ticks": rows, "dispatches": len(body.ledger.by_type("grant_dispatch")), "receipts": len(body.ledger.by_type("receipt")),
                      "observed": [o["detail"][:100] for o in (e.payload for e in body.journal.replay("mission.observed"))],
                      "events": {k: v for k, v in sorted(kinds.items()) if "mission" in k or "reconcil" in k or "crash" in k or "decision" in k},
                      "open_requests": [(r["kind"], r.get("why_now", "")[:120]) for r in body.engine.book.open_requests()]}, indent=1))
