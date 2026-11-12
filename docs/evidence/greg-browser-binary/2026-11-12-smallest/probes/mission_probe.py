"""One founder-signed mission whose only check is browser.render, run by a real Body, appraised by the separate
appraiser process the Body starts. Prints one JSON line: per tick, the mission's state; then the closure and the
appraisal verdicts and findings, and which browser the receipt names.

usage: python mission_probe.py <scratch dir>     (PYTHONPATH names the tree under test; GREG_CHROMIUM as the caller
sets it reaches the body only: greg/body.py starts the appraiser without it)
"""
import functools
import http.server
import json
import sys
import threading
import time
from pathlib import Path

from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, signed

PAGE = ("<html><head><title>probe</title></head><body><p id=x>static text</p>"
        "<script>document.getElementById('x').textContent = 'rendered by javascript'</script></body></html>")

root = Path(sys.argv[1])
site = root / "site"
site.mkdir(parents=True)
(site / "index.html").write_text(PAGE)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(site)))
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{server.server_address[1]}/index.html"
check = {"check_id": "rendered", "description": "the page shows its JavaScript-rendered text",
         "sensor": {"capability": "browser.render", "params": {"url": url}, "target": "web:127.0.0.1"},
         "predicate": {"op": "contains", "field": "text", "value": "rendered by javascript"}}
(root / "body").mkdir()
home, key, body_id, _ = make_body(root / "body")
drop(home, signed(key, body_id, "MISSION", mission("m:probe", checks=[check], strategies=[],
                                                   capabilities=["browser.render"], targets=("web:127.0.0.1",),
                                                   ceiling="read_only")))
clock, ticks = Clock(), []
started = time.monotonic()
with Body(home, clock=clock) as body:
    for tick in range(1, 5):
        t0 = time.monotonic()
        body.tick()
        achieved = [e for e in body.journal.replay("mission.achieved") if e.payload.get("mission_id") == "m:probe"]
        ticks.append({"tick": tick, "achieved_events": len(achieved), "seconds": round(time.monotonic() - t0, 2)})
        if [e for e in body.journal.replay("mission.appraised") if e.payload.get("mission_id") == "m:probe"]:
            break
        clock.advance(4000)
    observed = [e.payload for e in body.journal.replay("mission.observed") if e.payload.get("mission_id") == "m:probe"]
    appraised = [e.payload for e in body.journal.replay("mission.appraised")
                 if e.payload.get("mission_id") == "m:probe"]
    receipts = [r.payload["result"].get("output") for r in body.ledger.by_type("receipt")]
server.shutdown()
browsers = sorted({r.get("browser") for r in receipts if isinstance(r, dict) and r.get("url") == url})
print(json.dumps({"ticks": ticks, "observed": [(o.get("passed"), o.get("detail", "")[:200], o.get("failure_class"))
                                               for o in observed],
                  "appraised": [(a.get("verdict"), a.get("findings")) for a in appraised],
                  "receipt_browser": browsers, "seconds": round(time.monotonic() - started, 2)}))
