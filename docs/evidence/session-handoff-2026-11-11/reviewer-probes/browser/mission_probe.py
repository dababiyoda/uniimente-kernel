"""A founder-signed mission whose success check is a browser.render of a loopback page, driven by Body.tick.
Usage: python mission_probe.py <tmpdir> [ticks] ; run from a worktree root. Prints what the ledger retained."""
import functools, http.server, json, os, sys, threading, time
from pathlib import Path
sys.path.insert(0, os.getcwd())
from greg.body import Body
from greg import capabilities
from tests.greg_fixtures import Clock, drop, make_body, mission, signed, workspace, write_strategy

tmp = Path(sys.argv[1]); tmp.mkdir(parents=True, exist_ok=True)
ticks = int(sys.argv[2]) if len(sys.argv) > 2 else 6
home, key, body_id, _ = make_body(tmp)
mid = "m:browser-probe"
ws = workspace(home, mid); ws.mkdir(parents=True, exist_ok=True)

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ws)))
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{server.server_address[1]}/index.html"
check = {"check_id": "c", "description": "the page shows the text",
         "sensor": {"capability": "browser.render", "params": {"url": url}, "target": "web:127.0.0.1"},
         "predicate": {"op": "contains", "field": "text", "value": "hello-from-probe"}}
spec = mission(mid, checks=[check],
               strategies=[write_strategy("w", "index.html", "<html><body><p>hello-from-probe</p></body></html>", ["c"])],
               capabilities=["browser.render", "fs.write"], targets=("web:127.0.0.1", "workspace:*"))
drop(home, signed(key, body_id, "MISSION", spec))
clock = Clock()
m = capabilities.BUILTINS["browser.render"][0]
print(json.dumps({"manifest_binaries": list(m.binaries), "manifest_digest": m.digest()[:23],
                  "GREG_CHROMIUM": os.environ.get("GREG_CHROMIUM")}))
with Body(home, clock=clock) as body:
    for i in range(ticks):
        t = time.monotonic()
        body.tick()
        clock.advance(float(os.environ.get("PROBE_ADVANCE", "1")))
        took = round(time.monotonic() - t, 1)
        done = [e.payload for e in body.journal.replay("mission.achieved") if e.payload.get("mission_id") == mid]
        appraised = [e.payload for e in body.journal.replay("mission.appraised") if e.payload.get("mission_id") == mid]
        print(json.dumps({"tick": i, "seconds": took, "achieved": bool(done),
                          "appraised": [a["verdict"] for a in appraised]}), flush=True)
        if appraised:
            break
    def facts(kind):
        return [e.payload for e in body.journal.replay(kind) if e.payload.get("mission_id") == mid]
    obs = facts("mission.observed")
    out = {"observations": [{k: o.get(k) for k in ("check_id", "passed", "status", "detail", "why") if k in o} for o in obs],
           "actions": [{k: a.get(k) for k in ("action_id", "status", "why")} for a in facts("mission.action")],
           "achieved": bool(facts("mission.achieved")),
           "appraised": [{"verdict": a["verdict"], "findings": a.get("findings")} for a in facts("mission.appraised")],
           "open_requests": [{"kind": r["kind"], "why": r.get("why_now", "")[:200]} for r in body.engine.book.open_requests()],
           "blocked": [{k: str(v)[:200] for k, v in e.items() if k in ("why", "reason", "state", "kind")} for e in facts("mission.blocked")],
           "receipts": len(body.ledger.by_type("receipt")), "dispatches": len(body.ledger.by_type("grant_dispatch")),
           "ledger_records": body.ledger.head if isinstance(body.ledger.head, int) else None}
    types = {}
    for r in body.ledger.by_type("event"):
        types[r.payload.get("type")] = types.get(r.payload.get("type"), 0) + 1
    out["event_counts"] = {k: v for k, v in sorted(types.items()) if "mission" in k or "capab" in k or "decision" in k}
    rec = [r.payload for r in body.ledger.by_type("receipt")]
    out["receipt_results"] = [{"status": (p.get("result") or {}).get("status"), "error": str((p.get("result") or {}).get("error"))[:160],
                               "browser": ((p.get("result") or {}).get("output") or {}).get("browser") if isinstance((p.get("result") or {}).get("output"), dict) else None}
                              for p in rec]
    print(json.dumps(out, indent=1, default=str))
server.shutdown()
