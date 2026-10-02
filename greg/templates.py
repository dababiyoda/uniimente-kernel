"""Founder-facing mission templates: goals in plain parameters, not hand-written JSON.

Each template produces a complete mission body for ``contracts/greg-mission.schema.json``
that Alfonso reviews and signs. Templates never widen authority: every one names its
light cone explicitly (capabilities, targets, ceiling, budget, horizon).
"""
from __future__ import annotations

import hashlib
import json
import math
import re

from datetime import datetime, timedelta, timezone
from pathlib import Path


def _horizon(days: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat().replace("+00:00", "Z")


def repo_guardian(*, repositories: dict[str, str], expected_pin: str, expected_version: str,
                  cadence_seconds: int = 21600, horizon_days: float = 30) -> dict:
    """Nightly guardian: organs must pin the same Kernel boundary package (read-only, real Git).

    Infinite mission: holds while consistent and re-observes on cadence. On drift it has no
    admissible strategy (repositories are never modified), so it raises exactly one founder
    decision carrying the failing rows, and waits.
    """
    repos = [{"role": role, "path": str(Path(path).expanduser().resolve())} for role, path in sorted(repositories.items())]
    sensor = {"capability": "repo.pin_audit", "target": "repo:uniimente-organs",
              "params": {"repositories": repos, "expected_pin": expected_pin, "expected_version": expected_version}}
    return {
        "mission_id": "m:repo-guardian",
        "founder_expression": "Guard my UNIIMENTE repositories: every organ must pin the same Kernel boundary "
                              "package; watch it while I sleep and tell me in the morning.",
        "intended_effect": "kernel, DALEOBANKS and WMI default branches stay contract-consistent; drift is "
                           "detected within one cadence and surfaced with evidence",
        "beneficiaries": ["Alfonso", "every organ consuming the shared boundary package"],
        "unacceptable_outcomes": ["writing to any repository", "network fetches", "silent drift"],
        "priority": 70,
        "closure": {"kind": "infinite", "cadence_seconds": cadence_seconds},
        "success_checks": [{"check_id": "organs-consistent", "description": "all pins and version agree",
                            "sensor": sensor, "predicate": {"op": "equals", "field": "compatible", "value": True}}],
        # No strategy can make organs consistent without write authority GREG does not
        # hold; drift therefore becomes exactly one evidence-backed founder decision.
        "strategies": [],
        "light_cone": {"capabilities": ["repo.pin_audit", "fs.read"], "targets": ["repo:*", "fs:*", "workspace:*"],
                       "max_consequence_class": "read_only", "budget_usd": 0, "horizon": _horizon(horizon_days)},
    }


def integration_watch(*, repositories: dict[str, str], expected_pin: str, expected_version: str,
                      cadence_seconds: int = 21600, horizon_days: float = 30) -> dict:
    """Nightly integration watch: no authority-class blocker may sit on the organs' default branches.

    From PR #112's founder mission ("identify the most consequential integration blocker and
    produce a source-backed morning brief"), rebuilt on the signed, supervised body. Read-only:
    a finding becomes exactly one founder decision carrying exact commits, blobs and lines.
    """
    repos = [{"role": role, "path": str(Path(path).expanduser().resolve())} for role, path in sorted(repositories.items())]
    params = {"repositories": repos, "expected_pin": expected_pin, "expected_version": expected_version}
    return {
        "mission_id": "m:integration-watch",
        "founder_expression": "Inspect the approved local snapshots of the three repositories, identify the most "
                              "consequential integration blocker, and produce a source-backed morning brief.",
        "intended_effect": "no authority-class integration defect stays unseen on the Kernel, DALEOBANKS or WMI "
                           "default branch; each one reaches Alfonso once with exact source evidence",
        "beneficiaries": ["Alfonso", "every organ that relies on the Kernel's authority boundary"],
        "unacceptable_outcomes": ["writing to any repository", "network fetches", "a finding without source evidence"],
        "priority": 75,
        "closure": {"kind": "infinite", "cadence_seconds": cadence_seconds},
        "success_checks": [
            {"check_id": "pins-consistent", "description": "all organs pin the same Kernel boundary package",
             "sensor": {"capability": "repo.pin_audit", "target": "repo:uniimente-organs", "params": params},
             "predicate": {"op": "equals", "field": "compatible", "value": True}},
            {"check_id": "no-authority-blockers", "description": "no authority-class static finding",
             "sensor": {"capability": "repo.integration_audit", "target": "repo:uniimente-organs", "params": params},
             "predicate": {"op": "equals", "field": "authority_findings", "value": []}}],
        "strategies": [],
        "light_cone": {"capabilities": ["repo.pin_audit", "repo.integration_audit", "fs.read"],
                       "targets": ["repo:*", "fs:*", "workspace:*"], "max_consequence_class": "read_only",
                       "budget_usd": 0, "horizon": _horizon(horizon_days)},
    }


def workspace_note(*, text: str, must_contain: str, workspace_file: Path, horizon_days: float = 2) -> dict:
    """Bounded first-body smoke mission with a real approval boundary (write needs founder approval)."""
    return {
        "mission_id": "m:first-note",
        "founder_expression": f"Write a note containing '{must_contain}' in your workspace.",
        "intended_effect": "a note exists in the mission workspace with the required text",
        "priority": 50, "closure": {"kind": "bounded"},
        "success_checks": [{"check_id": "note", "description": f"note contains {must_contain}",
                            "sensor": {"capability": "fs.read", "params": {"path": str(workspace_file)},
                                       "target": "fs:note"},
                            "predicate": {"op": "contains", "field": "text", "value": must_contain}}],
        "strategies": [{"action_id": "write-note", "capability": "fs.write",
                        "params": {"relative_path": workspace_file.name, "content": text},
                        "target": f"workspace:{workspace_file.name}", "advances": ["note"],
                        "rationale": "write the note (outside the read-only cone: asks Alfonso first)"}],
        "light_cone": {"capabilities": ["fs.read"], "targets": ["fs:*", "workspace:*"],
                       "max_consequence_class": "read_only", "budget_usd": 0, "horizon": _horizon(horizon_days)},
    }


def engineering_brief(*, local: dict[str, str], github: list[str], daily: bool = False,
                      preauthorize_delivery: bool = False, stale_days: int = 14, horizon_days: float = 2,
                      today: str | None = None) -> dict:
    """The first useful mission: a morning engineering brief delivered to Alfonso.

    Reads local checkouts (no fetch) and open pull requests with their checks, renders
    one markdown brief and delivers it into the body's delivery root. Delivery is an
    internal_write outside the read-only cone, so by default the first run stops at a
    real founder approval boundary; the approved exact scope is then reused, so a
    ``daily`` mission asks once and delivers every morning after.

    ``bounded`` (default): closes when a brief no older than 12 hours exists, re-observed.
    ``daily``: an infinite mission that re-observes hourly and delivers again whenever
    the newest brief is older than 20 hours.
    """
    today = today or datetime.now(timezone.utc).date().isoformat()
    local_rows = [{"name": name, "path": str(Path(path).expanduser().resolve())} for name, path in sorted(local.items())]
    delivery = {"action_id": "deliver-engineering-brief", "capability": "brief.engineering",
                "params": {"local": local_rows, "github": sorted(github), "stale_days": stale_days},
                "target": "deliver:briefs", "advances": ["fresh-brief"],
                "expected_outcome": "one new engineering brief file in the delivery root",
                "rationale": "read-only sources, one founder-visible file; nothing in any repository changes"}
    capabilities = ["brief.freshness", "fs.read"] + (["brief.engineering"] if preauthorize_delivery else [])
    return {
        "mission_id": "m:engineering-brief-daily" if daily else f"m:engineering-brief-{today}",
        "founder_expression": "Every morning tell me the real state of my repositories and pull requests: what is "
                              "failing, what is stale, what needs my decision. Change nothing.",
        "intended_effect": "a current, source-bound engineering brief is waiting in the delivery folder",
        "beneficiaries": ["Alfonso"],
        "unacceptable_outcomes": ["writing to any repository", "fabricated status", "overwriting a previous brief"],
        "priority": 60,
        "closure": {"kind": "infinite", "cadence_seconds": 3600} if daily else {"kind": "bounded"},
        "success_checks": [{"check_id": "fresh-brief",
                            "description": "the newest engineering brief is recent enough",
                            "sensor": {"capability": "brief.freshness", "params": {"kind": "engineering"},
                                       "target": "deliver:briefs"},
                            "predicate": {"op": "lte", "field": "age_hours", "value": 20 if daily else 12}}],
        "strategies": [delivery],
        "light_cone": {"capabilities": capabilities, "targets": ["deliver:*", "fs:*"],
                       "max_consequence_class": "internal_write" if preauthorize_delivery else "read_only",
                       "budget_usd": 0, "horizon": _horizon(30 if daily else horizon_days)},
    }


def venture_assessment(*, railscout_root: str, wmi_root: str, manifest: str, source_root: str,
                       preauthorize_delivery: bool = False, standing: bool = False, cadence_seconds: int = 3600,
                       horizon_days: float = 2) -> dict:
    """Signal -> venture decision memo through the real organs (Bridge A).

    RailScout appraises the signal's real source bytes; WealthMachine's venture engine
    evaluates the packet built from that appraisal; the memo's binding verdict is the
    engine's verdict capped by the evidence status. Delivery is one founder-visible
    file and, like every internal_write, stops at a founder approval unless signed
    into the cone. Nothing is sent, published, bought or contacted.

    ``standing``: an infinite mission on this signal. Whenever the evidence file changes
    (Alfonso adds a buyer interview, a quote, a counterexample), the check fails, both
    organs run again under the once-approved scope, and a new memo is delivered for the
    new evidence, naming what would change the verdict next.
    """
    import hashlib
    resolved = {k: str(Path(v).expanduser().resolve()) for k, v in
                {"railscout_root": railscout_root, "wmi_root": wmi_root, "manifest": manifest,
                 "source_root": source_root}.items()}
    digest = hashlib.sha256(Path(resolved["manifest"]).read_bytes()).hexdigest()
    thread = hashlib.sha256(resolved["manifest"].encode()).hexdigest()[:12]
    delivery = {"action_id": "assess-venture", "capability": "venture.assess", "params": resolved,
                "target": "deliver:ventures", "advances": ["assessed"],
                "expected_outcome": "one decision memo in the delivery root; no external act",
                "rationale": "run both organs read-only on source bytes; deliver one memo for Alfonso"}
    capabilities = ["venture.status", "fs.read"] + (["venture.assess"] if preauthorize_delivery else [])
    return {
        "mission_id": f"m:venture-watch-{thread}" if standing else f"m:venture-{digest[:12]}",
        "founder_expression": "Take this signal, find out whether it is a real business, and tell me what to do "
                              "next. Do not act on it; do not let a score outrun the evidence.",
        "intended_effect": "a source-bound venture decision memo for this signal is waiting for Alfonso, with "
                           "the evidence gap and the smallest validation step named",
        "beneficiaries": ["Alfonso", "the buyers the venture would serve"],
        "unacceptable_outcomes": ["contacting anyone", "spending", "publishing", "an unevidenced buyer or budget",
                                  "a go verdict on NEEDS_EVIDENCE"],
        "priority": 65,
        "closure": {"kind": "infinite", "cadence_seconds": cadence_seconds} if standing else {"kind": "bounded"},
        "success_checks": [{"check_id": "assessed", "description": "a memo exists for the current evidence",
                            "sensor": {"capability": "venture.status", "params": {"manifest": resolved["manifest"]},
                                       "target": "deliver:ventures"},
                            "predicate": {"op": "equals", "field": "assessed", "value": True}}],
        "strategies": [delivery],
        "light_cone": {"capabilities": capabilities, "targets": ["deliver:*", "fs:*"],
                       "max_consequence_class": "internal_write" if preauthorize_delivery else "read_only",
                       "budget_usd": 0, "horizon": _horizon(30 if standing else horizon_days)},
    }


def verify_download(*, file: Path, sha256: str, workspace_root: Path, horizon_days: float = 2) -> dict:
    """Verify a file against its published SHA-256, then file a record: the first no-model genesis mission.

    GREG has no built-in hashing capability, so observing the digest opens a verified
    CapabilityDeficit that Capability Genesis closes by acquiring an installed tool
    (sha256sum/shasum/openssl), checked against a frozen oracle before it may attach
    (read-only auto-attach is signed here). Filing the record is a write outside the
    read-only cone, so it stops for founder approval, and it ``requires`` the digest check:
    a file that does not match is never recorded as verified (developmental node N2).
    """
    digest = sha256.lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("sha256 must be 64 hex characters")
    file = Path(file).expanduser().resolve()
    slug = re.sub(r"[^a-z0-9]+", "-", file.name.lower()).strip("-")[:40] or "file"
    mission_id = f"m:verify-{slug}"
    record = Path(workspace_root) / mission_id.replace(":", "_") / f"{file.name}.sha256"
    return {
        "mission_id": mission_id,
        "founder_expression": f"Verify {file} against SHA-256 {digest} and file a verification record.",
        "intended_effect": "the file is proven to match its published digest, and a record is filed only if it does",
        "priority": 60, "closure": {"kind": "bounded"},
        "success_checks": [
            {"check_id": "digest_matches", "description": f"SHA-256 of {file.name} equals the published digest",
             "sensor": {"function": "hash.sha256", "params": {"path": str(file)}, "target": f"fs:{file.name}"},
             "predicate": {"op": "equals", "field": "sha256", "value": digest}},
            {"check_id": "recorded", "description": "a verification record names the digest",
             "sensor": {"capability": "fs.read", "params": {"path": str(record)}, "target": f"fs:{record.name}"},
             "predicate": {"op": "contains", "field": "text", "value": digest}}],
        "strategies": [{"action_id": "file-record", "capability": "fs.write",
                        "params": {"relative_path": record.name, "content": f"{digest}  {file.name}\n"},
                        "target": f"workspace:{record.name}", "advances": ["recorded"], "requires": ["digest_matches"],
                        "rationale": "file the record only after the digest matched (outside the read-only cone: "
                                     "asks Alfonso first)"}],
        "light_cone": {"capabilities": ["fs.read", "acquired.hash.sha256.*"], "targets": ["fs:*", "workspace:*"],
                       "max_consequence_class": "read_only", "budget_usd": 0, "horizon": _horizon(horizon_days)},
        "auto_attach": {"max_consequence_class": "read_only"},
    }


def word_limit(*, file: Path, max_words: int, workspace_root: Path, horizon_days: float = 2) -> dict:
    """Confirm a draft is within a word limit, then file a record: a second, unrelated genesis function.

    Word counting is not built in either; genesis acquires and verifies an installed tool
    (wc). The record ``requires`` the limit check, so a draft over the limit is never
    recorded as within it. Filing stops for founder approval (outside the read-only cone).
    """
    if not isinstance(max_words, int) or max_words < 1:
        raise ValueError("max_words must be a positive integer")
    file = Path(file).expanduser().resolve()
    slug = re.sub(r"[^a-z0-9]+", "-", file.name.lower()).strip("-")[:40] or "file"
    mission_id = f"m:words-{slug}"
    record = Path(workspace_root) / mission_id.replace(":", "_") / f"{file.name}.words"
    statement = f"{file.name}: at most {max_words} words"
    return {
        "mission_id": mission_id,
        "founder_expression": f"Confirm {file} has at most {max_words} words and file a record.",
        "intended_effect": "the draft is proven within the word limit, and a record is filed only if it is",
        "priority": 60, "closure": {"kind": "bounded"},
        "success_checks": [
            {"check_id": "within_limit", "description": f"{file.name} has at most {max_words} words",
             "sensor": {"function": "text.wordcount", "params": {"path": str(file)}, "target": f"fs:{file.name}"},
             "predicate": {"op": "lte", "field": "words", "value": max_words}},
            {"check_id": "recorded", "description": "a record states the limit was met",
             "sensor": {"capability": "fs.read", "params": {"path": str(record)}, "target": f"fs:{record.name}"},
             "predicate": {"op": "contains", "field": "text", "value": statement}}],
        "strategies": [{"action_id": "file-record", "capability": "fs.write",
                        "params": {"relative_path": record.name, "content": statement + " (checked by GREG)\n"},
                        "target": f"workspace:{record.name}", "advances": ["recorded"], "requires": ["within_limit"],
                        "rationale": "file the record only after the count is within the limit (asks Alfonso first)"}],
        "light_cone": {"capabilities": ["fs.read", "acquired.text.wordcount.*"], "targets": ["fs:*", "workspace:*"],
                       "max_consequence_class": "read_only", "budget_usd": 0, "horizon": _horizon(horizon_days)},
        "auto_attach": {"max_consequence_class": "read_only"},
    }


def human_work(*, function: str, purpose: str, workspace_root: Path, deliverable: str = "deliverable.pdf",
               horizon_days: float = 30) -> dict:
    """A step only a person may do (directive section 60: "I need a licensed professional for this decision").

    ``function`` is ``professional.<field>`` (an attorney's review, a CPA's return, an engineer's
    stamp) or ``human.<task>``. GREG never searches for, builds or attaches software for it: the
    engine raises one costed ``professional`` / ``human_worker`` ask, contacts and pays no one, and
    keeps observing the mission's own check. When the deliverable exists where the check reads it,
    the ask is withdrawn and the mission closes without GREG acting. GREG checks that the
    deliverable exists, never its professional quality.
    """
    if not function.startswith(("professional.", "human.")) or not re.fullmatch(r"[a-z0-9_.-]{3,80}", function):
        raise ValueError("function must be professional.<field> or human.<task> (lowercase, 3-80 characters)")
    name = Path(deliverable).name
    if not name or name != deliverable or name.startswith("."):
        raise ValueError("deliverable is a plain file name placed in this mission's workspace folder")
    slug = re.sub(r"[^a-z0-9]+", "-", f"{function.split('.', 1)[1]}-{name}".lower()).strip("-")[:50]
    mission_id = f"m:work-{slug}"
    path = Path(workspace_root) / mission_id.replace(":", "_") / name
    return {
        "mission_id": mission_id,
        "founder_expression": f"{purpose.strip()} ({function}; deliverable at {path}).",
        "intended_effect": f"the deliverable of {function} exists where GREG observes it; GREG does not perform it",
        "priority": 50, "closure": {"kind": "bounded", "cadence_seconds": 3600},
        "success_checks": [
            {"check_id": "deliverable_present", "description": f"{name} is placed by whoever did {function}",
             "sensor": {"capability": "fs.read", "params": {"path": str(path)}, "target": f"fs:{name}"},
             "predicate": {"op": "equals", "field": "exists", "value": True}}],
        "strategies": [{"action_id": "arrange-the-person", "function": function, "target": f"person:{function}",
                        "advances": ["deliverable_present"], "rationale": purpose.strip()}],
        "light_cone": {"capabilities": ["fs.read"], "targets": ["fs:*", "person:*"],
                       "max_consequence_class": "read_only", "budget_usd": 0, "horizon": _horizon(horizon_days)},
    }


TEMPLATES = {"repo-guardian": repo_guardian, "integration-watch": integration_watch, "workspace-note": workspace_note,
             "engineering-brief": engineering_brief, "venture-assessment": venture_assessment,
             "verify-download": verify_download, "word-limit": word_limit, "human-work": human_work}


# Controlled-language reader lineage: PR143, commit
# 7105a7cbd013edd6bce88b9500e2b4477635c912, greg/templates.py (MIT).
# Every clause must match; these readers do not formalize arbitrary natural language.
NETWORK_NAME = r"[A-Za-z][A-Za-z0-9_-]{0,31}"
NETWORK_NUMBER = r"\d+(?:\.\d+)?"
NETWORK_LINK = re.compile(rf"^(?P<a>{NETWORK_NAME})\s+(?P<how>to|and)\s+(?P<b>{NETWORK_NAME})\s*[:,]?\s*"
                          rf"(?P<n>{NETWORK_NUMBER})(?:\s+(?P<unit>[A-Za-z]+))?$", re.I)
NETWORK_SHORTEST = re.compile(rf"^(?P<metric>shortest|cheapest|fastest|quickest)\s+(?:route|path|way)\s+from\s+"
                              rf"(?P<s>{NETWORK_NAME})\s+to\s+(?P<t>{NETWORK_NAME})$", re.I)
NETWORK_FLOW = re.compile(rf"^(?:maximum|max|most)\s+(?:flow|units|throughput|capacity)\s+from\s+"
                          rf"(?P<s>{NETWORK_NAME})\s+to\s+(?P<t>{NETWORK_NAME})$", re.I)
NETWORK_UNITS = {
    "m": "m", "meter": "m", "meters": "m", "metre": "m", "metres": "m",
    "km": "km", "kilometer": "km", "kilometers": "km", "kilometre": "km", "kilometres": "km",
    "second": "seconds", "seconds": "seconds", "minute": "minutes", "minutes": "minutes",
    "hour": "hours", "hours": "hours", "usd": "USD", "dollar": "USD", "dollars": "USD",
    "unit": "units", "units": "units", "item": "items", "items": "items",
}


def _controlled_clauses(text: str) -> list[str]:
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise ValueError("a controlled request of 1-4000 characters is required")
    clauses = [s.strip() for s in re.split(r"\.(?=\s|$)|[!?;\n]+", text) if s.strip()]
    if not clauses or len(clauses) > 80:
        raise ValueError("state 1-80 complete clauses")
    if any(len(clause) > 450 for clause in clauses):
        raise ValueError("each controlled clause must fit 450 characters for the signed review record")
    return clauses


def _controlled_number(text: str):
    value = float(text) if "." in text else int(text)
    if abs(value) > 1e9 or not math.isfinite(value):
        raise ValueError("numbers must be finite and have magnitude at most 1e9")
    return value


def _read_network_words(text: str) -> tuple[str, dict, dict]:
    clauses = _controlled_clauses(text)
    edges, questions, units, unread = [], [], [], []
    for clause in clauses:
        if link := NETWORK_LINK.fullmatch(clause):
            number = _controlled_number(link["n"])
            stated = link["unit"]
            if stated is not None and stated.lower() not in NETWORK_UNITS:
                raise ValueError(f"unsupported unit {stated!r}; use one declared unit on every link")
            units.append(NETWORK_UNITS[stated.lower()] if stated else "dimensionless")
            edges.append([link["a"], link["b"], number])
            if link["how"].lower() == "and":
                edges.append([link["b"], link["a"], number])
        elif ask := NETWORK_SHORTEST.fullmatch(clause):
            questions.append(("shortest_path", ask["s"], ask["t"], ask["metric"].lower()))
        elif ask := NETWORK_FLOW.fullmatch(clause):
            questions.append(("max_flow", ask["s"], ask["t"], "flow"))
        else:
            unread.append(clause)
    if unread:
        raise ValueError("GREG could not read: " + "; ".join(repr(u[:80]) for u in unread[:5])
                         + ". State every link and condition in the supported controlled language.")
    if len(questions) != 1 or not edges:
        raise ValueError("state at least one link and exactly one question, such as 'Shortest route from A to C.'")
    if len(set(units)) != 1:
        raise ValueError("all links must use the same explicit unit, or all be dimensionless; convert mixed units first")
    operation, source, target, metric = questions[0]
    unit = units[0]
    if metric in ("fastest", "quickest") and unit not in ("seconds", "minutes", "hours"):
        raise ValueError("fastest/quickest requires time units on every link")
    if metric == "cheapest" and unit != "USD":
        raise ValueError("cheapest requires dollar/USD costs on every link")
    if operation == "max_flow":
        if unit not in ("dimensionless", "units", "items"):
            raise ValueError("flow capacities must use dimensionless counts, units or items")
        if any(not isinstance(e[2], int) for e in edges):
            raise ValueError("maximum-flow capacities must be whole numbers")
        params = {"edges": edges, "source": source, "sink": target}
        from greg.cognition.network import flow_request
        flow_request(params)
    else:
        params = {"edges": edges, "start": source, "goal": target}
        from greg.cognition.network import shortest_request
        shortest_request(params)
    return operation, params, {"clauses": clauses, "unit": unit, "all_clauses_represented": True,
                               "scope": "restricted grammar only; real topology, availability and units unverified"}


def read_network_words(text: str) -> tuple[str, dict]:
    """Read all controlled clauses; reject unknown conditions and incompatible units."""
    operation, params, _ = _read_network_words(text)
    return operation, params


PLAN_NAME = r"[A-Za-z][A-Za-z0-9_]{0,31}"
PLAN_NUMBER = r"-?\d+(?:\.\d+)?"
PLAN_TERM = re.compile(rf"\s*(?P<sign>[+-])?\s*(?P<coef>\d+(?:\.\d+)?)?\s*\*?\s*(?P<name>{PLAN_NAME})\s*")
PLAN_OBJECTIVE = re.compile(r"^(?P<sense>maximi[sz]e|minimi[sz]e)\s+(?P<expr>.+)$", re.I)
PLAN_CONSTRAINT = re.compile(rf"^(?P<expr>.+?)\s*(?P<op><=|>=|=|≤|≥|\bat most\b|\bat least\b|\bequals\b)\s*"
                             rf"(?P<rhs>{PLAN_NUMBER})$", re.I)
PLAN_BETWEEN = re.compile(rf"^(?P<name>{PLAN_NAME})\s+between\s+(?P<lo>{PLAN_NUMBER})\s+and\s+(?P<hi>{PLAN_NUMBER})$", re.I)
PLAN_KEYWORDS = {"maximize", "maximise", "minimize", "minimise", "between", "and", "at", "most", "least", "equals"}


def _plan_expr(text: str) -> dict:
    coefficients, position = {}, 0
    for term in PLAN_TERM.finditer(text):
        if term.start() != position or (position and not term["sign"]) or term["name"].lower() in PLAN_KEYWORDS:
            raise ValueError(f"GREG could not read the expression {text.strip()!r}")
        value = _controlled_number(term["coef"]) if term["coef"] else 1
        coefficients[term["name"]] = coefficients.get(term["name"], 0) + (-value if term["sign"] == "-" else value)
        position = term.end()
    if position != len(text) or not coefficients:
        raise ValueError(f"GREG could not read the expression {text.strip()!r}")
    return coefficients


def _read_plan_words(text: str) -> tuple[dict, dict]:
    clauses = _controlled_clauses(text)
    objectives, constraints, bounds, unread = [], [], {}, []
    for index, clause in enumerate(clauses):
        if goal := PLAN_OBJECTIVE.fullmatch(clause):
            objectives.append({"sense": "max" if goal["sense"].lower().startswith("max") else "min",
                               "coefficients": _plan_expr(goal["expr"])})
        elif bound := PLAN_BETWEEN.fullmatch(clause):
            if bound["name"] in bounds:
                raise ValueError(f"duplicate bounds for {bound['name']}; state one explicit lower/upper range")
            bounds[bound["name"]] = [_controlled_number(bound["lo"]), _controlled_number(bound["hi"])]
        elif con := PLAN_CONSTRAINT.fullmatch(clause):
            op = {"<=": "<=", "≤": "<=", "at most": "<=", ">=": ">=", "≥": ">=", "at least": ">=",
                  "=": "==", "equals": "=="}[con["op"].lower()]
            constraints.append({"name": f"clause-{index + 1}", "coefficients": _plan_expr(con["expr"]),
                                "op": op, "rhs": _controlled_number(con["rhs"])})
        else:
            unread.append(clause)
    if unread:
        raise ValueError("GREG could not read: " + "; ".join(repr(u[:80]) for u in unread[:5])
                         + ". Units, integer requirements and other conditions cannot be silently dropped.")
    if len(objectives) != 1 or not constraints:
        raise ValueError("state exactly one objective and at least one linear constraint")
    names = sorted({n for part in objectives + constraints for n in part["coefficients"]} | set(bounds))
    missing = sorted(set(names) - set(bounds))
    if missing:
        raise ValueError("finite explicit bounds required for " + ", ".join(missing)
                         + "; write each as 'x between 0 and 3.'")
    params = {"variables": {name: bounds[name] for name in names}, "objective": objectives[0], "constraints": constraints}
    from greg.cognition.linear import canonical_request
    canonical_request(params)
    return params, {"clauses": clauses, "unit": "dimensionless model", "all_clauses_represented": True,
                    "scope": "continuous variables; no arbitrary language, real-unit formalization or empirical completeness claim"}


def read_plan_words(text: str) -> dict:
    """Read a dimensionless continuous LP, with every constraint and finite bound explicit."""
    params, _ = _read_plan_words(text)
    return params


def _controlled_cognition_mission(text: str, operation: str, data: dict, coverage: dict, *, horizon_days: float) -> dict:
    family = {"shortest_path": "graph", "max_flow": "flow", "linear_program": "linear"}[operation]
    source_digest = "sha256:" + hashlib.sha256(text.encode()).hexdigest()
    slug = hashlib.sha256(json.dumps({"operation": operation, "data": data, "source_digest": source_digest},
                                    sort_keys=True).encode()).hexdigest()[:10]
    step = {"capability": f"cognition.{family}", "target": f"cognition:words-{slug}",
            "params": {"problem_id": f"words:{slug}", "operation": operation, "data": data,
                       "assumptions": [f"Controlled-language source {source_digest}; represented only within the declared grammar.",
                                       f"Declared unit scope: {coverage['unit']}; real observations and applicability unverified.",
                                       coverage["scope"]], "geometry": {"latency_limit": 10, "compute_limit": 10000}}}
    native = {"shortest_path": ("output.reachable", "equals", True),
              "max_flow": ("output.value", "gte", 0), "linear_program": ("output.solver_status", "equals", "OPTIMAL")}[operation]
    checks = [("independent-proof", "independent evidence contract verifies the scoped computation",
               "evaluator_result.verdict", "equals", "STRUCTURALLY_VERIFIED"),
              ("within-competence", "the result does not abstain", "abstention_state", "equals", "NONE"),
              ("native-answer", "the requested bounded result exists", *native)]
    return {"mission_id": f"m:words-{slug}", "founder_expression": text,
            "intended_effect": f"a checked {operation.replace('_', ' ')} result for every stated controlled-language clause",
            "beneficiaries": ["Alfonso"], "unacceptable_outcomes": ["acting on the plan", "dropping an unread condition", "claiming real-world verification"],
            "constraints": [f"Controlled source digest: {source_digest}", "Reader: greg-controlled-words/0.1",
                            f"Coverage: all {len(coverage['clauses'])} clauses represented within the restricted grammar; no general completeness claim.",
                            f"Unit scope: {coverage['unit']}; {coverage['scope']}"]
                           + [f"Clause {index + 1}: {clause}" for index, clause in enumerate(coverage["clauses"])],
            "priority": 60, "closure": {"kind": "bounded"},
            "success_checks": [{"check_id": cid, "description": description, "sensor": step,
                                "predicate": {"field": field, "op": op, "value": value}} for cid, description, field, op, value in checks],
            "strategies": [], "light_cone": {"capabilities": [step["capability"]], "targets": ["cognition:*"],
                                             "max_consequence_class": "read_only", "budget_usd": 0, "horizon": _horizon(horizon_days)},
            "provenance": {"origin": "template:controlled-" + operation, "planner": "greg-controlled-words/0.1",
                           "prompt_sha256": source_digest}}


def network_in_words(*, text: str, horizon_days: float = 2) -> dict:
    """Propose existing graph/flow cognition; attachment and signing remain human decisions."""
    operation, data, coverage = _read_network_words(text)
    return _controlled_cognition_mission(text, operation, data, coverage, horizon_days=horizon_days)


def plan_in_words(*, text: str, horizon_days: float = 2) -> dict:
    """Propose a finite-bounded continuous LP through the canonical GLOP/verifier contracts."""
    data, coverage = _read_plan_words(text)
    return _controlled_cognition_mission(text, "linear_program", data, coverage, horizon_days=horizon_days)


TEMPLATES.update({"network-in-words": network_in_words, "plan-in-words": plan_in_words})
