"""Each safeguard that makes a backup of a running body consistent must fail a behavioral test when removed (WU-14).

Every mutant runs in a scratch copy of the repository, with bytecode off and every ``__pycache__`` purged first, so a
stale compiled module can never stand in for the mutated source.
"""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
SEED = "foundry/systems/seed.py"
UNIT = "tests/unit/test_greg_seed_consistency.py"
MUTANTS = [
    ("head read from the live ledger after the copy", SEED,
     '"backed_up_at": backed_up_at, "ledger_head": head}',
     '"backed_up_at": backed_up_at, "ledger_head": ledger_prefix(home)[1]}', UNIT),
    ("the live ledger copied again with the other files", SEED,
     "if rel == LEDGER:\n            continue", "if rel == LEDGER and False:\n            continue", UNIT),
    ("torn final line packed", SEED,
     'return raw[:raw.rfind(b"\\n") + 1]', "return raw", UNIT),
    ("prefix not verified as a chain", SEED, "    if not constitution:\n", "    if True:\n", UNIT),
    ("derived heartbeat packed", SEED,
     "if rel in DERIVED:\n            derived.append(rel)", "if False:\n            derived.append(rel)", UNIT),
    ("derived heartbeat restored from a seed that carries one", SEED,
     "if rel in DERIVED:                              #", "if False:                                       #", UNIT),
]


def purge(repo: Path) -> None:
    for cache in repo.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def main() -> int:
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="greg-consistent-backup-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
        for name, rel, old, new, tests in MUTANTS:
            path = repo / rel
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name)
                invalid += 1
                continue
            path.write_text(original.replace(old, new))
            purge(repo)
            run = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", tests],
                                 cwd=repo, env=env, capture_output=True, text=True, timeout=300)
            caught = (run.returncode == 1 and f"FAILED {tests}::" in run.stdout
                      and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            invalid += not caught
            path.write_text(original)
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
