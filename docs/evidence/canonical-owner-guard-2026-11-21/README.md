# Registered-body guard, exact pins and history guard (MW-C, 2026-11-21)

Unit MW-C of `acceptance/directive-sections.json` ("Canonical-owner guard: a function-to-canonical-module registry
whose test fails when a new module re-implements a registered function"). It bears on three asks of the 2026-10-28
directive. It answers S69.A3 ("reconcile architectural ownership; remove competing active ownership") and S76.A2 ("Do
not keep obsolete implementations merely to preserve history") in part. It adds no evidence to S52.A1 ("For every
major mechanism identify: CANONICAL IMPLEMENTATION, ALTERNATIVES ... RETIREMENT CONDITION"): it only rewrites that
ask's reason to name the three anchors that are still unsettled (below). All three stay open (`partial`,
BUILDABLE_NOT_BUILT, unit MW-C).

Branch `claude/mw-c-owner-guard-20261121`, draft PR #341 into `claude/greg-full-machine-completion-whgiee`. The first
build was based on `121195907fff`. This record describes the branch after the line at `e3a84f95` was merged in
(`99d2a102`) and after the review round that followed it. It builds on MU-H, recorded in
`docs/evidence/canonical-owner-guard-2026-10-30/README.md` (registry, guards 1-3, pins), which is not edited.

## What changed

| File | Change |
|---|---|
| `tests/unit/test_canonical_owner_guard.py` | Guard 4 (copies of a registered function's body), the twin check, the distinct check, `BODY_EXEMPTIONS`, the exact pin on an undecided record's candidates and alternates in `pin_problems`, the history guard `kept_for_problems`, a filesystem walk shared by guards 2-4; 18 new tests (34 in the file) |
| `scripts/ci/check_canonical_owner_guard_mutants.py` | 56 MW-C mutants (115 in all); `copy_body` and `append_body` edits that write a disguised copy of a registered function at run time |
| `docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml` | `greg.mission_control` REALITY: stale reason corrected, `kept_for: {consumer: acceptance.claims.crosswalk_problems}`; the header comment of `function_owner_records` corrected (which additions need a pin change); a note after the last record stating the four rules |
| `acceptance/directive-sections.json` | S52.A1: reason and note only. S69.A3: evidence, reason and note. S76.A2: evidence, `owner_paths`, declared tier and coverage, reason and note. S76.A2's computed tier moved from INTENDED (gap) to UNIT_VERIFIED (partial) |

No GREG runtime module changed. By guard 4's own definition of a runtime file, one changed: the mutant gate
`scripts/ci/check_canonical_owner_guard_mutants.py`. The registry is PROPOSED, as before: nothing is retired,
attached, activated or granted.

## What the guard now catches

**Guard 4.** It takes every canonical, candidate and alternate qualname of `function_owner_records` that names a
function (a method by its dotted qualname) and fingerprints its body. The docstring is dropped. Every variable,
argument, nested def, class, handler, alias, global and match name, and every constant, is rewritten to one sentinel.
Three one-node edits are normalised away, and nothing more: `pass` and no-op constant statements (a string, `...`)
are dropped, an annotated assignment is read as the plain assignment (a bare annotation is dropped), and every import
gets the erased alias, whether one is written or not. Attribute names, keyword names, imported module names and
structure are kept. The fingerprint is taken from a fresh deep copy, so the cached parse the other guards read is
never rewritten. A body counts when it has at least `MIN_COPY_NODES` (25, guard 3's threshold) AST nodes. That is a
node count, not a line count.

Every function and method at any depth (module level, methods, nested defs, async defs) of every runtime file is
compared. `runtime_files` walks the filesystem, because the mutant gate's copy of the tree has no `.git`. It lists every `.py` file
under the repository root, read as bytes (a UTF-8 BOM parses), with these exclusions:

- `tests/` and `docs/`, by top-level path prefix, never by a path segment. A copy under `greg/evaluation/` is seen.
  Fixtures in `tests/` may copy a body on purpose;
- top-level hidden entries (`.git`, tool caches, an agent's worktree);
- the files under `cortex/evaluation/` whose current bytes a `cortex/evaluation/freeze-*.json` manifest hashes
  (`inputs.code`, sha256): the sealed instruments, 9 of 55 on this tree. GREG imports `cortex.evaluation.closure`, so
  every other file there is scanned: new files, files edited after their freeze (`crossgeo.py` today) and every
  subdirectory.

A directory symlink is followed only when its target resolves inside the repository and is not already on the walk's
own path, so a loop ends there. A link that leaves the repository is never followed. `Path.rglob`, which the scan
used before, follows a link only at the directory it starts from and never below it, on 3.11 and 3.13 alike, so a
top-level `venv/` link to site-packages was walked in full (14,574 files, 102 s against 4 s here), while a nested
`greg/vendor -> docs/vendor` link, importable as `greg.vendor`, was never read. A `.py` file under `__pycache__/` is
importable and is scanned.

A body is exempt only at its own registered module and qualname. A match anywhere else fails and names both
locations, inside the body's record or outside it: beside the owner in its own module, in one of the record's
candidate or alternate modules, anywhere else. Two registered locations whose bodies share one fingerprint fail
(`registered_twin_problems`), so recording a copy does not make it an owner. A `distinct` entry never exempts a copy.
Only an entry in `BODY_EXEMPTIONS` does. That is a literal in the test, empty today, and it maps one location to the
registered body it resembles and the reason it is a different function. An entry clears that location for that body
and nothing else, and an entry that no longer matches a copy, or gives no reason, fails. Only functions of a
registered body's erased size are copied and fingerprinted (364 of 7,902 on this tree).

What the repository's tests plant, and what guard 4 does with each, is in
`test_the_body_guard_catches_renamed_nested_relocated_and_one_line_copies`,
`test_the_body_guard_ignores_one_node_edits_pass_no_op_constants_annotations_and_import_aliases`,
`test_a_registered_body_is_exempt_only_at_its_own_location`,
`test_the_body_scan_reads_bom_files_follows_links_inside_the_repository_only_and_sees_pycache`,
`test_the_body_scan_reads_cortex_evaluation_except_the_files_a_freeze_manifest_seals` and
`test_the_body_guard_does_not_see_an_attribute_rename`. Every copy there has its variables and arguments renamed and
its string and number literals changed, the one-line copy included, except the attribute-rename case and the copies
that change only one erased name or one statement:

| Planted copy | Guard 4 |
|---|---|
| a method copy of `greg.business_loop.reconcile` in `business/`; a nested-def copy; a copy in `closure/`, in a top-level `.py` file, under `cortex/` and in `greg/evaluation/` | caught |
| a copy of `foundry.systems.teams.form` in the owner's own directory; an `async def` copy; a copy of `greg.body.send_signed` with every statement on one line | caught |
| a copy with only an except-as name, an import alias or a nested def's name renamed | caught |
| a copy with one `pass`, a no-op string, `...`, a local annotation, a bare annotation or an added import alias | caught |
| a copy appended to an existing ALTERNATE module, beside the owner in its own module, or in an undecided record's alternate module | caught |
| a copy in a UTF-8 BOM file, under `__pycache__/`, through an in-repository directory link, under `cortex/evaluation/` (new, edited, subdirectory) | caught |
| the sealed `cortex/evaluation/` file; a copy reachable only through a link out of the repository | not scanned |
| one attribute renamed (`write_text` to `write_bytes`) or a field read as an attribute; a no-op `_unused = 0`; an `if True:` wrapper | missed (stated limits) |

Guard 3 and `test_no_structural_duplicates` were not changed. Guard 3 compares the exact module-level structure,
names included, in the six guarded packages only, so it cannot see a renamed copy, a method, a nested def or a copy
outside those packages.

**Distinct check** (`distinct_copy_problems`). A `distinct` entry says a module holds a different function. It may
not name a module that holds a copy of a registered body, from its own record or from any other, unless
`BODY_EXEMPTIONS` clears that copy. `test_a_distinct_entry_cannot_vouch_for_a_module_that_holds_a_copy` records a
structural copy of `greg.organs.exchange` as distinct, in its own record and in another, and both fail. Guard 4 still
reports the copy itself.

**Exact pin.** For every pinned record still NEEDS_FOUNDER_DECISION, the candidates and the alternates must equal
`PINNED`: a new candidate or alternate module, a new qualname on one, or a whole-module alternate where qualnames are
pinned fails. Before MW-C only removals failed. `test_an_undecided_record_takes_no_new_candidate_without_a_pin_change`
and `test_an_undecided_record_takes_no_new_alternate_without_a_pin_change` hold for each of the three undecided
records. The second closes the review's blocking finding: a disguised copy of `greg.gravity.step` recorded as a live
ALTERNATE (`egregore.goal_engine2` `advance`) of the undecided goal runtime passed every guard. It now fails the pin,
guard 4 (the copy and the original are each a copy of the other) and the twin check. A decided record still takes a
new alternate, and any record a new distinct entry, without a pin change. This amends the 2026-10-30 record and the
registry's header comment, which is corrected in place. A new competing implementation of an undecided record
(WU-13's `governance/reality_ladder.py` joining the evidence-ladder record, for example) now needs a reviewed change
to `PINNED`.

**History guard** (`kept_for_problems`, section 76). A forward guard: every HISTORICAL or RETIRED alternate whose
module or qualname is still defined in the tree carries `kept_for`, exactly one of:

- `{consumer: <module>.<function>}`: a function whose source names the kept object, in a module that imports it from
  the alternate. It may not be under `greg/`, `tests/`, `docs/` or `scripts/ci/`, in any `conftest.py`, or in the
  alternate's own module;
- `{open_decision: <record_id>}`: the alternate's own record, while that record is still NEEDS_FOUNDER_DECISION.
  Another record's open decision keeps nothing.

An alternate gone from the tree needs none. Today the guard binds one entry, `greg.mission_control` REALITY. Its
reason said "read by nothing in the repository". In fact `acceptance/claims.py:80` imports it, and
`acceptance.claims.crosswalk_problems` reads REALITY to check that the crosswalk (`REALITY_CROSSWALK`) covers its
labels. The claim-label reader itself uses `REALITY_CROSSWALK`, not REALITY. So this consumer is a self-check of the
kept object outside `tests/`, a weak reason to keep it, and the record says so. A consumer is checked by what its
source names, not by whether anything calls it, so a dead two-line shim elsewhere that imports and returns the object
still passes. `test_kept_for_names_the_alternates_own_open_record_and_a_consumer_outside_tests_and_tools` records
that as passing.

**Parse warnings.** An invalid escape in a tracked script is a SyntaxWarning on 3.12+ and a DeprecationWarning on
3.11, CI's version. The parse every guard reads now hides both, so CI's summary carries no warnings from this file.

## Measured state on this tree

| Measure | Value |
|---|---|
| Registered qualnames (canonical, candidate, alternate) | 50: 30 functions, 9 classes, 11 constants |
| Registered function bodies compared | 27 at or above 25 erased nodes; 27 distinct fingerprints; 0 twins |
| Registered functions below the threshold, not compared | `acceptance.rank` (8), `greg.improvement.attention_close_condition` (17), `greg.improvement.claim_close_condition` (7) |
| Methods of the 9 registered classes | not compared (0 added); see "Not done: class methods" |
| Runtime files; functions and methods at any depth | 553 (46 under `cortex/evaluation/`, 9 sealed files skipped); 7,902 (364 of a registered size, fingerprinted) |
| `_erased_size` equal to the fingerprint's size | 7,902 of 7,902 |
| Copies at any location but their own (guard 4); exemptions | 0; `BODY_EXEMPTIONS` empty |
| Distinct entries naming a module with a copy | 0 |
| HISTORICAL or RETIRED alternates still in the tree; without a live `kept_for` | 1 (REALITY); 0 |
| False-positive check: stdlib and site-packages of this container's Python 3.13 | 16,293 files, 204,082 functions, 0 match a registered body |
| Guard 4, the twin check and the distinct check, cold, in one process | 5.2 s |

## Run time

`python -B -m pytest -q -p no:cacheprovider tests/unit/test_canonical_owner_guard.py`: **34 passed** in 14-15 s on
Python 3.13 and 15-17 s on Python 3.11, with no warnings on either.

## Commands and results

All in this container with `-B` and `-p no:cacheprovider`. The worktree sits inside another checkout, so the
directive tool's collection was run with `PYTEST_ADDOPTS=--rootdir=<worktree>`; without it pytest picks the outer
checkout as rootdir.

| Command | Python 3.13 | Python 3.11 |
|---|---|---|
| `pytest tests/unit/test_canonical_owner_guard.py` | **34 passed**, no warnings | **34 passed**, no warnings (2 DeprecationWarnings before this round) |
| `pytest tests/unit/test_canonical_owner_guard.py tests/unit/test_no_structural_duplicates.py tests/unit/test_repo_health_gates.py tests/unit/test_import_layering.py` | **62 passed** | **62 passed**; the 2 DeprecationWarnings left come from `test_no_structural_duplicates.py`, which parses the same script and is not in this unit |
| `python scripts/ci/check_canonical_owner_guard_mutants.py`, in a `git archive` export without `.git` | BASELINE_PASSES (34 passed), **115/115 caught**, rc 0, 7 min | BASELINE_PASSES (34 passed), **115/115 caught**, rc 0, 9 min |
| `python scripts/repo_review.py --check` | rc 0, 0 hard findings, 992 literal anchors checked | rc 0, the same |
| `python -m acceptance.claims` | PASS: 0 crosswalk problems, 0 violations | PASS, the same |
| `python -B -m acceptance directive --collect --against e3a84f95` | rc 0: the pin holds, every ask closed since cites new or changed evidence (none closed), all 183 cited nodes collect; 82/272 asks met, as before; S52.A1, S69.A3 and S76.A2 each `UNIT_VERIFIED of UNIT_VERIFIED (partial)`, BUILDABLE_NOT_BUILT MW-C | not run |

The gate held 76 mutants (17 MW-C) before this round and holds 115 (56 MW-C): 40 new, and the three re-anchored ones.

Each item of the review round has a test that failed on the guard as it was and passes now, on both Pythons:

| Finding | Test (fails before, passes after) |
|---|---|
| A copy joins an undecided record as a live ALTERNATE (blocking) | `test_an_undecided_record_takes_no_new_alternate_without_a_pin_change`, `test_a_registered_body_is_exempt_only_at_its_own_location`, `test_two_registered_locations_with_one_body_fail`. The review's own tree (the copy recorded as an ALTERNATE, plus a copy appended to `business/commercial_loop.py`) passed every test of the guard as it stood before this fix (29 at `703297d0`) and now fails the pin, body, distinct and candidate-pin tests |
| `cortex/evaluation/` skipped wholesale | `test_the_body_scan_reads_cortex_evaluation_except_the_files_a_freeze_manifest_seals` |
| One-node edits evade the match | `test_the_body_guard_ignores_one_node_edits_pass_no_op_constants_annotations_and_import_aliases` |
| `kept_for` satisfied by any open decision, or by a consumer in docs/, scripts/ci/ or a conftest.py | `test_kept_for_names_the_alternates_own_open_record_and_a_consumer_outside_tests_and_tools` |
| No reviewed escape hatch for a false positive | `test_a_pinned_exemption_clears_exactly_one_location_and_a_stale_one_fails` |
| BOM files, directory links, `__pycache__/` | `test_the_body_scan_reads_bom_files_follows_links_inside_the_repository_only_and_sees_pycache` |
| DeprecationWarning leaks on 3.11 | `test_a_file_with_an_invalid_escape_parses_without_a_warning_on_any_python` |
| Eight code mutants survived the whole gate | new positive controls in T4 and T7; each matching gate mutant SURVIVES against the previous tests and is CAUGHT now |

## Compatibility with the line and with the open heads

WU-03 (#338) is now on the line, at `d776ca13`, and it added a real `greg/teams.py`. Two mutants from #253 create
`greg/teams.py`, so after that merge the gate reported both as STALE and exited 1, at 74/76. `c1679db0` re-pointed
both at `greg/team_forming.py`, keeping their intent: a re-implementation of temporary teams added, and F5, a second
canonical module added to temporary teams. Three earlier MW-C mutants anchored on lines this round rewrote are
re-anchored and still caught.

Both open heads that target the line were merged with this branch in a scratch tree (`git merge-tree`) and checked
the same way, with the guard file and the mutant gate run on Python 3.11, CI's version:

| Head | Merge | Every guard check (shape, pins, markers, existence, guards 2, 3 and 4, twins, distinct, history) | Mutant gate |
|---|---|---|---|
| PR #305 `6759a8c9` | clean | 0 problems; 27 bodies, 556 runtime files | BASELINE_PASSES (34 passed), **115/115 caught**, rc 0 |
| PR #314 `6608b774` | conflicts only in `.github/workflows/canonical-ci.yml` and `greg/authority.py`, as against the base; taken from #314 for the check; the registry merges automatically | 0 problems; 27 bodies, 555 runtime files | BASELINE_PASSES (34 passed), **115/115 caught**, rc 0 |

The `_deliver` question below applies to both.

## Stated limits

- **Structure, not meaning.** A copy that changes structure is a different body to guard 4. That covers a statement
  reordered or added (a no-op `_unused = 0`), a body wrapped in `if True:`, a body split into two functions, and a
  helper inlined. So is a copy that renames an attribute or a call keyword, or reads a field as an attribute
  instead of a key (`row['x']` to `row.x`). `test_the_body_guard_does_not_see_an_attribute_rename` records the
  attribute case as passing. A later change that claims that coverage must change its assertions.
- **Code outside a def.** A body pasted at module level, in a class body or in an `if __name__ == "__main__":` block,
  or held in a string and run with `exec`, is not a function and is never compared.
- **The fork pattern.** Edit the owner and, in the same diff, keep its old body elsewhere (`reconcile_v1`). The kept
  copy matches nothing registered, because the registered body is the edited one, so it passes.
- **Registered functions only.** A function the registry does not record has no owner check. The methods of the 9
  registered classes are not compared (see below), and classes and constants are compared by guard 3 only (exact
  structure, six packages, module level). The three registered functions below the 25-node threshold
  (`acceptance.rank`, `greg.improvement.attention_close_condition`, `greg.improvement.claim_close_condition`) have no
  copy check: a disguised copy of either `greg.improvement` function passes.
- **Small bodies have generic shapes.** A different function whose erased body equals a small registered one fails.
  The only way to clear one is a reviewed `BODY_EXEMPTIONS` entry; none is needed today.
- **The history guard binds what the registry records.** Obsolete code no record names is not found by any test; the
  S76.A2 excerpt covers it, so the ask stays partial. A consumer is checked by what its source names, so a dead shim
  outside the excluded places passes.
- **Pins are only as strong as review.** `PINNED`, `BODY_EXEMPTIONS`, `NOT_RUNTIME`, `SEALED_UNDER`, `NOT_CONSUMERS`
  and `MIN_COPY_NODES` are literals in the test; changing them changes the guard, visibly in the diff.
- **What is scanned.** The filesystem, not git. An untracked `.py` file outside a top-level hidden entry is scanned
  too, and a tracked `.py` file under a top-level hidden directory (there is none today) is not. Neither is a copy
  reachable only through a link out of the repository.
- **New records are not pinned.** The exact pin covers the records in `PINNED`; a new undecided record is checked by
  shape only until it is pinned.

## The anchor question (S52.A1)

Section 52 asks for a record "for every major mechanism". The registry records the 8 functions found duplicated.
Which list counts as "every major mechanism" is not settled, and no build can show the registry complete until it
is. The candidates are the 18 completion-contract functions (`acceptance/completion-contract.json`), the Foundry's
numbered systems (`foundry/systems/__init__.py` `SYSTEMS`, numbered 1-55, 54 entries) and the 10 concern records of
`docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml`. That is a question for the integrator or the founder. MW-C
records it in S52.A1's reason and adds no evidence to S52.A1. It does not choose.

## What was not done

- **Not done: class methods.** The review asked that each registered class be expanded into its methods
  (`Class.method`) for comparison. Measured first, the expansion adds 99 method bodies (126 bodies, 125 fingerprints).
  On today's tree it reports four problems, so it was not committed, and the rule was not weakened to pass:
  - `foundry/advantage.py:82` `OpportunitySpec.digest` and `foundry/advantage.py:161` `AdvantageArchitecture.digest`
    match `omnimorph.engine.OrganManifest.digest` (`omnimorph/engine.py:62`);
  - `foundry/pipeline.py:359` `_outcome_hash` matches the same `OrganManifest.digest`;
  - `egregore.goals.GoalRegistry.tactic_forbidden` (`egregore/goals.py:603`) and `GoalRegistry.domain_muted`
    (`:606`) share one fingerprint (28 nodes), which the twin check fails.

  Each is a generic shape: a JSON-dump-and-hash property, and a one-line preference lookup. Deciding whether they
  are copies, different functions (`BODY_EXEMPTIONS` entries) or a sign that the method threshold must be higher is a
  review decision, not a builder's. Until then the methods of the 9 registered classes are not compared.
- **The `_deliver` copies are not recorded.** `greg/organ_exchange.py:349` `_deliver` and `greg/ventures.py:340`
  `_deliver` are one body (199 erased nodes; also in `scripts/repo_review.py`'s duplicate trend). Adding `_deliver`
  to the `greg.organ_exchange` alternate's qualnames would make guard 4 fail on `greg/ventures.py:340`. It would also
  make the distinct check fail, through the `greg.ventures` distinct entry OWN-FN-ORGAN-EXCHANGE already has. That
  would turn this branch red, as well as #305 and #314, which target this line; the distinct entries #305 and #314
  add (`greg.intake`, `greg.cases`) play no part. Proposed for the integrator: move `_deliver` to one module both
  import (or record `greg.ventures` as an ALTERNATE of it, which the twin check would then also fail until one copy
  goes), then register it. #305's `greg/intake.py` `_deliver_twin` and #314's `greg/cases.py` `_deliver` are
  different bodies.
- `docs/CATALOG.md` is not regenerated for this file (it is regenerated at the next intake); dated snapshots,
  `docs/opus-maximus/REPOSITORY_CONVERGENCE_MAP.md` and `.github/workflows/canonical-ci.yml` are not edited. The
  mutant gate already runs in Canonical CI job 10b.
- S69.A3's blocker stays on MW-C: its residual includes functions the registry does not record, which is not S52.A2's
  (MU-H) residual.
- Not run: the full test suite and Canonical CI on this head.

## Reality level

UNIT-TESTED, in a container. The guards are unit tests over the source tree; no GREG runtime behaviour changed. The
effect is at review time, and limited by the stated limits above.

- A copy of one of the 27 registered function bodies, renamed, relocated, nested, made async, reformatted or changed
  by one of the three normalised one-node edits, cannot land anywhere but that body's own location without a test
  failing. That excludes the three registered functions below the threshold and the methods of the 9 registered
  classes, and it holds only in the scanned files, which leave out `tests/`, `docs/` and the sealed instruments.
- An undecided record cannot gain a competing candidate or alternate without a pin change. A new undecided record is
  not pinned.
- A historical alternate stays in the tree only while code outside `greg/`, `tests/`, `docs/`, `scripts/ci/` and any
  `conftest.py` names it, or while its own record's founder decision is open.
