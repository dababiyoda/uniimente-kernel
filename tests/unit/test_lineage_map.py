"""scripts/lineage_map.py measures competing futures from git objects alone."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

from scripts import lineage_map


def git(repo: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, text=True, check=True).stdout.strip()


def commit(repo: Path, name: str, text: str) -> str:
    (repo / name).write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-qm", f"{name}: {text[:10]}")
    return git(repo, "rev-parse", "HEAD")


def test_tips_divergence_conflicts_and_drafts_off_the_base(tmp_path, monkeypatch):
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    base = commit(repo, "core.py", "base\n")
    stack_a = commit(repo, "a.py", "a\n")                       # #1: builds on the base
    stack_b = commit(repo, "core.py", "mind from line B\n")     # #2: builds on #1
    git(repo, "checkout", "-q", "-b", "c", base)
    sibling = commit(repo, "core.py", "mind from line C\n")     # #3: competes with #2 on core.py
    git(repo, "checkout", "-q", "--orphan", "d")
    git(repo, "rm", "-rfq", ".")
    elsewhere = commit(repo, "other.py", "rooted elsewhere\n")  # #4: does not contain the base
    monkeypatch.chdir(repo)
    out = lineage_map.measure(base, [{"number": 1, "sha": stack_a}, {"number": 2, "sha": stack_b},
                                     {"number": 3, "sha": sibling}, {"number": 4, "sha": elsewhere}])
    assert out["tips"] == [2, 3, 4]                              # #1 is inside #2's stack, not a tip
    assert out["not_on_base"] == [4]
    [pair] = [p for p in out["divergent_tip_pairs"] if p["tips"] == [2, 3]]
    assert pair["only_2"] == 2 and pair["only_3"] == 1 and pair["conflicting_files"] == 1
    assert pair["sample"] == ["core.py"]
    assert [2, 4] in out["unrelated_tip_pairs"] and [3, 4] in out["unrelated_tip_pairs"]
    rows = {r["number"]: r for r in out["prs"]}
    assert rows[2]["contains_base"] and rows[2]["ahead_of_base"] == 2 and not rows[4]["contains_base"]
