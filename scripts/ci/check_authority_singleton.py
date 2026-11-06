#!/usr/bin/env python3
"""Required check 3 — exactly one source of authority.

One authority, many governed capabilities (UNIIMENTE_FINAL_BUILD_ORDER §3).
This check enforces the authority half only. It does NOT restrict multiple
capability implementations, which the build order explicitly preserves.

Filename counts stay the first pass. The second pass reads the AST: a
ConsequenceGate or GrantIssuer constructed outside the Kernel module fails,
unless the file's one current section-5 disposition says that path is not
live architecture.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from greg.path import METABOLISM_FILE, authority_plane_problems, section5_problems  # noqa: E402

SKIP = {".git", "__pycache__", "node_modules", ".venv", "venv", "archive"}

# name -> (glob, expected count, what a duplicate would mean)
SINGLETONS = {
    "Constitution": ("**/constitution.ucl", 1, "a second body of supreme law"),
    "Consequence Gate": ("**/consequence_gate.py", 1, "a second path to external effect"),
    "Authority matrix": ("**/authority-matrix.yaml", 1, "a second authority source"),
    "Legal principals": ("**/legal-principals.yaml", 1, "a second legal-actor registry"),
    "Organ registry": ("**/organ-registry.yaml", 1, "a second identity registry"),
    "Agent registry": ("**/agent-registry.yaml", 1, "a second identity registry"),
}


def find(pattern, root: Path = ROOT):
    return sorted(
        p for p in root.glob(pattern)
        if not any(part in SKIP for part in p.parts) and p.is_file()
    )


def filename_problems(root: Path = ROOT) -> list[str]:
    """The filename-only pass. A construction in some other filename is invisible here."""
    failures = []
    for name, (pattern, expected, meaning) in SINGLETONS.items():
        hits = find(pattern, root)
        rel = [str(p.relative_to(root)) for p in hits]
        if len(hits) > expected:
            failures.append(f"{name}: {len(hits)} found (expected {expected}) — {meaning}: {rel}")
        elif len(hits) < expected:
            failures.append(f"{name}: MISSING (expected {expected})")
    return failures


def main():
    failures = filename_problems(ROOT)
    print(f"{'artifact':<20} {'found':<6} paths")
    for name, (pattern, expected, _meaning) in SINGLETONS.items():
        hits = find(pattern)
        rel = [str(p.relative_to(ROOT)) for p in hits]
        print(f"{name:<20} {len(hits):<6} {', '.join(rel) if rel else '(none)'}")
    record = json.loads(METABOLISM_FILE.read_text())
    index = section5_problems(record)
    plane = authority_plane_problems(ROOT, record) if not index else []
    print()
    for failure in failures + index + plane:
        print(f"FAIL {failure}")
    if failures or index or plane:
        print(f"\n{len(failures) + len(index) + len(plane)} authority-duplication failure(s)")
        return 1
    print("exactly one source of authority for each governed artifact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
