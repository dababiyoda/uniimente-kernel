"""Scratch experiment (not repository code): B's residual on the unchanged integration head.

A real body closes a cognition mission, the separate appraiser VERIFIES it and settlement credits the method. The
founder then rejects that closure in a signed CRITIQUE. corrections.propagate records FOUNDER_REJECTED (it impugns the
measurement) and lists the receipt in contained_receipts. Question: does any credit projection withhold it?"""
import json, sys, tempfile
from pathlib import Path
from greg import corrections, disposition, sop
from greg.cognition import compiler, settlement
from tests.greg_fixtures import signed
from tests.unit.test_greg_failure_closure import blackbox, run

EVTYPE = "founder_judgment"
tmp = Path(tempfile.mkdtemp(dir=sys.argv[1]))
body, key, body_id, clock = run(tmp, [blackbox("m:okay", 3, 1e6)], ticks=6)
out = {}
try:
    j = body.journal
    out["appraisal"] = [e.payload["verdict"] for e in j.replay("mission.appraised")]
    out["settled_before"] = compiler._settled_counts(j)
    [achieved] = j.replay("mission.achieved")
    body.apply(signed(key, body_id, "CRITIQUE", {"target_event_id": achieved.event_id, "verdict": "reject", "evidence_type": EVTYPE,
                                                 "text": "this answer is wrong for my problem"}))
    for _ in range(3):
        body.tick(); clock.advance(31)
    out["critiques"] = [(e.payload.get("verdict")) for e in j.replay("critique.recorded")]
    out["causes"] = [(e.payload["class"], e.payload["impugns_measurement"]) for e in j.replay("evidence.invalidated")]
    contained = corrections.contained_receipts(j)
    out["contained_receipts"] = len(contained)
    out["claim_state"] = [(c["mission_id"], c["state"]) for c in corrections.claims(j, clock())]
    out["settled_after"] = compiler._settled_counts(j)
    out["measured_outcomes_resting_on_contained"] = sum(1 for o in settlement.measured_outcomes(j) if o["receipt"] in contained)
    out["cognition_settled_invalidated_flags"] = [bool(e.payload.get("invalidated")) for e in j.replay("cognition.settled")]
    out["sop_closed_procedures"] = sorted(sop.closed_procedures(j))
    out["asks"] = [e.payload["kind"] for e in j.replay("decision.requested")]
finally:
    body.close()
print(json.dumps(out, indent=1, default=str))
