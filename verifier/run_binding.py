#!/usr/bin/env python3
"""Bind verifier run records to the tree they measured.

A run record that does not name the commit it measured floats free of the
tree: it cannot serve as evidence ABOUT that tree. Surfaced by the
independent audit of main @ 8cb3074a, Finding 3
(docs/audit/INDEPENDENT_VERIFICATION_8cb3074a.md): a 172-test partial-mirror
record committed atop the canonical-v1 merge reads as if it described the
merge, and only its own `skips` field discloses otherwise.

Contract: when a git object store is available, return `git rev-parse HEAD`.
When it is not (API-fetched mirror, unpacked tarball, stripped checkout),
return MIRROR_UNKNOWN. Fail closed on every error path — never guess,
never omit, never return an unverifiable value.
"""
import subprocess

MIRROR_UNKNOWN = "MIRROR_UNKNOWN"
_HEX40 = frozenset("0123456789abcdef")


def head_commit(cwd=None):
    """Return the 40-hex HEAD commit for cwd, or MIRROR_UNKNOWN."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return MIRROR_UNKNOWN
    if proc.returncode != 0:
        return MIRROR_UNKNOWN
    sha = proc.stdout.strip()
    if len(sha) == 40 and all(c in _HEX40 for c in sha):
        return sha
    return MIRROR_UNKNOWN
