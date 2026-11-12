"""Further mutants of the changed lines, run through the branch's own harness against the unit's test file."""
import sys
from pathlib import Path
ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "scripts" / "ci"))
from mutation_harness import run
SET, COR, SOP, PRE = "greg/cognition/settlement.py", "greg/corrections.py", "greg/sop.py", "greg/precedents.py"
TESTS = "tests/unit/test_greg_evidence_corrections.py"
MUTANTS = [
    (SET, "R1 a construction's contained answer is still credited (the construction branch skips the filter)",
     "            identity = settle(outcome, data) if outcome is not None else None",
     "            identity = (observations.__setitem__(_outcome_identity(outcome), outcome) or _outcome_identity(outcome)) if outcome is not None else None"),
    (SET, "R2 only a passing contained reading is withheld; a contained failure still counts against the method",
     "        if why is None:\n            observations[identity] = outcome",
     "        if why is None or not outcome[\"correct\"]:\n            observations[identity] = outcome"),
    (SET, "R3 once withheld, a later reading no correction contains never settles the claim again",
     "        if why is None:\n            observations[identity] = outcome",
     "        if why is None and identity not in withheld:\n            observations[identity] = outcome"),
    (SET, "R4 the revision names the wrong class of cause",
     '"class": why["cause"], "event": why["event"]}', '"class": "FOUNDER_REJECTED", "event": why["event"]}'),
    (SET, "R5 the main (non-construction) path skips the filter",
     "        settle(outcome, data)\n    if world_seen:", "        observations[_outcome_identity(outcome)] = outcome\n    if world_seen:"),
    (SET, "R6 settlement reads the mission projection, not the receipt projection",
     "    contained = corrections.contained_receipts(journal)", "    contained = corrections.contained_missions(journal)"),
    (COR, "R7 only the root reading is listed, not the receipts of the actions that bound it",
     '        for r in correction["affected"]["receipts"]:', '        for r in [correction["root"]["receipt"]]:'),
    (COR, "R8 a standing mission's hold is never a contained mission",
     '        for claim in correction["affected"]["claims"]:\n            out.setdefault(claim["mission_id"], why)',
     '        for claim in correction["affected"]["claims"]:\n            if claim["kind"] == "achieved":\n                out.setdefault(claim["mission_id"], why)'),
    (COR, "R9 a failed replication contains nothing (only a founder rejection does)",
     'APPRAISED = ("APPRAISAL_REFUTED",)', 'APPRAISED = ("APPRAISAL_REFUTED", "REPLICATION_FAILED")'),
    (COR, "R10 a founder rejection contains nothing (only a failed replication does)",
     'APPRAISED = ("APPRAISAL_REFUTED",)', 'APPRAISED = ("APPRAISAL_REFUTED", "FOUNDER_REJECTED")'),
    (COR, "R11 any compilation without an answer (timeout, abstain) is no failed replication, not only a deficit",
     'return isinstance(output, dict) and "CAPABILITY_DEFICIT" in (output.get("state"), output.get("abstention_state"))',
     'return isinstance(output, dict) and (output.get("state") not in (None, "ANSWERED", "WORLD_UNVERIFIED") or output.get("abstention_state") == "CAPABILITY_DEFICIT")'),
    (COR, "R12 the containing cause does not name its evidence.invalidated event",
     '"cause_id": cid, "event": events.get(cid)})', '"cause_id": cid, "event": None})'),
    (COR, "R13 a requalification row lifts only a failed replication, never a founder rejection (requalified ignored for rejections is NOT the code: this mutant makes every requalified row lift nothing)",
     'if correction.get("impugns_measurement") and cid not in requalified\n', 'if correction.get("impugns_measurement") and (cid not in requalified or correction["class"] == "REPLICATION_FAILED")\n'),
    (PRE, "R14 precedents read the receipt projection (nothing is subtracted)",
     "    contained = corrections.contained_missions(ctx.journal)", "    contained = corrections.contained_receipts(ctx.journal)"),
    (SOP, "R15 a contained mission is withheld from procedures only while unappraised (filter applied before the appraisal intersection is undone)",
     "    achieved.difference_update(corrections.contained_missions(journal))\n", "    achieved.difference_update(set(corrections.contained_missions(journal)) - achieved)\n"),
    (SET, "R16 reconcile names a cause for every invalidation on a body that has any withheld claim",
     "            why = withheld.get(identity)          # a correction", "            why = withheld.get(identity) or next(iter(withheld.values()), None)          # a correction"),
    (SOP, "R17 ratification ignores containment (proposal still filters)",
     "    current = closed_procedures(journal)\n",
     "    from greg import corrections as _c; _keep, _c.contained_missions = _c.contained_missions, (lambda j: {}); current = closed_procedures(journal); _c.contained_missions = _keep\n"),
]
raise SystemExit(run(MUTANTS, TESTS, "rc-mutants-", root=ROOT))
