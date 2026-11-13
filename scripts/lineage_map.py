"""Measure competing branch futures: which open drafts build on the converged base, which are tips,
how far the tips have diverged from each other, and which files would conflict if merged.

One GREG (INTENT-2026-09-30-OPUS-MAXIMUS-CONVERGENCE) needs this measured, not asserted. Input is a
JSON list of {"number", "sha"} (for example from the GitHub pulls API); the commits must already be
fetched. Output is JSON on stdout. Read-only: it never checks out, merges or pushes anything.

    python scripts/lineage_map.py --base <sha> --prs prs.json
"""
from __future__ import annotations

import argparse
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True)
    parser.add_argument("--prs", required=True, help="JSON file: [{number, sha}, ...]")
    args = parser.parse_args(argv)
    with open(args.prs) as handle:
        prs = json.load(handle)
    json.dump(measure(git("rev-parse", args.base), prs), sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
