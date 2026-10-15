"""Bind a positive verdict to the executable code it measured: the function's dependency closure, not its name.

A solver's entry function can call helpers, read module constants (thresholds, tables, defaults) and instantiate
classes. Binding a verdict to the entry function's source alone lets a helper or configuration change alter
behaviour under an unchanged digest. ``closure`` follows, statically and transitively, every repository
definition the entry function references:

* module-level functions, classes and assignments of its own module (a class is hashed whole, methods included);
* names imported from repository modules (``from x import y``, relative imports included);
* attributes of imported repository modules (``import x.y as z`` then ``z.f``).

Each member is hashed as source text (decorators included, trailing whitespace stripped), so the digest does not
change with the Python version. The same function runs on the working tree and on any commit (``git show``), so a
verdict measured at a source commit is compared with today's code member by member.

Not covered, stated rather than hidden: third-party package versions, code reached only dynamically (``getattr``
on strings, ``importlib``), and data files a function opens by path. ``cortex.evaluation.closure`` freezes those
for a whole evaluation run.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import subprocess
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]

Reader = Callable[[str], "str | None"]


def working_tree(path: str) -> str | None:
    target = ROOT / path
    return target.read_text(encoding="utf-8") if target.is_file() else None


def at_commit(commit: str) -> Reader:
    def read(path: str) -> str | None:
        out = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True, text=True,
                             timeout=60)
        return out.stdout if out.returncode == 0 else None
    return read


def _segment(text: str, node: ast.AST) -> str:
    start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    return "\n".join(line.rstrip() for line in text.splitlines()[start - 1:node.end_lineno])


def _definitions(tree: ast.Module) -> dict[str, ast.AST]:
    out: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        out[n.id] = node
    return out


def _locals(node: ast.AST) -> set[str]:
    """Names bound inside a definition (arguments, assignments, loop and comprehension targets, nested defs and
    imports): a reference to one is local, never a module-level dependency."""
    out: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            a = sub.args
            out |= {x.arg for x in [*a.posonlyargs, *a.args, *a.kwonlyargs, *([a.vararg] if a.vararg else []),
                                    *([a.kwarg] if a.kwarg else [])]}
            if sub is not node and not isinstance(sub, ast.Lambda):
                out.add(sub.name)
        elif isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
            out.add(sub.id)
        elif isinstance(sub, (ast.Import, ast.ImportFrom)) and sub is not node:
            out |= {al.asname or al.name.split(".")[0] for al in sub.names}
        elif isinstance(sub, ast.ExceptHandler) and sub.name:
            out.add(sub.name)
    return out


def _module_path(module: str, read: Reader) -> str | None:
    base = module.replace(".", "/")
    for candidate in (f"{base}.py", f"{base}/__init__.py"):
        if read(candidate) is not None:
            return candidate
    return None


def _imports(tree: ast.Module, path: str, read: Reader) -> tuple[dict, dict]:
    """(names imported from repository modules -> (module path, original name), module aliases -> module path)."""
    package = path.split("/")[:-1]
    names, modules = {}, {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = package[:len(package) - node.level + 1] if node.level else []
            module = ".".join([*base, *(node.module.split(".") if node.module else [])])
            target = _module_path(module, read) if module else None
            for alias in node.names:
                sub = _module_path(f"{module}.{alias.name}" if module else alias.name, read)
                if sub is not None:
                    modules[alias.asname or alias.name] = sub
                elif target is not None:
                    names[alias.asname or alias.name] = (target, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                target = _module_path(alias.name if alias.asname else bound, read)
                if target is not None:
                    modules[bound] = target
    return names, modules


def closure(path: str, name: str, read: Reader = working_tree) -> dict | None:
    """Members (``path::name`` -> sha256) of the static dependency closure of ``name`` in ``path``, and their joint
    digest; None when the entry definition does not exist in that tree."""
    parsed: dict[str, tuple] = {}

    def module(p):
        if p not in parsed:
            text = read(p)
            if text is None:
                parsed[p] = None
            else:
                tree = ast.parse(text)
                parsed[p] = (text, tree, _definitions(tree), *_imports(tree, p, read))
        return parsed[p]

    entry = module(path)
    if entry is None or name not in entry[2]:
        return None
    members, todo = {}, [(path, name)]
    while todo:
        p, n = todo.pop()
        key = f"{p}::{n}"
        if key in members:
            continue
        m = module(p)
        if m is None or n not in m[2]:
            continue
        text, _tree, defs, names, modules = m
        node = defs[n]
        members[key] = "sha256:" + hashlib.sha256(_segment(text, node).encode()).hexdigest()
        local = _locals(node) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and sub.id != n and sub.id not in local:
                if sub.id in defs:
                    todo.append((p, sub.id))
                elif sub.id in names:
                    todo.append(names[sub.id])
            elif isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id in modules:
                todo.append((modules[sub.value.id], sub.attr))
    joint = "\n".join(f"{k}={v}" for k, v in sorted(members.items()))
    return {"entry": f"{path}::{name}", "members": dict(sorted(members.items())),
            "sha256": "sha256:" + hashlib.sha256(joint.encode()).hexdigest()}
