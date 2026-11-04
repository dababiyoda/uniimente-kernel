"""Every effectful call site in greg/, foundry/systems/ and the repository modules they import is on a reviewed
allowlist (MU-D, S37, S67).

An effectful call reaches outside the Python process:
- a child process: ``subprocess.run|Popen|call|check_call|check_output|getoutput|getstatusoutput``,
  ``os.system|popen|fork|forkpty|startfile|spawn*|exec*|posix_spawn*`` (``posix.*`` is the same function),
  ``asyncio.create_subprocess_exec|shell`` (also under ``asyncio.subprocess``), ``pty.spawn|fork``,
  ``multiprocessing.Process|Pool``, a context or manager that hands one out (``multiprocessing.get_context|Manager``,
  ``multiprocessing.pool.Pool``, the ``multiprocessing.managers`` managers), ``concurrent.futures.ProcessPoolExecutor``,
  ``webbrowser.open*|get``;
- a stdlib call that starts a child itself: ``platform.platform|processor|architecture`` (``uname -p`` and
  ``file -b``, found on PATH) and ``ctypes.util.find_library`` (``ldconfig -p``, then ``gcc`` and ``ld`` on PATH);
- code the scan cannot read, run in this process: the builtins ``exec`` and ``eval`` (where the module does not
  rebind the name) and ``runpy.run_module|run_path``;
- an outbound connection: ``urllib.request.urlopen|urlretrieve``, ``urllib.request.build_opener|OpenerDirector``
  and the ``.open`` of the opener they build, the ``urllib.request`` handlers and legacy openers that connect
  (``HTTPHandler|HTTPSHandler|FTPHandler|CacheFTPHandler|URLopener|FancyURLopener``),
  ``http.client.HTTPConnection|HTTPSConnection``, ``socket.socket|SocketType|create_connection`` (and
  ``ssl.create_connection``, the same function), ``ssl.get_server_certificate``,
  ``asyncio.open_connection|open_unix_connection``, the stdlib mail, FTP, telnet, NNTP and XML-RPC clients, and the
  I/O entry points of ``requests``, ``httpx``, ``httpx2``, ``urllib3`` and ``aiohttp`` (their request functions,
  sessions, clients, pools and transports, not their exceptions or constants);
- a name lookup: ``socket.getaddrinfo|gethostbyname|gethostbyname_ex|gethostbyaddr|getnameinfo|getfqdn``. A lookup
  sends the name to a resolver the host chooses, and a name can carry data out, so it counts as egress;
  ``socket.gethostname`` reads the local name and does not;
- an inbound listener: ``socket.create_server``, ``asyncio.start_server|start_unix_server``,
  ``http.server.HTTPServer|ThreadingHTTPServer`` and the ``socketserver`` servers;
- an event loop's ``subprocess_exec|subprocess_shell|create_connection|create_server|getaddrinfo|...`` on any
  receiver, a name the scan resolves included (a loop is an object, often held in an imported name or a class
  attribute).
``os.kill`` is not one: it signals a process the body already owns.

Names are resolved, so ``import subprocess as sp``, ``from subprocess import run as r``, ``sp = subprocess``,
``RUN = subprocess.run``, a name another scanned module imported or bound (followed module to module),
``importlib.import_module("subprocess")``, ``__import__`` (with or without ``fromlist``), ``sys.modules["subprocess"]``
and ``getattr(subprocess, "run")`` all count. A bare reference to an effect callable (``runner=subprocess.run``,
``send = opener.open``) counts like a call: it is how an effect is injected and later called under another name.
So does a module that holds one (``subprocess``, ``socket``, ``urllib.request``, ...) used as a value anywhere the
scan cannot follow a name: stored on an attribute or a class (``self.sp = subprocess``), a parameter default
(``sp=subprocess``), an argument (``vars(subprocess)``, ``attrgetter("run")(subprocess)``, ``go(subprocess)``), a
container, a loop or ``with`` target's source, a return value, or its namespace (``subprocess.__dict__``). Only a
plain name bound outside a class body is followed instead; ``getattr`` or ``hasattr`` with a literal name is an
attribute access. A star import fails the check: the names it binds cannot be resolved. Annotations are read where
Python evaluates them (parameter, return and module- or class-level annotations in a module without
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
Gate, supervised worker or person-run command behind them; they are findings, not approvals, and FINDINGS below
names each, so one cannot be re-filed as an approval by editing the list alone. Every entry carries a ``pin``: a
digest of the code its text describes, parsed, so comments and layout do not count. A known_unmediated reason is
pinned to its whole enclosing definition, an allowed justification to the calls recorded at its site (callee,
arguments, keywords); both also cover every module-level constant that code reads. Any change to that code fails
the check until someone re-reads the text and re-pins it. A pin binds what is run at the site, not who reaches it:
the routes a ``serves`` names are read from the code by hand, except that a declared wrapper makes each of its
callers a site.

``path_lookups`` lists every place the scanned code picks a program by name (``shutil.which``, or an argv whose
first item has no slash) with what it searches: the body's own PATH, a literal directory list, ``os.defpath`` or
something computed. A program found on the ambient PATH is whatever file of that name comes first in a directory
the body inherited. While ``bwrap`` is found that way, an allowed justification that relies on bubblewrap, a
namespace or the envelope must say so.

Being listed authorizes nothing: the list is a review-time inventory, and the Gate, the capability manifests and the
founder's authority are unchanged.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST = Path("tests/security/effect-call-allowlist.json")
SCANNED = ("greg", "foundry/systems")
# Where an import is looked up, in order: the repository root, and tools/, which greg.capabilities puts on sys.path
# to load the Kernel's seccomp filter (``_network_filter``). test_sys_path_roots_are_module_roots keeps this complete.
MODULE_ROOTS = ("", "tools")
MODULE = "<module>"

SUBPROCESS = frozenset({"run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput"})
OS_NAMES = frozenset({"system", "popen", "fork", "forkpty", "startfile"})
OS_PREFIXES = ("spawn", "exec", "posix_spawn")
# A callable that also lives under another module is keyed by its documented home (posix.system is os.system).
SAME_AS = {"posix": "os", "nt": "os", "asyncio.subprocess": "asyncio", "asyncio.streams": "asyncio",
           "_socket": "socket", "concurrent.futures.process": "concurrent.futures",
           "multiprocessing.context": "multiprocessing"}
DNS_LOOKUPS = ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr", "getnameinfo", "getfqdn")
SOCKETSERVERS = ("TCPServer", "UDPServer", "UnixStreamServer", "UnixDatagramServer", "ThreadingTCPServer",
                 "ThreadingUDPServer", "ForkingTCPServer", "ForkingUDPServer", "ThreadingUnixStreamServer",
                 "ThreadingUnixDatagramServer", "ForkingUnixStreamServer", "ForkingUnixDatagramServer")
EXACT = frozenset({
    # child processes
    "asyncio.create_subprocess_exec", "asyncio.create_subprocess_shell", "pty.spawn", "pty.fork",
    "multiprocessing.Process", "multiprocessing.Pool", "concurrent.futures.ProcessPoolExecutor",
    # a context or manager whose Process, Pool or start() spawns (the object is handed out, so naming it counts)
    "multiprocessing.get_context", "multiprocessing.Manager", "multiprocessing.pool.Pool",
    "multiprocessing.managers.BaseManager", "multiprocessing.managers.SyncManager",
    "_posixsubprocess.fork_exec", "webbrowser.open", "webbrowser.open_new", "webbrowser.open_new_tab", "webbrowser.get",
    # stdlib calls that start a child themselves (measured on Python 3.11 with an audit hook)
    "platform.platform", "platform.processor", "platform.architecture", "ctypes.util.find_library",
    # outbound connections
    "urllib.request.urlopen", "urllib.request.urlretrieve", "urllib.request.build_opener",
    "urllib.request.OpenerDirector", "urllib.request.HTTPHandler", "urllib.request.HTTPSHandler",
    "urllib.request.FTPHandler", "urllib.request.CacheFTPHandler", "urllib.request.URLopener",
    "urllib.request.FancyURLopener", "http.client.HTTPConnection", "http.client.HTTPSConnection", "socket.socket",
    "socket.SocketType", "socket.create_connection", "ssl.create_connection", "asyncio.open_connection",
    "asyncio.open_unix_connection", "smtplib.SMTP", "smtplib.SMTP_SSL", "smtplib.LMTP", "ftplib.FTP", "ftplib.FTP_TLS",
    "poplib.POP3", "poplib.POP3_SSL", "imaplib.IMAP4", "imaplib.IMAP4_SSL", "xmlrpc.client.ServerProxy",
    "ssl.get_server_certificate", "telnetlib.Telnet", "nntplib.NNTP", "nntplib.NNTP_SSL",
    # code the scan cannot read, run in this process (a builtin only where the module does not rebind its name)
    "builtins.exec", "builtins.eval", "runpy.run_module", "runpy.run_path",
    # name lookups (a query to the host's resolver)
    *(f"socket.{lookup}" for lookup in DNS_LOOKUPS),
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
DYNAMIC_BUILTINS = ("exec", "eval")
# Where a program named without a slash is looked up (path_lookups): the body's own PATH, a literal, os.defpath (a
# child env without PATH), or something the scan cannot read.
AMBIENT, DEFAULT_PATH, COMPUTED = "ambient PATH", "os.defpath", "<computed>"
ARGV_FIRST = frozenset({f"subprocess.{name}" for name in ("run", "Popen", "call", "check_call", "check_output")})
PROGRAM_AT = {"asyncio.create_subprocess_exec": 0, "os.execvp": 0, "os.execlp": 0, "os.execvpe": 0, "os.execlpe": 0,
              "os.posix_spawnp": 0, "os.spawnvp": 1, "os.spawnlp": 1, "os.spawnvpe": 1, "os.spawnlpe": 1}
LOOP = "asyncio.AbstractEventLoop"
LOOP_METHODS = frozenset({"subprocess_exec", "subprocess_shell", "create_connection", "create_unix_connection",
                          "create_datagram_endpoint", "create_server", "create_unix_server", "sock_connect",
                          "getaddrinfo", "getnameinfo"})
OPENER_BUILDERS = frozenset({"urllib.request.build_opener", "urllib.request.OpenerDirector"})
OPENER = "urllib.request.build_opener"
OPENER_OPEN = OPENER + "().open"
EXEMPT = "-"            # _effect_of: a wrapper call its exempt_when keywords cover, neither a call nor a reference
# A module that holds an effect callable, and the packages above it: used as a value where the scan cannot follow a
# name, it carries every effect it holds. Keyed by its documented home, like a callee.
EFFECT_MODULES = frozenset({"subprocess", "os", *HTTP_LIBRARIES,
                            *(parent for name in EXACT for parent in
                              (".".join(name.split(".")[:end]) for end in range(1, name.count(".") + 1)))})
MODULE_REFERENCE = "module reference"
# Dunder attributes of a module that name data, not its namespace; any other (``__dict__``, ``__getattribute__``,
# ``__loader__``, ...) hands the namespace out.
MODULE_DATA = frozenset({"__name__", "__file__", "__doc__", "__version__", "__package__", "__all__"})
# Fields a newer Python adds to a node without changing the code it parsed; the pin ignores them.
VERSION_FIELDS = frozenset({"type_params", "type_comment", "kind"})

ENTRY_FIELDS = {"allowed": {"module", "qualname", "callee", "count", "serves", "justification", "pin"},
                "known_unmediated": {"module", "qualname", "callee", "count", "serves", "reason", "pin"}}
WRAPPER_FIELDS = {"module", "qualname", "exempt_when", "why"}
LOOKUP_FIELDS = {"module", "qualname", "program", "count", "searches", "note"}
TOP_LEVEL = {"version", "purpose", "rule", "seeded_from", "wrappers", "path_lookups", *ENTRY_FIELDS}
# Every known_unmediated key, here as well as in the JSON: a finding cannot be re-filed as an approval (moved under
# "allowed" with a person-run serves) by editing the list alone. Taking one out is an edit of this test, reviewed as
# one, and is right only when the site is gone or something governs it now.
FINDINGS = frozenset({
    ("greg/body.py", "Body.appraise", "subprocess.run"),
    ("greg/compute.py", "memory_bytes", "subprocess.run"),
    ("greg/licensing.py", "system_binary", "subprocess.run"),
    ("greg/genesis.py", "_binary_license", "greg.licensing.system_binary"),
    ("greg/licensing.py", "requalify_binary", "greg.licensing.system_binary"),
    ("tools/offline_test.py", "install_filter", "ctypes.util.find_library"),
})
# The worker envelope and every namespaced capability run under the file the body finds as ``bwrap``. While a lookup
# of it searches the ambient PATH, a text that leans on that confinement must say so.
ENVELOPE_PROGRAM, ENVELOPE_WORDS = "bwrap", ("bubblewrap", "namespace", "envelope")
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


def effect_module(dotted: str) -> str | None:
    """The module holding effect callables that ``dotted`` names exactly (``posix`` is ``os``), else None. No suffix
    match, unlike ``effect``: ``sys.platform`` is a string, not the platform module. An HTTP library counts by its
    top-level package only (``requests.codes`` is data)."""
    name = _same_as(dotted)
    return name if name in EFFECT_MODULES else None


def module_name(path: str) -> tuple[str, bool]:
    """(dotted module name, is a package) for a repository-relative .py path, under the MODULE_ROOT it is found in."""
    parts = path[:-3].split("/")
    for top in sorted((top for top in MODULE_ROOTS if top), key=len, reverse=True):
        if path.startswith(top + "/"):
            parts = path[len(top) + 1:-3].split("/")
            break
    if parts[-1] == "__init__":
        return ".".join(parts[:-1]), True
    return ".".join(parts), False


def _literal(node):
    return node.value if isinstance(node, ast.Constant) else None


def _hands_out_namespace(attribute: str) -> bool:
    """A module's dunder attribute other than plain data (``__dict__``, ``__getattribute__``, ``__loader__``, ...)."""
    return attribute.startswith("__") and attribute.endswith("__") and attribute not in MODULE_DATA


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
        self.followed = self._followed()
        self.bound = self._bound()
        self.index: _Index | None = None
        self.returns: list[tuple[str, bool, ast.AST]] | None = None   # (function, is top-level, returned value)
        self.names: dict[str, set[str]] = defaultdict(set)
        self.openers: set[str] = set()          # names (``x``) and attributes (``.x``) bound to a built opener
        self.local_factories: set[str] = set()  # functions here (by name) that return a built opener
        self.kinds: dict = defaultdict(Counter)
        self.sites: dict = defaultdict(list)        # (qual, callee) -> the nodes recorded there, for its pin
        self.lookups: dict = defaultdict(Counter)   # (qual, program) -> Counter(searches), see _lookup
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

    def _followed(self) -> set[int]:
        """ids of the values bound to a plain name outside a class body. ``_bind`` follows such a name wherever it is
        used, so the value itself hands nothing out; a class-level name is read as ``self.x`` or ``C.x``, which the
        scan cannot follow."""
        in_class = {id(statement) for node in self.nodes if isinstance(node, ast.ClassDef) for statement in node.body}
        followed = set()
        for node in self.nodes:
            if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)) or node.value is None \
                    or id(node) in in_class:
                continue
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                if isinstance(target, ast.Name):
                    followed.add(id(node.value))
                elif (isinstance(target, (ast.Tuple, ast.List)) and isinstance(node.value, (ast.Tuple, ast.List))
                      and len(target.elts) == len(node.value.elts)):
                    followed |= {id(value) for name, value in zip(target.elts, node.value.elts)
                                 if isinstance(name, ast.Name)}
        return followed

    def _bound(self) -> set[str]:
        """Every name this module binds anywhere (assignment, def, class, import, parameter, ``global``, ``except``
        or ``case`` capture). A builtin the scan treats specially (``isinstance``, ``getattr``, ``exec``, ...) is the
        builtin only where its name is not in this set: ``isinstance = lambda a, b: b(a)`` makes a call of it."""
        bound = set()
        for node in self.nodes:
            if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load):
                bound.add(node.id)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bound.add(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                bound |= {(alias.asname or alias.name).split(".")[0] for alias in node.names}
            elif isinstance(node, ast.arg):
                bound.add(node.arg)
            elif isinstance(node, (ast.Global, ast.Nonlocal)):
                bound |= set(node.names)
            elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name:
                bound.add(node.name)
            elif isinstance(node, ast.MatchMapping) and node.rest:
                bound.add(node.rest)
        return bound

    def _builtin(self, node, *names: str) -> bool:
        """``node`` is the bare name of one of the builtins ``names``, not rebound in this module."""
        return isinstance(node, ast.Name) and node.id in names and node.id not in self.bound

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
        The binding is flow-insensitive, so a reused local name may over-report. It follows plain names only: an effect
        module that goes anywhere else is recorded where it goes (a module reference), and the module docstring and
        the evidence README list what neither reaches."""
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
            if self._builtin(node, *DYNAMIC_BUILTINS):          # exec(...), eval(...) as the builtins
                return {f"builtins.{node.id}"}
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

    def _module_of(self, node) -> str | None:
        """The effect module ``node`` evaluates to (``subprocess``, a name bound to it, ``sys.modules[...]``,
        ``importlib.import_module(...)``), else None."""
        found = {module for name in self.index.expand_all(self.resolve(node)) if (module := effect_module(name))}
        return min(found) if found else None

    def _module_reference(self, node, qual: str, typed: bool) -> bool:
        """Record ``node`` if it hands an effect module out as a value the scan cannot follow; True when ``node``
        denotes an effect module at all (its subtree is handled)."""
        module = self._module_of(node)
        if module is None:
            return False
        if not typed and id(node) not in self.followed:
            self._record(qual, module, MODULE_REFERENCE, node)
        return True

    def _module_read(self, call: ast.Call) -> str | None:
        """The effect module that ``getattr(M, "name"[, default])`` or ``hasattr(M, "name")`` reads one name of."""
        if (self._builtin(call.func, "getattr", "hasattr") and len(call.args) >= 2
                and isinstance(_literal(call.args[1]), str)):
            return self._module_of(call.args[0])
        return None

    # program lookups ------------------------------------------------------------------------------------
    def _text(self, node) -> str | None:
        """The string ``node`` denotes: a literal, or a name this module binds exactly once, to a literal."""
        if isinstance(node, ast.Name):
            values = [value for target, value in self.bindings if isinstance(target, ast.Name) and target.id == node.id]
            node = values[0] if len(values) == 1 else None
        literal = _literal(node)
        return literal if isinstance(literal, str) else None

    def _env_path(self, env) -> str:
        """Where a child started with ``env=env`` looks a bare program name up (subprocess uses the env's PATH)."""
        if env is None:
            return AMBIENT
        if isinstance(env, ast.Name):
            values = [value for target, value in self.bindings if isinstance(target, ast.Name) and target.id == env.id]
            env = values[0] if len(values) == 1 else env
        if not isinstance(env, ast.Dict) or None in env.keys:   # computed, or {**os.environ, ...}
            return COMPUTED
        paths = [value for key, value in zip(env.keys, env.values) if _literal(key) == "PATH"]
        if not paths:
            return DEFAULT_PATH
        return self._text(paths[0]) or COMPUTED

    def _lookup(self, call: ast.Call, qual: str) -> None:
        """Record where ``call`` chooses a program by name: ``shutil.which`` (a literal or computed name; its path=,
        else the ambient PATH), or a process started with a bare program name (no slash), looked up on the PATH of
        the env it is given. Keyed (qual, program); the value is what it searches."""
        names = self.index.expand_all(self.resolve(call.func))
        keywords = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg}
        if "shutil.which" in names:
            path = keywords.get("path", call.args[2] if len(call.args) > 2 else None)
            program = self._text(call.args[0]) if call.args else None
            self.lookups[(qual, program or COMPUTED)][AMBIENT if path is None else self._text(path) or COMPUTED] += 1
            return
        callees = {effect(name) for name in names} - {None}
        wrapped = bool(names & set(self.index.wrappers))
        program = None
        if callees & ARGV_FIRST or wrapped:
            argv = call.args[0] if call.args else keywords.get("args")
            if isinstance(argv, (ast.List, ast.Tuple)) and argv.elts and "executable" not in keywords:
                program = self._text(argv.elts[0])
            searches = COMPUTED if wrapped and not callees & ARGV_FIRST else self._env_path(keywords.get("env"))
        elif (at := next((PROGRAM_AT[c] for c in callees if c in PROGRAM_AT), None)) is not None:
            program = self._text(call.args[at]) if len(call.args) > at else None
            plain = next(c for c in callees if c in PROGRAM_AT)
            searches = (self._env_path(keywords.get("env")) if plain == "asyncio.create_subprocess_exec"
                        else COMPUTED if plain.endswith("e") or plain == "os.posix_spawnp" else AMBIENT)
        if program and "/" not in program:
            self.lookups[(qual, program)][searches] += 1

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
    def _record(self, qual: str, callee: str, kind: str, node) -> None:
        self.kinds[(qual, callee)][kind] += 1
        self.sites[(qual, callee)].append(node)

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
            self._record(qual, f"{base}.*", "star-import", node)
            return
        if isinstance(node, ast.Call):
            self._visit_call(node, qual, local)
            return
        if (isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Load)
                and self._visit_reference(node, qual, typed, local)):
            return
        if (isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load)       # sys.modules["subprocess"]
                and self._module_reference(node, qual, typed)):
            return
        if (isinstance(node, ast.Attribute) and not isinstance(node.ctx, ast.Load)   # subprocess.run = None
                and self._module_of(node.value) is not None):
            return
        for child in ast.iter_child_nodes(node):
            self._visit(child, qual, typed, local)

    def _visit_call(self, node: ast.Call, qual: str, local: bool) -> None:
        func, values = node.func, [*node.args, *(keyword.value for keyword in node.keywords)]
        self._lookup(node, qual)
        if self._builtin(func, "isinstance", "issubclass") and len(node.args) == 2:
            self._visit(node.args[0], qual, local=local)
            self._visit(node.args[1], qual, typed=True, local=local)
            return
        if (opener := self._opened(func)) is not None:          # X.open(...) / getattr(X, "open")(...)
            self._record(qual, OPENER_OPEN, "call", node)
            self._visit(opener, qual, local=local)
        elif (callee := self._effect_of(func, call=node)) == EXEMPT:
            pass                                                # a wrapper call its exempt_when keywords cover
        elif callee is not None:
            self._record(qual, callee, "call", node)
        elif (opener := self._opened(node)) is not None:        # getattr(X, "open") as a value
            self._record(qual, OPENER_OPEN, "reference", node)
            self._visit(opener, qual, local=local)
            return
        elif (callee := self._effect_of(node)) is not None:     # getattr(subprocess, "run") as a value
            self._record(qual, callee, "reference", node)
            return
        elif self._module_reference(node, qual, typed=False):   # importlib.import_module("subprocess") as a value
            return
        elif isinstance(func, ast.Attribute) and func.attr in LOOP_METHODS:   # any receiver: an imported loop too
            self._record(qual, f"{LOOP}.{func.attr}", "call", node)
            self._visit(func.value, qual, local=local)
        elif (module := self._module_read(node)) is not None:   # getattr(os, "O_NOFOLLOW", 0): one name read
            if _hands_out_namespace(node.args[1].value):         # getattr(subprocess, "__dict__") hands all out
                self._record(qual, module, MODULE_REFERENCE, node)
            for value in (*node.args[2:], *(keyword.value for keyword in node.keywords)):
                self._visit(value, qual, local=local)
            return
        else:
            self._visit(func, qual, local=local)
        for value in values:
            self._visit(value, qual, local=local)

    def _visit_reference(self, node, qual: str, typed: bool, local: bool) -> bool:
        """Record ``node`` if it names an effect callable without calling it; True when its subtree is handled."""
        callee = self._effect_of(node)
        if callee is not None:
            if not typed:
                self._record(qual, callee, "reference", node)
            return True
        if self._module_reference(node, qual, typed):          # self.sp = subprocess; sp=subprocess; go(socket)
            return True
        if isinstance(node, ast.Attribute):
            if (module := self._module_of(node.value)) is not None:   # subprocess.PIPE reads one name
                if _hands_out_namespace(node.attr) and not typed:     # subprocess.__dict__ hands all out
                    self._record(qual, module, MODULE_REFERENCE, node)
                return True
            if (opener := self._opened(node)) is not None:      # send = opener().open
                if not typed:
                    self._record(qual, OPENER_OPEN, "reference", node)
                self._visit(opener, qual, local=local)
                return True
            if node.attr != "__call__" and self._effect_of(node.value) is not None:
                return True                                     # subprocess.run.__doc__ starts nothing
            if node.attr in LOOP_METHODS:
                if not typed:
                    self._record(qual, f"{LOOP}.{node.attr}", "reference", node)
                self._visit(node.value, qual, local=local)
                return True
        return False


class Scan:
    """What one pass over the sources found: effect sites, the nodes at each, and program lookups."""

    def __init__(self, found: dict, nodes: dict, lookups: dict, trees: dict):
        self.found, self.nodes, self.lookups, self.trees = found, nodes, lookups, trees


def scan_all(sources: dict[str, str], wrappers: dict | None = None) -> Scan:
    """Effect sites {(module path, qualname, callee): Counter(call=n, reference=m)}, the nodes recorded at each
    (their pins), and program lookups {(module path, qualname, program): Counter(searches)}.
    ``wrappers``: {dotted function: exempt_when} whose callers are sites too (see ``wrapper_table``)."""
    modules = [_Module(path, source) for path, source in sorted(sources.items())]
    index = _Index(modules, wrappers or {})
    for module in modules:
        module.index = index
    for _ in range(len(modules) + 1):                          # an opener factory may return another module's
        grew = [module.find_factories() for module in modules]   # every module, no short-circuit
        if not any(grew):
            break
    found, nodes, lookups = {}, {}, {}
    for module in modules:
        module.scan()
        for (qual, callee), kinds in module.kinds.items():
            found[(module.path, qual, callee)] = kinds
            nodes[(module.path, qual, callee)] = module.sites[(qual, callee)]
        for (qual, program), searches in module.lookups.items():
            lookups[(module.path, qual, program)] = searches
    return Scan(found, nodes, lookups, {module.path: module.tree for module in modules})


def scan_sources(sources: dict[str, str], wrappers: dict | None = None) -> dict[tuple[str, str, str], Counter]:
    """{(module path, qualname, callee): Counter(call=n, reference=m)} for repository-relative sources."""
    return scan_all(sources, wrappers).found


def _module_file(root: Path, dotted: str) -> Path | None:
    """The repository file ``dotted`` imports from, searched in MODULE_ROOTS order like sys.path, else None."""
    for top in MODULE_ROOTS:
        base = root.joinpath(top, *dotted.split("."))
        for path in (base / "__init__.py", base.with_suffix(".py")):
            if path.is_file():
                return path
    return None


def imported_names(path: str, source: str) -> set[str]:
    """Every dotted module name ``source`` may import: ``import``, ``from`` (relative too, and each imported name as a
    possible submodule), ``importlib.import_module`` and ``__import__`` with a literal, at any depth."""
    name, package = module_name(path)
    names = set()
    for node in ast.walk(ast.parse(source, filename=path)):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = name.split(".") if package else name.split(".")[:-1]
                parts = parts[:len(parts) - (node.level - 1)] if node.level > 1 else parts
                base = ".".join(parts + ([node.module] if node.module else []))
            else:
                base = node.module or ""
            names |= {base, *(f"{base}.{alias.name}" for alias in node.names if alias.name != "*")}
        elif (isinstance(node, ast.Call) and node.args and isinstance(_literal(node.args[0]), str)
              and ((isinstance(node.func, ast.Attribute) and node.func.attr == "import_module")
                   or (isinstance(node.func, ast.Name) and node.func.id == "__import__"))):
            names.add(node.args[0].value)
    return {".".join(parts[:cut]) for dotted in names if dotted for parts in [dotted.split(".")]
            for cut in range(1, len(parts) + 1)}


def read_tree(root: Path = ROOT) -> dict[str, str]:
    """greg/, foundry/systems/ and every repository module they import, followed import by import: an effect in
    ``egregore/`` or ``tools/`` that GREG calls is GREG's effect. Third-party and stdlib modules are not read."""
    sources, queue = {}, []
    for top in SCANNED:
        queue += sorted((root / top).rglob("*.py"))
    while queue:
        path = queue.pop()
        relative = path.relative_to(root).as_posix()
        if relative in sources or "__pycache__" in path.parts:
            continue
        sources[relative] = path.read_text(encoding="utf-8")
        queue += [found for dotted in sorted(imported_names(relative, sources[relative]))
                  if (found := _module_file(root, dotted)) is not None]
    return dict(sorted(sources.items()))


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
        escaped = (" A module reference means the module object goes where the scan cannot follow a name (an "
                   "attribute, a class, a default, an argument, a container, a return value, its namespace); "
                   "calling the effect through the module's own name, or a plain name bound to it, keys each call "
                   "instead." if MODULE_REFERENCE in found[key] else "")
        problems.append(
            f"UNLISTED effect call site {' :: '.join(key)} ({_describe(found[key])}).{escaped} Add to {ALLOWLIST} "
            f"under \"allowed\": {_suggested(key, count)} where serves names the governed path behind it (one of "
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
            f"{', '.join(SCANNED)} or the repository modules they import any more. Remove it from {ALLOWLIST}, or, if the call moved, re-key it to the new "
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


def _canonical(node) -> str:
    """``node`` as text without positions, comments or layout, and without the fields newer Pythons add."""
    if isinstance(node, ast.AST):
        fields = ", ".join(f"{name}={_canonical(getattr(node, name, None))}" for name in node._fields
                           if name not in VERSION_FIELDS)
        return f"{type(node).__name__}({fields})"
    if isinstance(node, list):
        return "[" + ", ".join(_canonical(item) for item in node) + "]"
    return repr(node)


def _definition(tree: ast.Module, qualname: str):
    """The innermost named definition on ``qualname``'s path (``f`` for ``f.<lambda>`` or for a function nested in a
    block of ``f``), the module for ``<module>``; None when the outermost name is not defined at top level."""
    if qualname == MODULE:
        return tree
    found, scope = None, tree.body
    for part in qualname.split("."):
        node = next((node for node in scope if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                     and node.name == part), None)
        if node is None:
            break
        found, scope = node, node.body
    return found


def _constants_read(tree: ast.Module, nodes) -> tuple[list, list[str]]:
    """The top-level plain-name assignments (``DPKG_TIMEOUT = 5``) whose names ``nodes`` read, and those names."""
    read = {name.id for node in nodes for name in ast.walk(node)
            if isinstance(name, ast.Name) and isinstance(name.ctx, ast.Load)}
    constants, names = [], set()
    for statement in tree.body:
        if isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None:
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            bound = {target.id for target in targets if isinstance(target, ast.Name)} & read
            if bound:
                constants.append(statement)
                names |= bound
    return constants, sorted(names)


def pinned_code(source: str, qualname: str) -> tuple[str, list[str]] | None:
    """(sha256, constants) over the code a known_unmediated reason describes: the definition ``qualname`` names and
    every top-level plain-name assignment it reads (``DPKG_TIMEOUT = 5``, ``ACTIVE_BINARY_POLICY = "P0"``), each
    parsed, so comments and layout do not count. None when the definition is gone (``compare`` reports it stale)."""
    tree = ast.parse(source)
    definition = _definition(tree, qualname)
    if definition is None:
        return None
    constants, names = _constants_read(tree, [definition]) if definition is not tree else ([], [])
    text = "\n".join(_canonical(node) for node in (definition, *constants))
    return hashlib.sha256(text.encode()).hexdigest(), names


def call_pin(tree: ast.Module, nodes) -> tuple[str, list[str]]:
    """(sha256, constants) over what an allowed justification describes: each call or reference recorded at the
    site (callee, arguments, keywords), in any order, and every top-level constant those read, parsed."""
    constants, names = _constants_read(tree, nodes)
    text = "\n".join(sorted(_canonical(node) for node in nodes)) + "\n--\n" + "\n".join(map(_canonical, constants))
    return hashlib.sha256(text.encode()).hexdigest(), names


def pin_problems(document: dict, sources: dict[str, str], scan: Scan | None = None) -> list[str]:
    """Every entry whose pinned code changed since its text was written: the check holds a known_unmediated reason
    to its whole definition and an allowed justification to the calls at its site, so a rewritten spawn cannot keep
    a text that no longer fits it. ``scan`` (from scan_all) is needed for allowed entries."""
    problems = []
    for entry in document.get("known_unmediated", []):
        source = sources.get(entry["module"])
        pinned = pinned_code(source, entry["qualname"]) if source is not None else None
        if pinned is None:
            continue
        digest, constants = pinned
        if entry.get("pin") != digest:
            reads = f" or a top-level constant it reads ({', '.join(constants)})" if constants else ""
            problems.append(
                f"PIN MISMATCH known_unmediated {' :: '.join(entry_key(entry))}: the code its reason describes "
                f"changed ({entry['qualname']} in {entry['module']}{reads}; compared as parsed, so comments and layout "
                f"do not count). Re-read the reason and serves against the code as it is now. If every word still "
                f"holds, set \"pin\": \"{digest}\"; if not, rewrite them first, or move the entry if the site is now "
                f"governed. A pin binds the reason to the code; it approves nothing.")
    for entry in document.get("allowed", []) if scan is not None else ():
        key = entry_key(entry)
        if key not in scan.nodes:
            continue                                            # compare reports it stale
        digest, constants = call_pin(scan.trees[entry["module"]], scan.nodes[key])
        if entry.get("pin") != digest:
            reads = f" and the top-level constants they read ({', '.join(constants)})" if constants else ""
            problems.append(
                f"PIN MISMATCH allowed {' :: '.join(key)}: a call its justification describes changed (the "
                f"{len(scan.nodes[key])} call(s) or reference(s) at {entry['qualname']} in {entry['module']}{reads}; "
                f"compared as parsed, so comments, layout and the order of the calls do not count). Re-read the "
                f"justification and serves against the calls as they are now. If every word still holds, set "
                f"\"pin\": \"{digest}\"; if not, rewrite them first, or move the entry to known_unmediated. A pin "
                f"binds the justification to the call; it approves nothing.")
    return problems


def finding_problems(document: dict, found: dict) -> list[str]:
    """known_unmediated holds exactly FINDINGS, and each finding's site still exists."""
    filed = {entry_key(entry) for entry in document.get("known_unmediated", [])}
    problems = [f"FINDING RE-FILED {' :: '.join(key)}: it is a recorded finding (FINDINGS in {Path(__file__).name}), "
                f"so it stays under known_unmediated with a body-loop: serves. Moving it out is an edit of FINDINGS, "
                f"reviewed as one, and is right only when the site is gone or governed." for key in sorted(FINDINGS - filed)
                if key in found]
    problems += [f"STALE finding {' :: '.join(key)}: the site is gone; remove it from FINDINGS in "
                 f"{Path(__file__).name} with its entry." for key in sorted(FINDINGS) if key not in found]
    problems += [f"NEW FINDING {' :: '.join(key)}: add it to FINDINGS in {Path(__file__).name} as well, so it cannot be "
                 f"re-filed as an approval by editing the list alone." for key in sorted(filed - FINDINGS)]
    return problems


def _searches(counter: Counter) -> str:
    return " | ".join(sorted(counter))


def lookup_problems(lookups: dict, document: dict) -> list[str]:
    """Every place the scanned code picks a program by name must be listed under path_lookups with what it searches,
    so a new lookup on the body's own PATH, or a lookup that moves to it, is reviewed."""
    listed = {(entry["module"], entry["qualname"], entry["program"]): entry for entry in document.get("path_lookups", [])}
    problems = []
    for key in sorted(set(lookups) - set(listed)):
        suggestion = json.dumps({"module": key[0], "qualname": key[1], "program": key[2],
                                 "count": sum(lookups[key].values()), "searches": _searches(lookups[key]),
                                 "note": "<who runs what it finds, under what confinement>"})
        problems.append(
            f"UNLISTED path lookup {' :: '.join(key)} (searches {_searches(lookups[key])}). Add to {ALLOWLIST} under "
            f"\"path_lookups\": {suggestion}. A program found on the {AMBIENT} is whatever file of that name comes "
            f"first in a directory the body inherited; the note says who runs it, with what privileges and confinement.")
    for key in sorted(set(listed) - set(lookups)):
        problems.append(f"STALE path_lookups entry {' :: '.join(key)}: no such lookup any more. Remove it from "
                        f"{ALLOWLIST}, or re-key it to where the lookup moved.")
    for key in sorted(set(listed) & set(lookups)):
        entry, count, searches = listed[key], sum(lookups[key].values()), _searches(lookups[key])
        if entry["count"] != count:
            problems.append(f"COUNT MISMATCH path lookup {' :: '.join(key)}: listed {entry['count']}, the source has "
                            f"{count}. Set \"count\": {count} and check the note covers each.")
        if entry["searches"] != searches:
            problems.append(f"SEARCHES MISMATCH path lookup {' :: '.join(key)}: listed {entry['searches']!r}, the "
                            f"source searches {searches!r}. Set \"searches\": {json.dumps(searches)} and re-read the note "
                            f"and every entry whose text relies on where this program comes from.")
    return problems


def envelope_problems(document: dict, lookups: dict) -> list[str]:
    """While ``bwrap`` is looked up on the ambient PATH, an allowed justification that relies on bubblewrap, a
    namespace or the worker envelope must say so: the confinement is whatever file that lookup finds. A
    known_unmediated reason is not held to it: nothing governs those sites, and their reasons name the envelope only
    to say it is absent."""
    ambient = sorted(" :: ".join(key) for key, searches in lookups.items()
                     if key[2] == ENVELOPE_PROGRAM and AMBIENT in searches)
    if not ambient:
        return []
    problems = []
    for entry in document.get("allowed", []):
        text = str(entry.get("justification", ""))
        if any(word in text.lower() for word in ENVELOPE_WORDS) and AMBIENT not in text:
            problems.append(
                f"ENVELOPE CLAIM allowed {' :: '.join(entry_key(entry))}: its justification relies on bubblewrap "
                f"confinement, but {'; '.join(ambient)} look {ENVELOPE_PROGRAM} up on the body's {AMBIENT}, so the "
                f"envelope is whatever file of that name comes first there, run unconfined with the body's "
                f"privileges. Say so in the justification (the words \"{AMBIENT}\"), or pin that lookup to a "
                f"trusted path.")
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


def _repository_module(path) -> bool:
    return (isinstance(path, str) and path.endswith(".py") and not path.startswith("/")
            and ".." not in path.split("/") and "\\" not in path)


def _words(text, at_least: int = 6) -> bool:
    return isinstance(text, str) and len(text.split()) >= at_least


def malformed(document: dict, builtins) -> list[str]:
    """Structural problems: missing or extra fields, unknown serves kinds, unknown capability ids, duplicate keys."""
    problems, seen = [], {}
    unknown = set(document) - TOP_LEVEL
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
            if not _repository_module(entry["module"]):
                problems.append(f"{where}: module must be a repository-relative .py path")
            if entry["callee"].endswith(".*"):
                problems.append(f"{where}: a star import cannot be allowlisted")
            if type(entry["count"]) is not int or entry["count"] < 1:
                problems.append(f"{where}: count must be a positive integer")
            if not (isinstance(entry["pin"], str) and re.fullmatch(r"[0-9a-f]{64}", entry["pin"])):
                problems.append(f"{where}: pin must be the sha256 digest the check prints for the code the "
                                f"{'justification' if section == 'allowed' else 'reason'} describes")
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
        if not _repository_module(wrapper["module"]):
            problems.append(f"{where}: module must be a repository-relative .py path")
        if not str(wrapper["qualname"]).isidentifier():
            problems.append(f"{where}: a wrapper is a top-level function, named without dots")
        if not isinstance(wrapper["exempt_when"], dict) or not all(
                isinstance(k, str) and isinstance(v, (bool, int, str, type(None)))
                for k, v in wrapper["exempt_when"].items()):
            problems.append(f"{where}: exempt_when maps keyword names to literals")
        if not _words(wrapper["why"]):
            problems.append(f"{where}: why must say, in words grounded in the code, which check the wrapper skips")
    lookups = document.get("path_lookups", [])
    if not isinstance(lookups, list):
        return problems + ["path_lookups must be a list"]
    keys = set()
    for entry in lookups:
        if not isinstance(entry, dict) or set(entry) != LOOKUP_FIELDS:
            problems.append(f"path_lookups entry {entry!r} must have exactly the fields {sorted(LOOKUP_FIELDS)}")
            continue
        key = (entry["module"], entry["qualname"], entry["program"])
        where = f"path lookup {' :: '.join(map(str, key))}"
        if key in keys:
            problems.append(f"{where} is listed twice")
        keys.add(key)
        if not _repository_module(entry["module"]):
            problems.append(f"{where}: module must be a repository-relative .py path")
        if type(entry["count"]) is not int or entry["count"] < 1:
            problems.append(f"{where}: count must be a positive integer")
        if not isinstance(entry["searches"], str) or not entry["searches"]:
            problems.append(f"{where}: searches is what the check prints for the lookup")
        if not _words(entry["note"]):
            problems.append(f"{where}: note must say who runs what the lookup finds, with what privileges and "
                            f"confinement")
    return problems


# -- the scanner, against known inputs ---------------------------------------------------------------------

def _sites(sources: dict[str, str], wrappers: dict | None = None) -> dict:
    return {key: sum(kinds.values()) for key, kinds in scan_sources(sources, wrappers).items()}


def _heads(problems: list[str], expected: list[str]) -> list[str]:
    """Each problem cut to the length of the prefix expected at its place, extra problems kept whole: compared with
    ``expected``, a failure prints both lists, so it names the problem that is missing or unexpected."""
    return [problem[:len(prefix)] for problem, prefix in zip(problems, expected)] + problems[len(expected):]


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
import os, socket, subprocess, urllib.parse, requests, httpx, httpx2, platform, sys

def quiet(sock: socket.socket, done: subprocess.CompletedProcess = None) -> os.system("true"):
    os.kill(1, 0); os.killpg(1, 0); os.path.join("a", "b"); os.environ.get("X")
    urllib.parse.urlsplit("https://x"); socket.socketpair(); socket.gethostname()
    print(getattr(os, "O_NOFOLLOW", 0), hasattr(os, "fork"), subprocess.__name__, socket.timeout, sys.platform)
    print(platform.system(), platform.machine(), platform.release(), platform.python_version())
    alias = subprocess
    print(alias.PIPE, alias.__name__)
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


def test_an_effect_module_used_as_a_value_and_the_added_callees_are_sites():
    source = '''
import subprocess, socket, ssl, os, operator, platform, ctypes.util, sys, importlib
import urllib.request
from contextlib import nullcontext

TOOLS = {"sp": subprocess}
followed = subprocess

class Runner:
    host = os
    def __init__(self):
        self.sp = subprocess
    def go(self):
        return self.sp.run(["id"]), self.host.system("id"), followed.run(["id"])

def injected(argv, sp=subprocess):
    return sp.run(argv)

def passed():
    vars(subprocess)["run"](["id"]); operator.attrgetter("run")(subprocess)(["id"])
    return subprocess.__dict__["Popen"](["id"])

def looped():
    for sp in (subprocess,):
        sp.Popen(["id"])
    with nullcontext(socket) as s:
        return s

def returned():
    return importlib.import_module("subprocess"), sys.modules["socket"], getattr(subprocess, "__dict__")

def added(secret):
    ssl.create_connection(("x", 443)); socket.SocketType(); urllib.request.HTTPSHandler().https_open(None)
    urllib.request.HTTPHandler(); urllib.request.URLopener(); socket.getaddrinfo(secret + ".x", 443)
    socket.gethostbyname("x"); socket.getfqdn(); platform.platform(); platform.processor(); platform.architecture()
    ctypes.util.find_library("c")
'''
    module = {"<module>": {"subprocess": 1}, "Runner": {"os": 1}, "Runner.__init__": {"subprocess": 1},
              "injected": {"subprocess": 1}, "passed": {"subprocess": 3},
              "looped": {"subprocess": 1, "socket": 1}, "returned": {"subprocess": 2, "socket": 1}}
    expected = {(qual, callee): n for qual, callees in module.items() for callee, n in callees.items()}
    expected |= {("Runner.go", "subprocess.run"): 1}            # followed: a plain name bound at module level
    expected |= {("added", callee): 1 for callee in (
        "ssl.create_connection", "socket.SocketType", "urllib.request.HTTPSHandler", "urllib.request.HTTPHandler",
        "urllib.request.URLopener", "socket.getaddrinfo", "socket.gethostbyname", "socket.getfqdn",
        "platform.platform", "platform.processor", "platform.architecture", "ctypes.util.find_library")}
    found = scan_sources({"greg/probe.py": source})
    assert {key[1:]: sum(kinds.values()) for key, kinds in found.items()} == expected
    assert all(set(kinds) == {MODULE_REFERENCE} for key, kinds in found.items() if (key[1], key[2]) in
               {(qual, callee) for qual, callees in module.items() for callee in callees})
    problem = compare(found, {"allowed": [], "known_unmediated": []})[0]
    assert problem.startswith("UNLISTED effect call site greg/probe.py :: <module> :: subprocess (1 module reference)")
    assert "keys each call instead" in problem


def test_a_known_unmediated_pin_binds_its_reason_to_the_code():
    module = ('import subprocess\nTIMEOUT = 5\nPOLICY = "P0"\nUNREAD = 1\n\n\ndef probe(path):\n'
              '    # resolved on the body\'s PATH\n    return subprocess.run(["q", path], timeout=TIMEOUT)\n')
    digest, constants = pinned_code(module, "probe")
    assert constants == ["TIMEOUT"]
    same = (module.replace("    # resolved on the body's PATH\n", ""), module.replace("UNREAD = 1", "UNREAD = 2"),
            module.replace('["q", path]', '[\n        "q",  path,\n    ]'))
    assert [pinned_code(text, "probe")[0] for text in same] == [digest] * 3      # comments, layout, unread names
    changed = (module.replace('["q", path]', '"q " + path + "; curl x", shell=True'),
               module.replace("timeout=TIMEOUT", "timeout=None"), module.replace("TIMEOUT = 5", "TIMEOUT = 500"),
               module.replace('return subprocess.run(["q", path], timeout=TIMEOUT)', 'return subprocess.run'))
    assert all(pinned_code(text, "probe")[0] != digest for text in changed)       # what it runs, constants, kind
    entry = {"module": "greg/p.py", "qualname": "probe", "callee": "subprocess.run", "count": 1,
             "serves": ["body-loop:Body.tick"], "reason": "a fixed query with a five second timeout", "pin": digest}
    assert pin_problems({"known_unmediated": [entry]}, {"greg/p.py": module}) == []
    problems = pin_problems({"known_unmediated": [entry]}, {"greg/p.py": changed[2]})
    assert len(problems) == 1 and problems[0].startswith(
        "PIN MISMATCH known_unmediated greg/p.py :: probe :: subprocess.run: the code its reason describes changed "
        "(probe in greg/p.py or a top-level constant it reads (TIMEOUT);")
    assert pinned_code(module, "gone") is None and pin_problems(
        {"known_unmediated": [{**entry, "qualname": "gone"}]}, {"greg/p.py": module}) == []   # compare: stale
    nested = ("class Body:\n    def appraise(self):\n        if True:\n"
              "            def inner():\n                return 1\n")
    method = ast.parse(nested).body[0].body[0]
    assert pinned_code(nested, "Body.appraise.inner")[0] == pinned_code(nested, "Body.appraise")[0] == \
        hashlib.sha256(_canonical(method).encode()).hexdigest()
    assert any("pin must be the sha256 digest" in p for p in malformed(
        {"allowed": [], "known_unmediated": [{**entry, "pin": "ab"}]}, set()))
    unpinned = {key: value for key, value in entry.items() if key != "pin"}
    assert any("must have exactly the fields" in p for p in malformed(
        {"allowed": [], "known_unmediated": [unpinned]}, set()))


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
             "serves": ["operator:x"], "justification": "j", "pin": "0" * 64}
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
             "justification": "a fixed read only host query on macOS", "pin": "0" * 64}
    unmediated = {key: value for key, value in entry.items() if key != "justification"}
    as_allowed = malformed({"allowed": [{**entry, "serves": ["body-loop:Body.run"]}], "known_unmediated": []}, set())
    assert any("belongs under known_unmediated" in problem for problem in as_allowed)
    unnamed = malformed({"allowed": [], "known_unmediated": [{**unmediated, "serves": ["operator:x"],
                                                              "reason": entry["justification"]}]}, set())
    assert any("names the body's schedule" in problem for problem in unnamed)


def test_a_finding_cannot_be_refiled_as_an_approval():
    found = {key: Counter(call=1) for key in FINDINGS}
    filed = [{"module": key[0], "qualname": key[1], "callee": key[2]} for key in sorted(FINDINGS)]
    assert finding_problems({"known_unmediated": filed}, found) == []
    moved = min(FINDINGS)                                       # re-filed under allowed with an operator: serves
    problems = finding_problems({"known_unmediated": filed[1:]}, found)
    assert _heads(problems, [f"FINDING RE-FILED {' :: '.join(moved)}"]) == [f"FINDING RE-FILED {' :: '.join(moved)}"]
    extra = ("greg/new.py", "tick", "subprocess.run")
    problems = finding_problems({"known_unmediated": [*filed, dict(zip(("module", "qualname", "callee"), extra))]},
                                {**found, extra: Counter(call=1)})
    assert _heads(problems, [f"NEW FINDING {' :: '.join(extra)}"]) == [f"NEW FINDING {' :: '.join(extra)}"]
    gone = {key: count for key, count in found.items() if key != moved}
    assert finding_problems({"known_unmediated": filed[1:]}, gone) == [
        (f"STALE finding {' :: '.join(moved)}: the site is gone; remove it from FINDINGS in {Path(__file__).name} "
         f"with its entry.")]


def test_the_round_three_forms_are_sites():
    probe = '''import multiprocessing, ssl, subprocess
from multiprocessing.pool import Pool
from greg.rt import LOOP
isinstance = lambda value, kind: kind(value)


class C:
    loop = None


def forms(handler):
    multiprocessing.get_context("spawn").Process(target=print).start(); Pool(1)
    ssl.get_server_certificate(("collector.example", 443)); exec("import subprocess; subprocess.run(['id'])")
    isinstance(["id"], subprocess.Popen)
    LOOP.create_connection(handler, "collector.example", 443); C.loop.subprocess_exec(handler, "id")
'''
    found = _sites({"greg/probe.py": probe, "greg/rt.py": "import asyncio\nLOOP = None\n"})
    assert found == {("greg/probe.py", "forms", callee): 1 for callee in (
        "multiprocessing.get_context", "multiprocessing.pool.Pool", "ssl.get_server_certificate", "builtins.exec",
        "subprocess.Popen", f"{LOOP}.create_connection", f"{LOOP}.subprocess_exec")}
    rebound = "exec = print\n\ndef quiet():\n    exec('not code')\n"          # the module's own exec, not the builtin
    assert _sites({"greg/quiet.py": rebound}) == {}


def test_program_lookups_record_what_they_search():
    source = '''import os, shutil, subprocess
SAFE = "/usr/bin:/bin"


def lookups(name, env):
    shutil.which("dpkg-query"); shutil.which(name); shutil.which("git", path=SAFE); shutil.which("tar", path=env)
    subprocess.run(["git", "status"]); subprocess.run(["git", "log"], env={"PATH": "/usr/bin:/bin"})
    subprocess.run(["git", "diff"], env={"LANG": "C"}); subprocess.run(["git", "show"], env={**os.environ})
    subprocess.run(["/usr/bin/git", "status"]); subprocess.run(["git"], executable="/usr/bin/git")
    os.execvp("sh", ["sh"]); os.execvpe("sh", ["sh"], env)
'''
    lookups = scan_all({"greg/l.py": source}).lookups
    assert {key[1:]: dict(searches) for key, searches in lookups.items()} == {
        ("lookups", "dpkg-query"): {AMBIENT: 1}, ("lookups", COMPUTED): {AMBIENT: 1}, ("lookups", "tar"): {COMPUTED: 1},
        ("lookups", "git"): {"/usr/bin:/bin": 2, AMBIENT: 1, DEFAULT_PATH: 1, COMPUTED: 1},
        ("lookups", "sh"): {AMBIENT: 1, COMPUTED: 1}}
    listed = [{"module": "greg/l.py", "qualname": "lookups", "program": "dpkg-query", "count": 1,
               "searches": "/usr/bin:/bin", "note": "n"},
              {"module": "greg/l.py", "qualname": "lookups", "program": "sh", "count": 1,
               "searches": f"{COMPUTED} | {AMBIENT}", "note": "n"},
              {"module": "greg/l.py", "qualname": "gone", "program": "git", "count": 1, "searches": AMBIENT, "note": "n"}]
    problems = lookup_problems(lookups, {"path_lookups": listed})
    expected = [
        f"UNLISTED path lookup greg/l.py :: lookups :: {COMPUTED} (searches {AMBIENT})",
        (f"UNLISTED path lookup greg/l.py :: lookups :: git (searches /usr/bin:/bin | {COMPUTED} | {AMBIENT} | "
         f"{DEFAULT_PATH})"),
        f"UNLISTED path lookup greg/l.py :: lookups :: tar (searches {COMPUTED})",
        "STALE path_lookups entry greg/l.py :: gone :: git",
        "SEARCHES MISMATCH path lookup greg/l.py :: lookups :: dpkg-query",
        "COUNT MISMATCH path lookup greg/l.py :: lookups :: sh"]
    assert _heads(problems, expected) == expected


def test_an_envelope_claim_names_the_ambient_path():
    ambient = {("greg/w.py", "_backend", "bwrap"): Counter({AMBIENT: 1})}
    claim = {"module": "greg/a.py", "qualname": "f", "callee": "subprocess.run",
             "justification": "runs inside the bubblewrap envelope with no network"}
    said = {**claim, "qualname": "g", "justification": f"inside a namespace whose bwrap is found on the {AMBIENT}"}
    document = {"allowed": [claim, said],
                "known_unmediated": [{**claim, "qualname": "h", "reason": "no worker envelope stands behind it"}]}
    problems = envelope_problems(document, ambient)
    expected = ["ENVELOPE CLAIM allowed greg/a.py :: f :: subprocess.run: its justification relies on bubblewrap"]
    assert _heads(problems, expected) == expected
    assert envelope_problems(document, {("greg/w.py", "_backend", "bwrap"): Counter({"/usr/bin:/bin": 1})}) == []


def test_an_allowed_pin_binds_its_justification_to_the_calls():
    module = ('import subprocess\nTIMEOUT = 5\n\n\ndef probe(path):\n'
              '    subprocess.run(["git", "-C", path, "status"], timeout=TIMEOUT)\n'
              '    return subprocess.run(["git", "-C", path, "log"])\n')
    key = ("greg/p.py", "probe", "subprocess.run")

    def pin(text):
        scan = scan_all({"greg/p.py": text})
        return call_pin(scan.trees["greg/p.py"], scan.nodes[key])
    digest, constants = pin(module)
    assert constants == ["TIMEOUT"]
    reordered = module.replace('    subprocess.run(["git", "-C", path, "status"], timeout=TIMEOUT)\n', "").replace(
        '    return subprocess', '    # status first\n    subprocess.run(["git", "-C", path,\n'
                                 '                    "status"], timeout=TIMEOUT)\n    return subprocess')
    assert pin(reordered)[0] == digest                          # order, comments and layout do not count
    changed = (module.replace('"log"])', '"log"], env={})'), module.replace("TIMEOUT = 5", "TIMEOUT = 500"),
               module.replace('"status"]', '"-c", "core.fsmonitor=id", "status"]'))
    assert all(pin(text)[0] != digest for text in changed)
    entry = {"module": key[0], "qualname": key[1], "callee": key[2], "count": 2, "serves": ["operator:x"],
             "justification": "two read only git queries on the given path", "pin": digest}
    assert pin_problems({"allowed": [entry]}, {key[0]: module}, scan_all({key[0]: module})) == []
    problems = pin_problems({"allowed": [entry]}, {key[0]: changed[2]}, scan_all({key[0]: changed[2]}))
    expected = ["PIN MISMATCH allowed greg/p.py :: probe :: subprocess.run: a call its justification describes changed"]
    assert _heads(problems, expected) == expected


def test_the_scan_follows_imports_into_the_repository(tmp_path):
    files = {"greg/a.py": "from helpers.b import go\nimport offline_tool\n",
             "helpers/__init__.py": "", "helpers/b.py": "import subprocess\nfrom helpers import c\n\n\ndef go():\n"
                                                        "    return subprocess.run(['id'])\n",
             "helpers/c.py": "x = 1\n", "helpers/unused.py": "import os\n",
             "tools/offline_tool.py": "import os\n\n\ndef spawn():\n    return os.system('id')\n",
             "elsewhere/x.py": "import subprocess\n\n\ndef go():\n    return subprocess.run(['id'])\n"}
    for path, text in files.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(text)
    assert sorted(read_tree(tmp_path)) == ["greg/a.py", "helpers/__init__.py", "helpers/b.py", "helpers/c.py",
                                           "tools/offline_tool.py"]
    assert _sites(read_tree(tmp_path)) == {("helpers/b.py", "go", "subprocess.run"): 1,
                                           ("tools/offline_tool.py", "spawn", "os.system"): 1}


def test_sys_path_roots_are_module_roots():
    """Every repository directory the scanned code puts on sys.path is a MODULE_ROOT, so ``read_tree`` finds what
    ``import offline_test`` (greg.capabilities, foundry.systems.segmentation) really loads."""
    roots = set()
    for path, source in read_tree().items():
        for node in ast.walk(ast.parse(source, filename=path)):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("insert", "append") and ast.unparse(node.func.value) == "sys.path"):
                roots |= {literal.value for argument in node.args for literal in ast.walk(argument)
                          if isinstance(literal, ast.Constant) and isinstance(literal.value, str)
                          and not literal.value.startswith("/") and (ROOT / literal.value).is_dir()}
    assert "tools" in roots and roots <= set(MODULE_ROOTS)


# -- the tree against its allowlist --------------------------------------------------------------------------

def test_allowlist_is_well_formed():
    from greg.capabilities import BUILTINS
    assert malformed(load_allowlist(), BUILTINS) == []


def test_every_effect_call_site_is_listed():
    document = load_allowlist()
    sources = read_tree()
    scan = scan_all(sources, wrapper_table(document))
    problems = (wrapper_problems(document, scan.found, sources) + compare(scan.found, document)
                + pin_problems(document, sources, scan) + finding_problems(document, scan.found)
                + lookup_problems(scan.lookups, document) + envelope_problems(document, scan.lookups))
    assert not problems, "\n\n".join(problems)
