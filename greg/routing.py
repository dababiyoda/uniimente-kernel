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
FAILURE = {"UNAVAILABLE", "UNCERTAIN", "RECONCILED_NOT_EXECUTED"}
EFFECT_CHECKS = ("checks_rederived_from_receipts", "world_reobserved")  # appraiser checks a capability owns
AUTHENTICITY_CHECKS = ("chain_intact", "founder_signature_verified", "approval_boundaries_honored", "exactly_once")


def track_record(journal: Journal) -> dict[str, dict]:
    record = defaultdict(lambda: {"done": 0, "failed": 0, "ineffective": 0, "refuted": 0,
                                  "verified": 0, "computationally_verified": 0, "refused": 0})
    appraisals = {}
    negative_invocations = {r.hash for r in journal.ledger.by_type("receipt")
                            if r.payload.get("result", {}).get("result_class") == "negative"
                            and (r.payload["result"].get("failure_kind") == "CAPABILITY_ERROR"
                                 or r.payload["result"].get("observed_outcome", "").startswith("capability refused: "))}
    for event in journal.replay("mission.appraised"):
        data = event.payload
        effect_ok = all(data.get("checks", {}).get(c, False) for c in EFFECT_CHECKS)
        authentic = all(data.get("checks", {}).get(c) is True for c in AUTHENTICITY_CHECKS)
        if data["verdict"] == "VERIFIED" and authentic:
            if effect_ok:
                appraisals[data["mission_id"]] = "verified"
            elif data.get("checks", {}).get("applicable_observations_revalidated") is True:
                appraisals[data["mission_id"]] = "computationally_verified"
            else:
                appraisals.pop(data["mission_id"], None)
        elif data["verdict"] == "REFUTED" and authentic and not effect_ok:
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
        elif data["status"] == "REFUSED":
            # Founder/policy/provider refusal is an authority outcome, never a
            # capability outage. Keep it visible without reducing reliability.
            record[capability]["refused"] += 1
            if data.get("receipt") in negative_invocations:
                # Legacy REFUSED also represents an invoked adapter exception.
                # Native negative receipts distinguish it from pre-invocation
                # founder/policy refusal without guessing from caller text.
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
