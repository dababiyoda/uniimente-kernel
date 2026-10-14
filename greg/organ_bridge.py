"""Organ bridge exchanges as GREG journal facts, so #44 observability sees them.

DALEOBANKS and WealthMachineIntelligence talk over the signed bridge
(`adapters/bridge_transport.py`). Until now those exchanges landed nowhere GREG's
observability could correlate them. This module records each verified message
through the existing data plane (`greg.dataplane.ingest`: retained as inert,
untrusted content, never a command) and links it to a mission with a
`mission.observed` fact, so `foundry.systems.observability.correlate` returns one
trace per mission across organs.

What it deliberately does not do:
* Authentication is the transport's job: a message is recorded only after
  `verify_headers` succeeds. A verified sender is still untrusted content.
* It never emits `mission.achieved`, so it cannot move VEPMC.
* It never emits a `VERIFIED` appraisal. Reproduction by a second run is
  recorded as `REPRODUCED`, which routing treats as neutral and #44 counts as
  not verified.
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
    for event in journal.replay("mission.observed"):
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
    journal.record("mission.observed", observed,
                   key=[mission_id, "bridge", observed["content_sha256"]])
    return observed


def record_appraisal(journal: Journal, *, mission_id: str, reproduced: dict, invariants: dict,
                     appraiser: str) -> dict:
    """Record a non-producer appraisal. Never VERIFIED: agreement is not acceptance."""
    passed = all(reproduced.values()) and all(invariants.values())
    data = {"mission_id": mission_id, "verdict": APPRAISAL_VERDICT if passed else "REFUTED",
            "appraiser": appraiser, "checks": {**{f"reproduced:{k}": v for k, v in reproduced.items()},
                                               **{f"invariant:{k}": v for k, v in invariants.items()}},
            "tier": "multi-process reproduction + invariant check; not external acceptance"}
    journal.record("mission.appraised", data, key=[mission_id, "organ-bridge-appraisal", data["verdict"]])
    return data


__all__ = ["APPRAISAL_VERDICT", "MissionBindingError", "record_appraisal", "record_exchange"]
