"""Canonical worker acceptance must survive hostile, self-consistent local edits."""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
MUTANTS = [
    ("canonical commission binding", "greg/workers.py", "if ctx.journal is not None:", "if False:"),
    ("worker world reobservation", "greg/appraisal.py", '"worker.appraise", "browser.trace"', '"browser.trace"'),
    ("read-only journal propagation", "greg/appraisal.py", '"artifact.inspect", "worker.appraise")', '"artifact.inspect")'),
    # A worker's own tests cannot certify its own change (greg/evidence_strength.py).
    ("discrimination on the base", "greg/evidence_strength.py",
     'discriminates = on_base["returncode"] in (1, 2, -1)', "discriminates = True",
     "tests/unit/test_greg_worker_evidence_strength.py::test_a_vacuous_test_no_longer_certifies_a_corrupted_change"),
    ("mutation adversary threshold", "greg/evidence_strength.py",
     "adequate = (not measured) or (killed >= MIN_KILLED and ratio >= MIN_KILL_RATIO)", "adequate = True",
     "tests/unit/test_greg_worker_evidence_strength.py::"
     "test_a_test_that_cannot_tell_add_from_sub_is_refused_by_the_mutation_adversary"),
    ("sealed acceptance oracle", "greg/workers.py",
     'tampered = sorted(n for n in names if n in evidence_strength.sealed_paths(order["acceptance"], base_files))',
     "tampered = []",
     "tests/unit/test_greg_worker_evidence_strength.py::"
     "test_a_worker_that_rewrites_its_sealed_oracle_is_judged_by_the_founders_version"),
    ("strength step skipped", "greg/workers.py",
     'if verdict == "ACCEPTED" and order["acceptance"].get("run_changed_tests") and authored:', "if False:",
     "tests/unit/test_greg_worker_evidence_strength.py::test_a_vacuous_test_no_longer_certifies_a_corrupted_change"),
]
DEFAULT_TEST = "tests/unit/test_greg_workers.py::test_appraisal_binds_acceptance_to_the_original_commission"

def main():
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="greg-worker-appraisal-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        for name, relative, old, new, *test in MUTANTS:
            path = repo / relative
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name); invalid += 1; continue
            path.write_text(original.replace(old, new))
            node = test[0] if test else DEFAULT_TEST
            run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", node],
                                 cwd=repo, env={**os.environ, "PYTHONPATH": str(repo)},
                                 capture_output=True, text=True, timeout=120)
            caught = (run.returncode == 1 and f"FAILED {node.split('::')[0]}::" in run.stdout
                      and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            invalid += not caught
            path.write_text(original)
    return int(bool(invalid))

if __name__ == "__main__":
    raise SystemExit(main())
