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


def _intake_repo(tmp_path):
    """main carries an integrator's tree; feature carries six commits it may or may not have absorbed."""
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    commit(repo, "core.py", "def core():\n    return 'base'\n")
    commit(repo, "old.py", "def legacy_helper():\n    return 'kept on main'\n")
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "-b", "feature")
    picked = commit(repo, "a.py", "def picked():\n    return 'cherry-picked verbatim'\n")
    ported = commit(repo, "b.py", "def ported():\n    return 'hand-ported with other context'\n")
    missing = commit(repo, "c.py", "def missing():\n    return 'never reached main'\n")
    commit(repo, "d.py", "def first_draft():\n    return 'rewritten later in the source'\n")
    commit(repo, "d.py", "def second_draft():\n    return 'the source head says this'\n")
    git(repo, "rm", "-q", "old.py")
    git(repo, "commit", "-qm", "drop legacy helper")
    feature = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "main")
    (repo / "b.py").write_text("# integrator's header\n\ndef ported():\n    return 'hand-ported with other context'\n")
    git(repo, "add", "b.py")
    git(repo, "commit", "-qm", "port b by hand")                            # different patch, same added text
    git(repo, "cherry-pick", picked)        # same patch on a new parent (on the old parent, within one second,
                                            # git would recreate the identical commit and make it an ancestor)
    (repo / "d.py").write_text("def second_draft():\n    return 'the source head says this'\n")
    git(repo, "add", "d.py")
    git(repo, "commit", "-qm", "take d at the source head")
    return repo, base, feature, {"picked": picked, "ported": ported, "missing": missing}


def test_intake_judges_behaviour_not_ancestry(tmp_path, monkeypatch):
    repo, _, feature, shas = _intake_repo(tmp_path)
    monkeypatch.chdir(repo)
    lineage_map._blob_lines.cache_clear()
    lineage_map._test_names.cache_clear()
    out = lineage_map.intake("main", feature)
    by_subject = {c["subject"].split(":")[0]: c for c in out["commits"]}
    assert by_subject["a.py"]["verdict"] == "EQUIVALENT_PATCH"               # cherry-pick found by patch-id
    assert by_subject["b.py"]["verdict"] == "CONTENT_PRESENT"                # hand port found by hunk text
    assert by_subject["c.py"]["verdict"] == "MISSING" and by_subject["c.py"]["missing_files"] == ["c.py"]
    drafts = [c for c in out["commits"] if c["subject"].startswith("d.py")]
    assert [c["verdict"] for c in drafts] == ["SUPERSEDED_IN_SOURCE", "CONTENT_PRESENT"]
    # main still holds the block the source deleted: that deletion is unported, not "contained"
    assert by_subject["drop legacy helper"]["verdict"] == "MISSING"
    assert out["verdict"] == "UNPORTED_DELTA"
    assert sorted(out["unported"]) == sorted([shas["missing"][:12], by_subject["drop legacy helper"]["sha"]])


def test_intake_counts_ancestry_and_unrelated_roots(tmp_path, monkeypatch):
    repo, base, _, _ = _intake_repo(tmp_path)
    monkeypatch.chdir(repo)
    lineage_map._blob_lines.cache_clear()
    assert lineage_map.intake("main", base)["verdict"] == "CONTAINED_BY_ANCESTRY"
    git(repo, "checkout", "-q", "--orphan", "elsewhere")
    git(repo, "rm", "-rfq", ".")
    other = commit(repo, "x.py", "unrelated root\n")
    assert lineage_map.intake("main", other)["verdict"] == "UNRELATED"


def test_intake_does_not_guess_from_trivial_or_absent_deletions(tmp_path, monkeypatch):
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    commit(repo, "x.py", "def f():\n    value = compute_something_long()\n    return value\n")
    git(repo, "checkout", "-q", "-b", "feature")
    commit(repo, "x.py", "def f():\n    return compute_something_long()\n}\n")   # rewrite + a trivial line
    feature = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "main")
    commit(repo, "x.py", "def f():\n    return compute_something_long()\n")      # integrator's own rewrite
    monkeypatch.chdir(repo)
    lineage_map._blob_lines.cache_clear()
    [row] = lineage_map.intake("main", feature)["commits"]
    assert row["verdict"] == "CONTENT_PRESENT"     # the long added line is there; "}" alone proves nothing


def test_intake_credits_a_rewritten_port_whose_tests_survive_but_not_one_that_dropped_them(tmp_path, monkeypatch):
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    commit(repo, "core.py", "def core():\n    return 'base'\n")
    git(repo, "checkout", "-q", "-b", "feature")
    kept = commit(repo, "test_guard.py", "def test_the_guard_refuses_a_stale_grant():\n    assert refuse(stale_grant())\n")
    dropped = commit(repo, "test_other.py", "def test_an_overspend_is_booked():\n    assert book(overspend())\n")
    git(repo, "checkout", "-q", "main")
    commit(repo, "test_guard.py", "def test_the_guard_refuses_a_stale_grant():\n    grant = stale_grant()\n"
                                  "    assert refuse(grant), 'integrator rewrote the body'\n")
    monkeypatch.chdir(repo)
    lineage_map._blob_lines.cache_clear()
    lineage_map._test_names.cache_clear()
    rows = {c["sha"]: c for c in lineage_map.intake("main", "feature")["commits"]}
    assert rows[kept[:12]]["verdict"] == "TESTS_PRESENT" and rows[kept[:12]]["tests"] == {"added": 1, "present": 1}
    assert rows[dropped[:12]]["verdict"] == "MISSING" and rows[dropped[:12]]["tests"] == {"added": 1, "present": 0}
