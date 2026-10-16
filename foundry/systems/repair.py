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
import hashlib
import json
import math
import os
import re
import shutil
import stat
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


# -- source-tree repair: a copied multi-file tree, every execution inside the worker OS envelope -------
#
# ``repair`` above works on one in-memory module. ``repair_source`` repairs a module inside a real
# multi-file Python tree (for example a copy of GREG or Foundry source):
#
#   recipe      the target module and the existing tests are named; their static import closure
#               (parsed, never executed) plus explicit extras is copied into a private scratch tree.
#               The source tree itself is only read, and its digests are checked before and after.
#   isolation   every execution (diagnosis tracer, before-run, baseline, each candidate, after-run)
#               runs in a fresh copy of the frozen tree through greg.worker_isolation.prepare_worker
#               with network=False (bubblewrap: no network, private PID/user namespaces, read-only
#               except the run's own copy). Without that envelope the repair is refused, fail closed.
#   freeze      before any candidate exists the regression test is written and the acceptance is frozen:
#               the digest of every file in the scratch tree except the target module, and the digest of
#               the evaluator inputs. After every run the copy is re-hashed; any file other than the
#               target that changed, appeared or disappeared rejects that run as tampering.
#   intended    the before-run must fail by the regression test's own AssertionError at its comparison
#               line (read from pytest's junit XML). An ImportError, collection error, other exception
#               or timeout is not failing-before evidence.
#   outcomes    each candidate: survived | regression_still_fails | broke_existing | tampering | timeout
#               | crashed. Per-run wall timeout and a candidate cap bound the search.
#   proposal    the result is a proposal (diff, evidence, recovery procedure committed with #3). The
#               source tree is never written, and no field of the result grants promotion: applying the
#               patch to a real tree is a separate reviewed act.

SOURCE_RUN_TIMEOUT = 120
MAX_CANDIDATES = 24
MAX_SOURCE_FILES = 2000
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_REPORT_BYTES = 1024 * 1024
REGRESSION_FILE = "test_repair_regression.py"
REGRESSION_MARKER = "repair-regression: observed differs from expected"
OUTCOMES = ("survived", "regression_still_fails", "broke_existing", "tampering", "timeout", "crashed")
_RUN_PROVIDER = "repair-tests"
_FLIP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt}


class RepairEscalation(RepairError):
    """No candidate survived the frozen acceptance; ``evidence`` carries the diagnosis for escalation."""

    def __init__(self, message: str, evidence: dict):
        super().__init__(message)
        self.evidence = evidence


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _digest(value) -> str:
    return _sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def _relative(path) -> str:
    text = str(path)
    rel = Path(text)
    if not text or "\x00" in text or rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise RepairError(f"recipe path must be relative and inside the source tree: {text!r}")
    return rel.as_posix()


def _source_file(source_root: Path, rel: str) -> Path:
    path = source_root / rel
    if path.is_symlink() or not path.is_file():
        raise RepairError(f"recipe file is missing, not a regular file, or a symlink: {rel}")
    if source_root.resolve() not in path.resolve().parents:
        raise RepairError(f"recipe file resolves outside the source tree: {rel}")
    return path


def module_name(rel: str) -> str:
    parts = list(Path(_relative(rel)).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if not rel.endswith(".py") or not parts or not all(p.isidentifier() for p in parts):
        raise RepairError(f"{rel!r} is not an importable Python module path")
    return ".".join(parts)


def _resolve_module(source_root: Path, name: str) -> str | None:
    if not name or not all(p.isidentifier() for p in name.split(".")):
        return None
    base = Path(*name.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        path = source_root / candidate
        if path.is_file() and not path.is_symlink():
            return candidate.as_posix()
    return None


def source_closure(source_root, entries, extra=()) -> list[str]:
    """Files a run needs: the entries, their static import closure inside ``source_root``, every
    ancestor package ``__init__.py`` and every ``conftest.py`` on an entry's path. Files are parsed with
    ``ast``; nothing is imported or executed. Imports that resolve outside the tree are left to the
    read-only runtime (the interpreter's own site-packages)."""
    source_root = Path(source_root)
    queue = [_relative(e) for e in entries]
    for rel in list(queue):
        for parent in [*reversed(Path(rel).parents)]:
            conftest = (parent / "conftest.py").as_posix() if parent != Path(".") else "conftest.py"
            if (source_root / conftest).is_file() and not (source_root / conftest).is_symlink():
                queue.append(conftest)
    for rel in (_relative(e) for e in extra):          # explicit data files, or every file of a directory
        directory = source_root / rel
        if directory.is_dir() and not directory.is_symlink():
            queue += sorted(p.relative_to(source_root).as_posix() for p in directory.rglob("*")
                            if p.is_file() and "__pycache__" not in p.parts)
        else:
            queue.append(rel)
    seen: set[str] = set()
    total = 0
    while queue:
        rel = queue.pop()
        if rel in seen:
            continue
        path = _source_file(source_root, rel)
        seen.add(rel)
        total += path.stat().st_size
        if len(seen) > MAX_SOURCE_FILES or total > MAX_SOURCE_BYTES:
            raise RepairError(f"source recipe exceeds {MAX_SOURCE_FILES} files / {MAX_SOURCE_BYTES} bytes")
        for parent in list(Path(rel).parents)[:-1]:
            init = (parent / "__init__.py").as_posix()
            if (source_root / init).is_file() and not (source_root / init).is_symlink():
                queue.append(init)
        if not rel.endswith(".py"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
            raise RepairError(f"recipe file does not parse: {rel}: {exc}") from None
        try:
            own = module_name(rel).split(".")
            package = own if rel.endswith("__init__.py") else own[:-1]
        except RepairError:
            package = None
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    if package is None or node.level - 1 > len(package):
                        continue
                    base = package[:len(package) - (node.level - 1)]
                    module = ".".join(base + ([node.module] if node.module else []))
                else:
                    module = node.module or ""
                names = [module] + [f"{module}.{a.name}" if module else a.name for a in node.names if a.name != "*"]
            for name in names:
                parts = name.split(".")
                for k in range(1, len(parts) + 1):
                    found = _resolve_module(source_root, ".".join(parts[:k]))
                    if found and found not in seen:
                        queue.append(found)
    return sorted(seen)


_SPECIAL = {stat.S_IFIFO: "fifo", stat.S_IFSOCK: "socket", stat.S_IFCHR: "chr", stat.S_IFBLK: "blk"}


def _entry(path: Path) -> str:
    """One manifest value, read without ever blocking on what tree code left behind. A FIFO, socket or device is
    named by its type and never opened: a FIFO's writer died with the namespace, so opening it would wait forever.
    A regular file is opened non-blocking and checked again on the descriptor, in case it was swapped in between."""
    try:
        info = os.lstat(path)
        if stat.S_ISLNK(info.st_mode):
            return "symlink:" + os.readlink(path)
        if stat.S_ISDIR(info.st_mode):
            return "dir"
        if not stat.S_ISREG(info.st_mode):
            return "special:" + _SPECIAL.get(stat.S_IFMT(info.st_mode), "other")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        return f"unreadable:{exc.errno}"
    with os.fdopen(fd, "rb") as fh:
        if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
            return "special:swapped"
        return _sha256(fh.read())


def _manifest(tree: Path) -> dict[str, str]:
    """Every directory, file and symlink under ``tree`` with its content digest. The frozen tree holds only
    directories and regular files, so any other entry differs from it and its run is rejected as tampering."""
    out: dict[str, str] = {}
    for directory, dirs, files in os.walk(tree, followlinks=False):
        base = Path(directory)
        for name in sorted(dirs) + sorted(files):
            path = base / name
            out[path.relative_to(tree).as_posix()] = _entry(path)
    return out


def _report_rows(rows, count: int) -> bool:
    """The tracer's report has the shape the parent reads: one row per case, each with the covered line numbers as
    positive integers and the observation as text or nothing. Code under repair can rewrite the report file, so a
    row of any other shape means the diagnosis did not run the target."""
    if not isinstance(rows, list) or len(rows) != count:
        return False
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("lines"), list):
            return False
        if not all(type(n) is int and n > 0 for n in row["lines"]):
            return False
        if any(row.get(k) is not None and not isinstance(row[k], str) for k in ("observed", "raised")):
            return False
        if "equals_expected" in row and type(row["equals_expected"]) is not bool:
            return False
    return True


def tampered(expected: dict[str, str], observed: dict[str, str]) -> list[str]:
    """Paths that differ from the frozen manifest: changed, added or removed."""
    return sorted(p for p in set(expected) | set(observed) if expected.get(p) != observed.get(p))


def _sites(tree: ast.AST, lines: set[int]) -> list[tuple[ast.AST, str, ast.AST]]:
    inside_fstring = {id(n) for j in ast.walk(tree) if isinstance(j, ast.JoinedStr) for n in ast.walk(j)}
    out = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", None)
        if line not in lines or getattr(node, "end_col_offset", None) is None or id(node) in inside_fstring:
            continue
        span = f"{node.col_offset}" if node.end_lineno == line else f"{node.col_offset}..{node.end_lineno}"
        where = f"line {line} col {span}-{node.end_col_offset}"     # unique: one span per node
        if isinstance(node, ast.Constant) and type(node.value) is int:
            out.append((node, f"{where}: {node.value} -> {node.value + 1}", ast.Constant(node.value + 1)))
            out.append((node, f"{where}: {node.value} -> {node.value - 1}", ast.Constant(node.value - 1)))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
            sign = "+" if isinstance(node.op, ast.Add) else "-"
            if isinstance(node.right, ast.Constant):
                out.append((node, f"{where}: drop '{sign} {node.right.value!r}'", node.left))
            flipped = ast.Sub() if isinstance(node.op, ast.Add) else ast.Add()
            out.append((node, f"{where}: swap +/-", ast.BinOp(node.left, flipped, node.right)))
        elif isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _FLIP:
            out.append((node, f"{where}: flip comparison",
                        ast.Compare(node.left, [_FLIP[type(node.ops[0])]()], node.comparators)))
    return sorted(out, key=lambda s: (s[0].lineno, s[0].col_offset, s[1]))


def _splice(source: str, node: ast.AST, replacement: ast.AST) -> str | None:
    """Replace exactly ``node``'s source span; every other byte (comments, layout) is preserved.

    ``ast`` column offsets are UTF-8 byte offsets. The bare replacement is used only when it parses to the
    same tree as the parenthesized one, so operator precedence can never silently change the meaning."""
    raw = source.encode("utf-8")
    starts = [0]
    for line in source.encode("utf-8").splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    begin = starts[node.lineno - 1] + node.col_offset
    end = starts[node.end_lineno - 1] + node.end_col_offset
    text = ast.unparse(replacement)
    variants = []
    for wrapped in (text, f"({text})"):
        patched = (raw[:begin] + wrapped.encode("utf-8") + raw[end:]).decode("utf-8")
        try:
            variants.append((patched, ast.dump(ast.parse(patched))))
        except SyntaxError:
            variants.append((None, None))
    (bare, bare_tree), (paren, paren_tree) = variants
    if paren is None:
        return None
    return bare if bare_tree == paren_tree else paren


def source_mutants(source: str, lines) -> list[tuple[str, str]]:
    """Layout-preserving AST mutants at ``lines`` (same operators as ``candidates``)."""
    tree = ast.parse(source)
    out, seen = [], {source}
    for node, label, replacement in _sites(tree, set(lines)):
        patched = _splice(source, node, replacement)
        if patched is not None and patched not in seen:
            seen.add(patched)
            out.append((label, patched))
    return out


def suspect_lines(diagnosis: list[dict], limit: int = MAX_SUSPECT_LINES) -> list[int]:
    """Whole Ochiai score bands, most suspicious first, while they fit in ``limit`` lines.

    A tie is never truncated by line number: a band that does not fit is left out entirely, and if
    even the first band does not fit the caller must add discriminating passing cases."""
    bands: dict[float, list[int]] = {}
    for d in diagnosis:
        if d["score"] > 0:
            bands.setdefault(d["score"], []).append(d["line"])
    chosen: list[int] = []
    for score in sorted(bands, reverse=True):
        if len(chosen) + len(bands[score]) > limit:
            if not chosen:
                raise RepairError(f"{len(bands[score])} equally suspicious lines; add discriminating passing cases")
            break
        chosen += sorted(bands[score])
    return chosen


def regression_source(module: str, func: str, case: dict) -> tuple[str, str, int]:
    """(test text, test function name, line of the comparing assertion)."""
    name = "test_regression_" + re.sub(r"[^0-9a-zA-Z_]", "_", str(case["id"]))
    lines = [f'"""Generated by Foundry #52 before any candidate patch exists; frozen by digest."""',
             f"from {module} import {func}", "", "",
             f"ARGS = {tuple(case['args'])!r}", f"EXPECTED = {case['expect']!r}", "", "",
             f"def {name}():", f"    observed = {func}(*ARGS)",
             f"    assert observed == EXPECTED, {REGRESSION_MARKER!r}", ""]
    return "\n".join(lines), name, len(lines) - 1


def parse_junit(data: bytes | None) -> list[dict] | None:
    if not data:
        return None
    from xml.etree import ElementTree
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError:
        return None
    cases = []
    for case in root.iter("testcase"):
        outcome, message, text = "passed", "", ""
        for tag in ("failure", "error", "skipped"):
            element = case.find(tag)
            if element is not None:
                outcome, message, text = tag, element.get("message", ""), element.text or ""
                break
        cases.append({"file": case.get("classname", ""), "name": case.get("name", ""), "outcome": outcome,
                      "message": message[:600], "text_tail": text[-600:]})
    return cases


def fails_by_assertion(cases: list[dict] | None, test_name: str, assert_line: int) -> tuple[bool, str]:
    """True only when the regression test itself failed by its comparing assertion."""
    if cases is None:
        return False, "no junit report: the run crashed, timed out or never reached pytest"
    if [c["name"] for c in cases] != [test_name]:
        return False, f"expected exactly the regression test, junit has {[c['name'] for c in cases]}"
    case = cases[0]
    if case["outcome"] != "failure":
        return False, f"regression test outcome is {case['outcome']}: {case['message'][:200]}"
    if not case["message"].startswith("AssertionError") or REGRESSION_MARKER not in case["message"]:
        return False, f"regression test failed by {case['message'][:200]!r}, not by its comparison"
    if not case["text_tail"].rstrip().endswith(f"{REGRESSION_FILE}:{assert_line}: AssertionError"):
        return False, "the AssertionError was raised outside the regression test's comparison line"
    return True, "the regression test failed by its own comparing assertion"


_TRACER = r'''
import json, os, sys
sys.path.insert(0, os.getcwd())
spec = json.loads(sys.argv[1])
target = os.path.join(os.getcwd(), spec["target"])
import importlib
fn = getattr(importlib.import_module(spec["module"]), spec["func"])
out = []
for case in spec["cases"]:
    hit = set()
    def tracer(frame, event, arg):
        if frame.f_code.co_filename == target:
            if event == "line":
                hit.add(frame.f_lineno)
            return tracer
        return None
    raised = value = None
    sys.settrace(tracer)
    try:
        value = fn(*case["args"])
    except BaseException as exc:
        raised = type(exc).__name__ + ": " + str(exc)[:300]
    finally:
        sys.settrace(None)
    row = {"lines": sorted(hit), "raised": raised, "observed": None if raised else repr(value)[:500]}
    if "expect" in case and raised is None:
        row["equals_expected"] = bool(value == case["expect"])
    out.append(row)
with open(spec["report"], "w") as handle:
    json.dump(out, handle)
'''


class _Runner:
    """Each call copies the frozen tree, runs one command in the worker envelope and checks for tampering."""

    def __init__(self, scratch: Path, pristine: Path, manifest: dict, target: str, timeout: float):
        self.scratch, self.pristine, self.manifest, self.target = scratch, pristine, manifest, target
        self.timeout, self.count, self.isolation = timeout, 0, None

    def run(self, argv_for, target_source: str | None = None) -> dict:
        from greg import worker_isolation
        from greg.workers import WorkerError, supervised_run
        self.count += 1
        run_dir = self.scratch / "runs" / f"{self.count:03d}"
        run_dir.mkdir(parents=True, mode=0o700)
        tree = run_dir / "tree"
        try:
            shutil.copytree(self.pristine, tree, symlinks=True)
            expected = dict(self.manifest)
            if target_source is not None:
                (tree / self.target).write_text(target_source, encoding="utf-8")
                expected[self.target] = _sha256(target_source.encode("utf-8"))
            report = run_dir / ".worker-runtime" / _RUN_PROVIDER / "tmp" / "report"
            argv = argv_for(report)
            try:
                envelope = worker_isolation.prepare_worker(argv, tree, timeout_seconds=self.timeout,
                                                           provider=_RUN_PROVIDER, reviewed=True, source_env={},
                                                           network=False, file_bytes=8 * 1024 * 1024)
            except worker_isolation.WorkerIsolationError as exc:
                raise RepairError("refused: source repair executes only inside the worker OS isolation "
                                  f"envelope, which is unavailable here ({exc})") from None
            evidence = envelope["evidence"]
            if (evidence.get("network_isolated") is not True or evidence.get("mechanism") != "bubblewrap"
                    or Path(envelope["runtime_root"]) != report.parent.parent):
                raise RepairError("refused: the worker envelope is not the no-network bubblewrap envelope")
            self.isolation = {"mechanism": evidence["mechanism"], "network": evidence["network"],
                              "network_isolated": evidence["network_isolated"],
                              "process_isolation": evidence["process_isolation"],
                              "writable": "the run's own tree copy and private runtime only",
                              "wall_timeout_seconds": self.timeout,
                              "cpu_seconds": evidence["limits"]["cpu_seconds"],
                              "file_bytes": evidence["limits"]["file_bytes"]}
            envelope["env"]["PYTHONDONTWRITEBYTECODE"] = "1"
            status, code, output = "exited", None, ""
            try:
                proc = supervised_run(envelope["argv"], cwd=tree, timeout=self.timeout, capture_output=True,
                                      env=envelope["env"], preexec_fn=envelope["preexec_fn"], close_fds=True)
                code, output = proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", "replace")
            except subprocess.TimeoutExpired:
                status = "timeout"
            except (WorkerError, OSError, subprocess.SubprocessError) as exc:
                status, output = "crashed", str(exc)[:300]
            data = None
            if report.is_file() and not report.is_symlink() and report.stat().st_size <= MAX_REPORT_BYTES:
                data = report.read_bytes()
            changed = tampered(expected, _manifest(tree))
            return {"status": status, "code": code, "tail": output[-1500:], "report": data, "tampered": changed}
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    def pytest(self, nodes: list[str], target_source: str | None = None) -> dict:
        def argv(report):
            return [sys.executable, "-B", "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", "--rootdir", ".",
                    "-o", "addopts=", f"--junitxml={report}", *nodes]
        out = self.run(argv, target_source)
        out["cases"] = parse_junit(out["report"]) if out["status"] == "exited" else None
        return out


def _evaluate(run: dict, regression_name: str, existing_names: list[str]) -> str:
    if run["tampered"]:
        return "tampering"
    if run["status"] == "timeout":
        return "timeout"
    cases = run["cases"]
    if run["status"] != "exited" or run["code"] not in (0, 1) or cases is None:
        return "crashed"
    by_name = {c["name"]: c["outcome"] for c in cases}
    if sorted(by_name) != sorted([regression_name, *existing_names]) or len(cases) != len(by_name):
        return "crashed"
    if any(outcome in ("error", "skipped") for outcome in by_name.values()):
        return "crashed"
    if by_name[regression_name] != "passed":
        return "regression_still_fails"
    if any(by_name[n] != "passed" for n in existing_names):
        return "broke_existing"
    return "survived" if run["code"] == 0 else "crashed"


def freeze_acceptance(manifest: dict, evaluator: dict, test_files: list[str], target: str) -> dict:
    """Digests fixed before any candidate exists; only the target module may differ afterwards."""
    return {"regression_test_sha256": manifest[REGRESSION_FILE],
            "existing_tests_sha256": {f: manifest[f] for f in test_files},
            "evaluator_inputs_sha256": _digest(evaluator),
            "frozen_tree_sha256": _digest({k: v for k, v in manifest.items() if k != target}),
            "frozen_files": len(manifest)}


def acceptance_intact(acceptance: dict, evaluator: dict, pristine: Path, target: str) -> bool:
    """The frozen acceptance still holds: evaluator inputs, regression test, existing tests, every other file."""
    current = _manifest(pristine)
    return (_digest(evaluator) == acceptance["evaluator_inputs_sha256"]
            and current.get(REGRESSION_FILE) == acceptance["regression_test_sha256"]
            and all(current.get(f) == d for f, d in acceptance["existing_tests_sha256"].items())
            and _digest({k: v for k, v in current.items() if k != target}) == acceptance["frozen_tree_sha256"])


def _tree_digest(source_root: Path, files: list[str]) -> str:
    return _digest({rel: _sha256((source_root / rel).read_bytes()) for rel in files})


def repair_source(root, *, source_root, target: str, func: str, failing: dict, passing: list[dict],
                  existing_tests: list[str], include=(), proposals=(), max_candidates: int = MAX_CANDIDATES,
                  run_timeout: float = SOURCE_RUN_TIMEOUT) -> dict:
    """Repair ``func`` in ``target`` inside a copy of ``source_root``; return a proposal, never apply it.

    Candidates are AST mutants of the original source only. A free-form proposal is refused: its code runs inside
    the process that reports its own test results, so it can forge the verdict (a rewritten junit report, a value
    that compares equal to anything, tests changed and restored within the run; independent review, 2026-10-16).
    Judging arbitrary candidate code needs the judgement outside the candidate's process and the frozen files
    mounted read-only; until then it is not admitted."""
    if proposals:
        raise RepairError("refused: a free-form proposal would run inside the process that reports its own result and "
                          "could forge it; only mutants of the original source are evaluated")
    return _repair_source(root, source_root=source_root, target=target, func=func, failing=failing, passing=passing,
                          existing_tests=existing_tests, include=include, max_candidates=max_candidates,
                          run_timeout=run_timeout)


def _repair_source(root, *, source_root, target: str, func: str, failing: dict, passing: list[dict],
                   existing_tests: list[str], include=(), max_candidates: int = MAX_CANDIDATES,
                   run_timeout: float = SOURCE_RUN_TIMEOUT, _untrusted=()) -> dict:
    """The repair loop. ``_untrusted`` lets tests feed hostile candidates to the defense-in-depth checks (tampering
    left in place, timeouts, crashes, a patch that passes only once); no operation or interface reaches it."""
    source_root = Path(source_root).resolve(strict=True)
    target = _relative(target)
    module = module_name(target)
    if not str(func).isidentifier():
        raise RepairError(f"func must be an identifier, not {func!r}")
    if not isinstance(max_candidates, int) or isinstance(max_candidates, bool) or not 1 <= max_candidates <= 200:
        raise RepairError("max_candidates must be an integer in [1, 200]")
    if isinstance(run_timeout, bool) or not 0 < float(run_timeout) <= 600:
        raise RepairError("run_timeout must be in (0, 600] seconds")
    if not existing_tests:
        raise RepairError("repair needs existing tests: a patch that passes only its own regression is not verified")
    nodes = [str(n) for n in existing_tests]
    test_files = sorted({_relative(n.split("::", 1)[0]) for n in nodes})
    if REGRESSION_FILE in test_files:
        raise RepairError(f"{REGRESSION_FILE} is reserved for the generated regression test")
    proposals = [{"label": str(p["label"]), "source": str(p["source"])} for p in _untrusted]
    if len({p["label"] for p in proposals}) != len(proposals):        # checked before anything executes
        raise RepairError("candidate labels must be unique: the recorded patch must be the one verified")
    try:
        cases = [{"args": list(failing["args"]), "expect": failing["expect"]}] + [{"args": list(c["args"])} for c in passing]
        json.dumps({"failing": failing, "passing": passing}, allow_nan=False)
    except (KeyError, TypeError, ValueError) as exc:
        raise RepairError(f"cases must be JSON values with 'args' (and 'expect' for the failing case): {exc}") from None

    files = source_closure(source_root, [target, *test_files], include)
    source_before = _tree_digest(source_root, files)
    original = (source_root / target).read_text(encoding="utf-8")

    # Scratch lives under the store, held by one lock: a run killed mid-way leaves its directory behind, and the
    # next run, holding the same lock, removes it before starting.
    import fcntl
    parent = Path(root) / "repair-scratch"
    parent.mkdir(parents=True, exist_ok=True)
    guard = open(parent / ".lock", "a")
    try:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        guard.close()
        raise RepairError("another source repair is running on this store") from None
    for stale in parent.glob("foundry-repair-*"):
        shutil.rmtree(stale, ignore_errors=True)
    scratch = Path(tempfile.mkdtemp(prefix="foundry-repair-", dir=parent))
    try:
        pristine = scratch / "pristine"
        for rel in files:
            destination = pristine / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_root / rel, destination)
        regression, regression_name, assert_line = regression_source(module, func, {**failing, "id": failing.get("id", "case")})
        (pristine / REGRESSION_FILE).write_text(regression, encoding="utf-8")

        # -- freeze acceptance before any candidate exists ------------------------------------------
        manifest = _manifest(pristine)
        evaluator = {"module": module, "func": func, "target": target, "failing": failing, "passing": passing,
                     "existing_tests": nodes, "regression_test": REGRESSION_FILE, "assert_line": assert_line,
                     "run_timeout": float(run_timeout), "max_candidates": max_candidates,
                     "outcomes": list(OUTCOMES)}
        acceptance = freeze_acceptance(manifest, evaluator, test_files, target)

        runner = _Runner(scratch, pristine, manifest, target, float(run_timeout))

        # -- diagnosis: line spectra of the failing and passing cases, traced inside the envelope ------
        traced = runner.run(lambda report: [sys.executable, "-B", "-c", _TRACER, json.dumps(
            {"target": target, "module": module, "func": func, "cases": cases, "report": str(report)})])
        rows = None
        if traced["status"] == "exited" and traced["code"] == 0 and not traced["tampered"] and traced["report"]:
            try:
                rows = json.loads(traced["report"])
            except ValueError:
                rows = None
        if not _report_rows(rows, len(cases)):
            raise RepairError(f"diagnosis could not run the target ({traced['status']}, exit {traced['code']}, "
                              f"tampered {traced['tampered'][:5]}): {traced['tail'][-300:]}")
        failing_row = rows[0]
        symptom = {"observed": failing_row.get("observed"), "raised": failing_row.get("raised"),
                   "expected": repr(failing["expect"])[:500]}
        f_cov, p_cov = [set(failing_row["lines"])], [set(r["lines"]) for r in rows[1:]]
        target_lines = original.splitlines()
        ranked = []
        for line in sorted(set().union(*f_cov, *p_cov)):
            ef, ep = sum(line in c for c in f_cov), sum(line in c for c in p_cov)
            score = ef / math.sqrt(len(f_cov) * (ef + ep)) if ef else 0.0
            text = target_lines[line - 1].strip() if 0 < line <= len(target_lines) else ""
            ranked.append({"line": line, "score": round(score, 4), "text": text})
        diagnosis = sorted(ranked, key=lambda r: (-r["score"], r["line"]))
        suspects = suspect_lines(diagnosis)

        # -- the regression test must fail for the intended reason on the current code ----------------
        before = runner.pytest([REGRESSION_FILE])
        intended, why = (False, "the before-run tampered with the frozen tree") if before["tampered"] else \
            (False, "the before-run timed out") if before["status"] == "timeout" else \
            (False, f"pytest exited {before['code']}") if before["code"] != 1 else \
            fails_by_assertion(before["cases"], regression_name, assert_line)
        if not intended:
            raise RepairError(f"refused: the regression test does not fail for the intended reason ({why}); "
                              "an ImportError, collection error, other exception or timeout is not failing-before evidence")
        baseline = runner.pytest(nodes)
        if baseline["tampered"] or baseline["status"] != "exited" or baseline["cases"] is None \
                or not baseline["cases"] or any(c["outcome"] in ("error", "skipped") for c in baseline["cases"]):
            raise RepairError(f"existing tests cannot be evaluated on the current code: {baseline['tail'][-300:]}")
        existing_names = [c["name"] for c in baseline["cases"]]
        if len(set(existing_names)) != len(existing_names) or regression_name in existing_names:
            raise RepairError("existing test names must be unique and distinct from the regression test")

        # -- competing candidates under the frozen acceptance ------------------------------------------
        pool = [{"label": label, "origin": "mutation", "source": patched}
                for label, patched in source_mutants(original, suspects)]
        pool += [{"label": p["label"], "origin": "proposal", "source": p["source"]} for p in proposals]
        labels = [c["label"] for c in pool]
        if len(set(labels)) != len(labels):
            raise RepairError("candidate labels must be unique: the recorded patch must be the one verified")
        evaluated, not_evaluated = pool[:max_candidates], len(pool) - min(len(pool), max_candidates)
        tried = []
        for index, candidate in enumerate(evaluated):
            outcome = _evaluate(runner.pytest([REGRESSION_FILE, *nodes], candidate["source"]),
                                regression_name, existing_names)
            if not acceptance_intact(acceptance, evaluator, pristine, target):
                raise RepairError("refused: the frozen acceptance changed during candidate evaluation")
            diff = "".join(difflib.unified_diff(original.splitlines(True), candidate["source"].splitlines(True),
                                                f"a/{target}", f"b/{target}"))
            tried.append({"patch": candidate["label"], "origin": candidate["origin"], "outcome": outcome,
                          "diff_lines": sum(1 for ln in diff.splitlines() if ln[:1] in "+-" and ln[:3] not in ("+++", "---")),
                          "size": len(candidate["source"]), "diff": diff,
                          "sha256": _sha256(candidate["source"].encode("utf-8")), "index": index})
        survivors = sorted((t for t in tried if t["outcome"] == "survived"),
                           key=lambda t: (t["diff_lines"], t["size"], t["patch"]))
        outcomes = [{k: t[k] for k in ("patch", "origin", "outcome", "diff_lines")} for t in tried]
        if not survivors:
            raise RepairEscalation(
                f"no candidate survives ({len(tried)} tried, {not_evaluated} over the cap); escalate with the diagnosis",
                {"status": "ESCALATED", "symptom": symptom, "diagnosis": [d for d in diagnosis if d["line"] in suspects],
                 "suspects": suspects, "candidates": outcomes, "not_evaluated": not_evaluated, "acceptance": acceptance})
        chosen = survivors[0]
        fixed = evaluated[chosen["index"]]["source"]
        if _sha256(fixed.encode("utf-8")) != chosen["sha256"]:
            raise RepairError("the patch to verify is not the one recorded")

        # -- verified recovery: an independent fresh run of the chosen patch ---------------------------
        after = runner.pytest([REGRESSION_FILE, *nodes], fixed)
        after_outcome = _evaluate(after, regression_name, existing_names)
        if after_outcome != "survived" or not acceptance_intact(acceptance, evaluator, pristine, target):
            raise RepairError(f"the chosen patch did not reproduce on verification ({after_outcome})")
        after_cases = after["cases"]
        isolation = runner.isolation
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        guard.close()

    if _tree_digest(source_root, files) != source_before:
        raise RepairError("the source tree changed during repair; the proposal is void")
    procedure = {"symptom": {"module": module, "function": func, "case": failing, **symptom},
                 "diagnosis": [d for d in diagnosis if d["line"] in suspects], "target": target,
                 "fix": chosen["patch"], "origin": chosen["origin"], "diff": chosen["diff"],
                 "patched_sha256": chosen["sha256"], "regression_test": regression, "acceptance": acceptance,
                 "verified_after": {c["name"]: c["outcome"] for c in after_cases}, "isolation": isolation,
                 "candidates": outcomes, "not_evaluated": not_evaluated,
                 "status": "PROPOSED", "applies_to_source": False,
                 "promotion": "none: applying the patch to a real tree is a separate reviewed act"}
    record = versions.commit(Path(root) / "procedures", f"recovery:{module}.{func}", procedure,
                             reason=f"source repair {module}.{func}: {chosen['patch']}",
                             evidence=[str(failing.get("id", "case")), acceptance["evaluator_inputs_sha256"]])
    return {"status": "PROPOSED", "module": module, "target": target, "recipe_files": len(files),
            "symptom": symptom, "suspects": suspects, "diagnosis": procedure["diagnosis"],
            "regression_before": {"failed_for_intended_reason": True, "reason": why,
                                  "message": before["cases"][0]["message"][:300]},
            "existing_tests": existing_names, "acceptance": acceptance, "candidates": outcomes,
            "not_evaluated": not_evaluated, "survivors": [t["patch"] for t in survivors], "chosen": chosen["patch"],
            "diff": chosen["diff"], "after": {c["name"]: c["outcome"] for c in after_cases},
            "after_passed": all(c["outcome"] == "passed" for c in after_cases), "isolation": isolation,
            "procedure_version": record["n"], "source_tree_unchanged": True, "applies_to_source": False,
            "promotion": procedure["promotion"]}


QUERY_OPS = {"localize": lambda a, r: {"ranked": localize(a["source"], a["func"], a["failing"], a["passing"])}}
APPLY_OPS = {"repair": lambda a, r: repair(r, source=a["source"], func=a["func"], failing=a["failing"],
                                           passing=a["passing"], existing_tests=a["existing_tests"]),
             "repair_source": lambda a, r: repair_source(
                 r, source_root=a["source_root"], target=a["target"], func=a["func"], failing=a["failing"],
                 passing=a.get("passing", []), existing_tests=a["existing_tests"], include=a.get("include", ()),
                 proposals=a.get("proposals", ()), max_candidates=int(a.get("max_candidates", MAX_CANDIDATES)),
                 run_timeout=float(a.get("run_timeout", SOURCE_RUN_TIMEOUT)))}


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


def exercise_fixture(root) -> dict:
    failing = {"id": "inv-100-3", "args": [100, 3], "expect": [34, 33, 33]}
    passing = [{"args": [90, 3]}, {"args": [10, 1]}, {"args": [60, 4]}]
    out = repair(Path(root), source=TARGET, func="split_invoice", failing=failing, passing=passing,
                 existing_tests=EXISTING)
    return {k: out[k] for k in ("symptom", "suspects", "tied", "regression_before", "candidates", "survivors", "chosen",
                                "diff", "after", "after_passed", "procedure_version")} | {
        "rejected_that_broke_existing_tests": [r["patch"] for r in out["rejected"]
                                               if r["regression_passes"] and r["existing_pass"] is False]}


# A real repository module and its real test, copied; one off-by-one boundary fault is seeded into the copy.
REPO_ROOT = Path(__file__).resolve().parents[2]
SEEDED_TARGET = "foundry/systems/dsl.py"
SEEDED_TESTS = ["tests/unit/test_foundry_systems.py::test_dsl_runs_narrow_rules_and_rejects_code"]
SEEDED_INCLUDE = ["contracts"]   # the test module reads JSON schemas at import time
SEEDED_FAULT = ("ast.LtE: lambda a, b: a <= b", "ast.LtE: lambda a, b: a < b")
SEEDED_FAILING = {"id": "lte-boundary", "args": ["pricing", "1 if units <= 10 else 2", {"units": 10}], "expect": 1}
SEEDED_PASSING = [{"args": ["pricing", "1 if units >= 10 else 2", {"units": 10}]},
                  {"args": ["pricing", "1 if units == 3 else 2", {"units": 10}]},
                  {"args": ["budget", "min(requested, remaining - reserve)",
                            {"remaining": 1000, "requested": 1500, "reserve": 200}]}]


def seed_fault_copy(destination: Path, source_root: Path = REPO_ROOT) -> list[str]:
    """Copy the target's recipe out of the repository and seed the fault into the copy only."""
    files = source_closure(source_root, [SEEDED_TARGET, *sorted({n.split("::")[0] for n in SEEDED_TESTS})], SEEDED_INCLUDE)
    for rel in files:
        (destination / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root / rel, destination / rel)
    text = (destination / SEEDED_TARGET).read_text(encoding="utf-8")
    if text.count(SEEDED_FAULT[0]) != 1:
        raise RepairError("the seeded-fault site is not unique in the repository module")
    (destination / SEEDED_TARGET).write_text(text.replace(*SEEDED_FAULT), encoding="utf-8")
    return files


def exercise_source(root) -> dict:
    root = Path(root)
    files = seed_fault_copy(root / "seeded-copy")
    repository_before = _tree_digest(REPO_ROOT, files)
    try:
        out = repair_source(root / "store", source_root=root / "seeded-copy", target=SEEDED_TARGET, func="run",
                            failing=SEEDED_FAILING, passing=SEEDED_PASSING, existing_tests=SEEDED_TESTS,
                            include=SEEDED_INCLUDE)
    except RepairError as exc:
        if "isolation envelope" not in str(exc):
            raise
        return {"refused": "worker OS isolation (bubblewrap user/network namespaces) unavailable on this host"}
    # The frozen closure's size is left out: it is the import closure of the target and its test, so any import added
    # anywhere in that closure changed it and the recorded evidence stopped reproducing (fifth review, M1).
    return {k: out[k] for k in ("status", "target", "symptom", "suspects", "regression_before", "existing_tests",
                                "candidates", "survivors", "chosen", "diff", "after", "after_passed", "isolation",
                                "procedure_version", "source_tree_unchanged", "applies_to_source", "promotion")} | {
        "fault": SEEDED_FAULT[1], "repository_unchanged": _tree_digest(REPO_ROOT, files) == repository_before}


def exercise(root) -> dict:
    return exercise_fixture(Path(root) / "fixture") | {"source_repair": exercise_source(Path(root) / "source")}
