"""Each safeguard of the canonical-owner registry (directive section 52) must fail its test when defeated.

The registry is ``function_owner_records`` in docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml; the guards are
tests/unit/test_canonical_owner_guard.py. A mutant here is a change a contributor could make: drop a record or an
alternate, import a historical alternate from greg/, add a re-implementation, rename what the registry names, or
weaken a record. Each names the test that must fail on it.

Every mutant runs in one scratch copy of the repository with ``python -B`` and PYTHONDONTWRITEBYTECODE=1, after every
``__pycache__`` in the copy is purged, and the copy is restored after each. The unmutated copy must pass first; a
mutant whose text no longer occurs exactly once, or whose new file already exists, is STALE.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TESTS = "tests/unit/test_canonical_owner_guard.py"
MAP = "docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml"
SHAPE = "test_registry_names_an_owner_status_alternates_and_conditions_for_every_required_function"
EXISTS = "test_every_registered_module_and_qualname_exists"
IMPORTS = "test_no_greg_module_imports_a_retired_or_historical_alternate"
DEFINES = "test_no_unrecorded_reimplementation_of_a_registered_function"
VACUOUS = "test_the_registry_has_at_least_one_alternate_the_import_guard_applies_to"
REHEARSAL = ("        status: ALTERNATE\n        reason: >-\n"
             "          a FIXTURE rehearsal of the Foundry company loop")
# (name, edits, test that must fail). An edit is ("replace", path, old, new), ("cut", path, start, end): remove from
# the unique ``start`` up to the next ``end``, ("append", path, text) or ("create", path, text).
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
     [("replace", MAP, "        status: ALTERNATE\n        reason: >-\n          the organs.exchange capability",
       "        status: RETIRED\n        revival_condition: none\n        reason: >-\n"
       "          the organs.exchange capability")], IMPORTS),
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
     [("replace", MAP, "    refines: [OWN-0008]\n    owner_status: NEEDS_FOUNDER_DECISION\n    canonical: []\n"
                       "    candidates:\n      - side: A\n        module: greg.goal_gravity\n",
       "    refines: [OWN-0008]\n    owner_status: CANONICAL\n    canonical: []\n"
       "    candidates:\n      - side: A\n        module: greg.goal_gravity\n")], SHAPE),
    ("an alternate left without its retirement condition",
     [("replace", MAP, "        retirement_condition: >-\n          a founder-tier business case closes",
       "        note: >-\n          a founder-tier business case closes")], SHAPE),
    ("the only historical alternate relabelled, leaving the import guard vacuous",
     [("replace", MAP, "        status: HISTORICAL\n", "        status: ALTERNATE\n        retirement_condition: none\n")],
     VACUOUS),
]


def _purge(repo: Path) -> None:
    for cache in repo.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def _run(repo: Path) -> subprocess.CompletedProcess:
    _purge(repo)
    return subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", TESTS],
                          cwd=repo, env={**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"},
                          capture_output=True, text=True, timeout=600)


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
            stop = text.find(end, at + len(start))
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
        baseline = _run(repo)
        if baseline.returncode != 0:
            print("BASELINE_FAILS")
            print(baseline.stdout[-3000:])
            return 1
        for name, edits, test in MUTANTS:
            applied = _apply(repo, edits)
            if applied is None:
                print("STALE", name)
                invalid += 1
                continue
            run = _run(repo)
            caught = (run.returncode == 1 and f"FAILED {TESTS}::{test}" in run.stdout
                      and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            if not caught:
                print(run.stdout[-2000:])
            invalid += not caught
            _restore(*applied)
    print(f"{len(MUTANTS) - invalid}/{len(MUTANTS)} caught")
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
