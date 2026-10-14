# Finding: every ledger append re-verifies the whole chain (2026-10-14)

Status: **measured finding, not changed.** It is the Kernel evidence owner's decision
(`provenance/ledger.py`). It creates no authority.

## What happens

`EvidenceLedger._append` calls `verify_chain()` before every append. That call recomputes the hash of
every retained record. One append therefore costs time proportional to the length of history, and
writing a history costs time proportional to the square of its length.

## Measured

Container CPU, one `event` record per append (same payload shape as `greg.mission.observed`), Python 3.11:

| records retained | one full verification | cumulative time to write them |
|---:|---:|---:|
| 1,000 | 8.8 ms | 4.7 s |
| 2,000 | 17.0 ms | 18.5 s |
| 4,000 | 34.2 ms | 73.2 s |
| 8,000 | 71.6 ms | 293.1 s |

That is about 9 µs per record per append.

Every Gate-receipted observation writes several records. A body running daily missions for months
reaches 10⁵ records, at which point each append takes about 0.9 s. A persistent GREG would then spend
most of its time re-verifying what it already verified.

The N7 test (`tests/unit/test_greg_venture_books.py`) runs five full business cases on one body. It
crossed this line, so its writer checks only new records against the last verified head. The
separate-process appraiser still verifies the full chain from the file for every closure, and the
test ends with one full verification.

## Why it exists, and what must survive

A full re-verification before each write detects tampering with records already held in memory, by
any code that holds the ledger object. Any replacement must keep that property, or state plainly
that it gives it up.

## Proposed (for the evidence owner)

1. Keep a verified prefix: the length and head hash at the last full verification. Before an append,
   verify the new tail against that head, and confirm the prefix is unchanged by comparing its head
   hash and identity.
2. Re-verify the whole chain on open, on a schedule (for example hourly), before every appraisal
   (which the separate-process appraiser already does), and whenever the prefix check fails.
3. Make records immutable in memory (frozen dataclasses; payloads deep-copied on read), so the
   in-memory tampering the full check guards against cannot happen through the public interface.

**Falsifier:** a test that mutates `ledger.records[i].payload` in place must still be refused before
the next append is acknowledged.

## Reproduce

```python
from compiler.ucl_compiler import compile_constitution
from provenance.ledger import EvidenceLedger
ledger = EvidenceLedger(compile_constitution(".").constitution_hash)
# append N event records, timing verify_chain() at 1k, 2k, 4k and 8k
```
