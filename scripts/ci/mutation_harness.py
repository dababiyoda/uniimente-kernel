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

Before any mutant the runner runs the named tests once, in full (without ``-x``), unmutated, in the same scratch copy.
The tests that fail there must be none; if not, it prints ``BASELINE_FAILS`` and exits 1 without applying a mutant: a
test that already fails would otherwise count as a catch for every mutant. (Seen on 2026-11-12: on a tree where two
branches were merged, one test of the named file failed for an unrelated reason and the gate printed 81/81 caught.)
The baseline costs one more run of the named tests per call. A gate that mutates a tree planted to fail names that
failure with ``failing_first``; the baseline must then fail on that test and on no other, and a mutant is caught only
by a different one. Test ids are compared whole, so a test whose name begins with the planted one's is another test.
(Until a review on 2026-11-12 a planted baseline stopped at the planted test, so a later test that already failed
read as a catch.) The collection-error exclusion matches pytest's heading anywhere in its output: a failing test whose
shown source or output contains that heading reads as not caught. ``tests/unit/test_mutation_harness.py`` pins each
clause of the rule.

Mutants run on ``workers`` scratch copies at once (``MUTATION_WORKERS``, a whole number in ASCII digits from 1 to the
CPU count; by default, and when the value is anything else, one less than the CPUs, at most three, and a value that
is set but not used is reported on stderr). Each copy has its own pytest base temporary directory and its own
``PYTHONPATH``, so a process a test starts outside the copy still imports that copy; a mutant is applied, tested and
reverted inside its own copy only. The copies still share HOME, TMPDIR, the network and the machine: a test that fails
only under load, or when another run holds the same fixed path or port, can pass the baseline (which runs alone) and
fail under a mutant. (A review on 2026-11-13 showed it: one test holding a fixed path, a real mutant beside a no-op
one, three runs each: the no-op mutant read as caught in 1 or 2 of 3 runs.)

So with more than one worker no catch is taken from a parallel run. After every parallel run has ended, each mutant a
parallel run caught is judged again, one at a time, in the copy the baseline ran in. The test that failed is run by
itself, unmutated, where it must pass, then with the mutant applied: if it fails, the mutant is caught. Where that
test cannot pass by itself (it relies on an earlier test of the file), or alone does not fail (beside other copies a
test can fail first for a reason of its own, before the test that catches the mutant), the whole named file decides:
unmutated it must pass as the baseline did, and with the mutant applied the rule above decides. A mutant whose tests
failed only beside other copies reads ``SURVIVED_OR_INVALID`` with that reason. If the named tests no longer pass
unmutated after the other mutants ran, the mutant is not judged (``SURVIVED_OR_INVALID``, with that reason): the
copy's surroundings have changed, so no run of it shows what the mutant did. The unmutated run is made again before
every mutated one, never reused, because a run can leave its surroundings changed. With one worker every mutant is
judged alone already and no second run is made, as before; a mutant that leaves state behind outside its copy can then
still make a later mutant read as caught.

On 2026-11-12 the composed candidate's gate job took 176 of its 180 minutes with every mutant run one after another;
its two slowest gates (43 and 34 minutes) both use this runner. An exception while judging one mutant (a timeout, a
target that is not there) reads as ``SURVIVED_OR_INVALID`` with its reason, and the other mutants are still judged. A
survivor is printed when its parallel run finishes, a catch once it is confirmed; the closing count and the exit
status do not depend on the order.

New gates should use this runner. Gates with a different contract (another
timeout, a single target, no purge) keep their own loop rather than change
behaviour to fit it.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def purge(repo: Path, dirs: tuple[str, ...]) -> None:
    for top in dirs:
        for cache in (repo / top).rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)


SUMMARY_HEADING = re.compile(r"=+ short test summary info =+")


def failures(stdout: str) -> list[str]:
    """``FAILED <test id>`` and ``ERROR <test id>`` lines of pytest's closing short summary, each without its message.
    Only the summary is read: a test's own output can contain lines that begin with those words. The summary starts
    after pytest's last whole heading line; a failure message that contains the heading's words is not a heading."""
    lines = stdout.splitlines()
    starts = [i for i, line in enumerate(lines) if SUMMARY_HEADING.fullmatch(line)]
    if not starts:
        return []
    return [line.split(" - ", 1)[0] for line in lines[starts[-1] + 1:] if line.startswith(("FAILED ", "ERROR "))]


def default_workers() -> int:
    cpus = os.cpu_count() or 1
    fallback = max(1, min(3, cpus - 1))
    asked = os.environ.get("MUTATION_WORKERS", "")
    if not asked:
        return fallback
    if re.fullmatch("[0-9]+", asked) and 1 <= int(asked) <= cpus:
        return int(asked)
    message = (f"MUTATION_WORKERS={asked!r} is not a whole number from 1 to {cpus} (the CPU count); "
               f"using {fallback} workers")
    print(message, file=sys.stderr, flush=True)
    return fallback


def run(mutants: list[tuple[str, str, str, str]], tests: str, prefix: str, *,
        root: Path = ROOT, purge_dirs: tuple[str, ...] = ("greg", "tests"), timeout: int = 900,
        failing_first: str | None = None, workers: int | None = None) -> int:
    """``failing_first`` is for a tree that is meant to fail before any mutant (a planted fault): it names the one
    test that must then be the only failing one, unmutated, and a mutant is caught only when a *different* test of
    the file fails instead. Without it the named tests must pass unmutated. ``workers`` scratch copies run mutants at
    once (default :func:`default_workers`)."""
    workers = max(1, min(workers or default_workers(), len(mutants) or 1))
    planted = f"FAILED {tests}::{failing_first}" if failing_first else None
    lock = threading.Lock()
    with tempfile.TemporaryDirectory(prefix=prefix) as temp:
        copies = []
        for index in range(workers):
            repo = Path(temp) / f"repo{index}"
            shutil.copytree(root, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
            env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
            command = [sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                       f"--basetemp={Path(temp) / f'pytest{index}'}", tests]
            copies.append((repo, env, command))
        repo, env, command = copies[0]
        purge(repo, purge_dirs)
        full = [part for part in command if part != "-x"]        # the baseline runs every named test
        baseline = subprocess.run(full, cwd=repo, env=env, capture_output=True, text=True, timeout=timeout)
        failed, expected = failures(baseline.stdout), [] if planted is None else [planted]
        if baseline.returncode != (0 if planted is None else 1) or failed != expected:
            print(f"BASELINE_FAILS {tests} (pytest exit {baseline.returncode}): "
                  + ("the named tests do not pass before any mutant is applied" if planted is None else
                     f"before any mutant the one failing test is not {failing_first} alone")
                  + (f" (failing: {'; '.join(failed)})" if failed else "") + ", so no mutant is judged")
            print(f"0/{len(mutants)} caught")
            return 1
        free = list(copies)

        def catches(result: subprocess.CompletedProcess) -> bool:
            """pytest exits 1 with a FAILED test in the named file and no collection error; on a planted tree that
            test is not the planted one."""
            caught = (result.returncode == 1 and f"FAILED {tests}::" in result.stdout
                      and "ERROR collecting" not in result.stdout)
            if planted is not None:           # the planted failure itself is no catch: another test must fail
                caught = caught and planted not in failures(result.stdout)
            return caught

        def judge(mutant) -> bool:
            target, name, old, new = mutant
            with lock:
                repo, env, command = free.pop()
            try:
                path = repo / target
                original = path.read_text()
                if original.count(old) != 1:
                    with lock:
                        print("STALE", name, flush=True)
                    return False
                try:
                    path.write_text(original.replace(old, new))
                    purge(repo, purge_dirs)
                    result = subprocess.run(command, cwd=repo, env=env, capture_output=True, text=True,
                                            timeout=timeout)
                finally:
                    path.write_text(original)
                caught = catches(result)
                if caught and workers > 1:        # beside other copies: judged again alone, once they have all ended
                    return [line[len("FAILED "):] for line in failures(result.stdout)
                            if line.startswith(f"FAILED {tests}::") and line != planted][:1] or [None]
                with lock:
                    print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name, flush=True)
                return caught
            except Exception as error:            # a timeout, a missing target: this mutant only is not judged
                with lock:
                    print("SURVIVED_OR_INVALID", name, f"(not judged: {type(error).__name__}: {error})", flush=True)
                return False
            finally:
                with lock:
                    free.append((repo, env, command))

        with ThreadPoolExecutor(max_workers=workers) as pool:
            verdicts = list(pool.map(judge, mutants))

        # Every parallel run has ended. A catch made beside other copies counts only if it holds alone.
        repo, env, command = copies[0]                # the copy the baseline ran in, each mutant reverted

        def alone(argv: list[str]) -> subprocess.CompletedProcess:
            purge(repo, purge_dirs)
            return subprocess.run(argv, cwd=repo, env=env, capture_output=True, text=True, timeout=timeout)

        def passes_unmutated(node: str | None) -> bool:
            # Run again before every mutated run, never reused: a run may leave its surroundings changed.
            if node is None:                         # the whole file, judged as the baseline was
                result = alone(full)
                return (result.returncode == (0 if planted is None else 1)
                        and failures(result.stdout) == ([] if planted is None else [planted]))
            return alone(command[:-1] + [node]).returncode == 0

        def mutated(mutant, argv: list[str]) -> subprocess.CompletedProcess:
            target, name, old, new = mutant
            path = repo / target
            original = path.read_text()
            try:
                path.write_text(original.replace(old, new))
                return alone(argv)
            finally:
                path.write_text(original)

        def confirm(mutant, node: str | None) -> bool:
            name = mutant[1]
            try:
                if node is not None and passes_unmutated(node):     # the one test, by its whole id
                    result = mutated(mutant, command[:-1] + [node])
                    if (f"FAILED {node}" in failures(result.stdout) and result.returncode == 1
                            and "ERROR collecting" not in result.stdout):
                        print("CAUGHT", name, flush=True)
                        return True
                # That test cannot pass by itself, or alone it does not catch the mutant (beside other copies a test
                # can fail first for a reason of its own, before the one that catches): the whole file decides.
                if not passes_unmutated(None):
                    print("SURVIVED_OR_INVALID", name, "(not judged: the named tests no longer pass unmutated after "
                          "the other mutants ran)", flush=True)
                    return False
                if catches(mutated(mutant, command)):
                    print("CAUGHT", name, flush=True)
                    return True
                print("SURVIVED_OR_INVALID", name, "(its tests failed only beside other copies: alone, with the "
                      f"mutant applied, {tests} gave no catch)", flush=True)
                return False
            except Exception as failure:             # as in a parallel run: this mutant only is not judged
                print("SURVIVED_OR_INVALID", name, f"(not judged: {type(failure).__name__}: {failure})", flush=True)
                return False

        verdicts = [confirm(mutant, verdict[0]) if isinstance(verdict, list) else verdict
                    for mutant, verdict in zip(mutants, verdicts)]
    invalid = verdicts.count(False)
    print(f"{len(mutants) - invalid}/{len(mutants)} caught")
    return int(bool(invalid))
