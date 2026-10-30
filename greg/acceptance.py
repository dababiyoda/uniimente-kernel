"""Founder-device acceptance: what actually happened on THIS body, read from its own ledger.

    greg acceptance            print the report and keep a copy in <deliver_root>/acceptance/

Read-only (the observer never takes the writer lock), so it is safe while the body runs. Each property is PASS
only when the body's own retained history shows it; otherwise NOT_YET with the step of the runbook that would
produce it. Nothing here signs, attaches, starts or stops anything.

Reality labels: the report says FOUNDER-DEVICE only when a founder-signed first-body designation exists on this
ledger, the First Mission ran after it, and that mission's signature is at the founder tier (greg/metrics.py
founder_tier: the key attested passphrase custody before the mission was registered, the rule that gates N1). A
designated body whose mission a test key or a ``--no-passphrase`` key signed reads LOCAL-DESIGNATED with the reason.
Ledger evidence cannot prove who held the keyboard or that the machine is Alfonso's; the report says so. A rehearsal
body (``greg rehearse``) is never founder-device evidence.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

RUNBOOK = "greg/CHROMEBOOK_FIRST_MISSION.md"
STALE_HEARTBEAT_SECONDS = 180           # the console's and Mission Control's rule: older is not a running body


def _runtime(heartbeat: dict) -> dict:
    """Whether a body process is running now: a RUNNING or PAUSED heartbeat under three minutes old, written by a
    process that still exists. The heartbeat file outlives its process, so its state alone proves nothing."""
    try:
        at = datetime.fromisoformat(str(heartbeat["at"]).replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - at).total_seconds()
    except (KeyError, TypeError, ValueError):
        age = None
    pid = heartbeat.get("pid")
    alive = None
    if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0:
        try:
            os.kill(pid, 0)
            alive = True
        except ProcessLookupError:
            alive = False
        except PermissionError:            # it exists, under another user
            alive = True
    running = (heartbeat.get("state") in ("RUNNING", "PAUSED") and age is not None
               and 0 <= age < STALE_HEARTBEAT_SECONDS and alive is True)
    return {"running": running, "state": heartbeat.get("state"), "pid": pid, "process_alive": alive,
            "age_seconds": None if age is None else round(age, 1)}


def _passed(journal, mission_id: str, check_id: str) -> bool:
    obs = [e.payload for e in journal.replay("mission.observed")
           if e.payload["mission_id"] == mission_id and e.payload["check_id"] == check_id]
    return bool(obs) and bool(obs[-1]["passed"])


def _code(home: Path) -> dict:
    """The exact code this body runs: the kernel checkout's commit and whether a tracked file differs from it, read
    with the hardened read-only git (nothing the checkout's own config names runs). An acceptance then names the
    tree it accepted, so a reviewer can compare it with the candidate under review."""
    from greg.capabilities import KERNEL_ROOT, read_only_git
    root = Path(KERNEL_ROOT)
    try:
        head = read_only_git(root, "rev-parse", "HEAD", home=home)
        changes = read_only_git(root, "status", "--porcelain", "--untracked-files=no", home=home)
    except (OSError, subprocess.TimeoutExpired):
        return {"root": str(root), "commit": None, "dirty": None}
    return {"root": str(root), "commit": (head.stdout.strip() or None) if head.returncode == 0 else None,
            "dirty": bool(changes.stdout.strip()) if changes.returncode == 0 else None}


def _egress(home: Path, config: dict) -> dict:
    """#26 on this body, from its own relay journal: confined or not, and what the relay allowed and refused.

    Only a refusal of a destination counts as one: the relay also refuses a request over its limit, oversized or
    malformed without consulting any allowlist. Rows from any identity count as GREG's connections (the console's
    model drafting and anchoring share this journal), so the report names the identities rather than claiming a
    mission made them."""
    if not config.get("confined_egress"):
        return {"confined": False, "chain_intact": False, "allowed": 0, "denied": 0, "denied_other": 0,
                "identities": [], "allowed_identities": [], "torn_tail": False, "quarantined_tails": 0}
    from foundry.systems.segmentation import DESTINATION_REFUSALS, Journal as EgressJournal
    journal = EgressJournal(Path(home) / "egress-journal.jsonl")
    check = journal.verify()                     # damage is a result: a row that does not parse fails the chain
    rows = [] if check.get("malformed") else journal.read()
    refused = [r for r in rows if r.get("verdict") == "DENIED"]
    destination = [r for r in refused if r.get("host") and r.get("why") in DESTINATION_REFUSALS]
    allowed = [r for r in rows if r.get("verdict") == "ALLOWED"]
    return {"confined": True, "chain_intact": bool(check["intact"]), "allowed": len(allowed),
            "denied": len(destination), "denied_other": len(refused) - len(destination),
            "identities": sorted({str(r.get("identity")) for r in rows}),
            "allowed_identities": sorted({str(r.get("identity")) for r in allowed}),
            "torn_tail": bool(check.get("torn_tail_bytes")), "quarantined_tails": check.get("quarantined_tails", 0),
            **({"broken_at": check["broken_at"]} if "broken_at" in check else {})}


def report(home: str | Path) -> dict:
    from greg import metrics
    from greg.body import Layout, observe, status
    layout = Layout(home)
    st = status(home)
    config = json.loads(layout.config.read_text())
    with observe(home, actor="spiffe://uniimente.internal/greg/acceptance-reader") as journal:
        ok, chain = journal.ledger.verify_chain()
        achieved = {e.payload["mission_id"] for e in journal.replay("mission.achieved")}
        appraised = {e.payload["mission_id"]: e.payload["verdict"] for e in journal.replay("mission.appraised")}
        first = sorted(m for m in achieved if m.startswith("m:first-mission-"))
        verified_first = [m for m in first if appraised.get(m) == "VERIFIED"]
        ventures = sorted(m for m in achieved if m.startswith("m:venture-rehearsal-") and appraised.get(m) == "VERIFIED")
        states = [e.payload for e in journal.replay("capability.state")]
        attach = [s for s in states if s["capability_id"] == "cognition.dp_knapsack" and s["state"] == "ATTACHED"
                  and s.get("by") == "founder command"]
        toggles = [e.type for e in journal.replay("body.") if e.type in ("greg.body.paused", "greg.body.resumed")]
        recovered = len(journal.replay("body.recovered"))
        accepted = len([e for e in journal.replay("critique.recorded") if e.payload["verdict"] == "accept"])
        vepmc = metrics.vepmc(journal)
        tiers = metrics.founder_tier(journal)
        designated = bool(journal.replay("body.designated"))
        lifecycle = [e.payload for e in journal.replay("mission.lifecycle")]
        memory = None
        for m in verified_first:
            stem = m.replace(":", "_")
            doc = Path(config.get("deliver_root") or layout.home / "deliveries") / "first-mission" / f"{stem}.json"
            if doc.is_file() and json.loads(doc.read_text()).get("since_last"):
                memory = m
        owned = [m for m in verified_first if _passed(journal, m, "owned-preview")]
        retained = [m for m in verified_first if _passed(journal, m, "lesson-retained")]
    egress = _egress(layout.home, config)
    code = _code(layout.home)
    rows = {r["mission_id"]: r for r in vepmc["missions"]}
    first_row = next((rows[m] for m in verified_first if m in rows), None)
    runtime = _runtime(st.get("background") or {})
    props = [
        ("ledger_chain_verified", ok, "the hash chain of every retained record verifies", "—"),
        ("code_identified", bool(code["commit"]) and code["dirty"] is False,
         "the body runs a clean checkout of one named commit (code.commit), so this report binds to that tree",
         "1. Install (clone the review branch; do not edit tracked files)"),
        ("founder_key_enrolled", bool(st["security"]["founder_keys_enrolled"]), "a founder key is enrolled", "1. Install"),
        ("first_body_designated", designated, "a founder-signed first-body designation is on this ledger", "1. Install (step 8/8)"),
        ("supervised_runtime", runtime["running"],
         "a body process is running now: its heartbeat is RUNNING or PAUSED, under three minutes old, and the "
         "process that wrote it exists (runtime names what was read)", "1. Install (service)"),
        ("engine_attached_by_founder", bool(attach), "you attached the exact selection engine with your key",
         "4. First Mission: Attach in Mission Control"),
        ("first_mission_verified", bool(verified_first), "a First Mission closed and its appraisal re-derived it",
         "4. First Mission"),
        ("foundry_private_page", bool(owned), "Foundry #31 holds the dossier's intact private page", "4. First Mission"),
        ("lesson_retained", bool(retained), "the dossier's bytes are retained by digest", "4. First Mission"),
        ("interruption_survived", bool(first_row and first_row["interruption_survived"]),
         "the First Mission crossed a body recovery (kill -9) before closing", "4. First Mission: kill -9"),
        ("founder_accepted", bool(first_row and first_row["founder_accepted"]), "you accepted the result", "4. Accept"),
        ("memory_across_missions", memory is not None, "a later First Mission compared itself with an earlier one",
         "5. Run it again (memory)"),
        ("commerce_rehearsal_verified", bool(ventures), "the FIXTURE commerce loop closed and re-verified", "6. Ventures"),
        ("pause_and_resume_exercised", "greg.body.paused" in toggles and "greg.body.resumed" in toggles,
         "you paused and resumed the body with your key", "7. Founder control"),
        ("revoke_exercised", any(l.get("state") == "ABANDONED" for l in lifecycle),
         "you revoked a mission with your key", "7. Founder control"),
        ("network_confined", egress["confined"] and egress["chain_intact"] and egress["allowed"] > 0,
         "the body was created confined, its relay journal chain verifies, and at least one connection GREG made "
         "crossed the relay (egress.allowed_identities names which parts of GREG made them)",
         "1. Install (the installer confines when the doctor finds the kernel filter and namespaces), then "
         "2. Run and judge one bounded mission (its public GitHub reads cross the relay)"),
        ("undeclared_destination_denied", egress["confined"] and egress["chain_intact"] and egress["denied"] > 0,
         "the relay refused and journaled a connection to a destination no capability declared for the part of GREG "
         "asking (a request limit or a malformed request is not counted)",
         "6a. A hosted MCP server: GREG renders the page you name, and Chromium's own background connections are "
         "refused at the relay"),
    ]
    on_body = bool(designated and first_row and first_row.get("founder_body"))
    signature = tiers.get(first_row["mission_id"], {}) if first_row else {}
    if on_body and signature.get("tier") == metrics.FOUNDER_TIER:
        tier = "FOUNDER-DEVICE (ledger evidence; physical ownership and presence are not provable from a ledger)"
    elif on_body:
        tier = ("LOCAL-DESIGNATED (the First Mission ran on the designated body, but its signature is not at the "
                f"founder tier: {signature.get('why_not', 'no founder-tier record')}; not founder-device evidence)")
    else:
        tier = "LOCAL (not a founder-designated body run; not founder-device evidence)"
    out = {"kind": "greg-founder-device-acceptance/1", "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "body_id": st["body_id"], "home": str(layout.home), "reality": tier, "chain": chain if not ok else "verified",
           "code": code,
           "properties": [{"property": p, "status": "PASS" if v else "NOT_YET", "means": means, "runbook": step}
                          for p, v, means, step in props],
           "passed": sum(1 for _, v, _, _ in props if v), "total": len(props),
           "first_mission": first_row, "signature_tier": signature, "runtime": runtime, "egress": egress, "vepmc": vepmc["VEPMC"], "recoveries": recovered,
           "acceptances": accepted,
           "runbook": RUNBOOK, "authority_created": False}
    return out


def main(home: str | Path) -> int:
    from greg.body import Layout
    result = report(home)
    config = json.loads(Layout(home).config.read_text())
    folder = Path(config.get("deliver_root") or Path(home) / "deliveries") / "acceptance"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (result["at"].replace(":", "") + ".json")
    path.write_text(json.dumps(result, indent=1, default=str))
    print(json.dumps({**result, "kept_at": str(path)}, indent=1, default=str))
    return 0
