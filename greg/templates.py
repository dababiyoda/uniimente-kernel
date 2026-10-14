"""Founder-facing mission templates: goals in plain parameters, not hand-written JSON.

Each template produces a complete mission body for ``contracts/greg-mission.schema.json``
that Alfonso reviews and signs. Templates never widen authority: every one names its
light cone explicitly (capabilities, targets, ceiling, budget, horizon).
"""
from __future__ import annotations

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
                  minor_units: bool = False, horizon_days: float = 45) -> dict:
    """One customer case through the Kernel's commercial order, as a founder-signed mission (node N3).

    problem -> buyer -> offer -> payment -> delivery -> customer outcome (business/commercial_loop.py).
    GREG drafts the offer and writes the settlement record inside its workspace; every act that
    reaches a person outside the body is ``human.*`` work (one costed ask each, no contact, no
    spend). Payment counts only when ``business.reconcile`` finds exactly one posting of the signed
    amount and currency carrying the case reference in the statement Alfonso exports. Each stage
    ``requires`` the one before it, and the settlement record requires payment, delivery and the
    buyer's confirmation, so nothing is recorded as settled out of order.
    """
    amount = business_loop_amount(price)
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
        "light_cone": {"capabilities": ["fs.read", "fs.write", "business.reconcile"],
                       "targets": ["fs:*", "workspace:*", "person:*"], "max_consequence_class": "internal_write",
                       "budget_usd": 0, "horizon": _horizon(horizon_days)},
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
