"""What a pre-registered evaluation freezes: every repository file the run can execute, and the versions of the
numerical dependencies it imports.

A hand-picked file list misses modules on the path (the P6 v1/v2 freezes did not hash ``greg/capabilities.py``,
the genome admission freeze did not hash ``cortex.py``, ``solvers.py`` or the M4 data). The closure here is
static: every ``import`` (nested ones included) reachable from the entry points, resolved inside the
repository, plus whole packages that import modules by name, plus declared data and pins.
"""
from __future__ import annotations

import ast
import importlib.metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _module_files(name: str, root: Path) -> list[Path]:
    parts = name.split(".")
    for i in range(len(parts), 0, -1):
        base = root.joinpath(*parts[:i])
        for found in (base.with_suffix(".py"), base / "__init__.py"):
            if found.is_file():
                inits = [root.joinpath(*parts[:j], "__init__.py") for j in range(1, i)]
                return [found, *(f for f in inits if f.is_file())]
    return []


def code_closure(entry_points, *, packages=(), extra=(), root: Path = ROOT) -> list[str]:
    """Repository-relative paths of the static import closure of ``entry_points`` and of every ``.py`` file
    under ``packages`` (for code that imports by name), plus ``extra`` files (data, pins, scripts loaded by
    path). Missing extras raise: a freeze must not silently hash less than it names."""
    seen, todo = set(), [root / p for p in entry_points]
    for package in packages:
        todo += sorted((root / package).rglob("*.py"))
    while todo:
        path = todo.pop()
        if path in seen:
            continue
        seen.add(path)
        package = path.relative_to(root).parts[:-1]
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    todo += _module_files(alias.name, root)
            elif isinstance(node, ast.ImportFrom):
                base = list(package[:len(package) - node.level + 1]) if node.level else []
                module = ".".join([*base, *(node.module.split(".") if node.module else [])])
                todo += _module_files(module, root)
                for alias in node.names:
                    todo += _module_files(f"{module}.{alias.name}" if module else alias.name, root)
    missing = [p for p in extra if not (root / p).is_file()]
    if missing:
        raise FileNotFoundError(f"freeze names files that do not exist: {missing}")
    files = {str(p.relative_to(root)) for p in seen if "__pycache__" not in p.parts}
    return sorted(files | set(extra))


def dependency_versions(names=("numpy", "scipy", "networkx", "ortools", "z3-solver", "sympy")) -> dict:
    out = {}
    for name in names:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            out[name] = None
    return out
