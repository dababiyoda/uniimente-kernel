"""Claim 1: a detached sensor's adapter runs in the appraiser on base, not on head. Count adapter calls."""
import sys
from lib import *

for how in ("unchanged", "changed", "deleted"):
    tmp = tmpdir("p1")
    child = Child(tmp)
    home, key, body_id, note = note_mission(tmp)
    clock = Clock()
    close_then_stop(home, clock)
    detach(home, key, body_id)
    with Body(home, clock=clock) as body:
        if how == "changed":
            note.write_text("changed after the detach")
        elif how == "deleted":
            note.unlink()
        body.tick()
        ap = facts(body, "mission.appraised")
        show(f"{how} | registry fs.read", body.registry.state["fs.read"])
        show(f"{how} | appraiser children", len(child.requests))
        show(f"{how} | adapters run by appraiser", child.ran)
        show(f"{how} | appraised", [(a["verdict"], a["checks"].get("world_reobserved"), a["findings"], a.get("not_run")) for a in ap])
        for _ in range(3):
            clock.advance(60)
            body.tick()
        show(f"{how} | after 3 more ticks: children, appraised, unavailable", (len(child.requests), len(facts(body, "mission.appraised")), len(facts(body, "mission.appraisal_unavailable"))))
        from greg import autonomy, routing, corrections
        show(f"{how} | autonomy.failures", len(autonomy.failures(body.journal)))
        show(f"{how} | corrections APPRAISAL_REFUTED", len([c for c in corrections.Index(body.journal).causes(body.clock()) if c["class"] == "APPRAISAL_REFUTED"]))
        show(f"{how} | routing", {k: v for k, v in routing.track_record(body.journal).items()})
