# Composition rehearsal: first runs, 2026-11-11

`scripts/compose_rehearsal.py` runs each head's own tests on its own tree and on the merged tree, and reports what
passes alone and fails merged, with its cause. This note records what it found the first day. Everything here was
run in a cloud container on #196 `8d20532464b1533b28d71d8331ca3412a90dbb11`. It is read-only evidence for the
integration owner. Nothing was merged, and no result here approves a merge.

## Why it exists

`scripts/branch_catalog.py` lists what merges cleanly and says that clean is not correct. On 2026-11-11 two pairs
that `git merge-tree` reports clean were found broken in behaviour, by hand: #273 against #291, and #278 against an
earlier head of #291. 181 pull requests were open that day.

## The case it was designed on

Heads #290 `facea170`, #291 `41fcc41f`, #273 `331de165`, #278 `a639add7`. All four merge without a textual
conflict.

- 13 tests of #273 (`tests/unit/test_greg_background_dispatch.py`) pass on #273 and fail merged. Cause named for
  each: #291. Leaving #291 out, they pass.
- Why, read in the code: #273 hands the office a wrapped adapter; #291's office runs only the adapter registered
  for the capability. #291 offers `around=` for a caller's wrapper, so #273's one call site becomes
  `adapter=adapter, around=wrap`. With that one line the merged tree passes (checked separately).
- #290's 9 and #291's 97 tests pass merged.
- 46 tests of #278 fail on #278's own tree here. They need solver packages this container lacks. The report lists
  them as failing before the merge, not as a composition problem.

## Sets it was not designed on

These are the test of the tool: sets chosen afterwards, whose results were not known.

| Set | Heads | Textual | Behavioural |
|---|---|---|---|
| This session's branches | #290, #291, #294, #293, #295, revoked-device `f35b7986`, detached-sensor appraiser `bf8e4b9f` | CI step list and ledger top only (kept both sides) | 1: a test of #295 failed once the revoked-device branch's ledger entry was beside its own |
| Genesis | #267, #276, #280, #281, #289, #292 | none | none: 83 tests pass merged |
| Engine and Hands | #214, #283, #288, #240, #233, #285, #293 | #293 against #233 in `greg/computer.py` | 2 (below) |

Each finding was then re-derived with a smaller run.

1. **#214 no longer works on the line.** Three tests of `tests/unit/test_greg_self_repair_incident.py` pass on
   #214's own tree and fail when #214 alone is merged onto `8d205324`:
   `test_a_failure_one_repair_did_not_cure_asks_the_founder_and_never_crashes`,
   `test_a_new_fault_right_after_a_repair_is_not_a_second_strike`,
   `test_beside_a_measured_failure_the_same_incident_is_still_repaired_once`. Cause named: the base. I did not
   read why.
2. **#285 breaks with #240 and not with #278.** `tests/integration/test_greg_business_path_process.py::
   test_business_path_runs_in_one_body_process_and_survives_restart` passes on #285 and fails merged with #240
   `4441bcb5`; it passes merged with #278 `a639add7`, #240's fix round. Intake order that works: #278, not #240,
   with #285.
3. **#293 overlapped #233.** Both changed `chromium()` in `greg/computer.py` for the same stale path. #293 now
   leaves that file to #233 (`da2aff57`).
4. **#295's test was too wide.** It read every ledger entry above a later heading as its own. Fixed in #295
   (`d86e83c2`).

What the baseline would have shown: `git merge-tree` reports item 3 and nothing else. Items 1, 2 and 4 are
behaviour.

## What it does not show

- It runs only the test files each head changed. A clean set is not proven compatible. A head that changed no test
  is listed as not checked.
- A test that fails only with three or more heads together is reported without a single cause.
- Where both sides' lines were kept in a named file (`--union`), nobody reviewed that resolution.
- It ran here without networkx, scipy, z3, ortools and bubblewrap, so tests that need them skipped or failed on
  their own trees. On a CI runner the same command checks more.
- Cost here, with four other workers on four CPUs: the seven-head set took about 25 minutes; small pairs a few
  minutes.

## One recurring conflict worth removing

Every pull request that adds a mutation gate adds a step at the same place in
`.github/workflows/canonical-ci.yml`, so any two of them conflict textually there. The rehearsal keeps both lines
when asked. A proposal for the integration owner, not made here: one step that runs every
`scripts/ci/check_*_mutants.py` it finds would remove that conflict and the class of a gate that exists and is not
wired.

## How to run it

```
python scripts/compose_rehearsal.py --base <line head> \
    --unit 290=<sha> --unit 291=<sha> --unit 273=<sha> \
    --union .github/workflows/canonical-ci.yml \
    --json out.json --markdown out.md
```

Exit status 0 when nothing conflicts, 1 when something does, 2 on a usage error.
