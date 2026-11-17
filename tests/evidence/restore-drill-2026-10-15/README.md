# Section 14 restore from a tested backup — 2026-10-15

Directive section 14 asks GREG to implement and measure "restoration from retained evidence and tested backups" and
to "choose recovery-time, recovery-point, detection, containment, duplicate-effect, and authority-continuity
thresholds before testing". It also says: "Every recovery and failover test must include revocation persistence";
"multiple copies must not become competing policy authorities"; and "Unresolved authority conflict blocks new
consequences." The requirement map listed "backup restore" as open.

## Order of work

1. `THRESHOLDS.md` and the reproduction were committed first (`119a287`), with no mechanism on the branch.
2. The mechanism followed (`ccb095b7`).

## The defect, reproduced first (`reproduction.log`, at `6a878655`)

GREG already had a backup: `greg foundry seed` writes a content-addressed Institutional Seed. Its test is named
"restores a real GREG body that verifies and reboots", but it verifies only the restored ledger, and never boots
the body.

The scenario:
1. the original body enrolls a phone, registers a mission whose write needs the founder's approval, and the
   founder approves it;
2. the seed is taken;
3. after the seed, the original executes the write, the founder revokes the phone, and the original accepts a
   second mission;
4. the machine is lost, and the seed is restored to the same path on a new one.

| At the base | Observed |
|---|---|
| The restored body boots | **no**: the seed excludes `witness.key` (correctly), and the founder is never given it |
| With the witness key copied by hand, the approved write | **executes a second time** (the original already did it) |
| The second mission's envelope, consumed by the original after the backup | **accepted again** |
| The phone the founder revoked after the backup | **delegated again**, and its approval is honoured |

Found while testing, also at the base: the seed holds files only, so a restored body had **no `inbox/`,
`processed/`, `rejected/` or `outbox/`**. A founder command dropped into the inbox would go unread.

## What was built

- **`foundry/systems/seed.py`.**
  - The seed records its recovery point: when it was taken, and the ledger head then.
  - `restore` refuses a manifest path outside the target, and any key material. Integrity proves the files match a
    manifest; it does not prove the manifest is benign.
- **`greg/recovery.py`, `restore_body`.**
  - **Verification:** the restored chain must verify and end at the recorded head.
  - **Layout:** it recreates the body's directories.
  - **A fresh witness key:** the original's never leaves its machine, and a witness is checked only at its own
    commit, so the history stays verifiable by its hash chain.
  - **The device private key is not needed:** nothing reads it at run time.
  - **What the restore records:** `body.restored`, with the recovery point and what is unknown after it.
  - **What it voids:**
    - every device delegation;
    - every approval a live mission held: it is withdrawn and asked again.
  - **The hold:** the body is held.
- **`greg/body.py`.**
  - A restored body refuses every command issued before the restore, because the original may already have
    applied it.
  - Only the founder key releases the restore hold. A device the founder enrols again after the restore may
    pause and resume later, but not release this hold.
- **`greg/missions.py`.** A withdrawal that voids an approval removes its scope, so the action is asked again.
- **`greg/cli.py`.** `greg foundry restore --store DIR --seed ADDRESS` restores into an empty `--home` and prints
  what only the founder can supply.

## The drill against the thresholds (`drill.log`)

| Threshold | Declared | Measured |
|---|---|---|
| Recovery time | ≤ 60 s for at least 200 records | restore, verify and boot of 200 records: **0.2 s** |
| Recovery point | the seed's recorded time; everything after it reported unknown | recorded and reported; nothing after it reconstructed |
| Detection | a tampered object, tampered manifest or wrong head never boots | tampered object: `IntegrityError`; wrong head: `RestoreError`; broken chain with the head intact: `RestoreError` (tests); no witness key written |
| Containment | 0 actions until a founder command issued after the restore | **0** |
| Duplicate effect | 0 pre-restore commands accepted; 0 pre-restore approvals used | the consumed mission is refused; the approved write executes **0** times after resume and is asked again; after a fresh decision it executes once |
| Authority continuity | 0 pre-restore delegations usable; only the founder key releases the hold | the phone revoked after the backup is unusable; a re-enrolled device cannot release the hold |
| Revocation persistence | revoked before or after the backup, the device stays unusable | the hold and the voids survive a restart |

## Verification

- `restore-tests.log`: `tests/unit/test_greg_restore.py`, 13 passed.
- `mutants.log`: 55 of 55 caught. Ten target this change:
  - delegations kept;
  - approvals kept;
  - a voided approval ignored by the engine;
  - no hold;
  - pre-restore commands accepted;
  - a device releasing the hold;
  - the recorded head not compared;
  - a broken chain restored;
  - the layout not restored;
  - a crafted seed writing outside its target.
- `full-suite.log`: at `ccb095b7`, 3872 passed, 5 failed, 25 skipped. The five are the environmental Landlock tests; they fail identically at the base and pass in CI. The tampered-manifest test was added after this run (test-only); `restore-tests.log` and `mutants.log` are on the final tree.

## Limits (stated in `THRESHOLDS.md` before the drill)

- **A second living copy is not detectable without an external anchor.** The founder's resume is the declaration
  that the original is gone; GREG cannot verify it.
- **A founder-key rotation after the recovery point is unknown** to the restored body, which trusts the key
  enrolled at the recovery point. The restore report tells the founder to rotate again.
- **External consequences after the recovery point** are re-asked, not reconciled with the external system.
- **Coverage:** the in-process authority cases run with fake clocks; the timed drill runs with the wall clock.
  No physical device, second machine or network partition was involved.
- **Older seeds:** a seed made before this change has no recorded recovery point. The head check is skipped and
  the report says so; every void and the hold still apply.

Nothing was sent, spent or activated. Every key is a per-test key. Authority delta: a restored body holds more
narrowly than before (it voids, refuses and holds); no authority is created. VEPMC: 0.
