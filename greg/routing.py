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
Each dispatched attempt is one outcome: a founder reconciliation of an UNCERTAIN
dispatch replaces that attempt's outcome and, having no receipt, is counted apart
(founder_reconciled) and never moves reliability.
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


RECONCILIATION_ROUTES = ("founder_reconciliation", "standing_reconciliation")


def founder_reconciled(action: dict) -> bool:
    """A statement about an UNCERTAIN dispatch, not a receipted execution: the founder's own, or one settled under
    the founder's signed standing mandate with a recorded proof (greg.workers.inert_interruption_proof).

    Records written before 2026-10-14 name no route; their reasons still say so."""
    return not action.get("receipt") and (action.get("route") in RECONCILIATION_ROUTES or any(
        str(r).startswith("founder reconciliation: ") for r in action.get("reasons") or ()))


def dispatch_outcomes(events):
    """Each dispatch's outcome counted once. A founder's RECONCILED_NOT_EXECUTED settles an UNCERTAIN dispatch whose
    failure was already counted (same mission, action and attempt), so it is not a second failure, even when it
    carries the capability for its spend record (a metered run's booked cap). A settlement with no UNCERTAIN before
    it is still counted."""
    uncertain = set()
    for event in events:
        data = event.payload
        dispatch = (data.get("mission_id"), data.get("action_id"), data.get("attempt"))
        if data.get("status") == "UNCERTAIN":
            uncertain.add(dispatch)
        elif data.get("status") == "RECONCILED_NOT_EXECUTED" and dispatch in uncertain:
            continue
        yield event


def track_record(journal: Journal) -> dict[str, dict]:
    record = defaultdict(lambda: {"done": 0, "failed": 0, "ineffective": 0, "refuted": 0, "verified": 0,
                                  "founder_reconciled": 0})
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
    # One outcome per dispatched attempt: a founder reconciliation of an UNCERTAIN dispatch is a later fact
    # about the same (mission, action, attempt) and replaces it; it never adds a second outcome.
    attempts = {}
    for index, event in enumerate(journal.replay("mission.action")):
        data = event.payload
        key = (data.get("mission_id"), data.get("action_id"), data["attempt"]) if "attempt" in data else index
        prior = attempts.get(key)
        if prior is not None and not data.get("capability"):     # legacy reconciliations name no capability
            data = {**data, "capability": prior.get("capability")}
        attempts[key] = data
    for data in attempts.values():
        capability = data.get("capability")
        if not capability:
            continue
        if data["status"] in SUCCESS and founder_reconciled(data):
            record[capability]["founder_reconciled"] += 1     # no receipt: neither a success nor a failure
        elif data["status"] in SUCCESS:
            record[capability]["done"] += 1
            if data.get("mission_id") in appraisals:
                record[capability][appraisals[data["mission_id"]]] += 1
        elif data["status"] in FAILURE:
            record[capability]["failed"] += 1
    for event in journal.replay("routing.outcome"):
        if event.payload["verdict"] == "ineffective":
            record[event.payload.get("capability") or "?"]["ineffective"] += 1
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


def cognitive_knowledge(journal: Journal) -> list[dict]:
    """Conditional outcome projection; never edits routing weights or protected policy.

    Latest corrections supersede, not erase. Missing outcomes stay unscored.
    Benchmark, synthetic and observed tiers cannot lend each other credibility.
    """
    from greg.cognition.seed_path import claim_ran
    latest = {}
    for event in journal.replay('cognition.outcome'):
        latest[event.payload['receipt_id']] = event.payload
    receipts = {e.payload['receipt_id']: e.payload for e in journal.replay('cognition.receipt')}
    groups = {}
    import json
    for outcome in latest.values():
        methods = outcome['methods']
        if 'unexecuted_methods' not in outcome:
            # An outcome retained before 0.2.2 listed every claim: count only the claims that ran (verified 2026-10-21).
            claims = (receipts.get(outcome['receipt_id']) or {}).get('claims') or []
            methods = [m for m, c in zip(methods, claims) if claim_ran(c)]
        for method in methods:
            key = json.dumps([method, outcome['tier'], outcome['conditions']], sort_keys=True)
            row = groups.setdefault(key, {'method': method, 'tier': outcome['tier'],
                'conditions': outcome['conditions'], 'observations': 0, 'missing': 0, 'scores': [],
                'authority_created': False, 'routing_update': 'none; held-out promotion gate required'})
            row['observations'] += 1
            if outcome['score'] is None:
                row['missing'] += 1
            else:
                row['scores'].append(outcome['score'])
    return [groups[k] for k in sorted(groups)]


# Sensors and acquired readers. A method that did not measure the world is recorded on
# mission.observed with a detail the engine prefixes "sensor " (the same marker as
# greg.missions.measured). Later selection reads this projection. It is recomputed from
# the journal, bounded to the newest observations, and it never receives or rewrites a
# signed check.
OBSERVATION_WINDOW = 64


def observation_method_failed(observation: dict) -> bool:
    """True when this observation did not measure the world.

    A predicate miss is a measurement: its detail does not start with "sensor ".
    """
    return str(observation.get("detail", "")).startswith("sensor ")


def observation_competence(journal) -> dict[str, dict]:
    """Latest retained outcome per capability, inside the newest OBSERVATION_WINDOW observations that name one.

    ``method_failed`` is the only fact selection uses. Older than the window, a failure no longer ranks.
    No journal, no memory. The payloads are not copied back and are not signed checks.
    """
    if journal is None:
        return {}
    named = [e.payload for e in journal.replay("mission.observed")
             if isinstance(e.payload, dict) and e.payload.get("capability")]
    latest = {}
    for payload in named[-OBSERVATION_WINDOW:]:
        latest[payload["capability"]] = {"method_failed": observation_method_failed(payload)}
    return latest


def rank_observation_methods(items, competence: dict, capability_id):
    """Stable order: a method whose latest in-window observation failed sorts after the others.

    Nothing is removed. ``items`` are not signed checks; this does not write into them.
    """
    return sorted(items, key=lambda item: 1 if competence.get(capability_id(item), {}).get("method_failed") else 0)
