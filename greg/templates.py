"""Founder-facing mission templates: goals in plain parameters, not hand-written JSON.

Each template produces a complete mission body for ``contracts/greg-mission.schema.json``
that Alfonso reviews and signs. Templates never widen authority: every one names its
light cone explicitly (capabilities, targets, ceiling, budget, horizon).
"""
from __future__ import annotations

import hashlib
import json
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


def cognitive_problem(problem: dict, *, horizon_days=2) -> dict:
    """Founder reviews/signs bounded input and optional local model identity before dispatch."""
    from cortex.seed.contracts import validate_problem
    validate_problem(problem)
    return {'mission_id': 'm:cognition-' + problem['problem_id'],
            'founder_expression': problem['objective'],
            'intended_effect': 'Return independently checked, conditional cognitive artifacts; no external action.',
            'priority': 50, 'closure': {'kind': 'bounded'},
            'success_checks': [{'check_id': 'verified-answer', 'description': 'All subclaims answered within declared scope',
                'sensor': {'capability': 'cognition.status', 'target': 'cognition:' + problem['problem_id'],
                           'params': {'problem_id': problem['problem_id']}},
                'predicate': {'op': 'equals', 'field': 'answered', 'value': True}}],
            'strategies': [{'action_id': 'compute', 'capability': 'cognition.seed.solve',
                'target': 'cognition:' + problem['problem_id'], 'params': {'problem': problem},
                'advances': ['verified-answer'], 'rationale': 'Smallest eligible methods, typed proof, independent checks'}],
            'light_cone': {'capabilities': ['cognition.seed.solve', 'cognition.status'],
                'targets': ['cognition:' + problem['problem_id']], 'max_consequence_class': 'read_only',
                'budget_usd': 0, 'horizon': _horizon(horizon_days)}}


TEMPLATES['cognition'] = cognitive_problem


# -- execution fabric: work orders, computer use, DALEOBANKS ----------------------------------

def _slug(text: str, limit: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit] or "work"


def code_change(*, repo: str, objective: str, order: str | None = None, allowed_paths: list[str] | None = None,
                tests: list[list[str]] | None = None, budget_usd: float = 3.0, provider: str = "claude-code",
                timeout_seconds: int = 1200, horizon_days: float = 2, founder_expression: str | None = None,
                workspace_root: Path | None = None) -> dict:
    """Software work through a temporary coding worker; GREG appraises it independently, then hands off.

    1. ``worker.commission`` (internal_write, spends at most ``budget_usd``): a real worker edits a private
       clone; GREG collects the diff, runs acceptance with no network and commits on ``greg/<order>``.
    2. ``worker.appraise`` (read-only sensor): fresh clone, patch re-applied, scope and protected-surface
       checks, acceptance re-run. Only ``ACCEPTED`` closes the check; a protected surface yields a
       founder decision, never acceptance.
    3. The handoff note is written only after acceptance (``requires``): the parent mission continues on
       the appraised result. Push, PR and merge stay with the existing authorized path.
    """
    order = order or _slug(objective, 30)
    repo_path = str(Path(repo).expanduser().resolve())
    allowed_paths = allowed_paths or ["greg/*", "tests/unit/*"]
    acceptance = {"run_changed_tests": True, "max_changed_files": 8}
    if tests:
        acceptance["tests"] = tests
    handoff = f"handoff-{order}.md"
    mission_id = f"m:work-{order}"
    handoff_path = str(Path(workspace_root or ".").resolve() / mission_id.replace(":", "_") / handoff)
    return {
        "mission_id": mission_id,
        "founder_expression": founder_expression or f"Improve {Path(repo_path).name}: {objective}",
        "intended_effect": "a tested, independently appraised proposed change exists on a reviewable branch; "
                           "promotion remains with the authorized repository path",
        "priority": 55, "closure": {"kind": "bounded"},
        "constraints": ["the worker never pushes, merges or commits; GREG commits on a greg/ branch in a private clone",
                        "protected constitutional surfaces cannot be accepted without a founder decision"],
        "success_checks": [
            {"check_id": "work_accepted", "description": "independent appraisal ACCEPTED the work order",
             "sensor": {"capability": "worker.appraise", "params": {"order": order}, "target": f"work:{order}"},
             "predicate": {"op": "equals", "field": "verdict", "value": "ACCEPTED"}},
            {"check_id": "handoff_written", "description": "the review handoff exists for the founder",
             "sensor": {"capability": "fs.read", "params": {"path": handoff_path}, "target": f"fs:{handoff}"},
             "predicate": {"op": "contains", "field": "text", "value": f"greg/{order}"}}],
        "strategies": [
            {"action_id": "commission-worker", "capability": "worker.commission", "target": f"work:{order}",
             "params": {"order": order, "mode": "repository", "repo": repo_path, "objective": objective,
                        "acceptance": acceptance, "allowed_paths": allowed_paths, "provider": provider,
                        "max_budget_usd": budget_usd, "timeout_seconds": timeout_seconds},
             "cost_usd": budget_usd, "advances": ["work_accepted"],
             "rationale": "software-development work: commission a temporary coding worker under a bounded lease",
             "expected_outcome": "a committed change on a greg/ branch in a private clone, with evidence"},
            {"action_id": "write-handoff", "capability": "fs.write", "target": f"workspace:{handoff}",
             "params": {"relative_path": handoff,
                        "content": f"# Proposed change ready for review: greg/{order}\n\nIndependently appraised "
                                   f"ACCEPTED by worker.appraise. Evidence: work-orders/{order}/evidence.json and "
                                   f"change.patch in this mission workspace. Promotion (push, PR, merge) requires "
                                   "the existing authorized path; GREG holds no push or merge authority.\n"},
             "advances": ["handoff_written"], "requires": ["work_accepted"],
             "rationale": "continue the parent mission only on an independently accepted result"}],
        "light_cone": {"capabilities": ["worker.commission", "worker.appraise", "fs.read", "fs.write"],
                       "targets": [f"work:{order}", f"fs:{handoff}", f"workspace:{handoff}"],
                       "max_consequence_class": "internal_write", "budget_usd": budget_usd,
                       "horizon": _horizon(horizon_days)},
    }


def browser_task(*, url: str, steps: list[dict], session: str, expect: dict, horizon_days: float = 1,
                 founder_expression: str | None = None, on_challenge: str = "stop") -> dict:
    """Bounded computer use: one disposable browser session; the trace sensor re-reads the evidence.

    ``expect`` is a predicate over the ``browser.trace`` output (e.g. an extracted key exists).
    """
    from urllib.parse import urlsplit
    host = urlsplit(url).hostname or ""
    return {
        "mission_id": f"m:browse-{_slug(session)}",
        "founder_expression": founder_expression or f"Operate {host} in a browser: {session}",
        "intended_effect": "the requested information is retrieved by operating the site, with per-step evidence; "
                           "consequential steps stop at the authority boundary",
        "priority": 50, "closure": {"kind": "bounded"},
        "success_checks": [
            {"check_id": "retrieved", "description": "the session's retained trace holds the requested result",
             "sensor": {"capability": "browser.trace", "params": {"session": session}, "target": f"web:{host}"},
             "predicate": expect}],
        "strategies": [
            {"action_id": "operate-browser", "capability": "browser.session", "target": f"web:{host}",
             "params": {"url": url, "steps": steps, "session": session, "on_challenge": on_challenge},
             "advances": ["retrieved"], "rationale": "structured DOM control in a disposable real browser"}],
        "light_cone": {"capabilities": ["browser.session", "browser.trace"], "targets": [f"web:{host}"],
                       "max_consequence_class": "internal_write", "budget_usd": 0, "horizon": _horizon(horizon_days)},
    }


def daleobanks_post(*, daleobanks_root: str, source: str, brief: str, order: str, budget_usd: float = 2.0,
                    max_chars: int = 280, horizon_days: float = 2, founder_expression: str | None = None) -> dict:
    """GREG -> research/content worker -> DALEOBANKS verification -> publish request through both gates.

    The draft is written by a temporary worker from a read-only source; DALEOBANKS's own checks plus
    figure-to-source binding must pass before the publish request may run (``requires``). Publishing is
    external_contact: outside this cone, so it stops for a founder decision; even when approved,
    DALEOBANKS's LIVE kill switch and credentials decide, and a dry-run is reported as a block.
    """
    source = str(Path(source).expanduser().resolve())
    root = str(Path(daleobanks_root).expanduser().resolve())
    draft_name = "post.txt"
    return {
        "mission_id": f"m:media-{_slug(order)}",
        "founder_expression": founder_expression or f"DALEOBANKS: {brief}",
        "intended_effect": "a source-bound post is drafted, verified by DALEOBANKS and submitted to its publishing "
                           "gate; the truthful outcome (posted or blocked) returns to GREG",
        "priority": 50, "closure": {"kind": "bounded"},
        "success_checks": [
            {"check_id": "draft_verified", "description": "DALEOBANKS checks and source binding pass",
             "sensor": {"capability": "daleobanks.verify",
                        "params": {"daleobanks_root": root, "source": source, "max_chars": max_chars,
                                   "draft": f"work-orders/{order}/work/{draft_name}"},
                        "target": "daleobanks:verify"},
             "predicate": {"op": "equals", "field": "verdict", "value": "VERIFIED"}},
            {"check_id": "publish_outcome_known", "description": "DALEOBANKS's ledger holds the request's outcome",
             "sensor": {"capability": "daleobanks.outcome", "params": {}, "target": "daleobanks:outcome"},
             "predicate": {"op": "equals", "field": "requested", "value": True}}],
        "strategies": [
            {"action_id": "draft-post", "capability": "worker.commission", "target": f"work:{order}",
             "params": {"order": order, "mode": "document", "inputs": [source],
                        "objective": f"{brief} Write the post as plain text, at most {max_chars} characters, "
                                     "stating only facts present in the input; every number must appear in the input.",
                        "acceptance": {"output": draft_name,
                                       "criteria": f"<= {max_chars} characters; no figures absent from the source; no "
                                                   "hype, no calls to buy; not a proposal (no pilot/KPI language)"},
                        "allowed_paths": [draft_name], "max_budget_usd": budget_usd, "timeout_seconds": 600},
             "cost_usd": budget_usd, "advances": ["draft_verified"],
             "rationale": "research/content work by a temporary worker; DALEOBANKS verifies it"},
            {"action_id": "request-publish", "capability": "daleobanks.publish", "target": "daleobanks:publish",
             "params": {"daleobanks_root": root, "draft": f"work-orders/{order}/work/{draft_name}"},
             "advances": ["publish_outcome_known"], "requires": ["draft_verified"],
             "rationale": "publishing is external contact: founder decision, then DALEOBANKS's own LIVE gate"}],
        "light_cone": {"capabilities": ["worker.commission", "daleobanks.verify", "daleobanks.outcome"],
                       "targets": [f"work:{order}", "daleobanks:*"], "max_consequence_class": "internal_write",
                       "budget_usd": budget_usd, "horizon": _horizon(horizon_days)},
    }


AVAILABILITY = re.compile(r"(?:^|(?<=[.!?\n]))\s*((?:the\s+)?machine\s+is\s+(?:free|available)\s+(?:all|the\s+whole)\s+"
                          r"shift[^.!?\n]*[.!?]?)", re.I)


def schedule_in_words(*, text: str, horizon_days: float = 2) -> dict:
    """A schedule written in the controlled language, solved by the cortex seed composition.

    The words go to cognition.solve unchanged: extraction, a token audit independent of the
    extractor, CP-SAT with a Z3 optimality certificate, the verifier, and a receipt with a
    reverse translation. If the founder states that the machine is free all shift, that
    sentence becomes the availability evidence; otherwise the result stays conditional on it.
    The check needs a feasible schedule, so an impossible request never closes: GREG asks.
    Read-only: nothing is scheduled or written; acting on the plan is a separate mission.
    """
    stated = AVAILABILITY.search(text)
    request = AVAILABILITY.sub("", text).strip() if stated else text.strip()
    if not request or len(request) > 4000:
        raise ValueError("a schedule request of 1-4000 characters is required")
    digest = __import__("hashlib").sha256(request.encode()).hexdigest()[:10]
    payload = {"schedule_request": {"text": request},
               "declared": {"consequence_class": "read_only", "reversibility": "reversible"}}
    if stated:
        payload["schedule_request"]["availability_evidence"] = f"founder statement in the signed mission: " \
                                                               f"{stated.group(1).strip()!r}"
    step = {"capability": "cognition.solve", "target": f"cognition:schedule-{digest}",
            "params": {"problem_id": f"schedule:{digest}",
                       "problem": {"question": "Best schedule for the stated jobs", "payload": payload}}}
    return {
        "mission_id": f"m:schedule-{digest}",
        "founder_expression": text,
        "intended_effect": "a certified schedule for the stated jobs, with the reading shown back for comparison",
        "priority": 60, "closure": {"kind": "bounded"},
        "success_checks": [{"check_id": "feasible-schedule", "description": "a feasible schedule, checked "
                            "independently of the extractor and the solver",
                            "sensor": step, "predicate": {"op": "equals", "field": "output.answer.1.feasible",
                                                          "value": True}}],
        "strategies": [{"action_id": "solve", **step, "advances": ["feasible-schedule"],
                        "rationale": "compute through the cortex (read-only)"}],
        "light_cone": {"capabilities": ["cognition.solve"], "targets": ["cognition:*"],
                       "max_consequence_class": "read_only", "budget_usd": 0, "horizon": _horizon(horizon_days)},
    }


TEMPLATES["schedule-in-words"] = schedule_in_words


NETWORK_NAME = r"[A-Za-z][A-Za-z0-9_-]{0,31}"
NETWORK_NUMBER = r"\d+(?:\.\d+)?"
NETWORK_LINK = re.compile(rf"^(?P<a>{NETWORK_NAME})\s+(?P<how>to|and)\s+(?P<b>{NETWORK_NAME})\s*[:,]?\s*"
                          rf"(?P<n>{NETWORK_NUMBER})(?:\s+[A-Za-z]+)?$", re.I)
NETWORK_SHORTEST = re.compile(rf"^(?:shortest|cheapest|fastest|quickest)\s+(?:route|path|way)\s+from\s+"
                              rf"(?P<s>{NETWORK_NAME})\s+to\s+(?P<t>{NETWORK_NAME})$", re.I)
NETWORK_FLOW = re.compile(rf"^(?:maximum|max|most)\s+(?:flow|units|throughput|capacity)\s+from\s+"
                          rf"(?P<s>{NETWORK_NAME})\s+to\s+(?P<t>{NETWORK_NAME})$", re.I)


def read_network_words(text: str) -> tuple[str, dict]:
    """The controlled network language, read without a model. Unread sentences stop the plan.

    ``A to B: 4.`` is one direction, ``A and B: 4.`` both; a trailing unit word is allowed.
    One question: ``Shortest route from A to C.`` or ``Maximum flow from A to C.``"""
    sentences = [s.strip() for s in re.split(r"\.(?=\s|$)|[!?;\n]+", text) if s.strip()]
    edges, questions, unread = [], [], []
    for sentence in sentences:
        if link := NETWORK_LINK.match(sentence):
            number = float(link["n"]) if "." in link["n"] else int(link["n"])
            edges.append([link["a"], link["b"], number])
            if link["how"].lower() == "and":
                edges.append([link["b"], link["a"], number])
        elif ask := NETWORK_SHORTEST.match(sentence):
            questions.append(("graph.shortest_path", ask["s"], ask["t"]))
        elif ask := NETWORK_FLOW.match(sentence):
            questions.append(("graph.max_flow", ask["s"], ask["t"]))
        else:
            unread.append(sentence)
    if unread:
        raise ValueError("GREG could not read: " + "; ".join(repr(u[:80]) for u in unread[:5])
                         + ". Write links as 'A to B: 4.' or 'A and B: 4.'")
    if len(questions) != 1 or not edges:
        raise ValueError("state at least one link and exactly one question ('Shortest route from A to C.' or "
                         "'Maximum flow from A to C.')")
    function, source, target = questions[0]
    if function == "graph.max_flow":
        if any(isinstance(e[2], float) for e in edges):
            raise ValueError("capacities for a maximum flow must be whole numbers")
        return function, {"edges": edges, "source": source, "sink": target}
    return function, {"edges": edges, "source": source, "target": target}


def network_in_words(*, text: str, horizon_days: float = 2, auto_attach: bool = False) -> dict:
    """A route or flow question in plain controlled words, answered by an open-source engine.

    GREG has no built-in engine for these functions, so the first such mission opens a
    CapabilityDeficit. Genesis looks for an installed open-source package (NetworkX, SciPy),
    pins it on a Mechanism Card (version, license, upstream, file digest), qualifies it
    against GREG's own oracle, and asks you to attach it unless this signed mission
    pre-authorizes a read-only attach. Every answer is accepted only on GREG's certificate
    (shortest distances: feasible potentials; maximum flow: an equal-capacity cut).
    Read-only: nothing is routed, shipped or written.
    """
    if not text.strip() or len(text) > 4000:
        raise ValueError("a network question of 1-4000 characters is required")
    function, params = read_network_words(text)
    digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:10]
    step = {"function": function, "params": params, "target": f"cognition:network-{digest}"}
    what = "shortest route" if function == "graph.shortest_path" else "maximum flow"
    spec = {
        "mission_id": f"m:network-{digest}",
        "founder_expression": text,
        "intended_effect": f"the {what} for the stated network, with a certificate GREG checks itself",
        "priority": 60, "closure": {"kind": "bounded"},
        "success_checks": [{"check_id": "certified-answer", "description": f"a {what} whose optimality GREG's own "
                            "certificate proves, independent of the engine that computed it",
                            "sensor": step, "predicate": {"op": "equals", "field": "certified", "value": True}}],
        "strategies": [{"action_id": "solve", **step, "advances": ["certified-answer"],
                        "rationale": "compute with a qualified open-source engine (read-only)"}],
        "light_cone": {"capabilities": [f"acquired.{function}.*"], "targets": ["cognition:*"],
                       "max_consequence_class": "read_only", "budget_usd": 0, "horizon": _horizon(horizon_days)},
    }
    if auto_attach:
        spec["auto_attach"] = {"max_consequence_class": "read_only"}
    return spec


TEMPLATES["network-in-words"] = network_in_words


PLAN_NAME = r"[A-Za-z][A-Za-z0-9_]{0,31}"
PLAN_NUMBER = r"-?\d+(?:\.\d+)?"
PLAN_TERM = re.compile(rf"\s*(?P<sign>[+-])?\s*(?P<coef>\d+(?:\.\d+)?)?\s*\*?\s*(?P<name>{PLAN_NAME})\s*")
PLAN_OBJECTIVE = re.compile(r"^(?P<sense>maximi[sz]e|minimi[sz]e)\s+(?P<expr>.+)$", re.I)
PLAN_CONSTRAINT = re.compile(rf"^(?P<expr>.+?)\s*(?P<op><=|>=|=|≤|≥|\bat most\b|\bat least\b|\bequals\b)\s*"
                             rf"(?P<rhs>{PLAN_NUMBER})$", re.I)
PLAN_BETWEEN = re.compile(rf"^(?P<name>{PLAN_NAME})\s+between\s+(?P<lo>{PLAN_NUMBER})\s+and\s+(?P<hi>{PLAN_NUMBER})$",
                          re.I)
PLAN_KEYWORDS = {"maximize", "maximise", "minimize", "minimise", "between", "and", "at", "most", "least", "equals"}


def _plan_number(text: str):
    return float(text) if "." in text else int(text)


def _plan_expr(text: str) -> dict:
    coefficients, position = {}, 0
    for term in PLAN_TERM.finditer(text):
        if term.start() != position or (position and not term["sign"]) or term["name"].lower() in PLAN_KEYWORDS:
            raise ValueError(f"GREG could not read the expression {text.strip()!r}")
        value = _plan_number(term["coef"]) if term["coef"] else 1
        coefficients[term["name"]] = coefficients.get(term["name"], 0) + (-value if term["sign"] == "-" else value)
        position = term.end()
    if position != len(text) or not coefficients:
        raise ValueError(f"GREG could not read the expression {text.strip()!r}")
    return coefficients


def read_plan_words(text: str) -> dict:
    """The controlled planning language, read without a model. Unread sentences stop the plan.

    ``Maximize 40 chairs + 30 tables.`` one objective; ``2 chairs + 3 tables <= 120.`` (also >=, =,
    at most, at least); ``chairs between 0 and 50.`` A quantity is taken as nonnegative unless a
    sentence gives it a lower bound."""
    sentences = [s.strip() for s in re.split(r"\.(?=\s|$)|[!?;\n]+", text) if s.strip()]
    objectives, constraints, bounds, unread = [], [], {}, []
    for sentence in sentences:
        try:
            if goal := PLAN_OBJECTIVE.match(sentence):
                objectives.append({"sense": "max" if goal["sense"].lower().startswith("max") else "min",
                                   "coefficients": _plan_expr(goal["expr"])})
            elif bound := PLAN_BETWEEN.match(sentence):
                bounds[bound["name"]] = (_plan_number(bound["lo"]), _plan_number(bound["hi"]))
            elif con := PLAN_CONSTRAINT.match(sentence):
                op = {"<=": "<=", "≤": "<=", "at most": "<=", ">=": ">=", "≥": ">=", "at least": ">=", "=": "==",
                      "equals": "=="}[con["op"].lower()]
                constraints.append({"name": sentence[:40], "coefficients": _plan_expr(con["expr"]), "op": op,
                                    "rhs": _plan_number(con["rhs"])})
            else:
                unread.append(sentence)
        except ValueError:
            unread.append(sentence)
    if unread:
        raise ValueError("GREG could not read: " + "; ".join(repr(u[:80]) for u in unread[:5])
                         + ". Write 'Maximize 3 x + 2 y.', 'x + y <= 4.', 'x between 0 and 3.'")
    if len(objectives) != 1 or not constraints:
        raise ValueError("state exactly one objective ('Maximize ...' or 'Minimize ...') and at least one constraint")
    names = sorted({n for part in objectives + constraints for n in part["coefficients"]} | set(bounds))
    variables = [{"name": n, "lower": bounds.get(n, (0, None))[0], "upper": bounds.get(n, (0, None))[1]}
                 for n in names]
    return {"variables": variables, "objective": objectives[0], "constraints": constraints}


def plan_in_words(*, text: str, horizon_days: float = 2, auto_attach: bool = False) -> dict:
    """A linear plan in plain controlled words, solved by an open-source engine and certified by GREG.

    The first such mission opens a CapabilityDeficit: genesis looks for an installed open-source
    LP engine (SciPy's HiGHS, OR-Tools GLOP), pins it on a Mechanism Card, qualifies it against
    GREG's exact oracle and asks you to attach it. An answer counts only if GREG's duality
    certificate holds: the plan is feasible and a set of prices proves no plan does better. If no
    plan meets every limit, GREG proves that too (a certified elastic program) and names the
    limits in conflict and the least total violation; if the objective has no limit, GREG shows a
    plan and a direction that improves it forever. Read-only: nothing is bought, made or moved.
    """
    if not text.strip() or len(text) > 4000:
        raise ValueError("a plan of 1-4000 characters is required")
    params = read_plan_words(text)
    digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:10]
    step = {"function": "lp.optimize", "params": params, "target": f"cognition:plan-{digest}"}
    spec = {
        "mission_id": f"m:plan-{digest}",
        "founder_expression": text,
        "intended_effect": "the best plan under the stated limits with prices that prove no plan does better, or a "
                           "proof that no plan meets them (naming the limits in conflict) or that the objective has "
                           "no limit",
        "priority": 60, "closure": {"kind": "bounded"},
        "success_checks": [{"check_id": "certified-plan", "description": "an optimal plan, or the impossibility of "
                            "any plan, proved by GREG's own duality certificate, independent of the engine",
                            "sensor": step, "predicate": {"op": "equals", "field": "certified", "value": True}}],
        "strategies": [{"action_id": "solve", **step, "advances": ["certified-plan"],
                        "rationale": "compute with a qualified open-source engine (read-only)"}],
        "light_cone": {"capabilities": ["acquired.lp.optimize.*"], "targets": ["cognition:*"],
                       "max_consequence_class": "read_only", "budget_usd": 0, "horizon": _horizon(horizon_days)},
    }
    if auto_attach:
        spec["auto_attach"] = {"max_consequence_class": "read_only"}
    return spec


TEMPLATES["plan-in-words"] = plan_in_words
