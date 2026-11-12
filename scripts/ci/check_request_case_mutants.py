"""Each decision point of a request-led case (greg/cases.py, and the engine and appraiser lines it relies on) must fail a
behavioural test in tests/unit/test_greg_request_case.py when removed: the three-valued combination, conflict
detection, duplicate detection and the separation of estimates from reconciled actuals among them.

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
     '    if eligibility != "ineligible":', '    if True:'),
    # conflict detection
    ("two documents that disagree are not a conflict", "greg/cases.py",
     'state = ("conflict" if len(distinct) > 1 else', 'state = ("conflict" if False else'),
    ("a rule silently picks one of two conflicting values", "greg/cases.py",
     '            conflicts.append(fact)\n            continue\n', '            pass\n'),
    # duplicate detection
    ("an earlier case for the same reference is not found", "greg/cases.py",
     'if provenance.get("origin") == "template:request-case" \\', 'if False \\'),
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
     '            lapsed = sorted(set(step.get("requires", [])) & failing)', '            lapsed = []'),
]


if __name__ == "__main__":
    raise SystemExit(run([(target, name, old, new) for name, target, old, new in MUTANTS], TESTS,
                         "greg-request-case-mutants-"))
