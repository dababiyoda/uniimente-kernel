"""What an admission run records about its own source (greg/cognition/genomes/admission.py), checked without
running ``--freeze`` or ``--run``: no held-out instance is generated here.

Found by the 2026-10-15 independent review (E9): the v3 results.json recorded ``source_commit`` but not whether the
frozen files were the committed ones, so its README's "clean worktree" rested on the operator's word. The freeze
digests bind the bytes a run executes; ``source_dirty`` binds them to the recorded commit, as P8's record does.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

from greg.cognition.genomes import admission

GIT = ["git", "-c", "user.email=test@example.invalid", "-c", "user.name=test", "-c", "commit.gpgsign=false"]


def _repo(root: Path, files: dict) -> Path:
    root.mkdir()
    subprocess.run([*GIT, "init", "-q"], cwd=root, check=True)
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "base"], cwd=root, check=True)
    return root


def test_source_dirty_names_every_frozen_file_whose_bytes_are_not_its_commit(tmp_path):
    repo = _repo(tmp_path / "repo", {"a.py": "a = 1\n", "pkg/b.py": "b = 1\n", "data.bin": "x"})
    frozen = ["pkg/b.py", "a.py", "data.bin"]
    assert admission.source_dirty(frozen, root=repo) == []                       # a clean tree records nothing
    (repo / "a.py").write_text("a = 2\n")                                         # modified in the worktree
    (repo / "c.py").write_text("c = 1\n")                                         # untracked, never committed
    assert admission.source_dirty([*frozen, "c.py"], root=repo) == ["a.py", "c.py"]
    (repo / "pkg/b.py").write_text("b = 2\n")
    subprocess.run([*GIT, "add", "pkg/b.py"], cwd=repo, check=True)               # staged is still not committed
    assert admission.source_dirty([*frozen, "c.py"], root=repo) == ["a.py", "c.py", "pkg/b.py"]
    (repo / "a.py").write_text("a = 1\n")                                         # restored bytes are clean again
    assert admission.source_dirty(frozen, root=repo) == ["pkg/b.py"]


def test_source_dirty_names_every_path_when_git_cannot_tell(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))                # no repository above tmp_path
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "a.py").write_text("a = 1\n")
    assert admission.source_dirty(["a.py"], root=plain) == ["a.py"]              # not a repository
    repo = _repo(tmp_path / "repo", {"a.py": "a = 1\n"})
    assert admission.source_dirty(["a.py", "gone.py"], root=repo) == ["a.py", "gone.py"]   # an unreadable path


def test_the_results_header_records_the_dirty_state_of_the_frozen_files(tmp_path):
    frozen = {"inputs": {"code": {"greg/cognition/genomes/admission.py": "sha256:x",
                                  "tools/offline_test.py": "sha256:y"}}}
    (tmp_path / "freeze.json").write_text(json.dumps(frozen))
    header = admission.report_header(tmp_path, frozen)
    assert header["source_dirty"] == admission.source_dirty(frozen["inputs"]["code"])
    assert set(header["source_dirty"]) <= set(frozen["inputs"]["code"])
    assert header["rule"] == admission.RULE and header["genomes"] == {} and header["source_commit"]
