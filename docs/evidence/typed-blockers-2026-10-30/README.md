# Typed blockers (directive section 29), 2026-10-30

Work unit MU-E of the 2026-10-28 OPUS MAXIMUS build directive (sections 29, 30 and 70). Branch
`claude/typed-blockers-20261030`, based on `b1950be2` (#196 head).

Section 29 says: "Blocked goals remain durable. Store: blocker, why blocked, reconsideration condition, required
evidence, required authority, next possible move."

## What changed

- **`greg/blockers.py` (new, read-only).** It folds the journal through the one `MissionBook` and keeps every
  mission that is still pursued and holds a blocker. It then asks the engine's own rule,
  `MissionEngine._blocker_resolved`, whether that blocker still holds. The rule is imported, not copied: the
  module calls it on a `MissionEngine` built over a read-only registry view (`registry_view` plus
  `Genesis.restore(record=False)`, the view the independent appraiser already uses), or on the running body's
  engine when the caller has one.
  - Each blocker that still holds becomes one record: `{mission_id, kind, blocker, why, reconsider_when,
    required_evidence, required_authority, next_move, since, source_event}`.
  - `since` and `source_event` come from the `mission.blocked` fact that recorded the blocker.
  - Every field is non-empty text. A field that does not apply reads `none required: <reason>`.
  - A record missing a field raises `BlockerError` and is never shown half-typed.
  - A blocker the next tick lifts is not listed: one `_blocker_resolved` treats as resolved, or one whose ask the
    body withdrew (the `withdrawn` marker `missions.active_constraint` already sets; `_step` then runs
    `_finish_withdrawal`). While a pause or hold is in force that tick does not come: `_step` returns PAUSED first,
    and a paused or held body returns before `engine.tick` (`body.py:952`). So such a blocker is listed with
    `nothing to answer`, and every record under a hold leads with each hold and what lifts it. The holds are
    `active_constraint`'s `paused_by` over `body.body_pauses` (signed BODY_PAUSE, crash-loop hold, restore hold,
    the PAUSE file) and the mission's own LIFECYCLE pause, so the record and `greg status` name the same holds.
  - `section()` is the guarded form the founder surfaces use. If the records cannot be computed, for example
    because a formed capability no longer restores or a record could not be typed, the section reads
    `{"unavailable", "error"}` in their place. It is never an empty list, and every other section stays.
  - The module records, signs, attaches and asks nothing, and never opens the secret broker.
- **`greg blockers [--mission ID]`.** A read-only CLI command that prints the module's records as JSON. The
  change is one parser block and one handler in `greg/cli.py`.
- **Morning report.** `greg/tribunal.py` adds a `blockers` section (`blockers.section`) with the same records. It
  is used by `greg morning` and `morning_projection`.
- **Mission Control.** `projection()["blockers"]` is the morning report's section, computed once. The Goal Chase
  view shows a "Blocked goals" table, or the reason the section could not be computed. Before editing, the open
  PRs were checked with the GitHub REST API (`pulls/N/files`) for every PR based on #196 or stacked on it: #201,
  #203, #206, #209, #211, #213-#215, #218, #220, #221 and #226-#236. None edits `greg/mission_control.py` or
  `greg/tribunal.py`. This session's sibling worktrees don't edit them either.
  - In round two, all 167 open PRs of the repository were checked the same way (2026-10-30).
  - Six older PRs also touch these files: #178 (`mission_control.py` and `tribunal.py`) and #115, #119, #120, #121
    and #122 (`tribunal.py`).
  - The heads of #178, #120 and #122 are ancestors of the base `b1950be2`, so they are already integrated.
  - #115, #119 and #121 are not. They are drafts on older bases, last updated 2026-10-02, and none is based on
    #196.
  - This unit's `tribunal.py` change is two added lines at the end of `morning_report`. Under a strict reading of
    the scope ("not edited by any open PR"), those two lines should move to a follow-up; that is left to the
    integrator.
- Not edited: `greg/missions.py`, `greg/asks.py`, `greg/genesis.py` and every file on the avoid list.

## Blocker kinds that exist in code (base `b1950be2`)

There are six mission blocker types. All are set by `MissionEngine._block`, and `_blocker_resolved` is at
`greg/missions.py:1658`.

| kind | raised at | what lifts it (engine) | record |
| --- | --- | --- | --- |
| `decision` | `missions.py:1821` (SCOPE_RENEWAL, expired mandate), `:1929` (SENSOR_FAILURE), `:2207` (SENSOR_SCOPE), `:3175` (NO_STRATEGY ask: "no admissible strategy", with `failing_checks`), `:3363` (APPROVAL for one exact scope) | a counted founder answer (`:1660`). SCOPE_RENEWAL takes no DECISION (`missions.py:68`, `asks.py:372`). A withdrawn request is finished at the next tick (`_finish_withdrawal`, `:1631`). A `failing_checks` blocker is also watched (`_watch_while_blocked`, `:2276`) | listed |
| `reconciliation` | `:1976`, `:2549` | a counted `reconcile_*` answer (`:1660`) | listed |
| `capability` | `:2721` (after a Genesis search found nothing to attach; deficits at `genesis.py:1078`/`:1182`, offers at `:1282`/`:1300`/`:1826`/`:1840`) | the registry reports the named capability usable, or `Genesis.serving`, `construction_ready` or `recovered_for` finds one (`:1662-1680`) | listed |
| `human_work` | `:2768` (functions under `asks.py:58` `HUMAN_WORK`) | observing the deliverable (`_watch_while_blocked`); `_blocker_resolved` never resolves it (`:1686`) | listed |
| `outage` (back-off) | `:2499`, then blocked at `:2512` | `_after_outage` (`:2589`) re-runs the search once `retry_at` passes; from the 5th consecutive outage (`:2482`) the founder is also told (CAPABILITY_ATTACH ask). `_blocker_resolved` never resolves it (`:1684`) | listed |
| `no_strategy` | `:2178` (a check's sensor is not read-only) | `_blocker_resolved` returns `(True, "re-evaluate strategies at cadence")` unconditionally (`:1682`) | **not listed** unless a pause or hold keeps it: see negatives |

Every decision ask kind is built on a real body in the tests: APPROVAL as a paid scope stop and as a budget stop,
SCOPE_RENEWAL, NO_STRATEGY (with `failing_checks`), SENSOR_FAILURE and SENSOR_SCOPE.

Things that are not separate blocker kinds in code:

- **Budget and spend stops.** A spend beyond the signed budget is refused by the light cone (`lightcone.py:119`).
  The engine then raises a `decision` blocker on an APPROVAL ask whose resource is `spend` (`_spend_ask`,
  `missions.py:3069`). The record names the spend in `blocker`, the overrun in `why` ("cost 2.0 with 0.0 spent
  exceeds budget 1.0") and the exact authority asked in `required_authority`. The `over_budget` fixture tests this.
- **Founder decisions** are the `decision` and `reconciliation` kinds above.
- **The retry-safe uncertain retry limit** (`RETRY_LIMIT`, `missions.py:57`). This is a back-off on a schedule
  that ends in replanning, not a blocker.
- **An input wait** (`mission.input_wait`, `missions.py:2190`) is a failing check, not a blocker.
- **Body-level holds** (`body.py:82` CRASH_LOOP_HOLD, `body.py:124` `body_pauses`) hold every mission and are
  not mission blockers. Each record under one names it and what lifts it, prefixed to `next_move` and
  `reconsider_when`, as it does the mission's own pause.

Section 29 names behaviours (WORK, WAIT, SLEEP, RETRY, RECONCILE, ESCALATE, REQUEST DECISION, RESUME, STOP), not
blocker kinds. No kind was invented for them.

## Commands and results

Fail-before ran in a temporary detached worktree with only the new test file copied in, first at the base
`b1950be2` and then at the previous head of this branch, `4f109258`, which is the state the reviewers attacked.
The worktree was removed afterwards.

```
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider -n 3 tests/unit/test_greg_blockers.py
```

| run | result |
| --- | --- |
| before (base `b1950be2`, final 33-test file) | 33 failed |
| before (previous head `4f109258`, final 33-test file) | 8 failed, 25 passed |
| after (this branch) | 33 passed |

- **On base**, 31 tests fail with `ImportError: cannot import name 'blockers'`. Two fail with
  `KeyError: 'blockers'`: the outage morning-report test, and the test where a capability no longer restores.
- **On `4f109258`**, the eight failures are the regression tests for the review findings below. Each fails for
  the reported reason:
  - the withdrawn ask is still listed as one to answer;
  - the outage under a BODY_PAUSE says "nothing for you to do";
  - the answered decision of a paused mission, the decision under a PAUSE file, and the paused `no_strategy`
    blocker all list no record;
  - the morning report raises `IsADirectoryError` and `BlockerError`;
  - the pause prefix has its old wording.

  The new over-budget, NO_STRATEGY, SENSOR_FAILURE and SENSOR_SCOPE fixtures pass on `4f109258`. They closed
  coverage gaps, not code defects.

The defect reproduces. On base, an outage blocker appears on three surfaces and none of them carries a required
authority. The probe is `outage_surfaces.py` in this folder, run as `python -B outage_surfaces.py <repo root>`
against a tree that holds the new test file:

```
status.active_constraint:          outage_shown=True  required_authority_field=False
status.decisions_required:         outage_shown=False required_authority_field=False
morning.q4_intentionally_not_done: outage_shown=True  required_authority_field=False
morning.q13_tonight:               outage_shown=True  required_authority_field=False
morning.blockers:                  outage_shown=False required_authority_field=False   (base: no such section)
```

After the change, the first four lines are unchanged and the new section reads
`morning.blockers: outage_shown=True required_authority_field=True`.

On base, `active_constraint` gives the outage `"lifted_by": "outage"`. After the change, the morning report's
`blockers` section types it with `required_authority: "none required: the re-run searches under the mission's own
signed scope and budget and asks for no new authority"`. Its `reconsider_when` gives the back-off time.

### Mutants

```
PYTHONDONTWRITEBYTECODE=1 python -B scripts/ci/check_typed_blockers_mutants.py
```

The script uses a scratch copy, `python -B` and `PYTHONDONTWRITEBYTECODE=1`, and purges `__pycache__` before
every run. The unmutated copy passes first. Result after the review fixes (28 mutants): **28/28 caught**. Each
mutant removes one safeguard:

- the engine-rule filter, the ended-mission filter and the mission filter;
- the completeness guard and the "none required" reason guard;
- the engine choice, the read-only view's Genesis, and finding the body home from the ledger;
- citing the current `mission.blocked` fact;
- the not-answerable branch, and the NO_STRATEGY ask's re-observation clause;
- the outage's and the person step's "none required" authority;
- naming a capability for attach;
- the CLI `--mission` filter, the morning-report section and the Mission Control section.

Added for the review findings:

- the hold prefix;
- reading the mission's own pause, the body's pauses and holds, and the PAUSE file;
- the withdrawn marker;
- listing a resolved or withdrawn blocker under a hold, and typing it as owing nothing;
- the outage's "nothing for you to do" under a hold;
- the guarded section, both in its failure value (never an empty list) and in its use by the morning report;
- Mission Control rendering an unavailable section.

The first run of the 28 caught 27. The survivor was an invalid mutant, not a gap:
`return [] or {...}` still returns the dict, because `[]` is falsy. It was rewritten as `return []; {...}` and
caught on the full re-run. Earlier runs: 17/17 at `6a1a2a03` and 16/16 at `c1a99797`.

### Related suites

```
pytest -n 2 tests/unit/test_greg_{answer_reverification,closure_integrity,continuity,founder_asks,
  goal_gravity_surfaces,human_work,improvement_attacks,learning_gate,linear_genesis,mission_control_costs,missions,
  outcome_resolution,outcome_resolution_signed,presence,reconciliation,reconciliation_record,sop_compounding,
  active_constraint,blockers}.py tests/unit/test_morning_review.py
  tests/integration/test_greg_{mission_control,credentials_view}.py
```

Results after the review fixes (`742a5b0d`):

- **This command:** 412 passed in 8 min 58 s. Round one gave 400 passed at `6a1a2a03`; the 12 new tests in
  `test_greg_blockers.py` account for the difference.
- **The suites that scan the source tree:** `test_greg_mind_convergence`, `test_greg_platform`,
  `test_greg_runbook_commands`, `test_governance_integrity` and `test_cortex_pipeline`, run with `-n 2`, gave
  230 passed.
- **The integration suites that build morning reports:** `tests/integration/test_one_machine{,_ten_steps,_attacks}.py`,
  `test_greg_{mcp_founder_path,mcp_act_founder_path,vendor_failures}.py` and the blocker tests, run with `-n 2`,
  gave 48 passed, 7 skipped and 1 failed.
  - The failure was `test_attack_founder_stop_during_ongoing_work_ends_the_worker_now`: a body SIGTERMed at the
    end returned -15. It failed the same way in round one.
  - Run alone four times on this branch, it passed once and failed three times.
  - Run alone twice on base `b1950be2`, in a temporary worktree that was then removed, it failed once and passed
    once. The flake exists on base too.
  - The load average was about 4.5 on 4 cores, with other agents running tests.
  - The running body's loop calls `tribunal.critique`, never `morning_report`, `greg/blockers.py` or Mission
    Control. It is recorded as a pre-existing timing failure under load, not as caused by this unit.

## Review findings (second round) and their disposition

Two reviewers attacked `4f109258`. Every finding was reproduced on that head before it was fixed, by running the
reviewers' probes in this worktree. Each fix has a regression test that fails on `4f109258`.

- **F1: a formed capability that no longer restores took down the founder surfaces. Fixed.** The read-only view
  runs `Genesis.restore`. When it raised (for example `IsADirectoryError` on a pinned binary path that is now a
  directory, the state in which the body itself cannot start), `morning_projection`, the morning page and Mission
  Control raised with it. A `BlockerError` did the same.
  - The surfaces now use `blockers.section`, which shows `{"unavailable", "error"}` in place of the records. Every
    other section stays, and Mission Control shows the reason in the Goal Chase view.
  - `greg blockers` still fails loudly with the exception: it is the dedicated command, and an empty answer would
    be false.
  - Tests: `test_a_capability_that_no_longer_restores_...` and `test_a_record_the_projection_cannot_type_...`.
- **F2 / TB-2: a withdrawn but not yet lifted ask told the founder to answer it. Fixed.** `MissionEngine.answer`
  refuses such a request.
  - The projection now reuses the `withdrawn` marker of `missions.active_constraint`. Such a blocker is lifted by
    the next tick (`_finish_withdrawal`), so it is not listed.
  - Under a pause or hold, it is listed with "nothing to answer" and the withdrawal's reason.
  - Test: `test_a_withdrawn_ask_never_sends_the_founder_to_answer_it`.
- **F3: under a body hold, the outage record said "nothing for you to do". Fixed.**
  - Every record under a hold now leads `next_move` and `reconsider_when` with each hold and what lifts it, read
    through `active_constraint`'s `paused_by` over `body.body_pauses`.
  - The outage drops "nothing for you to do" while a hold is in force.
  - Tests: `test_a_body_pause_names_what_lifts_it_...` (signed BODY_PAUSE) and `test_a_pause_file_is_a_hold_too_...`.
  - The crash-loop and restore holds come from the same `body_pauses` call and are not built separately here.
- **F4 / TB-1: a paused mission whose decision was answered disappeared from the blocked list. Fixed.**
  `_step` returns PAUSED before any resolution, so the blocker is held until a signed LIFECYCLE ACTIVE.
  - It is now listed with the pause, "nothing to answer", the recorded answer, and the resume as its required
    authority.
  - The same rule lists a paused `no_strategy` blocker, which `_blocker_resolved` always treats as resolved.
  - Tests: `test_a_paused_mission_whose_decision_was_answered_...` and `test_a_paused_self_clearing_no_strategy_...`.
- **TB-3: the fixture called "the budget stop" was a paid scope stop. Fixed.** `paid_approval` is relabelled. A
  new `over_budget` fixture (capability inside the cone, cost 2.0, budget 1.0) is in `SHOWN`. Its record says
  "cost 2.0 with 0.0 spent exceeds budget 1.0".
- **TB-4: three decision ask kinds and the NO_STRATEGY re-observation clause were untested. Fixed.**
  - New fixtures `no_strategy_ask`, `sensor_failure` and `sensor_scope` are in `SHOWN`.
  - `test_each_decision_ask_kind_names_its_ask_and_what_it_asks` asserts the NO_STRATEGY `reconsider_when` text.
  - The mutant that drops that clause is caught.

## Limitations and negatives

- **An unpaused no_strategy blocker is never listed.** The engine's rule treats it as resolved at every tick. The
  next tick lifts it and re-observes, and blocks again while the sensor is still not read-only. The scope requires
  reusing that rule, so the projection does not list it, although such a mission is in effect stuck. Under a pause
  or hold it is listed, because then no tick lifts it. `greg status`
  (`active_constraint`) still shows it. Its typing is complete and tested on a real `mission.blocked` fact.
  Listing it would need `missions.py` to tell "re-evaluate" apart from "resolved", which is a follow-up for that
  file's owner.
- **"The next tick lifts it" assumes the body runs.** A blocker the next tick would lift (answered, resolved or
  withdrawn) is not listed when no pause or hold is in force. If the body process is simply down, that tick
  waits until it runs again. `greg status` says the same (`lifted_by: the next tick`).
- **A withdrawn shared ask** is treated like any withdrawn ask, as `active_constraint` treats it. The next tick
  asks again about the undecided part (`_shared_ask_lapsed`) rather than lifting it.
- **Ended missions are not listed.** This includes a reconciliation the engine still waits on after a mission
  ended. That question stays on `greg decisions`.
- **`greg blockers` fails loudly** when the records cannot be computed (for example when a formed capability no
  longer restores). Only the morning report and Mission Control degrade to the `unavailable` section.
- **The console's /morning page** (`greg/console.py`, avoid-listed for this unit) shows a fixed list of morning
  sections and not `blockers`. Mission Control's Goal Chase view does show them.
- **Text from the journal is shown as recorded.** The projection never reads the secret broker; a test makes the
  broker raise if opened and plants a value in it and the environment. If GREG ever wrote a secret into a
  `mission.blocked` reason, it would already be on the ledger and on every surface. Redacting that is out of
  scope.
- **Reading cost.** The read-only view re-runs `Genesis.restore(record=False)` on each call, which re-pins
  installed packages, so the cost grows with the number of formed capabilities. Mission Control reuses the
  morning report's section, so one page view pays it once.
- **Holds built in the tests:** a signed BODY_PAUSE, the PAUSE file and a mission's LIFECYCLE pause. The
  crash-loop and restore holds reach the projection through the same `body_pauses` call, but no test builds them
  here.

## Reality level

UNIT-TESTED, with integration-tested surfaces. The evidence is in-process SANDBOX bodies with a test clock and
per-test founder keys, not Alfonso's. No founder device, no real outage and no external effect was involved.
VEPMC is unchanged at 0.

## Section 70: what can GREG now do that it could not before?

For every mission still pursued, GREG can now state in one place, from retained facts, what blocks it, why, when
that is reconsidered, what evidence and whose authority would lift it, and the next move: `greg blockers`, the
morning report and Mission Control. This covers every blocker type except an unpaused, self-clearing
`no_strategy`. Under a pause or hold, a record says so first and names what lifts it. A surface that cannot
compute the records says why instead of crashing or showing none. Before this change, an outage back-off showed
only as `lifted_by: "outage"` and named no authority.
