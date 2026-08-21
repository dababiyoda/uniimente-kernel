#!/usr/bin/env python3
"""Prove PA-1/PA-2 ordering and frozen test semantics from git history.

The addendum must be a single-file commit. The strict-xfail tests, design, this
checker and CI wiring must arrive later and before any new v5 runtime commit.
The frozen test hash is checked at the test file's introducing commit, not
merely at HEAD. After implementation, the only permitted test edit is one
marker-only commit removing all declared ``@prearrival`` lines.
"""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys


ADDENDUM = "verification/phase3g/PREARRIVAL_CONTROL_ADDENDUM.json"
TESTS = "tests/unit/test_substrate_v5_prearrival_controls.py"
DESIGN = "verification/phase3g/PREARRIVAL_CONTROL_DESIGN.md"
RUNTIME = "substrate/v5.py"
RUNNER = "verification/phase3g/prearrival_adversarial_twin.py"
RESULTS = "verification/phase3g/PREARRIVAL_CONTROL_RESULTS.json"


def git(*args: str, check: bool = True) -> str:
    proc = subprocess.run(("git", *args), capture_output=True, text=True)
    if check and proc.returncode:
        raise RuntimeError(proc.stderr.strip() or "git command failed")
    return proc.stdout.strip()


def introducing_commit(path: str) -> str | None:
    output = git("log", "--reverse", "--diff-filter=A", "--format=%H", "--", path)
    return output.splitlines()[0] if output else None


def commits_after(start: str, path: str) -> list[str]:
    output = git("log", "--format=%H", f"{start}..HEAD", "--", path)
    return output.splitlines() if output else []


def files_in(commit: str) -> list[str]:
    output = git("show", "--name-only", "--format=", commit)
    return sorted(line for line in output.splitlines() if line)


def is_strict_ancestor(ancestor: str, descendant: str) -> bool:
    if ancestor == descendant:
        return False
    return subprocess.run(
        ("git", "merge-base", "--is-ancestor", ancestor, descendant),
        capture_output=True,
    ).returncode == 0


def at(commit: str, path: str) -> str:
    return git("show", f"{commit}:{path}") + "\n"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def node_ids(source: str) -> list[str]:
    module = ast.parse(source, filename=TESTS)
    return [
        f"{TESTS}::{item.name}"
        for item in module.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name.startswith("test_")
    ]


def without_marker(source: str, marker: str) -> str:
    return "\n".join(
        line for line in source.splitlines() if line.strip() != marker
    ) + "\n"


def main() -> int:
    failures: list[str] = []
    add_commit = introducing_commit(ADDENDUM)
    if add_commit is None:
        print(f"SKIP: {ADDENDUM} is absent")
        return 0

    if files_in(add_commit) != [ADDENDUM]:
        failures.append(
            f"addendum commit {add_commit[:8]} touched {files_in(add_commit)}, "
            f"expected only [{ADDENDUM}]"
        )

    add_original = at(add_commit, ADDENDUM)
    try:
        addendum = json.loads(add_original)
    except json.JSONDecodeError as exc:
        failures.append(f"addendum is not valid JSON: {exc}")
        addendum = {}

    if at("HEAD", ADDENDUM) != add_original:
        failures.append("the immutable PA-1 addendum changed after preregistration")

    test_commit = introducing_commit(TESTS)
    design_commit = introducing_commit(DESIGN)
    if test_commit is None:
        failures.append(f"{TESTS} has not been introduced")
    elif not is_strict_ancestor(add_commit, test_commit):
        failures.append("the frozen tests are not a strict descendant of the addendum")
    if design_commit is None:
        failures.append(f"{DESIGN} has not been introduced")
    elif test_commit and design_commit != test_commit:
        failures.append("the PA-2 design was not frozen in the PA-1 test commit")

    if test_commit:
        introduced_files = files_in(test_commit)
        for prohibited in (RUNTIME, RUNNER, RESULTS):
            if prohibited in introduced_files:
                failures.append(
                    f"test preregistration commit also touched prohibited {prohibited}"
                )

        frozen = at(test_commit, TESTS)
        contract = addendum.get("frozen_test_contract", {})
        expected_hash = contract.get("sha256_with_strict_markers")
        if sha256(frozen) != expected_hash:
            failures.append(
                f"frozen test hash {sha256(frozen)} != declared {expected_hash}"
            )

        expected_nodes = contract.get("node_ids", [])
        if node_ids(frozen) != expected_nodes:
            failures.append("test node IDs differ from the frozen addendum")

        marker = contract.get("activation_marker_line", "@prearrival")
        expected_count = len(expected_nodes)
        frozen_count = sum(
            line.strip() == marker for line in frozen.splitlines()
        )
        if frozen_count != expected_count:
            failures.append(
                f"frozen file has {frozen_count} marker lines, expected {expected_count}"
            )

        current = at("HEAD", TESTS)
        current_count = sum(
            line.strip() == marker for line in current.splitlines()
        )
        if current_count not in (expected_count, 0):
            failures.append(
                f"partial marker activation: {current_count} of {expected_count} remain"
            )
        if without_marker(current, marker) != without_marker(frozen, marker):
            failures.append("frozen test semantics changed; only marker removal is allowed")
        if node_ids(current) != expected_nodes:
            failures.append("current test node IDs differ from preregistration")

        later_test_commits = commits_after(test_commit, TESTS)
        if current_count == expected_count and later_test_commits:
            failures.append("test file changed before marker activation")
        if current_count == 0:
            if len(later_test_commits) != 1:
                failures.append(
                    "activation must be exactly one marker-only commit; found "
                    f"{len(later_test_commits)} test-file commits"
                )
            for commit in later_test_commits:
                if files_in(commit) != [TESTS]:
                    failures.append(
                        f"activation commit {commit[:8]} touched {files_in(commit)}"
                    )

        for path in (RUNTIME, RUNNER, RESULTS):
            for commit in commits_after(add_commit, path):
                if not is_strict_ancestor(test_commit, commit):
                    failures.append(
                        f"{path} commit {commit[:8]} is not a strict descendant "
                        "of the frozen tests"
                    )

    print(f"PA-1 addendum commit: {add_commit}")
    print(f"PA-1 test commit: {test_commit or 'absent'}")
    print(f"PA-2 design commit: {design_commit or 'absent'}")
    if test_commit:
        print(f"frozen test sha256: {sha256(at(test_commit, TESTS))}")
        print(f"runtime commits after addendum: {len(commits_after(add_commit, RUNTIME))}")

    if failures:
        print("\nFAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("\nOK: PA-1 tests and PA-2 design precede runtime and remain frozen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
