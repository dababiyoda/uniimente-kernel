#!/usr/bin/env python3
"""Prove the Phase 3G checksum manifest still COVERS what it used to cover.

`sha256sum -c CHECKSUMS.txt` proves that every listed file matches its listed
hash. It proves nothing about files that stopped being listed. Deleting a line
is therefore the cheapest way to make a failing integrity check pass, and it
leaves no trace in the check's own output -- the manifest just verifies clean
with one fewer entry.

That is not hypothetical here. The manifest sat stale from `1d7349c` while
`DEVELOPMENT_RESULTS.json` was rewritten seven times, and nothing reported it,
because nothing executed the manifest at all. Adding execution without adding
coverage would replace a check nobody ran with a check anybody could silence.

So this asserts monotonic coverage: the set of paths listed in CHECKSUMS.txt
must be a SUPERSET of the set listed at the merge base with the base branch.
Adding evidence is always allowed. Removing evidence from the manifest fails
here and must be argued for in a commit message rather than performed quietly.

Exit non-zero on any failure. Skips cleanly when the manifest is absent, or
when no merge base is reachable (a shallow checkout has nothing to compare
against and must not be reported as a pass or a failure of coverage).
"""
from __future__ import annotations

import os
import subprocess
import sys

MANIFEST = "verification/phase3g/CHECKSUMS.txt"


def git(*args: str) -> tuple[int, str]:
    p = subprocess.run(("git", *args), capture_output=True, text=True)
    return p.returncode, p.stdout.strip()


def paths_in(text: str) -> set[str]:
    """The path column of a sha256sum manifest.

    `sha256sum` separates hash from path with two spaces, and a leading '*'
    marks binary mode. Split once so a path containing spaces survives intact.
    """
    out = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            print(f"FAIL: unparseable manifest line: {line!r}")
            sys.exit(1)
        out.add(parts[1].lstrip("*"))
    return out


def main() -> int:
    if not os.path.exists(MANIFEST):
        print(f"SKIP: {MANIFEST} absent on this history")
        return 0

    with open(MANIFEST) as fh:
        current = paths_in(fh.read())
    print(f"manifest lists {len(current)} paths")

    base = os.environ.get("GITHUB_BASE_REF") or "main"
    for ref in (f"origin/{base}", base):
        code, mb = git("merge-base", "HEAD", ref)
        if code == 0 and mb:
            break
    else:
        print("SKIP: no merge base reachable (shallow checkout)")
        return 0

    code, previous_text = git("show", f"{mb}:{MANIFEST}")
    if code != 0:
        print(f"OK: manifest did not exist at merge base {mb[:8]}; "
              f"nothing could have been dropped")
        return 0

    previous = paths_in(previous_text)
    dropped = sorted(previous - current)
    if dropped:
        print(f"FAIL: {len(dropped)} path(s) present in the manifest at "
              f"{mb[:8]} and missing now:")
        for p in dropped:
            print(f"  - {p}")
        print("Removing an entry hides a changed file instead of verifying it.")
        return 1

    added = sorted(current - previous)
    print(f"OK: coverage is monotonic against {mb[:8]} "
          f"({len(previous)} -> {len(current)} paths, {len(added)} added)")
    for p in added:
        print(f"  + {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
