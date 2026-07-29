#!/usr/bin/env python3
"""Prove the Phase 3G pre-registration from git ancestry, not from self-report.

A manifest that records its own hash proves nothing: whoever wrote the results
could have written the manifest afterwards and recomputed the hash. The only
tamper-evident ordering available in-repo is commit ancestry.

This check asserts:

  1. The manifest exists and was introduced by exactly one commit.
  2. That commit introduced NOTHING ELSE - no implementation, no results.
  3. The manifest commit is a strict ancestor of every commit that touched the
     substrate implementation and the results file.
  4. The manifest is byte-identical to its originally committed content, so
     thresholds cannot have been relaxed after seeing the outcome.

Exit non-zero on any failure. Skips cleanly when the Phase 3G files are absent
so the check is safe to run on branches that predate the phase.
"""
from __future__ import annotations

import subprocess
import sys

MANIFEST = "verification/phase3g/EVALUATION_MANIFEST.json"
IMPLEMENTATION = ["substrate/v5.py"]
RESULTS = ["verification/phase3g/PHASE3G_RESULTS.json"]
ADDENDUM = None


def git(*args: str) -> str:
    return subprocess.run(("git", *args), capture_output=True, text=True,
                          check=True).stdout.strip()


def introducing_commit(path: str) -> str | None:
    """Oldest commit that touched `path` on the current history."""
    out = git("log", "--reverse", "--format=%H", "--diff-filter=A", "--", path)
    return out.splitlines()[0] if out else None


def touching_commits(path: str) -> list[str]:
    out = git("log", "--format=%H", "--", path)
    return out.splitlines() if out else []


def is_ancestor(a: str, b: str) -> bool:
    return subprocess.run(("git", "merge-base", "--is-ancestor", a, b)).returncode == 0


def main() -> int:
    failures: list[str] = []

    manifest_commit = introducing_commit(MANIFEST)
    if manifest_commit is None:
        print(f"SKIP: {MANIFEST} not present on this history")
        return 0

    # 2. the pre-registration commit must contain the manifest and nothing else
    files = git("show", "--name-only", "--format=", manifest_commit).split()
    if files != [MANIFEST]:
        failures.append(
            f"pre-registration commit {manifest_commit[:8]} touched {files}, "
            f"expected only [{MANIFEST}]")

    # 3. strict ancestry over implementation and results
    for path in IMPLEMENTATION + RESULTS:
        commits = touching_commits(path)
        if not commits:
            if path in RESULTS:
                print(f"note: {path} not yet present; ancestry check deferred")
                continue
            failures.append(f"{path} is absent but is required by this phase")
            continue
        for c in commits:
            if c == manifest_commit:
                failures.append(f"{path} was introduced by the manifest commit itself")
            elif not is_ancestor(manifest_commit, c):
                failures.append(
                    f"manifest commit {manifest_commit[:8]} is not an ancestor of "
                    f"{c[:8]} which touched {path}")

    # 4. the manifest has not been edited since pre-registration
    original = git("show", f"{manifest_commit}:{MANIFEST}")
    current = git("show", f"HEAD:{MANIFEST}")
    if original != current:
        failures.append(
            "manifest differs from its pre-registered content: thresholds or "
            "held-out fixtures were changed after pre-registration")

    # The run-2 addendum must itself be a manifest-only commit that precedes
    # the run-2 runner and results.
    add_commit = introducing_commit(ADDENDUM) if ADDENDUM else None
    if add_commit is not None:
        add_files = git("show", "--name-only", "--format=", add_commit).split()
        if add_files != [ADDENDUM]:
            failures.append(f"addendum commit {add_commit[:8]} touched {add_files}")
        for path in ["verification/phase3g/run_phase3g2.py",
                     "verification/phase3g/PHASE3G_RUN2_RESULTS.json"]:
            for c in touching_commits(path):
                if c == add_commit or not is_ancestor(add_commit, c):
                    failures.append(f"{path} is not a strict descendant of the "
                                    f"run-2 addendum commit")
        orig = git("show", f"{add_commit}:{ADDENDUM}")
        if orig != git("show", f"HEAD:{ADDENDUM}"):
            failures.append("run-2 addendum edited after pre-registration")

    print(f"pre-registration commit: {manifest_commit}")
    print(f"manifest unchanged since pre-registration: {original == current}")
    for path in IMPLEMENTATION + RESULTS:
        cs = touching_commits(path)
        print(f"  {path}: {len(cs)} commit(s), all descendants: "
              f"{all(is_ancestor(manifest_commit, c) and c != manifest_commit for c in cs)}")

    if failures:
        print("\nFAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK: Phase 3G thresholds were fixed before the substrate that is "
          "measured against them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
