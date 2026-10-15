"""Canonical worker acceptance must survive hostile, self-consistent local edits."""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
MUTANTS = [
    ("canonical commission binding", "greg/workers.py", "if ctx.journal is not None:", "if False:"),
    ("worker world reobservation", "greg/appraisal.py", '"worker.appraise", "browser.trace"', '"browser.trace"'),
    ("read-only journal propagation", "greg/appraisal.py", '"artifact.inspect", "worker.appraise", "daleobanks.outcome")',
     '"artifact.inspect", "daleobanks.outcome")'),
]

def main():
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="greg-worker-appraisal-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        for name, relative, old, new in MUTANTS:
            path = repo / relative
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name); invalid += 1; continue
            path.write_text(original.replace(old, new))
            run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                                  "tests/unit/test_greg_workers.py::test_appraisal_binds_acceptance_to_the_original_commission"],
                                 cwd=repo, env={**os.environ, "PYTHONPATH": str(repo)},
                                 capture_output=True, text=True, timeout=45)
            caught = (run.returncode == 1 and "FAILED tests/unit/test_greg_workers.py::" in run.stdout
                      and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            invalid += not caught
            path.write_text(original)
    return int(bool(invalid))

if __name__ == "__main__":
    raise SystemExit(main())
