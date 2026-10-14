"""Organ bridge exchanges as GREG journal facts, so #44 observability sees them.

DALEOBANKS and WealthMachineIntelligence talk over the signed bridge
(`adapters/bridge_transport.py`). Until now those exchanges landed nowhere GREG's
observability could correlate them. This module records each verified message
through the existing data plane (`greg.dataplane.ingest`: retained as inert,
untrusted content, never a command) and links it to a mission with a
`organ.observed` fact, so `foundry.systems.observability.correlate` returns one
trace per mission across organs.

What it deliberately does not do:
* Authentication is the transport's job: a message is recorded only after
  `verify_headers` succeeds. A verified sender is still untrusted content.
* It never emits `mission.achieved`, so it cannot move VEPMC, and it never
  writes `mission.observed`: that type is a success-check observation the
  mission engine rebuilds state from (an organ message carries no check id).
* It never emits a `VERIFIED` appraisal. Reproduction by a second run is
  recorded as `REPRODUCED` under its own event type, `organ.appraised`. It is
  never a `mission.appraised` fact: that type is the body's independent closure
  appraisal, and an organ-level fact under it would make the body skip the
  closure appraisal and shadow the mission's verdict in VEPMC and routing.
* It emits no `mission.action`: an organ message is an observation, not an
  action GREG executed, so it cannot inflate any capability's track record.
"""
from __future__ import annotations

import hashlib

from adapters import bridge_transport as bt
from greg import dataplane
from greg.journal import Journal

APPRAISAL_VERDICT = "REPRODUCED"


class MissionBindingError(ValueError):
    """A bridge message's trace does not belong to the mission it is filed under."""


def _check_binding(journal: Journal, mission_id: str, trace_id: str) -> None:
    """One mission, one trace. The first observed message binds them; later
    messages must agree in both directions, so a caller cannot file another
    mission's exchange under this mission or split one exchange across two."""
    if not trace_id:
        raise MissionBindingError("bridge message carries no trace id; cannot bind it to a mission")
    for event in journal.replay("organ.observed"):
        p = event.payload
        if p.get("operation") is None or "trace_id" not in p:
            continue
        if p["trace_id"] == trace_id and p["mission_id"] != mission_id:
            raise MissionBindingError(f"trace {trace_id} is bound to mission {p['mission_id']}")
        if p["mission_id"] == mission_id and p["trace_id"] != trace_id:
            raise MissionBindingError(f"mission {mission_id} is bound to trace {p['trace_id']}")


def record_exchange(journal: Journal, *, mission_id: str, headers: dict, body: bytes,
                    nonce_cache, expected_sender: str, expected_operation: str,
                    expected_recipient: str | None = None, request_digest: str | None = None) -> dict:
    """Verify one bridge message, retain it as evidence, link it to a mission.

    Raises `bt.BridgeSecurityError` (and records nothing) when verification fails,
    and `MissionBindingError` when the signed trace id belongs to another mission.
    """
    meta = bt.verify_headers(headers, body, nonce_cache=nonce_cache, expected_sender=expected_sender,
                             expected_recipient=expected_recipient, expected_operation=expected_operation,
                             request_digest=request_digest)
    trace_id = meta.get("trace_id") or ""
    _check_binding(journal, mission_id, trace_id)
    retained = dataplane.ingest(journal, source=f"organ:{meta['identity']}",
                                content=body.decode("utf-8"), channel=f"bridge:{expected_operation}")
    observed = {"mission_id": mission_id, "organ": meta["identity"], "operation": expected_operation,
                "content_sha256": hashlib.sha256(body).hexdigest(), "transport_verified": True,
                # The bridge uses one shared key: it authenticates a key holder,
                # not a specific organ. Carried so no trace overstates it.
                "sender_identity_isolated": meta.get("identity_isolated") == "true",
                "content_trust": "untrusted", "quarantined": retained.get("quarantined", False),
                "trace_id": trace_id, "receipt": None}
    # No timestamp in the payload: the event envelope carries occurrence time,
    # and a volatile field would make a redelivered message collide with its
    # own retained fact.
    journal.record("organ.observed", observed,
                   key=[mission_id, "bridge", observed["content_sha256"]])
    return observed


def record_appraisal(journal: Journal, *, mission_id: str, reproduced: dict, invariants: dict,
                     appraiser: str, exchange: dict | None = None) -> dict:
    """Record a non-producer appraisal. Never VERIFIED: agreement is not acceptance.

    ``exchange`` names what was judged (trace id and the request, answer and re-derivation
    digests). It is part of the fact's identity, so two exchanges never collapse into one
    appraisal and a reader can tie the verdict to the exchange a receipt stands behind."""
    passed = all(reproduced.values()) and all(invariants.values())
    data = {"mission_id": mission_id, "verdict": APPRAISAL_VERDICT if passed else "REFUTED",
            "appraiser": appraiser, "checks": {**{f"reproduced:{k}": v for k, v in reproduced.items()},
                                               **{f"invariant:{k}": v for k, v in invariants.items()}},
            "tier": "multi-process reproduction + invariant check; not external acceptance"}
    key = [mission_id, "organ-bridge-appraisal", data["verdict"]]
    if exchange is not None:
        data["exchange"] = {k: exchange[k] for k in ("trace_id", "packet_sha256", "assessment_sha256", "redo_sha256")}
        key = [mission_id, "organ-bridge-appraisal", *(data["exchange"][k] for k in
                                                       ("packet_sha256", "assessment_sha256", "redo_sha256"))]
    journal.record("organ.appraised", data, key=key)
    return data


def bound_facts(journal: Journal, mission_id: str, *, capability: str = "organ.exchange") -> dict:
    """This mission's organ facts that a completed exchange stands behind.

    The adapter records its facts before the Gate writes the receipt. A crash between the two
    leaves facts that no receipt vouches for; if the founder then reconciles that dispatch as not
    executed, those facts must not satisfy the mission. A fact counts only when its digest appears
    in the output of a DONE receipt of one of this mission's ``capability`` strategies, or when it
    was recorded before a founder reconciliation that declared such a dispatch executed."""
    ledger = journal.ledger
    seq = {r.payload.get("event_id"): r.seq for r in ledger.by_type("event")}
    action_ids = {s["action_id"] for e in journal.replay("mission.registered") if e.payload.get("mission_id") == mission_id
                  for s in e.payload.get("spec", {}).get("strategies", []) if s.get("capability") == capability}
    digests, receipts, founder_cut = set(), [], None
    for event in journal.replay("mission.action"):
        p = event.payload
        if p.get("mission_id") != mission_id or p.get("action_id") not in action_ids or p.get("status") != "DONE":
            continue
        if p.get("receipt"):
            record = ledger.find(p["receipt"])
            output = record.payload["result"].get("output") if record is not None and \
                record.record_type == "receipt" else None
            if isinstance(output, dict) and output.get("packet_sha256") and output.get("assessment_sha256"):
                digests |= {output["packet_sha256"], output["assessment_sha256"]}
                receipts.append(p["receipt"])
        elif p.get("route") == "founder_reconciliation":
            founder_cut = max(founder_cut or 0, seq.get(event.event_id, 0))

    def before_cut(event) -> bool:
        return founder_cut is not None and seq.get(event.event_id, founder_cut) < founder_cut

    observed, appraisals, unbound = [], [], 0
    for event in journal.replay("organ.observed"):
        p = event.payload
        if p.get("mission_id") != mission_id or not p.get("operation"):
            continue
        if p.get("content_sha256") in digests or before_cut(event):
            observed.append(p)
        else:
            unbound += 1
    for event in journal.replay("organ.appraised"):
        p = event.payload
        if p.get("mission_id") != mission_id:
            continue
        judged = p.get("exchange") or {}
        if {judged.get("packet_sha256"), judged.get("assessment_sha256")} <= digests or before_cut(event):
            appraisals.append(p)
        else:
            unbound += 1
    return {"observed": observed, "appraisals": appraisals, "receipts": receipts,
            "founder_reconciled": founder_cut is not None, "unbound": unbound}


__all__ = ["APPRAISAL_VERDICT", "MissionBindingError", "bound_facts", "record_appraisal", "record_exchange"]
