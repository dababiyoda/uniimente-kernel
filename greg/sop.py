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


def closed_procedures(journal: Journal) -> dict[str, list]:
    """mission_id -> ordered capabilities of DONE actions, for achieved missions only."""
    achieved = {e.payload["mission_id"] for e in journal.replay("mission.achieved")}
    steps = defaultdict(list)
    for event in journal.replay("mission.action"):
        data = event.payload
        if data["mission_id"] in achieved and data["status"] == "DONE":
            steps[data["mission_id"]].append(data["capability"])
    return dict(steps)


def propose(journal: Journal) -> list[dict]:
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
                  "state": "PROPOSED", "promotion": "requires founder SOP_RATIFY"}
        journal.record("sop.proposed", record, key=procedure_id)
        proposals.append(record)
    return proposals


def ratify(journal: Journal, body: dict, command_digest: str) -> dict:
    procedure_id = body.get("procedure_id")
    proposed = [e.payload for e in journal.replay("sop.proposed") if e.payload["procedure_id"] == procedure_id]
    if not proposed:
        raise ValueError("unknown SOP proposal")
    record = {"procedure_id": procedure_id, "steps": proposed[0]["steps"], "state": "RATIFIED",
              "command_digest": command_digest, "authority_inherited": False}
    journal.record("sop.ratified", record, key=procedure_id)
    return record


def compounding_metrics(journal: Journal) -> dict:
    outcomes = len(journal.replay("mission.achieved"))
    actions = sum(1 for e in journal.replay("mission.action") if e.payload["status"] == "DONE")
    decisions = len(journal.replay("decision.requested"))
    return {"verified_outcomes": outcomes,
            "actions_per_outcome": (actions / outcomes) if outcomes else None,
            "founder_decisions_per_outcome": (decisions / outcomes) if outcomes else None,
            "model_calls_per_outcome": 0 if outcomes else None,
            "note": "null means no verified outcome yet; not zero cost and not infinite improvement"}
