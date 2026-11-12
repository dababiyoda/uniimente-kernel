"""Each reader of an appraisal must fail its tests when it takes the mission's latest record again instead of the
appraisal of the closure it means (founder ruling of 2026-11-12: "Bind an appraisal to the specific closure and
evidence it actually evaluates. A stale appraisal cannot qualify a different closure").

    python scripts/ci/check_appraisal_closure_readers_mutants.py

One mutant per reader (greg/sop.py, greg/metrics.py, greg/routing.py, greg/cognition/settlement.py,
greg/acceptance.py, greg/autonomy.py, greg/goal_gravity.py), and for the one reader they all ask
(greg/appraisal.py ``standings``): how a record that names no closure is read, and which of several appraisals of one
closure stands. Mutants are applied in a scratch copy of the repository, never to the working tree. The copy runs
without bytecode and its __pycache__ is purged before each mutant. A mutant is caught only when
tests/unit/test_greg_appraisal_closure_readers.py reports a FAILED test (an import or collection error does not
count). The hand-ordered tests come first in that file, so all but the last mutant are caught in seconds; the last
needs a real body. Exit status 1 if any mutant survives or no longer applies.
"""
from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

APPRAISAL = "greg/appraisal.py"
SOP = "greg/sop.py"
METRICS = "greg/metrics.py"
ROUTING = "greg/routing.py"
SETTLEMENT = "greg/cognition/settlement.py"
ACCEPTANCE = "greg/acceptance.py"
AUTONOMY = "greg/autonomy.py"
GOAL_GRAVITY = "greg/goal_gravity.py"
TESTS = "tests/unit/test_greg_appraisal_closure_readers.py"
LATEST = 'for e in journal.replay("mission.appraised") if book.named_by(e.event_id)'
MUTANTS = [
    # each reader takes the mission's latest record again, whatever closure it judged
    (SOP, "the SOP readers take the mission's latest appraisal, whatever closure it judged",
     '    return standings(journal).current_records()\n',
     '    book = standings(journal)\n'
     '    return {e.payload["mission_id"]: (book.named_by(e.event_id), e) ' + LATEST + '}\n'),
    (METRICS, "VEPMC and the sandbox closure read the mission's latest appraisal, not the achievement's",
     '        closure = book.achievement(mission_id)\n',
     '        closure = ([None] + [book.named_by(e.event_id) for e in journal.replay("mission.appraised")\n'
     '                             if e.payload.get("mission_id") == mission_id])[-1]\n'),
    (ROUTING, "an earlier closure's verdict reaches a run a later closure covers",
     '    closure = covering[-1] if covering else None\n', '    closure = covering[0] if covering else None\n'),
    (ROUTING, "the mission's newest closure judges every run, whatever its window",
     '    covering = book.covering(mission_id, book.pos.get(event_id, -1))\n',
     '    covering = book.of(mission_id)\n'),
    (SETTLEMENT, "a mission's readings settle under its latest appraisal, whatever closure it judged",
     '    for mid, (closure, _) in book.current_records().items():\n',
     '    for mid, closure in {e.payload["mission_id"]: book.named_by(e.event_id)\n'
     '                         ' + LATEST + '}.items():\n'),
    (SETTLEMENT, "every reading settles under the mission's newest closure, whichever closure claimed it",
     '        return _settles(book.following(mid, at) or closures[-1])\n',
     '        return _settles(closures[-1])\n'),
    (ACCEPTANCE, "the acceptance report reads the mission's latest appraisal, not the achievement's",
     '        appraised = {m: book.achievement(m).verdict for m in achieved}\n',
     '        appraised = {e.payload["mission_id"]: e.payload["verdict"] for e in journal.replay("mission.appraised")}\n'),
    (AUTONOMY, "a later closure judges a run whose own closure is not appraised yet",
     '            if closure.event_id is None:\n                continue\n            stands = closure.standing\n',
     '            if closure.event_id is None or not closure.appraisals:\n                continue\n'
     '            stands = closure.standing\n'),
    # the one reader: several appraisals of one closure, and records that name no closure
    (APPRAISAL, "the first appraisal of a closure stands, not its final one",
     '        return self.appraisals[-1] if self.appraisals else None\n',
     '        return self.appraisals[0] if self.appraisals else None\n'),
    (APPRAISAL, "a record that names no closure counts for nothing (records from before closures were named)",
     '        closure = by_event.get(wanted) if wanted else achievement.get(mid)\n',
     '        closure = by_event.get(wanted) if wanted else None\n'),
    (APPRAISAL, "a record that names no closure is dropped when the ledger holds no achievement",
     '        if not event.payload.get("closure_event") and mid not in achieved:\n', '        if False:\n'),
    # last: caught by the first test on a real body
    (GOAL_GRAVITY, "an appraisal of another closure moves the mission's appraised_verified reading",
     '            if stands is not None and stands.event_id == rec.payload["event_id"]:\n', '            if True:\n'),
]

if __name__ == "__main__":
    raise SystemExit(run(MUTANTS, TESTS, prefix="greg-appraisal-closure-readers-mutants-"))
