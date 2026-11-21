"""Black-start read-only core: recovery stage 1 and the stage-2 integrity checks (workflows/shutdown-recovery.yaml).

Run it over a copy of a body home, on any machine that has this repository and no access to the body itself. It
writes nothing inside that home. Over a copy, it:

- **Reads the ledger and the constitution.** It verifies the hash chain read-only. The genesis record binds the
  constitution hash, so a ``config.json`` naming another constitution fails that verification. It compares the
  constitution this checkout compiles with the one the body recorded. It requires the ledger to contain the head
  the body last published in ``heartbeat.json``, as ``Body._require_published_head`` does on every start.
- **Asserts shutdown.** The body is shown down only when its last main-loop boot recorded a clean stop and the
  heartbeat says STOPPED. A boot without a stop (still running, killed, lost power) is reported as not shown down.
- **Revokes credentials, by proposal only.** It lists every device delegation and every unrevoked node enrollment
  as the founder-signed command that would end it (``greg device revoke ... --suspected-compromise``,
  ``greg node revoke``). It holds no key and signs nothing. Founder keys are listed; only the founder rotates them.
- **Notifies Alfonso, by file only.** It writes the notification it would send to ``--out``, which must be outside
  the home. ``reality_status`` says it was not sent: sending needs a channel the founder authorizes.

When the history does not verify, the stage-2 rule applies (``on_failure: remain_read_only_and_escalate``). No
credential list is derived from unverified history, and the notification says so.

It grants nothing and restores nothing. ``greg/recovery.py`` restores a body from its seed; this reads one that may
never run again.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from greg import compute
from greg.body import KERNEL_ROOT, BodyError, Layout, device_delegations, founder_keys
from greg.journal import Journal, iso

NOT_SENT = ("NOT_SENT: written to a file only; sending it to Alfonso needs a founder-authorized channel, and this "
            "core has none")
ESCALATE = "remain_read_only_and_escalate"      # workflows/shutdown-recovery.yaml stage 2, on_failure


class BlackStartError(BodyError):
    pass


def _read_json(path: Path):
    try:
        return json.loads(path.read_text()), None
    except FileNotFoundError:
        return None, "absent"
    except (OSError, ValueError) as exc:
        return None, f"unreadable: {type(exc).__name__}"


def _integrity(layout: Layout, config: dict, heartbeat: dict | None) -> tuple[dict, object]:
    """Stage-2 checks. Returns the findings and the open read-only ledger (or None when it does not verify)."""
    from compiler.ucl_compiler import compile_constitution
    from provenance.ledger import EvidenceLedger

    recorded = config.get("constitution_hash")
    compiled = compile_constitution(str(KERNEL_ROOT)).constitution_hash
    out = {"constitution_recorded": recorded, "constitution_compiled_here": compiled,
           "constitution_matches": recorded == compiled}
    if not layout.ledger.exists():
        return {**out, "chain_verified": False, "chain": "no ledger in this home"}, None
    try:
        ledger = EvidenceLedger(recorded, str(layout.ledger), read_only=True, tail="ignore")
    except (ValueError, OSError) as exc:            # the ledger verifies itself as it loads
        return {**out, "chain_verified": False, "chain": f"does not load: {exc}"[:400]}, None
    ok, why = ledger.verify_chain()
    out.update(chain_verified=ok, chain=why, ledger_head=ledger.head,
               unacknowledged_tail=bool(ledger.unacknowledged_tail))
    published = (heartbeat or {}).get("ledger_head")
    if isinstance(published, str):
        out["published_head"] = published
        out["published_head_in_ledger"] = ledger.find(published) is not None
    else:
        out["published_head"] = None
        out["published_head_in_ledger"] = None      # no published head: nothing to compare (not evidence)
    if not ok or out["published_head_in_ledger"] is False:
        ledger.close()
        return out, None
    return out, ledger


def _shutdown(journal: Journal, layout: Layout, heartbeat: dict | None) -> dict:
    boots = [e.payload for e in journal.replay("body.booted") if e.payload.get("main_loop")]
    stops = {e.payload["boot_id"]: e.payload for e in journal.replay("body.stopped")}
    last = boots[-1] if boots else None
    stop = stops.get(last["boot_id"]) if last else None
    beat = (heartbeat or {}).get("state")
    down = last is None or (stop is not None and beat in (None, "STOPPED"))
    if last is None:
        why = "the body never ran a main loop"
    elif stop is None:
        why = (f"its last boot {last['boot_id']} recorded no clean stop: it may still be running, or it was killed "
               f"or lost power. Stop it (sign BODY_STOP, or create the STOP file on its machine) before recovery")
    elif beat not in (None, "STOPPED"):
        why = f"its last boot recorded a clean stop, but heartbeat.json says {beat}"
    else:
        why = f"its last boot {last['boot_id']} stopped cleanly: {stop.get('reason')}"
    return {"shown_down": down, "why": why, "last_boot": last and last["boot_id"],
            "stop": stop and {k: stop.get(k) for k in ("reason", "at", "ledger_head", "dispatches_unfinished")
                              if k in stop},
            "heartbeat_state": beat, "stop_file_present": layout.stop_file.exists(),
            "pause_file_present": layout.pause_file.exists()}


def _credentials(journal: Journal, now: datetime) -> dict:
    devices = [{"device_key_id": kid, "label": d.get("label"), "kinds": d.get("kinds"),
                "expires_at": d.get("expires_at"),
                "command": {"kind": "DEVICE_REVOKE", "body": {"device_key_id": kid, "suspected_compromise": True}},
                "cli": f"greg device revoke {kid} --suspected-compromise --key <founder key>"}
               for kid, d in sorted(device_delegations(journal).items())]
    states = compute.node_states(journal, now=now)
    nodes = [{"node_id": n, "state": states[n]["state"], "expires_at": states[n].get("expires_at"),
              "command": {"kind": "NODE_REVOKE", "body": {"node_id": n}},
              "cli": f"greg node revoke {n} --key <founder key>"}
             for n in compute.unrevoked_nodes(journal, now=now)]
    return {"signed": False,
            "why": "this core holds no founder key; each entry is the command the founder signs to end it",
            "device_delegations": devices, "nodes": nodes,
            "founder_keys": sorted(founder_keys(journal)),
            "founder_keys_note": "not revoked here: only the founder rotates a founder key (greg founder rotate)"}


def assess(home: str | Path, *, now: datetime | None = None) -> dict:
    """The read-only report over ``home``. Opens nothing for writing."""
    from events.spine import EventSpine

    now = now or datetime.now(timezone.utc)
    layout = Layout(home)
    config, config_error = _read_json(layout.config)
    if config is None:
        raise BlackStartError(f"{layout.config} is {config_error}: this is not a body home")
    heartbeat, heartbeat_error = _read_json(layout.heartbeat)
    integrity, ledger = _integrity(layout, config, heartbeat)
    verified = ledger is not None and integrity["constitution_matches"]
    report = {"body_id": config.get("body_id"), "at": iso(now), "home": str(layout.home),
              "stage": "1_read_only_core", "writes_in_home": "none",
              "integrity": {**integrity, "heartbeat": heartbeat_error or "read"}, "verified": verified}
    if ledger is None:
        report.update(outcome=ESCALATE, shutdown=None, credentials=None,
                      unavailable=("the history does not verify: nothing is derived from it. Keep it read-only, "
                                   "keep this copy, and restore from a tested backup (greg/recovery.py)"))
        return report
    try:
        journal = Journal(EventSpine(ledger), actor="spiffe://uniimente.internal/greg/black-start")
        report["shutdown"] = _shutdown(journal, layout, heartbeat)
        report["credentials"] = _credentials(journal, now)
    finally:
        ledger.close()
    report["outcome"] = (ESCALATE if not verified
                         else "shown_down" if report["shutdown"]["shown_down"] else "not_shown_down")
    return report


def notification(report: dict) -> dict:
    """The message for Alfonso, derived only from the report."""
    creds = report.get("credentials") or {}
    lines = [f"Body {report.get('body_id')}: black-start read-only core at {report['at']}."]
    if report["outcome"] == ESCALATE:
        integrity = report["integrity"]
        failed = ("its ledger does not verify" if report.get("shutdown") is None
                  else "the constitution this checkout compiles is not the one the body recorded")
        lines.append(f"Integrity check failed: {failed} ({integrity.get('chain')}). Keep it read-only and escalate."
                     + (" Nothing was derived from the history." if report.get("shutdown") is None else ""))
    else:
        lines.append("Its ledger chain and constitution verify." +
                     (" It is shown down." if report["outcome"] == "shown_down"
                      else f" It is NOT shown down: {report['shutdown']['why']}."))
        n_dev, n_node = len(creds.get("device_delegations", [])), len(creds.get("nodes", []))
        lines.append(f"Credentials still standing: {n_dev} device delegation(s) and {n_node} node enrollment(s). "
                     "Each is listed with the command you would sign to revoke it; nothing was revoked.")
    return {"to": "Alfonso (founder)", "subject": f"GREG black start: {report['outcome']}",
            "text": " ".join(lines), "report": report, "reality_status": NOT_SENT}


def write_notification(report: dict, out: str | Path) -> Path:
    """Write the notification to ``out``, never inside the assessed home and never over an existing file."""
    out = Path(out).expanduser().resolve()
    home = Path(report["home"]).resolve()
    if out == home or home in out.parents:
        raise BlackStartError("refused: the notification goes outside the assessed home, which stays unwritten")
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(notification(report), handle, indent=1, default=str)
    return out


def exit_code(report: dict) -> int:
    """0 shown down and verified; 1 verified but not shown down; 3 history does not verify."""
    return {"shown_down": 0, "not_shown_down": 1}.get(report["outcome"], 3)
