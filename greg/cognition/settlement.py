"""Outcome competence is a replayed projection of canonical receipts and appraisals."""
from __future__ import annotations

from collections import defaultdict

from .contracts import CognitiveReceipt, ProblemGeometry, digest


IDENTITY_VERSION = "signed-claim/1"
IDENTITY_FIELDS = ("identity_version", "mission_id", "command_digest", "check_id", "check_digest",
                   "input_digest", "problem_id", "method", "method_version", "geometry_key")


def _claim_fields(registration, check, receipt):
    """The registered, signed check defines the claim; a method label does not."""
    return {"identity_version": IDENTITY_VERSION,
            "mission_id": registration["mission_id"], "command_digest": registration["command_digest"],
            "check_id": check["check_id"], "check_digest": digest(check),
            "input_digest": receipt["input_digest"], "problem_id": receipt["problem_id"]}


def _outcome_identity(outcome):
    return digest({field: outcome[field] for field in IDENTITY_FIELDS})


def _valid_receipt(value):
    if not isinstance(value, dict) or value.get("authority_created") is not False:
        return False
    copy = dict(value)
    identity = copy.pop("receipt_id", None)
    try:
        if identity != digest(copy) or set(copy) - set(CognitiveReceipt.__dataclass_fields__):
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
    registrations = {e.payload["mission_id"]: e.payload for e in journal.replay("mission.registered")}
    witnesses = {r.payload["witness_id"]: r.payload for r in journal.ledger.by_type("witness")}
    latest_appraisal, observations = {}, {}
    for event in journal.replay("mission.appraised"):
        data = event.payload
        checks = data.get("checks", {})
        supported = all(checks.get(k) is True for k in REQUIRED_CHECKS if k != "world_reobserved")
        local_artifact = (checks.get("applicable_observations_revalidated") is True
                          and bool(data.get("numerical_artifact_verification")))
        if (data.get("verdict") == "VERIFIED" and supported
                and (checks.get("world_reobserved") is True or local_artifact)):
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
        appraisal = latest_appraisal[data["mission_id"]].payload
        if appraisal.get("checks", {}).get("world_reobserved") is not True:
            scope = next((s for s in appraisal.get("numerical_artifact_verification", [])
                          if s.get("check_id") == data["check_id"]), {})
            if (scope.get("current_world_observation") is not False
                    or scope.get("receipt_id") != (receipt or {}).get("receipt_id")
                    or scope.get("artifact_verification", {}).get("verdict") != "STRUCTURALLY_VERIFIED"):
                continue  # no generic snapshot, semantic or Foundry credit
        witness = witnesses.get(record.payload.get("witness_id"), {})
        producer = witness.get("capability")
        method = BUILTINS.get(receipt["method"], (None,))[0]
        registration = registrations.get(data["mission_id"], {})
        check = next((c for c in registration.get("spec", {}).get("success_checks", [])
                      if c["check_id"] == data["check_id"]), None)
        if (method is None or not method.cognitive_profile or method.version != receipt["method_version"] or
                producer not in ("cognition.solve", receipt["method"]) or not check or
                check["sensor"].get("capability") != producer or
                digest(check["sensor"].get("params", {})) != receipt["input_digest"]):
            continue  # an arbitrary adapter's self-labelled receipt is not cognitive competence
        outcome = {**_claim_fields(registration, check, receipt), "receipt": data["receipt"],
                             "cognitive_receipt": receipt["receipt_id"], "method": receipt["method"],
                             "method_version": receipt["method_version"], "geometry_key": geometry_key(ProblemGeometry(**receipt["geometry"])),
                             "correct": data["passed"], "observation_event": event.event_id,
                             "appraisal_event": latest_appraisal[data["mission_id"]].event_id,
                             "cost_usd": receipt["money_cost"], "latency": receipt["latency"],
                             "causal_credit": receipt["causal_credit"],
                             "evidence_tier": "validated local encoded computation; empirical outcome unproven",
                             "empirical_outcome": False,
                             "authority_created": False}
        # Reobservations revise this signed claim; another check/input is not its duplicate.
        observations[_outcome_identity(outcome)] = outcome
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


def _historical_identity(payload, registrations, observations, journal):
    """Project old records onto claim identities without altering retained bytes.

    Legacy outcome IDs collapsed different inputs. Their exact observation and
    receipt pointers can disambiguate them, even after an appraisal is refuted.
    Unresolvable history retains its old identity and is invalidated, not credited.
    """
    if all(field in payload for field in IDENTITY_FIELDS):
        return _outcome_identity(payload)
    observation = observations.get(payload.get("observation_event"), {})
    registration = registrations.get(observation.get("mission_id"), {})
    check = next((c for c in registration.get("spec", {}).get("success_checks", [])
                  if c["check_id"] == observation.get("check_id")), None)
    record = journal.ledger.find(observation.get("receipt")) if observation.get("receipt") else None
    receipt = record.payload.get("result", {}).get("output") if record is not None and record.record_type == "receipt" else None
    if (check and isinstance(receipt, dict) and registration.get("command_digest") and
            payload.get("mission_id") == observation.get("mission_id") and
            payload.get("receipt") == observation.get("receipt") and
            payload.get("method") == receipt.get("method") and
            payload.get("method_version") == receipt.get("method_version") and
            isinstance(receipt.get("problem_id"), str) and
            digest(check["sensor"].get("params", {})) == receipt.get("input_digest")):
        return _outcome_identity({**payload, **_claim_fields(registration, check, receipt)})
    return payload.get("outcome_id", payload.get("observation_event"))


def reconcile(journal):
    # Append revisions/invalidation. Never silently rewrite historical credit.
    registrations = {e.payload["mission_id"]: e.payload for e in journal.replay("mission.registered")}
    observations = {e.event_id: e.payload for e in journal.replay("mission.observed")}
    current = {}
    for event in journal.replay("cognition.settled"):
        identity = _historical_identity(event.payload, registrations, observations, journal)
        current[identity if identity is not None else event.event_id] = event
    measured = {}
    for outcome in measured_outcomes(journal):
        identity = _outcome_identity(outcome)
        outcome = {**outcome, "outcome_id": identity, "evidence_class": "validated_local_computation", "invalidated": False}
        measured[identity] = outcome
        prior = current.get(identity)
        if prior is None or digest({k:v for k,v in prior.payload.items() if k != "supersedes"}) != digest(outcome):
            journal.record("cognition.settled", {**outcome, "supersedes": prior.event_id if prior else None},
                           key=[identity, "revision", digest(outcome), prior.event_id if prior else None],
                           causal_parent=outcome["observation_event"])
    for identity, prior in current.items():
        if identity not in measured and not prior.payload.get("invalidated"):
            revision = {**prior.payload, "invalidated": True, "supersedes": prior.event_id,
                        "reason": "current appraisal no longer supports competence; history retained"}
            journal.record("cognition.settled", revision, key=[identity, "invalidate", prior.event_id], causal_parent=prior.event_id)


def outcome_calibration(journal):
    # A passing predicate is not a labeled realization of a probabilistic event.
    # Retain the seam; require real prediction-target outcomes before calibration.
    return {"verdict": "unmeasured", "n": 0,
            "missing": "receipt-bound realizations of the predicted event, distinct from solver acceptance"}
