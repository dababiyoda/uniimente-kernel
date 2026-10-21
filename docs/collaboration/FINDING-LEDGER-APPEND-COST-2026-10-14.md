# Ledger verification cost: finding and change (2026-10-14, second layer 2026-10-21)

Status: **changed on the draft branch (`claude/uniimente-greg-reconciliation-39syff`), not merged.**
It touches the Kernel evidence plane (`provenance/ledger.py`, `events/spine.py`), so it is yours to
accept, change or revert. It creates no authority. One further step needs your decision because it
changes a continuity artifact: see [Founder decision](#founder-decision-the-gates-claim-scan).

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
  - What still grew was `MissionBook.rebuild`, which copied and folded every GREG event once per tick
    (5,775 events at 37,446 records). The second layer below removes it.
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

## Second layer (2026-10-21): the mission book and per-observation lookups

**Measured first.** Same body (one holding mission, 60 s cadence, 13 records per observation), median of
600 active ticks, container CPU, nothing else running:

| retained records | `291e037` | `bd0c17d` mission book | now: + ledger index | with the Gate change below (not applied) |
|---:|---:|---:|---:|---:|
| 7,817 | 25.2 ms | 13.3 ms | 10.1 ms | 8.0 ms |
| 15,630 | 46.6 ms | 25.2 ms | 11.2 ms | 8.1 ms |
| 23,443 | 90.2 ms | 38.6 ms | 14.6 ms | 7.9 ms |
| 31,256 | 136.8 ms | 55.9 ms | 18.0 ms | 8.2 ms |

Growth per thousand retained records: 4.8 ms, then 1.8 ms, now 0.34 ms; flat with the Gate change.

**What changed.**

1. **`MissionBook` folds only new events** (`bd0c17d`). `EventSpine.since(prefix, cursor)` returns the
   events retained after a cursor; a cursor is honored only within one history, so a replaced history
   is folded again from the beginning. The book keeps its own fold and hands out copies:
   - missions are copied afresh on every rebuild, so what the engine changes on them never reaches
     the fold;
   - a decision record is copied once, when folded, because copying every decision ever made on every
     rebuild would grow with history again. The fold reads only its own copy, so a caller that changes
     a handed-out record cannot change mission state. **Given up:** such a change stays visible in that
     handed-out record until the body restarts. Nothing in the code base changes one; the old book
     dropped such a change at the next rebuild;
   - a fold that raises part-way is redone from the beginning on the next call;
   - a journal that offers only `replay()` (draft #168's gravity stand-in) is folded whole every time,
     as before. The first version required `since()` and broke three #168 tests; the comparison
     against #168 found it.
2. **The ledger answers lookups from indexes** (`provenance/ledger.py`). `find(hash)`, `by_type(type)`
   and a new `select(type, field=value, ...)` use indexes of positions kept up to date the way the
   spine keeps its views: only records added since the last lookup are indexed, and a different record
   where the last indexed one was (assigned or reloaded history) rebuilds them. Every answer is
   re-checked against the record and handed out as a copy. A record altered in place in the private
   list (which verification detects) is never returned for a value it no longer holds.
3. **`AuthorityOffice._prior`** finds a proposal's dispatch claim and receipt with `select` instead of
   copying every claim and receipt (`greg/authority.py`).
4. **The engine numbers a sensor read** by counting only observations retained since its last count
   (`MissionEngine._observations_retained`); a test checks every count against a replay of all of them.

**Evidence.**

- `tests/unit/test_greg_mission_book_incremental.py` (17): eight real mission scenarios re-run with
  every rebuild compared to a fold from the first event; caller changes; replaced history; an
  interrupted fold; each new event folded exactly once; the cursor contract; a replay-only journal;
  observation numbering across a restart, two checks and a replaced history.
- `tests/unit/test_ledger_lookup_index.py` (9): randomized queries against a scan while history grows,
  after assignment and after reload; a lookup copies only what it returns; in-place alteration;
  unhashable values; the first of a repeated hash; the Gate still refuses a second dispatch of a
  claimed proposal or grant.
- **Mutation:** 21 mutants (10 of the book and cursor, 11 of the index, prior lookup and counting);
  20 caught. The survivor builds a field index from every record instead of one type's; answers are
  identical (the re-check filters by type), so it is slower, not wrong.
- **Full suite:** 1,383 passed, 6 skipped.
- **Draft #168** merged with the book change: the same 24 failures as #168 alone (its optional solver
  dependencies are missing here), no new ones; `git merge-tree` is clean against #168 and `main`.
- **Negative evidence:** the first index version also changed the Gate. Thirteen repair-harness tests
  failed, because `policy/consequence_gate.py` is one of the twelve continuity artifacts whose bytes
  define identity and authority (`evolution/repair/spec.py`, `evolution/repair/subjects.py`). That
  change was reverted; it is the decision below.

## Founder decision: the Gate's claim scan

What still grows is the Consequence Gate's own check that a proposal or grant was not dispatched
before. It reads every `grant_dispatch` record (one per Gate-mediated act, so one per observation):
about 2,400 copies per observation at 31,256 records, 0.34 ms per thousand records. A holding mission
observed every minute writes about 18,700 records a day, so after 50 days this check alone would cost
roughly half a second per observation.

The change that removes it is three lines in `policy/consequence_gate.py`, step 11:

```python
            if (self.ledger.select('grant_dispatch', proposal_id=proposal.proposal_id)
                    or self.ledger.select('grant_dispatch', grant_id=grant['grant_id'])):
```

It answers the same question from the index (tested: a claim found by proposal and by grant each still
stops a second dispatch). It is not applied because the Gate's bytes are a continuity artifact: changing
them changes the identity and authority fingerprint the repair harness pins (subject SR002), which needs
your decision and a re-bound subject. Options: approve the change and re-bind SR002 at the new hash;
keep the Gate and accept the growth; or have the Gate's claim check reviewed separately first.

## Rollback

Revert the commit. History files are byte-identical either way: the same JSON lines and the same hashes.
The change is to memory and verification frequency only. The second layer reverts the same way
(`bd0c17d` and the index commit); it changes no file format, no event and no record.
