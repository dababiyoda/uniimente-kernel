#!/usr/bin/env python3
"""Required check 3 — exactly one source of authority.

One authority, many governed capabilities (UNIIMENTE_FINAL_BUILD_ORDER §3).
This check enforces the authority half only. It does NOT restrict multiple
capability implementations, which the build order explicitly preserves.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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


def find(pattern):
    return sorted(
        p for p in ROOT.glob(pattern)
        if not any(part in SKIP for part in p.parts) and p.is_file()
    )


def main():
    failures = []
    print(f"{'artifact':<20} {'found':<6} paths")
    for name, (pattern, expected, meaning) in SINGLETONS.items():
        hits = find(pattern)
        rel = [str(p.relative_to(ROOT)) for p in hits]
        print(f"{name:<20} {len(hits):<6} {', '.join(rel) if rel else '(none)'}")
        if len(hits) > expected:
            failures.append(f"{name}: {len(hits)} found (expected {expected}) — {meaning}: {rel}")
        elif len(hits) < expected:
            failures.append(f"{name}: MISSING (expected {expected})")

    print()
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        print(f"\n{len(failures)} authority-duplication failure(s)")
        return 1
    print("exactly one source of authority for each governed artifact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
