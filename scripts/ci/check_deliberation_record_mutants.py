"""Directive ask S65.A1: each check the two-pass protocol validator makes must fail a behavioural test when removed.

The vendored validator's bytes are pinned by test_the_vendored_validator_is_the_founders_bytes; that test is left
out here, so each mutant must be caught by the defect and record tests alone.
"""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
TARGET = "tools/collaboration_protocol/scripts/validate_deliberation.py"
TESTS = "tests/unit/test_deliberation_records.py"
MUTANTS = [
    ("a missing role is accepted", "    if missing:\n        errors.append(\n            \"$.roles: missing required role(s): \"",
     "    if False:\n        errors.append(\n            \"$.roles: missing required role(s): \""),
    # The numbered-pass check and the schema's unexpected-field check each refuse a pass_3; removing one alone is
    # caught by the other, so this mutant removes both.
    ("a third pass is accepted", [("    if numbered_passes != {\"pass_1\", \"pass_2\"}:", "    if False:"),
                                  ("    for field in sorted(set(record) - set(properties)):",
                                   "    for field in sorted(set(record) - set(properties) - {\"pass_3\"}):")]),
    ("a Pass-1 disadvantage may be silently omitted", "    if missing_dispositions:", "    if False:"),
    ("declared dissent may be erased", "    if present is True and not entries:", "    if False:"),
]


def main() -> int:
    bad = 0
    with tempfile.TemporaryDirectory(prefix="deliberation-record-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        path = repo / TARGET
        original = path.read_text()
        base = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", TESTS,
                               "-k", "not founders_bytes"], cwd=repo, env={**os.environ, "PYTHONPATH": str(repo)},
                              capture_output=True, text=True, timeout=300)
        if base.returncode != 0:
            print("BASELINE_RED: the tests fail unmutated; no mutant is judged")
            print(base.stdout[-2000:])
            return 1
        for mutant in MUTANTS:
            name, edits = mutant[0], (mutant[1] if isinstance(mutant[1], list) else [mutant[1:]])
            mutated = original
            for old, new in edits:
                if mutated.count(old) != 1:
                    break
                mutated = mutated.replace(old, new)
            else:
                old = None
            if old is not None:
                print("STALE", name)
                bad += 1
                continue
            path.write_text(mutated)
            run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", TESTS,
                                  "-k", "not founders_bytes"], cwd=repo, env={**os.environ, "PYTHONPATH": str(repo)},
                                 capture_output=True, text=True, timeout=300)
            caught = run.returncode == 1 and f"FAILED {TESTS}::" in run.stdout and "ERROR collecting" not in run.stdout
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            bad += not caught
            path.write_text(original)
    print(f"{len(MUTANTS)} mutants, {bad} survived or stale")
    return int(bool(bad))


if __name__ == "__main__":
    raise SystemExit(main())
