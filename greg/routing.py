"""Default Routing learned from receipts: the Spider-Web compounding loop.

    mission execution -> receipts -> track record per capability
      -> reliability estimate -> strategy choice for the NEXT mission
      -> routing decision recorded -> compared with its outcome

Reliability is a Laplace (Beta(1,1)) estimate over retained outcomes, so an
unknown capability starts at 0.5 and every verified success or failure moves it.

Proof feeds routing (verification weighting, after memory/causal.py): when the
independent appraiser REFUTES a closure because its receipts or the re-observed
world do not hold, every capability that acted for that mission loses reliability.
A refutation for reasons that are not the capability's (signature, inbox, replay
boundary) does not move routing. Appraiser-VERIFIED actions are counted apart.
Knowledge is institutional and cross-mission: one mission's failure changes the
next mission's routing. Nothing here grants authority; it only ranks options
that are already inside the founder-signed light cone.
"""
from __future__ import annotations

from collections import defaultdict

from greg.journal import Journal

SUCCESS = {"DONE"}
FAILURE = {"REFUSED", "UNAVAILABLE", "UNCERTAIN", "RECONCILED_NOT_EXECUTED"}
EFFECT_CHECKS = ("checks_rederived_from_receipts", "world_reobserved")  # appraiser checks a capability owns


def track_record(journal: Journal) -> dict[str, dict]:
    record = defaultdict(lambda: {"done": 0, "failed": 0, "ineffective": 0, "refuted": 0, "verified": 0})
    appraisals = {}
    for event in journal.replay("mission.appraised"):
        data = event.payload
        effect_ok = all(data.get("checks", {}).get(c, False) for c in EFFECT_CHECKS)
        if data["verdict"] == "VERIFIED":
            appraisals[data["mission_id"]] = "verified"
        elif data["verdict"] == "REFUTED" and not effect_ok:
            appraisals[data["mission_id"]] = "refuted"
        else:
            appraisals.pop(data["mission_id"], None)
    for event in journal.replay("mission.action"):
        data = event.payload
        capability = data.get("capability")
        if not capability:
            continue
        if data["status"] in SUCCESS:
            record[capability]["done"] += 1
            if data.get("mission_id") in appraisals:
                record[capability][appraisals[data["mission_id"]]] += 1
        elif data["status"] in FAILURE:
            record[capability]["failed"] += 1
    for event in journal.replay("routing.outcome"):
        if event.payload["verdict"] == "ineffective":
            record[event.payload["capability"]]["ineffective"] += 1
    return dict(record)


def reliability(record: dict | None) -> float:
    if not record:
        return 0.5
    penalties = record.get("ineffective", 0) + record.get("refuted", 0)
    good = record["done"] - penalties
    bad = record["failed"] + penalties
    return (max(good, 0) + 1) / (max(good, 0) + bad + 2)


def score(*, gain: int, reliability_estimate: float, cost_usd: float, value_per_check_usd: float) -> float:
    """Expected discrepancy value closed minus spend (both in dollars)."""
    return gain * reliability_estimate * value_per_check_usd - cost_usd


def routing_knowledge(journal: Journal) -> list[dict]:
    rows = []
    for capability, record in sorted(track_record(journal).items()):
        rows.append({"capability": capability, **record, "reliability": round(reliability(record), 3)})
    return rows
