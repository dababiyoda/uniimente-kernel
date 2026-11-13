"""The two Mind lineages' frozen-path collisions stay identified, never rewritten (INTENT-20261014-MIND-LINEAGE-CONVERGENCE).

A frozen artifact's identity is (source commit, original path, sha256). The tree may hold either lineage's content at
a colliding path, never a third, edited version. Where the commit object is present, the recorded digest must be
the digest of that commit's file.
"""
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/collaboration/MIND-LINEAGE-SOURCE-MANIFEST-2026-10-14.json"


def manifest():
    return json.loads(MANIFEST.read_text())


def test_every_collision_names_both_lineages_with_full_identities():
    m = manifest()
    assert set(m["lineages"]) == {"pr155", "pr158"}
    assert len(m["frozen_path_collisions"]) == 8
    for row in m["frozen_path_collisions"]:
        assert set(row["lineages"]) == {"pr155", "pr158"}
        digests = {v["sha256"] for v in row["lineages"].values()}
        assert len(digests) == 2, f"{row['path']}: the lineages' contents are recorded as identical"
        for v in row["lineages"].values():
            assert len(v["added_in"]) == len(v["last_changed_in"]) == 40 and len(v["sha256"]) == 64


def test_the_tree_holds_one_lineages_content_at_each_colliding_path_never_a_rewrite():
    for row in manifest()["frozen_path_collisions"]:
        path = ROOT / row["path"]
        if not path.exists():
            continue                                   # a converged tree may cite the path without carrying it
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest in {v["sha256"] for v in row["lineages"].values()}, f"{row['path']} was rewritten"


def test_recorded_digests_match_their_commits_where_the_objects_are_present():
    checked = 0
    for row in manifest()["frozen_path_collisions"]:
        for v in row["lineages"].values():
            shown = subprocess.run(["git", "show", f"{v['last_changed_in']}:{row['path']}"], cwd=ROOT,
                                   capture_output=True)
            if shown.returncode:
                continue                               # shallow clone or the other lineage's objects not fetched
            assert hashlib.sha256(shown.stdout).hexdigest() == v["sha256"], row["path"]
            checked += 1
    shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT, capture_output=True, text=True)
    if checked < 8 and shallow.stdout.strip() != "false":
        pytest.skip("shallow clone: the lineage commits are not available")
    assert checked >= 8                                 # with full history, at least this branch's own lineage
