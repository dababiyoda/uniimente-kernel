# Correction-driven evidence: a contradiction becomes investigable work, and an authorized correction changes a later decision (2026-10-28)

**Parent:** BODY + ORGANS + MIND = GREG / UNIIMENTE. This increment covers the Mind's outcome learning: settled
competence, Goal Gravity and the compiler's selection from settled outcomes. It does not close the parent.

- **Claim:** [#96 comment 6476826663](https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6476826663),
  session `session_01KucyfnwWG7Lgp8QvCTKeHg`.
- **Assignment:** founder directive of 2026-10-28 on #210, sections 1 to 4: "If that failure is reproducible, fix
  the causal attribution"; build "an explicit, auditable resolution mechanism"; "the new decision must be better
  under a frozen, independent evaluation rule".
- **Base:** #196 `9e5a0b09`, merged into #210 at `8c431b85`.
- **Declaration:** [DECLARATION.md](DECLARATION.md), committed and pushed at `3886d727` before the experiment
  existed.

## What changed (all in the existing settlement, CLI, body dispatch and Goal Gravity; no new framework)

1. **Answer-versioned attribution (the alias is fixed).**
   - *Defect, reproduced as a strict xfail at `ec38d8a5`:* a construction's claim identity bound mission, check,
     input, method and version, but not the answer. So a report on one certified answer (promise 2) settled a
     later, different answer of the same check (promise 4), and the later answer stopped being asked for.
   - *Fix:* construction outcomes carry `answer_version`, the digest of the certificate output, which holds no
     timing. `_outcome_identity` includes it.
   - *Result:* a changed answer is its own claim and inherits nothing. Re-observing an unchanged answer still
     settles once, so competence is not inflated.
   - *Legacy records:* settlement records written before this have no answer version. `reconcile` records each
     one's answer-versioned successor as a revision that supersedes it, rather than listing it as invalid.
2. **Explicit knowledge states for every answer's world outcome** (`settlement.WORLD_STATES`). Every fact stays on
   the record in every state.

   | State | Meaning | Scoring |
   |---|---|---|
   | `unreported` | no report yet | certificate only |
   | `reported` | one value, possibly corroborated by several sources | that value |
   | `verdict_concordant` | values differ but all give the same verdict under the declared tolerance | that verdict, with no investigation, since resolving it cannot change competence |
   | `disputed` | values give different verdicts | neither; competence is withheld |
   | `adjudicated` | one value left after a founder-signed resolution | that value |
   | `invalidated` | every report was rejected | certificate only, and the answer awaits a new report |
3. **A founder-signed, traceable resolution on the existing REALIZATION command.** The CLI form is
   `greg realize RECEIPT --resolves E1 --resolves E2 --accept E2 --note <basis>`.
   - It may accept only a recorded report whose reporter declared an independent source (`sensor_observation`,
     `external_record`), because a signed report proves who reported it, not that it is true. Omitting `--accept`
     invalidates the named reports instead.
   - It must name every live report that disagrees, and it must state its basis.
   - Settlement counts it only if this body accepted the REALIZATION command it came from. One written into the
     journal any other way resolves nothing.
   - Each fact is ruled by the latest resolution that names it. A correction can therefore be corrected, and a
     later resolution never revives a fact it does not name.
   - A later report that disagrees reopens the dispute.
4. **Corroboration is kept.** The same value from another source used to be dropped as a repeat, so an independent
   confirmation lost its source. It is now kept as a corroborating fact. Run 1 of the experiment found this defect
   (below).
5. **A dispute is investigable work** (`awaiting_realization`, `kind: objective_conflict`). Each dispute row gives:
   - the reports, with each one's source and verdict;
   - the distinguishing observation, e.g. "at or above 1.9 it kept its promise";
   - whether a resolution can be prepared now from a recorded report declared as an independent source, in which case the
     row carries the unsigned REALIZATION body the founder would sign;
   - otherwise, an evidence request that says exactly what record to obtain and how. No capability on a body
     declares an observation of these world quantities, so GREG asks for the record rather than guessing it.
6. **Decision value decides priority.** `_weigh_investigations` bounds each method's settled counts between the
   two extreme resolutions of its open disputes. It then asks whether the inhibition rule, the 10-outcome floor,
   or a one-sided Fisher comparison with another method crosses its threshold between those bounds.
   - If one does, the row is `priority: investigate`; otherwise `hold`, kept on record and weighed again as
     evidence accrues.
   - Goal Gravity reports `disputes_to_investigate` and `decisions_to_recheck`.
7. **Dependency-aware memory.** `decisions_to_recheck` lists every compile decision retained while a later-rejected
   report was in force, if it considered the affected method. A decision leaves the list once that problem is
   compiled again.

## Source labels are declared, not verified (integrator review of `67184991`)

`source` is whatever the REALIZATION command declared: a founder can file a value as `external_record` and then
accept it. GREG cannot verify the label. So the rule restricts which reports are *eligible* to be accepted, and every
surface shows the label for what it is:

- dispute rows report `declared_source` and `independence: "declared by the reporter, not verified by GREG"`
  (formerly `independent: true`);
- the constant is `DECLARED_INDEPENDENT_SOURCES`;
- an adjudicated outcome's evidence tier names the accepted source as declared, not verified;
- the CLI help says the same.

`test_a_founder_report_labelled_external_record_is_eligible_but_shown_as_declared_never_verified` pins it. Where this
README says "independent" below, read "declared as independent".

## The decisive experiment: run 1 failed one prediction, then a defect fix, then run 2 passed

The test is `tests/integration/test_outcome_correction_changes_decision.py`. Scenario and frozen rule are in
[DECLARATION.md](DECLARATION.md).

- **The evidence:** ten adversarial `founder_reported` claims that the construction kept its promise, then
  independent `external_record` readings of the declared truth (6 of 10 fell short). In arm C, the founder signs
  each resolution the body prepared.
- **The decision:** what the compiler selects for a later request carrying both input shapes.

| Arm | Evidence | Selected | Score under the frozen rule |
|---|---|---|---|
| A | adversarial reports only | the construction | 0.4 |
| B | independent observations with the repair disabled (#210 `ec38d8a5` behaviour) | the construction | 0.4 |
| B, after step 3 | the same history with resolutions ignored | the construction | 0.4 |
| **C** | **authorized corrections** | **`cognition.flow_maxflow`** | **1.0** |

**Run 1** ([run1-failed-prediction-3.txt](run1-failed-prediction-3.txt)) failed **prediction 3**:
- 16 of 20 facts were on record. The four independent readings that agreed with the founder's reports had been
  dropped as repeats.
- Predictions 1, 2 and the first part of 4 had passed before it stopped.
- **Fix:** keep a same-value fact from another source as corroboration (item 4 above). Nothing in the declaration
  changed.

**Run 2** passed every prediction:
- **1, 2:** see the table. A signed mission after the corrections also selects `flow_maxflow`.
- **3:** all 20 facts are kept.
- **4:** before resolution the disputed answers score nothing. The following are refused or ignored:
  - a resolution accepting the founder's report;
  - a resolution with no basis;
  - a resolution written without a founder-signed command (recorded, resolves nothing).
- **5:**
  - the ten corrected claims settle at 4 correct of 10;
  - the settlement records exactly six adjudicated revisions (one per corrected claim, each superseding its
    prior record), and a second `reconcile` adds none.
  - *Disclosure:* the declaration said the method's competence would be "(4 correct of 10)". The method total is
    (5 of 11), because the mission that prediction 6 requires answered once with the construction. The ten
    corrected claims are (4 of 10). The declaration omitted that answer from the count; no rule changed.
- **6:** the mission decided on contested evidence is listed once in `decisions_to_recheck`.
- **7:** Goal Gravity shows 6 disputes to investigate before the corrections and 0 after.
- **8:** after the setup, no capability state changes, nothing creates authority, nothing is spent, and the
  evaluation fixture is byte-identical.

**Before the change** ([before-8c431b85.txt](before-8c431b85.txt)), on the pre-change tree:
- 18 of the new or updated tests fail: the experiment, all 13 resolution tests, the two attribution tests, the
  corroboration expectation and the gravity count.
- 58 tests pass on both trees.

**Further evidence:**
- [after.txt](after.txt): every settlement-touching test passes on `050e2e42` (463 passed, 1 skipped).
- [mutants.txt](mutants.txt): 8 of 8 safeguard mutants caught, using [mutants.py](mutants.py). The mutants
  covered:
  - identity without the answer version;
  - a resolution with no accepted founder command;
  - accepting a non-independent source, both at replay and at record time;
  - reviving facts a resolution did not name;
  - treating concordant values as disputed;
  - dropping corroboration;
  - accepting a partial resolution.
- [combined-candidate-job8.txt](combined-candidate-job8.txt): CI job 8's whole set plus the combined test, with
  real organs, run on both trees:
  - `8c431b85` (#196 `9e5a0b09` + #212 + #210 `ec38d8a5`): 117 passed, 1 skipped (supervisord not installed
    locally);
  - `050e2e42`: 117 passed, 1 skipped.
- `docs/evidence/greg-data-exposure-ledger.json` is rebuilt for the experiment's declared development seed
  (`maxflow_instance(3)`).

## Power, inspection and repair (Spider-Web check)

The new power is the founder's ability to resolve a disputed outcome. Every use of it can be:

| Safeguard | How |
|---|---|
| Inspected | every fact, resolution and rejected event stays on the record |
| Challenged | a later disagreeing report reopens the dispute |
| Restricted | only a recorded report declared as an independent source can be accepted; every disagreeing report must be named; a basis must be stated |
| Revoked | a later resolution rules again on any fact it names |
| Repaired downstream | `decisions_to_recheck` names the decisions that rested on the rejected evidence |

## What GREG can do now that it could not before

When two reports about a completed construction disagree, the body now does the following:

1. It names the claim, the answer and the disputed verdicts.
2. It states the observation that would decide between them.
3. It prepares the correction when a report declared as an independent source already exists, or asks for that record when none does.
4. It weighs whether resolving the dispute can change any selection.
5. It withholds competence until the dispute is resolved.

After the founder signs a correction that accepts a report declared as an independent source, the corrected competence reaches the
compiler's existing selection rule, and a later decision changes: in the declared world it moves from the
construction (true rate 0.4) to `flow_maxflow` (1.0). The decision made on contested evidence is flagged for
recheck. With the repair disabled, the same history leaves the worse decision in place.

## Limits

- Laboratory tier only: declared world values, a scripted founder who signs every prepared resolution, and a
  fixture evidence index that ranks the construction first.
  - The experiment shows that the mechanism carries a legitimate correction into a decision.
  - It is not a measured real-world learning dividend.
- The decision value is an estimate. The Fisher comparison is unadjusted, whereas the compiler applies Holm over
  its challengers.
- The recheck projection compares retained UTC stamps across the ledger and the journal.
- No capability declares an observation of a world objective, so GREG cannot acquire the evidence itself. It asks.
- The #213 transfer experiment, the compiler's selection rules, Genesis, authority and the mission engine are
  unchanged.

## Next capability deficit (measured, not built here)

Every evidence request today ends with `acquirable_by_body: []`: GREG can say exactly what observation would
decide a dispute, but it cannot obtain one.

- **Next increment:** a read-only world-observation capability that the founder attaches with a declared source
  and scope, for example a time-clock export under a read root, or an MCP tool the founder approves. The
  investigation would then prepare a bounded verification mission (a signed check that reads the declared
  record) instead of an ask.
- **Its falsifier:** a dispute that it resolves to the wrong verdict, or a read outside its declared scope.
- **Its subtraction test:** without it, the same dispute stays open.
