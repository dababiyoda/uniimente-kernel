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
   - *Upgrade from `917404cf` (second review of #219, F1; fixed in #221):* S10 later dropped the engine label and
     other provenance fields from the version digest, so records written by `917404cf` carry an older digest.
     `_historical_identity` now re-derives each record's version from its retained compile receipt, so such a
     record becomes the prior of its successor, a revision, instead of being invalidated with a false reason.
   - *Two `917404cf` versions of one answer* (for example across an engine-label change) re-derive to one identity.
     Since the fixes for the review of #221 (F1-a) and round 3 (F1-r3-1, F1-r3-2), `reconcile` closes every live
     head but the identity's current row: a measured claim's duplicate with a `merged_into` row naming this pass's
     final row, an unmeasured claim's with an invalidation. One live record remains, none after a withdrawal, also
     on a body that `8e91315c` reconciled; later passes write nothing. Re-derivation runs only for rows whose stored
     identity is not measured (F1-b). `receipt_links` follows a merge closure through `merged_into` to the claim's
     latest row (R3-N33).
   - *Open (round 4 of #221):*
     - A duplicate chain invalidated while its claim was unmeasured keeps its receipt on that invalidation after
       the claim settles again; the merged path follows the claim (R4-REC-1, split between its two checks).
     - No test reaches the unmeasured branch, nor a merge followed by a withdrawal (mutants N46 and N32).
     - Counts are unaffected throughout, because competence is recomputed from `measured_outcomes`.
2. **Explicit knowledge states for every answer's world outcome** (`settlement.WORLD_STATES`). Every fact stays on
   the record in every state.

   | State | Meaning | Scoring |
   |---|---|---|
   | `unreported` | no report yet | certificate only |
   | `reported` | one value, possibly corroborated by several sources | that value |
   | `verdict_concordant` | values differ but all give the same verdict under the declared tolerance | that verdict, with no investigation, since resolving it cannot change competence |
   | `disputed` | values give different verdicts | neither, and competence is withheld; an answer whose signed check failed is scored wrong whatever the world value (S6) |
   | `adjudicated` | one value left after a founder-signed resolution | that value |
   | `invalidated` | every report was rejected | certificate only, and the answer awaits a new report |
3. **A founder-signed, traceable resolution on the existing REALIZATION command.** The CLI form is
   `greg realize RECEIPT --resolves E1 --resolves E2 --accept E2 --note <basis>`.
   - It may accept only a recorded report whose reporter declared an independent source (`sensor_observation`,
     `external_record`) and that a verified signed REALIZATION carried (S9), because a signed report proves who
     reported it, not that it is true. Omitting `--accept` invalidates the named reports instead; an
     invalidation must name every live report (S2).
   - An accepting resolution must name every live report that disagrees, and every resolution must state its basis.
   - Settlement counts a resolution only when its digest names a verified REALIZATION envelope whose signed body is
     that resolution (same receipt, resolves and accept), at most once per signed command (S1). One written into the
     journal any other way resolves nothing. Since #221 the envelope must be the founder's (F6; a device key cannot
     sign REALIZATION in any case), and `test_n2_…` covers the once-per-command guard (mutant N2 is caught).
   - Each fact is ruled by the latest-signed resolution that names it, ordered by the envelope's `issued_at` and
     then journal order (S4). A correction can therefore be corrected, and a later resolution never revives a fact
     it does not name. Since #221 (F4) `issued_at` is compared as an instant, and a resolution signed before a
     recorded one that names any of the same facts is refused with the reason, never applied as a silent no-op.
     That includes the case where the earlier one was signed on a clock up to 5 minutes fast (`CLOCK_SKEW`).
   - An equal `issued_at` is accepted and replays last (G4-d). Inbox files are named by a fixed-width UTC stamp
     (`inbox_stamp`, in `send_signed` and the remote intake), so the inbox is read in signing order (G4-a). Both
     are fixes for the review of #221; since round 3 a test drives each writer (G4F7-1).
   - A later report that disagrees reopens the dispute.
4. **Corroboration is kept.** The same value from another source used to be dropped as a repeat, so an independent
   confirmation lost its source. It is now kept as a corroborating fact. Run 1 of the experiment found this defect
   (below).
5. **A dispute is investigable work** (`awaiting_realization`, `kind: objective_conflict`). Each dispute row gives:
   - the reports, with each one's source and verdict;
   - the distinguishing observation, e.g. "at or above 1.9 it kept its promise";
   - whether a resolution can be prepared now, which needs exactly one value held by reports that are declared
     independent and carried by a verified signed REALIZATION; in that case the row carries the unsigned
     REALIZATION body the founder would sign;
   - otherwise, an evidence request that says exactly what record to obtain and how. No capability on a body
     declares an observation of these world quantities, so GREG asks for the record rather than guessing it.
6. **Decision value decides priority.** `_weigh_investigations` walks each method's settled counts over every
   resolution of its open disputes: now, and each number of them kept (F2-b). It then asks whether the inhibition
   rule, the compiler's settled-outcome preference (`_settled_preference`: one-sided Fisher tests with Holm), or
   the Laplace rank differs across those states, and whether resolving the disputes lifts the method from below
   the 10-outcome floor to at least 10.
   - Since #221 the preference runs over every family of co-eligible fits with at least 10 settled outcomes, each
     member ranked first in turn and demoted fits last, as `_rank` orders them, so Holm adjusts over the family
     the compiler would form (F2, F2-d).
   - Other disputed methods are walked with it at every count they can reach, with any number of their disputes
     resolved (F2-c; round 3, F2R-1).
   - Above 8 such fits, 3 other disputed methods or 256 joint states of them, the walk is cut short. The row then
     reads `investigate` with the limit in `decision_impact.walk_limits`, apart from the changes found, and says the
     walk could not be completed (F2-a; round 3, F2R-3).
   - The Laplace rank is compared with every settled method, with each value another disputed method can reach,
     with an unsettled fit (which the compiler reads at 1/2) and with a tie at either bound (S8, F3, F2-c; round
     3, F2R-2).
   - Only disputes whose mission holds a settling appraisal and whose signed check passed are weighed (S6, S7).
     The others are `hold`, and the row says why.
   - If one rule differs, the row is `priority: investigate`; otherwise `hold`, kept on record and weighed again as
     evidence accrues.
   - Fixed in #221: the gaps F2 and F3 above, and F5: a signed report is no longer absorbed by an unsigned fact
     with the same source and value.
   - The review of #221's gaps F2-a to F2-d and round 3's F2R-1 to F2R-3 and F2R-5 are fixed. Open (round 4 of #221):
     - a disputed method with no settled outcome is never in the preference walk, so another row can read a false
       `hold` (W4-4; needs 10 or more open disputes on that method);
     - the inhibition check compares the demotion texts, which carry the counts, so a method demoted at every
       reachable count reads `investigate` (W4-3, since `8e91315c`);
     - the full walk is 4 to 10 times slower than at `5b4e293f` on maps inside the limits, and the 256-state limit
       cuts the whole walk on about 30% of random rows, naming both limits (W4-1, W4-2, W4-7).
   - Most disputes now read `investigate`, by design: the rule errs toward it, since a false `investigate` costs
     one outside record and a false `hold` hides a decision change.
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

## The decisive experiment: run 1 failed prediction 3; after a defect fix, run 2 met predictions 1-4, 6 and 7 and missed 5 and 8 as worded

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

**Run 2** (corrected 2026-10-28 after the cross-session re-review, and again 2026-10-29 after the second review;
see [REVIEW-FIXES.md](REVIEW-FIXES.md)):
- **1, 2:** see the table. A signed mission after the corrections also selects `flow_maxflow`. As a check added
  after the run, the test also asserts that the compiler's existing selection rule made the choice: its
  settled-outcome preference names the construction `against` and `flow_maxflow` `preferred`, at selection level
  `preferred_by_settled_outcomes` (the compiler's selection rules are unchanged since `3886d727`; #221's
  `72f57753` only memoizes the Fisher p-value, with the same results). The frozen rule,
  which scores the selected method by its declared true rate, is unchanged.
- **3:** all 20 facts are kept.
- **4:** before resolution the disputed answers score nothing. The following are refused or ignored:
  - a resolution accepting the founder's report;
  - a resolution with no basis;
  - a resolution written without a founder-signed command (recorded, resolves nothing).
- **5: missed as worded.** The declaration said "(4 correct of 10)" for the method; the method total is (5 of 11).
  What held:
  - the ten reported claims settle at 4 correct of 10;
  - the settlement records exactly six adjudicated revisions (one per corrected claim, each superseding its
    prior record), and a second `reconcile` adds none.
  - *Disclosure:* the declaration said the method's competence would be "(4 correct of 10)". The method total is
    (5 of 11), because the mission that prediction 6 requires answered once with the construction. The ten
    reported claims are (4 of 10); six of them were corrected. The declaration omitted that answer from the count;
    no rule changed.
- **6:** the mission decided on contested evidence is listed once in `decisions_to_recheck`.
- **7:** Goal Gravity shows 6 disputes to investigate before the corrections and 0 after.
- **8: missed as worded on one point.** The declaration said "other than the two founder attaches"; the setup
  records three attaches: one founder command and two founder-signed mission `auto_attach` (read only). The test
  now asserts that list as recorded. The rest held: after the setup no capability state changes, nothing creates
  authority, nothing is spent, and the evaluation fixture is byte-identical.

**Before the change** ([before-8c431b85.txt](before-8c431b85.txt)), on the pre-change tree:
- 18 of the new or updated tests fail: the experiment, all 13 resolution tests, the two attribution tests, the
  corroboration expectation and the gravity count.
- 58 tests pass on both trees.

**Further evidence:**
- **On the code after the review fixes (`b1a3c1af` and later):**
  - [run-final.txt](run-final.txt): the experiment and five related files at `b1a3c1af`, 94 passed, bound to the
    test file's sha256.
  - [integrator-intake-runs.txt](integrator-intake-runs.txt): the integrator's intake on `0bf8528c`: the
    goal_gravity, Goal Gravity, founder and mission suites (527 passed, 5 skipped), and CI job 8's whole set plus
    the combined test with real organs (117 passed, 1 skipped).
  - [mutants-review.txt](mutants-review.txt): the review fixes' mutants, run with
    [mutants-review.py](mutants-review.py) on a clean tree and bound to its commit. Re-recorded after the fixes for
    round 3 of the review of #221, at #221's `399c6c08` (N37-N51 added): 45 of 51 caught, 0 invalid.
    - N6 (S3's fact key) is harmless on the production path since F5.
    - Five are MISSED, each changing what is written or said with no test for it: N32 (a merged shadow closed again
      after a withdrawal), N38 (the 256-state limit), N43 (the fit ranked first), N46 (an unmeasured claim's
      duplicate) and N49 (an appraised held closure's text).
    - Earlier records are in git history:
      - `934a5125`: at #221's `5b4e293f`, 32 of 36 caught;
      - `f0094388`: at #221's `5983deeb`, 22 of 24 caught;
      - `be8fbd09`: at #196's `8e91315c`, 13 of 14 caught, N2 missed.
    - The first record counted N9, which did not compile, as caught (second review R3).
- **Not bound to any code:** [broad-review-fixes.txt](broad-review-fixes.txt), a snapshot taken before `b1a3c1af`
  that names no commit or command: 1 failed (the experiment test itself: a `TypeError` in its stale `_resolutions`
  stand-in, fixed in `b1a3c1af`), 750 passed, 1 skipped.
- **On the code before the review fixes:**
  - [after.txt](after.txt): every settlement-touching test passes on `050e2e42` (463 passed, 1 skipped).
  - [mutants.txt](mutants.txt): 8 of 8 safeguard mutants caught at `90c1b118`, using [mutants.py](mutants.py).
    From `b1a3c1af` the targets of M2 and M6 no longer exist, so that script cannot run on later code. The mutants
    covered:
    - identity without the answer version;
    - a resolution with no accepted founder command;
    - accepting a non-independent source, both at replay and at record time;
    - reviving facts a resolution did not name;
    - treating concordant values as disputed;
    - dropping corroboration;
    - accepting a partial resolution.
  - [combined-candidate-job8.txt](combined-candidate-job8.txt): CI job 8's whole set plus the combined test,
    with real organs, run on both trees:
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
| Restricted | only a recorded report declared as an independent source, and carried by a REALIZATION the founder signed (F6, since #221), can be accepted; every disagreeing report must be named; an invalidation must name every live report; a basis must be stated |
| Revoked | a later resolution rules again on any fact it names |
| Repaired downstream | `decisions_to_recheck` names the decisions that rested on the rejected evidence |

## What GREG can do now that it could not before

When two reports about a completed construction disagree, the body now does the following:

1. It names the claim, the answer and the disputed verdicts.
2. It states the observation that would decide between them.
3. It prepares the correction when exactly one value is held by reports declared as independent and carried by a REALIZATION the founder signed, or asks for that record otherwise.
4. It weighs whether resolving the dispute can change any selection.
5. It withholds competence until the dispute is resolved, unless the answer's signed check failed: that answer is scored wrong whatever the world value.

After the founder signs a correction that accepts a report declared as an independent source, the corrected competence reaches the
compiler's existing selection rule, and a later decision changes: in the declared world it moves from the
construction (true rate 0.4) to `flow_maxflow` (1.0). The decision made on contested evidence is flagged for
recheck. With the repair disabled, the same history leaves the worse decision in place.

## Limits

- Laboratory tier only: declared world values, a scripted founder who signs every prepared resolution, and a
  fixture evidence index that ranks the construction first.
  - The experiment shows that the mechanism carries a legitimate correction into a decision.
  - It is not a measured real-world learning dividend.
- The decision value is an estimate. Since #221 the preference is checked with Holm over every family of
  co-eligible fits with at least 10 settled outcomes, as the compiler forms it (F2); above 8 such fits, over the
  pairs and the whole family only. It is weighed against every method with settled outcomes and an unsettled fit,
  since co-eligibility depends on the request. The fixes for the review of #221 and its round 3 close F2-a to F2-d
  and F2R-1 to F2R-3; round 4 found the gaps in item 6 (W4-1 to W4-4, W4-7).
- A bounded mission's achievement after an appraised unmet closure is never appraised, and its passing observation
  is then credited under the unmet closure's `VERIFIED_UNMET` (round 4 of #221, TXT-R4-1). `Body._close_out` and
  `_awaiting_appraisal` both treat any appraisal of the mission as judging the achievement. Reproduced at the head
  and at `8e91315c` on a real body; the credit was shown with the check's world change simulated in-process.
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
