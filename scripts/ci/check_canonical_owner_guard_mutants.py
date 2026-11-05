"""Each safeguard of the canonical-owner registry (directive section 52) must fail its test when defeated.

The registry is ``function_owner_records`` in docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml; the guards are
tests/unit/test_canonical_owner_guard.py. A mutant here is a change a contributor could make: drop a record, an
entry or a field, import a historical alternate from greg/, add a re-implementation or a copy, add a second owner,
resolve a founder decision alone, narrow the markers, rename what the registry names, or weaken a guard. Each names
the test that must fail on it. The mutants added after the 2026-10-30 review of 77deac50 name the finding they
replay (F1-F8, MUH-F1-MUH-F5); those added when #196 was merged in on 2026-11-04 are marked MERGE-196.

Every mutant runs in one scratch copy of the repository with ``python -B`` and PYTHONDONTWRITEBYTECODE=1, after every
``__pycache__`` in the copy is purged, and the copy is restored after each. The unmutated copy must pass the whole
test file first; each mutant then runs the test it names. A mutant whose text no longer occurs exactly once, or whose
new file already exists, is STALE.
"""
from pathlib import Path
import ast
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TESTS = "tests/unit/test_canonical_owner_guard.py"
MAP = "docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml"
SHAPE = "test_registry_names_an_owner_status_alternates_and_conditions_for_every_required_function"
PINS = "test_the_registry_keeps_every_pinned_record_entry_and_founder_decision"
MARKERS = "test_every_record_catches_the_names_it_must_and_exempts_only_common_names"
EXISTS = "test_every_registered_module_and_qualname_exists"
IMPORTS = "test_no_greg_module_imports_a_retired_or_historical_alternate"
DYNAMIC = "test_every_dynamic_import_in_greg_resolves_or_is_allowlisted"
DEFINES = "test_no_unrecorded_reimplementation_of_a_registered_function"
VACUOUS = "test_the_registry_has_at_least_one_alternate_the_import_guard_applies_to"
AUTONOMY_B = "test_the_adopted_autonomy_ladder_is_candidate_side_b_and_only_a_founder_ruling_promotes_it"
REHEARSAL = ("        status: ALTERNATE\n        reason: >-\n"
             "          a FIXTURE rehearsal of the Foundry company loop")
ORGAN_ALT = "        status: ALTERNATE\n        reason: >-\n          the organs.exchange capability"
RETIRED_ORGAN_ALT = ("        status: RETIRED\n        revival_condition: none\n        reason: >-\n"
                     "          the organs.exchange capability")
# The goal runtime made CANONICAL by an agent, side B owner and side A alternates, with no founder ruling (F6).
GOAL_UNDECIDED = ("    refines: [OWN-0008]\n    owner_status: NEEDS_FOUNDER_DECISION\n    canonical: []\n"
                  "    candidates:\n      - side: A\n        module: greg.goal_gravity\n")
GOAL_FLIPPED = ("    refines: [OWN-0008]\n    owner_status: CANONICAL\n    canonical:\n      - module: greg.gravity\n"
                "        qualnames: [select, step]\n    evidence: [\"flipped by an agent\"]\n{ruling}"
                "    candidates:\n      - side: A\n        module: greg.goal_gravity\n")
GOAL_ALTERNATES = "    alternates:\n      - module: egregore.goal_chase\n"
GOAL_FLIPPED_ALTERNATES = "    alternates:\n" + "".join(
    f"      - module: {m}\n        qualnames: [{q}]\n        status: ALTERNATE\n        reason: flipped\n"
    f"        retirement_condition: flipped\n" for m, q in (("greg.goal_gravity", "tick"),
                                                           ("egregore.gravity", "GoalGravityLoop"),
                                                           ("egregore.goals", "GoalRegistry, GoalSpec"))
) + "      - module: egregore.goal_chase\n"


def _flip(ruling: str = "") -> list:
    return [("replace", MAP, GOAL_UNDECIDED, GOAL_FLIPPED.format(ruling=ruling)),
            ("cut", MAP, "    candidates:\n      - side: A\n        module: greg.goal_gravity\n",
             "    review_trigger: >-\n      the founder's ruling on the canonical Goal Gravity runtime"),
            ("replace", MAP, GOAL_ALTERNATES, GOAL_FLIPPED_ALTERNATES)]


# (name, edits, test that must fail). An edit is ("replace", path, old, new), ("cut", path, start, end): remove from
# the unique ``start`` up to the next ``end`` (None: to the end of the file), ("append", path, text),
# ("create", path, text) or ("copy_def", path, name, new_name, new_path): a top-level def copied under a new name.
MUTANTS = [
    ("a registry entry removed: temporary teams",
     [("cut", MAP, "  - record_id: OWN-FN-TEMPORARY-TEAMS\n", "  - record_id: OWN-FN-COMMERCE-CLOSURE\n")], SHAPE),
    ("a registry entry removed: goal runtime",
     [("cut", MAP, "  - record_id: OWN-FN-GOAL-RUNTIME\n", "  - record_id: OWN-FN-STATUS-EVIDENCE-LADDER\n")], SHAPE),
    ("an alternate removed: the venture rehearsal",
     [("cut", MAP, "      - module: greg.venture_rehearsal\n", "      - module: business.commercial_loop\n")], DEFINES),
    ("a distinct entry removed: forecast quantile LEVELS",
     [("replace", MAP, '      - module: greg.cognition.genomes.forecasting\n        qualnames: [LEVELS]\n'
                       '        why: "forecast quantile levels"\n', "")], DEFINES),
    ("a historical alternate imported from greg/, inside a function",
     [("append", "greg/console.py", "\n\ndef _mutant_ladder():\n    from greg.mission_control import REALITY\n"
                                    "    return REALITY\n")], IMPORTS),
    ("a historical alternate reached through a module alias",
     [("append", "greg/briefs.py", "\nfrom greg import mission_control as _mc\n_MUTANT = _mc.REALITY\n")], IMPORTS),
    ("a historical alternate imported relatively under another name",
     [("append", "greg/metrics.py", "\nfrom .mission_control import REALITY as _LADDER\n")], IMPORTS),
    ("the venture rehearsal retired while greg still imports it",
     [("replace", MAP, REHEARSAL, REHEARSAL.replace("status: ALTERNATE", "status: RETIRED\n        revival_condition: "
                                                    "none"))], IMPORTS),
    ("the organ-exchange alternate retired while a capability still binds it with _lazy",
     [("replace", MAP, ORGAN_ALT, RETIRED_ORGAN_ALT)], IMPORTS),
    ("a re-implementation of temporary teams added (greg/teams.py)",
     [("create", "greg/teams.py", "class TeamError(RuntimeError):\n    pass\n\n\n"
                                  "def form_team(members, grant):\n    return {'members': members}\n")], DEFINES),
    ("a third evidence ladder added (governance/reality_ladder.py)",
     [("create", "governance/reality_ladder.py", "REALITY_LADDER = ('ASPIRATIONAL', 'PROPOSED', 'DOCUMENTED')\n")],
     DEFINES),
    ("a second regression closer added (greg/regressions.py)",
     [("create", "greg/regressions.py", "def close_regression(journal, regression_id):\n    return None\n")], DEFINES),
    ("a second autonomy ladder added in #235's shape",
     [("create", "greg/earned.py", "LEVELS = ('SHADOW', 'RECOMMENDER')\nEARNED_CEILING = 'RECOMMENDER'\n")], DEFINES),
    ("a second goal loop added (egregore/pursuit.py)",
     [("create", "egregore/pursuit.py", "class GoalRuntime:\n    pass\n")], DEFINES),
    ("a stale qualname: the canonical regression closer renamed",
     [("replace", "greg/improvement.py", "def _close_regressions(", "def _close_regressions_v2(")], EXISTS),
    ("a stale module: the team owner's path mistyped",
     [("replace", MAP, "      - module: foundry.systems.teams\n", "      - module: foundry.systems.team\n")], EXISTS),
    ("a stale qualname in the registry",
     [("replace", MAP, "qualnames: [_close_regressions, _reopen_regressions",
       "qualnames: [_close_regression, _reopen_regressions")], EXISTS),
    ("an undecided owner declared canonical without its evidence",
     [("replace", MAP, GOAL_UNDECIDED, GOAL_UNDECIDED.replace("NEEDS_FOUNDER_DECISION", "CANONICAL"))], SHAPE),
    ("an alternate left without its retirement condition",
     [("replace", MAP, "        retirement_condition: >-\n          a founder-tier business case closes",
       "        note: >-\n          a founder-tier business case closes")], SHAPE),
    ("the only historical alternate relabelled, leaving the import guard vacuous",
     [("replace", MAP, "        status: HISTORICAL\n", "        status: ALTERNATE\n        retirement_condition: none\n")],
     VACUOUS),
    # -- F1: constant-name dynamic imports and attribute chains on them ------------------------------------------
    ("F1: __import__(..., fromlist).REALITY in greg/console.py",
     [("append", "greg/console.py", "\n\ndef _probe_ladder():\n"
                                    "    return __import__('greg.mission_control', fromlist=['REALITY']).REALITY\n")],
     IMPORTS),
    ("F1: import_module bound to a name, then .REALITY (greg/briefs.py)",
     [("append", "greg/briefs.py", "\n\ndef _probe_ladder():\n    import importlib\n"
                                   "    m = importlib.import_module('greg.mission_control')\n    return m.REALITY\n")],
     IMPORTS),
    ("F1: getattr(module, 'REALITY') (greg/metrics.py)",
     [("append", "greg/metrics.py", "\nfrom greg import mission_control as _mc\n_X = getattr(_mc, 'REALITY')\n")],
     IMPORTS),
    # -- F2: a module name from a table, and a name guard 2 cannot resolve ---------------------------------------
    ("F2: the organ-exchange alternate retired while only appraisal's DELIVERING still reaches it",
     [("replace", MAP, ORGAN_ALT, RETIRED_ORGAN_ALT),
      ("replace", "greg/capabilities.py", '_lazy("greg.organ_exchange", "exchange")', '_lazy("greg.organs", "exchange")'),
      ("replace", "greg/capabilities.py", '_lazy("greg.organ_exchange", "status")', '_lazy("greg.organs", "status")')],
     IMPORTS),
    ("F2: an unresolvable dynamic import added to greg/console.py",
     [("append", "greg/console.py", "\n\ndef _probe_load(name):\n    import importlib\n"
                                    "    return importlib.import_module(name)\n")], DYNAMIC),
    ("F2: the evolution sandbox's allowlist entry removed from the guard",
     [("replace", TESTS, '    ("greg/cognition/evolution_sandbox.py", "main"):\n'
                         '        "imports the modules a TARGETS row names (greg.cognition.genomes modules and numpy), '
                         'unpacked from a tuple",\n', "")], DYNAMIC),
    # -- F3: a re-implementation under a registered name, or a renamed copy --------------------------------------
    ("F3: send_signed re-implemented under its own name (greg/nodes.py)",
     [("create", "greg/nodes.py", "def send_signed(home, key, kind, body):\n    return None\n")], DEFINES),
    ("F3: exchange re-implemented under its own name (greg/organ_relay.py)",
     [("create", "greg/organ_relay.py", "def exchange(params, ctx):\n    return {}\n")], DEFINES),
    ("F3: form, act and dissolve re-implemented (foundry/systems/crew.py)",
     [("create", "foundry/systems/crew.py", "def form(store, spec):\n    pass\n\n\ndef act(store, spec):\n    pass\n\n\n"
                                            "def dissolve(store, spec):\n    pass\n")], DEFINES),
    ("F3: tick and select re-implemented (egregore/pursuit_runtime.py)",
     [("create", "egregore/pursuit_runtime.py", "def tick(body):\n    pass\n\n\ndef select(missions):\n"
                                                "    return missions\n")], DEFINES),
    ("F3: a renamed verbatim copy of greg.organs.exchange (greg/organ_relay.py)",
     [("copy_def", "greg/organs.py", "exchange", "relay_exchange", "greg/organ_relay.py")], DEFINES),
    # -- F4: the markers narrowed or neutralized; a rare name exempted -------------------------------------------
    ("F4: the autonomy markers neutralized",
     [("cut", MAP, "      - '_?([A-Z][A-Za-z0-9]*)?Autonomy([A-Z][A-Za-z0-9]*)?'\n", "\n  - record_id: OWN-FN-REGRESSION"),
      ("replace", MAP, "\n  - record_id: OWN-FN-REGRESSION", "      - '(?!)'\n\n  - record_id: OWN-FN-REGRESSION")],
     MARKERS),
    ("F4: one autonomy marker dropped (_?LEVELS)",
     [("replace", MAP, "      - '_?LEVELS'\n", "")], MARKERS),
    ("F4: a rare registered name declared generic (send_signed)",
     [("replace", MAP, "    markers:\n      - '_?([a-z0-9]+_)*send_signed(_[a-z0-9]+)*'\n",
       "    generic_names: [send_signed]\n    markers:\n      - '_?([a-z0-9]+_)*send_signed(_[a-z0-9]+)*'\n")], MARKERS),
    # -- F5: a second canonical owner ------------------------------------------------------------------------------
    ("F5: a second canonical module added to temporary teams",
     [("replace", MAP, "        qualnames: [form, act, dissolve, report]\n",
       "        qualnames: [form, act, dissolve, report]\n      - module: greg.teams\n        qualnames: [form_team]\n"),
      ("create", "greg/teams.py", "def form_team(members, grant):\n    return {'members': members}\n")], PINS),
    # -- F6: a founder decision resolved by an agent ---------------------------------------------------------------
    ("F6: the goal runtime made canonical with no founder ruling", _flip(), PINS),
    ("F6: the same, citing a ruling file that does not exist",
     _flip("    founder_ruling: docs/decisions/ADR-GOAL-GRAVITY-RULING.md\n"), PINS),
    ("F6: the same, citing a proposed ADR that does not rule on the record",
     _flip("    founder_ruling: docs/decisions/ADR-GOAL-GRAVITY-002-greg-binding.md\n"), PINS),
    # -- MUH-F1: a record or an entry removed ------------------------------------------------------------------------
    ("MUH-F1: the inbox-transport record removed",
     [("cut", MAP, "  - record_id: OWN-FN-INBOX-TRANSPORT\n", None)], SHAPE),
    ("MUH-F1: the organ-exchange record removed",
     [("cut", MAP, "  - record_id: OWN-FN-ORGAN-EXCHANGE\n", "  - record_id: OWN-FN-INBOX-TRANSPORT\n")], PINS),
    ("MUH-F1: the greg.organ_exchange alternate removed",
     [("cut", MAP, "      - module: greg.organ_exchange\n", "    distinct:\n")], PINS),
    ("MUH-F1: the business.commercial_loop alternate removed",
     [("cut", MAP, "      - module: business.commercial_loop\n        qualnames: [CommercialLoop, STAGES]\n",
       "    distinct:\n")], PINS),
    ("MUH-F1: candidate B (acceptance) of the evidence ladder removed",
     [("cut", MAP, "      - side: B\n        module: acceptance\n", "      - side: C\n")], PINS),
    ("MUH-F1: the egregore.local_mission distinct entry removed",
     [("cut", MAP, "      - module: egregore.local_mission\n", "    migration_path: >-\n      the founder's ruling makes")],
     PINS),
    ("MUH-F1: a canonical qualname dropped (founder_revert)",
     [("replace", MAP, "_reopen_regressions, founder_revert, attention_close_condition",
       "_reopen_regressions, attention_close_condition")], PINS),
    # -- MUH-F2: GoalChase -------------------------------------------------------------------------------------------
    ("MUH-F2: the GoalChase alternate removed",
     [("cut", MAP, "      - module: egregore.goal_chase\n", "    distinct:\n")], PINS),
    ("MUH-F2: a second goal-chase engine added (egregore/chase_runtime.py)",
     [("create", "egregore/chase_runtime.py", "class GoalChaseRuntime:\n    pass\n")], DEFINES),
    # -- MUH-F5: migration path and review trigger -------------------------------------------------------------------
    ("MUH-F5: the organ-exchange migration_path removed",
     [("replace", MAP, "    migration_path: >-\n      the organ-exchange template signs organ.exchange;",
       "    note: >-\n      the organ-exchange template signs organ.exchange;")], SHAPE),
    ("MUH-F5: the autonomy review_trigger removed",
     [("replace", MAP, "    review_trigger: >-\n      the founder's ruling on section 59's five levels",
       "    note: >-\n      the founder's ruling on section 59's five levels")], SHAPE),
    # -- MERGE-196: entries for what #196 adopted after b1950be2 (#235 at 6fc4b22b, #236 at 2161dbe2) -------------
    ("MERGE-196: #235's ladder, candidate side B (greg.autonomy), removed from the record",
     [("cut", MAP, "      - side: B\n        module: greg.autonomy\n",
       "    decision_needed: >-\n      whether autonomy/levels.py")], DEFINES),
    ("MERGE-196: one side-B qualname dropped (regress)",
     [("replace", MAP, "qualnames: [LEVELS, EARNED_CEILING, earned_level, report, regress]",
       "qualnames: [LEVELS, EARNED_CEILING, earned_level, report]")], PINS),
    ("MERGE-196: side B made canonical by an agent, with no founder ruling",
     [("replace", MAP, "    owner_status: NEEDS_FOUNDER_DECISION\n    canonical: []\n    candidates:\n"
                       "      - side: A\n        module: autonomy.levels\n",
       "    owner_status: CANONICAL\n    canonical:\n      - module: greg.autonomy\n"
       "        qualnames: [LEVELS, EARNED_CEILING, earned_level, report, regress]\n"
       "    evidence: [\"flipped by an agent\"]\n    candidates:\n      - side: A\n        module: autonomy.levels\n")],
     PINS),
    ("MERGE-196: greg.autonomy unpinned, so a founder ruling could not promote it",
     [("replace", TESTS, ',\n                       "greg.autonomy": ("LEVELS", "EARNED_CEILING", "earned_level", "report", '
                         '"regress")},', "},")], AUTONOMY_B),
    ("MERGE-196: the greg.autonomy regress distinct entry removed (regression closing)",
     [("cut", MAP, "      - module: greg.autonomy\n        qualnames: [regress]\n",
       "      - module: foundry.systems.repair\n")], PINS),
    ("MERGE-196: #236's greg.path build-state distinct entry removed (evidence ladder)",
     [("cut", MAP, "      - module: greg.path\n        qualnames: [STRUCTURALLY_BUILT",
       "    migration_path: >-\n      the founder's ruling names the canonical tuple")], PINS),
    # -- F8: module-level bindings the definition scan did not see ---------------------------------------------------
    ("F8: a ladder bound by a module-level for loop (governance/reality_loop.py)",
     [("create", "governance/reality_loop.py", "for REALITY_LADDER in [('ASPIRATIONAL', 'PROPOSED')]:\n    pass\n")],
     DEFINES),
    ("F8: an autonomy ladder bound through globals() (greg/earned_globals.py)",
     [("create", "greg/earned_globals.py", "globals()['EARNED_CEILING'] = 'RECOMMENDER'\n")], DEFINES),
    ("F8: a ladder bound by a walrus in a module-level if (greg/earned_walrus.py)",
     [("create", "greg/earned_walrus.py", "if (LEVELS := ('SHADOW', 'RECOMMENDER')):\n    pass\n")], DEFINES),
    ("F8: a ladder imported under a marked alias (greg/earned_alias.py)",
     [("create", "greg/earned_alias.py", "from json import loads as EARNED_CEILING\n")], DEFINES),
]


def _purge(repo: Path) -> None:
    for cache in repo.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def _run(repo: Path, target: str) -> subprocess.CompletedProcess:
    _purge(repo)
    return subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", target],
                          cwd=repo, env={**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"},
                          capture_output=True, text=True, timeout=900)


def _apply(repo: Path, edits) -> tuple[dict, list[Path]] | None:
    """Apply every edit; None (nothing changed) when any edit is stale."""
    originals, created = {}, []
    for kind, relative, *args in edits:
        path = repo / relative
        if kind == "create":
            if path.exists():
                return _restore(originals, created)
            created.append(path)
            path.write_text(args[0])
            continue
        if kind == "copy_def":
            name, new_name, new_relative = args
            target = repo / new_relative
            text = path.read_text()
            node = next((n for n in ast.parse(text).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                         and n.name == name), None)
            if node is None or target.exists():
                return _restore(originals, created)
            created.append(target)
            target.write_text(ast.get_source_segment(text, node).replace(f"def {name}(", f"def {new_name}(", 1) + "\n")
            continue
        if path not in originals:
            originals[path] = path.read_text()
        text = path.read_text()
        if kind == "append":
            path.write_text(text + args[0])
        elif kind == "replace":
            old, new = args
            if text.count(old) != 1:
                return _restore(originals, created)
            path.write_text(text.replace(old, new))
        elif kind == "cut":
            start, end = args
            if text.count(start) != 1:
                return _restore(originals, created)
            at = text.index(start)
            stop = len(text) if end is None else text.find(end, at + len(start))
            if stop < 0:
                return _restore(originals, created)
            path.write_text(text[:at] + text[stop:])
        else:
            raise ValueError(kind)
    return originals, created


def _restore(originals: dict, created: list[Path]) -> None:
    for path, text in originals.items():
        path.write_text(text)
    for path in created:
        path.unlink(missing_ok=True)
    return None


def main() -> int:
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="canonical-owner-guard-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        baseline = _run(repo, TESTS)
        if baseline.returncode != 0:
            print("BASELINE_FAILS")
            print(baseline.stdout[-3000:])
            return 1
        print("BASELINE_PASSES", baseline.stdout.strip().splitlines()[-1], flush=True)
        for name, edits, test in MUTANTS:
            applied = _apply(repo, edits)
            if applied is None:
                print("STALE", name, flush=True)
                invalid += 1
                continue
            run = _run(repo, f"{TESTS}::{test}")
            caught = (run.returncode == 1 and f"FAILED {TESTS}::{test}" in run.stdout
                      and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name, flush=True)
            if not caught:
                print(run.stdout[-2000:])
            invalid += not caught
            _restore(*applied)
    print(f"{len(MUTANTS) - invalid}/{len(MUTANTS)} caught")
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
