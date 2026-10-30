"""Every effectful call site in greg/ and foundry/systems/ is on a reviewed allowlist (MU-D, S37, S67).

An effectful call reaches outside the Python process: a child process (``subprocess.run|Popen|
call|check_call|check_output|getoutput|getstatusoutput``, ``os.system|popen|fork|forkpty|spawn*|
exec*|posix_spawn*``, ``asyncio.create_subprocess_exec|shell``) or the network
(``urllib.request.urlopen``, ``urllib.request.build_opener`` and the ``.open`` of the opener it
builds, ``http.client.HTTPConnection|HTTPSConnection``, ``socket.socket|create_connection``,
``requests.*``, ``httpx.*``). ``os.kill`` is not one: it signals a process the body already owns.

Imports are resolved, so ``import subprocess as sp``, ``from subprocess import run as r``, a module
re-exported by another module, ``importlib.import_module("subprocess")`` / ``__import__`` bound to a
name, and ``getattr(subprocess, "run")`` all count. A bare reference to an effect callable
(``runner=subprocess.run``) counts like a call: it is how an effect is injected and later called
under another name. Annotations never run, so they are not read.

Each site is keyed by (module path, enclosing qualname, callee) with an occurrence count, never by
line number: moving a call within its function does not churn the list; adding one, or moving one
into another function, does.

The allowlist is tests/security/effect-call-allowlist.json. ``allowed`` names what each site serves
(a capability id in greg.capabilities.BUILTINS, the confinement capabilities run behind, the supervised
worker path, a founder-signed route or command, a command a person runs, the installer) with a one-line
justification grounded in the code. ``known_unmediated`` lists sites the body reaches on its own with no
capability manifest, Gate, supervised worker or person-run command behind them; they are findings,
recorded so they cannot grow silently, not approvals. Being listed authorizes nothing: the list is a
review-time inventory, and the Gate, the capability manifests and the founder's authority are unchanged.
"""
from __future__ import annotations

import ast
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST = Path("tests/security/effect-call-allowlist.json")
SCANNED = ("greg", "foundry/systems")
MODULE = "<module>"

SUBPROCESS = frozenset({"run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput"})
OS_NAMES = frozenset({"system", "popen", "fork", "forkpty"})
OS_PREFIXES = ("spawn", "exec", "posix_spawn")
EXACT = frozenset({"asyncio.create_subprocess_exec", "asyncio.create_subprocess_shell", "urllib.request.urlopen",
                   "urllib.request.build_opener", "http.client.HTTPConnection", "http.client.HTTPSConnection",
                   "socket.socket", "socket.create_connection"})
ANY_MEMBER = frozenset({"requests", "httpx"})
OPENER = "urllib.request.build_opener"
OPENER_OPEN = OPENER + "().open"

ENTRY_FIELDS = {"allowed": {"module", "qualname", "callee", "count", "serves", "justification"},
                "known_unmediated": {"module", "qualname", "callee", "count", "serves", "reason"}}
# What a site may serve: ``kind:detail``. ``capability`` details must be ids in greg.capabilities.BUILTINS.
SERVES_KINDS = frozenset({"capability", "confinement", "egress", "supervised-worker", "model-route",
                          "mission-appraisal", "founder-command", "operator", "installer"})


# -- the scanner ---------------------------------------------------------------------------------------

def effect(dotted: str) -> str | None:
    """The effect callee ``dotted`` names, matched on its longest suffix (``x.subprocess.run`` counts)."""
    parts = dotted.split(".")
    for start in range(len(parts)):
        name = ".".join(parts[start:])
        head, _, attr = name.partition(".")
        if (name in EXACT
                or (head == "subprocess" and attr in SUBPROCESS)
                or (head == "os" and "." not in attr and (attr in OS_NAMES or attr.startswith(OS_PREFIXES)))
                or (head in ANY_MEMBER and attr)):
            return name
    return None


def module_name(path: str) -> tuple[str, bool]:
    """(dotted module name, is a package) for a repository-relative .py path."""
    parts = path[:-3].split("/")
    if parts[-1] == "__init__":
        return ".".join(parts[:-1]), True
    return ".".join(parts), False


class _Module:
    """One parsed module: its import bindings, opener factories and (after ``scan``) its effect sites."""

    def __init__(self, path: str, source: str):
        self.path = path
        self.name, self.package = module_name(path)
        self.tree = ast.parse(source, filename=path)
        self.nodes = list(ast.walk(self.tree))   # one walk; every later pass filters this list
        self.assigns = [node for node in self.nodes
                        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None]
        self.source = source
        self.returns: list[tuple[str, ast.AST]] | None = None   # (innermost function, returned expression), lazily
        self.names: dict[str, set[str]] = defaultdict(set)
        self.openers: set[str] = set()          # names (``x``) and attributes (``.x``) bound to a built opener
        self.local_factories: set[str] = set()  # functions here that return a built opener
        self.factories: set[str] = set()        # fully-qualified opener factories across the scanned tree
        self.kinds: dict = defaultdict(Counter)
        self._bind_imports()

    def _collect_returns(self, node, function: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._collect_returns(child, child.name)
            else:
                if isinstance(child, ast.Return) and child.value is not None and function is not None:
                    self.returns.append((function, child.value))
                self._collect_returns(child, function)

    # imports ------------------------------------------------------------------------------------------
    def _absolute(self, level: int, target: str | None) -> str:
        parts = self.name.split(".") if self.package else self.name.split(".")[:-1]
        parts = parts[:len(parts) - (level - 1)] if level > 1 else parts
        return ".".join(parts + ([target] if target else []))

    def _bind_imports(self) -> None:
        for node in self.nodes:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        self.names[alias.asname].add(alias.name)
                    else:
                        head = alias.name.split(".")[0]
                        self.names[head].add(head)
            elif isinstance(node, ast.ImportFrom):
                base = node.module if not node.level else self._absolute(node.level, node.module)
                for alias in node.names:
                    if alias.name != "*":
                        self.names[alias.asname or alias.name].add(f"{base}.{alias.name}")
        for node in self.assigns:                              # sp = importlib.import_module("subprocess")
            if isinstance(node.value, ast.Call):
                bound = self._dynamic_import(node.value)
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                    if bound and isinstance(target, ast.Name):
                        self.names[target.id].add(bound)

    def _dynamic_import(self, call: ast.Call) -> str | None:
        if not call.args or not isinstance(call.args[0], ast.Constant) or not isinstance(call.args[0].value, str):
            return None
        literal = call.args[0].value
        if isinstance(call.func, ast.Name) and call.func.id == "__import__":
            return literal.split(".")[0]                       # __import__("a.b") returns package a
        if "importlib.import_module" in self.resolve(call.func):
            return literal
        return None

    # resolution ---------------------------------------------------------------------------------------
    def resolve(self, node) -> set[str]:
        """Every dotted name ``node`` can denote through this module's imports (empty when unknown)."""
        if isinstance(node, ast.Name):
            return set(self.names.get(node.id, ()))
        if isinstance(node, ast.Attribute):
            return {f"{base}.{node.attr}" for base in self.resolve(node.value)}
        if isinstance(node, ast.Call):
            bound = self._dynamic_import(node)
            if bound:
                return {bound}
            if (isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2
                    and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)):
                return {f"{base}.{node.args[1].value}" for base in self.resolve(node.args[0])}
        return set()

    def _effect_of(self, node) -> str | None:
        found = sorted(filter(None, (effect(name) for name in self.resolve(node))))
        return found[0] if found else None

    # openers ------------------------------------------------------------------------------------------
    def builds_opener(self, node) -> bool:
        """``node`` evaluates to an opener made by ``urllib.request.build_opener``."""
        if isinstance(node, ast.Call):
            func = node.func
            terminal = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            return (any(effect(name) == OPENER or name in self.factories for name in self.resolve(func))
                    or terminal in self.local_factories)
        if isinstance(node, ast.Name):
            return node.id in self.openers
        if isinstance(node, ast.Attribute):
            return "." + node.attr in self.openers
        return False

    def find_factories(self) -> None:
        """Bind names and attributes assigned an opener; collect functions that return one."""
        for _ in range(2):                                     # a factory may return a name bound earlier
            for node in self.assigns:
                if self.builds_opener(node.value):
                    for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                        if isinstance(target, ast.Name):
                            self.openers.add(target.id)
                        elif isinstance(target, ast.Attribute):
                            self.openers.add("." + target.attr)
            # Only a module that names build_opener or another module's factory can define a factory.
            if self.returns is None and ("build_opener" in self.source
                                         or any(f.rsplit(".", 1)[-1] in self.source for f in self.factories)):
                self.returns = []
                self._collect_returns(self.tree, None)
            self.local_factories.update(function for function, value in self.returns or ()
                                        if self.builds_opener(value))

    def exported_factories(self) -> set[str]:
        return {f"{self.name}.{node.name}" for node in self.tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in self.local_factories}

    # the walk -----------------------------------------------------------------------------------------
    def _record(self, qual: str, callee: str, kind: str) -> None:
        self.kinds[(qual, callee)][kind] += 1

    def scan(self) -> _Module:
        self._visit(self.tree, MODULE)
        return self

    def _visit(self, node, qual: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            inner = node.name if qual == MODULE else f"{qual}.{node.name}"
            for child in ast.iter_child_nodes(node):
                if child is not getattr(node, "returns", None):   # decorators and defaults belong to the def
                    self._visit(child, inner)
            return
        if isinstance(node, ast.arg):                              # a parameter: name and annotation only
            return
        if isinstance(node, ast.AnnAssign):                        # the annotation never runs
            self._visit(node.target, qual)
            if node.value is not None:
                self._visit(node.value, qual)
            return
        if isinstance(node, ast.Lambda):
            qual = "<lambda>" if qual == MODULE else f"{qual}.<lambda>"
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "open" and self.builds_opener(func.value):
                self._record(qual, OPENER_OPEN, "call")
                self._visit(func.value, qual)
            elif (callee := self._effect_of(func)) is not None:
                self._record(qual, callee, "call")
            elif (callee := self._effect_of(node)) is not None:   # getattr(subprocess, "run") as a value
                self._record(qual, callee, "reference")
                return
            else:
                self._visit(func, qual)
            for child in (*node.args, *node.keywords):
                self._visit(child, qual)
            return
        if isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Load):
            callee = self._effect_of(node)
            if callee is not None:
                self._record(qual, callee, "reference")
                return
        for child in ast.iter_child_nodes(node):
            self._visit(child, qual)


def scan_sources(sources: dict[str, str]) -> dict[tuple[str, str, str], Counter]:
    """{(module path, qualname, callee): Counter(call=n, reference=m)} for repository-relative sources."""
    modules = [_Module(path, source) for path, source in sorted(sources.items())]
    for module in modules:
        module.find_factories()
    exported = set().union(*(module.exported_factories() for module in modules)) if modules else set()
    found = {}
    for module in modules:
        module.factories = exported
        module.find_factories()                                # cross-module factories bind openers too
        module.scan()
        for (qual, callee), kinds in module.kinds.items():
            found[(module.path, qual, callee)] = kinds
    return found


def scan_tree(root: Path = ROOT) -> dict[tuple[str, str, str], Counter]:
    sources = {}
    for top in SCANNED:
        for path in sorted((root / top).rglob("*.py")):
            if "__pycache__" not in path.parts:
                sources[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return scan_sources(sources)


# -- the allowlist ---------------------------------------------------------------------------------------

def load_allowlist(path: Path = ROOT / ALLOWLIST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def entry_key(entry: dict) -> tuple[str, str, str]:
    return entry["module"], entry["qualname"], entry["callee"]


def _describe(kinds: Counter) -> str:
    return ", ".join(f"{n} {kind}{'s' if n != 1 else ''}" for kind, n in sorted(kinds.items()))


def _suggested(key, count) -> str:
    module, qualname, callee = key
    return json.dumps({"module": module, "qualname": qualname, "callee": callee, "count": count,
                       "serves": ["<kind>:<detail>"], "justification": "<one line grounded in the code>"})


def compare(found: dict, document: dict) -> list[str]:
    """Every difference between the scanned sites and the allowlist, each worded as the fix a contributor makes."""
    listed = {entry_key(entry): (section, entry) for section in ENTRY_FIELDS for entry in document.get(section, [])}
    problems = []
    for key in sorted(set(found) - set(listed)):
        count = sum(found[key].values())
        problems.append(
            f"UNLISTED effect call site {' :: '.join(key)} ({_describe(found[key])}). Add to {ALLOWLIST} under "
            f"\"allowed\": {_suggested(key, count)} where serves names the governed path behind it (one of "
            f"{', '.join(kind + ':' for kind in sorted(SERVES_KINDS))}; capability: takes an id in BUILTINS, operator: "
            f"a command a person runs) and the justification says how that path bounds this call. If no capability "
            f"manifest, Gate, supervised worker or person-run command stands behind it, list it under "
            f"\"known_unmediated\" with a \"reason\" instead; do not invent a justification.")
    for key in sorted(set(listed) - set(found)):
        section, entry = listed[key]
        problems.append(
            f"STALE {section} entry {' :: '.join(key)} (count {entry['count']}): no such call site exists in "
            f"{', '.join(SCANNED)} any more. Remove it from {ALLOWLIST}, or, if the call moved, re-key it to the new "
            f"module and qualname and re-check that its justification still holds there.")
    for key in sorted(set(found) & set(listed)):
        section, entry = listed[key]
        count = sum(found[key].values())
        if entry["count"] != count:
            problems.append(
                f"COUNT MISMATCH {' :: '.join(key)}: {ALLOWLIST} lists {entry['count']} under {section}, the source "
                f"has "
                f"{count} ({_describe(found[key])}). Set \"count\": {count} and confirm the {section} entry's "
                f"{'justification' if section == 'allowed' else 'reason'} covers every occurrence.")
    return problems


def malformed(document: dict, builtins) -> list[str]:
    """Structural problems: missing or extra fields, unknown serves kinds, unknown capability ids, duplicate keys."""
    problems, seen = [], {}
    unknown = set(document) - {"version", "purpose", "rule", "seeded_from", *ENTRY_FIELDS}
    if unknown:
        problems.append(f"unknown top-level fields: {sorted(unknown)}")
    for section, fields in ENTRY_FIELDS.items():
        if not isinstance(document.get(section), list):
            problems.append(f"{section} must be a list")
            continue
        for entry in document[section]:
            if not isinstance(entry, dict) or set(entry) != fields:
                problems.append(f"{section} entry {entry!r} must have exactly the fields {sorted(fields)}")
                continue
            key = entry_key(entry)
            where = f"{section} {' :: '.join(key)}"
            if key in seen:
                problems.append(f"{where} is also listed under {seen[key]}")
            seen[key] = section
            if not entry["module"].endswith(".py") or not entry["module"].startswith(
                    tuple(f"{top}/" for top in SCANNED)):
                problems.append(f"{where}: module must be a .py path under {SCANNED}")
            if type(entry["count"]) is not int or entry["count"] < 1:
                problems.append(f"{where}: count must be a positive integer")
            text = entry["justification" if section == "allowed" else "reason"]
            if not isinstance(text, str) or len(text.split()) < 6:
                problems.append(f"{where}: the {'justification' if section == 'allowed' else 'reason'} must say, in "
                                f"words grounded in the code, how the call is bounded")
            if not isinstance(entry["serves"], list) or not entry["serves"]:
                problems.append(f"{where}: serves must name at least one path")
                continue
            for served in entry["serves"]:
                kind, _, detail = str(served).partition(":")
                if kind not in SERVES_KINDS or not detail.strip():
                    problems.append(f"{where}: serves {served!r} is not <kind>:<detail> with kind in "
                                    f"{sorted(SERVES_KINDS)}")
                elif kind == "capability" and detail not in builtins:
                    problems.append(f"{where}: serves {served!r} names no capability in greg.capabilities.BUILTINS")
    return problems


# -- the scanner, against known inputs ---------------------------------------------------------------------

def _sites(sources: dict[str, str]) -> dict:
    return {key: sum(kinds.values()) for key, kinds in scan_sources(sources).items()}


def test_every_import_form_and_call_shape_is_resolved():
    source = '''
import subprocess, socket, asyncio, os, importlib
import subprocess as sp
import urllib.request
import http.client
import requests
import httpx as hx
from subprocess import run as r, Popen
from os import execv
from urllib import request as rq
from urllib.request import urlopen as fetch, build_opener
from http.client import HTTPSConnection
from greg import capabilities
dyn = importlib.import_module("subprocess")
raw = __import__("socket")

def calls():
    subprocess.run(["true"]); sp.check_output(["true"]); r(["true"]); Popen(["true"])
    subprocess.getoutput("true"); os.system("true"); os.popen("true"); os.spawnlp(0, "true", "true")
    execv("/bin/true", ["true"]); os.posix_spawnp("true", ["true"], {}); os.fork(); os.forkpty()
    asyncio.create_subprocess_exec("true"); asyncio.create_subprocess_shell("true")
    urllib.request.urlopen("https://x"); rq.urlopen("https://x"); fetch("https://x")
    http.client.HTTPConnection("x"); HTTPSConnection("x")
    socket.socket(); socket.create_connection(("x", 1)); raw.socket()
    requests.get("https://x"); requests.Session(); hx.Client()
    getattr(subprocess, "run")(["true"]); dyn.run(["true"]); importlib.import_module("os").system("true")
    capabilities.subprocess.run(["true"])

def openers(request):
    build_opener().open(request)
    held = urllib.request.build_opener()
    held.open(request)

def injected(runner=subprocess.run):
    return runner

class Outer:
    def method(self):
        def inner():
            return sp.Popen(["true"])
        return lambda: socket.create_connection(("x", 1))
'''
    found = _sites({"greg/probe.py": source})
    expected = {
        ("calls", "subprocess.run"): 5, ("calls", "subprocess.check_output"): 1, ("calls", "subprocess.Popen"): 1,
        ("calls", "subprocess.getoutput"): 1, ("calls", "os.system"): 2, ("calls", "os.popen"): 1,
        ("calls", "os.spawnlp"): 1, ("calls", "os.execv"): 1, ("calls", "os.posix_spawnp"): 1, ("calls", "os.fork"): 1,
        ("calls", "os.forkpty"): 1, ("calls", "asyncio.create_subprocess_exec"): 1,
        ("calls", "asyncio.create_subprocess_shell"): 1, ("calls", "urllib.request.urlopen"): 3,
        ("calls", "http.client.HTTPConnection"): 1, ("calls", "http.client.HTTPSConnection"): 1,
        ("calls", "socket.socket"): 2, ("calls", "socket.create_connection"): 1, ("calls", "requests.get"): 1,
        ("calls", "requests.Session"): 1, ("calls", "httpx.Client"): 1,
        ("openers", OPENER): 2, ("openers", OPENER_OPEN): 2,
        ("injected", "subprocess.run"): 1,
        ("Outer.method.inner", "subprocess.Popen"): 1, ("Outer.method.<lambda>", "socket.create_connection"): 1,
    }
    assert found == {("greg/probe.py", qual, callee): n for (qual, callee), n in expected.items()}


def test_what_is_not_an_effect_is_not_listed():
    source = '''from __future__ import annotations
import os, socket, subprocess, urllib.parse

def quiet(sock: socket.socket, done: subprocess.CompletedProcess = None) -> socket.socket:
    os.kill(1, 0); os.killpg(1, 0); os.path.join("a", "b"); os.environ.get("X")
    urllib.parse.urlsplit("https://x"); socket.socketpair(); socket.gethostname()
    sock: socket.socket = sock
    try:
        pass
    except subprocess.TimeoutExpired:
        pass
    text = "subprocess.run(['true'])"
    requests = []
    requests.append(1)
    def run(argv):
        return argv
    run(["true"])
    subprocess.run = None
    return subprocess.PIPE, subprocess.DEVNULL
'''
    assert _sites({"greg/quiet.py": source}) == {}


def test_an_opener_factory_in_another_module_is_followed():
    factory = "import urllib.request\n\ndef opener():\n    return urllib.request.build_opener()\n"
    caller = "from greg import egress_like\n\ndef send(request):\n    return egress_like.opener().open(request)\n"
    found = _sites({"greg/egress_like.py": factory, "greg/caller.py": caller})
    assert found == {("greg/egress_like.py", "opener", OPENER): 1, ("greg/caller.py", "send", OPENER_OPEN): 1}


def test_compare_names_each_fix():
    found = {("greg/a.py", "f", "subprocess.run"): Counter(call=2),
             ("greg/b.py", "g", "socket.socket"): Counter(call=1, reference=1)}
    document = {"allowed": [{"module": "greg/a.py", "qualname": "f", "callee": "subprocess.run", "count": 1,
                             "serves": ["operator:x"], "justification": "j"},
                            {"module": "greg/c.py", "qualname": "h", "callee": "os.system", "count": 1,
                             "serves": ["operator:x"], "justification": "j"}],
                "known_unmediated": []}
    problems = compare(found, document)
    assert len(problems) == 3
    unlisted, stale, mismatch = problems
    assert unlisted.startswith("UNLISTED effect call site greg/b.py :: g :: socket.socket (1 call, 1 reference)")
    assert '"count": 2' in unlisted and "known_unmediated" in unlisted and "do not invent" in unlisted
    assert stale.startswith("STALE allowed entry greg/c.py :: h :: os.system")
    assert mismatch.startswith("COUNT MISMATCH greg/a.py :: f :: subprocess.run") and '"count": 2' in mismatch
    assert compare({("greg/a.py", "f", "subprocess.run"): Counter(call=1)},
                   {"allowed": [], "known_unmediated": [document["allowed"][0]]}) == []


# -- the tree against its allowlist --------------------------------------------------------------------------

def test_allowlist_is_well_formed():
    from greg.capabilities import BUILTINS
    assert malformed(load_allowlist(), BUILTINS) == []


def test_every_effect_call_site_is_listed():
    problems = compare(scan_tree(), load_allowlist())
    assert not problems, "\n\n".join(problems)
