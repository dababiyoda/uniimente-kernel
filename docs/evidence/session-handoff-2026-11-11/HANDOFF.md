# Session handoff, 2026-11-12 (session `session_01Kucyfm9exT5imDVYvHTYSv`)

Rewritten at 02:12 UTC on 2026-11-12 (read from the clock). It replaces the 23:29, 19:30, 17:45 and 14:49 versions
of 2026-11-11, kept in this branch's history. This branch is evidence only: **not for merge**.

Reality status of everything below: a cloud container, test keys, no founder device. VEPMC 0. No merge,
deployment, spending, publication or outside contact happened.

## 0. What governs the work now

The founder's clarification of 2026-11-12 01:54 UTC, kept verbatim on #295
(`docs/intent/sources/CONVERGENCE-CLARIFICATION-2026-11-12-source.md`, record
`docs/intent/INTENT-20261112-CONVERGENCE-USEFUL-PATH.json`). In order:

1. Finish the active repair and review rounds.
2. Compose compatible work on one reversible candidate and run checks on that exact revision.
3. Repair the integration line's timeout and closure-appraisal defects.
4. Exercise one useful operational mission through the connected machinery.
5. Transfer the retained capability into a second, materially different case and measure what transferred.
6. Use the observed bottleneck to select the next intelligence or capability-formation build.

The founder's five engineering answers (unreadable receipt stays unknown; smallest browser implementation that
passes the declared requirements; rejection history scoped with explicit requalification; a late appraisal
mismatch is stale, not a refutation; prepare the intake package, approval stays the founder's and the integrator's)
are in that source file. They are recommendations to reconcile with canonical contracts, not constitutional changes.

## 1. Refs, read at 02:12 UTC

| Ref | Head | Note |
|---|---|---|
| #196 `claude/greg-full-machine-completion-whgiee` | `8d20532464b1533b28d71d8331ca3412a90dbb11` | integration line, unchanged since 2026-11-11 11:48 |
| #290 | `facea170` | another session |
| #291 | `41fcc41f` | this session; every check passed |
| #273 | `331de165` | another session |
| #278 | `a639add7` | another session |

## 2. Draft pull requests opened by this session (all into #196's branch)

| PR | Branch | Pushed head | State at 02:12 |
|---|---|---|---|
| #293 | `claude/browser-render-qualified-binary-20261111` | `32ca8de7` | review round answered; CI running. A smallest-implementation recommendation is owed (founder answer 3) |
| #294 | `claude/retained-negative-receipt-20261111` | `1643932e` | one reader of a receipt; compensation recovery from the Gate's record; CI running |
| #295 | `claude/intent-20261111-absolute-opus-maximus` | `16fa6cba` | the founder's messages, two disposition records, the defect-class register; CI running |
| #296 | `claude/compose-rehearsal-20261111` | `0b0bb6d3` | the rehearsal tool |
| #297 | `claude/seed-path-collection-clock-20261111` | `0454ab62` | |
| #298 | `claude/unmeasured-check-not-pursued-20261111` | `b9a34259` | the replay fix, repaired after review, plus two acceptance locks; Canonical CI queued behind its earlier run |
| #299 | `candidate/composed-20261112` | `45c3644b` | **evidence only.** Eleven heads on one tree. Local: the 20 changed test files plus health gates, 415 passed, 1 skipped (no supervisord). CI running. Local head `e6905364` adds #300 and #295 at `16fa6cba`; pushed once its tests pass |
| #300 | `claude/revoked-device-authority-20261111` | `934a9f77` | stacked on #294. 245 passed locally. Its 16 gates are left to CI jobs 6 and 10. The fix round is not independently reviewed |

Push-time `collaboration-receipt` failures on #295 and #298 are the run that starts before the body carries the
new head; the run after the body edit passed on both.

## 3. Unit branches without a pull request

| Unit | Branch | Local head | Pushed head | State |
|---|---|---|---|---|
| appraiser runs no detached sensor | `claude/appraiser-detached-sensor-20261111` | moving | `bf8e4b9f` | reviewed (`reviews/review-appraiser.md`); fix round running. Rule given: a late re-read mismatch is stale, never REFUTED |
| a rejected answer stops earning credit | `claude/correction-containment-credit-20261111` | moving | `b01d319f` | reviewed (`reviews/review-credit.md`); fix round running. Rule given: rejection scoped to answer, evidence, conditions and version; explicit founder-signed requalification |
| a compile the host stalled is not a measured failure | `claude/compile-unanswered-unread-20261112` | moving | none | being built, stacked on #298. Defect reproduced on `8d205324` (`stall-reproduction/`) |
| intake recommendation as a GREG mission | `claude/intake-recommendation-mission-20261112` | moving | none | being built, stacked on #296. The first useful mission the founder named |
| goal intake counted by independent source | `claude/goal-intake-accumulation-20261111` | `c9ec07c8` | `c9ec07c8` | built; independent review owed |
| S69.A6 map corrections | `claude/directive-map-s69a6-20261111` | `a69f5b72` | `a69f5b72` | built; independent review owed |

## 4. Agents running at 02:12 (Agent tool; they commit locally and push nothing)

1. Appraiser fix round, worktree `scratchpad/appraiser`.
2. Credit fix round, worktree `scratchpad/credit`.
3. Compile-unread build, worktree `scratchpad/compile-unread`.
4. Intake-recommendation mission build, worktree `scratchpad/intake-mission`.

If this session stops before they report: their commits are on those local branches. Read `git log` there, run the
tests each brief names, and take no count from a commit message without running it.

## 5. Two checks to run before any push (both on this branch, `tools/`)

- `stale_anchor_scan.py <worktree> <base>`: mutation-gate strings that matched a changed file on the base and no
  longer match once. A heuristic: a mutant's replacement text and generic lines show up as suspects.
- `gates_for_changes.py <worktree> <base>`: every gate and cortex-gate group that mutates a changed file. **Run
  them.** A matching anchor does not show that a test still reaches the line (found by CI on #298).

Where they helped and where they did not is in `docs/collaboration/REPOSITORY-DISPOSITIONS-2026-11-12.md` on #295.

## 6. Next steps, in order

1. When the candidate's tests on `e6905364` pass, push it and update #299's body (the eleven-head run's result,
   the two added heads, the new conflict in `docs/FOUNDER_INTENT_LEDGER.md` resolved by keeping both sides).
2. As each fix-round or build agent reports: read the diff, run its tests, run the two checks above and the gates
   they list, commission an independent review where there is none, push, open a draft pull request with a version 2
   receipt, add the head to the candidate.
3. Run the intake-recommendation mission on the real open heads and hand its output to the #196 integrator.
4. Write the seven-behaviour mission on the candidate (entry point; interruption and restart; capability identity
   and device revocation; completed work kept when a dependency fails; uncertainty, timeout, refusal, failure and
   refutation kept apart; an appraisal bound to its closure; an account of outcome, costs, uncertainty and next
   step), including the combined experiment the founder named.
5. Unit: the five appraisal readers key on the closure they mean (`reviewer-probes`, `p13b_retry_window.py`).
6. #293: build the small variant (candidate order plus the fixes that do not depend on the render check), run the
   requirement tests on both, recommend.
7. Operational slice: request to settlement reconciliation on a synthetic case with explicit rules, the adverse
   cases the founder listed, then a second materially different case. Two readings of the existing business path
   are in `reviews/read-runtime.json` and `reviews/read-evidence.json`; the synthesis is not written.
8. Representation repair: no further pilot before a baseline, budget, withheld cases and success conditions are
   declared on a decision taken from the working mission.

## 7. Decisions that are the founder's

- Intake of #290, #291, #293, #294, #295, #296, #297, #298, #300 into #196. #299 is not for merge.
- #300: question 12 (who may approve a held compensation), question 3 (a mission a revoked device resumed keeps
  running), question 13 (a revocation during a turn), question 14 (re-delegating a suspected key), and adopting the
  optional `suspected_compromise` field.
- #291 reverses #290's choice that an office without a registry "keeps its earlier behaviour".
- `GREG_REQUIRE_BROWSER=1` in Canonical CI.
- The stray tracked file at the root of `8d205324`
  (`orker-evidence-replay.py with the fallback tier in place of the constant policies#`, 27 bytes, from `9ee9b612`).
- One CI step that runs every `scripts/ci/check_*_mutants.py`, which would end the recurring step-list conflict
  (five of the candidate's six textual conflicts are that list).
- From the locks on #298: whether a signed `auto_attach` may attach a different implementation after the founder
  detached one without asking; whether a mission precondition is read again at the Gate's commit.
- From the intake-count unit: whether GREG's own observation of a change clears what a goal has already woken on.

## 8. What this directory holds

- `reviews/`: the raw result of every builder, reviewer, designer and reader agent that finished.
- `reviewer-probes/`: the probe scripts the reviewers wrote, by unit.
- `workflow-journals/`: journals of the six workflow runs of 2026-11-11.
- `tools/`: the two checks above, `run_cortex_groups.py`, `union_resolve.py`.
- `stall-reproduction/`: the compile-timeout defect on `8d205324`.
- `NEXT-CHAIN-DECISION.md`, `staffing-proof/`, `receipt-process/`, `browser-probe/`, `scout/`: earlier evidence.
