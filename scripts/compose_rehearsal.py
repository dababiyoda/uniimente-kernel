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
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = {"GIT_AUTHOR_NAME": "compose-rehearsal", "GIT_AUTHOR_EMAIL": "rehearsal@localhost",
            "GIT_COMMITTER_NAME": "compose-rehearsal", "GIT_COMMITTER_EMAIL": "rehearsal@localhost",
            "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"}
RESULT = re.compile(r"^(FAILED|ERROR) (\S+)")
SHOWN = 8          # failing-before-the-merge tests listed per head in the Markdown report
ON_BASE = "(the base)"   # the cause named when a head's test fails on base + that head alone
COUNT = re.compile(r"(\d+) (passed|failed|skipped|error|errors|xfailed|xpassed)")


class RehearsalError(Exception):
    """The rehearsal could not be carried out as asked (an unknown ref, a tree that could not be exported)."""


@dataclass
class Unit:
    name: str
    ref: str
    sha: str = ""
    tests: list[str] = field(default_factory=list)


def git(root: Path, *args: str, stdin: bytes | None = None, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", *args], cwd=root, input=stdin, capture_output=True, env={**os.environ, **IDENTITY})
    if check and proc.returncode:
        raise RehearsalError(f"git {' '.join(args[:3])}: {proc.stderr.decode('utf-8', 'replace').strip()[-300:]}")
    return proc


def resolve(root: Path, ref: str) -> str:
    return git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").stdout.decode().strip()


def keep_both(root: Path, ours: str, theirs: str, tree: str, paths: list[str]) -> str:
    """``tree`` with each of ``paths`` replaced by the three-way merge that keeps both sides' lines.

    For a file where every change adds lines at the same place (a list of CI steps, a ledger that grows at the top),
    keeping both additions is the resolution a person would make. It is wrong for anything else, so it is applied
    only to the files the caller names, and the report says where it was applied. Objects only: a scratch index
    file, no working tree, no ref."""
    fork = git(root, "merge-base", ours, theirs, check=False).stdout.decode().strip()
    with tempfile.TemporaryDirectory(prefix="compose-rehearsal-index-") as work:
        index = {"GIT_INDEX_FILE": str(Path(work) / "index")}

        def scratch(*args: str, stdin: bytes | None = None) -> bytes:
            proc = subprocess.run(["git", *args], cwd=root, input=stdin, capture_output=True,
                                  env={**os.environ, **IDENTITY, **index})
            if proc.returncode:
                raise RehearsalError(f"git {' '.join(args[:2])}: {proc.stderr.decode('utf-8', 'replace')[-200:]}")
            return proc.stdout
        scratch("read-tree", tree)
        for path in paths:
            sides = []
            for name, commit in (("ours", ours), ("base", fork), ("theirs", theirs)):
                shown = git(root, "show", f"{commit}:{path}", check=False) if commit else None
                side = Path(work) / name
                side.write_bytes(shown.stdout if shown is not None and shown.returncode == 0 else b"")
                sides.append(str(side))
            merged = subprocess.run(["git", "merge-file", "--union", "-p", *sides], cwd=root, capture_output=True)
            if merged.returncode < 0 or merged.returncode > 127:
                raise RehearsalError(f"could not merge {path}: {merged.stderr.decode('utf-8', 'replace')[-200:]}")
            blob = scratch("hash-object", "-w", "--stdin", stdin=merged.stdout).decode().strip()
            entry = git(root, "ls-tree", ours, "--", path).stdout.decode().split()
            scratch("update-index", "--add", "--cacheinfo", f"{entry[0] if entry else '100644'},{blob},{path}")
        return scratch("write-tree").decode().strip()


def merge(root: Path, ours: str, theirs: str, label: str,
          union: tuple[str, ...] = ()) -> tuple[str | None, list[str], list[str]]:
    """The commit of ``ours`` merged with ``theirs``, made in memory, or None and the files that conflict. A conflict
    confined to the files named in ``union`` is resolved by keeping both sides' lines; those files come back third."""
    proc = git(root, "merge-tree", "--write-tree", "--name-only", "--no-messages", ours, theirs, check=False)
    lines = proc.stdout.decode().splitlines()
    kept: list[str] = []
    if proc.returncode == 1:
        files = [name for name in lines[1:] if name] or ["(conflict)"]
        if not lines or not set(files) <= set(union):
            return None, files, []
        tree, kept = keep_both(root, ours, theirs, lines[0], files), files
    elif proc.returncode or not lines:
        raise RehearsalError(f"git merge-tree {ours[:10]} {theirs[:10]}: "
                             + proc.stderr.decode("utf-8", "replace").strip()[-300:])
    else:
        tree = lines[0]
    made = git(root, "commit-tree", tree, "-p", ours, "-p", theirs, "-m", f"rehearsal: {label}")
    return made.stdout.decode().strip(), [], kept


def compose(root: Path, base: str, units: list[Unit], union: tuple[str, ...] = (),
            kept_both: dict[str, list[str]] | None = None) -> tuple[str, list[str], dict[str, list[str]]]:
    """Merge the units onto the base in order. Returns the merged commit, the names merged, and the textual
    conflicts of each unit that could not be merged onto what came before it. ``kept_both``, when given, is filled
    with the files of each unit that were resolved by keeping both sides' lines."""
    at, merged, conflicts = base, [], {}
    for unit in units:
        made, files, kept = merge(root, at, unit.sha, unit.name, union)
        if made is None:
            conflicts[unit.name] = files
            continue
        if kept and kept_both is not None:
            kept_both[unit.name] = kept
        at = made
        merged.append(unit.name)
    return at, merged, conflicts


def export(root: Path, treeish: str, dest: Path) -> Path:
    dest.mkdir(parents=True)
    archive = git(root, "archive", "--format=tar", treeish)
    unpack = subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout, capture_output=True)
    if unpack.returncode:
        raise RehearsalError(f"could not export {treeish[:10]}: {unpack.stderr.decode('utf-8', 'replace')[-200:]}")
    return dest


def changed_tests(root: Path, base: str, sha: str) -> list[str]:
    """The test files a head added or changed since it left the base."""
    fork = git(root, "merge-base", base, sha, check=False).stdout.decode().strip() or base
    names = git(root, "diff", "--name-only", "--diff-filter=AM", fork, sha, "--", "tests").stdout.decode().splitlines()
    return sorted(n for n in names if Path(n).name.startswith("test_") and n.endswith(".py"))


def run_tests(tree: Path, files: list[str], timeout: int) -> dict:
    """Run pytest on ``files`` inside an exported tree. Returns the failing node ids and the counts it printed."""
    present = [f for f in files if (tree / f).is_file()]
    missing = sorted(set(files) - set(present))
    if not present:
        return {"failed": [], "counts": {}, "missing": missing, "ran": False, "tail": ""}
    env = {**os.environ, "PYTHONPATH": str(tree), "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfE",
                               "--no-header", *present], cwd=tree, env=env, capture_output=True, text=True,
                              timeout=timeout)
        out, timed_out = proc.stdout, False
    except subprocess.TimeoutExpired as exc:
        out, timed_out = (exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) \
            else (exc.stdout or ""), True
    failed = sorted({m.group(2) for m in map(RESULT.match, out.splitlines()) if m})
    lines = [line for line in out.splitlines() if line.strip()]
    counts = {kind.rstrip("s") if kind == "errors" else kind: int(n) for n, kind in COUNT.findall(lines[-1])} \
        if lines else {}
    if timed_out:
        failed = sorted(set(failed) | {f"{f}::(timed out after {timeout}s)" for f in present})
    elif not counts and not failed:      # pytest printed no summary: collection or start-up failed
        failed = [f"{f}::(pytest did not run: {lines[-1][:120] if lines else 'no output'})" for f in present]
    return {"failed": failed, "counts": counts, "missing": missing, "ran": True, "tail": "\n".join(lines[-4:])}


def node_file(node: str) -> str:
    return node.split("::", 1)[0]


def rehearse(root: Path, base_ref: str, units: list[Unit], also: list[str], timeout: int, scratch: Path,
             union: tuple[str, ...] = ()) -> dict:
    base = resolve(root, base_ref)
    if not base:
        raise RehearsalError(f"unknown base {base_ref}")
    for unit in units:
        unit.sha = resolve(root, unit.ref)
        if not unit.sha:
            raise RehearsalError(f"unknown ref for {unit.name}: {unit.ref}")
        unit.tests = unit.tests or changed_tests(root, base, unit.sha)
    kept_both: dict[str, list[str]] = {}
    merged_commit, merged, textual = compose(root, base, units, union, kept_both)
    in_merge = [u for u in units if u.name in merged]

    own = {}
    for unit in units:
        tree = export(root, unit.sha, scratch / f"own-{unit.name}")
        own[unit.name] = run_tests(tree, unit.tests, timeout)
    base_also = run_tests(export(root, base, scratch / "base"), also, timeout) if also else None

    composed_tree = export(root, merged_commit, scratch / "composed")
    composed = {u.name: run_tests(composed_tree, u.tests, timeout) for u in in_merge}
    composed_also = run_tests(composed_tree, also, timeout) if also else None

    behavioural, already_failing = [], []
    for unit in in_merge:
        alone = set(own[unit.name]["failed"])
        for node in composed[unit.name]["failed"]:
            (already_failing if node in alone else behavioural).append({"test": node, "unit": unit.name})
        for node in sorted(alone - set(composed[unit.name]["failed"])):
            already_failing.append({"test": node, "unit": unit.name, "note": "fails alone, passes merged"})
    if also:
        before = set(base_also["failed"])
        for node in composed_also["failed"]:
            (already_failing if node in before else behavioural).append({"test": node, "unit": "(also)"})

    # Which head causes each behavioural conflict: the merge without it passes the test. Each merge-without-one is
    # made and exported once, and each test file is run on it once, however many of its tests conflict.
    without: dict[str, Path | None] = {}
    reruns: dict[tuple[str, str], dict] = {}
    by_name = {u.name: u for u in in_merge}
    for conflict in behavioural:
        causes, file = [], node_file(conflict["test"])
        if conflict["unit"] in by_name:
            # First the cheapest explanation: the head no longer works on the line itself. Its own tree passes because
            # it branched from an older line; merged onto today's base, with no other head, the test already fails.
            key = ("(base)+" + conflict["unit"], file)
            if key not in reruns and len(in_merge) == 1:
                reruns[key] = composed[conflict["unit"]]        # the merged tree is the base and this head alone
            elif key not in reruns:
                commit, kept, _ = compose(root, base, [by_name[conflict["unit"]]], union)
                reruns[key] = (run_tests(export(root, commit, scratch / f"onbase-{conflict['unit']}"), [file], timeout)
                               if kept else {"failed": [], "ran": False})
            if reruns[key]["ran"] and conflict["test"] in reruns[key]["failed"]:
                conflict["caused_by"] = [ON_BASE]
                conflict["note"] = "fails as soon as this head is merged onto the base, with no other head: " \
                                   "the line has moved since it branched"
                continue
        for other in in_merge:
            if other.name == conflict["unit"]:
                continue
            if other.name not in without:
                rest = [u for u in in_merge if u.name != other.name]
                commit, kept, _ = compose(root, base, rest, union)
                # when the rest does not merge without it, this split gives no verdict
                without[other.name] = (export(root, commit, scratch / f"without-{other.name}")
                                       if len(kept) == len(rest) else None)
            tree = without[other.name]
            if tree is None:
                continue
            if (other.name, file) not in reruns:
                reruns[other.name, file] = run_tests(tree, [file], timeout)
            result = reruns[other.name, file]
            if conflict["test"] not in result["failed"] and result["ran"]:
                causes.append(other.name)
        conflict["caused_by"] = causes
        conflict["note"] = ("passes when this head is left out" if len(causes) == 1 else
                            "no single head explains it: it passes with any one of these left out" if causes else
                            "no single head explains it: it fails with any one head left out")

    return {
        "tool": "compose_rehearsal/1", "base": base,
        "units": [{"name": u.name, "sha": u.sha, "tests": u.tests, "in_merge": u.name in merged,
                   "alone": {k: own[u.name][k] for k in ("counts", "failed", "missing")},
                   "merged": ({k: composed[u.name][k] for k in ("counts", "failed", "missing")}
                              if u.name in composed else None)} for u in units],
        "also": {"tests": also, "base": base_also and {k: base_also[k] for k in ("counts", "failed")},
                 "merged": composed_also and {k: composed_also[k] for k in ("counts", "failed")}} if also else None,
        "merge_order": merged, "textual_conflicts": textual, "kept_both_sides": kept_both,
        # A head with no test to run was checked for nothing: it must not read as compatible.
        "unchecked": [u.name for u in units if not [f for f in u.tests if f not in own[u.name]["missing"]]],
        "behavioural_conflicts": behavioural, "failing_before_the_merge": already_failing,
        "clean": not textual and not behavioural,
        "limits": ["only the named tests were run: a clean result does not prove the heads are compatible",
                   "a unit left out for a textual conflict was not tested in the merge",
                   "where both sides' lines were kept in a named file, that resolution was not reviewed by a person",
                   "read-only: nothing was merged, pushed or edited; no result here approves a merge"],
    }


def markdown(report: dict) -> str:
    lines = [f"# Composition rehearsal on `{report['base'][:10]}`", "",
             "Each head's own tests, run on its own tree and on the merged tree. Read-only; nothing was merged.", "",
             "| Head | Commit | Test files | Alone | Merged |", "|---|---|---:|---|---|"]

    def counts(result) -> str:
        if result is None:
            return "not merged"
        shown = ", ".join(f"{n} {kind}" for kind, n in sorted(result["counts"].items())) or "nothing ran"
        return shown + (f" ({len(result['failed'])} failing)" if result["failed"] else "")
    for unit in report["units"]:
        lines.append(f"| {unit['name']} | `{unit['sha'][:10]}` | {len(unit['tests'])} | {counts(unit['alone'])} | "
                     f"{counts(unit['merged'])} |")
    lines += ["", f"Merge order: {', '.join(report['merge_order']) or 'none'}.", ""]
    if report["kept_both_sides"]:
        lines += ["## Conflicts resolved by keeping both sides' lines", ""] + [
            f"- **{name}**: " + ", ".join(f"`{f}`" for f in files)
            for name, files in report["kept_both_sides"].items()] + [
            "", "Asked for on the command line for these files only. Nobody reviewed the result.", ""]
    if report["textual_conflicts"]:
        lines += ["## Textual conflicts", ""] + [f"- **{name}** conflicts with what was merged before it in: "
                                                  + ", ".join(f"`{f}`" for f in files)
                                                  for name, files in report["textual_conflicts"].items()] + [""]
    if report["behavioural_conflicts"]:
        lines += ["## Tests that pass alone and fail merged", ""]
        for conflict in report["behavioural_conflicts"]:
            cause = ", ".join(conflict["caused_by"]) or "no single head"
            lines.append(f"- `{conflict['test']}` (from {conflict['unit']}): caused by **{cause}**; {conflict['note']}.")
        lines.append("")
    if report["failing_before_the_merge"]:
        lines += ["## Failing before the merge (not a composition problem)", ""]
        by_unit: dict[str, list[dict]] = {}
        for item in report["failing_before_the_merge"]:
            by_unit.setdefault(item["unit"], []).append(item)
        for name, items in by_unit.items():          # the JSON report lists every one; here, the first few and a count
            lines += [f"- `{item['test']}` (from {name})" + (f": {item['note']}" if item.get("note") else "")
                      for item in items[:SHOWN]]
            if len(items) > SHOWN:
                lines.append(f"- and {len(items) - SHOWN} more from {name} (all are in the JSON report)")
        lines.append("")
    if report["unchecked"]:
        lines += ["## Not checked", "", "No test was run for: " + ", ".join(f"**{n}**" for n in report["unchecked"])
                  + ". These heads changed no test file and none was named for them, so nothing here says whether "
                  "they are compatible.", ""]
    lines += ["## Result", "", "No textual or behavioural conflict was found in the tests that were run."
              if report["clean"] else "Conflicts were found; see above.", "", "Limits:"]
    return "\n".join(lines + [f"- {limit}" for limit in report["limits"]]) + "\n"


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
