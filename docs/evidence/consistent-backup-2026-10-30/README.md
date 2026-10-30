# Consistent backups of a running body, on a founder-signed cadence, each proven by a restore drill — 2026-10-30

Work unit WU-14 of the 2026-10-28 build directive (sections 47, 49 and 24: continuity after the loss of a disk or a
computer). Branch `claude/consistent-backup-restore-drill-20261030`, based on `a6c29bbd` (#196 head).

This record describes the branch head after the second review round. Earlier versions of this file described
`ec462575`, before the interrupted first-round commit `d96756b0`; their counts are superseded by the tables below.

## The defect, reproduced first

`foundry/systems/seed.make_seed` copied every file of the body home and only then read the ledger head, with no
consistency between the two:

- A body appending in between produced a seed whose recorded head is not where its packed ledger ends.
  `greg.recovery.restore_body` refuses such a seed (`RestoreError: ... not at the head the seed recorded`).
- `ledger_head` called `json.loads` on the last line. A line still being written (no newline yet) made `make_seed`
  raise `JSONDecodeError`. A whole record without its newline was packed, and no restore accepts it.

Fail-before runs used a detached worktree of the named commit with the current test files copied in, removed after.

| Run | Result |
|---|---|
| `tests/unit/test_greg_seed_consistency.py` at `a6c29bbd` | **16 failed, 3 passed** (the 3 are controls that pass before and after). Failures: `RestoreError ... not at the head the seed recorded` (concurrent append); `JSONDecodeError` (half a record); `RestoreError ... partial or blank history record` (whole record without newline); no `SeedError`; heartbeat packed; `BodyError` on a seed carrying a stale heartbeat; links followed and a hard-linked key packed; one unreadable file fails the seed; an intake item lost; a tool call's credential packed; a queue link followed; a swapped file packed |
| `tests/unit/test_greg_backup.py` at `a6c29bbd` | collection error: `cannot import name 'backup' from 'greg'` (the cadence did not exist) |
| `tests/integration/test_greg_backup_process.py` first test at `a6c29bbd` (20 seeds from a real `python -m greg run` process; run in round 0) | **10, 5 and 7 of 20 seeds restored** in three runs; every failure was `RestoreError ... not at the head the seed recorded` |

## Review rounds

### Round 1 (finished in this round)

A container restart interrupted the first fix round; its changes were committed unverified as `d96756b0`. This round
reviewed and verified them. They are:

- **The walk.** `os.fwalk` without following links, each file opened with `O_NOFOLLOW` after `lstat` says it is
  regular, and re-checked by `(st_dev, st_ino)` and `S_ISREG` after the open. A link, a device, a pipe, an unreadable
  file and another name (hard link) of key material are never packed. Each is listed with its reason in the
  manifest's new `not_packed`; one unreadable file no longer fails the whole seed.
- **The queue pre-read** (`QUEUES`: `inbox/`, `intake/`). The items waiting in the queues are read just before the
  ledger. At `ec462575` ("ledger first, then every other file") an intake item the running body consumed after the
  ledger was read was lost from the seed. Verified here: 2 of the 3 variants of
  `test_an_item_waiting_in_the_intake_is_never_lost...` fail at `ec462575` with `KeyError: 'intake/<item>.json'`; the
  third fails only because the test patches `seed._walk`, which `ec462575` lacks.
- **The store.** A backup refuses a store that does not exist (it never creates one), a store on the body's own
  filesystem unless the founder signs `accept_same_filesystem` (`python -m greg.backup --accept-same-filesystem`), a
  store that changes during the backup, a target not in canonical form and a path with a glob character.
  `mission` refuses an RPO shorter than twice the cadence.
- **Status reads the store too.** `body.backup_status` checks that the store is there and the latest seed is still in
  it, and returns `why` when it is not fresh.
- **The drill** also requires the restored body to come back held.

### Round 2 (this round)

| Finding | Disposition | Regression test (fails before the fix) |
|---|---|---|
| WU14-R2-1 downtime after a backup blocks the cadence | fixed | `test_a_body_stopped_between_a_backup_and_its_first_read_keeps_its_cadence_without_an_ask` (2 cases); `test_a_backup_already_older_than_the_rpo_when_taken_is_judged_by_its_age_at_its_first_read` |
| WU14-R2-2 MCP credential files packed | fixed | `test_a_tool_calls_credential_file_is_never_packed` |
| WU14-R2-3 `<store>/objects` link, mount, or home/read root inside it | fixed | `test_a_store_whose_objects_directory_is_a_link...` (2), `..._is_another_filesystem_is_refused`, `test_a_read_root_inside_the_stores_objects_is_refused` (2), `..._is_replaced_while_the_backup_is_written_is_refused`, `test_status_is_not_fresh_once_the_stores_objects_directory_is_a_link` |
| WU14-R2-4 tmpfs store accepted as another disk | fixed (memory filesystems refused); filesystem, not disk, compared, now stated | `test_a_store_held_in_memory_is_refused` |
| WU14-R2-5 rotten object stays fresh and blocks every later backup | fixed | `test_a_rotten_object_is_never_fresh_and_the_next_backup_rewrites_it` |
| WU14-R2-6 backup readable by other users | fixed (`objects` kept `0700`, refused when it cannot be) | `test_a_backup_is_private_to_the_bodys_user` |
| WU14-R2-7 memory grows by the largest file; no time bound | deferred: reproduced (+300 MiB RSS for one 300 MiB file, unchanged at this head); OOM and stop latency not run | none |
| WU14-FID-1 README describes `ec462575`, not the head | fixed (this file) | n/a |
| WU14-FID-2 README contradicts the head | fixed (this file) | n/a |
| WU14-FID-3 five round-1 safeguards survive removal | fixed: tests added, each now a caught mutant | `test_a_queue_that_is_a_link_packs_nothing_from_where_it_leads` (2), `test_a_file_swapped_between_its_listing_and_its_open_is_never_packed` (2), `test_status_is_not_fresh_once_a_store_taken_on_another_filesystem_is_on_the_bodys`, `test_a_backup_takes_no_parameter_but_the_signed_acceptance` |

The round-2 fail-before was run at `d96756b0` (the head before this round) with the current unit test files:
**15 failed, 44 passed, 2 errors**. The 2 errors are the stand-in-disk fixture, which stubs `backup._volatile`, absent
there. The FID-3 tests pass at `d96756b0` because the safeguards existed; their evidence is the mutants below. The
downtime tests fail there first on the new `current` field. Without those two field lines they fail on the behaviour:
in both cases the engine raises a `NO_STRATEGY` ask after the first backup (2 failed).

## What changed

### Part 1: a seed is consistent with itself (`foundry/systems/seed.py`)

- **The queues, then the ledger, read first.** The items waiting in `inbox/` and `intake/` are read just before the
  ledger. The ledger is read once, and only its complete lines are packed.
  - In a GREG body they are verified with `provenance.ledger.EvidenceLedger(read_only=True)`, exactly as
    `restore_body` verifies a restored ledger. A ledger that does not verify raises `SeedError`.
  - Their last record is the seed's `ledger_head`.
  - The live ledger is never modified.
  - An item waiting just before the ledger is carried even if the body consumes it next. The restored body reads it
    again as a retained fact (intake) or a spent nonce (inbox), never a second effect.
- **Then every other file**, by `os.fwalk` with `O_NOFOLLOW` opens and an inode re-check (round 1, above).
- **Never packed.**
  - Key material (`SECRET_MARKERS`) and any other name of it.
  - Derived files (`heartbeat.json`, `heartbeat.tmp`), which are also never restored. Packed after the ledger, the
    heartbeat could name a head the seed lacks, and the restored body would refuse its own history. The restored body
    writes its own on its first turn (tested).
  - A tool call's credential and scratch directories, `workspace/<mission>/<greg.mcp_tools.LEFTOVER>/`. They are
    listed in `excluded_secrets`.
- **A rotten stored object is rewritten.** If an object an earlier seed stored no longer hashes to its address, the
  correct bytes this seed holds replace it atomically (`cas.repair`). The address is listed in the manifest's
  `repaired_objects`. Before, `cas.put` raised on it, and every later seed failed.
- **`make_seed(..., end=<hash>)`** packs an earlier recovery point, which must be a record of the verified prefix.

`foundry/systems/cas.py` gains two functions, and `put` is unchanged in behaviour:

- `repair` rewrites one object.
- `intact` re-hashes an object in 1 MiB chunks.

### Part 2: a founder-signed cadence, each backup proven by a restore drill (`greg/backup.py`)

It is a standing mission over two built-ins. There is no new body command and no edit to `greg/body.py`,
`greg/missions.py` or `greg/templates.py`; registration is one additive line in `greg/capabilities.py`.

- **`body.backup`** (internal_write):
  - writes one seed to exactly the signed target `backup:<absolute path>`;
  - runs `greg.recovery.drill`: restore into a scratch home, re-verify the restored ledger from its file, require the
    body held, report the restored head, remove the scratch home;
  - returns the result. The Gate's positive receipt of that output is the only record that a backup is verified.
- **The store is refused when:**
  - it is inside or equal to the body home or a read root, or the home or a read root is, or lies inside,
    `<store>/objects`;
  - it does not exist;
  - it is on a memory filesystem (`tmpfs`, `ramfs`), read from `/proc/self/mountinfo`. Where that file is
    unavailable, the type is not checked;
  - it is on the body's own filesystem, unless `accept_same_filesystem` is signed. The comparison is `st_dev`: two
    filesystems of one disk pass;
  - `<store>/objects` is a link, on another filesystem than the store, holds a link, or cannot be kept `0700`;
  - the store or `objects` changes during the backup;
  - the target is not in canonical form, or the path holds a glob character.
- **`body.backup_status`** (read_only) returns:
  - `fresh`: the latest verified backup's recovery point is younger than the RPO, the store and `objects` are where
    they were, and the manifest and every object re-hash to their addresses;
  - `current`: fresh, or this is the first receipted read of the store since the latest verified backup and that
    backup was within the RPO when taken. The read in progress has no receipt yet. The mission's check reads
    `current`. The engine judges a backup by the next read of its check. A body stopped, asleep or paused before that
    read for longer than the RPO used to blame the backup it had just taken, and ask the founder (R2-1). The next read
    judges by age, so a backup is due again at most one cadence after the body runs again;
  - `why`: what is not fresh;
  - `first_read`.
- **The recovery point is just before the backup's own dispatch** (`before_dispatch`). A restored body finds no
  interrupted backup to reconcile. After the founder's `BODY_RESUME`, its cadence takes the next backup with no ask
  (tested).
- **The RPO must be at least twice the cadence.** The body reads the check once per cadence, so the recovery point can
  pass the RPO by up to one cadence; the rule keeps that to at most half the RPO.
- **Failure.** When the store is unwritable or the drill fails, the action fails. The mission asks the founder once
  (`NO_STRATEGY`), and the body keeps running. A rot found after its first read is a new backup, not an ask.
- **No signed mission, no backup.** `python -m greg.backup --store DIR [--accept-same-filesystem]` prints the spec;
  the founder signs it with `greg mission submit` (tested through `greg.cli`).

## Commands and results at this head

Run from `/home/user/wu14` with `PYTHONDONTWRITEBYTECODE=1 /home/user/venv311/bin/python -B -m pytest -q -p no:cacheprovider`:

| Command | Result |
|---|---|
| `tests/unit/test_greg_seed_consistency.py tests/unit/test_greg_backup.py` | **61 passed** (19 + 42) |
| `tests/integration/test_greg_backup_process.py -s` (two real `greg run` processes) | **2 passed**; 20 of 20 seeds taken while the body appended, 20 of 20 restored held; the cadence's first backup verified, restored on a second "machine", its `objects` `0700` |
| `-n 2` on `test_foundry_systems`, `test_greg_restore`, `test_greg_restore_fold`, `test_greg_capabilities`, `test_greg_capability_ask_label`, `test_greg_mcp_tools`, `test_greg_mcp_act`, `test_greg_mcp_worker`, `test_greg_packaging`, `test_ledger_tail_recovery`, `test_seed_compatibility_seal`, `test_seed_replay_seal`, `test_seed_genome_continuity`, `test_greg_seed_compat` | **211 passed, 8 skipped** |
| `tests/unit/test_greg_owned_company.py` (the remaining test file that imports `cas`, `seed` or `recovery`) | **13 passed** |
| `python -B tests/evidence/restore-drill-2026-10-15/drill.py` | exit 0; restore-drill evidence unchanged in kind (held after boot, head mismatch and tampered object refused) |
| every `tests/unit/test_greg_*.py` plus `test_foundry_systems.py` and `test_ledger_tail_recovery.py` | **not repeated at this head** (the machine was shared and runs were kept targeted). A reviewer's run at `d96756b0` gave 2825 passed, 76 skipped, 0 failed; that is their evidence, not this round's |
| `python -m foundry.completion --run 36` and `--run 46` | result digests `sha256:1a6f5c27...` (#36) and `sha256:3938fd98...` (#46), identical to `a6c29bbd`'s |
| `python -B scripts/ci/check_consistent_backup_mutants.py` | **55 of 55 mutants caught**, exit 0: 6 seed consistency, 2 earlier recovery point, 8 cadence and drill (round 0); 17 from round 1; 22 from round 2 |
| anchors of the 7 seed/recovery mutants in `scripts/ci/check_cognition_residual_mutants.py` | each still matches exactly once (that script was not run) |

The independent appraiser judges a backup hold VERIFIED from its receipts. `body.backup_status` is not in
`greg/appraisal.py`'s `REOBSERVABLE` set, which another open PR edits, so the appraiser does not re-observe it.

## Limitations

- **Scope and reality.**
  - Linux container only. Every key is a per-test key, not Alfonso's.
  - Every real store in these tests is on the container's one disk, with `accept_same_filesystem` signed. This
    machine's only other writable filesystem is `/dev/shm`, a tmpfs, which is now refused. The tests that need
    "another filesystem" use it with the memory-filesystem check stubbed. No second disk, off-site store or real
    disk failure was exercised. Nothing was reboot-verified or run on a founder device.
- **What "another filesystem" means.** `st_dev` distinguishes filesystems, not disks. Two partitions or btrfs
  subvolumes of one disk pass without `accept_same_filesystem`, and survive only what that disk survives. Memory
  filesystems are detected only where `/proc/self/mountinfo` exists (not macOS).
- **Privacy.** Every object lies under `<store>/objects`, kept `0700`. The objects themselves are `0644` inside it.
  There is no encryption at rest. A store directory that other users can write can still be raced during a backup.
  The before/after identity check then refuses to count the backup, but the objects written meanwhile may have
  landed where the race pointed.
- **Memory and time (R2-7, deferred).** `make_seed` reads each file whole, and the drill's restore reads each object
  whole: the body's memory grows by the largest file (+300 MiB measured for one 300 MiB file). The drill writes a
  full copy under the system temp directory. Nothing bounds a backup's time or checks the body's stop flag between
  files. OOM and stop latency were not run. Follow-up: stream files into and out of CAS, cap very large files with a
  `not_packed` reason, place the drill's scratch beside the store.
- **Cost.**
  - `body.backup_status` re-hashes every object of the latest backup on every read (once per cadence).
  - `before_dispatch`, status and every seed each load and verify the whole ledger read-only.
  - None of this was measured on a large body or ledger.
- **The cadence.**
  - A recovery point is at most the RPO plus one cadence old while the body runs. After the body was down, it is at
    most one cadence older than when the body runs again.
  - A rot or loss found in the window between a backup and its first read blames that backup: one `NO_STRATEGY` ask.
  - A status read of the same store by another mission counts as that store's first read.
  - The standing mission expires at its signed horizon (30 days by default).
- **Couplings.**
  - `before_dispatch` reads the engine's `greg.mission.dispatching` and grant records.
  - `current` reads the Gate's `body.backup_status` witnesses and receipts.
  - A format change falls back to the latest head (the disk-loss test then fails on a RECONCILIATION ask), or
    loses the first-read rule (the downtime tests then fail).
- **What a seed holds.**
  - Files other than the ledger and the queues may hold content newer than the recovery point.
  - A non-ledger file torn by a concurrent writer is packed as read.
  - In a home without `body.json`'s `constitution_hash`, the ledger chain is not verified; only its torn tail is
    dropped.
- **Not built from the unit's design sketch.**
  - The doctor and Mission Control line ("last verified backup N h old").
  - An availability ask when the RPO elapses with no cadence mission.
- No change was pushed and no PR was opened.

## Reality level

**INTEGRATION-TESTED**: real `python -m greg run` body processes, real ledger appends, real restores, on this Linux
container with per-test keys. Not LOCAL-REAL on a founder device, not REBOOT-VERIFIED, not off-site.
