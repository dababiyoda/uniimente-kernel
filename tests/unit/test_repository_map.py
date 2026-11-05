"""The repository map cannot silently drift.

Every top-level directory must (1) carry a README.md saying what it is and
(2) appear in the root README "Layout" table. A new directory without both is
an undocumented organ — the exact navigation debt INTENT-0027 targets.
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Hidden/tooling directories are not part of the institutional layout.
NOT_LAYOUT = {".github", ".git"}


def _top_level_dirs():
    try:
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                                 text=True, check=True).stdout.splitlines()
        dirs = {p.split("/", 1)[0] for p in tracked if "/" in p}
    except (OSError, subprocess.CalledProcessError):
        dirs = {p.name for p in ROOT.iterdir() if p.is_dir()}
    return sorted(d for d in dirs if d not in NOT_LAYOUT and not d.startswith("."))


def _layout_section():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    start = text.index("## Layout")
    end = text.index("\n## ", start + 1)
    return text[start:end]


def test_every_top_level_directory_has_a_readme():
    missing = [d for d in _top_level_dirs() if not (ROOT / d / "README.md").is_file()]
    assert not missing, f"add a README.md to: {missing}"


def test_every_top_level_directory_is_in_the_layout_table():
    listed = set(re.findall(r"`/([A-Za-z0-9_.-]+)`", _layout_section()))
    missing = [d for d in _top_level_dirs() if d not in listed]
    assert not missing, f"add rows to README.md ## Layout for: {missing}"


def test_layout_table_names_no_directory_that_does_not_exist():
    listed = set(re.findall(r"`/([A-Za-z0-9_.-]+)`", _layout_section()))
    ghosts = sorted(d for d in listed if not (ROOT / d).is_dir())
    assert not ghosts, f"README.md ## Layout lists missing directories: {ghosts}"


def test_docs_index_lists_every_top_level_document():
    index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    docs = sorted(p.name for p in (ROOT / "docs").iterdir()
                  if p.is_file() and p.name != "README.md")
    missing = [name for name in docs if name not in index]
    assert not missing, f"add to docs/README.md: {missing}"
