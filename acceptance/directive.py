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
  requirements (and, as for contract functions, the trace links of a cited mission that carries a trace), its
  contract functions and its own test nodes. Its own test nodes establish the tier the ask declares for them
  (``tests_tier``, UNIT_VERIFIED by default), never above BODY_VERIFIED, and BODY_VERIFIED only with a cited node that
  drives a real Body process. An ask that cites nothing is INTENDED;
- an ask's coverage is never above the coverage of a requirement, trace or function it cites;
- an ask is met only when its tier reaches its required tier and it is covered. Tests reach at most BODY_VERIFIED,
  so an ask that requires FOUNDER_ACCEPTED or above is never met by building, and its blocker is FOUNDER_ONLY or
  EXTERNAL. On a tier a test can reach, a FOUNDER_ONLY or EXTERNAL blocker cites the record that holds it;
- a section is DONE only when every ask is met and every listed line of the section (a bullet, or a line that
  starts "Do not" or "Never") is answered by an ask or set aside with a reason; OPEN when no ask is met, and PARTIAL
  otherwise;
- "the prompt is completely built" holds only when no ask is open for a reason building can close
  (BUILDABLE_NOT_BUILT, or a PRINCIPLE no test guards or whose guard fell short in a run) and every listed line is
  accounted for. "Every section DONE" also needs every founder and external record. Neither is a count: one open ask
  or one unread line in one section makes each false.

The set of asks is pinned (``directive-asks.pin.json``): an ask is retired, never deleted, and an open ask's blocker
may move only to BUILDABLE_NOT_BUILT unless the pin is changed, which ``directive --against <base>`` refuses.

Without a run, an ask's tier is what its evidence could establish if every cited test passed (the static
ceiling); ``directive --outcomes`` recomputes it from a recorded run. Nothing here grants, attaches or activates
anything: it reads the directive, this tree and test outcomes.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from acceptance import (BEYOND_TESTS, BLOCKED, CONTRACT, HERE, MANIFEST, ROOT, TEST_TIERS, _schema_problems, covers,
                        load, lowest, node_problem, rank, real_process_nodes, report, shortfalls)

DIRECTIVE_MAP = HERE / "directive-sections.json"
PIN = HERE / "directive-asks.pin.json"
SOURCE = "docs/intent/sources/OPUS-MAXIMUS-MASTER-BUILD-DIRECTIVE-2026-10-28-source.md"
SECTIONS = 77
BLOCKER_CLASSES = ("FOUNDER_ONLY", "EXTERNAL", "BUILDABLE_NOT_BUILT", "PRINCIPLE")
SECTION_STATUSES = ("DONE", "PARTIAL", "OPEN")
UNGUARDED = "UNGUARDED"
NO_EVIDENCE = "INTENDED"                     # an ask that cites nothing shows nothing
SHORT_FLOOR = "IMPLEMENTED"                  # an ask's own nodes fell short in a run: nothing verified the code
# The missions.json gap dependencies that can hold an ask's founder or external blocker.
RECORD_DEPENDENCIES = {"FOUNDER_ONLY": ("founder", "credential"),
                       "EXTERNAL": ("external", "technical", "legal", "physical")}
_COVERAGE_RANK = {"gap": 0, "partial": 1, "covered": 2}
_HEADING = re.compile(r"(\d{1,2})\. (\S.*)")
_BANNER = re.compile(r"^={10,}$", re.M)
_LISTED = re.compile(r"(\* |Do not |Never )")


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
    """The first copy's sections by number: {n: (heading, text)}; empty when the text has none."""
    found = copies(fenced(path))
    return {n: (heading, text) for n, heading, text in found[0]} if found else {}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("⸻", "")).strip()


def listed_lines(text: str) -> list[str]:
    """A section's listed lines, distinct and in order: each bullet, and each line that starts 'Do not' or 'Never'.
    Every one is a candidate obligation; a DONE section answers each with an ask or sets it aside with a reason."""
    out = []
    for line in text.splitlines():
        line = _norm(line)
        if _LISTED.match(line) and line not in out:
            out.append(line)
    return out


def _core(line: str) -> str:
    """A listed line without its bullet and closing punctuation: what an excerpt must quote to answer it."""
    return _norm(line).removeprefix("* ").rstrip(";:.,").strip()


def ask_nodes(ask: dict) -> list[str]:
    """The pytest nodes an ask cites itself, outside mission requirements and contract functions."""
    return [e for e in ask.get("evidence", []) if e.startswith("tests/")]


def _guards(ask: dict) -> list[str]:
    guard = (ask.get("blocker") or {}).get("guarded_by")
    return guard if isinstance(guard, list) else []


def cited_nodes(doc: dict) -> list[str]:
    """Every distinct node the map cites, guards included. Not reduced to the files that cover them: a node inside a
    file another ask cites whole must still collect a test of its own."""
    nodes = []
    for section in doc["sections"]:
        for ask in section["asks"]:
            nodes += ask_nodes(ask) + _guards(ask)
    return sorted(set(nodes))


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
    whether that meets its required tier. ``rep`` is evidence_report() for the same ``outcomes``. A requirement of a
    mission that carries a trace (Mission L) is also capped by that trace's links, as contract_status() caps a
    function. In a run, a PRINCIPLE whose guards fell short records what they did: it no longer counts as guarded."""
    functions = {f["id"]: f for f in rep["contract"]}
    tiers, caps, observed = [], [], []
    for ref in ask.get("evidence", []):
        kind, _, name = ref.partition(":")
        if kind == "mission":
            mid, _, rid = name.partition(".")
            r = rep["missions"][mid]["requirements"][rid]
            links = rep["missions"][mid].get("trace", [])
            tiers += [r["status"]] + [x["status"] for x in links]
            caps.append(_requirement_coverage(r))
            if not all(x["attained"] for x in links):
                caps.append("partial")
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
    guards = _guards(ask)
    return {"id": ask["id"], "required_tier": ask["required_tier"], "tier": tier, "coverage": coverage, "met": met,
            "blocker": None if met else ask.get("blocker"), "observed": observed,
            "guard_observed": shortfalls(guards, outcomes) if outcomes is not None and guards else []}


def section_status(asks: list[dict], unaccounted=()) -> str:
    """DONE only when every ask is met and no listed line of the section is left unanswered."""
    met = sum(a["met"] for a in asks)
    return "DONE" if asks and met == len(asks) and not unaccounted else "OPEN" if met == 0 else "PARTIAL"


def accounted_lines(section: dict, text: str) -> tuple[list[str], list[str]]:
    """The section's listed lines (accounted, unaccounted). A line is accounted when an ask's excerpt quotes it whole
    or an ask names it in ``lines`` (retired asks included: retiring is a disposition), or the section sets it aside
    in ``not_asks`` with a reason."""
    excerpts = [_norm(a["excerpt"]) for a in section["asks"]]
    named = {_norm(line) for a in section["asks"] for line in a.get("lines", [])}
    named |= {_norm(x["line"]) for x in section.get("not_asks", [])}
    lines = listed_lines(text)
    done = [line for line in lines if line in named or any(_core(line) in e for e in excerpts)]
    return done, [line for line in lines if line not in done]


def _builds_can_close(row: dict) -> bool:
    """Open for a reason building can close: not built yet, a standing rule no test guards (or whose guard fell
    short in a run), or no reason named at all (a met ask a run reopened)."""
    blocker = row.get("blocker") or {}
    return blocker.get("class") == "BUILDABLE_NOT_BUILT" or (
        blocker.get("class") == "PRINCIPLE" and _unguarded(row)) or not blocker


def _unguarded(row: dict) -> bool:
    return (row.get("blocker") or {}).get("guarded_by") == UNGUARDED or bool(row.get("guard_observed"))


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


def _prerequisites(named, units: dict) -> set[str]:
    """``named`` and every unit they depend on, transitively, that is not closed."""
    out, stack = set(named), list(named)
    while stack:
        for dep in units.get(stack.pop(), {}).get("depends_on", []):
            if dep in units and dep not in out and not units[dep].get("closed_by"):
                out.add(dep)
                stack.append(dep)
    return out


def _source_texts(doc: dict, root: Path) -> dict[int, tuple[str, str]]:
    source = root / doc["source"]["directive"]
    try:
        return source_sections(source)
    except (OSError, ValueError):
        return {}


def directive_report(doc: dict, manifest: dict, contract: dict, outcomes: dict | None = None,
                     root: Path = ROOT) -> dict:
    """Every section's status computed from its asks and its listed lines, and the two conjunctive verdicts.
    ``outcomes`` None: static ceilings (no test ran)."""
    rep = evidence_report(manifest, contract, outcomes)
    texts = _source_texts(doc, root)
    live = {a["id"]: a for s in doc["sections"] for a in s["asks"] if "retired" not in a}
    sections, asks, retired, unread = [], [], [], 0
    for section in doc["sections"]:
        rows = []
        for ask in section["asks"]:
            gone = ask.get("retired")
            if gone and gone.get("superseded_by") in live:      # its successor carries the obligation
                row = {**ask_status(live[gone["superseded_by"]], rep, outcomes), "id": ask["id"],
                       "retired": {"superseded_by": gone["superseded_by"]}}
            elif gone:                                          # withdrawn by the founder's record: not counted
                retired.append({"id": ask["id"], "retired": gone})
                continue
            else:
                row = ask_status(ask, rep, outcomes)
            rows.append(row)
        _, unaccounted = accounted_lines(section, texts[section["n"]][1]) if section["n"] in texts else ([], [])
        unread += len(unaccounted)
        sections.append({"n": section["n"], "heading": section["heading"],
                         "status": section_status(rows, unaccounted), "asks": rows, "unaccounted_lines": unaccounted})
        asks += rows
    open_asks = [a for a in asks if not a["met"]]
    residual = [a for a in open_asks if _builds_can_close(a)]
    units = {u["id"]: u for u in doc.get("units", [])}
    by_unit: dict[str, list[str]] = {}
    for a in open_asks:
        if (a["blocker"] or {}).get("class") == "BUILDABLE_NOT_BUILT":
            by_unit.setdefault(a["blocker"].get("unit", ""), []).append(a["id"])
    needed = _prerequisites({u for u in by_unit if u}, units)
    order = [u for u in unit_order(list(units.values())) if u in needed] + ([""] if "" in by_unit else [])
    by_class = {c: sum(1 for a in open_asks if (a["blocker"] or {}).get("class") == c) for c in BLOCKER_CLASSES}
    by_class["PRINCIPLE_UNGUARDED"] = sum(1 for a in open_asks if (a["blocker"] or {}).get("class") == "PRINCIPLE"
                                          and _unguarded(a))
    by_class["NONE_NAMED"] = sum(1 for a in open_asks if not a["blocker"])
    whole = len(sections) == SECTIONS
    return {"version": "directive-report/2", "ran": outcomes is not None,
            "summary": {"sections": len(sections),
                        "by_status": {s: sum(x["status"] == s for x in sections) for s in SECTION_STATUSES},
                        "asks": len(asks), "asks_met": len(asks) - len(open_asks), "asks_retired": len(retired),
                        "open_by_blocker": by_class, "build_residual": len(residual),
                        "listed_lines_unaccounted": unread,
                        "prompt_completely_built": not residual and not unread and whole,
                        "every_section_done": whole and all(x["status"] == "DONE" for x in sections)},
            "buildable_in_dependency_order": [{"unit": u or None, "asks": by_unit.get(u, []),
                                               **({"prerequisite_only": True} if u not in by_unit else {})}
                                              for u in order],
            "retired": retired, "sections": sections}


# -- validation -------------------------------------------------------------------------------------------------------

def directive_problems(doc: dict, manifest: dict, contract: dict, root: Path = ROOT, pin: dict | None = None
                       ) -> list[str]:
    """Everything that makes the directive map unsound against this tree. Empty means sound (not built). ``pin``
    None reads acceptance/directive-asks.pin.json under ``root``."""
    out = _schema_problems(doc, "directive-sections.schema.json")
    if out:
        return out
    if doc["source"]["directive"] != SOURCE:
        return [f"source: this map reads {SOURCE}, not {doc['source']['directive']}"]
    source = root / doc["source"]["directive"]
    if not source.is_file():
        return [f"source: no such file {doc['source']['directive']}"]
    try:
        body = fenced(source)
    except ValueError:
        return [f"source: {doc['source']['directive']} holds no four-backtick text fence"]
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
    gaps = {(m["id"], g["id"]): g for m in manifest["missions"] for g in m.get("gaps", [])}
    functions = {f["id"] for f in contract["functions"]}
    rep = evidence_report(manifest, contract, None)
    live = {a["id"]: a for s in doc["sections"] for a in s["asks"] if "retired" not in a}
    cache: dict = {}
    seen: set = set()
    named_units: set = set()
    opened: dict[str, str] = {}
    for section in doc["sections"]:
        n, where_s = section["n"], f"section {section['n']}"
        if n in texts and section["heading"] != texts[n][0]:
            out.append(f"{where_s}: heading {section['heading']!r} does not match the source ({texts[n][0]!r})")
        listed = listed_lines(texts[n][1]) if n in texts else []
        statuses, counted = [], 0
        for ask in section["asks"]:
            where = f"{where_s} {ask['id']}"
            if ask["id"] in seen:
                out.append(f"{where}: duplicate ask id")
            seen.add(ask["id"])
            if not ask["id"].startswith(f"S{n}."):
                out.append(f"{where}: an ask id names its own section (S{n}.A<k>)")
            if n in texts and _norm(ask["excerpt"]) not in _norm(texts[n][1]):
                out.append(f"{where}: excerpt is not verbatim in section {n} of the source")
            for line in ask.get("lines", []):
                if n in texts and _norm(line) not in listed:
                    out.append(f"{where}: {line!r} is not a listed line of section {n}")
            if "retired" in ask:
                out += _retired_problems(where, ask, live, gaps, root)
                successor = live.get(ask["retired"].get("superseded_by"))
                if successor is not None:
                    statuses.append(ask_status(successor, rep, None))
                counted += successor is not None or "superseded_by" not in ask["retired"]
                continue
            for path in ask["owner_paths"]:
                if not (root / path).exists():
                    out.append(f"{where}: owner path {path} does not exist")
            broken = _evidence_problems(where, ask, reqs, functions, registry, root, cache)
            out += broken
            if broken:
                continue
            got = ask_status(ask, rep, None)
            statuses.append(got)
            counted += 1
            out += _claim_problems(where, ask, got, units, gaps, root)
            if not got["met"] and ask.get("blocker"):
                opened[ask["id"]] = ask["blocker"]["class"]
                if ask["blocker"]["class"] == "BUILDABLE_NOT_BUILT" and ask["blocker"].get("unit"):
                    named_units.add(ask["blocker"]["unit"])
        excerpts = {_norm(a["excerpt"]) for a in section["asks"]}
        named = {_norm(line) for a in section["asks"] for line in a.get("lines", [])}
        for item in section.get("not_asks", []):
            line = _norm(item["line"])
            if n in texts and line not in listed:
                out.append(f"{where_s}: not_asks names {item['line']!r}, which is not a listed line of section {n}")
            elif line in named or any(_core(line) in e for e in excerpts):
                out.append(f"{where_s}: {item['line']!r} is both answered by an ask and set aside in not_asks")
        if counted == len(section["asks"]):
            rows = [s for s in statuses]
            unaccounted = accounted_lines(section, texts[n][1])[1] if n in texts else []
            computed = section_status(rows, unaccounted)
            if section["status"] == "DONE" and computed != "DONE":
                opened_ids = ", ".join(a["id"] for a in rows if not a["met"])
                if opened_ids:
                    out.append(f"{where_s}: DONE is claimed with an open ask ({opened_ids})")
                else:
                    out.append(f"{where_s}: DONE is claimed with {len(unaccounted)} listed line(s) no ask answers "
                               f"and no not_asks entry sets aside (first: {unaccounted[0]!r})")
            elif section["status"] != computed:
                out.append(f"{where_s}: status {section['status']} is not what its asks compute ({computed})")

    for u, unit in units.items():
        if unit.get("closed_by") and u in named_units:
            out.append(f"unit {u}: closed by {unit['closed_by']}, yet an open ask still names it")
    for u in sorted(set(units) - _prerequisites(named_units, units)):
        if not units[u].get("closed_by"):
            out.append(f"unit {u}: no open ask names it and no unit an open ask names depends on it; attach it to "
                       f"the ask it closes, or record closed_by")
    if pin is None:
        pin_path = root / PIN.relative_to(ROOT)
        if not pin_path.is_file():
            return out + [f"pin: no {PIN.relative_to(ROOT)}: the set of asks is not pinned"]
        pin = json.loads(pin_path.read_text(encoding="utf-8"))
    return out + pin_problems(pin, doc, opened)


def pin_problems(pin: dict, doc: dict, opened: dict[str, str]) -> list[str]:
    """The map against the pinned asks: no pinned ask is missing (an ask is retired, never deleted), every ask is
    pinned, and an open ask's blocker is its pinned class or BUILDABLE_NOT_BUILT (``opened``: id -> class of every
    open ask). Moving an ask out of the build residual is a change to the pin, which ``pin_ratchet_problems``
    refuses against a base."""
    out = _schema_problems(pin, "directive-asks.pin.schema.json")
    if out:
        return [f"pin: {p}" for p in out]
    ids = [a["id"] for s in doc["sections"] for a in s["asks"]]
    for aid in pin["asks"]:
        if aid not in ids:
            out.append(f"pin: {aid} is pinned and missing from the map: an ask is retired, never deleted")
    for aid in ids:
        if aid not in pin["asks"]:
            out.append(f"pin: {aid} is not pinned; add it to {PIN.relative_to(ROOT)}")
    for aid, cls in opened.items():
        pinned = pin["asks"].get(aid)
        if pinned and cls not in (pinned, "BUILDABLE_NOT_BUILT"):
            out.append(f"pin: {aid} is pinned {pinned}; an open ask's blocker moves only to BUILDABLE_NOT_BUILT, "
                       f"not to {cls}")
    return out


def pin_ratchet_problems(base: dict, head: dict) -> list[str]:
    """The pin against the pin at a base: no pinned ask disappears, and a pinned class moves only to
    BUILDABLE_NOT_BUILT. A change that takes an ask out of the build residual cannot pass by editing the pin."""
    out = []
    for aid, cls in base["asks"].items():
        if aid not in head["asks"]:
            out.append(f"pin: {aid} was pinned at the base and is gone")
        elif head["asks"][aid] not in (cls, "BUILDABLE_NOT_BUILT"):
            out.append(f"pin: {aid} was pinned {cls} at the base; it may move only to BUILDABLE_NOT_BUILT, "
                       f"not to {head['asks'][aid]}")
    return out


def evidence_nodes(ask: dict, manifest: dict, contract: dict) -> list[str]:
    """The test nodes an ask's evidence reaches: its own pytest nodes and guards; for a mission requirement, its
    tests and, for a mission that carries a trace, every trace link's proof; for a contract function, the
    requirements its evidence names. Parametrization brackets are dropped. Declarations (coverage, tier, notes,
    obligation) are not evidence."""
    missions = {m["id"]: m for m in manifest["missions"]}
    functions = {f["id"]: f for f in contract["functions"]}

    def requirement(ref: str) -> list[str]:
        mid, _, rid = ref.partition(".")
        mission = missions.get(mid) or {}
        req = next((r for r in mission.get("requirements", []) if r["id"] == rid), {})
        return list(req.get("tests", [])) + [n for link in mission.get("trace", []) for n in link.get("proof", [])]

    nodes = []
    for ref in ask.get("evidence", []) + _guards(ask):
        kind, _, name = ref.partition(":")
        if ref.startswith("tests/"):
            nodes.append(ref)
        elif kind == "mission":
            nodes += requirement(name)
        elif kind == "contract":
            for req_ref in (functions.get(name) or {}).get("evidence", []):
                nodes += requirement(req_ref)
    return sorted({re.sub(r"\[.*\]$", "", n) for n in nodes if n.startswith("tests/")})


def evidence_files(ask: dict, manifest: dict, contract: dict) -> list[str]:
    """The test files an ask's evidence reaches (``evidence_nodes`` without their node paths)."""
    return sorted({n.split("::")[0] for n in evidence_nodes(ask, manifest, contract)})


def node_text(text: str | None, node: str) -> str | None:
    """What a test node is, compared without its comments or layout: ``ast.dump`` of the named function or class
    (decorators, and so parametrize cases, included), and of the whole module for a node with no path. When a name
    is defined more than once the last definition is read, as pytest runs it. None when the file or the node is
    absent. A file that does not parse is its raw text: it collects nothing, which --collect reports."""
    if text is None:
        return None
    try:
        module = ast.parse(text)
    except SyntaxError:
        return text
    path = node.split("::")[1:]
    if not path:
        return ast.dump(module)
    scope, found = module.body, None
    for name in path:
        found = next((x for x in reversed(scope) if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef,
                                                                     ast.ClassDef)) and x.name == name), None)
        if found is None:
            return None
        scope = getattr(found, "body", [])
    return ast.dump(found)


def _met_at_base(base: tuple[dict, dict, dict], root: Path, source: Path | None) -> dict[str, bool]:
    """Whether each ask of the base map is met there. An ask the base withdrew by a record counts as open: it
    closed nothing, so reinstating it closes nothing either."""
    rows = {a["id"]: a["met"] for s in directive_report(*base, root=root)["sections"] for a in s["asks"]}
    return {a["id"]: rows.get(a["id"], False) for s in base[0]["sections"] for a in s["asks"]}


FOUNDER_AT_MERGE = "the founder's decision at merge, not a map edit that passes the check"
CLOSE_BUDGET = 5            # asks one change may close, and listed lines it may newly answer, before the founder decides
LINE_BUDGET = 20


def evidence_ratchet_problems(base: tuple[dict, dict, dict], head: tuple[dict, dict, dict], read_base, read_head,
                              root: Path = ROOT) -> list[str]:
    """The map against the map at a base, as an allow-list: what remains to build may shrink only through new or
    changed executable evidence. Each of ``base`` and ``head`` is (map, manifest, contract); ``read_base`` and
    ``read_head`` return a file's content at that side, or None.

    Evidence is the test nodes an ask reaches (``evidence_nodes``); it changed when one node's syntax tree
    (``node_text``: the test function or class with its decorators, or a whole-file node's module; comments and
    layout never count) differs from the base or did not exist there. Coverage, tiers, blockers,
    excerpts and lines, in the map or in a mission requirement, are declarations: editing them discharges nothing.

    Allowed without the founder:
    - closing: a live ask open at the base reads met at the head only through changed evidence of its own;
    - editing an open ask that stays open (the pin bounds its class);
    - a new ask pinned BUILDABLE_NOT_BUILT, met at the head only through changed evidence;
    - answering a listed line the base left unanswered with a live ask that is open and BUILDABLE_NOT_BUILT (a new
      obligation), or with a met ask whose own evidence changed;
    - guarding a PRINCIPLE that was UNGUARDED with a guard whose source changed.
    Refused, as the founder's decision at merge: any new or changed retirement (superseded_by or record), a new
    ask pinned other than BUILDABLE_NOT_BUILT, a new ``not_asks`` set-aside, and any change to the directive source
    or to the digest the map reads it against.

    Both sides are judged at the static ceiling (no test runs), as ``directive_report`` computes it. The rule asks
    for new evidence, not sufficient evidence: whether what changed answers the obligation stays the tiers' and the
    reviewers' to judge."""
    source_rel = SOURCE
    out = []
    if read_base(source_rel) != read_head(source_rel) or base[0].get("source") != head[0].get("source"):
        out.append(f"ratchet: the directive source {source_rel} or the digest the map reads it against changed; "
                   f"what the directive asks is {FOUNDER_AT_MERGE}")
    try:
        was_met = _met_at_base(base, root, None)
        texts = _source_texts(base[0], root)
        base_lines = {s["n"]: set(accounted_lines(s, texts[s["n"]][1])[0]) for s in base[0]["sections"]
                      if s["n"] in texts}
    except (KeyError, TypeError, ValueError) as exc:
        return out + [f"ratchet: the base map cannot be read by this tree's directive schema ({type(exc).__name__}: "
                      f"{exc}); migrate it before comparing"]
    rows = {a["id"]: a for s in directive_report(*head, root=root)["sections"] for a in s["asks"]}
    base_asks = {a["id"]: a for s in base[0]["sections"] for a in s["asks"]}
    pin_text = read_head(PIN.relative_to(ROOT).as_posix())
    head_pin = (json.loads(pin_text) if pin_text else {}).get("asks", {})

    def changed(ask: dict, nodes=None) -> bool:
        nodes = evidence_nodes(ask, head[1], head[2]) if nodes is None else nodes
        for node in nodes:
            path = node.split("::")[0]
            now = node_text(read_head(path), node)
            if now is not None and now != node_text(read_base(path), node):
                return True
        return False

    for section in head[0]["sections"]:
        for ask in section["asks"]:
            aid, row = ask["id"], rows.get(ask["id"]) or {}
            gone = ask.get("retired") or {}
            if aid not in base_asks:
                if gone:
                    out.append(f"ratchet: {aid} is new and retired at once; retiring an obligation is {FOUNDER_AT_MERGE}")
                elif head_pin.get(aid, "BUILDABLE_NOT_BUILT") != "BUILDABLE_NOT_BUILT":
                    out.append(f"ratchet: {aid} is new and pinned {head_pin[aid]}; a new ask is pinned "
                               f"BUILDABLE_NOT_BUILT, and taking one out of the build residual is {FOUNDER_AT_MERGE}")
                elif row.get("met") and not changed(ask):
                    out.append(f"ratchet: {aid} is new and reads met, but no test its own evidence reaches changed")
                continue
            then = base_asks[aid].get("retired") or {}
            if gone != then:
                if not was_met[aid] or gone:
                    out.append(f"ratchet: {aid}'s retirement changed ({then or 'live'} to {gone or 'live'}); "
                               f"retiring, re-pointing or withdrawing an obligation is {FOUNDER_AT_MERGE}")
                continue
            if gone or was_met[aid]:
                continue
            if row.get("met") and not changed(ask):
                out.append(f"ratchet: {aid} was open at the base and reads met at the head, but no test its own "
                           "evidence reaches changed: closing an ask needs new or changed evidence, not an edit to "
                           "its coverage, required tier or blocker, here or in a mission requirement")
            guard, prior = (ask.get("blocker") or {}).get("guarded_by"), \
                (base_asks[aid].get("blocker") or {}).get("guarded_by")
            if not row.get("met") and prior == UNGUARDED and isinstance(guard, list) and guard and \
                    not changed(ask, sorted({re.sub(r"\[.*\]$", "", g) for g in guard})):
                out.append(f"ratchet: {aid} was UNGUARDED at the base and names guards at the head, but no guard "
                           "changed: a standing rule is guarded by a test written for it, not by naming an existing one")
    out += _accounting_problems(base[0], head[0], base_lines, rows, changed, root)
    out += _budget_problems(base, head, base_asks, was_met, rows, base_lines, root)
    return out


def _budget_problems(base, head, base_asks, was_met, rows, base_lines, root) -> list[str]:
    """One change may discharge only a bounded amount on its own: changed evidence shows something new was written,
    not how much it answers, and one trivial test cited by every ask would otherwise close them all. Beyond
    CLOSE_BUDGET closed asks or LINE_BUDGET newly answered lines the change is the founder's at merge. An ask that
    closes in the change may not also take on listed lines the base left unanswered."""
    closed = [aid for aid, row in rows.items() if row.get("met") and not was_met.get(aid, False)
              and "retired" not in row]
    texts = _source_texts(head[0], root)
    answered = sum(len(set(accounted_lines(s, texts[s["n"]][1])[0]) - base_lines.get(s["n"], set()))
                   for s in head[0]["sections"] if s["n"] in texts)
    out = []
    if len(closed) > CLOSE_BUDGET:
        out.append(f"ratchet: this change closes {len(closed)} asks ({', '.join(sorted(closed)[:8])}"
                   f"{', ...' if len(closed) > 8 else ''}); more than {CLOSE_BUDGET} in one change is "
                   f"{FOUNDER_AT_MERGE}")
    if answered > LINE_BUDGET:
        out.append(f"ratchet: this change newly answers {answered} listed lines; more than {LINE_BUDGET} in one "
                   f"change is {FOUNDER_AT_MERGE}")
    for section in head[0]["sections"]:
        for ask in section["asks"]:
            if ask["id"] not in closed:
                continue
            prior = {_norm(x) for x in (base_asks.get(ask["id"]) or {}).get("lines", [])}
            added = [x for x in ask.get("lines", []) if _norm(x) not in prior]
            if added:
                out.append(f"ratchet: {ask['id']} closes in this change and also takes on {len(added)} listed "
                           "line(s); answer new lines with an open ask, and close it in a later change")
    return out


def _accounting_problems(base_doc: dict, head_doc: dict, base_lines: dict, rows: dict, changed,
                         root: Path) -> list[str]:
    """Listed lines answered at the head that the base left unanswered, claimed without a buildable obligation or
    new evidence: see ``evidence_ratchet_problems``."""
    texts = _source_texts(head_doc, root)
    base_aside = {s["n"]: {_norm(x["line"]) for x in s.get("not_asks", [])} for s in base_doc["sections"]}
    out = []
    for section in head_doc["sections"]:
        n = section["n"]
        if n not in texts or n not in base_lines:
            continue
        aside = {_norm(x["line"]) for x in section.get("not_asks", [])} - base_aside.get(n, set())
        for line in sorted(set(accounted_lines(section, texts[n][1])[0]) - base_lines[n]):
            claimants = [a for a in section["asks"] if "retired" not in a
                         and (line in {_norm(x) for x in a.get("lines", [])} or _core(line) in _norm(a["excerpt"]))]

            def answers(a: dict) -> bool:
                row = rows.get(a["id"]) or {}
                if row.get("met"):
                    return changed(a)
                return (row.get("blocker") or {}).get("class") == "BUILDABLE_NOT_BUILT"

            if any(answers(a) for a in claimants):
                continue
            out.append(f"ratchet: section {n}: the listed line {line[:80]!r} is newly "
                       + (f"set aside in not_asks; setting a line aside is {FOUNDER_AT_MERGE}" if line in aside
                          and not claimants else
                          "answered only by asks that are met with no changed evidence, retired, or open for a "
                          "reason building cannot close; answer it with an open BUILDABLE_NOT_BUILT ask, or with "
                          "evidence that changed"))
    return out


def read_at(ref: str, root: Path = ROOT):
    """A reader of files as committed at git ``ref`` (None for a file absent there), cached per path."""
    cache: dict[str, str | None] = {}

    def read(path: str) -> str | None:
        if path not in cache:
            shown = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=root, capture_output=True)
            cache[path] = shown.stdout.decode("utf-8", "replace") if shown.returncode == 0 else None
        return cache[path]
    return read


def read_tree(root: Path = ROOT):
    """A reader of files as they are in the working tree at ``root`` (None for a file absent there)."""
    def read(path: str) -> str | None:
        try:
            return (root / path).read_text(encoding="utf-8", errors="replace")
        except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
            return None
    return read


def map_at(ref: str, root: Path = ROOT) -> tuple[dict, dict, dict] | None:
    """(map, manifest, contract) as committed at git ``ref``, or None when the ref has no directive map."""
    read = read_at(ref, root)
    texts = [read(p.relative_to(ROOT).as_posix()) for p in (DIRECTIVE_MAP, MANIFEST, CONTRACT)]
    return None if any(t is None for t in texts) else tuple(json.loads(t) for t in texts)


def pin_at(ref: str, root: Path = ROOT) -> tuple[dict | None, str | None]:
    """The pin as committed at git ``ref``: (pin, None), (None, None) when the ref has no pin yet, or (None, why)
    when the ref cannot be read."""
    path = PIN.relative_to(ROOT).as_posix()
    if subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd=root,
                      capture_output=True).returncode:
        return None, f"pin: cannot read git ref {ref}"
    shown = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=root, capture_output=True, text=True)
    return (json.loads(shown.stdout), None) if shown.returncode == 0 else (None, None)


_NODES: dict[tuple, str | None] = {}


def _node_problem(node: str, root: Path) -> str | None:
    """node_problem, kept per node and the version of the file it names (a test file is parsed once per run), and a
    named function or class pytest would not collect as a test (a helper in a test file is not evidence)."""
    file = root / node.partition("::")[0]
    key = (str(root), node, file.stat().st_mtime_ns if file.is_file() else None)
    if key not in _NODES:
        _NODES[key] = node_problem(node, root)
        parts = [re.sub(r"\[.*\]$", "", p) for p in node.split("::")[1:]]
        if _NODES[key] is None and parts and not (
                parts[-1].startswith(("test", "Test")) and all(p.startswith("Test") for p in parts[:-1])):
            _NODES[key] = f"{node}: {parts[-1]} is not a test pytest collects"
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
    for node in _guards(ask):
        problem = _node_problem(node, root)
        if problem:
            out.append(f"{where}: guard {problem}")
        elif not any(e == node or covers(e, node) for e in nodes):
            out.append(f"{where}: guard {node} is not among the ask's own evidence")
    return out


def _claim_problems(where, ask, got, units, gaps, root) -> list[str]:
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
    if cls in RECORD_DEPENDENCIES:
        if "record" in blocker:
            problem = _record_problem(blocker["record"], cls, gaps, root)
            if problem:
                out.append(f"{where}: record {blocker['record']!r} {problem}")
        elif ask["required_tier"] in TEST_TIERS:
            out.append(f"{where}: a test can reach {ask['required_tier']}, so a {cls} blocker cites the record that "
                       f"holds it (gap:<mission>.<gap> or <path>#<verbatim text>)")
    elif "record" in blocker:
        out.append(f"{where}: only a FOUNDER_ONLY or EXTERNAL blocker cites a record")
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


def _record_problem(ref: str, cls: str | None, gaps: dict, root: Path, intent_only: bool = False) -> str | None:
    """Why ``ref`` does not hold a blocker (``cls``) or a retirement, or None. A record is an open missions.json gap
    building cannot close whose dependency fits the class (``gap:<mission>.<gap>``), or a file in this tree that
    holds the quoted words (``<path>#<verbatim text>``); a retirement needs a founder intent record (docs/intent/)."""
    if ref.startswith("gap:") and not intent_only:
        gap = gaps.get(tuple(ref[4:].split(".", 1)))
        if gap is None:
            return "names no missions.json gap"
        if gap["state"] != "OPEN" or gap["buildable_now"]:
            return "is not an open gap that building cannot close"
        if gap["dependency"] not in RECORD_DEPENDENCIES[cls]:
            return f"is a {gap['dependency']} gap, which does not hold a {cls} blocker"
        return None
    path, sep, words = ref.partition("#")
    if not sep or not words.strip():
        return "is neither gap:<mission>.<gap> nor <path>#<verbatim text>"
    if intent_only and not path.startswith("docs/intent/"):
        return "is not a founder intent record under docs/intent/"
    if path in (DIRECTIVE_MAP.relative_to(ROOT).as_posix(), PIN.relative_to(ROOT).as_posix()):
        return "is the map or its pin, which cannot hold its own claims"
    file = root / path
    if not file.is_file():
        return f"names no file ({path})"
    if _norm(words) not in _norm(file.read_text(encoding="utf-8", errors="replace")):
        return f"quotes words that are not in {path}"
    return None


def _retired_problems(where, ask, live, gaps, root) -> list[str]:
    """A retired ask stays in the map. It is superseded by a live ask that requires at least as much, or withdrawn
    by a founder intent record."""
    gone = ask["retired"]
    if ("superseded_by" in gone) == ("record" in gone):
        return [f"{where}: a retired ask names exactly one of superseded_by or record"]
    if "superseded_by" in gone:
        successor = live.get(gone["superseded_by"])
        if successor is None:
            return [f"{where}: superseded by {gone['superseded_by']}, which is not a live ask"]
        if rank(successor["required_tier"]) < rank(ask["required_tier"]):
            return [f"{where}: its successor {successor['id']} requires {successor['required_tier']}, less than "
                    f"{ask['required_tier']}"]
        return []
    problem = _record_problem(gone["record"], None, gaps, root, intent_only=True)
    return [f"{where}: retirement record {gone['record']!r} {problem}"] if problem else []


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
    met = "asks met in this run" if rep.get("ran") else "asks met at the static ceiling (no test ran)"
    return (f"directive: {s['sections']} sections ({status}); {s['asks_met']}/{s['asks']} {met}; "
            f"{s['build_residual']} open asks building can still close; {s['listed_lines_unaccounted']} listed lines "
            f"no ask answers yet; prompt completely built: {'yes' if s['prompt_completely_built'] else 'NO'}; "
            f"every section done: {'yes' if s['every_section_done'] else 'NO'}")


def print_report(rep: dict, doc: dict) -> None:
    units = {u["id"]: u for u in doc.get("units", [])}
    print(f"directive sections ({'tests ran' if rep['ran'] else 'static ceilings: no test ran'})")
    for section in rep["sections"]:
        met = sum(a["met"] for a in section["asks"])
        unread = len(section["unaccounted_lines"])
        print(f"  {section['n']:>2}. {section['status']:<7} {met}/{len(section['asks'])} asks met  "
              f"{section['heading']}" + (f"  [{unread} listed lines no ask answers yet]" if unread else ""))
        for a in section["asks"]:
            if a["met"]:
                continue
            b = a["blocker"] or {}
            why = b.get("class", "NO BLOCKER NAMED")
            why += f" {b['unit']}" if b.get("unit") else ""
            why += " UNGUARDED" if b.get("guarded_by") == UNGUARDED else ""
            why += " (its guard fell short in this run)" if a.get("guard_observed") else ""
            print(f"        {a['id']}: {a['tier']} of {a['required_tier']} ({a['coverage']}) -- {why}")
    s = rep["summary"]
    print("open asks by blocker: " + ", ".join(f"{k} {v}" for k, v in s["open_by_blocker"].items()))
    print("BUILDABLE_NOT_BUILT asks in dependency order:")
    for row in rep["buildable_in_dependency_order"]:
        title = units.get(row["unit"], {}).get("title", "no gap-map unit")
        asks = "prerequisite; no ask of its own" if row.get("prerequisite_only") else ", ".join(row["asks"])
        print(f"  {row['unit'] or '-'}: {title[:100]}  [{asks}]")
    print(summary_line(rep))


def load_map(path: Path = DIRECTIVE_MAP) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def defaults() -> tuple[dict, dict, dict]:
    return load_map(), load(MANIFEST), load(CONTRACT)
