"""A fabricated, self-consistent staffing report, sent over the real organ exchange.

The Kernel's hostile cases (truncated, inconsistent, contradictory, replayed, self-promoting) are all reports that
contradict themselves or each other. This one does not: it claims 8 of 8 staffed with workers who do not exist
("Zed", "Yan"), in the exact shape certify_staffing emits, for the 4-of-8 problem whose true answer is a shortage of
4. No Kernel code produced it.

Expectation, stated before the run: WealthMachine has only the report, so it returns "go" with one reading
"staffed=8, total_demand=8, shortage=0" labelled "(unverified report)"; the Kernel-stated verdict stays
"needs_more_evidence" (governing_bottleneck is not stated) and requires_human_approval stays true.

Usage (cwd = the Kernel worktree, PYTHONPATH = the Kernel worktree, the four UNIIMENTE_* organ variables set):
    python consistent_lie.py <output-dir>
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

from events.spine import EventSpine
from greg.journal import Journal
from provenance.ledger import EvidenceLedger
import tests.integration.test_organ_staffing_figures as t
from tests.unit.test_greg_organs import live_organs

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
params = live_organs()
truth = t.certified(t.SHORT)                      # what GREG certifies for the problem: 4 of 8, shortage 4
lie = {**t.certified(t.FULL), "assignment": [["Yan", "Line", 4], ["Zed", "Dock", 4]]}
work = Path(tempfile.mkdtemp(prefix="consistent-lie-", dir=OUT))
journal = Journal(EventSpine(EvidenceLedger("sha256:" + "1" * 64, path=str(work / "l.jsonl"))),
                  actor="spiffe://uniimente.internal/test/organs")
out, packet, wmi = t.run(work / "lie", journal, params, t.seed_for(lie), "m:consistent-lie")
readings = [r for r in wmi["reasons"] if r.startswith("staffing evidence[")]
record = {"true_certified_answer": {k: truth[k] for k in ("staffed", "total_demand", "shortage", "unfilled")},
          "fabricated_report": lie, "wealthmachine_go_no_go": wmi["go_no_go"], "readings": readings,
          "recommended_next_action": wmi["recommended_next_action"],
          "requires_human_approval": wmi["requires_human_approval"],
          "kernel_stated_verdict": out["verdict"], "kernel_verdict_why": out["verdict_why"],
          "appraisal_verdict": out["appraisal_verdict"], "authority_created": out["authority_created"],
          "organ_heads": out["organ_heads"]}
expected = {"wealthmachine_says_go": wmi["go_no_go"] == "go",
            "reading_repeats_the_lie_as_unverified": len(readings) == 1 and "staffed=8, total_demand=8, shortage=0"
                                                     in readings[0] and "(unverified report)" in readings[0],
            "kernel_stated_verdict_stays_below_go": out["verdict"] == "needs_more_evidence",
            "requires_human_approval": wmi["requires_human_approval"] is True,
            "no_authority": out["authority_created"] is False and out["external_effects"] is None}
record["expectations"] = expected
(OUT / "consistent-lie.json").write_text(json.dumps(record, indent=1, sort_keys=True, ensure_ascii=False))
print(json.dumps({k: v for k, v in record.items() if k != "fabricated_report"}, indent=1, sort_keys=True,
                 ensure_ascii=False))
raise SystemExit(0 if all(expected.values()) else 1)
