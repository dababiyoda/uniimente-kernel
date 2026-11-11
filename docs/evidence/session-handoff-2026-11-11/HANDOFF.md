# Session handoff, 2026-11-11 (session `session_01Kucyfm9exT5imDVYvHTYSv`)

Rewritten at 17:45 UTC; it replaces the 14:49 version (kept in this branch's history). This branch is evidence
only: **not for merge**. It holds the exact continuation state, the connected staffing proof, raw review results,
the scout's experiments and the two workflow scripts.

Reality status of everything below: a cloud container, test keys, no founder device. VEPMC 0. No merge,
deployment, spending, publication or outside contact happened.

## 1. Refs, refreshed 16:50 UTC

| Ref | Head | Note |
|---|---|---|
| #196 `claude/greg-full-machine-completion-whgiee` | `8d20532464b1533b28d71d8331ca3412a90dbb11` | integration line, unchanged since 11:48 |
| #290 | `facea1703dded45e495d0e6dfe059e001ffc9565` | contains #196's head |
| #291 `egregore/fervent-mayer-syy5d6` | `41fcc41f04911ccb1f0f8d5dfc18158999a18def` | contains #290's head |
| #273 | `331de165898ed5779ba87fc1532089a8f763dd4d` | based on `8d205324` |
| #278 | `a639add726df949c36a554aa87ba7c60cdabe66a` | based on `f1646209`, an ancestor of #196's head |

## 2. Draft PRs opened by this session

| PR | Branch | Head | State |
|---|---|---|---|
| #291 | `egregore/fervent-mayer-syy5d6` | `41fcc41f` | Canonical CI run 43055969609: jobs 2, 3, 4, 5, 7, 8 passed; 1, 9, 10 still running at 17:33; job 6 failed in `apt-get` (runner DNS) before any test, as on the previous head. One re-run of job 6 is owed when the run finishes |
| #293 | `claude/browser-render-qualified-binary-20261111` | `46ab6f89` | self-reviewed; independent review running (workflow 2, unit `browser`) |
| #294 | `claude/retained-negative-receipt-20261111` | `85b4cc18` | builder commit `fb9b1414` plus my acceptance commit; independent review queued (workflow 1, unit `negreceipt`) |

Board #96: claims and handoffs in comments 6802130261 and 6802820715. No acknowledgment from the #196 integrator
or #290's owner yet.

## 3. What each PR shows

**#294, retained receipts.** On `8d205324`, in real processes: a `greg run` process sent SIGKILL after the Gate's
negative receipt of a refused compensation; the new process records the compensation DONE and never asks the
founder (`tests/integration/test_greg_retained_receipt_process.py`, 1 failed, 2 passed there). On `85b4cc18`: 3
passed, each killed run equal to the run never killed. A receipt with no class or an unreadable result is
UNCERTAIN with one reconciliation ask (on `fb9b1414` it was REFUSED, no ask, and the mission moved on). Mutation
gate 18/18. Left open: one strict xfail (a receipted, unrecorded dispatch of a mission the founder ends before the
restarted body steps it).

**#293, browser.** On `8d205324` here, `tests/unit/test_greg_browser.py`: 1 passed, 2 skipped (the full Chrome
binary, Chrome for Testing 153.0.8010.12, never returns from `--headless=new --dump-dom`). On `46ab6f89`: 3 passed.
The headless shell renders under GREG's isolation flags in about 0.5 s; Playwright's own launch works too
(`browser-probe/pw.js`). 14 hermetic tests, mutation gate 25/25.

**#291, authority identity.** Unchanged since the earlier handoff: 51 tests in the two authority files, gates 23/23
and 5/5.

## 4. Composed tree

Local branch `compose-20261111b`, worktree `scratchpad/compose2`, head `3b1c743a`:
`8d205324` + #290 `facea170` + #291 `41fcc41f` + #273 `331de165` + #278 `a639add7` + one call-site line
(`adapter=adapter, around=wrap`) + #294 (`525ab6b0` merged, then `85b4cc18` cherry-picked).

- Two textual conflicts merging #294 onto #273: the CI step list (keep both) and `MissionEngine._dispatch` (take
  #273's `act`/`finish` structure and drop `finish`'s copy of the interrupted-worker rule, which `_record_outcome`
  now owns).
- Result: receipt (unit, history, real-process), authority identity and attach state, capabilities, handoff,
  egress, repo-health, compensation, both kill-window files, reconciliation, blockers, background dispatch and
  resource bounds files: 254 passed, 3 skipped, 1 xfailed. Receipt mutation gate 18/18 on this tree.
- Not composed yet: #293 (touches `greg/capabilities.py` and the CI step list; expect a step-list conflict only).

## 5. Work running when this was written

**Workflow 1** (`track-a-resume`, run `wf_c7bc9338-5cc`, script in `workflow-journals/`): build done for `device`
and `negreceipt`; builds running for `appraiser` and `map`; reviews and fixes queued; then a `scout` unit.

| Unit | Branch | Local head | Pushed |
|---|---|---|---|
| revoked-device approvals | `claude/revoked-device-authority-20261111` | `f35b7986` (3 commits, 17 files, about 2,700 lines) | only `d7c43ce5` |
| appraiser runs a detached sensor | `claude/appraiser-detached-sensor-20261111` | in progress | no |
| S69.A6 map corrections | `claude/directive-map-s69a6-20261111` | `252be328` plus uncommitted work | `252be328` |

**Workflow 2** (`track-a-capability-wave`, run `wf_24637629-6ac`): review of #293; builds, reviews and fixes for
three new units:

| Unit | Branch (not created until its builder starts) | What |
|---|---|---|
| `credit` | `claude/correction-containment-credit-20261111` | corrected evidence stops earning competence credit |
| `intake` | `claude/goal-intake-accumulation-20261111` | independent weak signals add up, repetition does not |
| `locks` | `claude/acceptance-locks-20261111` | two test-only locks (stale precondition; reconstitution without replay) |

A background label or a launch is not a result. Read each unit's branch head and its tests before trusting it.

## 6. Scout result (read-only, on `8d205324`), in brief

The founder's eight proposed extensions against the code. Experiments: `scout/exp_b.*`, `exp_c.*`, `exp_g.*`.

| | Minimum test | Residual |
|---|---|---|
| A representation repair | partial | no code names the invalid assumption or compares with a fixed-representation baseline |
| B evidence-dependency correction | met at journal tier | contained readings still earn credit (reproduced on a real Body): unit `credit` |
| C proof-bearing plans | met in behaviour | one clause has no committed test: unit `locks` |
| D adaptive organization | partial | no signed action fields a team; large (WU-03, WU-04) |
| E transferable capability | met | none |
| F development-process improvement | partial | met for brief production only; nothing judges Genesis's own method |
| G goal opportunity synthesis | fails on the body | per-item scoring: unit `intake` |
| H functional reconstitution | clauses met separately | no composite test: unit `locks` |

The venv has no networkx, scipy, z3, ortools or sympy, so 69 test files skip some or all of their tests here.

## 7. Next steps, in order

1. Workflow results as they land: read each diff, run its tests, verify on `compose-20261111b` (merge, then run
   both sides' tests), push, open a draft PR into `claude/greg-full-machine-completion-whgiee` with a v2 receipt,
   subscribe, post the handoff on #96.
2. #291: re-run job 6 once; record the final CI in the PR at the next push.
3. #294: fold in its independent review; then decide the strict xfail (fix or keep).
4. Recompute the open directive units (`python -m acceptance directive`) and pick the next build. Candidates read
   so far: A (representation repair, medium), F for Genesis's own method (blocked by #289/#292 until they land),
   S40-A, S40-C, S50-A, S51-A.

## 8. Decisions that are the founder's

- Intake of #290, #291, #293, #294 into #196.
- #291 reverses #290's choice that an office without a registry "keeps its earlier behaviour".
- #294 reads an unclassed or unreadable receipt as UNCERTAIN. The alternative is REFUSED.
- Revoked-device approvals: the policy is being built as stated; any protected authority file stays untouched.
- `GREG_REQUIRE_BROWSER=1` in Canonical CI (turns a runner without a working browser from a skip into a failure).
- The stray tracked file at the root of `8d205324`
  (`orker-evidence-replay.py with the fallback tier in place of the constant policies#`, from `9ee9b612`).
