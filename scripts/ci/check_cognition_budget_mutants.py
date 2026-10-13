"""A removed budget boundary must fail its focused behavioral test."""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
MUTANTS = [
    ("mandatory verification reserve", "self.verification_reserve = max(.01, self.total_seconds * .5)",
     "self.verification_reserve = 0"),
    ("caller compute intersection", "self.compute_limit = min(self.compute_limit, integer(caller_window.compute_ceiling_operations, low=0, high=100000))",
     "self.compute_limit = self.compute_limit"),
    ("grant horizon", "for name in (\"horizon\", \"grant_expires_at\"):",
     "for name in ():")
]

def main():
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="greg-budget-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        path = repo / "greg/cognition/budget.py"
        original = path.read_text()
        for name, old, new in MUTANTS:
            if original.count(old) != 1:
                print("STALE", name); invalid += 1; continue
            path.write_text(original.replace(old, new))
            run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                                  "tests/unit/test_cognition_runtime_budget.py"], cwd=repo,
                                 env={**os.environ, "PYTHONPATH": str(repo)}, capture_output=True,
                                 text=True, timeout=45)
            caught = (run.returncode == 1 and "FAILED tests/unit/test_cognition_runtime_budget.py::" in run.stdout
                      and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            invalid += not caught
            path.write_text(original)
    return int(bool(invalid))

if __name__ == "__main__":
    raise SystemExit(main())
