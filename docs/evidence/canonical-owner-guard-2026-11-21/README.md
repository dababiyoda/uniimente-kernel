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
(`99d2a102`), after the review round that followed it, after the second review of `7c2b39e5` (round 4,
2026-11-22, findings N1-N8 below), and after round 5's review of `79ef5742` (fixed in round 6, 2026-11-22, items B1-B6
below). It builds on MU-H, recorded in
`docs/evidence/canonical-owner-guard-2026-10-30/README.md` (registry, guards 1-3, pins), which is not edited.

Claims discipline: every guarantee below names the test that enforces it; anything without a test is stated as a
limit. Threat model: see "Reality level" at the end. These guards catch ordinary changes by cooperating agents, not a
deliberate evader.

## What changed

| File | Change |
|---|---|
| `tests/unit/test_canonical_owner_guard.py` | Guard 4 (copies of a registered function's body), the twin check, the distinct check, `BODY_EXEMPTIONS`, the history guard `kept_for_problems`, a filesystem walk shared by guards 2-4. Round 4: `UNDECIDED_ENTRIES` (an undecided record pinned whole, replacing the exact pin on its candidates and alternates), guard 3's structural-copy check no longer honouring `distinct`, `SEALED` (the skipped cortex/evaluation/ files by path and digest), `COMPARED` (the compared bodies), `binding` (last binding), `module_file` package-first with `AmbiguousModule`, `module_name_problems`, `_once` (each real file once). Round 6: `binding_problems` (one binding per registered qualname; no star import or computed namespace write in its module), every record pinned in `PINNED`, registered classes compared whole (`body_shape`; `COMPARED` 36), sealed files in the module-name rule. 30 new tests since `e3a84f95` (46 in the file), 7 of them in round 4 and 5 in round 6 |
| `scripts/ci/check_canonical_owner_guard_mutants.py` | 98 MW-C mutants (157 in all): 24 new in round 4 and 8 re-anchored on rewritten lines; 18 new and 1 re-anchored in round 6; `copy_body`, `append_body`, (round 4) `seal` and (round 6) `copy_class` and `append_class` edits that write a disguised copy of a registered function, a freeze manifest for a file, or a verbatim copy of a registered class, at run time |
| `docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml` | `greg.mission_control` REALITY: stale reason corrected, `kept_for: {consumer: acceptance.claims.crosswalk_problems}`; the header comment of `function_owner_records` and the note after the last record rewritten on 2026-11-22 so that each rule names its test and the rest are stated as limits, and again in round 6 (the threat model, the ruling case, every pin's test, the new rules; "nine" corrected to 10). No record or entry changed |
| `acceptance/directive-sections.json` | S52.A1: reason and note only. S69.A3: evidence (7 more nodes in round 4, 5 more in round 6), reason and note. S76.A2: evidence, `owner_paths`, declared tier and coverage, reason and note. S76.A2's computed tier moved from INTENDED (gap) to UNIT_VERIFIED (partial) |

No GREG runtime module changed. By guard 4's own definition of a runtime file, one changed: the mutant gate
`scripts/ci/check_canonical_owner_guard_mutants.py`. The registry is PROPOSED, as before: nothing is retired,
attached, activated or granted.

## What the guard now catches

**Guard 4.** It takes every canonical, candidate and alternate qualname of `function_owner_records` that names a
function (a method by its dotted qualname) and fingerprints its body, and since round 6 every one that names a class,
whose whole body it fingerprints (B3, below). A qualname resolves, part by part, to the LAST statement that binds it
in source order (`binding`; `test_a_registered_qualname_names_its_last_binding_as_python_does`), and a module resolves
to its package before a module file of the same name, both present failing with `AmbiguousModule` (`module_file`;
`test_a_package_shadows_a_module_of_the_same_name_and_no_two_files_share_a_module_name`). Source order is not what
Python runs: round 5's review put a decoy def in a branch that never runs (`if False:`, `if TYPE_CHECKING:`,
`try: ... except ImportError:`) after the real def, the guard read the decoy, and a copy of the real body passed.
Since round 6 every canonical, candidate and alternate qualname has exactly one binding at its level in its module
(one def or class statement, or one assignment for a constant; no other def, class, assignment, import, loop, with,
except or match target, walrus, `globals()` key, `global` declaration or `Class.attr =` binding, dead branches
included), and a module that holds one has no star import and no write to its namespace with a computed name
(`globals().update(vars(m))`, `globals()[name] = ...`) (`binding_problems`;
`test_every_registered_qualname_has_one_binding_and_its_module_no_computed_binding`,
`test_a_decoy_rebinding_or_star_import_of_a_registered_qualname_fails`). So, for ordinary code, the def or class the
guards read is the one Python binds. `@overload` stubs of a registered function are now a second binding and fail.
In the body, the docstring is dropped, and every variable, argument, nested def, class, handler, alias, global and match name, and every
constant, is rewritten to one sentinel.
Three one-node edits are normalised away, and nothing more: `pass` and no-op constant statements (a string, `...`)
are dropped, an annotated assignment is read as the plain assignment (a bare annotation is dropped), and every import
gets the erased alias, whether one is written or not. Attribute names, keyword names, imported module names and
structure are kept. The fingerprint is taken from a fresh deep copy, so the cached parse the other guards read is
never rewritten. A body counts when it has at least `MIN_COPY_NODES` (25, guard 3's threshold) AST nodes. That is a
node count, not a line count. Which bodies are compared is pinned: `COMPARED` lists the 36 (module, qualname)
locations (27 functions and, since round 6, the 9 registered classes), and a body that leaves the comparison (its last
binding no longer a def or class, a body shrunk below the threshold, a thin delegation that leaves the wrapper below
it) or joins it fails until the literal changes (`compared_problems`;
`test_the_set_of_compared_registered_bodies_is_pinned`). The count floor of 20 that stood in for this is gone.
`COMPARED` pins where the compared bodies are, not what they hold. Round 5's review showed that a wrapper of 25 nodes
or more that calls a new helper holding the owner's old logic stays compared while the helper is not, so a copy of
the moved logic passes. Round 4's record said this extracted-helper case was caught; only the thin delegation is.
It is the fork pattern performed in the owner's own module, a stated limit (below, with the measurement behind the
choice not to pin each body's digest).

Every function and method at any depth (module level, methods, nested defs, async defs) of every runtime file is
compared with the registered function bodies, and since round 6 every class at any depth with the registered class
bodies. `runtime_files` walks the filesystem, because the mutant gate's copy of the tree has no `.git`. It lists every `.py` file
under the repository root, read as bytes (a UTF-8 BOM parses), each real file once, with these exclusions:

- `tests/` and `docs/`, by top-level path prefix, never by a path segment. A copy under `greg/evaluation/` is seen.
  Fixtures in `tests/` may copy a body on purpose;
- top-level hidden entries (`.git`, tool caches, an agent's worktree);
- the sealed instruments under `cortex/evaluation/`: the files the test's `SEALED` literal names, each only while its
  current bytes hash to the digest pinned there and a `cortex/evaluation/freeze-*.json` manifest (`inputs.code`)
  records that digest for it. 9 of 55 on this tree. A manifest added in a diff seals nothing, a pinned file edited and
  re-sealed by a new manifest is scanned, and a `SEALED` entry that seals nothing fails (`sealed_files`,
  `sealed_problems`; `test_a_freeze_manifest_seals_only_the_files_and_bytes_the_test_pins`,
  `test_the_body_scan_reads_cortex_evaluation_except_the_files_a_freeze_manifest_seals`,
  `test_no_copy_of_a_registered_function_body_outside_its_record`). GREG imports `cortex.evaluation.closure`, so
  every other file there is scanned: new files, files edited after their freeze (`crossgeo.py` today) and every
  subdirectory. Round 3 trusted any manifest; round 4's review showed a manifest written in the same diff hid a copy.

A DIRECTORY symlink is followed only when its target resolves inside the repository and is not already on the walk's
own path, so a loop ends there; a directory link that leaves the repository is never followed
(`test_the_body_scan_reads_bom_files_follows_links_inside_the_repository_only_and_sees_pycache`). A FILE symlink ending
in `.py` is followed wherever it points, out of the repository too: the scan reads more, not less, and an unparseable
target fails guard 4 (`test_the_walk_reads_each_real_file_once_and_follows_file_links_anywhere`; round 3 said no link
out of the repository was followed, which was true of directory links only). Each real file is read once (`_once`):
at its real path when the walk lists it there and the scan keeps it, otherwise at one link path, the one through the
fewest links. So a sibling link such as `examples/app/greg -> greg` adds nothing and a registered body is never a copy
of itself, while `greg/vendor -> docs/vendor` (importable as `greg.vendor`, its target never read where it lies) is
read at the link path (`test_the_walk_reads_each_real_file_once_and_follows_file_links_anywhere`,
`test_the_body_scan_reads_bom_files_follows_links_inside_the_repository_only_and_sees_pycache`). Two runtime files with
one module name (a top-level `greg.business_loop.py` beside `greg/business_loop.py`) fail, because guard 4 tells a
body's own location by module name (`module_name_problems`;
`test_a_package_shadows_a_module_of_the_same_name_and_no_two_files_share_a_module_name`). Since round 6 the `SEALED`
files take part in that rule too, so a package `cortex/evaluation/scoring/` beside the sealed `scoring.py` (Python
imports the package) fails instead of shadowing the frozen instrument while the guard counts it sealed
(`test_a_package_beside_a_sealed_file_fails_the_module_name_rule`). `Path.rglob`, which the scan used before round 3,
follows a link only at the directory it starts from and never below it, on 3.11 and 3.13 alike, so a top-level
`venv/` link to site-packages was walked in full (measured in round 3 on this container: 14,574 files, about 102 s
against about 4 s; round 5 counted 14,067 files under a link to today's site-packages), while a nested
`greg/vendor -> docs/vendor` link was never read. A `.py` file under `__pycache__/` is importable and is scanned. The tree has no symlinks today.

A body is exempt only at its own registered module and qualname. A match anywhere else fails and names both
locations, inside the body's record or outside it: beside the owner in its own module, in one of the record's
candidate or alternate modules, anywhere else. Two registered locations whose bodies share one fingerprint fail
(`registered_twin_problems`; `test_two_registered_locations_with_one_body_fail`), so recording a copy does not make
it an owner. Since round 6 both rules hold for the whole body of a registered class too, compared with classes only
(`body_shape`; `test_a_registered_class_body_is_compared_whole_at_its_own_location_and_for_twins`): round 5's review
appended a verbatim copy of `GoalGravityLoop` (candidate side A) to `greg/gravity.py` (side B's own module, which
guard 3 skips), and recorded a copy of `CommercialLoop` as a new ALTERNATE of the decided commerce record, and both
passed every test; both fail now, as does a disguised class copy elsewhere. A class's methods are still not compared
one by one, so a copy of one method on its own passes (the same test records it). A `distinct` entry exempts no copy from guard 4 (`test_a_distinct_entry_cannot_vouch_for_a_module_that_holds_a_copy`)
nor, since round 4, from guard 3's structural-copy check
(`test_guard_3_reports_a_structural_copy_even_where_a_distinct_entry_names_it`); it still exempts a name from guard 3's
marker and exact-name checks, which is what it is for. Only an entry in `BODY_EXEMPTIONS` clears a copy. That is a literal in the test, empty today, and it maps one location to the
registered body it resembles and the reason it is a different function. An entry clears that location for that body
and nothing else, and an entry that no longer matches a copy, or gives no reason, fails
(`test_a_pinned_exemption_clears_exactly_one_location_and_a_stale_one_fails`). Only functions of a registered body's
erased size are copied and fingerprinted (418 of 7,902 functions and 23 of 618 classes on this tree).

What the repository's tests plant, and what guard 4 does with each, is in
`test_the_body_guard_catches_renamed_nested_relocated_and_one_line_copies`,
`test_the_body_guard_ignores_one_node_edits_pass_no_op_constants_annotations_and_import_aliases`,
`test_a_registered_body_is_exempt_only_at_its_own_location`,
`test_the_body_scan_reads_bom_files_follows_links_inside_the_repository_only_and_sees_pycache`,
`test_the_body_scan_reads_cortex_evaluation_except_the_files_a_freeze_manifest_seals`,
`test_a_freeze_manifest_seals_only_the_files_and_bytes_the_test_pins`,
`test_a_registered_qualname_names_its_last_binding_as_python_does`,
`test_a_package_shadows_a_module_of_the_same_name_and_no_two_files_share_a_module_name`,
`test_the_walk_reads_each_real_file_once_and_follows_file_links_anywhere`,
`test_a_decoy_rebinding_or_star_import_of_a_registered_qualname_fails`,
`test_a_registered_class_body_is_compared_whole_at_its_own_location_and_for_twins`,
`test_a_package_beside_a_sealed_file_fails_the_module_name_rule` and
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
| a copy in a UTF-8 BOM file, under `__pycache__/`, through an in-repository directory link to an unscanned place (`greg/vendor -> docs/vendor`), under `cortex/evaluation/` (new, edited, subdirectory) | caught |
| a copy under `cortex/evaluation/` sealed by a freeze manifest written in the same diff; a `SEALED` file edited and re-sealed | caught |
| a copy reached through a FILE link to a file outside the repository | caught, at the link path |
| a copy in a package beside a module of the same name; a top-level file named after the owner's module | fails (`AmbiguousModule`; one module name for two files) |
| a registered body hidden behind `@overload` stubs, a decoy def in an `if False:`, `if TYPE_CHECKING:` or `except ImportError:` branch after it, a later rebinding, or a star import or `globals().update(vars(m))` in its module | fails (one binding, round 6; `binding_problems`) |
| the owner's body moved to a helper behind a thin delegation (the wrapper below 25 nodes) | fails (`COMPARED`) |
| a verbatim copy of a registered class in its record's own module or recorded as a new alternate of a decided record; a disguised class copy | caught (round 6, class bodies compared whole) |
| a package beside a `SEALED` file of the same module name | fails (round 6, one module name for two files) |
| a registered body reached again through a sibling directory link (`examples/app/greg -> greg`) | read once, at its real path: no false copy |
| a `SEALED` `cortex/evaluation/` file whose bytes still match; a copy reachable only through a DIRECTORY link out of the repository | not scanned |
| one attribute renamed (`write_text` to `write_bytes`) or a field read as an attribute; a no-op `_unused = 0`; an `if True:` wrapper | missed (stated limits) |
| the owner's logic moved to a new helper behind a wrapper of 25 nodes or more, and a copy of the moved logic; a copy of one method of a registered class | missed (stated limits: the fork pattern; methods not compared one by one) |

`test_no_structural_duplicates` was not changed. Guard 3 was, though round 3's record said it was not: its file
listing (`python_files`) moved to the shared walk in round 3 (directory links followed inside the repository,
`__pycache__/` read) and, in round 4, reads each real file once and lists the six packages together, so a link
between two of them is read once (`test_the_walk_reads_each_real_file_once_and_follows_file_links_anywhere`); on
today's tree both listings are file for file what they were. In round 4 its structural-copy check also stopped
honouring `distinct` entries (0 reports on today's tree). Guard 3 compares the exact module-level structure, names
included, in the six guarded packages only, so it cannot see a renamed copy, a method, a nested def or a copy outside
those packages.

**Distinct check** (`distinct_copy_problems`). A `distinct` entry says a module holds a different function. It may
not name a module that holds a copy of a registered body, from its own record or from any other, unless
`BODY_EXEMPTIONS` clears that copy. `test_a_distinct_entry_cannot_vouch_for_a_module_that_holds_a_copy` records a
structural copy of `greg.organs.exchange` as distinct, in its own record and in another, and both fail. Guard 4 still
reports the copy itself.

**Undecided records' entries pinned** (`undecided_problems`, round 4). Every record that is NEEDS_FOUNDER_DECISION
must hold exactly the entries of its `UNDECIDED_ENTRIES` literal in the test, field for field and in order:
canonical, candidates, alternates (status, reason, conditions and `kept_for` included) and distinct entries, 24 entries
across the three records today. The entries only: the record's own fields (`decision_needed`, `safe_default`,
`review_trigger`, `migration_path`, `effect`) change with no test failure, and `markers` and `generic_names` are
bounded, not pinned (below).
Any entry or field added, removed, changed or reordered fails, and so does an undecided record the literal does not
hold (`test_an_undecided_record_takes_no_new_or_changed_entry_of_any_role_without_a_pin_change`). Round 3 pinned
only the candidates and alternates by module and qualname; round 4's review showed that a competing owner still
joined through `distinct` (WU-13's `REALITY_LADDER` on the evidence ladder; a verbatim copy of `GoalGravityLoop` as a
third goal runtime) and that an alternate's status could change (`GoalChase` RESEARCH to a live ALTERNATE; `REALITY`
revived from HISTORICAL), each with 34 tests passing. All four now fail. The earlier tests still hold:
`test_an_undecided_record_takes_no_new_candidate_without_a_pin_change` and
`test_an_undecided_record_takes_no_new_alternate_without_a_pin_change` (the round-3 blocking finding: a disguised
copy of `greg.gravity.step` recorded as a live ALTERNATE, which also fails guard 4 and the twin check). A decided
record still takes a new alternate or distinct entry without a pin change (asserted in both tests); a distinct entry
there exempts names only. This amends the 2026-10-30 record and the registry's header comment, which is corrected
in place.

**Every record pinned** (round 6, B2). A record that `PINNED` does not hold fails `pin_problems`
(`test_a_new_record_fails_until_it_is_pinned`). Round 5's review added a NEW CANONICAL record for the goal runtime
that named candidate side A (`greg.goal_gravity.tick`) as its owner and side B (`greg.gravity` select and step) as its
ALTERNATE, with no ruling and no test change, and every test passed (X1; X2, a new record for a rewritten loop under
unmarked names, and the skeptic's R4 are the same hole). Each now fails until `PINNED` changes in the same reviewed
diff. The second half of B2 was a rule that a module and qualname that is a decided record's canonical owner, or a
candidate of an undecided record, may appear in no other record in any role. Measured on today's tree it reports one
mention: `greg.autonomy.regress`, candidate side B of the undecided OWN-FN-AUTONOMY-LEVELS, is also a `distinct`
entry of OWN-FN-REGRESSION-CLOSING (and pinned there). As instructed, that rule was not weakened and not committed,
and no registry entry was changed to make it pass. So an EXISTING decided record can still take a new alternate (or
distinct entry) that names an undecided record's candidate, with no test change: a stated limit below.

**History guard** (`kept_for_problems`, section 76). A forward guard: every HISTORICAL or RETIRED alternate whose
module or qualname is still defined in the tree carries `kept_for`, exactly one of:

- `{consumer: <module>.<function>}`: a function whose source names the kept object, in a module that imports it from
  the alternate. It may not be under `greg/`, `tests/`, `docs/` or `scripts/ci/`, in any `conftest.py`, or in the
  alternate's own module;
- `{open_decision: <record_id>}`: the alternate's own record, while that record is still NEEDS_FOUNDER_DECISION.
  Another record's open decision keeps nothing.

An alternate gone from the tree needs none (`test_the_history_guard_refuses_a_kept_alternate_with_no_live_reason`,
`test_kept_for_names_the_alternates_own_open_record_and_a_consumer_outside_tests_and_tools`). Today the guard binds one
entry, `greg.mission_control` REALITY, whose `kept_for` is also pinned by `UNDECIDED_ENTRIES`. Its
reason said "read by nothing in the repository". In fact `acceptance/claims.py:80` imports it, and
`acceptance.claims.crosswalk_problems` reads REALITY to check that the crosswalk (`REALITY_CROSSWALK`) covers its
labels. The claim-label reader itself uses `REALITY_CROSSWALK`, not REALITY. So this consumer is a self-check of the
kept object outside `tests/`, a weak reason to keep it, and the record says so. A consumer is checked by what its
source names, not by whether anything calls it, so a dead two-line shim elsewhere that imports and returns the object
still passes. `test_kept_for_names_the_alternates_own_open_record_and_a_consumer_outside_tests_and_tools` records
that as passing.

**Parse warnings.** An invalid escape in a tracked script is a SyntaxWarning on 3.12+ and a DeprecationWarning on
3.11, CI's version. The parse every guard reads now hides both, so CI's summary carries no warnings from this file
(`test_a_file_with_an_invalid_escape_parses_without_a_warning_on_any_python`).

## Measured state on this tree

| Measure | Value |
|---|---|
| Registered qualnames (canonical, candidate, alternate) | 50: 30 functions, 9 classes, 11 constants |
| Registered bodies compared | 36, exactly the 36 `COMPARED` pins: 27 functions at or above 25 erased nodes and the 9 classes whole (48 to 8,431 erased nodes); 36 distinct fingerprints; 0 twins |
| Registered qualnames bound more than once at their level; star imports or computed namespace writes in their modules | 0; 0 (`binding_problems`) |
| Records in the registry; records `PINNED` does not hold | 8; 0 |
| Mentions the stated, uncommitted B2 cross-record rule would report | 1: `greg.autonomy.regress` (candidate of OWN-FN-AUTONOMY-LEVELS, distinct in OWN-FN-REGRESSION-CLOSING) |
| Qualname mentions whose resolution changed with round 4's last-binding rule | 0 of 89 (every canonical, candidate, alternate and distinct mention: 50 registered qualnames and 39 distinct ones, 88 unique; guards 1, 3 and 4 read the same nodes as before) |
| Entries pinned by `UNDECIDED_ENTRIES` | 24 (goal runtime 7, evidence ladder 13, autonomy levels 4) |
| `SEALED` files skipped; `SEALED` entries that seal nothing | 9; 0 |
| Module names shared by two runtime or `SEALED` files; a package beside a module of its name | 0; 0 |
| Guard 3's structural copies once `distinct` entries no longer exempt them | 0 |
| Registered functions below the threshold, not compared | `acceptance.rank` (8), `greg.improvement.attention_close_condition` (17), `greg.improvement.claim_close_condition` (7) |
| Methods of the 9 registered classes | compared only as part of their class's whole body (round 6), not one by one; see "Not done: class methods" |
| Runtime files; functions and methods at any depth; classes at any depth | 553 (46 under `cortex/evaluation/`, 9 sealed files skipped), the same files as before round 4's de-duplication; 7,902 (418 of a registered size, fingerprinted); 618 (23 of a registered size, fingerprinted) |
| `_erased_size` equal to the fingerprint's size | 7,902 of 7,902 functions; 618 of 618 classes |
| Copies at any location but their own (guard 4, functions and classes); exemptions | 0; `BODY_EXEMPTIONS` empty |
| Distinct entries naming a module with a copy | 0 |
| HISTORICAL or RETIRED alternates still in the tree; without a live `kept_for` | 1 (REALITY); 0 |
| False-positive check (round 4, functions only): this container's Python 3.13 stdlib and site-packages, the user site `/root/.local` (504 files) and `/usr/lib/python3/dist-packages` (1,182 files) | 16,293 files, 204,082 functions, 0 match a registered body (stdlib and site-packages alone: 14,607 files, 181,326 functions) |
| Guard 4, the twin check and the distinct check, cold, in one process | about 8 s on this container (4 cores, other agents' jobs running); 5.2 s in round 4 |
| Commits on the line (`claude/greg-full-machine-completion-whgiee`) since 2026-11-08 that change one of the 27 registered function bodies, by fingerprint diff over `git log --full-history` of their 13 files | 5 (one authored change, `d7c43ce5` to `greg.remote.handle`, and 4 merges that carried it); with git's default history simplification, 2 |
| Open heads committed since 2026-11-08, not merged into the line, that change one of the 27 bodies against their merge-base | 5 of 19 |

## Run time

`python -B -m pytest -q -p no:cacheprovider tests/unit/test_canonical_owner_guard.py`: **46 passed**, with no warnings
on either Python, in about 22-27 s on Python 3.13 and on 3.11 in round 6, on this container (4 cores, with other
agents' jobs running). Round 4 measured 15-18 s on a quieter container and round 5's verifier 21-23 s. Timings depend
on the machine and its load and are approximate.

## Commands and results

All in this container with `-B` and `-p no:cacheprovider`. The worktree sits inside another checkout, so the
directive tool's collection was run with `PYTEST_ADDOPTS=--rootdir=<worktree>`; without it pytest picks the outer
checkout as rootdir. The container's disk was full during round 4, so the mutant gate's own scratch copy
(`TMPDIR`) was put on `/dev/shm`; the export it ran on had no `.git`.

| Command | Python 3.13 | Python 3.11 |
|---|---|---|
| `pytest tests/unit/test_canonical_owner_guard.py` | **46 passed**, no warnings | **46 passed**, no warnings |
| `pytest tests/unit/test_canonical_owner_guard.py tests/unit/test_no_structural_duplicates.py tests/unit/test_repo_health_gates.py tests/unit/test_import_layering.py`, in the worktree (`test_no_structural_duplicates` lists files with `git ls-files`) | **74 passed** | **74 passed**; the 2 DeprecationWarnings come from `test_no_structural_duplicates.py`, which parses the same script and is not in this unit |
| `python scripts/ci/check_canonical_owner_guard_mutants.py`, in an export without `.git` | BASELINE_PASSES (46 passed), **157/157 caught**, 0 STALE, rc 0 | BASELINE_PASSES (46 passed), **157/157 caught**, 0 STALE, rc 0 |
| `python scripts/repo_review.py --check` | rc 0, 0 hard findings, 1,001 literal anchors checked | rc 0, the same |
| `python -m acceptance.claims` | PASS: 6,019 claims in 637 files, 0 crosswalk problems, 0 violations | PASS, the same |
| `python -B -m acceptance directive --collect --against e3a84f95` | rc 0: the pinned asks hold, every ask closed since cites new or changed evidence (none closed), all 195 cited nodes collect; 82/272 asks met, as before; S52.A1, S69.A3 and S76.A2 each `UNIT_VERIFIED of UNIT_VERIFIED (partial)`, BUILDABLE_NOT_BUILT MW-C | not run in round 6 (round 4: rc 2, because this venv lacks `cryptography`; none of the 114 nodes that collect nothing is a node of this unit) |

`repo_review --check` prints 17 advisories in round 6, two more than at `79ef5742` (round 6's `copy_class` edit of
`CommercialLoop`, read in `business/commercial_loop.py`, and its `copy_body` edit of `handle` in `greg/remote.py`), and five more at `79ef5742` than at `7c2b39e5` ("anchor occurs at 3 sites" in
`greg/business_loop.py` and `greg/remote.py`): its static reader takes the function name a round-4 `copy_body` edit
copies (`reconcile`, `handle`) for a text anchor. Advisories are not findings, and those edits read the function from
the AST, not by text.

The gate held 76 mutants (17 MW-C) before round 3, 115 (56 MW-C) after it, 139 (80 MW-C) after round 4 (24 new,
and 8 earlier ones re-anchored on lines round 4 rewrote: the two undecided-pin mutants, the two manifest-seal mutants
and the four that rewrite the runtime-file filter), and holds 157 (98 MW-C) after round 6: 18 new, one or more for
each new rule (B1: five tree edits and four code mutants; B2: one of each; B3: two tree edits and three code mutants;
B4: one of each), none removed, and one re-anchored ("async defs no longer scanned", on the line of `_functions` that
round 6 rewrote), each caught. The gate's `create` edit now makes a missing directory and removes it again, which
the B4 tree edit needs.

Each item of round 3 has a test that failed on the guard as it was and passes now, on both Pythons:

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


Round 4 (the review of `7c2b39e5`). Each fix has a test that fails on `7c2b39e5`'s guard and passes now, on 3.13 and
3.11 (logs and attack scripts in the session's scratch directory, not in the repository). "Attack" is the reviewer's
end-to-end tree, run as the whole guard file:

| Item | Test | Fails before | Passes after |
|---|---|---|---|
| N1 (blocking): a competing owner joins an undecided record through `distinct`, which switched off guard 3 for it | `test_an_undecided_record_takes_no_new_or_changed_entry_of_any_role_without_a_pin_change`; `test_guard_3_reports_a_structural_copy_even_where_a_distinct_entry_names_it` | yes: no problem for WU-13's `REALITY_LADDER` as a distinct entry; no structural copy reported under a distinct name. Attack: A1 and A2 each 34 passed | yes. Attack: A1 3 failed, A2 4 failed |
| N2: an undecided record's alternate changes status | the first test above (`GoalChase` to ALTERNATE, `REALITY` to ALTERNATE) | yes. Attack: B1 and B2b each 34 passed | yes. Attack: B1 and B2b each 4 failed |
| N3: a freeze manifest written in the same diff seals a copy | `test_a_freeze_manifest_seals_only_the_files_and_bytes_the_test_pins` | yes: both planted copies skipped. Attack: C 34 passed | yes. Attack: C 1 failed (guard 4) |
| N4: the first def of a qualname is fingerprinted, and nothing pins which bodies are compared | `test_a_registered_qualname_names_its_last_binding_as_python_does`; `test_the_set_of_compared_registered_bodies_is_pinned` | yes: an overload stub fingerprinted, the copy not reported; no rule pinned the set (NameError). Attack: H2 overload and H2 helper each 34 passed | yes. Attack: overload 1 failed, helper 2 failed (guard 4; the compared-set pin) |
| N5: a module file read where Python imports the package; a module name shared by two files | `test_a_package_shadows_a_module_of_the_same_name_and_no_two_files_share_a_module_name` | yes: no failure existed (NameError); the old guard returns [] for both trees (attack D, and a top-level `greg.business_loop.py`) | yes; attack D now raises `AmbiguousModule` |
| N6: a sibling directory link makes a registered body a false copy | `test_the_walk_reads_each_real_file_once_and_follows_file_links_anywhere` | yes: `examples/app/greg/business_loop.py:52` reported as a copy of `reconcile` | yes; attack E reports nothing for the sibling link |
| N7: file links are followed out of the repository, contrary to the README | the same test, now asserting the behaviour; the README corrected | the behaviour was already so; the README sentence was false | yes |
| N8: four real duplicates found while measuring method comparison | none (no runtime code changed); recorded under "Found evidence" below | - | - |

Round 6 (the items of round 5's review of `79ef5742`). Each fix has a test that fails on `79ef5742`'s guard (the
round-6 tests appended to that guard file) and passes now, on 3.13 and 3.11; "Attack" is the reviewers' end-to-end
tree, run as the whole guard file at `79ef5742` and now (scripts and logs in the session's scratch directory):

| Item | Test | Fails before | Passes after |
|---|---|---|---|
| B1: a dead-branch decoy, a `TYPE_CHECKING` decoy, a class rebinding or a star import hid a registered body | `test_every_registered_qualname_has_one_binding_and_its_module_no_computed_binding`; `test_a_decoy_rebinding_or_star_import_of_a_registered_qualname_fails` | yes (NameError: no rule existed). Attack, at `79ef5742`: `if False:` decoy plus a copy of `handle`, `except ImportError:` decoy, `TYPE_CHECKING` decoy plus a copy of `reconcile`, `GoalGravityLoop` rebound plus a verbatim copy, star-import accelerator: each 41 passed on 3.13 and 3.11 | yes. Attack now: each fails the one-binding test on both (the class rebinding also fails guard 4, the compared-set pin and the class test, 4 failed) |
| B2: a new record adopts an undecided record's candidate (X1, X2, R4) | `test_a_new_record_fails_until_it_is_pinned` | yes: `pin_problems` returned `[]`. Attack: 41 passed on both | yes. Attack: 4 failed on both (this test and the three that assert `pin_problems` is clean). The cross-record half was measured and stopped (above) |
| B3: a verbatim class copy in its record's own module, or recorded as a new alternate (R2a, R2b) | `test_a_registered_class_body_is_compared_whole_at_its_own_location_and_for_twins` | yes: no copy reported. Attack: R2a 41 passed, R2b 41 passed, on both | yes. Attack: R2a 1 failed (guard 4), R2b 5 failed (guard 4, the distinct check, the compared-set pin, the class test, and the one-binding test's count of 50 registered qualnames), on both |
| B4: a package beside a `SEALED` file | `test_a_package_beside_a_sealed_file_fails_the_module_name_rule` | yes: no problem reported. Attack: 41 passed on both | yes. Attack: 1 failed (guard 4's test) on both |
| B5: a wrapper of 25 nodes or more and an extracted helper (skeptic R1) | none: stated as the fork-pattern limit after measurement (above) | - | Attack, at `79ef5742` and now: 41 passed and 46 passed, on both (the limit, as stated) |
| B6: wording | none (documents only): the sentences the verifier marked are corrected in this README, the registry comments, the test's docstring and S52.A1, S69.A3 and S76.A2 | - | - |

## Compatibility with the line and with the open heads

WU-03 (#338) is now on the line, at `d776ca13`, and it added a real `greg/teams.py`. Two mutants from #253 create
`greg/teams.py`, so after that merge the gate reported both as STALE and exited 1, at 74/76. `c1679db0` re-pointed
both at `greg/team_forming.py`, keeping their intent: a re-implementation of temporary teams added, and F5, a second
canonical module added to temporary teams. Three earlier MW-C mutants anchored on lines this round rewrote are
re-anchored and still caught.

At `7c2b39e5` (round 3), both open heads that target the line were merged with this branch in a scratch tree
(`git merge-tree`) and checked the same way, with the guard file and the mutant gate run on Python 3.11, CI's version:

| Head | Merge | Every guard check (shape, pins, markers, existence, guards 2, 3 and 4, twins, distinct, history) | Mutant gate |
|---|---|---|---|
| PR #305 `6759a8c9` | clean | 0 problems; 27 bodies, 556 runtime files | BASELINE_PASSES (34 passed), **115/115 caught**, rc 0 |
| PR #314 `6608b774` | conflicts only in `.github/workflows/canonical-ci.yml` and `greg/authority.py`, as against the base; taken from #314 for the check; the registry merges automatically | 0 problems; 27 bodies, 555 runtime files | BASELINE_PASSES (34 passed), **115/115 caught**, rc 0 |

Round 4: both merges were rebuilt with this branch's round-4 head (the same conflicts, taken from #314), and the guard
file gives **41 passed** on each, on 3.13 and 3.11 (556 and 555 runtime files; 27 compared bodies). The distinct
entries #305 and #314 add belong to OWN-FN-ORGAN-EXCHANGE, a decided record, so `UNDECIDED_ENTRIES` does not bind
them, and guard 3 reports no structural copy behind them. The mutant gate was not re-run on the merges in round 4.
In round 6 the merges were not rebuilt.

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
  copy matches nothing registered, because the registered body is the edited one, so it passes. The same holds inside
  the owner's own module: move the owner's logic into a new helper (`_handle`) and leave the registered name as a
  wrapper of 25 erased nodes or more that does a little work and calls it (round 5's skeptic R1: a 43-node
  `greg.remote.handle` wrapper). The wrapper stays in `COMPARED`, the helper is unregistered, and a copy of the moved
  logic anywhere passes. Round 4's record claimed this extracted-helper case was caught; only a thin delegation that
  leaves the wrapper below 25 nodes is. The fix considered (round 6, B5) was to pin each `COMPARED` body's digest, so
  that every edit to a registered body becomes a reviewed test change. Measured first: 5 commits on the line since
  2026-11-08 changed one of the 27 registered function bodies by a full-history fingerprint diff (one authored change
  and 4 merges that carried it; 2 with git's default history simplification), and 5 of the 19 open heads committed in
  that window change one against their merge-base. Above the threshold of 3, a digest pin would put a test edit into
  each of those parallel PRs, so it was not adopted, and this stays a stated limit.
- **Registered functions and classes only.** A function the registry does not record has no owner check. Since round
  6 the 9 registered classes are compared whole by guard 4; their methods are not compared one by one (see below), so
  a copy of one method passes. Constants are compared by guard 3 only (exact structure, six packages, module level). The three registered functions below the 25-node threshold
  (`acceptance.rank`, `greg.improvement.attention_close_condition`, `greg.improvement.claim_close_condition`) have no
  copy check: a disguised copy of either `greg.improvement` function passes.
- **Small bodies have generic shapes.** A different function whose erased body equals a small registered one fails.
  The only way to clear one is a reviewed `BODY_EXEMPTIONS` entry; none is needed today.
- **The history guard binds what the registry records.** Obsolete code no record names is not found by any test; the
  S76.A2 excerpt covers it, so the ask stays partial. A consumer is checked by what its source names, so a dead shim
  outside the excluded places passes.
- **Pins are only as strong as review.** `PINNED`, `UNDECIDED_ENTRIES`, `SEALED`, `COMPARED`, `BODY_EXEMPTIONS`,
  `NOT_RUNTIME`, `SEALED_UNDER`, `NOT_CONSUMERS` and `MIN_COPY_NODES` are literals in the test; changing them changes
  the guard, visibly in the diff, and nothing but review stops a diff that changes the registry and the literal
  together.
- **What is scanned.** The filesystem, not git. An untracked `.py` file outside a top-level hidden entry is scanned
  too, and a tracked `.py` file under a top-level hidden directory (there is none today) is not. A copy reachable only
  through a DIRECTORY link out of the repository is not scanned; a FILE link is followed wherever it points. A copy
  in a non-`.py` file is never read.
- **Static resolution.** A qualname resolves to the last statement that binds it in source order, not by which branch
  runs. Since round 6 a registered qualname may have only one binding, so an `if X:` / `else:` pair, a dead-branch
  decoy, `@overload` stubs, a rebinding, a star import and a computed `globals()`, `vars()` or `locals()` write in its
  module fail instead of being read (`binding_problems`). Still not seen: a decorator on the one def or class that
  returns a different object (`@functools.lru_cache` and `@dataclass` are allowed); a rebinding the rule does not
  parse (`setattr` on the module or the class, `sys.modules[__name__].__dict__`, a literal `vars()` or `locals()` key,
  `exec`); and a different module object put in `sys.modules`. These are deliberate-evasion forms, outside the threat
  model. `AmbiguousModule` stops the guard with an exception naming the module (the test fails) rather than a list of
  every problem.
- **What the pins leave open.** `UNDECIDED_ENTRIES` pins an undecided record's entries, not its other fields
  (`decision_needed`, `safe_default`, `review_trigger`, `migration_path`, `effect`, which define the founder's question
  and the interim rule, change with no test failure): its `markers` are bounded below by `MUST_FLAG` (a marker can be
  widened freely and narrowed only down to those names) and its `generic_names` by `GENERIC_MIN`. A decided record is
  pinned by `PINNED` against removal only: it takes a new alternate or distinct entry with no test change, and a
  distinct entry there exempts a name from guard 3's name checks. Since round 6 a new record of either kind fails
  until it is in `PINNED` (and, if undecided, in `UNDECIDED_ENTRIES`). Not closed (B2's cross-record rule was stopped,
  above): an existing decided record can take a new alternate or distinct entry that names an undecided record's
  candidate, for example recording side B as an alternate of some decided record, with no test change. A ruling
  record written in the same diff clears a founder decision (`ruling_problems` cannot authenticate the founder; the
  2026-10-30 record states it).
- **Each real file once.** A file reachable by several paths is read at one of them (`_once`). Guard 2 resolves a
  relative import from the path it reads, so a link inside greg/ to another file under greg/ (read at its real path)
  is not also checked as the module the link path names, whose relative imports could resolve elsewhere; a link to a
  file outside greg/ is read at the link path, as Python imports it there. There are no links in the tree today.

- **Threat model.** Every limit above that needs exotic code or text (a decorator that swaps the object, a namespace
  write through `setattr` or `exec`, a self-issued ruling) is a limit against a deliberate evader, which these guards do
  not claim to stop (see "Reality level").

## The anchor question (S52.A1)

Section 52 asks for a record "for every major mechanism". The registry records the 8 functions found duplicated.
Which list counts as "every major mechanism" is not settled, and no build can show the registry complete until it
is. The candidates are the 18 completion-contract functions (`acceptance/completion-contract.json`), the Foundry's
numbered systems (`foundry/systems/__init__.py` `SYSTEMS`, numbered 1-55, 54 entries) and the 10 concern records of
`docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml`. That is a question for the integrator or the founder. MW-C
records it in S52.A1's reason and adds no evidence to S52.A1. It does not choose.

## What was not done

- **Not done: class methods one by one.** See "Found evidence" below: comparing them now would fail on four real
  duplicates already in the tree, and the decision on those is not the builder's. Since round 6 each registered class
  is compared whole, which none of the four duplicates affects (0 class copies on this tree).
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

## Found evidence: four real duplicates, and why method comparison stays off

Measured while trying to compare the methods of the 9 registered classes (round 3's review asked for it). With the
guard's own fingerprint, on this tree (`_function_node` and `fingerprint` in the test file), these are one body each:

| Location | Same erased body as | Size |
|---|---|---|
| `foundry/advantage.py:82` `OpportunitySpec.digest` | `omnimorph/engine.py:62` `OrganManifest.digest` | 35 nodes |
| `foundry/advantage.py:161` `AdvantageArchitecture.digest` | `omnimorph/engine.py:62` `OrganManifest.digest` | 35 nodes |
| `foundry/pipeline.py:359` `_outcome_hash` | `omnimorph/engine.py:62` `OrganManifest.digest` | 35 nodes |
| `egregore/goals.py:603` `GoalRegistry.tactic_forbidden` | `egregore/goals.py:606` `GoalRegistry.domain_muted` | 28 nodes |

`OrganManifest` is a registered RESEARCH alternate of OWN-FN-TEMPORARY-TEAMS (`omnimorph.engine`); `GoalRegistry` a
registered candidate of the undecided OWN-FN-GOAL-RUNTIME (`egregore.goals`). The first three are one
JSON-dump-and-sha256 helper written four times; the last pair is one preference lookup written twice under two
keys. Expanding the registered classes into their methods (99 method bodies of at least 25 nodes; 126 bodies, 125
fingerprints) makes guard 4 fail on the first three and the twin check on the pair, so the expansion is not committed
and no rule was weakened to pass. No runtime code was changed to make it pass either: that is outside this unit.

The decision someone must make before methods can be compared: fix them (one shared digest helper the four import;
one preference lookup with the key as a parameter), or record them (a `BODY_EXEMPTIONS` entry each, with the reason
it is a different function, or a registry entry naming the shared helper), or decide that the method threshold must be
higher than 25 nodes. That is the integrator's or the founder's call. Until it is made, the methods of registered
classes stay uncompared, a stated limit above.

## Reality level

UNIT-TESTED, in a container. The guards are unit tests over the source tree; no GREG runtime behaviour changed. The
effect is at review time, and limited by the stated limits above. Each sentence below names the tests that hold it.

Threat model. These guards are for ORDINARY changes by cooperating agents working in parallel: refactors, copies made
by mistake or for convenience, handoffs, relays, templates filled in for someone else, receipts copied between PRs.
They are not a security boundary against a deliberate evader who writes exotic code or text to defeat them. Each such
residual is stated as a limit above, and none is claimed as covered.

- A copy of one of the 36 registered bodies `COMPARED` pins (27 functions, and 9 classes compared whole), renamed,
  relocated, nested, made async, reformatted or changed by one of the three normalised one-node edits, fails anywhere
  but that body's own location, in every scanned file. Each real file is read once: at its real path when the scan
  lists it there, otherwise at one link path
  (`test_no_copy_of_a_registered_function_body_outside_its_record`,
  `test_the_body_guard_catches_renamed_nested_relocated_and_one_line_copies`,
  `test_the_body_guard_ignores_one_node_edits_pass_no_op_constants_annotations_and_import_aliases`,
  `test_a_registered_body_is_exempt_only_at_its_own_location`,
  `test_a_registered_class_body_is_compared_whole_at_its_own_location_and_for_twins`,
  `test_the_walk_reads_each_real_file_once_and_follows_file_links_anywhere`). The body read is the one Python binds,
  because each registered qualname has one binding and its module no star import or computed namespace write
  (`test_every_registered_qualname_has_one_binding_and_its_module_no_computed_binding`,
  `test_a_decoy_rebinding_or_star_import_of_a_registered_qualname_fails`). The scanned files leave out `tests/`,
  `docs/`, top-level hidden entries and the 9 `SEALED` instruments, which no diff can extend without changing the
  test (`test_a_freeze_manifest_seals_only_the_files_and_bytes_the_test_pins`), and which no package of the same module
  name can shadow (`test_a_package_beside_a_sealed_file_fails_the_module_name_rule`). Not covered: the three
  registered functions below the threshold, the methods of the 9 registered classes one by one, the fork pattern
  (a wrapper that keeps its place in `COMPARED` included), and every other stated limit above.
- A body leaves or joins the comparison only with a change to `COMPARED`
  (`test_the_set_of_compared_registered_bodies_is_pinned`); `COMPARED` pins locations, not contents.
- A record joins the registry only with a change to `PINNED` (`test_a_new_record_fails_until_it_is_pinned`).
- An undecided record cannot gain, lose or change any entry or field, of any role, without a change to
  `UNDECIDED_ENTRIES`, and a record cannot become undecided without being added to it
  (`test_an_undecided_record_takes_no_new_or_changed_entry_of_any_role_without_a_pin_change`).
- A historical or retired alternate the registry records stays in the tree only while code outside `greg/`,
  `tests/`, `docs/`, `scripts/ci/` and any `conftest.py` names it, or while its own record's founder decision is open
  (`test_every_historical_or_retired_alternate_still_in_the_tree_says_what_keeps_it`,
  `test_kept_for_names_the_alternates_own_open_record_and_a_consumer_outside_tests_and_tools`).
