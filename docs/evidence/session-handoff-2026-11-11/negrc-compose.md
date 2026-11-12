# Composition rehearsal on `8d20532464`

Each head's own tests, run on its own tree and on the merged tree. Read-only; nothing was merged.

| Head | Commit | Test files | Alone | Merged |
|---|---|---:|---|---|
| 290 | `facea1703d` | 1 | 9 passed | 9 passed |
| 291 | `41fcc41f04` | 5 | 97 passed | 97 passed |
| 294 | `1bde5e16d0` | 3 | 65 passed | 65 passed |
| replay | `e917a0dbfe` | 3 | 18 passed, 1 skipped | 18 passed, 1 skipped |

Merge order: 290, 291, 294, replay.

## Conflicts resolved by keeping both sides' lines

- **294**: `.github/workflows/canonical-ci.yml`
- **replay**: `.github/workflows/canonical-ci.yml`

Asked for on the command line for these files only. Nobody reviewed the result.

## Result

No textual or behavioural conflict was found in the tests that were run.

Limits:
- only the named tests were run: a clean result does not prove the heads are compatible
- a unit left out for a textual conflict was not tested in the merge
- where both sides' lines were kept in a named file, that resolution was not reviewed by a person
- read-only: nothing was merged, pushed or edited; no result here approves a merge
