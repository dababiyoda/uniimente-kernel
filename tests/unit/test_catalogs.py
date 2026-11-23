"""The document catalog lists every file once; the branch catalog classifies honestly."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import branch_catalog  # noqa: E402
import docs_catalog  # noqa: E402


def _tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return [f for f in out.stdout.splitlines() if f]


def test_every_document_is_catalogued_once():
    text = docs_catalog.build(ROOT)
    for f in _tracked():
        if not f.startswith("docs/") or f == docs_catalog.CATALOG:
            continue
        parts = f.split("/")
        if parts[1] == "evidence" and len(parts) > 4:
            # evidence is listed by run directory
            assert f"[`{'/'.join(parts[1:4])}`]" in text, f
        else:
            assert text.count(f"[`{f[5:]}`]({f[5:]})") == 1, f


def test_catalog_is_deterministic():
    assert docs_catalog.build(ROOT) == docs_catalog.build(ROOT)


def test_kind_rules_classify_known_names():
    assert docs_catalog.kind_of("deliberation-regular-review-20261105.json").startswith("Deliberation")
    assert docs_catalog.kind_of("INTEGRATION-196-HANDOFF-2026-10-22.md") == "Handoff"
    assert docs_catalog.date_of("CONTRIBUTOR-PAIN-POINTS-2026-11-05.md") == "2026-11-05"


def _run(cwd: Path, *args: str) -> str:
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
           "PATH": "/usr/bin:/bin", "HOME": str(cwd)}
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          check=True, env=env).stdout


def _commit(repo: Path, name: str, text: str) -> None:
    (repo / name).write_text(text)
    _run(repo, "add", name)
    _run(repo, "commit", "-qm", name)


def test_branch_classification(tmp_path):
    origin, work = tmp_path / "origin.git", tmp_path / "work"
    _run(tmp_path, "init", "-q", "--bare", str(origin))
    _run(tmp_path, "init", "-q", "-b", "line", str(work))
    _commit(work, "a", "a")
    for b in ("finished", "parked", "open", "closed", "picked"):
        _run(work, "branch", b)
    _run(work, "checkout", "-q", "finished"); _commit(work, "f", "f")
    for b, f in (("parked", "p"), ("open", "o"), ("closed", "c"), ("picked", "k")):
        _run(work, "checkout", "-q", b); _commit(work, f, f)
    _run(work, "checkout", "-q", "line")
    _run(work, "merge", "-q", "--no-ff", "-m", "take finished", "finished")
    _run(work, "cherry-pick", "picked")  # same change, different commit
    _run(work, "remote", "add", "origin", str(origin))
    _run(work, "push", "-q", "origin", "--all")
    _run(work, "fetch", "-q", "origin")
    pr = lambda n, ref, state, merged=None: {  # noqa: E731
        "number": n, "head": {"ref": ref}, "base": {"ref": "line"}, "state": state,
        "merged_at": merged, "title": ref}
    prs = [pr(1, "open", "open"), pr(2, "closed", "closed"), pr(3, "finished", "closed", "x")]
    got = {r["branch"]: r["status"] for r in branch_catalog.classify(work, prs, line="line")}
    assert got == {"line": "LINE", "finished": "INTEGRATED", "picked": "INTEGRATED",
                   "parked": "NO_PR", "open": "OPEN_PR", "closed": "CLOSED_UNMERGED"}


def test_conflicts_and_intake_queue(tmp_path):
    work = tmp_path / "w"
    _run(tmp_path, "init", "-q", "-b", "line", str(work))
    _commit(work, "a", "base\n")
    _run(work, "branch", "clash"); _run(work, "branch", "clean")
    _commit(work, "a", "line edit\n")
    _run(work, "checkout", "-q", "clash"); _commit(work, "a", "branch edit\n")
    _run(work, "checkout", "-q", "clean"); _commit(work, "b", "new file\n")
    _run(work, "checkout", "-q", "line")
    _run(work, "update-ref", "refs/remotes/origin/line", "line")
    for b in ("clash", "clean"):
        _run(work, "update-ref", f"refs/remotes/origin/{b}", b)
    rows = {r["branch"]: r for r in branch_catalog.classify(work, [], line="line")}
    assert rows["clash"]["conflicts"] == ["a"]
    assert rows["clean"]["conflicts"] == []
    assert [r["branch"] for r in branch_catalog.intake_queue(list(rows.values()), "line")] == ["clean"]
    # the check merges nothing: the line is where it was
    assert _run(work, "rev-parse", "line") == _run(work, "rev-parse", "origin/line")
