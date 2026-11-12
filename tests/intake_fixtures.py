"""Shared fixtures for the intake recommendation tests: a small real Git repository and a scripted test envelope.

The repository is the one ``tests/unit/test_compose_rehearsal.py`` builds, with more branches:

- ``steeper`` changes what ``price`` returns and updates the base's test with it;
- ``consumer`` adds a test that relies on the old ``price`` (merges cleanly with ``steeper``, breaks in behaviour);
- ``label`` adds an unrelated function and its test; ``label2`` is built on top of ``label`` (it contains it);
- ``flat`` rewrites the same line as ``steeper`` (a textual conflict);
- ``broken`` adds a test that fails on its own head;
- ``slow`` adds a test that sleeps far longer than any timeout used here;
- ``silent`` changes behaviour and changes no test;
- ``old`` branched from the commit before the base.

``Script`` stands in for ``greg.workers.run_tests`` where a test is about what GREG does with an outcome, not about
producing it: it returns what the real function returns, from a table, and starts no process. The tests that produce
outcomes with real pytest inside the real envelope say so.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@t"}
PKG = "REGISTRY = ['base']\n\n\ndef price(n):\n    return n * 2\n\n\ndef label(n):\n    return f'item-{n}'\n"
TOTAL = "tests/test_total.py"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, env=ENV, capture_output=True, text=True, check=True).stdout.strip()


def branch(repo: Path, name: str, files: dict[str, str], start: str = "base") -> str:
    """A branch off ``start`` with ``files`` written and committed. Returns its commit."""
    git(repo, "checkout", "-q", "-b", name, start)
    for path, text in files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text)
        git(repo, "add", path)
    git(repo, "commit", "-qm", name)
    return git(repo, "rev-parse", "HEAD")


def build_repo(repo: Path) -> dict[str, str]:
    """Create the repository at ``repo``. Returns every branch's full SHA by name (``base`` included)."""
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "trunk")
    (repo / "README").write_text("first\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "first")
    shas = {"first": git(repo, "rev-parse", "HEAD")}
    git(repo, "checkout", "-q", "-b", "base")
    (repo / "pkg.py").write_text(PKG)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_base.py").write_text("import pkg\n\n\ndef test_price():\n    assert pkg.price(2) == 4\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    shas["base"] = git(repo, "rev-parse", "HEAD")
    shas["steeper"] = branch(repo, "steeper", {
        "pkg.py": PKG.replace("n * 2", "n * 3"),
        "tests/test_base.py": "import pkg\n\n\ndef test_price():\n    assert pkg.price(2) == 6\n"})
    shas["consumer"] = branch(repo, "consumer", {
        TOTAL: "import pkg\n\n\ndef test_total():\n    assert pkg.price(2) + 1 == 5\n\n\n"
               "def test_label_untouched():\n    assert pkg.label(1) == 'item-1'\n"})
    shas["label"] = branch(repo, "label", {
        "pkg.py": PKG + "\n\ndef shout(n):\n    return label(n).upper()\n",
        "tests/test_shout.py": "import pkg\n\n\ndef test_shout():\n    assert pkg.shout(1) == 'ITEM-1'\n"})
    shas["label2"] = branch(repo, "label2", {
        "tests/test_shout_twice.py": "import pkg\n\n\ndef test_twice():\n    assert pkg.shout(2) == 'ITEM-2'\n"},
        start="label")
    shas["flat"] = branch(repo, "flat", {
        "pkg.py": PKG.replace("n * 2", "n * 4"),
        "tests/test_base.py": "import pkg\n\n\ndef test_price():\n    assert pkg.price(2) == 8\n"})
    shas["broken"] = branch(repo, "broken", {"tests/test_broken.py": "def test_never_passed():\n    assert 1 == 2\n"})
    shas["slow"] = branch(repo, "slow", {"tests/test_slow.py": "import time\n\n\ndef test_slow():\n    time.sleep(600)\n"})
    shas["silent"] = branch(repo, "silent", {"pkg.py": PKG.replace("n * 2", "n * 5")})
    shas["old"] = branch(repo, "old", {"tests/test_old.py": "def test_old():\n    assert True\n"}, start="trunk")
    git(repo, "checkout", "-q", "base")
    return shas


def state(repo: Path):
    """Everything about the repository a read-only rehearsal must leave alone, loose objects included."""
    objects = sorted(str(p.relative_to(repo)) for p in (repo / ".git" / "objects").rglob("*") if p.is_file())
    return (git(repo, "for-each-ref"), git(repo, "status", "--porcelain"), git(repo, "rev-parse", "HEAD"),
            git(repo, "worktree", "list"), git(repo, "stash", "list"), sorted(p.name for p in repo.iterdir()),
            (repo / ".git" / "index").read_bytes(), objects)


MODE = "supervised: network denied, environment scrubbed, filesystem confined by Landlock (scripted)"
REFUSED = ("acceptance confinement refused: worker OS filesystem isolation unavailable: Landlock alone does not "
           "isolate untrusted acceptance processes/network; bubblewrap is unavailable on this host")


def outcome(kind, file: str, timeout: int) -> dict:
    """One ``greg.workers.run_tests`` result of the given kind, shaped exactly as the real function shapes it."""
    base = {"argv": ["python", file], "seconds": 0.01, "network": "denied", "confinement": MODE,
            "filesystem": {"filesystem": "landlock", "abi": 7, "writable": ["(scripted)"]}}
    if isinstance(kind, tuple):                     # ("fail", [test names])
        names = kind[1]
        tail = "F\n" + "".join(f"FAILED {file}::{n} - assert\n" for n in names) + f"{len(names)} failed in 0.01s\n"
        return {**base, "returncode": 1, "passed": False, "tail": tail}
    if kind == "pass":
        return {**base, "returncode": 0, "passed": True, "tail": ".\n1 passed in 0.01s\n"}
    if kind == "timeout":
        return {**base, "returncode": -1, "passed": False, "tail": f"timed out after {timeout}s"}
    if kind == "refused":
        return {**base, "returncode": -1, "passed": False, "tail": REFUSED, "confinement": "refused",
                "filesystem": None}
    if kind == "collect-error":
        return {**base, "returncode": 2, "passed": False,
                "tail": f"ERROR {file} - ImportError: cannot import name 'gone'\n1 error in 0.01s\n"}
    if kind == "no-start":
        return {**base, "returncode": 4, "passed": False, "tail": "ImportError while loading conftest 'conftest.py'.\n"}
    if kind == "skipped":
        return {**base, "returncode": 0, "passed": True, "tail": "s\n1 skipped in 0.01s\n"}
    if kind == "none":
        return {**base, "returncode": 5, "passed": False, "tail": "\nno tests ran in 0.00s\n"}
    raise AssertionError(kind)


class Script:
    """``greg.workers.run_tests`` from a table: ``{test file: kind or function of the tree's name}``; anything not
    in the table passes. ``calls`` records (tree, file, the confinement setting it was asked for)."""

    def __init__(self, table: dict | None = None, default="pass"):
        self.table, self.default, self.calls = table or {}, default, []

    def __call__(self, tests, cwd, *, timeout, stop_check=None, confinement="required"):
        [argv] = tests
        file, tree = argv[-1], Path(cwd).name
        self.calls.append((tree, file, confinement))
        kind = self.table.get(file, self.default)
        return [outcome(kind(tree) if callable(kind) else kind, file, timeout)]


def breaks_with_steeper(tree: str):
    """``consumer``'s test as it really behaves: it fails wherever ``steeper`` is in the tree."""
    with_steeper = tree == "composed" or (tree.startswith("without-") and tree != "without-steeper")
    return ("fail", ["test_total"]) if with_steeper else "pass"
