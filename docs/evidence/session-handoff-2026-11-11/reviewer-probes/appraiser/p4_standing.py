"""A standing mission: hold #1 waits for its appraisal while its sensor is detached. The world drifts (which is what
a standing mission exists for). The founder re-attaches. What is hold #1's appraisal judged against, and who reads
the result as failure evidence? Also: what Mission Control and the morning report show (claim 2)."""
import re
import sys
from lib import *
from greg import autonomy, routing, corrections

DRIFT = sys.argv[1] if len(sys.argv) > 1 else "drift"

tmp = tmpdir("p4"); child = Child(tmp)
home, key, body_id, note = note_mission(tmp, closure={"kind": "infinite"})
clock = Clock()
close_then_stop(home, clock, closure="mission.held")
detach(home, key, body_id)


def ap(body):
    return [(a["verdict"], (a.get("closure_event") or "")[:8], sorted(a.get("not_run", {})), a["findings"][:1])
            for a in facts(body, "mission.appraised")]


with Body(home, clock=clock) as body:
    body.tick(); clock.advance(60)
    holds = [e.event_id[:8] for e in body.journal.replay("mission.held")]
    show("holds, appraised after detach", (holds, ap(body), child.ran))
    m = body.engine.book.missions[MID]
    show("mission state", (m.status, (m.blocker or {}).get("type")))
    # claim 2: what the founder sees
    from greg.tribunal import morning_report
    rep = [a for a in morning_report(body.journal, body.engine)["appraisals"] if a["mission_id"] == MID]
    show("morning report", [(a["verdict"], a["findings"]) for a in rep])
from greg.console import Console
from greg.mission_control import projection, render_view
console = Console(home)
html = render_view(console, "proof", {})
show("proof view has UNAVAILABLE", "UNAVAILABLE" in html)
show("proof view has the reason text", ("could not be re-measured" in html, "DETACHED" in html))
show("proof view rows", re.findall(r"<td>[^<]*m:note[^<]*</td><td>(?:<[^>]+>)?([A-Z_]+)", html)[:5])
show("projection appraisals", projection(console)["appraisals"])
for view in ("missions", "authority", "asks", "home"):
    try:
        h = render_view(console, view, {})
        show(f"view {view}: mentions UNAVAILABLE / reason", ("UNAVAILABLE" in h, "could not be re-measured" in h))
    except Exception as exc:
        show(f"view {view}", type(exc).__name__)

if DRIFT == "drift":
    note.write_text("drifted while the sensor was detached")     # the world moves on, as a standing mission expects
attach(home, key, body_id)
with Body(home, clock=clock) as body:
    for i in range(6):
        body.tick(); clock.advance(600)
        show(f"tick {i+1} after re-attach | holds, appraised, adapters run", (len(body.journal.replay("mission.held")), ap(body), child.ran))
    show("note now", note.read_text())
    fails = autonomy.failures(body.journal)
    show("autonomy.failures", [(f["kind"], f["run"].payload["action_id"], f["why"][:80]) for f in fails])
    show("corrections APPRAISAL_REFUTED", [(c["class"], (c.get("detail") or {}).get("closure_event", "")[:8])
                                           for c in corrections.Index(body.journal).causes(body.clock()) if c["class"] == "APPRAISAL_REFUTED"])
    show("routing", routing.track_record(body.journal))
    from greg.sop import verified_appraisals
    show("sop.verified_appraisals has mission", MID in verified_appraisals(body.journal))
    from greg.cognition.settlement import _settling_appraisals
    show("settling appraisal", {k: v.payload["verdict"] for k, v in _settling_appraisals(body.journal).items()})
