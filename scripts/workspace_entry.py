"""Install/check workspace-level pointers to the existing collaboration protocol.

No network, repository edits, credentials or client-setting changes. Installation
creates missing files only; differing existing instructions require human review.
"""
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "<!-- UNIIMENTE workspace entry v1 -->"
FILES = ("AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md", ".cursor/rules/uniimente.mdc")


def documents(kernel: Path) -> dict[str, str]:
    guide = kernel / "docs/collaboration/START_HERE.md"
    if not guide.is_file() or not (kernel / "AGENTS.md").is_file():
        raise ValueError("Kernel checkout must contain AGENTS.md and docs/collaboration/START_HERE.md")
    text = f"""{MARKER}
# UNIIMENTE workspace — start here

This workspace contains several repositories belonging to one intended machine:
**BODY + ORGANS + MIND = GREG / UNIIMENTE**.

Before new or resumed work:
1. Read the canonical team entry: [{guide}]({guide}). Follow its source-access fallback if needed.
2. Read the target repository's AGENTS.md and applicable nested/client instructions.
   User instructions govern the task; workspace pointers do not replace local engineering rules.
3. Refresh [Discussion #89](https://github.com/dababiyoda/uniimente-kernel/discussions/89),
   [work board #96](https://github.com/dababiyoda/uniimente-kernel/issues/96), relevant open PRs,
   current branch/head and working-tree status. Do not assume main or an old handoff is current.
4. Before editing, identify the intended outcome, actual session/task identity,
   files/interfaces, competing claims, tests, rollback and integration destination.
   Post the bounded claim on the existing work item. A notice is not an atomic lock;
   overlapping live concerns need an acknowledged split. Preserve unrelated work.
5. Give a concise session check-in: repository/branch/head, source revision read,
   intended outcome, owned scope, overlap status, next action and genuine blocker.
   Recheck sources/claims after a pause, base change or material scope change.
6. Use the existing protocol's proportionate decision process: material work has
   five perspectives and exactly two strengthening passes. Label one worker's
   perspectives self-review; never invent independent review or receiver acceptance.
7. Before handoff, record exact base/head, changed behavior, commands/results,
   failed/unrun checks, limits, rollback, next owner/action and acknowledgment status.
   Use the existing v2 PR receipt. Resume the parent objective after each increment.

Keep one canonical protocol; do not copy its SOPs into each repository. Kernel
owns institutional authority; organs own specialist behavior. A tool, worker,
model or generated capability gains no authority by being installed or tested.
Protected merges, deployment, spending, publishing, external contact, credentials
and live activation retain their existing separate authorization requirements.

If a source or receiving worker is unavailable, state that precisely and continue
unrelated authorized work. Never turn a missing acknowledgment into consent.

These pointers aid discovery, not enforcement. Clients that do not load these
files need their normal startup instruction to point to the canonical team entry.
"""
    out = {name: text for name in FILES}
    out[FILES[-1]] = '---\ndescription: UNIIMENTE workspace collaboration entry\nalwaysApply: true\n---\n\n' + text
    return out


def check_or_install(workspace: Path, kernel: Path, *, install: bool = False) -> list[str]:
    workspace, kernel = workspace.resolve(), kernel.resolve()
    if not workspace.is_dir():
        raise ValueError("workspace must be an existing directory")
    expected = documents(kernel)
    missing = []
    # Preflight every destination before creating anything. Never follow a link
    # in an instruction path, and never replace an existing instruction file.
    for relative, content in expected.items():
        path = workspace / relative
        for part in (path, *path.parents):
            if part == workspace:
                break
            if part.is_symlink():
                raise ValueError(f"symlink instruction path refused: {relative}")
        if path.exists():
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                raise ValueError(f"existing instructions differ; review manually: {relative}")
        else:
            missing.append(relative)
    if install:
        for relative in missing:
            path = workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation also refuses a destination created since preflight.
            with path.open("x", encoding="utf-8") as stream:
                stream.write(expected[relative])
    return missing


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--kernel", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--install", action="store_true", help="create missing pointers; never overwrite")
    args = parser.parse_args(argv)
    try:
        missing = check_or_install(args.workspace, args.kernel, install=args.install)
    except (OSError, ValueError) as exc:
        print(f"Workspace entry refused: {exc}")
        return 2
    if missing and not args.install:
        print("Missing workspace entry files: " + ", ".join(missing))
        return 1
    print("Workspace entry pointers installed" if missing else "Workspace entry pointers match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
