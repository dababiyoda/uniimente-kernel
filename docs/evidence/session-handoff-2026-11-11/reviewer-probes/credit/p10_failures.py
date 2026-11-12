"""(1) A founder rejection of a failure closure, or of a failing reading. (2) Founder question 1: a claim that failed
under an unmet closure and passed under a later achievement, and the achievement is rejected (the second reading,
its closure and its appraisal are written directly: a deterministic solver cannot fail and then pass)."""
from rc_common import *
from greg.sop import REQUIRED_CHECKS
from tests.unit.test_greg_failure_closure import blackbox, run
from pathlib import Path
body, key, body_id, clock = run(Path(tmp()), [blackbox("m:fails", 1, 0.0), blackbox("m:passes", 1, 1e6)])
def sign(kind, payload): return body.apply(signed(key, body_id, kind, payload))
try:
    j = body.journal
    out("credit0", credit(body)); out("credited0", credited(j))
    [unmet] = [e for e in j.replay("mission.unmet")]
    reject(sign, unmet.event_id, "this failure is not the method's fault: my threshold was wrong")
    failing = [e for e in j.replay("mission.observed") if e.payload["mission_id"] == "m:fails"][-1]
    reject(sign, failing.event_id, "this reading is wrong")
    turn(body, clock, 2)
    out("1 after rejecting the unmet closure and its failing reading", {"causes": causes(j), "credit": credit(body), "credited": credited(j),
        "claims": [(c["mission_id"], c["state"]) for c in corrections.claims(j, clock())]})
    # (2) the same claim read again, passing, under an achievement that a VERIFIED appraisal judges
    old = j.ledger.find(failing.payload["receipt"])
    new = j.ledger.append("receipt", dict(old.payload))
    j.record("mission.observed", {**failing.payload, "passed": True, "detail": "staged pass", "receipt": new.hash}, key=["m:fails", "good", "staged"])
    j.record("mission.achieved", {"mission_id": "m:fails", "evidence": [new.hash], "actions_done": 1, "closure_rule": "staged",
                                  "founder_authenticated_mission": True, "at": "2026-11-12T00:00:00Z"}, key=["m:fails", "achieved"])
    j.record("mission.appraised", {"mission_id": "m:fails", "head": "staged", "verdict": "VERIFIED", "checks": {k: True for k in REQUIRED_CHECKS},
                                   "findings": [], "appraiser": "staged"}, key=["m:fails", "appraised", "staged"])
    settlement.reconcile(j)
    out("2a staged: failed under the unmet closure, passed under the achievement", {"credit": credit(body), "credited": credited(j)})
    reject(sign, closure_of(j, "m:fails").event_id, "this achievement is wrong")
    corrections.propagate(j, clock()); settlement.reconcile(j)
    out("2b the founder rejects the achievement", {"causes": causes(j), "credit": credit(body), "credited": credited(j)})
    import greg.corrections as c
    real = c.contained_receipts
    c.contained_receipts = lambda journal: {}
    out("2c the same history with the filter off (what the appraiser verified under each closure)", {"credit": credit(body), "credited": credited(j)})
    c.contained_receipts = real
finally:
    body.close()
