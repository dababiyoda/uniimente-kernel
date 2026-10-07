"""Outcome competence is a replayed projection of canonical receipts and appraisals."""
from __future__ import annotations

from collections import defaultdict

from .contracts import CognitiveReceipt, ProblemGeometry, digest


def _valid_receipt(value):
    if not isinstance(value, dict) or value.get("authority_created") is not False:
        return False
    copy = dict(value)
    identity = copy.pop("receipt_id", None)
    try:
        fields = set(CognitiveReceipt.__dataclass_fields__)
        # Optional additive fields may be absent in retained historical receipts.
        optional = {"outcome", "authority_refs", "reason_code", "stopping_reason"}
        if identity != digest(copy) or not fields - optional <= set(copy) <= fields:
            return False
        CognitiveReceipt(**copy)
    except (TypeError, ValueError, KeyError):
        return False
    return True


def measured_outcomes(journal):
    if journal is None:
        return []
    from greg.sop import REQUIRED_CHECKS
    from .cortex import geometry_key
    from greg.capabilities import BUILTINS
    specs = {e.payload["mission_id"]: e.payload["spec"] for e in journal.replay("mission.registered")}
    witnesses = {r.payload["witness_id"]: r.payload for r in journal.ledger.by_type("witness")}
    latest_appraisal, observations = {}, {}
    for event in journal.replay("mission.appraised"):
        data = event.payload
        if (data.get("verdict") == "VERIFIED" and all(data.get("checks", {}).get(k) is True for k in REQUIRED_CHECKS)):
            latest_appraisal[data["mission_id"]] = event
        else:
            latest_appraisal.pop(data["mission_id"], None)
    for event in journal.replay("mission.observed"):
        data = event.payload
        if data.get("mission_id") not in latest_appraisal or not data.get("receipt"):
            continue
        record = journal.ledger.find(data["receipt"])
        if record is None or record.record_type != "receipt":
            continue
        receipt = record.payload.get("result", {}).get("output")
        if (not _valid_receipt(receipt) or receipt["abstention_state"] != "NONE" or
                receipt["evaluator_result"].get("verdict") != "STRUCTURALLY_VERIFIED"):
            continue
        witness = witnesses.get(record.payload.get("witness_id"), {})
        producer = witness.get("capability")
        method = BUILTINS.get(receipt["method"], (None,))[0]
        check = next((c for c in specs.get(data["mission_id"], {}).get("success_checks", [])
                      if c["check_id"] == data["check_id"]), None)
        if (method is None or not method.cognitive_profile or method.version != receipt["method_version"] or
                producer not in ("cognition.solve", receipt["method"]) or not check or
                check["sensor"].get("capability") != producer or
                digest(check["sensor"].get("params", {})) != receipt["input_digest"]):
            continue  # an arbitrary adapter's self-labelled receipt is not cognitive competence
        key = (data["mission_id"], receipt["input_digest"], receipt["method"], receipt["method_version"])
        observations[key] = {"mission_id": data["mission_id"], "receipt": data["receipt"],
                             "cognitive_receipt": receipt["receipt_id"], "method": receipt["method"],
                             "method_version": receipt["method_version"], "geometry_key": geometry_key(ProblemGeometry(**receipt["geometry"])),
                             "correct": data["passed"], "observation_event": event.event_id,
                             "appraisal_event": latest_appraisal[data["mission_id"]].event_id,
                             "cost_usd": receipt["money_cost"], "latency": receipt["latency"],
                             "causal_credit": receipt["causal_credit"],
                             "evidence_tier": "locally reobserved and appraised computation; external outcome unproven",
                             "authority_created": False}
    return list(observations.values())


def competence(journal):
    # Recompute from current evidence instead of trusting a stale settlement cache.
    rows = defaultdict(lambda: {"count": 0, "correct": 0, "cost_usd": 0.0, "latency_seconds": 0.0,
                                "evidence_tier": "local separate-process appraisal"})
    for outcome in measured_outcomes(journal):
        row = rows[outcome["method"], outcome["method_version"], outcome["geometry_key"]]
        row["count"] += 1
        row["correct"] += int(outcome["correct"])
        row["cost_usd"] += outcome["cost_usd"]
        row["latency_seconds"] += outcome["latency"]
    return dict(rows)


def reconcile(journal):
    retained = {e.payload["observation_event"] for e in journal.replay("cognition.settled")}
    for outcome in measured_outcomes(journal):
        if outcome["observation_event"] not in retained:
            journal.record("cognition.settled", outcome, key=outcome["observation_event"],
                           causal_parent=outcome["observation_event"])


def outcome_calibration(journal):
    # A passing predicate is not a labeled realization of a probabilistic event.
    # Retain the seam; require real prediction-target outcomes before calibration.
    return {"verdict": "unmeasured", "n": 0,
            "missing": "receipt-bound realizations of the predicted event, distinct from solver acceptance"}
