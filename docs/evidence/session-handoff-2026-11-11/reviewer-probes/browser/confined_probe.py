"""A body configured for confined egress (ctx.egress is a relay): which browser processes does browser.render start,
and outside which namespace? No bubblewrap exists in this container, so the confined route must refuse and, by
_render_behind_relay's own rule ('without namespaces nothing runs'), start nothing."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, os.getcwd())
from greg import capabilities
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, browser_render

ran = []
real_run = subprocess.run
def logging_run(argv, *a, **k):
    ran.append({"argv0": Path(argv[0]).name, "no_sandbox": "--no-sandbox" in argv, "bwrap": "bwrap" in argv[0],
                "page": argv[-1][:24]})
    return real_run(argv, *a, **k)
capabilities.subprocess.run = logging_run

class FakeRelay:                       # stands for the body's relay; never reached without bubblewrap
    journal = None; connect = None; proxy = None
manifest, _ = BUILTINS["browser.render"]
tmp = Path(tempfile.mkdtemp(prefix="adv-br-conf-"))
ctx = InvocationContext(workspace=tmp, read_roots=(), secrets=None, manifest=manifest, egress=FakeRelay())
try:
    browser_render({"url": "https://example.invalid/"}, ctx)
    result = "rendered"
except CapabilityError as exc:
    result = "CapabilityError: " + str(exc)[:140]
print(json.dumps({"tree": subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip(),
                  "result": result, "browser_processes_started_before_the_refusal": ran}, indent=1))
