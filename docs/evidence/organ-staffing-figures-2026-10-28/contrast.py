"""Evidence: one real exchange per report; prints what WealthMachine concluded (used before/after)."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, ".")
from tests.integration import test_organ_staffing_figures as T
from tests.unit.test_greg_organs import live_organs
from events.spine import EventSpine
from greg.journal import Journal
from provenance.ledger import EvidenceLedger
tmp = Path(tempfile.mkdtemp())
j = Journal(EventSpine(EvidenceLedger("sha256:" + "1" * 64, path=str(tmp / "l.jsonl"))), actor="spiffe://uniimente.internal/test/organs")
params = live_organs()
rows = {}
for name, prob in (("8/8", T.FULL), ("4/8", T.SHORT)):
    out, packet, wmi = T.run(tmp / name.replace("/", "of"), j, params, T.seed_for(T.certified(prob)), "m:" + name.replace("/", "of"))
    rows[name] = {"organ_heads": out["organ_heads"], "appraisal": out["appraisal_verdict"],
                  "evidence_items": len(packet["evidence"]), "go_no_go": wmi["go_no_go"],
                  "opportunity_score": wmi["opportunity_score"], "reasons": wmi["reasons"],
                  "validation_plan": wmi["validation_plan"], "recommended_next_action": wmi["recommended_next_action"]}
same = {k: rows["8/8"][k] == rows["4/8"][k] for k in ("evidence_items", "go_no_go", "opportunity_score", "reasons", "validation_plan", "recommended_next_action")}
print(json.dumps({"python": sys.version.split()[0], "rows": rows, "identical_between_8of8_and_4of8": same}, indent=1))
