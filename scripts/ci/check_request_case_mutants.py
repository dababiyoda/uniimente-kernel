"""Each decision point of a request-led case (greg/cases.py, and the engine, authority, statement, template and appraiser
lines it relies on) must fail a behavioural test in tests/unit/test_greg_request_case.py when removed: the three-valued
combination, conflict detection, duplicate detection, the separation of estimates from reconciled actuals, and the
2026-11-12 review fixes (reference matching, measured-only lapses, refused receipts, payment GREG cannot settle on,
undecidable rules, the decline route, absence and unread conflicts shown) among them.

    python scripts/ci/check_request_case_mutants.py

Mutants are applied in a scratch copy of the repository, never to the working tree; the copy runs without bytecode and
its __pycache__ is purged before each mutant (scripts/ci/mutation_harness.py). A mutant is caught only when the test
file reports a FAILED test; an import or collection error does not count. Exit status 1 if any mutant survives or no
longer applies.
"""
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
TESTS = "tests/unit/test_greg_request_case.py"
# (name, target, old, new): the target is written out so scripts/repo_review.py checks every anchor still exists
MUTANTS = [
    # three-valued combination
    ("an unknown rule is read as met", "greg/cases.py",
     '"undetermined" if any(r["state"] == "unknown" for r in rules)', '"undetermined" if False'),
    ("a failed rule waits on what is still unknown", "greg/cases.py",
     'eligibility = "ineligible" if failed else',
     'eligibility = "ineligible" if failed and not any(r["state"] == "unknown" for r in rules) else'),
    ("an undetermined eligibility is a decided field", "greg/cases.py",
     '("eligibility", eligibility == "undetermined"),', '("eligibility", False),'),
    ("a declined case is asked for its unknown facts", "greg/cases.py",
     '    if eligibility != "ineligible":\n        gaps = ', '    if True:\n        gaps = '),
    # conflict detection
    ("two documents that disagree are not a conflict", "greg/cases.py",
     'state = ("conflict" if len(distinct) > 1 else', 'state = ("conflict" if False else'),
    ("a rule silently picks one of two conflicting values", "greg/cases.py",
     '            conflicts.append(fact)\n            continue\n', '            pass\n'),
    # duplicate detection
    ("an earlier case for the same reference is not found", "greg/cases.py",
     'if theirs is not None and reference_key(theirs) == wanted:', 'if False:'),
    ("only a case the template made is an earlier case", "greg/cases.py",
     'theirs = case_reference(data.get("spec") or {})',
     'theirs = case_reference(data.get("spec") or {}) if ((data.get("spec") or {}).get("provenance") or {}).get('
     '"origin") == "template:request-case" else None'),
    ("a reference written with a non-breaking hyphen is another reference", "greg/business_loop.py",
     'kept = ("-" if unicodedata.category(c) == "Pd" or c in _MINUS else c for c in folded',
     'kept = (c for c in folded'),
    ("a reference in full-width digits is another reference", "greg/business_loop.py",
     'folded = unicodedata.normalize("NFKC", unicodedata.normalize("NFKC", str(text)).casefold())',
     'folded = str(text).casefold()'),
    ("a longer reference carries this one", "greg/business_loop.py",
     'after = r"(?![^\\W_])" if re.match(r"[^\\W_]", wanted[-1]) else ""', 'after = ""'),
    ("a posting for a longer reference is counted as this case's payment", "greg/business_loop.py",
     '        if not carries_reference(row.get(columns["reference"]) or "", reference):\n            continue',
     '        if False:\n            continue'),
    ("a settled earlier case is not counted", "greg/cases.py",
     'if state in ("open", "settled"):', 'if state == "open":'),
    ("an abandoned case still counts", "greg/cases.py",
     'elif event.type == "greg.mission.lifecycle" and data.get("state") in ("ABANDONED", "SUPERSEDED"):',
     'elif False:'),
    ("a case registered later counts as earlier", "greg/cases.py",
     'earlier = earlier and mid != mission_id', 'earlier = True'),
    ("a duplicate counts the earlier case's payment", "greg/cases.py",
     '    if duplicates:\n        # a posting', '    if False:\n        # a posting'),
    # the estimate/actual separation
    ("the estimate fills the actual column", "greg/cases.py",
     '"actual": [payment["actual"]] if payment["state"] == "observed" else [],',
     '"actual": [payment["actual"]] if payment["state"] == "observed" else estimate,'),
    ("the actual amount is the estimate, not the statement row", "greg/cases.py",
     'actual = parse_amount(str(posting.get("amount")), minor_units=bool(params.get("minor_units")))',
     'actual = amount'),
    ("the actual currency is the estimate's", "greg/cases.py",
     '"currency": posting.get("currency"),', '"currency": currency,'),
    ("the statement row's own values are not returned", "greg/business_loop.py",
     '"posting": {name: row.get(column) for name, column in columns.items()},', ''),
    ("an unreadable statement reads as payment not observed", "greg/cases.py",
     '    if seen.get("complete") is False:\n        return {**expected, "state": "unknown", "observed": False, '
     '"decided": False,',
     '    if seen.get("complete") is False:\n        return {**expected, "state": "unknown", "observed": False, '
     '"decided": True,'),
    # text is data; the rulebook is the signed one, in its own language
    ("a quarantined document still gives facts", "greg/cases.py", '    if quarantines(flags):', '    if False:'),
    ("a rulebook changed since signing is used", "greg/cases.py",
     '    if hashlib.sha256(raw).hexdigest() != signed:', '    if False:'),
    ("a rule may read a fact it does not list", "greg/cases.py",
     '            if not _names(item.get("condition")) <= set(needs):', '            if False:'),
    ("a condition may use anything Python parses", "greg/cases.py",
     '        if not isinstance(node, allowed):', '        if False:'),
    # packets: never overwritten, re-rendered by the appraiser
    ("a different packet already on disk is taken as this one", "greg/cases.py",
     '    if on_disk != files:', '    if False:'),
    ("the appraiser accepts a changed packet", "greg/cases.py",
     '        if not path.is_file() or path.read_bytes() != data:', '        if not path.is_file():'),
    ("the appraiser re-reads a case without the body's ledger", "greg/appraisal.py",
     '"organ.", "foundry.", "case."))', '"organ.", "foundry."))'),
    # the engine: a person sees what is missing, and is not left asked for a step whose precondition lapsed
    ("a person's ask does not show what the check still lacks", "greg/missions.py",
     '        return {"last_read": {"field": check["predicate"].get("field", ""), **params_view(value)}}',
     '        return {}'),
    ("a person stays asked for a step whose precondition no longer holds", "greg/missions.py",
     '            lapsed = sorted(set(step.get("requires", [])) & measured_failing)', '            lapsed = []'),
    ("a precondition nothing measured lapses a person's ask", "greg/missions.py",
     '            measured_failing = failing - set(self.sensor_errors) - set(self.unread)',
     '            measured_failing = failing'),
    # one refused sensor shared by several checks: every one of them is unread, none a decided failure
    ("a refused receipt reused reads as done with no output", "greg/authority.py",
     '        if receipt is not None and receipt.payload["result"].get("result_class") != "positive":',
     '        if False:'),
    # the rulebook is applied as written
    ("the rulebook's filter ignores case", "greg/cases.py",
     '        if "only" in spec and not re.search(spec["only"], found.group(2)):',
     '        if "only" in spec and not re.search(spec["only"], found.group(2), re.IGNORECASE):'),
    ("a date compared with text is silently false", "greg/cases.py",
     '        raise _Undecidable(f"{_shown(a)!r} and {_shown(b)!r} are not the same kind of value")',
     '        return False'),
    ("a rule comparing two kinds of value is signed", "greg/cases.py",
     '            _typecheck(item["condition"], facts)', '            pass'),
    ("an acceptance comparing two kinds of value is signed", "greg/cases.py",
     '    _typecheck(acceptance["condition"], facts)', '    pass'),
    ("a rule may look for a value among another kind", "greg/cases.py",
     '                    if a not in (None, "list") and kind is not None and kind != a:', '                    if False:'),
    ("a rule may order text", "greg/cases.py",
     '            elif not isinstance(op, (ast.Eq, ast.NotEq)) and (a or b) in ("text", "truth value", "list"):',
     '            elif False:'),
    # unknown is neither pass nor fail
    ("a rule the facts cannot decide leaves evidence complete decided", "greg/cases.py",
     '("unresolved", bool(undecidable) and not unresolved),', '("unresolved", False),'),
    ("an unreadable claim in another document is ignored", "greg/cases.py",
     '        gaps += [(k, s["reason"]) for k, s in sources.items() if k not in kinds and s["state"] == "unknown"]',
     '        gaps += []'),
    ("a document silent on a fact is an unreadable claim", "greg/cases.py",
     '        return {"state": "silent", "reason": f"{doc[\'file\']} has no {spec[\'from\'][kind]!r} line"}',
     '        return {"state": "unknown", "reason": f"{doc[\'file\']} has no {spec[\'from\'][kind]!r} line"}'),
    ("an ambiguous statement is a decided not-paid", "greg/cases.py",
     'elif seen.get("missing_columns") or seen.get("matches", 0) > 1 or seen.get("near_misses"):',
     'elif seen.get("missing_columns") or seen.get("near_misses"):'),
    ("a statement without the signed columns is a decided not-paid", "greg/cases.py",
     'elif seen.get("missing_columns") or seen.get("matches", 0) > 1', 'elif seen.get("matches", 0) > 1'),
    ("a posting of another amount is a decided not-paid", "greg/cases.py",
     ' or seen.get("matches", 0) > 1 or seen.get("near_misses"):', ' or seen.get("matches", 0) > 1:'),
    ("a statement GREG cannot settle on is a decided not-paid", "greg/cases.py",
     '        return {**expected, "state": "unknown", "observed": False, "decided": False,\n'
     '                "reason": "not known: " + seen["detail"]}',
     '        return {**expected, "state": "unknown", "observed": False, "decided": True,\n'
     '                "reason": "not known: " + seen["detail"]}'),
    ("the statement does not say which signed columns it lacks", "greg/business_loop.py",
     ' "missing_columns": missing,', ''),
    # the rulebook's routes are carried out, and what is shown is what was read
    ("a declined case asks no one", "greg/templates.py",
     'person("decline", "human.decline", ["eligible"], ["packet_current"],',
     'person("decline", "human.decline", ["eligible"], ["packet_current", "accepted"],'),
    ("no acceptance on file is printed as a refusal", "greg/cases.py", '    if files:', '    if False:'),
    ("an optional document not on file is not recorded as absent", "greg/cases.py",
     'shown_absent = {"absent": absent} if absent else {}', 'shown_absent = {}'),
    ("a conflict no rule reads is dropped", "greg/cases.py",
     'for f in sorted(set(facts) - needed)', 'for f in sorted(set())'),
    ("a figure a document states unreadably is left out of the estimate", "greg/cases.py",
     '                 for kind, s in record["sources"].items() if s["state"] == "unknown"]',
     '                 for kind, s in record["sources"].items() if False]'),
]


if __name__ == "__main__":
    raise SystemExit(run([(target, name, old, new) for name, target, old, new in MUTANTS], TESTS,
                         "greg-request-case-mutants-"))
