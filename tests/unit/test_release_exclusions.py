"""Uncleared third-party data stays out of every release (review of #179, M19)."""
import importlib.util
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_release_exclusions", ROOT / "scripts/check_release_exclusions.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
LIST = json.loads((ROOT / "docs/collaboration/RELEASE-EXCLUSIONS.json").read_text())


def test_every_listed_path_is_tracked_frozen_evidence_and_every_source_is_uncleared():
    tracked = set(subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split())
    assert {e["path"] for e in LIST["paths"]} <= tracked
    assert {e["source"] for e in LIST["paths"]} == set(LIST["sources"])
    assert all(s["status"].startswith("uncleared") for s in LIST["sources"].values())


def test_no_unlisted_tracked_file_carries_a_marker_of_listed_data():
    """A new suite, result or log built from an uncleared source must join the list."""
    listed = {e["path"] for e in LIST["paths"]}
    ignore = ("docs/collaboration/", "docs/evidence/greg-mind-evidence-index.json", "tests/")
    found = set()
    for markers in LIST["markers"].values():
        for marker in markers:
            out = subprocess.run(["git", "grep", "-lF", marker, "--", "*.json", "*.log", "*.jsonl"], cwd=ROOT,
                                 capture_output=True, text=True).stdout.split()
            found |= {p for p in out if not p.startswith(ignore)}
    assert found - listed == set(), sorted(found - listed)


def test_the_package_ships_none_and_an_archive_that_carries_one_is_blocked(tmp_path):
    assert C.check(C.packaged()) == [] and C.main([]) == 0
    path = LIST["paths"][0]["path"]
    archive = tmp_path / "release.tar"
    with tarfile.open(archive, "w") as t:
        t.add(ROOT / path, arcname=f"release/{path}")
    assert C.check(C.members(archive)) == [path] and C.main(["--archive", str(archive)]) == 1
