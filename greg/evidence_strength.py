"""Worker evidence strength: a worker's own tests cannot certify its own change.

The default code-change mission (``templates.code_change``) accepts a WorkOrder when the tests the
worker itself added pass in an independent clone. Rehearsed on #168: a worker that wrote a wrong
``sub()`` (it adds) together with ``assert True``, or with ``assert sub(0, 0) == 0``, was ACCEPTED,
the mission closed and the review handoff was written. The appraiser re-ran the worker's evidence
faithfully; nothing asked whether that evidence could tell a right change from a wrong one.

Recombined from three mechanisms already on the GREG path (INTENT-20261019-UPWARD-ASCENT), each
changed in role:

* genesis.py held-out oracle (the builder never controls its judge) -> SEALED ORACLE. Files the
  founder named in ``acceptance.tests`` are judged as they were at the base commit. A patch that
  edits or deletes one is refused, and the founder's version, not the worker's, is what runs.
* workers.appraise fresh-clone re-run -> DISCRIMINATION. The worker's changed test files also run
  on the base commit with only their own hunks applied. Tests that already pass without the change
  certify nothing about it.
* foundry/systems/repair.py AST mutation operators, built to search for a fix -> ADVERSARY. The
  same operators, plus a few more, now mutate the worker's own added lines. Tests that kill none of
  those mutants, or fewer than ``MIN_KILL_RATIO`` of them, cannot tell the change from a corrupted
  version of it.

Thresholds were fixed before measurement. Limits, stated: mutation testing samples at most
``MAX_MUTANTS`` sites. Equivalent mutants count as survivors. Python sources only. Only the
worker-authored tests are scored; a founder-named oracle is trusted as the founder's judgment.
"""
from __future__ import annotations

import ast
from fnmatch import fnmatchcase
from pathlib import Path
import re

from foundry.systems import repair

MAX_MUTANTS = 12
MIN_KILLED = 1
MIN_KILL_RATIO = 0.5
TEST_SIDE = "tests/*"
WORKER_TESTS = "tests/*test_*.py"
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


# -- sealed oracle --------------------------------------------------------------------------

def sealed_paths(acceptance: dict, base_files: set[str]) -> set[str]:
    """Base-commit files the founder named as the judge: test paths or directories in ``acceptance.tests``."""
    sealed = set()
    for argv in acceptance.get("tests", []):
        for arg in argv:
            path = arg.split("::", 1)[0].rstrip("/")
            if not path or path.startswith("-"):
                continue
            if path in base_files:
                sealed.add(path)
            else:
                sealed.update(f for f in base_files if f.startswith(path + "/"))
    return sealed


# -- adversary --------------------------------------------------------------------------------

class _Adversary(repair._Mutator):
    """repair.py's operators (integer +-1, drop a constant term, swap +/-, flip <,<=,>,>=) plus
    equality and membership flips, and/or swap, dropped ``not`` and boolean flip.

    Negative evidence, kept: a ``return None`` operator was tried and removed. Any test that merely
    calls the function kills it, so it lifted ``assert sub(0, 0) == 0`` over the threshold for a
    ``sub`` that adds. An operator every test kills measures nothing about the test.
    """

    _FLIP = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Is: ast.IsNot, ast.IsNot: ast.Is,
             ast.In: ast.NotIn, ast.NotIn: ast.In}

    def _here(self, node) -> bool:
        return getattr(node, "lineno", None) in self.lines

    def visit_Compare(self, node):
        node = super().visit_Compare(node)
        if isinstance(node, ast.Compare) and self._here(node) and len(node.ops) == 1 \
                and type(node.ops[0]) in self._FLIP:
            flipped = self._FLIP[type(node.ops[0])]()
            node = self._site(node, f"line {node.lineno}: negate comparison",
                              lambda: ast.copy_location(ast.Compare(node.left, [flipped], node.comparators), node))
        return node

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        if self._here(node):
            other = ast.Or() if isinstance(node.op, ast.And) else ast.And()
            node = self._site(node, f"line {node.lineno}: swap and/or",
                              lambda: ast.copy_location(ast.BoolOp(other, node.values), node))
        return node

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if self._here(node) and isinstance(node.op, ast.Not):
            node = self._site(node, f"line {node.lineno}: drop 'not'", lambda: node.operand)
        return node

    def visit_Constant(self, node):
        if self._here(node) and isinstance(node.value, bool):
            return self._site(node, f"line {node.lineno}: {node.value} -> {not node.value}",
                              lambda: ast.copy_location(ast.Constant(not node.value), node))
        return super().visit_Constant(node)


def added_lines(diff_u0: str) -> set[int]:
    """Line numbers, in the new file, of the lines a ``git diff -U0`` adds."""
    lines = set()
    for raw in diff_u0.splitlines():
        match = _HUNK.match(raw)
        if match:
            start, count = int(match.group(1)), int(match.group(2) if match.group(2) is not None else 1)
            lines.update(range(start, start + count))
    return lines


def mutants(source: str, lines: set[int], limit: int = MAX_MUTANTS) -> list[tuple[str, str]]:
    """Deterministic, evenly spread sample of single-site mutants of ``lines``; no-op mutants dropped."""
    try:
        original = ast.unparse(ast.parse(source)) + "\n"
    except SyntaxError:
        return []
    probe = _Adversary(lines)
    probe.visit(ast.parse(source))
    total = len(probe.labels)
    picks = range(total) if total <= limit else sorted({round(i * (total - 1) / (limit - 1)) for i in range(limit)})
    out = []
    for index in picks:
        tree = _Adversary(lines, target=index).visit(ast.parse(source))
        text = ast.unparse(ast.fix_missing_locations(tree)) + "\n"
        if text != original:
            out.append((probe.labels[index], text))
    return out


# -- the appraisal step -----------------------------------------------------------------------

def test_side(names: list[str]) -> list[str]:
    return [n for n in names if fnmatchcase(n, TEST_SIDE)]


def worker_tests(names: list[str]) -> list[str]:
    return [n for n in names if fnmatchcase(n, WORKER_TESTS)]


def judge(*, fresh: Path, base_clone: Path, patch: Path, base: str, names: list[str], command: list[str],
          git, run_tests, timeout: int) -> dict:
    """Score the worker-authored tests against the base and against mutants of the worker's change.

    ``fresh`` holds the patched tree; ``base_clone`` is a second clean clone at ``base``. ``git`` and
    ``run_tests`` are the appraiser's own scrubbed, no-network helpers. Returns findings; the caller
    turns any finding into REJECTED.
    """
    findings, report = [], {"command": command}
    tests_only = test_side(names)
    include = [arg for name in tests_only for arg in ("--include", name)]
    applied = git(base_clone, "apply", "--index", "--binary", *include, str(patch), check=False)
    if applied.returncode:
        findings.append("the worker's test changes do not apply to the base on their own")
        report["discrimination"] = {"established": False, "reason": "test hunks do not apply alone"}
        return {"findings": findings, **report}
    [on_base] = run_tests([command], base_clone, timeout=timeout)
    # pytest: 1 = a test failed, 2 = collection/import error (e.g. the new function does not exist
    # yet), -1 = timed out. 0 = everything passed without the change; 5 = nothing was collected.
    discriminates = on_base["returncode"] in (1, 2, -1)
    report["discrimination"] = {"established": discriminates, "returncode_on_base": on_base["returncode"],
                                "tail_on_base": on_base["tail"][-600:]}
    if not discriminates:
        findings.append("the worker's tests also pass on the base without its change; they certify nothing "
                        f"about it (pytest exit {on_base['returncode']} on the base)")

    sources = [n for n in names if n.endswith(".py") and not fnmatchcase(n, TEST_SIDE) and (fresh / n).is_file()]
    results = []
    for name in sources:
        lines = added_lines(git(fresh, "diff", "--cached", "-U0", base, "--", name).stdout)
        path = fresh / name
        original = path.read_bytes()
        for label, text in mutants(original.decode("utf-8", "replace"), lines,
                                   max(0, MAX_MUTANTS - len(results))):
            try:
                path.write_text(text)
                [run] = run_tests([command], fresh, timeout=timeout)
            finally:
                path.write_bytes(original)
            results.append({"file": name, "mutant": label, "killed": not run["passed"],
                            "returncode": run["returncode"]})
        if len(results) >= MAX_MUTANTS:
            break
    killed = sum(r["killed"] for r in results)
    ratio = killed / len(results) if results else None
    measured = bool(results)
    adequate = (not measured) or (killed >= MIN_KILLED and ratio >= MIN_KILL_RATIO)
    report["mutation"] = {"measured": measured, "mutants": len(results), "killed": killed,
                          "kill_ratio": round(ratio, 3) if ratio is not None else None,
                          "thresholds": {"min_killed": MIN_KILLED, "min_kill_ratio": MIN_KILL_RATIO,
                                         "max_mutants": MAX_MUTANTS},
                          "survivors": [r["mutant"] for r in results if not r["killed"]][:MAX_MUTANTS],
                          "operators": "foundry/systems/repair.py _Mutator + greg/evidence_strength.py _Adversary"}
    if not adequate:
        findings.append(f"the worker's tests kill {killed} of {len(results)} mutants of its own change; "
                        "they cannot tell it from a corrupted version")
    return {"findings": findings, **report}
