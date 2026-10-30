# One canonical owner per important function: registry and guard (MU-H, 2026-10-30)

Directive 2026-10-28, section 52: "For every major mechanism identify: CANONICAL IMPLEMENTATION, ALTERNATIVES,
SHIMS, EXPERIMENTS, BENCHMARKS, HISTORICAL IMPLEMENTATIONS, MIGRATION PATH, RETIREMENT CONDITION. Do not allow
architectural generations to remain equally canonical forever." Section 3 forbids "a competing persistent goal
system"; section 76 says "Do not keep obsolete implementations merely to preserve history." Claim:
https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6526234097. Base `b1950be2` (#196 head).

## What changed

| File | Change |
|---|---|
| `docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml` | New section `function_owner_records` (8 records) after the existing concern records, which are unchanged |
| `tests/unit/test_canonical_owner_guard.py` | New: the registry's shape and the three guards, plus tests of the guards on synthetic trees |
| `scripts/ci/check_canonical_owner_guard_mutants.py` | New: 19 mutants, each naming the test that must fail |

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
concern records (`refines: [OWN-0008, ...]`, checked), and the test now makes the whole file machine-checked.

## The records

Owners were decided by what `greg/` and the CLI import and call at `b1950be2`. Where that does not settle it,
the record is `NEEDS_FOUNDER_DECISION`, with the evidence on each side.

| Record | Owner status | Owner or candidates | Other implementations (status) |
|---|---|---|---|
| OWN-FN-TEMPORARY-TEAMS | CANONICAL | `foundry/systems/teams.py` (#48), through `foundry.apply` in `greg/foundry_bridge.py` | `omnimorph/engine.py` (RESEARCH: imported by no greg module; OWN-SR-001 "not activated") |
| OWN-FN-COMMERCE-CLOSURE | CANONICAL | `greg/business_loop.py`, `greg/templates.py` `business_case`, `greg/path.py` `business_loop_closed` (N3's measure) | `greg/venture_rehearsal.py` (ALTERNATE: fixture, never moves N3); `business/commercial_loop.py` (ALTERNATE: phase-7 loop, reached only from `closure/`) |
| OWN-FN-GOAL-RUNTIME | NEEDS_FOUNDER_DECISION | A: `greg/goal_gravity.py` `tick` over `egregore/gravity.py` `GoalGravityLoop`; B: `greg/gravity.py` `select`, `step` | Both run on every `Body.tick`. The ledger and INTENT_CONFLICT_MATRIX row 19 list it as an open founder decision |
| OWN-FN-STATUS-EVIDENCE-LADDER | NEEDS_FOUNDER_DECISION | A: `foundry/completion.py` `EVIDENCE_TIERS`; B: `acceptance` `STATUSES` | `greg/mission_control.py` `REALITY` (HISTORICAL: nothing reads it). Same twelve names in A and B; neither is section 56's seventeen |
| OWN-FN-AUTONOMY-LEVELS | NEEDS_FOUNDER_DECISION | A: `autonomy/levels.py` (A0-A9; imported by no greg module) | Open proposal: #235's `greg/autonomy.py` (section 59's five levels, called from `Body.tick`) |
| OWN-FN-REGRESSION-CLOSING | CANONICAL | `greg/improvement.py` `_close_regressions`, `_reopen_regressions` | none; `greg/tribunal.py` opens regressions, `greg/goal_gravity.py` `_reopen` reopens goals (both recorded as distinct) |
| OWN-FN-ORGAN-EXCHANGE | CANONICAL | `greg/organs.py` (`organ.exchange`, the one-machine template's) | `greg/organ_exchange.py` (`organs.exchange`, ALTERNATE, per REPOSITORY_CONVERGENCE_MAP) |
| OWN-FN-INBOX-TRANSPORT | CANONICAL | `greg/body.py` `send_signed`, `greg/remote.py` `handle` | none |

Section 52's fields map to: `canonical` (canonical implementation); alternate `status` ALTERNATE (alternatives
and shims), RESEARCH (experiments), HISTORICAL, RETIRED; `migration_path`; `retirement_condition` for an ALTERNATE
and `revival_condition` for the rest. Benchmarks have no field of their own.

## The guards (`tests/unit/test_canonical_owner_guard.py`)

1. Every module and qualname the registry names exists. Read with `ast`; nothing is imported.
2. No module under `greg/` imports a HISTORICAL or RETIRED alternate. This covers `import`, `from ... import`,
   relative imports, `as` aliases, attribute access through an aliased module, function-level imports, star
   imports, `import_module`/`__import__` with a constant name, and a capability bound with
   `_lazy("<module>", "<function>")`. `greg/capabilities.py` wires about 30 capabilities that way.
3. A module-level definition in `greg/`, `foundry/`, `egregore/`, `omnimorph/`, `autonomy/` or `governance/`
   whose name matches a record's `markers` fails unless its module is that record's canonical, candidate or
   alternate module, or the name is listed as `distinct`. The message names the record and asks for an alternate
   or shim record. **This is a name heuristic.** It cannot catch:
   - a re-implementation under a name no marker matches;
   - a method inside a class;
   - code outside those six packages (`acceptance/`, `business/`, `closure/`, `scripts/`);
   - a second implementation added inside a module the record already lists.

The registry's shape is also checked:
- the six required functions are present;
- every alternate has a valid status and its condition;
- a NEEDS_FOUNDER_DECISION record has candidates with evidence and no owner;
- markers compile;
- `refines` points at a real concern record;
- at least one HISTORICAL or RETIRED alternate exists, so guard 2 is not vacuous.

## Commands and results

All runs are in this container: `/home/user/venv311/bin/python` (3.11), `PYTHONDONTWRITEBYTECODE=1 ... -B -m pytest -q -p no:cacheprovider`.

| Command | Result |
|---|---|
| Fail-before: new test file copied into a detached worktree of `b1950be2`, then `pytest tests/unit/test_canonical_owner_guard.py` | **6 failed, 2 passed** (no `function_owner_records`: `KeyError`). The 2 that pass test the scanners on synthetic trees and need no registry |
| Pass-after: `pytest tests/unit/test_canonical_owner_guard.py` at this branch | **8 passed** |
| `python -B scripts/ci/check_canonical_owner_guard_mutants.py` (the unmutated copy passes first) | **20/20 caught**, each by the test it names, exit 0. The mutants cover: <ul><li>2 records removed</li><li>1 alternate and 1 distinct entry removed</li><li>3 imports of the historical `REALITY`: direct in a function, through a module alias, relative under another name</li><li>2 alternates retired while greg still uses them: by import, and through `_lazy`</li><li>5 re-implementations: teams, an evidence ladder, a regression closer, an autonomy ladder in #235's shape, a goal loop</li><li>3 stale names: a renamed def, a mistyped module, a mistyped qualname</li><li>2 weakened records</li><li>1 vacuous import guard</li></ul> |
| Related: `python -B scripts/ci/check_authority_singleton.py` | exit 0, "exactly one source of authority for each governed artifact" |
| Related: `pytest tests/unit/test_developmental_inheritance.py tests/unit/test_greg_packaging.py tests/unit/test_autonomy.py tests/unit/test_omnimorph_v1.py` (the placement record, the owned-source inventory, and the two packages the registry names that have unit suites) | **97 passed** |
| Verification of the `_lazy` negative: guard 2 with and without the `_lazy` branch, the organ-exchange alternate set to RETIRED | 2 findings (`greg/capabilities.py:1001`, `:1007`) against 0 |

What the open program PRs meet when they land. This was simulated by copying their modules into a scratch tree
and running guard 3:
- **#235** `greg/autonomy.py` fails on `LEVELS`, `EARNED_CEILING` and `earned_level` (OWN-FN-AUTONOMY-LEVELS). It
  must add itself as a candidate or alternate in that record.
- **MU-B** `greg/readiness.py` (`RUNGS`, `ladder`) is not flagged. Its section 32 capability-readiness ladder is a
  different question from a claim's evidence level, but that is the heuristic's boundary, not a judgment the test
  makes.
- The program's other new modules also have migration notes in the records:
  - WU-03 `greg/teams.py` (OWN-FN-TEMPORARY-TEAMS);
  - WU-06 `nodes.py` (OWN-FN-INBOX-TRANSPORT);
  - WU-12 `greg/regressions.py` (OWN-FN-REGRESSION-CLOSING);
  - WU-13 `governance/reality_ladder.py` (OWN-FN-STATUS-EVIDENCE-LADDER).

## Limitations and negatives

- Three owners are not decided: goal runtime, evidence ladder and autonomy levels. That is the founder's
  decision; the safe default in each record is what runs today.
- Guard 2 cannot see a module whose name is computed at run time (`import_module(name)` with a variable). It
  follows `_lazy` only by that function name. Alias binding is per file, not per scope, so a name rebound to
  something else could be a false positive.
- Negative, found while building: the first version of guard 2 did not follow `_lazy`. Retiring the
  organ-exchange alternate passed even though `greg/capabilities.py` still binds `organs.exchange` to it. Fixed,
  with a synthetic case and a mutant.
- Guard 3 is the name heuristic described above.
- The registry is PROPOSED, like every record in the map. No record retires code.
- Nothing is wired into `.github/workflows/canonical-ci.yml`, which is outside this unit's scope. The guard test
  runs with the unit suite, but the mutant script is not in CI.

## Reality level

UNIT-TESTED, in a container. The guards are unit tests over the source tree. No GREG runtime behaviour changed and
no product capability was added. The effect is review-time: a second implementation of a registered function
cannot land without a record that names its status and its retirement or revival condition.
