"""Each rule a mutation gate is trusted for must fail a unit test when removed (directive section 69, S69.A6).

    python scripts/ci/check_gate_rules_mutants.py

Three groups, each run by the shared runner in a scratch copy of the repository, never in the working tree:

* what the shared runner counts as caught (scripts/ci/mutation_harness.py, tests/unit/test_mutation_harness.py):
  pytest exits 1, reports a FAILED test in the named file and reports no collection error; an anchor that does not
  occur exactly once is STALE; a stale or surviving mutant fails the gate; before any mutant every named test runs and
  none fails, or on a planted tree the planted test alone, named whole; each scratch copy has its own pytest base
  temporary directory and its own import path; an exception while judging one mutant loses no other verdict; and
  MUTATION_WORKERS is used only as a whole number from 1 to the CPU count, a value not used being reported;
* gate liveness (scripts/repo_review.py, tests/unit/test_repo_health_gates.py): a gate no workflow names reads as
  unwired, and an anchor that left its target reads as stale;
* the pin on KEPT_UNWIRED_GATES. The copy first receives a gate no workflow names, so the liveness test fails there
  until the mutant adds that gate to the kept list. With the mutant applied the only failing test is the pin, which
  is what this group shows: growing the list in the same change as a new unwired gate is refused.

Before any mutant, both test files must pass unmutated, read in place. The shared runner checks each group's tests
itself in its first scratch copy (BASELINE_FAILS), and for the planted group that the planted test is the only one
failing. This gate's own check runs first, on the working tree, so a failing file stops the gate before any copy of
the repository is made. (Until 2026-11-12 this said the check was kept because a mutant removes the runner's; the
mutants edit only the scratch copies' runner, never the one this gate imports, so that was not the reason.) A mutant
is caught only by a FAILED test. Exit status 1 if the baseline fails or any mutant survives or no longer applies.
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
               '                          and "ERROR collecting" not in result.stdout)')
RUNNER_MUTANTS = [
    (RUNNER, "any non-zero pytest exit counts as caught", CAUGHT_RULE, "caught = result.returncode != 0"),
    (RUNNER, "a failed test in a run that did not finish counts as caught",
     'result.returncode == 1 and f"FAILED', 'f"FAILED'),
    (RUNNER, "an error that is not a FAILED test counts as caught", ' and f"FAILED {tests}::" in result.stdout', ""),
    (RUNNER, "the word FAILED anywhere in the output counts as caught",
     'f"FAILED {tests}::" in result.stdout', '"FAILED " in result.stdout'),
    (RUNNER, "a failed test beside a collection error counts as caught",
     '\n                          and "ERROR collecting" not in result.stdout)', ")"),
    (RUNNER, "an anchor at several sites is applied", "if original.count(old) != 1:", "if original.count(old) == 0:"),
    (RUNNER, "a stale mutant does not fail the gate", 'print("STALE", name, flush=True)\n                    return False',
     'print("STALE", name, flush=True)\n                    return True'),
    (RUNNER, "a surviving mutant does not fail the gate", "invalid = verdicts.count(False)", "invalid = 0"),
    (RUNNER, "two mutants share one worker's scratch copy at once", "repo, env, command = free.pop()",
     "repo, env, command = free[0]"),
    (RUNNER, "a named test that already fails counts as a catch for every mutant",
     "if baseline.returncode != (0 if planted is None else 1) or failed != expected:", "if False:"),
    (RUNNER, "on a planted tree the planted failure itself counts as a catch",
     "caught = caught and planted not in failures(result.stdout)", "pass"),
    (RUNNER, "on a planted tree the baseline stops at the planted failure",
     'full = [part for part in command if part != "-x"]', "full = command"),
    (RUNNER, "on a planted tree only the first failing test is checked", "or failed != expected:",
     "or failed[:1] != expected:"),
    (RUNNER, "on a planted tree a test named with the planted name as its prefix counts as the planted one",
     "planted not in failures(result.stdout)", "planted not in result.stdout"),
    (RUNNER, "the summary is read from wherever its heading's words last appear, even inside a failure message",
     "SUMMARY_HEADING.fullmatch(line)", '"short test summary info" in line'),
    (RUNNER, "every copy runs pytest with one shared base temporary directory",
     "f\"--basetemp={Path(temp) / f'pytest{index}'}\"", "f\"--basetemp={Path(temp) / 'pytest'}\""),
    (RUNNER, "every copy imports from the first copy", '"PYTHONPATH": str(repo)',
     '"PYTHONPATH": str(Path(temp) / "repo0")'),
    (RUNNER, "an exception while judging one mutant loses the other verdicts", "except Exception as error:",
     "except ArithmeticError as error:"),
    (RUNNER, "a worker count in other digits, or above the CPU count, is used",
     're.fullmatch("[0-9]+", asked) and 1 <= int(asked) <= cpus', "asked.isdigit() and int(asked) >= 1"),
    (RUNNER, "a worker count that is not used is dropped without a word",
     "print(message, file=sys.stderr, flush=True)", "None"),
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
