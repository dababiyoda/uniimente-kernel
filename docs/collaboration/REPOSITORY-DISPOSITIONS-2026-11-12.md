# Dispositions and review-found defect classes, 2026-11-12

Session `session_01Kucyfm9exT5imDVYvHTYSv`, written 2026-11-12 02:00 UTC (read from the clock) against the
integration line #196 at `8d20532464b1533b28d71d8331ca3412a90dbb11`. It continues
[the record of 2026-11-11](REPOSITORY-DISPOSITIONS-2026-11-11.md), which stays as written.

The founder's clarification of 2026-11-12 asks each disposition to "record where retained value goes, who consumes
it, what behavior changes, and how that change is verified." The first table does that for what changed since the
earlier record. The second table is new: the classes of defect that independent review or CI found in this
session's own work, kept so that later units can be checked against them.

Everything here was run in a cloud container with test keys. VEPMC is 0. Nothing below is on the integration
line. A composed candidate (#299, `candidate/composed-20261112` at `45c3644b`) holds eleven of these heads on one
tree for checks; it is evidence, not a merge request.

## 1. Where the retained value goes

| Source | Useful mechanism | Disposition | Consumer | Behaviour that changes | How it is verified | State |
|---|---|---|---|---|---|---|
| The revoked-device fix round's own receipt reader (`checkpoint/revoked-device-fix-wip-20261111`) | Look up the Gate's record of a compensation's one proposal before deciding from the capability's state | consolidate | `MissionEngine._run_compensation` on #294, through `AuthorityOffice.outcome_of` | A compensation the Gate completed is recorded done from its receipt when its capability was detached, unavailable, or its approver revoked. Before: asked again, or recorded UNAVAILABLE | 12 cases in `tests/unit/test_greg_retained_receipt_history.py`; 8 mutants; the revoked-device branch's five tests on its merge with #294 | #294 at `1643932e`; the device branch dropped its copy |
| `corrections.contained_receipts` on the line (no production reader) | Which receipts a correction contains | integrate | settlement, procedure proposal and ratification, precedents; in the fix round also routing reliability and the earned-autonomy report | A rejected answer stops earning competence credit | The unit's tests on a real Body; review reproductions | review done (three high findings); fix round running |
| Review of the first replay fix (`e917a0db`) | A fault the Mind names is an unmeasured reading, classified where it is observed | integrate | the retry rounds, self-repair, `blames_strategy`, the failure closure, `_prepare` | No replayed write, no strategy blamed for an instrument's fault, no unseen retry | #298: the reviewer's six probes; gates 9/9, 4/4, 162/0; the cortex gate's groups | #298 at `b9a34259` |
| The appraiser unit's review | A deferred re-read cannot tell a false closure from a world that changed later | integrate | the separate appraiser; then routing, autonomy, procedure trend | A late mismatch is recorded as stale, never as a refutation; a separately valid refutation is kept | The reviewer's two reproductions on the fix round's tree | fix round running |
| The same review, base defect | Several readers take the latest appraisal per mission, whatever closure it judges | preserve for a named unit | `sop.verified_appraisals`, `metrics.vepmc`, `routing.track_record`, `settlement._settling_appraisals`, `acceptance.report` | An appraisal counts only for the closure it names | The reviewer's `p13b_retry_window.py` fails on `8d205324` | not built; revival condition: the appraiser fix round returns its specification |
| The credit unit's review, base defect | A compile receipt carries `state`, not `abstention_state` | integrate | `missions.unanswered`, read by the engine and twice by the appraiser | A host timeout or crash of the solver is retried, not asked about at once and not counted as a failure | Reproduced on `8d205324` (`NO_STRATEGY` on the first pass); acceptance list in the unit's brief | being built on `claude/compile-unanswered-unread-20261112` |
| #296's rehearsal tool | Each head's changed tests on the merged tree, cause by leave-one-out | integrate | this session's intake preparation; the composed candidate | Behavioural conflicts are found before intake | Found three that `git merge-tree` does not report; rehearsed #294 with #290, #291, #298 | #296 green |
| The reviewer's four-line browser baseline | Prefer the headless shell by candidate order | preserve as the comparison | #293's evidence note; the founder's decision | none yet | Measured: with this container's real browsers it does all the branch does; with stand-ins it never reaches the browser that renders | recommendation owed: the smallest implementation that passes the declared requirements |
| The two representation-repair designs and their pilots | Their seam and their baselines; the negative result itself | extract | the next pilot, on a decision from the working mission (timeout or measured failure; missing evidence or ineligible; which closure an appraisal judges) | none yet | A pre-registration before any run | revival condition: the operational slice exists to supply the decision |
| `origin/codex/business-path-process` `650de5e5` and `greg rehearse --path` | A real-process run of offer to settlement; reconciliation that matches one statement row | extract | the operational slice | none yet | not started | next after the candidate's acceptance mission |
| #214 | Repair once per incident | preserve; not ready to integrate | — | — | Its three tests fail on `8d205324` alone: the mission blocks before any repair | its owner rebases |
| The intake-count unit (`c9ec07c8`) | One unit of evidence per independent source per claim | preserve as an experiment | Goal Gravity's wake rule | 16 right wakes, 3 false, 1 missed against 10, 10, 7 on the builder's own scenarios; three scenarios worse than baseline | not independently reviewed; scenarios not withheld | review owed |

## 2. Defect classes found in this session's own work

Six independent reviews ran (retained receipts, browser, revoked device, the replay fix, the appraiser unit, the
credit unit). Each returned "sound, with fixes". CI then found three more defects the reviews had not, and one
capacity limit (rows eight and nine, added 2026-11-12 at 10:07 UTC). The reviewers were separate agents on the same model: a second process, not an
independent operator.

| Class | First seen | Seen again | What now checks for it | What still escapes |
|---|---|---|---|---|
| **A mutant of another gate left stale.** A change moves a line that a different gate's mutant is anchored on; the changed unit's own tests and gate pass | the replay fix (`e917a0db`), found by review | #294's fix round, found by CI an hour after the push; the reconstitution gate, found by the scan before the push | `stale_anchor_scan.py` (kept on the evidence branch `claude/session-evidence-20261111`; its canonical owner would be the gate-liveness check in `scripts/repo_review.py`): gate strings that matched a changed file on the base and no longer match once. Run before every push | It is a heuristic with false positives; nobody has made it a test. The repository's static check does not read about half the gates' formats (recorded under S69.A6) |
| **A mutant that lost its only test.** The anchor still matches, but the change rerouted behaviour so no test reaches the line | #298 (`0a16997b`), found by CI job 6 | — | `gates_for_changes.py` (same place): lists every gate and group that mutates a changed file, so they are run, not scanned. The three fix rounds in flight were told to use it | Running every listed gate costs minutes to an hour of CPU; a gate nobody runs locally still waits for CI |
| **A second reader of one fact.** The same record interpreted in two places that can disagree | #294's defect itself (receipts) | the revoked-device fix round wrote another receipt reader; a compile receipt's `state` against `abstention_state` | A rule in each brief: extend the one reader. No automatic check | Readers that already exist: five appraisal readers by ledger order |
| **Unmeasured read as measured.** A reading that established nothing is counted as a failure | #298's defect (a faulted instrument) | a Mind-named fault recorded as measured; a solver timeout; a late appraisal re-read | Regression tests per case on #298; the appraiser and compile-unread units in flight | Each was found by a person or reviewer building the shape; no general test generates such shapes |
| **A fix that regresses a neighbouring mission shape** | the replay fix (a refused read lost its route) | the appraiser unit (an old closure blamed for a later world); the credit unit (a host stall cost a correct method its credit) | Independent review before a pull request, with base-against-head probes | Three of three were found only by review, none by the author's tests |
| **A silent loop.** A mission retries or re-blocks for ever and asks nobody | the replay fix (unseen `SENSOR_RETRY`) | an answered `NO_STRATEGY` ask re-blocks every cadence (on the line; recorded on #209 and by the appraiser review) | Tests that count asks and ticks on #298 | The answered-ask churn is not fixed |
| **A stored patch left unable to apply.** A draft patch kept in the repository is another consumer of the file it patches; a test keeps it applicable; no test of the changed behaviour names it | #300 (`934a9f77`): an import line in `greg/body.py` rewrapped, found by CI job 9 seventy-five minutes after the push | — | `gates_for_changes.py` now runs `git apply --check` for every stored patch a test names (it flags `934a9f77` and passes `0aa09c87`) | Only patches a test names by path. Seven other stored patches in the tree do not apply and no test says they should |
| **A check that stops instead of failing.** A job cancelled at its time limit reports neither pass nor fail, and a targeted local run can miss what only the whole run covers | Canonical CI job 10 on #300 and #299: cancelled at 90 minutes, every mutant so far caught. The job took 80 to 90 minutes on three base heads | the composed candidate's targeted local run (238 passed) missed the licence test that the full suite then failed on #300 | Draft #302 raises the limit to 180 minutes and records the measurements. Pull-request bodies record a cancelled job as `fail`, never as passed | The composed candidate carries every unit's gate and may exceed 180 minutes. Parallel shards are the structural answer and are not decided |
| **A count stated before it was read** | #294's `c4c0ca53` message (18/18 written, 17/18 measured) | — | Rule in every brief: no result that was not read from output | — |

**Cost, so far.** The three reviews whose run time was recorded took 43, 43 and 48 minutes of one agent each.
The three fix rounds recorded took 39, 45 and 109 minutes. The other three reviews ran inside a workflow and their
times were not kept. A CI round trip on this repository is one to two hours; the two defects CI found cost one
round trip each.

**Recurrence is the measure to watch.** The first class recurred twice after it was known and was caught earlier
each time: by review, then by CI, then by the scan before any push. That is one observation of an earlier catch,
not evidence that the process is reliable.

## 3. What this record does not cover

The same limits as the earlier record: pull requests this session did not open, read or rehearse; organ
repositories; Project conversations that are not in a repository.
