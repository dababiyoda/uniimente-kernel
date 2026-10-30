"""The 2026-10-28 directive section by section: "the prompt is completely built", computed and conjunctive.

On 2026-10-30 the founder wrote "That is done when we completely build the prompt"
(INTENT-20261030-BUILD-BEFORE-DEVICE-RUN). The prompt is the 77-section directive kept verbatim in
``docs/intent/sources/OPUS-MAXIMUS-MASTER-BUILD-DIRECTIVE-2026-10-28-source.md``. ``directive-sections.json``
holds one record per section: its exact heading and its testable asks. Each ask carries a short faithful
paraphrase and a short verbatim excerpt, the paths that own it, the evidence it rests on (completion-contract
functions, mission requirements and pytest nodes), the tier it requires and the tier that evidence computes, and,
while it is open, why: FOUNDER_ONLY, EXTERNAL, BUILDABLE_NOT_BUILT (with its gap-map unit) or PRINCIPLE (guarded by
named tests, or UNGUARDED).

The harness's own rules (acceptance/__init__.py) carry over, and are extended:

- an ask's tier is computed from what it cites and never declared above it: the least-verified of its mission
  requirements, its contract functions and its own test nodes. Its own test nodes establish the tier the ask
  declares for them (``tests_tier``, UNIT_VERIFIED by default), never above BODY_VERIFIED, and BODY_VERIFIED only with
  a cited node that drives a real Body process. An ask that cites nothing is INTENDED;
- an ask's coverage is never above the coverage of a requirement or function it cites;
- an ask is met only when its tier reaches its required tier and it is covered. Tests reach at most BODY_VERIFIED,
  so an ask that requires FOUNDER_ACCEPTED or above is never met by building, and its blocker is FOUNDER_ONLY or
  EXTERNAL;
- a section is DONE only when every ask is met, OPEN when none is, and PARTIAL otherwise;
- "the prompt is completely built" holds only when no ask is open for a reason building can close
  (BUILDABLE_NOT_BUILT, or a PRINCIPLE no test guards). "Every section DONE" also needs every founder and external
  record. Neither is a count: one open ask in one section makes each false.

Without a run, an ask's tier is what its evidence could establish if every cited test passed (the static
ceiling); ``directive --outcomes`` recomputes it from a recorded run. Nothing here grants, attaches or activates
anything: it reads the directive, this tree and test outcomes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from acceptance import (BEYOND_TESTS, BLOCKED, CONTRACT, HERE, MANIFEST, ROOT, _schema_problems, covers, load, lowest,
                        minimal_nodes, node_problem, rank, real_process_nodes, report, shortfalls)

DIRECTIVE_MAP = HERE / "directive-sections.json"
SECTIONS = 77
BLOCKER_CLASSES = ("FOUNDER_ONLY", "EXTERNAL", "BUILDABLE_NOT_BUILT", "PRINCIPLE")
SECTION_STATUSES = ("DONE", "PARTIAL", "OPEN")
UNGUARDED = "UNGUARDED"
NO_EVIDENCE = "INTENDED"                     # an ask that cites nothing shows nothing
SHORT_FLOOR = "IMPLEMENTED"                  # an ask's own nodes fell short in a run: nothing verified the code
_COVERAGE_RANK = {"gap": 0, "partial": 1, "covered": 2}
_HEADING = re.compile(r"(\d{1,2})\. (\S.*)")
_BANNER = re.compile(r"^={10,}$", re.M)


# -- the directive's own text --------------------------------------------------------------------------------------

def fenced(path: Path) -> str:
    """The message between the four-backtick fences: the text the source file's SHA-256 covers."""
    text = Path(path).read_text(encoding="utf-8")
    start = text.index("````text\n") + len("````text\n")
    return text[start:text.rindex("\n````")]


def copies(body: str) -> list[list[tuple[int, str, str]]]:
    """Each copy of the numbered sections, in order, as (n, heading, text). A section starts on the first non-blank
    line after a '⸻' rule and runs to the next rule, or to the '=====' banner that opens the repeated copy."""
    found = []
    for block in re.split(r"^⸻$", body, flags=re.M)[1:]:
        block = _BANNER.split(block, maxsplit=1)[0]
        first = next((line.strip() for line in block.splitlines() if line.strip()), "")
        match = _HEADING.fullmatch(first)
        if match:
            found.append((int(match.group(1)), match.group(2), block))
    out: list[list] = []
    for section in found:
        if not out or section[0] <= out[-1][-1][0]:
            out.append([])
        out[-1].append(section)
    return out


def source_sections(path: Path) -> dict[int, tuple[str, str]]:
    """The first copy's sections by number: {n: (heading, text)}."""
    return {n: (heading, text) for n, heading, text in copies(fenced(path))[0]}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("⸻", "")).strip()


def ask_nodes(ask: dict) -> list[str]:
    """The pytest nodes an ask cites itself, outside mission requirements and contract functions."""
    return [e for e in ask.get("evidence", []) if e.startswith("tests/")]


def cited_nodes(doc: dict) -> list[str]:
    nodes = []
    for section in doc["sections"]:
        for ask in section["asks"]:
            nodes += ask_nodes(ask)
            guard = ask.get("blocker", {}).get("guarded_by")
            nodes += guard if isinstance(guard, list) else []
    return minimal_nodes(nodes)


# -- tiers and statuses ---------------------------------------------------------------------------------------------

def _manifest_nodes(manifest: dict) -> list[str]:
    return [n for m in manifest["missions"] for r in m["requirements"] for n in r.get("tests", [])] + \
        [n for m in manifest["missions"] for link in m.get("trace", []) for n in link["proof"]]


_CEILINGS: dict[str, dict] = {}


def evidence_report(manifest: dict, contract: dict, outcomes: dict | None) -> dict:
    """The harness's report on the missions and the contract. With no run, every cited node is taken as passed:
    what is reported is then a ceiling, the most the cited evidence could establish, never an attainment (kept per
    manifest and contract content, which is all it depends on)."""
    if outcomes is not None:
        return report(manifest, contract, outcomes, {})
    key = hashlib.sha256(json.dumps([manifest, contract], sort_keys=True).encode()).hexdigest()
    if key not in _CEILINGS:
        passed = {n: {"outcome": "passed", "reason": ""} for n in _manifest_nodes(manifest)}
        _CEILINGS[key] = report(manifest, contract, passed, {})
    return _CEILINGS[key]


def _requirement_coverage(r: dict) -> str:
    return "covered" if r["whole_obligation"] else "partial" if r["attained"] else "gap"


def ask_status(ask: dict, rep: dict, outcomes: dict | None) -> dict:
    """What one ask reaches: the least-verified of everything it cites, its coverage capped by what it cites, and
    whether that meets its required tier. ``rep`` is evidence_report() for the same ``outcomes``."""
    functions = {f["id"]: f for f in rep["contract"]}
    tiers, caps, observed = [], [], []
    for ref in ask.get("evidence", []):
        kind, _, name = ref.partition(":")
        if kind == "mission":
            mid, _, rid = name.partition(".")
            r = rep["missions"][mid]["requirements"][rid]
            tiers.append(r["status"])
            caps.append(_requirement_coverage(r))
        elif kind == "contract":
            f = functions[name]
            tiers.append(f["evidence_tier"])
            caps.append(f["coverage"])
    nodes = ask_nodes(ask)
    if nodes:
        observed = [] if outcomes is None else shortfalls(nodes, outcomes)
        tiers.append(SHORT_FLOOR if observed else ask.get("tests_tier", "UNIT_VERIFIED"))
    tier = lowest(tiers) if tiers else NO_EVIDENCE
    coverage = min([ask["coverage"]] + caps, key=_COVERAGE_RANK.__getitem__)
    met = tier != BLOCKED and coverage == "covered" and rank(tier) >= rank(ask["required_tier"])
    return {"id": ask["id"], "required_tier": ask["required_tier"], "tier": tier, "coverage": coverage, "met": met,
            "blocker": None if met else ask.get("blocker"), "observed": observed}


def section_status(asks: list[dict]) -> str:
    met = sum(a["met"] for a in asks)
    return "DONE" if asks and met == len(asks) else "OPEN" if met == 0 else "PARTIAL"


def _builds_can_close(ask: dict) -> bool:
    """Open for a reason building can close: not built yet, or a standing rule no test guards."""
    blocker = ask.get("blocker") or {}
    return blocker.get("class") == "BUILDABLE_NOT_BUILT" or (
        blocker.get("class") == "PRINCIPLE" and blocker.get("guarded_by") == UNGUARDED) or not blocker


def unit_order(units: list[dict]) -> list[str]:
    """The units in dependency order: each after everything it depends on, ties kept in the file's order."""
    deps = {u["id"]: [d for d in u.get("depends_on", []) if d != u["id"]] for u in units}
    done, order = set(), []
    while len(order) < len(deps):
        ready = [u for u in deps if u not in done and all(d in done or d not in deps for d in deps[u])]
        if not ready:                                    # a cycle: reported by directive_problems
            ready = [next(u for u in deps if u not in done)]
        order.append(ready[0])
        done.add(ready[0])
    return order


def directive_report(doc: dict, manifest: dict, contract: dict, outcomes: dict | None = None) -> dict:
    """Every section's status computed from its asks, and the two conjunctive verdicts. ``outcomes`` None: static
    ceilings (no test ran)."""
    rep = evidence_report(manifest, contract, outcomes)
    sections, asks = [], []
    for section in doc["sections"]:
        rows = [ask_status(ask, rep, outcomes) for ask in section["asks"]]
        sections.append({"n": section["n"], "heading": section["heading"], "status": section_status(rows),
                         "asks": rows})
        asks += rows
    open_asks = [a for a in asks if not a["met"]]
    residual = [a for a in open_asks if _builds_can_close(a)]
    by_unit: dict[str, list[str]] = {}
    for a in open_asks:
        if (a["blocker"] or {}).get("class") == "BUILDABLE_NOT_BUILT":
            by_unit.setdefault(a["blocker"].get("unit", ""), []).append(a["id"])
    order = [u for u in unit_order(doc.get("units", [])) if u in by_unit] + ([""] if "" in by_unit else [])
    by_class = {c: sum(1 for a in open_asks if (a["blocker"] or {}).get("class") == c) for c in BLOCKER_CLASSES}
    by_class["PRINCIPLE_UNGUARDED"] = sum(1 for a in open_asks if (a["blocker"] or {}).get("class") == "PRINCIPLE"
                                          and a["blocker"].get("guarded_by") == UNGUARDED)
    by_class["NONE_NAMED"] = sum(1 for a in open_asks if not a["blocker"])
    return {"version": "directive-report/1", "ran": outcomes is not None,
            "summary": {"sections": len(sections),
                        "by_status": {s: sum(x["status"] == s for x in sections) for s in SECTION_STATUSES},
                        "asks": len(asks), "asks_met": len(asks) - len(open_asks),
                        "open_by_blocker": by_class, "build_residual": len(residual),
                        "prompt_completely_built": not residual and len(sections) == SECTIONS,
                        "every_section_done": len(sections) == SECTIONS and all(x["status"] == "DONE"
                                                                                for x in sections)},
            "buildable_in_dependency_order": [{"unit": u or None, "asks": by_unit[u]} for u in order],
            "sections": sections}


# -- validation -------------------------------------------------------------------------------------------------------

def directive_problems(doc: dict, manifest: dict, contract: dict, root: Path = ROOT) -> list[str]:
    """Everything that makes the directive map unsound against this tree. Empty means sound (not built)."""
    out = _schema_problems(doc, "directive-sections.schema.json")
    if out:
        return out
    source = root / doc["source"]["directive"]
    if not source.is_file():
        return [f"source: no such file {doc['source']['directive']}"]
    body = fenced(source)
    if hashlib.sha256(body.encode("utf-8")).hexdigest() != doc["source"]["sha256"]:
        out.append("source: the directive's text no longer matches the digest this map was read against")
    texts = source_sections(source)
    if sorted(texts) != list(range(1, SECTIONS + 1)):
        out.append(f"source: expected sections 1..{SECTIONS} in the directive, found {len(texts)}")

    numbers = [s["n"] for s in doc["sections"]]
    for n in range(1, SECTIONS + 1):
        if numbers.count(n) == 0:
            out.append(f"section {n}: missing")
        elif numbers.count(n) > 1:
            out.append(f"section {n}: duplicated ({numbers.count(n)} records)")
    for n in sorted(set(numbers) - set(range(1, SECTIONS + 1))):
        out.append(f"section {n}: the directive has no such section")
    if numbers != sorted(numbers):
        out.append("sections must be in the directive's order")

    units = {u["id"]: u for u in doc.get("units", [])}
    if len(units) != len(doc.get("units", [])):
        out.append("units: a unit id is listed twice")
    for u in units.values():
        for d in u.get("depends_on", []):
            if d not in units:
                out.append(f"unit {u['id']}: depends on unknown unit {d}")
    if _cyclic(units):
        out.append("units: the dependency graph has a cycle")

    registry = {e["file"]: e["starts"] for e in manifest["body_process_tests"]}
    reqs = {(m["id"], r["id"]) for m in manifest["missions"] for r in m["requirements"]}
    functions = {f["id"] for f in contract["functions"]}
    rep = evidence_report(manifest, contract, None)
    cache: dict = {}
    seen: set = set()
    for section in doc["sections"]:
        n, where_s = section["n"], f"section {section['n']}"
        if n in texts and section["heading"] != texts[n][0]:
            out.append(f"{where_s}: heading {section['heading']!r} does not match the source ({texts[n][0]!r})")
        statuses = []
        for ask in section["asks"]:
            where = f"{where_s} {ask['id']}"
            if ask["id"] in seen:
                out.append(f"{where}: duplicate ask id")
            seen.add(ask["id"])
            if not ask["id"].startswith(f"S{n}."):
                out.append(f"{where}: an ask id names its own section (S{n}.A<k>)")
            if n in texts and _norm(ask["excerpt"]) not in _norm(texts[n][1]):
                out.append(f"{where}: excerpt is not verbatim in section {n} of the source")
            for path in ask["owner_paths"]:
                if not (root / path).exists():
                    out.append(f"{where}: owner path {path} does not exist")
            broken = _evidence_problems(where, ask, reqs, functions, registry, root, cache)
            out += broken
            if broken:
                continue
            got = ask_status(ask, rep, None)
            statuses.append(got)
            out += _claim_problems(where, ask, got, units, root)
        if len(statuses) == len(section["asks"]):
            computed = section_status(statuses)
            if section["status"] == "DONE" and computed != "DONE":
                opened = ", ".join(a["id"] for a in statuses if not a["met"])
                out.append(f"{where_s}: DONE is claimed with an open ask ({opened})")
            elif section["status"] != computed:
                out.append(f"{where_s}: status {section['status']} is not what its asks compute ({computed})")
    return out


_NODES: dict[tuple, str | None] = {}


def _node_problem(node: str, root: Path) -> str | None:
    """node_problem, kept per node and the version of the file it names (a test file is parsed once per run)."""
    file = root / node.partition("::")[0]
    key = (str(root), node, file.stat().st_mtime_ns if file.is_file() else None)
    if key not in _NODES:
        _NODES[key] = node_problem(node, root)
    return _NODES[key]


def _evidence_problems(where, ask, reqs, functions, registry, root, cache) -> list[str]:
    out = []
    for ref in ask.get("evidence", []):
        kind, _, name = ref.partition(":")
        if kind == "mission" and tuple(name.split(".", 1)) not in reqs:
            out.append(f"{where}: evidence {ref} names no mission requirement")
        elif kind == "contract" and name not in functions:
            out.append(f"{where}: evidence {ref} names no completion-contract function")
        elif ref.startswith("tests/"):
            problem = _node_problem(ref, root)
            if problem:
                out.append(f"{where}: {problem}")
    nodes = ask_nodes(ask)
    if "tests_tier" in ask and not nodes:
        out.append(f"{where}: tests_tier names the tier of the ask's own test nodes, and it cites none")
    if ask.get("tests_tier") == "BODY_VERIFIED" and not out and not real_process_nodes(nodes, registry, root, cache):
        out.append(f"{where}: tests_tier BODY_VERIFIED needs a cited node that drives a real Body process (a test in a "
                   f"body_process_tests file that starts one)")
    guard = ask.get("blocker", {}).get("guarded_by")
    for node in guard if isinstance(guard, list) else []:
        problem = _node_problem(node, root)
        if problem:
            out.append(f"{where}: guard {problem}")
    return out


def _claim_problems(where, ask, got, units, root) -> list[str]:
    out = []
    if ask["tier"] != got["tier"]:
        if _level(ask["tier"]) > _level(got["tier"]):
            out.append(f"{where}: tier {ask['tier']} is claimed above what its evidence can establish ({got['tier']})")
        else:
            out.append(f"{where}: tier {ask['tier']} is not what its evidence computes ({got['tier']})")
    caps = got["coverage"]
    if _COVERAGE_RANK[ask["coverage"]] > _COVERAGE_RANK[caps]:
        out.append(f"{where}: coverage {ask['coverage']!r} is claimed above what it cites ({caps!r})")
    blocker = ask.get("blocker")
    if got["met"]:
        if blocker:
            out.append(f"{where}: a met ask names a blocker ({blocker['class']})")
        return out
    if not blocker:
        out.append(f"{where}: an open ask (tier {got['tier']}, coverage {got['coverage']}, required "
                   f"{ask['required_tier']}) names no blocker class")
        return out
    cls = blocker["class"]
    if ask["required_tier"] in BEYOND_TESTS and cls not in ("FOUNDER_ONLY", "EXTERNAL"):
        out.append(f"{where}: no build or test reaches {ask['required_tier']}; its blocker is FOUNDER_ONLY or "
                   f"EXTERNAL, not {cls}")
    if "unit" in blocker and cls != "BUILDABLE_NOT_BUILT":
        out.append(f"{where}: only a BUILDABLE_NOT_BUILT ask names a gap-map unit")
    if blocker.get("unit") and blocker["unit"] not in units:
        out.append(f"{where}: unit {blocker['unit']} is not in the units table")
    if cls == "PRINCIPLE":
        guard = blocker.get("guarded_by")
        if guard != UNGUARDED and not (isinstance(guard, list) and guard):
            out.append(f"{where}: a PRINCIPLE names the tests that guard it, or {UNGUARDED}")
    elif "guarded_by" in blocker:
        out.append(f"{where}: only a PRINCIPLE names guards")
    return out


def _level(status: str) -> int:
    """A status's rung, BLOCKED_WITH_REASON below every rung (it dominates, as in lowest())."""
    return -1 if status == BLOCKED else rank(status)


def _cyclic(units: dict) -> bool:
    state: dict = {}

    def visit(u) -> bool:
        if state.get(u) == 1:
            return True
        if state.get(u) == 2 or u not in units:
            return False
        state[u] = 1
        if any(visit(d) for d in units[u].get("depends_on", [])):
            return True
        state[u] = 2
        return False
    return any(visit(u) for u in units)


# -- collection: every cited node collects at least one test ----------------------------------------------------------

def collect_problems(nodes, root: Path = ROOT, timeout: int = 1800) -> list[str]:
    """Run pytest's collection over the files the nodes name and report every node that collects nothing. Nothing
    is executed: ``--collect-only``. A file that fails to import collects nothing."""
    nodes = list(nodes)
    files = sorted({n.partition("::")[0] for n in nodes if (root / n.partition("::")[0]).is_file()})
    collected: list[str] = []
    if files:
        proc = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
                               "--continue-on-collection-errors", *files], cwd=root, capture_output=True, text=True,
                              timeout=timeout)
        collected = [line.strip() for line in proc.stdout.splitlines() if re.match(r"tests/\S+\.py::", line.strip())]
    return [f"{node}: collects nothing" for node in nodes if not any(covers(node, c) for c in collected)]


# -- printing ---------------------------------------------------------------------------------------------------------

def summary_line(rep: dict) -> str:
    s = rep["summary"]
    status = ", ".join(f"{k} {v}" for k, v in s["by_status"].items())
    return (f"directive: {s['sections']} sections ({status}); {s['asks_met']}/{s['asks']} asks met; "
            f"{s['build_residual']} open asks building can still close; prompt completely built: "
            f"{'yes' if s['prompt_completely_built'] else 'NO'}; every section done: "
            f"{'yes' if s['every_section_done'] else 'NO'}")


def print_report(rep: dict, doc: dict) -> None:
    units = {u["id"]: u for u in doc.get("units", [])}
    print(f"directive sections ({'tests ran' if rep['ran'] else 'static ceilings: no test ran'})")
    for section in rep["sections"]:
        met = sum(a["met"] for a in section["asks"])
        print(f"  {section['n']:>2}. {section['status']:<7} {met}/{len(section['asks'])} asks met  "
              f"{section['heading']}")
        for a in section["asks"]:
            if a["met"]:
                continue
            b = a["blocker"] or {}
            why = b.get("class", "NO BLOCKER NAMED")
            why += f" {b['unit']}" if b.get("unit") else ""
            why += " UNGUARDED" if b.get("guarded_by") == UNGUARDED else ""
            print(f"        {a['id']}: {a['tier']} of {a['required_tier']} ({a['coverage']}) -- {why}")
    s = rep["summary"]
    print("open asks by blocker: " + ", ".join(f"{k} {v}" for k, v in s["open_by_blocker"].items()))
    print("BUILDABLE_NOT_BUILT asks in dependency order:")
    for row in rep["buildable_in_dependency_order"]:
        title = units.get(row["unit"], {}).get("title", "no gap-map unit")
        print(f"  {row['unit'] or '-'}: {title[:100]}  [{', '.join(row['asks'])}]")
    print(summary_line(rep))


def load_map(path: Path = DIRECTIVE_MAP) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def defaults() -> tuple[dict, dict, dict]:
    return load_map(), load(MANIFEST), load(CONTRACT)

