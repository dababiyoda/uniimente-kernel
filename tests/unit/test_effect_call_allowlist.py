"""Every effectful call site in greg/ and foundry/systems/ is on a reviewed allowlist (MU-D, S37, S67).

An effectful call reaches outside the Python process:
- a child process: ``subprocess.run|Popen|call|check_call|check_output|getoutput|getstatusoutput``,
  ``os.system|popen|fork|forkpty|startfile|spawn*|exec*|posix_spawn*`` (``posix.*`` is the same function),
  ``asyncio.create_subprocess_exec|shell`` (also under ``asyncio.subprocess``), ``pty.spawn|fork``,
  ``multiprocessing.Process|Pool``, ``concurrent.futures.ProcessPoolExecutor``, ``webbrowser.open*|get``;
- an outbound connection: ``urllib.request.urlopen|urlretrieve``, ``urllib.request.build_opener|OpenerDirector``
  and the ``.open`` of the opener they build, ``http.client.HTTPConnection|HTTPSConnection``,
  ``socket.socket|create_connection``, ``asyncio.open_connection|open_unix_connection``, the stdlib mail, FTP and
  XML-RPC clients, and the I/O entry points of ``requests``, ``httpx``, ``httpx2``, ``urllib3`` and ``aiohttp``
  (their request functions, sessions, clients, pools and transports, not their exceptions or constants);
- an inbound listener: ``socket.create_server``, ``asyncio.start_server|start_unix_server``,
  ``http.server.HTTPServer|ThreadingHTTPServer`` and the ``socketserver`` servers;
- an event loop's ``subprocess_exec|subprocess_shell|create_connection|create_server|...`` on a receiver the scan
  cannot name (a loop is an object, not an import).
``os.kill`` is not one: it signals a process the body already owns.

Names are resolved, so ``import subprocess as sp``, ``from subprocess import run as r``, ``sp = subprocess``,
``RUN = subprocess.run``, a name another scanned module imported or bound (followed module to module),
``importlib.import_module("subprocess")``, ``__import__`` (with or without ``fromlist``), ``sys.modules["subprocess"]``
and ``getattr(subprocess, "run")`` all count. A bare reference to an effect callable (``runner=subprocess.run``,
``send = opener.open``) counts like a call: it is how an effect is injected and later called under another name.
A star import fails the check: the names it binds cannot be resolved. Annotations are read where Python evaluates
them (parameter, return and module- or class-level annotations in a module without
``from __future__ import annotations``); there, and in an ``except`` clause or isinstance's class argument, naming
an effect class starts nothing, so only a call there counts.

``wrappers`` in the allowlist names in-tree functions that pass an effect on with no check of their own
(``greg.egress.send`` sends without the allowlist ``open_checked`` applies; ``run_isolated`` with
``isolate_network`` other than ``True`` runs without the network filter). Each call or reference to a wrapper is a
site of its own, so a new caller is reviewed like a new ``urlopen``. A wrapper may declare ``exempt_when``
keyword literals (a keyword-only parameter whose default is that literal): a call that keeps them is not a site.

Each site is keyed by (module path, enclosing qualname, callee) with an occurrence count, never by line number:
moving a call within its function does not churn the list; adding one, or moving one into another function, does.

The allowlist is tests/security/effect-call-allowlist.json. ``allowed`` names what each site serves (a capability id
in greg.capabilities.BUILTINS, the confinement capabilities run behind, the supervised worker path, a founder-signed
route or command, a command a person runs, the installer) with a one-line justification grounded in the code.
``known_unmediated`` lists sites the body reaches on its own schedule (``body-loop:``) with no capability manifest,
Gate, supervised worker or person-run command behind them; they are findings, recorded so they cannot grow
silently, not approvals. Being listed authorizes nothing: the list is a review-time inventory, and the Gate, the
capability manifests and the founder's authority are unchanged.
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
OS_NAMES = frozenset({"system", "popen", "fork", "forkpty", "startfile"})
OS_PREFIXES = ("spawn", "exec", "posix_spawn")
# A callable that also lives under another module is keyed by its documented home (posix.system is os.system).
SAME_AS = {"posix": "os", "nt": "os", "asyncio.subprocess": "asyncio", "asyncio.streams": "asyncio",
           "_socket": "socket", "concurrent.futures.process": "concurrent.futures",
           "multiprocessing.context": "multiprocessing"}
SOCKETSERVERS = ("TCPServer", "UDPServer", "UnixStreamServer", "UnixDatagramServer", "ThreadingTCPServer",
                 "ThreadingUDPServer", "ForkingTCPServer", "ForkingUDPServer", "ThreadingUnixStreamServer",
                 "ThreadingUnixDatagramServer", "ForkingUnixStreamServer", "ForkingUnixDatagramServer")
EXACT = frozenset({
    # child processes
    "asyncio.create_subprocess_exec", "asyncio.create_subprocess_shell", "pty.spawn", "pty.fork",
    "multiprocessing.Process", "multiprocessing.Pool", "concurrent.futures.ProcessPoolExecutor",
    "_posixsubprocess.fork_exec", "webbrowser.open", "webbrowser.open_new", "webbrowser.open_new_tab", "webbrowser.get",
    # outbound connections
    "urllib.request.urlopen", "urllib.request.urlretrieve", "urllib.request.build_opener",
    "urllib.request.OpenerDirector", "http.client.HTTPConnection", "http.client.HTTPSConnection", "socket.socket",
    "socket.create_connection", "asyncio.open_connection", "asyncio.open_unix_connection", "smtplib.SMTP",
    "smtplib.SMTP_SSL", "smtplib.LMTP", "ftplib.FTP", "ftplib.FTP_TLS", "poplib.POP3", "poplib.POP3_SSL",
    "imaplib.IMAP4", "imaplib.IMAP4_SSL", "xmlrpc.client.ServerProxy",
    # inbound listeners
    "socket.create_server", "asyncio.start_server", "asyncio.start_unix_server", "http.server.HTTPServer",
    "http.server.ThreadingHTTPServer", *(f"socketserver.{server}" for server in SOCKETSERVERS),
})
HTTP_LIBRARIES = frozenset({"requests", "httpx", "httpx2", "urllib3", "aiohttp"})
HTTP_ENTRY_POINTS = frozenset({"request", "get", "options", "head", "post", "put", "patch", "delete", "stream",
                               "Session", "session", "Client", "AsyncClient", "HTTPTransport", "AsyncHTTPTransport",
                               "HTTPAdapter", "PoolManager", "ProxyManager", "HTTPConnectionPool",
                               "HTTPSConnectionPool", "connection_from_url", "proxy_from_url", "ClientSession",
                               "TCPConnector", "UnixConnector"})
LOOP = "asyncio.AbstractEventLoop"
LOOP_METHODS = frozenset({"subprocess_exec", "subprocess_shell", "create_connection", "create_unix_connection",
                          "create_datagram_endpoint", "create_server", "create_unix_server", "sock_connect"})
OPENER_BUILDERS = frozenset({"urllib.request.build_opener", "urllib.request.OpenerDirector"})
OPENER = "urllib.request.build_opener"
OPENER_OPEN = OPENER + "().open"
EXEMPT = "-"            # _effect_of: a wrapper call its exempt_when keywords cover, neither a call nor a reference

ENTRY_FIELDS = {"allowed": {"module", "qualname", "callee", "count", "serves", "justification"},
                "known_unmediated": {"module", "qualname", "callee", "count", "serves", "reason"}}
WRAPPER_FIELDS = {"module", "qualname", "exempt_when", "why"}
TOP_LEVEL = {"version", "purpose", "rule", "seeded_from", "wrappers", *ENTRY_FIELDS}
# What a site may serve: ``kind:detail``. ``capability`` details must be ids in greg.capabilities.BUILTINS.
# ``body-loop`` (the body reaches the site on its own schedule) is a known_unmediated finding, never an approval.
SERVES_KINDS = frozenset({"capability", "confinement", "egress", "supervised-worker", "model-route",
                          "founder-command", "operator", "installer", "body-loop"})
UNMEDIATED_ONLY = "body-loop"


# -- the scanner ---------------------------------------------------------------------------------------

def _same_as(name: str) -> str:
    for alias, home in SAME_AS.items():
        if name == alias or name.startswith(alias + "."):
            return home + name[len(alias):]
    return name


def effect(dotted: str) -> str | None:
    """The effect callee ``dotted`` names, matched on its longest suffix (``x.subprocess.run`` counts)."""
    parts = dotted.split(".")
    for start in range(len(parts)):
        name = _same_as(".".join(parts[start:]))
        head, _, attr = name.partition(".")
        *middle, last = name.split(".")[1:] or [""]
        if (name in EXACT
                or (head == "subprocess" and attr in SUBPROCESS)
                or (head == "os" and "." not in attr and (attr in OS_NAMES or attr.startswith(OS_PREFIXES)))
                or (head in HTTP_LIBRARIES and last in HTTP_ENTRY_POINTS and all(part.islower() for part in middle))):
            return name
    return None


def module_name(path: str) -> tuple[str, bool]:
    """(dotted module name, is a package) for a repository-relative .py path."""
    parts = path[:-3].split("/")
    if parts[-1] == "__init__":
        return ".".join(parts[:-1]), True
    return ".".join(parts), False


def _literal(node):
    return node.value if isinstance(node, ast.Constant) else None


def _exempt(call: ast.Call, exempt_when: dict) -> bool:
    """``call`` keeps every ``exempt_when`` keyword at its literal: passed as exactly that, or left to the default
    (wrapper_problems checks the default is that literal). ``**kwargs`` may carry anything, so it is not exempt."""
    if not exempt_when:
        return False
    passed = {keyword.arg: keyword.value for keyword in call.keywords}
    if None in passed:
        return False
    return all(name not in passed or (isinstance(passed[name], ast.Constant)
                                      and type(passed[name].value) is type(literal) and passed[name].value == literal)
               for name, literal in exempt_when.items())


class _Index:
    """Every scanned module by dotted name, the declared wrappers and the opener factories found so far."""

    def __init__(self, modules, wrappers: dict):
        self.modules = {module.name: module for module in modules}
        self.wrappers = dict(wrappers)
        self.factories: set[str] = set()       # fully-qualified functions that return a built opener
        self._expanded: dict[str, frozenset] = {}

    def expand(self, dotted: str, seen: frozenset = frozenset()) -> frozenset:
        """``dotted`` and every name it denotes through a scanned module's own bindings (``greg.a.run`` where
        greg/a.py did ``from subprocess import run`` also denotes ``subprocess.run``), followed module to module."""
        if dotted in seen:
            return frozenset()
        if dotted in self._expanded:
            return self._expanded[dotted]
        out, parts = {dotted}, dotted.split(".")
        for cut in range(len(parts) - 1, 0, -1):                # the longest prefix that is a scanned module
            module = self.modules.get(".".join(parts[:cut]))
            if module is not None:
                for target in module.names.get(parts[cut], ()):
                    out |= self.expand(".".join([target, *parts[cut + 1:]]), seen | {dotted})
                break
        if not seen:
            self._expanded[dotted] = frozenset(out)
        return frozenset(out)

    def expand_all(self, names) -> set[str]:
        return set().union(*(self.expand(name) for name in names)) if names else set()


class _Module:
    """One parsed module: its name bindings, opener factories and (after ``scan``) its effect sites."""

    def __init__(self, path: str, source: str):
        self.path = path
        self.name, self.package = module_name(path)
        self.tree = ast.parse(source, filename=path)
        self.nodes = list(ast.walk(self.tree))   # one walk; every later pass filters this list
        self.source = source
        # Without ``from __future__ import annotations`` Python 3.11 evaluates annotations when the def runs.
        self.lazy_annotations = any(isinstance(node, ast.ImportFrom) and node.module == "__future__"
                                    and any(alias.name == "annotations" for alias in node.names)
                                    for node in self.tree.body)
        self.bindings = self._bindings()
        self.index: _Index | None = None
        self.returns: list[tuple[str, bool, ast.AST]] | None = None   # (function, is top-level, returned value)
        self.names: dict[str, set[str]] = defaultdict(set)
        self.openers: set[str] = set()          # names (``x``) and attributes (``.x``) bound to a built opener
        self.local_factories: set[str] = set()  # functions here (by name) that return a built opener
        self.kinds: dict = defaultdict(Counter)
        self._bind()

    def _bindings(self) -> list[tuple[ast.AST, ast.AST]]:
        """(target, value) for every assignment, ``a, b = x, y`` pairwise, walrus included."""
        pairs = []
        for node in self.nodes:
            if isinstance(node, ast.Assign):
                pairs += [(target, node.value) for target in node.targets]
            elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
                pairs.append((node.target, node.value))
        flat = []
        for target, value in pairs:
            if (isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List))
                    and len(target.elts) == len(value.elts)):
                flat += zip(target.elts, value.elts)
            elif isinstance(target, (ast.Name, ast.Attribute)):
                flat.append((target, value))
        return flat

    def _collect_returns(self, node, function: str | None, top: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._collect_returns(child, child.name, top=function is None and node is self.tree)
            elif isinstance(child, ast.ClassDef):
                self._collect_returns(child, function, top=False)
            else:
                if isinstance(child, ast.Return) and child.value is not None and function is not None:
                    self.returns.append((function, top, child.value))
                self._collect_returns(child, function, top)

    # names --------------------------------------------------------------------------------------------
    def _absolute(self, level: int, target: str | None) -> str:
        parts = self.name.split(".") if self.package else self.name.split(".")[:-1]
        parts = parts[:len(parts) - (level - 1)] if level > 1 else parts
        return ".".join(parts + ([target] if target else []))

    def _bind(self) -> None:
        """Local names -> the dotted names they may denote: imports, top-level definitions, and assignments of a
        value that resolves (``sp = subprocess``, ``RUN = subprocess.run``), repeated until a chain of them settles.
        The binding is flow-insensitive, so a reused local name may over-report; it never under-reports."""
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.names[node.name].add(f"{self.name}.{node.name}")
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
        targets = [(target.id, value) for target, value in self.bindings if isinstance(target, ast.Name)]
        for _ in range(len(targets) + 1):
            grew = False
            for name, value in targets:
                new = self.resolve(value) - self.names[name] if name in self.names else self.resolve(value)
                if new:
                    self.names[name] |= new
                    grew = True
            if not grew:
                break

    def _dynamic_import(self, call: ast.Call) -> str | None:
        literal = _literal(call.args[0]) if call.args else None
        if not isinstance(literal, str):
            return None
        callee = self.resolve(call.func) | ({call.func.id} if isinstance(call.func, ast.Name) else set())
        if callee & {"__import__", "importlib.__import__", "builtins.__import__"}:
            fromlist = next((k.value for k in call.keywords if k.arg == "fromlist"),
                            call.args[3] if len(call.args) > 3 else None)
            empty = fromlist is None or (isinstance(fromlist, (ast.List, ast.Tuple)) and not fromlist.elts) \
                or (isinstance(fromlist, ast.Constant) and not fromlist.value)
            return literal.split(".")[0] if empty else literal   # with a fromlist, __import__ returns the submodule
        if "importlib.import_module" in callee:
            return literal
        return None

    def resolve(self, node) -> set[str]:
        """Every dotted name ``node`` can denote through this module's own bindings (empty when unknown)."""
        if isinstance(node, ast.Name):
            return set(self.names.get(node.id, ()))
        if isinstance(node, ast.Attribute):
            return {f"{base}.{node.attr}" for base in self.resolve(node.value)}
        if isinstance(node, ast.Subscript):                     # sys.modules["subprocess"]
            literal = _literal(node.slice)
            if isinstance(literal, str) and "sys.modules" in self.resolve(node.value):
                return {literal}
            return set()
        if isinstance(node, ast.Call):
            bound = self._dynamic_import(node)
            if bound:
                return {bound}
            if (isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2
                    and isinstance(_literal(node.args[1]), str)):
                return {f"{base}.{node.args[1].value}" for base in self.resolve(node.args[0])}
        return set()

    def _effect_of(self, node, call: ast.Call | None = None) -> str | None:
        """The callee ``node`` denotes: an effect, or a declared wrapper (``EXEMPT`` when ``call`` keeps the
        wrapper's exempt_when keywords), else None."""
        found, exempt = set(), False
        for name in self.index.expand_all(self.resolve(node)):
            if name in self.index.wrappers:
                if call is not None and _exempt(call, self.index.wrappers[name]):
                    exempt = True
                else:
                    found.add(name)
            elif (callee := effect(name)) is not None:
                found.add(callee)
        return min(found) if found else EXEMPT if exempt else None

    # openers ------------------------------------------------------------------------------------------
    def builds_opener(self, node) -> bool:
        """``node`` evaluates to an opener made by ``urllib.request.build_opener`` or ``OpenerDirector``."""
        if isinstance(node, ast.Call):
            func = node.func
            terminal = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            return (any(effect(name) in OPENER_BUILDERS or name in self.index.factories
                        for name in self.index.expand_all(self.resolve(func)))
                    or terminal in self.local_factories)
        if isinstance(node, ast.Name):
            return node.id in self.openers
        if isinstance(node, ast.Attribute):
            return "." + node.attr in self.openers
        return False

    def _opened(self, node):
        """The opener whose ``open`` method ``node`` names (``X.open`` or ``getattr(X, "open")``), else None."""
        if isinstance(node, ast.Attribute) and node.attr == "open" and self.builds_opener(node.value):
            return node.value
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr"
                and len(node.args) >= 2 and _literal(node.args[1]) == "open" and self.builds_opener(node.args[0])):
            return node.args[0]
        return None

    def find_factories(self) -> bool:
        """Bind names and attributes assigned an opener; collect functions that return one. True when it grew."""
        before = (len(self.openers), len(self.local_factories), len(self.index.factories))
        for target, value in self.bindings:
            if self.builds_opener(value):
                self.openers.add(target.id if isinstance(target, ast.Name) else "." + target.attr)
        # Only a module that names an opener builder or another module's factory can define a factory.
        if self.returns is None and ("build_opener" in self.source or "OpenerDirector" in self.source
                                     or any(f.rsplit(".", 1)[-1] in self.source for f in self.index.factories)):
            self.returns = []
            self._collect_returns(self.tree, None, top=False)
        for function, top, value in self.returns or ():
            if self.builds_opener(value):
                self.local_factories.add(function)
                if top:
                    self.index.factories.add(f"{self.name}.{function}")
        return before != (len(self.openers), len(self.local_factories), len(self.index.factories))

    # the walk -----------------------------------------------------------------------------------------
    def _record(self, qual: str, callee: str, kind: str) -> None:
        self.kinds[(qual, callee)][kind] += 1

    def scan(self) -> _Module:
        for child in self.tree.body:
            self._visit(child, MODULE)
        return self

    def _visit(self, node, qual: str, typed: bool = False, local: bool = False) -> None:
        """Record effect sites under ``qual``. ``typed``: a type position (an evaluated annotation, an ``except``
        clause, isinstance's class argument), where naming an effect class starts nothing but a call still does.
        ``local``: inside a function body, where Python never evaluates a variable annotation."""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            name = "<lambda>" if isinstance(node, ast.Lambda) else node.name
            inner = name if qual == MODULE else f"{qual}.{name}"
            arguments = node.args                              # decorators and defaults belong to the def
            for child in (*getattr(node, "decorator_list", ()), *arguments.defaults,
                          *(default for default in arguments.kw_defaults if default is not None)):
                self._visit(child, inner, local=local)
            if not self.lazy_annotations and not isinstance(node, ast.Lambda):
                every = (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs, arguments.vararg,
                         arguments.kwarg)
                for annotation in (*(arg.annotation for arg in every if arg is not None), node.returns):
                    if annotation is not None:
                        self._visit(annotation, inner, typed=True)
            for child in (node.body if isinstance(node.body, list) else [node.body]):
                self._visit(child, inner, local=True)
            return
        if isinstance(node, ast.ClassDef):
            inner = node.name if qual == MODULE else f"{qual}.{node.name}"
            for child in (*node.decorator_list, *node.bases, *node.keywords, *node.body):
                self._visit(child, inner)                       # a class body runs at definition, annotations too
            return
        if isinstance(node, ast.AnnAssign):
            for child in (node.target, node.value):
                if child is not None:
                    self._visit(child, qual, local=local)
            if not self.lazy_annotations and not local:
                self._visit(node.annotation, qual, typed=True)
            return
        if isinstance(node, ast.ExceptHandler):
            if node.type is not None:
                self._visit(node.type, qual, typed=True, local=local)
            for child in node.body:
                self._visit(child, qual, local=local)
            return
        if isinstance(node, ast.MatchClass):
            self._visit(node.cls, qual, typed=True, local=local)
            for child in (*node.patterns, *node.kwd_patterns):
                self._visit(child, qual, local=local)
            return
        if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
            base = node.module if not node.level else self._absolute(node.level, node.module)
            self._record(qual, f"{base}.*", "star-import")
            return
        if isinstance(node, ast.Call):
            self._visit_call(node, qual, local)
            return
        if (isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Load)
                and self._visit_reference(node, qual, typed, local)):
            return
        for child in ast.iter_child_nodes(node):
            self._visit(child, qual, typed, local)

    def _visit_call(self, node: ast.Call, qual: str, local: bool) -> None:
        func, values = node.func, [*node.args, *(keyword.value for keyword in node.keywords)]
        if isinstance(func, ast.Name) and func.id in ("isinstance", "issubclass") and len(node.args) == 2:
            self._visit(node.args[0], qual, local=local)
            self._visit(node.args[1], qual, typed=True, local=local)
            return
        if (opener := self._opened(func)) is not None:          # X.open(...) / getattr(X, "open")(...)
            self._record(qual, OPENER_OPEN, "call")
            self._visit(opener, qual, local=local)
        elif (callee := self._effect_of(func, call=node)) == EXEMPT:
            pass                                                # a wrapper call its exempt_when keywords cover
        elif callee is not None:
            self._record(qual, callee, "call")
        elif (opener := self._opened(node)) is not None:        # getattr(X, "open") as a value
            self._record(qual, OPENER_OPEN, "reference")
            self._visit(opener, qual, local=local)
            return
        elif (callee := self._effect_of(node)) is not None:     # getattr(subprocess, "run") as a value
            self._record(qual, callee, "reference")
            return
        elif isinstance(func, ast.Attribute) and func.attr in LOOP_METHODS and not self.resolve(func.value):
            self._record(qual, f"{LOOP}.{func.attr}", "call")
            self._visit(func.value, qual, local=local)
        else:
            self._visit(func, qual, local=local)
        for value in values:
            self._visit(value, qual, local=local)

    def _visit_reference(self, node, qual: str, typed: bool, local: bool) -> bool:
        """Record ``node`` if it names an effect callable without calling it; True when its subtree is handled."""
        callee = self._effect_of(node)
        if callee is not None:
            if not typed:
                self._record(qual, callee, "reference")
            return True
        if isinstance(node, ast.Attribute):
            if (opener := self._opened(node)) is not None:      # send = opener().open
                if not typed:
                    self._record(qual, OPENER_OPEN, "reference")
                self._visit(opener, qual, local=local)
                return True
            if node.attr != "__call__" and self._effect_of(node.value) is not None:
                return True                                     # subprocess.run.__doc__ starts nothing
            if node.attr in LOOP_METHODS and not self.resolve(node.value):
                if not typed:
                    self._record(qual, f"{LOOP}.{node.attr}", "reference")
                self._visit(node.value, qual, local=local)
                return True
        return False


def scan_sources(sources: dict[str, str], wrappers: dict | None = None) -> dict[tuple[str, str, str], Counter]:
    """{(module path, qualname, callee): Counter(call=n, reference=m)} for repository-relative sources.
    ``wrappers``: {dotted function: exempt_when} whose callers are sites too (see ``wrapper_table``)."""
    modules = [_Module(path, source) for path, source in sorted(sources.items())]
    index = _Index(modules, wrappers or {})
    for module in modules:
        module.index = index
    for _ in range(len(modules) + 1):                          # an opener factory may return another module's
        grew = [module.find_factories() for module in modules]   # every module, no short-circuit
        if not any(grew):
            break
    found = {}
    for module in modules:
        module.scan()
        for (qual, callee), kinds in module.kinds.items():
            found[(module.path, qual, callee)] = kinds
    return found


def read_tree(root: Path = ROOT) -> dict[str, str]:
    sources = {}
    for top in SCANNED:
        for path in sorted((root / top).rglob("*.py")):
            if "__pycache__" not in path.parts:
                sources[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return sources


def scan_tree(root: Path = ROOT, wrappers: dict | None = None) -> dict[tuple[str, str, str], Counter]:
    return scan_sources(read_tree(root), wrappers)


# -- the allowlist ---------------------------------------------------------------------------------------

def load_allowlist(path: Path = ROOT / ALLOWLIST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def entry_key(entry: dict) -> tuple[str, str, str]:
    return entry["module"], entry["qualname"], entry["callee"]


def wrapper_table(document: dict) -> dict[str, dict]:
    """{dotted function: exempt_when} for the allowlist's declared wrappers."""
    return {f"{module_name(w['module'])[0]}.{w['qualname']}": dict(w["exempt_when"])
            for w in document.get("wrappers", [])}


def _describe(kinds: Counter) -> str:
    return ", ".join(f"{n} {kind}{'s' if n != 1 else ''}" for kind, n in sorted(kinds.items()))


def _suggested(key, count) -> str:
    module, qualname, callee = key
    return json.dumps({"module": module, "qualname": qualname, "callee": callee, "count": count,
                       "serves": ["<kind>:<detail>"], "justification": "<one line grounded in the code>"})


def compare(found: dict, document: dict) -> list[str]:
    """Every difference between the scanned sites and the allowlist, each worded as the fix a contributor makes."""
    listed = {entry_key(entry): (section, entry) for section in ENTRY_FIELDS for entry in document.get(section, [])}
    stars = {key for key in found if key[2].endswith(".*")}
    problems = [f"STAR IMPORT {' :: '.join(key)}: the scan cannot tell which names `from {key[2][:-2]} import *` "
                f"binds, so an effect call through one would go unlisted. Import the names explicitly; a star import "
                f"cannot be allowlisted." for key in sorted(stars)]
    for key in sorted(set(found) - set(listed) - stars):
        count = sum(found[key].values())
        problems.append(
            f"UNLISTED effect call site {' :: '.join(key)} ({_describe(found[key])}). Add to {ALLOWLIST} under "
            f"\"allowed\": {_suggested(key, count)} where serves names the governed path behind it (one of "
            f"{', '.join(kind + ':' for kind in sorted(SERVES_KINDS - {UNMEDIATED_ONLY}))}; capability: takes an id "
            f"in BUILTINS, operator: a command a person runs) and the justification says how that path bounds this "
            f"call. If no capability manifest, Gate, supervised worker or person-run command stands behind it, list "
            f"it under \"known_unmediated\" with a \"reason\" and a body-loop: serves naming the schedule that reaches "
            f"it instead; do not invent a justification. If {key[1]} passes the effect on to its callers with no "
            f"check of its own, also declare it under \"wrappers\" so each caller is listed.")
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
                f"has {count} ({_describe(found[key])}). Set \"count\": {count} and confirm the {section} entry's "
                f"{'justification' if section == 'allowed' else 'reason'} covers every occurrence.")
    return problems


def wrapper_problems(document: dict, found: dict, sources: dict[str, str]) -> list[str]:
    """A declared wrapper must be a top-level function that still holds an effect site, and each exempt_when keyword
    must be keyword-only with that literal as its default, so a call that omits it really is exempt."""
    problems = []
    for wrapper in document.get("wrappers", []):
        where = f"wrapper {wrapper['module']} :: {wrapper['qualname']}"
        source = sources.get(wrapper["module"])
        definition = next((node for node in ast.parse(source).body
                           if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                           and node.name == wrapper["qualname"]), None) if source is not None else None
        if definition is None:
            problems.append(f"STALE {where}: no such top-level function. Remove it from \"wrappers\" in {ALLOWLIST} "
                            f"(its callers' entries then go stale too) or point it at the function that moved.")
            continue
        if not any(key[:2] == (wrapper["module"], wrapper["qualname"]) for key in found):
            problems.append(f"STALE {where}: its body holds no effect site any more. Remove it from \"wrappers\" "
                            f"in {ALLOWLIST} together with its callers' entries.")
        defaults = dict(zip((arg.arg for arg in definition.args.kwonlyargs), definition.args.kw_defaults))
        for keyword, literal in wrapper["exempt_when"].items():
            default = defaults.get(keyword)
            if not (isinstance(default, ast.Constant) and type(default.value) is type(literal)
                    and default.value == literal):
                problems.append(f"{where}: exempt_when {keyword}={literal!r} needs a keyword-only parameter "
                                f"{keyword} whose default is {literal!r}; otherwise a call that omits it is not exempt.")
    return problems


def _words(text, at_least: int = 6) -> bool:
    return isinstance(text, str) and len(text.split()) >= at_least


def malformed(document: dict, builtins) -> list[str]:
    """Structural problems: missing or extra fields, unknown serves kinds, unknown capability ids, duplicate keys."""
    problems, seen = [], {}
    unknown = set(document) - TOP_LEVEL
    if unknown:
        problems.append(f"unknown top-level fields: {sorted(unknown)}")
    module_ok = tuple(f"{top}/" for top in SCANNED)
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
            if not entry["module"].endswith(".py") or not entry["module"].startswith(module_ok):
                problems.append(f"{where}: module must be a .py path under {SCANNED}")
            if entry["callee"].endswith(".*"):
                problems.append(f"{where}: a star import cannot be allowlisted")
            if type(entry["count"]) is not int or entry["count"] < 1:
                problems.append(f"{where}: count must be a positive integer")
            text = entry["justification" if section == "allowed" else "reason"]
            if not _words(text):
                problems.append(f"{where}: the {'justification' if section == 'allowed' else 'reason'} must say, in "
                                f"words grounded in the code, how the call is bounded")
            if not isinstance(entry["serves"], list) or not entry["serves"]:
                problems.append(f"{where}: serves must name at least one path")
                continue
            kinds = set()
            for served in entry["serves"]:
                kind, _, detail = str(served).partition(":")
                kinds.add(kind)
                if kind not in SERVES_KINDS or not detail.strip():
                    problems.append(f"{where}: serves {served!r} is not <kind>:<detail> with kind in "
                                    f"{sorted(SERVES_KINDS)}")
                elif kind == "capability" and detail not in builtins:
                    problems.append(f"{where}: serves {served!r} names no capability in greg.capabilities.BUILTINS")
            if section == "allowed" and UNMEDIATED_ONLY in kinds:
                problems.append(f"{where}: {UNMEDIATED_ONLY}: is the body's own schedule, a finding; an entry that "
                                f"serves it belongs under known_unmediated")
            if section == "known_unmediated" and UNMEDIATED_ONLY not in kinds:
                problems.append(f"{where}: a known_unmediated entry names the body's schedule that reaches it as "
                                f"{UNMEDIATED_ONLY}:<detail>")
    wrappers = document.get("wrappers", [])
    if not isinstance(wrappers, list):
        return problems + ["wrappers must be a list"]
    named = set()
    for wrapper in wrappers:
        if not isinstance(wrapper, dict) or set(wrapper) != WRAPPER_FIELDS:
            problems.append(f"wrappers entry {wrapper!r} must have exactly the fields {sorted(WRAPPER_FIELDS)}")
            continue
        where = f"wrapper {wrapper['module']} :: {wrapper['qualname']}"
        if (wrapper["module"], wrapper["qualname"]) in named:
            problems.append(f"{where} is declared twice")
        named.add((wrapper["module"], wrapper["qualname"]))
        if not str(wrapper["module"]).endswith(".py") or not str(wrapper["module"]).startswith(module_ok):
            problems.append(f"{where}: module must be a .py path under {SCANNED}")
        if not str(wrapper["qualname"]).isidentifier():
            problems.append(f"{where}: a wrapper is a top-level function, named without dots")
        if not isinstance(wrapper["exempt_when"], dict) or not all(
                isinstance(k, str) and isinstance(v, (bool, int, str, type(None)))
                for k, v in wrapper["exempt_when"].items()):
            problems.append(f"{where}: exempt_when maps keyword names to literals")
        if not _words(wrapper["why"]):
            problems.append(f"{where}: why must say, in words grounded in the code, which check the wrapper skips")
    return problems


# -- the scanner, against known inputs ---------------------------------------------------------------------

def _sites(sources: dict[str, str], wrappers: dict | None = None) -> dict:
    return {key: sum(kinds.values()) for key, kinds in scan_sources(sources, wrappers).items()}


def test_every_import_form_and_call_shape_is_resolved():
    source = '''
import subprocess, socket, asyncio, os, importlib, sys
import subprocess as sp
import urllib.request
import http.client
import requests
import httpx as hx
import httpx2, urllib3, aiohttp, posix, pty, multiprocessing, webbrowser, smtplib, _socket, socketserver
import http.server
import concurrent.futures
from subprocess import run as r, Popen
from os import execv
from urllib import request as rq
from urllib.request import urlopen as fetch, build_opener
from http.client import HTTPSConnection
from asyncio.subprocess import create_subprocess_exec as spawn_async
from greg import capabilities
dyn = importlib.import_module("subprocess")
raw = __import__("socket")
sub = __import__("urllib.request", fromlist=["urlopen"])
again = subprocess
RUN = subprocess.run

def calls():
    subprocess.run(["true"]); sp.check_output(["true"]); r(["true"]); Popen(["true"])
    subprocess.getoutput("true"); os.system("true"); os.popen("true"); os.spawnlp(0, "true", "true")
    execv("/bin/true", ["true"]); os.posix_spawnp("true", ["true"], {}); os.fork(); os.forkpty()
    asyncio.create_subprocess_exec("true"); asyncio.create_subprocess_shell("true"); spawn_async("true")
    urllib.request.urlopen("https://x"); rq.urlopen("https://x"); fetch("https://x"); sub.urlopen("https://x")
    http.client.HTTPConnection("x"); HTTPSConnection("x")
    socket.socket(); socket.create_connection(("x", 1)); raw.socket(); _socket.socket()
    requests.get("https://x"); requests.Session(); hx.Client(); httpx2.AsyncClient(); urllib3.PoolManager()
    aiohttp.ClientSession(); requests.api.post("https://x")
    getattr(subprocess, "run")(["true"]); dyn.run(["true"]); importlib.import_module("os").system("true")
    capabilities.subprocess.run(["true"]); again.run(["true"]); RUN(["true"]); sys.modules["subprocess"].run([])
    posix.system("true"); pty.spawn(["sh"]); multiprocessing.Process(target=print); webbrowser.open("https://x")
    concurrent.futures.ProcessPoolExecutor(); smtplib.SMTP("x"); urllib.request.urlretrieve("https://x")
    asyncio.open_connection("x", 1)

def listeners(loop, handler):
    socket.create_server(("", 0)); asyncio.start_server(handler, "", 0); http.server.ThreadingHTTPServer(("", 0), handler)
    socketserver.TCPServer(("", 0), handler); loop.subprocess_exec(handler, "true")
    asyncio.get_running_loop().create_connection(handler, "x", 1)

def openers(request):
    build_opener().open(request)
    held = urllib.request.build_opener()
    held.open(request)
    send = build_opener().open
    getattr(held, "open")(request)
    urllib.request.OpenerDirector().open(request)

def injected(runner=subprocess.run):
    return runner

def annotated(sock: socket.socket) -> os.system("true"):
    if (spawn := subprocess.Popen):
        return spawn

class Outer:
    def method(self):
        def inner():
            return sp.Popen(["true"])
        return lambda: socket.create_connection(("x", 1))
'''
    found = _sites({"greg/probe.py": source})
    expected = {
        ("<module>", "subprocess.run"): 1,
        ("calls", "subprocess.run"): 8, ("calls", "subprocess.check_output"): 1, ("calls", "subprocess.Popen"): 1,
        ("calls", "subprocess.getoutput"): 1, ("calls", "os.system"): 3, ("calls", "os.popen"): 1,
        ("calls", "os.spawnlp"): 1, ("calls", "os.execv"): 1, ("calls", "os.posix_spawnp"): 1, ("calls", "os.fork"): 1,
        ("calls", "os.forkpty"): 1, ("calls", "asyncio.create_subprocess_exec"): 2,
        ("calls", "asyncio.create_subprocess_shell"): 1, ("calls", "urllib.request.urlopen"): 4,
        ("calls", "http.client.HTTPConnection"): 1, ("calls", "http.client.HTTPSConnection"): 1,
        ("calls", "socket.socket"): 3, ("calls", "socket.create_connection"): 1, ("calls", "requests.get"): 1,
        ("calls", "requests.Session"): 1, ("calls", "httpx.Client"): 1, ("calls", "httpx2.AsyncClient"): 1,
        ("calls", "urllib3.PoolManager"): 1, ("calls", "aiohttp.ClientSession"): 1, ("calls", "requests.api.post"): 1,
        ("calls", "pty.spawn"): 1, ("calls", "multiprocessing.Process"): 1, ("calls", "webbrowser.open"): 1,
        ("calls", "concurrent.futures.ProcessPoolExecutor"): 1, ("calls", "smtplib.SMTP"): 1,
        ("calls", "urllib.request.urlretrieve"): 1, ("calls", "asyncio.open_connection"): 1,
        ("listeners", "socket.create_server"): 1, ("listeners", "asyncio.start_server"): 1,
        ("listeners", "http.server.ThreadingHTTPServer"): 1, ("listeners", "socketserver.TCPServer"): 1,
        ("listeners", f"{LOOP}.subprocess_exec"): 1, ("listeners", f"{LOOP}.create_connection"): 1,
        ("openers", OPENER): 3, ("openers", OPENER_OPEN): 5, ("openers", "urllib.request.OpenerDirector"): 1,
        ("injected", "subprocess.run"): 1,
        ("annotated", "os.system"): 1, ("annotated", "subprocess.Popen"): 2,
        ("Outer.method.inner", "subprocess.Popen"): 1, ("Outer.method.<lambda>", "socket.create_connection"): 1,
    }
    assert found == {("greg/probe.py", qual, callee): n for (qual, callee), n in expected.items()}


def test_what_is_not_an_effect_is_not_listed():
    lazy = '''from __future__ import annotations
import os, socket, subprocess, urllib.parse, requests, httpx, httpx2

def quiet(sock: socket.socket, done: subprocess.CompletedProcess = None) -> os.system("true"):
    os.kill(1, 0); os.killpg(1, 0); os.path.join("a", "b"); os.environ.get("X")
    urllib.parse.urlsplit("https://x"); socket.socketpair(); socket.gethostname()
    sock: socket.socket = sock
    if isinstance(sock, (socket.socket, str)) or issubclass(type(sock), socket.socket):
        pass
    try:
        pass
    except (subprocess.TimeoutExpired, requests.exceptions.Timeout, httpx.HTTPStatusError):
        pass
    match sock:
        case socket.socket():
            pass
    print(requests.codes.ok, subprocess.run.__doc__, httpx2.Timeout(30.0), requests.Session.get)
    text = "subprocess.run(['true'])"
    requests = []
    requests.append(1)
    def run(argv):
        return argv
    run(["true"])
    subprocess.run = None
    return subprocess.PIPE, subprocess.DEVNULL
'''
    evaluated = '''import os, socket

def eager(sock: socket.socket = None) -> socket.socket:
    local: os.system("never evaluated in a function body") = 1
    return sock

class Typed:
    field: socket.socket = None
'''
    assert _sites({"greg/quiet.py": lazy, "greg/eager.py": evaluated}) == {}


def test_names_are_followed_across_scanned_modules():
    sources = {
        "greg/a.py": "from subprocess import run\nimport subprocess as _sp\nfrom os import system as _host_system\n",
        "greg/b.py": ("from greg.a import run, _sp\nfrom greg import a\n\n"
                      "def f():\n    run(['curl', 'https://x']); _sp.Popen(['true']); a._host_system('true')\n"),
        "greg/c.py": "from greg.b import run as again\nRUN = again\n\ndef g():\n    return RUN(['true'])\n",
        "greg/egress_like.py": "import urllib.request\n\ndef opener():\n    return urllib.request.build_opener()\n",
        "greg/relay.py": "from greg.egress_like import opener as make\n\ndef factory():\n    return make()\n",
        "greg/caller.py": ("from greg import relay\n\ndef send(request):\n    held = relay.factory()\n"
                           "    return held.open(request)\n"),
    }
    assert _sites(sources) == {
        ("greg/b.py", "f", "subprocess.run"): 1, ("greg/b.py", "f", "subprocess.Popen"): 1,
        ("greg/b.py", "f", "os.system"): 1, ("greg/c.py", "g", "subprocess.run"): 1,
        ("greg/c.py", "<module>", "subprocess.run"): 1,
        ("greg/egress_like.py", "opener", OPENER): 1, ("greg/caller.py", "send", OPENER_OPEN): 1,
    }


def test_declared_wrappers_are_listed_at_each_caller():
    egress = ("import urllib.request\n\ndef opener():\n    return urllib.request.build_opener()\n\n"
              "def send(request, timeout):\n    return opener().open(request, timeout=timeout)\n")
    caps = ("import subprocess\n\ndef run_isolated(argv, *, isolate_network: bool = True):\n"
            "    return subprocess.run(argv)\n")
    callers = '''from greg import egress, caps
from greg.caps import run_isolated

def unchecked(request):
    egress.send(request, 5)
    sender = egress.opener().open
    getattr(egress.opener(), "open")(request)
    return sender

def confined(argv, flags):
    run_isolated(argv); run_isolated(argv, isolate_network=True); caps.run_isolated(argv, isolate_network=True)

def open_network(argv, flags, model):
    run_isolated(argv, isolate_network=False); caps.run_isolated(argv, isolate_network=model is None)
    run_isolated(argv, **flags); run_isolated(argv, isolate_network=1)
    return run_isolated
'''
    wrappers = {"greg.egress.send": {}, "greg.egress.opener": {}, "greg.caps.run_isolated": {"isolate_network": True}}
    found = _sites({"greg/egress.py": egress, "greg/caps.py": caps, "greg/callers.py": callers}, wrappers)
    assert found == {
        ("greg/egress.py", "opener", OPENER): 1, ("greg/egress.py", "send", OPENER_OPEN): 1,
        ("greg/egress.py", "send", "greg.egress.opener"): 1, ("greg/caps.py", "run_isolated", "subprocess.run"): 1,
        ("greg/callers.py", "unchecked", "greg.egress.send"): 1, ("greg/callers.py", "unchecked", OPENER_OPEN): 2,
        ("greg/callers.py", "unchecked", "greg.egress.opener"): 2,
        ("greg/callers.py", "open_network", "greg.caps.run_isolated"): 5,
    }
    document = {"wrappers": [{"module": "greg/caps.py", "qualname": "run_isolated",
                              "exempt_when": {"isolate_network": False}, "why": "w"},
                             {"module": "greg/caps.py", "qualname": "gone", "exempt_when": {}, "why": "w"},
                             {"module": "greg/callers.py", "qualname": "confined", "exempt_when": {}, "why": "w"}]}
    problems = wrapper_problems(document, scan_sources({"greg/caps.py": caps, "greg/callers.py": callers}),
                                {"greg/caps.py": caps, "greg/callers.py": callers})
    assert len(problems) == 3
    assert "exempt_when isolate_network=False needs a keyword-only parameter" in problems[0]
    assert problems[1].startswith("STALE wrapper greg/caps.py :: gone: no such top-level function")
    assert problems[2].startswith("STALE wrapper greg/callers.py :: confined: its body holds no effect site")


def test_a_star_import_fails_and_cannot_be_listed():
    found = scan_sources({"greg/star.py": "from subprocess import *\n\ndef go():\n    return run(['true'])\n"})
    assert found == {("greg/star.py", "<module>", "subprocess.*"): Counter({"star-import": 1})}
    entry = {"module": "greg/star.py", "qualname": "<module>", "callee": "subprocess.*", "count": 1,
             "serves": ["operator:x"], "justification": "j"}
    problems = compare(found, {"allowed": [entry], "known_unmediated": []})
    assert len(problems) == 1 and problems[0].startswith("STAR IMPORT greg/star.py :: <module> :: subprocess.*")
    assert any("a star import cannot be allowlisted" in p for p in malformed({"allowed": [entry],
                                                                              "known_unmediated": []}, set()))


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
    assert "\"wrappers\"" in unlisted
    assert stale.startswith("STALE allowed entry greg/c.py :: h :: os.system")
    assert mismatch.startswith("COUNT MISMATCH greg/a.py :: f :: subprocess.run") and '"count": 2' in mismatch
    assert compare({("greg/a.py", "f", "subprocess.run"): Counter(call=1)},
                   {"allowed": [], "known_unmediated": [document["allowed"][0]]}) == []


def test_body_loop_is_a_finding_never_an_approval():
    entry = {"module": "greg/a.py", "qualname": "f", "callee": "subprocess.run", "count": 1,
             "justification": "a fixed read only host query on macOS"}
    unmediated = {key: value for key, value in entry.items() if key != "justification"}
    as_allowed = malformed({"allowed": [{**entry, "serves": ["body-loop:Body.run"]}], "known_unmediated": []}, set())
    assert any("belongs under known_unmediated" in problem for problem in as_allowed)
    unnamed = malformed({"allowed": [], "known_unmediated": [{**unmediated, "serves": ["operator:x"],
                                                              "reason": entry["justification"]}]}, set())
    assert any("names the body's schedule" in problem for problem in unnamed)


# -- the tree against its allowlist --------------------------------------------------------------------------

def test_allowlist_is_well_formed():
    from greg.capabilities import BUILTINS
    assert malformed(load_allowlist(), BUILTINS) == []


def test_every_effect_call_site_is_listed():
    document = load_allowlist()
    sources = read_tree()
    found = scan_sources(sources, wrapper_table(document))
    problems = wrapper_problems(document, found, sources) + compare(found, document)
    assert not problems, "\n\n".join(problems)
