# Consistent backups of a running body, on a founder-signed cadence, each proven by a restore drill — 2026-10-30

Work unit WU-14 of the 2026-10-28 build directive (sections 47, 49 and 24: continuity after the loss of a disk or a
computer). Branch `claude/consistent-backup-restore-drill-20261030`, based on `a6c29bbd` (#196 head).

## The defect, reproduced first

`foundry/systems/seed.make_seed` copied every file of the body home and only then read the ledger head, with no
consistency between the two:

- A body appending in between produced a seed whose recorded head is not where its packed ledger ends.
  `greg.recovery.restore_body` refuses such a seed (`RestoreError: ... not at the head the seed recorded`).
- `ledger_head` called `json.loads` on the last line. A line still being written (no newline yet) made `make_seed`
  raise `JSONDecodeError`. A whole record without its newline was packed, and no restore accepts it.

The fail-before runs used a detached worktree of `a6c29bbd` with the new test files copied in.

| Test at `a6c29bbd` | Result |
|---|---|
| `tests/unit/test_greg_seed_consistency.py` | **6 failed**, 2 passed (the 2 are controls that pass before and after) |
| a seed taken while the body appends (one append injected per stored object) | `RestoreError: the restored ledger ends at ..., not at the head the seed recorded` |
| half a record at the end of the ledger | `json.decoder.JSONDecodeError: Unterminated string` from `make_seed` |
| a whole record without its newline | `RestoreError: the restored ledger does not verify: partial or blank history record` |
| a ledger that does not verify | packed into a seed without complaint (no `SeedError` existed) |
| a heartbeat rewritten during the copy | packed into the seed |
| a seed that carries a heartbeat naming a head the ledger lacks | `BodyError` when the restored body opens |
| `tests/integration/test_greg_backup_process.py` first test: 20 seeds taken from a real `python -m greg run` process (0.1 s ticks, intake every 5 ms) | **10, 5 and 7 of 20 seeds restored** in three runs; every failure was `RestoreError: ... not at the head the seed recorded` |
| `tests/unit/test_greg_backup.py` (part 2) | collection error: `cannot import name 'backup' from 'greg'` (the cadence did not exist) |

## What changed

### Part 1: a seed is consistent with itself (`foundry/systems/seed.py`)

- **The ledger first.**
  - It is read once, before any other file, and only its complete lines are packed.
  - In a GREG body, those lines are verified with `provenance.ledger.EvidenceLedger(read_only=True)`, exactly as
    `restore_body` verifies a restored ledger.
  - Their last record is the seed's `ledger_head`.
  - A ledger that does not verify raises `SeedError` instead of producing a seed that never restores.
  - The live ledger is never modified: no quarantine and no truncation.
- **Then every other file.** A file the body moved or removed after it was listed is left out. `os.walk` replaces
  `rglob`, so a directory removed while it is walked is ignored instead of raising.
- **Derived files are neither packed nor restored.**
  - `heartbeat.json` and `heartbeat.tmp` are rewritten by the body from its ledger.
  - Packed after the ledger, the heartbeat could name a head the packed ledger lacks. The restored body would then
    refuse its own history (`Body._require_published_head`).
  - The manifest lists them under `derived_not_packed`.
  - A restored body writes its own heartbeat on its first turn (tested).
  - The ledger's lookup indexes live only in memory and are rebuilt on every open.
- **`make_seed(..., end=<hash>)`**: an earlier recovery point. It must be a record of the verified prefix; otherwise
  `SeedError`.

### Part 2: a founder-signed cadence, each backup proven by a restore drill

The cadence is a standing mission over two new built-in capabilities in `greg/backup.py`. There is no new body
command and no edit to `greg/body.py`, `greg/missions.py` or `greg/templates.py`. Registration is one additive line in
`greg/capabilities.py`.

- **`body.backup_status`** (read_only) says whether the recovery point (`backed_up_at`) of the latest verified backup
  to the signed store is younger than the signed `rpo_seconds`.
  - It reads only the body's own ledger: the positive Gate receipts of `body.backup` dispatches whose witness names
    exactly that store.
  - A file in the store is never evidence; a seed placed there by hand does not count (tested).
- **`body.backup`** (internal_write) does three things:
  - writes one seed of the body to exactly the signed target `backup:<absolute path>`;
  - runs `greg.recovery.drill`;
  - returns the result.
- **The store.**
  - A store inside the body home or a read root is refused, by the action and by the sensor, and nothing is written.
  - So is a relative path or another target prefix.
- **`greg.recovery.drill`** is new, appended after `restore_body`, which is untouched. It:
  - restores the seed into a scratch home with `restore_body`;
  - re-verifies the restored ledger from its file;
  - reports the head it was restored to and that the body came back held;
  - removes the scratch home, whatever the outcome.
  A damaged object or a ledger that does not re-verify fails the action, so no verified receipt exists.
- **The recovery point is just before the backup's own dispatch** (`greg.backup.before_dispatch`).
  - A seed taken in the middle of the dispatch would hold the dispatch's claim but not its outcome.
  - The restored body would then ask a RECONCILIATION about that backup and block the cadence. This was observed
    in a probe before the change. The mutant that removes the earlier point is caught by the disk-loss test.
  - With the earlier point, after the founder's `BODY_RESUME` the restored body's cadence takes its next backup with
    no ask.
- **Failure.** When the store is unwritable or damaged, or a drill fails, the action fails. The mission raises exactly
  one founder ask (NO_STRATEGY), and the body keeps running.
- **No signed mission, no backup.** `python -m greg.backup --store DIR` prints the spec. The founder signs it with the
  existing `greg mission submit` (tested end to end through `greg.cli`).

## Commands and results (after)

Run from `/home/user/wu14` with `PYTHONDONTWRITEBYTECODE=1 /home/user/venv311/bin/python -B -m pytest -q -p no:cacheprovider`:

| Command | Result |
|---|---|
| `tests/unit/test_greg_seed_consistency.py` | 8 passed |
| `tests/unit/test_greg_backup.py` | 13 passed |
| `tests/integration/test_greg_backup_process.py` (two real `greg run` processes) | 2 passed. The race test, in each of 7 runs: 19-20 of 20 seeds taken while the body appended, **20 of 20 restored held**; the cadence test's first backup was verified and restored on a second "machine" |
| `tests/unit/test_greg_restore.py tests/unit/test_greg_restore_fold.py` plus the seed tests of `tests/unit/test_foundry_systems.py` (`-k "restore or seed or Seed or fold"`) | 28 passed |
| 14 capability, restore, Goal Gravity, platform and Spider-Web suites (`test_greg_capabilities`, `test_greg_capability_ask_label`, `test_greg_goal_gravity_surfaces`, `test_greg_interface`, `test_greg_platform`, `test_greg_spiderweb`, `test_greg_organ_exchange`, `test_greg_routing_integrity`, `test_greg_restore`, `test_greg_restore_fold`, `test_greg_seed_consistency`, `test_greg_backup`, `test_greg_goal_gravity_founder_effect`, `test_greg_goal_gravity_reattack`; `-n 3`) | 168 passed, 3 skipped |
| `python -m foundry.completion --run 46` (system #46's exercise) | unchanged result digest `sha256:3938fd98...` |
| `python -B scripts/ci/check_consistent_backup_mutants.py` | **16 of 16 mutants caught** (6 seed consistency, 2 earlier recovery point, 8 cadence and drill) |

The independent appraiser judges a backup hold VERIFIED from its receipts. `body.backup_status` is not in
`greg/appraisal.py`'s `REOBSERVABLE` set, which belongs to another open PR, so the appraiser does not re-observe it.

## Limitations

- **Scope and reality.**
  - Linux container only. Every key is a per-test key, not Alfonso's.
  - The store is a directory on the same disk in every test; an off-site or second-disk store is not exercised.
  - Not reboot-verified, not run on a founder device, not run against a real disk failure.
- **Not built.** Stores have no encryption at rest and no retention or pruning.
- **The cadence.**
  - A recovery point is at most the RPO plus the mission's cadence (at least 60 s) old.
  - After the one ask, the cadence waits for the founder to revise or re-sign the mission.
  - Its standing mission expires at its signed horizon (30 days by default) and asks for renewal like any mission.
- **Not built from the unit's design sketch.** The doctor and Mission Control line ("last verified backup N h old")
  and an availability ask that fires when the RPO elapses without the mission are recorded as follow-ups.
- **A coupling.** `before_dispatch` reads the engine's `greg.mission.dispatching` and grant records. A change to
  those formats falls back to the latest head, and the disk-loss test would then fail on the RECONCILIATION ask.
- **Untested by a dedicated test.** These are written for a running body's churn, but no test forces their race:
  - a file moved or removed between the listing and its read is left out;
  - a directory removed during the walk is ignored.
- **What a seed holds.**
  - Files other than the ledger may hold content newer than the recovery point (content-addressed extras).
  - A non-ledger file torn by a concurrent writer is packed as read.
  - In a home that is not a GREG body (no `constitution_hash`), the ledger's chain is not verified; only its torn tail
    is dropped.

## Reality level

**INTEGRATION-TESTED**: real `python -m greg run` body processes, real ledger appends, real restores, on this Linux
container with per-test keys. Not LOCAL-REAL on a founder device, not REBOOT-VERIFIED, not off-site.
