# Registered-body guard, exact candidate pin and history guard (MW-C, 2026-11-21)

Unit MW-C of `acceptance/directive-sections.json` ("Canonical-owner guard: a function-to-canonical-module registry
whose test fails when a new module re-implements a registered function"). It answers three asks of the 2026-10-28
directive in part: S52.A1 ("For every major mechanism identify: CANONICAL IMPLEMENTATION, ALTERNATIVES ... RETIREMENT
CONDITION"), S69.A3 ("reconcile architectural ownership; remove competing active ownership") and S76.A2 ("Do not keep
obsolete implementations merely to preserve history"). All three stay open (`partial`, BUILDABLE_NOT_BUILT, unit
MW-C). Base: `121195907fff261bb8610ed03488ef4461b59f73` (the integration line); branch
`claude/mw-c-owner-guard-20261121`. It builds on MU-H, recorded in
`docs/evidence/canonical-owner-guard-2026-10-30/README.md` (registry, guards 1-3, pins), which is not edited.

## What changed

| File | Change |
|---|---|
| `tests/unit/test_canonical_owner_guard.py` | Guard 4 (copies of a registered function's body anywhere in the runtime tree), the distinct check, the exact candidate pin in `pin_problems`, the history guard `kept_for_problems`; 9 new tests (25 in the file) |
| `scripts/ci/check_canonical_owner_guard_mutants.py` | 17 MW-C mutants (76 in all) and a `copy_body` edit that writes a disguised copy of a registered function at run time |
| `docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml` | `greg.mission_control` REALITY: stale reason corrected, `kept_for: {consumer: acceptance.claims.crosswalk_problems}`; a comment block after the last record stating the three new rules |
| `acceptance/directive-sections.json` | S52.A1, S69.A3 and S76.A2 only: evidence, reasons and notes; S76.A2's computed tier moves from INTENDED (gap) to UNIT_VERIFIED (partial) |

No runtime file changed. The registry is PROPOSED, as before: nothing is retired, attached, activated or granted.

## What the guard now catches

**Guard 4.** For every canonical, candidate and alternate qualname of `function_owner_records` that names a function
(a method by its dotted qualname), the body is fingerprinted: docstring dropped, every variable, argument, nested def,
class, handler, alias, global and match name and every constant rewritten to one sentinel, attribute names, keyword
names, imported module names and structure kept. The fingerprint is taken from a fresh deep copy, so the cached parse
the other guards read is never rewritten and nothing is erased twice; erasing an erased tree changes nothing. A body
counts when it has at least `MIN_COPY_NODES` (25, guard 3's threshold) AST nodes: a node count, not a line count.

Every function and method at any depth (module level, methods, nested defs) of every runtime file is compared:
`runtime_files` lists the filesystem by guard 3's rule (`python_files`), because the mutant gate's copy of the tree has
no `.git`, and skips `tests/`, `docs/`, the frozen `cortex/evaluation/` and top-level hidden directories (`.git`, tool
caches, an agent's worktree). The skips are full path prefixes, never a path segment: a copy under `greg/evaluation/`
is still seen. A match outside the record's canonical, candidate and alternate modules fails and names both
locations; a `distinct` entry never exempts one. Only candidate functions of a registered body's size are copied and
fingerprinted (340 of 7,380 on this tree).

What each detector sees, on the synthetic trees of
`test_the_body_guard_catches_renamed_nested_relocated_and_one_line_copies` and
`test_the_body_guard_does_not_see_an_attribute_rename` (every copy below has its variables and arguments renamed and
its string and number literals changed, except the one-line and attribute cases; each planted file alone against
the originals):

| Planted copy | Guard 3 (`unrecorded`) | `test_no_structural_duplicates` | Guard 4 |
|---|---|---|---|
| `business/case_copy.py`: `Case.settle`, a method copy of `greg.business_loop.reconcile` | missed | missed | caught |
| `greg/wrapped.py`: `outer.inner`, a nested-def copy of `reconcile` | missed | missed | caught |
| `closure/settle_copy.py`: a copy of `reconcile` outside the six guarded packages | missed | missed | caught |
| `foundry/systems/team_copy.py`: `convene`, a copy of `foundry.systems.teams.form` in the owner's own directory | missed | missed | caught |
| `greg/oneline.py`: every statement of a registered body on one line | missed | missed | caught |
| `greg/renamed_attribute.py`: one attribute renamed (`write_text` to `write_bytes`) | missed | missed | missed (stated limit) |

The same test also shows that a copy under `greg/evaluation/` is caught, one under `cortex/evaluation/` is not (frozen),
the owners' own modules are not reported, and a genuinely different function within a fifth of the registered body's
size is not flagged. The comparison was run by a scratch script; guard 3 and `test_no_structural_duplicates` were not
changed.

**Distinct check** (`distinct_copy_problems`). A `distinct` entry says a module holds a different function; it may not
name a module that holds a copy of a registered body. Replaying the second half of the adversary's candidate game
(`scratchpad/mwc/attack/candidate_game.py`: a structural copy of `greg.organs.exchange` recorded as distinct) now fails
twice: the distinct check names the record, and guard 4 still reports the copy.

**Exact candidate pin.** For every pinned record still NEEDS_FOUNDER_DECISION, the candidates must equal `PINNED`:
a new candidate module or a new qualname on a candidate fails (before, only removals failed). Replaying the first
half of the candidate game (a side-C `greg.goal_engine2.run` on OWN-FN-GOAL-RUNTIME) gave `pin: []` on the base and
gives `OWN-FN-GOAL-RUNTIME: candidate greg.goal_engine2.run is not pinned ...` now; the same holds for each of the three
undecided records. A decided record still takes a new alternate or distinct entry without a pin change. This amends
the registry's header comment and the 2026-10-30 record ("Adding a candidate ... needs no test change"): a new
competing owner (WU-13's `governance/reality_ladder.py` joining the evidence-ladder record, for example) now needs a
reviewed change to `PINNED`.

**History guard** (`kept_for_problems`, section 76). A forward guard: every HISTORICAL or RETIRED alternate whose
module or qualname is still defined in the tree carries `kept_for`, exactly one of `{consumer: <module>.<function>}`
(outside `greg/` and `tests/` and outside the alternate's own module, a function whose source names the kept object
in a module that imports it from the alternate) or `{open_decision: <record_id>}` (a record still
NEEDS_FOUNDER_DECISION). An alternate gone from the tree needs none. Today it binds one entry: `greg.mission_control`
REALITY. Its reason said "read by nothing in the repository"; `acceptance/claims.py:80` imports it and
`crosswalk_problems` checks its six labels against `acceptance.LADDER`. The reason is corrected and the entry carries
`kept_for: {consumer: acceptance.claims.crosswalk_problems}`.

## Measured state on this tree

| Measure | Value |
|---|---|
| Registered functions (canonical, candidate, alternate) | 30; 27 at or above 25 erased nodes (27 distinct fingerprints) |
| Registered functions below the threshold, not compared | `acceptance.rank` (8), `greg.improvement.attention_close_condition` (17), `greg.improvement.claim_close_condition` (7) |
| Runtime files; functions and methods at any depth | 506; 7,380 (340 of a registered size, fingerprinted) |
| Copies outside their record (guard 4) | 0 (the study's 0, re-measured) |
| Distinct entries naming a module with a copy | 0 |
| HISTORICAL or RETIRED alternates still in the tree; without a live `kept_for` | 1 (REALITY); 0 |
| Guard 4 and the distinct check, cold, in one process | 5.5 s |

## Run time

`python -B -m pytest -q -p no:cacheprovider tests/unit/test_canonical_owner_guard.py`: **25 passed in 13.8-14.6 s**
over three runs (about 21 s wall with interpreter start); in the fail-before run the 16 earlier tests passed in 11.0 s.
By `--durations`, guard 4's real-tree test takes 3.4 s (guard 3's takes 5.2 s). Guard 4 shares guard 3's parse cache
and caches each file's fingerprints, so the distinct check costs no second scan.

## Commands and results

All in this container with Python 3.13, `-B` and `-p no:cacheprovider`. The worktree sits inside another checkout,
so the directive tool's collection was run with `PYTEST_ADDOPTS=--rootdir=<worktree>`; without it pytest picks the
outer checkout as rootdir and six nodes appear to collect nothing, on the base and on this branch alike.

| Command | Result |
|---|---|
| Fail-before: the 9 new tests on the unchanged guard code | **9 failed, 16 passed**. The pin test fails on its assertion (a new candidate passes `pin_problems`); the 8 others fail because guard 4, the distinct check and `kept_for_problems` do not exist |
| Pass-after, before the registry fix | 24 passed, 1 failed: the history guard reports REALITY without `kept_for` |
| Pass-after: the guard file | **25 passed** in 14.4 s |
| `pytest tests/unit/test_canonical_owner_guard.py tests/unit/test_no_structural_duplicates.py tests/unit/test_repo_health_gates.py tests/unit/test_import_layering.py` | **53 passed** in 22.5 s |
| `python scripts/repo_review.py --check` | exit 0, 0 hard findings; 982 mutation anchors checked; the new `copy_body` anchors (a function name in its source file) are advisory multi-site entries |
| `python -B -u scripts/ci/check_canonical_owner_guard_mutants.py` | **76/76 caught**, exit 0, 351 s. Its baseline, the whole file in the gate's copy of the tree without `.git`, passed first (25 passed in 14.1 s). The 59 earlier mutants are all still caught; the 17 MW-C mutants are listed below |
| `python -m acceptance.claims` | PASS: 0 crosswalk problems, 0 violations |
| `python -m acceptance directive --collect --against 12119590` | the pin holds, every ask closed since cites changed evidence, all 179 cited nodes collect; the only line that differs from the base's output is S76.A2, from `INTENDED of UNIT_VERIFIED (gap)` to `UNIT_VERIFIED of UNIT_VERIFIED (partial)` |

The 17 MW-C mutants, each caught by the test it names: a method copy of `reconcile` in `business/`; a copy of
`teams.form` in `foundry/systems/`; a nested-def copy of `greg.body.send_signed` in `acceptance/`; a copy of
`greg.remote.handle` in `scripts/`; a copy recorded as distinct; guard 4 exempting distinct modules; constant
erasure removed from the anonymiser; erasing the parsed tree in place; methods and nested defs no longer scanned; the
scan narrowed to the six packages; the frozen directory skipped by path segment; a third candidate on the goal
runtime; a qualname added to a candidate; the exact pin removed; REALITY's `kept_for` deleted; REALITY kept for a
consumer that does not read it; REALITY kept for a consumer under `greg/`.

## Other heads

Guard 4 and the distinct check were run statically (the worktree's guard functions called on each exported tree with
that tree's own registry; nothing from the trees was imported or run) on `git archive` exports of:

| Head | Registry change it carries | Guard 4 | Distinct check |
|---|---|---|---|
| PR #305 `6759a8c9` (base `12119590`) | distinct `greg.intake` `verify_delivery` | 0 (27 bodies, 509 files) | 0 |
| PR #314 `6608b774` (base `8d205324`) | distinct `greg.cases` `verify_delivery` | 0 (27 bodies, 493 files) | 0 |
| `claude/worker-team-20261121` `e3100f4b` (WU-03, base `12119590`) | evidence for #48 and distinct `greg.teams` `TeamRefused` | 0 (27 bodies, 507 files) | 0 |

None of the three touches the guard file, the mutant script or the directive map; each adds lines to the registry
away from the REALITY entry and the end of the file. `git merge-tree` of this branch with #305 and with the WU-03 head
is clean. With #314 it conflicts in `.github/workflows/canonical-ci.yml` and `greg/authority.py` only, as #314 already
does against the base; the registry merges automatically. Every check of the guard file (shape, pins, markers,
existence, guards 2, 3 and 4, the distinct check and the history guard), run the same static way on the merged trees
(for #314: its head with the auto-merged registry), reports **0 problems** on all three.

## Stated limits

- **Structure, not meaning.** A copy that changes structure (a statement reordered, a loop rewritten, a helper
  inlined) is a different body to guard 4. So is a copy that renames an attribute or reads a field as an attribute
  instead of a key (`row['x']` to `row.x`): `test_the_body_guard_does_not_see_an_attribute_rename` records this as
  passing, and a later change that claims that coverage must change its assertions.
- **Registered functions only.** A function the registry does not record has no owner check. Classes and constants
  are compared by guard 3 only (exact structure, six packages, module level). Three registered functions are below
  the 25-node threshold.
- **The history guard binds what the registry records.** Obsolete code no record names is not found by any test;
  the S76.A2 excerpt covers it, so the ask stays partial.
- **Pins are only as strong as review.** `PINNED`, `NOT_RUNTIME`, `FROZEN` and `MIN_COPY_NODES` are literals in the
  test; changing them changes the guard, visibly in the diff.
- **What is scanned.** The filesystem, not git: an untracked `.py` file outside a top-level hidden directory is
  scanned too, and a tracked `.py` file under a top-level hidden directory (there is none today) is not.
- **New records are not pinned.** The exact candidate pin covers the records in `PINNED`; a new undecided record is
  checked by shape only until it is pinned.

## The anchor question (S52.A1)

Section 52 asks for a record "for every major mechanism". The registry records the 8 functions found duplicated.
Which list counts as "every major mechanism" is not settled, and no build can show the registry complete until it
is: the 18 completion-contract functions (`acceptance/completion-contract.json`), the Foundry's numbered systems
(`foundry/systems/__init__.py` `SYSTEMS`, numbered 1-55, 54 entries) or the 10 concern records of
`docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml`. It is a question for the integrator or the founder, recorded in
S52.A1's reason; this unit does not choose.

## What was not done

- **The `_deliver` copies are not recorded.** `greg/organ_exchange.py:349` `_deliver` and `greg/ventures.py:340`
  `_deliver` are one body (199 erased nodes; also in `scripts/repo_review.py`'s duplicate trend). Adding `_deliver`
  to the `greg.organ_exchange` alternate's qualnames makes guard 4 fail on `greg/ventures.py:340`, and the distinct
  check fail on OWN-FN-ORGAN-EXCHANGE's `greg.ventures` entry, on this tree and on all three heads above (measured in
  memory). That would turn #305 and #314, which target this line and add distinct entries to the same record, red.
  Proposed for the integrator: move `_deliver` to one module both import (or record `greg.ventures` as an ALTERNATE
  of it), then register it. #305's `greg/intake.py` `_deliver_twin` and #314's `greg/cases.py` `_deliver` are
  different bodies and are not affected.
- `docs/CATALOG.md` is not regenerated for this file (it is regenerated at the next intake); dated snapshots,
  `docs/opus-maximus/REPOSITORY_CONVERGENCE_MAP.md` and `.github/workflows/canonical-ci.yml` are not edited. The
  mutant gate already runs in Canonical CI job 10b.
- S69.A3's blocker stays on MW-C: its residual includes functions the registry does not record, which is not S52.A2's
  (MU-H) residual.
- Not run: the full test suite and Canonical CI on this head.

## Reality level

UNIT-TESTED, in a container. The guards are unit tests over the source tree; no GREG runtime behaviour changed. The
effect is review-time: a copy of a registered function's body, renamed, relocated, nested or reformatted, cannot land
outside its record without a test failing; an undecided record cannot gain a competing owner without a pin change;
and a historical alternate stays in the tree only while something outside `greg/` and `tests/` reads it, or a founder
decision is open.
