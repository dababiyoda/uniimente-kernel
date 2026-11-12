"""Each reader of an appraisal must fail its tests when it takes the mission's latest record again instead of the
appraisal of the closure it means, or when it lets any closure but a run's (or a reading's) own judge it (founder ruling
of 2026-11-12: "Bind an appraisal to the specific closure and evidence it actually evaluates. A stale appraisal
cannot qualify a different closure." "Unreadable evidence remains unknown until reconciled." "A rejected answer
receives no unsupported success credit.").

    python scripts/ci/check_appraisal_closure_readers_mutants.py

Mutants for the one reader (greg/appraisal.py ``standings``): how a record that names no closure is read, which of
several appraisals of one closure stands, the one rule for which closure judges a run or a reading
(``Standings.judging``), and the book kept per journal. Then one or more per reader: greg/sop.py, greg/metrics.py,
greg/routing.py, greg/cognition/settlement.py, greg/acceptance.py, greg/autonomy.py, greg/goal_gravity.py,
greg/cognition/seed_path.py, and the Foundry readers (foundry/systems/reputation.py, twin.py, observability.py,
graph.py, datamodel.py). Mutants are applied in a scratch copy of the repository, never to the working tree. The copy
runs without bytecode and its __pycache__ is purged before each mutant. A mutant is caught only when
tests/unit/test_greg_appraisal_closure_readers.py reports a FAILED test (an import or collection error does not
count). Exit status 1 if any mutant survives or no longer applies.
"""
from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

APPRAISAL = "greg/appraisal.py"
SOP = "greg/sop.py"
METRICS = "greg/metrics.py"
ROUTING = "greg/routing.py"
SETTLEMENT = "greg/cognition/settlement.py"
SEED_PATH = "greg/cognition/seed_path.py"
ACCEPTANCE = "greg/acceptance.py"
AUTONOMY = "greg/autonomy.py"
GOAL_GRAVITY = "greg/goal_gravity.py"
REPUTATION = "foundry/systems/reputation.py"
TWIN = "foundry/systems/twin.py"
OBSERVABILITY = "foundry/systems/observability.py"
GRAPH = "foundry/systems/graph.py"
DATAMODEL = "foundry/systems/datamodel.py"
TESTS = "tests/unit/test_greg_appraisal_closure_readers.py"
LATEST = 'for e in journal.replay("mission.appraised") if book.named_by(e.event_id)'
OWN_CLOSURE = ("        closure = self._by_mission[mission_id][i]\n        if not closure.start < position:\n"
               "            return None\n")
MUTANTS = [
    # the one reader: several appraisals of one closure, and records that name no closure
    (APPRAISAL, "the first appraisal of a closure stands, not its final one",
     '        return self.appraisals[-1] if self.appraisals else None\n',
     '        return self.appraisals[0] if self.appraisals else None\n'),
    (APPRAISAL, "a record that names no closure is not read as the achievement's (records from before closures "
                "were named)",
     '        closure = self._by_event.get(wanted) if wanted else self._achievement.get(mid)\n',
     '        closure = self._by_event.get(wanted) if wanted else None\n'),
    (APPRAISAL, "a record that names no closure is dropped when the ledger holds no achievement before it",
     '        if closure is None and not wanted:      # no achievement on the ledger before it: one it does not hold\n',
     '        if False:\n'),
    (APPRAISAL, "a record that names no closure judges an achievement of an earlier registration",
     '        if kind == "mission.registered":    # a record naming no closure judged this registration\'s achievement\n'
     '            self._achievement.pop(mid, None)\n', ''),
    # the one rule: a run's own closure judges it, a reading only when that closure's appraisal re-derived it
    (APPRAISAL, "the newest closure whose window holds a run judges it, in its own closure's place",
     OWN_CLOSURE,
     "        closure = [c for c in self._by_mission[mission_id][i:] if c.start < position][-1]\n"),
    (APPRAISAL, "a run after the mission's newest closure is judged by that closure",
     '            return None                 # after the mission\'s newest closure: no closure has evaluated it yet\n',
     '            return self._by_mission[mission_id][-1]\n'),
    (APPRAISAL, "a reading taken before a later run of its window is judged by the closure",
     '            if last and runs[last - 1] > closure.start and runs[last - 1] > position:\n',
     '            if False:\n'),
    # the book kept per journal
    (APPRAISAL, "every call folds the journal from scratch: nothing is kept",
     '        kept = _KEPT.get(spine)\n', '        kept = None\n'),
    (APPRAISAL, "what was recorded since the last call is never folded in",
     '                for event in arrived:\n', '                for event in ():\n'),
    (APPRAISAL, "the achievement is found by scanning the mission's closures",
     '        return self._achievement.get(mission_id)\n',
     '        return next((c for c in self.of(mission_id) if c.kind == "achieved"), None)\n'),
    # each reader takes the mission's latest record again, or another closure's verdict
    (SOP, "the SOP readers take the mission's latest appraisal, whatever closure it judged",
     '    return standings(journal).current_records()\n',
     '    book = standings(journal)\n'
     '    return {e.payload["mission_id"]: (book.named_by(e.event_id), e) ' + LATEST + '}\n'),
    (METRICS, "VEPMC and the sandbox closure read the mission's latest appraisal, not the achievement's",
     '        closure = book.achievement(mission_id)\n',
     '        closure = ([None] + [book.named_by(e.event_id) for e in journal.replay("mission.appraised")\n'
     '                             if e.payload.get("mission_id") == mission_id])[-1]\n'),
    (ROUTING, "routing lets the newest closure whose window holds a run judge it",
     '    closure = book.judging(mission_id, book.pos.get(event_id, -1))\n',
     '    closure = ([c for c in book.of(mission_id) if c.start < book.pos.get(event_id, -1) < c.at] or [None])[-1]\n'),
    (ROUTING, "the mission's newest closure judges every run, whatever its window",
     '    closure = book.judging(mission_id, book.pos.get(event_id, -1))\n',
     '    closure = (book.of(mission_id) or [None])[-1]\n'),
    (SETTLEMENT, "a mission's readings settle under its latest appraisal, whatever closure it judged",
     '    for mid, (closure, _) in book.current_records().items():\n',
     '    for mid, closure in {e.payload["mission_id"]: book.named_by(e.event_id)\n'
     '                         ' + LATEST + '}.items():\n'),
    (SETTLEMENT, "every reading settles under the mission's newest closure, whichever closure claimed it",
     '        closure = book.judging(event.payload.get("mission_id"), book.pos.get(event.event_id), reading=True)\n',
     '        closure = (book.of(event.payload.get("mission_id")) or [None])[-1]\n'),
    (SETTLEMENT, "a reading is judged as a run: one a later run of its window superseded still settles",
     '        closure = book.judging(event.payload.get("mission_id"), book.pos.get(event.event_id), reading=True)\n',
     '        closure = book.judging(event.payload.get("mission_id"), book.pos.get(event.event_id))\n'),
    (ACCEPTANCE, "the acceptance report reads the mission's latest appraisal, not the achievement's",
     '        appraised = {m: book.achievement(m).verdict for m in achieved}\n',
     '        appraised = {e.payload["mission_id"]: e.payload["verdict"] for e in journal.replay("mission.appraised")}\n'),
    (AUTONOMY, "a later closure judges a run whose own closure is not appraised yet",
     '            closure = closures.judging(p["mission_id"], at)\n',
     '            closure = next((c for c in closures.of(p["mission_id"]) if c.start < at < c.at\n'
     '                            and c.standing is not None), None)\n'),
    (AUTONOMY, "a refuted closure charges every run its window holds, also runs another closure judged",
     '        closure = book.judging(run.payload["mission_id"], book.pos.get(run.event_id, -1))\n',
     '        closure = next((c for c in book.of(run.payload["mission_id"])\n'
     '                        if c.start < book.pos.get(run.event_id, -1) < c.at and c.verdict == "REFUTED"), None)\n'),
    (SEED_PATH, "any VERIFIED appraisal of the mission qualifies a computation as verified",
     '        if own is None or own.event_id not in refs:    # recorded after its closure, so after the receipt\n',
     '        if not any(book.named_by(r) is not None and book.named_by(r).verified() for r in refs):\n'),
    # the Foundry readers
    (REPUTATION, "a closure's verdict reaches every run of its mission",
     '            closure = book.judging(p.get("mission_id"), book.pos.get(e["event_id"]))\n'
     '            stands = closure.standing if closure is not None else None\n'
     '            if stands is not None:\n',
     '            for closure in book.of(p.get("mission_id")):\n'
     '                stands = closure.standing\n'
     '                if stands is not None:\n'),
    (REPUTATION, "every appraisal of a closure is an outcome, an UNAVAILABLE answer included",
     '        if e["type"].removeprefix("greg.") == "mission.appraised" and e["event_id"] in judged:\n',
     '        named = book.named_by(e["event_id"]) if e["type"].endswith("mission.appraised") else None\n'
     '        if named is not None and named.standing is not None and named.standing.event_id in judged:\n'
     '            judged[e["event_id"]] = judged[named.standing.event_id]\n'),
    (TWIN, "an observation takes the last run of the mission, not of the closure",
     '            if closure is not None:\n'
     '                last_run[id(closure)] = (p.get("capability"), float(p.get("cost_usd") or 0.0))\n',
     '            for closure in book.of(p.get("mission_id")):\n'
     '                last_run[id(closure)] = (p.get("capability"), float(p.get("cost_usd") or 0.0))\n'),
    (TWIN, "every appraisal of a closure is an observation, an UNAVAILABLE answer included",
     '        if stands is None or stands.event_id != e["event_id"] or id(closure) not in last_run:\n',
     '        if closure is None or id(closure) not in last_run:\n'),
    (OBSERVABILITY, "the verified rate counts every appraisal, an UNAVAILABLE answer included",
     '            elif s["kind"] == "mission.appraised" and s.get("stands"):   # each closure\'s standing, once\n',
     '            elif s["kind"] == "mission.appraised":\n'),
    (OBSERVABILITY, "an appraisal's span takes the capability of the mission's last run",
     'capability=p.get("capability") or (judged.get(id(closure)) if closure is not None else None))',
     'capability=p.get("capability") or last_capability.get(mid))'),
    (GRAPH, "an appraisal measures every receipt so far, whatever closure judged its run",
     '            for receipt in measured.get(id(closure), ()) if closure is not None else ():\n',
     '            for receipt in [r for rows in measured.values() for r in rows]:\n'),
    (DATAMODEL, "the mission ledger reads the latest outcome row, whatever closure it judged",
     '        "(SELECT s.verdict FROM standings s WHERE s.mission_id = d.mission_id) AS current_verdict, "\n',
     '        "(SELECT o.verdict FROM outcomes o WHERE o.mission_id = d.mission_id ORDER BY o.at DESC, o.id DESC "\n'
     '        "LIMIT 1) AS current_verdict, "\n'),
    # Goal Gravity: the reading follows the current closure
    (GOAL_GRAVITY, "an unappraised current closure keeps the previous closure's verdict",
     '            if value is None and (held is None or held.value is None):\n', '            if value is None:\n'),
    (GOAL_GRAVITY, "the newest closure with a verdict stands for the mission, not its current closure",
     '            current = book.current(mid)\n',
     '            current = next((c for c in reversed(book.of(mid)) if c.standing is not None), None)\n'),
]

if __name__ == "__main__":
    raise SystemExit(run(MUTANTS, TESTS, prefix="greg-appraisal-closure-readers-mutants-",
                         purge_dirs=("greg", "foundry", "tests")))
