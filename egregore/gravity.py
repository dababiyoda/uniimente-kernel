"""Goal Gravity loop: the composition that makes authorized goals attractors.

    Sense -> Experience -> Backcast -> Detect Gate -> Manufacture Leverage
    -> Execute/Prepare/Escalate -> Create Favorable Intersection -> Verify
    -> Compound -> Recalculate -> Repeat

This module composes the existing canonical machinery (Evidence Ledger,
standing cognition signals, policy engine, Consequence Gate, Capability
Genome registry) with the goal registry, world model, relevance router,
GPS adapter, intervention classifier, intersection detector, retention and
attention router. It introduces no second Kernel, mission authority plane,
identity plane or evidence plane:

* goals are data on the one ledger;
* every executed move goes through ``ConsequenceGate.run`` with a
  pre-existing grant supplied by the caller; the loop holds none;
* a turn is idempotent per ``trigger_id`` and hydrates from the ledger, so
  a restart never duplicates a consequential action;
* dormant goals cost nothing; a hibernating resource governor processes
  no goal at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence

from .attention import AttentionItem, AttentionPolicy, FounderAttentionRouter, Routing
from .contracts import ContractError, IntegrityConflict, SignalEnvelope, canonical_copy, digest, require_text
from .experience import WorldModel
from .goals import CONSEQUENCE_CLASSES, GoalRegistry, GoalSpec, GoalState, InterventionSpec, iso, parse_time
from .gps import BackcastGPSAdapter, GPSFix
from .intersections import FavorableIntersectionDetector, IntersectionReport
from .interventions import Classification, InterventionClassifier
from .relevance import GoalRelevanceRouter
from .resources import ResourceGovernor, ResourceMode
from .retention import AsymmetryRetention, DurableAsset

TURN_STATUSES = ("silent", "advanced", "hibernating", "conserving")


@dataclass(frozen=True)
class GravityTurn:
    turn_id: str
    trigger_id: str
    request_hash: str
    status: str
    at: str
    signal_ids: tuple[str, ...]
    woken: tuple[str, ...]
    processed: tuple[dict[str, Any], ...]
    executed: tuple[dict[str, Any], ...]
    prepared: tuple[dict[str, Any], ...]
    escalated: tuple[dict[str, Any], ...]
    routing: dict[str, Any]
    resource_snapshot: dict[str, Any]
    experience_surface: dict[str, Any]

    @property
    def execution_authority(self) -> str:
        return "none"

    def to_dict(self) -> dict[str, Any]:
        return canonical_copy({
            "turn_id": self.turn_id, "trigger_id": self.trigger_id, "request_hash": self.request_hash,
            "status": self.status, "at": self.at, "signal_ids": list(self.signal_ids), "woken": list(self.woken),
            "processed": list(self.processed), "executed": list(self.executed), "prepared": list(self.prepared),
            "escalated": list(self.escalated), "routing": self.routing, "resource_snapshot": self.resource_snapshot,
            "experience_surface": self.experience_surface, "execution_authority": "none"})

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "GravityTurn":
        return cls(turn_id=value["turn_id"], trigger_id=value["trigger_id"], request_hash=value["request_hash"],
                   status=value["status"], at=value["at"], signal_ids=tuple(value["signal_ids"]),
                   woken=tuple(value["woken"]), processed=tuple(value["processed"]), executed=tuple(value["executed"]),
                   prepared=tuple(value["prepared"]), escalated=tuple(value["escalated"]),
                   routing=canonical_copy(value["routing"]), resource_snapshot=canonical_copy(value["resource_snapshot"]),
                   experience_surface=canonical_copy(value["experience_surface"]))


class GoalGravityLoop:
    TURN_RECORD = "egregore.gravity_turn"
    TURN_CONFLICT_RECORD = "egregore.gravity_turn_conflict"
    INTERVENTION_RECORD = "egregore.intervention"
    PREPARED_RECORD = "egregore.prepared_work"
    DRIFT_RECORD = "egregore.goal_drift"

    def __init__(self, *, ledger: Any, compiled: Any, passports: Any, actor: str, legal_principal: str,
                 genomes: Any = None, cognition: Any = None, attention_policy: AttentionPolicy | None = None,
                 source: str = "spiffe://uniimente.internal/egregore/goal-gravity"):
        if not hasattr(ledger, "append") or not hasattr(ledger, "by_type"):
            raise ContractError("ledger must provide append() and by_type()")
        self.ledger = ledger
        self.source = require_text("source", source)
        self.registry = GoalRegistry(ledger=ledger, source=source)
        self.world = WorldModel(ledger=ledger, source=source)
        self.genomes = genomes
        self.cognition = cognition
        self.router = GoalRelevanceRouter(self.registry)
        self.gps = BackcastGPSAdapter(ledger=ledger, world=self.world, genomes=genomes, source=source)
        self.classifier = InterventionClassifier(ledger=ledger, registry=self.registry, compiled=compiled,
                                                 passports=passports, actor=actor, legal_principal=legal_principal,
                                                 source=source)
        self.detector = FavorableIntersectionDetector(ledger=ledger, world=self.world, source=source)
        self.retention = AsymmetryRetention(ledger=ledger, registry=self.registry, genomes=genomes, source=source) if genomes is not None else None
        self.attention = FounderAttentionRouter(ledger=ledger, registry=self.registry, policy=attention_policy, source=source)
        self._turns: dict[str, GravityTurn] = {}
        self._interventions: list[dict[str, Any]] = []
        for record in getattr(ledger, "records", ()):
            rtype = getattr(record, "record_type", None)
            if rtype == self.TURN_RECORD:
                turn = GravityTurn.from_dict(record.payload["turn"])
                self._turns[turn.trigger_id] = turn
            elif rtype == self.INTERVENTION_RECORD:
                self._interventions.append(canonical_copy(record.payload))

    @property
    def execution_authority(self) -> str:
        return "none"

    # ------------------------------------------------------------ helpers
    def _record_intervention(self, goal_id: str, intervention: InterventionSpec, classification: Classification,
                             *, evidence_state: str, detail: Mapping[str, Any] | None = None, now: str) -> dict[str, Any]:
        payload = {"source": self.source, "goal_id": goal_id, "intervention": intervention.to_dict(),
                   "classification_id": classification.classification_id, "decision": classification.decision,
                   "evidence_state": evidence_state, "detail": canonical_copy(dict(detail or {})), "at": now}
        self.ledger.append(self.INTERVENTION_RECORD, payload)
        self._interventions.append(canonical_copy(payload))
        return payload

    def _already_attempted(self, goal_id: str, route_hash: str) -> dict[str, Any] | None:
        for item in reversed(self._interventions):
            if item["goal_id"] == goal_id and item["intervention"]["route_hash"] == route_hash:
                if item["evidence_state"] in ("attempted", "executed", "externally_verified", "unknown"):
                    return item
        return None

    @staticmethod
    def _marginal_value(spec: GoalSpec, intervention: InterventionSpec, priority: int) -> float:
        """Attention leverage: higher priority and higher consequence => more value in asking."""
        consequence = CONSEQUENCE_CLASSES.index(intervention.consequence_class) / (len(CONSEQUENCE_CLASSES) - 1)
        return round(min(1.0, 0.35 + 0.4 * ((6 - priority) / 5) + 0.25 * consequence), 3)

    def _ask_for(self, spec: GoalSpec, intervention: InterventionSpec, classification: Classification,
                 *, kind: str, urgency: str, now: str, fix: GPSFix) -> AttentionItem:
        priority = self.registry.effective_priority(spec.goal_id)
        return AttentionItem.build(
            goal_id=spec.goal_id, kind=kind, urgency=urgency,
            marginal_value=self._marginal_value(spec, intervention, priority),
            title=f"{spec.desired_state[:60]}: {intervention.description[:60]}",
            question=f"Gate '{fix.active_gate}' is active. GREG prepared '{intervention.description}' "
                     f"({intervention.consequence_class}). Reasons: {'; '.join(classification.reasons)}. Proceed?",
            options=({"label": "authorize this move", "cost": f"{intervention.estimated_cost_usd} USD estimated"},
                     {"label": "revise the route", "cost": "none"},
                     {"label": "do nothing now", "cost": "none"}),
            recommendation="authorize if the evidence below is sufficient; otherwise revise",
            evidence_refs=tuple(self.registry.state(spec.goal_id).evidence_refs[-5:]),
            effort_estimate="one decision; no further action required from you unless you choose to act",
            category=intervention.consequence_class, created_at=now,
            route_hash=intervention.route_hash, tactic=intervention.tactic or None)

    def drift_report(self, goal_id: str) -> dict[str, Any]:
        """Observed execution versus the authorized plan: unknown routes are visible drift."""
        spec = self.registry.get(goal_id)
        planned = {i.route_hash[:23] for n in spec.plan for i in n.interventions}
        prefix = f"egregore:goal:{goal_id[:23]}:"
        observed, drifted = [], []
        for record in self.ledger.by_type("event"):
            p = record.payload
            if p.get("type") == "action.committed" and str(p.get("proposal_id", "")).startswith(prefix):
                route = p["proposal_id"][len(prefix):]
                observed.append(route)
                if route not in planned:
                    drifted.append(route)
        return {"goal_id": goal_id, "observed_routes": observed, "drifted_routes": drifted, "drift": bool(drifted)}

    # ------------------------------------------------------------ the loop
    def turn(self, *, trigger_id: str, now: datetime | str, signals: Sequence[SignalEnvelope] = (),
             resources: ResourceGovernor, grants: Mapping[str, Mapping[str, Any]] | None = None,
             gate: Any = None, executor: Callable[[Any], dict] | None = None,
             evidence_confidence: float = 0.0) -> GravityTurn:
        trigger_id = require_text("trigger_id", trigger_id)
        if not isinstance(resources, ResourceGovernor):
            raise ContractError("resources must be a ResourceGovernor")
        at = iso(parse_time(now))
        grants = {k: canonical_copy(dict(v)) for k, v in (grants or {}).items()}
        ordered_signals = tuple(sorted({s.signal_id: s for s in signals}.values(), key=lambda s: s.signal_id))
        request_hash = digest({"kind": "egregore-gravity-request", "trigger_id": trigger_id, "at": at,
                               "signal_ids": [s.signal_id for s in ordered_signals],
                               "grant_ids": sorted(g.get("grant_id", "") for g in grants.values()),
                               "resource_limits": {"max_model_calls": resources.max_model_calls,
                                                   "max_estimated_cost_usd": resources.max_estimated_cost_usd}})
        existing = self._turns.get(trigger_id)
        if existing is not None:
            if existing.request_hash == request_hash:
                return GravityTurn.from_dict(existing.to_dict())
            self.ledger.append(self.TURN_CONFLICT_RECORD, {"source": self.source, "trigger_id": trigger_id,
                                                           "accepted_request_hash": existing.request_hash,
                                                           "conflicting_request_hash": request_hash,
                                                           "disposition": "refused_and_retained"})
            raise IntegrityConflict("trigger_id was reused for a different gravity request")

        # 1. Sense -> Experience: every signal becomes a provenance-backed experience.
        wake_requests: dict[str, list[str]] = {}
        touched_keys: set[str] = set()
        for signal in ordered_signals:
            if self.cognition is not None:
                self.cognition.ingest(signal)
            observations = self.world.observations_from_signal(signal)
            touched_keys.update(o.key for o in observations)
            verdicts = self.router.route(signal, observations=observations)
            self.world.integrate(signal, now=at, goal_relevance={g: v.score for g, v in verdicts.items()},
                                 context={"trigger_id": trigger_id})
            for goal_id, verdict in verdicts.items():
                if verdict.wake:
                    wake_requests.setdefault(goal_id, []).append(signal.signal_id)
        # Individually weak signals may still combine: a favorable intersection wakes a goal.
        intersection_wakes: dict[str, float] = {}
        if resources.mode is not ResourceMode.HIBERNATE:
            for goal_id in self.registry.goals():
                if goal_id in wake_requests:
                    continue
                spec = self.registry.get(goal_id)
                state = self.registry.state(goal_id)
                if not spec.opportunity_factors or state.status not in ("dormant", "blocked") or state.preferences.get("stop_pushing"):
                    continue
                if not any(f"{f.subject}.{f.attribute}" in touched_keys for f in spec.opportunity_factors):
                    continue
                report = self.detector.detect(spec, now=at)
                if report.favorable:
                    intersection_wakes[goal_id] = report.score

        # 2. Wake: relevant evidence or cadence; never when hibernating.
        woken: list[str] = []
        if resources.mode is not ResourceMode.HIBERNATE:
            for goal_id, signal_ids in wake_requests.items():
                state = self.registry.state(goal_id)
                if state.status != "awake":
                    self.registry.wake(goal_id, reason=f"relevant evidence: {len(signal_ids)} signal(s)", now=at, signal_ids=signal_ids)
                woken.append(goal_id)
            for goal_id, score in intersection_wakes.items():
                self.registry.wake(goal_id, reason=f"favorable intersection (score={score:.2f})", now=at)
                woken.append(goal_id)
            for goal_id in self.registry.due_for_review(at):
                if goal_id not in woken:
                    self.registry.wake(goal_id, reason="review cadence elapsed", now=at)
                    woken.append(goal_id)
            for goal_id in self.registry.by_status("awake"):
                if goal_id not in woken:
                    woken.append(goal_id)
        woken.sort(key=lambda g: (self.registry.effective_priority(g), g))
        if resources.mode is ResourceMode.CONSERVE:
            woken = [g for g in woken if self.registry.effective_priority(g) <= 2]

        processed, executed, prepared, escalated, items = [], [], [], [], []
        for goal_id in woken:
            spec = self.registry.get(goal_id)
            state = self.registry.state(goal_id)
            summary: dict[str, Any] = {"goal_id": goal_id, "priority": self.registry.effective_priority(goal_id)}
            # 3. Backcast -> active gate -> SBM.
            fix = self.gps.fix(spec, state, now=at)
            summary.update({"active_node_id": fix.active_node_id, "active_gate": fix.active_gate, "sbm": fix.sbm,
                            "missing_capabilities": list(fix.missing_capabilities), "complete": fix.complete})
            if fix.complete:
                self.registry.transition(goal_id, reason="all plan nodes satisfied by observed evidence", now=at,
                                         status="completed", current_state=fix.current_position,
                                         active_node_id=None, active_gate=None, sbm=None, blockers=[])
                summary["decisions"] = []
                processed.append(summary)
                continue
            # 4. Favorable intersections are observed, never acted on directly.
            report: IntersectionReport | None = None
            if spec.opportunity_factors:
                report = self.detector.detect(spec, now=at)
                summary["intersection"] = {"score": report.score, "favorable": report.favorable,
                                           "domains": list(report.domains)}
            # 5. Drift is made visible before any new move.
            drift = self.drift_report(goal_id)
            if drift["drift"]:
                self.ledger.append(self.DRIFT_RECORD, {"source": self.source, **drift, "at": at,
                                                       "disposition": "discrepancy_visible_not_hidden"})
                summary["drift"] = drift["drifted_routes"]
            # 6. Classify every candidate move; execute at most one, through the Gate only.
            decisions: list[dict[str, Any]] = []
            blockers = list(fix.blockers)
            executed_this_goal = False
            for raw in fix.next_interventions:
                intervention = InterventionSpec.from_dict(raw)
                grant = grants.get(intervention.requested_capability)
                grant_view = None
                if grant is not None and gate is not None and hasattr(gate, "grants"):
                    stage = gate.grants.get_meta(grant.get("grant_id", "")).get("stage")
                    grant_view = {**grant, "stage": stage} if stage else grant
                classification = self.classifier.classify(
                    spec, state, intervention, fix=fix, grant=grant, grant_view=grant_view,
                    evidence_refs=list(state.evidence_refs) or [f"goal:{goal_id}"],
                    evidence_confidence=evidence_confidence, now=at)
                entry = {"intervention_id": intervention.intervention_id, "decision": classification.decision,
                         "reasons": list(classification.reasons)}
                if classification.decision == "EXECUTE_AUTONOMOUSLY":
                    prior = self._already_attempted(goal_id, intervention.route_hash)
                    if prior is not None:
                        entry["evidence_state"] = prior["evidence_state"]
                        entry["note"] = "already attempted; no duplicate consequential action"
                    elif executed_this_goal or gate is None or executor is None:
                        self._record_intervention(goal_id, intervention, classification, evidence_state="planned",
                                                  detail={"note": "execution deferred: one move per goal per turn, or no gate/executor supplied"}, now=at)
                        entry["evidence_state"] = "planned"
                    else:
                        proposal = self.classifier.proposal_for(spec, intervention, evidence_refs=list(state.evidence_refs) or [f"goal:{goal_id}"],
                                                                evidence_confidence=evidence_confidence)
                        self._record_intervention(goal_id, intervention, classification, evidence_state="attempted",
                                                  detail={"proposal_id": proposal.proposal_id}, now=at)
                        try:
                            action = gate.run(proposal, executor=executor, standing_grant=grant)
                        except Exception as exc:  # the attempt is retained; nothing is retried blindly
                            self._record_intervention(goal_id, intervention, classification, evidence_state="unknown",
                                                      detail={"error": f"{type(exc).__name__}: {exc}"[:200]}, now=at)
                            entry["evidence_state"] = "unknown"
                            blockers.append("gate outcome unknown; reconciliation required")
                            executed_this_goal = True
                            decisions.append(entry)
                            continue
                        if action.state == "recorded":
                            validation = (action.outcome or {}).get("validation_status")
                            evidence_state = "externally_verified" if validation == "externally_verified" else "executed"
                            detail = {"action_id": action.action_id, "receipt_hash": action.receipt_hash,
                                      "outcome_id": (action.outcome or {}).get("outcome_id"),
                                      "result_class": (action.outcome or {}).get("result_class")}
                            self._record_intervention(goal_id, intervention, classification, evidence_state=evidence_state, detail=detail, now=at)
                            refs = list(state.evidence_refs) + [action.receipt_hash]
                            state.evidence_refs = refs
                            executed.append({"goal_id": goal_id, **detail, "evidence_state": evidence_state})
                            entry["evidence_state"] = evidence_state
                            if self.retention is not None and detail["result_class"] == "positive":
                                self.retention.retain(goal_id=goal_id, outcome_ref=detail["outcome_id"],
                                                      what_worked=[intervention.description],
                                                      assets=[DurableAsset.build(kind="evidence", name=f"receipt:{action.receipt_hash[:19]}",
                                                                                 description=f"verified receipt for {intervention.description}",
                                                                                 evidence_refs=[action.receipt_hash])], now=at)
                        elif action.state == "reconciliation_required":
                            self._record_intervention(goal_id, intervention, classification, evidence_state="unknown",
                                                      detail={"action_id": action.action_id, "reasons": action.refusal_reasons}, now=at)
                            entry["evidence_state"] = "unknown"
                            blockers.append("gate outcome unknown; reconciliation required")
                        else:
                            self._record_intervention(goal_id, intervention, classification, evidence_state="failed",
                                                      detail={"action_id": action.action_id, "state": action.state,
                                                              "reasons": action.refusal_reasons}, now=at)
                            entry["evidence_state"] = "failed"
                            blockers.append(f"gate {action.state}: {'; '.join(action.refusal_reasons)[:160]}")
                        executed_this_goal = True
                elif classification.decision in ("PREPARE_FOR_FOUNDER", "ESCALATE"):
                    package = {"source": self.source, "goal_id": goal_id, "intervention": intervention.to_dict(),
                               "classification_id": classification.classification_id, "fix_hash": fix.fix_hash,
                               "reasons": list(classification.reasons), "prepared_at": at,
                               "disposition": "prepared_not_executed"}
                    self.ledger.append(self.PREPARED_RECORD, package)
                    self._record_intervention(goal_id, intervention, classification, evidence_state="planned",
                                              detail={"prepared": True}, now=at)
                    prepared.append({"goal_id": goal_id, "intervention_id": intervention.intervention_id,
                                     "decision": classification.decision})
                    urgency = "high" if classification.decision == "ESCALATE" else "normal"
                    items.append(self._ask_for(spec, intervention, classification, kind="decision", urgency=urgency, now=at, fix=fix))
                    if classification.decision == "ESCALATE":
                        escalated.append({"goal_id": goal_id, "intervention_id": intervention.intervention_id})
                    entry["evidence_state"] = "planned"
                elif classification.decision == "REQUEST_EVIDENCE":
                    self._record_intervention(goal_id, intervention, classification, evidence_state="planned",
                                              detail={"missing": list(classification.missing)}, now=at)
                    blockers.append(f"evidence below floor for {intervention.consequence_class}")
                    entry["evidence_state"] = "planned"
                elif classification.decision == "WAIT":
                    blockers.extend(f"capability deficit: {c}" for c in fix.missing_capabilities)
                    entry["evidence_state"] = "planned"
                else:  # ABSTAIN
                    entry["evidence_state"] = "planned"
                decisions.append(entry)
            summary["decisions"] = decisions
            blocked = bool(fix.missing_capabilities) or any("evidence below floor" in b or "unknown" in b for b in blockers)
            self.registry.transition(goal_id, reason="gravity turn processed", now=at,
                                     status="blocked" if blocked else "dormant",
                                     current_state=fix.current_position, active_node_id=fix.active_node_id,
                                     active_gate=fix.active_gate, sbm=fix.sbm, blockers=sorted(set(blockers)),
                                     missing_capabilities=list(fix.missing_capabilities),
                                     evidence_refs=list(state.evidence_refs))
            processed.append(summary)

        # 7. Protect attention: route asks by leverage, dedupe, batch.
        routing: Routing = self.attention.route(items, now=at)
        if resources.mode is ResourceMode.HIBERNATE:
            status = "hibernating"
        elif resources.mode is ResourceMode.CONSERVE:
            status = "conserving"
        elif processed:
            status = "advanced"
        else:
            status = "silent"
        turn = GravityTurn(
            turn_id=digest({"kind": "egregore-gravity-turn", "trigger_id": trigger_id}), trigger_id=trigger_id,
            request_hash=request_hash, status=status, at=at, signal_ids=tuple(s.signal_id for s in ordered_signals),
            woken=tuple(woken), processed=tuple(processed), executed=tuple(executed), prepared=tuple(prepared),
            escalated=tuple(escalated), routing=routing.to_dict(), resource_snapshot=resources.snapshot().to_dict(),
            experience_surface=self.world.experience_surface(goals=[self.registry.get(g) for g in self.registry.goals()], now=at))
        self.ledger.append(self.TURN_RECORD, {"source": self.source, "turn": turn.to_dict(), "disposition": "proposal_only"})
        self._turns[trigger_id] = GravityTurn.from_dict(turn.to_dict())
        return turn

    # ------------------------------------------------------------ founder surface
    def founder_answer(self, item_id: str, *, decision: str, actor: str, note: str, now: datetime | str) -> dict[str, Any]:
        return self.attention.answer(item_id, decision=decision, actor=actor, note=note, now=now)

    def status(self, goal_id: str, *, now: datetime | str) -> dict[str, Any]:
        """The founder-facing compression of section 27: where things stand, in one read."""
        spec = self.registry.get(goal_id)
        state = self.registry.state(goal_id)
        fix = self.gps.fix(spec, state, now=now, record=False)
        open_asks = [a for a in self.attention.open_asks() if a["goal_id"] == goal_id]
        prepared = [r.payload for r in self.ledger.by_type(self.PREPARED_RECORD) if r.payload["goal_id"] == goal_id]
        interventions = [i for i in self._interventions if i["goal_id"] == goal_id]
        latest = {}
        for i in interventions:
            latest[i["intervention"]["route_hash"]] = i["evidence_state"]
        return {
            "goal_id": goal_id, "founder_intent": spec.founder_intent, "desired_state": spec.desired_state,
            "status": state.status, "priority": self.registry.effective_priority(goal_id),
            "current_position": fix.current_position, "active_node": fix.active_node_id, "active_gate": fix.active_gate,
            "single_bottleneck_metric": fix.sbm, "exit_evidence": list(fix.exit_evidence),
            "relevant_environmental_signals": [e.signal_id for e in self.world.experiences() if goal_id in e.goal_relevance],
            "available_capabilities": [c for n in spec.plan for c in n.requires_capabilities if c not in fix.missing_capabilities],
            "missing_capabilities": list(fix.missing_capabilities),
            "next_autonomous_work": [i for i in fix.next_interventions if self.registry.state(goal_id).status != "paused"],
            "prepared_work": [p["intervention"]["intervention_id"] for p in prepared],
            "founder_required_decisions": [a["item_id"] for a in open_asks],
            "evidence_state": latest, "blockers": list(state.blockers),
            "review_trigger": f"relevant signal or every {spec.review_cadence_seconds} seconds",
            "drift": self.drift_report(goal_id)["drift"], "execution_authority": "none",
        }
