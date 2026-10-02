"""#52 Repair loop: failure -> diagnosis -> competing patches -> regression test -> recovery procedure.

Mechanisms (standard automated-program-repair techniques, small and inspectable):

  diagnosis     re-run the failing case and the passing cases under a line tracer;
                rank lines by the Ochiai suspiciousness score (spectrum-based fault
                localization) and record the observed symptom
  regression    write a pytest file from the failing case; it must FAIL on the current code
  patches       AST mutations at the most suspicious lines (integer +-1, drop a constant
                term, flip a comparison, swap +/-), each applied to an isolated copy
  selection     a patch survives only if the regression test now passes AND the existing
                tests still pass; the smallest surviving diff wins; the rest are kept as
                negative evidence
  procedure     the symptom signature, the fix, the test and the rejected candidates are
                committed as a versioned recovery procedure (#3)

Tests run in a separate Python process (pytest) against the patched copy; the
original source is never modified in place. Proposing a patch to the product
still goes through review/CI; this produces the patch, the proof and the runbook.
"""
from __future__ import annotations

import ast
import difflib
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from foundry.systems import versions


MAX_SUSPECT_LINES = 8


class RepairError(RuntimeError):
    pass


def _trace_lines(source: str, func: str, args: list) -> tuple[set[int], object]:
    ns: dict = {}
    code = compile(source, "<target>", "exec")
    exec(code, ns)
    hit: set[int] = set()

    def tracer(frame, event, arg):
        if frame.f_code.co_filename == "<target>":
            if event == "line":
                hit.add(frame.f_lineno)
            return tracer
        return None
    sys.settrace(tracer)
    try:
        try:
            result = ns[func](*args)
        except Exception as exc:  # the symptom may be an exception
            result = f"{type(exc).__name__}: {exc}"
    finally:
        sys.settrace(None)
    return hit, result


def localize(source: str, func: str, failing: list[dict], passing: list[dict]) -> list[dict]:
    """Ochiai: failed(s) / sqrt(total_failed * (failed(s) + passed(s)))."""
    f_cov = [_trace_lines(source, func, c["args"])[0] for c in failing]
    p_cov = [_trace_lines(source, func, c["args"])[0] for c in passing]
    lines = set().union(*f_cov, *p_cov)
    ranked = []
    for line in lines:
        ef, ep = sum(line in c for c in f_cov), sum(line in c for c in p_cov)
        score = ef / math.sqrt(len(f_cov) * (ef + ep)) if ef else 0.0
        ranked.append({"line": line, "score": round(score, 4), "text": source.splitlines()[line - 1].strip()})
    return sorted(ranked, key=lambda r: (-r["score"], r["line"]))


class _Mutator(ast.NodeTransformer):
    """Produces one mutant per (site, operator); ``target`` selects which one to apply."""

    def __init__(self, lines: set[int], target: int | None = None):
        self.lines, self.target, self.count, self.labels = lines, target, 0, []

    def _site(self, node, label, replacement):
        idx = self.count
        self.count += 1
        self.labels.append(label)
        return replacement() if idx == self.target else node

    def visit_Constant(self, node):
        if getattr(node, "lineno", None) in self.lines and isinstance(node.value, int) and not isinstance(node.value, bool):
            node = self._site(node, f"line {node.lineno}: {node.value} -> {node.value + 1}",
                              lambda: ast.copy_location(ast.Constant(node.value + 1), node))
            if isinstance(node, ast.Constant):
                node = self._site(node, f"line {node.lineno}: {node.value} -> {node.value - 1}",
                                  lambda: ast.copy_location(ast.Constant(node.value - 1), node))
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if getattr(node, "lineno", None) not in self.lines:
            return node
        if isinstance(node.right, ast.Constant) and isinstance(node.op, (ast.Add, ast.Sub)):
            sign = "+" if isinstance(node.op, ast.Add) else "-"
            node = self._site(node, f"line {node.lineno}: drop '{sign} {node.right.value}'", lambda: node.left)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
            flipped = ast.Sub() if isinstance(node.op, ast.Add) else ast.Add()
            node = self._site(node, f"line {node.lineno}: swap +/-",
                              lambda: ast.copy_location(ast.BinOp(node.left, flipped, node.right), node))
        return node

    def visit_Compare(self, node):
        self.generic_visit(node)
        swaps = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt}
        if getattr(node, "lineno", None) in self.lines and len(node.ops) == 1 and type(node.ops[0]) in swaps:
            node = self._site(node, f"line {node.lineno}: flip comparison",
                              lambda: ast.copy_location(ast.Compare(node.left, [swaps[type(node.ops[0])]()],
                                                                    node.comparators), node))
        return node


def candidates(source: str, lines: set[int]) -> list[tuple[str, str]]:
    probe = _Mutator(lines)
    probe.visit(ast.parse(source))
    out = []
    for i, label in enumerate(probe.labels):
        tree = _Mutator(lines, target=i).visit(ast.parse(source))
        out.append((label, ast.unparse(ast.fix_missing_locations(tree)) + "\n"))
    return out


def _pytest(module_source: str, test_sources: dict[str, str]) -> dict:
    with tempfile.TemporaryDirectory(prefix="repair-") as tmp:
        (Path(tmp) / "target.py").write_text(module_source)
        for name, text in test_sources.items():
            (Path(tmp) / name).write_text(text)
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *test_sources],
                              cwd=tmp, capture_output=True, text=True, timeout=120)
        tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else proc.stderr[-200:]
        tail = re.sub(r" in [0-9.]+s", "", tail)
        # pytest exit codes: 0 all passed, 1 some tests failed; anything else (collection or usage
        # error) is not evidence about the code under test
        return {"passed": proc.returncode == 0, "failed": proc.returncode == 1, "summary": tail}


def regression_test(func: str, case: dict) -> str:
    return (f"from target import {func}\n\n\n"
            f"def test_regression_{re.sub(r'[^0-9a-zA-Z_]', '_', case['id'])}():\n"
            f"    assert {func}(*{case['args']!r}) == {case['expect']!r}\n")


def repair(root: Path, *, source: str, func: str, failing: dict, passing: list[dict], existing_tests: str,
           top_lines: int = 2) -> dict:
    _, symptom = _trace_lines(source, func, failing["args"])
    if symptom == failing["expect"]:
        raise RepairError("the failing case does not reproduce")
    diagnosis = localize(source, func, [failing], passing)
    # ties at the cutoff are all suspects: when failing and passing runs share coverage, Ochiai
    # cannot discriminate and truncating a tie by line number would hide the fault
    cutoff = diagnosis[min(top_lines, len(diagnosis)) - 1]["score"] if diagnosis else 0
    suspects = {d["line"] for d in diagnosis if d["score"] > 0 and d["score"] >= cutoff}
    if len(suspects) > MAX_SUSPECT_LINES:
        raise RepairError(f"{len(suspects)} equally suspicious lines; add discriminating passing cases")
    regression = regression_test(func, failing)
    before = _pytest(source, {"test_regression.py": regression})
    if not before["failed"]:
        raise RepairError(f"regression test must fail by assertion on the current code; got: {before['summary']}")
    original = ast.unparse(ast.parse(source)) + "\n"
    tried = []
    for label, patched in candidates(source, suspects):
        r = _pytest(patched, {"test_regression.py": regression})
        e = _pytest(patched, {"test_existing.py": existing_tests}) if r["passed"] else {"passed": None, "summary": "-"}
        diff = "".join(difflib.unified_diff(original.splitlines(True), patched.splitlines(True), "a/target.py", "b/target.py"))
        tried.append({"patch": label, "regression_passes": r["passed"], "existing_pass": e["passed"],
                      "diff_lines": sum(1 for ln in diff.splitlines() if ln[:1] in "+-" and ln[:3] not in ("+++", "---")),
                      "size": len(patched), "diff": diff})
    survivors = sorted((t for t in tried if t["regression_passes"] and t["existing_pass"]),
                       key=lambda t: (t["diff_lines"], t["size"], t["patch"]))
    if not survivors:
        raise RepairError(f"no candidate survives ({len(tried)} tried); escalate with the diagnosis")
    chosen = survivors[0]
    fixed = next(p for label, p in candidates(source, suspects) if label == chosen["patch"])
    after = _pytest(fixed, {"test_regression.py": regression, "test_existing.py": existing_tests})
    procedure = {"symptom": {"function": func, "case": failing, "observed": symptom},
                 "diagnosis": [d for d in diagnosis if d["line"] in suspects], "fix": chosen["patch"], "diff": chosen["diff"],
                 "regression_test": regression, "verified_after": after["summary"],
                 "rejected": [{k: t[k] for k in ("patch", "regression_passes", "existing_pass")}
                              for t in tried if t is not chosen]}
    record = versions.commit(Path(root) / "procedures", f"recovery:{func}", procedure,
                             reason=f"repair {func}: {chosen['patch']}", evidence=[failing["id"]])
    return {"symptom": symptom, "suspects": sorted(suspects), "tied": len(suspects) > top_lines, "regression_before": before["summary"],
            "candidates": len(tried), "survivors": [t["patch"] for t in survivors], "chosen": chosen["patch"],
            "diff": chosen["diff"], "after": after["summary"], "after_passed": after["passed"],
            "procedure_version": record["n"], "rejected": procedure["rejected"]}


QUERY_OPS = {"localize": lambda a, r: {"ranked": localize(a["source"], a["func"], a["failing"], a["passing"])}}
APPLY_OPS = {"repair": lambda a, r: repair(r, source=a["source"], func=a["func"], failing=a["failing"],
                                           passing=a["passing"], existing_tests=a["existing_tests"])}


TARGET = '''def split_invoice(total_cents, parts):
    if parts <= 0:
        raise ValueError("parts must be positive")
    base = total_cents // parts
    shares = [base] * parts
    remainder = total_cents - base * parts
    for i in range(remainder - 1):
        shares[i] += 1
    return shares
'''
EXISTING = '''from target import split_invoice
import pytest


def test_even_split():
    assert split_invoice(90, 3) == [30, 30, 30]


def test_single_part():
    assert split_invoice(10, 1) == [10]


def test_rejects_zero_parts():
    with pytest.raises(ValueError):
        split_invoice(10, 0)


def test_shares_are_never_negative():
    assert min(split_invoice(5, 5)) == 1
'''


def exercise(root) -> dict:
    failing = {"id": "inv-100-3", "args": [100, 3], "expect": [34, 33, 33]}
    passing = [{"args": [90, 3]}, {"args": [10, 1]}, {"args": [60, 4]}]
    out = repair(Path(root), source=TARGET, func="split_invoice", failing=failing, passing=passing,
                 existing_tests=EXISTING)
    return {k: out[k] for k in ("symptom", "suspects", "tied", "regression_before", "candidates", "survivors", "chosen",
                                "diff", "after", "after_passed", "procedure_version")} | {
        "rejected_that_broke_existing_tests": [r["patch"] for r in out["rejected"]
                                               if r["regression_passes"] and r["existing_pass"] is False]}
