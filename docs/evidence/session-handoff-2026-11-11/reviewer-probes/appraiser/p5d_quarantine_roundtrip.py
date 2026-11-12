"""Claim 3 class: after a failure closure, the sensor goes QUARANTINED (recorded as Genesis records it), then
VERIFIED (recovered), then the founder attaches it. Also: a body restart in the middle of the round trip."""
from p5_unmet_roundtrip import build, turns, state, MID2
from lib import *

tmp = tmpdir("p5d")
body, key, body_id, clock, note = build(tmp)
home = body.layout.home
try:
    turns(body, clock, 4)
    show("setup | unmet, appraised, state", (len(body.journal.replay("mission.unmet")), [e.payload["verdict"] for e in body.journal.replay("mission.appraised")], state(body)))
    for st in ("QUARANTINED", "VERIFIED"):
        body.journal.record("capability.state", {"capability_id": "fs.read", "state": st, "why": "probe", "by": "self-repair (probe)"}, key=["fs.read", "probe", st])
        body._apply_capability_states()
        show(f"after {st}", (turns(body, clock, 3, 3600), state(body), body.registry.state["fs.read"]))
finally:
    body.close()
with Body(home, clock=clock) as body:      # restart in the middle
    show("after restart (sensor VERIFIED, not attached)", (turns(body, clock, 2, 3600), state(body), body.registry.state["fs.read"]))
    body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "fs.read"}))
    show("after founder ATTACH", (turns(body, clock, 4, 3600), state(body), len(body.journal.replay("mission.unmet")), [e.payload["verdict"] for e in body.journal.replay("mission.appraised")]))
