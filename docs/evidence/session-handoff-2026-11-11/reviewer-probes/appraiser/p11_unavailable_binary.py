"""An ATTACHED sensor that cannot run (its binary is gone: the adapter raises CapabilityError, as
CapabilityManifest.available() failures do through the office). In-process appraise on a closed, VERIFIED mission."""
from lib import *
import greg.appraisal as appraisal
from greg.capabilities import BUILTINS, CapabilityError

tmp = tmpdir("p11")
home, key, body_id, note = note_mission(tmp)
clock = Clock()
with Body(home, clock=clock) as body:
    for _ in range(4):
        body.tick(); clock.advance(1)
    show("closed", [a["verdict"] for a in facts(body, "mission.appraised")])
    request = body.appraisal_request(MID)
manifest, real = BUILTINS["fs.read"]
calls = []


def gone(params, ctx):
    calls.append(1)
    raise CapabilityError("binary /usr/bin/x not installed or not executable")


BUILTINS["fs.read"] = (manifest, gone)
v = appraisal.appraise(request)
show("unavailable binary | adapter calls, verdict, world_reobserved, findings, not_run", (len(calls), v["verdict"], v["checks"]["world_reobserved"], v["findings"], v.get("not_run")))
