"""Whole-machine acceptance harness: Missions A-L and the full-machine completion contract.

Directive 2026-10-13, sections 33 and 35 (docs/intent/sources/OPUS-MAXIMUS-MASTER-EXECUTION-DIRECTIVE-
2026-10-13-source.md). ``missions.json`` maps every obligation of Missions A-L to the executable tests that
demonstrate it and the evidence tier those tests can establish; ``completion-contract.json`` records, for
each required function of Body, Mind, Organs and the operating loop, its owner, interface, status and the
mission requirements that carry its evidence.

The harness reports only what the tests establish. It never infers a higher status from a lower one:

- a requirement attains its declared tier only when every cited test node was collected and passed; a
  failure, an error, a skip or a node that collects nothing leaves it unverified, with the observed reason;
- a requirement without tests keeps its declared unverified status (INTENDED .. INTEGRATED) or is
  BLOCKED_WITH_REASON with its reason;
- tests can establish at most BODY_VERIFIED. FOUNDER_ACCEPTED and every status above it need a record that
  no test can produce (Alfonso's signed acceptance, a live authorization, an external observation, a
  commercial outcome), so the manifest refuses to declare them and the harness never assigns them;
- a mission or a contract function is only as verified as its least-verified requirement.

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

def requirement_status(req: dict, outcomes: dict | None) -> dict:
    """What one requirement attained in a run. ``outcomes`` maps collected nodeid -> {outcome, reason}.

    With ``outcomes`` None (no run), a tested requirement is reported at its declared implementation
    status only: a declaration is never evidence."""
    tests = req.get("tests", [])
    if not tests:
        status = req.get("status", "INTENDED")
        return {"status": status, "declared_tier": None, "attained": False,
                "observed": [req.get("blocked_reason", "no executable test cites this requirement")]}
    if outcomes is None:
        return {"status": req.get("implementation", "IMPLEMENTED"), "declared_tier": req["tier"],
                "attained": False, "observed": ["not run"]}
    observed = []
    for node in tests:
        items = {k: v for k, v in outcomes.items() if covers(node, k)}
        if not items:
            observed.append(f"{node}: collected nothing")
        for nodeid, result in sorted(items.items()):
            if result["outcome"] != "passed":
                observed.append(f"{nodeid}: {result['outcome']}: {result.get('reason', '')}"[:500])
    if observed:
        return {"status": req.get("implementation", "IMPLEMENTED"), "declared_tier": req["tier"],
                "attained": False, "observed": observed}
    return {"status": req["tier"], "declared_tier": req["tier"], "attained": True, "observed": []}


def mission_status(mission: dict, outcomes: dict | None) -> dict:
    reqs = {r["id"]: requirement_status(r, outcomes) for r in mission["requirements"]}
    open_gaps = [g for g in mission.get("gaps", []) if g["state"] == "OPEN"]
    return {"id": mission["id"], "title": mission["title"], "status": lowest(r["status"] for r in reqs.values()),
            "requirements": reqs, "open_gaps": len(open_gaps),
            "blocked_beyond_tests": sorted({g["id"] for g in open_gaps if g["dependency"] != "none"
                                            and not g.get("buildable_now")})}


def contract_status(function: dict, missions: dict) -> dict:
    """A contract function's evidence tier is computed from the mission requirements it cites, never
    declared: the least-verified of them, and never above what its own implementation status allows."""
    reached = []
    for ref in function["evidence"]:
        mid, _, rid = ref.partition(".")
        reached.append(missions[mid]["requirements"][rid]["status"])
    tier = lowest(reached) if reached else function["implementation"]
    if tier != BLOCKED and function["implementation"] in UNVERIFIED and rank(function["implementation"]) < rank(
            "IMPLEMENTED"):
        tier = function["implementation"]           # designed-only functions cannot be verified by tests
    return {"id": function["id"], "evidence_tier": tier, "evidence": function["evidence"]}


def report(manifest: dict, contract: dict, outcomes: dict | None, meta: dict) -> dict:
    missions = {m["id"]: mission_status(m, outcomes) for m in manifest["missions"]}
    functions = [contract_status(f, missions) for f in contract["functions"]]
    attained = sum(r["attained"] for m in missions.values() for r in m["requirements"].values())
    total = sum(len(m["requirements"]) for m in missions.values())
    return {"version": "acceptance-report/1", **meta, "ran": outcomes is not None,
            "summary": {"requirements": total, "attained_declared_tier": attained,
                        "missions": {k: v["status"] for k, v in missions.items()},
                        "highest_status_any_test_can_establish": TEST_TIERS[-1],
                        "statuses_no_test_can_establish": list(BEYOND_TESTS)},
            "missions": missions, "contract": functions}


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
    for m in manifest["missions"]:
        seen = set()
        for r in m["requirements"]:
            where = f"{m['id']}.{r['id']}"
            if r["id"] in seen:
                out.append(f"{where}: duplicate requirement id")
            seen.add(r["id"])
            if r.get("tests"):
                if r.get("tier") not in TEST_TIERS:
                    out.append(f"{where}: a tested requirement declares a tier tests can establish "
                               f"({', '.join(TEST_TIERS)}), not {r.get('tier')}")
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
