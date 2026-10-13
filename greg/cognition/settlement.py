"""Outcome competence is a replayed projection of canonical receipts and appraisals."""
from __future__ import annotations

from collections import defaultdict

from .contracts import RECEIPT_V01_FIELDS, CognitiveReceipt, ProblemGeometry, digest


def _valid_receipt(value):
    if not isinstance(value, dict) or value.get("authority_created") is not False:
        return False
    copy = dict(value)
    identity = copy.pop("receipt_id", None)
    try:
        # Both receipt versions settle: v0.1 with its original field set, v0.2 with every field.
        if identity != digest(copy) or set(copy) not in (set(RECEIPT_V01_FIELDS),
                                                         set(CognitiveReceipt.__dataclass_fields__)):
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


def _logical(outcome):
    """One settlement per logical outcome: the same mission, input, method and version."""
    return digest({k: outcome[k] for k in ("mission_id", "cognitive_receipt", "method", "method_version")})


def reconcile(journal):
    # Idempotent: a duplicated delivery of the same outcome settles nothing new. A changed
    # outcome (a later failure or appraisal) appends a record that supersedes the last one;
    # nothing earlier is rewritten.
    latest = {}
    for event in journal.replay("cognition.settled"):
        payload = event.payload
        key = payload.get("settlement_key") or _logical(payload)
        latest[key] = (event.event_id, payload)
    for outcome in measured_outcomes(journal):
        key = _logical(outcome)
        previous = latest.get(key)
        if previous and previous[1].get("correct") == outcome["correct"]:
            continue
        record = {**outcome, "settlement_key": key, "supersedes": previous[0] if previous else None}
        event = journal.record("cognition.settled", record, key=key + ":" + outcome["observation_event"],
                               causal_parent=outcome["observation_event"])
        latest[key] = (getattr(event, "event_id", None), record)


def outcome_calibration(journal):
    # A passing predicate is not a labeled realization of a probabilistic event.
    # Retain the seam; require real prediction-target outcomes before calibration.
    return {"verdict": "unmeasured", "n": 0,
            "missing": "receipt-bound realizations of the predicted event, distinct from solver acceptance"}
