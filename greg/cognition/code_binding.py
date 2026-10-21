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


SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef, ast.ListComp, ast.SetComp, ast.DictComp,
          ast.GeneratorExp)
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _bindings(node: ast.AST) -> set[str]:
    """Names one top-level statement binds or mutates anywhere inside it, never inside a function or class body:
    assignment, deletion and loop targets and their roots (``T['k'] = v``, ``del T['k']``, ``for T[k] in ...``),
    roots of method-call statements (``T.update(...)``), and defs, classes and imports nested in ``if``/``try``/
    ``with``/``for`` blocks (round-2 review of #179, N4)."""
    names: set[str] = set()
    pending = [node]
    while pending:
        sub = pending.pop()
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(sub.name)
            continue
        if isinstance(sub, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            continue
        if isinstance(sub, (ast.Import, ast.ImportFrom)) and sub is not node:
            names |= {a.asname or a.name.split(".")[0] for a in sub.names if a.name != "*"}
        elif isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
            names.add(sub.id)
        elif isinstance(sub, (ast.Subscript, ast.Attribute)) and isinstance(sub.ctx, (ast.Store, ast.Del)):
            if (root := _base(sub)) is not None:
                names.add(root)
        elif isinstance(sub, ast.Expr) and isinstance(sub.value, ast.Call) and isinstance(sub.value.func, ast.Attribute):
            if (root := _base(sub.value.func)) is not None:      # T.update(...), T.append(...), T.setdefault(...)
                names.add(root)
        elif isinstance(sub, ast.ExceptHandler) and sub.name:
            names.add(sub.name)
        pending.extend(ast.iter_child_nodes(sub))
    return names


def _definitions(tree: ast.Module) -> dict[str, list[ast.AST]]:
    """Every top-level statement that binds or mutates each module-level name, in source order. A plain top-level
    import is resolved by ``_imports`` instead; an import inside a compound statement (a guarded fallback) is a
    definition, so the guard and its fallback are hashed."""
    out: dict[str, list[ast.AST]] = {}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for name in _bindings(node):
            out.setdefault(name, []).append(node)
    return out


def _direct(node: ast.AST):
    """Nodes evaluated in ``node``'s own scope: never a nested scope's body, but the decorators, defaults, bases and
    first iterable that the enclosing scope evaluates; nested scope nodes themselves are yielded for recursion."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        roots = node.body
    elif isinstance(node, ast.Lambda):
        roots = [node.body]
    elif isinstance(node, ast.ClassDef):
        roots = node.body
    elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        roots = [node.elt, *[g.target for g in node.generators], *[x for g in node.generators[1:] for x in (g.iter,)],
                 *[c for g in node.generators for c in g.ifs]]
    elif isinstance(node, ast.DictComp):
        roots = [node.key, node.value, *[g.target for g in node.generators],
                 *[g.iter for g in node.generators[1:]], *[c for g in node.generators for c in g.ifs]]
    else:
        roots = [node]
    pending = list(roots)
    while pending:
        sub = pending.pop()
        yield sub
        if isinstance(sub, SCOPES):
            outer = []                               # evaluated where the nested scope is defined
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                outer += sub.decorator_list
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                outer += [d for d in [*sub.args.defaults, *sub.args.kw_defaults] if d is not None]
            if isinstance(sub, ast.ClassDef):
                outer += [*sub.bases, *[k.value for k in sub.keywords]]
            if isinstance(sub, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
                outer.append(sub.generators[0].iter)
            pending.extend(outer)
            continue
        pending.extend(ast.iter_child_nodes(sub))


def _own_locals(node: ast.AST) -> set[str]:
    """Names bound in ``node``'s own scope (parameters, assignments, loop and comprehension targets, nested def
    names, imports, exception names), minus names it declares ``global``. Nested scopes are excluded, so a nested
    function's parameter never hides a module function the outer body calls."""
    out: set[str] = set()
    if isinstance(node, FUNCTIONS):
        a = node.args
        out |= {x.arg for x in [*a.posonlyargs, *a.args, *a.kwonlyargs, *([a.vararg] if a.vararg else []),
                                *([a.kwarg] if a.kwarg else [])]}
    declared_global = set()
    for sub in _direct(node):
        if sub is node:
            continue
        if isinstance(sub, ast.Global):
            declared_global |= set(sub.names)
        elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(sub.name)
        elif isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
            out.add(sub.id)
        elif isinstance(sub, (ast.Import, ast.ImportFrom)):
            out |= {al.asname or al.name.split(".")[0] for al in sub.names if al.name != "*"}
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
                if alias.name == "*":
                    if target is not None:                       # resolved name by name in closure()
                        modules.setdefault("*", []).append(target)
                    continue
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


def _dynamic_module(call: ast.AST, read: Reader) -> tuple[str | None, bool]:
    """(module path, is_dynamic_import) for ``importlib.import_module("x")``, ``import_module("x")`` or
    ``__import__("x")``; a non-constant argument is a dynamic import the closure cannot follow."""
    if not isinstance(call, ast.Call):
        return None, False
    f = call.func
    name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else None
    if name not in ("import_module", "__import__"):
        return None, False
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return _module_path(call.args[0].value, read), True
    return None, True


def _references(node, own: str, p: str, defs: dict, names: dict, modules: dict, read: Reader,
                star_defs: dict | None = None, unresolved: list | None = None) -> list[tuple]:
    """Repository definitions ``node`` references, scope by scope (round-2 review of #179, N4): each function,
    lambda, comprehension and class has its own locals; a function's locals are visible to the scopes nested in it,
    a class body's are not; a nested scope's names never hide a module name the outer body uses."""
    out: list[tuple] = []
    star_defs = star_defs or {}

    def visit(scope, enclosing: set, scope_names: dict, scope_modules: dict):
        top = not isinstance(scope, SCOPES)
        local = set() if top else _own_locals(scope)
        inner_names, inner_modules = ({}, {}) if top else _imports_direct(scope, p, read)
        # a dynamic import bound to a name in this scope (m = import_module("x")) is a module alias
        for sub in ([] if top else _direct(scope)):
            if isinstance(sub, ast.Assign) and len(sub.targets) == 1 and isinstance(sub.targets[0], ast.Name):
                target, dynamic = _dynamic_module(sub.value, read)
                if target is not None:
                    inner_modules[sub.targets[0].id] = target
                elif dynamic and unresolved is not None:
                    unresolved.append(f"{p}::{own}: dynamic import with a non-constant module name")
        local = local - set(inner_names) - set(inner_modules)
        names_here, modules_here = {**scope_names, **inner_names}, {**scope_modules, **inner_modules}
        hidden = local | enclosing
        for sub in _direct(scope):
            if sub is not scope and isinstance(sub, SCOPES):
                visit(sub, hidden if isinstance(scope, FUNCTIONS) or top else enclosing, names_here, modules_here)
                continue
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load) and sub.id != own and sub.id not in hidden:
                if sub.id in defs:
                    out.append((p, sub.id))
                elif sub.id in names_here:
                    out.append(names_here[sub.id])
                elif sub.id in star_defs:
                    out.append(star_defs[sub.id])
            elif isinstance(sub, ast.Attribute):
                chain = _chain(sub)
                if chain is None:
                    target, dynamic = _dynamic_module(sub.value, read)
                    if target is not None:
                        out.append((target, sub.attr))
                    elif dynamic and unresolved is not None:
                        unresolved.append(f"{p}::{own}: dynamic import with a non-constant module name")
                    continue
                if chain[0] in hidden and chain[0] not in inner_modules:
                    continue
                for cut in range(len(chain) - 1, 0, -1):      # the longest dotted prefix naming a repository module
                    dotted = ".".join(chain[:cut])
                    if dotted in modules_here and isinstance(modules_here[dotted], str):
                        out.append((modules_here[dotted], chain[cut]))
                        break
            elif isinstance(sub, ast.Call) and unresolved is not None:
                target, dynamic = _dynamic_module(sub, read)
                if dynamic and target is None:
                    unresolved.append(f"{p}::{own}: dynamic import with a non-constant module name")

    if isinstance(node, SCOPES):            # a member def or class: its decorators, defaults and bases first
        outer = list(getattr(node, "decorator_list", []))
        if isinstance(node, FUNCTIONS):
            outer += [d for d in [*node.args.defaults, *node.args.kw_defaults] if d is not None]
        if isinstance(node, ast.ClassDef):
            outer += [*node.bases, *[k.value for k in node.keywords]]
        for expr in outer:
            visit(expr, set(), names, modules)
    visit(node, set(), names, modules)
    return out


def _imports_direct(scope: ast.AST, path: str, read: Reader) -> tuple[dict, dict]:
    """``_imports`` restricted to the imports in ``scope``'s own body (never a nested scope's)."""
    holder = ast.Module(body=[n for n in _direct(scope) if isinstance(n, (ast.Import, ast.ImportFrom))],
                        type_ignores=[])
    names, modules = _imports(holder, path, read)
    modules.pop("*", None)
    return names, modules


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

    def mutates(fn) -> bool:
        """A function body that rebinds or mutates the table (a helper called at import time could)."""
        for sub in ast.walk(fn):
            if isinstance(sub, (ast.Subscript, ast.Attribute)) and isinstance(sub.ctx, (ast.Store, ast.Del)) \
                    and _base(sub) == table:
                return True
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and _base(sub.func) == table \
                    and sub.func.attr not in ("get", "items", "keys", "values", "copy", "__getitem__", "__contains__"):
                return True
            if isinstance(sub, ast.Global) and table in sub.names:
                return True
        return False

    for node in tree.body:
        found = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and mutates(node):
            unresolved += 1                       # round-3 review of #179, finding 2: a mutating helper
            continue
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
        elif table in _bindings(node) and not (
                isinstance(node, ast.Assign) and all(isinstance(t, ast.Subscript) and _base(t) == table
                                                     and isinstance(t.slice, ast.Constant) for t in node.targets)):
            # any other module-level touch of the table: a loop, if-block or with-block rebind, ``|=``,
            # ``pop``/``setdefault``/``__setitem__``, ``del`` (round-3 review of #179, finding 2)
            unresolved += 1
        if found is not None:
            bound = found
    if bound is None:
        return None
    return {**bound, "unresolved_updates": unresolved}


def closure(path: str, name: str, read: Reader = working_tree, stop: frozenset = frozenset()) -> dict | None:
    """Members (``path::name`` -> sha256) of the static dependency closure of ``name`` in ``path``, and their joint
    digest; None when the entry definition does not exist in that tree. A member named in ``stop`` is hashed but
    not followed: a boundary whose callees carry their own bindings (round-2 review of #179, N5)."""
    parsed: dict[str, tuple] = {}

    def module(p):
        if p not in parsed:
            text = read(p)
            if text is None:
                parsed[p] = None
            else:
                tree = ast.parse(text)
                names, modules = _imports(tree, p, read)
                stars = modules.pop("*", [])
                star_defs = {}
                for star in stars:                       # from x import *: x's own definitions, name by name
                    star_text = read(star)
                    if star_text is not None:
                        for n in _definitions(ast.parse(star_text)):
                            star_defs.setdefault(n, (star, n))
                parsed[p] = (text, tree, _definitions(tree), names, modules, star_defs)
        return parsed[p]

    entry = module(path)
    if entry is None or name not in entry[2]:
        return None
    members, todo, unresolved = {}, [(path, name)], []
    while todo:
        p, n = todo.pop()
        key = f"{p}::{n}"
        if key in members:
            continue
        m = module(p)
        if m is None or n not in m[2]:
            continue
        text, _tree, defs, names, modules, star_defs = m
        nodes = defs[n]
        members[key] = "sha256:" + hashlib.sha256("\n".join(_segment(text, x) for x in nodes).encode()).hexdigest()
        if key in stop:
            continue
        for node in nodes:
            todo += _references(node, n, p, defs, names, modules, read, star_defs, unresolved)
    joint = "\n".join(f"{k}={v}" for k, v in sorted(members.items()))
    return {"entry": f"{path}::{name}", "members": dict(sorted(members.items())),
            "sha256": "sha256:" + hashlib.sha256(joint.encode()).hexdigest(),
            # code the static closure cannot follow: a positive verdict must not bind it (N4)
            "unresolved": sorted(set(unresolved))}
