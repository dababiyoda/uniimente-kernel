"""Authority: the founder detaches browser.render. Does a browser that passes the check restore anything? Counts
browser processes started, capability.state records, grants and dispatches before and after, across a restart."""
import functools, http.server, json, os, subprocess, sys, threading
from pathlib import Path
sys.path.insert(0, os.getcwd())
from greg import capabilities
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, signed, workspace, write_strategy

ran = []
real_run = subprocess.run
def logging_run(argv, *a, **k):
    if "chrome" in str(argv[0]): ran.append(Path(argv[0]).name)
    return real_run(argv, *a, **k)
capabilities.subprocess.run = logging_run

tmp = Path(sys.argv[1]); tmp.mkdir(parents=True, exist_ok=True)
home, key, body_id, _ = make_body(tmp)
mid = "m:detached"; ws = workspace(home, mid); ws.mkdir(parents=True, exist_ok=True)
(ws / "index.html").write_text("<p>hello-detached</p>")
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ws)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/index.html"
check = {"check_id": "c", "description": "page", "sensor": {"capability": "browser.render", "params": {"url": url}, "target": "web:127.0.0.1"},
         "predicate": {"op": "contains", "field": "text", "value": "hello-detached"}}
spec = mission(mid, checks=[check], strategies=[write_strategy("w", "x.txt", "x", ["c"])],
               capabilities=["browser.render", "fs.write"], targets=("web:127.0.0.1", "workspace:*"))
def snapshot(body):
    return {"state": body.registry.state["browser.render"],
            "state_records": [(e.payload["capability_id"], e.payload["state"]) for e in body.journal.replay("capability.state")],
            "grants": len([r for r in body.ledger.by_type("event") if r.payload.get("type") == "greg.authority.grant_issued"]),
            "dispatches": len(body.ledger.by_type("grant_dispatch")), "receipts": len(body.ledger.by_type("receipt"))}
clock = Clock(); out = {}
with Body(home, clock=clock) as body:
    body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "browser.render"}))
    out["after_founder_detach"] = snapshot(body)
    # the browser passes the check in this very process: the memory now holds "renders"
    out["check_says"] = capabilities.cannot_render(capabilities.installed_chrome()); out["chrome_binary"] = Path(capabilities.chrome_binary()).name
    ran.clear()
    drop(home, signed(key, body_id, "MISSION", spec))
    for _ in range(3):
        body.tick(); clock.advance(4000)
    out["after_three_ticks"] = snapshot(body)
    out["observations"] = [o["detail"][:90] for o in (e.payload for e in body.journal.replay("mission.observed")) if o["mission_id"] == mid]
    out["browser_processes_started_by_the_mission"] = list(ran)
with Body(home, clock=clock) as body:              # restart
    for _ in range(2):
        body.tick(); clock.advance(4000)
    out["after_restart"] = snapshot(body)
    out["browser_processes_started_after_restart"] = list(ran)
    out["achieved"] = bool([e for e in body.journal.replay("mission.achieved") if e.payload["mission_id"] == mid])
print(json.dumps(out, indent=1))
srv.shutdown()
