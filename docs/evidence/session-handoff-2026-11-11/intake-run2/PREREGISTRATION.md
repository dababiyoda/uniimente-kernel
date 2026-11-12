# Second case: transfer of the intake capability (pre-registered 2026-11-12 ~15:22 UTC, before the run)

Capability: brief.intake at b032f38a, unchanged. Body, key and driver as in the first run (throwaway body, test key).
Case: four heads in another part of the machine (cognition, credit, CI gates), of a shape the first case did not
contain: a test that pins another unit's old defect.

Units, in this order: 304 `1c4a758c`, 303-old `9097b276`, 303 `0a9a246f`, runner `18e228a9`.

Ground truth, found by hand before this run (merged tree candidate + 9097b276 + e97d1bd0, 11:39 UTC):
`tests/unit/test_greg_evidence_corrections.py::test_a_reading_the_canonical_reader_calls_unanswered_is_neither_blamed_nor_credited`
passes on 9097b276 and fails once #304 is merged (it asserted the old reader's gap). 0a9a246f removes that line.

Predictions (success conditions):
P1. behavioural conflict on 303-old for that test, cause 304.
P2. no behavioural conflict for 303 (0a9a246f).
P3. 303-old and 303: 303 contains 303-old (ancestry).
P4. no false hold from the envelope (b032f38a's rule).
Failure of any is recorded as such; no threshold is changed after the run.
Intervention counted: every human or session step other than writing the request and the founder approval.

## Result (read 15:43 UTC; mission achieved 15:42; capability b032f38a unchanged)

- P1 FAILED: no behavioural conflict reported. 303-old "ready to take"; its test file "passed" on own head and merged.
  Cause, by reading the run: every unit is tested on one merged tree of all four heads. 303 (0a9a246f) contains
  303-old and replaced its test file, so 303-old's version of the file never met #304's code. The selection
  contained the old head and its descendant; the mechanism measures each unit's files on the merge of all units.
- P2 held (no conflict for 303). P3 held (303 "take after 303-old"; 303-old "arrives with 303-rejected-credit").
- P4 held: no false hold (every file passed on both trees).
- Intervention: none beyond writing the request and the (test) founder approval. Wall time 19 min 51 s.

## Follow-up registered AFTER seeing the result (a deviation, labelled as such)

Units: 304 `1c4a758c`, 303-old `9097b276` only. Prediction F1: a behavioural conflict on 303-old for
`test_a_reading_the_canonical_reader_calls_unanswered_is_neither_blamed_nor_credited`, cause 304.

## Follow-up result (read 16:06 UTC; mission achieved 16:00:53; capability b032f38a unchanged)

F1 HELD: 303-old "hold: behavioural conflict: its test tests/unit/test_greg_evidence_corrections.py::
test_a_reading_the_canonical_reader_calls_unanswered_is_neither_blamed_nor_credited passes on its own head and fails
on the merged tree (cause: 304-compile-unread)"; 304 "hold: … merging it breaks 303-old's test …". No other file
changed result. Intervention: none beyond the request and the (test) founder approval. Wall time 18 min 44 s.

## What transferred and what did not

- Transferred without change: composition, ancestry, the envelope attribution rule, behavioural-conflict detection
  with cause attribution, on a different part of the machine (cognition and credit, not authority and dispatch) and
  a different conflict shape (a test pinning another unit's old defect).
- Did not transfer: a selection holding a head and its own descendant hides the old head's own test from the merge
  (run 2). Sent to the intake fix round as F18.
