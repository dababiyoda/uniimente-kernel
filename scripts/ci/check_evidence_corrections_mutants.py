"""Each safeguard of evidence-correction propagation (directive section 45, S45.A3; behaviour B) must fail its tests.

    python scripts/ci/check_evidence_corrections_mutants.py

Mutants are applied to greg/corrections.py, greg/body.py, greg/tribunal.py (the result of a signed rejection) and
the readers that withhold what a correction contains (greg/cognition/settlement.py, greg/sop.py, greg/precedents.py,
greg/routing.py, greg/autonomy.py) in a scratch copy of the repository, never to the working tree; the copy runs without bytecode and its __pycache__ is purged before each mutant. A mutant is caught only
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
ROUTING = "greg/routing.py"
AUTONOMY = "greg/autonomy.py"
TRIBUNAL = "greg/tribunal.py"
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
    (CORRECTIONS, "a founder rejection is not noticed",
     'rows = [e for e in journal.replay("critique.recorded") if e.payload.get("verdict") in verdicts]', "rows = []"),
    (CORRECTIONS, "a reading overrules a founder rejection",
     'if cause["class"] == "FOUNDER_REJECTED":\n            by = self.rejections()',
     'if False:\n            by = self.rejections()'),
    (CORRECTIONS, "a refuted appraisal is requalified by a reading",
     '        if cause["class"] == "APPRAISAL_REFUTED":\n            closure', '        if False:\n            closure'),
    (CORRECTIONS, "a source that moved on contains the method that read it",
     '           if c.get("impugns_measurement")\n', "           if True\n"),
    # "a requalified cause stays contained" was a mutant of a ``cid not in requalified`` test, deleted with the review
    # of 0a9a246f: a requalification now lifts a cause by moving its basis, so the cause is no longer derived. Its
    # behaviour is the mutant "a recorded correction the readings do not produce withholds credit" below.
    (CORRECTIONS, "a refuted appraisal contains what its readers already withdraw and restore",
     'and c["class"] not in APPRAISED and c["class"] != "FOUNDER_REJECTED"', 'and c["class"] != "FOUNDER_REJECTED"'),
    (CORRECTIONS, "a mission that acted on a contained reading is not named",
     'out["missions"].setdefault(claim["mission_id"], why)',
     'out["missions"].setdefault(index.by_receipt[root]["mission_id"], why) if root in index.by_receipt else None'),
    (CORRECTIONS, "a compilation that ran no method counts as a failed replication",
     'later["inconclusive"] or later["unanswered"] \\\n', 'later["inconclusive"] \\\n'),
    (CORRECTIONS, "a deficit is read from data GREG did not produce",
     '"unanswered": own and held_no_answer(output),', '"unanswered": held_no_answer(output),'),
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
     ',\n                        "predicate": check.get("predicate")})', "})"),
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
    (CORRECTIONS, "a cause's identity ignores the basis it was found on",
     '                            else base["receipt"])', '                            else root["receipt"])'),
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
    # Review of b01d319f (2026-11-12) and the founder's decision of that day. One mutant per safeguard that only these
    # make; the tests assert more than is mutated here (a rejected settled row or appraisal, the morning report, the
    # restored row), because this gate runs in a CI job with a 30-minute limit.
    # F1 and F2: a founder rejection withholds the answer, not one receipt of it
    (CORRECTIONS, "a founder rejection contains one receipt, and the same answer under another earns the credit back",
     "            for other in self.same_answer(root):", "            for other in []:"),
    (CORRECTIONS, "the rejected answer earns credit again through another mission",
     '\n                     or (reading["own"] and r["own"] and r["sensor"] is not None and r["sensor"] == reading["sensor"]))]',
     ")]"),
    (CORRECTIONS, "a different answer is withheld with the rejected one",
     'if r is not reading and r["answer"] == reading["answer"] and r["passed"] == reading["passed"]',
     'if r is not reading and r["passed"] == reading["passed"]'),
    (CORRECTIONS, "the method that answered is not part of the answer",
     'return sha256_json({"method": method, "method_version": version, "answer": result})',
     'return sha256_json({"answer": result})'),
    (CORRECTIONS, "the same answer to another question is withheld",
     'and r["sensor"] is not None and r["sensor"] == reading["sensor"]))]', 'and r["sensor"] is not None))]'),
    # F3: a compilation that held no answer is no failed replication; one that refuted the claim is
    (CORRECTIONS, "a timeout or a stopped worker on a later mission is a failed replication",
     'and output.get("state") in ABSTAINED', 'and output.get("state") == "CAPABILITY_DEFICIT"'),
    # one reader of "did this reading answer": greg.missions.unanswered. What it calls unanswered is neither blamed
    # nor credited here (a mutant of REFUTED would be that reader's: this module asks it and decides nothing itself)
    (CORRECTIONS, "a reading the canonical reader calls unanswered is counted as a failed replication",
     "    if unanswered(output) is not None:\n        return True\n", ""),
    (CORRECTIONS, "a reading the canonical reader calls unanswered requalifies a cause",
     '\n                    and not later["unanswered"]         # a reading that held no answer requalifies nothing', ""),
    (CORRECTIONS, "a reading the canonical reader calls unanswered carries an answer to compare",
     "if not isinstance(output, dict) or held_no_answer(output):\n        return None",
     "if not isinstance(output, dict):\n        return None"),
    # F4 and F8: containment does not depend on which tick recorded what
    (CORRECTIONS, "a rejection waits for a tick to record a correction before it withholds anything",
     'if journal.replay("evidence.correction") or signed_rejections(journal):', 'if journal.replay("evidence.correction"):'),
    (CORRECTIONS, "a dependent that appears after the correction was recorded is not contained",
     "if root in index.by_receipt else {}\n            path", "if root in index.by_receipt and not stored else {}\n            path"),
    # F5: what a rejection rejects, and a rejection that names no reading is not silent
    (CORRECTIONS, "a rejected reading maps to nothing",
     '            return "reading", [self.by_event[target]]', '            return "reading", []'),
    (CORRECTIONS, "a rejected failure closure maps to nothing", 'return "failure closure", out',
     'return "failure closure", []'),
    (TRIBUNAL, "a signed critique's result does not say what it withheld or lifted, or that it changed no credit",
     "    effect = corrections.critique_effect(journal, record)\n", "    effect = None\n"),
    (SETTLEMENT, "a failure the founder rejected still counts against the method",
     "        if why is None:\n            observations[identity] = outcome",
     '        if why is None or not outcome["correct"]:\n            observations[identity] = outcome'),
    # F6: routing reliability, the earned level and precedent action evidence; a rejection only lowers them
    (ROUTING, "routing reliability still counts a rejected mission's runs",
     'elif data["status"] in SUCCESS and data.get("mission_id") in rejected \\', 'elif False \\'),
    (ROUTING, "a founder rejection lifts the penalty of a refuted closure",
     ' \\\n                and appraisals.get(data.get("mission_id")) != "refuted":', ":"),
    (AUTONOMY, "the earned level still counts a rejected mission's verified runs",
     'if kind == "verified" and p["mission_id"] in rejected:', "if False:"),
    (PRECEDENTS, "a rejected mission's self-reports are still action evidence",
     'if not (a["action_id"] in withheld and a.get("result_class") in POSITIVE)]', "if True]"),
    # F7: only a signed rejection counts, and no record lifts one
    (CORRECTIONS, "a critique row nobody signed is followed, a rejection or an acceptance",
     'signed = accepted.get(e.payload.get("command_digest")) if e.payload.get("command_digest") else None',
     'signed = {"verdict": e.payload.get("verdict"), "target_event_id": e.payload.get("target_event_id")}'),
    (CORRECTIONS, "a requalification record with no signed acceptance behind it lifts a founder rejection",
     '    if correction["class"] == "FOUNDER_REJECTED":\n        return correction["cause_id"] not in standing\n', ""),
    # the founder's decision of 2026-11-12: explicit requalification by his own signed acceptance, scoped to the answer
    (CORRECTIONS, "the founder's signed acceptance does not lift his rejection",
     "for key in [k for k in standing if k[1] in accepted]:", "for key in []:"),
    (CORRECTIONS, "an acceptance lifts his rejections of other answers too",
     "for key in [k for k in standing if k[1] in accepted]:", "for key in list(standing):"),
    (CORRECTIONS, "the requalification is not recorded with its cause and the command it came from",
     'return None if by is None else {"event_id": by.event_id', 'return None if True else {"event_id": by.event_id'),
    (CORRECTIONS, "a withholding does not name the rejection and the answer it withholds",
     'why(cid, "FOUNDER_REJECTED", rejection=e.payload.get("critique_id"),\n'
     '                        answer=index.identity(reading))', 'why(cid, "FOUNDER_REJECTED")'),
    # F9: the reviewer's surviving mutants (R11 is superseded by the F3 mutants above)
    (SETTLEMENT, "R1: the construction branch skips the containment filter",
     "            identity = settle(outcome, data) if outcome is not None else None",
     "            identity = (observations.__setitem__(_outcome_identity(outcome), outcome) or "
     "_outcome_identity(outcome)) if outcome is not None else None"),
    (SETTLEMENT, "R3: once withheld, a later reading that no correction contains never settles the claim again",
     "        if why is None:\n            observations[identity] = outcome",
     "        if why is None and identity not in withheld:\n            observations[identity] = outcome"),
    (SETTLEMENT, "R4: the invalidating revision names the wrong class of cause",
     '"class": why["cause"], "event": why["event"],', '"class": "FOUNDER_REJECTED", "event": why["event"],'),
    (CORRECTIONS, "R7: only the root reading is listed, not the receipts of the actions that bound it",
     'for r in [*reached.get("receipts", []), *(stored.get("receipts") or [])]:', "for r in [root]:"),
    (CORRECTIONS, "R8: a standing mission's hold is never a contained mission",
     'out["missions"].setdefault(claim["mission_id"], why)',
     'out["missions"].setdefault(claim["mission_id"], why) if claim["kind"] == "achieved" else None'),
    # review of 0a9a246f (2026-11-12): N4, N5, N6, N9, N10 and a forged correction row
    (CORRECTIONS, "N4: another mission that only asked the rejected computation loses its runs' credit",
     '"answer_only": not acted and cited <= shared}', '"answer_only": False}'),
    (CORRECTIONS, "N4: the readers of run credit ignore that a claim was reached by the answer only",
     'if cls == "FOUNDER_REJECTED" and not claim.get("answer_only"):', 'if cls == "FOUNDER_REJECTED":'),
    (CORRECTIONS, "N4: a mission found later to act on the rejected answer keeps its runs' credit",
     '                        known["answer_only"] = False\n                        frontier = True\n',
     "                        pass\n"),
    (CORRECTIONS, "N4: the command result does not say whose runs it withholds",
     '        runs.update(c["mission_id"] for c in affected["claims"] if not c.get("answer_only"))',
     '        runs.update(c["mission_id"] for c in affected["claims"])'),
    (CORRECTIONS, "N5: a problem_id is read as part of the question: a relabelled rejected answer escapes",
     'LABEL_PARAMS = ("problem_id",)', "LABEL_PARAMS = ()"),
    (CORRECTIONS, "N6: a later run whose own answer the verifier refuted is a failed replication",
     ' or later["unanswered"] \\\n                            or later["refuted"]:',
     ' or later["unanswered"]:'),
    (CORRECTIONS, "N6: a method receipt the verifier refuted is a failed replication",
     '        return output.get("abstention_state") == "REFUTED" \\\n', "        return False and None \\\n"),
    (CORRECTIONS, "N6: a compilation that refuted the claim with a counterexample is read as its own refuted run",
     '    return output.get("state") == "REFUTED" and output.get("result") is None',
     '    return output.get("state") == "REFUTED"'),
    (PRECEDENTS, "N9: a rejection withholds a negative self-report too",
     'a["action_id"] in withheld and a.get("result_class") in POSITIVE', 'a["action_id"] in withheld'),
    (CORRECTIONS, "N10: the report does not say who signed a rejection",
     '"signed_by": signers.get(e.payload.get("command_digest"))}', '"signed_by": None}'),
    (CORRECTIONS, "N10: the report does not say who signed a requalification",
     '"requalified_by_signer": signers.get(by.payload.get("command_digest"))}', '"requalified_by_signer": None}'),
    (CORRECTIONS, "a bare requalification row stands in for the real one and blocks it",
     '    return by.get("receipt") in index.by_receipt or by.get("kind") == "founder-signed acceptance"',
     "    return record is not None"),
    (CORRECTIONS, "a recorded correction the readings do not produce withholds credit",
     ' and c["class"] != "FOUNDER_REJECTED" and cid in derived]', ' and c["class"] != "FOUNDER_REJECTED"]'),
    (SETTLEMENT, "R16: an outcome that fell for another reason is blamed on some correction",
     "            why = withheld.get(identity)          # a correction",
     "            why = withheld.get(identity) or next(iter(withheld.values()), None)          # a correction"),
]


def main() -> int:
    return run(MUTANTS, TESTS, prefix="evidence-corrections-mutants-", root=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
