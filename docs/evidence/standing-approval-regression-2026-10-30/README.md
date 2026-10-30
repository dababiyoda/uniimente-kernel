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
  - A refuted or ineffective run, or a regression, drops the tuple at once.
  - BOUNDED_AUTONOMY and MANAGE_BY_EXCEPTION are never earned from evidence.
  - It writes nothing and grants nothing.

## Commands and results

| Run | Command | Result |
|---|---|---|
| Fail-before (a), base `a6c29bbd`, new test file only | `python -B -m pytest -q -p no:cacheprovider tests/unit/test_greg_standing_approval_regression.py` in a detached worktree | collection error: `greg.autonomy` does not exist |
| Fail-before (b), base + test file + `greg/autonomy.py`, no body hook or CLI | same | **4 failed, 5 passed**: the ineffective, fresh-approval, refuted and climb/CLI tests fail. The ablation, verified-hold control, crash, dedupe and Wilson tests pass, as they should without the hook. |
| Pass-after | same, in `/home/user/wu09` | **9 passed** |
| Mutants | `python -B scripts/ci/check_standing_approval_regression_mutants.py` (scratch copy, `PYTHONDONTWRITEBYTECODE=1`, `__pycache__` purged before each run, baseline must pass) | **9/9 caught** |
| Related suites | `pytest -n 3` over test_greg_platform (incl. `test_guardrail_autonomy_is_not_authority`), _missions, _active_constraint, _answer_reverification, _appraisal_closure, _appraisal_retry_bound, _closure_integrity, _founder_and_scope, _goal_gravity_consumed_approval, _mission_book_incremental(_verified), _paid_approval_zero_booked, _paid_ask_withdrawn_after_spend, _paid_scope, _resilience, _restore, _restore_fold, _routing_integrity, _self_repair, _interface, test_autonomy and the new file | **473 passed, 1 skipped** (`test_greg_paid_approval_zero_booked`: no bubblewrap on this host) |

The 9 mutants each remove one safeguard:

1. the body hook;
2. the ineffective evidence;
3. the refuted evidence;
4. `voids_approval`;
5. the asked-before-the-run guard;
6. the once-per-call guard;
7. the reuse of a retained regression after a crash;
8. the level ceiling;
9. refuted counted as severe.

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
- **Upgrade effect:** on a body that already holds approvals, the failure evidence on its ledger regresses them the
  first time this code runs.
- **Tuple boundaries:**
  - The target pattern is the target's scheme (`workspace:c.txt` -> `workspace:*`).
  - Budget bands are $0, up to $1, $10 and $100, and over $100.
  - Both are first choices, not founder-ratified.
- **Behaviour change:** a standing mission whose first-ranked strategy was regressed now waits on the founder's
  re-ask, even when another standing strategy could heal the drift. Ranking is in `greg/missions.py`, which this
  unit does not edit.
