"""Frozen-baseline tests read historical commits; a shallow checkout does not contain them.

``require_commits`` skips with the reason only when the checkout is shallow. In a full
checkout a missing commit still fails, so a rewritten or lost history is never hidden.
Found while reproducing the #173/#175 suite discrepancy (2026-10-14): a depth-1 clone of
#175 failed exactly these frozen-continuity tests and nothing else.
"""
from __future__ import annotations

import subprocess

import pytest


def require_commits(root, *shas: str) -> None:
    missing = [s for s in shas if subprocess.run(["git", "cat-file", "-e", f"{s}^{{commit}}"], cwd=root,
                                                 capture_output=True).returncode != 0]
    if not missing:
        return
    shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=root, capture_output=True,
                             text=True).stdout.strip() == "true"
    if shallow:
        pytest.skip(f"git history unavailable in a shallow checkout: {', '.join(s[:12] for s in missing)}")
    pytest.fail(f"historical commit(s) missing from a full checkout: {', '.join(missing)}")
