"""Bind a positive verdict to the executable code it measured: the function's dependency closure, not its name.

A solver's entry function can call helpers, read module constants (thresholds, tables, defaults) and instantiate
classes. Binding a verdict to the entry function's source alone lets a helper or configuration change alter
behaviour under an unchanged digest. ``closure`` follows, statically and transitively, every repository
definition the entry function references:

* module-level functions, classes and assignments of its own module (a class is hashed whole, methods included);
* names imported from repository modules (``from x import y``, relative imports included);
* attributes of imported repository modules (``import x.y as z`` then ``z.f``, and unaliased dotted chains
  ``import x.y`` then ``x.y.f``);
* repository names imported inside the function body, and names it declares ``global``.

A module-level name is hashed as every top-level statement that binds or mutates it, in order (``T = {...}``,
``T['k'] = v``, ``T.update(...)``, ``T += ...``), so an edit to an original literal that a later statement
mutates still changes the digest. Locals are computed per function, so a method's parameter never hides a module
function another method calls. ``dispatch`` resolves which function a dispatch table bound a key to at a given
commit, so a verdict is never bound to a function its run did not call (review of #179, B1 and B2).

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


def _base(expr: ast.AST) -> str | None:
    """The name at the root of a target or call chain: ``T`` for ``T``, ``T['k']``, ``T.a.b`` and ``T.update``."""
    while isinstance(expr, (ast.Subscript, ast.Attribute)):
        expr = expr.value
    return expr.id if isinstance(expr, ast.Name) else None


def _definitions(tree: ast.Module) -> dict[str, list[ast.AST]]:
    """Every top-level statement that binds or mutates each module-level name, in source order."""
    out: dict[str, list[ast.AST]] = {}
    for node in tree.body:
        names: set[str] = set()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = {node.name}
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                names |= {n.id for n in ast.walk(t) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
                if (root := _base(t)) is not None:
                    names.add(root)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
            if (root := _base(node.value.func)) is not None:     # T.update(...), T.append(...), T.setdefault(...)
                names.add(root)
        for name in names:
            out.setdefault(name, []).append(node)
    return out


def _locals(node: ast.AST) -> set[str]:
    """Names bound inside one function (arguments, assignments, loop and comprehension targets, nested defs and
    imports): a reference to one is local, never a module-level dependency. A name declared ``global`` is not
    local."""
    out: set[str] = set()
    declared_global = {n for sub in ast.walk(node) if isinstance(sub, ast.Global) for n in sub.names}
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
    return out - declared_global


def _module_path(module: str, read: Reader) -> str | None:
    base = module.replace(".", "/")
    for candidate in (f"{base}.py", f"{base}/__init__.py"):
        if read(candidate) is not None:
            return candidate
    return None


def _imports(tree: ast.AST, path: str, read: Reader) -> tuple[dict, dict]:
    """(names imported from repository modules -> (module path, original name), module aliases -> module path).
    An unaliased ``import x.y`` also maps the dotted name ``x.y`` to its path, for dotted attribute chains."""
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
                if not alias.asname and "." in alias.name:
                    parts = alias.name.split(".")
                    for i in range(2, len(parts) + 1):
                        dotted = _module_path(".".join(parts[:i]), read)
                        if dotted is not None:
                            modules[".".join(parts[:i])] = dotted
    return names, modules


def _chain(expr: ast.AST) -> list[str] | None:
    parts = []
    while isinstance(expr, ast.Attribute):
        parts.append(expr.attr)
        expr = expr.value
    return [expr.id, *reversed(parts)] if isinstance(expr, ast.Name) else None


def _scopes(node: ast.AST) -> list[tuple[ast.AST, set[str]]]:
    """(subtree, its locals): one scope per function. A class's methods each get their own locals, so a parameter
    of one method never hides a module function another method calls; class-level statements have none."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return [(node, _locals(node))]
    if isinstance(node, ast.ClassDef):
        out = []
        for stmt in [*node.decorator_list, *node.bases, *node.body]:
            out += _scopes(stmt) if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                else [(stmt, set())]
        return out
    return [(node, set())]


def _references(node, own: str, p: str, defs: dict, names: dict, modules: dict, read: Reader) -> list[tuple]:
    out = []
    for scope, local in _scopes(node):
        # repository names imported inside the function body are dependencies, not locals
        inner_names, inner_modules = _imports(scope, p, read) if scope is not node or not isinstance(
            node, ast.Module) else ({}, {})
        local = local - set(inner_names) - set(inner_modules)
        scope_names, scope_modules = {**names, **inner_names}, {**modules, **inner_modules}
        for sub in ast.walk(scope):
            if isinstance(sub, ast.Name) and sub.id != own and sub.id not in local:
                if sub.id in defs:
                    out.append((p, sub.id))
                elif sub.id in scope_names:
                    out.append(scope_names[sub.id])
            elif isinstance(sub, ast.Attribute):
                chain = _chain(sub)
                if not chain or chain[0] in local:
                    continue
                # the longest dotted prefix that names a repository module, then the attribute after it
                for cut in range(len(chain) - 1, 0, -1):
                    dotted = ".".join(chain[:cut])
                    if dotted in scope_modules:
                        out.append((scope_modules[dotted], chain[cut]))
                        break
    return out


def dispatch(path: str, table: str, key: str, read: Reader = working_tree) -> dict | None:
    """Which function the module-level dispatch table ``table`` in ``path`` binds ``key`` to, statically, in that
    tree: ``{"path", "function"}``, or None when no literal statement binds it. Statements are read in order:
    ``T = {...}``, ``T.update({...})``, ``T.update(NAME)`` with NAME a dict literal in a repository module, and
    ``T[k] = f``. A non-literal update (a comprehension) is listed in ``unresolved_updates``; it cannot bind a
    literal key it does not name, which the caller states rather than hides."""
    text = read(path)
    if text is None:
        return None
    tree = ast.parse(text)
    names, modules = _imports(tree, path, read)
    bound, unresolved = None, 0

    def resolve(value, module_path, module_names, module_defs):
        if isinstance(value, ast.Attribute) and isinstance(value.value, ast.Call) \
                and isinstance(value.value.func, ast.Name) and value.value.func.id == "__import__" \
                and value.value.args and isinstance(value.value.args[0], ast.Constant):
            target = _module_path(value.value.args[0].value, read)        # __import__("pkg.mod", ...).name
            if target is not None:
                return {"path": target, "function": value.attr}
        if isinstance(value, ast.Name):
            if value.id in module_names:
                return {"path": module_names[value.id][0], "function": module_names[value.id][1]}
            if value.id in module_defs:
                return {"path": module_path, "function": value.id}
        return {"path": None, "function": None, "expression": ast.unparse(value)}

    def from_literal(d, module_path, module_names, module_defs):
        for k, v in zip(d.keys, d.values):
            if isinstance(k, ast.Constant) and k.value == key:
                return resolve(v, module_path, module_names, module_defs)
        return None

    defs = _definitions(tree)
    for node in tree.body:
        found = None
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == table for t in node.targets):
            bound = from_literal(node.value, path, names, defs) if isinstance(node.value, ast.Dict) else None
            continue
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Subscript) and _base(t) == table
                                                 and isinstance(t.slice, ast.Constant) and t.slice.value == key
                                                 for t in node.targets):
            found = resolve(node.value, path, names, defs)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) \
                and _base(node.value.func) == table and node.value.func.attr == "update" and node.value.args:
            arg = node.value.args[0]
            if isinstance(arg, ast.Dict):
                found = from_literal(arg, path, names, defs)
            elif isinstance(arg, ast.Name) and arg.id in names:
                other_path, other_name = names[arg.id]
                other_text = read(other_path)
                other_tree = ast.parse(other_text) if other_text else None
                other_defs = _definitions(other_tree) if other_tree else {}
                literal = [n for n in other_defs.get(other_name, []) if isinstance(n, ast.Assign)
                           and isinstance(n.value, ast.Dict)]
                if literal:
                    found = from_literal(literal[-1].value, other_path, _imports(other_tree, other_path, read)[0],
                                         other_defs)
                else:
                    unresolved += 1
            else:
                unresolved += 1
        if found is not None:
            bound = found
    if bound is None:
        return None
    return {**bound, "unresolved_updates": unresolved}


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
        nodes = defs[n]
        members[key] = "sha256:" + hashlib.sha256("\n".join(_segment(text, x) for x in nodes).encode()).hexdigest()
        for node in nodes:
            todo += _references(node, n, p, defs, names, modules, read)
    joint = "\n".join(f"{k}={v}" for k, v in sorted(members.items()))
    return {"entry": f"{path}::{name}", "members": dict(sorted(members.items())),
            "sha256": "sha256:" + hashlib.sha256(joint.encode()).hexdigest()}
