# Session handoff, 2026-11-11 (session `session_01Kucyfm9exT5imDVYvHTYSv`)

Rewritten at 23:29 UTC (read from the clock). It replaces the 19:30, 17:45 and 14:49 versions, kept in this
branch's history. This branch is evidence only: **not for merge**.

Reality status of everything below: a cloud container, test keys, no founder device. VEPMC 0. No merge,
deployment, spending, publication or outside contact happened.

What happened since 19:30: the account's usage limit stopped every running agent at about 19:45 UTC. Work resumed
at 23:12 UTC. Nothing was lost: every unit branch and the two interrupted worktrees were committed or snapshotted
and pushed.

## 1. Refs, read at 23:29 UTC

| Ref | Head | Note |
|---|---|---|
| #196 `claude/greg-full-machine-completion-whgiee` | `8d20532464b1533b28d71d8331ca3412a90dbb11` | integration line, unchanged since 11:48 |
| #290 | `facea1703dded45e495d0e6dfe059e001ffc9565` | contains #196's head |
| #291 `egregore/fervent-mayer-syy5d6` | `41fcc41f04911ccb1f0f8d5dfc18158999a18def` | contains #290's head |
| #273 | `331de165898ed5779ba87fc1532089a8f763dd4d` | based on `8d205324` |
| #278 | `a639add726df949c36a554aa87ba7c60cdabe66a` | based on `f1646209`, an ancestor of #196's head |

## 2. Draft pull requests opened by this session (all into #196's branch, base `8d205324`)

| PR | Branch | Pushed head | State at 23:29 |
|---|---|---|---|
| #291 | `egregore/fervent-mayer-syy5d6` | `41fcc41f` | every check passed; the body records it |
| #293 | `claude/browser-render-qualified-binary-20261111` | `da2aff57` | all ten Canonical CI jobs passed on this head. A fix round for its review is running locally |
| #294 | `claude/retained-negative-receipt-20261111` | `e24b326c` | Canonical CI failed at artifact upload after the tests ran (runner service error; not re-run because a new head is coming). Local head `a01997fd`, also pushed as `checkpoint/retained-negative-receipt-a01997fd`. A fix round is running locally |
| #295 | `claude/intent-20261111-absolute-opus-maximus` | `fb3515b7` | pushed 23:27 with the founder's resume message and the first disposition record; a new CI run starts |
| #296 | `claude/compose-rehearsal-20261111` | `0b0bb6d3` | job 1 failed at artifact upload; re-run requested once |
| #297 | `claude/seed-path-collection-clock-20261111` | `0454ab62` | check suite completed, no failure reported |

## 3. Unit branches, all pushed, no pull request yet

Read each head and its tests before trusting it. A label is not a result.

| Unit | Branch | Head | State |
|---|---|---|---|
| replay fix (a check a faulted capability could not read is not pursued) | `claude/unmeasured-check-not-pursued-20261111` | `e917a0db` | stacked on the locks. Independent review running. A rehearsal with #214 is running (#214's tests cover the same situation) |
| two acceptance locks (test only) | `claude/acceptance-locks-20261111` | `1f4bf62d` | reviewed together with the replay fix |
| revoked-device approvals | `claude/revoked-device-authority-20261111` | `f35b7986` | reviewed; four fixes owed. The interrupted fix round is at `checkpoint/revoked-device-fix-wip-20261111` (`d1f69b25`) and in `reviews/device-fix-wip.patch` here |
| appraiser runs no detached sensor | `claude/appraiser-detached-sensor-20261111` | `bf8e4b9f` | built; diff read; review owed |
| corrected evidence stops earning credit | `claude/correction-containment-credit-20261111` | `b01d319f` | built; diff read; review owed |
| goal intake counted by independent source | `claude/goal-intake-accumulation-20261111` | `1106795d` | built; three scenarios worse than baseline; Mechanism Card to be renumbered MC-0004 |
| S69.A6 map corrections | `claude/directive-map-s69a6-20261111` | `a69f5b72` | built; review owed |

## 4. Agents running at 23:29 (Agent tool, in this session; they commit locally and push nothing)

1. **Finish #294** in worktree `scratchpad/negreceipt` from `a01997fd`: one compensation-recovery lookup that reads
   the Gate's record through `AuthorityOffice.outcome_of` (covering a revoked approval and a detached or unavailable
   capability), and tests plus mutants for the 11 survivors its review found.
2. **Attack the replay fix** at `scratchpad/review-unmeasured` (`e917a0db`), including whether a construction that
   faults for ever and cannot be repaired now retries without ever asking the founder.
3. **Fix #293's review findings** in worktree `scratchpad/browser` from `da2aff57`.

If this session stops before they report: their commits are on those local branches in the scratchpad worktrees.
Read `git log` there, run the tests named in each brief, and never take a count from a commit message without
running it.

## 5. One decision made today that later work depends on

`_run_compensation` never reads the Gate's own record of a compensation's dispatch. Two reviews found it
separately (#294's adjacent gap; the revoked-device unit's first finding). The device fix round had started a
second inline reader of a receipt. Decision: one implementation, in #294, through `outcome_of`, which #294 made
the one reader. The device branch is then restacked on #294's new head and drops its copy. The reasoning is in
`docs/collaboration/REPOSITORY-DISPOSITIONS-2026-11-11.md` on #295.

## 6. What this directory holds

- `reviews/`: the raw result of every builder, reviewer, designer and reader agent that finished, and the device
  fix-round patch.
- `reviewer-probes/`: the probe scripts the reviewers wrote, by unit.
- `workflow-journals/`: journals of the six workflow runs of the day and their scripts. The four afternoon runs
  ended when the usage limit was reached; a journal shows which agents finished.
- `NEXT-CHAIN-DECISION.md`: the work-selection record (self-review; binds nobody).
- `staffing-proof/`, `receipt-process/`, `browser-probe/`, `scout/`: earlier evidence of the day.

## 7. Next steps, in order

1. When agent 1 reports: read its diff, run the receipt and compensation files and the gate, compose with #291 and
   #273, push #294 once with a body update.
2. Restack the device branch on #294's new head; finish its four fixes from the checkpoint; drop its reader.
3. When agent 2 reports: fix what it confirms, then open one draft pull request for the locks and the replay fix.
4. When agent 3 reports: read, run, push #293 once with a body update.
5. Independent reviews of the appraiser, credit, intake and map units; then draft pull requests, each rehearsed
   with `scripts/compose_rehearsal.py --union .github/workflows/canonical-ci.yml --union
   docs/FOUNDER_INTENT_LEDGER.md` against #290, #291, #294 and the others.
6. Representation repair (board claim 6805031119, branch not created): two of three designs finished. Redo the
   adversary and the synthesis, commit the pre-registration, then build and run once. Neither pilot shows a gain
   over a simple baseline yet.
7. Business path: the third reader and the synthesis did not run. No build there until they do.

## 8. Decisions that are the founder's

- Intake of #290, #291, #293, #294, #295, #296, #297 into #196.
- #291 reverses #290's choice that an office without a registry "keeps its earlier behaviour".
- #294 reads an unclassed or unreadable receipt as UNCERTAIN. The alternative is REFUSED.
- Revoked-device approvals: the unit adds an optional `suspected_compromise: true` to a founder-signed
  DEVICE_REVOKE. No protected authority file is touched; adopting the field is the founder's.
- `GREG_REQUIRE_BROWSER=1` in Canonical CI.
- The stray tracked file at the root of `8d205324`
  (`orker-evidence-replay.py with the fallback tier in place of the constant policies#`, 27 bytes, from
  `9ee9b612`).
- One CI step that runs every `scripts/ci/check_*_mutants.py`, which would end the recurring step-list conflict.
- From the locks unit: whether a signed `auto_attach` may still attach a different implementation after the
  founder detached one without asking; whether a mission precondition is read again at the Gate's commit.
- From the credit unit: four questions about what a founder rejection withholds and what lifts it
  (`reviews/build-credit.json`, `founder_questions`).
- From the intake unit: whether GREG's own observation of a change clears what a goal has already woken on, and
  whether a bare mention counts (`reviews/build-intake.json`, `founder_questions`).
