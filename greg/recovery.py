"""Restore a GREG body from its Institutional Seed (directive section 14: restoration from tested backups).

``foundry.systems.seed.restore`` rebuilds the files and re-verifies every byte. ``restore_body`` completes a GREG
restore on top of it and fails closed on authority:

- **Verification:** the restored ledger must verify and end exactly at the head the seed recorded, or the body is
  never given a witness key and cannot open.
- **A fresh witness key** is written. The original's never leaves its machine, and a witness is checked only at its
  own commit, so the history stays verifiable by its hash chain.
- **The restore is recorded** with its recovery point. Everything after that point is unknown here, so the body:
  - voids every device delegation, so a revocation the original applied after the backup cannot be lost;
  - voids every node enrollment not already revoked, for the same reason (``greg/compute.py`` void_for_restore);
  - withdraws every approval a live mission still holds, because the original may have acted on it; it is asked
    again;
  - holds itself paused until a founder-key command issued after the restore resumes it.
- **Pre-restore commands:** ``Body.apply`` refuses any command issued before the restore, because the original
  may already have applied it.

The device private key is not needed: nothing reads it at run time, and the body's identity is its ``body_id``.

Limits: a second living copy cannot be detected without an external anchor, so the founder's resume is the
declaration that the original is gone. A founder-key rotation after the recovery point is not known here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import time

from foundry.systems import cas, seed as seed_store
from greg import compute
from greg.body import Body, BodyError, Layout, _private_write
from greg.journal import iso
from greg.missions import TERMINAL

RESTORE_HOLD = "restored from a backup: held until a founder-key command issued after the restore resumes it"


class RestoreError(BodyError):
    pass


def restored(journal) -> dict | None:
    """The latest restore of this body, or None."""
    events = journal.replay("body.restored")
    return events[-1].payload if events else None


def _verified_head(layout: Layout, recorded: str | None) -> str | None:
    from provenance.ledger import EvidenceLedger
    config = json.loads(layout.config.read_text())
    try:
        ledger = EvidenceLedger(config["constitution_hash"], str(layout.ledger), read_only=True)
    except ValueError as exc:                                     # the ledger verifies itself as it loads
        raise RestoreError(f"the restored ledger does not verify: {exc}") from exc
    try:
        ok, why = ledger.verify_chain()
        head = ledger.head
    finally:
        ledger.close()
    if not ok:
        raise RestoreError(f"the restored ledger does not verify: {why}")
    if recorded is not None and head != recorded:
        raise RestoreError(f"the restored ledger ends at {head}, not at the head the seed recorded ({recorded})")
    return head


def restore_body(store, seed_address: str, home, *, clock=None) -> dict:
    """Restore ``seed_address`` from ``store`` into an empty ``home``; the body comes back held, never acting."""
    started = time.monotonic()
    store, layout = Path(store), Layout(home)
    manifest = json.loads(cas.get(store, seed_address))          # refuses a tampered manifest
    try:
        files = seed_store.restore(store, seed_address, layout.home)  # refuses a tampered object
    except (FileExistsError, ValueError) as exc:
        raise RestoreError(str(exc)) from exc    # a living body is never overwritten; a crafted seed is refused
    head = _verified_head(layout, manifest.get("ledger_head"))
    # The seed holds files only: the layout init_body creates comes back with them, or commands go unread.
    for d in (layout.inbox, layout.processed, layout.rejected, layout.outbox, layout.workspace):
        d.mkdir(parents=True, exist_ok=True)
    os.chmod(layout.home, 0o700)
    _private_write(layout.witness_key, secrets.token_bytes(32))
    with Body(layout.home, clock=clock) as body:
        now = body.clock()
        restore_id = "restore-" + secrets.token_hex(8)
        book = body.engine.book
        approvals = [rid for rid, answer in sorted(book.answers.items())
                     if answer["answer"] == "approve" and rid not in book.withdrawn
                     and (m := book.missions.get(answer["mission_id"])) is not None and m.status not in TERMINAL]
        devices = sorted(body.device_keys())
        nodes = compute.unrevoked_nodes(body.journal, now=now)
        record = {"restore_id": restore_id, "seed": seed_address, "recovery_point": manifest.get("backed_up_at"),
                  "ledger_head_at_recovery_point": head, "restored_at": iso(now), "witness_key": "fresh",
                  "voided": {"device_delegations": devices, "approvals": approvals, "node_enrollments": nodes},
                  "hold": RESTORE_HOLD,
                  "unknown_after_recovery_point": [
                      "commands, revocations, decisions and stops the original applied after the recovery point",
                      "external consequences the original caused after the recovery point",
                      "a founder-key rotation after the recovery point (rotate again if one happened)",
                      "whether the original body is still running (resuming declares that it is not)"]}
        body.journal.record("body.restored", record, key=restore_id)
        for kid in devices:
            body.journal.record("device.revoked", {"device_key_id": kid, "by": "restore", "restore_id": restore_id,
                                                   "at": iso(now)}, key=[kid, restore_id])
        compute.void_for_restore(body.journal, nodes, restore_id=restore_id, now=now)
        for rid in approvals:
            body.journal.record("decision.withdrawn", {
                "request_id": rid, "mission_id": book.answers[rid]["mission_id"], "voids_approval": True,
                "why": "restored from a backup: the original may have acted on this approval after the recovery "
                       "point; it is asked again", "restore_id": restore_id, "at": iso(now)},
                key=[rid, "withdrawn", restore_id])
        body.journal.record("body.paused", {"reason": RESTORE_HOLD, "restore_id": restore_id}, key=[restore_id, "hold"])
    return {**record, "restored_files": files["restored"], "recovery_seconds": round(time.monotonic() - started, 3),
            "needs_from_founder": [
                "a founder-key BODY_RESUME issued after the restore (declares the original gone)",
                "DEVICE_ENROLL again for each device still trusted",
                "NODE_ENROLL again for each node still trusted",
                "a fresh decision on every withdrawn approval",
                "ROTATE_FOUNDER_KEY again if the founder key was rotated after the recovery point"]}
