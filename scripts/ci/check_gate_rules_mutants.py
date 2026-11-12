"""Each rule a mutation gate is trusted for must fail a unit test when removed (directive section 69, S69.A6).

    python scripts/ci/check_gate_rules_mutants.py

Three groups, each run by the shared runner in a scratch copy of the repository, never in the working tree:

* what the shared runner counts as caught (scripts/ci/mutation_harness.py, tests/unit/test_mutation_harness.py):
  pytest exits 1, reports a FAILED test in the named file and reports no collection error; an anchor that does not
  occur exactly once is STALE; a stale or surviving mutant fails the gate;
* gate liveness (scripts/repo_review.py, tests/unit/test_repo_health_gates.py): a gate no workflow names reads as
  unwired, and an anchor that left its target reads as stale;
* the pin on KEPT_UNWIRED_GATES. The copy first receives a gate no workflow names, so the liveness test fails there
  until the mutant adds that gate to the kept list. With the mutant applied the only failing test is the pin, which
  is what this group shows: growing the list in the same change as a new unwired gate is refused.

Before any mutant, both test files must pass unmutated. The shared runner now checks that itself (BASELINE_FAILS);
this gate keeps its own check as well, because one of its mutants removes the runner's. A mutant is caught only by a
FAILED test. Exit status 1 if the baseline fails or any mutant survives or no longer applies.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
RUNNER = "scripts/ci/mutation_harness.py"
REVIEW = "scripts/repo_review.py"
RUNNER_TESTS = "tests/unit/test_mutation_harness.py"
LIVENESS_TESTS = "tests/unit/test_repo_health_gates.py"
PLANTED = "check_planted_mutants.py"
UNWIRED_TEST = "test_unwired_gates_match_the_shrink_only_list"   # what the planted gate makes fail, unmutated
CAUGHT_RULE = ('caught = (result.returncode == 1 and f"FAILED {tests}::" in result.stdout\n'
               '                      and "ERROR collecting" not in result.stdout)')
RUNNER_MUTANTS = [
    (RUNNER, "any non-zero pytest exit counts as caught", CAUGHT_RULE, "caught = result.returncode != 0"),
    (RUNNER, "a failed test in a run that did not finish counts as caught",
     'result.returncode == 1 and f"FAILED', 'f"FAILED'),
    (RUNNER, "an error that is not a FAILED test counts as caught", ' and f"FAILED {tests}::" in result.stdout', ""),
    (RUNNER, "the word FAILED anywhere in the output counts as caught",
     'f"FAILED {tests}::" in result.stdout', '"FAILED " in result.stdout'),
    (RUNNER, "a failed test beside a collection error counts as caught",
     '\n                      and "ERROR collecting" not in result.stdout)', ")"),
    (RUNNER, "an anchor at several sites is applied", "if original.count(old) != 1:", "if original.count(old) == 0:"),
    (RUNNER, "a stale mutant does not fail the gate", 'print("STALE", name)\n                invalid += 1',
     'print("STALE", name)'),
    (RUNNER, "a surviving mutant does not fail the gate", "invalid += not caught", "invalid += 0"),
    (RUNNER, "a named test that already fails counts as a catch for every mutant",
     "if (baseline.returncode != 0) if planted is None else", "if False if planted is None else"),
    (RUNNER, "on a planted tree the planted failure itself counts as a catch",
     "caught = caught and planted not in result.stdout", "pass"),
]
LIVENESS_MUTANTS = [
    (REVIEW, "every gate reads as wired", '"wired": gate.name in workflows,', '"wired": True,'),
    (REVIEW, "an anchor that left its target is not reported",
     'for t, a, c in counts if c == 0],', 'for t, a, c in counts if False],'),
]
GROWTH_MUTANTS = [
    (REVIEW, "a new unwired gate joins the kept list in the same change",
     "KEPT_UNWIRED_GATES = {\n", f'KEPT_UNWIRED_GATES = {{\n    "{PLANTED}": "planted",\n'),
]


def baseline() -> int:
    """Both test files pass on the unmutated tree, read in place (pytest writes nothing: no bytecode, no cache)."""
    clean = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", RUNNER_TESTS,
                            LIVENESS_TESTS], cwd=ROOT, capture_output=True, text=True, timeout=900)
    print("UNMUTATED", "PASS" if clean.returncode == 0 else "FAIL", flush=True)
    if clean.returncode:
        print(clean.stdout[-2000:], flush=True)
    return int(clean.returncode != 0)


def main() -> int:
    if baseline():
        return 1
    status = run(RUNNER_MUTANTS, RUNNER_TESTS, prefix="gate-rules-runner-", root=ROOT, purge_dirs=("scripts", "tests"))
    status |= run(LIVENESS_MUTANTS, LIVENESS_TESTS, prefix="gate-rules-liveness-", root=ROOT,
                  purge_dirs=("scripts", "tests"))
    with tempfile.TemporaryDirectory(prefix="gate-rules-planted-") as temp:
        planted = Path(temp) / "repo"
        shutil.copytree(ROOT, planted, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        (planted / "scripts" / "ci" / PLANTED).write_text(
            '"""Planted by check_gate_rules_mutants.py: a mutation gate no workflow names."""\nMUTANTS = []\n')
        # The planted gate makes the liveness test fail before any mutant; the mutant is caught only when the pin
        # fails in its place. Until 2026-11-12 the runner took the planted failure itself for a catch.
        status |= run(GROWTH_MUTANTS, LIVENESS_TESTS, prefix="gate-rules-growth-", root=planted,
                      purge_dirs=("scripts", "tests"), failing_first=UNWIRED_TEST)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
