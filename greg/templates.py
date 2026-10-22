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


def read_economics(manifest: str, economics=None) -> dict | None:
    """The signal's stated economics: an explicit dict or file, else ``economics.json`` beside the manifest.

    ``revenue`` is a bounded estimate request (named factors with low/central/high and units, optional
    expected_units, assumptions, next_measurement); ``causal_support`` is a causal request (design,
    treated, control, dag). Absent economics means the memo states no revenue figure."""
    if economics is None:
        sibling = Path(manifest).expanduser().resolve().with_name("economics.json")
        if not sibling.is_file():
            return None
        economics = str(sibling)
    if isinstance(economics, (str, Path)):
        economics = json.loads(Path(economics).expanduser().read_text(encoding="utf-8"))
    if not isinstance(economics, dict) or not isinstance(economics.get("revenue"), dict) \
            or not isinstance(economics["revenue"].get("factors"), list):
        raise ValueError("economics needs a revenue block with named factors (low, central, high, units)")
    causal = economics.get("causal_support") or {"design": "unstated"}
    if not isinstance(causal, dict):
        raise ValueError("causal_support must be an object (design, treated, control, dag)")
    return {"revenue": economics["revenue"], "causal_support": causal}


def venture_assessment(*, railscout_root: str, wmi_root: str, manifest: str, source_root: str,
                       preauthorize_delivery: bool = False, standing: bool = False, cadence_seconds: int = 3600,
                       horizon_days: float = 2, economics=None) -> dict:
    """Signal -> venture decision memo through the real organs (Bridge A).

    RailScout appraises the signal's real source bytes; WealthMachine's venture engine
    evaluates the packet built from that appraisal; the memo's binding verdict is the
    engine's verdict capped by the evidence status. Delivery is one founder-visible
    file and, like every internal_write, stops at a founder approval unless signed
    into the cone. Nothing is sent, published, bought or contacted.

    When the signal carries economics (``economics.json`` beside the manifest, or passed here),
    the mission first asks GREG's own cognition, read-only, for a certified revenue range and for
    causal support. The memo's revenue section is rendered from those receipts only: a revenue
    figure may not outrun its causal support (directive section 16, the venture case).

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
    stated = read_economics(resolved["manifest"], economics)
    # The memo's revenue section is computed from these economics: the memo, its cognition questions, the mission
    # and the check that it was delivered are all bound to them, so a memo built from other (or no) economics on
    # the same signal never closes this mission.
    basis = "sha256:" + hashlib.sha256(json.dumps(stated, sort_keys=True, separators=(",", ":")).encode()
                                       ).hexdigest() if stated else None
    suffix = f"-{basis[7:15]}" if basis else ""
    resolved = {**resolved, "economics_sha256": basis}
    cognition, checks = [], []
    if stated:
        ids = {"revenue": f"venture-revenue-{thread}{suffix}", "causal": f"venture-causal-{thread}{suffix}"}
        asks = {"revenue": ("estimate", stated["revenue"], "revenue_estimated",
                            {"op": "equals", "field": "abstention_state", "value": "NONE"},
                            "GREG's own revenue range from the stated factors, with units and the dominant uncertainty"),
                "causal": ("treatment_effect", stated["causal_support"], "causal_checked",
                           {"op": "equals", "field": "authority_created", "value": False},
                           "whether any identified causal support exists for the offer producing that revenue; "
                           "an unidentified design is a truthful abstention, not a failure")}
        for role, (operation, data, check_id, predicate, rationale) in asks.items():
            step = {"capability": "cognition.solve", "target": f"cognition:{ids[role]}",
                    "params": {"problem_id": ids[role], "operation": operation, "data": data}}
            checks.append({"check_id": check_id, "description": f"a cognition receipt for the {role} question",
                           "sensor": step, "predicate": predicate})
            cognition.append({"action_id": f"{role}-receipt", **step, "advances": [check_id], "rationale": rationale})
        resolved = {**resolved, "cognition": ids}
    delivery = {"action_id": "assess-venture", "capability": "venture.assess", "params": resolved,
                "target": "deliver:ventures", "advances": ["assessed"],
                **({"requires": [c["check_id"] for c in checks]} if checks else {}),
                "expected_outcome": "one decision memo in the delivery root; no external act",
                "rationale": "run both organs read-only on source bytes; deliver one memo for Alfonso"}
    capabilities = ["venture.status", "fs.read"] + (["venture.assess"] if preauthorize_delivery else []) \
        + (["cognition.solve"] if cognition else [])
    return {
        "mission_id": f"m:venture-watch-{thread}{suffix}" if standing else f"m:venture-{digest[:12]}{suffix}",
        "founder_expression": "Take this signal, find out whether it is a real business, and tell me what to do "
                              "next. Do not act on it; do not let a score outrun the evidence.",
        "intended_effect": "a source-bound venture decision memo for this signal is waiting for Alfonso, with "
                           "the evidence gap and the smallest validation step named",
        "beneficiaries": ["Alfonso", "the buyers the venture would serve"],
        "unacceptable_outcomes": ["contacting anyone", "spending", "publishing", "an unevidenced buyer or budget",
                                  "a go verdict on NEEDS_EVIDENCE"],
        "priority": 65,
        "closure": {"kind": "infinite", "cadence_seconds": cadence_seconds} if standing else {"kind": "bounded"},
        "success_checks": checks + [{"check_id": "assessed", "description": "a memo exists for the current evidence",
                                     "sensor": {"capability": "venture.status",
                                                "params": {"manifest": resolved["manifest"],
                                                           "economics_sha256": basis},
                                                "target": "deliver:ventures"},
                                     "predicate": {"op": "equals", "field": "assessed", "value": True}}],
        "strategies": cognition + [delivery],
        "light_cone": {"capabilities": capabilities, "targets": ["deliver:*", "fs:*"] + (["cognition:*"] if cognition else []),
                       "max_consequence_class": "internal_write" if preauthorize_delivery else "read_only",
                       "budget_usd": 0, "horizon": _horizon(30 if standing else horizon_days)},
    }


def organ_exchange(*, daleobanks_root: str, wmi_root: str, signal: str, preauthorize_delivery: bool = False,
                   legal_principal: str = "alfonso_lopez", horizon_days: float = 2) -> dict:
    """One signal through two organs with authenticated messages, led by GREG (Bridge A, both organs real).

    DALEOBANKS senses and signs; WealthMachine verifies, assesses and signs back; DALEOBANKS verifies and
    records. GREG carries each leg, checks each signature, adapts both messages to the canonical contracts
    and delivers one memo whose verdict may not outrun the evidence. Nothing is sent, published, bought or
    contacted; the memo stops at your approval unless delivery is signed into the cone.
    """
    import hashlib
    resolved = {k: str(Path(v).expanduser().resolve()) for k, v in
                {"daleobanks_root": daleobanks_root, "wmi_root": wmi_root, "signal": signal}.items()}
    digest = hashlib.sha256(Path(resolved["signal"]).read_bytes()).hexdigest()
    params = {**resolved, "legal_principal": legal_principal}
    delivery = {"action_id": "exchange", "capability": "organs.exchange", "params": params,
                "target": "deliver:organs", "advances": ["exchanged"],
                "expected_outcome": "one memo in the delivery root; no external act",
                "rationale": "run both organs on the signal with signed messages; deliver one memo for Alfonso"}
    capabilities = ["organs.exchange_status", "fs.read"] + (["organs.exchange"] if preauthorize_delivery else [])
    return {
        "mission_id": f"m:organs-{digest[:12]}",
        "founder_expression": "Run this signal through DALEOBANKS and WealthMachine as two organs that must "
                              "authenticate to each other, and tell me what they conclude. Do not act on it.",
        "intended_effect": "a memo for Alfonso carrying both organs' verified messages, the canonical "
                           "fields they could not evidence, and a verdict capped by that evidence",
        "beneficiaries": ["Alfonso"],
        "unacceptable_outcomes": ["contacting anyone", "spending", "publishing", "an unverified organ message",
                                  "a go verdict on unevidenced fields"],
        "priority": 65, "closure": {"kind": "bounded"},
        "success_checks": [{"check_id": "exchanged", "description": "a memo exists for this signal",
                            "sensor": {"capability": "organs.exchange_status", "params": {"signal": resolved["signal"]},
                                       "target": "deliver:organs"},
                            "predicate": {"op": "equals", "field": "exchanged", "value": True}}],
        "strategies": [delivery],
        "light_cone": {"capabilities": capabilities, "targets": ["deliver:*", "fs:*"],
                       "max_consequence_class": "internal_write" if preauthorize_delivery else "read_only",
                       "budget_usd": 0, "horizon": _horizon(horizon_days)},
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


RELATIONSHIPS = ("contract", "employment")


def shared_work(*, task: str, person: str, relationship: str, function: str, deliverable: str, acceptance: str,
                workspace_root: Path, horizon_days: float = 30) -> dict:
    """One piece of work done by Alfonso, GREG and a named person together (developmental node N6).

    GREG writes the handoff; the person agrees to the terms and does the work; Alfonso reviews
    it; GREG records the outcome. GREG contacts, hires and pays no one: Alfonso sends the handoff
    and engages and pays the person under the relationship he names here. Each step of the
    person's is one ``HUMAN_WORK`` ask that closes only when its evidence is observed in the
    case folder. The person may decline at any time before delivering: a ``declined.txt``
    carrying the reference is honored as legitimate, so GREG withdraws its ask, never asks that
    step again in this mission and asks Alfonso how to proceed. That the person is real and the
    relationship lawful is attested by Alfonso's acceptance of the closure, not provable here.
    """
    if not asks_human_work(function) or function == "human.founder_review" \
            or not re.fullmatch(r"[a-z0-9_.-]{3,80}", function):
        raise ValueError("function is the person's work: professional.<field> or human.<task> (lowercase)")
    if relationship not in RELATIONSHIPS:
        raise ValueError(f"relationship is one of {RELATIONSHIPS}: a lawful engagement Alfonso makes himself")
    task, person, acceptance = (" ".join(str(v).split()) for v in (task, person, acceptance))
    for name, value, limit in (("task", task, 300), ("person", person, 200), ("acceptance", acceptance, 1000)):
        if not value or len(value) > limit:
            raise ValueError(f"{name} is required (at most {limit} characters)")
    name = Path(deliverable).name
    if not name or name != deliverable or name.startswith(".") or name in SHARED_WORK_FILES:
        raise ValueError("deliverable is a plain file name placed in the case folder")
    slug = re.sub(r"[^a-z0-9]+", "-", task.lower()).strip("-")[:40].strip("-")
    if len(slug) < 3:
        raise ValueError("task needs at least three letters or digits")
    mission_id, ref = f"m:shared-{slug}", f"WORK-{slug.upper()}"
    folder = Path(workspace_root) / mission_id.replace(":", "_")

    def read(check_id, file, description, predicate):
        return {"check_id": check_id, "description": description,
                "sensor": {"capability": "fs.read", "params": {"path": str(folder / file)}, "target": f"fs:{file}"},
                "predicate": predicate}
    declined = {"sensor": {"capability": "fs.read", "params": {"path": str(folder / "declined.txt")},
                           "target": "fs:declined.txt"},
                "predicate": {"op": "contains", "field": "text", "value": ref}}
    handoff = (f"# Work handoff {ref}\n\nTask: {task}\nFor: {person}, under a {relationship} that Alfonso Lopez "
               f"arranges and pays directly\nDeliverable: {name}, placed in the case folder\nAcceptance: "
               f"{acceptance}\n\nYour written agreement to these terms, carrying {ref}, is kept as consent.txt.\n"
               "You may decline at any time before delivering. If you do, nothing more is asked of you for "
               "this work.\nGREG, Alfonso's software, wrote this handoff; it contacts and pays no one.\n")
    target = "person:" + (re.sub(r"[^a-z0-9]+", "-", person.lower()).strip("-")[:60] or "named")
    return {
        "mission_id": mission_id,
        "founder_expression": f"Do {task} with {person} under a {relationship}; {name} is accepted when: {acceptance}",
        "intended_effect": "the work is agreed, delivered, reviewed by Alfonso and recorded, with the person free to "
                           "decline; GREG writes only the handoff and the outcome record",
        "priority": 55, "closure": {"kind": "bounded", "cadence_seconds": 3600},
        "success_checks": [
            read("handoff_written", "handoff.md", "GREG's handoff names the task, terms and reference",
                 {"op": "contains", "field": "text", "value": ref}),
            read("consent_recorded", "consent.txt", f"{person}'s written agreement carries {ref}",
                 {"op": "contains", "field": "text", "value": ref}),
            read("deliverable_received", name, f"{name} is in the case folder",
                 {"op": "equals", "field": "exists", "value": True}),
            read("founder_review", "review.txt", f"Alfonso accepted the deliverable: ACCEPT {ref}",
                 {"op": "contains", "field": "text", "value": f"ACCEPT {ref}"}),
            read("outcome_recorded", "outcome.md", "GREG recorded the outcome",
                 {"op": "contains", "field": "text", "value": ref})],
        "strategies": [
            {"action_id": "write-handoff", "capability": "fs.write",
             "params": {"relative_path": "handoff.md", "content": handoff}, "target": "workspace:handoff.md",
             "advances": ["handoff_written"], "rationale": "the person learns the task, terms and their right to decline"},
            {"action_id": "agree-terms", "function": "human.agree_terms", "target": target,
             "advances": ["consent_recorded"], "requires": ["handoff_written"], "declined_if": declined,
             "rationale": f"Alfonso sends the handoff to {person} and saves their written agreement"},
            {"action_id": "do-the-work", "function": function, "target": target,
             "advances": ["deliverable_received"], "requires": ["consent_recorded"], "declined_if": declined,
             "rationale": f"{person} does {task} and the deliverable is saved to the case folder"},
            {"action_id": "review", "function": "human.founder_review", "target": "person:alfonso",
             "advances": ["founder_review"], "requires": ["deliverable_received"],
             "rationale": f"Alfonso checks {name} against the acceptance terms and writes ACCEPT {ref} or what "
                          "to revise"},
            {"action_id": "record-outcome", "capability": "fs.write",
             "params": {"relative_path": "outcome.md",
                        "content": f"# Outcome {ref}\n\n{person} delivered {name} for: {task}, under a "
                                   f"{relationship}. Alfonso reviewed it against: {acceptance}\n"},
             "target": "workspace:outcome.md", "advances": ["outcome_recorded"],
             "requires": ["consent_recorded", "deliverable_received", "founder_review"],
             "rationale": "the agreed, delivered and reviewed work is recorded"}],
        "light_cone": {"capabilities": ["fs.read", "fs.write"], "targets": ["fs:*", "workspace:*", "person:*"],
                       "max_consequence_class": "internal_write", "budget_usd": 0, "horizon": _horizon(horizon_days)},
    }


SHARED_WORK_FILES = ("handoff.md", "consent.txt", "review.txt", "outcome.md", "declined.txt")


def asks_human_work(function) -> bool:
    from greg.asks import human_work
    return human_work(function) is not None


def business_case(*, case: str, buyer: str, offer: str, price: str, currency: str, acceptance: str,
                  workspace_root: Path, statement: str = "statement.csv", columns: dict | None = None,
                  minor_units: bool = False, horizon_days: float = 45, venture: str | None = None,
                  approve_writes: bool = False) -> dict:
    """One customer case through the Kernel's commercial order, as a founder-signed mission (node N3).

    problem -> buyer -> offer -> payment -> delivery -> customer outcome (business/commercial_loop.py).
    GREG drafts the offer and writes the settlement record inside its workspace; every act that
    reaches a person outside the body is ``human.*`` work (one costed ask each, no contact, no
    spend). Payment counts only when ``business.reconcile`` finds exactly one posting of the signed
    amount and currency carrying the case reference in the statement Alfonso exports. Each stage
    ``requires`` the one before it, and the settlement record requires payment, delivery and the
    buyer's confirmation, so nothing is recorded as settled out of order.

    ``venture`` names the business the case serves (books and transfer are measured per venture).
    ``approve_writes`` keeps GREG's cone read-only, so drafting the offer and writing the settlement
    each stop for Alfonso's approval; a procedure he later ratifies may pre-approve them.
    """
    amount = business_loop_amount(price)
    if venture is not None and not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,40}", venture):
        raise ValueError("venture is a short lowercase name (letters, digits, hyphens)")
    currency = currency.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("currency is a three-letter code such as USD")
    for name, value in (("buyer", buyer), ("offer", offer), ("acceptance", acceptance)):
        if not str(value).strip():
            raise ValueError(f"{name} must be stated before the case is signed")
    if Path(statement).name != statement or statement.startswith("."):
        raise ValueError("statement is a plain file name in this mission's folder")
    slug = re.sub(r"[^a-z0-9]+", "-", case.lower()).strip("-")[:40]
    if len(slug) < 3:
        raise ValueError("case needs a short name of at least 3 letters or digits")
    mission_id = f"m:case-{slug}"
    ref = f"CASE-{slug.upper()}"
    folder = Path(workspace_root) / mission_id.replace(":", "_")

    def evidence(check_id, name, description):
        path = folder / name
        return {"check_id": check_id, "description": description,
                "sensor": {"capability": "fs.read", "params": {"path": str(path)}, "target": f"fs:{name}"},
                "predicate": {"op": "contains", "field": "text", "value": ref}}

    offer_text = (f"# Offer {ref}\n\nFor: {buyer}\nOffer: {offer}\nPrice: {amount} {currency}\n"
                  f"Accepted when: {acceptance}\nPay with the reference {ref} so the payment can be reconciled.\n")
    settlement = (f"{ref} settled: {amount} {currency} from {buyer}, reconciled against {statement}; "
                  "delivered and confirmed by the buyer\n")
    return {
        "mission_id": mission_id,
        "founder_expression": (f"Run case {ref}: offer {offer} to {buyer} at {amount} {currency}; "
                               f"accepted when {acceptance}."),
        "intended_effect": (f"{buyer} receives {offer}, confirms it met the acceptance terms, and {amount} {currency} "
                            "is reconciled to the cent; GREG itself contacts, charges and pays no one"),
        "priority": 70, "closure": {"kind": "bounded", "cadence_seconds": 3600},
        "success_checks": [
            evidence("offer_drafted", "offer.md", "the offer names buyer, price and the precommitted acceptance terms"),
            evidence("buyer_accepted", "acceptance.txt", f"{buyer}'s written acceptance, carrying {ref}"),
            {"check_id": "paid", "description": f"exactly one posting of {amount} {currency} carrying {ref}",
             "sensor": {"capability": "business.reconcile",
                        "params": {"path": str(folder / statement), "amount": str(amount), "currency": currency,
                                   "reference": ref, **({"columns": columns} if columns else {}),
                                   **({"minor_units": True} if minor_units else {})},
                        "target": f"fs:{statement}"},
             "predicate": {"op": "equals", "field": "matched", "value": True}},
            evidence("delivered", "delivery.txt", f"a delivery record for {ref}"),
            evidence("outcome_confirmed", "outcome.txt", f"{buyer}'s confirmation that the acceptance terms were met"),
            evidence("settled", "settlement.md", "GREG's settlement record, written only after the stages above"),
        ],
        "strategies": [
            {"action_id": "draft-offer", "capability": "fs.write", "target": "workspace:offer.md",
             "params": {"relative_path": "offer.md", "content": offer_text}, "advances": ["offer_drafted"],
             "rationale": "draft the offer inside the workspace; sending it is a person's act"},
            {"action_id": "send-offer", "function": "human.send_offer", "target": "person:human.send_offer",
             "requires": ["offer_drafted"], "advances": ["buyer_accepted"],
             "rationale": f"you send offer.md to {buyer} and save their written acceptance as acceptance.txt"},
            {"action_id": "collect-payment", "function": "human.collect_payment",
             "target": "person:human.collect_payment", "requires": ["buyer_accepted"], "advances": ["paid"],
             "rationale": f"{buyer} pays with the reference {ref}; you export the statement as {statement}"},
            {"action_id": "deliver", "function": "human.deliver", "target": "person:human.deliver",
             "requires": ["paid"], "advances": ["delivered"],
             "rationale": f"deliver {offer} and save a delivery record carrying {ref} as delivery.txt"},
            {"action_id": "confirm-outcome", "function": "human.confirm_outcome",
             "target": "person:human.confirm_outcome", "requires": ["delivered"], "advances": ["outcome_confirmed"],
             "rationale": f"{buyer} confirms the acceptance terms were met; save it carrying {ref} as outcome.txt"},
            {"action_id": "record-settlement", "capability": "fs.write", "target": "workspace:settlement.md",
             "params": {"relative_path": "settlement.md", "content": settlement},
             "requires": ["paid", "delivered", "outcome_confirmed"], "advances": ["settled"],
             "rationale": "record the settlement only after payment, delivery and confirmation are all observed"},
        ],
        "light_cone": {"capabilities": ["fs.read", "business.reconcile"] if approve_writes else
                       ["fs.read", "fs.write", "business.reconcile"],
                       "targets": ["fs:*", "workspace:*", "person:*"],
                       "max_consequence_class": "read_only" if approve_writes else "internal_write",
                       "budget_usd": 0, "horizon": _horizon(horizon_days)},
        **({"venture": venture} if venture else {}),
        "provenance": {"origin": "template:business-case", "planner": "greg.templates/1",
                       "inputs": {"reference": ref, "buyer": " ".join(buyer.split()), "offer": " ".join(offer.split()),
                                  "price": str(amount), "currency": currency,
                                  "acceptance": " ".join(acceptance.split())}},
    }


def business_loop_amount(price) -> str:
    """A signed price as a plain decimal string with at most two places, never a float."""
    from decimal import Decimal, InvalidOperation
    try:
        value = Decimal(str(price).strip())
    except InvalidOperation:
        raise ValueError("price must be a number such as 250 or 249.99") from None
    if not value.is_finite() or value <= 0 or value.as_tuple().exponent < -2:
        raise ValueError("price must be positive with at most two decimal places")
    return f"{value:.2f}"


TEMPLATES = {"repo-guardian": repo_guardian, "integration-watch": integration_watch, "workspace-note": workspace_note,
             "engineering-brief": engineering_brief, "venture-assessment": venture_assessment,
             "verify-download": verify_download, "word-limit": word_limit, "human-work": human_work,
             "business-case": business_case, "shared-work": shared_work}


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
                workspace_root: Path | None = None, script: str | None = None) -> dict:
    """Software work through a temporary coding worker; GREG appraises it independently, then hands off.

    1. ``worker.commission`` (internal_write, spends at most ``budget_usd``): a real worker edits a private
       clone; GREG collects the diff, runs acceptance with no network and commits on ``greg/<order>``.
    2. ``worker.appraise`` (read-only sensor): fresh clone, patch re-applied, scope and protected-surface
       checks, acceptance re-run. Only ``ACCEPTED`` closes the check; a protected surface yields a
       founder decision, never acceptance.
    ``script`` (with ``provider="script"``): the founder-signed program that does the work instead of a
    model-backed worker; it runs in the same confined envelope with no network (``greg.workers.ScriptWorker``).
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
                        "max_budget_usd": budget_usd, "timeout_seconds": timeout_seconds,
                        **({"context": script} if script else {})},
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
                    max_chars: int = 280, horizon_days: float = 2, founder_expression: str | None = None,
                    bound_claims: bool = True, quality: str = "unverified", python: str | None = None) -> dict:
    """GREG -> research/content worker -> DALEOBANKS verification -> publish request through both gates.

    The draft is written by a temporary worker from a read-only source; DALEOBANKS's own checks plus
    figure-to-source binding must pass before the publish request may run (``requires``). Publishing is
    external_contact: outside this cone, so it stops for a founder decision; even when approved,
    DALEOBANKS's LIVE kill switch and credentials decide, and a dry-run is reported as a block.

    With ``bound_claims`` (the default), the worker also lists each sentence with the source spans that support
    it, and the Task Fabric's evaluator (``worker.appraise``) asks the Mind about every sentence against GREG's
    own copy of the source: the publish request also requires that appraisal. ``quality`` is the signer's
    declaration about the source. ``bound_claims=False`` keeps the figure-only floor.
    """
    source = str(Path(source).expanduser().resolve())
    root = str(Path(daleobanks_root).expanduser().resolve())
    draft_name, claims_name = "post.txt", "post.claims.json"
    contract = {"claims": claims_name, "quality": quality, "expires_at": _horizon(horizon_days)}
    acceptance = {"output": draft_name,
                  "criteria": f"<= {max_chars} characters; no figures absent from the source; no "
                              "hype, no calls to buy; not a proposal (no pilot/KPI language)"}
    objective = (f"{brief} Write the post as plain text, at most {max_chars} characters, "
                 "stating only facts present in the input; every number must appear in the input.")
    checks = [{"check_id": "draft_verified", "description": "DALEOBANKS checks and source binding pass",
               "sensor": {"capability": "daleobanks.verify",
                          "params": {"daleobanks_root": root, "source": source, "max_chars": max_chars,
                                     "draft": f"work-orders/{order}/work/{draft_name}",
                                     **({"python": python} if python else {})},
                          "target": "daleobanks:verify"},
               "predicate": {"op": "equals", "field": "verdict", "value": "VERIFIED"}}]
    if bound_claims:
        acceptance["bound_claims"] = contract
        objective += (" Keep the source's hedges, negations, scope, direction and names; list each sentence's "
                      f"supporting spans in {claims_name}.")
        checks.append({"check_id": "draft_appraised",
                       "description": "the Task Fabric's evaluator: every sentence is a claim the Mind answered "
                                      "as written against GREG's copy of the source",
                       "sensor": {"capability": "worker.appraise",
                                  "params": {"order": order, "bound_claims": contract}, "target": f"work:{order}"},
                       "predicate": {"op": "equals", "field": "verdict", "value": "ACCEPTED"}})
    gates = [c["check_id"] for c in checks]
    publish = {"daleobanks_root": root, "draft": f"work-orders/{order}/work/{draft_name}",
               **({"python": python} if python else {})}
    return {
        "mission_id": f"m:media-{_slug(order)}",
        "founder_expression": founder_expression or f"DALEOBANKS: {brief}",
        "intended_effect": "a source-bound post is drafted, verified by DALEOBANKS and submitted to its publishing "
                           "gate; the truthful outcome (posted or blocked) returns to GREG",
        "priority": 50, "closure": {"kind": "bounded"},
        "success_checks": checks + [
            {"check_id": "publish_outcome_known", "description": "DALEOBANKS's ledger holds the request's outcome",
             "sensor": {"capability": "daleobanks.outcome", "params": {}, "target": "daleobanks:outcome"},
             "predicate": {"op": "equals", "field": "requested", "value": True}}],
        "strategies": [
            {"action_id": "draft-post", "capability": "worker.commission", "target": f"work:{order}",
             "params": {"order": order, "mode": "document", "inputs": [source], "objective": objective,
                        "acceptance": acceptance,
                        "allowed_paths": [draft_name] + ([claims_name] if bound_claims else []),
                        "max_budget_usd": budget_usd, "timeout_seconds": 600},
             "cost_usd": budget_usd, "advances": gates,
             "rationale": "research/content work by a temporary worker; DALEOBANKS verifies it"
                          + ("; the Mind appraises every sentence" if bound_claims else "")},
            {"action_id": "request-publish", "capability": "daleobanks.publish", "target": "daleobanks:publish",
             "params": publish, "advances": ["publish_outcome_known"], "requires": gates,
             "rationale": "publishing is external contact: founder decision, then DALEOBANKS's own LIVE gate"}],
        "light_cone": {"capabilities": ["worker.commission", "daleobanks.verify", "daleobanks.outcome"]
                                       + (["worker.appraise"] if bound_claims else []),
                       "targets": [f"work:{order}", "daleobanks:*"], "max_consequence_class": "internal_write",
                       "budget_usd": budget_usd, "horizon": _horizon(horizon_days)},
    }


def daleobanks_paraphrase(*, daleobanks_root: str, source: str, draft: str, claims: list,
                          quality: str = "unverified", python: str | None = None, content_type: str = "reply",
                          max_chars: int = 600, horizon_days: float = 2, founder_expression: str | None = None) -> dict:
    """Media case (directive section 16): a DALEOBANKS draft that restates a source, checked claim by claim.

    ``claims`` lists each sentence of the draft with the exact source spans that support it:
    ``[{"text": sentence, "quotes": [span, ...]}]``. GREG's evidence family answers each claim first
    (``cognition.solve``, read-only): bound to its spans and showing none of the six detected kinds of change
    (figures, negation, certainty, scope, direction, named terms). DALEOBANKS's verify then runs its own content
    checks and requires every sentence of the draft to be a claim the Mind answered as written. Consequence-inert:
    the light cone holds no publish capability, so nothing can be posted from this mission.
    """
    import hashlib
    from greg.cognition.contracts import digest
    source_path = Path(source).expanduser().resolve()
    root = str(Path(daleobanks_root).expanduser().resolve())
    text = source_path.read_text(encoding="utf-8")
    thread = hashlib.sha256(Path(draft).expanduser().resolve().read_bytes()).hexdigest()[:12]
    src = {"id": "source", "text": text, "digest": digest(text), "quality": quality, "expires_at": _horizon(horizon_days),
           "provenance": f"{source_path} sha256:{hashlib.sha256(text.encode()).hexdigest()}"}
    ids, checks, strategies = {}, [], []
    for i, claim in enumerate(claims, 1):
        if not claim.get("quotes"):
            raise ValueError(f"claim {i} has no supporting span; every sentence must cite the source")
        ids[f"c{i}"] = f"media-claim-{thread}-{i}"
        step = {"capability": "cognition.solve", "target": f"cognition:{ids[f'c{i}']}",
                "params": {"problem_id": ids[f"c{i}"], "operation": "bind_evidence",
                           "data": {"claim": claim["text"], "sources": [src],
                                    "bindings": [{"source_id": "source", "quote": q, "relationship": "supports"}
                                                 for q in claim["quotes"]]}}}
        checks.append({"check_id": f"claim_{i}_checked", "description": f"GREG's evidence receipt for claim {i}",
                       "sensor": step, "predicate": {"op": "equals", "field": "authority_created", "value": False}})
        strategies.append({"action_id": f"claim-{i}-receipt", **step, "advances": [f"claim_{i}_checked"],
                           "rationale": "bind the claim to its spans and check what it changes; an abstention is a "
                                        "truthful answer, not a failure"})
    verify = {"capability": "daleobanks.verify", "target": "daleobanks:verify",
              "params": {"daleobanks_root": root, "draft": str(Path(draft).expanduser().resolve()),
                         "source": str(source_path), "max_chars": max_chars, "content_type": content_type,
                         "cognition": ids, **({"python": python} if python else {})}}
    checks.append({"check_id": "paraphrase_verified",
                   "description": "DALEOBANKS's checks pass and every sentence is a claim answered as written",
                   "sensor": verify, "predicate": {"op": "equals", "field": "verdict", "value": "VERIFIED"}})
    strategies.append({"action_id": "verify-paraphrase", **verify, "advances": ["paraphrase_verified"],
                       "requires": [c["check_id"] for c in checks[:-1]],
                       "rationale": "DALEOBANKS's own content checks over a draft whose claims GREG has answered"})
    return {
        "mission_id": f"m:paraphrase-{thread}",
        "founder_expression": founder_expression or "DALEOBANKS restates a source without changing what it says",
        "intended_effect": "a draft that restates its source is checked claim by claim against it; a sentence that "
                           "changes a figure, a negation, a hedge, a scope, a direction or a name is held back",
        "priority": 50, "closure": {"kind": "bounded"},
        "success_checks": checks, "strategies": strategies,
        "light_cone": {"capabilities": ["cognition.solve", "daleobanks.verify", "fs.read"],
                       "targets": ["cognition:*", "daleobanks:verify"], "max_consequence_class": "read_only",
                       "budget_usd": 0, "horizon": _horizon(horizon_days)},
    }


def research_post(*, url: str, steps: list[dict], session: str, expect: dict, daleobanks_root: str, brief: str,
                  order: str, workspace_root: Path, budget_usd: float = 2.0, max_chars: int = 280,
                  horizon_days: float = 2, founder_expression: str | None = None, on_challenge: str = "stop") -> dict:
    """One signed mission: browser -> recorded facts -> content worker -> DALEOBANKS -> publish request.

    The browser's extracted values reach the worker through a typed edge (``bind``): the
    ``record-facts`` action writes the latest ``operate-browser`` receipt's ``extracted``
    object into this mission's workspace, so nobody relays facts by hand. The worker reads
    that file as untrusted data, DALEOBANKS binds every figure in the draft to it, and the
    publish request is external contact: outside the cone, so it stops for a founder decision
    and then meets DALEOBANKS's own LIVE gate.
    """
    from urllib.parse import urlsplit
    host = urlsplit(url).hostname or ""
    mission_id = f"m:research-{_slug(order)}"
    facts = str(Path(workspace_root).resolve() / mission_id.replace(":", "_") / "facts.json")
    browse = browser_task(url=url, steps=steps, session=session, expect=expect, on_challenge=on_challenge)
    post = daleobanks_post(daleobanks_root=daleobanks_root, source=facts, brief=brief, order=order,
                           budget_usd=budget_usd, max_chars=max_chars)
    draft = next(x for x in post["strategies"] if x["action_id"] == "draft-post")
    draft = {**draft, "requires": ["facts_recorded"],
             "params": {**draft["params"], "inputs": [facts]}}
    return {
        "mission_id": mission_id,
        "founder_expression": founder_expression or f"Research {host} and draft a DALEOBANKS post: {brief}",
        "intended_effect": "facts retrieved by operating the site become a source-bound post that DALEOBANKS "
                           "verifies and submits to its publishing gate, in one mission with no manual hand-off",
        "priority": 50, "closure": {"kind": "bounded"},
        "success_checks": browse["success_checks"] + [
            {"check_id": "facts_recorded", "description": "the browser's extracted facts are recorded for binding",
             "sensor": {"capability": "fs.read", "params": {"path": facts}, "target": "fs:facts.json"},
             "predicate": {"op": "contains", "field": "text", "value": "{"}}] + post["success_checks"],
        "strategies": browse["strategies"] + [
            {"action_id": "record-facts", "capability": "fs.write", "target": "workspace:facts.json",
             "params": {"relative_path": "facts.json"},
             "bind": [{"param": "content", "from": {"action_id": "operate-browser", "field": "extracted"},
                       "type": "object", "render": "json", "max_bytes": 32768}],
             "requires": ["retrieved"], "advances": ["facts_recorded"],
             "rationale": "typed edge: the browser receipt's extracted values become the worker's source"},
            draft, next(x for x in post["strategies"] if x["action_id"] == "request-publish")],
        "light_cone": {"capabilities": sorted(set(browse["light_cone"]["capabilities"]) |
                                              set(post["light_cone"]["capabilities"]) | {"fs.write", "fs.read"}),
                       "targets": browse["light_cone"]["targets"] + ["workspace:facts.json", "fs:facts.json"]
                       + post["light_cone"]["targets"],
                       "max_consequence_class": "internal_write", "budget_usd": budget_usd,
                       "horizon": _horizon(horizon_days)},
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


def mcp_tool(*, server: str, root: str, command: list[str], tool: str, arguments: dict, readable=(),
             expect: dict | None = None, founder_expression: str | None = None, horizon_days: float = 1) -> dict:
    """Ask one tool of an MCP server the founder installed (``mcp.call``), read-only by construction.

    The server runs confined with no network and a read-only filesystem, so whatever the tool does, nothing changes.
    The check passes when the server answers (or, with ``expect``, when its answer meets that predicate); the answer
    itself is kept with the observation's receipt, as untrusted external data."""
    digest = hashlib.sha256(json.dumps([tool, arguments], sort_keys=True).encode()).hexdigest()[:8]
    params = {"server": server, "root": str(root), "command": [str(c) for c in command], "tool": tool,
              "arguments": dict(arguments)}
    if readable:
        params["readable"] = [str(r) for r in readable]
    return {
        "mission_id": f"m:mcp-{_slug(server, 20)}-{_slug(tool, 30)}-{digest}",
        "founder_expression": founder_expression or f"Ask the {server} server: {tool}",
        "intended_effect": f"the {server} server's {tool} tool answers, and the answer is kept with its receipt",
        "priority": 50, "closure": {"kind": "bounded"},
        "success_checks": [{
            "check_id": "answered", "description": f"the {server} server's {tool} answered",
            "sensor": {"capability": "mcp.call", "params": params, "target": f"mcp:{server}"},
            "predicate": expect or {"op": "exists", "field": "text"}}],
        "strategies": [],
        "light_cone": {"capabilities": ["mcp.call"], "targets": [f"mcp:{server}"],
                       "max_consequence_class": "read_only", "budget_usd": 0.0, "horizon": _horizon(horizon_days)}}


TEMPLATES["mcp-tool"] = mcp_tool


def mcp_act(*, server: str, root: str, command: list[str], tool: str, arguments: dict, writable: list,
            check_path: str, expect: dict, readable=(), founder_expression: str | None = None,
            horizon_days: float = 1) -> dict:
    """One change by a tool of an MCP server the founder installed (``mcp.act``), inside the scope they approve.

    The light cone stops at read-only, so the act always waits for the founder's decision on its exact scope: the
    paths it may write (everything else stays read-only), no network, no credentials. GREG checks the effect itself
    by reading ``check_path``; the server's own answer is untrusted data. If the effect is already there, nothing
    runs."""
    digest = hashlib.sha256(json.dumps([tool, arguments, writable], sort_keys=True).encode()).hexdigest()[:8]
    params = {"server": server, "root": str(root), "command": [str(c) for c in command], "tool": tool,
              "arguments": dict(arguments), "writable": [str(w) for w in writable]}
    if readable:
        params["readable"] = [str(r) for r in readable]
    name = Path(check_path).name
    return {
        "mission_id": f"m:mcp-act-{_slug(server, 20)}-{_slug(tool, 30)}-{digest}",
        "founder_expression": founder_expression or f"Use the {server} server's {tool}",
        "intended_effect": f"{check_path} shows the change made by the {server} server's {tool}; nothing outside "
                           f"{', '.join(params['writable'])} changes",
        "priority": 50, "closure": {"kind": "bounded"},
        "success_checks": [{
            "check_id": "changed", "description": f"GREG reads {name} and finds the change",
            "sensor": {"capability": "fs.read", "params": {"path": str(check_path)}, "target": f"fs:{name}"},
            "predicate": expect}],
        "strategies": [{"action_id": "act", "capability": "mcp.act", "params": params, "target": f"mcp:{server}",
                        "advances": ["changed"],
                        "rationale": f"the {server} server's {tool}, inside the scope the founder approves"}],
        "light_cone": {"capabilities": ["mcp.act", "fs.read"], "targets": [f"mcp:{server}", f"fs:{name}"],
                       "max_consequence_class": "read_only", "budget_usd": 0.0, "horizon": _horizon(horizon_days)}}


TEMPLATES["mcp-act"] = mcp_act


REMOTE_EVIDENCE = {
    "same_service": "a read-after-write through the service's own host: it shows the service's state, not an "
                    "independent corroboration of it",
    "separate_host": "a read through a different host than the service's; GREG cannot show that host is independent "
                     "of the service, so this is not proven independent corroboration",
}


def remote_evidence(url: str, check_url: str) -> str:
    """Which evidence a page check is: a read-after-write through the same service, or a read through another host.

    Same service only when the page is on the service's own host or a name under it. Without a public-suffix list,
    sharing the last two labels proves nothing (``alice.github.io`` and ``mallory.github.io``, ``evil.co.uk``), and
    neither does a parent name, so every other case gets the cautious label, which claims no independence either."""
    import ipaddress
    from urllib.parse import urlsplit
    service = (urlsplit(url).hostname or "").rstrip(".")
    page = (urlsplit(check_url).hostname or "").rstrip(".")
    if not service or not page:
        return "separate_host"
    if page == service:
        return "same_service"
    for host in (service, page):
        try:
            ipaddress.ip_address(host)
            return "separate_host"      # an address is the same service only when it is the same address
        except ValueError:
            pass
    return "same_service" if service.count(".") >= 1 and page.endswith("." + service) else "separate_host"


def mcp_remote_act(*, server: str, url: str, tool: str, arguments: dict, bearer: str | None, check_url: str,
                   expect_text: str, hosts=(), founder_expression: str | None = None, horizon_days: float = 1) -> dict:
    """One call to a tool of a hosted MCP server (``mcp.act`` by URL), inside the scope the founder approves.

    A call on someone else's machine cannot be made read-only, so it always waits for the founder's decision, which
    shows the server, the hosts it may reach and the credential handle. GREG checks the effect itself by rendering a
    page the founder named (``browser.render``, which reaches only that page's host) and finding the text there; the
    server's own answer is untrusted data. If the page already shows it, nothing runs."""
    from urllib.parse import urlsplit
    digest = hashlib.sha256(json.dumps([url, tool, arguments], sort_keys=True).encode()).hexdigest()[:8]
    params = {"server": server, "url": url, "tool": tool, "arguments": dict(arguments)}
    if bearer:
        params["bearer"] = bearer
    if hosts:
        params["hosts"] = [str(h) for h in hosts]
    page = urlsplit(check_url).hostname
    return {
        "mission_id": f"m:mcp-remote-{_slug(server, 20)}-{_slug(tool, 30)}-{digest}",
        "founder_expression": founder_expression or f"Use the {server} service's {tool}",
        "intended_effect": f"{check_url} shows {expect_text!r} after the {server} service's {tool}",
        "priority": 50, "closure": {"kind": "bounded"},
        "success_checks": [{
            "check_id": "shown", "description": f"GREG renders {check_url} and finds the text "
                                                f"({REMOTE_EVIDENCE[remote_evidence(url, check_url)]})",
            "sensor": {"capability": "browser.render", "params": {"url": check_url}, "target": f"web:{page}"},
            "predicate": {"op": "contains", "field": "text", "value": expect_text}}],
        "strategies": [{"action_id": "act", "capability": "mcp.act", "params": params, "target": f"mcp:{server}",
                        "advances": ["shown"],
                        "rationale": f"the {server} service's {tool}, inside the scope the founder approves"}],
        "light_cone": {"capabilities": ["mcp.act", "browser.render"], "targets": [f"mcp:{server}", f"web:{page}"],
                       "max_consequence_class": "read_only", "budget_usd": 0.0, "horizon": _horizon(horizon_days)}}


TEMPLATES["mcp-remote-act"] = mcp_remote_act


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


def constructed_question(*, function: str, params: dict, horizon_days: float = 2, auto_attach: bool = False) -> dict:
    """A question for a function GREG has no engine for, answered by a capability it constructs.

    Genesis reduces the question onto an engine it can already certify (maximum flow, linear
    programming), acquiring that engine first if needed, qualifies the construction on the
    function's own brute-force oracle through the real engine, and asks you to attach it unless
    this signed mission pre-authorizes a read-only attach. Every answer carries a certificate in
    your problem's own terms (for staffing: the orders and the only workers who could serve them).
    Read-only: nobody is assigned, scheduled or paid.
    """
    from greg.genesis import CATALOG
    from greg.recombine import REDUCTIONS, chain

    found = chain(function, CATALOG)
    if found is None:
        raise ValueError(f"GREG has no reduction chain for {function!r}; known: {sorted(REDUCTIONS)}")
    path, engine = found
    REDUCTIONS[function].normalize(params)          # refuse a malformed question before it is signed
    digest = hashlib.sha256(json.dumps([function, params], sort_keys=True).encode()).hexdigest()[:10]
    step = {"function": function, "params": params, "target": f"cognition:{function}-{digest}"}
    spec = {
        "mission_id": f"m:constructed-{digest}",
        "founder_expression": f"{function}: {json.dumps(params, sort_keys=True)[:3000]}",
        "intended_effect": f"{REDUCTIONS[function].description}, with a certificate GREG checks itself",
        "priority": 60, "closure": {"kind": "bounded"},
        "success_checks": [{"check_id": "certified-answer", "description": "an answer whose optimality (or "
                            "impossibility) GREG proves in the problem's own terms, independent of the engine",
                            "sensor": step, "predicate": {"op": "equals", "field": "certified", "value": True}}],
        "strategies": [{"action_id": "solve", **step, "advances": ["certified-answer"],
                        "rationale": "construct the function by certified reduction (read-only): "
                                     + " -> ".join([r.function for r in path] + [engine])}],
        "light_cone": {"capabilities": [f"composed.{function}.*", f"acquired.{engine}.*"],
                       "targets": ["cognition:*"], "max_consequence_class": "read_only", "budget_usd": 0,
                       "horizon": _horizon(horizon_days)},
    }
    if auto_attach:
        spec["auto_attach"] = {"max_consequence_class": "read_only"}
    return spec


TEMPLATES["constructed-question"] = constructed_question


FIRST_MISSION_WORDS = re.compile(r"\b(first mission|where (?:am i|i am) (?:trying to go|going)|highest[- ]value "
                                 r"(?:work|opportunit)|what should (?:greg|you) (?:work on|do) next)\b", re.I)


def first_mission(*, kernel_root: str, effort_budget: int = 8, run: str | None = None, horizon_days: float = 1,
                  founder_expression: str | None = None) -> dict:
    """The Founder's First Mission: one signed mission across Mind, Hands, Foundry and appraisal.

    survey (read the authorized sources, reconstruct the objective, route founder-only items to the
    decision queue) -> select (``cognition.dp_knapsack``: exact selection under the signed effort
    budget, with its own verifier) and compose (which existing machinery advances each candidate,
    and what is missing) -> dossier (one private deliverable to the founder's delivery root) ->
    ``institution.appraise`` as the success sensor: an independent re-survey, a different exact
    algorithm and a greedy replay. Steps hand typed outputs to each other through ``bind`` edges,
    so nobody relays data by hand and a crash resumes from retained receipts without repeating
    a completed step. Nothing is sent, published, spent or merged.
    """
    if not isinstance(effort_budget, int) or isinstance(effort_budget, bool) or not 1 <= effort_budget <= 200:
        raise ValueError("effort_budget is an integer in [1, 200]")
    root = str(Path(kernel_root).expanduser().resolve())
    run = run or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")
    digest = hashlib.sha256(json.dumps([root, effort_budget, run]).encode()).hexdigest()[:10]
    mission_id = f"m:first-mission-{digest}"
    canon_id = f"first-mission-{digest}"
    base = {"kernel_root": root}
    return {
        "mission_id": mission_id,
        "founder_expression": founder_expression or (
            "Understand where I am trying to go, find the highest-value unfinished work you can advance now, "
            "compare the ways to do it, produce something useful, verify it and tell me what is next."),
        "intended_effect": "one private dossier whose objective, selection, composition and next step an "
                           "independent appraisal re-derives from the sources",
        "priority": 70, "closure": {"kind": "bounded"},
        "success_checks": [{"check_id": "dossier-verified",
                            "description": "an independent re-survey and a different exact algorithm reproduce the "
                                           "dossier's objective, optimal selection and baseline",
                            "sensor": {"capability": "institution.appraise", "target": "institution:first-mission",
                                       "params": base},
                            "predicate": {"op": "equals", "field": "verdict", "value": "VERIFIED"}},
                           {"check_id": "owned-preview",
                            "description": "the Foundry's owned-page system holds an intact, receipted private page of the dossier",
                            "sensor": {"capability": "foundry.query", "target": "foundry:first-mission",
                                       "params": {"system": 31, "op": "inspect", "args": {"name": canon_id}}},
                            "predicate": {"op": "equals", "field": "result.intact", "value": True}},
                           {"check_id": "lesson-retained",
                            "description": "the dossier's exact bytes are retained in the body's content-addressed memory",
                            "sensor": {"capability": "institution.appraise", "target": "institution:first-mission",
                                       "params": {**base, "require_retained": True}},
                            "predicate": {"op": "equals", "field": "retained", "value": True}}],
        "strategies": [
            {"action_id": "survey", "capability": "institution.survey", "target": "institution:first-mission",
             "params": {**base, "effort_budget": effort_budget}, "advances": ["dossier-verified"],
             "rationale": "read GREG's own path and Foundry contract; founder-only items go to the decision queue"},
            {"action_id": "select", "capability": "cognition.dp_knapsack", "target": f"cognition:first-mission-{digest}",
             "params": {"problem_id": f"first-mission-{digest}", "operation": "knapsack_01_select"},
             "bind": [{"param": "data", "from": {"action_id": "survey", "field": "knapsack"}, "type": "object"}],
             "advances": ["dossier-verified"],
             "rationale": "exact 0/1 selection under the signed effort budget; the genome verifies itself"},
            {"action_id": "compose", "capability": "institution.compose", "target": "institution:first-mission",
             "params": dict(base),
             "bind": [{"param": "candidates", "from": {"action_id": "survey", "field": "candidates"}, "type": "array", "max_bytes": 65536}],
             "advances": ["dossier-verified"],
             "rationale": "start from existing capabilities and Foundry systems; name each CapabilityDeficit"},
            {"action_id": "dossier", "capability": "institution.dossier", "target": "deliver:first-mission",
             "params": {"canon_id": canon_id},
             "bind": [{"param": "survey", "from": {"action_id": "survey", "field": ""}, "type": "object", "max_bytes": 65536},
                      {"param": "selection", "from": {"action_id": "select", "field": "output"}, "type": "object", "max_bytes": 65536},
                      {"param": "composition", "from": {"action_id": "compose", "field": ""}, "type": "object", "max_bytes": 65536}],
             "advances": ["dossier-verified"],
             "rationale": "one private deliverable to the founder; nothing is sent, published, spent or merged"},
            {"action_id": "owned-page", "capability": "foundry.apply", "target": "foundry:first-mission",
             "params": {"system": 31, "op": "build", "args": {"reason": "Founder's First Mission dossier, private preview"}},
             "bind": [{"param": "args.canon", "from": {"action_id": "dossier", "field": "canon"}, "type": "object"}],
             "advances": ["owned-preview"],
             "rationale": "Foundry #31 renders a versioned, content-addressed private page; nothing is publicly served"},
            {"action_id": "retain", "capability": "artifact.store", "target": "artifact:first-mission",
             "params": {"namespace": "first-mission"},
             "bind": [{"param": "path", "from": {"action_id": "dossier", "field": "workspace_copy"}, "type": "string"}],
             "advances": ["lesson-retained"],
             "rationale": "keep the dossier and its lesson by digest; the next First Mission compares against it"}],
        "light_cone": {"capabilities": ["institution.survey", "institution.compose", "institution.dossier",
                                        "institution.appraise", "cognition.dp_knapsack", "foundry.apply",
                                        "foundry.query", "artifact.store"],
                       "targets": ["institution:*", "cognition:*", "deliver:*", "foundry:first-mission",
                                   "artifact:first-mission"],
                       "max_consequence_class": "internal_write", "budget_usd": 0,
                       "horizon": _horizon(horizon_days)},
    }


TEMPLATES["first-mission"] = first_mission


def compiled_question(*, problem_id: str, data: dict, geometry: dict | None = None, objective: str = "",
                      allow_construction: bool = False, horizon_days: float = 2) -> dict:
    """A problem for the Competency Compiler (Layer 5), which may need a capability GREG constructs.

    The Mind recognizes the problem's shape. When no admitted method fits but a reduction does, its
    CapabilityDeficit names that function; Capability Genesis constructs it over an engine it already
    certifies and, only if you sign ``allow_construction``, attaches it read-only inside this mission's
    light cone (the construction and its engine are named there). The Mind then answers with the
    construction's problem-level certificate. Without that signature GREG asks you to attach.
    Read-only: nobody is assigned, scheduled or paid.
    """
    from greg.genesis import CATALOG
    from greg.recombine import chain, fits

    if not isinstance(problem_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}", problem_id):
        raise ValueError("problem_id must be 1-64 letters, digits or _.:-")
    params = {"problem_id": problem_id, "compile": {"geometry": dict(geometry or {"geometry": "optimization"}),
                                                    "data": data}}
    if objective:
        params["compile"]["geometry"].setdefault("objective", objective[:300])
    target = f"cognition:{problem_id}"
    capabilities = ["cognition.solve"]
    if allow_construction:
        for reduction in fits(data):
            found = chain(reduction.function, CATALOG)
            if found:
                capabilities += [f"composed.{reduction.function}.*", f"acquired.{found[1]}.*"]
    spec = {
        "mission_id": f"m:compiled-{problem_id}"[:96],
        "founder_expression": objective or f"answer {problem_id} with the smallest competent method",
        "intended_effect": "an answer from the smallest competent method, with typed evidence GREG checks itself",
        "priority": 60, "closure": {"kind": "bounded"},
        "success_checks": [{"check_id": "answered", "description": "a competent method answered with its evidence",
                            "sensor": {"capability": "cognition.solve", "target": target, "params": params},
                            "predicate": {"op": "equals", "field": "state", "value": "ANSWERED"}}],
        "strategies": [{"action_id": "compile", "capability": "cognition.solve", "target": target, "params": params,
                        "advances": ["answered"], "rationale": "compile the problem's geometry to a competent method"}],
        "light_cone": {"capabilities": list(dict.fromkeys(capabilities)), "targets": ["cognition:*"],
                       "max_consequence_class": "read_only", "budget_usd": 0, "horizon": _horizon(horizon_days)},
    }
    if allow_construction:
        spec["auto_attach"] = {"max_consequence_class": "read_only"}
    return spec


TEMPLATES["compiled-question"] = compiled_question
TEMPLATES["organ-exchange"] = organ_exchange


def one_machine(*, problem_id: str, data: dict, sandbox_repo: str, organs: dict, seed: str,
                provider: str = "claude-code", worker_budget_usd: float = 0.05, horizon_days: float = 1,
                workspace_root: Path | None = None, founder_expression: str | None = None) -> dict:
    """One signed mission through Mind, Genesis, Organs and Hands, closed by independent appraisal.

    Composes existing capabilities only; each step hands typed outputs to the next through ``bind``:

    1. ``cognition.solve``: the Competency Compiler recognizes the problem. When no admitted method
       fits but a certified reduction does, its CapabilityDeficit names the function; Capability
       Genesis constructs it and attaches it read-only inside this cone (``auto_attach``). The answer
       carries a problem-level certificate GREG checks from the original problem.
    2. ``organ.exchange``: DALEOBANKS and WealthMachine run their own code, sign their messages and
       are verified at the kernel; a second WealthMachine process re-derives the assessment.
    3. ``worker.commission``: only after (1) and (2) are observed passing, a worker receives the
       certified answer (bound from the receipt, never relayed by hand) and records it with a test in
       a private clone of ``sandbox_repo``; GREG runs the acceptance itself with no network.
    4. ``worker.appraise`` (sensor): fresh clone, patch re-applied, scope checks, acceptance re-run.
    5. A handoff note is written only after the work is ACCEPTED.

    ``organs`` names ``daleobanks_root``, ``daleobanks_python``, ``wealthmachine_root`` and
    ``wealthmachine_python``, all inside the body's read roots. Nothing is sent, published, merged
    or paid; the worker's signed cap is the only spend bound and a local worker spends nothing.
    """
    from greg.cognition.compiler import CERTIFIED
    from greg.genesis import CATALOG
    from greg.organs import TARGET
    from greg.recombine import chain, fits

    if not isinstance(problem_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,47}", problem_id):
        raise ValueError("problem_id must be 1-48 letters, digits or _.:-")
    organ_keys = ("daleobanks_root", "daleobanks_python", "wealthmachine_root", "wealthmachine_python")
    missing = set(organ_keys) - set(organs)
    if missing:
        raise ValueError(f"organs is missing {sorted(missing)}")
    repo = str(Path(sandbox_repo).expanduser().resolve())
    order = _slug(f"record-{problem_id}", 30)
    mission_id = f"m:one-machine-{problem_id}"[:96]
    handoff = f"handoff-{order}.md"
    handoff_path = str(Path(workspace_root or ".").resolve() / mission_id.replace(":", "_") / handoff)
    compile_params = {"problem_id": problem_id, "compile": {"geometry": {"geometry": "optimization"}, "data": data}}
    capabilities = ["cognition.solve"]
    for reduction in fits(data):
        found = chain(reduction.function, CATALOG)
        if found:
            capabilities += [f"composed.{reduction.function}.*", f"acquired.{found[1]}.*"]
    objective = ("Record GREG's certified plan for problem.json in plan/plan.json (the assignment exactly as "
                 "certified) and add tests/test_plan.py that checks it against problem.json from first principles: "
                 "every assignment uses an eligible skill, no worker exceeds capacity, no order receives more than "
                 "its demand, the staffed total equals the plan's claim, and no feasible assignment staffs more "
                 "(exhaustive search; do not import GREG).")
    return {
        "mission_id": mission_id,
        "founder_expression": founder_expression or (
            "Solve this with the smallest competent method, form what is missing, consult the organs, have a "
            "worker do the real work, survive interruption, and prove it to someone who did not do it."),
        "intended_effect": "a certified answer, an organ assessment reproduced by a second process, and an "
                           "independently accepted change that records and re-checks the answer, on one trace",
        "priority": 75, "closure": {"kind": "bounded"},
        "constraints": ["nothing is sent, published, merged or paid",
                        "the worker never pushes, merges or commits; GREG commits on a greg/ branch in a private clone",
                        "organ messages are evidence about organ computation, not Kernel consequences"],
        "success_checks": [
            # The label the worker is handed ("CERTIFIED_PLAN_JSON") must be what this gate guarantees:
            # the compiler sets this confidence type only for an ANSWER that carries a problem-level
            # certificate GREG checked, never for a composition, an estimate or a model-backed trace.
            {"check_id": "answered", "description": "a constructed method answered with a problem-level certificate",
             "sensor": {"capability": "cognition.solve", "target": f"cognition:{problem_id}", "params": compile_params},
             "predicate": {"op": "equals", "field": "confidence_type", "value": CERTIFIED}},
            {"check_id": "organs-reproduced",
             "description": "both organ messages verified at the kernel and a second process reproduced the answer",
             "sensor": {"capability": "organ.status", "target": TARGET, "params": {}},
             "predicate": {"op": "equals", "field": "verdict", "value": "REPRODUCED"}},
            {"check_id": "work_accepted", "description": "independent appraisal ACCEPTED the work order",
             "sensor": {"capability": "worker.appraise", "params": {"order": order}, "target": f"work:{order}"},
             "predicate": {"op": "equals", "field": "verdict", "value": "ACCEPTED"}},
            {"check_id": "handoff_written", "description": "the review handoff exists for the founder",
             "sensor": {"capability": "fs.read", "params": {"path": handoff_path}, "target": f"fs:{handoff}"},
             "predicate": {"op": "contains", "field": "text", "value": f"greg/{order}"}}],
        "strategies": [
            {"action_id": "compile", "capability": "cognition.solve", "target": f"cognition:{problem_id}",
             "params": compile_params, "advances": ["answered"],
             "rationale": "compile the problem's geometry to a competent method; construct one if missing"},
            {"action_id": "organs", "capability": "organ.exchange", "target": TARGET,
             "params": {**{k: str(organs[k]) for k in organ_keys}, "seed": seed},
             "advances": ["organs-reproduced"],
             "rationale": "ask the organs through their own code over the signed bridge; re-derive in a second process"},
            {"action_id": "commission", "capability": "worker.commission", "target": f"work:{order}",
             "params": {"order": order, "mode": "repository", "repo": repo, "objective": objective,
                        "acceptance": {"run_changed_tests": True, "max_changed_files": 4},
                        "allowed_paths": ["plan/*", "tests/*"], "provider": provider,
                        "max_budget_usd": worker_budget_usd, "timeout_seconds": 300},
             # the exact certified answer that satisfied "answered", which may come from the re-observation
             # after Genesis attached the construction rather than from the compile action's first receipt
             "bind": [{"param": "context", "from": {"check_id": "answered", "field": "result"}, "type": "object",
                       "render": "json", "template": "CERTIFIED_PLAN_JSON:\n{value}", "max_bytes": 16384}],
             "requires": ["answered", "organs-reproduced"], "cost_usd": worker_budget_usd,
             "advances": ["work_accepted"],
             "rationale": "Hands act only on a certified answer and a reproduced organ assessment"},
            {"action_id": "handoff", "capability": "fs.write", "target": f"workspace:{handoff}",
             "params": {"relative_path": handoff,
                        "content": f"# One-machine mission ready for review: greg/{order}\n\nThe certified answer "
                                   "was recorded and re-checked by an independently ACCEPTED change; the organ "
                                   "assessment was reproduced by a second process. Promotion requires the existing "
                                   "authorized path; GREG holds no push or merge authority.\n"},
             "advances": ["handoff_written"], "requires": ["work_accepted"],
             "rationale": "continue the parent mission only on an independently accepted result"}],
        "light_cone": {"capabilities": list(dict.fromkeys(capabilities + [
                           "organ.exchange", "organ.status", "worker.commission", "worker.appraise",
                           "fs.read", "fs.write"])),
                       "targets": ["cognition:*", TARGET, f"work:{order}", f"fs:{handoff}", f"workspace:{handoff}"],
                       "max_consequence_class": "internal_write", "budget_usd": worker_budget_usd,
                       "horizon": _horizon(horizon_days)},
        "auto_attach": {"max_consequence_class": "read_only"},
    }


TEMPLATES["one-machine"] = one_machine
