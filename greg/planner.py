"""Founder intent -> mission proposal. A proposal is data; only a founder signature makes it a MISSION.

This is how Alfonso talks to GREG in plain words instead of hand-writing mission JSON.
Two routes behind one interface (governed pluralism, cheapest first):

1. **Template route** (deterministic, zero model calls, always available): recognizes
   the missions GREG already knows how to run and fills their parameters from what
   the body can see (Git repositories under its read roots, their GitHub remotes).
2. **Model route** (optional): a model drafts a mission against the real capability
   inventory through the one ``greg.models`` router. Open-source-first: only a route the
   founder selected is used, normally a locally served open model (Ollama); paid APIs or
   the Claude Code CLI are used only when the founder's own selection names them.

Every model draft is vetted before Alfonso sees it: it must satisfy the mission
contract, name only registered capabilities (or a function, which Capability Genesis
can acquire), and it is clamped to a read-only light cone with zero budget and at
most a seven-day horizon. The founder's own words replace whatever the model wrote
as ``founder_expression``. Anything consequential then stops at an approval boundary.
Models propose; the founder signs; the Gate decides. Nothing here grants authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

from greg import models, templates
from greg.missions import MissionError, validate_mission

PLANNER = "greg.planner/1"
MAX_HORIZON = timedelta(days=7)
DAILY = re.compile(r"\b(every|each)\s+(morning|day|night)\b|\bdaily\b|\bnightly\b", re.I)
BRIEF = re.compile(r"\b(brief|pull requests?|prs?|ci|checks?|failing|stale|state of (my )?(repos|repositories)|"
                   r"what needs my (attention|decision))\b", re.I)
GUARD = re.compile(r"\b(pins?|pinned|consisten\w*|drift|boundary package|guard)\b", re.I)
NOTE = re.compile(r"\b(note|write down|remember)\b", re.I)
SHA256 = re.compile(r"\b([0-9a-fA-F]{64})\b")
WORD_LIMIT = re.compile(r"\b(under|at most|no more than|fewer than|below)\s+(\d{1,7})\s+words?\b", re.I)
FILE_PATH = re.compile(r"(~?/[^\s'\"“”]+)")
CODE_WORK = re.compile(r"^\s*(?:improve|change|fix|modify|update|extend)\s+(?:the\s+)?(?P<name>[\w.-]+)"
                       r"(?:\s+(?:repo|repository|code(?:base)?))?\s*[:\u2014-]\s*(?P<objective>\S.*)$", re.I | re.S)
QUOTED = re.compile(r"[\"“']([^\"”']{1,400})[\"”']")
SCHEDULE = re.compile(r"\b(?:shift|window)\s*:?\s*(?:is\s+)?\d{1,5}\s*(?:h|hours?)\b.*\btakes\s+\d", re.I | re.S)
NETWORK = re.compile(r"\b(?:(?:shortest|cheapest|fastest|quickest)\s+(?:route|path|way)|(?:maximum|max|most)\s+"
                     r"(?:flow|units|throughput|capacity))\s+from\s+\w+\s+to\s+\w+", re.I)
NETWORK_LINK = re.compile(r"\b\w+\s+(?:to|and)\s+\w+\s*[:,]?\s*\d", re.I)
PLAN = re.compile(r"(?:^|[.!?\n]\s*)(?:maximi[sz]e|minimi[sz]e)\s+\S", re.I)
PLAN_LIMIT = re.compile(r"(?:<=|>=|≤|≥|\bat most\b|\bat least\b|\bbetween\b|=)\s*-?\d", re.I)


@dataclass
class PlannerContext:
    read_roots: tuple
    capabilities: list[dict]                       # CapabilityRegistry.inventory()
    workspace: Path | None = None
    today: str = field(default_factory=lambda: datetime.now(timezone.utc).date().isoformat())
    repositories: dict | None = None               # name -> {"path", "github"}; discovered when None
    hosted: dict | None = None                     # name -> public record of a hosted MCP login or registered token

    def repos(self) -> dict:
        if self.repositories is None:
            self.repositories = discover(self.read_roots)
        return self.repositories


def _github_remote(repo: Path) -> str | None:
    config = repo / ".git" / "config"
    if not config.is_file():
        return None
    text = config.read_text(errors="replace")
    block = re.search(r'\[remote "origin"\](.*?)(?:\n\[|\Z)', text, re.S)
    url = re.search(r"url\s*=\s*(\S+)", block.group(1)) if block else None
    match = re.search(r"github\.com[:/]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$", url.group(1)) if url else None
    return f"{match.group(1)}/{match.group(2)}" if match else None


def discover(read_roots, *, max_depth: int = 2, limit: int = 12) -> dict:
    """Git repositories GREG may read: a root itself or directories up to ``max_depth`` below it."""
    found = {}
    for root in read_roots:
        root = Path(root)
        frontier = [(root, 0)]
        while frontier and len(found) < limit:
            path, depth = frontier.pop(0)
            if (path / ".git").exists():
                found.setdefault(path.name, {"path": str(path.resolve()), "github": _github_remote(path)})
                continue
            if depth < max_depth and path.is_dir():
                try:
                    children = sorted(p for p in path.iterdir() if p.is_dir() and not p.name.startswith("."))
                except OSError:
                    continue
                frontier.extend((child, depth + 1) for child in children)
    return dict(sorted(found.items()))


def _proposal(spec: dict, origin: str, *, notes=(), questions=(), status="PROPOSED", extra=None) -> dict:
    spec = dict(spec)
    spec["provenance"] = {"origin": origin, "planner": PLANNER, **(extra or {})}
    try:
        validate_mission(spec)
    except MissionError as exc:
        return {"status": "REJECTED", "why": str(exc), "origin": origin}
    return {"status": status, "spec": spec, "origin": origin, "notes": list(notes), "questions": list(questions)}


def _readable_file(text: str, ctx: PlannerContext, origin: str):
    """The one file a request names, if GREG may read it here; otherwise the question to ask."""
    path = FILE_PATH.search(text)
    if not path or ctx.workspace is None:
        return None, {"status": "NEEDS_INPUT", "origin": origin,
                      "questions": ["Which file? Give its full path, e.g. ~/src/downloads/tool.tar.gz"]}
    file = Path(path.group(1).rstrip(".,;")).expanduser().resolve()
    roots = [Path(r).expanduser().resolve() for r in ctx.read_roots]
    if not any(file == r or r in file.parents for r in roots):
        return None, {"status": "NEEDS_INPUT", "origin": origin,
                      "questions": [f"GREG may only read under {', '.join(map(str, roots))}. Copy the file there, "
                                    "or re-create the body with another --read-root."]}
    if not file.is_file():
        return None, {"status": "NEEDS_INPUT", "origin": origin, "questions": [f"{file} does not exist on this body."]}
    return file, None


def _words_route(text: str, ctx: PlannerContext, match) -> dict:
    file, question = _readable_file(text, ctx, "template:word-limit")
    if question:
        return question
    limit = int(match.group(2)) - (1 if match.group(1).lower() in ("under", "fewer than", "below") else 0)
    spec = templates.word_limit(file=file, max_words=max(limit, 1), workspace_root=Path(ctx.workspace))
    spec["founder_expression"] = text
    return _proposal(spec, "template:word-limit",
                     notes=["GREG has no word-count capability yet: it will acquire and verify one (read-only)",
                            "filing the record asks you first, and happens only within the limit"])


def _verify_route(text: str, ctx: PlannerContext) -> dict:
    digest = SHA256.search(text)
    file, question = _readable_file(text, ctx, "template:verify-download")
    if question:
        return question
    spec = templates.verify_download(file=file, sha256=digest.group(1), workspace_root=Path(ctx.workspace))
    spec["founder_expression"] = text
    return _proposal(spec, "template:verify-download",
                     notes=["GREG has no hashing capability yet: it will acquire and verify one (read-only) before "
                            "it can check the digest", "filing the record asks you first, and happens only if the "
                            "digest matches"])


EFFORT = re.compile(r"\b(?:effort|budget)\D{0,20}(\d{1,3})\b", re.I)


def kernel_checkouts(ctx: PlannerContext) -> list[Path]:
    """UNIIMENTE kernel checkouts inside the read roots: the sources the First Mission reads."""
    def children(directory: Path, limit: int) -> list[Path]:
        try:
            return sorted(d for d in directory.iterdir() if d.is_dir() and not d.name.startswith("."))[:limit]
        except OSError:
            return []

    found, candidates = [], []
    for root in (Path(r) for r in ctx.read_roots if Path(r).is_dir()):   # the root and two levels below, bounded
        level1 = children(root, 64)
        candidates += [root, *level1, *[d for c in level1 for d in children(c, 16)]]
    candidates += [Path(r["path"]) for r in ctx.repos().values()]
    for candidate in candidates:
        if (candidate / "greg/path.json").is_file() and (candidate / "foundry/completion.yaml").is_file():
            if candidate.resolve() not in found:
                found.append(candidate.resolve())
    return found


def _first_mission_route(text: str, ctx: PlannerContext) -> dict:
    kernels = kernel_checkouts(ctx)
    if not kernels:
        return {"status": "NEEDS_INPUT", "origin": "template:first-mission",
                "questions": ["Which UNIIMENTE kernel checkout should GREG read? Add it to the read roots "
                              "(it must contain greg/path.json and foundry/completion.yaml)."]}
    budget = EFFORT.search(text)
    effort = int(budget.group(1)) if budget else 8
    if not 1 <= effort <= 200:
        return {"status": "NEEDS_INPUT", "origin": "template:first-mission",
                "questions": ["An effort budget is a whole number of units from 1 to 200."]}
    spec = templates.first_mission(kernel_root=str(kernels[0]), effort_budget=effort, founder_expression=text)
    return _proposal(spec, "template:first-mission", notes=[
        f"reads {kernels[0]} (greg/path.json and foundry/completion.yaml) and writes one private dossier to "
        "your delivery folder; nothing is sent, published, spent or merged",
        f"effort budget: {effort} units" + ("" if budget else " (default; say 'effort budget 12' to change it)"),
        "the selection uses GREG's exact knapsack engine; if it is not attached yet the mission stops and asks "
        "you to attach it (read-only)",
        "the scores are a declared prior over the sources, shown in the dossier; you can change them",
        "an independent appraisal re-derives the dossier before the mission counts as achieved"])


MCP_WORDS = re.compile(r"\b(?:mcp|(?:tool\s+)?servers?)\b", re.I)
GENERIC_VERBS = {"get", "show", "list", "find", "read", "fetch", "give", "tell", "use", "run", "make", "do", "ask"}
TIMEZONE = re.compile(r"\b(?:UTC|[A-Z][A-Za-z_]+/[A-Za-z_]+(?:/[A-Za-z_]+)?)\b")
CHANGE_WORDS = re.compile(r"\b(?:write|append|add|create|save|store|edit|update|replace|insert|put|delete|remove|"
                          r"rename|move|commit|post|send|record)\b", re.I)
ACT_QUOTE = re.compile(r"\"([^\"]{1,400})\"|\u201c([^\u201d]{1,400})\u201d|(?<!\w)'([^']{1,400})'(?!\w)")


def _words(text: str) -> set:
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in re.findall(r"[a-z0-9]+", text.lower())}


def _mcp_route(text: str, ctx: PlannerContext) -> dict | None:
    """Words that name an installed MCP server: one read-only ``mcp.call`` mission, its tool and arguments taken from
    the server's own tool list and schemas. Anything the words do not settle becomes a question, never a guess."""
    from greg import mcp_tools
    origin = "template:mcp-tool"
    servers = mcp_tools.installed_servers(ctx.read_roots)
    words = _words(text)
    named = [n for n in servers if re.search(rf"\b{re.escape(n)}\s+(?:mcp\s+)?(?:tool\s+)?server", text, re.I)]
    if not named and not re.search(r"\bmcp\b", text, re.I):
        return None                                  # "server" alone, without an installed server named: not ours
    if not servers:
        return {"status": "NEEDS_INPUT", "origin": origin, "questions": [
            "No MCP servers are installed under GREG's read roots. Install one into its own folder there, for example "
            "python3 -m venv <read root>/tools/git && <read root>/tools/git/bin/pip install mcp-server-git"]}
    if len(named) != 1:
        if not named and len(servers) == 1:
            named = list(servers)
        else:
            return {"status": "NEEDS_INPUT", "origin": origin, "questions": [
                "Which server? Installed: " + ", ".join(servers) + " (say e.g. 'the git server')"]}
    name, server = named[0], servers[named[0]]
    scratch = Path(ctx.workspace or Path.home() / ".cache" / "greg") / "mcp-planner"
    try:
        tools = mcp_tools.server_tools(server, scratch_parent=scratch)
    except Exception as exc:
        return {"status": "NEEDS_INPUT", "origin": origin,
                "questions": [f"The {name} server did not list its tools: {str(exc)[:200]}"]}

    def fit(tool):
        """(distinctive words of the tool's name present in the request, minus those absent); generic verbs and the
        server's own name do not count. Naming the tool exactly wins."""
        if re.search(rf"\b{re.escape(tool['name'])}\b", text):
            return (99, 0)
        parts = {w[:-1] if len(w) > 3 and w.endswith("s") else w
                 for w in re.findall(r"[a-z0-9]+", tool["name"].lower())} - GENERIC_VERBS - {name}
        return (len(parts & words), -len(parts - words))
    ranked = sorted((t for t in tools if fit(t)[0] > 0), key=fit, reverse=True)
    matching = ranked
    if not matching or (len(matching) > 1 and fit(matching[0]) == fit(matching[1])):
        return {"status": "NEEDS_INPUT", "origin": origin, "questions": [
            f"Which of the {name} server's tools? " + "; ".join(
                f"{t['name']}: {(t['description'] or '').strip().splitlines()[0][:80] if t['description'] else ''}"
                for t in tools[:20])]}
    tool = matching[0]
    schema = tool.get("input_schema") or {}
    properties = schema.get("properties", {})
    # A change: the words ask for one and the server does not claim the tool only reads. Text in quotes may fill one
    # string argument, and a file that does not exist yet may be named (its folder must exist).
    act = not tool.get("claims_read_only") and bool(CHANGE_WORDS.search(text))
    quotes = [next(g for g in m.groups() if g is not None) for m in ACT_QUOTE.finditer(text)] if act else []
    plain = ACT_QUOTE.sub(" ", text) if act else text
    arguments, readable, missing, target, quoted = {}, [], [], None, None
    roots = [Path(r).expanduser().resolve() for r in ctx.read_roots]
    for prop in schema.get("required", []):
        spec = properties.get(prop, {})
        key = prop.lower()
        if any(k in key for k in ("path", "repo", "file", "dir", "folder")):
            found = FILE_PATH.search(plain)
            target = Path(found.group(1).rstrip(".,;")).expanduser().resolve() if found else None
            if target is None or not (target.exists() or (act and target.parent.is_dir())):
                missing.append(f"{prop} (a path under {', '.join(map(str, roots))})")
            elif not any(target == r or r in target.parents for r in roots):
                return {"status": "NEEDS_INPUT", "origin": origin, "questions": [
                    f"GREG may only read under {', '.join(map(str, roots))}; {target} is outside."]}
            else:
                arguments[prop], readable = str(target), [str(target)]
        elif "timezone" in key or key in ("tz", "zone"):
            zone = TIMEZONE.search(text)
            if zone:
                arguments[prop] = zone.group(0)
            else:
                missing.append(f"{prop} (an IANA zone such as Asia/Tokyo)")
        elif act and quoted is None and len(quotes) == 1 and spec.get("type", "string") == "string":
            arguments[prop], quoted = quotes[0], quotes[0]
        else:
            missing.append(f"{prop}: {spec.get('description') or spec.get('type') or 'a value'}"
                           + (" (put it in quotes)" if act else ""))
    if missing:
        return {"status": "NEEDS_INPUT", "origin": origin,
                "questions": [f"The {name} server's {tool['name']} needs " + "; ".join(missing) + "."]}
    if act:
        return _mcp_act_route(text, name, server, tool, arguments, target, quoted)
    readable = list(dict.fromkeys([*server.get("readable", []), *readable]))
    spec = templates.mcp_tool(server=name, root=server["root"], command=[*server["command"], *server.get("args", [])],
                              tool=tool["name"], arguments=arguments, readable=readable, founder_expression=text)
    return _proposal(spec, origin, notes=[
        f"the {name} server's {tool['name']} tool, with {json.dumps(arguments)}",
        "read-only by construction: the server runs with no network and a read-only view of what this mission "
        "names; a tool that tries to write or send fails and nothing changes",
        "the server's own claims about its tools are not trusted; its answer is shown as untrusted data"]
        + ([] if tool.get("claims_read_only") else [
            f"the server does not claim {tool['name']} is read-only: if it tries to change something, it fails inside "
            "GREG's namespace and nothing changes (to change something, ask for the change with the text in quotes: "
            "GREG proposes an mcp.act mission you approve)"]))


PAGE_URL = re.compile(r"\bhttps?://[^\s'\"\u201c\u201d<>]+")


def _hosted_route(text: str, ctx: PlannerContext) -> dict | None:
    """Words that name a hosted MCP server the founder logged in to (``greg mcp login``) or registered a token for
    (``greg mcp token``): one ``mcp.act`` by URL, its tool taken from the list the server gave then, so drafting
    contacts nobody. A call on someone else's machine is a change GREG cannot read back from its own disk, so the
    words must name a page GREG renders to see the effect, and the text it should show, in quotes. Whatever the words
    do not settle becomes a question."""
    from urllib.parse import urlsplit
    origin = "template:mcp-remote-act"
    named = [n for n in ctx.hosted
             if re.search(rf"\b{re.escape(n)}\s+(?:mcp\s+)?(?:service|server)\b", text, re.I)]
    if len(named) != 1:
        return None                                 # not about one hosted server by name: other routes decide
    name, hosted = named[0], ctx.hosted[named[0]]
    tools, words = hosted.get("tools") or [], _words(text)

    def fit(tool):
        if re.search(rf"\b{re.escape(tool['name'])}\b", text):
            return (99, 0)
        parts = {w[:-1] if len(w) > 3 and w.endswith("s") else w
                 for w in re.findall(r"[a-z0-9]+", tool["name"].lower())} - GENERIC_VERBS - _words(name)
        return (len(parts & words), -len(parts - words))
    ranked = sorted((t for t in tools if fit(t)[0] > 0), key=fit, reverse=True)
    if not ranked or (len(ranked) > 1 and fit(ranked[0]) == fit(ranked[1])):
        return {"status": "NEEDS_INPUT", "origin": origin, "questions": [
            f"Which of the {name} service's tools (as it listed them)? "
            + ("; ".join(f"{t['name']}: {t.get('description', '')[:80]}" for t in tools[:20]) or "it listed none")]}
    tool = ranked[0]
    verb = re.findall(r"[a-z0-9]+", tool["name"].lower())[:1]
    if tool.get("claims_read_only") or not (CHANGE_WORDS.search(text) or set(verb) & words):
        return {"status": "NEEDS_INPUT", "origin": origin, "questions": [
            f"Every call to the hosted {name} service waits for your approval, and GREG proposes one only for a change "
            "it can then see. Say what should change, the text in quotes, and the page that will show it."]}
    quotes = [next(g for g in m.groups() if g is not None) for m in ACT_QUOTE.finditer(text)]
    needs = list(tool.get("needs") or [])
    if len(quotes) != 1 or len(needs) > 1:
        return {"status": "NEEDS_INPUT", "origin": origin, "questions": [
            f"The {name} service's {tool['name']} needs " + (", ".join(needs) or "no arguments")
            + ". GREG fills one of them from the one text in quotes; say the rest in a mission you sign by hand."]}
    arguments = {needs[0]: quotes[0]} if needs else {}
    server_url = hosted["server"]
    pages = [u.rstrip(".,;)") for u in PAGE_URL.findall(ACT_QUOTE.sub(" ", text)) if u.rstrip(".,;)") != server_url]
    if len(pages) != 1:
        return {"status": "NEEDS_INPUT", "origin": origin, "questions": [
            f"GREG checks a change on the {name} service by rendering a page that shows it. Which page (one https "
            f"address)? GREG closes the mission when that page shows {quotes[0]!r}."]}
    check_url = pages[0]
    host, renew_at = urlsplit(server_url).hostname, hosted.get("renews_at")
    hosts = [host, renew_at] if renew_at and renew_at != host else []
    handle = hosted.get("handle") or f"mcp:{name}"
    spec = templates.mcp_remote_act(server=name, url=server_url, tool=tool["name"], arguments=arguments,
                                    bearer=handle, check_url=check_url, expect_text=quotes[0], hosts=hosts,
                                    founder_expression=text)
    return _proposal(spec, origin, notes=[
        f"the hosted {name} service's {tool['name']} tool at {server_url}, with {json.dumps(arguments)}; chosen from "
        "the tools the service listed when you logged in or registered it, so drafting contacted nobody",
        f"GREG asks you before it runs and shows this exact scope: {host}" + (f" (and {renew_at} to renew the login)"
                                                                           if hosts else "")
        + f" through the relay, with the credential {handle}; nothing on this computer is written",
        f"closes only when GREG itself renders {check_url} and finds {quotes[0]!r}; if it already does, nothing runs",
        "evidence: the service's answer to the call is its own claim; the page render is "
        + templates.REMOTE_EVIDENCE[templates.remote_evidence(server_url, check_url)],
        "the service's own answer is untrusted data"])


def _mcp_act_route(text: str, name: str, server: dict, tool: dict, arguments: dict, target: Path | None,
                   quoted: str | None) -> dict:
    """One ``mcp.act`` mission from the founder's words. GREG checks the change itself by reading the file the words
    name, so a change it cannot read back becomes a question. The server may write the file's folder (servers often
    replace a file by writing a new one and renaming it) and nothing else; no network, no credentials."""
    origin = "template:mcp-act"
    if target is None or target.is_dir():
        return {"status": "NEEDS_INPUT", "origin": origin, "questions": [
            f"GREG checks a change by reading the file it changes. The {name} server's {tool['name']} names "
            + (f"the folder {target}" if target else "no file") + ", so GREG could not tell whether it worked. "
            "Name the file and, in quotes, the text it should contain afterwards."]}
    if quoted is not None:
        expect, closes = {"op": "contains", "field": "text", "value": quoted}, f"finds {quoted!r} in it"
    elif not target.exists():
        expect, closes = {"op": "equals", "field": "exists", "value": True}, "finds that it exists"
    else:
        return {"status": "NEEDS_INPUT", "origin": origin, "questions": [
            f"What should {target} contain after the change? Put that text in quotes so GREG can check it."]}
    writable = target.parent
    spec = templates.mcp_act(server=name, root=server["root"], command=[*server["command"], *server.get("args", [])],
                             tool=tool["name"], arguments=arguments, writable=[str(writable)], check_path=str(target),
                             expect=expect, readable=server.get("readable", []), founder_expression=text)
    return _proposal(spec, origin, notes=[
        f"the {name} server's {tool['name']} tool, with {json.dumps(arguments)}",
        f"GREG asks you before it runs and shows this exact scope: the server may write {writable} and nothing "
        "else; no network; no credentials",
        f"closes only when GREG itself reads {target} and {closes}; if that is already true, nothing runs",
        "the server's own answer is untrusted data"])


def template_route(text: str, ctx: PlannerContext) -> dict | None:
    lowered = text.lower()
    if (work := CODE_WORK.match(text)):    # software-development work: a temporary coding worker, appraised
        return _code_work_route(text, work, ctx)
    if SHA256.search(text):                 # a published digest: verification, never a repository brief
        return _verify_route(text, ctx)
    if (limit := WORD_LIMIT.search(text)) and FILE_PATH.search(text):
        return _words_route(text, ctx, limit)
    if SCHEDULE.search(text):               # a schedule in the controlled language: the cortex composition
        try:
            spec = templates.schedule_in_words(text=text)
        except ValueError as exc:
            return {"status": "NEEDS_INPUT", "origin": "template:schedule-in-words", "questions": [str(exc)]}
        stated = "availability_evidence" in spec["strategies"][0]["params"]["problem"]["payload"]["schedule_request"]
        return _proposal(spec, "template:schedule-in-words", notes=[
            "read-only: GREG computes and shows the plan; it schedules nothing",
            "the controlled language is read without a model; a sentence it cannot read stops the plan",
            "availability taken from your words" if stated else
            "no availability statement: the answer stays conditional (add 'The machine is free all shift.')"])
    if NETWORK.search(text) and NETWORK_LINK.search(text):   # a route or flow question in controlled words
        try:
            spec = templates.network_in_words(text=text)
        except ValueError as exc:
            return {"status": "NEEDS_INPUT", "origin": "template:network-in-words", "questions": [str(exc)]}
        function = spec["strategies"][0]["function"]
        return _proposal(spec, "template:network-in-words", notes=[
            "read-only: GREG computes and shows the answer; it routes or ships nothing",
            "the controlled language is read without a model; a sentence it cannot read stops the plan",
            f"GREG has no built-in {function}: it looks for an installed open-source engine (NetworkX, SciPy), "
            "qualifies it, and asks you to attach it, showing its version and license",
            "every answer is accepted only on GREG's own certificate, not on the engine's word"])
    if PLAN.search(text) and PLAN_LIMIT.search(text):          # a linear plan in controlled words
        try:
            spec = templates.plan_in_words(text=text)
        except ValueError as exc:
            return {"status": "NEEDS_INPUT", "origin": "template:plan-in-words", "questions": [str(exc)]}
        return _proposal(spec, "template:plan-in-words", notes=[
            "read-only: GREG computes and shows the plan; it buys, makes or moves nothing",
            "the controlled language is read without a model; a sentence it cannot read stops the plan",
            "every quantity is taken as nonnegative unless a sentence gives it a lower bound",
            "GREG has no built-in LP engine: it looks for an installed open-source one (SciPy HiGHS, OR-Tools "
            "GLOP), qualifies it, and asks you to attach it, showing its version and license",
            "the plan counts only if GREG's own duality certificate proves no plan does better; if no plan meets "
            "every limit, GREG proves that and names the limits in conflict"])
    if getattr(ctx, "hosted", None) and (proposal := _hosted_route(text, ctx)) is not None:
        return proposal                     # a tool on a hosted MCP server the founder logged in to or registered
    if MCP_WORDS.search(text) and (proposal := _mcp_route(text, ctx)) is not None:
        return proposal                     # a tool on an MCP server the founder installed, named in the words
    if templates.FIRST_MISSION_WORDS.search(text):      # the founder's first mission: where am I going, what next
        return _first_mission_route(text, ctx)
    if BRIEF.search(text):
        repos = ctx.repos()
        named = {n: r for n, r in repos.items() if n.lower() in lowered}
        chosen = named or repos
        if not chosen:
            return {"status": "NEEDS_INPUT", "origin": "template:engineering-brief",
                    "questions": ["No Git repositories are visible under GREG's read roots. Which folders should "
                                  "GREG read? (re-create the body with --read-root, or name them)"]}
        spec = templates.engineering_brief(local={n: r["path"] for n, r in chosen.items()},
                                           github=sorted({r["github"] for r in chosen.values() if r["github"]}),
                                           daily=bool(DAILY.search(text)), today=ctx.today)
        spec["founder_expression"] = text
        notes = [f"repositories: {', '.join(chosen)}" + (" (named in your request)" if named else " (all visible)")]
        if not any(r["github"] for r in chosen.values()):
            notes.append("no GitHub remotes found; the brief will cover local checkouts only")
        return _proposal(spec, "template:engineering-brief", notes=notes)
    if GUARD.search(text):
        return {"status": "NEEDS_INPUT", "origin": "template:repo-guardian",
                "questions": ["Which Kernel boundary package commit (40 hex) and version must every organ pin? "
                              "Use `greg mission new repo-guardian --pin ... --version ...` once known."]}
    if NOTE.search(text):
        quoted = QUOTED.search(text)
        if not quoted or ctx.workspace is None:
            return {"status": "NEEDS_INPUT", "origin": "template:workspace-note",
                    "questions": ["Put the exact note text in quotes."]}
        body = quoted.group(1)
        spec = templates.workspace_note(text=body, must_contain=body.split()[0],
                                        workspace_file=Path(ctx.workspace) / "m_first-note" / "note.txt")
        spec["founder_expression"] = text
        return _proposal(spec, "template:workspace-note")
    return None


def _code_work_route(text: str, work, ctx: PlannerContext) -> dict:
    name = work.group("name").lower()
    repos = ctx.repos()
    chosen = {n: r for n, r in repos.items() if n.lower() == name}
    if not chosen and name in ("greg", "uniimente", "kernel"):   # GREG's own code lives in the Kernel repository
        chosen = {n: r for n, r in repos.items() if (Path(r["path"]) / "greg" / "body.py").is_file()}
    if len(chosen) != 1:
        return {"status": "NEEDS_INPUT", "origin": "template:code-change",
                "questions": [f"Which repository is {work.group('name')!r}? Visible: {', '.join(sorted(repos)) or 'none'}"]}
    (repo_name, repo), = chosen.items()
    spec = templates.code_change(repo=repo["path"], objective=work.group("objective").strip(),
                                 workspace_root=ctx.workspace, founder_expression=text)
    return _proposal(spec, "template:code-change",
                     notes=[f"repository: {repo_name}", "a temporary coding worker edits a private clone; GREG "
                            "appraises independently; spend capped at the signed budget; no push or merge"])


# -- model route ------------------------------------------------------------------------

SYSTEM = (
    "You draft missions for GREG, a persistent agent that pursues a founder's goals only through registered "
    "capabilities, under a light cone the founder signs. Reply with exactly one JSON object and nothing else: "
    "a mission that satisfies the provided JSON Schema. Rules: use only capability ids from the inventory, or a "
    "\"function\" name when no capability exists (GREG will try to acquire it and will ask before using it); "
    "every invocation's target must start with that capability's target_prefix, its params must use only the "
    "capability's declared input names (a trailing ? marks an optional input; {\"none\": ...} means no params), and a "
    "predicate field must be one of the sensor's declared outputs; "
    "success checks must be observable with read_only sensors; every strategy must advance at least one check; "
    "prefer the fewest, lowest-consequence strategies; to be told when something is wrong, write the desired state "
    "as a check (for example dirty equals false) with no strategy for it: when that check fails GREG raises exactly "
    "one founder decision carrying the evidence, which is how the founder is told; "
    "never plan spending, messages to other people, publishing, "
    "or anything irreversible. If the goal cannot be expressed with these capabilities, reply "
    "{\"cannot_plan\": \"<one sentence why>\"}."
)


def _prompt(text: str, ctx: PlannerContext) -> str:
    from greg.missions import MISSION_SCHEMA
    inventory = [{k: c.get(k) for k in ("capability_id", "function", "description", "consequence_class", "inputs",
                                         "outputs", "target_prefix", "state")} for c in ctx.capabilities]
    context = {"founder_words": text, "today": ctx.today, "capability_inventory": inventory,
               "readable_repositories": ctx.repos(), "mission_json_schema": MISSION_SCHEMA}
    if MCP_WORDS.search(text):          # the founder's installed MCP servers and their tools, for an mcp.call mission
        from greg import mcp_tools
        servers = {}
        for name, server in list(mcp_tools.installed_servers(ctx.read_roots).items())[:5]:
            try:
                tools = mcp_tools.server_tools(server, scratch_parent=Path(ctx.workspace or Path.home() / ".cache" /
                                                                           "greg") / "mcp-planner")
            except Exception as exc:
                tools = f"unlisted: {str(exc)[:120]}"
            servers[name] = {**server, "tools": tools}
        context["installed_mcp_servers"] = servers
    return json.dumps(context, sort_keys=True, indent=1, default=str)


def _first_json_object(text: str) -> dict:
    start = text.find("{")
    while start != -1:
        depth, in_string, escape = 0, False, False
        for index in range(start, len(text)):
            ch = text[index]
            if in_string:
                escape = (ch == "\\" and not escape)
                if ch == '"' and not escape:
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        value = json.loads(text[start:index + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(value, dict):
                        return value
                    break
        start = text.find("{", start + 1)
    raise MissionError("model reply contained no JSON object")


def semantic_problems(draft: dict, known: dict) -> list[str]:
    """What the mission contract cannot see: would each invocation actually run?"""
    problems = []
    checks = [(f"check {c.get('check_id')}", c.get("sensor", {}), c.get("predicate", {}))
              for c in draft.get("success_checks", []) if isinstance(c, dict)]
    strategies = [(f"strategy {s.get('action_id')}", s, None) for s in draft.get("strategies", []) if isinstance(s, dict)]
    for label, invocation, predicate in checks + strategies:
        cap = known.get(invocation.get("capability"))
        if cap is None:
            continue
        prefix = cap.get("target_prefix", "")
        if not str(invocation.get("target", "")).startswith(prefix):
            problems.append(f"{label}: target must start with {prefix!r} for {cap['capability_id']}")
        declared = {k.rstrip("?") for k in (cap.get("inputs") or {}) if k != "none"}
        required = {k for k in (cap.get("inputs") or {}) if k != "none" and not str(cap["inputs"][k]).endswith("?")}
        params = invocation.get("params", {}) or {}
        extra_keys = sorted(set(params) - declared)
        if extra_keys:
            problems.append(f"{label}: {cap['capability_id']} has no inputs named {extra_keys}; declared {sorted(declared)}")
        missing = sorted(required - set(params))
        if missing:
            problems.append(f"{label}: {cap['capability_id']} requires inputs {missing}")
        field_path = (predicate or {}).get("field")
        outputs = set(cap.get("outputs") or {})
        if predicate is not None and field_path and outputs and field_path.split(".")[0] not in outputs:
            problems.append(f"{label}: {cap['capability_id']} does not output {field_path.split('.')[0]!r}; "
                            f"it outputs {sorted(outputs)}")
    return problems


def vet(draft: dict, text: str, ctx: PlannerContext, *, origin: str, extra: dict) -> dict:
    """Make a model draft safe to show: contract, known capabilities, clamped authority."""
    if "cannot_plan" in draft:
        return {"status": "NO_ROUTE", "origin": origin, "why": str(draft["cannot_plan"])[:500]}
    draft = {k: v for k, v in draft.items() if k != "provenance"}
    clamped = []
    known = {c["capability_id"]: c for c in ctx.capabilities}
    slug = re.sub(r"[^a-z0-9]+", "-", str(draft.get("mission_id", "plan")).lower().removeprefix("m:"))[:40].strip("-")
    draft["mission_id"] = f"m:plan-{slug or 'mission'}-{ctx.today}"
    draft["founder_expression"] = text
    invocations = [c.get("sensor", {}) for c in draft.get("success_checks", [])] + list(draft.get("strategies", []))
    unknown = sorted({i["capability"] for i in invocations if isinstance(i, dict) and i.get("capability")
                      and i["capability"] not in known})
    if unknown:
        return {"status": "REJECTED", "origin": origin, "why": f"draft names unregistered capabilities {unknown}"}
    for check in draft.get("success_checks", []):
        cap = known.get(check.get("sensor", {}).get("capability"))
        if cap and cap["consequence_class"] != "read_only":
            return {"status": "REJECTED", "origin": origin, "why": "a success check must use a read-only sensor"}
    problems = semantic_problems(draft, known)
    if problems:
        return {"status": "REJECTED", "origin": origin, "why": "draft would not run as written",
                "problems": problems}
    cone = dict(draft.get("light_cone") or {})
    read_only = sorted({i["capability"] for i in invocations if isinstance(i, dict) and i.get("capability")
                        and known[i["capability"]]["consequence_class"] == "read_only"})
    if cone.get("max_consequence_class") != "read_only":
        clamped.append(f"ceiling {cone.get('max_consequence_class')!r} -> 'read_only' (consequential steps will ask you)")
    if cone.get("budget_usd", 0) != 0:
        clamped.append(f"budget {cone.get('budget_usd')} -> 0")
    if set(cone.get("capabilities", [])) - set(read_only):
        clamped.append("cone limited to the read-only capabilities the plan uses")
    horizon = datetime.now(timezone.utc) + MAX_HORIZON
    try:
        asked = datetime.fromisoformat(str(cone.get("horizon", "")).replace("Z", "+00:00"))
        if asked.tzinfo is not None and asked < horizon:
            horizon = asked
        else:
            clamped.append("horizon limited to 7 days")
    except ValueError:
        clamped.append("horizon set to 7 days")
    draft["light_cone"] = {"capabilities": read_only or ["fs.read"],
                           "targets": [t for t in cone.get("targets", []) if isinstance(t, str) and t.strip("*?")]
                           or ["fs:*"], "max_consequence_class": "read_only", "budget_usd": 0,
                           "horizon": horizon.isoformat().replace("+00:00", "Z")}
    draft.pop("auto_attach", None)
    draft.pop("standing_reconciliation", None)     # the founder adds a standing mandate, never a model
    if clamped:
        extra = {**extra, "clamped": clamped}
    return _proposal(draft, origin, notes=["drafted by a model; review every check and strategy before signing"]
                     + clamped, extra=extra)


class _TextTransport:
    """Compatibility shim: the pre-router transports returned plain text and raised MissionError."""

    def complete(self, system: str, user: str) -> str:
        try:
            return super().complete(system, user)["text"]
        except models.RouteError as exc:
            raise MissionError(str(exc)) from exc


class AnthropicTransport(_TextTransport, models.AnthropicRoute):
    """Claude through the official Anthropic SDK; now a single route of ``greg.models``."""


class ClaudeCodeTransport(_TextTransport, models.ClaudeCodeRoute):
    """The installed Claude Code CLI, headless; now a single route of ``greg.models``."""

    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, **kwargs)
        except models.RouteError as exc:
            raise MissionError(str(exc)) from exc


IDENTITY_FIELDS = ("served_model", "requested_model", "substituted")   # model identity evidence, when reported


def _complete(transport, system: str, user: str) -> tuple[str, str, list, dict]:
    """Text, true author, routes tried and the reported model identity, for a transport or a ModelRouter."""
    result = transport.complete(system, user)
    if isinstance(result, dict):
        identity = {k: result[k] for k in IDENTITY_FIELDS if result.get(k) is not None}
        return result["text"], result["route"], result.get("tried", []), identity
    return result, transport.name, [], {}


def model_route(text: str, ctx: PlannerContext, transport, *, repair_rounds: int = 1) -> dict:
    """Draft, vet, and give the model one bounded chance to fix concrete problems."""
    prompt = _prompt(text, ctx)
    origin = f"model:{transport.name}"
    attempts = []
    for round_number in range(repair_rounds + 1):
        try:
            reply, author, tried, identity = _complete(transport, SYSTEM, prompt)
            draft = _first_json_object(reply)
        except models.Refusal as exc:   # a decline is final; the router never re-asks another vendor
            return {"status": "REFUSED", "origin": origin, "why": str(exc)[:400], "refusal_class": exc.kind,
                    "attempts": attempts, "routes_tried": (getattr(transport, "last", None) or {}).get("tried", [])}
        except (MissionError, models.RouteError, subprocess.TimeoutExpired, OSError, ValueError) as exc:
            return {"status": "FAILED", "origin": origin, "why": f"{type(exc).__name__}: {exc}"[:400],
                    "attempts": attempts}
        origin = f"model:{author}"   # the route that actually wrote this draft
        extra = {"model": author, "rounds": round_number + 1,
                 "prompt_sha256": "sha256:" + hashlib.sha256((SYSTEM + "\n" + prompt).encode()).hexdigest()}
        if tried:
            extra["routes_tried"] = tried
        extra.update(identity)
        digest = (getattr(transport, "last", None) or {}).get("model_digest")
        if digest:
            extra["model_digest"] = digest
        result = vet(draft, text, ctx, origin=origin, extra=extra)
        if result["status"] != "REJECTED" or round_number == repair_rounds:
            if attempts:
                result["attempts"] = attempts
            return result
        attempts.append({"why": result["why"], "problems": result.get("problems", [])})
        prompt = (_prompt(text, ctx) + "\n\nYour previous draft cannot be accepted. Return a corrected mission "
                  "JSON object only.\nPREVIOUS DRAFT:\n" + json.dumps(draft, sort_keys=True)[:30000]
                  + "\nPROBLEMS:\n" + "\n".join(["- " + result["why"]] + ["- " + p for p in result.get("problems", [])]))
    return result


def propose(text: str, ctx: PlannerContext, *, transport=None) -> dict:
    """Cheapest sufficient route first. Returns a proposal; never signs or submits."""
    text = " ".join(str(text).split())
    if not text:
        return {"status": "NEEDS_INPUT", "origin": "planner", "questions": ["What should GREG achieve?"]}
    proposal = template_route(text, ctx)
    if proposal is not None:
        return proposal
    if transport is None:
        return {"status": "NO_ROUTE", "origin": "planner",
                "why": "no template matches and no model route is configured",
                "known_templates": sorted(templates.TEMPLATES),
                "enable_model_route": "select a locally installed open model: greg model set --route ollama "
                                      "--local-model <name> --key <founder key>; a paid route is used only "
                                      "if your own signed selection names it"}
    return model_route(text, ctx, transport)


def default_transport(secrets=None, *, config: dict | None = None, egress=None):
    """Every model route this body can reach behind one router, or None when there is none. ``egress`` is the body's
    #26 relay when confined egress is on; paid routes then reach their providers only through it."""
    routes, _ = models.available_routes(secrets, config=config, egress=egress)
    return models.ModelRouter(routes) if routes else None


CONSEQUENCE_WORDS = {"read_only": "read", "internal_write": "write a file on this computer",
                     "external_contact": "contact someone outside", "financial": "spend money",
                     "irreversible": "do something irreversible"}


def _builtin_consequence(capability_id) -> str | None:
    """A built-in capability's class when the caller's list does not carry it; unknown stays unknown (and asks)."""
    from greg.capabilities import BUILTINS
    return BUILTINS[capability_id][0].consequence_class if capability_id in BUILTINS else None


def authority_summary(spec: dict, capabilities: list[dict]) -> dict:
    """Plain-language statement of what signing this mission lets GREG do."""
    known = {c["capability_id"]: c for c in capabilities}
    cone = spec["light_cone"]
    inside, ask = [], []
    from fnmatch import fnmatchcase
    for strategy in spec.get("strategies", []):
        cid = strategy.get("capability")
        consequence = known.get(cid, {}).get("consequence_class") or _builtin_consequence(cid)
        words = f"{strategy['action_id']}: {cid or 'function ' + str(strategy.get('function'))} " \
                f"({CONSEQUENCE_WORDS.get(consequence, 'unknown consequence')}) on {strategy['target']}"
        order = ["read_only", "internal_write", "external_contact"]
        within = bool(cid and consequence in order and any(fnmatchcase(cid, p) for p in cone["capabilities"])
                      and order.index(consequence) <= order.index(cone["max_consequence_class"]))
        (inside if within else ask).append(words)
    return {"may_do_without_asking": ["observe: " + ", ".join(sorted({c["sensor"].get("capability") or
                                                                      c["sensor"].get("function") for c in
                                                                      spec["success_checks"]}))] + inside,
            "must_ask_you_first": ask, "budget_usd": cone["budget_usd"], "expires": cone["horizon"],
            "never": ["spend beyond the budget", "act after the horizon", "anything financial or irreversible "
                      "without its own decision"],
            "closure": "closes only when the checks are re-observed passing" if spec["closure"]["kind"] == "bounded"
                       else "keeps holding: re-observes and acts again whenever the goal drifts"}
