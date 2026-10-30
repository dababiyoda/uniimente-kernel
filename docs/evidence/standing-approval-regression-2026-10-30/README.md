# A standing approval falls on failure evidence; the earned level is reported, never granted (2026-10-30)

**Parent:** BODY + ORGANS + MIND = GREG / UNIIMENTE. Work unit WU-09 part A of the 2026-10-28 OPUS MAXIMUS build
directive (sections 59-60). Part B (a founder-signed `AUTONOMY_GRANT`, binding `autonomy/levels.py` issuance to a
signed command) is out of scope and stays NEEDS_FOUNDER_DECISION.

- **Base:** #196 head `a6c29bbd`. **Branch:** `claude/standing-approval-regression-20261030`. Not pushed.

## The defect, reproduced on a real body

An unpaid founder APPROVAL of an exact scope sits in the mission's `approved_scopes` until a paid run (`greg/missions.py`,
paid DONE) or a restore (`decision.withdrawn` with `voids_approval`) voids it. Nothing else removes it. On a booted body
in a temporary home, with a test founder key:

1. **Ineffective run.** A standing mission has two `fs.write` strategies outside its cone. The founder approves
   `w-bad`; it runs, the check it advances still fails, and the engine records `routing.outcome` `ineffective`. The
   founder approves `w-good`, which fixes the check. After drift, `w-bad` ran again under its old approval, unasked.
2. **Refuted closure.** The founder approves `w`; it runs and the mission holds. The separate appraiser re-reads the
   world, finds it changed and records `REFUTED`. At the next cadence `w` ran again under its old approval, unasked.

## What changed

- `greg/autonomy.py` (new): `regress` names each completed run that failure evidence covers. That evidence is a
  `routing.outcome` `ineffective` for its receipt, or a `REFUTED` appraisal of the closure whose window holds the run
  (the window is the one `greg/appraisal.py` uses). For each APPROVAL of that scope that was asked before the run and
  still stands, `regress` records `autonomy.regressed` and then `decision.withdrawn {voids_approval: true}`, the
  pattern `greg/recovery.py` uses. The existing mission fold discards the scope, and the next selection asks again.
  An approval given after the regression stands until its own run fails.
- `greg/body.py`: one call line in `Body.tick`, before Goal Gravity and the mission engine select anything (and
  `autonomy` added to the existing local import line). `greg/missions.py`, `greg/authority.py` and
  `greg/appraisal.py` are untouched.
- `greg/autonomy.py` `report` and `greg autonomy` (`greg/cli.py`, additive): a read-only fold of the ledger. It
  works per (capability, action class, target pattern, budget band) and reports SHADOW, RECOMMENDER or
  SUPERVISED_CANARY, with thresholds declared in code:
  - SUPERVISED_CANARY needs 5 appraiser-verified runs since the latest failure and a Wilson lower bound of at least
    0.5 (z = 1.96).
  - A refuted or ineffective run drops the tuple at once. Runs are ordered by where each run sits on the ledger, not
    by when its verdict was recorded.
  - A regression is counted, but it drops nothing a second time: it always names a run the fold already counts as
    refuted or ineffective.
  - BOUNDED_AUTONOMY and MANAGE_BY_EXCEPTION are never earned from evidence.
  - It writes nothing and grants nothing.

## Review round 1

Two reviewers reported four findings. Each was reproduced on head `c925ebfd` and fixed in `greg/autonomy.py`, with
tests in `tests/unit/test_greg_standing_approval_regression.py` and mutants in the mutant script.

| Finding | Reproduced on `c925ebfd` | Fix |
|---|---|---|
| WU09-R-1: the report placed a verified run where its appraisal was recorded. An earlier closure appraised after a later refuted one (one unavailable appraiser run) counted as "verified since the latest failure". | Reviewer probe on a real body: `RECOMMENDER`, verified_since_last_failure 1, though the latest run was refuted. | Every outcome sits at its run's own ledger position. Refuted and ineffective runs come from `failures`, the same evidence `regress` uses. `regressed` is no longer a separate severe outcome, because it always names a run already counted as failed. |
| WU09-R-2: `failures`, which `regress` runs on every `Body.tick` while an approval stands, re-sorted a mission's marks for every appraisal and rescanned every run for every refuted window. | Reviewer probe, `failures()` on a synthetic standing history of 250/500/1000/2000 holds: 0.012/0.045/0.168/0.674 s, about 4x per doubling. | One sort of the marks and one pass, runs indexed per mission, window runs found by bisect, asks indexed by (mission, scope). Same probe after the fix: 0.001/0.002/0.005/0.012 s. |
| WU09-F1: no test pinned the refuted window's bounds. | Reviewer mutants "window start ignored" and "window end ignored" survived the 9 tests. | Two tests. A fresh approval after a refuted regression stands, and heals drift unasked after a verified hold (end bound). A refutation regresses only the approvals of runs inside its window (start bound: two checks, two approvals). |
| WU09-F2: no tests for the ineffective drop, the regression drop or the Wilson condition. | Reviewer mutants "ineffective not severe", "regressions not severe" and "Wilson ignored" survived. | An ineffective in-cone run drops a SUPERVISED_CANARY tuple to SHADOW. Three refuted runs followed by five verified runs give RECOMMENDER (Wilson 0.306). The regression claim is restated, as described above. |

## Review round 2

Two reviewers reported three findings on head `6e1cc639`. Each was reproduced here before any change.

| Finding | Reproduced on `6e1cc639` | Disposition |
|---|---|---|
| WU09-ATK-1: a run the founder reconciled as executed has no receipt, so the engine writes no `routing.outcome` for it, and `failures` never named it. With two checks, no hold closes before the world drifts, so no refutation lands either. The ineffective scope ran again under its first approval. | The reviewer's probe, run in this worktree: `w-bad` ran unasked at ledger position 46; its approval was first regressed at 53, on the evidence of that rerun. | **Fixed.** `failures` now reads a reconciled run's effect from the observations after it, as the mission fold reads them: each check the strategy advances is decided by its first observation after the run (before the strategy's next run) that passed or measured the world. A measured failure is the fold's "executed but ... still failing", judged by the engine's own `blames_strategy`. A strategy whose output another binds is skipped, as in the fold. The report counts reconciled runs apart (`reconciled`), never as verified; failure evidence naming one counts against the tuple. Before, a regression could name a reconciled run the report did not count at all. |
| WU09-ATK-2: `report` folded no compensation events, although the unit's spec lists them. | `sorted(autonomy._blank({}).keys())` had no compensation field. | **Fixed.** `compensation_required`, `compensated` (undone through the Gate, or the founder decided) and `compensation_open` are counted against the original run's tuple. They are counted, not judged: an abandoned or superseded mission does not show the run failed, so levels do not change. |
| WU09-TF-1: two report guards were untested. X1 dropped the `windows[i][2] < at` check, so a later closure judged a run made before its window opened. X2 counted a VERIFIED_UNMET closure as verified. | Both mutants survived the 16 tests. The reviewer's VERIFIED_UNMET probe, run here, gives `SHADOW` with `unappraised` 1; X2 gives `RECOMMENDER`. | **Fixed (tests only; the code was right).** The ordering test now checks the report while the first hold is still unappraised. A new real-body test closes a bounded mission unmet. Both mutants are in the script and caught. |

New tests:

- the reconciled-ineffective probe;
- a control in which a reconciled run that worked keeps its approval, regressed later only by the hold's refutation;
- the compensation fold;
- the VERIFIED_UNMET closure.

## Commands and results

| Run | Command | Result |
|---|---|---|
| Fail-before (a), base `a6c29bbd`, new test file only | `python -B -m pytest -q -p no:cacheprovider tests/unit/test_greg_standing_approval_regression.py` in a detached worktree | collection error: `greg.autonomy` does not exist |
| Fail-before (b), base + test file + `greg/autonomy.py`, no body hook or CLI | same | **4 failed, 5 passed**: the ineffective, fresh-approval, refuted and climb/CLI tests fail. The ablation, verified-hold control, crash, dedupe and Wilson tests pass, as they should without the hook. |
| Pass-after (round 0) | same, in `/home/user/wu09` at `c925ebfd` | **9 passed** |
| Fail-before (c), review round 1: head `c925ebfd` + the round-1 test file, detached worktree | same | **3 failed, 13 passed**. Failing: the ordering test in both directions (`assert (1 == 0)` and `assert (0 == 1)`) and the cost test (`680598 < 8 * 42648`). The window-bound, ineffective-drop and Wilson tests pass on `c925ebfd`: its behaviour was right but untested. Their fail-before evidence is the mutants below. |
| Pass-after (round 1) | same, in `/home/user/wu09` | **16 passed** |
| Reviewer probe, review round 2 | the reviewer's `test_probe_reconciled.py`, copied into this worktree at `6e1cc639`, `pytest -s`; then removed | **1 failed, 1 passed**: the two-check case fails (`w-bad` reruns at position 46, regressed at 53); the one-check case passes (its hold is refuted). After the fix: **2 passed**. |
| Fail-before (d), review round 2: head `6e1cc639` + the round-2 test file, detached worktree (removed after) | `pytest -rA ... -k "reconciled or compensations or unmet or ordered"` | **2 failed, 4 passed**. Failing: the reconciled-ineffective test (`ValueError`: no `autonomy.regressed`) and the compensation test (`KeyError: 'compensation_required'`). Passing on `6e1cc639`: the ordering test (both directions), the reconciled-worked control and the VERIFIED_UNMET test. Their code was right but untested; their fail-before evidence is mutants 20 and 21 below. |
| Pass-after (round 2) | whole test file, `-n 3`, in a scratch copy of the tree committed as `eef31b30` | **20 passed** |
| Mutants | `python -B scripts/ci/check_standing_approval_regression_mutants.py` (scratch copy, `PYTHONDONTWRITEBYTECODE=1`, `__pycache__` purged before each run, baseline must pass) | round 1: **15/15 caught**. Round 2: **21/21 caught** (the first run reported mutant 14 STALE, because its anchor now occurred twice; the anchor was lengthened and the whole script re-run). |
| Narrowing-only guards of the round-2 code (not in the script) | three mutants, whole test file, `-n 3` | **3 survived** (see Limits) |
| Reviewer's other mutants (not findings) | the same 6 mutants re-expressed on the revised code, whole test file | **6 survived** (see Limits) |
| Related suites | `pytest -n 3` over test_greg_platform (incl. `test_guardrail_autonomy_is_not_authority`), _missions, _active_constraint, _answer_reverification, _appraisal_closure, _appraisal_retry_bound, _closure_integrity, _founder_and_scope, _goal_gravity_consumed_approval, _mission_book_incremental(_verified), _paid_approval_zero_booked, _paid_ask_withdrawn_after_spend, _paid_scope, _resilience, _restore, _restore_fold, _routing_integrity, _self_repair, _interface, test_autonomy and the new file | round 0: **473 passed, 1 skipped**. Round 1 (16-test file): **480 passed, 1 skipped** in 110 s. Round 2, adding test_greg_mission_reconciliation, _native_reconciliation, _reconciliation, _reconciliation_record, _standing_reconciliation and _goal_gravity_merge (the body hook now reads reconciled runs; the report reads compensations): **578 passed, 4 skipped** in 241 s. Every skip needs bubblewrap, which this host lacks: `test_greg_paid_approval_zero_booked` and 3 in `test_greg_standing_reconciliation`. |

The 21 mutants each remove one safeguard:

1. the body hook;
2. the ineffective evidence;
3. the refuted evidence;
4. `voids_approval`;
5. the asked-before-the-run guard;
6. the once-per-call guard;
7. the reuse of a retained regression after a crash;
8. the level ceiling;
9. refuted counted as severe;
10. the refuted window's start;
11. the refuted window's end;
12. ineffective counted as severe;
13. the Wilson condition for SUPERVISED_CANARY;
14. ordering by the run's place (the mutant places a verified run where its verdict landed);
15. the bisect over a mission's runs (the mutant rescans every run for each refuted window);
16. reading founder-reconciled runs at all;
17. a passing observation deciding a reconciled run (the mutant lets a later drift blame a run that worked);
18. the report counting failure evidence that names a reconciled run;
19. a compensation's own status (the mutant counts every one as settled);
20. the window-start check in the report (X1: a later closure judges a run made before its window opened);
21. VERIFIED only, not VERIFIED_UNMET, judging a run verified (X2).

The cost test counts comparisons between ledger positions instead of timing, so machine load cannot change its
result. Revised code: 971 comparisons at 100 heals and 4,687 at 400 (4.8x). `c925ebfd`: 42,648 and 680,598 (16.0x).
The bound is 8x.

## Limits

- **Reality level: INTEGRATION-TESTED.** Real bodies, the real engine, AuthorityOffice, Gate and separate appraiser
  process were used, with a test key. It was not run on a founder device and is not founder-used.
- **Not covered:**
  - A strategy pre-approved inside the signed mission (`pre_approved_steps`) is part of the signed mission and is
    not withdrawn.
  - A capability failure (a REFUSED receipt) lowers the level but does not regress an approval. The mission's loop
    already keeps that strategy out of selection.
  - A collateral regression ("regressed X") is not used as evidence. The fold never re-runs that strategy
    automatically.
- **Any refutation regresses:** a REFUTED verdict regresses the approvals of the runs in that closure's window even
  when the action did not cause it (the world changed between the hold and the appraisal, or another strategy broke
  the check). This only narrows authority; the founder's next approval restores it. Attribution is a founder decision.
- **Mutant 6** ("one rid returned twice in a call") is caught through the list `regress()` returns. On the ledger, the
  record keys `[rid, 'regressed']` and `[rid, 'withdrawn', 'regressed']` already keep a run named by two failures to
  one regression, with or without the guard.
- **Event name:** the journal kind `autonomy.regressed` shares its name with the licence event `autonomy/levels.py`
  writes, as payload type `autonomy.regressed` inside an `event` record on its own ledger. The record types differ, so
  neither reader sees the other's rows; the shared name is a naming hazard only.
- **Upgrade effect:** on a body that already holds approvals, the failure evidence on its ledger regresses them the
  first time this code runs.
- **Tuple boundaries:**
  - The target pattern is the target's scheme (`workspace:c.txt` -> `workspace:*`).
  - Budget bands are $0, up to $1, $10 and $100, and over $100.
  - Both are first choices, not founder-ratified.
- **Behaviour change:** a standing mission whose first-ranked strategy was regressed now waits on the founder's
  re-ask, even when another standing strategy could heal the drift. Ranking is in `greg/missions.py`, which this
  unit does not edit.
- **Run order, both ways (round 1):** a refutation recorded late for an earlier run no longer discounts a later
  verified run. The rule counts verified runs after the latest failed run, by where the runs sit on the ledger. The
  old fold happened to be stricter in that case and looser in the reverse one. Both directions are now tested.
- **Founder-reconciled runs (round 2):**
  - The evidence is the first observation of an advanced check after the run, so the regression lands on the tick
    after that observation. In between, the mission fold already keeps the strategy out of selection ("executed but
    ... still failing").
  - The fold's collateral exception is not followed. A run already blamed for damaging another check counts as
    ineffective here too, which only narrows.
  - A reconciled run that worked keeps its approval only until the hold: its appraisal refutes the window, because
    the run has no Gate receipt, and the approval falls then (tested).
  - A reconciliation settled under a standing mandate (`standing_reconciliation`) is read the same way, through
    `routing.founder_reconciled`. Its suite skips on this host (no bubblewrap), so that route is not exercised here.
  - A reconciled DONE record carries a scope digest only when its blocker named a proposal. Without one, nothing
    is regressed.
- **Compensations (round 2)** are counted, never judged, so an open compensation for an external effect does not
  lower a level. Whether it should is a policy choice left to the founder.
- **Narrowing-only guards of the round-2 code that no test pins** (each mutant survives the 20 tests). Each mutant
  would record extra withdrawals and would never keep an approval standing:
  - judging a strategy whose output another strategy binds;
  - counting an unmeasured read (a failed or abstaining sensor) as ineffective;
  - reading observations after the strategy's next run. This is equivalent on ledgers the engine writes: the engine
    observes a strategy's checks before it can select that strategy again.
- **Reviewer mutants that still survive** (not raised as findings; checked on the revised code):
  - Equivalent on ledgers the engine writes:
    - other missions' asks of the same scope: `greg/authority.py` puts the mission id in the scope digest;
    - dropping the ineffective outcome's mission/action match: a receipt belongs to one run;
    - counting founder-reconciled runs: such a run had no receipt and was skipped first. Round 2 superseded this
      guard: the report now counts reconciled runs apart, and mutant 18 covers what it counts.
  - Untested guards that only narrow: withdrawing unanswered or rejected asks, already withdrawn or consumed asks,
    or asks on terminal missions would record extra withdrawals. They would never keep an approval standing.
