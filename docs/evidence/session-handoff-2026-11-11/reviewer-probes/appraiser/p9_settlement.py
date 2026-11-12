"""Settlement and competence credit: a cognition closure (success and failure) whose sensor cognition.solve is
detached before the appraisal. Is anything settled (credit or blame) under UNAVAILABLE? After re-attach, once?"""
from lib import *
from greg.cognition import settlement
from tests.unit.test_greg_failure_closure import blackbox, METHODS


def settled(body):
    return [(e.payload.get("mission_id"), e.payload.get("method"), e.payload.get("correct")) for e in body.journal.replay("cognition.settled")]


for mid, tau, closure in (("m:passes", 1e6, "mission.achieved"), ("m:fails", 0.0, "mission.unmet")):
    tmp = tmpdir("p9"); child = Child(tmp)
    home, key, body_id, _ = make_body(tmp)
    clock = Clock()
    for cid in METHODS:
        drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))
    drop(home, signed(key, body_id, "MISSION", blackbox(mid, 1, tau)))
    close_then_stop(home, clock, closure=closure, mid=mid, ticks=12, step=31.0)
    detach(home, key, body_id, "cognition.solve")
    with Body(home, clock=clock) as body:
        for _ in range(3):
            body.tick(); clock.advance(31)
        show(f"{mid} detached | adapters run, appraised", (child.ran, [(a["verdict"], sorted(a.get("not_run", {}))) for a in facts(body, "mission.appraised", mid)]))
        show(f"{mid} detached | cognition.settled", settled(body))
        show(f"{mid} detached | measured_outcomes", len(settlement.measured_outcomes(body.journal)))
        attach(home, key, body_id, "cognition.solve")
        for _ in range(4):
            body.tick(); clock.advance(31)
        show(f"{mid} re-attached | children, adapters run, appraised", (len(child.requests), child.ran, [a["verdict"] for a in facts(body, "mission.appraised", mid)]))
        show(f"{mid} re-attached | cognition.settled", settled(body))
        show(f"{mid} re-attached | measured_outcomes", [(o["method"], o["correct"]) for o in settlement.measured_outcomes(body.journal)])
