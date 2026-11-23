#!/usr/bin/env python3
"""Rehearse an intake: do several heads still behave when they are merged together?

``scripts/branch_catalog.py`` says which branches merge cleanly, and says itself that clean is not correct. Two
changes can merge without a conflict and break each other: one moves the code the other calls, or tightens a rule
the other relies on. This script finds that before an intake does.

Read-only. It merges nothing, pushes nothing and edits no branch or working tree. For a base and an ordered set of
heads it:

1. computes the merge in memory, one head at a time (``git merge-tree --write-tree``, then ``git commit-tree``:
   objects only, no working tree, no ref). A head that conflicts textually is reported as such and left out of the
   merged tree, unless the conflict is confined to files named with ``--union``: there both sides' lines are kept
   (right for a list every change appends to, wrong for anything else) and the report says so;
2. exports each head, and the merged tree, to scratch directories (``git archive``);
3. runs each head's own tests, by default the test files it changed, on its own tree and on the merged tree;
4. reports every test that passes on its own head and fails on the merged tree, and finds the cause: the base
   itself, when the test already fails with that head alone merged onto it (the line moved since the head
   branched), else the other head without which it passes, found by leaving one head out at a time.

A test that already fails on its own head is listed apart: it is not a composition problem. A head for which no
test was run is listed as not checked, never as compatible.

Limits, stated in every report: only the named tests are run, so a clean result does not prove the heads are
compatible; a test that fails only with three or more heads together is reported without a single cause; nothing
here approves a merge.

The rehearsal itself lives in ``greg/intake_rehearsal.py``, where GREG's ``brief.intake`` mission capability runs the
same code inside its worker envelope. This file is the command line over it: it parses the arguments, runs the
tests as you (unconfined: you chose to run these heads' code) and writes the reports.

Usage::

    python scripts/compose_rehearsal.py --base <sha> \\
        --unit 290=<sha> --unit 291=<sha> --unit 273=<sha> \\
        [--tests 273=tests/unit/a.py,tests/unit/b.py] [--also tests/unit/c.py] \\
        [--union .github/workflows/canonical-ci.yml] \\
        [--json out.json] [--markdown out.md]

Exit status: 0 when nothing conflicts, 1 when a textual or behavioural conflict was found, 2 on a usage error.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:          # run as ``python scripts/compose_rehearsal.py``: the package is one level up
    sys.path.insert(0, str(ROOT))

from greg import intake_rehearsal  # noqa: E402
from greg.intake_rehearsal import (COUNT, IDENTITY, ON_BASE, PYTEST, RESULT, SHOWN, RehearsalError,  # noqa: E402,F401
                                   Unit, changed_tests, compose, export, git, keep_both, markdown, merge, node_file,
                                   read_pytest, resolve)


def run_tests(tree: Path, files: list[str], timeout: int) -> dict:
    """Run pytest on ``files`` inside an exported tree. Returns the failing node ids and the counts it printed."""
    present = [f for f in files if (tree / f).is_file()]
    missing = sorted(set(files) - set(present))
    if not present:
        return {"failed": [], "counts": {}, "missing": missing, "ran": False, "tail": ""}
    env = {**os.environ, "PYTHONPATH": str(tree), "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run([sys.executable, *PYTEST, *present], cwd=tree, env=env, capture_output=True, text=True,
                              timeout=timeout)
        out, timed_out = proc.stdout, False
    except subprocess.TimeoutExpired as exc:
        out, timed_out = (exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) \
            else (exc.stdout or ""), True
    failed, counts, lines = read_pytest(out)
    if timed_out:
        failed = sorted(set(failed) | {f"{f}::(timed out after {timeout}s)" for f in present})
    elif not counts and not failed:      # pytest printed no summary: collection or start-up failed
        failed = [f"{f}::(pytest did not run: {lines[-1][:120] if lines else 'no output'})" for f in present]
    return {"failed": failed, "counts": counts, "missing": missing, "ran": True, "tail": "\n".join(lines[-4:])}


def rehearse(root: Path, base_ref: str, units: list[Unit], also: list[str], timeout: int, scratch: Path,
             union: tuple[str, ...] = ()) -> dict:
    """The rehearsal with this command's runner: pytest started as you, unconfined."""
    return intake_rehearsal.rehearse(root, base_ref, units, also, timeout, scratch, union, run=run_tests)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", default=str(ROOT))
    parser.add_argument("--base", required=True)
    parser.add_argument("--unit", action="append", default=[], metavar="NAME=REF")
    parser.add_argument("--tests", action="append", default=[], metavar="NAME=FILE[,FILE]")
    parser.add_argument("--also", action="append", default=[], metavar="FILE")
    parser.add_argument("--union", action="append", default=[], metavar="FILE",
                        help="a file in which a textual conflict is resolved by keeping both sides' lines")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--json")
    parser.add_argument("--markdown")
    args = parser.parse_args(argv)
    try:
        units = [Unit(*spec.split("=", 1)) for spec in args.unit]
        named = dict(spec.split("=", 1) for spec in args.tests)
    except (TypeError, ValueError):
        parser.print_usage(sys.stderr)
        return 2
    if not units or len({u.name for u in units}) != len(units) or set(named) - {u.name for u in units}:
        print("give at least one --unit NAME=REF, each name once; --tests names must be units", file=sys.stderr)
        return 2
    for unit in units:
        unit.tests = [f for f in named.get(unit.name, "").split(",") if f]
    try:
        with tempfile.TemporaryDirectory(prefix="compose-rehearsal-") as scratch:
            report = rehearse(Path(args.repo), args.base, units, args.also, args.timeout, Path(scratch),
                              tuple(args.union))
    except RehearsalError as exc:
        print(f"rehearsal failed: {exc}", file=sys.stderr)
        return 2
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1) + "\n")
    text = markdown(report)
    if args.markdown:
        Path(args.markdown).write_text(text)
    print(text)
    return 0 if report["clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
