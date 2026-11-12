# Composition rehearsal on `8d20532464`

Each head's own tests, run on its own tree and on the merged tree. Read-only; nothing was merged.

| Head | Commit | Test files | Alone | Merged |
|---|---|---:|---|---|
| 214 | `f8b603c774` | 3 | 1 failed, 38 passed, 2 skipped (1 failing) | 4 failed, 35 passed, 2 skipped (4 failing) |
| replay | `e917a0dbfe` | 3 | 25 passed | 25 passed |

Merge order: 214, replay.

## Tests that pass alone and fail merged

- `tests/unit/test_greg_self_repair_incident.py::test_a_failure_one_repair_did_not_cure_asks_the_founder_and_never_crashes` (from 214): caused by **(the base)**; fails as soon as this head is merged onto the base, with no other head: the line has moved since it branched.
- `tests/unit/test_greg_self_repair_incident.py::test_a_new_fault_right_after_a_repair_is_not_a_second_strike` (from 214): caused by **(the base)**; fails as soon as this head is merged onto the base, with no other head: the line has moved since it branched.
- `tests/unit/test_greg_self_repair_incident.py::test_beside_a_measured_failure_the_same_incident_is_still_repaired_once` (from 214): caused by **(the base)**; fails as soon as this head is merged onto the base, with no other head: the line has moved since it branched.

## Failing before the merge (not a composition problem)

- `tests/unit/test_mind_status.py::test_the_exercised_scan_misses_no_retained_settlement` (from 214)

## Result

Conflicts were found; see above.

Limits:
- only the named tests were run: a clean result does not prove the heads are compatible
- a unit left out for a textual conflict was not tested in the merge
- where both sides' lines were kept in a named file, that resolution was not reviewed by a person
- read-only: nothing was merged, pushed or edited; no result here approves a merge
