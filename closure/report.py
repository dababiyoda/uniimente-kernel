"""Commit-pinned proof that a module's five closures actually ran and passed.

Doctrine (CLOSURE PROOF): registration is not passing. Until this module existed,
`blueprint/evidence.py` awarded the EXERCISED rung on the strength of a *textual*
`ModuleClosures("name", ...)` match in `closure/`. That is a check that the author
wrote a registration, not a check that the five closures hold. Adding a
registration with five `lambda: (True, "")` stubs would have moved a technology up
a rung, which is precisely the ceremony the ladder exists to refuse.

This module closes that gap. It records, per module, whether
`ClosureRegistry.verify()` actually reported `complete`, anchored to the commit the
run was taken at. The evidence binder then requires *passing* rather than
*registered*.

Two properties keep the artifact from becoming a rubber stamp:

1. It is derived. `generate()` runs the real registry; there is no code path that
   accepts a module's status from a caller.
2. It is falsifiable. `tests/unit/test_closure_report.py` regenerates the report
   live and asserts the committed file agrees, so a hand-edited status fails the
   suite rather than silently raising a rung.

The report proves that the five checks passed in the environment that ran them. It
does not prove the checks are the right checks — that remains a review question,
and `open_closures` is recorded so a partially closed module is visible rather
than rounded to false.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone

REPORT_VERSION = 1
KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_PATH = os.path.join(KERNEL_ROOT, "closure", "CLOSURE_REPORT.json")

_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")


class ClosureReportError(ValueError):
    """The closure report is absent, malformed, or unanchored. Fails closed."""


@dataclass(frozen=True)
class ClosureProof:
    """Which modules were observed to close completely, and at which commit."""

    commit: str
    generated_at: str
    modules: dict[str, tuple[bool, tuple[str, ...]]]

    @property
    def passing(self) -> frozenset[str]:
        return frozenset(name for name, (ok, _) in self.modules.items() if ok)

    def open_closures(self, module: str) -> tuple[str, ...]:
        entry = self.modules.get(module)
        return entry[1] if entry else ()


def generate(commit: str) -> dict:
    """Run every registered module's five closures and record what happened.

    Derived only. The caller supplies the anchor and nothing else.
    """
    if not _COMMIT_RE.match(commit or ""):
        raise ClosureReportError(
            f"a closure report must be anchored to a commit; got {commit!r}"
        )
    from closure.integration_registry import build_registry

    registry = build_registry()
    _, reports = registry.verify()
    return {
        "report_version": REPORT_VERSION,
        "commit": commit,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modules": {
            report.module: {
                "complete": report.complete,
                "open_closures": list(report.open_closures),
            }
            for report in sorted(reports, key=lambda r: r.module)
        },
    }


def write(report: dict, path: str = REPORT_PATH) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return path


def load(root: str = KERNEL_ROOT) -> ClosureProof | None:
    """Read the committed proof, or None when there is none.

    None is a first-class answer: the binder must treat "no proof" as "no
    closure evidence", never as "assume it passed".
    """
    path = os.path.join(root, "closure", "CLOSURE_REPORT.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    if raw.get("report_version") != REPORT_VERSION:
        return None
    commit = raw.get("commit", "")
    if not _COMMIT_RE.match(commit or ""):
        return None
    modules: dict[str, tuple[bool, tuple[str, ...]]] = {}
    for name, entry in (raw.get("modules") or {}).items():
        if not isinstance(entry, dict):
            continue
        modules[str(name)] = (
            bool(entry.get("complete")),
            tuple(str(c) for c in entry.get("open_closures") or ()),
        )
    if not modules:
        return None
    return ClosureProof(commit=commit,
                        generated_at=str(raw.get("generated_at", "")),
                        modules=modules)


def proven_closure_modules(root: str = KERNEL_ROOT) -> frozenset[str]:
    """Modules a commit-pinned report observed closing completely."""
    proof = load(root)
    return proof.passing if proof else frozenset()


def main(argv: list[str] | None = None) -> int:
    import argparse

    from blueprint.cycle import head_commit

    parser = argparse.ArgumentParser(
        prog="python -m closure.report",
        description="Record a commit-pinned proof that the five closures passed.")
    parser.add_argument("command", nargs="?", default="show",
                        choices=("show", "write"))
    parser.add_argument("--commit", default=None,
                        help="anchor; defaults to HEAD read from .git")
    args = parser.parse_args(argv)

    commit = args.commit or head_commit()
    report = generate(commit)
    complete = [m for m, e in report["modules"].items() if e["complete"]]
    incomplete = {m: e["open_closures"]
                  for m, e in report["modules"].items() if not e["complete"]}

    print(f"commit    {report['commit']}")
    print(f"modules   {len(report['modules'])}")
    print(f"complete  {len(complete)}")
    if incomplete:
        print("incomplete:")
        for module, open_closures in sorted(incomplete.items()):
            print(f"  {module:<28} open: {open_closures}")
    if args.command == "write":
        print(f"wrote {os.path.relpath(write(report), KERNEL_ROOT)}")
    return 0


if __name__ == "__main__":            # pragma: no cover - CLI entry
    raise SystemExit(main())
