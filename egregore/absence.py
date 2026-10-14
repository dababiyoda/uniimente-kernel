"""Founder return report: what happened while the founder was away, folded from the one ledger.

Founder source (verbatim, ``docs/intent/sources/EGREGORE-SYNTHESIS-MATERIALS-2026-10-14-source.md``,
"At full intended maturity"):

    You disappear from operational involvement for several days. When you return, UNIIMENTE does not
    merely tell you, "I completed 842 tasks". It tells you: Three authorized missions remained active
    [...] $18,430 moved through authorized budgets; every movement reconciled. Two actions were blocked
    by policy. One decision exceeds delegated authority and is waiting for you. Here are the receipts,
    causal evidence, failures, financial results, and what the institution learned.

Compiled effect (directive sections 13 and 27, not the mythology): one deterministic, idempotent,
ledger-derived digest over a time window, readable in one sitting, that

* counts only ledger records whose *logical* time falls inside the window (``at``, ``routed_at``,
  ``prepared_at`` and the like, the same clock the loop writes), never wall-clock guesses or memory;
* never counts prepared work as executed, never counts an executor's own ``validation_status`` as
  verification (only ``verify_outcome`` records by an independent verifier do), never counts a
  classifier decision as a Gate refusal;
* reports money as declared estimates with the Gate's reconciliation flags, never as settlement; the
  ledger holds no bank statement and the report says so in its own words;
* is information. It carries no options, no urgency and no ask, requests nothing, is never routed as an
  attention item, and recording it twice appends nothing (same content, same report id).

Two reporters over one ledger, or one reporter across a restart, produce the same report dictionary.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Mapping, Sequence

from .acquisition import CapabilityAcquisition
from .advancement import AdvancementMonitor
from .attention import FounderAttentionRouter, URGENCY
from .contracts import ContractError, canonical_copy, digest
from .experience import WorldModel
from .goals import GoalRegistry, iso, parse_time
from .gps import BackcastGPSAdapter
from .intersections import FavorableIntersectionDetector
from .interventions import InterventionClassifier
from .opportunity import OpportunityPackager
from .retention import AsymmetryRetention

WAITING_KINDS = ("decision", "confirmation")
TIME_KEYS = ("at", "routed_at", "answered_at", "authorized_at", "prepared_at", "packaged_at", "reported_at",
             "recorded_at", "retained_at", "integrated_at", "detected_at", "planned_at", "qualified_at",
             "attached_at", "detached_at", "drafted_at", "fixed_at")


def _time(payload: Mapping[str, Any]) -> str | None:
    for key in TIME_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


class AbsenceReporter:
    """Read-only projection of the ledger into the founder's return brief. Zero execution authority."""

    REPORT_RECORD = "egregore.return_report"

    def __init__(self, loop: Any):
        self.loop = loop
        self.ledger = loop.ledger
        self.source = loop.source

    @property
    def execution_authority(self) -> str:
        return "none"

    # ------------------------------------------------------------ public
    def report(self, *, since: datetime | str, until: datetime | str, record: bool = True) -> dict[str, Any]:
        """Compile the window ``[since, until]`` (inclusive, logical time). ``record=True`` appends the report
        once; an identical report (same window, same content) is never appended twice."""
        start, end = parse_time(since), parse_time(until)
        if end < start:
            raise ContractError("until precedes since")
        self.loop._sync()
        body = self._compile(start, end)
        content_hash = digest(body)
        report_id = digest({"kind": "egregore-return-report", "since": iso(start), "until": iso(end),
                            "content_hash": content_hash})
        existing = next((r for r in self.ledger.by_type(self.REPORT_RECORD) if r.payload.get("report_id") == report_id), None)
        record_hash = existing.hash if existing is not None else None
        recorded = False
        if record and existing is None:
            written = self.ledger.append(self.REPORT_RECORD, {
                "source": self.source, "report_id": report_id, "content_hash": content_hash,
                "window": body["window"], "report": body,
                "disposition": "information_only; requests nothing; no external channel contacted"})
            record_hash = written.hash
            recorded = True
        return {"report_id": report_id, "content_hash": content_hash, "report": body, "recorded": recorded,
                "record_hash": record_hash, "execution_authority": "none"}

    # ------------------------------------------------------------ fold
    def _compile(self, start: datetime, end: datetime) -> dict[str, Any]:
        from .gravity import DONE_STATES, OPEN_ATTEMPT_STATES   # local: gravity imports this module

        loop = self.loop
        ledger = self.ledger
        by = ledger.by_type
        registry: GoalRegistry = loop.registry

        def within(at: str | None) -> bool:
            return at is not None and start <= parse_time(at) <= end

        def upto(at: str | None) -> bool:
            return at is not None and parse_time(at) <= end

        # -- turns ----------------------------------------------------------------------------------------
        turns = sorted((r.payload["turn"] for r in by(loop.TURN_RECORD) if within(r.payload["turn"]["at"])),
                       key=lambda t: (t["at"], t["turn_id"]))
        processed = [p for t in turns for p in t["processed"]]
        decisions_by_kind = Counter(d["decision"] for p in processed for d in p.get("decisions", []))
        turn_stats = {
            "count": len(turns),
            "by_status": dict(sorted(Counter(t["status"] for t in turns).items())),
            "signals_integrated": sum(len(t["signal_ids"]) for t in turns),
            "derived_readings": sum(len(t.get("derived_signal_ids", ())) for t in turns),
            "wake_events": sum(len(t["woken"]) for t in turns),
            "goals_processed": len(processed),
            "deferred_by_conservation": sum(len(t.get("deferred", ())) for t in turns),
            "deliberation_modes": sorted({t.get("deliberation", "declared_moves") for t in turns}),
            "classifier_decisions": dict(sorted(decisions_by_kind.items())),
        }
        touched = sorted({p["goal_id"] for p in processed})

        # -- interventions: executed / refused / open attempts (as of ``until``) -----------------------------
        interventions = sorted((r.payload for r in by(loop.INTERVENTION_RECORD) if within(r.payload.get("at"))),
                               key=lambda p: (p["at"], p["classification_id"], p["evidence_state"]))
        verifications_upto: dict[tuple[str, str], dict[str, Any]] = {}
        for r in by(loop.VERIFICATION_RECORD):
            v = r.payload
            if upto(v.get("at")):
                verifications_upto[(v["goal_id"], v["route_hash"])] = {
                    "verifier": v["verifier"], "verdict": v["verdict"], "at": v["at"], "record_hash": r.hash}
        executed: list[dict[str, Any]] = []
        seen_executions: set[tuple[str, str, int]] = set()
        refused: list[dict[str, Any]] = []
        for p in interventions:
            spec_i = p["intervention"]
            detail = p.get("detail", {})
            key = (p["goal_id"], spec_i["route_hash"], int(detail.get("attempt", 0) or 0))
            if p["evidence_state"] in DONE_STATES and key not in seen_executions and detail.get("verdict") is None:
                seen_executions.add(key)
                executed.append({
                    "goal_id": p["goal_id"], "intervention_id": spec_i["intervention_id"],
                    "description": spec_i["description"], "consequence_class": spec_i["consequence_class"],
                    "action_class": spec_i["action_class"], "at": p["at"], "attempt": key[2],
                    "receipt_hash": detail.get("receipt_hash"), "action_id": detail.get("action_id"),
                    "outcome_id": detail.get("outcome_id"), "result_class": detail.get("result_class"),
                    "reconciled": "reconciled=True" in str(detail.get("expected_vs_actual", "")),
                    "expected_vs_actual": detail.get("expected_vs_actual"),
                    "executor_claimed_validation": detail.get("executor_claimed_validation"),
                    "how": detail.get("reconciled_from", "gate_run_in_turn"),
                    "estimated_cost_usd": float(spec_i.get("estimated_cost_usd", 0.0) or 0.0),
                    "verification": verifications_upto.get((p["goal_id"], spec_i["route_hash"])),
                })
            elif p["evidence_state"] == "failed":
                refused.append({
                    "goal_id": p["goal_id"], "intervention_id": spec_i["intervention_id"],
                    "description": spec_i["description"], "consequence_class": spec_i["consequence_class"],
                    "at": p["at"], "gate_state": detail.get("state"), "reasons": list(detail.get("reasons", ())),
                    "how": detail.get("reconciled_from", "gate_run_in_turn")})
        latest_as_of: dict[tuple[str, str], dict[str, Any]] = {}
        for r in by(loop.INTERVENTION_RECORD):
            p = r.payload
            if upto(p.get("at")):
                latest_as_of[(p["goal_id"], p["intervention"]["route_hash"])] = p
        open_attempts = sorted(({
            "goal_id": p["goal_id"], "intervention_id": p["intervention"]["intervention_id"],
            "description": p["intervention"]["description"], "consequence_class": p["intervention"]["consequence_class"],
            "evidence_state": p["evidence_state"], "proposal_id": p.get("detail", {}).get("proposal_id"), "since": p["at"],
            "disposition": "never retried blindly; reconcile() closes it from Gate records or an accountable resolution"}
            for p in latest_as_of.values() if p["evidence_state"] in OPEN_ATTEMPT_STATES),
            key=lambda o: (o["since"], o["goal_id"], o["intervention_id"]))
        attempted_in_window = sum(1 for p in interventions if p["evidence_state"] == "attempted")

        # -- prepared (never executed) -----------------------------------------------------------------------
        decision_by_classification = {p["classification_id"]: p["decision"] for p in interventions}
        prepared = sorted(({
            "goal_id": p["goal_id"], "intervention_id": p["intervention"]["intervention_id"],
            "description": p["intervention"]["description"], "consequence_class": p["intervention"]["consequence_class"],
            "decision": decision_by_classification.get(p["classification_id"], "PREPARE_FOR_FOUNDER"),
            "reasons": list(p.get("reasons", ())), "at": p["prepared_at"],
            "estimated_cost_usd": float(p["intervention"].get("estimated_cost_usd", 0.0) or 0.0),
            "disposition": p.get("disposition", "prepared_not_executed")}
            for p in (r.payload for r in by(loop.PREPARED_RECORD)) if within(p.get("prepared_at"))),
            key=lambda o: (o["at"], o["goal_id"], o["intervention_id"]))

        # -- reconciliation, discrepancies, verification ---------------------------------------------------------
        reconciliations = sorted(({"goal_id": p["goal_id"], "route_hash": p["route_hash"], "from": p["from"], "to": p["to"],
                                   "how": p.get("detail", {}).get("reconciled_from"), "at": p["at"]}
                                  for p in (r.payload for r in by(loop.RECONCILIATION_RECORD)) if within(p.get("at"))),
                                 key=lambda o: (o["at"], o["goal_id"], o["route_hash"]))
        reviews_upto = {r.payload["discrepancy_hash"]: r.payload for r in by(loop.DISCREPANCY_REVIEW_RECORD)
                        if upto(r.payload.get("at"))}
        discrepancy_records = [(r.hash, r.payload) for r in by(loop.DISCREPANCY_RECORD) if upto(r.payload.get("at"))]
        discrepancies = {
            "recorded_in_window": sorted(({"goal_id": p["goal_id"], "route_hash": p.get("route_hash"),
                                           "result_class": p.get("result_class"), "expected_vs_actual": p.get("expected_vs_actual"),
                                           "at": p["at"], "discrepancy_hash": h, "reviewed": h in reviews_upto}
                                          for h, p in discrepancy_records if within(p.get("at"))),
                                         key=lambda o: (o["at"], o["goal_id"])),
            "unreviewed_as_of_until": sum(1 for h, _ in discrepancy_records if h not in reviews_upto),
            "reviews_in_window": sum(1 for p in reviews_upto.values() if within(p.get("at"))),
        }
        verifications = sorted(({"goal_id": v["goal_id"], "route_hash": v["route_hash"], "verifier": v["verifier"],
                                 "verdict": v["verdict"], "evidence_refs": len(v.get("evidence_refs", ())), "at": v["at"]}
                                for v in (r.payload for r in by(loop.VERIFICATION_RECORD)) if within(v.get("at"))),
                               key=lambda o: (o["at"], o["goal_id"], o["route_hash"]))

        # -- founder attention: waiting as of ``until`` -----------------------------------------------------------
        asks_upto = {r.payload["item"]["item_id"]: r.payload for r in by(FounderAttentionRouter.ASK_RECORD)
                     if upto(r.payload.get("routed_at"))}
        answers_upto: dict[str, dict[str, Any]] = {}
        for r in by(FounderAttentionRouter.ANSWER_RECORD):
            p = r.payload
            if upto(p.get("answered_at")):
                answers_upto[p["item_id"]] = p   # ledger order: the latest answer wins
        waiting, deferred, informed = [], [], []
        for item_id, ask in asks_upto.items():
            item = ask["item"]
            answer = answers_upto.get(item_id)
            entry = {"item_id": item_id, "goal_id": item["goal_id"], "kind": item["kind"], "urgency": item["urgency"],
                     "category": item.get("category"), "title": item["title"], "question": item["question"],
                     "recommendation": item.get("recommendation"), "effort_estimate": item.get("effort_estimate"),
                     "options": [{"label": o.get("label"), "cost": o.get("cost")} for o in item.get("options", ())],
                     "lane": ask["lane"], "routed_at": ask["routed_at"],
                     "waiting_seconds": (end - parse_time(ask["routed_at"])).total_seconds()}
            if answer is None:
                (waiting if item["kind"] in WAITING_KINDS else informed).append(entry)
            elif answer["decision"] == "defer":
                deferred.append({**entry, "resurface_after": answer.get("resurface_after")})
        order = lambda e: (URGENCY.index(e["urgency"]), e["routed_at"], e["item_id"])  # noqa: E731
        waiting.sort(key=order)
        informed.sort(key=order)
        deferred.sort(key=order)
        information_in_window = [e for e in informed if within(e["routed_at"])]

        # -- founder activity in the window ---------------------------------------------------------------------
        answers_in_window = [p for p in (r.payload for r in by(FounderAttentionRouter.ANSWER_RECORD)) if within(p.get("answered_at"))]
        preferences_in_window = [p for p in (r.payload for r in by(GoalRegistry.PREFERENCE_RECORD))
                                 if within(p.get("state", {}).get("last_reviewed_at"))]
        authorizations_in_window = [p for p in (r.payload for r in by(GoalRegistry.AUTHORIZED_RECORD)) if within(p.get("authorized_at"))]
        reviews_in_window = [p for p in reviews_upto.values() if within(p.get("at"))]
        resolutions_in_window = [p for p in reconciliations if p["how"] == "accountable_resolution"]
        founder_activity = {
            "answers": len(answers_in_window),
            "answer_decisions": dict(sorted(Counter(p["decision"] for p in answers_in_window).items())),
            "preferences_or_refusals": len(preferences_in_window),
            "goals_authorized": len(authorizations_in_window),
            "discrepancy_reviews": len(reviews_in_window),
            "accountable_resolutions": len(resolutions_in_window),
            "actors": sorted({p.get("actor") for p in answers_in_window if p.get("actor")}
                             | {p.get("reviewer") for p in reviews_in_window if p.get("reviewer")}),
        }
        founder_activity["away"] = not any(v for k, v in founder_activity.items() if isinstance(v, int))
        founder_activity["note"] = ("no founder answer, preference, authorization, review or resolution fell in this window; "
                                    "everything below happened under standing authority or was prepared"
                                    if founder_activity["away"] else "the founder acted in this window; counts above")

        # -- money: estimates and reconciliation flags, never settlement --------------------------------------------
        reconciled_n = sum(1 for e in executed if e["reconciled"])
        settlement_like = sum(1 for r in by("event")
                              if str(r.payload.get("type", "")).startswith(("treasury.", "business.")))
        money = {
            "estimated_cost_usd_executed": round(sum(e["estimated_cost_usd"] for e in executed), 6),
            "estimated_cost_usd_prepared_not_spent": round(sum(p["estimated_cost_usd"] for p in prepared), 6),
            "executed_moves_reconciled": reconciled_n,
            "executed_moves_unreconciled": len(executed) - reconciled_n,
            "treasury_or_business_events_on_ledger_all_time": settlement_like,
            "basis": "declared intervention cost estimates and the Gate's expected-vs-actual reconciliation flags",
            "note": "estimates are not money moved; no payment, settlement or bank record exists in this report",
        }

        # -- retention and learning ----------------------------------------------------------------------------------
        retentions = [p["retention"] for p in (r.payload for r in by(AsymmetryRetention.ASSET_RECORD))
                      if within(p.get("retention", {}).get("retained_at"))]
        assets_by_kind: Counter = Counter(a["kind"] for rt in retentions for a in rt["assets"])
        retained = {
            "retentions": len(retentions),
            "assets_by_kind": dict(sorted(assets_by_kind.items())),
            "capabilities_registered": sorted({c for rt in retentions for c in rt["capabilities_registered"]}),
            "goals_made_cheaper": sorted({g for rt in retentions for g in rt["goals_made_cheaper"]}),
            "what_worked": sorted({w for rt in retentions for w in rt["what_worked"]}),
            "new_options": sorted({o for rt in retentions for o in rt.get("new_options", ())}),
        }
        experiences = [p["experience"] for p in (r.payload for r in by(WorldModel.EXPERIENCE_RECORD))
                       if within(p.get("experience", {}).get("integrated_at"))]
        changes = [c for e in experiences for c in e.get("changes", ())]
        contradictions = [p for p in (r.payload for r in by(WorldModel.CONTRADICTION_RECORD)) if within(p.get("detected_at"))]
        fixes_by_goal: dict[str, list[dict[str, Any]]] = {}
        for p in (r.payload["fix"] for r in by(BackcastGPSAdapter.GPS_RECORD)):
            if upto(p.get("fixed_at")):
                fixes_by_goal.setdefault(p["goal_id"], []).append(p)
        node_advances = 0
        for fixes in fixes_by_goal.values():
            for previous, current in zip(fixes, fixes[1:]):
                if within(current["fixed_at"]) and previous["active_node_id"] != current["active_node_id"]:
                    node_advances += 1
        completed_in_window = sorted({p["goal_id"] for p in (r.payload for r in by(GoalRegistry.TRANSITION_RECORD))
                                      if p.get("state", {}).get("status") == "completed"
                                      and within(p.get("state", {}).get("last_reviewed_at"))})
        learned = {
            "experiences_integrated": len(experiences),
            "beliefs_updated": sum(1 for c in changes if c.get("updated")),
            "beliefs_corroborated": sum(1 for c in changes if c.get("disposition") == "corroborated"),
            "contradictions_retained": len(contradictions),
            "gps_fixes": sum(1 for fixes in fixes_by_goal.values() for f in fixes if within(f["fixed_at"])),
            "plan_nodes_advanced": node_advances,
            "goals_completed": completed_in_window,
            "independent_verifications": len(verifications),
            "muted_signals_not_integrated": sum(1 for r in by(loop.MUTED_RECORD) if within(r.payload.get("at"))),
            "reserved_source_refusals": sum(1 for r in by(loop.RESERVED_SOURCE_RECORD) if within(r.payload.get("at"))),
            "institutional_learning_all_time": canonical_copy(loop.memory.institutional_learning()),
        }

        # -- deficits, intersections, advancement, capability lifecycle --------------------------------------------
        deficit_classes = Counter(r.payload["class"] for r in by(loop.DEFICIT_CLASS_RECORD) if within(r.payload.get("at")))
        typed = [r.payload["deficit"] for r in by(InterventionClassifier.DEFICIT_RECORD) if r.payload.get("deficit")]
        deficits = {
            "recorded_by_class": dict(sorted(deficit_classes.items())),
            "typed_capability_deficits_opened": sum(1 for d in typed if d.get("disposition") == "goal_blocked_not_closed"
                                                    and within(d.get("detected_at"))),
            "typed_capability_deficits_resolved": sum(1 for d in typed if d.get("disposition") == "resolved_resume_original_goal"
                                                      and within(d.get("resolved_at"))),
        }
        intersections = sorted(({"goal_id": p["report"]["goal_id"], "score": p["report"]["score"],
                                 "domains": list(p["report"]["domains"]), "at": p["report"]["detected_at"]}
                                for p in (r.payload for r in by(FavorableIntersectionDetector.INTERSECTION_RECORD))
                                if within(p.get("report", {}).get("detected_at"))),
                               key=lambda o: (o["at"], o["goal_id"]))
        packages = sorted(({"package_id": p["package_id"], "goal_id": p["goal_id"], "score": p["score"], "at": p["packaged_at"],
                            "options": len(p.get("options", ()))}
                           for p in (r.payload for r in by(OpportunityPackager.PACKAGE_RECORD)) if within(p.get("packaged_at"))),
                          key=lambda o: (o["at"], o["goal_id"]))
        reports = [p for p in (r.payload for r in by(AdvancementMonitor.REPORT_RECORD)) if within(p.get("reported_at"))]
        resolved = [p for p in (r.payload for r in by(AdvancementMonitor.RESOLUTION_RECORD)) if within(p.get("recorded_at"))]
        advancement = {
            "stall_or_lateness_reports": len(reports),
            "main_friction": dict(sorted(Counter(p["main_friction"] for p in reports).items())),
            "stalls_resolved": len(resolved),
            "mean_resolution_latency_seconds": (sum(p["latency_seconds"] for p in resolved) / len(resolved)) if resolved else None,
        }
        lifecycle = {
            "acquisition_plans": sum(1 for r in by(CapabilityAcquisition.PLAN_RECORD) if within(_time(r.payload))),
            "qualifications": sum(1 for r in by(CapabilityAcquisition.QUALIFICATION_RECORD) if within(_time(r.payload))),
            "attachments": sum(1 for r in by(CapabilityAcquisition.ATTACH_RECORD) if within(_time(r.payload))),
            "detachments": sum(1 for r in by(CapabilityAcquisition.DETACH_RECORD) if within(_time(r.payload))),
            "note": "counted when the record carries a logical time field",
        }

        # -- goals ----------------------------------------------------------------------------------------------------
        per_goal = []
        for goal_id in registry.goals():
            spec = registry.get(goal_id)
            state = registry.state(goal_id)
            transitions = [p["state"]["status"] for p in (r.payload for r in by(GoalRegistry.TRANSITION_RECORD))
                           if p["goal_id"] == goal_id and within(p.get("state", {}).get("last_reviewed_at"))]
            statuses_seen = list(dict.fromkeys(transitions))
            per_goal.append({
                "goal_id": goal_id, "founder_intent": spec.founder_intent, "desired_state": spec.desired_state,
                "priority": registry.effective_priority(goal_id), "status_now": state.status,
                "active_gate_now": state.active_gate, "single_bottleneck_metric_now": (state.sbm or {}).get("name"),
                "blockers_now": len(state.blockers),
                "authorized_in_window": any(p["goal"]["goal_id"] == goal_id for p in authorizations_in_window),
                "turns_processed": sum(1 for p in processed if p["goal_id"] == goal_id),
                "statuses_in_window": statuses_seen,
                "executed": sum(1 for e in executed if e["goal_id"] == goal_id),
                "prepared": sum(1 for p in prepared if p["goal_id"] == goal_id),
                "refused_by_gate": sum(1 for p in refused if p["goal_id"] == goal_id),
                "open_attempts": sum(1 for o in open_attempts if o["goal_id"] == goal_id),
                "decisions_waiting": sum(1 for w in waiting if w["goal_id"] == goal_id),
                "deficits_recorded": sum(1 for r in by(loop.DEFICIT_CLASS_RECORD)
                                         if r.payload["goal_id"] == goal_id and within(r.payload.get("at"))),
            })
        active = [g for g in per_goal if g["turns_processed"] or g["statuses_in_window"]]
        goals = {
            "total": len(per_goal),
            "active_in_window": len(active),
            "by_status_now": dict(sorted(Counter(g["status_now"] for g in per_goal).items())),
            "touched": touched,
            "per_goal": per_goal,
        }

        # -- evidence tier --------------------------------------------------------------------------------------------
        ok, _chain = ledger.verify_chain()   # the detail string counts records and would change with this report's own record
        tier = {
            "basis": "ledger records with logical time inside the window; nothing estimated from memory",
            "ledger_chain_intact": ok,
            "executed_moves_with_receipts": sum(1 for e in executed if e["receipt_hash"]),
            "externally_verified_moves": sum(1 for e in executed if (e["verification"] or {}).get("verdict") == "confirmed"),
            "executor_claims_counted_as_verification": False,
            "prepared_counted_as_executed": False,
            "note": "whether any receipt touched reality depends on the executors and verifiers behind it; this report "
                    "cannot certify that and does not",
        }

        body = {
            "kind": "information", "requests_nothing": True,
            "window": {"since": iso(start), "until": iso(end), "seconds": (end - start).total_seconds()},
            "founder_activity": founder_activity,
            "goals": goals,
            "turns": turn_stats,
            "executed": executed,
            "prepared": prepared,
            "refused_by_gate": refused,
            "withheld_by_classifier": {k: decisions_by_kind.get(k, 0) for k in ("REQUEST_EVIDENCE", "WAIT", "ABSTAIN")},
            "attempted_in_window": attempted_in_window,
            "open_attempts_as_of_until": open_attempts,
            "reconciliations": reconciliations,
            "discrepancies": discrepancies,
            "verifications": verifications,
            "decisions_waiting_as_of_until": waiting,
            "deferred_as_of_until": deferred,
            "information_items_in_window": information_in_window,
            "money": money,
            "retained": retained,
            "learned": learned,
            "deficits": deficits,
            "intersections": {"favorable_detected": intersections, "opportunity_packages": packages},
            "advancement": advancement,
            "capability_lifecycle": lifecycle,
            "evidence_tier": tier,
            "execution_authority": "none",
        }
        body["headline"] = self._headline(body)
        return canonical_copy(body)

    # ------------------------------------------------------------ headline
    @staticmethod
    def _headline(body: Mapping[str, Any]) -> list[str]:
        """Deterministic sentences, each emitted only when its facts exist; nothing is requested."""
        g, t, m, r, l, d = body["goals"], body["turns"], body["money"], body["retained"], body["learned"], body["discrepancies"]
        lines: list[str] = []
        if not t["count"] and not body["executed"] and not body["prepared"] and not body["decisions_waiting_as_of_until"]:
            lines.append("Nothing happened in this window: no turn ran, nothing executed, nothing was prepared, "
                         "nothing waits for you.")
        else:
            lines.append(f"{g['active_in_window']} of {g['total']} authorized goal(s) were active: {t['goals_processed']} "
                         f"goal-processing(s) across {t['count']} turn(s); {t['signals_integrated']} signal(s) and "
                         f"{t['derived_readings']} derived reading(s) integrated.")
            lines.append(f"{len(body['executed'])} move(s) executed through the Consequence Gate with receipts; "
                         f"{len(body['prepared'])} prepared for you and not executed; {len(body['refused_by_gate'])} refused by "
                         f"the Gate or policy at commit.")
        if body["open_attempts_as_of_until"]:
            lines.append(f"{len(body['open_attempts_as_of_until'])} dispatched move(s) have an unknown outcome and wait for "
                         f"reconciliation; none will be retried blindly.")
        if body["executed"]:
            lines.append(f"Estimated cost of executed moves: ${m['estimated_cost_usd_executed']:.2f} (declared estimates; "
                         f"{m['executed_moves_reconciled']} reconciled against the expected outcome, "
                         f"{m['executed_moves_unreconciled']} not). No settlement record exists; this is not a bank statement.")
        if body["decisions_waiting_as_of_until"] or body["information_items_in_window"]:
            lines.append(f"{len(body['decisions_waiting_as_of_until'])} decision(s) exceed delegated authority and wait for you; "
                         f"{len(body['information_items_in_window'])} information item(s) were batched. This report requests nothing.")
        if r["retentions"]:
            lines.append(f"{r['retentions']} durable asset record(s) retained ({sum(r['assets_by_kind'].values())} asset(s); "
                         f"{len(r['capabilities_registered'])} reusable capability(ies) registered; "
                         f"{len(r['goals_made_cheaper'])} goal(s) made cheaper).")
        if d["recorded_in_window"] or d["unreviewed_as_of_until"]:
            lines.append(f"{len(d['recorded_in_window'])} outcome discrepancy(ies) recorded; {d['unreviewed_as_of_until']} "
                         f"unreviewed; the affected goals stay blocked until an accountable review.")
        if t["count"]:
            lines.append(f"The institution learned: {l['beliefs_updated']} belief update(s), {l['contradictions_retained']} "
                         f"contradiction(s) retained side by side, {l['plan_nodes_advanced']} plan node(s) advanced, "
                         f"{l['independent_verifications']} independent verification(s).")
        fa = body["founder_activity"]
        if fa["away"]:
            lines.append("You answered nothing in this window; everything above happened under standing authority or was prepared.")
        else:
            lines.append(f"You acted {fa['answers']} answer(s), {fa['preferences_or_refusals']} preference(s), "
                         f"{fa['goals_authorized']} authorization(s) in this window.")
        tier = body["evidence_tier"]
        lines.append(f"Evidence: ledger-derived ({'chain intact' if tier['ledger_chain_intact'] else 'CHAIN BROKEN'}); "
                     f"{tier['externally_verified_moves']} move(s) externally verified; executor claims are not verification.")
        return lines
