"""SOP compounding: stop paying intelligence to rediscover the same procedure.

The systems worker watches verified closures. When the same ordered sequence of
capabilities closes missions repeatedly, it proposes a Standard Operating
Procedure with measured cost per verified outcome. A founder-signed SOP_RATIFY
turns the proposal into a registered procedure; nothing self-promotes.

Compounding is measured, not asserted: actions, model calls and founder
decisions per verified outcome are reported so a declining trend can be seen
(or its absence admitted).
"""
from __future__ import annotations

from collections import defaultdict

from greg.journal import Journal
from provenance.ledger import sha256_json

MIN_OCCURRENCES = 3
REQUIRED_CHECKS = ("chain_intact", "founder_signature_verified", "checks_rederived_from_receipts",
                   "world_reobserved", "exactly_once", "deliveries_bound_to_evidence",
                   "approval_boundaries_honored")


def verified_appraisals(journal: Journal) -> dict[str, str]:
    """Latest appraisal wins; an achievement alone does not establish an outcome.

    This is the body's separate-process appraisal, not an external trust root.
    Its event ID records which local evidence supported a proposal.
    """
    latest = {}
    for event in journal.replay("mission.appraised"):
        latest[event.payload["mission_id"]] = event
    return {mid: event.event_id for mid, event in latest.items()
            if event.payload.get("verdict") == "VERIFIED"
            and all(event.payload.get("checks", {}).get(check) is True for check in REQUIRED_CHECKS)}


def closed_procedures(journal: Journal) -> dict[str, list]:
    """mission_id -> ordered capabilities of DONE actions for locally verified closures."""
    achieved = {e.payload["mission_id"] for e in journal.replay("mission.achieved")}
    achieved.intersection_update(verified_appraisals(journal))
    steps = defaultdict(list)
    for event in journal.replay("mission.action"):
        data = event.payload
        if data["mission_id"] in achieved and data["status"] == "DONE":
            steps[data["mission_id"]].append(data["capability"])
    return dict(steps)


def propose(journal: Journal) -> list[dict]:
    appraisals = verified_appraisals(journal)
    groups = defaultdict(list)
    for mission_id, sequence in closed_procedures(journal).items():
        groups[tuple(sequence)].append(mission_id)
    proposals = []
    existing = {e.payload["procedure_id"] for e in journal.replay("sop.proposed")}
    for sequence, missions in groups.items():
        if len(missions) < MIN_OCCURRENCES or not sequence:
            continue
        procedure_id = "sop-" + sha256_json(list(sequence))[7:23]
        if procedure_id in existing:
            continue
        record = {"procedure_id": procedure_id, "steps": list(sequence), "occurrences": len(missions),
                  "missions": sorted(missions), "actions_per_outcome": len(sequence),
                  "appraisal_events": {mid: appraisals[mid] for mid in sorted(missions)},
                  "evidence_level": "local separate-process appraisal; external outcome unproven",
                  "state": "PROPOSED", "promotion": "requires founder SOP_RATIFY"}
        journal.record("sop.proposed", record, key=procedure_id)
        proposals.append(record)
    return proposals


def ratify(journal: Journal, body: dict, command_digest: str) -> dict:
    procedure_id = body.get("procedure_id")
    proposed = [e.payload for e in journal.replay("sop.proposed") if e.payload["procedure_id"] == procedure_id]
    if not proposed:
        raise ValueError("unknown SOP proposal")
    current = closed_procedures(journal)
    if any(current.get(mid) != proposed[0]["steps"] for mid in proposed[0]["missions"]):
        raise ValueError("SOP proposal no longer locally appraised as verified; inspect its evidence")
    record = {"procedure_id": procedure_id, "steps": proposed[0]["steps"], "state": "RATIFIED",
              "command_digest": command_digest, "authority_inherited": False}
    journal.record("sop.ratified", record, key=procedure_id)
    return record


def compounding_metrics(journal: Journal) -> dict:
    achieved = {e.payload["mission_id"] for e in journal.replay("mission.achieved")}
    outcomes = len(achieved.intersection(verified_appraisals(journal)))
    actions = sum(1 for e in journal.replay("mission.action") if e.payload["status"] == "DONE")
    decisions = len(journal.replay("decision.requested"))
    # Recorded provider attempts and cognitive workers are different seams.
    # These are a lower bound: historical planner calls can lack a durable
    # event, so absence of records cannot establish zero model expenditure.
    model_attempts = sum(e.payload.get("outcome") in {"ok", "failed", "refused"}
                         for e in journal.replay("model.route"))
    def cognitive_attempts(output):
        if not isinstance(output, dict):
            return 0
        if "receipts" in output:
            return sum(cognitive_attempts(r) for r in output["receipts"] if isinstance(r, dict))
        count = output.get("compute_cost", {}).get("model_calls", 0)
        return count if type(count) is int and count >= 0 else 0
    model_attempts += sum(cognitive_attempts(r.payload.get("result", {}).get("output"))
                          for r in journal.ledger.by_type("receipt"))
    return {"verified_outcomes": outcomes,
            "actions_per_outcome": (actions / outcomes) if outcomes else None,
            "founder_decisions_per_outcome": (decisions / outcomes) if outcomes else None,
            "model_calls_per_outcome": None,
            "recorded_model_call_attempts": model_attempts,
            "model_calls_per_outcome_lower_bound": model_attempts / outcomes if outcomes else None,
            "model_call_coverage": "partial retained observations; total unmeasured",
            "note": "null means no complete measurement; local computation and founder attention also cost resources"}
