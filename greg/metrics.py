"""VEPMC — Verified Embodied Persistent Mission Closures, computed from retained history.

The Single Bottleneck Metric is derived only from ledger facts, never from
activity counts. A closure counts when EVERY condition holds for one mission:

  founder_signed        appraiser re-verified the Ed25519 mission signature
  interface_detached    the mission arrived through the inbox (the interface process had exited)
  persistent_runtime    it closed inside a hosted body run (a recorded boot)
  real_capability       at least one receipted Gate action or observation used a real capability
  approval_boundary     it met at least one founder approval boundary and honored it
  interruption_survived a body interruption was recovered between registration and closure
  appraised_verified    the separate-process appraiser returned VERIFIED (includes exactly-once)
  founder_accepted      Alfonso signed an accepting CRITIQUE of the closure (morning tribunal)
  mac_body              it closed on macOS (the first body is the Mac)

The last two require Alfonso and his Mac. A machine cannot award them to itself.
"""
from __future__ import annotations

from greg.journal import Journal

CONDITIONS = ("founder_signed", "interface_detached", "persistent_runtime", "real_capability",
              "approval_boundary", "interruption_survived", "appraised_verified", "founder_accepted", "mac_body")


def vepmc(journal: Journal) -> dict:
    ledger = journal.ledger
    seq = {r.payload.get("event_id"): r.seq for r in ledger.by_type("event")}
    registered = {e.payload["mission_id"]: seq[e.event_id] for e in journal.replay("mission.registered")}
    achieved = {e.payload["mission_id"]: (e, seq[e.event_id]) for e in journal.replay("mission.achieved")}
    appraised = {e.payload["mission_id"]: e for e in journal.replay("mission.appraised")}
    contexts = {e.payload["mission_id"]: e.payload for e in journal.replay("mission.closure_context")}
    recoveries = [seq[e.event_id] for e in journal.replay("body.recovered")]
    accepted_targets = {e.payload["target_event_id"] for e in journal.replay("critique.recorded")
                        if e.payload["verdict"] == "accept"}
    rows = []
    for mid, (event, done_seq) in achieved.items():
        appraisal = appraised.get(mid)
        checks = appraisal.payload.get("checks", {}) if appraisal else {}
        receipts = [e for e in journal.replay("mission.observed")
                    if e.payload["mission_id"] == mid and e.payload.get("receipt")]
        context = contexts.get(mid, {})
        row = {
            "founder_signed": bool(checks.get("founder_signature_verified")),
            "interface_detached": bool(checks.get("arrived_via_inbox")),
            "persistent_runtime": bool(context.get("hosted")),
            "real_capability": bool(receipts),
            "approval_boundary": bool(checks.get("approval_boundary_encountered"))
                                 and bool(checks.get("approval_boundaries_honored")),
            "interruption_survived": any(registered.get(mid, 1 << 60) < r < done_seq for r in recoveries),
            "appraised_verified": bool(appraisal) and appraisal.payload.get("verdict") == "VERIFIED",
            "founder_accepted": bool(accepted_targets & {event.event_id, appraisal.event_id if appraisal else None}),
            "mac_body": context.get("platform") == "Darwin",
        }
        rows.append({"mission_id": mid, "closure_event_id": event.event_id, **row,
                     "counts": all(row[c] for c in CONDITIONS),
                     "missing": [c for c in CONDITIONS if not row[c]]})
    return {"VEPMC": sum(r["counts"] for r in rows), "missions": rows, "conditions": list(CONDITIONS)}
