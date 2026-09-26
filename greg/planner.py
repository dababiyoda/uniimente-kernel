"""Founder intent -> mission proposal. A proposal is data; only a founder signature makes it a MISSION.

This is how Alfonso talks to GREG in plain words instead of hand-writing mission JSON.
Two routes behind one interface (governed pluralism, cheapest first):

1. **Template route** (deterministic, zero model calls, always available): recognizes
   the missions GREG already knows how to run and fills their parameters from what
   the body can see (Git repositories under its read roots, their GitHub remotes).
2. **Model route** (optional): a Claude model drafts a mission against the real
   capability inventory. Transports: the Anthropic API (official SDK, key from the
   ``anthropic_api_key`` credential handle) or the locally installed Claude Code CLI.

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
QUOTED = re.compile(r"[\"“']([^\"”']{1,400})[\"”']")


@dataclass
class PlannerContext:
    read_roots: tuple
    capabilities: list[dict]                       # CapabilityRegistry.inventory()
    workspace: Path | None = None
    today: str = field(default_factory=lambda: datetime.now(timezone.utc).date().isoformat())
    repositories: dict | None = None               # name -> {"path", "github"}; discovered when None

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


def template_route(text: str, ctx: PlannerContext) -> dict | None:
    lowered = text.lower()
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
    return json.dumps({"founder_words": text, "today": ctx.today, "capability_inventory": inventory,
                       "readable_repositories": ctx.repos(), "mission_json_schema": MISSION_SCHEMA},
                      sort_keys=True, indent=1)


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


def _complete(transport, system: str, user: str) -> tuple[str, str, list, str | None]:
    """Text, true author, routes tried and provider-reported served model, for a transport or a ModelRouter."""
    result = transport.complete(system, user)
    if isinstance(result, dict):
        return result["text"], result["route"], result.get("tried", []), result.get("served_model")
    return result, transport.name, [], None


def model_route(text: str, ctx: PlannerContext, transport, *, repair_rounds: int = 1) -> dict:
    """Draft, vet, and give the model one bounded chance to fix concrete problems."""
    prompt = _prompt(text, ctx)
    origin = f"model:{transport.name}"
    attempts = []
    for round_number in range(repair_rounds + 1):
        try:
            reply, author, tried, served = _complete(transport, SYSTEM, prompt)
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
        if served:
            extra["served_model"] = served
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
                "enable_model_route": "store an anthropic_api_key credential, or install Claude Code (claude)"}
    return model_route(text, ctx, transport)


def default_transport(secrets=None, *, config: dict | None = None):
    """Every model route this body can reach behind one router, or None when there is none."""
    routes, _ = models.available_routes(secrets, config=config)
    return models.ModelRouter(routes) if routes else None


CONSEQUENCE_WORDS = {"read_only": "read", "internal_write": "write a file on this computer",
                     "external_contact": "contact someone outside", "financial": "spend money",
                     "irreversible": "do something irreversible"}


def authority_summary(spec: dict, capabilities: list[dict]) -> dict:
    """Plain-language statement of what signing this mission lets GREG do."""
    known = {c["capability_id"]: c for c in capabilities}
    cone = spec["light_cone"]
    inside, ask = [], []
    from fnmatch import fnmatchcase
    for strategy in spec.get("strategies", []):
        cid = strategy.get("capability")
        cap = known.get(cid, {})
        words = f"{strategy['action_id']}: {cid or 'function ' + str(strategy.get('function'))} " \
                f"({CONSEQUENCE_WORDS.get(cap.get('consequence_class'), 'unknown consequence')}) on {strategy['target']}"
        within = (cid and any(fnmatchcase(cid, p) for p in cone["capabilities"])
                  and ["read_only", "internal_write", "external_contact"].index(cap.get("consequence_class", "read_only"))
                  <= ["read_only", "internal_write", "external_contact"].index(cone["max_consequence_class"]))
        (inside if within else ask).append(words)
    return {"may_do_without_asking": ["observe: " + ", ".join(sorted({c["sensor"].get("capability") or
                                                                      c["sensor"].get("function") for c in
                                                                      spec["success_checks"]}))] + inside,
            "must_ask_you_first": ask, "budget_usd": cone["budget_usd"], "expires": cone["horizon"],
            "never": ["spend beyond the budget", "act after the horizon", "anything financial or irreversible "
                      "without its own decision"],
            "closure": "closes only when the checks are re-observed passing" if spec["closure"]["kind"] == "bounded"
                       else "keeps holding: re-observes and acts again whenever the goal drifts"}
