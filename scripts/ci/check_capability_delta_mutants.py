"""Directive ask S70.A1: each rule of the capability delta must fail a behavioural test when removed.

The delta answers "what can GREG now do that it could not do before" from the directive map at two commits. Each
mutant below removes one rule that keeps that answer honest; tests/unit/test_capability_delta.py must catch every
one in a copy of the repository without .git, where the command-line test skips.
"""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
TARGET = "acceptance/directive.py"
TESTS = "tests/unit/test_capability_delta.py"
MUTANTS = [
    ("a newly met ask counts without changed evidence", "            (gained if changed else unproven).append(row)",
     "            gained.append(row)"),
    ("a lost ask is dropped instead of listed", "        elif was_met and not now[\"met\"]:\n            lost.append(row)",
     "        elif was_met and not now[\"met\"]:\n            pass"),
    ("an open ask that came closer counts as gained", "        if now[\"met\"] and not was_met:",
     "        if (now[\"met\"] or _rung(now[\"tier\"]) > _rung(was_tier)) and not was_met:"),
    ("a recorded run at head is ignored", "    after = _ask_rows(head, head_outcomes, root)",
     "    after = _ask_rows(head, None, root)"),
    ("an unchanged file is read as changed evidence", "    return then != now and node_text(then, node) != node_text(now, node)",
     "    return True"),
]


def _pytest(repo: Path, *extra: str):
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *extra, TESTS], cwd=repo,
                          env={**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"},
                          capture_output=True, text=True, timeout=600)


def main() -> int:
    bad = 0
    with tempfile.TemporaryDirectory(prefix="capability-delta-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        path = repo / TARGET
        original = path.read_text()
        base = _pytest(repo)
        if base.returncode != 0:
            print("BASELINE_RED: the tests fail unmutated; no mutant is judged")
            print(base.stdout[-2000:])
            return 1
        for name, old, new in MUTANTS:
            if original.count(old) != 1:
                print("STALE", name)
                bad += 1
                continue
            path.write_text(original.replace(old, new))
            run = _pytest(repo, "-x")
            caught = run.returncode == 1 and f"FAILED {TESTS}::" in run.stdout and "ERROR collecting" not in run.stdout
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            bad += not caught
            path.write_text(original)
    print(f"{len(MUTANTS)} mutants, {bad} survived or stale")
    return int(bool(bad))


if __name__ == "__main__":
    raise SystemExit(main())
