"""Night shift -> morning tribunal: truthful review and governed founder critique.

The report is a read-only projection of retained history since the previous
review. It answers the founder's morning questions from evidence, labels every
claim with its reality status, and never counts process activity as a result.

Critique is a founder-signed command. It is appended as new evidence and never
edits the reviewed record. It becomes, explicitly and traceably:

* a binding strategy exclusion (policy correction the engine enforces), and/or
* a regression obligation that stays open in every report until closed, and/or
* a preference note for future planning.

"Alfonso disliked this" (founder_judgment) and "evidence shows this failed"
(objective_failure) are different evidence types and are kept distinct.
"""
from __future__ import annotations

from greg.journal import Journal, iso, utcnow
from provenance.ledger import sha256_json

EVIDENCE_TYPES = ("founder_judgment", "objective_failure")
VERDICTS = ("reject", "accept", "note")


class CritiqueError(ValueError):
    pass


def _window(journal: Journal):
    events = journal.replay()
    last = [e for e in events if e.type == "greg.tribunal.reported"]
    start = last[-1].payload["through_event"] if last else None
    if start is None:
        return events, None
    ids = [e.event_id for e in events]
    return (events[ids.index(start) + 1:] if start in ids else events), start


def morning_report(journal: Journal, engine=None) -> dict:
    events, previous = _window(journal)
    by = lambda kind: [e.payload for e in events if e.type == "greg." + kind]
    all_events = journal.replay()
    missions = {e.payload["mission_id"]: e.payload["spec"] for e in all_events if e.type == "greg.mission.registered"}
    touched = sorted({e.payload.get("mission_id") for e in events if e.payload.get("mission_id") in missions})
    actions = by("mission.action")
    observations = by("mission.observed")
    done = [a for a in actions if a["status"] == "DONE"]
    failures = [a for a in actions if a["status"] in ("REFUSED", "UNAVAILABLE", "UNCERTAIN")]
    # Surprise = predicted effect did not appear: a DONE action whose advanced
    # checks were still failing at the next observation of that check.
    surprises = []
    for action in done:
        spec = missions.get(action["mission_id"], {})
        strategy = next((s for s in spec.get("strategies", []) if s["action_id"] == action["action_id"]), None)
        for check in (strategy or {}).get("advances", []):
            later = [o for o in observations if o["mission_id"] == action["mission_id"]
                     and o["check_id"] == check and o["at"] >= action["at"]]
            if later and not later[0]["passed"]:
                surprises.append({"action_id": action["action_id"], "check_id": check,
                                  "expected": "check passes after action", "observed": later[0]["detail"]})
    open_requests = []
    answered = {e.payload["request_id"] for e in all_events
                if e.type in ("greg.decision.answered", "greg.decision.withdrawn")}
    for e in all_events:
        if e.type == "greg.decision.requested" and e.payload["request_id"] not in answered:
            open_requests.append(e.payload)
    critiques = [e.payload for e in all_events if e.type == "greg.critique.recorded"]
    closed = {e.payload["regression_id"] for e in all_events if e.type == "greg.critique.regression_closed"}
    regressions = [c["regression"] for c in critiques if c.get("regression")
                   and c["regression"]["regression_id"] not in closed]
    ok, chain = journal.ledger.verify_chain()
    status = {}
    if engine is not None:
        engine.book.rebuild()
        for mid, m in engine.book.missions.items():
            status[mid] = {"status": m.status, "paused": m.paused, "rung": m.rung, "blocker": m.blocker,
                           "next_observe_at": m.next_observe_at, "spent_usd": m.spent_usd}
    report = {
        "reality_status": "RETAINED_EVIDENCE_PROJECTION",
        "window": {"after_event": previous, "events": len(events)},
        "q1_goals_worked_on": [{"mission_id": mid, "intended_effect": missions[mid]["intended_effect"],
                                 "state": status.get(mid)} for mid in touched],
        "q2_why": {mid: missions[mid]["founder_expression"][:300] for mid in touched},
        "q3_what_i_did": [{k: a[k] for k in ("mission_id", "action_id", "capability", "route", "status",
                                               "receipt", "cost_usd", "at")} for a in actions],
        "q4_intentionally_not_done": [{"mission_id": b["mission_id"], "blocker": b["blocker"]}
                                      for b in by("mission.blocked")],
        "q5_what_changed_in_reality": {
            "setpoints_reached": by("mission.setpoint"), "missions_achieved": by("mission.achieved"),
            "checks_passing": sorted({(o["mission_id"], o["check_id"]) for o in observations if o["passed"]}),
            "note": "changes are re-observed through read-only sensors; worker claims are not counted"},
        "q6_what_failed": failures + [{"deficit_route": r} for r in by("genesis.route")
                                      if "failed" in r["result"] or "cannot verify" in r["result"]]
                          + [{"verification": v} for v in by("genesis.verified") if not v["passed"]]
                          + by("command.rejected"),
        "q7_surprises": surprises,
        "q8_evidence": {"ledger_head": journal.ledger.head, "chain_verified": ok, "chain": chain,
                        "receipts": [a["receipt"] for a in done if a.get("receipt")]},
        "q9_learned": {"capabilities_acquired": by("deficit.resolved"), "sops_proposed": by("sop.proposed"),
                       "critiques_applied": [c["critique_id"] for c in critiques]},
        "q10_retain": sorted({a["capability"] for a in done}),
        "q11_change": [{"regression_id": r["regression_id"], "description": r["description"]} for r in regressions],
        "q12_decisions_required": [{"request_id": r["request_id"], "kind": r["kind"], "mission_id": r["mission_id"],
                                    "why_now": r["why_now"], "recommendation": r["recommendation"],
                                    "alternatives": r["alternatives"],
                                    "consequence_of_no_response": r["consequence_of_no_response"]}
                                   for r in open_requests],
        "q13_tonight": [{"mission_id": mid, **st} for mid, st in status.items()
                        if st["status"] not in ("ACHIEVED", "ABANDONED", "SUPERSEDED")],
        "metrics": {"actions_done": len(done), "actions_failed": len(failures),
                    "founder_decisions_requested": len(by("decision.requested")),
                    "founder_commands_accepted": len(by("command.accepted")),
                    "model_calls": 0, "verified_mission_closures": len(by("mission.achieved")),
                    "spend_usd": round(sum(a.get("cost_usd", 0.0) for a in done), 6)},
        "claims_not_made": ["no external business outcome", "no Mac verification unless recorded by the Mac package",
                            "no model output treated as evidence"],
    }
    from greg import metrics, routing
    report["single_bottleneck_metric"] = metrics.vepmc(journal)
    report["appraisals"] = [e.payload for e in journal.replay("mission.appraised")]
    report["routing_knowledge"] = routing.routing_knowledge(journal)
    report["report_digest"] = sha256_json(report)
    return report


def mark_reviewed(journal: Journal, report: dict) -> None:
    events = journal.replay()
    through = events[-1].event_id if events else None
    journal.record("tribunal.reported", {"through_event": through, "report_digest": report["report_digest"],
                                         "at": iso(utcnow())}, key=report["report_digest"])


def critique(journal: Journal, engine, body: dict, command_digest: str) -> dict:
    """Apply a founder-signed critique without rewriting the criticized history."""
    required = {"target_event_id", "verdict", "evidence_type", "text"}
    if not required <= set(body) or set(body) - required - {"exclude_strategy", "regression"}:
        raise CritiqueError("critique needs target_event_id, verdict, evidence_type, text")
    if body["verdict"] not in VERDICTS or body["evidence_type"] not in EVIDENCE_TYPES:
        raise CritiqueError("unknown verdict or evidence type")
    target = next((e for e in journal.replay() if e.event_id == body["target_event_id"]), None)
    if target is None:
        raise CritiqueError("critique must reference a retained event")
    critique_id = "crit-" + command_digest[7:31]
    record = {"critique_id": critique_id, "target_event_id": target.event_id,
              "target_event_hash": journal.event_hash(target.event_id), "target_type": target.type,
              "verdict": body["verdict"], "evidence_type": body["evidence_type"], "text": body["text"][:4000],
              "command_digest": command_digest, "history_rewritten": False}
    if body.get("regression"):
        record["regression"] = {"regression_id": "reg-" + command_digest[7:23],
                                "description": str(body["regression"])[:1000], "state": "OPEN",
                                "close_condition": "a test or check that fails on the criticized behavior"}
    journal.record("critique.recorded", record, key=critique_id)
    if body.get("exclude_strategy"):
        mission_id = target.payload.get("mission_id")
        action_id = target.payload.get("action_id") or body["exclude_strategy"]
        if not mission_id:
            raise CritiqueError("strategy exclusion needs a mission-bound target event")
        engine.exclude_strategy(mission_id, action_id, f"founder critique ({body['evidence_type']}): "
                                + body["text"][:200], critique_id)
    return record
