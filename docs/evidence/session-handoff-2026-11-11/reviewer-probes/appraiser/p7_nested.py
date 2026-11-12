"""A method nested inside an ATTACHED cognition sensor is detached after the closure, before its appraisal.
Does the appraiser run it? What verdict, and who reads it as failure evidence? Base vs head."""
from lib import *
from greg import autonomy, routing, corrections
from tests.unit.test_greg_failure_closure import blackbox, METHODS

MIDC = "m:passes"
for what in ("none", "detach"):
    tmp = tmpdir("p7"); child = Child(tmp)
    home, key, body_id, _ = make_body(tmp)
    clock = Clock()
    for cid in METHODS:
        drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))
    drop(home, signed(key, body_id, "MISSION", blackbox(MIDC, 1, 1e6)))
    close_then_stop(home, clock, mid=MIDC, ticks=10, step=31.0)
    if what == "detach":
        for cid in METHODS:
            detach(home, key, body_id, cid)
    with Body(home, clock=clock) as body:
        body.tick(); clock.advance(31)
        a = facts(body, "mission.appraised", MIDC)
        show(f"{what} | adapters run by appraiser child", child.ran)
        show(f"{what} | appraised", [(x["verdict"], x["checks"].get("world_reobserved"), x["findings"], x.get("not_run")) for x in a])
        show(f"{what} | autonomy.failures", [(f["kind"], f["run"].payload["action_id"]) for f in autonomy.failures(body.journal)])
        show(f"{what} | corrections APPRAISAL_REFUTED", len([c for c in corrections.Index(body.journal).causes(body.clock()) if c["class"] == "APPRAISAL_REFUTED"]))
        show(f"{what} | routing", routing.track_record(body.journal))
        if what == "detach":
            for cid in METHODS:
                attach(home, key, body_id, cid)
            for _ in range(3):
                body.tick(); clock.advance(31)
            show(f"{what} | after re-attach: children, appraised", (len(child.requests), [x["verdict"] for x in facts(body, "mission.appraised", MIDC)]))
