"""Each safeguard of evidence-correction propagation (directive section 45, S45.A3; behaviour B) must fail its tests.

    python scripts/ci/check_evidence_corrections_mutants.py

Mutants are applied to greg/corrections.py, greg/body.py and the readers that withhold what a correction contains
(greg/cognition/settlement.py, greg/sop.py, greg/precedents.py) in a scratch copy of the repository, never to the
working tree; the copy runs without bytecode and its __pycache__ is purged before each mutant. A mutant is caught only
when tests/unit/test_greg_evidence_corrections.py reports a FAILED test (an import or collection error does not
count). Exit status 1 if any mutant survives or no longer applies.
"""
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
CORRECTIONS = "greg/corrections.py"
BODY = "greg/body.py"
SETTLEMENT = "greg/cognition/settlement.py"
SOP = "greg/sop.py"
PRECEDENTS = "greg/precedents.py"
TESTS = "tests/unit/test_greg_evidence_corrections.py"
MUTANTS = [
    (CORRECTIONS, "a refuted appraisal or a founder rejection asks again about the mission alone",
     'cause["class"] not in SELF_REPORTED and any(', 'any('),
    (CORRECTIONS, "a changed source is not noticed", 'if other["digest"] != src["digest"]:', "if False:"),
    (CORRECTIONS, "a retracted source is not noticed", '                    if other["absent"]:\n',
     "                    if False:\n"),
    (CORRECTIONS, "a changed API is not noticed",
     'if src["api"] and other["api"] and other["api"] != src["api"]:', "if False:"),
    (CORRECTIONS, "a server error counts as a reading of the source", ' or other["server_error"] or (', " or ("),
    (CORRECTIONS, "a standing mission's own drift counts against its hold",
     'return later["seq"] > base["seq"] and later["mission_id"] != own', 'return later["seq"] > base["seq"]'),
    (CORRECTIONS, "an expired measurement is not noticed", "if instant is not None and instant <= now:", "if False:"),
    (CORRECTIONS, "a replication on a changed input counts as failed",
     "                    if computed and later[\"source\"] is None or (",
     "                    if True or computed and later[\"source\"] is None or ("),
    (CORRECTIONS, "a failed replication is not noticed", '                        cause("REPLICATION_FAILED"',
     '                        False and cause("REPLICATION_FAILED"'),
    (CORRECTIONS, "a world sensor's failure is a failed replication", 'COMPUTATIONS = ("cognition.",)',
     'COMPUTATIONS = ("",)'),
    (CORRECTIONS, "a refuted appraisal is not noticed", 'if p.get("verdict") != "REFUTED":', "if True:"),
    (CORRECTIONS, "a founder rejection is not noticed", 'if p.get("verdict") != "reject":', "if True:"),
    (CORRECTIONS, "a reading overrules a founder rejection",
     'if cause["class"] == "FOUNDER_REJECTED":\n            return None', "if False:\n            return None"),
    (CORRECTIONS, "a refuted appraisal is requalified by a reading",
     '        if cause["class"] == "APPRAISAL_REFUTED":\n            closure', '        if False:\n            closure'),
    (CORRECTIONS, "a source that moved on contains the method that read it",
     'if correction.get("impugns_measurement") and cid not in requalified\n', "if cid not in requalified\n"),
    (CORRECTIONS, "a requalified cause stays contained",
     'if correction.get("impugns_measurement") and cid not in requalified\n', 'if correction.get("impugns_measurement")\n'),
    (CORRECTIONS, "a refuted appraisal contains what its readers already withdraw and restore",
     '\n            and correction["class"] not in APPRAISED]', "]"),
    (CORRECTIONS, "a mission that acted on a contained reading is not named",
     'out.setdefault(claim["mission_id"], why)', 'out.setdefault(correction["root"]["mission_id"], why)'),
    (CORRECTIONS, "a compilation that ran no method counts as a failed replication",
     'later["inconclusive"] or later["no_method"]:', 'later["inconclusive"]:'),
    (CORRECTIONS, "a deficit is read from data GREG did not produce",
     '"no_method": own and no_method_ran(output),', '"no_method": no_method_ran(output),'),
    (CORRECTIONS, "an action that bound an affected receipt is not followed", "hit = used & receipts", "hit = set()"),
    (CORRECTIONS, "the claim of a mission that acted on it is not followed",
     'acted = claim["mission_id"] in acted_at and claim["seq"] > acted_at[claim["mission_id"]]', "acted = False"),
    (CORRECTIONS, "a decision citing it is not named", "named = any(r in text for r in receipts)", "named = False"),
    (CORRECTIONS, "an approval of an action that used it is not named",
     'if named or p.get("scope_digest") in scopes:', "if named:"),
    (CORRECTIONS, "a settled outcome on it is not named",
     '(e.payload.get("receipt") in receipts or e.payload.get("observation_event") in observed)', "False"),
    (CORRECTIONS, "a procedure from its mission is not named",
     'if set(e.payload.get("missions") or []) & affected_missions)', "if False)"),
    (CORRECTIONS, "a terminal delivery is not put to the founder",
     'if terminal or outside or affected["decisions"]:', 'if outside or affected["decisions"]:'),
    (CORRECTIONS, "a hold nothing depends on is put to the founder",
     'if terminal or outside or affected["decisions"]:', "if True:"),
    (CORRECTIONS, "one event asks once per reading", '"mission": cause["root"]["mission_id"]})[7:31]',
     '"mission": cause["root"]["mission_id"], "root": cause["root"]["receipt"]})[7:31]'),
    (CORRECTIONS, "any later passing reading requalifies",
     'if (later["sensor"] == root["sensor"] and later["passed"]', 'if (later["passed"]'),
    (CORRECTIONS, "the claim's predicate is not part of the sensor's identity",
     ',\n                     "predicate": check.get("predicate")})', "})"),
    (CORRECTIONS, "a requalifying reading with expired evidence counts",
     '\n                    and all((_instant(t) or now) > now for t in later["expires"])', ''),
    (CORRECTIONS, "an expired measurement can never be requalified", "self.head_seq, False)", "1 << 62, False)"),
    (CORRECTIONS, "requalification is checked against the recomputed trigger",
     "by = index.requalified(invalidated.get(cid, cause), now)", "by = index.requalified(cause, now)"),
    (CORRECTIONS, "expiries are read from untrusted data", 'own = str(p.get("capability", "")).startswith("cognition.")',
     "own = True"),
    (CORRECTIONS, "an expiry with no evidence digest counts",
     'if isinstance(output.get("expires_at"), str) and "digest" in output:', 'if isinstance(output.get("expires_at"), str):'),
    (CORRECTIONS, "a requalification does not move the claim's basis", '            out[q["root"]] = q["by"]["receipt"]\n',
     '            pass\n'),
    (CORRECTIONS, "a cause's identity ignores the basis it was found on", 'else base["receipt"]})[7:39]',
     'else root["receipt"]})[7:39]'),
    (CORRECTIONS, "a server's final URL is kept as text", '"api": [sha256_json({"u": output.get("final_url")})[7:23],',
     '"api": [output.get("final_url"),'),
    (CORRECTIONS, "the founder's own words are screened as GREG's",
     "asks.record(journal, _ask(group), quoted=_quoted(index, group))", "asks.record(journal, _ask(group))"),
    (CORRECTIONS, "a known cause is recorded again", "        if cid in corrected:\n            continue",
     "        if False:\n            continue"),
    (CORRECTIONS, "a crash before the correction leaves the cause without one",
     "        if cid in corrected:\n            continue",
     '        if cid in corrected or journal.retained("evidence.invalidated", [cid]) is not None:\n            continue'),
    (CORRECTIONS, "a requalified group keeps its ask open", "elif not open_causes and asked and rid not in answered",
     "elif False"),
    (CORRECTIONS, "an answered ask is withdrawn on requalification",
     "elif not open_causes and asked and rid not in answered", "elif not open_causes and asked"),
    (BODY, "the body never propagates", "        corrections.propagate(self.journal, now)\n", "        pass\n"),
    # what a correction contains stops earning credit: every reader of settled competence, procedures, precedents
    (SOP, "a procedure is learned from a contained mission",
     "    achieved.difference_update(corrections.contained_missions(journal))\n", ""),
    (PRECEDENTS, "a contained mission is still a precedent", ") - contained.keys())]", "))]"),
    (SETTLEMENT, "settlement ignores containment",
     "    contained = corrections.contained_receipts(journal)", "    contained = {}"),
    (SETTLEMENT, "the invalidating revision does not name its cause", "why = withheld.get(identity)", "why = None"),
    (SETTLEMENT, "an earlier reading of a withheld claim earns the credit back",
     "        observations.pop(identity, None)       # no earlier", "        pass       # no earlier"),
]


def main() -> int:
    return run(MUTANTS, TESTS, prefix="evidence-corrections-mutants-", root=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
