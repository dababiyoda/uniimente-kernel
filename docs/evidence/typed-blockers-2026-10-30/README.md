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
  - The module records, signs, attaches and asks nothing, and never opens the secret broker.
- **`greg blockers [--mission ID]`.** A read-only CLI command that prints the module's records as JSON. The
  change is one parser block and one handler in `greg/cli.py`.
- **Morning report.** `greg/tribunal.py` adds a `blockers` section with the same records. It is used by
  `greg morning` and `morning_projection`.
- **Mission Control.** `projection()["blockers"]` holds the same records, and the Goal Chase view shows a
  "Blocked goals" table. Before editing, the open PRs were checked with the GitHub REST API (`pulls/N/files`)
  for every PR based on #196 or stacked on it: #201, #203, #206, #209, #211, #213-#215, #218, #220, #221 and
  #226-#236. None edits `greg/mission_control.py` or `greg/tribunal.py`. This session's sibling worktrees
  don't edit them either.
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
| `no_strategy` | `:2178` (a check's sensor is not read-only) | `_blocker_resolved` returns `(True, "re-evaluate strategies at cadence")` unconditionally (`:1682`) | **not listed**: see negatives |

Things that are not separate blocker kinds in code:

- **Budget and spend stops.** A spend beyond the signed budget is refused by the light cone (`lightcone.py:119`).
  The engine then raises a `decision` blocker on an APPROVAL ask whose resource is `spend` (`_spend_ask`,
  `missions.py:3069`). The record names the spend in `blocker` and the exact authority asked in
  `required_authority`.
- **Founder decisions** are the `decision` and `reconciliation` kinds above.
- **The retry-safe uncertain retry limit** (`RETRY_LIMIT`, `missions.py:57`). This is a back-off on a schedule
  that ends in replanning, not a blocker.
- **An input wait** (`mission.input_wait`, `missions.py:2190`) is a failing check, not a blocker.
- **Body-level holds** (`body.py:82` CRASH_LOOP_HOLD, `body.py:124` `body_pauses`) hold every mission and are
  not mission blockers. A record does name the mission's own pause, prefixed to `next_move`.

Section 29 names behaviours (WORK, WAIT, SLEEP, RETRY, RECONCILE, ESCALATE, REQUEST DECISION, RESUME, STOP), not
blocker kinds. No kind was invented for them.

## Commands and results

Fail-before ran in a detached worktree of `b1950be2` with only the new test file copied in. The worktree was
removed afterwards.

```
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider tests/unit/test_greg_blockers.py
```

| run | result |
| --- | --- |
| before (base `b1950be2`, final 21-test file) | 21 failed |
| after (this branch) | 21 passed |

On base, 20 tests fail with `ImportError: cannot import name 'blockers'`. The outage morning-report test fails
with `KeyError: 'blockers'`.

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
every run. The unmutated copy passes first. Result at `6a1a2a03`: **17/17 mutants caught**. Each mutant removes
one safeguard:

- the engine-rule filter;
- the ended-mission filter;
- the mission filter;
- the completeness guard;
- the "none required" reason guard;
- the engine choice;
- the read-only view's Genesis;
- finding the body home from the ledger;
- citing the current `mission.blocked` fact;
- the not-answerable branch;
- the outage's and the person step's "none required" authority;
- naming a capability for attach;
- the pause prefix;
- the CLI `--mission` filter;
- the morning-report section;
- the Mission Control section.

An earlier run on `c1a99797` caught 16/16; the named-capability mutant was added afterwards.

### Related suites

```
pytest -n 3 tests/unit/test_greg_{answer_reverification,closure_integrity,continuity,founder_asks,
  goal_gravity_surfaces,human_work,improvement_attacks,learning_gate,linear_genesis,mission_control_costs,missions,
  outcome_resolution,outcome_resolution_signed,presence,reconciliation,reconciliation_record,sop_compounding,
  active_constraint,blockers}.py tests/unit/test_morning_review.py
  tests/integration/test_greg_{mission_control,credentials_view}.py
```

Results at `6a1a2a03`:

- **This command:** 400 passed in 5 min 2 s.
- **An earlier run at an intermediate tree:** 396 passed.
- **The suites that scan the source tree:** `test_greg_mind_convergence`, `test_greg_platform`,
  `test_greg_runbook_commands`, `test_governance_integrity` and `test_cortex_pipeline` gave 230 passed.
- **The integration suites that build morning reports:** `tests/integration/test_one_machine{,_ten_steps,_attacks}.py`,
  `test_greg_{mcp_founder_path,mcp_act_founder_path,vendor_failures}.py` and the blocker tests, run with `-n 2`,
  gave 36 passed, 7 skipped and 1 failed.
  - The failure was `test_attack_founder_stop_during_ongoing_work_ends_the_worker_now`: a body SIGTERMed at the
    end returned -15.
  - It ran while the mutant gate was running on the same 4 cores.
  - Re-run alone, it passed (1 passed in 9.5 s). It is recorded as a timing failure under load.
  - The running body never calls code this unit changed. Its loop calls neither the morning report nor
    `greg/blockers.py`.

## Limitations and negatives

- **no_strategy is never listed.** The engine's rule treats it as resolved at every tick. The next tick lifts it
  and re-observes, and blocks again while the sensor is still not read-only. The scope requires reusing that rule,
  so the projection does not list it, although such a mission is in effect stuck. `greg status`
  (`active_constraint`) still shows it. Its typing is complete and tested on a real `mission.blocked` fact.
  Listing it would need `missions.py` to tell "re-evaluate" apart from "resolved", which is a follow-up for that
  file's owner.
- **Withdrawn asks.** A blocker whose ask was withdrawn but not yet lifted is listed until the next tick, with
  its own ask id. `_blocker_resolved` does not see withdrawals; `_finish_withdrawal` does.
- **Ended missions are not listed.** This includes a reconciliation the engine still waits on after a mission
  ended. That question stays on `greg decisions`.
- **Only the mission's own pause is named.** A body pause or crash-loop hold is not repeated in each record.
- **Text from the journal is shown as recorded.** The projection never reads the secret broker; a test makes the
  broker raise if opened and plants a value in it and the environment. If GREG ever wrote a secret into a
  `mission.blocked` reason, it would already be on the ledger and on every surface. Redacting that is out of
  scope.
- **Reading cost.** The read-only view re-runs `Genesis.restore(record=False)` on each call, which re-pins
  installed packages, so the cost grows with the number of formed capabilities.

## Reality level

UNIT-TESTED, with integration-tested surfaces. The evidence is in-process SANDBOX bodies with a test clock and
per-test founder keys, not Alfonso's. No founder device, no real outage and no external effect was involved.
VEPMC is unchanged at 0.

## Section 70: what can GREG now do that it could not before?

For every mission still pursued, GREG can now state in one place, from retained facts, what blocks it, why, when
that is reconsidered, what evidence and whose authority would lift it, and the next move: `greg blockers`, the
morning report and Mission Control. This covers every blocker type except the self-clearing `no_strategy`. Before
this change, an outage back-off showed only as `lifted_by: "outage"` and named no authority.
