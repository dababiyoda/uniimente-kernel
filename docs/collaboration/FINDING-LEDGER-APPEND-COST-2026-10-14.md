# Ledger verification cost: finding and change (2026-10-14)

Status: **changed on the draft branch (`claude/uniimente-greg-reconciliation-39syff`), not merged.**
It touches the Kernel evidence plane (`provenance/ledger.py`, `events/spine.py`), so it is yours to
accept, change or revert. It creates no authority.

## Finding

The first measurement looked only at appends. The full cost was larger.

- **Appends.** `EvidenceLedger._append` re-hashed every retained record before writing (about 9 µs per
  record).
- **Spine reads.** Every spine read did the same: `EventSpine._spine_payloads` called `verify_chain()`.
- **Emits.** Every emit re-verified the chain three times and rebuilt the spine's views twice.
- **Ticks.** One idle body tick read the spine **46 times** (cProfile of `Body.tick`).

So a tick cost about 46 × 9 µs per retained record. A holding mission observed once a minute writes 13
records per observation (Gate witness, receipt, outcome and events).

| retained records | one full verification | old: one emit | old: time to write that many events |
|---:|---:|---:|---:|
| 1,000 | 7–9 ms | 59 ms | 40 s |
| 3,000 | 28 ms | 222 ms | 304 s |
| 5,000 | 52 ms | 395 ms | 619 s |

A real body (one holding mission, 60 s cadence) on the old code did not finish 600 ticks (about 7,800
records) in 20 minutes. At that size each tick cost about 3 s. On a slower Chromebook CPU a body running
daily missions for weeks would spend most of its time re-verifying history; past roughly 10⁵ records a
tick would outlast the 30 s tick interval.

## Change

1. **Retained records never leave the ledger.**
   - Every read hands out the caller's own copy: `records` (indexing, slicing, iteration), `by_type`,
     `find`, `append`'s return value, and the spine's `replay`, `latest` and outbox events.
   - The copies are plain dicts and lists, exactly as before. Callers' exact type checks
     (`type(x) is dict`) keep working.
   - Changing a copy changes nothing retained. `records` is a read-only view; assigning history (a
     review snapshot) copies it in.
   - An outbox mediator gets its own copy, so what is written after it runs is the staged fact.
2. **Hot paths verify only what is new.** `append` and spine reads call `verify_incremental()`. It checks
   records added since the last verification and confirms the verified prefix ends with the same object.
   A record built by `append` from the verified head is verified by construction.
3. **The whole chain is still reconstructed:**
   - on open;
   - on every explicit `verify_chain()`, which callers such as the tribunal, appraisal, anchor and
     artifacts use, and which is never shortened;
   - when history is assigned;
   - whenever the verified prefix is not the one last seen;
   - at least every `FULL_VERIFY_SECONDS` (300 s) on the hot path.
   The separate-process appraiser still verifies the full chain from the file before every appraisal.
4. **The spine folds only new records** into its views: bindings, outbox, uncertain deliveries, a
   per-type index, an event-id index and per-prefix positions.
   - Each record is checked before any view changes, so a refused record is refused again on every
     later call. Replaced history is rebuilt from the beginning.
   - `Journal` finds retained facts and numbers events through those indexes instead of scanning
     history.
   - `greg/improvement.py`'s `_order` used to replay all history nine times per tick. It now reads
     `journal.positions()`, which gives the same numbers; the numbers are persisted, and a test pins
     them to the old definition.

**A first version froze payloads instead** (immutable dict and list subclasses). It passed this
branch's 1,357 tests, but on draft #168 four cognition tests failed silently: #168 validates proof
fields with exact type checks, so a frozen subclass was rejected and nothing settled. Copies keep plain
types and close the same hole, so the frozen version was dropped. The lesson is now a test: readers get
plain types.

## What is preserved, and what is given up

| Property | Before | Now |
|---|---|---|
| History on disk tampered | refused on open | refused on open (unchanged) |
| A reader changes a record or event it was given | changed retained history in memory; every later operation then failed with a hash mismatch | changes only the reader's copy; history stays intact |
| An outbox mediator changes the event it was shown | corrupted the staged record (hash mismatch) | changes only its copy; the staged fact is written |
| The ledger's private list altered (`ledger._records`) | detected at the next read or append | detected at once by any explicit `verify_chain()`; on the hot path at its next full reconstruction (≤ 300 s), or immediately if the record is new or the verified tail changed |
| Conflicting event identity in history | refused | refused, and keeps being refused |

The one thing given up: code inside the process that alters the ledger's private list can be served by
the hot path for up to 300 s. Code that can do that can also replace `verify_chain` itself, so the old
check did not stop it either. A reader's bug can no longer corrupt history at all.

## Evidence

- **Op cost** (one emit + one prefix replay; container CPU, Python 3.11):

  | retained records | emit | replay of ¼ of events | full verification | time to write them |
  |---:|---:|---:|---:|---:|
  | 1,000 | 0.49 ms | 1.7 ms | 12 ms | 0.7 s |
  | 5,000 | 0.42 ms | 8.9 ms | 54 ms | 2.3 s |
  | 20,000 | 0.59 ms | 39 ms | 222 ms | 8.9 s |
  | 50,000 | 0.63 ms | 140 ms | 619 ms | 18.4 s |

  A replay now costs about 11 µs per event it returns (most of it copying the payload), not a hash of
  every record retained.
- **Real body**, same mission as above: 32 ms per tick at 6,517 records, 65 ms at 13,017, 103 ms at
  19,517 and 49 ms at 37,446, with noisy peaks near 200 ms.
  - The tick no longer re-hashes anything: two hashes per tick, both for new records.
  - What still grows is `MissionBook.rebuild`, which copies and folds every GREG event once per tick
    (5,775 events at 37,446 records).
  - That is the next layer: keep one book and fold only new events. It is not built here because draft
    #168 changes `greg/missions.py`.
  - Old code at 7,800 records: about 3 s per tick.
- **Full suite:** 9 min 17 s before; 4 min 11 s to 4 min 38 s after, with the same tests plus the new ones.
- **Tests:** `tests/unit/test_ledger_incremental_verification.py` (20).
  - One loads a ledger written before the change and re-serializes it byte for byte.
  - One checks that readers get plain types.
  - **Five existing tamper tests** (`test_provenance` ×2, `test_shared_recovery` ×2, the `altered` case in
    `test_shared_compatibility_continuation`) and the runtime self-check in `closure/kernel_registry.py` now
    do two things: assert that changing what a reader gets leaves retained evidence unchanged, then tamper
    with the ledger's private list and assert that reconstruction still detects it.
  - The N7 test's own workaround (it re-verified only the tail) is removed; the ledger does that now.
- **Draft #168 with this change applied**, in this container, which lacks #168's optional solver
  dependencies: 268 failures with or without this change, the same set; 2,135 passed with it. The frozen first version had added four, as
  described above.
- **Mutation:** 33 mutants of the ledger, spine, journal and improvement changes; 31 caught.
  - The first round's survivors each got a test: a record that bypassed `append`, history reassigned
    mid-chain, a non-object payload, conflicting identities in retained history, history replaced at the
    same length, `Journal.event_hash`, and the improvement numbers.
  - The two left are redundant guards kept on purpose. Assigned history is already re-verified, because
    copies are new objects and fail the tail identity check. Pending outbox events are already isolated,
    because the mediator gets its own copy.

## Rollback

Revert the commit. History files are byte-identical either way: the same JSON lines and the same hashes.
The change is to memory and verification frequency only.
