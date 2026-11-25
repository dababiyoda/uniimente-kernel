# Registered-body guard, exact pins and history guard (MW-C, 2026-11-21)

Unit MW-C of `acceptance/directive-sections.json` ("Canonical-owner guard: a function-to-canonical-module registry
whose test fails when a new module re-implements a registered function"). It bears on three asks of the 2026-10-28
directive. It answers S69.A3 ("reconcile architectural ownership; remove competing active ownership") and S76.A2 ("Do
not keep obsolete implementations merely to preserve history") in part. To S52.A1 ("For every major mechanism
identify: CANONICAL IMPLEMENTATION, ALTERNATIVES ... RETIREMENT CONDITION") it adds one evidence node,
`test_a_decided_records_canonical_qualnames_equal_the_pin` (round 7), and rewrites the ask's reason to name the three
anchors that are still unsettled (below); it does not choose among them. All three stay open (`partial`,
BUILDABLE_NOT_BUILT, unit MW-C).

Branch `claude/mw-c-owner-guard-20261121`, draft PR #341 into `claude/greg-full-machine-completion-whgiee`. The first
build was based on `121195907fff`. This record describes the branch after the line at `e3a84f95` was merged in
(`99d2a102`), after the review round that followed it, after the second review of `7c2b39e5` (round 4,
2026-11-22, findings N1-N8 below), after round 5's review of `79ef5742` (fixed in round 6, 2026-11-22, items B1-B6
below), after the line at `357b353d` was merged in (`19982b72`, no conflict) and after round 6's review of `16d35caa`
(fixed in round 7, 2026-11-22, items M1-M5 below) and after round 7's review of `ce7fc937` (fixed in round 8,
2026-11-22, items M6-M11 below). It builds on MU-H, recorded in
`docs/evidence/canonical-owner-guard-2026-10-30/README.md` (registry, guards 1-3, pins), which is not edited.

Claims discipline: every guarantee below names the test that enforces it; anything found without a test is stated as
a limit, and no list of limits is complete. Threat model: see "Reality level" at the end. These guards catch ordinary changes by cooperating agents, not a
deliberate evader.

## What changed

| File | Change |
|---|---|
| `tests/unit/test_canonical_owner_guard.py` | Guard 4 (copies of a registered function's body), the twin check, the distinct check, `BODY_EXEMPTIONS`, the history guard `kept_for_problems`, a filesystem walk shared by guards 2-4. Round 4: `UNDECIDED_ENTRIES` (an undecided record pinned whole, replacing the exact pin on its candidates and alternates), guard 3's structural-copy check no longer honouring `distinct`, `SEALED` (the skipped cortex/evaluation/ files by path and digest), `COMPARED` (the compared bodies), `binding` (last binding), `module_file` package-first with `AmbiguousModule`, `module_name_problems`, `_once` (each real file once). Round 6: `binding_problems` (one binding per registered qualname; no star import or computed namespace write in its module), every record pinned in `PINNED`, registered classes compared whole (`body_shape`; `COMPARED` 36), sealed files in the module-name rule. Round 7: a decided record's canonical qualnames pinned exactly; `attribute_rebinding_problems` (a registered qualname or a registered class's attribute written from outside its definition); a name bound to the module namespace in `binding_problems`; `imported_test_files` (the tests/ modules runtime code imports are scanned); the class test made independent of the live tree. Round 8: `_chains` (every written chain also read through `origin()`), `_globals_uses` (a literal `globals()` key anywhere is a binding; any other use of a `globals()` call in a registered module fails), and `__dict__`, `vars()`, `patch.object` and `patch("<dotted>")` writes in `_attribute_writes` and `_patch_targets`. 38 new tests since `e3a84f95` (54 in the file), 7 of them in round 4, 5 in round 6, 4 in round 7 and 4 in round 8 |
| `scripts/ci/check_canonical_owner_guard_mutants.py` | 121 MW-C mutants (180 in all): 24 new in round 4 and 8 re-anchored on rewritten lines; 18 new and 1 re-anchored in round 6; 10 new in round 7; 13 new in round 8; `copy_body`, `append_body`, (round 4) `seal` and (round 6) `copy_class` and `append_class` edits that write a disguised copy of a registered function, a freeze manifest for a file, or a verbatim copy of a registered class, at run time |
| `docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml` | `greg.mission_control` REALITY: stale reason corrected, `kept_for: {consumer: acceptance.claims.crosswalk_problems}`; the header comment of `function_owner_records` and the note after the last record rewritten on 2026-11-22 so that each rule names its test and the rest are stated as limits, and again in round 6 (the threat model, the ruling case, every pin's test, the new rules; "nine" corrected to 10) and round 7 (the note's rule count matches its six bullets; the new rules and limits), and round 8 (two bullets name the round-8 forms and tests; the limits say the list of rebinding forms not read is not complete and name what is open). No record or entry changed |
| `acceptance/directive-sections.json` | S52.A1: reason and note, in round 7 one evidence node, and in round 8 the reason names that node's test. S69.A3: evidence (7 more nodes in round 4, 5 more in round 6, 4 more in round 7, 4 more in round 8), reason and note. S76.A2: evidence, `owner_paths`, declared tier and coverage, reason and note. S76.A2's computed tier moved from INTENDED (gap) to UNIT_VERIFIED (partial) |

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
`test_a_decoy_rebinding_or_star_import_of_a_registered_qualname_fails`). Round 6's review showed that this read only
the registered module: an accelerator shim elsewhere (`import greg.business_loop as _bl; _bl.reconcile = _native`),
a method of a registered class swapped after its class statement (`GoalGravityLoop.execution_authority = _v2`) and
`_ns = globals(); _ns['reconcile'] = ...` each made Python run something the guards never read, with every test
passing. Since round 7 no runtime file may assign, augment, delete, or `setattr()` or `delattr()` with a literal name
a registered qualname as an attribute of a name bound to its module (by `import a.b as X`, `from a import b as X` or
the dotted `import a.b`), nor an attribute of a registered class outside its own class body when the written chain
opens with a name the file binds by import (or, in the class's own module, the class's own name), and a module that holds
a registered qualname may not bind a name to `globals()`, or to `vars()` or `locals()` at module level
(`attribute_rebinding_problems`, `binding_problems`;
`test_no_runtime_file_rebinds_a_registered_qualname_or_a_registered_class_attribute`,
`test_a_registered_qualname_rebound_from_another_module_or_through_a_namespace_alias_fails`). On today's tree the scan
reads 19 attribute writes through an imported name (the ordinary patches at `scripts/measure_body_memory.py:61`,
`scripts/node_cut_development.py:137`, `:169`, `:441` and `:470`, `cortex/evaluation/composition_lift/run_converged_v1.py:94-95`,
and `sys` and `importlib` patches in four cognition and cortex files), and none names a registered qualname. Round 7's review showed that rules (a) and (b) read only the raw import target: a timing shim on a registered class
reached through its package re-export (`from omnimorph import OmnimorphEngine; OmnimorphEngine.simulate = _timed`,
`from egregore import GoalGravityLoop; GoalGravityLoop.turn = _traced`), a write to a consumer's or a package's
imported name of a registered qualname (`import greg.cli as _cli; _cli.send_signed = f`,
`egregore.GoalGravityLoop = Quick`), a literal `globals()["reconcile"] = fast` inside an installer function, a
`globals()` handed to a helper or unpacked, and a write through another module's `__dict__` or `vars()` or by a `mock`
patcher each passed. Since round 8 the written chain is also read with every prefix resolved through the guard's own
`origin()` (`_chains`; `origin()` follows a name that a module binds at its level by `import` or `from ... import`,
up to four hops: package re-exports and a consumer's imported names), and these forms are read as writes:
`X.__dict__["<literal>"]` and `vars(X)["<literal>"]` set or deleted, `X.__dict__.update(...)` and
`vars(X).update(...)` with keyword arguments or a dict display with constant keys, `patch.object`, `mock.patch.object` or `unittest.mock.patch.object` with `X`
and a literal name, and `patch`, `mock.patch` or `unittest.mock.patch` with a literal dotted target, wherever the
call is (a decorator, a `with` item, a `.start()` receiver) (`_attribute_writes`, `_patch_targets`;
`test_a_registered_qualname_rebound_through_a_re_export_or_a_consumers_imported_name_fails`,
`test_a_registered_qualname_written_through_a_namespace_or_a_mock_patcher_fails`). In a module that holds a
registered qualname, a literal `globals()["X"]` write, `globals().update(X=...)` or `globals().setdefault("X", ...)`
anywhere (a def, a lambda, a class body, any target position) counts as a binding of X, and a `globals()` call used
in any other way fails: passed to a helper, unpacked, stored, a default argument, `globals().__setitem__`, `.get`, a
read (`_globals_uses`; `test_a_literal_globals_key_inside_a_function_binds_the_module_level_name`,
`test_globals_used_as_a_value_in_a_module_that_holds_a_registered_qualname_fails`). So the def or class the guards
read is the one Python binds for the forms these rules read. Python has other ways to rebind a name; "Static
resolution" below lists those the rules do not read, and that list is not complete. `@overload` stubs of a registered function are now a second binding and fail.
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
  Fixtures in `tests/` may copy a body on purpose. Since round 7 a `tests/` module that a scanned file imports,
  directly or through other such modules, and each package `__init__.py` on the way, is scanned all the same, because
  it runs (`imported_test_files`; `test_a_tests_module_that_runtime_code_imports_is_scanned_as_runtime`): four scripts
  import `tests.greg_fixtures` or `tests.unit.test_greg_oci`, which adds 3 files today. `docs/` stays unscanned,
  including its 24 `.py` files outside `lineage-archive/` (6 with a `__main__` guard), 5 of which import `tests/`;
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
| a registered function rebound as an attribute of its module from another file (`_bl.reconcile = _native`, `setattr(_b, 'send_signed', f)`, `del`), an attribute of a registered class set outside its body through an imported name (or the class's name in its own module), or `_ns = globals()` in a registered module | fails (round 7, `attribute_rebinding_problems`, `binding_problems`) |
| a copy in a `tests/` module that a script imports (`tests/greg_fixtures.py`) | caught (round 7, `imported_test_files`) |
| a method of a registered class swapped through its package re-export (`from omnimorph import OmnimorphEngine; OmnimorphEngine.simulate = f`, `import omnimorph; omnimorph.OmnimorphEngine.simulate = f`); a consumer's or a package's imported name of a registered qualname rebound (`_cli.send_signed = f`, `_gg.GoalGravityLoop = egregore.GoalGravityLoop = Quick`) | fails (round 8, M6, `attribute_rebinding_problems` through `_chains`) |
| a literal `globals()["reconcile"] = fast`, `globals().update(reconcile=fast)` or `.setdefault` inside a def, a lambda or a class body of the registered module | fails (round 8, M7, one binding) |
| `_install(globals(), f)`, `_ns, _ = globals(), None`, `def f(ns=globals())`, `globals().__setitem__(...)`, `globals().get(...)` or `globals()["x"]` read in a module that holds a registered qualname | fails (round 8, M8, `binding_problems`) |
| `_bl.__dict__["reconcile"] = f`, `del _bl.__dict__[...]`, `_bl.__dict__.update(reconcile=f)`, `vars(_bl)["reconcile"] = f`, `vars(_bl).update(...)`, `mock.patch.object(_bl, "reconcile", f)`, `patch("greg.business_loop.reconcile", f)` (decorator, `with` or `.start()`) | fails (round 8, M9, `attribute_rebinding_problems`) |
| `patch.dict(_bl.__dict__, {...})`, `patch.multiple`, an aliased `patch`, a computed name, a module or class reached by assignment or a parameter, a computed name, and the other forms "Static resolution" lists (that list is not complete) | not read (stated limits) |
| the owner's logic moved to a new helper behind a wrapper of 25 nodes or more, and a copy of the moved logic; a copy of one method of a registered class; a class copy with one method added, removed or reordered | missed (stated limits: the fork pattern; methods not compared one by one; a class is one whole body) |

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
diff. Since round 7 a decided record's canonical qualnames equal `PINNED` exactly, and a founder ruling makes canonical
only qualnames its module held as a candidate (`test_a_decided_records_canonical_qualnames_equal_the_pin`): round 6's
review added `EVIDENCE_STATUS`, candidate side C of the undecided evidence ladder, to the commerce record's canonical
`greg.path` qualnames, one word in the YAML, and every test passed. All 5 decided records equal `PINNED` today. The
second half of B2 was a rule that a module and qualname that is a decided record's canonical owner, or a
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
| Records in the registry; records `PINNED` does not hold; decided records whose canonical qualnames differ from `PINNED` | 8; 0; 0 of 5 |
| Attribute writes through an imported name in runtime files; of them, a registered qualname or a registered class's attribute; names bound to the namespace in a registered module | 19; 0; 0 (round 7) |
| Round 8: of those 19 writes, any whose chain resolved through `origin()` names a registered qualname or a registered class's attribute; `__dict__`, `vars()` or `patch.object` writes; `patch("<dotted>")` targets; in the modules that hold a registered qualname, literal `globals()` keys outside module-level statements and other uses of a `globals()` call | 0; 0; 0; 0 and 0. Across all 558 runtime files there is one other use of a `globals()` call, `foundry/systems/promotion.py:169` (`globals()[f'_stage_{s}']`, a read in a module the registry does not name) |
| Mentions the stated, uncommitted B2 cross-record rule would report | 1: `greg.autonomy.regress` (candidate of OWN-FN-AUTONOMY-LEVELS, distinct in OWN-FN-REGRESSION-CLOSING) |
| Qualname mentions whose resolution changed with round 4's last-binding rule | 0 of 89 (every canonical, candidate, alternate and distinct mention: 50 registered qualnames and 39 distinct ones, 88 unique; guards 1, 3 and 4 read the same nodes as before) |
| Entries pinned by `UNDECIDED_ENTRIES` | 24 (goal runtime 7, evidence ladder 13, autonomy levels 4) |
| `SEALED` files skipped; `SEALED` entries that seal nothing | 9; 0 |
| Module names shared by two runtime or `SEALED` files; a package beside a module of its name | 0; 0 |
| Guard 3's structural copies once `distinct` entries no longer exempt them | 0 |
| Registered functions below the threshold, not compared | `acceptance.rank` (8), `greg.improvement.attention_close_condition` (17), `greg.improvement.claim_close_condition` (7) |
| Methods of the 9 registered classes | compared only as part of their class's whole body (round 6), not one by one; see "Not done: class methods" |
| Runtime files; functions and methods at any depth; classes at any depth | 558 after the merge of `357b353d` and round 7 (555 walked, 46 under `cortex/evaluation/`, 9 sealed files skipped; plus 3 `tests/` files runtime code imports); 7,938 (419 of a registered size, fingerprinted); 619 (23 of a registered size, fingerprinted). Round 6 measured 553, 7,902 (418) and 618 (23) before the merge |
| `_erased_size` equal to the fingerprint's size | 7,902 of 7,902 functions; 618 of 618 classes (round 6; not re-measured) |
| Copies at any location but their own (guard 4, functions and classes); exemptions | 0; `BODY_EXEMPTIONS` empty |
| Distinct entries naming a module with a copy | 0 |
| HISTORICAL or RETIRED alternates still in the tree; without a live `kept_for` | 1 (REALITY); 0 |
| False-positive check (round 4, functions only): this container's Python 3.13 stdlib and site-packages, the user site `/root/.local` (504 files) and `/usr/lib/python3/dist-packages` (1,182 files) | 16,293 files, 204,082 functions, 0 match a registered body (stdlib and site-packages alone: 14,607 files, 181,326 functions) |
| Guard 4, the twin check and the distinct check, cold, in one process | about 8 s on this container (4 cores, other agents' jobs running); 5.2 s in round 4. Round 7's whole measurement (the scan above, guard 3 and the new rules) took 26.5 s cold |
| Commits on the line (`claude/greg-full-machine-completion-whgiee`) since 2026-11-08 that change one of the 27 registered function bodies, by fingerprint diff over `git log --full-history` of their 13 files | 5 (one authored change, `d7c43ce5` to `greg.remote.handle`, and 4 merges that carried it); with git's default history simplification, 2 (round 6's measure, up to `e3a84f95`) |
| Open heads committed since 2026-11-08, not merged into the line, that change one of the 27 bodies against their merge-base | 5 of 19 |

## Run time

`python -B -m pytest -q -p no:cacheprovider tests/unit/test_canonical_owner_guard.py`: **54 passed**, with no warnings
on either Python, in about 36-38 s on Python 3.13 and on 3.11 in round 8 (31-33 s for 50 tests in round 7, 22-27 s for
46 tests in round 6), on this container (4 cores, with other agents' jobs running). Round 7's rules add a parse of
every runtime file's imports and attribute writes; the parse itself is cached. Round 8's rules add an `origin()`
lookup per prefix of each attribute write through an imported name (19 today) and one more walk of each registered
module; `binding_problems` and `attribute_rebinding_problems` together took 10 s cold on today's tree. Round 4 measured 15-18 s on a quieter container and round 5's verifier 21-23 s. Timings depend
on the machine and its load and are approximate.

## Commands and results

All in this container with `-B` and `-p no:cacheprovider`. The worktree sits inside another checkout, so the
directive tool's collection was run with `PYTEST_ADDOPTS=--rootdir=<worktree>`; without it pytest picks the outer
checkout as rootdir. The container's disk was full during round 4, so the mutant gate's own scratch copy
(`TMPDIR`) was put on `/dev/shm`; the export it ran on had no `.git`.

| Command | Python 3.13 | Python 3.11 |
|---|---|---|
| `pytest tests/unit/test_canonical_owner_guard.py` | **54 passed**, no warnings | **54 passed**, no warnings |
| `pytest tests/unit/test_canonical_owner_guard.py tests/unit/test_no_structural_duplicates.py tests/unit/test_repo_health_gates.py tests/unit/test_import_layering.py`, in the worktree (`test_no_structural_duplicates` lists files with `git ls-files`) | **82 passed** | **82 passed**; the 2 DeprecationWarnings come from `test_no_structural_duplicates.py`, which parses the same script and is not in this unit |
| `python scripts/ci/check_canonical_owner_guard_mutants.py`, in an export without `.git` | BASELINE_PASSES (54 passed), **180/180 caught**, 0 STALE, 0 SURVIVED, rc 0 | BASELINE_PASSES (54 passed), **180/180 caught**, 0 STALE, 0 SURVIVED, rc 0; the CAUGHT lines are identical on the two Pythons |
| `python scripts/repo_review.py --check` | rc 0, 0 hard findings, 1,008 literal anchors in 40 gate scripts checked | rc 0, the same |
| `python -m acceptance.claims` | PASS: 6,021 claims in 641 files, 0 crosswalk problems, 0 violations | PASS, the same |
| `python -B -m acceptance directive --collect --against 357b353d` | rc 0: the pinned asks hold, every ask closed since cites new or changed evidence, all 208 cited nodes collect (204 and the 4 round-8 tests); 82/272 asks met; S52.A1, S69.A3 and S76.A2 each `UNIT_VERIFIED of UNIT_VERIFIED (partial)`, BUILDABLE_NOT_BUILT MW-C | not run (round 4: rc 2, because this venv lacks `cryptography`; none of the nodes that collect nothing is a node of this unit) |

`repo_review --check` prints 17 advisories in round 8, as in rounds 6 and 7 (the edits of rounds 7 and 8 add none), two more than at `79ef5742` (round 6's `copy_class` edit of
`CommercialLoop`, read in `business/commercial_loop.py`, and its `copy_body` edit of `handle` in `greg/remote.py`), and five more at `79ef5742` than at `7c2b39e5` ("anchor occurs at 3 sites" in
`greg/business_loop.py` and `greg/remote.py`): its static reader takes the function name a round-4 `copy_body` edit
copies (`reconcile`, `handle`) for a text anchor. Advisories are not findings, and those edits read the function from
the AST, not by text.

The gate held 76 mutants (17 MW-C) before round 3, 115 (56 MW-C) after it, 139 (80 MW-C) after round 4 (24 new,
and 8 earlier ones re-anchored on lines round 4 rewrote: the two undecided-pin mutants, the two manifest-seal mutants
and the four that rewrite the runtime-file filter), and holds 157 (98 MW-C) after round 6: 18 new, one or more for
each new rule (B1: five tree edits and four code mutants; B2: one of each; B3: two tree edits and three code mutants;
B4: one of each), none removed, and one re-anchored ("async defs no longer scanned", on the line of `_functions` that
round 6 rewrote), each caught. After round 7 it holds 167 (108 MW-C): 10 new (M1: one tree edit and one code mutant;
M2: three tree edits, the shim of E1/E2, the method swap of N2 and the namespace alias of E3, and three code mutants;
M3: one of each), none removed or re-anchored. After round 8 it holds 180 (121 MW-C): 13 new (M6: two tree edits and
one code mutant; M7: one of each; M8: one of each; M9: two tree edits and four code mutants), none removed or
re-anchored. The merge of the line brought `a82b0d38`, the same
`greg/teams.py` to `greg/team_forming.py` change this branch already had, so the gate file merged without a conflict. The gate's `create` edit now makes a missing directory and removes it again, which
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
round-6 tests appended to that guard file) and passes now, on 3.13 and 3.11. "Attack" is an end-to-end tree run as the
whole guard file at `79ef5742` and at `16d35caa`. The counts in this table come from the fixer's own re-creations of
the reviewers' attacks (round 6's `attacks.py`), not from the reviewers' scripts; where the two differ, both are given
(round 6's verifier and skeptic re-ran the reviewers' scripts; scripts and logs in the session's scratch directory):

| Item | Test | Fails before | Passes after |
|---|---|---|---|
| B1: a dead-branch decoy, a `TYPE_CHECKING` decoy, a class rebinding or a star import hid a registered body | `test_every_registered_qualname_has_one_binding_and_its_module_no_computed_binding`; `test_a_decoy_rebinding_or_star_import_of_a_registered_qualname_fails` | yes (NameError: no rule existed). Attack, at `79ef5742`: `if False:` decoy plus a copy of `handle`, `except ImportError:` decoy, `TYPE_CHECKING` decoy plus a copy of `reconcile`, `GoalGravityLoop` rebound plus a verbatim copy, star-import accelerator: each 41 passed on 3.13 and 3.11 | yes. Attack now: each fails the one-binding test on both (the class rebinding also fails guard 4, the compared-set pin and the class test, 4 failed) |
| B2: a new record adopts an undecided record's candidate (X1, X2, R4) | `test_a_new_record_fails_until_it_is_pinned` | yes: `pin_problems` returned `[]`. Attack: 41 passed on both | yes. Attack: 4 failed on both (this test and the three that assert `pin_problems` is clean). The cross-record half was measured and stopped (above) |
| B3: a verbatim class copy in its record's own module, or recorded as a new alternate (R2a, R2b) | `test_a_registered_class_body_is_compared_whole_at_its_own_location_and_for_twins` | yes: no copy reported. Attack: R2a 41 passed, R2b 41 passed, on both | yes. Attack: R2a 1 failed (guard 4) in the fixer's re-creation, whose copy was named `PullLoop`; 2 failed (guard 4 and the class test) with the reviewers' own script, whose copy is named `GravityLoop`, because the class test's fixture read the live `greg/gravity.py` (fixed in round 7, M5); R2b 5 failed (guard 4, the distinct check, the compared-set pin, the class test, and the one-binding test's count of 50 registered qualnames), on both |
| B4: a package beside a `SEALED` file | `test_a_package_beside_a_sealed_file_fails_the_module_name_rule` | yes: no problem reported. Attack: 41 passed on both | yes. Attack: 1 failed (guard 4's test) on both |
| B5: a wrapper of 25 nodes or more and an extracted helper (skeptic R1) | none: stated as the fork-pattern limit after measurement (above) | - | Attack, at `79ef5742` and now: 41 passed and 46 passed, on both (the limit, as stated) |
| B6: wording | none (documents only): the sentences the verifier marked are corrected in this README, the registry comments, the test's docstring and S52.A1, S69.A3 and S76.A2 | - | - |

Round 7 (the items of round 6's review of `16d35caa`, after the merge of the line at `357b353d`). Each fix has a test
that fails on the guard as it stood before the fix and passes now, on 3.13 and 3.11. "Attack" is the reviewers' own
round-6 script (the skeptic's `e2e_new.py` and `c1.py`, the verifier's `new6.py`), unchanged but for the tree path, run
as the whole guard file on an export of `16d35caa` and on an export of round 7's last code commit (`abdc7837`). Every
count below is identical on 3.13 and 3.11:

| Item | Test | Fails before | Passes after |
|---|---|---|---|
| M1: an existing decided record names an undecided record's candidate as canonical, one word in the YAML (skeptic C1) | `test_a_decided_records_canonical_qualnames_equal_the_pin` | yes: `pin_problems` returned no problem for the edit. Attack C1 at `16d35caa`: 46 passed | yes. Attack C1: 5 failed (the pins test, the three tests that assert `pin_problems` is clean, and this test) |
| M2 (a): a registered function rebound as an attribute of its module from another file (skeptic E1, verifier E2) | `test_no_runtime_file_rebinds_a_registered_qualname_or_a_registered_class_attribute`; `test_a_registered_qualname_rebound_from_another_module_or_through_a_namespace_alias_fails` | yes (NameError: no rule existed). Attack at `16d35caa`: E1 46 passed, E2 46 passed | yes. Attack: E1 1 failed, E2 1 failed (the tree test) |
| M2 (b): a method of a registered class swapped after its class statement (skeptic N2, a library-level check) | the same two tests | yes (NameError) | yes; covered by the synthetic test and a gate mutant that appends `GoalGravityLoop.execution_authority = ...` to `egregore/gravity.py` |
| M2 (c): `_ns = globals(); _ns['reconcile'] = ...` in the registered module (verifier E3) | the second test above; `test_every_registered_qualname_has_one_binding_and_its_module_no_computed_binding` on the tree | yes (NameError; `binding_problems` returned no problem). Attack E3 at `16d35caa`: 46 passed | yes. Attack E3: 1 failed (the one-binding test) |
| M3: a copy in a `tests/` module that a script imports (skeptic E2) | `test_a_tests_module_that_runtime_code_imports_is_scanned_as_runtime` | yes: the imported `tests/` modules were not listed. Attack E2 at `16d35caa`: 46 passed | yes. Attack E2: 1 failed (guard 4) |
| M4: wording | none (documents only): the YAML note's rule count matches its six bullets; the round-6 table names the tree each attack count comes from; Reality bullet 4; the fork-pattern basis; S69.A3's open list; the class limits; the guard-2 file-link case | - | - |
| M5: the class test's exact assertion depended on the live tree | `test_a_registered_class_body_is_compared_whole_at_its_own_location_and_for_twins` (rewritten fixture) | yes: with a verbatim copy of `GoalGravityLoop` appended to the live `greg/gravity.py` as `GravityLoop` (round 5's R2a), the guard file gave 2 failed (guard 4 and this test); as `PullLoop`, the fixture's own name, 1 failed, the fixture's copy hiding behind the live one | yes: 1 failed (guard 4 only) under either name |

Still passing at round 7, as stated limits: the verifier's E1 (a decided record takes greg.gravity select and step as
a new ALTERNATE: 50 passed; B2a's stopped cross-record rule), the skeptic's E3 (base-class extraction of
`CommercialLoop` plus a disguised copy of the base: 50 passed) and E4 (a verbatim `GoalGravityLoop` copy plus one
method, in `greg/evaluation/`: 50 passed). The verifier's E4 and E5 (whole-class copies nested in a function, and
with `@dataclass` and a base added) failed before and fail now (1 failed each).

Round 8 (the items of round 7's review of `ce7fc937`). Each fix has a test that fails on `ce7fc937`'s guard (the
round-8 tests appended to that guard file) and passes now, on 3.13 and 3.11. "Attack" is round 7's skeptic's
`e2e7.py` or verifier's `new7.py`, unchanged but for the tree path, run as the whole guard file on an export of
`ce7fc937` with this branch's guard file copied in; the counts before are round 7's own logs. Every count below is
identical on 3.13 and 3.11:

| Item | Test | Fails before | Passes after |
|---|---|---|---|
| M6 (blocking): a rebinding through a package re-export or a consumer's imported name (skeptic X5, X5b, X5c, X2b, X3b) | `test_a_registered_qualname_rebound_through_a_re_export_or_a_consumers_imported_name_fails` | yes: `attribute_rebinding_problems` returned `[]` for all 9 rebinding files. Attack at `ce7fc937`: X5, X5b, X2b, X3b 50 passed (X5c a library case) | yes. Attack: X5, X5b, X5c, X2b, X3b 1 failed each (the tree rebinding test); X2 and X3, the same shims in `greg/`, 2 failed (that test and guard 3) |
| M7: a literal `globals()` key inside an installer function (skeptic X1) | `test_a_literal_globals_key_inside_a_function_binds_the_module_level_name` | yes: no problem for any of the 10 variants. Attack X1 at `ce7fc937`: 50 passed | yes. Attack X1: 1 failed (the one-binding test), as its `global` control X1c |
| M8: `globals()` handed to a helper or unpacked (verifier F3, F4) | `test_globals_used_as_a_value_in_a_module_that_holds_a_registered_qualname_fails` | yes: no problem for the first variant. Attack F3, F4 at `ce7fc937`: 50 passed each | yes. Attack F3, F4: 1 failed each (the one-binding test) |
| M9: a write through another module's `__dict__` or `vars()`, or a `mock` patcher (skeptic X4, verifier F1, F2) | `test_a_registered_qualname_written_through_a_namespace_or_a_mock_patcher_fails` | yes: `[]` for all 13 rebinding files. Attack at `ce7fc937`: X4, F1, F2 50 passed each | yes. Attack X4, F1, F2: 1 failed each (the tree rebinding test) |
| M10: wording | none (documents only): "Static resolution", the guard docstring's item 1, the YAML note and S69.A3 say the list of rebinding forms the rules do not read is not complete and name what round 7 found and round 8 leaves open; the monkeypatch sentence; S52.A1 names the round-7 pin test; `docs/` holds 24 `.py` files outside `lineage-archive/`, 6 with a `__main__` guard (round 7's verifier counted 9; this record's count is by `grep __main__`) | - | - |
| M11: the round-7 and round-8 rules on the open heads | none: measured (below, "Compatibility") | - | - |

Each rule was measured on today's tree before it was committed, and reports nothing: M6 (round 7's `fix_origin.py`,
then the committed rule) 0; M7 (`fixes7.py`, `fixcost.py`) 0; M8 0 uses of a `globals()` call other than literal-key
writes in the modules that hold a registered qualname; M9 0 `__dict__`, `vars()` or `patch.object` writes and 0
`patch("<dotted>")` targets in runtime code. The gate gained 13 mutants: for M6 two tree edits (the X5 shim appended
to `foundry/pipeline.py`, the X2b shim in a new `greg/quick_drop.py`) and one code mutant; for M7 one tree edit (an
installer with a literal key appended to `greg/business_loop.py`) and one code mutant; for M8 one tree edit (a
`globals()` default argument there) and one code mutant; for M9 two tree edits (`greg/accel.py` writing through
`__dict__`, `greg/reconcile_patch.py` calling `mock.patch`) and four code mutants (one per form). Each is caught.

Every earlier attack was re-run at round 8 on both Pythons, with identical counts: round 5's scripts, round 6's
reviewers' scripts (`e2e_new.py`, `c1.py`, `lib6.py`, `new6.py`), and round 7's `e2e7.py`, `new7.py` and library
probes, against an export of `ce7fc937` with this branch's guard file copied in. Every attack that failed at round 7
still fails, and X1, X2b, X3b, X4, X5, X5b, X5c and F1-F4 now fail too (the table above). Still passing, each a
stated limit: round 6's skeptic E3 (base-class extraction) and E4 (a class copy plus one method), round 6's verifier
E1 (B2a's stopped cross-record rule), round 5's R1 (a wrapper of 25 nodes or more, the fork pattern) and round 5's
`alias_g2` (an import through a file link to a HISTORICAL module). The library probes that still pass are each in the
"Static resolution" list: a `__code__` swap; a class or module reached by assignment (`R = Relay`, `m = greg.body`)
or through a function parameter (`def install(cls=Relay)`); `object.__setattr__`; `builtins.setattr`; `setattr` with
a starred name; `importlib.import_module(...).x = f`; `getattr(...)` and `type(...)` as write targets; `globals`
through another name; `sys.modules[__name__]`, also with its `__dict__` bound to a name; and a literal `vars()` key at
module level.

Round 8's review, of `5bbd9a95` (2026-11-22). A verifier and a skeptic, run as separate subagents this session
launched and briefed (the same model; no other session or person has reviewed this branch), re-ran the attacks of
rounds 5, 6 and 7 on Python 3.13 and 3.11, ran the full mutant gate (180/180 on both) and re-measured 12 of the open heads, every one that conflicts among them.
They found no blocking gap. Their findings were sentences that described a rule by meaning or wrote a list of limits as
complete, ordinary forms called exotic, and rebinding forms that pass every test but that no list named yet (among
them a second import used as an accelerator, a computed-name timing helper, an in-place change to a registered
constant, `__globals__` and `f_globals` writes and a comprehension target). `3ac3e9d8` states them by form as open
limits under "Static resolution"; it changes text only, and its guard code is the same as `5bbd9a95`'s apart from
docstrings. On `3ac3e9d8` the mutant gate catches 180/180 on 3.13 (786 s) and on 3.11 (883 s).

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
In round 6 the merges were not rebuilt. In round 8 they were, for every open PR into the line in the board snapshot
(`prs_flat.json`: 45; this branch's #341 is not among them), at the head each PR had when fetched on 2026-11-22
(`git fetch origin refs/pull/N/head`; 18 heads had moved since the snapshot). For each, the tree
`git merge-tree --write-tree 357b353d <PR head>` writes was exported, this branch's guard file copied in, and every
problem function of the guard run on it (shape, pins, undecided pins, markers, existence, guards 2, 3 and 4, the
compared pin, twins, sealed files, distinct, kept_for, `binding_problems` and `attribute_rebinding_problems`, and the
pinned list of scanned `tests/` files), then the tree deleted, one at a time, on Python 3.13:

| Open heads | Merge into `357b353d` | Problems beyond the line's own |
|---|---|---|
| #206, #214, #218, #220, #226, #237, #240, #258, #260, #266, #267, #270, #280, #281, #282, #283, #288, #289, #303, #305, #313, #316, #317, #322, #324, #325, #327, #328, #330, #331, #332, #334, #335, #337, #338, #339 (36) | clean | none |
| #221, #299, #310, #311, #314, #323 (6) | conflicts; measured on the PR head's tree, as asked, and again on the merged tree with each conflicted path taken from the PR head | none, either way |
| #233, #243, #244 (3) | conflicts; the PR head's tree predates `function_owner_records`, so the guard stops on its first read of the registry (a `KeyError`); measured instead on the merged tree with each conflicted path taken from the PR head (`greg/computer.py` and its test; `greg/appraisal.py`; `greg/appraisal.py`, `greg/genesis.py`, `greg/missions.py`, `foundry/owned-source.json`, `scripts/ci/check_cortex_mutants.py`) | none |

"The line's own" are five problems the line head alone gives with this guard (`357b353d` plus the guard file): its
registry lacks this branch's `kept_for` on `greg.mission_control` REALITY, so the undecided pin (twice, once in
`pin_problems` and once in `undecided_problems`) and `kept_for_problems` report that entry. They go when this branch's
registry is merged. No round-7 or round-8 rule reports anything on any of the 45 merged trees: the canonical pin, the
rebinding rules (as written and resolved through `origin()`), the namespace and `mock` forms, the `globals()` rules and
the `tests/` scan. The trees hold 541 to 562 runtime files and 19 attribute writes through an imported name, 20 in
#316 and in #233's merged tree; none names a registered qualname. No rule was changed because of an open head. The
mutant gate was not run on the merges. Script and logs: the session's scratch directory (`round8/tools/heads.sh`,
`heads_problems.py`, `round8/mwc8/heads_conflict.sh`).

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
  that every edit to a registered body becomes a reviewed test change. Measured first, on the line since 2026-11-08:
  one authored change to a registered function body (`d7c43ce5`, `greg.remote.handle`), which a full-history
  fingerprint diff counts in 5 commits (the 4 merges that carried it) and git's default history simplification in 2;
  and 5 of the 19 open heads committed in that window (this branch and its backup among the 19) change one of the 27
  bodies against their merge-base. The basis for the choice is the open heads: a digest pin would put a test edit,
  and a merge conflict on the pin literal, into each of those 5 parallel PRs and every later edit of a registered
  body, which is the churn the guard is meant to spare cooperating agents. So it was not adopted, and this stays a
  stated limit. The class form of the fork pattern is base-class extraction: move every method but one of a
  registered class into a new base class (`_CommercialCore`) and keep the one in the registered class, which stays in
  `COMPARED` because it is still 25 erased nodes or more; a copy of the new base passes (round 6's skeptic E3).
- **Registered functions and classes only.** A function the registry does not record has no owner check. Since round
  6 the 9 registered classes are compared whole by guard 4; their methods are not compared one by one (see below), so
  a copy of one method passes. A class is one fingerprint, so any added, removed or reordered method makes a copy a
  different body: a copy of `GoalGravityLoop` with one 2-line method added passes (round 6's skeptic E4), and that
  copy-and-tweak is the usual shape of a convenience class copy. Guard 4 catches only verbatim, renamed or disguised
  whole-class copies. Constants are compared by guard 3 only (exact structure, six packages, module level). The three registered functions below the 25-node threshold
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
- **What is scanned.** `docs/` is not scanned, its 24 `.py` files outside `lineage-archive/` included (6 with a
  `__main__` guard; 5 `docs/evidence/` scripts import `tests/`), and a `tests/` module is scanned only when a scanned file imports it by an
  `import` statement: one imported by `importlib`, `__import__` or `exec`, or by a bare name after `sys.path` is changed
  to put a directory under `tests/` first, is not. The filesystem, not git. An untracked `.py` file outside a top-level hidden entry is scanned
  too, and a tracked `.py` file under a top-level hidden directory (there is none today) is not. A copy reachable only
  through a DIRECTORY link out of the repository is not scanned; a FILE link is followed wherever it points. A copy
  in a non-`.py` file is never read.
- **Static resolution.** A qualname resolves to the last statement that binds it in source order, not by which branch
  runs. Since round 6 a registered qualname may have only one binding, so an `if X:` / `else:` pair, a dead-branch
  decoy, `@overload` stubs, a rebinding, a star import and a computed `globals()`, `vars()` or `locals()` write in its
  module fail instead of being read (`binding_problems`). Since round 7 an assignment, augmented assignment, `del`, a
  for or with target, or `setattr()` or `delattr()` with a literal name, from any runtime file, that writes a
  registered qualname as an attribute of a name bound to its module, or an attribute of a registered class outside
  its class body through a name the file binds by import (or, in the class's own module, the class's own name), fails, and so does a name bound to the namespace in a registered module
  (`attribute_rebinding_problems`; round 6's E1, E2, E3 and N2). Since round 8 the written chain is also read with
  every prefix resolved through `origin()` (M6); `X.__dict__["<literal>"]` and `vars(X)["<literal>"]` set or
  deleted, `X.__dict__.update(...)` and `vars(X).update(...)` with keyword arguments or a dict display with constant
  keys, `patch.object`,
  `mock.patch.object` or `unittest.mock.patch.object` with `X` and a literal name, and `patch`, `mock.patch` or
  `unittest.mock.patch` with a literal dotted target are read as writes (M9); a literal `globals()["X"]` write,
  `globals().update(X=...)` or `globals().setdefault("X", ...)` anywhere in a registered module counts as a binding
  of X (M7); and any other use of a `globals()` call there fails (M8). Python has other ways to rebind a name; among
  those the rules do not read are: `setattr` or `delattr` with a computed name; `sys.modules`
  (`sys.modules[__name__].__dict__`, or a different module object put in `sys.modules`); `exec`;
  `importlib.import_module`, `__import__` and `runpy.run_path`; a module or class reached by assignment
  (`m = greg.body; m.send_signed = f`, `_R = Relay; _R.send = f`), a consumer's name bound by assignment included
  (`send = send_signed` in a consumer, then `_cli.send = f`); a module or class reached through a function parameter
  (`def install(cls=Relay): cls.send = f`); `getattr(greg, "body").x = f`; `type(obj).m = f`;
  `object.__setattr__` and `builtins.setattr`; a `__code__` swap; a decorator on the one def or class that returns a
  different object (`@functools.lru_cache` and `@dataclass` are allowed); a re-export through a star import
  (`from .engine import *`) or more than four hops, which `origin()` does not follow; the writer's own star import
  (`from omnimorph import *`, then `OmnimorphEngine.simulate = f`); a module rebinding its own imported name by a
  second import (`from greg.body import send_signed`, then `try: from vendor.fastsig import sign_and_drop as
  send_signed`: guard 3 reads the first import of a name, Python keeps the last), or by assignment
  (`send_signed = f`) outside the six packages guard 3 reads; a consumer whose imported name also has a fallback
  binding (`try: from omnimorph import OmnimorphEngine` / `except ImportError: OmnimorphEngine = None`), where
  `origin()` stops at the consumer; a consumer's dotted `import greg.body`, whose name `greg` `origin()` records as
  `greg.body` (`_cli.greg.body.send_signed = f`); a consumer's imported module replaced (`_gg.egregore = x`); an
  in-place change to a registered constant (`LEVELS[9] = ...`, `LEVELS.update(...)`); a comprehension target
  (`[None for _b.send_signed in [f]]`); `fn.__globals__[...]` and `sys._getframe().f_globals[...]`; a literal-key
  `.update` written another way (`vars(_b).update(dict(send_signed=f))`, `.update(**{...})`, `.update([(...)])`); a
  literal `vars()` or
  `locals()` key at module level, and `vars()` or `locals()` used as a value there (M8 reads `globals()` only);
  `globals` reached through another name (`g = globals; g()["X"] = f`); a `__dict__` or `vars(X)` reached through
  another name (`d = _b.__dict__; d["x"] = f`), its `.setdefault`, `.__setitem__` or `|=`, and a computed key; and
  `patch` under another name (`from unittest.mock import patch as p`, `import unittest.mock as um`), with a computed
  target or name, `patch.dict`, `patch.multiple`, pytest's `monkeypatch.setattr` and pytest-mock's `mocker.patch`
  and `mocker.patch.object`. The import scan does not tell
  scopes apart, so a name imported in one function counts in every function of the file (it fails closed). Many of
  the forms listed are exotic code, outside the threat model. These are ordinary and are open, stated here, not
  covered: `patch.dict`, `patch.multiple`, an aliased `patch`, `monkeypatch.setattr`, `mocker.patch`, a module or
  class reached by assignment or through a function parameter, `setattr` or `delattr` with a computed name (a timing
  or tracing helper that takes the object and the name, `def instrument(cls, *names): setattr(cls, name, ...)`), a
  consumer's name bound by assignment, a second import of a name as an optional accelerator, and a consumer's import
  with a fallback binding. The
  tree's own monkeypatches replace constants (`scripts/node_cut_development.py:137` and `:169`,
  `scripts/measure_body_memory.py:61`, `cortex/evaluation/composition_lift/run_converged_v1.py:94-95`), functions
  (`scripts/node_cut_development.py:441` and `:470` swap `greg.cognition.cortex._numeric` and `independent_verify`
  for timing wrappers) and a class method (`importlib.machinery.SourceFileLoader.get_data`, at
  `greg/cognition/evolution_room.py:41`, `greg/cognition/evolution_sandbox.py:51` and
  `cortex/evaluation/composition_lift/run_v6.py:100`); that plain form is read, and fails when it writes a registered
  qualname. `AmbiguousModule` stops the guard with an exception naming the module (the test fails) rather than a
  list of every problem.
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
  file outside greg/ is read at the link path, as Python imports it there. An import through a FILE link to a
  HISTORICAL module is not flagged by guard 2: with `greg/mission_view.py` linking to `greg/mission_control.py`,
  `from greg.mission_view import REALITY` in `greg/ladder.py` passes, because guard 2 matches the module name the
  import names (round 5's `alias_g2`, unchanged since). There are no links in the tree today.

- **Threat model.** Every limit above that needs exotic code or text (a decorator that swaps the object,
  `sys.modules` or `exec`, a self-issued ruling) is a limit against a deliberate evader, which these guards do not
  claim to stop (see "Reality level"). The ordinary forms "Static resolution" names are open against cooperating
  agents too, stated, not covered.

## The anchor question (S52.A1)

Section 52 asks for a record "for every major mechanism". The registry records the 8 functions found duplicated.
Which list counts as "every major mechanism" is not settled, and no build can show the registry complete until it
is. The candidates are the 18 completion-contract functions (`acceptance/completion-contract.json`), the Foundry's
numbered systems (`foundry/systems/__init__.py` `SYSTEMS`, numbered 1-55, 54 entries) and the 10 concern records of
`docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml`. That is a question for the integrator or the founder. MW-C
records it in S52.A1's reason. Its one S52.A1 evidence node (round 7) pins a decided record's canonical qualnames; it
does not choose the list.

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
residual found so far is stated as a limit above, and none is claimed as covered; the list of rebinding forms the rules
do not read ("Static resolution") is not complete.

- A copy of one of the 36 registered bodies `COMPARED` pins (27 functions, and 9 classes compared whole), renamed,
  relocated, nested, made async, reformatted or changed by one of the three normalised one-node edits, fails anywhere
  but that body's own location, in every scanned file. Each real file is read once: at its real path when the scan
  lists it there, otherwise at one link path
  (`test_no_copy_of_a_registered_function_body_outside_its_record`,
  `test_the_body_guard_catches_renamed_nested_relocated_and_one_line_copies`,
  `test_the_body_guard_ignores_one_node_edits_pass_no_op_constants_annotations_and_import_aliases`,
  `test_a_registered_body_is_exempt_only_at_its_own_location`,
  `test_a_registered_class_body_is_compared_whole_at_its_own_location_and_for_twins`,
  `test_the_walk_reads_each_real_file_once_and_follows_file_links_anywhere`). The body read is the one Python binds
  for the forms the rules read: each registered qualname has one binding (a literal `globals()` key anywhere in its
  module counted), its module no star import, computed namespace write, name bound to its namespace or other use of a
  `globals()` call, and no runtime file writes it, or an attribute of a registered class, from outside its definition
  through a name the file binds by import (or the class's own name in its module) by an assignment, augmented assignment, `del`, a for or with target, a literal `setattr` or `delattr`, a
  `__dict__["<literal>"]` or `vars(X)["<literal>"]` write or `.update` with keyword arguments or a constant-key dict
  display, `patch.object` with a
  literal name or `patch` with a literal dotted target (the names `patch`, `mock.patch` and `unittest.mock.patch`),
  read as written and with every prefix resolved through `origin()` (names a module binds by `import` or
  `from ... import`, up to four hops)
  (`test_every_registered_qualname_has_one_binding_and_its_module_no_computed_binding`,
  `test_a_decoy_rebinding_or_star_import_of_a_registered_qualname_fails`,
  `test_no_runtime_file_rebinds_a_registered_qualname_or_a_registered_class_attribute`,
  `test_a_registered_qualname_rebound_from_another_module_or_through_a_namespace_alias_fails`,
  `test_a_registered_qualname_rebound_through_a_re_export_or_a_consumers_imported_name_fails`,
  `test_a_literal_globals_key_inside_a_function_binds_the_module_level_name`,
  `test_globals_used_as_a_value_in_a_module_that_holds_a_registered_qualname_fails`,
  `test_a_registered_qualname_written_through_a_namespace_or_a_mock_patcher_fails`). Python has other ways to rebind
  a name; among those the rules do not read are a computed `setattr`, `sys.modules`, `exec`, `importlib`, `__import__`
  and `runpy.run_path`, a module or class reached by assignment, `getattr(...)` and `type(obj)` as a write target,
  `object.__setattr__`, a `__code__` swap, a decorator that returns a different object, a star-import re-export,
  `patch.dict` and an aliased `patch`; "Static resolution" lists the rest found so far, and neither list is complete. The scanned files leave out
  `docs/`, `tests/` except the modules a scanned file imports
  (`test_a_tests_module_that_runtime_code_imports_is_scanned_as_runtime`), top-level hidden entries and the 9 `SEALED` instruments, which no diff can extend without changing the
  test (`test_a_freeze_manifest_seals_only_the_files_and_bytes_the_test_pins`), and which no package of the same module
  name can shadow (`test_a_package_beside_a_sealed_file_fails_the_module_name_rule`). Not covered: the three
  registered functions below the threshold, the methods of the 9 registered classes one by one, the fork pattern
  (a wrapper that keeps its place in `COMPARED` included, and its class form, base-class extraction), a class copy with
  a method added, removed or reordered, and every other stated limit above.
- A body leaves or joins the comparison only with a change to `COMPARED`
  (`test_the_set_of_compared_registered_bodies_is_pinned`); `COMPARED` pins locations, not contents.
- A record joins the registry only with a change to `PINNED` (`test_a_new_record_fails_until_it_is_pinned`), and a
  decided record's canonical qualnames change only with one (`test_a_decided_records_canonical_qualnames_equal_the_pin`).
- An undecided record cannot gain, lose or change any entry, or any field of an entry, of any role, without a change to
  `UNDECIDED_ENTRIES`, and a record cannot become undecided without being added to it
  (`test_an_undecided_record_takes_no_new_or_changed_entry_of_any_role_without_a_pin_change`).
- A historical or retired alternate the registry records stays in the tree only while code outside `greg/`,
  `tests/`, `docs/`, `scripts/ci/` and any `conftest.py` names it, or while its own record's founder decision is open
  (`test_every_historical_or_retired_alternate_still_in_the_tree_says_what_keeps_it`,
  `test_kept_for_names_the_alternates_own_open_record_and_a_consumer_outside_tests_and_tools`).
