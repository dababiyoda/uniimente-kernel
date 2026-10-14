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
    cognition, checks = [], []
    if stated:
        ids = {"revenue": f"venture-revenue-{thread}", "causal": f"venture-causal-{thread}"}
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
        "success_checks": checks + [{"check_id": "assessed", "description": "a memo exists for the current evidence",
                                     "sensor": {"capability": "venture.status",
                                                "params": {"manifest": resolved["manifest"]},
                                                "target": "deliver:ventures"},
                                     "predicate": {"op": "equals", "field": "assessed", "value": True}}],
        "strategies": cognition + [delivery],
        "light_cone": {"capabilities": capabilities, "targets": ["deliver:*", "fs:*"] + (["cognition:*"] if cognition else []),
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


NETWORK_TREE = re.compile(r"^(?:cheapest|lowest[- ]cost|minimum|shortest)\s+(?:network|links|wiring|cabling|"
                          r"roads|pipes)\s+(?:connecting|joining|to\s+connect|that\s+connects)\s+(?:all|every|"
                          r"everything|all\s+(?:the\s+)?(?:sites|places|nodes|stops|towns|buildings))$", re.I)


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
        elif NETWORK_TREE.match(sentence):
            questions.append(("graph.spanning_tree", None, None))
        else:
            unread.append(sentence)
    if unread:
        raise ValueError("GREG could not read: " + "; ".join(repr(u[:80]) for u in unread[:5])
                         + ". Write links as 'A to B: 4.' or 'A and B: 4.'")
    if len(questions) != 1 or not edges:
        raise ValueError("state at least one link and exactly one question ('Shortest route from A to C.', "
                         "'Maximum flow from A to C.' or 'Cheapest network connecting all sites.')")
    function, source, target = questions[0]
    if function == "graph.spanning_tree":                 # links have no direction in a network to build
        return function, {"edges": [e for i, e in enumerate(edges)
                                    if not (i and edges[i - 1] == [e[1], e[0], e[2]])]}
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
    what = {"graph.shortest_path": "shortest route", "graph.max_flow": "maximum flow",
            "graph.spanning_tree": "cheapest connecting network"}[function]
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


ASSIGN_NAME = r"[A-Za-z][A-Za-z0-9_-]{0,31}"
ASSIGN_PAIR = re.compile(rf"^(?P<row>{ASSIGN_NAME})\s+(?:on|for|to)\s+(?P<col>{ASSIGN_NAME})\s*[:,]\s*"
                         rf"(?P<n>-?\d+(?:\.\d+)?)(?:\s+[A-Za-z$€£%]+)?$", re.I)
ASSIGN_CANNOT = re.compile(rf"^(?P<row>{ASSIGN_NAME})\s+cannot\s+(?:do\s+|take\s+)?(?P<col>{ASSIGN_NAME})$", re.I)
ASSIGN_MIN = re.compile(r"^(?:(?:cheapest|lowest[- ]cost|least[- ]cost|minimum[- ]cost|fastest|quickest)\s+"
                        r"assignment|minimi[sz]e\s+(?:the\s+)?total(?:\s+\w+)?)$", re.I)
ASSIGN_MAX = re.compile(r"^(?:(?:most\s+valuable|highest[- ]value|maximum[- ]value|best[- ]scoring)\s+assignment|"
                        r"maximi[sz]e\s+(?:the\s+)?total(?:\s+\w+)?)$", re.I)


def read_assignment_words(text: str) -> dict:
    """The controlled assignment language, read without a model. Unread sentences stop the plan.

    ``Ana on Painting: 4.`` is the cost (or value) of that pair; a pair never stated is not allowed,
    and ``Ana cannot do Wiring.`` says so explicitly. One goal: ``Cheapest assignment.`` (also
    ``Minimize total cost.``) or ``Most valuable assignment.`` (also ``Maximize total value.``)."""
    sentences = [s.strip() for s in re.split(r"\.(?=\s|$)|[!?;\n]+", text) if s.strip()]
    rows, cols, cost, forbidden, goals, unread = [], [], {}, set(), [], []
    for sentence in sentences:
        if pair := ASSIGN_PAIR.match(sentence):
            r, c = pair["row"], pair["col"]
            if (r, c) in cost:
                raise ValueError(f"{r} on {c} is stated twice")
            cost[r, c] = float(pair["n"]) if "." in pair["n"] else int(pair["n"])
        elif no := ASSIGN_CANNOT.match(sentence):
            r, c = no["row"], no["col"]
            forbidden.add((r, c))
        elif ASSIGN_MIN.match(sentence):
            goals.append(False)
            continue
        elif ASSIGN_MAX.match(sentence):
            goals.append(True)
            continue
        else:
            unread.append(sentence)
            continue
        rows += [r] if r not in rows else []
        cols += [c] if c not in cols else []
    if unread:
        raise ValueError("GREG could not read: " + "; ".join(repr(u[:80]) for u in unread[:5])
                         + ". Write pairs as 'Ana on Painting: 4.'")
    if len(goals) != 1 or not cost:
        raise ValueError("state at least one pair and exactly one goal ('Cheapest assignment.' or "
                         "'Most valuable assignment.')")
    if clash := sorted(forbidden & set(cost)):
        raise ValueError(f"{clash[0][0]} on {clash[0][1]} has a cost and is also said to be impossible")
    if len(rows) > len(cols):
        raise ValueError(f"{len(rows)} people (or machines) but only {len(cols)} jobs: everyone needs their own job")
    return {"rows": rows, "columns": cols, "maximize": goals[0],
            "costs": [[cost.get((r, c)) for c in cols] for r in rows]}


def assignment_in_words(*, text: str, horizon_days: float = 2, auto_attach: bool = False) -> dict:
    """Who should do which job, in plain controlled words, solved by an open-source engine.

    The first such mission opens a CapabilityDeficit: genesis looks for an installed open-source
    assignment engine (SciPy, OR-Tools), pins it on a Mechanism Card, qualifies it against GREG's
    brute-force oracle and asks you to attach it. An answer counts only if GREG's own certificate
    holds: no exchange of jobs lowers (or raises) the total. If no full assignment exists, GREG
    proves it and names the people whose allowed jobs are too few. Read-only: nobody is assigned.
    """
    if not text.strip() or len(text) > 8000:
        raise ValueError("an assignment of 1-8000 characters is required")
    params = read_assignment_words(text)
    digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:10]
    step = {"function": "assignment.optimize", "params": params, "target": f"cognition:assign-{digest}"}
    spec = {
        "mission_id": f"m:assign-{digest}",
        "founder_expression": text,
        "intended_effect": "the best assignment of the stated people or machines to jobs, with a certificate that no "
                           "exchange does better, or a proof that no full assignment exists",
        "priority": 60, "closure": {"kind": "bounded"},
        "success_checks": [{"check_id": "certified-assignment", "description": "an optimal assignment, or the "
                            "impossibility of any, proved by GREG's own certificate, independent of the engine",
                            "sensor": step, "predicate": {"op": "equals", "field": "certified", "value": True}}],
        "strategies": [{"action_id": "solve", **step, "advances": ["certified-assignment"],
                        "rationale": "compute with a qualified open-source engine (read-only)"}],
        "light_cone": {"capabilities": ["acquired.assignment.optimize.*"], "targets": ["cognition:*"],
                       "max_consequence_class": "read_only", "budget_usd": 0, "horizon": _horizon(horizon_days)},
    }
    if auto_attach:
        spec["auto_attach"] = {"max_consequence_class": "read_only"}
    return spec


TEMPLATES["assignment-in-words"] = assignment_in_words


DELIVER_NAME = r"[A-Za-z][A-Za-z0-9_-]{0,31}"
DELIVER_SUPPLY = re.compile(rf"^(?P<n>{DELIVER_NAME})\s+(?:sends|supplies|has|ships|makes)\s+(?P<q>\d+)(?:\s+[A-Za-z]+)?$",
                            re.I)
DELIVER_DEMAND = re.compile(rf"^(?P<n>{DELIVER_NAME})\s+(?:needs|wants|requires|takes)\s+(?P<q>\d+)(?:\s+[A-Za-z]+)?$",
                            re.I)
DELIVER_ARC = re.compile(rf"^(?P<a>{DELIVER_NAME})\s+to\s+(?P<b>{DELIVER_NAME})\s*[:,]?\s*(?:(?P<cap>\d+)"
                         rf"(?:\s+[A-Za-z]+)?\s+)?at\s+\$?(?P<cost>-?\d+(?:\.\d+)?)(?:\s+(?:each|per\s+\w+))?$", re.I)
DELIVER_GOAL = re.compile(r"^(?:(?:cheapest|lowest[- ]cost|least[- ]cost)\s+(?:delivery|shipping|plan|way\s+to\s+"
                          r"(?:deliver|ship))|minimi[sz]e\s+(?:the\s+)?(?:shipping|delivery|transport)\s+cost)$", re.I)


def read_delivery_words(text: str) -> dict:
    """The controlled delivery language, read without a model. Unread sentences stop the plan.

    ``Plant sends 30.`` and ``Store needs 20.`` state supplies and demands (they must balance);
    ``Plant to Store: 40 at 4.`` is a route carrying at most 40 at 4 per unit (``Plant to Store at 4.``
    has no limit); one goal: ``Cheapest delivery.``"""
    sentences = [s.strip() for s in re.split(r"\.(?=\s|$)|[!?;\n]+", text) if s.strip()]
    supplies, arcs, goals, unread, unlimited = {}, [], 0, [], []
    for sentence in sentences:
        if m := DELIVER_SUPPLY.match(sentence):
            supplies[m["n"]] = supplies.get(m["n"], 0) + int(m["q"])
        elif m := DELIVER_DEMAND.match(sentence):
            supplies[m["n"]] = supplies.get(m["n"], 0) - int(m["q"])
        elif m := DELIVER_ARC.match(sentence):
            cost = float(m["cost"]) if "." in m["cost"] else int(m["cost"])
            arcs.append([m["a"], m["b"], int(m["cap"]) if m["cap"] else None, cost])
        elif DELIVER_GOAL.match(sentence):
            goals += 1
        else:
            unread.append(sentence)
    if unread:
        raise ValueError("GREG could not read: " + "; ".join(repr(u[:80]) for u in unread[:5])
                         + ". Write 'Plant sends 30.', 'Store needs 20.', 'Plant to Store: 40 at 4.'")
    if goals != 1 or not arcs or not supplies:
        raise ValueError("state supplies, demands, at least one route and exactly one goal ('Cheapest delivery.')")
    enough = sum(q for q in supplies.values() if q > 0)
    return {"arcs": [[a, b, enough if cap is None else cap, cost] for a, b, cap, cost in arcs], "supplies": supplies}


def delivery_in_words(*, text: str, horizon_days: float = 2, auto_attach: bool = False) -> dict:
    """Least-cost delivery from supplies to demands, in plain controlled words, from an open-source engine.

    The first such mission opens a CapabilityDeficit: genesis looks for an installed open-source
    min-cost-flow engine (NetworkX, OR-Tools), pins it on a Mechanism Card, qualifies it against GREG's
    brute-force oracle and asks you to attach it. A plan counts only if GREG's own certificate holds: no
    rerouting is cheaper. If no plan can meet every demand, GREG proves it and names the sites whose
    supply the routes cannot carry out. Read-only: nothing is shipped.
    """
    if not text.strip() or len(text) > 8000:
        raise ValueError("a delivery plan of 1-8000 characters is required")
    params = read_delivery_words(text)
    digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:10]
    step = {"function": "flow.min_cost", "params": params, "target": f"cognition:deliver-{digest}"}
    spec = {
        "mission_id": f"m:deliver-{digest}",
        "founder_expression": text,
        "intended_effect": "the least-cost way to meet every stated demand from the stated supplies, with a "
                           "certificate that no rerouting is cheaper, or a proof that no plan meets them",
        "priority": 60, "closure": {"kind": "bounded"},
        "success_checks": [{"check_id": "certified-delivery", "description": "a least-cost delivery plan, or the "
                            "impossibility of any, proved by GREG's own certificate, independent of the engine",
                            "sensor": step, "predicate": {"op": "equals", "field": "certified", "value": True}}],
        "strategies": [{"action_id": "solve", **step, "advances": ["certified-delivery"],
                        "rationale": "compute with a qualified open-source engine (read-only)"}],
        "light_cone": {"capabilities": ["acquired.flow.min_cost.*"], "targets": ["cognition:*"],
                       "max_consequence_class": "read_only", "budget_usd": 0, "horizon": _horizon(horizon_days)},
    }
    if auto_attach:
        spec["auto_attach"] = {"max_consequence_class": "read_only"}
    return spec


TEMPLATES["delivery-in-words"] = delivery_in_words
