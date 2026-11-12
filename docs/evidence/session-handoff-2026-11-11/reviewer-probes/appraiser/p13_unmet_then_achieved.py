"""A mission closes unmet; its failure closure waits for its appraisal while the sensor is detached. The founder
does the work himself (one of the alternatives the ask offers) and re-attaches the sensor. The mission then
achieves. What is recorded about the failure closure and about the mission, and who reads it?"""
from lib import *
from greg import autonomy, routing, corrections, metrics
from greg.sop import verified_appraisals
from greg.cognition.settlement import _settling_appraisals

tmp = tmpdir("p13"); child = Child(tmp)
home, key, body_id, data = make_body(tmp)
status = data / "status.txt"; status.write_text("not yet")
drop(home, signed(key, body_id, "MISSION", mission(MID, checks=[note_check("status", status, "shipped")],
     strategies=[write_strategy("nudge", "nudge.txt", "nudged", ["status"])], capabilities=["fs.read", "fs.write"])))
clock = Clock()
close_then_stop(home, clock, closure="mission.unmet", ticks=12, step=600.0)
detach(home, key, body_id)


def ap(body):
    return [(a["verdict"], "failure closure" if a.get("closure_event") else "achievement", a["findings"][:1]) for a in facts(body, "mission.appraised")]


with Body(home, clock=clock) as body:
    out = []
    for _ in range(2):
        try:
            body.tick(); out.append("ok")
        except Exception as exc:
            out.append("CRASH " + type(exc).__name__)
        clock.advance(600)
    show("while detached | ticks, appraised, adapters run", (out, ap(body), child.ran))
    status.write_text("shipped")                 # the founder does the work himself
    attach(home, key, body_id)
    out = []
    for _ in range(4):
        try:
            body.tick(); out.append("ok")
        except Exception as exc:
            out.append("CRASH " + type(exc).__name__ + " " + str(exc)[:80])
        clock.advance(3600)
    m = body.engine.book.missions[MID]
    show("after the work and the re-attach | ticks, mission status", (out, m.status))
    show("appraised (ledger order)", ap(body))
    show("autonomy.failures", [(f["kind"], f["run"].payload["action_id"], f["why"][:70]) for f in autonomy.failures(body.journal)])
    show("corrections APPRAISAL_REFUTED", len([c for c in corrections.Index(body.journal).causes(body.clock()) if c["class"] == "APPRAISAL_REFUTED"]))
    show("routing.track_record", routing.track_record(body.journal))
    show("sop.verified_appraisals has the mission", MID in verified_appraisals(body.journal))
    row = [r for r in metrics.vepmc(body.journal)["missions"] if r["mission_id"] == MID]
    show("metrics.vepmc appraised_verified", [r["appraised_verified"] for r in row])
    show("settling appraisal", {k: v.payload["verdict"] for k, v in _settling_appraisals(body.journal).items()})
from greg.console import Console
from greg.mission_control import projection
show("Mission Control appraisals", [(a["mission_id"], a["verdict"]) for a in projection(Console(home))["appraisals"]])
