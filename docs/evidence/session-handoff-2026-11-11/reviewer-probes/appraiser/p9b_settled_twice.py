"""Why two cognition.settled records for one failure after the re-attach? Control: no detach at all, same ticks."""
import sys
from lib import *
from greg.cognition import settlement
from tests.unit.test_greg_failure_closure import blackbox, METHODS

mid = "m:fails"
for mode in sys.argv[1:] or ("control", "detach"):
    tmp = tmpdir("p9b"); child = Child(tmp)
    home, key, body_id, _ = make_body(tmp)
    clock = Clock()
    for cid in METHODS:
        drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))
    drop(home, signed(key, body_id, "MISSION", blackbox(mid, 1, 0.0)))
    close_then_stop(home, clock, closure="mission.unmet", mid=mid, ticks=12, step=31.0)
    if mode == "detach":
        detach(home, key, body_id, "cognition.solve")
    with Body(home, clock=clock) as body:
        for _ in range(3):
            body.tick(); clock.advance(31)
        if mode == "detach":
            attach(home, key, body_id, "cognition.solve")
        for _ in range(4):
            body.tick(); clock.advance(31)
        show(f"{mode} | appraised", [a["verdict"] for a in facts(body, "mission.appraised", mid)])
        show(f"{mode} | observations", [(e.payload["check_id"], e.payload["passed"], (e.payload.get("receipt") or "")[:8]) for e in body.journal.replay("mission.observed")])
        show(f"{mode} | unmet", len(body.journal.replay("mission.unmet")))
        for e in body.journal.replay("cognition.settled"):
            p = e.payload
            show(f"{mode} | settled", {k: (str(v)[:16] if isinstance(v, str) else v) for k, v in p.items() if k in ("mission_id", "method", "correct", "receipt", "cognitive_receipt", "observation_event", "appraisal_event", "claim", "outcome_id")})
        show(f"{mode} | measured_outcomes", [(o["method"], o["correct"], o["receipt"][:8]) for o in settlement.measured_outcomes(body.journal)])
        try:
            from greg.cognition.settlement import competence
            show(f"{mode} | competence", competence(body.journal))
        except Exception as exc:
            show(f"{mode} | competence n/a", type(exc).__name__)
