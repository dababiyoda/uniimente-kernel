"""Shared runner for mutation gates: each safeguard must fail its tests when removed.

A gate script keeps its own literal ``MUTANTS`` list and calls :func:`run`.
``scripts/repo_review.py`` does not read these lists today: its static reader
expects a target path directly followed by its anchor, and here the mutant's
name sits between them (written as a literal path, the target would make the
reader take the name for the anchor and call it stale). For a gate that calls
this runner a moved anchor is therefore reported by the gate's own run, as
``STALE``, not by the unit suite.

For each ``(target, name, old, new)`` mutant, in a scratch copy of the
repository (never the working tree):

* ``old`` must occur exactly once in ``target``, else the gate reports ``STALE``;
* the replacement is applied, ``__pycache__`` under ``purge_dirs`` is removed,
  and the tests run without bytecode;
* the mutant is caught only when the tests report a ``FAILED`` test in the
  named file; an import or collection error does not count.

Exit status 1 if any mutant survives, errors or no longer applies.

The runner does not run the tests unmutated first. A named test that already fails counts as a catch for every
mutant, so a gate runs its tests green beforehand (as ``check_gate_rules_mutants.py`` does) or relies on the job that
runs the whole suite. The collection-error exclusion matches pytest's heading anywhere in its output: a failing test
whose shown source or output contains that heading reads as not caught. ``tests/unit/test_mutation_harness.py`` pins
each clause of the rule.

New gates should use this runner. Gates with a different contract (another
timeout, a single target, no purge) keep their own loop rather than change
behaviour to fit it.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def purge(repo: Path, dirs: tuple[str, ...]) -> None:
    for top in dirs:
        for cache in (repo / top).rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)


def run(mutants: list[tuple[str, str, str, str]], tests: str, prefix: str, *,
        root: Path = ROOT, purge_dirs: tuple[str, ...] = ("greg", "tests"), timeout: int = 900) -> int:
    invalid = 0
    with tempfile.TemporaryDirectory(prefix=prefix) as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(root, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
        for target, name, old, new in mutants:
            path = repo / target
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name)
                invalid += 1
                continue
            path.write_text(original.replace(old, new))
            purge(repo, purge_dirs)
            try:
                result = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", tests],
                                        cwd=repo, env=env, capture_output=True, text=True, timeout=timeout)
            finally:
                path.write_text(original)
            caught = (result.returncode == 1 and f"FAILED {tests}::" in result.stdout
                      and "ERROR collecting" not in result.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name, flush=True)
            invalid += not caught
    print(f"{len(mutants) - invalid}/{len(mutants)} caught")
    return int(bool(invalid))
