"""A running body across a browser upgrade. The manifest of browser.render names the first installed candidate as
it was at import. Simulated install root (a copy of the real headless-shell wrapper, which execs the real binary):
the module constant PLAYWRIGHT_BROWSERS is pointed at it and the manifest's binaries set to installed_chrome(),
which is what import computes when that root is the machine's. Then the build directory is replaced by a newer one
while the body keeps running, as `playwright install` of a newer version followed by its cleanup does."""
import functools, http.server, json, os, shutil, sys, threading, time
from pathlib import Path
sys.path.insert(0, os.getcwd())
from greg import capabilities
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, signed, workspace, write_strategy

REAL = "/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell"
tmp = Path(sys.argv[1]); shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(parents=True)
root = tmp / "pw"
def install(build):
    d = root / f"chromium_headless_shell-{build}" / "chrome-headless-shell-linux64"; d.mkdir(parents=True)
    shutil.copy(REAL, d / "chrome-headless-shell"); return str(d / "chrome-headless-shell")
old = install(1300)
capabilities.PLAYWRIGHT_BROWSERS = str(root)
manifest = capabilities.BUILTINS["browser.render"][0]
manifest.binaries = (capabilities.installed_chrome(),)          # what import names on a machine with this root
digest_at_boot = manifest.digest()
home, key, body_id, _ = make_body(tmp)
mid = "m:upgrade"; ws = workspace(home, mid); ws.mkdir(parents=True, exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ws)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/index.html"
check = {"check_id": "c", "description": "the page shows the text",
         "sensor": {"capability": "browser.render", "params": {"url": url}, "target": "web:127.0.0.1"},
         "predicate": {"op": "contains", "field": "text", "value": "hello-upgrade"}}
spec = mission(mid, checks=[check], strategies=[write_strategy("w", "index.html", "<p>hello-upgrade</p>", ["c"])],
               capabilities=["browser.render", "fs.write"], targets=("web:127.0.0.1", "workspace:*"))
drop(home, signed(key, body_id, "MISSION", spec))
clock = Clock()
rows = []
with Body(home, clock=clock) as body:
    def obs():
        return [(o["passed"], o["detail"][:110]) for o in (e.payload for e in body.journal.replay("mission.observed")) if o["mission_id"] == mid]
    # the upgrade happens before the body's first look: build 1300 is replaced by 1301 while the process runs
    shutil.rmtree(root / "chromium_headless_shell-1300"); new = install(1301)
    for i in range(4):
        body.tick(); clock.advance(4000)
    rows = obs()
    print(json.dumps({"manifest_names": manifest.binaries[0].replace(str(tmp), "<root>"),
                      "installed_now": [c.replace(str(tmp), "<root>") for c in capabilities.chrome_candidates()][:2],
                      "chrome_binary_now": capabilities.chrome_binary().replace(str(tmp), "<root>"),
                      "registry_usable": body.registry.usable("browser.render"),
                      "observations": rows,
                      "achieved": bool([e for e in body.journal.replay("mission.achieved") if e.payload["mission_id"] == mid]),
                      "open_requests": [(r["kind"], r.get("why_now", "")[:160]) for r in body.engine.book.open_requests()],
                      "deficits": [e.payload.get("function") or e.payload.get("capability_id") for e in body.journal.replay("capability.deficit")][:3]},
                     indent=1, default=str))
srv.shutdown()
