"""Whole-machine acceptance harness: Missions A-L and the full-machine completion contract.

Directive 2026-10-13, sections 33 and 35 (docs/intent/sources/OPUS-MAXIMUS-MASTER-EXECUTION-DIRECTIVE-
2026-10-13-source.md). ``missions.json`` maps every obligation of Missions A-L to the executable tests that
demonstrate it and the evidence tier those tests can establish; ``completion-contract.json`` records, for
each required function of Body, Mind, Organs and the operating loop, its owner, interface, status and the
mission requirements that carry its evidence.

The harness reports only what the tests establish. It never infers a higher status from a lower one:

- a requirement attains its declared tier only when every cited test node was collected and passed; a
  failure, an error, a skip or a node that collects nothing leaves it unverified, with the observed reason;
- a tier says how strongly the cited tests ran, coverage says how much of the obligation they show. A
  requirement whose coverage is 'gap' never attains anything and may not declare a tier; one whose coverage
  is 'partial' can attain its tier, and the report says it covers only part of its obligation. A requirement
  covers its whole obligation only when it attained its declared tier and is declared 'covered'; a mission or
  a contract function covers its whole obligation only when every requirement (and trace link) it rests on
  does;
- every tested requirement records what its cited tests did, a 'gap' one included, and a cited test that
  failed, errored or collected nothing fails the run whether or not its requirement declares a tier;
- BODY_VERIFIED needs at least one cited node that drives a real Body process: a test in a file registered
  under ``body_process_tests`` in which an argv starting ``greg run``, supervisord running
  service.supervisord_program, or a driver script running Body.run statically reaches a process-spawning call.
  An in-process Body is SANDBOX_VERIFIED at most;
- a requirement without tests keeps its declared unverified status (INTENDED .. INTEGRATED) or is
  BLOCKED_WITH_REASON with its reason;
- tests can establish at most BODY_VERIFIED. FOUNDER_ACCEPTED and every status above it need a record that
  no test can produce (Alfonso's signed acceptance, a live authorization, an external observation, a
  commercial outcome), so the manifest refuses to declare them and the harness never assigns them;
- a mission or a contract function is only as verified as its least-verified requirement;
- each Mission L trace link is computed from its own proof run by the same rule as a requirement; a link
  whose proof falls short is reported short and fails the run like a requirement, and Mission L, and every
  contract function citing it, is only as verified as its least-verified requirement or trace link.

The harness holds no authority: it reads code and runs tests. It grants, attaches and activates nothing.
"""
from __future__ import annotations

import ast
from collections import ChainMap
import json
from pathlib import Path
import re
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "missions.json"
CONTRACT = HERE / "completion-contract.json"

# Directive section 35, in order. BLOCKED_WITH_REASON is not a rung: it says why a rung cannot be reached.
STATUSES = ("INTENDED", "DESIGNED", "IMPLEMENTED", "INTEGRATED", "UNIT_VERIFIED", "SANDBOX_VERIFIED",
            "BODY_VERIFIED", "FOUNDER_ACCEPTED", "AUTHORIZED_LIVE", "EXTERNALLY_VERIFIED",
            "COMMERCIAL_OUTCOME_VERIFIED", "BLOCKED_WITH_REASON")
LADDER = STATUSES[:-1]
BLOCKED = "BLOCKED_WITH_REASON"
UNVERIFIED = ("INTENDED", "DESIGNED", "IMPLEMENTED", "INTEGRATED")
TEST_TIERS = ("UNIT_VERIFIED", "SANDBOX_VERIFIED", "BODY_VERIFIED")
BEYOND_TESTS = ("FOUNDER_ACCEPTED", "AUTHORIZED_LIVE", "EXTERNALLY_VERIFIED", "COMMERCIAL_OUTCOME_VERIFIED")
MISSIONS = tuple("ABCDEFGHIJKL")
DEPENDENCIES = ("none", "founder", "credential", "external", "technical", "legal", "physical")
TRACE_LINKS = ("Goal", "Mind", "Organs", "Body", "Action", "Evidence", "Outcome", "Learning", "Updated Goal")
COVERAGE = ("covered", "partial", "gap")
# How a registered test starts a real Body process (missions.json ``body_process_tests``).
PROCESS_KINDS = ("greg run", "supervisord", "Body.run driver")
# A trace link whose proof falls short still names code that exists (checked statically): IMPLEMENTED.
LINK_FLOOR = "IMPLEMENTED"


def rank(status: str) -> int:
    return LADDER.index(status)


def lowest(statuses) -> str:
    """The least-verified status: BLOCKED_WITH_REASON dominates, then the lowest rung."""
    statuses = list(statuses)
    if not statuses:
        return "INTENDED"
    if BLOCKED in statuses:
        return BLOCKED
    return min(statuses, key=rank)


def load(path: Path = MANIFEST) -> dict:
    return json.loads(Path(path).read_text())


# -- static resolution of cited test nodes ------------------------------------------------------------

_PARAMS = re.compile(r"\[.*\]$")


def node_problem(node: str, root: Path = ROOT) -> str | None:
    """Why ``node`` cannot name a test in this tree, or None. Static: file and symbols, no import."""
    path, _, rest = node.partition("::")
    file = root / path
    if not path.startswith("tests/") or not path.endswith(".py") or not file.is_file():
        return f"{node}: no such test file"
    tree = ast.parse(file.read_text())
    scope = tree.body
    for part in [p for p in rest.split("::") if p] if rest else []:
        name = _PARAMS.sub("", part)
        found = next((n for n in scope if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                      and n.name == name), None)
        if found is None:
            return f"{node}: {name} is not defined in {path}"
        scope = found.body if isinstance(found, ast.ClassDef) else []
    return None


def minimal_nodes(nodes) -> list[str]:
    """Distinct nodes, dropping any node already covered by a cited file or parent node."""
    nodes = sorted(set(nodes))
    return [n for n in nodes if not any(other != n and covers(other, n) for other in nodes)]


def covers(cited: str, nodeid: str) -> bool:
    """Does a run of ``cited`` include the collected item ``nodeid``?"""
    return nodeid == cited or nodeid.startswith(cited + "::") or (
        "[" not in cited and "::" in cited and nodeid.startswith(cited + "["))


# -- statuses from outcomes ---------------------------------------------------------------------------

def shortfalls(nodes, outcomes: dict) -> list[str]:
    """Why a run of ``nodes`` does not establish anything: every node must collect, and every item pass."""
    observed = []
    for node in nodes:
        items = {k: v for k, v in outcomes.items() if covers(node, k)}
        if not items:
            observed.append(f"{node}: collected nothing")
        for nodeid, result in sorted(items.items()):
            if result["outcome"] != "passed":
                observed.append(f"{nodeid}: {result['outcome']}: {result.get('reason', '')}"[:500])
    return observed


def failing(nodes, outcomes: dict) -> list[str]:
    """The cited tests a run shows broken: an item that failed or errored, or a node that collected nothing.
    A skip shows nothing, but it is not a failure."""
    broken = []
    for node in nodes:
        items = {k: v for k, v in outcomes.items() if covers(node, k)}
        if not items:
            broken.append(node)
        broken += sorted(k for k, v in items.items() if v["outcome"] in ("failed", "error"))
    return broken


def requirement_status(req: dict, outcomes: dict | None) -> dict:
    """What one requirement attained in a run. ``outcomes`` maps collected nodeid -> {outcome, reason}.

    With ``outcomes`` None (no run), a tested requirement is reported at its declared implementation
    status only: a declaration is never evidence. Coverage 'gap' (the cited tests do not show the obligation
    at any tier) never attains, whatever the tests do; a missing coverage is read as 'gap'. Every tested
    requirement, a 'gap' one included, records what its cited tests did, and ``failing`` names the cited tests
    that failed, errored or collected nothing. A requirement covers its whole obligation only when it attained
    its declared tier and its coverage is 'covered'."""
    tests = req.get("tests", [])
    coverage = req.get("coverage", "gap")
    if not tests:
        return {"status": req.get("status", "INTENDED"), "declared_tier": None, "attained": False,
                "coverage": coverage, "whole_obligation": False, "failing": [],
                "observed": [req.get("blocked_reason", "no executable test cites this requirement")]}
    floor = req.get("implementation", "IMPLEMENTED")
    observed = ["not run"] if outcomes is None else shortfalls(tests, outcomes)
    broken = [] if outcomes is None else failing(tests, outcomes)
    if coverage not in ("covered", "partial"):
        return {"status": floor, "declared_tier": None, "attained": False, "coverage": coverage,
                "whole_obligation": False, "failing": broken,
                "observed": [f"coverage is {coverage!r}: the cited tests do not establish this obligation "
                             "at any tier"] + observed}
    attained = not observed
    return {"status": req["tier"] if attained else floor, "declared_tier": req["tier"], "attained": attained,
            "coverage": coverage, "whole_obligation": attained and coverage == "covered", "failing": broken,
            "observed": observed}


def link_status(link: dict, outcomes: dict | None) -> dict:
    """What one Mission L trace link attained: its declared tier only when every proof node passed (the
    requirement rule); otherwise LINK_FLOOR, because its code paths exist but nothing verified them."""
    observed = ["not run"] if outcomes is None else shortfalls(link["proof"], outcomes)
    attained = not observed
    return {"link": link["link"], "owner": link["owner"], "status": link["tier"] if attained else LINK_FLOOR,
            "declared_tier": link["tier"], "attained": attained, "observed": observed}


def _coverage(results, links=()) -> str:
    """'covered' only when every contributing requirement covers its whole obligation (it attained its declared
    tier and is declared covered) and every contributing trace link attained its tier."""
    results = list(results)
    whole = results and all(r["whole_obligation"] for r in results) and all(x["attained"] for x in links)
    return "covered" if whole else "partial"


def mission_status(mission: dict, outcomes: dict | None) -> dict:
    """A mission is only as verified as its least-verified requirement and, for Mission L, trace link."""
    reqs = {r["id"]: requirement_status(r, outcomes) for r in mission["requirements"]}
    links = [link_status(link, outcomes) for link in mission.get("trace", [])]
    open_gaps = [g for g in mission.get("gaps", []) if g["state"] == "OPEN"]
    out = {"id": mission["id"], "title": mission["title"],
           "status": lowest([r["status"] for r in reqs.values()] + [x["status"] for x in links]),
           "coverage": _coverage(reqs.values(), links), "requirements": reqs, "open_gaps": len(open_gaps),
           "blocked_beyond_tests": sorted({g["id"] for g in open_gaps if g["dependency"] != "none"
                                           and not g.get("buildable_now")})}
    if mission.get("trace"):
        out["trace"] = links
    return out


def contract_status(function: dict, missions: dict) -> dict:
    """A contract function's evidence tier is computed from the mission requirements it cites, never
    declared: the least-verified of them and of the trace links of any cited mission that carries a trace
    (Mission L), and never above what its own implementation status allows. Its coverage is 'partial' unless
    every cited requirement covers its whole obligation and every such link attained its tier."""
    reached, cited = [], []
    for ref in function["evidence"]:
        mid, _, rid = ref.partition(".")
        reached.append(missions[mid]["requirements"][rid])
        if mid not in cited:
            cited.append(mid)
    links = [x for mid in cited for x in missions[mid].get("trace", [])]
    tier = (lowest([r["status"] for r in reached] + [x["status"] for x in links]) if reached
            else function["implementation"])
    if tier != BLOCKED and function["implementation"] in UNVERIFIED and rank(function["implementation"]) < rank(
            "IMPLEMENTED"):
        tier = function["implementation"]           # designed-only functions cannot be verified by tests
    return {"id": function["id"], "evidence_tier": tier, "coverage": _coverage(reached, links),
            "evidence": function["evidence"]}


def report(manifest: dict, contract: dict, outcomes: dict | None, meta: dict) -> dict:
    missions = {m["id"]: mission_status(m, outcomes) for m in manifest["missions"]}
    functions = [contract_status(f, missions) for f in contract["functions"]]
    reqs = [r for m in missions.values() for r in m["requirements"].values()]
    links = [link for m in missions.values() for link in m.get("trace", [])]
    attained = [r for r in reqs if r["attained"]]
    return {"version": "acceptance-report/3", **meta, "ran": outcomes is not None,
            "summary": {"requirements": len(reqs), "attained_declared_tier": len(attained),
                        "attained_whole_obligation": sum(r["whole_obligation"] for r in attained),
                        "attained_part_obligation": sum(not r["whole_obligation"] for r in attained),
                        "requirements_citing_failing_tests": sum(bool(r["failing"]) for r in reqs),
                        "declared_coverage": {c: sum(r["coverage"] == c for r in reqs) for c in COVERAGE},
                        "missions": {k: {"status": v["status"], "coverage": v["coverage"]}
                                     for k, v in missions.items()},
                        "trace_links": len(links), "trace_links_attained": sum(x["attained"] for x in links),
                        "contract_functions": len(functions),
                        "contract_functions_whole_obligation": sum(f["coverage"] == "covered" for f in functions),
                        "highest_status_any_test_can_establish": TEST_TIERS[-1],
                        "statuses_no_test_can_establish": list(BEYOND_TESTS)},
            "missions": missions, "contract": functions}


def shortfall_names(rep: dict) -> list[str]:
    """Everything that fails a run: every tested requirement and trace link that did not attain its declared
    tier, and every requirement, whether or not it declares a tier, citing a test that failed, errored or
    collected nothing."""
    short = [f"{mid}.{rid}" for mid, m in rep["missions"].items() for rid, r in m["requirements"].items()
             if (r.get("declared_tier") and not r["attained"]) or r.get("failing")]
    short += [f"{mid}.trace.{link['link']}" for mid, m in rep["missions"].items() for link in m.get("trace", [])
              if not link["attained"]]
    return short


# -- real Body processes (static) ----------------------------------------------------------------------
#
# A test drives a real Body process only when an argv that starts one reaches a call that spawns a process.
# The reader below follows values through the test function, the same-module functions it calls and the
# same-module fixtures it requests (names, list and tuple displays and their concatenation, starred
# arguments, ``+``, f-strings, ``str()``, a file written with ``write_text``), and it looks at an argv only
# where a spawning call receives it. It never evaluates a condition other than a constant, never follows a
# lambda, a method or a function from another module, and drops everything when the test patches the
# spawning calls, so whatever it cannot see counts as in-process.

_BODY_RUN = re.compile(r"\w*Body\([^()]*\)\.run\(")
SPAWNERS = frozenset({"subprocess.Popen", "subprocess.run", "subprocess.call", "subprocess.check_call",
                      "subprocess.check_output", "asyncio.create_subprocess_exec"})
_PROGRAM = "greg.service.supervisord_program"          # writes a supervisord program that runs `greg run`
_PASS_THROUGH = frozenset({"str", "os.fspath", "pathlib.Path"})
_PATCHERS = frozenset({"setattr", "patch", "object"})  # monkeypatch.setattr, setattr, mock.patch(.object)
_FOLLOW_BUDGET = 5000                                  # calls followed per test; past it, nothing more is seen


class _Value(NamedTuple):
    """What the reader knows about one value. ``facts``: 'driver' (is, or names a file holding, a script that
    calls ``Body(...).run(``) and 'program' (is, or names a file holding, service.supervisord_program output)."""
    const: object = None                     # a constant; sys.executable reads as 'python'
    items: tuple | None = None               # a list or tuple display: ((starred, _Value), ...)
    facts: frozenset = frozenset()
    qual: str | None = None                  # a module or module attribute, by dotted name
    func: tuple | None = None                # (FunctionDef, the scope it closes over): a function of this module


_NOTHING = _Value()


def _facts(values) -> frozenset:
    return frozenset().union(*(v.facts for v in values))


def _flatten(items) -> tuple[list, bool]:
    """The elements of a display or an argument list with starred parts expanded, and whether that is all of
    them (False once a starred part is unknown: nothing from there on is known)."""
    out = []
    for starred, value in items:
        if not starred:
            out.append(value)
            continue
        if value.items is None:
            return out, False
        inner, complete = _flatten(value.items)
        out += inner
        if not complete:
            return out, False
    return out, True


def _argv_kind(argv: _Value) -> str | None:
    """Which real Body process an argv starts: ``python -m greg [--home H] run``; supervisord whose -c
    configuration file holds service.supervisord_program; or python running a driver script that calls
    ``Body(...).run(`` (as a file, or with -c). Anything else, or anything not known, is None."""
    if argv.items is None:
        return None
    args, _ = _flatten(argv.items)
    const = [a.const if isinstance(a.const, str) else None for a in args]
    program = Path(const[0]).name if const and const[0] else ""
    if program == "supervisord":
        configured = any(c in ("-c", "--configuration") and i + 1 < len(args) and "program" in args[i + 1].facts
                         for i, c in enumerate(const))
        return "supervisord" if configured else None
    if not program.startswith("python"):
        return None
    if const[1:3] == ["-m", "greg"]:
        i = 3
        while i < len(const) and const[i] is not None and const[i].startswith("-"):
            i += 1 if "=" in const[i] else 2           # greg's one global option, --home, takes a value
        return "greg run" if i < len(const) and const[i] == "run" else None
    script = 2 if const[1:2] == ["-c"] else 1
    return "Body.run driver" if script < len(args) and "driver" in args[script].facts else None


def _is_fixture(fn) -> bool:
    for d in fn.decorator_list:
        d = d.func if isinstance(d, ast.Call) else d
        if (d.attr if isinstance(d, ast.Attribute) else getattr(d, "id", None)) == "fixture":
            return True
    return False


def _tree(root: Path, path: str, cache: dict):
    key = ("tree", path)
    if key not in cache:
        file = root / path
        cache[key] = ast.parse(file.read_text()) if file.is_file() else None
    return cache[key]


class _Reader:
    """Reads one test, and the code it reaches, for the real Body processes it spawns."""

    def __init__(self, root: Path, cache: dict):
        self.root, self.cache = root, cache
        self.kinds: set[str] = set()
        self.patched = False
        self.live = True                        # False while reading a module's top level: nothing runs there
        self.stack: list = []
        self.returns: list[list] = []
        self.followed = 0

    def module(self, path: str) -> dict:
        """What a module binds at top level: its imports, constants and functions."""
        key = ("env", path)
        if key not in self.cache:
            env = self.cache[key] = {}
            tree = _tree(self.root, path, self.cache)
            live, self.live = self.live, False
            try:
                for s in tree.body if tree is not None else []:
                    if isinstance(s, (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign, ast.FunctionDef,
                                      ast.AsyncFunctionDef)):
                        self.stmt(s, env)
            finally:
                self.live = live
        return self.cache[key]

    def imported(self, module: str | None, name: str) -> _Value:
        if not module:
            return _NOTHING
        path = module.replace(".", "/") + ".py"
        if module.startswith("tests.") and (self.root / path).is_file():
            value = self.module(path).get(name, _NOTHING)
            return _NOTHING if value.func else value          # another module's function is not followed
        return _Value(qual=f"{module}.{name}")

    # statements

    def block(self, stmts, env) -> None:
        for s in stmts:
            self.stmt(s, env)

    def stmt(self, s, env) -> None:
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
            env[s.name] = _Value(func=(s, env))                # followed only when called
        elif isinstance(s, ast.Import):
            for a in s.names:
                top = a.name.split(".")[0]
                env[a.asname or top] = _Value(qual=a.name if a.asname else top)
        elif isinstance(s, ast.ImportFrom):
            for a in s.names:
                env[a.asname or a.name] = self.imported(s.module if not s.level else None, a.name)
        elif isinstance(s, ast.Assign):
            value = self.expr(s.value, env)
            for target in s.targets:
                self.bind(target, value, env)
        elif isinstance(s, ast.AnnAssign) and s.value is not None:
            self.bind(s.target, self.expr(s.value, env), env)
        elif isinstance(s, ast.AugAssign):
            self.bind(s.target, self.binop(s.op, self.expr(s.target, env), self.expr(s.value, env)), env)
        elif isinstance(s, ast.Expr):
            self.expr(s.value, env)
        elif isinstance(s, ast.Return):
            value = self.expr(s.value, env) if s.value is not None else _NOTHING
            if self.returns:
                self.returns[-1].append(value)
        elif isinstance(s, (ast.If, ast.While)):
            self.expr(s.test, env)
            constant = isinstance(s.test, ast.Constant)
            if not (constant and not s.test.value):
                self.block(s.body, env)
            if not (constant and s.test.value and isinstance(s, ast.If)):
                self.block(s.orelse, env)
        elif isinstance(s, (ast.For, ast.AsyncFor)):
            self.expr(s.iter, env)
            self.bind(s.target, _NOTHING, env)
            self.block(s.body, env)
            self.block(s.orelse, env)
        elif isinstance(s, (ast.With, ast.AsyncWith)):
            for item in s.items:
                self.expr(item.context_expr, env)
                if item.optional_vars is not None:
                    self.bind(item.optional_vars, _NOTHING, env)
            self.block(s.body, env)
        elif isinstance(s, (ast.Try, getattr(ast, "TryStar", ast.Try))):
            self.block(s.body, env)
            for handler in s.handlers:
                if handler.name:
                    env[handler.name] = _NOTHING
                self.block(handler.body, env)
            self.block(s.orelse, env)
            self.block(s.finalbody, env)
        elif isinstance(s, ast.Assert):
            self.expr(s.test, env)                             # the message runs only on failure
        elif isinstance(s, ast.Raise) and s.exc is not None:
            self.expr(s.exc, env)
        # a class body, del, pass, break, continue, global, nonlocal, match: nothing here is followed

    def bind(self, target, value: _Value, env) -> None:
        if isinstance(target, ast.Name):
            env[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            items = value.items
            pairwise = (items is not None and len(items) == len(target.elts) and not any(s for s, _ in items)
                        and not any(isinstance(e, ast.Starred) for e in target.elts))
            for i, elt in enumerate(target.elts):
                self.bind(elt.value if isinstance(elt, ast.Starred) else elt, items[i][1] if pairwise else _NOTHING,
                          env)
        elif isinstance(target, (ast.Attribute, ast.Subscript)):
            self.expr(target.value, env)

    # expressions

    def expr(self, node, env) -> _Value:
        if node is None:
            return _NOTHING
        if isinstance(node, ast.Constant):
            driver = isinstance(node.value, str) and _BODY_RUN.search(node.value)
            return _Value(const=node.value, facts=frozenset({"driver"}) if driver else frozenset())
        if isinstance(node, ast.Name):
            return env[node.id] if node.id in env else _Value(qual=node.id)   # a builtin, or never bound
        if isinstance(node, ast.Attribute):
            base = self.expr(node.value, env)
            if not base.qual:
                return _NOTHING
            qual = f"{base.qual}.{node.attr}"
            return _Value(const="python") if qual == "sys.executable" else _Value(qual=qual)
        if isinstance(node, ast.Call):
            return self.call(node, env)
        if isinstance(node, (ast.List, ast.Tuple)):
            return _Value(items=tuple((isinstance(e, ast.Starred),
                                       self.expr(e.value if isinstance(e, ast.Starred) else e, env))
                                      for e in node.elts))
        if isinstance(node, ast.BinOp):
            return self.binop(node.op, self.expr(node.left, env), self.expr(node.right, env))
        if isinstance(node, ast.JoinedStr):
            return _Value(facts=_facts([self.expr(v, env) for v in node.values]))
        if isinstance(node, ast.FormattedValue):
            self.expr(node.format_spec, env)
            return _Value(facts=self.expr(node.value, env).facts)
        if isinstance(node, ast.IfExp):
            self.expr(node.test, env)
            return _Value(facts=_facts([self.expr(node.body, env), self.expr(node.orelse, env)]))
        if isinstance(node, ast.NamedExpr):
            value = self.expr(node.value, env)
            self.bind(node.target, value, env)
            return value
        if isinstance(node, ast.Await):
            return self.expr(node.value, env)
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            value = self.expr(node.value, env)
            if self.returns:
                self.returns[-1].append(value)
            return _NOTHING
        if isinstance(node, ast.Lambda):
            return _NOTHING                                    # never followed
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            inner = ChainMap({}, env)
            for gen in node.generators:
                self.expr(gen.iter, inner)
                self.bind(gen.target, _NOTHING, inner)
                for cond in gen.ifs:
                    self.expr(cond, inner)
            for part in (node.key, node.value) if isinstance(node, ast.DictComp) else (node.elt,):
                self.expr(part, inner)
            return _NOTHING
        for child in ast.iter_child_nodes(node):               # anything else: read it for the calls it makes
            if isinstance(child, ast.expr):
                self.expr(child, env)
        return _NOTHING

    @staticmethod
    def binop(op, left: _Value, right: _Value) -> _Value:
        facts = left.facts | right.facts
        if isinstance(op, ast.Add):
            if left.items is not None and right.items is not None:
                return _Value(items=left.items + right.items, facts=facts)
            if isinstance(left.const, str) and isinstance(right.const, str):
                return _Value(const=left.const + right.const, facts=facts)
        return _Value(facts=facts)

    def call(self, node, env) -> _Value:
        callee = self.expr(node.func, env)
        pos = tuple((isinstance(a, ast.Starred), self.expr(a.value if isinstance(a, ast.Starred) else a, env))
                    for a in node.args)
        kwargs = {k.arg: self.expr(k.value, env) for k in node.keywords if k.arg}
        for k in node.keywords:
            if not k.arg:
                self.expr(k.value, env)
        first = pos[0][1] if pos and not pos[0][0] else _NOTHING
        if callee.func is not None:
            return self.follow(callee.func, pos, kwargs)
        if callee.qual in SPAWNERS:
            if self.live:
                argv = _Value(items=pos) if callee.qual == "asyncio.create_subprocess_exec" else (
                    first if pos and not pos[0][0] else kwargs.get("args", _NOTHING))
                kind = _argv_kind(argv)
                if kind:
                    self.kinds.add(kind)
            return _NOTHING
        if callee.qual == _PROGRAM:
            return _Value(facts=frozenset({"program"}))
        if callee.qual == "shutil.which":
            return _Value(const=first.const if isinstance(first.const, str) else None)
        if callee.qual in _PASS_THROUGH:
            return _Value(const=first.const if isinstance(first.const, str) else None, facts=first.facts)
        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
        if name in _PATCHERS and (first.qual in ("subprocess", "asyncio") or first.qual in SPAWNERS or (
                isinstance(first.const, str) and first.const.split(".")[0] in ("subprocess", "asyncio"))):
            self.patched = True
        if name in ("write_text", "write_bytes") and isinstance(node.func, ast.Attribute) and isinstance(
                node.func.value, ast.Name) and pos:
            held = env[node.func.value.id] if node.func.value.id in env else _NOTHING
            env[node.func.value.id] = held._replace(facts=first.facts)     # the file now holds what was written
        return _NOTHING

    def follow(self, func: tuple, pos: tuple = (), kwargs: dict | None = None, fixtures: bool = False) -> _Value:
        """Read a call to a function of this module (or a fixture pytest calls) and return what it returns."""
        fn, scope = func
        if not self.live or fn in self.stack or self.followed >= _FOLLOW_BUDGET:
            return _NOTHING
        self.followed += 1
        for decorator in fn.decorator_list:
            self.expr(decorator, scope)
        env = ChainMap({}, scope)
        kwargs = dict(kwargs or {})
        values, complete = _flatten(pos)
        a = fn.args
        positional = a.posonlyargs + a.args
        defaults = dict(zip([p.arg for p in positional][len(positional) - len(a.defaults):], a.defaults))
        defaults.update({p.arg: d for p, d in zip(a.kwonlyargs, a.kw_defaults) if d is not None})
        for i, p in enumerate(positional + a.kwonlyargs):
            if i < len(positional) and i < len(values):
                env[p.arg] = values[i]
            elif p.arg in kwargs:
                env[p.arg] = kwargs.pop(p.arg)
            elif not complete and i < len(positional):
                env[p.arg] = _NOTHING                          # an unknown starred argument may fill it
            elif p.arg in defaults:
                env[p.arg] = self.expr(defaults[p.arg], scope)
            elif fixtures and p.arg in scope and scope[p.arg].func and _is_fixture(scope[p.arg].func[0]):
                env[p.arg] = self.follow(scope[p.arg].func, fixtures=True)
            else:
                env[p.arg] = _NOTHING
        if a.vararg:
            extra = values[len(positional):]
            env[a.vararg.arg] = _Value(items=tuple((False, v) for v in extra)) if complete else _NOTHING
        if a.kwarg:
            env[a.kwarg.arg] = _NOTHING
        self.stack.append(fn)
        self.returns.append([])
        try:
            self.block(fn.body, env)
        finally:
            self.stack.pop()
            returned = self.returns.pop()
        return returned[0] if len(returned) == 1 else _Value(facts=_facts(returned))


def _process_kinds(fn, path: str, root: Path, cache: dict) -> set[str]:
    """How the test function ``fn`` (in ``path``) starts a real Body process: the kinds of argv that reach a
    spawning call in it, its same-module helpers and its same-module fixtures. Empty when it patches them."""
    key = ("kinds", path, fn.lineno, fn.name)
    if key not in cache:
        reader = _Reader(root, cache)
        reader.follow((fn, reader.module(path)), fixtures=True)
        cache[key] = set() if reader.patched else set(reader.kinds)
    return cache[key]


def node_process_kinds(node: str, root: Path = ROOT, _cache: dict | None = None) -> set[str]:
    """The ways the tests a cited node selects start a real Body process (empty: in-process only)."""
    path, _, rest = node.partition("::")
    cache = {} if _cache is None else _cache
    tree = _tree(root, path, cache)
    if tree is None:
        return set()
    target = tree
    for part in [_PARAMS.sub("", p) for p in rest.split("::") if p] if rest else []:
        target = next((n for n in getattr(target, "body", []) if getattr(n, "name", None) == part), None)
        if target is None:
            return set()
    if isinstance(target, (ast.FunctionDef, ast.AsyncFunctionDef)):
        tests = [target]
    else:                                   # a module or a class: the tests pytest collects from it
        scopes = [target] + [n for n in target.body if isinstance(n, ast.ClassDef) and n.name.startswith("Test")]
        tests = [n for s in scopes for n in s.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test")]
    kinds = set()
    for fn in tests:
        kinds |= _process_kinds(fn, path, root, cache)
    return kinds


def real_process_nodes(nodes, registry: dict, root: Path = ROOT, _cache: dict | None = None) -> list[str]:
    """The cited nodes that drive a real Body process: in a registered file, and statically starting one."""
    return [n for n in nodes if n.partition("::")[0] in registry and node_process_kinds(n, root, _cache)]


# -- validation -----------------------------------------------------------------------------------------

def _schema_problems(document: dict, schema_name: str) -> list[str]:
    import jsonschema
    schema = json.loads((HERE / schema_name).read_text())
    validator = jsonschema.Draft202012Validator(schema)
    return [f"{schema_name}: {'/'.join(map(str, e.absolute_path))}: {e.message}"[:400]
            for e in validator.iter_errors(document)]


def problems(manifest: dict, contract: dict | None = None, root: Path = ROOT) -> list[str]:
    """Everything that makes the manifest or contract unsound. Empty means sound (not verified)."""
    out = _schema_problems(manifest, "missions.schema.json")
    if out:
        return out
    ids = [m["id"] for m in manifest["missions"]]
    if tuple(ids) != MISSIONS:
        out.append(f"missions must be exactly {''.join(MISSIONS)} in order, got {''.join(ids)}")
    cache: dict = {}
    registry = {}
    for entry in manifest["body_process_tests"]:
        where = f"body_process_tests {entry['file']}"
        if entry["file"] in registry:
            out.append(f"{where}: registered twice")
        registry[entry["file"]] = entry["starts"]
        problem = node_problem(entry["file"], root)
        if problem:
            out.append(f"{where}: {problem}")
        elif entry["starts"] not in node_process_kinds(entry["file"], root, cache):
            out.append(f"{where}: no test in it statically starts a {entry['starts']} Body process")

    def body_tier_problem(where: str, nodes) -> None:
        if not real_process_nodes(nodes, registry, root, cache):
            out.append(f"{where}: BODY_VERIFIED needs a cited node that drives a real Body process (a test in a "
                       f"body_process_tests file that starts one); every cited node runs in-process")

    for m in manifest["missions"]:
        seen = set()
        for r in m["requirements"]:
            where = f"{m['id']}.{r['id']}"
            if r["id"] in seen:
                out.append(f"{where}: duplicate requirement id")
            seen.add(r["id"])
            if r.get("tests"):
                if r["coverage"] == "gap":
                    if "tier" in r:
                        out.append(f"{where}: coverage 'gap' cannot claim a tier ({r['tier']}): its tests do not "
                                   f"establish the obligation, so it can never attain one")
                elif r.get("tier") not in TEST_TIERS:
                    out.append(f"{where}: a tested requirement declares a tier tests can establish "
                               f"({', '.join(TEST_TIERS)}), not {r.get('tier')}")
                elif r["tier"] == "BODY_VERIFIED":
                    body_tier_problem(where, r["tests"])
                for node in r["tests"]:
                    problem = node_problem(node, root)
                    if problem:
                        out.append(f"{where}: {problem}")
            else:
                if r.get("status") not in UNVERIFIED + (BLOCKED,):
                    out.append(f"{where}: an untested requirement cannot claim {r.get('status')}")
                if r.get("status") == BLOCKED and not r.get("blocked_reason"):
                    out.append(f"{where}: BLOCKED_WITH_REASON needs its reason")
        gap_ids = [g["id"] for g in m.get("gaps", [])]
        if len(set(gap_ids)) != len(gap_ids):
            out.append(f"{m['id']}: duplicate gap id")
        for g in m.get("gaps", []):
            if g["state"] == "CLOSED" and not g.get("closed_by"):
                out.append(f"{m['id']}.{g['id']}: a closed gap names what closed it")
            if g["state"] == "OPEN" and not g.get("buildable_now") and g["dependency"] == "none":
                out.append(f"{m['id']}.{g['id']}: an open gap that cannot be built now names its dependency")
    trace = next((m for m in manifest["missions"] if m["id"] == "L"), {}).get("trace", [])
    if [link["link"] for link in trace] != list(TRACE_LINKS):
        out.append(f"L.trace must name the links {' -> '.join(TRACE_LINKS)} in order")
    for link in trace:
        for path in link["code"]:
            file, _, symbol = path.partition("::")
            if not (root / file).is_file():
                out.append(f"L.trace {link['link']}: no such file {file}")
            elif symbol and not re.search(rf"^\s*(def|class)\s+{re.escape(symbol)}\b|^{re.escape(symbol)}\s*=",
                                          (root / file).read_text(), re.M):
                out.append(f"L.trace {link['link']}: {symbol} is not defined in {file}")
        for node in link["proof"]:
            problem = node_problem(node, root)
            if problem:
                out.append(f"L.trace {link['link']}: {problem}")
        if link["tier"] == "BODY_VERIFIED":
            body_tier_problem(f"L.trace {link['link']}", link["proof"])
    if contract is not None:
        out += _schema_problems(contract, "contract.schema.json")
        reqs = {(m["id"], r["id"]) for m in manifest["missions"] for r in m["requirements"]}
        for f in contract.get("functions", []):
            for ref in f.get("evidence", []):
                mid, _, rid = ref.partition(".")
                if (mid, rid) not in reqs:
                    out.append(f"contract {f['id']}: evidence {ref} names no mission requirement")
            for path in f.get("owner_paths", []):
                if not (root / path).exists():
                    out.append(f"contract {f['id']}: owner path {path} does not exist")
    return out
