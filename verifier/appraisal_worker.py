"""Fixed read-only subprocess entrypoint. No worker-selected code or evaluator."""
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# This is defense in depth for trusted fixed code, not an OS hostile-host sandbox.
def deny_effects(event, args):
    if event == "open":
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            raise PermissionError("appraiser is read-only")
    if event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn")) or event in {
        "os.system", "os.remove", "os.rename", "os.mkdir", "os.rmdir", "os.chmod"}:
        raise PermissionError("appraiser has no external-effect capability")
sys.addaudithook(deny_effects)

from verifier.mission_audit import appraise
from omnimorph.organization_compiler import content_digest
from verifier.retained_appraisal import policy, frozen_snapshot

request = json.loads(sys.stdin.read(262145))
if set(request) != {"snapshot", "result", "binding", "policy"}:
    raise ValueError("closed appraisal request")
if request["policy"] != policy():
    raise ValueError("evaluator policy drift")
if request["snapshot"] != frozen_snapshot():
    raise ValueError("source snapshot does not match frozen experiment")
report = appraise(request["snapshot"], request["result"])
receipt = {"report": report, "binding": request["binding"], "policy": request["policy"],
           "evidence_mode": "SIMULATION", "execution_authority": "none",
           "appraisal_performed": True, "process_id": os.getpid()}
receipt["digest"] = content_digest(receipt)
print(json.dumps(receipt, sort_keys=True))
