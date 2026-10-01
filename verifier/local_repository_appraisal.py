"""Fixed, credential-free child appraisal of a retained local audit receipt.

Canonical Ledger read_only + exact head binds the input. Independent derivation
and source reread defeat worker assertions. Reviewed-code process isolation is
not an OS filesystem sandbox against arbitrary native code or the host owner.
"""
import json
import sys

from egregore.repository_audit import capture, derive
from egregore.local_mission import validate_job, proposal, receipt_for
from events.spine import EventSpine
from provenance.ledger import EvidenceLedger, sha256_json


def appraise(request):
    ledger = EvidenceLedger(request["constitution"], request["ledger"], read_only=True,
                            expected_head=request["head"])
    try:
        submissions = [e for e in EventSpine(ledger).replay("greg.submitted")
                       if e.payload["mission_id"] == request["mission_id"]]
        if len(submissions) != 1:
            raise ValueError("one retained mission required")
        job = validate_job(submissions[0].payload["data"]["job"])
        receipt = ledger.find(request["receipt"])
        if receipt is None or receipt.record_type != "receipt":
            raise ValueError("retained receipt required")
        bound = receipt_for(ledger, proposal(job, submissions[0].actor))
        if bound is None or bound.hash != receipt.hash:
            raise ValueError("receipt is not the mission's retained acceptance")
        result = receipt.payload["result"]
        if result["scope_digest"] != sha256_json(job):
            raise ValueError("receipt belongs to another scope")
        actual = capture(job["repositories"])
        if actual != result["sources"]:
            raise ValueError("worker evidence differs from actual Git objects")
        report = derive(actual, job["expected_pin"], job["expected_version"])
        return {"head": request["head"], "receipt": receipt.hash, "report": report,
                "evidence_tier": "actual local sources; separate-process appraisal",
                "external_publication": False}
    finally:
        ledger.close()


if __name__ == "__main__":
    raw = sys.stdin.read(65537)
    if len(raw) > 65536:
        raise ValueError("appraisal input too large")
    print(json.dumps(appraise(json.loads(raw)), sort_keys=True))
