"""On a confined body the render always runs with --no-sandbox inside GREG's namespace. The check that chooses the
binary runs outside it under the unconfined rule. Stand-in: a browser that renders only with --no-sandbox (the
behaviour of Chrome where an ordinary user may not create its sandbox). _render_behind_relay is replaced by a
recorder that runs the argv directly (no bubblewrap here), so only the choice logic is exercised."""
import json, os, stat, subprocess, sys, tempfile, threading
from pathlib import Path
sys.path.insert(0, os.getcwd())
from greg import capabilities
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, browser_render

tmp = Path(tempfile.mkdtemp(prefix="adv-br-rule-"))
PAGE = "<html><head><title>t</title></head><body><p>greg-renders-42</p><p>hello</p></body></html>"
b = tmp / "chrome-needs-no-sandbox"
b.write_text("#!/bin/sh\ncase \" $* \" in *' --no-sandbox '*) echo '%s';; *) echo 'No usable sandbox!' >&2; exit 1;; esac\n" % PAGE)
b.chmod(0o755)
os.environ["GREG_CHROMIUM"] = str(b)
confined = []
def recorder(argv, relay, host, port, loopback, profile, env):
    confined.append("--no-sandbox" in argv)
    return subprocess.run(argv, capture_output=True, timeout=10, env=env)
capabilities._render_behind_relay = recorder
has_rule = hasattr(capabilities, "_sandboxes_itself")
if has_rule:
    capabilities._sandboxes_itself = lambda: False if os.environ.get("AS_ROOT") else True
else:                       # pr196 computes the rule inline from geteuid
    os.geteuid = (lambda: 0) if os.environ.get("AS_ROOT") else (lambda: 1000)
    capabilities.os.geteuid = os.geteuid
class Relay: journal = connect = proxy = None
manifest, _ = BUILTINS["browser.render"]
try:
    out = browser_render({"url": "https://example.invalid/"}, InvocationContext(workspace=tmp, read_roots=(), secrets=None, manifest=manifest, egress=Relay()))
    result = f"rendered inside the namespace route (os_sandboxed={out['os_sandboxed']})"
except CapabilityError as exc:
    result = "REFUSED: " + str(exc)[:160]
print(json.dumps({"tree": subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip(),
                  "ordinary_user": not os.environ.get("AS_ROOT"), "confined_render_reached_with_no_sandbox": confined, "result": result}))
