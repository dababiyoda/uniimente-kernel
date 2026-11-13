#!/usr/bin/env python3
"""Work map: where the build stands, what is open to take, and who holds what.

Read-only. It writes only the files you name, posts nothing, locks nothing and
grants nothing. It joins sources that already exist:

- ``greg/path.json`` (the route) and ``acceptance/directive-sections.json`` (the
  77-section directive: buildable units in dependency order, at the static ceiling);
- ``foundry/completion.yaml`` (the 55 obligations) and ``scripts/mind_status.py``;
- open pull requests and their version-2 receipts (exact);
- work-board comments (heuristic, and labelled so).

Ask it before you edit::

    python scripts/work_map.py --github OWNER/REPO                       # the whole map
    python scripts/work_map.py --github OWNER/REPO --paths greg/missions.py
    python scripts/work_map.py --github OWNER/REPO --unit WU-11

``--prs-json`` and ``--comments-json`` replay saved API responses offline.
Without any of them it prints the position and the units, with no owners.

A snapshot, not a lock. A claim coordinates work; an expired one never permits
overwriting someone's files (``docs/collaboration/START_HERE.md``). What the
parser cannot resolve is listed as unresolved, never guessed. It always exits 0.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import branch_catalog  # noqa: E402
from repo_review import RECEIPT_MARKER as MARKER, _get, receipt_of  # noqa: E402,F401 - one reader, one client

LINE = branch_catalog.LINE
CHECKIN = "<!-- uniimente:checkin -->"

# The check-in a session posts on the work board before it edits. Printed by the map
# so the block has one source. Tolerantly parsed: older claims use other labels.
CHECKIN_BLOCK = """\
<!-- uniimente:checkin -->
## Check-in: <one-line outcome>
- Session: <actual session or task id> (<client>)
- Prompt: <what I was asked, one or two sentences; no secrets>
- Plan: <how, in 1-3 steps; what I will not do>
- Route: N3 | P5 | <unit id> | process   (greg/path.json)
- Guidance read: uniimente-kernel@<sha>
- Repository / branch / base → head: <owner/repo> · <branch> · <sha> → <sha>
- Files / interfaces: <paths in backticks>; read-only: <...>
- Depends on: <...>
- Overlap inspected and split: <what you inspected> (clear | split with <session> | blocked)
- Acceptance evidence: <...>
- Reviewer / integrator · Destination: <session or unassigned> · <branch> (draft #<n>)
- Next action / blocker / handoff condition: <...>
- Recheck (UTC): <YYYY-MM-DDTHH:MM:SSZ>"""

# The engineering target the founder set on 2026-11-12 (verbatim source in draft #295 until it is taken in:
# docs/intent/sources/CONVERGENCE-CLARIFICATION-2026-11-12-source.md). One dated line; a later founder
# direction replaces it here.
ENGINEERING_TARGET = ("a useful mission on one exact composed revision; then recovery under interruption and "
                      "changed evidence; then useful transfer to a materially different mission "
                      "(founder direction of 2026-11-12)")

# ------------------------------------------------------------------ identities

_IDS = [
    ("claude", re.compile(r"session_01[0-9A-Za-z]{22}(?![0-9A-Za-z])"), lambda m: m[0]),
    ("cursor", re.compile(r"bc-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|bc-[0-9a-f]{8}(?![0-9a-f-])"),
     lambda m: m[0][:11]),
    ("kimi", re.compile(r"(?<![\w/.-])kimi-[a-z0-9]+(?:-[a-z0-9]+)*-20\d{6}(?:-\d{2})?(?![\w.-])"),
     lambda m: m[0]),
    ("codex", re.compile(r"(?i:codex)\s+`?/root`?[,;]?\s+(?:workspace\s+)?(?:session\s+)?`?([0-9a-f]{12})`?"),
     lambda m: "codex:" + m[1]),
    ("codex", re.compile(r"(?i)codex[-/]root[-/]([0-9a-f]{12})"), lambda m: "codex:" + m[1]),
]
_TEAM = re.compile(r"\bUAT\b|\bHegemony\b|Provider-review session")
_AUTHOR_LABELS = {"implementer", "agent / claim", "agent", "identity", "session", "posted by", "from"}
_ADDRESSEE_LABELS = {"receiver", "next owner", "reviewer", "integration owner", "reviewer / integrator",
                     "reviewer / integrator · destination"}
_OPENING = re.compile(r"(?i)^\W*(?:session|implementer|from|posted by|agent)\b")
_TO = re.compile(r"(?i)\b(?:for|to|cc)\b[^.;:]{0,50}$")
_FROM = re.compile(r"(?i)\bfrom\b[^.;:]{0,50}$")


def identities(text: str) -> list[tuple[int, str, str]]:
    """(position, canonical id, client) for every session identity in ``text``, in order."""
    found = []
    for client, pattern, key in _IDS:
        found += [(m.start(), key(m), client) for m in pattern.finditer(text or "")]
    return sorted(found)


def canonical_identity(value: str | None) -> tuple[str | None, str]:
    """A receipt's ``session_id`` as (canonical id, client). An id in no known form is kept verbatim."""
    value = (value or "").strip()
    if not value:
        return None, "unknown"
    hits = identities(value)
    if hits:
        return hits[0][1], hits[0][2]
    prefix = re.match(r"(?i)(codex|kimi|cursor|claude|uat)\b", value)
    return value, (prefix[1].lower() if prefix else "other")


# ------------------------------------------------------------------ board comments

_HTML = re.compile(r"\A\s*(?:<!--.*?-->\s*)+", re.S)
_LABEL = re.compile(r"^\s*(?:[-*]\s+)?(?:\*\*([A-Z][^*\n]{0,70}?)[:.]?\*\*\s*:?|([A-Z][A-Za-z /()·>→-]{1,48}):(?=\s))", re.M)
_KINDS = [
    ("correction", r"correction"), ("acknowledgment", r"acknowledg"), ("intake", r"\bintake\b"),
    ("check-in", r"check-?in"), ("claim+handoff", r"claim.*handoff|handoff.*claim"),
    ("handoff", r"handoff|released into"), ("claim", r"\bclaims?\b"),
    ("update", r"update|status|landed|resumed|pause|continuation|heads-up"),
]
_RECHECK = re.compile(r"(?i)\bre-?check[^\n]{0,24}?(20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?Z)")
_RELEASE = re.compile(r"(?i)releases?\s+(?:the \w+ half of\s+)?claims?\s+`?(\d{10})|claim\s+`?(\d{10})`?\s+released")
_STOPPED = re.compile(r"(?i)delivery under claim `?(\d{10})`? is stopped")
_CLAIM_REF = re.compile(r"(?i)claim[s:]*\s*(?:comment\s+)?`?(\d{10})|issuecomment-(\d{10})|correction to `?(\d{10})")
_ROUTE = re.compile(r"greg/path\.json#(N(?:10|\d)|P(?:1[0-3]|\d)|process)\b")
_NODE = re.compile(r"\b(N(?:10|\d)|P(?:1[0-3]|\d))\b|\bprocess\b")
UNIT = re.compile(r"\b(?:WU|MU|MW)-[0-9A-Z]{1,2}\b|\b[SD]\d{1,2}-[A-Z]\b")
_NEGATIVE = re.compile(r"(?i)^\W*(?:no|not|do not|explicitly not|out of scope|read-only|excluded)\b|read-only|"
                       r"\bexcluded\b|\bnot touched\b")
_ALIASES = {
    "prompt": {"prompt", "founder request", "asked to", "request", "task / intended observable outcome", "task"},
    "plan": {"plan", "approach", "method"},
    "route": {"route", "gps node", "parent gps node"},
    "files": {"files", "files / interfaces", "files or interfaces owned", "files/interfaces", "scope",
              "bounded scope", "remaining scope"},
    "guidance": {"guidance read", "guidance revision"},
}


def heading_of(body: str) -> str:
    text = _HTML.sub("", body or "")
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def comment_kind(heading: str) -> str:
    low = heading.lower()
    return next((kind for kind, pat in _KINDS if re.search(pat, low)), "other")


def _norm(label: str) -> str:
    return re.split(r"[,(]", label.lower())[0].strip(" *:.")


def fields(body: str) -> dict[str, str]:
    """Labelled segments of a comment: ``{normalized label: text up to the next label}``."""
    body = body or ""
    marks = [(m.start(), m.end(), _norm(m[1] or m[2])) for m in _LABEL.finditer(body)]
    out: dict[str, str] = {}
    for i, (_, end, label) in enumerate(marks):
        stop = marks[i + 1][0] if i + 1 < len(marks) else len(body)
        out.setdefault(label, body[end:stop].strip())
    return out


def _field(found: dict[str, str], name: str) -> str:
    """The first segment whose label is an alias of ``name``. Labels match whole, never by prefix, except that
    every label beginning "files" names files ("files / interfaces claimed", "files or interfaces owned")."""
    return next((found[a] for a in found if a in _ALIASES[name] or (name == "files" and a.startswith("files"))), "")


def declared_files(text: str, tracked: set[str], dirs: set[str]) -> list[str]:
    """Backticked repository paths in a files/scope field, without the lines that exclude them."""
    keep = []
    for line in re.split(r"\n|(?<=[.;])\s+", text or ""):
        if _NEGATIVE.search(line):
            continue
        for token in re.findall(r"`([^`\n]+)`", line):
            token = token.strip().rstrip("/") if token.strip().rstrip("/") in dirs else token.strip()
            known = token in tracked or token in dirs
            fresh = "/" in token and "." in token.rsplit("/", 1)[-1] and token.split("/")[0] in dirs
            if (known or fresh) and " " not in token and token not in keep:
                keep.append(token)
    return keep


def comment_author(body: str) -> dict:
    """Who wrote a board comment, from its heading or a labelled line. Never the first id in the body.

    Returns ``author`` (None when unresolved), ``client``, ``how`` and the ``addressees`` it names.
    """
    body = body or ""
    heading = heading_of(body)
    addressees, author = [], None
    for at, key, client in identities(heading):
        before = heading[:at]
        if _TO.search(before) and not _FROM.search(before):
            addressees.append(key)
        elif author is None:
            author = (key, client, "heading")
    if author is None:
        for line in _HTML.sub("", body).splitlines():
            m = _LABEL.match(line)
            if not m:
                continue
            label, hits = _norm(m[1] or m[2]), identities(line)
            if label in _ADDRESSEE_LABELS:
                addressees += [h[1] for h in hits]
            elif label in _AUTHOR_LABELS and hits and author is None:
                author = (hits[0][1], hits[0][2], "label")
    lead = _HTML.match(body)
    if author is None:                                   # "Session `...`." as the comment's opening line
        rest = [ln for ln in _HTML.sub("", body).splitlines() if ln.strip()][1:2]
        hits = identities(rest[0]) if rest and _OPENING.match(rest[0]) else []
        if hits:
            author = (hits[0][1], hits[0][2], "opening line")
    if author is None and lead:                          # a leading marker that carries the task's own id
        hits = identities(lead[0])
        if hits:
            author = (hits[0][1], hits[0][2], "marker")
    team = _TEAM.search(heading)
    return {"author": author[0] if author else None, "client": author[1] if author else "unknown",
            "how": author[2] if author else "unresolved", "addressees": sorted(set(addressees)),
            "team": team[0] if team else None,
            "marker": next(iter(re.findall(r"<!--\s*(UNIIMENTE-[A-Za-z0-9-]+)\s*-->", lead[0] if lead else "")), None)}


def parse_comment(c: dict, tracked: set[str], dirs: set[str]) -> dict:
    body = c.get("body") or ""
    found, heading = fields(body), heading_of(body)
    who = comment_author(body)
    route = _field(found, "route")
    node = _ROUTE.search(body)
    in_label = (_NODE.search(route) or UNIT.search(route)) if route else None
    recheck = _RECHECK.search(body)
    refs = [next(g for g in m.groups() if g) for m in _CLAIM_REF.finditer(body[:600])]
    draft = re.search(r"(?i)(?:draft(?:\s+PR)?|handoff:?|\bPR)\s*\[?#(\d+)", heading)
    return {
        "cid": c.get("id"), "at": c.get("created_at", ""), "heading": heading[:160],
        "kind": comment_kind(heading), **who,
        "prompt": _field(found, "prompt")[:400], "plan": _field(found, "plan")[:400],
        "route": node[1] if node else (in_label[0] if in_label else None),
        "guidance": _field(found, "guidance")[:160],
        "files": declared_files(_field(found, "files"), tracked, dirs),
        "recheck": recheck[1] if recheck else None,
        "releases": [next(g for g in m.groups() if g) for m in _RELEASE.finditer(body)],
        "stops": [m[1] for m in _STOPPED.finditer(body)],
        "claim_refs": refs, "draft_pr": int(draft[1]) if draft else None,
        "is_checkin": CHECKIN in body, "marker": who["marker"],
    }


def issue_comments(repo: str, issue: int, token: str | None) -> list[dict]:
    out, page = [], 1
    while True:
        batch = _get(f"https://api.github.com/repos/{repo}/issues/{issue}/comments?per_page=100&page={page}", token)
        out += batch
        if len(batch) < 100:
            return out
        page += 1


# ------------------------------------------------------------------ position

def _try(fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - a missing source is reported, never fatal
        return {"not_run": f"{type(exc).__name__}: {exc}"[:200]}


def _route(root: Path) -> dict:
    from greg import path as gp
    data = gp.load(root / "greg" / "path.json")
    pos = gp.position(None, data)
    cortex = next(iter(data.get("subordinate_workstreams", {}).values()), {})
    return {"destination": data["destination"], "boundary": data.get("completion_boundary", {}).get("product"),
            "acceptance_node": {"id": pos["active"]["id"], "title": pos["active"]["title"]} if pos.get("active") else None,
            "achieved": pos.get("achieved", []),
            "founder_use_gate": data.get("completion_boundary", {}).get("founder_use_gate"),
            "nodes": [n["id"] for n in data["nodes"]], "mind_nodes": [n["id"] for n in cortex.get("nodes", [])]}


def _directive(root: Path) -> dict:
    from acceptance import directive
    load = lambda p: json.loads((root / "acceptance" / p).read_text())  # noqa: E731
    doc = load("directive-sections.json")
    rep = directive.directive_report(doc, load("missions.json"), load("completion-contract.json"), None, root)
    units = {u["id"]: u for u in doc.get("units", [])}
    asks = {a["id"]: a for s in rep["sections"] for a in s["asks"]}
    paths = {a["id"]: a.get("owner_paths", []) for s in doc["sections"] for a in s["asks"]}
    open_units = {row["unit"] for row in rep["buildable_in_dependency_order"] if row["unit"]}
    rows = []
    for row in rep["buildable_in_dependency_order"]:
        unit = units.get(row["unit"] or "", {})
        waits = [d for d in unit.get("depends_on", []) if d in open_units]
        tiers = sorted({(f"{asks[a]['tier']} -> {asks[a]['required_tier']}" if asks[a]["tier"] != asks[a]["required_tier"]
                         else f"{asks[a]['tier']} ({asks[a].get('coverage', 'partial')})")
                        for a in row["asks"] if a in asks})
        rows.append({"unit": row["unit"], "title": unit.get("title", "asks with no gap-map unit"),
                     "asks": row["asks"], "prerequisite_only": bool(row.get("prerequisite_only")),
                     "waits_on": waits, "evidence": tiers,
                     "owner_paths": sorted({p for a in row["asks"] for p in paths.get(a, [])})})
    return {"ran_tests": rep["ran"], "summary": rep["summary"], "units": rows}


def _foundry(root: Path) -> dict:
    from foundry import completion
    s = completion.status()
    return {"complete": s["complete"], "by_state": {k: len(v) for k, v in s["by_state"].items()}}


def _mind(root: Path) -> dict:
    out = subprocess.run([sys.executable, "-B", "scripts/mind_status.py"], cwd=root, capture_output=True, text=True,
                         timeout=120, env={**os.environ, "PYTHONPATH": str(root)})
    return json.loads(out.stdout)["counts"]


def _intents(root: Path, top: int = 4) -> list[dict]:
    rows = []
    for f in sorted((root / "docs" / "intent").glob("INTENT-2026*.json"), reverse=True):
        try:
            d = json.loads(f.read_text())
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("intent_id"):
            rows.append({"id": d["intent_id"], "title": (d.get("title") or d.get("statement") or "")[:140],
                         "state": d.get("state", "")})
    rows.sort(key=lambda r: re.sub(r"\D", "", r["id"])[:8], reverse=True)
    return rows[:top]


def route_drift(root: Path, route: dict) -> dict:
    """Node ids on ``greg/path.json`` that the hand-written route table in BACKCAST_GPS.md does not name."""
    doc = root / "docs" / "BACKCAST_GPS.md"
    text = doc.read_text() if doc.exists() else ""
    m = re.search(r"^## Current full-machine route\n(.*?)(?=^## Preserved|\Z)", text, re.S | re.M)
    if not m:
        return {"section": False, "missing": []}
    section = m[1]
    named = set(re.findall(r"\b[NP]\d{1,2}\b", section))
    for letter, lo, hi in re.findall(r"\b([NP])(\d{1,2})\s*[–-]\s*[NP](\d{1,2})\b", section):
        named |= {f"{letter}{i}" for i in range(int(lo), int(hi) + 1)}
    wanted = route.get("nodes", []) + route.get("mind_nodes", [])
    return {"section": True, "missing": [n for n in wanted if n not in named]}


def line_checks(rows: list[dict], root: Path, line: str = LINE) -> dict:
    """How pushes to the line get checked: by a workflow's push filter, or only through a PR whose head is the line."""
    text = (root / ".github" / "workflows" / "canonical-ci.yml")
    found = re.search(r"^  push:\s*\n\s+branches:\s*\[([^\]]*)\]", text.read_text(), re.M) if text.exists() else None
    pushed = [b.strip().strip("'\"") for b in found[1].split(",")] if found else []
    carriers = sorted(r["pr"] for r in rows if r["head"] == line)
    return {"push_branches": pushed, "pull_requests_with_line_as_head": carriers,
            "covered": line in pushed or bool(carriers)}


def position(root: Path = ROOT) -> dict:
    route = _try(lambda: _route(root))
    return {"route": route, "directive": _try(lambda: _directive(root)), "foundry": _try(lambda: _foundry(root)),
            "mind": _try(lambda: _mind(root)), "latest_intents": _try(lambda: _intents(root)),
            "route_drift": _try(lambda: route_drift(root, route if "nodes" in route else {}))}


# ------------------------------------------------------------------ the join

def _when(stamp: str | None) -> datetime | None:
    try:
        return datetime.strptime((stamp or "")[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def activity(last: str | None, now: datetime) -> str:
    seen = _when(last)
    if not seen:
        return "UNKNOWN"
    hours = (now - seen).total_seconds() / 3600
    return "ACTIVE" if hours < 48 else "QUIET" if hours < 168 else "DORMANT"


def changed_files(pr: dict, root: Path) -> list[str] | None:
    """Files the PR changes against its base, from local git; None when the refs are not here."""
    r = subprocess.run(["git", "diff", "--name-only", f"origin/{pr['base']['ref']}...{pr['head']['sha']}"],
                       cwd=root, capture_output=True, text=True)
    return [f for f in r.stdout.splitlines() if f] if r.returncode == 0 else None


def _covers(declared: str, path: str) -> bool:
    declared, path = declared.rstrip("/*"), path.rstrip("/")
    return declared == path or path.startswith(declared + "/") or declared.startswith(path + "/")


def pr_rows(prs: list[dict], root: Path, use_git: bool = True) -> list[dict]:
    rows = []
    for p in prs:
        if p.get("state") != "open":
            continue
        r = receipt_of(p.get("body"))
        coord = (r or {}).get("coordination") if isinstance((r or {}).get("coordination"), dict) else {}
        sid, client = canonical_identity(coord.get("session_id"))
        text = f"{p.get('title') or ''}\n{(p.get('body') or '')[:1500]}"
        refs = " ".join(x for x in (r or {}).get("intent_refs", []) if isinstance(x, str))
        node = _ROUTE.search(refs)
        declared = [f for f in coord.get("files", []) if isinstance(f, str)]
        rows.append({
            "pr": p["number"], "title": (p.get("title") or "")[:110], "base": p["base"]["ref"],
            "head": p["head"]["ref"], "head_sha": p["head"]["sha"], "draft": bool(p.get("draft")),
            "updated": p.get("updated_at", ""), "receipt": r is not None,
            "session": sid, "client": client, "task_ref": coord.get("task_ref"),
            "files": declared, "changed": changed_files(p, root) if use_git else None,
            "overlap": (coord.get("overlap") or {}).get("status") if isinstance(coord.get("overlap"), dict) else None,
            "recheck": coord.get("recheck_at"), "scope": ((r or {}).get("scope") or "")[:200],
            "units": sorted(set(UNIT.findall(p.get("title") or "")) or set(UNIT.findall(refs))
                            or set(UNIT.findall(text))),
            "route": node[1] if node else None,
        })
    return rows


def line_bound(rows: list[dict], line: str = LINE) -> list[dict]:
    """Open PRs whose work is headed for the line: based on it, or stacked on a PR that is.

    The integration PR itself (its head is the line) and composed ``candidate/`` heads are left out: each
    carries everyone's files, so counting it would make every file look contended.
    """
    by_head = {r["head"]: r for r in rows}

    def reaches(r: dict, depth: int = 0) -> bool:
        if r["base"] == line:
            return True
        parent = by_head.get(r["base"])
        return bool(parent) and parent is not r and depth < 12 and reaches(parent, depth + 1)
    return [r for r in rows if r["head"] != line and not r["head"].startswith("candidate/") and reaches(r)]


def contended(rows: list[dict], line: str = LINE) -> list[dict]:
    """Files that line-bound PRs from two or more sessions declare or change. One session's stack is not contention."""
    holders: dict[str, dict[str, set[int]]] = {}
    for r in line_bound(rows, line):
        who = r["session"] or f"(no receipt) #{r['pr']}"
        for f in set(r["files"]) | set(r["changed"] or []):
            holders.setdefault(f, {}).setdefault(who, set()).add(r["pr"])
    out = [{"file": f, "sessions": len(by), "prs": sorted({n for ns in by.values() for n in ns}),
            "holders": {s: sorted(ns) for s, ns in sorted(by.items())}}
           for f, by in holders.items() if len(by) > 1]
    return sorted(out, key=lambda x: (-x["sessions"], -len(x["prs"]), x["file"]))


def who_touches(paths: list[str], rows: list[dict], claims: list[dict]) -> list[dict]:
    hits = []
    for path in paths:
        prs = [r for r in rows if any(_covers(f, path) for f in set(r["files"]) | set(r["changed"] or []))]
        cl = [c for c in claims if any(_covers(f, path) for f in c["files"])]
        hits.append({"path": path,
                     "prs": [{"pr": r["pr"], "session": r["session"], "base": r["base"], "overlap": r["overlap"],
                              "title": r["title"]} for r in prs],
                     "claims": [{"comment": c["comment"], "session": c["session"], "at": c["at"],
                                 "state": c["state"]} for c in cl]})
    return hits


def build(prs: list[dict] | None, comments: list[dict] | None, *, root: Path = ROOT, line: str = LINE,
          now: datetime | None = None, use_git: bool = True) -> dict:
    now = now or datetime.now(timezone.utc)
    tracked = set(branch_catalog._git("ls-files", root=root).splitlines())
    dirs = {"/".join(f.split("/")[:i]) for f in tracked for i in range(1, f.count("/") + 1)}
    pos = position(root)
    rows = pr_rows(prs or [], root, use_git)
    by_pr = {r["pr"]: r for r in rows}

    parsed = [parse_comment(c, tracked, dirs) for c in comments or []]
    by_id = {c["cid"]: c for c in parsed}
    for _ in range(2):                                  # joins, each labelled; twice so a chain resolves
        for c in parsed:
            if c["author"]:
                continue
            ref = next((by_id[int(x)] for x in c["claim_refs"]
                        if int(x) in by_id and int(x) != c["cid"] and by_id[int(x)]["author"]), None)
            pr = by_pr.get(c["draft_pr"]) if c["draft_pr"] else None
            plain = not re.search(r"(?i)review|intake|acknowledg", c["heading"]) and not c["team"]
            twin = next((o for o in parsed if c["marker"] and o["marker"] == c["marker"] and o["author"]), None)
            task = next((r for r in rows if r["session"] and r["task_ref"] and str(c["cid"]) in str(r["task_ref"])
                         and c["kind"] in ("claim", "check-in", "claim+handoff")), None)
            if ref:
                c.update(author=ref["author"], client=ref["client"], how="claim reference")
            elif twin:
                c.update(author=twin["author"], client=twin["client"], how="shared marker")
            elif pr and pr["session"] and plain:
                c.update(author=pr["session"], client=pr["client"], how="pr receipt")
            elif task and plain:
                c.update(author=task["session"], client=task["client"], how="pr task_ref")
    released = {x for c in parsed for x in c["releases"]}
    stopped = {x for c in parsed for x in c["stops"]}

    sessions: dict[str, dict] = {}

    def slot(key: str, client: str) -> dict:
        return sessions.setdefault(key, {"session": key, "client": client, "prs": [], "comments": 0, "last": "",
                                         "prompt": "", "plan": "", "route": None, "overlap": set(), "checkin": None})

    for r in rows:
        if r["session"]:
            s = slot(r["session"], r["client"])
            s["prs"].append(r["pr"])
            s["last"] = max(s["last"], r["updated"])
            if r["overlap"]:
                s["overlap"].add(r["overlap"])
            s["route"] = s["route"] or r["route"]
    claims = []
    for c in sorted(parsed, key=lambda x: x["at"]):
        who = c.get("author")
        if who:
            s = slot(who, c["client"])
            s["comments"] += 1
            s["last"] = max(s["last"], c["at"])
            if c["prompt"]:
                s["prompt"] = c["prompt"]
            if c["plan"]:
                s["plan"] = c["plan"]
            s["route"] = c["route"] or s["route"]
            if c["kind"] in ("claim", "check-in", "claim+handoff"):
                s["checkin"] = c["cid"]
        if c["kind"] in ("claim", "check-in", "claim+handoff") and c["files"]:
            cid = str(c["cid"])
            state = "released" if cid in released else "stopped" if cid in stopped else activity(c["at"], now).lower()
            has_pr = any(r["task_ref"] and cid in str(r["task_ref"]) for r in rows)
            claims.append({"comment": c["cid"], "session": who, "at": c["at"], "files": c["files"],
                           "recheck": c["recheck"], "state": state, "has_pr": has_pr, "heading": c["heading"]})

    units = pos["directive"].get("units", []) if isinstance(pos["directive"], dict) else []
    bound = line_bound(rows, line)
    for u in units:
        named = [r for r in rows if u["unit"] and u["unit"] in r["units"]]
        near = [r for r in bound if r not in named and u["owner_paths"]
                and any(_covers(f, p) for f in set(r["files"]) | set(r["changed"] or []) for p in u["owner_paths"])]
        u["owners"] = [{"pr": r["pr"], "session": r["session"], "base": r["base"]} for r in named]
        u["also_touching_its_files"] = sorted({r["pr"] for r in near})
        u["state"] = ("claimed" if named else "waits" if u["waits_on"] else "unclaimed")

    live = [s for s in sessions.values() if activity(s["last"], now) in ("ACTIVE", "QUIET")]
    recent = [c for c in parsed if activity(c["at"], now) in ("ACTIVE", "QUIET")]
    return {
        "generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "line": line, "authority": "none",
        "sources": {"open_prs": len(rows), "line_bound_prs": len(bound), "board_comments": len(parsed),
                    "git_diffs": sum(r["changed"] is not None for r in rows)},
        "position": pos, "units": units, "contended": contended(rows, line),
        "sessions": sorted(({**s, "overlap": sorted(s["overlap"]), "activity": activity(s["last"], now)}
                            for s in sessions.values()), key=lambda s: s["last"], reverse=True),
        "claims_without_pr": [c for c in claims if not c["has_pr"] and c["state"] in ("active", "quiet")],
        "dormant_claims_without_pr": sum(not c["has_pr"] and c["state"] == "dormant" for c in claims),
        "line_checks": _try(lambda: line_checks(rows, root, line)),
        "gaps": {
            "open_prs_without_receipt": sorted(r["pr"] for r in rows if not r["receipt"]),
            "open_prs_without_receipt_into_line": sorted(r["pr"] for r in rows if not r["receipt"] and r["base"] == line),
            "recent_posts_unresolved": [{"comment": c["cid"], "at": c["at"], "heading": c["heading"], "team": c["team"]}
                                        for c in recent if not c.get("author")],
            "recent_posts": len(recent),
            "live_sessions": len(live),
            "live_sessions_stating_prompt": sum(bool(s["prompt"]) for s in live),
            "live_sessions_stating_plan": sum(bool(s["plan"]) for s in live),
            "live_sessions_stating_route": sum(bool(s["route"]) for s in live),
        },
        "prs": rows, "claims": claims,
    }


# ------------------------------------------------------------------ rendering

def _cell(text) -> str:
    return str(text if text is not None else "").replace("|", "\\|").replace("\n", " ")[:150]


def markdown(m: dict) -> str:
    pos, g = m["position"], m["gaps"]
    route, dire = pos["route"], pos["directive"]
    out = [
        "# Work map", "",
        f"Generated by `scripts/work_map.py` at {m['generated']} against `{m['line']}`. A snapshot, not a lock, "
        "and no authority. Receipts and git diffs are exact. Work-board comments are parsed heuristically: the "
        "board shares one GitHub login, so a comment's author is what the comment says it is. What could not be "
        "resolved is listed under Gaps. Regenerate it; do not hand-edit it.", "",
        f"Sources: {m['sources']['open_prs']} open pull requests ({m['sources']['line_bound_prs']} headed for the "
        f"line), {m['sources']['board_comments']} board comments, {m['sources']['git_diffs']} pull requests with a "
        "local git diff.", "",
        "## 1. Position", "",
    ]
    if "not_run" in route:
        out += [f"Route: not read ({route['not_run']}).", "", "| | |", "|---|---|"]
    else:
        node = route["acceptance_node"] or {}
        out += [f"**Destination ({route['boundary']}).** {route['destination']}", "",
                "| | |", "|---|---|",
                f"| Achieved on the route | {', '.join(route['achieved']) or 'none'} (as the route file attests) |",
                f"| Acceptance node | `{node.get('id')}`: {_cell(node.get('title'))}. Its exit needs founder-tier "
                "evidence; nothing here measures it |",
                f"| Does it block building? | No. {_cell(route['founder_use_gate'])} |"]
    out += [f"| Engineering target | {ENGINEERING_TARGET}. A declared target, not a measured result |"]
    if "not_run" in dire:
        out += [f"| Directive | not read ({_cell(dire['not_run'])}) |"]
    else:
        s = dire["summary"]
        status = ", ".join(f"{k} {v}" for k, v in s["by_status"].items())
        out += [f"| Directive ({s['sections']} sections) | {status}; {s['asks_met']} of {s['asks']} asks met at the "
                f"{'run' if dire['ran_tests'] else 'static ceiling (no test ran)'}; "
                f"{s['open_by_blocker'].get('BUILDABLE_NOT_BUILT', 0)} open asks building can close, "
                f"{s['open_by_blocker'].get('FOUNDER_ONLY', 0)} founder-only, "
                f"{s['open_by_blocker'].get('EXTERNAL', 0)} external |"]
    f, mind = pos["foundry"], pos["mind"]
    out += [f"| Foundry obligations | {f.get('complete', 'not read')} complete (bounded local evidence) |",
            "| Mind mechanisms | " + (", ".join(f"{k} {v}" for k, v in mind.items()) if "not_run" not in mind
                                      else "not read") + " |"]
    intents = pos["latest_intents"]
    if isinstance(intents, list) and intents:
        out += ["", "Latest founder intent records on this tree (a newer one may be pending in an open PR):", ""]
        out += [f"- `{i['id']}` ({i['state']}): {_cell(i['title'])}" for i in intents]

    out += ["", "## 2. Next eligible work, in dependency order", "",
            "Units come from `acceptance/directive-sections.json`. *Claimed* means an open pull request names the "
            "unit. *Unclaimed* means none does: read the newest board comments before you take it.", "",
            "| Unit | What it builds | Closes | Evidence: now -> required | State | Owner | Also touching its files |",
            "|---|---|---|---|---|---|---|"]
    for u in m["units"]:
        owner = ", ".join(f"#{o['pr']}" for o in u["owners"]) or ""
        state = u["state"] + (f" (waits on {', '.join(u['waits_on'])})" if u["waits_on"] else "")
        closes = ", ".join(u["asks"][:4]) + (f" +{len(u['asks']) - 4}" if len(u["asks"]) > 4 else "")
        out.append(f"| `{u['unit'] or '-'}` | {_cell(u['title'])} | {closes or 'prerequisite'} | "
                   f"{_cell('; '.join(u['evidence']))} | {state} | {owner} | "
                   f"{', '.join('#%d' % n for n in u['also_touching_its_files'][:6])} |")

    out += ["", "## 3. Before you edit: contended files", "",
            "Files that pull requests headed for the line, from two or more sessions, declare or change. "
            "The integration PR and composed candidates are left out.", "",
            "| File | Sessions | Pull requests |", "|---|---:|---|"]
    out += [f"| `{_cell(c['file'])}` | {c['sessions']} | {', '.join('#%d' % n for n in c['prs'][:14])} |"
            for c in m["contended"][:40]]
    if len(m["contended"]) > 40:
        out.append(f"| ... | | {len(m['contended']) - 40} more: run with `--json` |")

    out += ["", "## 4. Active sessions", "",
            "| Session | Client | Last activity | Asked to | Plan | Route | Open PRs | Overlap declared |",
            "|---|---|---|---|---|---|---|---|"]
    for s in m["sessions"]:
        if s["activity"] == "DORMANT":
            continue
        out.append(f"| `{_cell(s['session'])}` | {s['client']} | {s['activity']} {s['last'][:16]} | "
                   f"{_cell(s['prompt'])} | {_cell(s['plan'])} | {_cell(s['route'] or '')} | "
                   f"{', '.join('#%d' % n for n in sorted(s['prs'])[:12])}"
                   f"{' +%d' % (len(s['prs']) - 12) if len(s['prs']) > 12 else ''} | {', '.join(s['overlap'])} |")
    dormant = sum(s["activity"] == "DORMANT" for s in m["sessions"])
    out += ["", f"{dormant} dormant sessions (no activity for 7 days) are in the JSON output."]

    out += ["", "## 5. Gaps: documented is not demonstrated", "",
            f"- Open pull requests without a receipt: {len(g['open_prs_without_receipt'])} "
            f"({len(g['open_prs_without_receipt_into_line'])} of them into the line).",
            f"- Sessions active in the last 7 days: {g['live_sessions']}. Stating their prompt: "
            f"{g['live_sessions_stating_prompt']}; their plan: {g['live_sessions_stating_plan']}; "
            f"a route node or unit: {g['live_sessions_stating_route']}.",
            f"- Board posts in the last 7 days whose author could not be resolved: "
            f"{len(g['recent_posts_unresolved'])} of {g['recent_posts']}.",
            _checks_line(m), "",
            "Claims with no pull request (active in the last 7 days):", "",
            "| Comment | Session | Posted | Files declared | Recheck | State |", "|---|---|---|---|---|---|"]
    out += [f"| {c['comment']} | `{_cell(c['session'] or 'unresolved')}` | {c['at'][:16]} | "
            f"{_cell(', '.join('`%s`' % f for f in c['files'][:6]))} | {c['recheck'] or 'event-based'} | {c['state']} |"
            for c in m["claims_without_pr"][-25:]]
    out += ["", f"{m['dormant_claims_without_pr']} older claims with no pull request and no activity for 7 days "
            "are in the JSON output. A dormant claim is still not permission to overwrite."]

    drift = pos["route_drift"]
    out += ["", "## 6. Route drift", ""]
    if not isinstance(drift, dict) or "not_run" in drift:
        out += ["Not read."]
    elif not drift.get("section"):
        out += ["This tree has no current-route section in `docs/BACKCAST_GPS.md` to compare with `greg/path.json`."]
    elif drift["missing"]:
        out += [f"`docs/BACKCAST_GPS.md` does not name these nodes of `greg/path.json`: {', '.join(drift['missing'])}."]
    else:
        out += ["None: the route table in `docs/BACKCAST_GPS.md` names every node of `greg/path.json`."]

    out += ["", "## The check-in", "", "Post this on the work board before you edit, and again when you resume:", "",
            "```text", CHECKIN_BLOCK, "```", ""]
    return "\n".join(out)


def _checks_line(m: dict) -> str:
    c = m.get("line_checks") or {}
    if "not_run" in c or not m["sources"]["open_prs"]:
        return "- Checks on pushes to the line: not read."
    if m["line"] in c["push_branches"]:
        return "- Checks on pushes to the line: Canonical CI runs on push to the line."
    if c["pull_requests_with_line_as_head"]:
        prs = ", ".join("#%d" % n for n in c["pull_requests_with_line_as_head"])
        return (f"- Checks on pushes to the line: only through the pull-request runs of {prs} (its head is the line). "
                "If it closes, pushes to the line run no Canonical CI.")
    return ("- Checks on pushes to the line: **none**. No open pull request has the line as its head, and "
            "`canonical-ci.yml` does not run on push to it.")


def _load(paths: list[Path] | None) -> list[dict] | None:
    if not paths:
        return None
    out: list[dict] = []
    for p in paths:
        data = json.loads(Path(p).read_text())
        out += data if isinstance(data, list) else [data]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--github", metavar="OWNER/REPO")
    ap.add_argument("--board", type=int, default=96)
    ap.add_argument("--prs-json", type=Path, action="append")
    ap.add_argument("--comments-json", type=Path, action="append")
    ap.add_argument("--line", default=LINE)
    ap.add_argument("--now", help="UTC time to judge activity against, YYYY-MM-DDTHH:MM:SSZ")
    ap.add_argument("--markdown", type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--paths", nargs="+", metavar="FILE", help="who touches these files?")
    ap.add_argument("--unit", help="is this unit taken?")
    a = ap.parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN")
    prs, comments, note = _load(a.prs_json), _load(a.comments_json), None
    try:
        if a.github and prs is None:
            prs = branch_catalog.pull_requests(a.github, token)
        if a.github and comments is None:
            comments = issue_comments(a.github, a.board, token)
    except Exception as exc:  # noqa: BLE001 - the map still prints what it can
        note = f"GitHub not read ({type(exc).__name__}: {exc})"[:200]
    m = build(prs, comments, line=a.line, now=_when(a.now) if a.now else None)
    if note:
        m["sources"]["note"] = note
    if a.json:
        a.json.write_text(json.dumps(m, indent=1, default=sorted) + "\n")
    if a.markdown:
        a.markdown.write_text(markdown(m) + "\n")
    if a.paths:
        print(json.dumps(who_touches(a.paths, m["prs"], m["claims"]), indent=1))
    elif a.unit:
        print(json.dumps([u for u in m["units"] if u["unit"] == a.unit], indent=1))
    elif not (a.json or a.markdown):
        print(markdown(m))
    if note:
        print(note, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
