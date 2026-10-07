"""P4: GREG learns which formal engine to lead with, from its own settled outcomes.

The cortex router (``cortex/routing.py``) already accepts a competence memory that may
reorder *eligible* formal engines and nothing else (``cortex.memory.CompetenceLedger``).
This module is the one projection that feeds that memory on GREG's canonical path:

    signed mission -> Gate receipt (cognition.solve or a pinned cortex organ)
      -> lead engine of the receipt's formal plan (the only engine ``route.selected`` names)
      -> outcome of that signed claim, once per claim (retries do not multiply it):
           answered and the separate-process appraisal is VERIFIED
               -> verified_success, or observed_failure if the signed check failed
               (``settlement.measured_outcomes``, unchanged)
           the lead engine returned TIMEOUT or INCONCLUSIVE under the signed budget
               -> observed_failure (the router observed it; nothing was answered)
           anything else (dependency outage, contested, unappraised) -> not settled
      -> ``CompetenceLedger.settle``: provenance ``internal_observation`` /
         ``internally_observed`` (weight 0.6), bounded, attributed, content-addressed.

Mode is a field of the founder-signed request (``routing``), never a body setting:

    static   the fixed route policy; memory is not consulted
    shadow   (default) the fixed policy executes; the receipt records the order memory
             would have chosen, so the founder can see disagreement before allowing it
    learned  memory may reorder eligible engines inside the worker

No mode can make an engine eligible, skip a gate or the verifier, raise a budget or a
consequence ceiling, or create authority. The cortex code that applies the order is
the frozen 0.2.1 router; this module adds evidence, not a second router.

Exploration is explicit: an engine that never leads never gets competence evidence. A
founder-signed mission that pins one organ (``cognition.cortex.<organ>``) is the lawful
way to gather it; GREG never spends budget on hidden counterfactual runs.
"""
from __future__ import annotations

from types import SimpleNamespace

from cortex.contracts import digest as cortex_digest
from cortex.memory import CompetenceLedger, RoutingMemoryRecord

from .contracts import CognitionError

MODES = ("static", "shadow", "learned")
DEFAULT_MODE = "shadow"
POLICY = "greg-learned-routing/0.1"
FAILING_STATES = ("TIMEOUT", "INCONCLUSIVE")
MAX_RECORDS = 20000
PROVENANCE = {"kind": "internal_observation", "validation_status": "internally_observed"}


def _formal_engines():
    from cortex.routing import FORMAL_ENGINES
    return FORMAL_ENGINES


def _cortex_receipt(receipts, receipt_hash):
    from .settlement import _valid_receipt
    from .bridge import check_receipt
    record = receipts.get(receipt_hash) if receipt_hash else None
    if record is None:
        return None, None, None
    value = record.payload.get("result", {}).get("output")
    if not _valid_receipt(value) or value.get("proof_type") != "cortex_receipt":
        return None, None, None
    try:
        artifact = check_receipt(value["proof_artifact"])
    except Exception:  # noqa: BLE001 - an invalid artifact is simply not evidence
        return None, None, None
    return record, value, artifact


def _lead(artifact):
    plan = (artifact.get("route") or {}).get("formal_plan") or {}
    order = plan.get("order") or []
    selected = (artifact.get("route") or {}).get("selected") or []
    if not order or order[0] not in _formal_engines() or order[0] not in selected:
        return None
    return order[0]


def _lead_failed(artifact, lead):
    """The lead engine's own result, as the router recorded it (final or superseded)."""
    rows = list(artifact["output"].get("per_route") or []) + list(artifact["route"].get("attempts") or [])
    return any(r.get("organ_id") == lead and r.get("state") in FAILING_STATES and r.get("answer") is None
               for r in rows)


def _claim(journal, registrations, observation, receipt):
    """The signed claim this observation belongs to, or None if it is not a signed cognition claim."""
    from .settlement import _claim_fields
    registration = registrations.get(observation.get("mission_id"))
    if not registration:
        return None
    check = next((c for c in registration.get("spec", {}).get("success_checks", [])
                  if c["check_id"] == observation.get("check_id")), None)
    if not check:
        return None
    from .contracts import digest
    if digest(check["sensor"].get("params", {})) != receipt["input_digest"]:
        return None
    capability = check["sensor"].get("capability", "")
    if capability != "cognition.solve" and not capability.startswith("cognition.cortex"):
        return None
    return digest(_claim_fields(registration, check, receipt))


def settled_claims(journal) -> list[dict]:
    """One settlement candidate per signed claim, in journal order (latest observation wins)."""
    if journal is None:
        return []
    from .settlement import measured_outcomes
    registrations = {e.payload["mission_id"]: e.payload for e in journal.replay("mission.registered")}
    verified = {o["observation_event"]: o for o in measured_outcomes(journal)}
    receipts = {r.hash: r for r in journal.ledger.by_type("receipt")}
    claims: dict[str, dict] = {}
    for position, event in enumerate(journal.replay("mission.observed")):
        data = event.payload
        record, receipt, artifact = _cortex_receipt(receipts, data.get("receipt"))
        if artifact is None:
            continue
        lead = _lead(artifact)
        identity = _claim(journal, registrations, data, receipt) if lead else None
        if identity is None:
            continue
        outcome = verified.get(event.event_id)
        if outcome is not None and artifact["output"]["per_route"] and \
                artifact["output"]["per_route"][0].get("organ_id") == lead and not _lead_failed(artifact, lead):
            status = "verified_success" if outcome["correct"] else "observed_failure"
            basis = "separate-process appraisal VERIFIED the signed check against the answered receipt"
            attribution = [{"method": lead.split("@")[0], "role": "final_answer", "uncertainty": "medium"},
                           {"method": "cortex.verifier.adversarial", "role": "flaw_detection",
                            "uncertainty": "medium"}]
            appraisal = outcome["appraisal_event"]
        elif _lead_failed(artifact, lead):
            status = "observed_failure"
            basis = "the router observed the lead engine return no decision within the signed budget"
            attribution = [{"method": lead.split("@")[0], "role": "resource_consumption", "uncertainty": "low"}]
            appraisal = None
        else:
            claims.pop(identity, None)      # a later unsettled observation supersedes an earlier one
            continue
        claims.pop(identity, None)
        claims[identity] = {"position": position, "claim": identity, "lead": lead, "status": status,
                            "receipt": artifact, "provenance": {**PROVENANCE, "basis": basis,
                                                                "observation_event": event.event_id,
                                                                "appraisal_event": appraisal,
                                                                "gate_receipt": data["receipt"]},
                            "attribution": attribution}
    return sorted(claims.values(), key=lambda c: c["position"])


def ledger(journal) -> CompetenceLedger:
    """Recompute the competence ledger from current evidence (never a stale cache)."""
    out = CompetenceLedger()
    for claim in settled_claims(journal)[-MAX_RECORDS:]:
        method, _, version = claim["lead"].partition("@")
        out.settle(receipt=claim["receipt"], method=method, method_version=version,
                   outcome_status=claim["status"], provenance=claim["provenance"],
                   attribution=claim["attribution"])
    return out


def record_from_dict(value: dict) -> RoutingMemoryRecord:
    """Rebuild a ledger record in the worker; its content address must hold."""
    if not isinstance(value, dict) or "record_id" not in value:
        raise CognitionError("routing memory record required")
    body = {k: v for k, v in value.items() if k != "record_id"}
    if cortex_digest(body) != value["record_id"]:
        raise CognitionError("routing memory record content address mismatch")
    fields = dict(value)
    fields["conditions"] = tuple(fields["conditions"])
    fields["attribution"] = tuple(fields["attribution"])
    return RoutingMemoryRecord(**fields)


def ledger_from_records(values) -> CompetenceLedger:
    return CompetenceLedger([record_from_dict(v) for v in values])


def summary(mode: str, memory: CompetenceLedger, artifact: dict | None) -> dict:
    """What the receipt states about routing: the fixed order, memory's order, the executed order."""
    base = {"mode": mode, "policy": POLICY, "ledger_head": memory.head, "settled_records": len(memory.records()),
            "authority_created": False,
            "limits": "reorders eligible formal engines only; eligibility, gates, verifier, budgets, ceilings "
                      "and authority are unchanged"}
    plan = ((artifact or {}).get("route") or {}).get("formal_plan")
    if not plan or not plan.get("order"):
        return {**base, "applies": False, "static_order": [], "memory_order": [], "executed_order": [],
                "changed_execution": False, "would_change": False, "estimates": []}
    executed = list(plan["order"])
    static = [k for k in plan["policy_order"] if k in executed] + [k for k in executed if k not in plan["policy_order"]]
    geometry = SimpleNamespace(epistemic_class=(artifact.get("geometry") or {}).get("epistemic_class"))
    memory_order = memory.reorder(list(static), geometry)
    estimates = [memory.estimate(k.split("@")[0], k.split("@")[1], geometry.epistemic_class or "unresolved")
                 for k in static]
    return {**base, "applies": True, "static_order": static, "memory_order": memory_order,
            "executed_order": executed, "changed_execution": executed != static,
            "would_change": memory_order != static, "estimates": estimates}


def check_summary(routing) -> None:
    """Receipt invariant: memory changes execution only in a signed learned mission, and only
    by permuting the engines the fixed policy already found eligible."""
    if routing is None:
        return
    if not isinstance(routing, dict) or routing.get("mode") not in MODES:
        raise CognitionError("routing mode must be static, shadow or learned")
    if routing.get("authority_created") is not False:
        raise CognitionError("routing memory cannot create authority")
    executed, static = routing.get("executed_order", []), routing.get("static_order", [])
    if sorted(executed) != sorted(static):
        raise CognitionError("routing memory changed which engines are eligible")
    if routing["mode"] != "learned" and executed != static:
        raise CognitionError("routing memory changed execution outside a signed learned mission")
