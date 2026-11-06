#!/usr/bin/env python3
"""Catalog every remote branch: what it holds, and whether that work is on the live line.

Read-only. It deletes, moves and pushes nothing. It answers, for each branch:

- is all of its work already on the integration line? (``INTEGRATED``)
- if not, how many commits exist only there, and which pull request carries them?

Statuses, in the order the catalog lists them:

``LINE``             the integration line itself, or ``main``
``OPEN_PR``          work in an open pull request, not yet on the line
``NO_PR``            unintegrated commits that no pull request carries
``MERGED_ELSEWHERE`` its pull request merged into another base, but the commits
                     are not on the line
``CLOSED_UNMERGED``  its pull request closed without merging; the commits remain
                     on the branch (nothing is lost; it is parked, not deleted)
``INTEGRATED``       every commit is already on the integration line

Usage::

    git fetch origin '+refs/heads/*:refs/remotes/origin/*'
    python scripts/branch_catalog.py --github dababiyoda/uniimente-kernel \\
        --markdown docs/collaboration/BRANCH-CATALOG-<date>.md --json out.json

Without ``--github`` the pull-request columns are empty and branches are
classified from git alone.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

LINE = "claude/greg-full-machine-completion-whgiee"
ORDER = ("LINE", "OPEN_PR", "NO_PR", "MERGED_ELSEWHERE", "CLOSED_UNMERGED", "INTEGRATED")
MEANING = {
    "LINE": "The integration line and `main`.",
    "OPEN_PR": "Active work: an open pull request whose commits are not on the line yet.",
    "NO_PR": "Commits on no pull request and not on the line. Someone should open a PR, fold them in, or record why they are parked.",
    "MERGED_ELSEWHERE": "Merged into another base (an older trunk or a stacked PR), but not on the line.",
    "CLOSED_UNMERGED": "Pull request closed without merging. The commits stay on the branch as history.",
    "INTEGRATED": "Finished: every change is already on the integration line (merge commits and cherry-picked copies count as present). Kept, not deleted.",
}


def _git(*args: str, root: Path = ROOT) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True,
                          capture_output=True, text=True).stdout


def remote_branches(root: Path = ROOT) -> list[tuple[str, str, str]]:
    """(name, tip sha, last commit date) for every ``origin/*`` branch."""
    out = _git("for-each-ref", "refs/remotes/origin",
               "--format=%(refname:short)\t%(objectname)\t%(committerdate:short)", root=root)
    rows = []
    for line in out.splitlines():
        name, sha, date = line.split("\t")
        name = name.removeprefix("origin/")
        if name == "HEAD" or name == "origin":
            continue
        rows.append((name, sha, date))
    return rows


def pull_requests(repo: str, token: str | None) -> list[dict]:
    from repo_review import _get  # one GitHub client for both instruments
    prs, page = [], 1
    while True:
        batch = _get(f"https://api.github.com/repos/{repo}/pulls?state=all&per_page=100&page={page}", token)
        prs += batch
        if len(batch) < 100:
            return prs
        page += 1


def classify(root: Path = ROOT, prs: list[dict] | None = None, line: str = LINE) -> list[dict]:
    line_ref = f"origin/{line}"
    by_head: dict[str, list[dict]] = {}
    for p in prs or []:
        by_head.setdefault(p["head"]["ref"], []).append(p)
    rows = []
    for name, sha, date in remote_branches(root):
        # Commits whose change is not on the line: merges and patch-equivalent
        # (cherry-picked or rebased) commits do not count as unfinished work.
        unique = int(_git("rev-list", "--count", "--no-merges", "--cherry-pick", "--right-only",
                          f"{line_ref}...{sha}", root=root).strip())
        cands = sorted(by_head.get(name, []), key=lambda p: p["number"], reverse=True)
        pr = next((p for p in cands if p["state"] == "open"), cands[0] if cands else None)
        if name in (line, "main"):
            status = "LINE"
        elif unique == 0:
            status = "INTEGRATED"
        elif pr is None:
            status = "NO_PR"
        elif pr["state"] == "open":
            status = "OPEN_PR"
        elif pr.get("merged_at"):
            status = "MERGED_ELSEWHERE"
        else:
            status = "CLOSED_UNMERGED"
        rows.append({
            "branch": name, "status": status, "unique_commits": unique, "last_commit": date,
            "pr": pr["number"] if pr else None, "pr_state": (pr and ("merged" if pr.get("merged_at") else pr["state"])),
            "pr_base": pr["base"]["ref"] if pr else None, "title": pr["title"] if pr else "",
        })
    rows.sort(key=lambda r: (ORDER.index(r["status"]), r["last_commit"]), reverse=False)
    # newest first within each status
    out = []
    for s in ORDER:
        out += sorted((r for r in rows if r["status"] == s), key=lambda r: r["last_commit"], reverse=True)
    return out


def markdown(rows: list[dict], line: str = LINE, repo: str | None = None) -> str:
    counts = {s: sum(r["status"] == s for r in rows) for s in ORDER}
    head = _git("rev-parse", "--short", f"origin/{line}").strip()
    lines = [
        "# Branch catalog",
        "",
        f"Generated by `scripts/branch_catalog.py` against `{line}` at `{head}`. "
        "A dated snapshot: regenerate it, do not hand-edit it. Nothing was deleted or moved to produce it.",
        "",
        "| Status | Branches | Meaning |", "|---|---:|---|",
    ]
    lines += [f"| `{s}` | {counts[s]} | {MEANING[s]} |" for s in ORDER]
    lines += [f"| **Total** | **{len(rows)}** | |", ""]
    url = f"https://github.com/{repo}/pull/" if repo else None
    for s in ORDER:
        group = [r for r in rows if r["status"] == s]
        if not group:
            continue
        lines += [f"## `{s}` ({len(group)})", "", MEANING[s], "",
                  "| Branch | Last commit | Commits not on the line | PR | Title |", "|---|---|---:|---|---|"]
        for r in group:
            pr = ""
            if r["pr"]:
                pr = f"[#{r['pr']}]({url}{r['pr']})" if url else f"#{r['pr']}"
                pr += f" {r['pr_state']}" + (f" → `{r['pr_base']}`" if r["pr_base"] else "")
            title = r["title"].replace("|", "\\|")
            lines.append(f"| `{r['branch']}` | {r['last_commit']} | {r['unique_commits']} | {pr} | {title} |")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--github", metavar="OWNER/REPO")
    ap.add_argument("--line", default=LINE)
    ap.add_argument("--markdown", type=Path)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    prs = pull_requests(a.github, os.environ.get("GITHUB_TOKEN")) if a.github else None
    rows = classify(prs=prs, line=a.line)
    md = markdown(rows, a.line, a.github)
    if a.markdown:
        a.markdown.write_text(md + "\n")
    if a.json:
        a.json.write_text(json.dumps(rows, indent=1) + "\n")
    if not (a.markdown or a.json):
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
