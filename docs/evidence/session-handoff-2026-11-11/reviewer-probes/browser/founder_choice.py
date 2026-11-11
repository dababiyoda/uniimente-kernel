"""GREG_CHROMIUM variants through the real browser_render on a loopback page; logs every binary actually run."""
import functools, http.server, json, os, stat, subprocess, sys, tempfile, threading
from pathlib import Path
sys.path.insert(0, os.getcwd())
from greg import capabilities
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, browser_render

HS = "/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell"
tmp = Path(tempfile.mkdtemp(prefix="adv-br-choice-"))
(tmp / "www").mkdir(); (tmp / "www" / "index.html").write_text("<html><title>t</title><body>hello choice</body></html>")
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(tmp / "www")))
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/index.html"

ran = []
real_run = subprocess.run
def logging_run(argv, *a, **k):
    ran.append(argv[0])
    return real_run(argv, *a, **k)
capabilities.subprocess.run = logging_run

broken = tmp / "broken-chrome"; broken.write_text("#!/bin/sh\necho broken >&2\nexit 7\n"); broken.chmod(0o755)
notexec = tmp / "not-executable"; notexec.write_text("#!/bin/sh\nexit 0\n"); notexec.chmod(0o644)
(tmp / "adir").mkdir()
(tmp / "rel").mkdir(); os.symlink(HS, tmp / "rel" / "my-chrome")
variants = [("working absolute (headless shell)", HS, None),
            ("broken executable", str(broken), None),
            ("a directory", str(tmp / "adir"), None),
            ("not executable file", str(notexec), None),
            ("missing path (typo)", str(tmp / "nope" / "chrome"), None),
            ("empty string", "", None),
            ("unexpanded ~", "~/chrome", None),
            ("relative path that exists from cwd", "rel/my-chrome", str(tmp)),
            ("relative path that does not exist from cwd", "rel/my-chrome", "/"),
            ("trailing newline on a working path", HS + "\n", None)]
manifest, _ = BUILTINS["browser.render"]
rows = []
for name, value, cwd in variants:
    capabilities._render_judged.clear(); ran.clear()
    os.environ["GREG_CHROMIUM"] = value
    here = os.getcwd()
    if cwd: os.chdir(cwd)
    try:
        cands = capabilities.chrome_candidates()
        try:
            out = browser_render({"url": url}, InvocationContext(workspace=tmp, read_roots=(), secrets=None, manifest=manifest))
            result = f"RENDERED by {out['browser']}"
        except CapabilityError as exc:
            result = "REFUSED: " + str(exc)[:150]
        except Exception as exc:
            result = f"RAISED {type(exc).__name__}: {exc}"[:200]
    finally:
        os.chdir(here)
    rows.append({"variant": name, "GREG_CHROMIUM": value, "candidates": [c if c == value else Path(c).name + " (NOT the chosen)" for c in cands],
                 "binaries_run": [b if b == value else Path(b).name + " (NOT the chosen)" for b in ran], "result": result})
print(json.dumps(rows, indent=1))
