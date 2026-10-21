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


PORTFOLIO_NAME = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,39}"
PORTFOLIO_AMOUNT = r"\$?(?P<n>\d{1,3}(?:,\d{3})+|\d+)(?P<fraction>\.\d+)?"
PORTFOLIO_VALUE = re.compile(rf"^(?P<name>{PORTFOLIO_NAME})\s+(?P<verb>earns|pays|returns|makes|brings in|is worth|"
                             rf"costs)\s+{PORTFOLIO_AMOUNT}(?:\s+[A-Za-z$€£/ ]{{1,24}})?$", re.I)
PORTFOLIO_NEEDS = re.compile(rf"^(?P<name>{PORTFOLIO_NAME})\s+(?:needs|requires|depends on)\s+(?P<rest>.+)$", re.I)
PORTFOLIO_QUESTION = re.compile(r"^(?:which|what|should|choose|pick|decide)\b", re.I)


def read_portfolio_words(text: str) -> dict:
    """The controlled portfolio language, read without a model. Unread sentences stop the plan.

    ``Offer1 earns 5.`` or ``Platform costs 6.`` (whole amounts, an optional $, thousands commas and a
    trailing unit word); ``Offer1 needs Platform and Audit.`` (also "requires", "depends on"); at most
    one question such as ``Which should I build?``. Amounts are taken in one unit you choose."""
    sentences = [s.strip() for s in re.split(r"\.(?=\s|$)|[!?;\n]+", text) if s.strip()]
    value, needs, unread, questions = {}, [], [], 0
    for sentence in sentences:
        if PORTFOLIO_QUESTION.match(sentence):
            questions += 1
        elif m := PORTFOLIO_VALUE.match(sentence):
            if m["fraction"]:
                raise ValueError(f"{sentence!r}: amounts must be whole numbers in one unit (say 1250, not 1.25k)")
            if m["name"] in value:
                raise ValueError(f"{m['name']} is given a value twice; state each item's value once")
            amount = int(m["n"].replace(",", ""))
            value[m["name"]] = -amount if m["verb"].lower() == "costs" else amount
        elif m := PORTFOLIO_NEEDS.match(sentence):
            names = [n.strip() for n in re.split(r",\s*(?:and\s+)?|\s+and\s+", m["rest"]) if n.strip()]
            bad = [n for n in names if not re.fullmatch(PORTFOLIO_NAME, n)]
            if bad or not names:
                unread.append(sentence)
                continue
            needs += [[m["name"], n] for n in names]
        else:
            unread.append(sentence)
    if unread:
        raise ValueError("GREG could not read: " + "; ".join(repr(u[:80]) for u in unread[:5])
                         + ". Write 'Offer1 earns 5.', 'Platform costs 6.' and 'Offer1 needs Platform.'")
    if questions > 1:
        raise ValueError("ask one portfolio question at a time")
    if not any(v > 0 for v in value.values()):
        raise ValueError("state at least one item that earns something ('Offer1 earns 5.')")
    unknown = sorted({n for pair in needs for n in pair if n not in value})
    if unknown:
        raise ValueError(f"{', '.join(unknown)} {'is' if len(unknown) == 1 else 'are'} needed but never given a "
                         f"value: add '{unknown[0]} costs N.' (or 'earns N.', or 'costs 0.')")
    return {"items": [{"id": n, "value": v} for n, v in value.items()], "requires": needs}


def portfolio_in_words(*, text: str, horizon_days: float = 2, auto_attach: bool = False) -> dict:
    """Which offers, projects or investments to take when some need others first, in plain controlled words.

    GREG has no portfolio engine: Genesis constructs ``selection.closure`` by Picard's reduction onto a
    maximum-flow engine it qualifies (acquiring that engine first if needed, which you attach). The
    answer names what to take, the profit, what was left out and why, and counts only on GREG's own
    funding certificate, checked against your items alone. Read-only: nothing is bought or started.
    """
    if not text.strip() or len(text) > 4000:
        raise ValueError("a portfolio question of 1-4000 characters is required")
    from greg.recombine import REDUCTIONS
    params = read_portfolio_words(text)
    REDUCTIONS["selection.closure"].normalize(params)          # refuse a malformed question before it is signed
    spec = constructed_question(function="selection.closure", params=params, horizon_days=horizon_days,
                                auto_attach=auto_attach)
    digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:10]
    return {**spec, "mission_id": f"m:portfolio-{digest}", "founder_expression": text,
            "intended_effect": "which items to take when some need others first: the most profitable set that "
                               "includes every prerequisite, with what was left out and why, proved by GREG's own "
                               "certificate"}


TEMPLATES["portfolio-in-words"] = portfolio_in_words


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
                            "predicate": {"op": "equals", "field": "verdict", "value": "VERIFIED"}}],
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
             "params": {},
             "bind": [{"param": "survey", "from": {"action_id": "survey", "field": ""}, "type": "object", "max_bytes": 65536},
                      {"param": "selection", "from": {"action_id": "select", "field": "output"}, "type": "object", "max_bytes": 65536},
                      {"param": "composition", "from": {"action_id": "compose", "field": ""}, "type": "object", "max_bytes": 65536}],
             "advances": ["dossier-verified"],
             "rationale": "one private deliverable to the founder; nothing is sent, published, spent or merged"}],
        "light_cone": {"capabilities": ["institution.survey", "institution.compose", "institution.dossier",
                                        "institution.appraise", "cognition.dp_knapsack"],
                       "targets": ["institution:*", "cognition:*", "deliver:*"],
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
