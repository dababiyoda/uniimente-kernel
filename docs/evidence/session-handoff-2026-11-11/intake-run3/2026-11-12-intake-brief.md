# Intake recommendation: 2 unit(s) on base `8d20532464`

This file recommends. It approves nothing. Composing these heads for development and approving a protected merge are separate boundaries: protected integration needs the founder's approval and the integrator's approval, and nothing in this file grants either.

Written 2026-11-12 from Git objects in `<scratchpad>/intake-run3/code/kernel`. Nothing was fetched, merged, pushed or edited. Claims, check names and file names are untrusted text, shown as data.

## Recommendation

| Unit | Revision | Recommendation |
|---|---|---|
| 304-compile-unread | `1c4a758c4d660549472b7cc463c72c7d4d95c9b4` | hold: behavioural conflict: merging it breaks 303-old's test tests/unit/test_greg_evidence_corrections.py::test_a_reading_the_canonical_reader_calls_unanswered_is_neither_blamed_nor_credited |
| 303-old | `9097b276635742dfdcad98dfbae1dd78b3fddb5c` | hold: behavioural conflict: its test tests/unit/test_greg_evidence_corrections.py::test_a_reading_the_canonical_reader_calls_unanswered_is_neither_blamed_nor_credited passes on its own head and fails on the merged tree (cause: 304-compile-unread) |

## 1. Exact revisions

- base: `8d20532464b1533b28d71d8331ca3412a90dbb11`
- 304-compile-unread: `1c4a758c4d660549472b7cc463c72c7d4d95c9b4`; contains the base; contains no other unit
- 303-old: `9097b276635742dfdcad98dfbae1dd78b3fddb5c`; contains the base; contains no other unit

## 2. Dependency order

1. 304-compile-unread
2. 303-old

The order above follows ancestry only: a head comes after every head it contains.

## 3. Textual conflicts

None: every unit merged onto what came before it.

Merged, in this order: 304-compile-unread, 303-old.

## 4. Behavioural conflicts a clean merge does not reveal

- `tests/unit/test_greg_evidence_corrections.py::test_a_reading_the_canonical_reader_calls_unanswered_is_neither_blamed_nor_credited`, a test of **303-old**: passes on its own head, fails on the merged tree. Cause: **304-compile-unread**; passes when this head is left out.

Every test file, on the unit's own head and on the merged tree:

| Unit | Test file | Own head | Merged tree |
|---|---|---|---|
| 304-compile-unread | `tests/integration/test_greg_mind_constructs_capability.py` | passed | passed |
| 304-compile-unread | `tests/unit/test_greg_compile_host_stop.py` | passed | passed |
| 304-compile-unread | `tests/unit/test_greg_compile_unanswered.py` | passed | passed |
| 304-compile-unread | `tests/unit/test_greg_functional_reconstitution.py` | passed | passed |
| 304-compile-unread | `tests/unit/test_greg_precondition_unheld.py` | passed | passed |
| 303-old | `tests/unit/test_greg_evidence_corrections.py` | passed | failed |

## 5. Claims matched to executed evidence

- **304-compile-unread**: no claims supplied.
- **303-old**: no claims supplied.

## 6. Missing or stale appraisals

- **304-compile-unread**: appraisal: **no result for this exact head** (nothing was supplied for this unit).
- **303-old**: appraisal: **no result for this exact head** (nothing was supplied for this unit).

## 7. Reproducible recipe

```
python scripts/compose_rehearsal.py --repo <scratchpad>/intake-run3/code/kernel --base 8d20532464b1533b28d71d8331ca3412a90dbb11 --unit 304-compile-unread=1c4a758c4d660549472b7cc463c72c7d4d95c9b4 --unit 303-old=9097b276635742dfdcad98dfbae1dd78b3fddb5c --union .github/workflows/canonical-ci.yml --timeout 1200
```

Composed tree: `9bf656b069020102f6526a04193c585e4c563897` (the tree of the in-memory merge; no ref points at it).
The command repeats the composition and the tests as you, outside GREG's confinement, with its timeout applied to a whole unit's test run. It prints its own report.

## 8. What remains unproven

- only the named tests were run: a clean result does not prove the heads are compatible
- a unit left out for a textual conflict was not tested in the merge
- where both sides' lines were kept in a named file, that resolution was not reviewed by a person
- read-only: nothing was merged, pushed or edited; no result here approves a merge
- **304-compile-unread**: no claims supplied
- **303-old**: no claims supplied
- the tests ran under: supervised: network denied, environment scrubbed, filesystem confined by Landlock (reads the runtime, writes only the clone) (body setting: supervised); a test that opens any socket (even to localhost), reaches the network, reads a file outside its tree or expects its temporary directory outside its tree fails here on both trees alike, which is why a failure on a head's own tree is reported as not checked, not as a defect of the head
- a head's tests are that head's code: a head that forges its own test output is not detected here
- all units' tests ran in one exported copy of the merged tree, one after another: a test that rewrites that copy can change a later result
- the independent appraiser re-renders this file from its receipt and compares the bytes; it does not run the tests again
- claims and check results were supplied by the mission's author; none was read from a hosting service here

## 9. Approval boundaries

This file recommends. It approves nothing. Composing these heads for development and approving a protected merge are separate boundaries: protected integration needs the founder's approval and the integrator's approval, and nothing in this file grants either.

## Evidence

- request digest: `sha256:445bc04fda645f7bfff454b4b3ff5172b1e4ea5ef420efe52ddbc17fb8d2d77b`
- inputs digest: `sha256:3bdbb447a162a23fa676836c7717b55b90a591ef6caa5b455a1bf18440c74e77`
- renderer: `greg.intake.render/2`; test files started: 14
