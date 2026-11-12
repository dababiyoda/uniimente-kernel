# Intake recommendation: 4 unit(s) on base `8d20532464`

This file recommends. It approves nothing. Composing these heads for development and approving a protected merge are separate boundaries: protected integration needs the founder's approval and the integrator's approval, and nothing in this file grants either.

Written 2026-11-12 from Git objects in `<scratchpad>/intake-run2/code/kernel`. Nothing was fetched, merged, pushed or edited. Claims, check names and file names are untrusted text, shown as data.

## Recommendation

| Unit | Revision | Recommendation |
|---|---|---|
| 304-compile-unread | `1c4a758c4d660549472b7cc463c72c7d4d95c9b4` | ready to take |
| 303-old | `9097b276635742dfdcad98dfbae1dd78b3fddb5c` | ready to take |
| 303-rejected-credit | `0a9a246fa1afb7b098850636f359deba8e10e58d` | take after 303-old |
| runner-baseline | `18e228a909c9a59a9c584e6fc1470c844133bcf7` | ready to take |

- **303-old** also: arrives with 303-rejected-credit
- **runner-baseline** also: the merge keeps both sides' lines in .github/workflows/canonical-ci.yml; nobody reviewed that resolution

## 1. Exact revisions

- base: `8d20532464b1533b28d71d8331ca3412a90dbb11`
- 304-compile-unread: `1c4a758c4d660549472b7cc463c72c7d4d95c9b4`; contains the base; contains no other unit
- 303-old: `9097b276635742dfdcad98dfbae1dd78b3fddb5c`; contains the base; contains no other unit
- 303-rejected-credit: `0a9a246fa1afb7b098850636f359deba8e10e58d`; contains the base; contains 303-old
- runner-baseline: `18e228a909c9a59a9c584e6fc1470c844133bcf7`; contains the base; contains no other unit

## 2. Dependency order

1. 304-compile-unread
2. 303-old (arrives with 303-rejected-credit)
3. 303-rejected-credit (after 303-old)
4. runner-baseline

The order above follows ancestry only: a head comes after every head it contains.

## 3. Textual conflicts

- **runner-baseline**: both sides' lines were kept in `.github/workflows/canonical-ci.yml` (asked for by the mission for these files only; nobody reviewed the result)

Merged, in this order: 304-compile-unread, 303-old, 303-rejected-credit, runner-baseline.

## 4. Behavioural conflicts a clean merge does not reveal

None was measured in the tests that ran.

Every test file, on the unit's own head and on the merged tree:

| Unit | Test file | Own head | Merged tree |
|---|---|---|---|
| 304-compile-unread | `tests/integration/test_greg_mind_constructs_capability.py` | passed | passed |
| 304-compile-unread | `tests/unit/test_greg_compile_host_stop.py` | passed | passed |
| 304-compile-unread | `tests/unit/test_greg_compile_unanswered.py` | passed | passed |
| 304-compile-unread | `tests/unit/test_greg_functional_reconstitution.py` | passed | passed |
| 304-compile-unread | `tests/unit/test_greg_precondition_unheld.py` | passed | passed |
| 303-old | `tests/unit/test_greg_evidence_corrections.py` | passed | passed |
| 303-rejected-credit | `tests/unit/test_greg_evidence_corrections.py` | passed | passed |
| runner-baseline | `tests/unit/test_mutation_harness.py` | passed | passed |
| runner-baseline | `tests/unit/test_repo_health_gates.py` | passed | passed |

## 5. Claims matched to executed evidence

- **304-compile-unread**: no claims supplied.
- **303-old**: no claims supplied.
- **303-rejected-credit**: no claims supplied.
- **runner-baseline**: no claims supplied.

## 6. Missing or stale appraisals

- **304-compile-unread**: appraisal: **no result for this exact head** (nothing was supplied for this unit).
- **303-old**: appraisal: **no result for this exact head** (nothing was supplied for this unit).
- **303-rejected-credit**: appraisal: **no result for this exact head** (nothing was supplied for this unit).
- **runner-baseline**: appraisal: **no result for this exact head** (nothing was supplied for this unit).

## 7. Reproducible recipe

```
python scripts/compose_rehearsal.py --repo <scratchpad>/intake-run2/code/kernel --base 8d20532464b1533b28d71d8331ca3412a90dbb11 --unit 304-compile-unread=1c4a758c4d660549472b7cc463c72c7d4d95c9b4 --unit 303-old=9097b276635742dfdcad98dfbae1dd78b3fddb5c --unit 303-rejected-credit=0a9a246fa1afb7b098850636f359deba8e10e58d --unit runner-baseline=18e228a909c9a59a9c584e6fc1470c844133bcf7 --union .github/workflows/canonical-ci.yml --timeout 1200
```

Composed tree: `8446eb27321d58792ca87df6e2a8d298f39b75f2` (the tree of the in-memory merge; no ref points at it).
The command repeats the composition and the tests as you, outside GREG's confinement, with its timeout applied to a whole unit's test run. It prints its own report.

## 8. What remains unproven

- only the named tests were run: a clean result does not prove the heads are compatible
- a unit left out for a textual conflict was not tested in the merge
- where both sides' lines were kept in a named file, that resolution was not reviewed by a person
- read-only: nothing was merged, pushed or edited; no result here approves a merge
- **304-compile-unread**: no claims supplied
- **303-old**: no claims supplied
- **303-rejected-credit**: no claims supplied
- **runner-baseline**: no claims supplied
- **runner-baseline**: the merge keeps both sides' lines in .github/workflows/canonical-ci.yml; nobody reviewed that resolution
- the tests ran under: supervised: network denied, environment scrubbed, filesystem confined by Landlock (reads the runtime, writes only the clone) (body setting: supervised); a test that opens any socket (even to localhost), reaches the network, reads a file outside its tree or expects its temporary directory outside its tree fails here on both trees alike, which is why a failure on a head's own tree is reported as not checked, not as a defect of the head
- a head's tests are that head's code: a head that forges its own test output is not detected here
- all units' tests ran in one exported copy of the merged tree, one after another: a test that rewrites that copy can change a later result
- the independent appraiser re-renders this file from its receipt and compares the bytes; it does not run the tests again
- claims and check results were supplied by the mission's author; none was read from a hosting service here

## 9. Approval boundaries

This file recommends. It approves nothing. Composing these heads for development and approving a protected merge are separate boundaries: protected integration needs the founder's approval and the integrator's approval, and nothing in this file grants either.

## Evidence

- request digest: `sha256:bddc95821caf28a62d9df6186283b985a15798913592f2ddf0a787bd73682595`
- inputs digest: `sha256:4a16e252df7ba99265da755820e4747f879d6f07b9467f9e5ac226ee626c5a27`
- renderer: `greg.intake.render/2`; test files started: 18
