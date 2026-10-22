"""Canonical worker acceptance must survive hostile, self-consistent local edits."""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
APPRAISAL = "tests/unit/test_greg_workers.py::test_appraisal_binds_acceptance_to_the_original_commission"
FREEZE = "tests/unit/test_greg_worker_containment.py::"
FROZEN = FREEZE + "test_helpers_the_runner_and_shadowing_modules_are_part_of_the_frozen_evaluator"
NAMED = FREEZE + "test_scripts_and_configuration_are_frozen_but_named_code_is_not"
MUTANTS = [
    ("canonical commission binding", "greg/workers.py", "if ctx.journal is not None:", "if False:", APPRAISAL),
    ("worker world reobservation", "greg/appraisal.py", '"worker.appraise", "browser.trace"', '"browser.trace"',
     APPRAISAL),
    ("read-only journal propagation", "greg/appraisal.py", '"artifact.inspect", "worker.appraise", "daleobanks.outcome")',
     '"artifact.inspect", "daleobanks.outcome")', APPRAISAL),
    # The frozen evaluator (#173 I.G6 and the PR #184 port's review 0afd309): each guard of evaluator_findings/appraise.
    ("evaluator: helper directory of a named test", "greg/workers.py",
     'or any(path.startswith(d + "/") for d in helper_dirs)', "", FROZEN),
    ("evaluator: package test's nearest test directory", "greg/workers.py", 'part in TEST_DIRS), "")',
     'part in ()), "")', FREEZE + "test_a_test_inside_packages_freezes_its_test_directory_not_the_code"),
    ("evaluator: named test directory frozen whole", "greg/workers.py", "                helper_dirs.add(path)",
     "                pass", FREEZE + "test_a_named_test_directory_freezes_every_existing_file_in_it"),
    ("evaluator: interpreter hooks and plugin metadata", "greg/workers.py", "allowed(path, EVALUATOR_RUNTIME) or ", "",
     FROZEN),
    ("evaluator: -m and -p modules", "greg/workers.py", "or module(path) or shadows(path)", "or shadows(path)", NAMED),
    ("evaluator: shadowing modules", "greg/workers.py", "or module(path) or shadows(path)", "or module(path)", FROZEN),
    ("evaluator: shadowing packages", "greg/workers.py", 'elif entry + "/__init__.py" in after', "elif False", FROZEN),
    ("evaluator: standard-library shadows", "greg/workers.py", "SHADOWED_MODULES | {m.split",
     "RUNNER_MODULES | {m.split", FROZEN),
    ("evaluator: executed scripts and named configuration", "greg/workers.py",
     'frozen = {p for p in map(norm, targets["scripts"] | targets["config"]) if p}', "frozen = set()", NAMED),
    ("evaluator: shell -c commands", "greg/workers.py", "                            _acceptance_targets(command, out)",
     "                            pass", NAMED),
    ("evaluator: named code stays writable", "greg/workers.py", 'elif not path.endswith(".py"):', "else:", NAMED),
    ("evaluator: named non-Python files frozen", "greg/workers.py", 'elif not path.endswith(".py"):', "elif False:",
     NAMED),
    ("evaluator: shared files never override a rejection", "greg/workers.py",
     'if evaluator["shared"] and verdict == "ACCEPTED":', 'if evaluator["shared"]:',
     FREEZE + "test_a_project_file_change_never_turns_a_rejection_into_a_founder_decision"),
]

def main():
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="greg-worker-appraisal-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        for name, relative, old, new, node in MUTANTS:
            path = repo / relative
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name); invalid += 1; continue
            path.write_text(original.replace(old, new))
            run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", node],
                                 cwd=repo, env={**os.environ, "PYTHONPATH": str(repo)},
                                 capture_output=True, text=True, timeout=90)
            caught = (run.returncode == 1 and f"FAILED {node.split('::')[0]}::" in run.stdout
                      and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            invalid += not caught
            path.write_text(original)
    return int(bool(invalid))

if __name__ == "__main__":
    raise SystemExit(main())
