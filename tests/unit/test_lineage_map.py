"""scripts/lineage_map.py measures competing futures from git objects alone."""
from __future__ import annotations

import json
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


# --- place: section 53's twelve dispositions, from the live open-PR list -----------------------------------

CANON = "claude/canonical"


def _live(*rows):
    return [{"number": n, "sha": sha, "ref": ref, "base": base, "title": f"PR {n}"} for n, sha, ref, base in rows]


NINE_FILLED = {k: f"answer {k}" for k in lineage_map.NINE}


def test_place_derives_from_facts_inherits_reviewed_placements_and_reports_the_rest():
    live = _live((1, "a" * 40, CANON, "main"), (2, "b" * 40, "child", CANON), (3, "c" * 40, "grandchild", "child"),
                 (4, "d" * 40, "absorbed", "main"), (5, "e" * 40, "old", "main"), (6, "f" * 40, "orphan", "main"),
                 (7, "1" * 40, "judged", "main"))
    verdicts = {1: "CONTAINED_BY_ANCESTRY", 2: "UNPORTED_DELTA", 3: "UNPORTED_DELTA", 4: "BEHAVIOUR_CONTAINED",
                5: "UNPORTED_DELTA", 6: "UNPORTED_DELTA", 7: "UNPORTED_DELTA"}
    inheritance = {"placements": [
        {"id": "x.mechanism", "lineage": ["#5", "greg/x.py"], "classification": "HISTORICAL_EVIDENCE"},
        {"id": "x.active", "lineage": ["#5"], "classification": "PORTABLE_MECHANISM"}]}
    record = {"placements": [{"number": 7, "head_sha": "1" * 40, "disposition": "NEEDS FOUNDER DECISION",
                              "decision": "sign or close", "basis": "awaiting the founder's signature"}]}
    out = lineage_map.place(live, CANON, verdicts, inheritance, record)
    got = {p["pr"]: (p["disposition"], p["source"]) for p in out["placements"]}
    assert got[1] == ("CANONICAL ACTIVE", "derived")            # the canonical head, whatever intake says
    assert got[2] == ("STACKED NEXT", "derived") and got[3] == ("STACKED NEXT", "derived")
    assert got[4] == ("EVIDENCE ONLY", "derived")
    assert got[5] == ("PORT MECHANISM", "inherited")             # the most active of its two lineages
    assert got[7] == ("NEEDS FOUNDER DECISION", "recorded")
    assert got[6] == (None, "unplaced")
    assert [(v["pr"], v["kind"]) for v in out["violations"]] == [(6, "unplaced")]
    assert out["open"] == 7 and out["counts"]["STACKED NEXT"] == 2


def test_place_refuses_stale_moved_contradicted_and_incomplete_records():
    live = _live((1, "a" * 40, CANON, "main"), (2, "b" * 40, "moved", "main"), (3, "c" * 40, "on", CANON),
                 (4, "d" * 40, "fut", "main"), (5, "e" * 40, "fake", "main"), (6, "f" * 40, "ask", "main"))
    record = {"placements": [
        {"number": 9, "head_sha": "9" * 40, "disposition": "HISTORICAL", "basis": "closed long ago"},
        {"number": 2, "head_sha": "0" * 40, "disposition": "PORT MECHANISM", "basis": "decided on an older head"},
        {"number": 3, "head_sha": "c" * 40, "disposition": "PORT MECHANISM", "basis": "but it is stacked"},
        {"number": 4, "head_sha": "d" * 40, "disposition": "FUTURE NODE", "basis": "no node named"},
        {"number": 5, "head_sha": "e" * 40, "disposition": "STACKED NEXT", "basis": "claims a stack it is not on"},
        {"number": 6, "head_sha": "f" * 40, "disposition": "NEEDS FOUNDER DECISION", "basis": "asks nothing"}]}
    out = lineage_map.place(live, CANON, {}, {}, record)
    kinds = sorted((v["pr"], v["kind"]) for v in out["violations"])
    assert kinds == [(2, "moved"), (3, "contradicted"), (4, "incomplete"), (5, "contradicted"),
                     (6, "incomplete"), (9, "stale_record")]


def test_place_lets_a_pr_close_only_after_section_53s_nine_extractions():
    live = _live((1, "a" * 40, CANON, "main"), (2, "b" * 40, "done", "main"), (3, "c" * 40, "half", "main"))
    partial = dict(NINE_FILLED, negative_evidence=" ")
    record = {"placements": [
        {"number": 2, "head_sha": "b" * 40, "disposition": "SUPERSEDED IMPLEMENTATION", "basis": "replaced",
         "closing": True, "nine": NINE_FILLED},
        {"number": 3, "head_sha": "c" * 40, "disposition": "HISTORICAL", "basis": "kept for history",
         "closing": True, "nine": partial}]}
    out = lineage_map.place(live, CANON, {}, {}, record)
    rows = {p["pr"]: p for p in out["placements"]}
    assert rows[2]["close_ready"] and not rows[3]["close_ready"]
    [violation] = out["violations"]
    assert violation["pr"] == 3 and violation["kind"] == "close_without_extraction"
    assert violation["detail"] == "missing: negative_evidence"
    assert out["closing_not_extracted"] == [3]


def test_every_inheritance_class_maps_to_a_section_53_disposition():
    assert set(lineage_map.FROM_CLASS.values()) <= set(lineage_map.DISPOSITIONS)
    assert len(lineage_map.DISPOSITIONS) == 12 and len(lineage_map.NINE) == 9
    assert set(lineage_map.ACTIVITY) | {"CANONICAL ACTIVE"} == set(lineage_map.DISPOSITIONS)


def test_the_reviewed_inheritance_records_classes_all_map():
    from pathlib import Path
    record = json.loads((Path(__file__).resolve().parents[2]
                         / "docs/collaboration/DEVELOPMENTAL-INHERITANCE-2026-09-30.json").read_text())
    assert set(record["classes"]) == set(lineage_map.FROM_CLASS)


def test_place_puts_a_branch_without_a_pr_with_the_open_pr_that_contains_it():
    live = _live((1, "a" * 40, CANON, "main"), (2, "b" * 40, "work", CANON))
    live += [{"number": "branch:review-of-2", "sha": "2" * 40, "ref": "review-of-2", "base": None},
             {"number": "branch:lost", "sha": "3" * 40, "ref": "lost", "base": None}]
    out = lineage_map.place(live, CANON, {}, {}, {}, {"branch:review-of-2": [2], "branch:lost": []})
    rows = {p["pr"]: p for p in out["placements"]}
    assert rows["branch:review-of-2"]["disposition"] == "STACKED NEXT"
    assert "contained in open #2" in rows["branch:review-of-2"]["basis"]
    assert not rows["branch:review-of-2"]["close_ready"]      # deleting a branch is a close: extract first
    assert [(v["pr"], v["kind"]) for v in out["violations"]] == [("branch:lost", "unplaced")]
    assert [p["pr"] for p in out["placements"]][:2] == [1, 2]   # PRs first, then branches
