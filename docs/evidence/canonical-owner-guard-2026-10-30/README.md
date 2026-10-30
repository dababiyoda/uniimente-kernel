# One canonical owner per important function: registry and guard (MU-H, 2026-10-30)

Directive 2026-10-28, section 52: "For every major mechanism identify: CANONICAL IMPLEMENTATION, ALTERNATIVES,
SHIMS, EXPERIMENTS, BENCHMARKS, HISTORICAL IMPLEMENTATIONS, MIGRATION PATH, RETIREMENT CONDITION. Do not allow
architectural generations to remain equally canonical forever." Section 3 forbids "a competing persistent goal
system"; section 76 says "Do not keep obsolete implementations merely to preserve history." Claim:
https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6526234097. Base `b1950be2` (#196 head).
Round 1 ended at `77deac50`; round 2 fixes 15 review findings on it (below).

## What changed

| File | Change |
|---|---|
| `docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml` | New section `function_owner_records` (8 records) after the existing concern records, which are unchanged |
| `tests/unit/test_canonical_owner_guard.py` | New: the registry's shape, a frozen pin of the registry, the three guards, and tests of the guards on synthetic trees (15 tests) |
| `scripts/ci/check_canonical_owner_guard_mutants.py` | New: 53 mutants, each naming the test that must fail (20 from round 1, 33 replaying round-2 findings) |

No runtime file changed. No status in the registry attaches, activates, retires or grants anything.

### Why this file and not a new one

The scope named four places to extend first. None fits the function level:

- `scripts/ci/check_authority_singleton.py` counts authority artifacts by file glob. Its docstring says it "does NOT
  restrict multiple capability implementations". Putting capability owners there would mix authority with
  capability (Final Build Order section 3).
- `docs/collaboration/DEVELOPMENTAL-INHERITANCE-2026-09-30.json` places PRs and branches on path nodes. It has no
  per-function canonical or alternate.
- `greg/path.json` is read at runtime by `greg/path.py`, `greg/metrics.py`, `greg/planner.py` and others. Editing it
  could change runtime behaviour, which this unit may not do.
- `governance/` holds the live integrity tripwire over founder-signed digests. An owner map is not signed
  authority data.

`docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml` is the repository's existing owner record ("one canonical owner
per concern; two active owners is a defect"). It already has the same shape: `copied_implementations` carry a
`removal_trigger`, and `consumers` carry `compatibility_shim`. Nothing read it before. The new records refine its
concern records (`refines: [OWN-0008, ...]`). The test checks only `function_owner_records` and that each
`refines` ID names a concern record; the concern records' own fields are not machine-checked.

## The records

Owners were decided by what `greg/` and the CLI import and call at `b1950be2`. Where that does not settle it,
the record is `NEEDS_FOUNDER_DECISION`, with the evidence on each side.

| Record | Owner status | Owner or candidates | Other implementations (status) |
|---|---|---|---|
| OWN-FN-TEMPORARY-TEAMS | CANONICAL | `foundry/systems/teams.py` (#48), through `foundry.apply` in `greg/foundry_bridge.py` | `omnimorph/engine.py` (RESEARCH: imported by no greg module; OWN-SR-001 "not activated") |
| OWN-FN-COMMERCE-CLOSURE | CANONICAL | `greg/business_loop.py`, `greg/templates.py` `business_case`, `greg/path.py` `business_loop_closed` (N3's measure) | `greg/venture_rehearsal.py` (ALTERNATE: fixture, never moves N3); `business/commercial_loop.py` `CommercialLoop`, `STAGES` (ALTERNATE: the phase-7 runner; its observation vocabulary is recorded as distinct, because the Foundry imports it) |
| OWN-FN-GOAL-RUNTIME | NEEDS_FOUNDER_DECISION | A: `greg/goal_gravity.py` `tick` over `egregore/gravity.py` `GoalGravityLoop` and `egregore/goals.py` `GoalRegistry`; B: `greg/gravity.py` `select`, `step` | `egregore/goal_chase.py` `GoalChase` (RESEARCH: "sealed experiment/benchmark", GREG-BODY-DECISION-2026-09-25). Both A and B run on every `Body.tick`; the ledger and INTENT_CONFLICT_MATRIX row 19 list it as an open founder decision |
| OWN-FN-STATUS-EVIDENCE-LADDER | NEEDS_FOUNDER_DECISION | A: `foundry/completion.py` `EVIDENCE_TIERS`; B: `acceptance` `STATUSES`, `TEST_TIERS`; C: `greg/path.py` `EVIDENCE_STATUS` (every path node) | `greg/mission_control.py` `REALITY` (HISTORICAL: nothing reads it). A and B use the same twelve names; none is section 56's seventeen. Verifier strength and mechanism-lifecycle ladders are recorded as distinct |
| OWN-FN-AUTONOMY-LEVELS | NEEDS_FOUNDER_DECISION | A: `autonomy/levels.py` (A0-A9; imported by no greg module) | Open proposal: #235's `greg/autonomy.py` (section 59's five levels, called from `Body.tick`) |
| OWN-FN-REGRESSION-CLOSING | CANONICAL | `greg/improvement.py`: `learn` closes and reopens; `founder_revert`, called from `tribunal.critique`, reopens | none; `greg/tribunal.py` opens regressions, `greg/goal_gravity.py` `_reopen` reopens goals (both distinct) |
| OWN-FN-ORGAN-EXCHANGE | CANONICAL | `greg/organs.py` (`organ.exchange`, the one-machine template's) | `greg/organ_exchange.py` `exchange`, `status`, `verify_delivery` (ALTERNATE; appraisal re-renders its deliveries, so it stays importable while retained closures need that) |
| OWN-FN-INBOX-TRANSPORT | CANONICAL | `greg/body.py` `send_signed`, `greg/remote.py` `handle` | none |

Section 52's fields map to:
- `canonical`: the canonical implementation;
- alternate `status`: ALTERNATE (alternatives and shims), RESEARCH (experiments and sealed benchmarks),
  HISTORICAL or RETIRED;
- `migration_path` (required on every record);
- `retirement_condition` for an ALTERNATE and `revival_condition` for the rest.

Each NEEDS_FOUNDER_DECISION record also states `decision_needed`, `safe_default` and `review_trigger`. Benchmarks
have no field of their own.

## The guards (`tests/unit/test_canonical_owner_guard.py`)

1. **Every module and qualname the registry names exists.** Read with `ast`; nothing is imported.
2. **No module under `greg/` reaches a HISTORICAL or RETIRED alternate.** A resolver follows:
   - `import`, `from ... import` (relative ones too) and `as` aliases;
   - attribute chains through any of them, and names assigned from them (to a fixed point);
   - `getattr`, `vars()[...]`, `.__dict__[...]` and `sys.modules[...]` with a constant name. A computed name
     counts as any name in the module;
   - `importlib.import_module` and `__import__`, with `name=`/`package=`, relative names and `fromlist`. The module
     name can also come from a module-level string table, as with `DELIVERING` in `greg/appraisal.py`;
   - `_lazy("<module>", "<function>")` in `greg/capabilities.py`, keywords too.

   A dynamic import whose module name it cannot resolve fails its own test, unless `ALLOWED_DYNAMIC` gives the
   reason. Three are allowed: `_lazy`'s adapter (its call sites are followed), the genome library's `MODULES`
   tuple, and the evolution sandbox's `TARGETS` rows. A stale allowlist entry also fails.
3. **No unrecorded re-implementation in the six guarded packages** (`greg/`, `foundry/`, `egregore/`,
   `omnimorph/`, `autonomy/` and `governance/`). The check covers every module-level binding:
   - def, class and assignment;
   - a for, with, except or match target;
   - a walrus, an import alias, or a `globals()` key.

   A binding outside the record's modules and its `distinct` names fails when:
   - its name matches the record's markers;
   - it reuses the exact name of a registered implementation. A record's `generic_names` are exempt, and a name
     qualifies only if at least three other guarded modules define it: today `report` and `status`;
   - or it is a structural copy (the same AST without its name and docstring, at least 25 nodes) of a registered
     function or class, under any name.

   Importing the owner's name, directly or through a package re-export, is a use and does not fail.

**The registry is pinned in the test.** `PINNED` freezes every record, every `(module, qualname)` it names and
each record's canonical module set. `FOUNDER_DECISIONS` lists the three undecided records, and `MUST_FLAG` lists
the names each record's markers must catch, such as #235's `LEVELS`, `EARNED_CEILING` and `earned_level`. Each of
these fails:
- removing a record or an entry;
- adding a second canonical module;
- narrowing the markers below `MUST_FLAG`;
- resolving a founder decision without a `founder_ruling`. The ruling must be a file under `docs/decisions/` or
  `docs/intent/` that names the record and is accepted or active, and it may only promote a recorded candidate.

Adding a candidate, an alternate or a distinct entry needs no test change, so #235 can record itself.

## Review round 2 (two reviewers on `77deac50`): dispositions

All 15 findings reproduced with the reviewers' probes before any change. All are fixed.

| Finding | What was wrong | Fix |
|---|---|---|
| F1 | Guard 2 missed 10 dynamic-import forms (probe: 10 MISSED, 1 control CAUGHT), including greg's own `__import__(...).name` idiom | the resolver above (probe after: 11/11 CAUGHT) |
| F2 | `greg/appraisal.py:558` reaches `greg.organ_exchange.verify_delivery` through `DELIVERING[...]`, unseen | string tables resolved, so appraisal is now reported when the alternate is retired. Unresolvable dynamic imports fail unless allowlisted. Record evidence and retirement condition name appraisal |
| F3 | A copy of a registered function under its own name passed (`send_signed`, `exchange`, `form`/`act`/`dissolve`, `tick`/`select`) | exact-name rule and structural copy rule; all four scenarios and a renamed copy of `greg.organs.exchange` are now flagged |
| F4 | Vacuous markers passed the shape check | `MUST_FLAG` fixture in the test |
| F5 | A second CANONICAL module passed every guard | canonical module set pinned exactly |
| F6 | A full unilateral flip of a founder decision passed | `FOUNDER_DECISIONS` and the `founder_ruling` check |
| F7 | The `business.commercial_loop` reason said "imported by closure/commercial_registry.py only" | reason names the Foundry importers and the transitive load; its vocabulary is recorded as distinct; the retirement condition keeps it importable |
| F8 | for/while/match blocks, walrus, import aliases and `globals()` keys were invisible (probe: 6 MISSED) | all bindings covered (probe after: 7/7 CAUGHT, control included) |
| MUH-F1 | Removing two whole records or 17 single entries passed | `REQUIRED` covers all 8 records, and `PINNED` covers every entry. All 48 single-entry deletions now fail a guard |
| MUH-F2 | `egregore/goal_chase.py` `GoalChase` unrecorded | RESEARCH alternate of OWN-FN-GOAL-RUNTIME with a revival condition; markers cover `GoalChase` and `goal_chase`. `egregore/goals.py` added to side A; `greg/missions.py` and `egregore/local_mission.py` recorded as distinct |
| MUH-F3 | Four evidence vocabularies unrecorded | `greg.path` `EVIDENCE_STATUS` becomes candidate C, and `acceptance` `TEST_TIERS` joins side B. `evolution.capsule` `VERIFIER_LEVELS` and the mind coverage `STATUSES` are distinct, with whether section 56 absorbs them written into `decision_needed`; a new marker covers `EVIDENCE_STATUS` and `VERIFIER_LEVELS` |
| MUH-F4 | The regression evidence said `learn` was the only writer | evidence names `founder_revert` (from `tribunal.critique`); added to the canonical qualnames; the tribunal "why" corrected |
| MUH-F5 | Four records had no `migration_path`, and the undecided records had no `review_trigger` | `migration_path` required on every record, `review_trigger` on every undecided one; both added |
| MUH-F6 | The README said "19 mutants" and that the whole file was machine-checked | corrected above |

## Commands and results

All runs are in this container, with `/home/user/venv311/bin/python` (3.11) and
`PYTHONDONTWRITEBYTECODE=1 ... -B -m pytest -q -p no:cacheprovider`.

| Command | Result |
|---|---|
| Fail-before 1: the new test file copied into a detached worktree of `b1950be2` | **9 failed, 6 passed**. The 6 that pass need no registry: four synthetic-tree tests, the stale-name test, and the dynamic-import test, whose allowlist matches the base tree |
| Fail-before 2: the new test file in a detached worktree of `77deac50` (round 1's registry) | **4 failed, 11 passed**. Shape fails 7 problems (missing `migration_path`/`review_trigger`). Pins fail 24 (the round-1 registry lacks the entries round 2 adds). Markers fail 6 (`GoalChase`, `goal_chase`, `EVIDENCE_STATUS`, `VERIFIER_LEVELS`, `send_signed`, `send_signed_envelope`). Definitions fail 23 (exact-name hits that round 2 records as distinct or generic) |
| Fail-before 3: `77deac50`'s own guard module with only round 2's five new or changed synthetic tests appended | **5 failed**: four on assertions (`wired_kw`, `table`, `for_block`, the copy test), one `NameError` (`pin_problems` did not exist) |
| Pass-after: `pytest tests/unit/test_canonical_owner_guard.py` | **15 passed** (about 20 s) |
| `python -B -u scripts/ci/check_canonical_owner_guard_mutants.py` (the unmutated copy passes the whole file first; each mutant runs the test it names) | **53/53 caught**, exit 0, each by the test it names: 20 from round 1 (all still caught) and 33 replaying round 2's findings. By target test: 17 definitions, 11 pins, 9 imports, 7 shape, 3 existence, 3 markers, 2 dynamic imports, 1 vacuous guard. About 15 s per mutant |
| Reviewer probes re-run after the fix | guard 2: 11/11 caught (10 forms and a control); binding shapes: 7/7 caught; appraisal `:558` reported, for the whole-module and the qualname-restricted alternate alike |
| Each registry finding replayed through every guard (vacuous markers, second canonical, full flip, records and alternates removed, migration/review fields removed) | every scenario fails at least one guard; 48/48 single-entry deletions caught |
| Related: `python -B scripts/ci/check_authority_singleton.py` | exit 0, "exactly one source of authority for each governed artifact" |
| Related: `pytest tests/unit/test_developmental_inheritance.py tests/unit/test_greg_packaging.py tests/unit/test_autonomy.py tests/unit/test_omnimorph_v1.py` | **97 passed** |

What the open program PRs meet when they land. This was simulated by copying their modules into a scratch tree
and running every guard:
- **#235** `greg/autonomy.py` fails guard 3 on `LEVELS`, `EARNED_CEILING` and `earned_level`. It must add itself
  as a candidate in OWN-FN-AUTONOMY-LEVELS, which needs no test change. It adds no unresolved dynamic import.
- **MU-B** `greg/readiness.py` (`RUNGS`, `ladder`) is not flagged. That is the heuristic's boundary, not a judgment
  the test makes.
- The program's other new modules also have migration notes in the records:
  - WU-03 `greg/teams.py` (OWN-FN-TEMPORARY-TEAMS);
  - WU-06 `nodes.py` (OWN-FN-INBOX-TRANSPORT);
  - WU-12 `greg/regressions.py` (OWN-FN-REGRESSION-CLOSING);
  - WU-13 `governance/reality_ladder.py` (OWN-FN-STATUS-EVIDENCE-LADDER).

## Limitations and negatives

- **Three owners are not decided:** goal runtime, evidence ladder and autonomy levels. That is the founder's
  decision; the safe default in each record is what runs today.
- **The ruling check cannot authenticate the founder.** It checks that a ruling file exists, names the record and
  is accepted or active. An agent could write such a file, but that is then a visible, reviewable act rather than
  a silent YAML edit.
- **The pins are only as strong as review.** Changing `PINNED`, `MUST_FLAG` or `ALLOWED_DYNAMIC` changes the guard;
  the pins make that edit visible in the diff, not impossible.
- **Guard 2's limits:**
  - It binds names per file, not per scope, so a name rebound to something unrelated can cause a false positive.
  - It follows module names in constants and module-level string tables only.
  - It does not see `setattr` on a module, or a name reached through a function's return value.
- **Guard 3 is a heuristic.** It misses:
  - a rewritten re-implementation under a name that no marker matches and that is not a registered name;
  - a method inside a class;
  - code outside the six packages (`acceptance/`, `business/`, `closure/`, `scripts/`);
  - a second implementation inside a module the record already lists;
  - anything under a generic name (`report`, `status`) unless it is a structural copy;
  - a near copy, because the copy rule matches exact structure only.
- **Negative, found while building round 2:** the new checks found real cases on the tree. These were evolution
  sandbox dynamic imports (allowlisted with their reason), a package re-export of the OMNIMORPH engine in
  `foundry/pipeline.py` (fixed by following re-exports to their origin), and exact-name collisions such as
  `greg/mcp_tools.py` `act` and three `verify_delivery` (recorded as distinct, with reasons).
- **Nothing is retired.** The registry is PROPOSED, like every record in the map.
- **Not in CI.** Nothing is wired into `.github/workflows/canonical-ci.yml`, which is outside this unit's scope.
  The guard test runs with the unit suite; the mutant script is not in CI.

## Reality level

UNIT-TESTED, in a container. The guards are unit tests over the source tree. No GREG runtime behaviour changed and
no product capability was added. The effect is review-time: a second implementation of a registered function, or a
greg import of a retired or historical alternate, cannot land without a record that names its status and its
retirement or revival condition. A founder decision cannot be resolved without a ruling record that names it.
