"""Control for p13, no detach: the failure closure's first appraiser run is killed (one unavailable attempt), the
founder does the work, the mission achieves, the retry then appraises the failure closure. Same class on base?"""
from lib import *
from greg import routing, metrics
from greg.sop import verified_appraisals

tmp = tmpdir("p13b"); child = Child(tmp)
home, key, body_id, data = make_body(tmp)
status = data / "status.txt"; status.write_text("not yet")
drop(home, signed(key, body_id, "MISSION", mission(MID, checks=[note_check("status", status, "shipped")],
     strategies=[write_strategy("nudge", "nudge.txt", "nudged", ["status"])], capabilities=["fs.read", "fs.write"])))
clock = Clock()
close_then_stop(home, clock, closure="mission.unmet", ticks=12, step=600.0)
with Body(home, clock=clock) as body:
    child.fail_next = 1
    body.tick(); clock.advance(3600)
    show("after the killed run | appraised, unavailable attempts", ([a["verdict"] for a in facts(body, "mission.appraised")], len(facts(body, "mission.appraisal_unavailable"))))
    status.write_text("shipped")
    for _ in range(3):
        body.tick(); clock.advance(3600)
    show("mission status", body.engine.book.missions[MID].status)
    show("appraised (ledger order)", [(a["verdict"], "failure closure" if a.get("closure_event") else "achievement") for a in facts(body, "mission.appraised")])
    show("routing", routing.track_record(body.journal))
    show("sop.verified_appraisals has the mission", MID in verified_appraisals(body.journal))
    show("vepmc appraised_verified", [r["appraised_verified"] for r in metrics.vepmc(body.journal)["missions"] if r["mission_id"] == MID])
