"""Measure competing branch futures: which open drafts build on the converged base, which are tips,
how far the tips have diverged from each other, and which files would conflict if merged.

One GREG (INTENT-2026-09-30-OPUS-MAXIMUS-CONVERGENCE) needs this measured, not asserted. Input is a
JSON list of {"number", "sha"} (for example from the GitHub pulls API); the commits must already be
fetched. Output is JSON on stdout. Read-only: it never checks out, merges or pushes anything.

    python scripts/lineage_map.py --base <sha> --prs prs.json
    python scripts/lineage_map.py --base <destination sha> --prs prs.json --intake

--intake answers the integrator's question instead: which of each head's commits outside the destination's
history still carry text the destination lacks (equivalent patch, hunk presence, test identity, superseded in
source).
"""
from __future__ import annotations

import argparse
import functools
import re
from itertools import combinations
import json
import subprocess
import sys


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def is_ancestor(a: str, b: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], capture_output=True).returncode == 0


def conflicts(a: str, b: str) -> list[str]:
    """Files git would leave conflicted when merging b into a (git >= 2.38 merge-tree)."""
    out = subprocess.run(["git", "merge-tree", "--write-tree", "--name-only", "--no-messages", a, b],
                         capture_output=True, text=True)
    if out.returncode not in (0, 1):
        raise RuntimeError(out.stderr.strip())
    return [line for line in out.stdout.splitlines()[1:] if line.strip()]


def measure(base: str, prs: list[dict]) -> dict:
    shas = {int(p["number"]): p["sha"] for p in prs}
    rows = {n: {"number": n, "sha": s[:12], "contains_base": is_ancestor(base, s),
                "ahead_of_base": int(git("rev-list", "--count", f"{base}..{s}"))} for n, s in shas.items()}
    tips = sorted(n for n, s in shas.items() if not any(m != n and s != t and is_ancestor(s, t)
                                                      for m, t in shas.items()))
    pairs, unrelated = [], []
    for x, y in combinations(tips, 2):
        found = subprocess.run(["git", "merge-base", shas[x], shas[y]], capture_output=True, text=True)
        if found.returncode:                       # no common history: not a merge, a second root
            unrelated.append([x, y])
            continue
        files = conflicts(shas[x], shas[y])
        pairs.append({"tips": [x, y], f"only_{x}": int(git("rev-list", "--count", f"{shas[y]}..{shas[x]}")),
                      f"only_{y}": int(git("rev-list", "--count", f"{shas[x]}..{shas[y]}")),
                      "merge_base": found.stdout.strip()[:12],
                      "conflicting_files": len(files), "sample": files[:8]})
    return {"base": base[:12], "prs": [rows[n] for n in sorted(rows, reverse=True)], "tips": tips,
            "not_on_base": sorted(n for n, r in rows.items() if not r["contains_base"]),
            "divergent_tip_pairs": [p for p in pairs if p["conflicting_files"]],
            "unrelated_tip_pairs": unrelated,
            "reality": "measured from git objects at the given SHAs; titles, intent and quality are not judged"}


# --- Intake: is a source head's behaviour already in the destination? -----------------------------------
# Ancestry alone cannot answer this (issue #96: "do not count ancestry alone as proof that ported behavior is
# missing"). An integrator cherry-picks, hand-ports and resolves merges, so a commit outside the destination's
# history may still be fully present. Each source commit is judged on its own patch, then on its own hunks.

TRIVIAL_LINE = 4           # shorter stripped lines ("}", "),", "];") are layout, not content
MIN_HUNK_CHARS = 8          # a hunk whose added text is shorter than this ("}", "pass") proves nothing either way


@functools.lru_cache(maxsize=None)
def _blob_lines(rev: str, path: str) -> tuple[str, ...] | None:
    out = subprocess.run(["git", "show", f"{rev}:{path}"], capture_output=True)
    if out.returncode:
        return None                                # the file does not exist at that revision
    return tuple(line.strip() for line in out.stdout.decode("utf-8", "replace").splitlines())


def _has_block(haystack: tuple[str, ...], block: list[str]) -> bool:
    """True when the block's substantive lines appear in order and contiguously among the haystack's.

    Blank lines and bare punctuation ("}", "),", "else:") are dropped from both sides: they move freely when an
    integrator re-wraps code, and they carry no behaviour a reader could attribute to the source commit."""
    needle = [line for line in block if len(line) >= TRIVIAL_LINE]
    hay = [line for line in haystack if len(line) >= TRIVIAL_LINE]
    if not needle:
        return False
    first, size = needle[0], len(needle)
    return any(hay[i:i + size] == needle for i, line in enumerate(hay) if line == first)


def _hunks(sha: str) -> list[dict]:
    """The first-parent diff of one commit, as hunks of stripped added and removed lines (no context)."""
    raw = subprocess.run(["git", "diff", "-U0", "--no-renames", "--no-color", "--no-ext-diff", f"{sha}^", sha],
                         capture_output=True).stdout.decode("utf-8", "replace")
    hunks, path, current = [], None, None
    for line in raw.splitlines():
        if line.startswith("diff --git "):
            path, current = None, None
        elif line.startswith("--- ") and current is None:
            path = None if line == "--- /dev/null" else line[6:]       # a deleted file keeps its old name
        elif line.startswith("+++ ") and current is None:
            path = line[6:] if line != "+++ /dev/null" else path
        elif line.startswith("@@"):
            current = {"path": path, "added": [], "removed": []}
            hunks.append(current)
        elif current is not None and line[:1] in "+-" and not line.startswith(("+++ ", "--- ")):
            current["added" if line[0] == "+" else "removed"].append(line[1:].strip())
        elif line.startswith("Binary files") and path is None:
            hunks.append({"path": line.split(" and ")[-1].removeprefix("b/").removesuffix(" differ"),
                          "added": [], "removed": [], "binary": True})
    return [h for h in hunks if h.get("path")]


def _patch_ids(rev_range: str) -> dict[str, str]:
    """patch-id --stable -> commit, for every non-merge commit in a range."""
    log = subprocess.run(["git", "log", "-p", "--no-merges", "--no-color", "--no-ext-diff", rev_range],
                         capture_output=True).stdout
    ids = subprocess.run(["git", "patch-id", "--stable"], input=log, capture_output=True).stdout.decode()
    return {pid: commit for pid, commit in (line.split() for line in ids.splitlines() if line.strip())}


def _judge_hunk(hunk: dict, source: str, dest: str) -> str:
    if hunk.get("binary"):
        return "undecidable"
    added = [line for line in hunk["added"] if line]
    if sum(len(line) for line in added) >= MIN_HUNK_CHARS:
        if not _has_block(_blob_lines(source, hunk["path"]) or (), added):
            return "superseded"                    # the source itself rewrote this later: its head is the claim
        dest_lines = _blob_lines(dest, hunk["path"])
        if dest_lines is None:
            return "missing"
        return "present" if _has_block(dest_lines, added) else "missing"
    removed = [line for line in hunk["removed"] if line]
    if not added and sum(len(line) for line in removed) >= MIN_HUNK_CHARS:
        # A deletion is evidence only when its block still stands in the destination and is gone at the source
        # head. Its absence from the destination proves nothing: the block may never have been there.
        dest_lines = _blob_lines(dest, hunk["path"])
        if dest_lines is not None and _has_block(dest_lines, removed) and not _has_block(
                _blob_lines(source, hunk["path"]) or (), removed):
            return "missing"
    return "undecidable"


_TEST_DEF = re.compile(r"^\+\s*(?:async\s+)?def\s+(test_\w+)", re.M)


@functools.lru_cache(maxsize=None)
def _test_names(rev: str) -> frozenset[str]:
    """Every pytest function name defined anywhere in a revision's tree."""
    out = subprocess.run(["git", "grep", "-h", "-o", "-E", r"def test_[A-Za-z0-9_]+", rev, "--", "*.py"],
                         capture_output=True, text=True).stdout
    return frozenset(line.split()[-1] for line in out.splitlines())


def _added_tests(sha: str) -> set[str]:
    diff = subprocess.run(["git", "diff", "--no-color", "--no-ext-diff", f"{sha}^", sha, "--", "*.py"],
                          capture_output=True).stdout.decode("utf-8", "replace")
    return set(_TEST_DEF.findall(diff))


def intake(dest: str, source: str) -> dict:
    """Which of `source`'s commits outside `dest`'s history still carry behaviour `dest` lacks."""
    dest, source = git("rev-parse", dest), git("rev-parse", source)
    found = subprocess.run(["git", "merge-base", dest, source], capture_output=True, text=True)
    if found.returncode:
        return {"source": source[:12], "dest": dest[:12], "verdict": "UNRELATED", "commits": []}
    base = found.stdout.strip()
    if is_ancestor(source, dest):
        return {"source": source[:12], "dest": dest[:12], "merge_base": base[:12], "verdict": "CONTAINED_BY_ANCESTRY",
                "commits": [], "merges_not_judged": 0}
    dest_ids = _patch_ids(f"{base}..{dest}")
    candidates = git("rev-list", "--reverse", "--no-merges", f"{dest}..{source}").split()
    merges = int(git("rev-list", "--count", "--merges", f"{dest}..{source}"))
    source_ids = {commit: pid for pid, commit in _patch_ids(f"{dest}..{source}").items()}
    commits = []
    for sha in candidates:
        row = {"sha": sha[:12], "subject": git("log", "-1", "--format=%s", sha)[:100]}
        if source_ids.get(sha) in dest_ids:
            row.update(verdict="EQUIVALENT_PATCH", dest_commit=dest_ids[source_ids[sha]][:12])
            commits.append(row)
            continue
        judged = [(h["path"], _judge_hunk(h, source, dest)) for h in _hunks(sha)]
        tally = {k: sum(1 for _, v in judged if v == k) for k in ("present", "missing", "superseded", "undecidable")}
        added_tests = _added_tests(sha)
        present_tests = added_tests & _test_names(dest)
        if tally["missing"] and added_tests and present_tests == added_tests:
            # Second, independent signal: the text was rewritten, yet every test the commit added exists at the
            # destination under its own name. A port that kept its tests; the integrator confirms the behaviour.
            verdict = "TESTS_PRESENT"
        elif tally["missing"] and tally["present"]:
            verdict = "PARTIAL"
        elif tally["missing"]:
            verdict = "MISSING"
        elif tally["present"]:
            verdict = "CONTENT_PRESENT"
        elif tally["superseded"]:
            verdict = "SUPERSEDED_IN_SOURCE"
        else:
            verdict = "UNDECIDABLE"
        row.update(verdict=verdict, hunks=tally, tests={"added": len(added_tests), "present": len(present_tests)},
                   missing_files=sorted({p for p, v in judged if v == "missing"})[:12])
        commits.append(row)
    unported = [c["sha"] for c in commits if c["verdict"] in ("MISSING", "PARTIAL")]
    return {"source": source[:12], "dest": dest[:12], "merge_base": base[:12],
            "verdict": "UNPORTED_DELTA" if unported else "BEHAVIOUR_CONTAINED",
            "unported": unported, "merges_not_judged": merges, "commits": commits,
            "reality": "textual presence of each hunk's added lines, and of each added test by name, at the destination; "
                       "equal text is not proof of "
                       "equal behaviour, and a missing hunk may have been deliberately replaced. A lead for the "
                       "integrator, not a disposition"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True)
    parser.add_argument("--prs", required=True, help="JSON file: [{number, sha}, ...]")
    parser.add_argument("--intake", action="store_true",
                        help="judge each PR head's commits for behaviour missing from --base (the destination)")
    args = parser.parse_args(argv)
    with open(args.prs) as handle:
        prs = json.load(handle)
    base = git("rev-parse", args.base)
    if args.intake:
        result = {"dest": base[:12], "prs": [{"number": int(p["number"]), **intake(base, p["sha"])} for p in prs]}
    else:
        result = measure(base, prs)
    json.dump(result, sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
