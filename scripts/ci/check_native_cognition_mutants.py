"""Challenge native proof, source, request and workload safeguards in a copy."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TEST = "tests/unit/test_greg_native_reconciliation.py"
MUTANTS = [
    ("source-bound appraisal", "greg/cognition/verification.py", "if family in NATIVE_QUALIFIED:", "if False:"),
    ("source digest", "greg/cognition/verification.py", 'artifact.get("input_digest") == digest(data)', "True"),
    ("unconsumed request clauses", "greg/cognition/solvers.py",
     'if not isinstance(data, dict) or not set(required) <= set(data) or set(data) - set(required) - set(optional):', "if False:"),
    ("native workload ceiling", "greg/cognition/solvers.py",
     'if operations > integer(geometry["compute_limit"], low=1, high=100000):', "if False:"),
]


def main():
    bad = 0
    with tempfile.TemporaryDirectory(prefix="greg-native-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        for name, rel, old, new in MUTANTS:
            path = repo / rel
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name)
                bad += 1
                continue
            path.write_text(original.replace(old, new))
            try:
                run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", TEST],
                                     cwd=repo, env={**os.environ, "PYTHONPATH": str(repo)},
                                     capture_output=True, text=True, timeout=60)
                caught = (run.returncode == 1 and "FAILED " + TEST + "::" in run.stdout
                          and "ERROR collecting" not in run.stdout)
                print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
                bad += not caught
            finally:
                path.write_text(original)
    print(f"{len(MUTANTS)} mutants; {bad} survived, stale or invalid")
    return int(bool(bad))


if __name__ == "__main__":
    raise SystemExit(main())
