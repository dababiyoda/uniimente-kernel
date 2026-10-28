# A body's memory no longer holds every payload in its history (2026-10-28)

Status: **changed on draft branch `claude/bounded-body-memory-arm-engines`, a child of #196; not merged.**
It changes how `provenance/ledger.py` and `events/spine.py` hold retained records in memory. The file
format, hashes, events and verification points are unchanged. Accepting, changing or reverting it is the
founder's and the #196 integrator's decision. It creates no authority and changes no Consequence Gate byte.

Session: `session_01Kucyfm6YBHMTjaiC1M9hqD`. Claim: kernel issue #96, comment 6472033495.

## Why

The founder wants a body that keeps working while they are away, for months
(INTENT-GREG-EMBODIED-2026-09-11, INTENT-2026-09-22-FIRST-BODY; `greg/path.json` horizon
`persistent_goal_pursuit`, N1). `FINDING-LEDGER-APPEND-COST-2026-10-14.md` measured the next limit after
tick time: the ledger kept every record's payload in memory, about 2.45 KB of resident memory per
retained record. A mission observed once a minute writes about 18,700 records a day: about 46 MB a day,
so 1 GB in about three weeks. On a 4–8 GB Chromebook the body runs out of memory long before disk.
That finding listed three options. This is option 1, "keep payloads on disk". Its own words: "Nothing
written changes. Verification still reads everything, now from disk." The next measurement showed the
last clause does not hold up on the commit path, so the mechanism below differs from it there.

## Measured first (baseline `190c58fb`, #196's head)

Same scenario as the earlier finding: a real body, one holding mission, infinite closure, 60 s cadence, a
simulated clock, 1,800 ticks (`scripts/measure_body_memory.py`; Python 3.11.17, 4-core container).

- **Resident memory:** 2,639 B per retained record from 7,820 to 23,420 records
  (`docs/evidence/body-memory-2026-10-28/baseline-190c58fb-rss.json`).
- **Python heap (tracemalloc):** about 2,270 B per record. About 65% is parsed payloads (`json/decoder.py`),
  22% is the ledger's own records and indexes, and 5% is the Consequence Gate's in-memory grants
  (`baseline-190c58fb-heap-attribution.json`).
- **Disk:** 722 B per record.

## Change

1. **The newest payloads stay in memory; older ones live only in the file.**
   - A file-backed ledger keeps the payloads of the genesis record and the newest `RESIDENT_RECORDS`
     (1,024) records, exactly as before.
   - Older records keep a skeleton: sequence, type, hashes, timestamp, `corrects`, hash version, the
     line's offset and length, and the SHA-256 of the line's bytes.
   - Reading such a payload reads the line back with `pread` and refuses it unless its SHA-256 equals the
     digest recorded when those bytes were written or verified.
   - Readers get a new object every time, so a reader still cannot change retained evidence.
   - An in-memory ledger keeps everything, as before.
2. **What stays of dropped history is held to a running digest.**
   - One SHA-256 runs over the dropped skeletons and their line digests, in order.
   - The encoding is type-strict: `ascii()` of each field, after exact type checks. `None` is not `'None'`, and
     `2` is not `'2'`.
   - A reconstruction recomputes the digest. Any change to what stays in memory is then found the way a changed
     in-memory payload is found by re-hashing it: a value, a type, a link, an offset, a digest, or a list entry
     replaced by another object.
   - Before a payload is dropped, its line pointer must name exactly that record's own bytes. Either the line
     this ledger writes for the record has the recorded digest, or the line in the file parses to the same
     record. A pointer altered while the payload was still in memory is never folded into the digest.
3. **Two reconstructions, both whole.**
   - `verify_chain()` (explicit: tribunal, appraisal, anchor, artifacts, disclosure) re-hashes resident records
     and checks dropped history against the running digest. It then re-derives every dropped record from the
     file alone: the bytes must have the bound digest, the parsed record must equal the skeleton, and it must
     hash to its own hash and link to its predecessor. It also refuses a ledger path that now names another file
     than the one opened.
   - The commit path (every Commit Witness) and the scheduled hot-path reconstruction (every 300 s) re-hash
     resident records and check dropped history against the running digest, without reading the file. They also
     judge the pointer of any record kept in memory past the window.
   - Once any read has found changed bytes, or a replaced file, every reconstruction (the commit path's
     included) reads the whole file. Nothing is appended again until the file is intact.
   - Failures are counted, not flagged: a reconstruction clears only failures found before it started, so a
     concurrent reader's refusal is never erased.
4. **A payload altered in memory is never dropped.** Eviction drops only a payload that still hashes to its
   record. An altered one stays in memory, with everything after it, so the next reconstruction reports
   the alteration. The file's copy never silently replaces it.
5. **Opening streams the file.** It verifies each line as it is read and keeps only the window of
   payloads, so reopening a long history does not hold all of it at once. Errors are reported in the order
   a whole-file read reported them: a torn tail, then a blank or malformed line, then the first
   verification failure.
6. **The event spine keeps positions, not payloads.**
   - Its views hold each event's ledger position, type and identity, and read payloads through the ledger
     on demand.
   - `_bindings` keeps 32-byte digests instead of 71-character strings.
   - The unused `_seen_ids` set is now a view of `_bindings`' keys.

## What is preserved, what is stronger, what is given up

| Property | Before | Now |
|---|---|---|
| File bytes and hashes | — | identical (tested line for line) |
| Every read API (records, find, by_type, select, spine replay/since/positions/latest/record_hash) | — | equal to a ledger holding everything in memory (tested on the same file) |
| A reader changes what it was given | no effect on retained evidence | no effect (a new object per read of dropped history) |
| In-memory alteration of retained history | found by explicit verification, the next Commit Witness, and the hot path within 300 s | the same, for resident payloads and for everything that stays of dropped history |
| Bytes changed in the file after open | invisible until reopen | refused at the first read of a changed line and by any explicit `verify_chain()`; then every append refuses, the witness included |
| Ledger file replaced after open (rename) | invisible until reopen | refused by any explicit `verify_chain()` once dropped history exists; then every append refuses |
| Tampered file at open | refused | refused |
| Commit Witness cost | re-hash every retained record (about 9 µs each) | re-hash the 1,024 resident records, plus about 1 µs per dropped record for the running digest |

Given up:
- A dropped payload costs a file read and a parse each time it is read. Hot paths that read all of
  history every tick (`greg/cognition/settlement.py` replays) now read old events from the file. The
  measured run is faster overall because the commit path got cheaper, but such a replay is still linear
  in history, as before.
- The commit path's check of dropped history relies on the running digest this process bound. A
  consistent in-process rewrite of skeletons and digest evades it, as a consistent in-process rewrite of
  payloads and hashes evaded the old re-hash. Explicit `verify_chain()`, any reopening and the
  separate-process appraiser re-derive every hash from the file.
- **Writer and reader input types are stricter.** A record type or correction ancestry that is not text is
  now refused before anything is written. A `str` subclass is stored as plain text, which is what reading
  the line back always yielded.

## Result

Same scenario, 1,800 ticks (`bounded-rss.json`, `bounded-heap-attribution.json`):

- **Resident memory:** 1,458 B per retained record from 7,820 to 23,420 records, against 2,639 (−45%).
- **Python heap:** 833 B per record, against about 2,270 (−63%).
- **Run time:** 223 s against 334 s. The two runs were concurrent on the same 4-core container, so treat
  the time as indicative.
- **Reclaimable memory:** `malloc_trim` before each reading (the `*-trim.json` files) changes neither slope
  materially. The gap between resident memory and heap is not freeable at those points.

For a body observing once a minute, about 27 MB a day instead of about 49 MB: 1 GB in about five weeks
instead of under three.

## Independent adversarial review (2026-10-28)

A separate agent, given the diff and the guarantees but not this record, attacked commit `45d65a30`. It
reproduced five breaks; each is fixed and pinned by a test in `tests/unit/test_ledger_dropped_payloads.py`
that fails on `45d65a30`, 13 tests in all.

- **F1 (high): pointer laundering.**
  - The attack: a later record's payload holds a parseable copy of an earlier record (same hash and seq, forged
    payload). Point the still-resident record's line pointer at it and let eviction run.
  - Result before the fix: every reader saw the forgery, and explicit verification, the hot path and the Commit
    Witness all passed.
  - Fixed: the pointer is bound before dropping, and explicit verification re-derives every hash from the file.
- **F2 (medium): type changes.** A change of type alone (`None` to `'None'`, `2` to `'2'`, an offset as text)
  passed the running digest. An offset as text crashed readers with `TypeError`. Fixed by the type-strict
  encoding and exact type checks; a bad pointer is now refused, not crashed on.
- **F3 (medium): exceptions after fsync.**
  - A lone surrogate in a record type or correction made the skeleton's UTF-8 encoding raise after fsync. Every
    later append was then durable but raised, and the file could no longer be opened.
  - A `str` subclass record type raised in `sys.intern` after fsync without marking the append uncertain, so the
    next append reused the sequence number.
  - Fixed: everything that can fail runs before the write, `ascii()` encodes any text, and a failure after fsync
    marks the ledger uncertain.
- **F4 (low–medium): a race on the tamper signal.** A whole-file reconstruction that started before a tamper
  cleared a concurrent reader's tamper signal, and the next witness was appended. Fixed with failure counters.
- **F5 (low): shared payload objects.** A reader racing eviction could be handed the retained object itself.
  Fixed by reading the slot once.

Also reported and changed:
- A replaced ledger file was invisible here, as in the old code. It is now detected.
- `rec in ledger.records` read payloads before comparing headers: 244 ms against 5 ms at 10k records. Headers
  are now compared first.

Kept as reported:
- Whole-history spine replays cost about 2.3x the old code per event read from the file: 358 ms against 153 ms
  for 20k events.
- The first `select` on a new field reads that type's dropped records once.
- After `records =` assignment, eviction stops for that ledger object.
- The reviewer's differential test matched the old ledger and spine exactly: 36 random operation sequences at
  windows 1, 2 and 3, with byte-identical files.

## Next measured limit (not changed here; each needs a decision)

What still grows, per retained record, at 11,720 records (`bounded-heap-attribution.json`):

1. **The ledger's per-record skeleton, about 500 B.** A slotted object, the hash string, timestamp, offset,
   line digest and index entries.
   - Packing dropped skeletons into arrays would cut most of it.
   - It changes `_records` from a list of objects to a sequence of views, so it touches every consumer of the
     private list. Not attempted.
2. **The Consequence Gate keeps every grant forever, about 120 B.** `_grants`, `_meta` and `_reservations`
   each gain one entry per Gate-mediated act (one per observation), used or not.
   - `policy/consequence_gate.py` is a hash-bound continuity artifact (SR-002), so changing it is the
     founder's decision.
3. **The passport registry keeps every process passport, about 40 B.** `identity/machine_passport.py`
   `PassportRegistry._passports` gains a passport per observation. Expiring them is an identity decision.
4. **Option 2 of the earlier finding** (checkpoint and archive segments) is still the only route to memory
   that does not grow with history at all. It needs signed checkpoints of projection state, as that finding
   says.

## Negative evidence kept

- **The first version slowed the body down 2×.** It read old payloads back with the strict per-object
  parser and re-hashed them at every Commit Witness: 690 s against 352 s for the same 1,800 ticks.
  - The cProfile run showed `verify_chain` at every Gate commit, re-reading every dropped line from disk.
  - The two-level reconstruction and the running digest replaced that.
- **The first version also failed open.** After a read had found changed bytes in the file, a Commit
  Witness could still be appended, because the commit path did not read the file.
  - `test_a_dropped_line_changed_on_disk_is_refused_when_read_and_stops_further_appends` caught it.
  - Every reconstruction now reads the file once any read has found a change.

## Evidence

- `tests/unit/test_ledger_dropped_payloads.py`: byte-identical file; reads equal to a ledger holding
  everything; the attacks below; streaming open and its error order; copies, equality and pickling.
  The attacks:
  - on-disk change refused at read and then at every append;
  - six in-memory skeleton fields each found at the Commit Witness;
  - a dropped record's link;
  - a plain object put in a dropped position;
  - a payload altered before eviction kept for detection;
  - a payload put back after eviction.
- The existing ledger, spine, Gate, mission-book and disclosure suites pass unchanged (136 tests). Their
  ledgers are smaller than the window, so they also pin that nothing changes there.
- The full unit suite and an independent adversarial review: see the PR.

## Rollback

Revert the commit. History files are byte-identical either way, so nothing needs migrating.
