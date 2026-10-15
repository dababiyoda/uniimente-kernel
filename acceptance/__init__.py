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
  is 'partial' can attain its tier, and the report says it covers only part of its obligation. A mission or
  a contract function covers its whole obligation only when every requirement it rests on does;
- BODY_VERIFIED needs at least one cited node that drives a real Body process: a test in a file registered
  under ``body_process_tests`` whose code statically starts ``greg run`` (directly or under supervisord) or a
  driver subprocess running Body.run. An in-process Body is SANDBOX_VERIFIED at most;
- a requirement without tests keeps its declared unverified status (INTENDED .. INTEGRATED) or is
  BLOCKED_WITH_REASON with its reason;
- tests can establish at most BODY_VERIFIED. FOUNDER_ACCEPTED and every status above it need a record that
  no test can produce (Alfonso's signed acceptance, a live authorization, an external observation, a
  commercial outcome), so the manifest refuses to declare them and the harness never assigns them;
- a mission or a contract function is only as verified as its least-verified requirement;
- each Mission L trace link is computed from its own proof run by the same rule as a requirement; a link
  whose proof falls short is reported short and fails the run like a requirement.

The harness holds no authority: it reads code and runs tests. It grants, attaches and activates nothing.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re

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


def requirement_status(req: dict, outcomes: dict | None) -> dict:
    """What one requirement attained in a run. ``outcomes`` maps collected nodeid -> {outcome, reason}.

    With ``outcomes`` None (no run), a tested requirement is reported at its declared implementation
    status only: a declaration is never evidence. Coverage 'gap' (the cited tests do not show the obligation
    at any tier) never attains, whatever the tests do; a missing coverage is read as 'gap'."""
    tests = req.get("tests", [])
    coverage = req.get("coverage", "gap")
    shape = {"coverage": coverage, "whole_obligation": coverage == "covered"}
    if not tests:
        status = req.get("status", "INTENDED")
        return {"status": status, "declared_tier": None, "attained": False, **shape,
                "observed": [req.get("blocked_reason", "no executable test cites this requirement")]}
    floor = req.get("implementation", "IMPLEMENTED")
    if coverage not in ("covered", "partial"):
        return {"status": floor, "declared_tier": None, "attained": False, **shape,
                "observed": [f"coverage is {coverage!r}: the cited tests do not establish this obligation "
                             "at any tier"]}
    if outcomes is None:
        return {"status": floor, "declared_tier": req["tier"], "attained": False, **shape, "observed": ["not run"]}
    observed = shortfalls(tests, outcomes)
    if observed:
        return {"status": floor, "declared_tier": req["tier"], "attained": False, **shape, "observed": observed}
    return {"status": req["tier"], "declared_tier": req["tier"], "attained": True, **shape, "observed": []}


def link_status(link: dict, outcomes: dict | None) -> dict:
    """What one Mission L trace link attained: its declared tier only when every proof node passed (the
    requirement rule); otherwise LINK_FLOOR, because its code paths exist but nothing verified them."""
    observed = ["not run"] if outcomes is None else shortfalls(link["proof"], outcomes)
    attained = not observed
    return {"link": link["link"], "owner": link["owner"], "status": link["tier"] if attained else LINK_FLOOR,
            "declared_tier": link["tier"], "attained": attained, "observed": observed}


def _coverage(results) -> str:
    """'covered' only when every contributing requirement covers its whole obligation."""
    results = list(results)
    return "covered" if results and all(r["whole_obligation"] for r in results) else "partial"


def mission_status(mission: dict, outcomes: dict | None) -> dict:
    reqs = {r["id"]: requirement_status(r, outcomes) for r in mission["requirements"]}
    open_gaps = [g for g in mission.get("gaps", []) if g["state"] == "OPEN"]
    out = {"id": mission["id"], "title": mission["title"], "status": lowest(r["status"] for r in reqs.values()),
           "coverage": _coverage(reqs.values()), "requirements": reqs, "open_gaps": len(open_gaps),
           "blocked_beyond_tests": sorted({g["id"] for g in open_gaps if g["dependency"] != "none"
                                           and not g.get("buildable_now")})}
    if mission.get("trace"):
        out["trace"] = [link_status(link, outcomes) for link in mission["trace"]]
    return out


def contract_status(function: dict, missions: dict) -> dict:
    """A contract function's evidence tier is computed from the mission requirements it cites, never
    declared: the least-verified of them, and never above what its own implementation status allows. Its
    coverage is 'partial' unless every cited requirement covers its whole obligation."""
    reached = []
    for ref in function["evidence"]:
        mid, _, rid = ref.partition(".")
        reached.append(missions[mid]["requirements"][rid])
    tier = lowest(r["status"] for r in reached) if reached else function["implementation"]
    if tier != BLOCKED and function["implementation"] in UNVERIFIED and rank(function["implementation"]) < rank(
            "IMPLEMENTED"):
        tier = function["implementation"]           # designed-only functions cannot be verified by tests
    return {"id": function["id"], "evidence_tier": tier, "coverage": _coverage(reached),
            "evidence": function["evidence"]}


def report(manifest: dict, contract: dict, outcomes: dict | None, meta: dict) -> dict:
    missions = {m["id"]: mission_status(m, outcomes) for m in manifest["missions"]}
    functions = [contract_status(f, missions) for f in contract["functions"]]
    reqs = [r for m in missions.values() for r in m["requirements"].values()]
    links = [link for m in missions.values() for link in m.get("trace", [])]
    attained = [r for r in reqs if r["attained"]]
    return {"version": "acceptance-report/2", **meta, "ran": outcomes is not None,
            "summary": {"requirements": len(reqs), "attained_declared_tier": len(attained),
                        "attained_whole_obligation": sum(r["whole_obligation"] for r in attained),
                        "attained_part_obligation": sum(not r["whole_obligation"] for r in attained),
                        "coverage": {c: sum(r["coverage"] == c for r in reqs) for c in COVERAGE},
                        "missions": {k: {"status": v["status"], "coverage": v["coverage"]}
                                     for k, v in missions.items()},
                        "trace_links": len(links), "trace_links_attained": sum(x["attained"] for x in links),
                        "contract_functions": len(functions),
                        "contract_functions_whole_obligation": sum(f["coverage"] == "covered" for f in functions),
                        "highest_status_any_test_can_establish": TEST_TIERS[-1],
                        "statuses_no_test_can_establish": list(BEYOND_TESTS)},
            "missions": missions, "contract": functions}


def shortfall_names(rep: dict) -> list[str]:
    """Every tested requirement and trace link that did not attain its declared tier in this report."""
    short = [f"{mid}.{rid}" for mid, m in rep["missions"].items() for rid, r in m["requirements"].items()
             if r.get("declared_tier") and not r["attained"]]
    short += [f"{mid}.trace.{link['link']}" for mid, m in rep["missions"].items() for link in m.get("trace", [])
              if not link["attained"]]
    return short


# -- real Body processes (static) ----------------------------------------------------------------------

_BODY_RUN = re.compile(r"\w*Body\([^()]*\)\.run\(")
_SUBPROCESS = {"Popen", "run", "call", "check_call", "check_output"}


def _const(node):
    return node.value if isinstance(node, ast.Constant) else None


def _greg_subcommand(node) -> str | None:
    """For a list/tuple display holding ``-m greg``: its subcommand, the first plain string after it (option
    flags and computed values such as ``str(home)`` are skipped), or '*' when a starred argument comes first."""
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    elts = node.elts
    for i in range(len(elts) - 1):
        if _const(elts[i]) == "-m" and _const(elts[i + 1]) == "greg":
            for item in elts[i + 2:]:
                if isinstance(item, ast.Starred):
                    return "*"
                value = _const(item)
                if isinstance(value, str) and not value.startswith("-"):
                    return value
            return None
    return None


def _process_kinds(fn, tree) -> set[str]:
    """How the test function ``fn`` starts a real Body process, following calls to and fixtures of functions
    defined in the same module: ``greg run`` in an argv, supervisord launched with a ``greg run`` program
    (service.supervisord_program), or a subprocess running a module-level driver script that calls
    ``Body(...).run(``. Static and conservative: anything it cannot see counts as in-process."""
    funcs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    drivers = {t.id for n in tree.body if isinstance(n, ast.Assign) and isinstance(_const(n.value), str)
               and _BODY_RUN.search(n.value.value) for t in n.targets if isinstance(t, ast.Name)}
    kinds, seen, todo = set(), set(), [fn]
    program = launch = driver = spawn = False
    while todo:
        f = todo.pop()
        if f.name in seen and funcs.get(f.name) is f:
            continue
        seen.add(f.name)
        args = f.args.posonlyargs + f.args.args + f.args.kwonlyargs
        todo += [funcs[a.arg] for a in args if a.arg in funcs and a.arg not in seen]   # module fixtures
        for n in ast.walk(f):
            if _greg_subcommand(n) == "run":
                kinds.add("greg run")
            if isinstance(n, (ast.List, ast.Tuple)) and n.elts and (
                    _const(n.elts[0]) == "supervisord" or getattr(n.elts[0], "id", None) == "SUPERVISORD"):
                launch = True
            if isinstance(n, ast.Name) and n.id in drivers:
                driver = True
            if not isinstance(n, ast.Call):
                continue
            name = n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", None)
            program |= name == "supervisord_program"
            spawn |= name in _SUBPROCESS
            if isinstance(n.func, ast.Name) and name in funcs:
                callee = funcs[name]
                if name not in seen:
                    todo.append(callee)
                first = next((a.value for a in n.args if isinstance(_const(a), str)), None)
                if first == "run" and any(_greg_subcommand(x) == "*" for x in ast.walk(callee)):
                    kinds.add("greg run")                # a helper like cli(home, *args) called with 'run'
    if program and launch:
        kinds.add("supervisord")
    if driver and spawn:
        kinds.add("Body.run driver")
    return kinds


def node_process_kinds(node: str, root: Path = ROOT, _cache: dict | None = None) -> set[str]:
    """The ways the tests a cited node selects start a real Body process (empty: in-process only)."""
    path, _, rest = node.partition("::")
    cache = {} if _cache is None else _cache
    if path not in cache:
        file = root / path
        cache[path] = ast.parse(file.read_text()) if file.is_file() else None
    tree = cache[path]
    if tree is None:
        return set()
    target = tree
    for part in [_PARAMS.sub("", p) for p in rest.split("::") if p] if rest else []:
        target = next((n for n in getattr(target, "body", []) if getattr(n, "name", None) == part), None)
        if target is None:
            return set()
    if isinstance(target, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return _process_kinds(target, tree)
    kinds = set()
    for n in ast.walk(target):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test"):
            kinds |= _process_kinds(n, tree)
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
