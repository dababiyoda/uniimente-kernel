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
  founder_body          it ran on the body explicitly designated by a founder-signed command

The ledger can check key possession, designation, and process history. It cannot
establish the physical owner's identity or verify hardware ownership by itself.
Fixture results are structural tests, never external VEPMC evidence.
"""
from __future__ import annotations

from greg.journal import Journal

CONDITIONS = ("founder_signed", "interface_detached", "persistent_runtime", "real_capability",
              "approval_boundary", "interruption_survived", "appraised_verified", "founder_accepted", "founder_body")


def vepmc(journal: Journal) -> dict:
    ledger = journal.ledger
    seq = {r.payload.get("event_id"): r.seq for r in ledger.by_type("event")}
    registered = {e.payload["mission_id"]: seq[e.event_id] for e in journal.replay("mission.registered")}
    achieved = {e.payload["mission_id"]: (e, seq[e.event_id]) for e in journal.replay("mission.achieved")}
    appraised = {e.payload["mission_id"]: e for e in journal.replay("mission.appraised")}
    contexts = {e.payload["mission_id"]: e.payload for e in journal.replay("mission.closure_context")}
    accepted_designations = {e.payload["digest"]: seq[e.event_id] for e in journal.replay("command.accepted")
                             if e.payload.get("kind") == "BODY_DESIGNATE" and e.payload.get("signer") == "founder"}
    designations = [(e.payload, accepted_designations.get(e.payload.get("command_digest"), 1 << 60))
                    for e in journal.replay("body.designated")]
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
            "founder_body": any(d.get("body_id") == context.get("body_id")
                                and d.get("platform") == context.get("platform")
                                and d.get("purpose") == "first_founder_body"
                                and designation_seq < registered.get(mid, 0)
                                for d, designation_seq in designations),
        }
        rows.append({"mission_id": mid, "closure_event_id": event.event_id, **row,
                     "counts": all(row[c] for c in CONDITIONS),
                     "missing": [c for c in CONDITIONS if not row[c]]})
    candidates = sum(r["counts"] for r in rows)
    return {"VEPMC": candidates,  # compatibility alias; not an externally verified count
            "structural_candidate_count": candidates,
            "evidence_level": "STRUCTURAL_CANDIDATE",
            "missions": rows, "conditions": list(CONDITIONS),
            "external_confirmation_required": "ledger checks cannot prove physical ownership or personal presence"}
